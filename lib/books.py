#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where a book lives and what it is called.

One directory per book under books/<language folder>/, each with a book.json:

    books/persian/farsi-shakar-ast/     books/japanese/<slug>/

Adding a title means adding a directory -- no tool has a list of books in it,
and none has a path to a particular book baked in.  The language folder is
the registry's `folder` (lib/languages.json says which folders there
are); the book's own language is book.json's "language" (a registry
code, default fa), and the two are expected to agree -- the JSON wins for
rendering, the folder for the URL, and a mismatch is reported once.

book.json declares a second language, "gloss": what the glosses are WRITTEN
in, which is not the same question as what the book teaches (an Italian
learning English wants the meanings in Italian).  Absent it is English, so
every book written before the field existed says what it always said.

    from books import find_book, all_books
    b = find_book("books/persian/<slug>")     # or a slug, or the current directory
    b.main            .../books/persian/<slug>/main.tex
    b.lang            the Lang record (b.lang.code, .dir, .strip(), .digits ...)
    b.gloss_lang      the Gloss record: what the glosses are written in
    b.has_audio       False when book.json has no audio, or the file is absent

A book.json found directly under books/ (the layout before languages) is
still read, as Persian, with a note to move it.
"""
import json
import os
import shutil
import time
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))
BOOKS_DIR = os.path.join(ROOT, "books")
FONTS = os.path.join(LIB, "fonts")

if LIB not in sys.path:
    sys.path.insert(0, LIB)
import languages  # noqa: E402

# The id the one recording of a book carries when book.json says nothing of
# narrations -- which is every book written before a book could have several.
# It is what the times of such a book are attributed to, and it is never
# written into book.json or into a `% @par` line: a book with one recording
# writes exactly the bytes it always wrote.
NARR_FIRST = "n1"

# THE SHAPE OF book.json, as a number (lib/version.py FORMATS).  Many modules
# write the file -- draft.py makes it, bookmeta.py edits its metadata, serve.py
# its list of recordings -- and every one of them writes the shape this module
# reads, so the number is kept here.  RAISE IT when the shape changes so that
# the Parseh before this one would read a book wrong; a field added that an
# older reader ignores (as "gloss" was, and "translit" is) is not such a change.
BOOK_FORMAT = 1


class Book:
    def __init__(self, directory):
        # REALPATH, not abspath.  Every asset the reader links -- the
        # stylesheet, the script, the fonts, the hub -- is a path relative
        # from this directory to the toolbox's own, and os.path.relpath
        # between two SPELLINGS of one directory is not a short hop but a
        # walk out to the root and back down the other name.  Reach the
        # toolbox through a symlink (~/allCoding -> /run/media/.../allCoding)
        # and that is exactly what happens: the roots come from __file__ as
        # it was invoked, this comes from the working directory, which Python
        # has already resolved, and the reader ends up linking
        # ../../../../../../../../../../../home/... for a file four levels
        # up.  Nothing loads, and the book opens with no styling at all.
        # One spelling, whatever path the toolbox was reached by.
        self.dir = os.path.realpath(directory)
        with open(os.path.join(self.dir, "book.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self._warned = False

    def _rel(self, key):
        v = self.meta.get(key)
        if not v:
            return None
        return os.path.abspath(os.path.join(self.dir, v))

    # --- identity -----------------------------------------------------------
    @property
    def slug(self):
        return self.meta.get("slug") or os.path.basename(self.dir)

    @property
    def title(self):
        return self.meta.get("title", self.slug)

    @property
    def title_latin(self):
        return self.meta.get("title_latin", "")

    @property
    def author(self):
        return self.meta.get("author", "")

    @property
    def author_latin(self):
        return self.meta.get("author_latin", "")

    # --- language -----------------------------------------------------------
    @property
    def declared_language(self):
        """What book.json itself says under "language", lower-cased, or None
        when it says nothing.  Not necessarily a registry code."""
        code = (self.meta.get("language") or "").strip().lower()
        return code or None

    @property
    def language(self):
        """The registry code: book.json's "language", else the folder the
        book sits in, else the default (Persian).  A declared code the
        registry does not know is read as the folder's language so the
        book still lists; language_problem() names it, check_placement()
        reports it and find_book() refuses it."""
        code = self.declared_language
        if code in languages.LANGS:
            return code
        by_dir = languages.detect_from_path(self.dir)
        return by_dir.code if by_dir else languages.DEFAULT

    @property
    def variety(self):
        """The variety the book is written in (book.json `variety`: Arabic's
        egy, lev, gulf, mor), or None for the standard language -- and for a
        key the language does not have."""
        v = (self.meta.get("variety") or "").strip().lower()
        return v if v and self.lang.variety_of(v) else None

    @property
    def lang(self):
        return languages.get(self.language)

    def language_problem(self):
        """The complaint about a book.json "language" that is not a registry
        code, or None.  Kept apart from check_placement so the tools that
        write files can refuse instead of merely warning: a misspelled code
        must not quietly become the folder's language (or Persian) in the
        files they produce."""
        code = self.declared_language
        if code is None or code in languages.LANGS:
            return None
        return ("!! %s: book.json language %r is not a registry code (known: %s), read as %s"
                % (self.slug, code, ", ".join(languages.CODES), self.language))

    @property
    def declared_gloss(self):
        """What book.json itself says under "gloss", lower-cased, or None
        when it says nothing.  Not necessarily a code a gloss may use, and
        not necessarily a string: a hand-edited book.json may hold a number
        there, and spelling it out makes it an unknown gloss language --
        which gloss_problem() reports -- instead of an AttributeError out of
        whatever tool asked."""
        code = self.meta.get("gloss")
        code = ("" if code is None else str(code)).strip().lower()
        return code or None

    @property
    def gloss(self):
        """The code the glosses are written in: book.json's "gloss", else
        English.  There is no folder to fall back on the way `language` has
        one -- where a book is filed says what it teaches and nothing about
        what language the meanings are in -- so an unusable code is read as
        English, which is what every book that says nothing means, and
        gloss_problem() names it."""
        return languages.gloss_or_default(self.declared_gloss).code

    @property
    def gloss_lang(self):
        return languages.gloss(self.gloss)

    def gloss_problem(self):
        """The complaint about a book.json "gloss" this toolbox cannot set,
        or None.  Kept apart from check_placement for the reason
        language_problem is: the tools that WRITE files must refuse it
        rather than gloss a chapter in a language nobody asked for, and
        hyphenating an Italian gloss by English rules is the silent kind of
        wrong -- it reaches the reader as `faleg-name` and nothing else."""
        code = self.declared_gloss
        if code is None:
            return None
        try:
            languages.gloss(code)
        except KeyError:
            return ("!! %s: book.json gloss %r is not a language this toolbox can "
                    "write in (it can: %s), read as English"
                    % (self.slug, code, ", ".join(languages.GLOSS_CODES)))
        return None

    @property
    def folder(self):
        """The language folder the book is filed under, or None for a book
        lying directly under books/ (the layout before languages)."""
        parent = os.path.basename(os.path.dirname(self.dir))
        return parent if languages.by_folder(parent) else None

    def check_placement(self, say=None):
        """Report a book whose folder and declared language disagree, whose
        gloss language is one nothing here can set, or which lies directly
        under books/.  Once per Book object."""
        if self._warned:
            return
        self._warned = True
        say = say or (lambda s: print(s, file=sys.stderr))
        for problem in (self.language_problem(), self.gloss_problem()):
            if problem:
                say(problem)
        want = self.lang.folder
        if self.folder is None:
            say("note: %s lies directly under books/ -- move it to books/%s/%s"
                % (self.slug, want, os.path.basename(self.dir)))
        elif self.folder != want:
            say("!! %s is filed under books/%s/ but book.json says language %s (books/%s/)"
                % (self.slug, self.folder, self.language, want))

    # --- paths --------------------------------------------------------------
    @property
    def main(self):
        return os.path.join(self.dir, self.meta.get("main", "main.tex"))

    @property
    def pdf(self):
        return os.path.splitext(self.main)[0] + ".pdf"

    @property
    def source_dir(self):
        return os.path.join(self.dir, "source")

    @property
    def paras_dir(self):
        return os.path.join(self.source_dir, "paras")

    @property
    def clean_text(self):
        return os.path.join(self.source_dir, "clean.txt")

    @property
    def reader_dir(self):
        return os.path.join(self.dir, "reader")

    @property
    def reader_html(self):
        return os.path.join(self.reader_dir, "index.html")

    @property
    def timings(self):
        return os.path.join(self.dir, "timings.json")

    @property
    def review_json(self):
        return os.path.join(self.dir, "review.json")

    @property
    def reading_json(self):
        """What somebody has decided about the text itself (lib/reading.py):
        the paragraphs that need not reproduce their source, and the runs of
        paragraphs folded away.  Absent until one of them is made."""
        return os.path.join(self.dir, "reading.json")

    @property
    def audio(self):
        return self._rel("audio")

    @property
    def transcript(self):
        return self._rel("transcript")

    @property
    def narrations(self):
        """Every recording this book has, in reading order.

        -> [{"id", "audio", "audio_rel", "transcript", "transcript_rel",
             "from", "to"}], the paths resolved the way `audio` resolves one.

        book.json's "narrations" is the many-recordings form: each record names
        its file, optionally its own transcript, and the stretch of text it
        covers as two subparagraphs, each named with its chapter -- "from":
        "2:1.1", "to": "2:3.4", since a label alone repeats in every chapter --
        with either left out meaning "to the end of the book that way".  A bare
        label ("1.1"), as older books have it, still reads: the first wearing
        it for a start, and for an end the first at or after the start
        (texparse.region_bounds).  It is how a
        narration is made a little at a time: record a few chapters, say which
        ones, align just those.

        A BOOK THAT SAYS NOTHING OF IT reads as exactly one narration covering
        everything, built from the old scalar "audio"/"transcript" -- which is
        every book written before this, and every book somebody records in one
        sitting.  Nothing about such a book changes anywhere: same id, same
        paths, same whole-book region.
        """
        out, seen = [], set()
        raw = self.meta.get("narrations")
        if isinstance(raw, list):
            for i, rec in enumerate(raw):
                if not isinstance(rec, dict):
                    continue
                nid = str(rec.get("id") or "").strip() or "n%d" % (i + 1)
                if nid in seen:                     # a hand-edited book.json
                    nid = "%s-%d" % (nid, i + 1)
                seen.add(nid)
                out.append({
                    "id": nid,
                    "audio": self._rel_to(rec.get("audio")),
                    "audio_rel": rec.get("audio") or "",
                    "transcript": self._rel_to(rec.get("transcript")),
                    "transcript_rel": rec.get("transcript") or "",
                    "from": str(rec.get("from") or "").strip(),
                    "to": str(rec.get("to") or "").strip(),
                })
        if out:
            return out
        # the one-recording book: the scalars, as they have always been read
        if self.meta.get("audio") or self.meta.get("transcript"):
            return [{"id": NARR_FIRST,
                     "audio": self.audio, "audio_rel": self.meta.get("audio") or "",
                     "transcript": self.transcript,
                     "transcript_rel": self.meta.get("transcript") or "",
                     "from": "", "to": ""}]
        return []

    def narration(self, nid):
        """One narration by id, or None."""
        for n in self.narrations:
            if n["id"] == nid:
                return n
        return None

    def _rel_to(self, v):
        """A path out of a narration record, resolved like Book._rel does."""
        if not v:
            return None
        return os.path.abspath(os.path.join(self.dir, v))

    # --- capability ---------------------------------------------------------
    @property
    def has_audio(self):
        """A book without a narration still builds; the reader simply omits
        every audio control instead of offering ones that cannot work.

        True when the old scalar names a file that is there, OR when any of
        the narrations does: a book recorded in parts has no one file to put
        in "audio", and it is still a book with a narration.
        """
        p = self.audio
        if bool(p) and os.path.exists(p):
            return True
        return any(n["audio"] and os.path.exists(n["audio"])
                   for n in self.narrations)

    @property
    def has_transcript(self):
        p = self.transcript
        return bool(p) and os.path.exists(p)

    @property
    def reorders(self):
        """book.json's "reorders": true -- a text read out of its written
        order (kanbun), so a chunk's reading is never compared with its word
        line (lib/wordline.py, check).  False for a book that says nothing,
        which is every book written in the order it is read."""
        return bool(self.meta.get("reorders"))

    @property
    def translit(self):
        """book.json's "translit": "ipa" -- the book's transliteration is IPA and
        not the language's usual scheme, so that the prompts ask for IPA by
        default and the checks written for the usual scheme step aside.  ""
        for a book that says nothing, which is every book made before the
        setting existed."""
        return "ipa" if self.meta.get("translit") == "ipa" else ""

    def rel_from_reader(self, path):
        """A path expressed relative to reader/index.html."""
        if not path:
            return None
        return os.path.relpath(path, self.reader_dir)

    def rel_from_books(self):
        """The book's directory relative to books/, forward slashes: what a
        URL under /books/ is made of (persian/farsi-shakar-ast)."""
        return os.path.relpath(self.dir, BOOKS_DIR).replace(os.sep, "/")

    def __repr__(self):
        return "<Book %s [%s]%s>" % (self.slug, self.language,
                                     "" if self.has_audio else " (no audio)")


def book_dirs(root=BOOKS_DIR):
    """Every directory holding a book.json: books/<folder>/<slug>/ first, then
    -- the layout before languages -- books/<slug>/ itself."""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        # A DOT DIRECTORY IS NEVER CONTENT.  books/.trash/ is where a book
        # goes when it is taken off the shelf, and it keeps its book.json --
        # a trash you cannot put back is not a trash.  Without this the
        # walker would read .trash as a language folder and every book in it
        # as a book: deleted, and still in the library, still in the counts,
        # still built.  ytpages keeps the same rule for videos/.trash/, and
        # it is the rule bundle.py's LEAF enforces at the other end, so that
        # nothing arriving in a zip can make one.
        if name.startswith("."):
            continue
        if not os.path.isdir(d):
            continue
        if os.path.isfile(os.path.join(d, "book.json")):
            out.append(d)                          # legacy: directly under books/
            continue
        for sub in sorted(os.listdir(d)):
            if sub.startswith("."):
                continue
            sd = os.path.join(d, sub)
            if os.path.isfile(os.path.join(sd, "book.json")):
                out.append(sd)
    return out


def all_books(root=BOOKS_DIR, language=None):
    """Every book, in folder order; `language` (a code) narrows to one."""
    out = [Book(d) for d in book_dirs(root)]
    if language:
        out = [b for b in out if b.language == language]
    return out


def _checked(book):
    """The book, unless its book.json declares a language the registry does
    not know, or a gloss language this toolbox cannot set: find_book is how
    every pipeline tool gets the book whose files it writes, and those must
    not be produced in a guessed language -- in either of the two."""
    problem = book.language_problem() or book.gloss_problem()
    if problem:
        raise SystemExit(problem + " -- fix book.json before running a tool on it")
    return book


def trash_book(path):
    """Move a book directory under books/.trash/<slug>-<stamp>/ and return
    where it went.

    Moved and not removed.  A note in the studio is a page somebody can write
    again; a reading edition is weeks of glossing and may have a recording
    beside it that exists nowhere else, so the one gesture that ends it puts
    it somewhere the owner can still reach.  `.trash` and not `trash` because
    every walker here skips a dot directory, so what is in it stops being a
    book the moment it lands: it is off the shelf, out of the library page and
    out of every count, and it is still on the disk.

    The name is made unique first, for the reason ytpages.trash_video gives:
    shutil.move into a directory that already exists puts the tree INSIDE it,
    so deleting two books of one slug within a second would bury the older
    copy a level down and the path reported for it would be wrong.
    """
    trash = os.path.join(BOOKS_DIR, ".trash")
    os.makedirs(trash, exist_ok=True)
    base = os.path.join(trash, "%s-%s" % (os.path.basename(os.path.normpath(path)),
                                          time.strftime("%Y%m%d-%H%M%S")))
    dest, n = base, 1
    while os.path.exists(dest):
        n += 1
        dest = "%s-%d" % (base, n)
    shutil.move(path, dest)
    return dest


def find_book(where=None):
    """A directory holding a book.json, a slug (in any language folder), a
    <folder>/<slug> pair, or the book the current directory is in.  Refuses
    a book whose book.json names a language the registry does not have."""
    if where:
        cand = [where, os.path.join(BOOKS_DIR, where)]
        for c in cand:
            if os.path.isfile(os.path.join(c, "book.json")):
                return _checked(Book(c))
        # a bare slug: look through every language folder
        hits = [d for d in book_dirs() if os.path.basename(d) == where]
        if len(hits) == 1:
            return _checked(Book(hits[0]))
        if len(hits) > 1:
            raise SystemExit("%r names %d books: %s -- say which, as <folder>/<slug>"
                             % (where, len(hits),
                                ", ".join(os.path.relpath(h, BOOKS_DIR) for h in hits)))
        raise SystemExit("no book.json in %s" % where)
    d = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(d, "book.json")):
            return _checked(Book(d))
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit(
                "not inside a book. Pass --book <slug>, or cd into books/<language>/<slug>.\n"
                "Known: " + ", ".join(b.rel_from_books() for b in all_books()))
        d = parent


if __name__ == "__main__":
    for b in all_books():
        b.check_placement()
        print("%-26s %-3s gloss=%-5s %-22s %-24s audio=%s  tex=%s"
              % (b.rel_from_books(), b.language, b.gloss, b.title_latin,
                 b.author_latin, "yes" if b.has_audio else "no ",
                 "yes" if os.path.exists(b.main) else "no"))
