#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Which Parseh this is (TO-DO §16.1): its version, read from one file, and
the numbers of the shapes of what it writes.

    import version
    version.VERSION                         this tree's, as its VERSION spells it
    version.parse("a0.3.10")                a key: versions compare as their keys do
    version.compare("a0.3.9", "a0.3.10")    -1, 0 or 1
    version.rc("a0.3.2-rc2")                2: the rehearsal's number, None for a version
    version.base("a0.3.2-rc2")              "a0.3.2": the version a rehearsal rehearses
    version.formats()                       {"parseh-bundle": 1, "parseh-book": 1, ...}
    version.lowered(installed, incoming)    the formats a move would take DOWN

ONE FILE, READ ONCE.  The version is the one line of VERSION at the root of
the tree, and this module is the only Python that opens it: the server's
Server header and its first line in the log, the studio's Server header, the
"software" a bundle is stamped with, the user agent every downloader sends and
the foot of the hub all ask `version.VERSION`.  It is a plain file and not a
constant written in here because a shell script has to read it too, and
install.sh may run before any Python exists on the machine (it fetches one): a
line is read with `cat` in a shell and with `for /f` in a .bat, where Python
source could only be picked at with a pattern.  And it is not CHANGELOG.md's
top heading, because a heading is prose, and an edit to prose must never change
what the running program calls itself.  The one more thing to bump is held to
the other two -- the tag and the changelog's top heading -- by the release
checks (lib/changelog.py reads the changelog), so it cannot be bumped wrong
without a machine saying so.

A tree with no VERSION, or a VERSION this module cannot read, is refused at
import, in words: every release carries the file beside this one, so its
absence means an install somebody took apart, and a Parseh that does not know
what it is must not stamp a guess into every bundle it writes.

THE SHAPE, AND THE ORDER.  A version is spelt as the tags and the changelog
spell it: a stage letter, then whole numbers joined by dots -- `a0.3.1`,
`a1.0`, one day `b1.0` or a plain `1.0`.  The rule the updater (TO-DO §13.16)
compares by, and the only one anything here may use:

  1. THE STAGE FIRST.  Every `a` (alpha) comes before every `b` (beta), and
     every `b` before a version with no letter at all.  The letter names a
     period of the project, not a pre-release of the numbers after it, so
     b0.1 is later than a0.9 -- which is NOT how PEP 440 reads `1.0a1`, and
     is exactly why the rule is written here rather than borrowed.
  2. THEN THE NUMBERS, one by one, AS NUMBERS: a0.3.10 is later than a0.3.9,
     which comparing the two strings would get backwards.
  3. A MISSING NUMBER IS A ZERO: a1.0 and a1.0.0 are one version.
  4. A REHEARSAL COMES BEFORE ITS VERSION.  `aX.Y.Z-rcN` -- a0.3.2-rc1 --
     is a release candidate: the name of a tag a release is rehearsed with
     on GitHub before its real tag is pushed (the owner, 2026-09-25;
     docs/releasing.md).  It sorts after every earlier version and before
     the version it rehearses, and the rehearsals among themselves by N:
     a0.3.1 < a0.3.2-rc1 < a0.3.2-rc2 < a0.3.2.  N counts from 1 and has no
     leading zero.  It is the name of a TAG, and of the zip and the manifest
     built from it, and of nothing else: VERSION and the changelog's
     headings name the version being made, a0.3.2, the whole time it is
     rehearsed -- a rehearsal is the same work, not a version of its own --
     so read() and lib/changelog.py refuse one.  An install made from a
     rehearsal's zip says so in its manifest, and a later update from it to
     the version itself goes forward.

Anything else -- a leading `v`, a number with a leading zero, any other word
after the numbers (`a0.3.2rc1`, `a0.3.2-beta`, `a0.3.2-rc0`) -- is refused by
parse(), so nothing ambiguous reaches a comparison.

THE DATA'S OWN NUMBERS ARE NOT THE VERSION.  What Parseh writes to the disk
has a shape, and a shape changes far less often than the software: a book
written by a0.2.0 is read by a0.3.1 exactly as it stands.  Each shape has its
own whole number, kept BESIDE THE CODE THAT WRITES IT -- the stamps written
into the files themselves ("parseh-bundle/<number>" and its siblings), and a
plain number for every store written without a stamp (a book's book.json and
its narration's timings.json, a deck's schedule, a video's waveform.json, the
studio's documents, the Anki decks, the settings in config/, the databases
the optional tools build in dict/, corpus/ and components/ ...).  Every place
a person's things are kept has at least one (tests/test_version.py holds
that against lib/release.py's list of them).  FORMATS below names where each
one is kept; formats() gathers them into one dict, which the release manifest
(.parseh-release.json) carries; and the updater will not, unless the person
insists after being told what may not survive, move to a version whose number
for any of them is LOWER than the installed one's -- an older Parseh may not
read what a newer one wrote (lowered() says which).  A number is RAISED when
the shape changes so that the Parseh before it would read the new files wrong;
a field added that an older reader simply ignores is not such a change.

READ FROM THE SOURCE, NOT IMPORTED.  formats() parses each file with `ast` and
takes the constant's value, running nothing: serve.py is one of the files, and
importing it would load the whole server; and the release builder asks the
same question of a tree it has only unpacked, whose modules must not run in
the builder's process.  The price is that each constant is a plain literal
assigned at the top level of its file, which is what they all are.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
# realpath: a test's scratch tree links lib/ in from the checkout, and the
# VERSION it means is the checkout's, beside the real lib/
ROOT = os.path.dirname(HERE)
FILE = "VERSION"

# a stage letter, in the order the stages come; "" is a version with none
STAGES = ("a", "b", "")
SHAPE = re.compile(r"(?P<stage>[ab]?)(?P<numbers>(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+)"
                   r"(?:-rc(?P<rc>[1-9][0-9]*))?")
# where a version stands among the rehearsals of it: every rehearsal (0, N)
# before the version itself (1,), which is how a tuple compares
_ITSELF = (1,)


def _match(v):
    m = SHAPE.fullmatch(v) if isinstance(v, str) else None
    if not m:
        raise ValueError("%r is not a version: it is spelt like a0.3.1, a stage letter "
                         "(a or b, or none) and whole numbers joined by dots -- and a "
                         "rehearsal's tag like a0.3.1-rc1" % (v,))
    return m


def parse(v):
    """A version -> its key, a tuple that orders as the versions do (the rule
    in this module's docstring).  ValueError for anything not spelt as one."""
    m = _match(v)
    numbers = [int(n) for n in m.group("numbers").split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()                               # a1.0.0 is a1.0 is a1
    rehearsal = (0, int(m.group("rc"))) if m.group("rc") else _ITSELF
    return (STAGES.index(m.group("stage")), tuple(numbers), rehearsal)


def compare(a, b):
    """-1 when `a` is earlier than `b`, 0 when they are one version, 1 when
    `a` is later.  Both are parsed, so a malformed one is a ValueError and
    never a guess."""
    ka, kb = parse(a), parse(b)
    return (ka > kb) - (ka < kb)


def rc(v):
    """The number of the rehearsal `v` names -- 2 for a0.3.2-rc2 -- or None
    when `v` is a version itself.  ValueError for anything not spelt as one."""
    m = _match(v)
    return int(m.group("rc")) if m.group("rc") else None


def base(v):
    """The version `v` rehearses -- "a0.3.2" for a0.3.2-rc2 -- and `v` itself,
    as it is spelt, when it is a version.  ValueError for anything not spelt
    as one."""
    m = _match(v)
    return m.group("stage") + m.group("numbers")


def spelt(text, where=FILE):
    """The text of a VERSION file -> the version it names.  ValueError, in
    words, when it holds more than one line, something that is not a
    version, or a rehearsal's name (the docstring's rule 4: a rehearsal is a
    tag's name, and VERSION names the version it rehearses).  `where` names
    the file in those words: the path, or the commit it was read at."""
    lines = text.splitlines()
    if len(lines) != 1:
        raise ValueError("%s must hold one line, the version, and holds %d" % (where, len(lines)))
    v = lines[0].strip()
    try:
        parse(v)
    except ValueError as e:
        raise ValueError("%s: %s" % (where, e)) from None
    if rc(v) is not None:
        raise ValueError("%s says %s, a rehearsal's name: it names the version being "
                         "rehearsed, %s, and only the tag carries -rc%d"
                         % (where, v, base(v), rc(v)))
    return v


def read(root=ROOT):
    """The version the tree at `root` says it is: its VERSION file's one line.

    ValueError when the file is missing, holds more than one line, or holds
    something that is not a version -- each said in words (spelt())."""
    path = os.path.join(root, FILE)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise ValueError("%s cannot be read (%s): every copy of Parseh carries it, so this "
                         "one is incomplete -- install it again from a release"
                         % (path, e.strerror or e)) from None
    return spelt(text, path)


VERSION = read()


# ------------------------------------------------------------ the data's shapes
# name: (the file the number is kept in, relative to the root; the constant
# holding it; what it is, in the words the updater says it to a person in).
# A constant is either a stamp the files carry, "<name>/<number>", or a plain
# number for a store written without one.  EVERY store Parseh writes has a row
# here, and tests/test_version.py fails when a new one is not -- a stamp
# written anywhere, or a file kept in config/.
FORMATS = {
    "parseh-speech": ("lib/speechconfig.py", "STORE_FORMAT", "speech preferences (config/speech.json)"),
    "parseh-pending-transcription": ("lib/asrpending.py", "FORMAT", "private resumable transcription drafts (youtube/videos/.pending-transcriptions/)"),
    "parseh-lm-likelihood": ("lib/lmlikelihoodconfig.py", "STORE_FORMAT", "the host-local numerical scoring settings (config/lm-likelihood.json)"),
    "parseh-llm": ("lib/llmconfig.py", "STORE_FORMAT", "the host-local reusable LLM connection (config/llm.json)"),
    "parseh-bundle": ("lib/bundle.py", "FORMAT",
                      "a book or a video downloaded as one file"),
    "parseh-shelf": ("lib/shelf.py", "FORMAT",
                     "a backup of all the books or all the videos"),
    "parseh-narration": ("serve.py", "NARR_FORMAT",
                         "a narration downloaded on its own"),
    "parseh-exercise-deck": ("markdown/app/decks.py", "FORMAT",
                             "an exercise deck, on the disk and exported"),
    "parseh-exercise-shelf": ("markdown/app/decks.py", "SHELF_FORMAT",
                              "a backup of every exercise deck"),
    "parseh-schedule": ("markdown/app/decks.py", "SCHEDULE_FORMAT",
                        "when each exercise of a deck is due, and its answers so far"),
    "parseh-book": ("lib/books.py", "BOOK_FORMAT",
                    "a book's own record of itself, book.json"),
    "parseh-reading": ("lib/reading.py", "READING_FORMAT",
                       "what was decided about a book's text, reading.json"),
    "parseh-video": ("youtube/lib/check_annotations.py", "VIDEO_FORMAT",
                     "a video's own record of itself, video.json"),
    "parseh-annotations": ("youtube/lib/check_annotations.py", "ANNOTATIONS_FORMAT",
                           "a video's captions and their glosses, annotations.json"),
    # keys added inside `settings` (a0.5.0: bk_cont, the bk_lvl: level names) do
    # not change this shape and an older Parseh ignores them: the number stays
    # (lib/prefs.py says why, beside STORE_FORMAT)
    "parseh-prefs": ("lib/prefs.py", "STORE_FORMAT",
                     "each book's reading place and the settings that follow you "
                     "(config/prefs.json)"),
    "parseh-network": ("lib/network.py", "STORE_FORMAT",
                       "who may reach Parseh, and the devices let in (config/network.json)"),
    "parseh-languages": ("lib/languages.py", "STORE_FORMAT",
                         "the languages added on this computer (config/languages.json)"),
    "parseh-digests": ("lib/offline.py", "DIGESTS_FORMAT",
                       "the checksums a phone checks what it keeps against "
                       "(config/digests.json)"),
    "parseh-wheres": ("lib/offline.py", "WHERES_FORMAT",
                      "where in its book each recording is, as a phone's keep sheet says it "
                      "(config/wheres.json)"),
    "parseh-updates": ("lib/updater.py", "STORE_FORMAT",
                       "whether Parseh looks for a new version once a day, and what it last "
                       "found (config/updates.json)"),
    # the LaTeX drawings (TO-DO §8.39, a0.4.0)
    "parseh-latex": ("lib/latexthemes.py", "STORE_FORMAT",
                     "the LaTeX themes, the default one and how long a drawing may take "
                     "(config/latex.json)"),
    "parseh-latex-theme": ("lib/latexthemes.py", "EXPORT_FORMAT",
                           "a LaTeX theme exported to a file"),
    "parseh-texmf": ("lib/texpackages.py", "MANIFEST_FORMAT",
                     "the TeX packages Parseh got for the LaTeX drawings, and their list "
                     "(texmf/)"),
    # a book made by an agent, in place (TO-DO §8.40, a0.4.2)
    "parseh-annot": ("lib/making.py", "ANNOT_FORMAT",
                     "the annotation JSON a book made by an agent was assembled from "
                     "(a book's annot/*.json)"),
    # the prompts a person wrote (a0.4.2)
    "parseh-prompts": ("lib/prompts.py", "STORE_FORMAT",
                       "your own prompts, and the studio's prompt moved in from the library "
                       "(config/prompts.json)"),
    "parseh-prompt": ("lib/prompts.py", "EXPORT_FORMAT",
                      "a prompt of yours exported to a file"),
    # the ARASAAC pictograms, fetched on Settings (a0.4.2, W9)
    "parseh-arasaac": ("lib/getarasaac.py", "ARASAAC_FORMAT",
                       "the ARASAAC pictograms, their words and their manifest (arasaac/)"),
    # where the optional analyzers are used (a0.6.0)
    "parseh-analysis": ("lib/analysisconfig.py", "STORE_FORMAT",
                        "where Parseh listens to the optional analyzers (config/analysis.json)"),
    # a book's narration, as the aligner leaves it beside the book
    "parseh-timings": ("lib/timestamp.py", "TIMINGS_FORMAT",
                       "where each sentence of a book's narration begins and ends "
                       "(a book's timings.json)"),
    "parseh-review": ("lib/timestamp.py", "REVIEW_FORMAT",
                      "the sentences of a book's narration left to check by ear "
                      "(a book's review.json)"),
    # a video's other files
    "parseh-parts": ("youtube/lib/merge_parts.py", "PARTS_FORMAT",
                     "the batches an older video's glosses were first written in "
                     "(a video's parts/*.json)"),
    "parseh-waveform": ("serve.py", "WAVEFORM_FORMAT",
                        "the picture of a video's sound, recorded while it played "
                        "(a video's waveform.json)"),
    "parseh-wordtimes": ("youtube/lib/wordtimes.py", "WORDTIMES_FORMAT",
                           "the timed words kept with a video, wordtimes.json"),
    # what is made from books and videos, kept beside them
    "parseh-library": ("markdown/app/store.py", "LIBRARY_FORMAT",
                       "the studio's documents, and the notes written into books and videos "
                       "(markdown/library/)"),
    "parseh-anki": ("youtube/lib/anki_store.py", "STORE_FORMAT",
                    "the Anki decks and their cards (youtube/anki/)"),
    "parseh-clips": ("lib/clips.py", "INFO_FORMAT",
                     "the recordings and pictures cut from books and videos, waiting for a "
                     "card (clips/)"),
    # the optional tools, as Parseh builds them from what it downloads
    "parseh-dictionary": ("lib/lookup.py", "DB_FORMAT",
                          "the dictionaries, as Parseh builds them (dict/)"),
    "parseh-corpus": ("lib/corpus.py", "DB_FORMAT",
                      "the translated sentences, as Parseh builds them (corpus/)"),
    "parseh-components": ("lib/getdecomposition.py", "PACK_FORMAT",
                          "the parts Chinese characters and kanji are built from (components/)"),
    "parseh-synonyms": ("lib/getsyn.py", "FORMAT",
                        "the English synonyms that match a machine translation's words to a "
                        "chunk's (mt/synonyms.en.json)"),
}


def _constant(path, name):
    """The literal assigned to `name` at the top level of the Python file
    `path`, found without running the file."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(value)
    raise ValueError("%s has no %s at its top level: lib/version.py's FORMATS says the "
                     "number is kept there" % (path, name))


def _number(fmt, value, where):
    """A constant's value -> the whole number it stands for."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("%s: %r is neither a number nor a stamp" % (where, value))
    if isinstance(value, int):
        n = value
    else:
        stamp, _, number = value.rpartition("/")
        if stamp != fmt or not number.isdigit():
            raise ValueError("%s: the stamp %r is not %s/<number>" % (where, value, fmt))
        n = int(number)
    if n < 1:
        raise ValueError("%s: a format's number starts at 1, and this is %d" % (where, n))
    return n


def formats(root=ROOT):
    """{name: number} for every shape of data the tree at `root` writes, read
    from its source (the docstring above says why not imported)."""
    out = {}
    for fmt, (rel, name, _what) in FORMATS.items():
        path = os.path.join(root, *rel.split("/"))
        out[fmt] = _number(fmt, _constant(path, name), "%s %s" % (rel, name))
    return out


def lowered(installed, incoming):
    """The formats a move from `installed` to `incoming` (two formats() dicts,
    one of them perhaps read from a release's manifest) would take DOWN,
    sorted -> [name, ...].  A format the incoming version does not know at all
    counts as lowered: that Parseh has never heard of the store, and whatever
    was kept in it is not read there."""
    return sorted(k for k, n in installed.items() if incoming.get(k, 0) < n)


def what(fmt):
    """A format's name -> what it is, in words for a person."""
    return FORMATS[fmt][2]


if __name__ == "__main__":
    # `python3 lib/version.py` prints the version; `formats` the data's
    # numbers as JSON -- for a developer, and for a release built from a tree
    # the builder must not import
    if sys.argv[1:] == ["formats"]:
        import json
        print(json.dumps(formats(), indent=2, sort_keys=True))
    else:
        print(VERSION)
