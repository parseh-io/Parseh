#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A book or a video as one file: take it away, edit it by hand, put it back.

    from bundle import pack_book, pack_video, inspect, install
    data, name = pack_book("books/persian/farsi-shakar-ast")  # zip bytes, filename
    what = inspect(data)                     # what is in it; nothing is written
    done = install(data, replace=False)      # into the toolbox, or a refusal

Everything a learner reads here is written by hand, and a textarea in a
browser is not where a person renames a character through fifteen paragraphs
or lines a column of transliterations up in a spreadsheet.  This is the other
way round the loop: one file out, the same file back, with the toolbox
refusing anything it cannot vouch for.

WHAT A BUNDLE CARRIES -- the authored files, and nothing else:

    a book     book.json, every top-level .tex but frankdraft.tex, NOTES.md,
               source/** (the .txt and .json the pipeline writes there),
               annot/** (the annotation JSON a book made by an agent was
               assembled from -- the record of how it was made), original/**
               (the text it was made from: a PDF, an epub or a text file) and
               markdown/** (the notes written into its seams -- in every
               shape, because they are part of the content), plus as much of
               the narration as the shape below asks for
    a video    video.json, annotations.json, transcript.txt, parts/*.json,
               waveform.json where one was recorded, markdown/** (its notes)

plus, at the root of the zip, the manifest below.  The tree sits under one
directory named after the slug or the id, so unzipping gives back a folder
with a name on it instead of twenty loose files in ~/Downloads.

THE THREE SHAPES OF A BOOK, asked for with `audio` and recorded in the
manifest.  A narration is not two files.  It is the recording
(audio/audio.webm, 219 MB on the book this was written for), its transcript,
timings.json, review.json and review-corrections.json, review.html, the two
book.json fields that name the first two -- and a `% @par` comment line above
every subparagraph of every chapter, which is the one a person forgets,
because it lives INSIDE a file the bundle carries whatever is asked for and
is what the reader actually reads the times out of (tex2html's load_times).

    text     the reading edition alone, with nothing left pointing at a
             recording: no timings, no review, book.json's audio and
             transcript nulled, the `% @par` lines gone.  What comes out is a
             book that reads as one that never had a narration -- not one
             claiming a narration it has not got, which is what the single
             download used to hand back.
    linked   everything except the recording itself: the timings, the review,
             the comments and the two fields all kept, so dropping audio/
             back in gives the full book again, file for file.  For somebody
             who already has the recording, and the shape to keep as a
             working copy, being the only one that leaves nothing behind.
    full     all of it, audio/ included, STORED rather than deflated (_pack).

`linked` is the default, and it is also what a manifest with no shape in it
means -- which every bundle written before this door had shapes is.  Both for
one reason: it is the only shape that leaves nothing out, so a caller that
does not choose cannot silently drop somebody's alignment, and a bundle
written before today installs today exactly as it did then.

A BOOK WITH NO NARRATION has nothing to leave out, so the three are ONE
bundle: the same bytes, the same filename, and no shape written into the
manifest at all -- which is also what keeps such a book's bundle byte for
byte the one this door made before it had shapes.  The choice is not
pretended to have mattered.

A VIDEO ON YOUTUBE HAS NO SHAPE and is not offered one: its media is an
address and never a file here, and its timestamps sync its own transcript
rather than pointing at a file that could be missing.  It packs to the bytes
it always did.

A VIDEO THAT IS A FILE ON THIS MACHINE has the same two words a narration
has, and the opposite default: `full` carries the film beside the glosses and
is what the download button asks for, `text` leaves it behind for somebody
who only wants the words.  A book without its recording is still the book; a
video without its film is a transcript of something the person unpacking it
cannot watch.

THE AGENT'S OWN FILES NEVER TRAVEL.  A book made by an agent in place
(lib/making.py) has AGENTS.md and CLAUDE.md, the asks in ASKS.md and the record
of the making in making.json beside it, the project skill in .claude/skills/ and
.agents/skills/, and perhaps a .claude/ the agent keeps its own settings in: they
are about one making on one machine, not about the
book, and the allowlist leaves them out on the way out and drops them on the
way in.  The original does travel -- the person's own source, in the book's own
folder, and not in others/, which no update keeps.

WHAT IS LEFT OUT, and why -- main.pdf has all three reasons at once.  It is
DERIVED (main.tex and the chapters make it, so a bundle holding it would
carry the same text twice), it is LARGE (a megabyte here, and the narration
beside it is hundreds), and carried back in stale it would LIE: whoever
opened it, or reader/index.html, would be shown text the .tex no longer
says, which is the one failure this door exists to prevent.  The same goes
for main.aux/.log/.toc, reader/ and .build-key/.reader-key -- the keys are
how build.sh knows a book has changed (they hash the .tex and book.json), so
a bundle carrying yesterday's key would tell the builder there was nothing to
do.  An install leaves the old keys where they are, which is the other half
of that rule: they no longer match the new text, so the next ./build.sh
rebuilds.

review.html is left out of all three shapes, and for none of those reasons:
it is a PAGE.  Everything under books/ is served as a static file, so a
bundle able to carry an .html could put a script of its own same-origin with
the reader, and the allowlist below is what stops it.  The one already in a
book is left where it stands, the way the PDF is.

Leaving the rest out is also what makes an upload safe to serve.  Everything
under books/ and youtube/videos/ is fetchable as a static file (serve.py's
STATIC_PREFIXES), so what an upload may put there is an allowlist -- the text
the doors already read -- and never a blocklist.  A bundle cannot install a
page, a script or a font of its own.  A note's pictures are the one place
that rule had to be thought about twice: a note is a studio document and can
have figures, so markdown/ carries images -- but not .svg, which is a
document that can carry a script and would land in exactly the place this
paragraph is about.  An SVG figure stays on the machine it was drawn on.

THE MANIFEST, parseh-bundle.json, is what makes an upload safe to reason
about: without it a zip of a folder is a guess.  Its fields are written (and
each is explained) in _manifest_for(); `format` is the only one install
believes on the bundle's word alone -- everything else it re-derives from the
files and refuses when the two disagree.

INSTALLING refuses, always with a sentence naming what to do about it:

    * a zip that is not a Parseh bundle, or a bundle of a format this
      toolbox does not read
    * a name that is not a plain directory leaf, or an entry whose path
      escapes the destination (../../etc/passwd, /etc/passwd, a symlink);
      such a bundle is never described, only refused
    * a language code the registry does not know, or one the manifest and
      the JSON inside disagree about -- and the same for the gloss language,
      the one the meanings are WRITTEN in, which may be a language nobody
      here studies (Portuguese) but not one nothing here can set at all
    * a book whose main file is missing, whose main.tex inputs a chapter the
      bundle does not carry, whose chapters do not parse, whose text no
      longer reproduces its own source paragraphs (verify_book.py's check),
      or one of whose word lines cannot be set (lib/wordline.py's check)
    * a video whose annotations do not pass check_annotations.py (a chunk
      half glossed is only noted: it is the middle of the work, which is
      when a video goes out and comes back)
    * a slug or an id already in the toolbox where this one would go, unless
      the caller passes replace -- and the answer then says what is being
      replaced
    * a slug or an id already in the toolbox SOMEWHERE ELSE -- under another
      language's folder, or directly under books/ -- which replace cannot
      reach and is therefore never offered for; the answer names the language
      the copy is filed under, since that is what says which directory to
      move, rename or delete

and it is atomic in the sense that matters: the bundle is unpacked into a
staging directory BESIDE the destination (so the move into place is a rename,
not a copy) and every check runs there.  Nothing that fails leaves anything
behind, and the destination is not touched until the tree in staging has
passed.  A replace frees the destination with one rename, moves the new tree
in with a second, and then carries across everything of the old directory's
that THIS bundle did not carry -- the built PDF, the reader, the build keys,
and whatever of the narration the shape left out -- so re-uploading a chapter
can never cost somebody a recording.  What a replace does overwrite is the
authored text, deliberately and only when asked; in this toolbox that text is
in git, which is where an undo comes from.

A SHAPE SAYS WHAT IS IN THE ZIP.  It never says what to destroy at the far
end, and install deletes no part of a narration, ever.  The case is a `text`
bundle uploaded over the book it came from, with replace: the recording, the
timings, the review and its page all stay, and book.json is pointed back at
the recording it still has, because a book.json nulled beside a 219 MB file
that is still there is not a state any door of this toolbox produces -- it
would be keeping the bytes and losing the narration.  The asymmetry is
deliberate and is the same one as above: the text is in git and the recording
is nowhere, so the shape a person picked in a download sheet last week must
not be able to delete it.  The one thing that does not come back is the
`% @par` comments, which are in the text the replace overwrote; the times
themselves are safe in timings.json and the answer names the one command that
writes them back.

The refusals are exceptions carrying the message a user should see:
BundleError for all of them, and Exists (a subclass) for the one an HTTP
route should answer 409 with and offer a "replace" box for, the way the add-a-
video page already does.

    python3 lib/bundle.py pack <dir|slug|id> [--audio text|linked|full] [-o out.zip]
    python3 lib/bundle.py inspect <bundle.zip>
    python3 lib/bundle.py install <bundle.zip> [--replace] [--root <toolbox>]

Standard library only: the server imports this.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import traceback
import zipfile
import zlib

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import books as booklib     # noqa: E402  where a book lives and what it is called
import languages           # noqa: E402  the registry: codes, folders
import texparse            # noqa: E402  does a chapter parse at all
import timestamp           # noqa: E402  AT_RE: the aligner's own `% @par` lines
import verify_book         # noqa: E402  does the built text still say what the source says
import wordline            # noqa: E402  can each chunk's word line be set
import audiofile           # noqa: E402  what a recording may be called
import version             # noqa: E402  which Parseh this is: VERSION, read once

# check_annotations is the video door's checker and lives under youtube/lib.
# The server has that directory on sys.path already; run as a script from
# anywhere it does not, so it is appended -- never inserted, so the server's
# own import order is left exactly as it was (anki_export.py does the same
# with lib/).
_YT_LIB = os.path.join(ROOT, "youtube", "lib")
try:
    import check_annotations as CA          # noqa: E402
except ImportError:
    if _YT_LIB not in sys.path:
        sys.path.append(_YT_LIB)
    import check_annotations as CA          # noqa: E402

MANIFEST = "parseh-bundle.json"
FORMAT = "parseh-bundle/3"      # bumped only when a reader of /1 would get it wrong
# (2: a0.4.0, a note may hold a latex block, TO-DO §8.39)
# (3: a0.4.2, a book made by an agent carries its original and annot/, TO-DO §8.40)
# who wrote a bundle, exactly as the server announces itself (serve.py's
# server_version): the name and the version of the Parseh doing the writing.
# Bundles written before the version was kept in one place say "Parseh/1.0",
# a number no release ever had; they install as every bundle does, because
# nothing reads this field back (see _manifest_for).
SOFTWARE = "Parseh/" + version.VERSION

# A zip arrives from the network and is unpacked onto the disk before any of
# it can be checked, so the two things a small file can do -- unpack to
# gigabytes, or to a million entries -- are capped first.  The Persian book
# is 24 files and 330 kB unpacked; the narrated one, in `full`, is 250 files
# and 220 MB, all but 3 MB of it one recording.
#
# TWO budgets, counted apart, because they were written for different
# dangers.  MAX_UNPACKED still guards the text exactly as before -- carrying
# a recording must not become a way to smuggle four gigabytes of
# source/*.txt past a route that unpacks before it can check -- and MAX_MEDIA
# is the recording's own, set where serve.py's MAX_AUDIO already sets it,
# that being the door a narration arrives by in the first place.  Both are
# read off the zip's own table of contents before a byte is written, so the
# most a refused bundle can put on the disk is one recording's worth, which
# is what the narration upload already risks.
MAX_ENTRIES = 5000
MAX_UNPACKED = 64 << 20
# NO CEILING ON THE MEDIA.  A recording or a film inside a bundle is one of
# the reader's own files: it is written out as it is read, in pieces, and a
# number here could only ever be smaller than somebody's two-hour lesson.
# MAX_UNPACKED still holds, and is a different thing -- it bounds the TEXT a
# bundle can claim to unpack to, which is what a zip bomb is made of.
MAX_MEDIA = None

# What a recording may be, and the one list here that is a copy of another:
# serve.py's AUDIO_EXTS, which this module cannot import (the server imports
# it, not the other way about).  tests/smoke.py reads the two against each
# other so they cannot drift, the way it already does for the four colours.
# It is an allowlist and has to be: audio/ lands under books/, which is
# served as static files, so a bundle that could put any extension there
# could put a page there.
AUDIO_EXTS = (".mp3", ".m4a", ".mp4", ".aac", ".webm", ".ogg", ".oga", ".opus",
              ".wav", ".flac")

# THE FILM ITSELF, for a video that is a file on this machine rather than an
# address on YouTube.  It is one file at the top of the video's directory,
# always called `media` and keeping only its extension, because the name is
# the toolbox's to choose: a name that arrived with an upload chooses a path,
# and this one is served as a static file like everything else under
# videos/.  An allowlist for the same reason AUDIO_EXTS is one.
VIDEO_EXTS = (".mp4", ".m4v", ".webm", ".mkv", ".mov", ".avi", ".ogv", ".ogg")
MEDIA_STEM = "media"
# A SOUND MAY BE A VIDEO'S MEDIA TOO: a lesson that was recorded and never
# filmed.  It is the same one file called `media`, so every rule above holds
# for it as it holds for a film, and the table is an allowlist for the same
# reason VIDEO_EXTS is one.  MEDIA_EXTS is what is_media_name reads; AUDIO_EXTS
# stays the books' narration, which is a different door.  `.ogg` is in both
# lists on purpose: it is a film in an old video and a sound in a new one, and
# video.json's "kind" (film_kind below) says which.
SOUND_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac",
              ".wma", ".aiff", ".aif", ".amr", ".mka", ".weba", ".caf")
MEDIA_EXTS = VIDEO_EXTS + tuple(e for e in SOUND_EXTS if e not in VIDEO_EXTS)
# WHAT THE STATIC ROUTE CALLS A SOUND when it serves it as a video's media: a
# film is announced as video/<ext> (serve.py's _static), and that is wrong for a
# sound an <audio> element is given.  Fixed here and not left to the platform's
# table, which disagrees with itself about these (Windows' registry above all).
# `.ogg` stays video/ogg, as it was for the films that used it.
SOUND_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
               ".oga": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav",
               ".flac": "audio/flac", ".wma": "audio/x-ms-wma", ".aiff": "audio/aiff",
               ".aif": "audio/aiff", ".amr": "audio/amr", ".mka": "audio/x-matroska",
               ".weba": "audio/webm", ".caf": "audio/x-caf"}
# THE ORIGINAL OF A SOUND THAT HAD TO BE MADE PLAYABLE (youtube/lib/filmkind.py)
# is kept beside the copy under this name.  It is never taken for the film, and
# a bundle does not carry it: the copy is what the next machine plays, and the
# original is a file the person already has.
ORIG_STEM = "media-orig"

# The three shapes a book comes out in, and what a bundle that names none of
# them is.  Spelt as the reader's download sheet and serve.py's ?audio= spell
# them, so one word carries the choice from the button to the manifest.
MODES = ("text", "linked", "full")
DEFAULT_MODE = "linked"

# THE NARRATION, in every place a book refers to one.  One table, as SHAPE is,
# and read in every direction: _owned decides which shape carries which of
# them, _clean takes `fields` out of the book.json that is carried anyway,
# and _narration asks a book on disk whether it has any of it at all.
#   files  the alignment, the review, and what the reader saves back into it
#          (serve.py's __save/review-corrections.json)
#   page   the review's own page -- carried by no shape (see the docstring),
#          named here because it is still part of what a narration IS
#   dir    the recording, its transcript, and whatever a narration import
#          left beside them (serve.py keeps a timings.before-import.json)
#   fields the two book.json keys naming the first two files in `dir`
# The sixth place is in the chapters themselves and has no name here: the
# `% @par` comment lines, which are timestamp.AT_RE's and are read from it.
NARR_FILES = ("timings.json", "review.json", "review-corrections.json")
NARR_PAGE = "review.html"
NARR_DIR = "audio"
NARR_EXTS = AUDIO_EXTS + (".txt", ".json")
# "narrations" is the list a book recorded in parts carries, and it belongs
# here with the two scalars: the `text` shape has to null it as well, or that
# shape hands over a book still naming recordings -- the precise lie the
# shape exists to prevent -- and _narration() has to count it, or such a book
# packs as one with no narration at all.
NARR_FIELDS = ("audio", "transcript", "narrations")

# Where a staging or a holding directory goes: beside the destination, so the
# move into place is a rename within one filesystem, and named with a leading
# dot.  Neither is ever seen as content: ytpages.video_dirs skips a dot
# directory outright, and books.book_dirs walks exactly two levels under
# books/, while a staged tree sits three deep (books/<folder>/.parseh-install-
# xxxx/<slug>/) -- which is why the tree is nested under the staging directory
# rather than being it.
STAGE = ".parseh-install-"
HOLD = ".parseh-replaced-"

# The two kinds, and what each is made of.  ONE table, read in both
# directions: pack_* walks it to decide what goes in, install lets nothing
# else through on the way back.  "dirs" maps a carried directory to the
# extensions it may hold -- .txt and .json under source/ is what the book
# pipeline writes there (extract_pdf.py, chapter_src.py), .json under parts/
# is the batches of a video added before they were retired (2026-09-23):
# nothing reads them any more, and they are carried so that an old video
# still travels whole rather than arriving with a folder silently missing.
# The notes somebody has written into the seams of a book or a video
# (markdown/app/notes.py).  They are part of the content and not of the
# toolbox, so they travel in EVERY shape of the bundle -- a `text` book with
# no recording still has whatever was written about it -- and they are the one
# carried directory that holds pictures, because a note is a studio document
# and a studio document can have figures in it.
NOTES_DIR = "markdown"
# No .svg, and the reason is the one this file already gives for having an
# allowlist at all: everything under books/ and youtube/videos/ is served as a
# static file, and an SVG is a document that can carry a script -- so a bundle
# able to install one could put a script of its own same origin with the
# reader.  A note that has an SVG figure keeps it on the machine it was drawn
# on; the bundle carries the rest.
# A note may hold RECORDINGS too (`![caption](audio/word.mp3)`, in its own
# audio/ folder), in the formats every other door for audio takes: the list is
# lib/audiofile.py's, so a note's recording never travels where a document's
# would be refused.  They count against MAX_UNPACKED like the rest of a note:
# a note's recording is a word or a sentence, not a narration.
NOTES_EXTS = (".md", ".json", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf") \
    + tuple("." + e for e in audiofile.EXTS)

# THE TWO DIRECTORIES OF A BOOK MADE BY AN AGENT (lib/making.py): the annotation
# JSON its chapters were assembled from, and the original it was made from.  The
# original's kinds are the tools' own -- a PDF with a text layer, an epub, plain
# text -- and are the list making.ORIGINAL_EXTS keeps (tests/test_making.py reads
# the two against each other).  It is the person's own file on their own machine,
# so it has no ceiling of its own, as a recording has none (MAX_MEDIA).
ANNOT_DIR = "annot"
ORIGINAL_DIR = "original"
ORIGINAL_EXTS = (".pdf", ".epub", ".txt")

SHAPE = {
    "book": {
        "name": "slug",
        "under": ("books",),
        # reading.json travels with the book: a folded reading and a paragraph
        # somebody has taken charge of are decisions about the EDITION, not
        # about one machine, and the allowlist is read both ways -- a file not
        # named here is dropped on the way out and refused on the way in.
        "files": ("book.json", "NOTES.md", "reading.json"),
        "dirs": {"source": (".txt", ".json"), ANNOT_DIR: (".json",),
                 ORIGINAL_DIR: ORIGINAL_EXTS, NOTES_DIR: NOTES_EXTS},
    },
    "video": {
        "name": "id",
        "under": ("youtube", "videos"),
        # waveform.json travels for the reason reading.json does, and more
        # so: a YouTube video's sound reaches no script here, so the picture
        # of it is a recording of the whole video made in real time, in a
        # browser that can share a tab.  It is derived, but it is derived at
        # the cost of sitting through the video once, from a source the
        # bundle cannot carry -- so making it again on the next machine is
        # an hour nobody should be asked to spend twice.
        "files": ("video.json", "annotations.json", "transcript.txt",
                  "waveform.json", "wordtimes.json"),
        "dirs": {"parts": (".json",), NOTES_DIR: NOTES_EXTS},
    },
}

# The slug or the id becomes a directory name under books/ or videos/ and a
# segment of a URL, so it is ASCII, and it never begins with a dot: a dot
# directory is how this toolbox hides its own scratch, and a bundle must not
# be able to make one.  `.` and `..` are refused by the same clause.
#
# THE FIRST CHARACTER IS NOT OTHERWISE SPECIAL, and used to be: this pattern
# asked for a letter or a digit there, which is one more rule than the
# sentence above states and one more than is true.  A YouTube id is eleven
# characters of [A-Za-z0-9_-] and perfectly well begins with an underscore or
# a hyphen -- `_bK2mQ8sTfA` is a video like any other -- so a bundle of one
# was refused at the door, with a message about dots that named nothing the
# uploader had done.
LEAF = re.compile(r"^(?!\.)[A-Za-z0-9._-]{1,100}$")


class BundleError(Exception):
    """A refusal.  The message is the one to show the person who uploaded."""


class Exists(BundleError):
    """The slug or id is already in the toolbox WHERE THIS ONE WOULD GO and
    `replace` was not given: the one refusal a page answers by offering a
    "replace" checkbox (409), rather than by saying the file is wrong -- so it
    is raised only where ticking the box would actually install the bundle.  A
    copy filed under another language is a plain BundleError, because a
    replace overwrites a directory where it stands and cannot move one."""


# ------------------------------------------------------------------ what is carried
def _owned(kind, entry, mode):
    """Is `entry` -- one name from the top level of the directory -- this
    bundle's to carry?

    "Every .tex but frankdraft.tex" is build.sh's own definition of what the
    book is made of (cat_book_tex): a chapter may be called anything, and
    frankdraft.tex is what ./build.sh --draft writes into the book directory,
    so it is output and not source.

    `mode` is one of MODES and moves only the narration.  It says nothing
    about a video, which has none; and _put reads this function to decide
    what of an old directory to carry across a replace, so a name a shape
    does NOT own is a name the old copy keeps -- which is how a `text` bundle
    installs without touching a recording.
    """
    S = SHAPE[kind]
    if entry in S["files"] or entry in S["dirs"]:
        return True
    if kind == "video":
        # the film, where the video has one: carried by `full` and by nothing
        # else, exactly as a book's recording is.  Left behind by `text`,
        # which is also how a text-only bundle installs over a video whose
        # film is already here without touching it.
        return is_media_name(entry) and mode == "full"
    if kind != "book":
        return False
    if entry in NARR_FILES:
        return mode in ("linked", "full")
    if entry == NARR_DIR:
        return mode == "full"
    return entry.endswith(".tex") and entry != "frankdraft.tex"


def _dir_exts(kind, mode):
    """Which extensions each carried directory may hold, in this shape."""
    exts = dict(SHAPE[kind]["dirs"])
    if kind == "book" and mode == "full":
        exts[NARR_DIR] = NARR_EXTS
    return exts


def is_media_name(entry):
    """Is this the one file a local video's film is allowed to be?"""
    stem, ext = os.path.splitext(entry)
    return stem == MEDIA_STEM and ext.lower() in MEDIA_EXTS


def is_orig_name(entry):
    """Is this the original a sound was kept as when its playable copy was
    made (media-orig.<ext>)?  Not the film, and not carried."""
    stem, ext = os.path.splitext(entry)
    return stem == ORIG_STEM and ext.lower() in MEDIA_EXTS


def _is_media(rel):
    """A recording or a film: what a bundle carries that is not text, and so
    what has a size budget of its own and a compression of its own."""
    if rel.startswith(NARR_DIR + "/"):
        return os.path.splitext(rel)[1].lower() in AUDIO_EXTS
    return "/" not in rel and is_media_name(rel)


def _is_original(rel):
    """A book's original: stored in the zip as it is (a PDF and an epub are
    compressed already), counted apart from the text, and given no ceiling."""
    return rel.startswith(ORIGINAL_DIR + "/")


def _narration(directory, meta):
    """Everywhere this book on disk refers to a recording -> a dict of lists.

    Found by looking rather than by guessing, because the two obvious files
    are not the half of it:

        fields  book.json's "audio" and "transcript"
        files   timings.json, review.json, review-corrections.json, and
                review.html, which no shape carries but which is a reference
                to a narration all the same
        audio   audio/ entire
        tex     the chapters carrying `% @par` lines -- a narration hiding
                inside files every shape carries

    None of them present is what "this book has no narration" means, and then
    the three shapes are one bundle: `any` is False, and neither the manifest
    nor the filename pretends the choice mattered.
    """
    got = {"fields": [k for k in NARR_FIELDS if meta.get(k)],
           "files": [fn for fn in NARR_FILES + (NARR_PAGE,)
                     if os.path.isfile(os.path.join(directory, fn))],
           "audio": [], "tex": []}
    adir = os.path.join(directory, NARR_DIR)
    if os.path.isdir(adir):
        got["audio"] = sorted(n for n in os.listdir(adir)
                              if os.path.isfile(os.path.join(adir, n)))
    for fn in sorted(os.listdir(directory)):
        path = os.path.join(directory, fn)
        # only the .tex a bundle carries at all: frankdraft.tex is build.sh's
        # output (_owned), so a time comment left behind in one is not a
        # difference between the shapes and must not make the choice appear
        if not fn.endswith(".tex") or not _owned("book", fn, "text") \
                or not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            # errors="replace" and not a refusal: this is a question about a
            # book, asked before anything is packed, and a .tex that is not
            # UTF-8 is the packer's problem to name, not this one's
            text = f.read().decode("utf-8", "replace")
        if any(timestamp.AT_RE.match(ln) for ln in text.split("\n")):
            got["tex"].append(fn)
    got["any"] = any(got[k] for k in ("fields", "files", "audio", "tex"))
    return got


def _carried(kind, directory, mode):
    """-> (paths to carry, paths left behind), both relative to `directory`,
    with forward slashes and in a stable order.

    A carried directory that would come out empty is listed as itself, with a
    trailing slash: an empty directory is a fact about the tree, and parts/
    with nothing in it yet is exactly what a video someone has only just
    started looks like.
    """
    take, left = [], []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not _owned(kind, name, mode):
            left.append(name + ("/" if os.path.isdir(path) else ""))
            continue
        if os.path.isfile(path):
            take.append(name)
            continue
        if not os.path.isdir(path):
            continue
        exts = _dir_exts(kind, mode).get(name)
        got = 0
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for fn in sorted(files):
                rel = os.path.relpath(os.path.join(root, fn), directory).replace(os.sep, "/")
                if exts is not None and os.path.splitext(fn)[1].lower() not in exts:
                    left.append(rel)
                    continue
                take.append(rel)
                got += 1
        if not got:
            take.append(name + "/")
    return take, left


# --------------------------------------------------------------- the `text` shape
def _text_book_json(raw):
    """book.json with the two fields that name a narration nulled -- or the
    bytes untouched, when there is nothing to null.

    NULLED and not removed: `"audio": null, "transcript": null` is what every
    book.json in this toolbox with no narration says, and a `text` bundle has
    to give a book indistinguishable from one of those, not a variant of one.
    A file that never held the keys does not gain them, for the same reason:
    absent and null are one answer to books.Book, and a book with no
    narration must come out of all three shapes as the same bytes.

    The rest is re-serialised the way serve.py's set_book_meta already writes
    this file whenever a narration is added or moved -- indent 2, key order
    kept, and the trailing newline the file had.  A book.json this toolbox
    wrote therefore comes back with those two lines changed and no other; one
    written by hand at another indent is reformatted whole, which is what
    adding a narration to it would have done anyway.
    """
    text = raw.decode("utf-8")
    meta = json.loads(text)
    if not isinstance(meta, dict) or not any(meta.get(k) for k in NARR_FIELDS):
        return raw
    for k in NARR_FIELDS:
        if meta.get(k):
            meta[k] = None
    out = json.dumps(meta, ensure_ascii=False, indent=2)
    return (out + "\n" if text.endswith("\n") else out).encode("utf-8")


def _strip_times(raw):
    """A chapter with the aligner's time comments taken out -- or the bytes
    untouched, when it carries none.

    `% @par <label> <t0> <t1> <conf> <src>` above every subparagraph is the
    reader's authority on when to light one up: tex2html's load_times reads
    these and not timings.json, so a `text` bundle that left them in would
    hand over a book still timed to a recording it does not carry.  The
    pattern is the aligner's own -- timestamp.AT_RE, which is what writes and
    rewrites them -- and never a second spelling of it here, which would let
    the two drift and leave a comment behind that this file did not know was
    one.

    Taking one out cannot move a glyph: a comment occupying a WHOLE line is
    consumed by TeX together with its newline (timestamp.py's own docstring,
    and its --verify-pdf), so the PDF and the reader are the same book with
    these lines and without them.
    """
    text = raw.decode("utf-8")
    lines = text.split("\n")
    keep = [ln for ln in lines if not timestamp.AT_RE.match(ln)]
    return raw if len(keep) == len(lines) else "\n".join(keep).encode("utf-8")


def _text_bytes(rel, raw):
    """One carried file as the `text` shape carries it.  Everything that says
    nothing about a narration comes back exactly as it went in."""
    if rel == "book.json":
        return _text_book_json(raw)
    if rel.endswith(".tex"):
        return _strip_times(raw)
    return raw


def _cleaned(rel, raw):
    """_text_bytes, with a refusal in place of a traceback for a file that
    cannot be read as what it claims to be."""
    try:
        return _text_bytes(rel, raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise BundleError("%s cannot be read as the %s it should be (%s), so the "
                          "narration cannot be taken out of it"
                          % (rel, "JSON" if rel.endswith(".json") else "UTF-8 text", e))


def _clean(tree):
    """Every reference to a narration out of an unpacked `text` tree. -> notes

    Run at BOTH ends: pack writes the cleaned bytes straight into the zip,
    and install cleans the staged tree again before one check runs on it.
    The second is not belt and braces.  A bundle is a file a person may edit
    by hand -- that is what this door is for -- and what `text` promises is
    about the book that LANDS, not about who wrote the zip: a hand-made
    manifest saying `text` over a book.json still naming a recording would
    otherwise install exactly the lie the shape exists to prevent.  It is the
    same transform at both ends, so a tree the packer cleaned cleans to
    itself and says nothing.
    """
    changed = []
    for fn in sorted(os.listdir(tree)):
        path = os.path.join(tree, fn)
        if not os.path.isfile(path) or (fn != "book.json" and not fn.endswith(".tex")):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        out = _cleaned(fn, raw)
        if out != raw:
            with open(path, "wb") as f:
                f.write(out)
            changed.append(fn)
    if not changed:
        return []
    return ["this bundle says `text` but still pointed at a narration in %d file(s) "
            "(%s); they were cleaned before anything was checked, so what is "
            "installed is what `text` means"
            % (len(changed), ", ".join(changed[:4]))]


def _filename(kind, name, shape=None):
    """What the browser saves it as.  <name>-book.zip / <name>-video.zip is
    the shape serve.py's narration export already uses (<slug>-narration.zip),
    so a book's two downloads sit side by side in a downloads folder.  A leaf
    is checked by LEAF everywhere it matters, but a directory on disk can be
    called anything, and this one string ends up in a Content-Disposition
    header.

    A narrated book says which of the three it is, because somebody comparing
    them has all three in one downloads folder and "(1)" is no answer to
    which one holds the recording.  A book with no narration keeps the name
    it has always had -- there being only one bundle of it to name."""
    safe = re.sub(r"[^\w.-]+", "-", name, flags=re.UNICODE).strip("-.") or kind
    return "%s-%s%s.zip" % (safe, kind, "-" + shape if shape else "")


def _manifest_for(kind, name, language, gloss, shape):
    """The bundle's own record of itself, written to parseh-bundle.json.

    format     the bundle format, not the toolbox's: the ONE field install
               takes on trust, because it is what says whether the rest can
               be read at all.  Everything below it is re-derived from the
               files and refused when the two disagree.
    software   who wrote it, name and version in one string, exactly as the
               server announces itself.  Informational for ever: a bundle
               must survive the toolbox being upgraded, so no install may
               ever refuse on this field.
    kind       "book" or "video" -- which door it goes in at, and so which
               checker has to pass before it does.
    language   the registry code (docs/languages.md section 1).  The folder
               is NOT stored: the registry turns the code into the folder,
               and a bundle holding both could arrive saying "ja" and
               "persian" at once.
    gloss      what the meanings are written in (languages.gloss): a registry
               code or a prose one, and "en" for a bundle that says nothing,
               which every bundle written before the field existed does.  It
               is here for the same reason `language` is -- so a person
               reading the zip can see it, and so install can refuse a
               manifest that disagrees with the JSON inside -- and it does
               NOT bump `format`: a toolbox that reads /1 and has never
               heard of a gloss language installs such a bundle correctly,
               because book.json carries the field itself and absent still
               means English on both sides of the exchange.
    slug / id  the name of the tree inside, spelt with the word that door
               already uses -- book.json says "slug", video.json says "id".
    audio      how much of the narration is inside: "text", "linked" or
               "full" (MODES).  A SHAPE and never a path -- book.json's field
               of that name holds the file, this one holds the word, and the
               two must no more be read as each other than `language` and
               `gloss` may.  It is written only for a book that HAS a
               narration: for one that has not, the three shapes are the same
               bundle, and naming one of them would be inventing a difference
               that is not in the zip.  Absent means `linked`, which is what
               every bundle written before the shapes existed is, those
               having carried the `% @par` comments and the book.json fields
               exactly as they stood.
               It does NOT bump `format`, for the reason `gloss` did not.  A
               toolbox that reads /1 and has never heard of a shape installs
               a `text` bundle correctly, the cleaning being in the files and
               not in this field; installs a `linked` one as the bundle it
               would have written itself, naming the timings.json it leaves
               out; and refuses a `full` one outright, its MAX_UNPACKED being
               64 MB and the recording hundreds.  Not one of the three is
               quietly got wrong, which is the whole of what this field would
               have to be believed for.
    exported   when, local time, the spelling serve.py's narration manifest
               uses.  For a human reading two downloads; nothing reads it
               back.
    """
    man = {"format": FORMAT, "software": SOFTWARE, "kind": kind,
           "language": language, "gloss": gloss, SHAPE[kind]["name"]: name}
    if shape:
        man["audio"] = shape
    man["exported"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return man


def _pack(kind, directory, name, language, gloss, mode, shaped):
    """-> (the bytes of the zip, the filename to offer it under).

    `shaped` is whether the shape is a fact about this bundle at all: false
    for a video, and false for a book with no narration, and then neither the
    manifest nor the filename carries one.

    A recording is STORED and not deflated.  Measured on the 218 MiB
    audio.webm this was written against (228,271,372 bytes): stored, the zip
    entry is 228,271,482 bytes and takes 0.11 s; deflated it is 228,131,647
    and takes 3.6 s.  Thirty times the work to save 0.061% -- a webm holds
    Vorbis or Opus and an m4a AAC, all of them already compressed, so there
    is nothing left in them for zlib to find, and the seconds are seconds a
    browser spends looking at a button that has not answered.  The text
    beside it still deflates, where it is worth better than 3:1.
    """
    take, _left = _carried(kind, directory, mode)
    clean = kind == "book" and mode == "text"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST,
                   json.dumps(_manifest_for(kind, name, language, gloss,
                                            mode if shaped else None),
                              ensure_ascii=False, indent=1) + "\n")
        for rel in take:
            arc = name + "/" + rel
            if rel.endswith("/"):
                zi = zipfile.ZipInfo(arc)
                # the bits every unzip reads as "make a directory"; without
                # them an empty parts/ arrives as nothing at all
                zi.external_attr = (0o40755 << 16) | 0x10
                z.writestr(zi, b"")
                continue
            src = os.path.join(directory, rel.replace("/", os.sep))
            if _is_media(rel) or _is_original(rel):
                z.write(src, arc, compress_type=zipfile.ZIP_STORED)
                continue
            if not clean:
                z.write(src, arc)
                continue
            with open(src, "rb") as f:
                z.writestr(arc, _cleaned(rel, f.read()))
    return buf.getvalue(), _filename(kind, name, mode if shaped else None)


def _book_at(directory, shown=None):
    """The books.Book at this directory, or a refusal a person can act on.

    Book() raises for a book.json that is missing or unreadable and
    find_book() exits the process for one naming a language the registry
    has not got; neither belongs in a module an HTTP route calls.  `shown`
    is what the refusal calls the directory: an uploader is being told about
    their zip, and the staging path it is unpacked at would mean nothing to
    them.
    """
    directory = os.path.abspath(directory)
    label = shown or directory
    if not os.path.isfile(os.path.join(directory, "book.json")):
        raise BundleError("%s holds no book.json -- a book is books/<language>/<slug>/"
                          % label)
    try:
        b = booklib.Book(directory)
    except (OSError, ValueError) as e:
        raise BundleError("%s: book.json cannot be read (%s)" % (label, e))
    problem = b.language_problem() or b.gloss_problem()
    if problem:
        raise BundleError(problem.lstrip("! ") + " -- fix book.json first")
    return b


def _video_at(directory, shown=None):
    """-> (video.json as a dict, the Lang, the Gloss) or a refusal, `shown`
    as above.  The two languages are read here together because they are
    read off the same file and a video is wrong to install if either is."""
    directory = os.path.abspath(directory)
    label = shown or directory
    path = os.path.join(directory, "video.json")
    if not os.path.isfile(path):
        raise BundleError("%s holds no video.json -- a video is "
                          "youtube/videos/<language>/<id>/" % label)
    try:
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        raise BundleError("%s: video.json cannot be read (%s)" % (label, e))
    if not isinstance(meta, dict):
        raise BundleError("%s: video.json is not a JSON object" % label)
    declared = CA.lang_code(meta.get("language"))
    if declared and declared.strip().lower() not in languages.LANGS:
        raise BundleError("video.json language %r is not a registry code (known: %s)"
                          % (meta.get("language"), ", ".join(languages.CODES)))
    try:
        G = languages.gloss(CA.lang_code(meta.get("gloss")))
    except KeyError:
        raise BundleError("video.json gloss %r is not a language this toolbox can "
                          "write in (it can: %s)"
                          % (meta.get("gloss"), ", ".join(languages.GLOSS_CODES)))
    return meta, languages.get_or_default(declared), G


def _asked(audio):
    """The shape a caller asked for, or a refusal naming the three.

    A word that is not one of them is refused rather than resolved to a
    default.  The three differ by a 219 MB recording and by whether the book
    inside still knows it has one, so a typo that quietly picked one of them
    is the mistake at this door somebody could lose work to -- and this is
    the message serve.py answers ?audio=<anything else> with.
    """
    mode = audio.strip().lower() if isinstance(audio, str) else audio
    if mode not in MODES:
        raise BundleError("%r is not a shape a bundle comes in. A book comes out as "
                          "`text` (the reading edition alone), `linked` (everything "
                          "but the recording) or `full` (all of it)." % (audio,))
    return mode


def pack_book(book_dir, audio=DEFAULT_MODE):
    """A reading edition as one zip: -> (bytes, filename).

    `audio` is how much of the narration comes with it -- one of MODES, and
    the three are described at the top of this file.  It is spelt as the
    reader's download sheet and serve.py's ?audio= spell it.  A book with no
    narration is the same bundle whichever is asked for, down to the filename.

    The tree is named after the DIRECTORY, not after book.json's "slug": the
    directory is what the destination is called, what build.sh takes as an
    argument and what the reader's URL is made of, so packing under any other
    name would make a bundle its own install refuses.
    """
    mode = _asked(audio)
    b = _book_at(book_dir)
    return _pack("book", b.dir, os.path.basename(b.dir), b.language, b.gloss,
                 mode, _narration(b.dir, b.meta)["any"])


def film_at(video_dir):
    """The video's own film, if it has one: the name, or "" for a video whose
    media is on YouTube."""
    try:
        here = os.listdir(video_dir)
    except OSError:
        return ""
    return next((n for n in sorted(here) if is_media_name(n)
                 and os.path.isfile(os.path.join(video_dir, n))), "")


def film_kind(video_dir, meta=None):
    """What the video's film is -- "video", or "audio" for a sound that has no
    picture -- or "" for a video that has no film here.

    video.json SAYS IT ("kind", written once, when the film was attached:
    youtube/lib/filmkind.py asks ffprobe where there is one), so no page
    guesses.  A video made before the key existed is read from the extension,
    which is also what a bundle from an older Parseh comes to: a sound that is
    only ever a sound is audio, and anything else -- `.ogg` among it, which
    those videos used as a film -- is a video, as they have always played.
    `meta` is video.json as the caller already has it.
    """
    film = film_at(video_dir)
    if not film:
        return ""
    if meta is None:
        try:
            with open(os.path.join(video_dir, "video.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            meta = {}
    said = meta.get("kind") if isinstance(meta, dict) else None
    if said in ("video", "audio"):
        return said
    ext = os.path.splitext(film)[1].lower()
    return "audio" if ext in SOUND_EXTS and ext not in VIDEO_EXTS else "video"


def video_mode(video_dir, mode=None):
    """Which shape a video actually packs in.  `None` means "whatever this
    video wants": everything, where there is a film to carry."""
    film = film_at(video_dir)
    mode = mode or ("full" if film else DEFAULT_MODE)
    if mode not in MODES:
        raise BundleError("no such shape: %r (one of %s)" % (mode, ", ".join(MODES)))
    # a film is here or it is not; there is no third thing to link to
    return "text" if (film and mode == "linked") else mode


def pack_video(video_dir, mode=None):
    """A video and its glossed transcript as one zip: -> (bytes, filename).

    A VIDEO ON YOUTUBE HAS NO SHAPE and is offered none: its media is an
    address and never a file here, its timestamps sync its own transcript,
    and it packs to the bytes it always did.

    A VIDEO THAT IS A FILE ON THIS MACHINE HAS ONE, and the same two words a
    book's narration uses: `full` carries the film, `text` leaves it behind.
    Full is the default here where linked is the default for a book, and the
    asymmetry is the point -- a book without its recording is still the book,
    and a video without its film is a transcript of something the person who
    unpacks it has no way to watch.  So the download button hands over both
    unless it is told not to.
    """
    directory = os.path.abspath(video_dir)
    _meta, L, G = _video_at(directory)
    return _pack("video", directory, os.path.basename(directory), L.code, G.code,
                 video_mode(directory, mode), bool(film_at(directory)))


# WHAT ONE CARRIED FILE COMES TO INSIDE THE ZIP, deflated the way _pack
# deflates it: (path, size, mtime, cleaned) -> bytes.  The reader's download
# sheet asks every time it is opened and the player every time its page is
# drawn, and the answer changes only when the file does -- so each version
# of a file is compressed once, and every later asking is a stat.  Two
# threads asking at once cost a second compression of the same bytes, never
# a wrong figure; the table starts again past _DEFLATED_MAX entries, which
# is a shelf of books a hundred times over.
_DEFLATED = {}
_DEFLATED_MAX = 50000
# a zip's own bytes around each file: its local header and its entry in the
# central directory, each followed by the name (zipfile writes neither an
# extra field nor a comment for the files _pack puts in); and the record
# that ends the archive
_ZIP_ENTRY = 30 + 46
_ZIP_END = 22


def _deflate_len(chunks):
    """How long these bytes come out of zlib as a zip entry has them: raw
    deflate (no zlib header) at the default level -- zipfile's own
    compressor for ZIP_DEFLATED."""
    z = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
    n = 0
    for c in chunks:
        n += len(z.compress(c))
    return n + len(z.flush())


def _deflated(path, rel, clean):
    """This file's bytes inside the zip, deflated: the file as it is, or --
    `clean`, the `text` shape of a book -- as _cleaned hands it to the zip."""
    st = os.stat(path)
    key = (path, st.st_size, st.st_mtime_ns, clean)
    n = _DEFLATED.get(key)
    if n is not None:
        return n
    with open(path, "rb") as f:
        if clean and (rel == "book.json" or rel.endswith(".tex")):
            raw = f.read()
            try:
                raw = _cleaned(rel, raw)
            except BundleError:
                pass            # the pack will refuse it; the file is what it is
            n = _deflate_len([raw])
        else:
            n = _deflate_len(iter(lambda: f.read(1 << 20), b""))
    if len(_DEFLATED) >= _DEFLATED_MAX:
        _DEFLATED.clear()
    _DEFLATED[key] = n
    return n


def _zip_entry(arc, data_bytes):
    """One file (or directory) in the zip, headers and all."""
    return _ZIP_ENTRY + 2 * len(arc.encode("utf-8")) + data_bytes


def payload(kind, directory, mode):
    """How big this book's or video's bundle in this shape will be, before
    anything is packed -> {"bytes", "files", "media", "media_bytes"}.

    THE SUM OF WHAT _carried TAKES -- the very list _pack walks, so the
    figure cannot count a file the zip leaves out or miss one it carries.
    That is the point of it: a book read in nine parts carries all nine
    recordings under audio/ in `full` (and a replaced one still on the
    shelf, and the transcripts beside them), and the size the reader's
    download sheet used to give was the first recording's alone.

    EACH FILE AS THE ZIP HOLDS IT, not as the disk does.  A recording or a
    film is STORED (_pack), so it counts byte for byte.  Everything else is
    deflated, and counts as what it deflates to (_deflated, worked out once
    per version of a file): the text of a book is most of a `text` or a
    `linked` bundle, and it goes into the zip at a third of its size or
    less -- Persian and Arabic text above all, two bytes a letter and a
    handful of letters -- so summing the files on disk said "2.3 MB" of a
    0.7 MB zip.  The `text` shape's chapters and book.json are counted as
    they go in, with the narration taken out.  The headers of every entry
    and the manifest are counted too; what is left over is a few bytes
    either way (the manifest's languages and time, which are not looked up
    here).  `media` is how many recordings (or the film) are carried and
    `media_bytes` their share.
    """
    if mode not in MODES:
        raise BundleError("no such shape: %r (one of %s)" % (mode, ", ".join(MODES)))
    take, _left = _carried(kind, directory, mode)
    name = os.path.basename(os.path.abspath(directory))
    clean = kind == "book" and mode == "text"
    man = json.dumps(_manifest_for(kind, name, "xx", "xx", mode),
                     ensure_ascii=False, indent=1) + "\n"
    out = {"bytes": _ZIP_END + _zip_entry(MANIFEST, _deflate_len([man.encode("utf-8")])),
           "files": 0, "media": 0, "media_bytes": 0}
    for rel in take:
        arc = name + "/" + rel
        if rel.endswith("/"):
            out["bytes"] += _zip_entry(arc, 0)      # an empty directory: a name
            continue
        path = os.path.join(directory, rel.replace("/", os.sep))
        try:
            if _is_media(rel):
                n = os.path.getsize(path)
                out["media"] += 1
                out["media_bytes"] += n
            elif _is_original(rel):
                n = os.path.getsize(path)           # stored: it counts byte for byte, and is no recording
            else:
                n = _deflated(path, rel, clean)
        except OSError:
            continue                    # gone since the listing
        out["bytes"] += _zip_entry(arc, n)
        out["files"] += 1
    return out


def payload_bytes(kind, directory, mode):
    """payload()'s bytes alone."""
    return payload(kind, directory, mode)["bytes"]


# ------------------------------------------------------------------ reading one
def _open(data):
    """The zip, whether the caller holds the bytes (an upload) or a path
    (the CLI)."""
    try:
        if isinstance(data, (bytes, bytearray)):
            return zipfile.ZipFile(io.BytesIO(bytes(data)))
        return zipfile.ZipFile(data)
    except zipfile.BadZipFile:
        raise BundleError("that is not a bundle: a bundle is a zip file, and this "
                          "is not one")
    except OSError as e:
        raise BundleError("the bundle cannot be read (%s)" % e)


def _reads(stamp, fmt):
    """Is `stamp` one this Parseh reads -- its own, or any number before it
    (a0.4.0 raised them for the latex block, TO-DO §8.39: what an older
    Parseh wrote holds none, and is read as it always was)?"""
    name, _, n = fmt.rpartition("/")
    if not isinstance(stamp, str) or not stamp.startswith(name + "/"):
        return False
    have = stamp[len(name) + 1:]
    return have.isdigit() and 1 <= int(have) <= int(n)


def _manifest(z):
    """parseh-bundle.json, checked far enough to be believed about the rest."""
    try:
        raw = z.read(MANIFEST)
    except KeyError:
        raise BundleError("that is not a Parseh bundle: it carries no %s. The "
                          "download button makes one; a zip of a folder is not one."
                          % MANIFEST)
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        # a truncated download, or a zip with a password on it (RuntimeError):
        # a sentence, not a traceback out of whatever route called this
        raise BundleError("the bundle is damaged or locked and cannot be read (%s)" % e)
    try:
        man = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise BundleError("%s is not JSON (%s)" % (MANIFEST, e))
    if not isinstance(man, dict):
        raise BundleError("%s must be a JSON object" % MANIFEST)
    if not _reads(man.get("format"), FORMAT):
        raise BundleError("this bundle says format %r; this toolbox reads %r"
                          % (man.get("format"), FORMAT))
    kind = man.get("kind")
    # isinstance first: a hand-edited manifest can hold a list there, and
    # `[…] in SHAPE` is a TypeError, not a refusal
    if not isinstance(kind, str) or kind not in SHAPE:
        raise BundleError("%s: kind %r -- a bundle is a %s"
                          % (MANIFEST, man.get("kind"), " or a ".join(SHAPE)))
    key = SHAPE[kind]["name"]
    name = man.get(key)
    if not isinstance(name, str) or not LEAF.match(name):
        raise BundleError('%s: %r is not a %s a directory can be called -- letters, '
                          'digits, . _ and -, not starting with a dot'
                          % (MANIFEST, man.get(key), key))
    return man, kind, name


def _shape(man, kind):
    """Which shape this bundle says it is -> one of MODES.

    Absent is `linked` for a book (and _manifest_for says why): a bundle
    written before the shapes carried the narration's two fields and its
    `% @par` comments exactly as they stood, which is what `linked` means, so
    reading it as `text` would have install rewrite files that bundle meant
    to hand over untouched.

    Absent is `text` FOR A VIDEO, and the difference is not an inconsistency:
    every video bundle written before a video could be a file carried no film
    at all, so there is nothing in it for `full` to restore, and `text` is
    the true description of what is inside.  Reading those as `linked` would
    be reading them as a shape that says nothing about a video anyway.
    """
    got = man.get("audio")
    if kind == "video":
        if got is None:
            return "text"
        if not isinstance(got, str) or got.strip().lower() not in MODES:
            raise BundleError("%s: audio %r -- a video bundle says whether its "
                              "film is inside, `full` or `text`, or says nothing "
                              "and means `text`" % (MANIFEST, man.get("audio")))
        got = got.strip().lower()
        return "text" if got == "linked" else got
    if kind != "book":
        return None
    if got is None:
        return DEFAULT_MODE
    if not isinstance(got, str) or got.strip().lower() not in MODES:
        raise BundleError("%s: audio %r -- a book bundle says how much of its "
                          "narration is inside, `text`, `linked` or `full`, or says "
                          "nothing and means `linked`" % (MANIFEST, man.get("audio")))
    return got.strip().lower()


def _size(n):
    """A cap as a refusal should say it -- GB where MB would be four digits.
    The two budgets are three orders of magnitude apart and one sentence
    prints both, so the unit is picked and not written in."""
    return "%d GB" % (n >> 30) if n >= (1 << 30) else "%d MB" % (n >> 20)


def _escape(entry):
    return BundleError("this bundle carries %r, which is not a path inside it -- "
                       "refused whole, and nothing was unpacked" % entry)


def _entries(z, kind, name, mode):
    """-> (files, empty directories, what was dropped, unpacked size).

    A zip is an archive of NAMES, and a name is not a path until somebody
    trusts it.  Nothing here goes through ZipFile.extractall, which quietly
    sanitises a name and would install a bundle that had tried; a name that
    is not plainly "<name>/<relative path>" is refused, and a bundle that
    tried is not described either -- inspect() shows nothing about it.

    A file that is not the bundle's to carry (SHAPE, NARR_*, and _owned in
    this shape) is DROPPED rather than refused: a person who zipped their
    book folder by hand has a main.pdf in it and meant no harm, and the same
    allowlist that keeps a stale artefact out keeps a page of somebody's own
    out of a directory the server serves.  A recording in a bundle that says
    `text` is dropped by that same rule, which is what makes the shape a fact
    about what lands rather than a label on the zip.  What was dropped is
    reported, never silent.
    """
    files, dirs, dropped, total, media, original = [], [], [], 0, 0, 0
    exts = _dir_exts(kind, mode)
    if len(z.infolist()) > MAX_ENTRIES:
        raise BundleError("this bundle holds more than %d entries -- refused unread"
                          % MAX_ENTRIES)
    for zi in z.infolist():
        entry = zi.filename
        if entry == MANIFEST:
            continue
        if "\\" in entry or any(ord(c) < 32 for c in entry):
            raise _escape(entry)
        parts = entry.split("/")
        if parts and parts[-1] == "":
            parts = parts[:-1]                       # a directory entry
        if not parts or any(p in ("", ".", "..") for p in parts):
            raise _escape(entry)
        if parts[0] != name:
            raise BundleError("this bundle says it holds %r but carries %r, which "
                              "is outside it" % (name, entry))
        # A symlink in a zip is a path somebody else chose, followed later by
        # whoever writes through it; a bundle is text files and nothing else.
        # Only the file-TYPE bits are read: a zip made on MS-DOS has no mode
        # at all, and ZipFile.writestr leaves permission bits with no type
        # beside them, so testing S_ISREG directly refuses every hand-made
        # bundle -- which it did, until this line was written the other way.
        kind_bits = stat.S_IFMT(zi.external_attr >> 16)
        if kind_bits and kind_bits not in (stat.S_IFREG, stat.S_IFDIR):
            raise BundleError("this bundle carries %r, which is not a plain file "
                              "(a link, or a device) -- refused whole" % entry)
        rel = "/".join(parts[1:])
        if not rel:
            continue                                 # the tree's own directory
        top = parts[1]
        if not _owned(kind, top, mode):
            dropped.append(rel)
            continue
        # ONLY A DIRECTORY MAY HOLD THINGS.  Every name owned at the top used
        # to be treated as a directory prefix whose contents are checked
        # against the extensions that prefix allows -- and a FILE has none,
        # so `exts.get(...)` was None and the allowlist was skipped for
        # everything under it, at any depth.  A bundle carrying
        # `<id>/media.mp4/evil.html` installed it, to be served as text/html
        # from the same origin as the reader; one carrying `<id>/video.json/x`
        # got as far as making a directory where a file of that name was
        # about to be written and came out as a raw FileExistsError.
        # `exts` is the list of names that ARE directories in this shape, and
        # nothing else may have a path under it.
        if rel != top and top not in exts:
            dropped.append(rel)
            continue
        allowed = exts.get(top)
        if zi.is_dir():
            # only the one directory the packer writes an entry for, and only
            # when it holds nothing: a deeper empty one is not a fact the
            # packer records either
            if allowed is not None and len(parts) == 2:
                dirs.append(rel)                     # an empty source/ or parts/
            continue
        if allowed is not None and os.path.splitext(rel)[1].lower() not in allowed:
            dropped.append(rel)                      # including "source" as a FILE
            continue
        if _is_media(rel):
            media += zi.file_size
            if MAX_MEDIA is not None and media > MAX_MEDIA:
                raise BundleError("the recording in this bundle is more than %s "
                                  "-- refused unread" % _size(MAX_MEDIA))
        elif _is_original(rel):
            original += zi.file_size
        else:
            total += zi.file_size
            if total > MAX_UNPACKED:
                raise BundleError("this bundle unpacks to more than %s of text "
                                  "-- refused unread" % _size(MAX_UNPACKED))
        files.append((entry, rel))
    return files, dirs, dropped, total + media + original


def _destination(kind, folder, name, root):
    return os.path.join(root, *(SHAPE[kind]["under"] + (folder, name)))


def _already(kind, name, root):
    """Where this slug or id already is in the toolbox, or None.

    Not just the place it would go: a book or a video from before languages
    lies directly under books/ or videos/, and one whose language was since
    corrected lies under the folder of the language it used to be called.
    Installing beside either would leave the toolbox holding the same slug
    twice, listed twice, with the older copy shadowing the new one in every
    lookup by name -- find_book("<slug>") stops and asks which, and
    _resolve() below silently picks whichever folder sorts first.
    """
    top = os.path.join(root, *SHAPE[kind]["under"])
    if not os.path.isdir(top):
        return None
    marker = "book.json" if kind == "book" else "video.json"
    for first in sorted(os.listdir(top)):
        d = os.path.join(top, first)
        if not os.path.isdir(d):
            continue
        if first == name and os.path.isfile(os.path.join(d, marker)):
            return d                                  # the layout before languages
        if first.startswith("."):
            continue
        sub = os.path.join(d, name)
        if os.path.isfile(os.path.join(sub, marker)):
            return sub
    return None


def _where_filed(kind, here):
    """The clause that says where a copy already in the toolbox sits -- "filed
    as Italian" -- for the refusal that has to tell somebody what to do next.
    `here` is inspect's "at": books/<folder>/<name>, or books/<name>.

    The FOLDER decides, not the copy's own book.json: the two are allowed to
    disagree (docs/languages.md section 2 -- the JSON wins for rendering, the
    folder for the URL), and it is the folder that says which directory a
    person has to move, rename or delete.  Naming the JSON's language instead
    would send them looking in a directory that is not there.
    """
    parts = here.split("/")
    if len(parts) != len(SHAPE[kind]["under"]) + 2:
        return ("directly under %s/ and so under no language at all"
                % "/".join(SHAPE[kind]["under"]))
    L = languages.by_folder(parts[-2])
    return ("filed as %s" % L.name if L else
            "in %s/, which is no language's folder" % parts[-2])


def inspect(data, root=ROOT):
    """What is in a bundle, without unpacking or installing it.

    -> {kind, language, gloss, audio, name, folder, dir, software, exported,
        files, bytes, dropped, at, problems}

    `dir` is where it would go, relative to the toolbox; `at` is where a copy
    of that name already is, or None; `audio` is which of the three shapes
    this is (None for a video, `linked` for a bundle naming none); `problems`
    is what would make install refuse before it even unpacks -- shown to the
    person choosing, so the refusal is not the first they hear of it.  The
    checks that need the files on disk (a chapter that does not parse,
    annotations that do not check) belong to install and are not run here:
    inspect writes nothing and reads nothing but the zip's own table of
    contents.
    """
    with _open(data) as z:
        man, kind, name = _manifest(z)
        mode = _shape(man, kind)
        files, dirs, dropped, total = _entries(z, kind, name, mode)
    # through CA.lang_code, which spells a malformed value (a number, a list)
    # out as a string: a bad language is an unknown language and a sentence
    # to read, never a traceback out of a route
    code = CA.lang_code(man.get("language")).strip().lower()
    L = languages.LANGS.get(code)
    problems = []
    if L is None:
        problems.append("this bundle is in language %r, which this toolbox has not "
                        "got (it teaches: %s)" % (man.get("language"),
                                                  ", ".join(languages.CODES)))
    # The gloss language is read the same way and refused separately: a
    # bundle may be glossed in a language nobody here studies (Portuguese is
    # nobody's target and a perfectly good gloss), but not in one nothing
    # here can set -- the preamble, the reader and the Anki card would each
    # have to guess a direction and a set of hyphenation patterns, and each
    # would guess English.
    gcode = CA.lang_code(man.get("gloss")).strip().lower()
    try:
        G = languages.gloss(gcode)
    except KeyError:
        G = None
        problems.append("this bundle's glosses are written in %r, which this "
                        "toolbox cannot set (it can write a gloss in: %s)"
                        % (man.get("gloss"), ", ".join(languages.GLOSS_CODES)))
    where = _already(kind, name, root) if L else None
    return {"kind": kind, "language": code, "name": name, "audio": mode,
            "gloss": G.code if G else gcode,
            "folder": L.folder if L else None,
            "dir": _rel(_destination(kind, L.folder, name, root), root) if L else None,
            "software": man.get("software"), "exported": man.get("exported"),
            "files": sorted([r for _a, r in files] + [d + "/" for d in dirs]),
            "bytes": total, "dropped": sorted(dropped),
            "at": _rel(where, root) if where else None,
            "problems": problems}


def _rel(path, root):
    """A path as the toolbox says it: books/persian/<slug>, forward slashes."""
    return os.path.relpath(path, root).replace(os.sep, "/")


# ------------------------------------------------------------------ checking one
def _fidelity(book_dir):
    """verify_book.py's own check, run on the unpacked tree: -> (mismatches, notes).

    The tool prints and returns 1 for a mismatch AND for a paragraph whose
    source file is absent, and those two are not the same thing here.  A
    mismatch means the text drifted from the source it claims to reproduce
    and is a refusal.  A missing source/paras/ file is not: a book authored
    from nothing may never have had one, and there is nothing to have drifted
    from.  Nor is a .tex that is not a chapter at all -- characters.tex, kept
    beside them by an author -- which the tool names and skips, and which is
    carried anyway because build.sh takes every .tex as part of the book
    (_owned).  Anything else non-zero is refused with the tool's own words --
    an unrecognised complaint fails closed, never open.
    """
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = verify_book.main(book_dir)
    except SystemExit as e:                 # find_book, on a book.json it will not read
        raise BundleError("the book cannot be checked: %s" % e)
    except Exception:
        # The checker raising at all is a fault in this toolbox, not in the
        # zip somebody uploaded, and "AttributeError: 'NoneType' object has no
        # attribute" is not something a person can act on -- which is exactly
        # what a book carrying a characters.tex used to be answered with.  The
        # traceback goes where a bug belongs (serve.py's stderr, the terminal
        # for the CLI); the refusal is a sentence.
        traceback.print_exc()
        raise BundleError("this book's text could not be checked against its own "
                          "source paragraphs: the check itself stopped part way, "
                          "which is a fault in the toolbox and not in this bundle. "
                          "Nothing was installed, and the traceback is in the "
                          "toolbox's log.")
    # the tool's own words, marked by their first word; NOT A CHAPTER carries
    # the file it means, so the prefix is dropped and the rest quoted as a note
    lines = [l.strip() for l in out.getvalue().splitlines()]
    bad = [l for l in lines if l.startswith(("MISMATCH", "built :", "source:"))]
    missing = [l for l in lines if l.startswith("NO SOURCE")]
    aside = [l[len("NOT A CHAPTER "):] for l in lines if l.startswith("NOT A CHAPTER ")]
    if rc and not bad and not missing:
        # its summary line names the book by the staging path it was handed;
        # everything else it said is the complaint, and that is what to show
        said = [l for l in lines if l and STAGE not in l]
        raise BundleError("verify_book refused this book:\n"
                          + "\n".join("  " + l for l in said[:9]))
    notes = []
    if missing:
        notes.append("%d paragraph(s) have no source/paras/ file to check against: %s"
                     % (len(missing), "; ".join(missing[:3])))
    if aside:
        notes.append("%d .tex the bundle carries %s not a chapter, and nothing in "
                     "%s was checked: %s"
                     % (len(aside), "is" if len(aside) == 1 else "are",
                        "it" if len(aside) == 1 else "them", "; ".join(aside[:3])))
    return bad, notes


def _here(msg, tree):
    """A checker's message with the staging path taken out of it.  The
    checkers are handed the tree where it is unpacked; the person reading the
    refusal has a zip in their downloads folder and no idea what
    .parseh-install-3f9x is.  (ytpages rewrites merge_parts' and
    check_annotations' output the same way before showing it.)"""
    return msg.replace(tree + os.sep, "").replace(tree, "the bundle")


def _check_book(tree, name, language, gloss, mode):
    """The unpacked book, before it is allowed anywhere near books/. -> notes."""
    b = _book_at(tree, "this bundle")        # book.json parses, both languages real
    # the cleaning comes FIRST, before a single check: what verify_book and
    # texparse judge has to be the tree that lands, not the one that arrived
    notes = _clean(tree) if mode == "text" else []
    declared = b.declared_language
    if declared and declared != language:
        raise BundleError("%s says the language is %s and book.json says %s -- they "
                          "must agree" % (MANIFEST, language, declared))
    # b.gloss is the resolved code and so is `gloss`, so a bundle written
    # "spa" and a book.json written "es" are the one language and agree
    if b.gloss != gloss:
        raise BundleError("%s says the glosses are written in %s and book.json says "
                          "%s -- they must agree" % (MANIFEST, gloss, b.gloss))
    if b.meta.get("slug") and b.meta["slug"] != name:
        # the directory decides (that is what the URL and build.sh use), so
        # this is a note and not a refusal -- but it is exactly the sort of
        # thing a find-and-replace leaves behind
        notes.append('book.json says slug "%s" while the bundle holds "%s"; the '
                     'directory name wins' % (b.meta["slug"], name))
    if not os.path.isfile(b.main):
        raise BundleError('book.json says main "%s", which the bundle does not carry'
                          % b.meta.get("main", "main.tex"))
    # \input{\FrankLib/frank-preamble.tex} names a file through a macro and
    # lives in lib/, not in the book; a chapter is an \input with no macro in
    # it, and one that is not there is a book that will not build.
    try:
        with open(b.main, encoding="utf-8") as f:
            main_tex = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise BundleError("%s cannot be read as text (%s)"
                          % (os.path.basename(b.main), e))
    for line in main_tex.split("\n"):
        if line.lstrip().startswith("%"):
            continue
        for arg in re.findall(r"\\input\{([^}]+)\}", line):
            if "\\" in arg:
                continue
            if not os.path.exists(os.path.join(tree, arg.replace("/", os.sep))):
                raise BundleError("main.tex inputs %s, which the bundle does not "
                                  "carry" % arg)
    # parse_chapter remembers the book's language in texparse, as it does for
    # every caller; the reader's own build sets it again before it reads a
    # field, so an install never leaves the next parse in the wrong language
    unset, doubts = [], 0
    for fn in sorted(os.listdir(tree)):
        if not (fn.endswith(".tex") and fn != "frankdraft.tex"):
            continue
        try:
            chapter = texparse.parse_chapter(os.path.join(tree, fn), b.lang)
        except Exception as e:
            raise BundleError("%s does not parse: %s. A \\ch takes five brace groups, "
                              "a \\chr six, a \\chw six and a \\chrw seven, the word "
                              "line last; an unbalanced brace stops the reader and "
                              "the PDF alike." % (fn, e))
        # A word line is held to the check the PDF's own reader of it makes
        # (lib/wordline.lua refuses the line that does not rejoin its text):
        # one it refuses is a book that will not build.  What it only doubts
        # -- a reading to look at -- is the author's to weigh, and counted.
        for c in (c for s in chapter.subs for c in s.chunks if c.wordline):
            errs, warns = wordline.check(c.fa, c.wordline, b.lang,
                                         reading=c.kana if b.lang.reading else c.tr,
                                         reorders=b.reorders, door=wordline.BOOK)
            unset += ["%s line %d: %s" % (fn, c.line + 1, e) for e in errs]
            doubts += len(warns)
    bad, more = _fidelity(tree)
    if bad:
        raise BundleError("the text no longer reproduces its own source paragraphs:\n"
                          + "\n".join("  " + l for l in bad[:9])
                          + "\n(source/paras/ is what a chunk's fa must add up to; "
                            "edit one, edit the other)")
    if unset:
        raise BundleError("%d word line(s) cannot be set:\n" % len(unset)
                          + "\n".join("  " + l for l in unset[:9]))
    if doubts:
        notes.append("%d warning(s) on the word lines: readings to look at, not "
                     "refusals (lib/wordline.py's check names each one)" % doubts)
    return notes + more


def _check_video(tree, name, language, gloss):
    """The unpacked video, through the video door's own checker. -> notes."""
    meta, L, G = _video_at(tree, "this bundle")
    notes = []
    declared = CA.lang_code(meta.get("language"))
    if declared and declared.strip().lower() != language:
        raise BundleError("%s says the language is %s and video.json says %s -- they "
                          "must agree" % (MANIFEST, language, declared))
    if G.code != gloss:
        raise BundleError("%s says the glosses are written in %s and video.json says "
                          "%s -- they must agree" % (MANIFEST, gloss, G.code))
    if meta.get("id") and meta["id"] != name:
        notes.append('video.json says id "%s" while the bundle holds "%s"; the '
                     'directory name wins' % (meta["id"], name))
    # A chunk HALF GLOSSED -- the meaning typed, the transliteration still to
    # come -- is how a video looks in the middle of its glossing, and the
    # player saves it so; a bundle is how that video goes to another machine
    # and back, so here it is noted and not refused.  The checker names each
    # missing field; the note counts the chunks (the part of the message
    # before ": missing").  Every other error still refuses.
    halves = []
    errors, warnings, (nseg, nch, nw) = CA.check(tree, half=halves.append)
    if errors:
        raise BundleError("check_annotations refuses this video (%d error(s)):\n"
                          % len(errors)
                          + "\n".join("  " + _here(e, tree) for e in errors[:9]))
    half = len({m.rsplit(": missing", 1)[0] for m in halves})
    if half:
        notes.append("%d chunk%s half glossed -- kept, not refused: finish %s "
                     "in the player" % (half, "" if half == 1 else "s",
                                        "it" if half == 1 else "them"))
    notes += ["check_annotations: " + _here(w, tree) for w in warnings[:5]]
    notes.append("%d captions, %d chunks, %d words -- %s, glossed in %s"
                 % (nseg, nch, nw, L.name, G.name))
    return notes


# ------------------------------------------------------------------ installing one
def _reattach(dest, old, kept):
    """A `text` bundle over a book that still has its narration: book.json
    pointed back at what stayed.  -> notes

    install deletes no part of a narration (the docstring at the top says why
    at length), and the recording, the timings and the review have just been
    carried across.  But a `text` bundle's book.json says the book has none,
    and a book.json saying that beside a 219 MB file that is still there is a
    state no door of this toolbox produces: the reader would show no
    controls, the library would say "no audio yet", and the person who
    uploaded a chapter would have every reason to think their recording had
    gone.  Keeping the bytes and losing the pointer is not keeping the
    narration.  So the two fields come back -- from the OLD book.json, which
    is the record of what they said, and only where what they name is still
    there to be named.  What is tested for existence is that old value and
    never anything out of the zip, so this cannot be talked into naming a
    file the uploader chose: it is the toolbox's own writing, put back.
    """
    back, why = {}, ""
    try:
        with open(os.path.join(old, "book.json"), encoding="utf-8") as f:
            was = json.load(f)
        if not isinstance(was, dict):
            raise ValueError("book.json is not an object")
        for k in NARR_FIELDS:
            v = was.get(k)
            if isinstance(v, str) and v and os.path.exists(
                    os.path.join(dest, v.replace("/", os.sep))):
                back[k] = v
            elif isinstance(v, list) and v:
                # A BOOK RECORDED IN PARTS.  The list is put back only when
                # every file it names is still here: half a list of pointers
                # is worse than none, because the reader would offer a
                # recording that cannot play and say nothing about the rest.
                here = [r for r in v
                        if isinstance(r, dict) and isinstance(r.get("audio"), str)
                        and r["audio"] and os.path.exists(
                            os.path.join(dest, r["audio"].replace("/", os.sep)))]
                if len(here) == len(v):
                    back[k] = v
        if back:
            path = os.path.join(dest, "book.json")
            with open(path, "rb") as f:
                text = f.read().decode("utf-8")
            meta = json.loads(text)
            meta.update(back)
            out = json.dumps(meta, ensure_ascii=False, indent=2)
            with open(path, "wb") as f:
                f.write((out + "\n" if text.endswith("\n") else out).encode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        # The files themselves are still in the book either way, and the
        # reader's narration panel offers a recording it finds in audio/.
        back, why = {}, " -- book.json could not be pointed back at it (%s)" % e
    note = ("this bundle is the `text` shape and its book.json says the book has no "
            "narration; the one that was here is kept (%s)%s"
            % (", ".join(kept), why))
    if back:
        note += ", and book.json names %s again" % " and ".join(sorted(back))
    if "timings.json" in kept:
        note += (". The times are safe in timings.json, but the chapters this bundle "
                 "carries have no `% @par` comments, which is what the reader reads "
                 "them from: the next build of the book (build on its card in the "
                 "library) writes them back from timings.json")
    return [note]


# WHAT IS DERIVED FROM THE TEXT, and is therefore a lie the moment the text
# is replaced.  A bundle carries none of these -- "no PDF and no built
# reader: those are derived, and one carried back in would be a lie" -- and
# for the same reason a replace must not carry the OLD ones forward either.
#
# It used to.  Everything the shape did not own was kept, which is right for
# a recording and wrong for these: you brought a book back, built it, and
# opened a reader made from the text you had just replaced -- and could not
# get rid of it, because .reader-key was kept too and build.sh reads that key
# to decide the reader is already current.  Worse where the old copy had
# lived at another depth: a reader built under books/<slug>/ links
# ../../../lib/parseh.css, which from books/<language>/<slug>/ is one level
# short, so every stylesheet on the page 404s and the book opens unstyled and
# dead.  They are thrown away now, and the answer says so.
DERIVED_NAMES = ("reader", ".reader-key", ".build-key",
                 "main.pdf", "main.aux", "main.log", "main.toc", "main.out")


def _is_derived(entry):
    return entry in DERIVED_NAMES or entry.startswith("frankdraft.")


def _put(tree, dest, kind, mode):
    """Move the validated tree to dest.  -> (what was kept from the old
    directory, notes).

    Two renames, in this order: the old directory out of the way, the new one
    in.  Both are renames inside one directory, so neither can half-happen,
    and the destination is never a half-written tree -- a reader refreshing
    mid-install sees the old book or the new one.  Only then is what the
    bundle does not own carried across: the built PDF, the reader, the build
    keys, and whatever of the narration THIS shape left out.  That order is
    deliberate.  Doing it before the swap would mean a failure could leave
    the OLD directory short of its narration, and the narration is the one
    thing here that cannot be made again.
    """
    kept, notes = [], []
    parent = os.path.dirname(dest)
    hold = old = None
    if os.path.exists(dest):
        hold = tempfile.mkdtemp(prefix=HOLD, dir=parent)
        old = os.path.join(hold, os.path.basename(dest))
        os.rename(dest, old)
    try:
        os.rename(tree, dest)
    except OSError as e:
        if old:
            os.rename(old, dest)             # put back exactly what was there
            shutil.rmtree(hold, ignore_errors=True)
        raise BundleError("the tree could not be moved into place (%s); nothing was "
                          "changed" % e)
    if not hold:
        return kept, notes
    stuck = False
    dropped = []
    for entry in sorted(os.listdir(old)):
        if _owned(kind, entry, mode):
            # THE FILM IS A VIDEO'S NARRATION: the one thing here that cannot
            # be made again.  A bundle whose manifest SAYS `full` and carries
            # no film used to take the old one with it -- not to the trash,
            # nowhere -- because the name was owned by that shape and the
            # bundle's version, which did not exist, had won.  A film is
            # given up only to another film.
            # AND SO IS THE WAVEFORM, for the same reason at a smaller
            # size: it is an hour of somebody's afternoon, not a thing the
            # next build makes again, and a bundle made before it was
            # recorded carries none.  Given up only to another waveform.
            if entry in ("waveform.json", "wordtimes.json") and not os.path.exists(
                    os.path.join(dest, entry)):
                pass                          # keep the one that is here
            elif kind == "book" and entry in (ANNOT_DIR, ORIGINAL_DIR) and not os.path.exists(
                    os.path.join(dest, entry)):
                # THE RECORD OF HOW A BOOK WAS MADE, AND WHAT IT WAS MADE FROM,
                # are given up only to another.  A bundle from before a0.4.2, or
                # a zip somebody made by hand, carries neither, and a replace
                # by it must not throw a book's annot/ and original/ away
                pass
            elif not (is_media_name(entry) and not film_at(dest)):
                continue                      # the bundle's version has won
        if _is_derived(entry):
            # made from the text that has just been replaced, so it describes
            # a book that is no longer there.  Left behind in the hold and
            # thrown away with it; the next build makes them again.
            dropped.append(entry)
            continue
        # nothing here can already exist at the destination: _entries lets
        # only names this shape owns through, and those are the ones skipped
        # above -- which matters, because shutil.move into an existing
        # directory puts the tree INSIDE it (the trap trash_video documents).
        # It is also the whole of how a `text` bundle keeps a recording: what
        # the shape does not own, the old directory keeps.
        try:
            shutil.move(os.path.join(old, entry), os.path.join(dest, entry))
            kept.append(entry)
        except OSError as e:
            stuck = True
            notes.append("%s could not be carried over from the old directory (%s); "
                         "it is in %s" % (entry, e, _rel(hold, ROOT)))
    narr = [e for e in kept if e == NARR_DIR or e == NARR_PAGE or e in NARR_FILES]
    if kind == "book" and mode == "text" and narr:
        notes += _reattach(dest, old, narr)
    elif (kind == "book" and mode == "linked" and NARR_DIR in kept
          and os.path.exists(os.path.join(dest, "timings.json"))):
        # The timings came in with the bundle and the recording did not.
        # They are the same book's, or they are not, and nothing here can
        # tell: an alignment names the file it was made against, never its
        # contents.
        notes.append("the recording already in %s/ was kept, and the timings are "
                     "this bundle's; if they were made against another recording, "
                     "put that one in %s/ instead" % (NARR_DIR, NARR_DIR))
    if dropped:
        notes.append("%s came from the book that was here and describe its text, "
                     "not this one, so %s thrown away -- build the book again to make them anew"
                     % (", ".join(dropped),
                        "it was" if len(dropped) == 1 else "they were"))
    if not stuck:
        shutil.rmtree(hold, ignore_errors=True)
    return kept, notes


def _unpack(z, files, dirs, tree):
    """The checked entries onto the disk under `tree`, and nothing else."""
    os.makedirs(tree)
    for rel in dirs:
        os.makedirs(os.path.join(tree, *rel.split("/")), exist_ok=True)
    total = media = 0
    for arc, rel in files:
        path = os.path.join(tree, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            src = z.open(arc)
        except (zipfile.BadZipFile, OSError, RuntimeError) as e:
            raise BundleError("%s cannot be read out of the bundle (%s)" % (rel, e))
        with src, open(path, "wb") as out:
            while True:
                try:
                    chunk = src.read(1 << 16)
                except (zipfile.BadZipFile, OSError, RuntimeError) as e:
                    # a bad CRC: the file arrived corrupt.  The staging tree
                    # goes with the refusal, so a half-written chapter never
                    # reaches the book
                    raise BundleError("%s is corrupt in the bundle (%s)" % (rel, e))
                if not chunk:
                    break
                # the header's file_size, counted in _entries, is the
                # writer's word for it; this is the reader's, and it is
                # counted against the same two budgets
                if _is_media(rel):
                    media += len(chunk)
                    if MAX_MEDIA is not None and media > MAX_MEDIA:
                        raise BundleError("the recording in this bundle is more than "
                                          "%s -- stopped" % _size(MAX_MEDIA))
                elif _is_original(rel):
                    pass                            # the person's own file: written as it is read
                else:
                    total += len(chunk)
                    if total > MAX_UNPACKED:
                        raise BundleError("this bundle unpacks to more than %s of "
                                          "text -- stopped" % _size(MAX_UNPACKED))
                out.write(chunk)


def install(data, replace=False, root=ROOT):
    """Put a bundle into the toolbox, or refuse.

    -> {ok, kind, language, gloss, audio, name, folder, dir, files, bytes,
        dropped, replaced, kept, notes}

    `replace` is the caller's word that overwriting is meant; without it a
    name already in the toolbox is an Exists refusal naming where it is.
    `root` is the toolbox to install into -- the real one by default, and a
    scratch copy for the tests, which must never write under the user's
    books/.

    The shape is the bundle's own (`audio`, and inspect reads it): a caller
    does not choose it here, because it is a fact about what is in the zip
    and not a thing to decide on the way in.  It moves what the bundle may
    carry and, for `text`, has the tree cleaned before a check runs on it --
    but it never deletes anything at the destination, which the docstring at
    the top of this file argues out.
    """
    what = inspect(data, root)
    if what["problems"]:
        raise BundleError(what["problems"][0])
    kind, name, folder, mode = (what["kind"], what["name"], what["folder"],
                                what["audio"])
    dest = _destination(kind, folder, name, root)
    here = what["at"]
    # A copy under some OTHER folder than this bundle's is checked FIRST, and
    # is a plain refusal whether or not replace was ticked: a replace
    # overwrites a directory where it stands, so it cannot reach that copy,
    # and Exists is the one refusal the page answers by offering a replace box
    # -- a tick the install then refuses is worse than the refusal itself.
    if here and here != what["dir"]:
        # install does not move the old copy either.  _already matches on the
        # NAME alone, and two languages may hold a book of the same slug on
        # purpose (build.sh's book_wanted takes <language>/<slug> for exactly
        # that), so WHICH of the two this bundle is a corrected copy of is the
        # uploader's knowledge and not the toolbox's -- moving on that guess
        # would bury an unrelated edition, and it would move a narration, a
        # PDF and a reader nobody asked about behind a URL that had changed.
        # The language it is filed under is what decides what they do next, so
        # the sentence names it.
        raise BundleError(
            "%s is already in the toolbox at %s, %s, and this bundle is %s: it "
            "would go to %s and leave the toolbox holding that name twice. "
            "Replacing cannot cross the two -- it overwrites the copy where it "
            "stands. Move %s to %s, or rename it, or delete it, then try again."
            % (name, here, _where_filed(kind, here),
               languages.get(what["language"]).name, what["dir"],
               here, what["dir"]))
    if here and not replace:
        raise Exists("%s is already in the toolbox, at %s. Ticking replace "
                     "overwrites its authored files with this bundle's."
                     % (name, here))
    parent = os.path.dirname(dest)
    made_folder = not os.path.isdir(parent)     # the first book of its language
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=STAGE, dir=parent)
    tree = os.path.join(stage, name)
    try:
        with _open(data) as z:
            files, dirs, _dropped, _total = _entries(z, kind, name, mode)
            _unpack(z, files, dirs, tree)
        notes = (_check_book(tree, name, what["language"], what["gloss"], mode)
                 if kind == "book"
                 else _check_video(tree, name, what["language"], what["gloss"]))
        kept, more = _put(tree, dest, kind, mode)
    finally:
        # whatever happened, the staging directory goes: a refusal leaves the
        # toolbox exactly as it was, which is the whole point of unpacking
        # beside the destination rather than into it -- down to the language
        # folder this install had to make and no longer needs
        shutil.rmtree(stage, ignore_errors=True)
        if made_folder and not os.path.exists(dest):
            try:
                os.rmdir(parent)
            except OSError:
                pass
    notes += more
    # A narration inside a bundle that is not the `full` shape is dropped by
    # the same allowlist, but for the opposite reason -- not "this is not the
    # book's" but "this is not this shape's" -- so it is said in those words.
    # Which of the two a name is, is asked of _owned rather than guessed at:
    # a file `full` would carry and this shape does not is the shape's doing,
    # and anything else is the ordinary drop.
    shaped = [r for r in what["dropped"]
              if not _owned(kind, r.split("/")[0], mode)
              and _owned(kind, r.split("/")[0], "full")]
    page = [r for r in what["dropped"] if r == NARR_PAGE]
    rest = [r for r in what["dropped"] if r not in shaped and r not in page]
    if shaped:
        notes.append("this bundle says `%s` and carries %d file(s) of the narration "
                     "anyway; they were left out, which is what `%s` means: %s"
                     % (mode, len(shaped), mode, ", ".join(shaped[:5])))
    if page:
        notes.append("%s was left out: it is a page, and a bundle may not install one "
                     "under books/, which is served as static files. The one this "
                     "book already has, if any, is where it was." % NARR_PAGE)
    if rest:
        notes.append("%d file(s) in the bundle are not a %s's authored files and "
                     "were left out: %s" % (len(rest), kind, ", ".join(rest[:5])))
    if kind == "book" and any(k in kept for k in ("reader", "main.pdf")):
        notes.append("the PDF and the reader are still the old ones until the book "
                     "is rebuilt")
    return {"ok": True, "kind": kind, "language": what["language"],
            "gloss": what["gloss"], "audio": mode, "name": name,
            "folder": folder, "dir": what["dir"],
            # the same shape inspect hands back, under the same name: a caller
            # that showed the one and then the other must not have to ask
            # which of them counted and which listed
            "files": what["files"], "bytes": what["bytes"],
            "dropped": what["dropped"],
            "replaced": here, "kept": kept, "notes": notes}


# ------------------------------------------------------------------ the CLI
def _resolve(arg):
    """A directory, a book slug or <folder>/<slug>, or a video id -- for a
    person at a prompt, who has the name in their head and not the path."""
    if os.path.isdir(arg):
        return arg
    for kind in SHAPE:
        marker = "book.json" if kind == "book" else "video.json"
        top = os.path.join(ROOT, *SHAPE[kind]["under"])
        if not os.path.isdir(top):
            continue
        for cand in (os.path.join(top, arg),
                     *(os.path.join(top, f, arg) for f in sorted(os.listdir(top))
                       if os.path.isdir(os.path.join(top, f)))):
            if os.path.isfile(os.path.join(cand, marker)):
                return cand
    raise BundleError("no book or video called %r -- give a directory, a slug, or a "
                      "video id" % arg)


def _kind_of(directory):
    if os.path.isfile(os.path.join(directory, "book.json")):
        return "book"
    if os.path.isfile(os.path.join(directory, "video.json")):
        return "video"
    raise BundleError("%s is neither a book (book.json) nor a video (video.json)"
                      % directory)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="a book or a video -> one .zip")
    p.add_argument("what", help="a directory, a book slug, or a video id")
    p.add_argument("--audio", "--media", dest="audio", default=None, choices=MODES,
                   help="how much of the media comes with it: the text alone, "
                        "everything but the recording, or all of it.  A book "
                        "defaults to %s; a video that IS a file defaults to "
                        "full, because a transcript of a film nobody can watch "
                        "is not much" % DEFAULT_MODE)
    p.add_argument("-o", "--out", default=None, help="where to write it")
    p = sub.add_parser("inspect", help="what is in a bundle; nothing is written")
    p.add_argument("file")
    p = sub.add_parser("install", help="a bundle -> the toolbox")
    p.add_argument("file")
    p.add_argument("--replace", action="store_true",
                   help="overwrite the book or video of that name")
    p.add_argument("--root", default=ROOT, help="the toolbox to install into")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "pack":
            d = os.path.abspath(_resolve(a.what))
            kind = _kind_of(d)
            data, fname = (pack_book(d, a.audio or DEFAULT_MODE) if kind == "book"
                           else pack_video(d, a.audio))
            out = a.out or fname
            with open(out, "wb") as f:
                f.write(data)
            take, left = _carried(kind, d, video_mode(d, a.audio) if kind == "video"
                                  else (a.audio or DEFAULT_MODE))
            print("%s -> %s  (%d files, %d kB)" % (_rel(d, ROOT), out,
                                                   len(take), len(data) // 1024))
            for name in take:
                print("   " + name)
            if left:
                print("   not carried (derived, personal or another shape's): "
                      + ", ".join(left[:8]) + (" ..." if len(left) > 8 else ""))
            if kind == "book" and not _narration(d, _book_at(d).meta)["any"]:
                print("   this book has no narration: text, linked and full are one "
                      "bundle, and this is it")
        elif a.cmd == "inspect":
            w = inspect(a.file)
            print("%s %s [%s, glossed in %s]%s  %d files, %d kB, written %s by %s"
                  % (w["kind"], w["name"], w["language"], w["gloss"],
                     "  audio: " + w["audio"] if w["audio"] else "",
                     len(w["files"]), w["bytes"] // 1024, w["exported"],
                     w["software"]))
            for name in w["files"]:
                print("   " + name)
            for name in w["dropped"]:
                print("   (not a %s's authored file, would be left out) %s"
                      % (w["kind"], name))
            print("goes to: %s%s" % (w["dir"] or "?",
                                     "  -- already here at " + w["at"] if w["at"] else ""))
            for pr in w["problems"]:
                print("PROBLEM: " + pr)
            return 1 if w["problems"] else 0
        else:
            r = install(a.file, replace=a.replace, root=os.path.abspath(a.root))
            print("installed %s %s [%s, glossed in %s]%s -> %s  (%d files)"
                  % (r["kind"], r["name"], r["language"], r["gloss"],
                     "  audio: " + r["audio"] if r["audio"] else "", r["dir"],
                     len(r["files"])))
            if r["replaced"]:
                print("   replaced %s%s" % (r["replaced"],
                                            ", kept " + ", ".join(r["kept"]) if r["kept"] else ""))
            for n in r["notes"]:
                print("   note: " + n)
            if r["kind"] == "book":         # a video's player has nothing to build
                print("   rebuild with: ./build.sh %s/%s" % (r["folder"], r["name"]))
    except BundleError as e:
        print("refused: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
