#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The dictionary behind a chunk nobody has glossed.

    import lookup
    lookup.available("fa")            # is there a dictionary for this language
    lookup.look_up("fa", "دوباره می‌سازمت وطن")

A reading edition and a video are worth reading only when the glosses are
written, and writing them takes weeks.  Until they are, every chunk is a
phrase the reader cannot get past.  This looks the words up.

WHAT THIS IS NOT.  It is not a gloss and must never be shown as one.  A
gloss is a person's judgement about THIS word in THIS sentence: which of
eleven senses is meant, what the ending is doing, why the idiom is not the
sum of its parts.  A dictionary knows none of that.  So everything here is
returned marked -- with the source it came from and the route by which the
word was found -- and both readers draw it in their own chrome, apart from
the written glosses, with the source named on it.  The studio's glossary has
shown a guess as a red row since it had rows (markdown/app/htmlgen.py); this
is the same instinct one door along.

Nothing here ever writes to a book, a video or the Anki store.  An entry
becomes a gloss only when somebody editing a chunk takes it from the sources
sidebar beside the gloss editor into the vocabulary field, and saves; the
save goes down the ordinary edit route (lib/texwrite.py,
youtube/lib/annwrite.py) with the ordinary checkers on the far side.  What
the sidebar inserts is built from a hit's `headword` and `head_sound` -- the
LEMMA's own sound, never the sound of the form the chunk happened to hold.

WHERE THE DATA IS.  `dict/<code>.db`, one SQLite file per language, built by
lib/getdict.py and carried by nobody: they are tens of megabytes, they are
somebody else's work under somebody else's licence, and the toolbox has
always shipped the doors and none of the content.  A language with no file
has no lookup, and both readers simply do not offer it -- the same way a
book with no narration has no scrub bar.  sqlite3 is in the standard
library, so this costs nothing to install.

WHY SQLITE AND NOT A FILE OF LINES.  A Wiktionary extract for one language
is 30-100 MB and the server is stdlib Python on somebody's laptop, answering
a click while a video plays.  An index and a page cache beat reading a file.

THE ONLY HARD PART is that a dictionary is keyed by lemma and a chunk is
running text: `می‌کنم` is under `کردن`, `लड़कों` under `लड़का`,
`sāvatthiyaṃ` under `sāvatthī`.  `_routes` below is the cascade, and it is
allowed to fail: what it tried comes back with the answer, so a reader can
see that the word was looked for and not found rather than assume the
dictionary has nothing to say about the language.
"""
import collections
import itertools
import json
import os
import re
import sqlite3
import sys
import threading
import unicodedata

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
DICT_DIR = os.path.join(ROOT, "dict")
LANG_DIR = os.path.join(LIB, "lang")

sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import translit                                                # noqa: E402

# How many of each to hand back.  A dictionary page for a common word runs to
# forty senses; a cloud over a line of text has room for a few, and a reader
# who needs the forty has a dictionary of their own.
MAX_HITS = 4
MAX_SENSES = 3

# For a language written without spaces, how long a word may be and how many
# a chunk may be cut into.  Japanese words run to three or four characters
# and rarely past six; twelve is room for a compound nobody expected, and the
# ceiling on pieces is a guard against a chunk somebody pasted a paragraph
# into.
MAX_TOKEN = 12
MAX_PIECES = 40

# How many rows a chunk's OWN words may have (look_up's `authoritative`).
# Not the guard of 24 on a cut this file made: these are words a person
# divided, each is given back under its own place, and 400 is a 400-character
# chunk -- the most serve.py reads -- cut one character at a time.
MAX_OWN_WORDS = 400

# How many affixes may come off one word, and how many spellings may be tried
# for it in all.  Persian stacks them -- نمی‌بینمش is ne- + mi- + بین + -am +
# -aš, a prefix and a suffix -- so one strip can never be enough.
#
# TWO, AND NOT THREE, AND THAT WAS MEASURED.  Depth three was the first
# guess.  Run over all 16,879 Persian headwords with each word's own entry
# hidden, depth 3 differs from depth 2 on thirty of them and every single one
# is an invention: زرتشت (Zoroaster) read as زر (gold), لیتیم (lithium) as لی,
# موریتانی (Mauritania) as مور, حشیش as ح.  Not one correct answer is gained.
# A third strip is where a word stops being a word and becomes whatever
# letters are left, so the ceiling is the point at which peeling still
# explains something.
MAX_PEEL = 2
MAX_ROUTES = 60

# THE SHAPE OF dict/<code>.db -- SCHEMA below, and the rows getdict.py puts
# in it through create() -- as a number (lib/version.py FORMATS).  The
# database carries none.  RAISE IT when the shape changes so that the Parseh
# before this one would read a dictionary wrong: a column it asks for gone
# or meaning something else.  A column added that an older reader never
# asks for is not such a change.
DB_FORMAT = 1

SCHEMA = """
PRAGMA journal_mode = OFF;
CREATE TABLE meta  (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE entry (
  id       INTEGER PRIMARY KEY,
  headword TEXT NOT NULL,
  translit TEXT NOT NULL DEFAULT '',
  -- HOW THE WORD IS SAID, in the register this language's editions are
  -- written in (lib/lang/<code>.ipa.json says which).  The transliteration a
  -- reader sees is derived FROM THIS and not from `translit`: the source's
  -- own romanisation of Persian is the classical one, so `translit` holds
  -- kitāb, xwāndan and dōst -- correct romanisations of a Persian nobody in
  -- Tehran speaks.  A pronunciation is a fact and the walk from it is a
  -- table; asking a 4B model to romanise instead gave the register it had
  -- seen most of, which was the same wrong one.
  ipa      TEXT NOT NULL DEFAULT '',
  -- HOW THE WORD IS READ, for a language whose writing does not say: the
  -- kana of a Japanese word.  Wiktionary keeps it in the head template
  -- (日本語 -> にほんご) and it is stored for the same reason the
  -- pronunciation is -- a model shown only the rōmaji `nihongo` and asked
  -- for the kana of a chunk answers `nihongo`, because that is what it was
  -- given.
  reading  TEXT NOT NULL DEFAULT '',
  pos      TEXT NOT NULL DEFAULT '',
  sense    TEXT NOT NULL DEFAULT '',     -- the senses, one per line
  -- WHAT REGISTER EACH SENSE BELONGS TO, one line per line of `sense`, the
  -- source's own tags joined by commas: `obsolete`, `archaic`, `dialectal`,
  -- `figurative`, and the rest.  A dictionary that lists every sense a word
  -- can EVER have buries the one this page means -- شیر is lion, faucet,
  -- tiger and milk, and the panel used to print them in whatever order
  -- Wiktionary happened to hold them.  These tags are what makes an
  -- ordering possible without asking anybody: a sense nobody has written
  -- since 1900 is not what a reader is looking at.  A tag with a colon is a
  -- fact about how the sense is used and not a register (`aux:sein`, the
  -- auxiliary German gives that meaning; `obj:dat`, what it governs), and so
  -- is `with-dative`; neither moves a sense up or down.
  sense_tags TEXT NOT NULL DEFAULT '',
  -- WHAT THE HEAD LINE SAYS AND NOTHING ELSE DOES, as a JSON object, '' when
  -- it says nothing: a Japanese verb's class and transitivity, a Chinese
  -- verb's type (vo is separable, vc takes a potential), a Persian verb's
  -- literary present stem and its sound.  A verb entry needs every one of
  -- them and none is a form or a sense.  lib/getdict.py _head says what goes
  -- in; a dictionary built before it has no such column, and every reader
  -- asks `_has_col` first.
  head     TEXT NOT NULL DEFAULT ''
);
-- Every way a word can appear on a page, pointing at the entry it belongs
-- to: the headword itself, every inflected form the source lists, and every
-- page that says "genitive singular of X".  This table is why the cascade
-- below can be short -- Wiktionary carries the morphology, so most languages
-- need no rules of their own at all.
CREATE TABLE form  (
  form     TEXT NOT NULL,
  entry_id INTEGER NOT NULL,
  note     TEXT NOT NULL DEFAULT '',     -- "plural", "genitive singular", ...
  -- HOW THIS FORM IS ROMANISED, which the pronunciation cannot say: IPA is
  -- recorded per lemma, so it romanises ساختن and never می‌سازم.  The
  -- source's form table does carry it (mí-sâzam), and it is the one a reader
  -- meeting that word actually needs -- and the one a model asked to invent
  -- it got wrong, answering with the infinitive.
  roman    TEXT NOT NULL DEFAULT '',
  -- HOW THIS FORM IS SAID, where the source says: a French conjugation row
  -- carries it (prends /pʁɑ̃/, aimons /ɛ.mɔ̃/), and so does a page that is
  -- only "simple past of help" (helped /hɛlpt/).  The lemma's pronunciation
  -- cannot give either, and a verb entry prints both.
  ipa      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX form_ix  ON form(form);
CREATE INDEX entry_ix ON entry(headword);
-- ONE ENTRY'S WHOLE TABLE, which is what a verb entry reads: its stems, its
-- participle, its auxiliary.  Without this that is a scan of the entire form
-- table per hit -- 0.061 s on German's 2 429 661 rows, measured -- and a
-- chunk asks it for every verb in it, the reader's look-ahead for ten chunks
-- more.  A dictionary built before this has no index and is still read
-- correctly, only slower: they are opened read-only and cannot be given one.
CREATE INDEX IF NOT EXISTS form_entry_ix ON form(entry_id);
"""

# One connection per (thread, language): the server is a ThreadingHTTPServer
# and a sqlite3 connection is not to be shared across threads.  The same
# pattern texgen.ThreadDict and store.lib() use for their own per-request
# state.
_CONNS = threading.local()
_RULES = {}


def path_for(code):
    """Where this language's dictionary would be, whether or not it is."""
    return os.path.join(DICT_DIR, "%s.db" % languages.get_or_default(code).code)


def available(code):
    """Is there a dictionary for this language that can actually be read?

    ONE QUESTION, ONE ANSWER.  This used to ask the filesystem while
    `about()` asked the connection cache, and the two could disagree -- which
    is exactly what they did: the reader's button appeared because the file
    was there, the panel came up empty because the cache still said there was
    no file, and the setup page said "no dictionary yet" about a dictionary
    that was plainly in dict/.  Both go through `_conn` now, so a file that
    exists but cannot be opened is not an available dictionary and nothing
    can be told two different stories.
    """
    return _conn(code) is not None


def _stamp(path):
    """What this file is, as far as anything here needs to know: when it
    changed and how big it is, or None if it is not there."""
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _conn(code):
    """This thread's connection to that language's dictionary, or None.

    Read-only (`mode=ro`): nothing in the toolbox writes to a dictionary
    after getdict.py has built it, and saying so means a corrupt file is an
    error here rather than a half-written one later.

    THE FILE IS RE-EXAMINED EVERY TIME, and this is the whole of the bug that
    made the feature look broken.  The cache used to be keyed by language
    alone, so whatever a thread found the first time it asked -- including
    "there is nothing here" -- it went on answering forever.  On a threading
    server that meant: build a dictionary from the page, and every thread
    that had answered a request before the build kept saying there was none.
    A stat is cheap; being permanently wrong is not.
    """
    code = languages.get_or_default(code).code
    have = getattr(_CONNS, "map", None)
    if have is None:
        have = _CONNS.map = {}
    p = path_for(code)
    stamp = _stamp(p)
    got = have.get(code)
    if got is not None and got[1] == stamp:
        return got[0]
    if got is not None and got[0] is not None:
        try:                            # it was rebuilt, or thrown away
            got[0].close()
        except sqlite3.Error:
            pass
    conn = None
    if stamp is not None:
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % p, uri=True,
                                   check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # which language this connection is, so a pronunciation can be
            # written the way that language writes one
            _CODE_OF[id(conn)] = code
            for _k in [k for k in _HAS_IPA if k[0] == id(conn)]:
                _HAS_IPA.pop(_k, None)
        except sqlite3.Error:
            conn = None
    have[code] = (conn, stamp)
    return conn


def about(code):
    """What the dictionary says about itself: the source, its licence, when
    it was built, how much is in it.  The readers print this under the
    entries, because an entry with no provenance is a rumour."""
    c = _conn(code)
    if c is None:
        return None
    try:
        out = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM meta")}
    except sqlite3.Error:
        return None
    out["lang"] = languages.get_or_default(code).code
    return out


# ------------------------------------------------- definitions, not translations
# THE LANGUAGE A DICTIONARY'S SENSES ARE WRITTEN IN.  Every dictionary
# getdict.py builds is kaikki's extract of the ENGLISH Wiktionary, which
# explains the words of every language in English.  For Persian or Italian
# that is a translation -- خانه is "house" -- and for English itself it is a
# definition: `house` is "A structure built or serving as an abode of human
# beings."  That is written in the language being learned, which a reader may
# not be ready to read, so the readers keep it behind a switch of its own
# (`definitions` in the server's answer) instead of printing it as the entry.
# A dictionary built from another edition would say so in its meta, as
# `senses_lang`.
SENSES_LANG = "en"
# how many senses `more_senses` adds to a hit past the MAX_SENSES it carries:
# a guard, since Wiktionary's verb `run` has sixty
MAX_MORE_SENSES = 40


def senses_language(code):
    """The language this dictionary's senses are written in, or None where
    there is no dictionary."""
    a = about(code)
    if a is None:
        return None
    return (a.get("senses_lang") or SENSES_LANG).strip().lower()


def defines(code):
    """Does this language's dictionary explain its words in that language --
    are its senses definitions rather than translations?"""
    said = senses_language(code)
    return bool(said) and (said.split("-")[0]
                           == languages.get_or_default(code).code.split("-")[0])


def more_senses(result):
    """Every sense the hits of look_up's `result` left out -> `result`.

    A hit carries the first MAX_SENSES of its ranked senses and `buried`, how
    many more there are.  To each hit with any buried this adds `more` and
    `more_marks`: the rest, ranked as the first were (rank_senses), up to
    MAX_MORE_SENSES, each mark the tags of the sense beside it.  `senses`
    itself is left alone -- the vocabulary line, the \\vb and the translation
    model's aligner all read it, and none of them should change because a
    reader asked to see the whole entry."""
    c = _conn((result or {}).get("lang") or "")
    if c is None:
        return result
    code = _code_of(c)
    tags = "sense_tags" if _has_col(c, "sense_tags") else "''"
    for w in result.get("words") or []:
        for h in w.get("hits") or []:
            if not h.get("buried") or h.get("entry") is None:
                continue
            row = c.execute("SELECT sense, %s AS sense_tags FROM entry WHERE id = ?"
                            % tags, (h["entry"],)).fetchone()
            if row is None:
                continue
            senses = [x for x in (row["sense"] or "").split("\n") if x.strip()]
            shown = set(h.get("senses") or [])
            rest = [r for r in rank_senses(senses, (row["sense_tags"] or "").split("\n"), code)
                    if r[0] not in shown][:MAX_MORE_SENSES]
            h["more"] = [r[0] for r in rest]
            h["more_marks"] = [r[1] for r in rest]
    return result


# ---------------------------------------------------------------- the rules
def rules(code):
    """The optional per-language lookup rules, `lib/lang/<code>.lookup.json`.

    Optional on purpose: a language with no file gets the surface form, the
    folded form and whatever the source's own form table knows, which for the
    European languages is nearly everything.  The file is where a language
    says the two things the data cannot:

        "fold":    "deva-iast" -- the dictionary is keyed in another script
                   than the page.  Where a source romanises its headwords
                   (Wiktionary does it for the classical Indic languages:
                   9129 Roman entries against 1473 in Devanagari, in the
                   extract this was measured on) and the edition prints
                   Devanagari, the word is transliterated before it is
                   looked for.  Deterministic, because that spelling is.
        "affixes": what to take off and what taking it off means.  These are
                   not new knowledge -- docs/lang/<code>.md already documents
                   every one of them for the annotator -- and the note is
                   shown to the reader, so a hit found by stripping `-hā` says
                   so rather than pretending the page said the lemma.
                   A rule is a `suffix` or a `prefix`, with the `note`; and
                   optionally `add`, put back at the end (a past stem given
                   its infinitive's ن); `front`, put back in front (Persian's
                   برمی‌گردم is `بر میگردم` in the table that lists it);
                   `after`, the endings the rest must have for the rule to
                   apply at all (an Italian enclitic comes off an infinitive's
                   -r or a gerund's -ndo, and never off the name Carla); and
                   `prefer`, notes that put an entry first when this rule is
                   the one that answered (after -mashita, the entry reached
                   through its `stem` row is the verb: 来ました is 来る).
                   `min_stem_length` and `pos` can restrict a short ending
                   to stems of a given length and part of speech. `terminal`
                   ends that route, so a copula cannot be peeled off and then
                   explained away through another, unrelated affix;
                   `surface_only` prevents earlier affix guesses as well;
                   `begins` restricts a spoken verb ending to known prefixes.

    And, where the language needs them, what the source's rows mean that
    the rows cannot say themselves:

        "own":      notes that make a row the word itself, as an empty note
                    does: Chinese `Simplified-Chinese`, since 帮忙 IS 幫忙.
        "spelled":  notes saying the text spells the entry another way; the
                    hit then carries `spelled`, the text's spelling, so a
                    Simplified book is not handed a Traditional \\dw.
        "regional": sense tags that mark a sense as another lect's, and
                    those that bring it back (Cantonese, unless Mandarin).
        "bare_stem": notes of a stem that is not a word by itself: a hit
                    reached only through one, where the word is also some
                    entry's own headword, goes last (در is `in`, not
                    دریدن's present stem).
        "also_peel": the entries a whole word may match that are only
                    spellings of two words (`pos`, or a note containing one
                    of `note_has`): French n'avait is a page, and a pointer
                    at ne; the affixes are then tried as well, so avoir is
                    reached too.
        "join_next": the words a text may write apart from the word they
                    belong to (`words`, compared without marks), and what
                    the two must be together to count (`pos`): Persian's
                    نمی and می before a verb, written with a plain space
                    where the joiner belongs (`نِمی سوزانَند`).  Such a word
                    is looked up JOINED to the next one, as one word; the
                    reader is shown both as written, and the next word is
                    looked up on its own only when the two together find
                    nothing of that part of speech (see `_joined`).
        "nominal_endings": ordered plural/degree, possessive and copula
                    suffixes. These expand into whole-suffix rules, restricted
                    to nominal dictionary entries, without increasing MAX_PEEL.
        "spoken":   the spoken pass (lib/spoken.py): a language whose pages
                    are written as it is spoken -- Persian's chat, subtitles
                    and dialogue -- and whose words are read back to the formal
                    word the dictionary has.  Its tables (a whole-word list
                    shipped beside this file), its writing-level rules and the
                    words it says its reasons in are all in this section; a
                    language without it is looked up as it always was.
    """
    code = languages.get_or_default(code).code
    if code not in _RULES:
        p = os.path.join(LANG_DIR, "%s.lookup.json" % code)
        d = {}
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, ValueError):
                d = {}
        d.setdefault("fold", "")
        d.setdefault("affixes", [])
        d["affixes"] += _nominal_affixes(d.get("nominal_endings") or {})
        _RULES[code] = d
    return _RULES[code]


def _nominal_affixes(groups):
    """Known nominal suffix sequences, never arbitrary extra peeling.

    Their order is number/degree, possession, copula. A contracted plural
    alone is deliberately excluded: a final -a is too weak a stem hint.
    Existing source forms and verb reconstruction are tried before these.
    """
    if not groups:
        return []
    inner = [("", (), "")]
    for family, pos in (("plural", ("noun",)), ("degree", ("adj",)),
                        ("reduced_plural", ("noun",))):
        inner.extend((suffix, pos, family) for suffix in groups.get(family, []))
    possessive = [""] + groups.get("possessive", [])
    copulas = [{"suffix": ""}] + groups.get("copula", [])
    out, seen = [], set()
    for (inside, pos, family), owner, copula in itertools.product(inner, possessive, copulas):
        ending = copula["suffix"]
        # Ordinary nominal morphology already has shallow rules. Only add
        # a copula or a reduced plural attached to a possessive/copula.
        if not ending and family != "reduced_plural":
            continue
        if family == "reduced_plural" and not owner and not ending:
            continue
        suffix = inside + owner + ending
        after = copula.get("after") or []
        if after and (inside or owner) and not (inside + owner).endswith(tuple(after)):
            continue
        allowed = pos or (("noun", "adj", "pron", "num") if owner else
                          ("noun", "adj", "pron", "num", "adv"))
        key = suffix, allowed, tuple(after) if not (inside or owner) else ()
        if key in seen:
            continue
        seen.add(key)
        notes = []
        if ending:
            notes.append("the copula ending %s taken off" % ending)
        if owner:
            notes.append("the possessive ending %s taken off" % owner)
        if inside:
            notes.append("the %s ending %s taken off" % (family.replace("_", " "), inside))
        rule = {"suffix": suffix, "min_stem_length": 2, "pos": list(allowed),
                "surface_only": True, "terminal": True, "note": ", then ".join(notes)}
        if key[2]:
            rule["after"] = list(key[2])
        out.append(rule)
    return sorted(out, key=lambda rule: -len(rule["suffix"]))


# ------------------------------------------------------------ normalisation
_ZW = "‌‍"                       # ZWNJ, ZWJ


def _keeps(ch):
    """Is this a character a word is made of?

    Letters, the marks that sit on them and figures -- by Unicode's own
    categories, not by a list per language.  A list would have been wrong
    twice over: the danda `।` and the double danda `॥` are Devanagari
    punctuation and sit INSIDE the block a Devanagari language's `chars`
    names, so "is it in the script" cannot answer this; and every language
    would have needed its own row (`،` `؛` `؟` for Arabic, `。` `、`
    for Japanese) for a question none of them answer differently.
    """
    return unicodedata.category(ch)[0] in "LMN"


def _bare(word, L):
    """A word with what surrounds it taken off: quotation marks, the danda,
    a comma, the parentheses a chunk's text carries because the text is
    reproduced verbatim and punctuation is part of it.

    Only at the ends: an apostrophe inside a word is part of it (`so'haṃ`,
    `l'ascia`), and so is a hyphen, and so is the ZWNJ that decides a
    Devanagari conjunct.
    """
    while word and not _keeps(word[0]):
        word = word[1:]
    while word and not _keeps(word[-1]):
        word = word[:-1]
    return word


def _fold(word, L):
    """The form to look for when the surface form is not in the book.

    Case goes (a sentence starts with a capital and a dictionary does not),
    the language's own marks go (the harakat: a vowelled reading edition
    writes them and a dictionary headword does not), and the zero-width
    joiners go (`می‌کنم` and `میکنم` are one word written two ways).

    TURKISH HAS TWO I'S, and a capital of each: İ is i and I is ı.
    casefold() knows one, so `İstiyorum.` became `i̇stiyorum` (with a
    combining dot no dictionary row carries) and found nothing at all, and
    `Islanmak` became `islanmak`, a word that is not Turkish.  Every verb
    that opens a sentence with either letter was unreachable.
    """
    w = word
    if L._strip_re is not None:
        w = L._strip_re.sub("", w)
    for z in _ZW:
        w = w.replace(z, "")
    if L.code == "tr":
        w = w.replace("İ", "i").replace("I", "ı")
    return w.casefold()


def _unmarked(word, L):
    """A word with the language's marks and the zero-width joiners taken
    out and its case left alone: the same word, written with or without
    what `_fold` says a dictionary may leave off -- but a capital is not
    that, since Given is a name and given is not."""
    w = word
    if L._strip_re is not None:
        w = L._strip_re.sub("", w)
    for z in _ZW:
        w = w.replace(z, "")
    return w


def _folded_variants(word, L, fold):
    """Every spelling worth trying for one surface word, in order, each with
    the plain-English reason it is being tried."""
    out = [(word, "as written", "surface")]
    f = _fold(word, L)
    if f and f != word:
        out.append((f, "without the marks and the case", "surface"))
    if fold == "deva-iast":
        for w, _why, _k in list(out):
            r = translit.deva_to_iast(w)
            if r and r != w:
                out.append((r, "transliterated, as the dictionary is keyed", "surface"))
    seen, uniq = set(), []
    for w, why, k in out:
        if w and w not in seen:
            seen.add(w)
            uniq.append((w, why, k))
    return uniq


def _peel(form, rule):
    """One affix off this form, or None if the rule does not apply.

    One character of stem is enough, and it has to be: `住んで` is 住 + んで,
    and a Japanese verb stem is very often the single kanji.  Demanding two
    (which suited Persian, where a one-letter stem is nothing) left
    every -mu verb's te-form uncut, and `んで` was then matched against `ぬ`.
    Generating a nonsense stem costs nothing anyway: it still has to be in
    the dictionary before anybody is told about it.
    """
    suf, pre = rule.get("suffix") or "", rule.get("prefix") or ""
    add, front = rule.get("add") or "", rule.get("front") or ""
    after = rule.get("after") or ()
    if rule.get("begins") and not form.startswith(tuple(rule["begins"])):
        return None
    if suf and form.endswith(suf) and len(form) > len(suf):
        rest = _trim(form[:-len(suf)])
        if len(rest) < rule.get("min_stem_length", 1):
            return None
        if after and not rest.endswith(tuple(after)):
            return None
        return _trim(front + rest + add)
    if pre and form.startswith(pre) and len(form) > len(pre):
        rest = _trim(form[len(pre):])
        if len(rest) < rule.get("min_stem_length", 1):
            return None
        if not rest or (after and not rest.endswith(tuple(after))):
            return None
        return _trim(front + rest + add)
    return None


def _trim(form):
    """A zero-width joiner left at an edge is not part of the word.

    Persian writes its prefixes with one -- `نمی‌بینم` is نمی + ZWNJ + بینم --
    so taking the prefix off leaves the joiner leading the stem, and nothing
    is keyed under that.  It cost the right answer by a hair: نمی‌بینمش found
    دیدن through `می‌بینم`, having dropped the negation, instead of through
    `بینم` with the negation named.
    """
    return form.strip(_ZW)


def _took(path, why):
    """How a form was reached, in the words the reader is shown.

    One affix reads as it always did (`the plural -hā taken off`); several
    read in the order they came off, which is the order that explains the
    word.  The folding, if any, is named once at the end rather than after
    every step.
    """
    # each step named, including one whose rule carries no note: dropping the
    # unnamed ones showed a two-strip route to the reader as a one-strip one,
    # which is a route description that is quietly false
    said = ", then ".join(p or "an ending taken off" for p in path) \
        or "an ending taken off"
    return said if why == "as written" else "%s (%s)" % (said, why)


Route = collections.namedtuple("Route", "form how kind rule base")


def _routes(word, L):
    """Every (form, how it was reached, what kind of route) to try for one
    word of the text, SHALLOWEST FIRST.

    The word itself and its folded spellings, then those with one affix off,
    then those with two, out to MAX_PEEL.  Shallowest first is the order of
    confidence and it is what keeps this safe: a word that IS in the
    dictionary is found as itself and never explained away as somebody
    else's stem.

    WHY IT PEELS MORE THAN ONCE.  It took exactly one affix off, and Persian
    stacks them: نمی‌بینمش is ne- + mi- + بین + -am + -aš, and a reader was
    told nothing was found -- the prefix came off, or the enclitic did, never
    both.  Wiktionary's own conjugation tables are good enough that one strip
    usually lands (می‌سازم is listed as a form of ساختن), so what needs two is
    exactly the interesting case: a form Wiktionary does not list, carrying
    an ending it does.

    The affixes are applied to the FOLDED spellings and not only to the raw
    word, because an affix rule is written in the script the DICTIONARY is
    keyed in, not the one the page is printed in.  Where a dictionary is
    romanised and the pages are Devanagari the endings are Roman (`-ssa`,
    `-aṃ`) while the word is not, so applying them to the surface form
    matched nothing at all: `बुद्धं` tried itself, then `buddhaṃ`, and
    stopped one step short of `buddha`.

    Nothing is visited twice, so a rule taking a form back where it came from
    cannot loop, and the total is capped -- a rule set written badly should
    cost a slow answer, not a hung server.

    Each route is a Route: the form, how it was reached in words, `kind`
    ("surface" or "affix"), the last `rule` taken off (None for a spelling),
    and `base`, the spelling it started from ("as written", or the folding
    that made it).
    """
    fold = rules(L.code).get("fold") or ""
    base = _folded_variants(word, L, fold)
    affixes = rules(L.code).get("affixes") or []
    out = [Route(f, w, k, None, w) for f, w, k in base]
    seen = {f for f, _w, _k in base}
    # each frontier entry carries how it got here: the folding that produced
    # its spelling, and the affixes taken off since, in order
    frontier = [(f, w, [], 0) for f, w, _k in base]
    for _step in range(MAX_PEEL):
        if not affixes or len(out) >= MAX_ROUTES:
            break
        nxt = []
        for form, why, path, prefixed in frontier:
            for rule in affixes:
                if rule.get("surface_only") and path:
                    continue
                # ONE PREFIX PER WORD.  A word has one prefix slot in every
                # language here -- Persian's نمی is already ne+mi as a single
                # rule -- so a second one is always the search eating the
                # word.  Unguarded it read بنده (a servant) as ده (a
                # village), بندر (a port) as در (a door) and بنزین as زین (a
                # saddle): twenty-one such answers dictionary-wide, and not
                # one correct answer lost by refusing them.
                if rule.get("prefix") and prefixed:
                    continue
                stem = _peel(form, rule)
                if stem is None or stem in seen:
                    continue
                seen.add(stem)
                took = path + [rule.get("note") or ""]
                if not rule.get("terminal"):
                    nxt.append((stem, why, took,
                                prefixed + (1 if rule.get("prefix") else 0)))
                # `affix` marks a route the LANGUAGE accounts for -- an
                # ending it knows how to take off -- as against one that
                # merely found the string.  _resolve uses the difference, and
                # it is the difference between a cut somebody can defend and
                # a coincidence.
                out.append(Route(stem, _took(took, why), "affix", rule, why))
                if len(out) >= MAX_ROUTES:
                    break
            if len(out) >= MAX_ROUTES:
                break
        if not nxt:
            break
        frontier = nxt
    return out


# ------------------------------------------------------------------ looking
# ---------------------------------------------------------------- ranking
# WHAT A DICTIONARY CANNOT DO IS CHOOSE, and what it can do is stop putting
# the wrong answer first.  شیر is lion, faucet, tiger and milk; کشیدن is to
# pull, to smoke, to draw and to suffer.  The panel used to print them in
# whatever order the source held them, which is neither frequency nor
# relevance -- it is the order somebody wrote the Wiktionary page in.
#
# There is no judgement in what follows and no model: only two facts the
# source already records and the toolbox was throwing away.  A sense the
# source marks `obsolete` is not what a reader of a living text is looking
# at, and a sense marked `figurative` is not the first place to look either.
# Everything unmarked keeps the source's own order, which for an unmarked
# sense is the best signal there is.

# Tags that say "this is not current usage".  A reader meeting a word in a
# book printed this century is almost never meeting these.
_STALE = frozenset((
    "obsolete", "archaic", "historical", "dated", "rare", "uncommon",
    "nonstandard", "proscribed", "misspelling", "informal-spelling",
    "pronunciation-spelling", "eye-dialect", "neologism",
))
# Tags that say "this is current, but it is not the plain reading".  A
# figurative or regional sense is a real answer and a later one.
#
# WHAT IS DELIBERATELY NOT HERE.  `literary` and `poetic` are not demoted,
# because this toolbox is pointed at literature: یار is tagged `literary` for
# "friend, lover" and that is exactly the sense a page of Hafez wants, while
# the untagged "a player in a team" is the one that would have been promoted
# over it.  `colloquial` is not demoted either -- a novel's dialogue is
# colloquial.  Nor are `Iran`, `Dari` or any other of Wiktionary's REGION
# tags, which say where a word is said and not whether it is the ordinary
# reading; Persian carries `Iran` on 620 senses and it is the register these
# editions are written in.
_MARKED = frozenset((
    "figurative", "figuratively", "broadly", "specifically",
    "dialectal", "regional", "slang", "vulgar", "humorous",
    "euphemistic", "childish", "ironic",
))


def _sense_rank(tags):
    """0 for a plain sense, 1 for a marked one, 2 for a stale one.

    Stable: everything inside a tier keeps the source's order, so a word
    whose senses carry no tags at all comes back exactly as before.

    A TAG WITH A COLON IS NOT A REGISTER and is not read here.  `obj:` keeps
    the object a sense governs with the template's own words in it -- folgen
    has `obj:dat<something; e.g. a book; film plot; etc.>` -- and split into
    words, a qualifier that happened to say `figurative` or `rare` would have
    demoted a plain sense for what its OBJECT is like.
    """
    have = set()
    for t in (tags or "").split(","):
        if ":" not in t:
            have.update(w.strip().lower() for w in t.split())
    if have & _STALE:
        return 2
    if have & _MARKED:
        return 1
    return 0


def rank_senses(senses, tags, code=""):
    """(sense, tag string, tier) per sense, plainest first.

    `senses` and `tags` are the two columns as stored, already split into
    lines and aligned -- line n of one describes line n of the other.  A
    dictionary built before the tags column existed passes tags as empty and
    gets its senses back untouched, in the order it always gave them.

    ANOTHER LECT'S SENSE IS A REGIONAL ONE, where the language says which
    tags name another lect (`regional` in lib/lang/<code>.lookup.json, and
    only when `code` is given).  Wiktionary's Chinese is one entry for every
    variety written in characters, and Cantonese carries none of the tags
    above: 生日 "to have one's birthday" is `Cantonese,informal`, and printed
    as plain Mandarin beside "birthday".  Such a sense is tier 1, with
    `dialectal` and `regional` -- unless it is also tagged as said in the
    lect the editions are written in.
    """
    lect = _lects(code) if code else None
    rows = []
    for i, sense in enumerate(senses):
        t = tags[i] if i < len(tags) else ""
        tier = _sense_rank(t)
        if lect is not None and tier == 0 and _other_lect(t, lect):
            tier = 1
        rows.append((sense, t, tier))
    rows.sort(key=lambda r: r[2])            # stable: ties keep source order
    return rows


def _lects(code):
    """The language's `regional` rule, as (tags, suffixes, unless tags,
    unless suffixes), or None where it has none."""
    R = rules(code).get("regional") or {}
    if not R:
        return None
    return (frozenset(R.get("tags") or ()), tuple(R.get("suffixes") or ()),
            frozenset(R.get("unless") or ()), tuple(R.get("unless_suffixes") or ()))


def _other_lect(tags, lect):
    """Does this tag line say the sense is only another lect's?"""
    have = {t.strip() for t in (tags or "").split(",") if t.strip()}
    names, ends, keep, keep_ends = lect
    if any(t in keep or (keep_ends and t.endswith(keep_ends)) for t in have):
        return False
    return any(t in names or (ends and t.endswith(ends)) for t in have)


def _hits_for(c, form, prefer=()):
    """Every entry that names this form, best first, once each.

    A page that IS the headword sorts above a page that merely mentions it,
    and the note on a form row ("genitive singular") comes back with it so a
    reader is told what the ending was doing.

    ONE ROW PER ENTRY.  A word reaches its lemma by several paths at once --
    `me` is the accusative, instrumental, dative AND ablative of `ahaṃ`, and
    each is a form row -- and printing the same entry four times with four
    labels is a wall of repetition around one meaning.  The paths are
    gathered into the one note instead, which is also the more useful
    answer: *accusative, instrumental, dative or ablative singular* is what
    the reader actually faces.

    THE ENTRIES ARE CHOSEN FIRST AND THEIR ROWS READ AFTER.  The cap used to
    be on rows -- 32 of them, then the first four entries among those -- and
    that was safe only while an entry had one row per spelling.  It has
    several now (lib/getdict.py keeps `walked` as the past AND the past
    participle, German `fahren` as infinitive, first and third plural, and
    more), so one busy entry could eat the budget and push a second lemma
    off the answer.  Four entries, then every row of each for this form, in
    the source's order -- which is also the order the notes are read out in.

    Each hit names its `entry` -- the id, which is how anything after this
    reads that entry's table, and the only thing that tells homographs apart
    (Persian has two رفتن: raftan to go, roftan to sweep) -- and its
    `head_sound`: how the LEMMA is said.  `translit` is how the word IN THE
    CHUNK is said, and the two differ exactly when it matters: می‌سازم has
    translit mi-sāzam and head_sound sāxtan, and the sidebar that paired the
    headword with the first wrote `\\dw{ساختن}{mi-sāzam}`.

    A LETTER OF THE ALPHABET GOES LAST, in a language written with spaces.
    Spanish `y` is the conjunction and also the letter's own page (pos
    `character`), which Wiktionary lists first; so is `a`, and Italian `i`,
    `e` and `o`.  A word in running text is almost never the name of a
    letter.  In Chinese and Japanese `character` is the entry for the
    written word itself -- 吃 is pos character -- and nothing moves.

    THE REST OF THE ORDER IS _tier_of's, and every rung of it was a verb
    lost off the end of four: a name reached through its lower case after
    the words (given/Given, not give), a compound reached through one of its
    words after every single word (هستند/بلد بودن, not بودن), a bare stem
    that is another word's headword last (در/دریدن), an entry reached only as
    an auxiliary not at all (haben/raven).  `prefer` is the answering rule's
    (lib/lang/<code>.lookup.json): the rows that put an entry first when
    that rule found the form -- 来 after -mashita is 来る's `stem`.  Where
    the word is four entries and none a verb, the verb it is a form of takes
    the fourth place (`left`: leave).  A hit carries `spelled`, the text's
    spelling, where the language says the row it came through is another
    spelling of the entry (帮忙 for 幫忙).
    """
    # THREE SMALL QUESTIONS AND NOT ONE BIG ONE, because of German `haben`:
    # it is the auxiliary row of 9 249 verbs, and asked as one join the
    # answer took 18 ms where the old row-capped query took 8.6.  Asked as
    # three -- which entries (grouped on the index, no join), what they are
    # (a few dozen rows of `entry`, by key), then their rows for this form --
    # it is 14 ms on the German file built before form_entry_ix and 2.3 on
    # one built with it (40 000 pages of the extract); every other word is
    # well under a millisecond either way.
    code = _code_of(c)
    R = rules(code)
    L = languages.get_or_default(code)

    def among(notes):
        # "is the row's note one of these", with the notes as parameters
        notes = [n for n in (notes or ()) if n]
        if not notes:
            return "0", []
        return "note IN (%s)" % ",".join("?" * len(notes)), notes
    own_q, own_a = among(R.get("own"))
    pref_q, pref_a = among(prefer)
    stem_q, stem_a = among(R.get("bare_stem"))
    # AN AUXILIARY IS NOT A FORM OF THE VERB IT HELPS.  getdict keeps the
    # conjugation table's multiword rows, and the auxiliary's own cell with
    # them, so `haben` is a form of 9 243 German verbs and `sein` of 1 429,
    # Italian `avére` of 9 798, French `ayant` of 249 and `avoir` of 21
    # (passer, partir: the verbs that take either).  Reached only through
    # such a row -- `auxiliary`, with or without a register after it
    # (wandern's `auxiliary rare`), or a `multiword-construction` -- an entry
    # is not an answer: `Wir haben Zeit` listed raven and listen.  An entry
    # the word is, or reaches through any other row, stays: haben is haben.
    cand = c.execute(
        "SELECT entry_id, max(note = '') AS bare, max(note != '') AS noted, "
        "max(%s) AS named, max(%s) AS pref, min(%s) AS stem "
        "FROM form WHERE form = ? GROUP BY entry_id "
        "HAVING min(instr(note, 'multiword-construction') > 0 OR "
        "(instr(note, 'auxiliary') > 0 AND instr(note, ',') = 0)) = 0 "
        "ORDER BY pref DESC, max(note = '' OR %s) DESC, entry_id LIMIT ?"
        % (own_q, pref_q, stem_q, own_q),
        own_a + pref_a + stem_a + [form] + own_a + [MAX_HITS * 16]).fetchall()
    if not cand:
        return []
    got = {r[0]: r for r in cand}
    ents = {r["id"]: r for r in c.execute(
        "SELECT id, headword, pos FROM entry WHERE id IN (%s)"
        % ",".join("?" * len(got)), list(got))}
    ids = [i for i in got if i in ents]
    # which of them the word IS: its own row names it, and it is spelt so,
    # joiners and marks aside (آنها is آن‌ها, and بزرگتر بزرگ‌تر) but not
    # the capital (given is not Given) -- or the language says the row it
    # came through is the word itself (帮忙 is 幫忙's `Simplified-Chinese`)
    plain = _unmarked(form, L)
    words = {i for i in ids
             if got[i]["named"] or (got[i]["bare"] and _unmarked(
                 ents[i]["headword"] or "", L) == plain)}
    folded = _folded_only(c, form, ids, words)
    tiers = {i: _tier_of(form, got[i], ents[i], i in words, bool(words - {i}),
                         i in folded, L)
             for i in ids}
    # inside a tier, an entry spelt as the word before one that is the word
    # in another spelling: 周末 is its own entry, and 週末's Simplified one
    ranked = sorted(ids, key=lambda i: (tiers[i], ents[i]["headword"] != form, i))
    chosen = ranked[:MAX_HITS]
    # ONE PLACE FOR THE VERB IT IS A FORM OF, in a language with spaces, when
    # the word is itself four entries and none of them a verb: `left` is two
    # adjectives, an adverb and a noun, and leave, whose past it is, was the
    # fifth; Persian کند is an adjective and three nouns, and کردن (he does)
    # was the fifth -- 37 times in 1 500 Tatoeba sentences.  Only through a
    # row that is an inflection in the plain register -- not a spelling of
    # it, not an archaic form (Italian sì is an archaic `is`), and not a
    # pointer like `reflexive-of`, which made yourself the fourth answer for
    # `you`.
    if (L.spaced and len(chosen) == MAX_HITS
            and all(tiers[i] <= T_IS for i in chosen)
            and not any((ents[i]["pos"] or "") == "verb" for i in chosen)):
        for i in ranked[MAX_HITS:]:
            if tiers[i] != T_FORM or (ents[i]["pos"] or "") != "verb":
                continue
            if any(_inflects(r[0]) for r in c.execute(
                    "SELECT note FROM form WHERE form = ? AND entry_id = ?", (form, i))):
                chosen[-1] = i
                break
    if not chosen:
        return []
    full = {r["id"]: r for r in c.execute(
        "SELECT id, headword, translit, %s AS ipa, %s AS reading, pos, sense, "
        "%s AS sense_tags FROM entry WHERE id IN (%s)"
        % ("ipa" if _has_ipa(c) else "''",
           "reading" if _has_col(c, "reading") else "''",
           "sense_tags" if _has_col(c, "sense_tags") else "''",
           ",".join("?" * len(chosen))),
        chosen)}
    notes = {i: [] for i in chosen}
    romans = {i: [] for i in chosen}
    ipas = {i: [] for i in chosen}
    spelled = set()
    spelt = set(R.get("spelled") or ())
    # through the entries' own rows where the dictionary can (form_entry_ix:
    # four entries are a few hundred rows, `haben` is 9 249); `+form` stops
    # SQLite choosing the form index, and is asked for only where the other
    # one exists -- on an older file it would scan the whole table
    for r in c.execute(
            "SELECT entry_id, note, %s AS roman, %s AS ipa FROM form "
            "WHERE %sform = ? AND entry_id IN (%s) ORDER BY rowid"
            % ("roman" if _has_col(c, "roman", "form") else "''",
               "ipa" if _has_col(c, "ipa", "form") else "''",
               "+" if _has_index(c, "form_entry_ix") else "",
               ",".join("?" * len(chosen))),
            [form] + chosen):
        i = r[0]
        romans[i].append(r[2] or "")
        ipas[i].append(r[3] or "")
        note = (r[1] or "").strip()
        if note in spelt:
            spelled.add(i)
        if note and note not in notes[i]:
            notes[i].append(note)
    hits = []
    for i in chosen:
        # THE FORM'S OWN SOUND, and none at all where the form IS the
        # headword, whose sound is the lemma's (`said`): which row says it
        # is translit.form_sound's business, and a language's ipa.json's.
        own = got[i]["bare"] or got[i]["named"]
        of_form = "" if own else translit.form_sound(code, romans[i], ipas[i],
                                                     " " in form)
        hit = _hit(c, full[i], notes[i], of_form,
                   form if (i in spelled and full[i]["headword"] != form) else "")
        # which tier the hit is in, for `_by_use` to keep (see _tier_of).
        # `_by_use` used to read the first off an empty note, and an entry
        # the word is can carry a note too -- جوان is its own ezafe form,
        # hacer its own infinitive.
        hit["_tier"] = tiers[i]
        hits.append(hit)
    return hits


# What a row's note says when it is not an inflection of the entry: a
# spelling of it, a pointer at it, or a register this reader is not in.
_NOT_INFLECTION = frozenset(("canonical", "alternative", "spelling", "romanization",
                             "abbreviation", "misspelling", "dialectal",
                             "colloquial", "error-unrecognized-form")) | _STALE


def _inflects(note):
    """Is this note an inflection in the plain register (`past`, `participle
    past`, `aorist indicative singular third-person`)?"""
    tags = [t for t in re.split(r"[ ,]+", note or "") if t]
    return bool(tags) and not any(t in _NOT_INFLECTION or t.endswith("-of")
                                  for t in tags)


# THE ORDER HITS COME IN, by what reached them.  `_by_use` keeps it and only
# counts inside a tier, so nothing a corpus says can lift a hit over one the
# dictionary ranks above it.
T_PREFERRED = -1    # reached through the row the answering rule asks for
T_IS = 0            # the word is this headword
T_FORM = 1          # the word is one of its forms
T_CASE = 2          # the word is its headword only once the capital is gone
T_PART = 3          # a headword of several words, reached through one of them
T_STEM = 4          # a bare stem, where the word is also a word of its own
T_LETTER = 10       # a letter of the alphabet, after everything


def _folded_only(c, form, ids, words):
    """The candidates that reach `form` only through the lower-case copy of
    a capitalised spelling: every row they have for it, they also have, with
    the same note, for the word with a capital.  getdict writes both.

    Asked of a word that has a case at all, and only of candidates the word
    is not: one question, through the candidates' own rows where the
    dictionary has form_entry_ix (the word may be `haben`, 9 243 rows).  The
    capitalised spelling and the capitals both count as the twin -- SE is an
    abbreviation's, and se its lower case.
    """
    caps = [s for s in dict.fromkeys((form[:1].upper() + form[1:], form.upper()))
            if s != form]
    if not caps:
        return set()
    need = [i for i in ids if i not in words]
    if not need:
        return set()
    mine, twin = {}, {}
    for r in c.execute(
            "SELECT entry_id, form, note FROM form WHERE %sform IN (%s) "
            "AND entry_id IN (%s)"
            % ("+" if _has_index(c, "form_entry_ix") else "",
               ",".join("?" * (len(caps) + 1)), ",".join("?" * len(need))),
            [form] + caps + need):
        (mine if r[1] == form else twin).setdefault(r[0], set()).add(r[2] or "")
    return {i for i in need if i in twin and mine.get(i, {""}) <= twin[i]}


def _tier_of(form, g, e, is_word, other_is, folded, L):
    """Where one candidate entry goes among the hits for `form`.

    `g` is its row of the grouped question in `_hits_for`, `e` its entry,
    `is_word` whether the word IS it, `other_is` whether the word is some
    OTHER candidate's own headword, `folded` whether it reaches the word
    only through a capitalised spelling's lower-case copy (_folded_only).

    A NAME REACHED THROUGH ITS LOWER CASE IS NOT THE WORD.  getdict writes a
    capitalised headword's case-folded spelling beside it, with the same
    empty note, and so `given` WAS the name Given, `came` the name Came, and
    `left` and `ran` names too, as surely as they were the adjective and the
    noun; with four places, the verb went: English lost give, come, leave
    and run.  A lower-case word in running text that is a capitalised
    word only once folded -- German essen and the noun Essen (and Esse,
    whose plural is Essen), Italian marco and the name Marco -- is that
    word last of the words it may be.

    A HEADWORD OF SEVERAL WORDS REACHED THROUGH ONE OF THEM goes after every
    single word.  Wiktionary's colloquial Persian table for بلد بودن has the
    bare هستند ("they are") among its cells, with an empty note, and six
    other compounds of بودن have it too: هستند came back as four of them and
    never as بودن.

    A BARE STEM that is also somebody's own headword goes last of all, where
    the language names its stem notes (`bare_stem`): در is the preposition
    and the door, and it is also دریدن's present stem; بر is on, and بردن's.
    A stem alone is not a word of running Persian and the preposition is.
    """
    hw = e["headword"] or ""
    if g["pref"]:
        t = T_PREFERRED
    elif is_word:
        t = T_IS
    elif folded or (hw != form and not g["noted"]
                    and form in (hw.casefold(), hw.lower(), _fold(hw, L))):
        t = T_CASE
    else:
        t = T_FORM
    if t > T_PREFERRED:
        if " " in hw and " " not in form:
            t = max(t, T_PART)
        if g["stem"] and other_is:
            t = T_STEM
    # A LETTER OF THE ALPHABET GOES LAST, in a language written with spaces
    # (see _hits_for)
    if L.spaced and (e["pos"] or "") in ("character", "letter"):
        t += T_LETTER
    return t


# WORDS A SOURCE ROMANISATION FIELD HELD THAT ARE NOT ROMANISATIONS.  A
# dictionary built before lib/getdict.py learned better has Japanese verbs
# romanised with their transitivity (する `both`, 擦る `trans`, 所持
# `transitive`) and Chinese verbs with their structure (`verb-complement`,
# 118 of them); the reader's panel printed those as the word's sound.
# Refused here so an old dictionary does not need rebuilding to stop saying
# it -- no language here writes any of them as a word's romanisation.
_NOT_A_SOUND = frozenset((
    "both", "trans", "transitive", "intrans", "intransitive", "intr",
    "verb-complement", "modifier-verb", "subject-predicate",
    "verb-complement-object",
))


def _hit(c, r, notes, of_form, spelled=""):
    """One entry, as the reader is shown it.

    `of_form` is how the word in the chunk is said, already in the edition's
    letters (translit.form_sound), "" where the word is the headword.
    `spelled` is the chunk's own spelling where it spells the entry another
    way (see `spelled` in `rules`), "" otherwise: what a vocabulary line
    writes is `spelled || headword`.
    """
    code = _code_of(c)
    # RANKED BEFORE IT IS CUT.  The cap used to be taken off the top of
    # the source's own order, so a plain sense sitting fifth behind four
    # obsolete ones could not be reached at all: کشیدن came back "to
    # suffer" and the reading the text wanted was never printed.
    all_senses = [x for x in (r["sense"] or "").split("\n") if x.strip()]
    all_tags = (r["sense_tags"] or "").split("\n")
    ranked = rank_senses(all_senses, all_tags, code)[:MAX_SENSES]
    senses = [x[0] for x in ranked]
    # what the source said about each, for a reader who wants to know why
    # a sense is where it is -- empty for a plain one
    marks = [x[1] for x in ranked]
    # THE TRANSLITERATION IS DERIVED FROM THE PRONUNCIATION where there
    # is one, and only falls back to the source's own romanisation where
    # there is not.  See the schema: `translit` is the classical register
    # for Persian, and the pronunciation is the register the edition is
    # actually written in.  A headword of several words is said word by
    # word (فکر کردن is `fekr kardan`, not `fekrkardan`).
    head = r["headword"] or ""
    said = translit.from_ipa(code, r["ipa"] or "", words=" " in head)
    # THE FORM'S OWN SOUND WINS, where the source gives one: it is of the
    # word in front of the reader (mi-sāzam) and the other two are of the
    # lemma (sāxtan).  Then the pronunciation, then whatever the source
    # romanised the headword as -- tidied, as everything else here is:
    # untidied it was Wiktionary's Arabic `ʔarā` and Hindi `hãsnā` in a
    # panel that otherwise wrote the edition's.
    source = (r["translit"] or "").strip()
    if source.lower() in _NOT_A_SOUND:
        source = ""
    source = translit.tidy_roman(code, source)
    of_form = of_form or ""
    return {"entry": r["id"],
            "headword": head,
            "spelled": spelled or "",
            "translit": of_form or said or source,
            "of_form": of_form,
            "said": said, "ipa": r["ipa"] or "",
            # the lemma's own sound, for anything that writes the LEMMA down
            "head_sound": said or source,
            "reading": r["reading"] or "",
            "pos": r["pos"] or "", "senses": senses, "marks": marks,
            "buried": max(0, len(all_senses) - len(senses)),
            "note": ", ".join(notes[:4])}


_HAS_IPA = {}
_CODE_OF = {}


def _has_col(c, name, table="entry"):
    """Does this dictionary carry that column?  Asked once per connection: a
    dictionary built before a column existed still answers every other
    question, and says what it always said."""
    k = (id(c), table, name)
    if k not in _HAS_IPA:
        cols = [r[1] for r in c.execute("PRAGMA table_info(%s)" % table)]
        _HAS_IPA[k] = name in cols
    return _HAS_IPA[k]


def _has_ipa(c):
    return _has_col(c, "ipa")


def _has_index(c, name):
    """Does this dictionary carry that index?  Asked once per connection, like
    `_has_col`: a file built before it is read the slow way, never refused."""
    k = (id(c), "index", name)
    if k not in _HAS_IPA:
        _HAS_IPA[k] = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (name,)).fetchone() is not None
    return _HAS_IPA[k]


def _code_of(c):
    """Which language this connection is, so the pronunciation can be written
    the way that language writes it."""
    return _CODE_OF.get(id(c), "")


def _known(c, form):
    """Is this string in the dictionary at all?  One indexed row, no columns."""
    return c.execute("SELECT 1 FROM form WHERE form = ? LIMIT 1",
                     (form,)).fetchone() is not None


def _is_word(c, piece, L):
    """Could this run of characters be a word?

    Not merely "is it a headword": a word the reader meets is usually
    inflected, and for an unspaced language the segmentation has to see that
    before it can cut anywhere.  `住んで` is in no dictionary and is
    unmistakably a word; asking the language's own rules (`住んで` -> `住む`)
    is what lets the cut fall in the right place instead of leaving `住` on
    its own and `んで` to be matched, absurdly, against `ぬ`.

    Every route is an indexed lookup on one column, and the rules are a few
    dozen, so a chunk costs a few thousand of them -- milliseconds, once,
    behind a click.
    """
    for form, _why, _kind, rule, _base in _routes(piece, L):
        if (_route_hits(c, form, rule) if (rule or {}).get("pos")
                else _known(c, form)):
            return True
    return False


def _segment(c, text, L):
    """Cut a chunk of an unspaced language into words.

    JAPANESE HAS NO WORD SEPARATOR, so `split_words` hands back the whole
    chunk as one word -- which is right for every other tool in the toolbox
    (a chunk is the hoverable unit, and an Anki card is made from a chunk)
    and useless here: `昨日本を読んだ` is not a headword and never will be.
    A dictionary is the one caller that needs the pieces.

    Longest match, left to right, against the dictionary's own form table --
    the oldest trick there is for this, and the one thing that makes it
    workable here is that the word list IS the dictionary, so there is
    nothing extra to install and nothing to keep in step.  A character that
    starts no word at all is emitted alone, which is how an unknown name
    comes back marked "not found" instead of swallowing the rest of the line.

    It is greedy and therefore sometimes wrong -- the standard failure is a
    long compound eaten where two short words were meant -- and being wrong
    here costs an entry the reader can see is wrong, not a silent one.
    """
    out, i, n = [], 0, len(text)
    while i < n and len(out) < MAX_PIECES:
        # punctuation is passed over, not emitted: a chunk's text is verbatim
        # and carries the source's own stops, and `、` reported as a word
        # nobody could find is noise in every Japanese cloud
        if not _keeps(text[i]):
            i += 1
            continue
        hit = ""
        for j in range(min(MAX_TOKEN, n - i), 0, -1):
            piece = text[i:i + j]
            if _is_word(c, piece, L):
                hit = piece
                break
        if hit:
            out.append(hit)
            i += len(hit)
        else:
            out.append(text[i])
            i += 1
    return out


# When one spelling is several parts of speech, which reading to believe.
# A SHORT word is believed to be the function word: `به` is a preposition and
# also a noun and an adjective, `の` is a particle and also a noun and a
# syllable, and in a running sentence the closed-class reading is right
# almost every time -- a one- or two-character token that CAN be a particle
# is one.  A long word is believed to be the content word, for the mirror
# reason.  Nothing here is a parser; it is the bias that is right most often.
_CLOSED = ("particle", "postp", "prep", "conj", "det", "article", "pron",
           "aux", "num", "intj")


def pos_of(code, word, short=3):
    """What part of speech this word is, best first -- [] where the language
    has no dictionary or the word is in none of it.

    The same roads `look_up` takes: as written, folded, and through the
    language's own affix rules, so an inflected form answers with its
    lemma's part of speech.
    """
    c = _conn(code)
    if c is None or not word:
        return []
    L = languages.get_or_default(code)
    for form, _why, _kind, _rule, _base in _routes(_bare(word, L), L):
        rows = c.execute(
            "SELECT DISTINCT e.pos FROM form f JOIN entry e ON e.id = f.entry_id "
            "WHERE f.form = ? AND e.pos != ''", (form,)).fetchall()
        got = [r[0] for r in rows if r[0]]
        if got:
            closed = [p for p in got if p in _CLOSED]
            open_ = [p for p in got if p not in _CLOSED]
            return (closed + open_) if len(word) <= short else (open_ + closed)
    return []


def pos_weights(code, word):
    """[(part of speech, senses)] for this word, the most senses first -- []
    where the language has no dictionary or the word is in none of it.

    The same roads as pos_of(), weighed: how many sense lines the dictionary
    gives the word under each part of speech, which is a rough measure of how
    much of the word that reading is.  pos_of() puts the closed classes of a
    short word first, which is right for `in` and wrong for `man` (filed
    under an interjection and a pronoun as well) and `not` (a conjunction);
    lib/chunker.py asks this for the open classes and its language's own list
    for the closed ones."""
    c = _conn(code)
    if c is None or not word:
        return []
    L = languages.get_or_default(code)
    for form, _why, _kind, _rule, _base in _routes(_bare(word, L), L):
        rows = c.execute(
            "SELECT e.pos, SUM(LENGTH(e.sense) - LENGTH(REPLACE(e.sense, char(10), '')) + 1) "
            "FROM form f JOIN entry e ON e.id = f.entry_id "
            "WHERE f.form = ? AND e.pos != '' GROUP BY e.pos", (form,)).fetchall()
        got = [(r[0], int(r[1] or 0)) for r in rows if r[0]]
        if got:
            return sorted(got, key=lambda pw: -pw[1])
    return []


def look_up(code, text, pieces=None, authoritative=False, register=None):
    """Look every word of a chunk up.  Returns None when the language has no
    dictionary installed, so a caller can tell "nothing found" from "nothing
    to find with".

    {"lang", "source": {...}, "words": [{"word", "hits": [...], "tried": [...]}]}

    A `word` is the text as written, and may be TWO of its words with the
    space between them, where the language writes a prefix apart from the
    word it belongs to (`join_next`: Persian `نمی سوزانند`); a caller that
    finds the word among the chunk's must look for it as a run of words.

    `pieces` is the optional second reading of the same text: a list of
    {"word", "lemma"} from something that knows the language better than
    longest match does.
    The word is looked for as it stands and then, if that finds nothing, as
    the lemma -- which is what rescues a word the dictionary has under
    another spelling.  NOTHING HERE IMPORTS THAT MODULE: the dictionary is
    the half that works with no model at all, and the day it needs one to
    answer is the day it has stopped being what it is for.  The caller that
    has both hands the pieces in.

    `authoritative` says the pieces are the DOCUMENT'S OWN WORDS -- a
    Japanese or Chinese chunk's word line (lib/wordline.py), which a person
    divided -- and not a model's guess.  Then nothing second-guesses them: a
    piece the dictionary cannot place is left whole and unfound instead of
    cut again offline (住んでいました stays one row), every piece has exactly
    one row, in order, a word written twice has its row twice, and each row
    carries `i`, its index in `pieces`, which is how a reader puts it back
    under its word.  Without it nothing here changes.

    `register` is what the page says of the text it is looking up: "spoken"
    for a video's subtitles, nothing for a book's narration (lib/spoken.py).
    For a language with spoken rules (Persian) a spoken reading of a word
    the dictionary knows is offered only where a word of the chunk is
    certainly spoken or the page says so; it changes nothing for the rest.
    """
    c = _conn(code)
    if c is None:
        return None
    L = languages.get_or_default(code)
    # COMPOSED FIRST, because a dictionary is.  Devanagari's nukta letters
    # have code points of their own (ड़ is U+095C) that NFC takes apart --
    # they are composition exclusions -- and Hindi's 525 159 form rows hold
    # not one of them: `वह अचानक रो पड़ी।` typed with the one code point found
    # no पड़ना, and typed composed it did.
    text = unicodedata.normalize("NFC", text or "")
    if pieces or authoritative:
        pairs = []
        for p in pieces or []:
            w = unicodedata.normalize("NFC", (p.get("word") or "").strip())
            if not w and not authoritative:     # a document's word keeps its place
                continue
            alts = p.get("lemmas")
            if isinstance(alts, str):
                alts = [alts]
            elif not isinstance(alts, list):
                alts = [p.get("lemma")] if p.get("lemma") else []
            pairs.append((w, [unicodedata.normalize("NFC", str(a))
                              for a in alts if a]))
    else:
        pairs = [(w, []) for w in
                 (_segment(c, _bare(text, L), L) if not L.spaced
                  else L.split_words(text))]
    starts = _starts([w for w, _a in pairs]) if L.spaced else [False] * len(pairs)
    # a word written apart from the next one it belongs to (`join_next`):
    # the two are one word when together they find what the rule allows
    join = _join_rule(L) if L.spaced and not (pieces or authoritative) else None
    words, seen, also = [], set(), []
    # THE SPOKEN PASS (lib/spoken.py), for a language that has rules for it and a text of its own words: it reads
    # two or three words that are one thing, and adds readings to a word the dictionary has not found or knows
    # only by a guess.  `host` is this module, handed over so that it is the one copy whichever way it was started.
    spoken, ctx = None, None
    if L.spaced and not (pieces or authoritative):
        import spoken as _spoken_module
        spoken = _spoken_module.rules(sys.modules[__name__], L)
        if spoken:
            ctx = spoken.context(sys.modules[__name__], c, L, [w for w, _a in pairs], register)
    host = sys.modules[__name__]
    i = 0
    while i < len(pairs):
        (raw, alts), initial = pairs[i], starts[i]
        window = spoken.window(host, c, L, [w for w, _a in pairs], i, ctx) if spoken else None
        joined = (_joined(c, raw, pairs[i + 1][0], L, join)
                  if join and i + 1 < len(pairs) and not window else None)
        if joined is not None and not joined["hits"] and spoken:
            # می یاد: the two words, written together, may be a spoken verb the old routes do not know
            whole = _bare(raw, L) + "\u200c" + _bare(pairs[i + 1][0], L)
            probe = spoken.augment(host, c, L, {"word": whole, "hits": [], "via": "", "tried": [], "kind": ""}, ctx, i)
            if probe["hits"]:
                joined = dict(probe, word=joined["word"], tried=joined["tried"])
        if window:
            got, i = [window[0]], i + window[1]
        elif joined is not None and joined["hits"]:
            got, i = [joined], i + 2
        elif spoken and spoken.noise(raw):
            got, i = [{"word": raw, "hits": [], "via": "", "tried": [], "kind": ""}], i + 1
        else:
            got, start = _resolve(c, raw, alts, L, bool(pieces) and not authoritative,
                                  initial), i
            if spoken:
                got = [spoken.augment(host, c, L, one, ctx, start) for one in got]
            i += 1
        if authoritative:
            # one row per piece and never a second cut, so `got` is that
            # row or nothing -- and nothing (`、`, a word of no letters)
            # still holds the piece's place, empty
            one = got[0] if got else {"word": raw, "hits": [], "via": "",
                                      "tried": [], "kind": ""}
            one["i"] = i - 1
            words.append(one)
            if len(words) >= MAX_OWN_WORDS:
                break
            continue
        # what a join that found nothing tried is told with the word after
        # it, which is the word a reader then sees `not found`: سوزانند was
        # looked for as نمی‌سوزانند too, and saying so is the difference
        # between "not in this dictionary" and "not looked for"
        if also and got:
            got[0]["tried"] = got[0]["tried"] + [f for f in also
                                                 if f not in got[0]["tried"]]
        also = joined["tried"] if joined is not None and not joined["hits"] else []
        for one in got:
            if one["word"] in seen:
                continue
            seen.add(one["word"])
            words.append(one)
        if len(words) >= 24:               # a chunk is 2-6 words; this is a guard
            break
    _by_use(L.code, words)
    for w in words:
        w.pop("_rule", None)
        for h in w.get("hits") or []:
            h.pop("_tier", None)
    return {"lang": L.code, "source": about(code) or {}, "words": words}


# What ends a sentence, and what opens one, around a word of the chunk.
_STOPS = ".!?…:;"
_OPENS = "«“„‘‚\"'¿¡—–([-"
_CLOSES = "»”’\"')]"


def _starts(tokens):
    """For each word of the chunk: may it be the first word of a sentence?

    The first word of the chunk may (a chunk is cut from the sentence and
    very often begins it), and so may a word after a full stop, a question
    or a colon, or one that opens a quotation.  A capital anywhere else is
    the word's own.
    """
    out, prev = [], None
    for t in tokens:
        tail = prev.rstrip(_CLOSES) if prev is not None else ""
        out.append(prev is None or tail[-1:] in _STOPS or t[:1] in _OPENS
                   or not prev.strip(_OPENS))      # a dash on its own
        prev = t
    return out


def _by_use(code, words):
    """Where one written word reaches two different lemmas, put the one the
    language actually uses first.

    A dictionary cannot rank its own entries: it holds کشیدن and کشتن with
    equal confidence and prints whichever it met first.  A CORPUS can, and
    the ranking is a count rather than a judgement -- how many translated
    sentences hold each headword.  Nothing happens where no corpus is
    installed, and nothing happens to a word with one lemma, which is nearly
    all of them.
    """
    try:
        import corpus                                          # noqa: E402
    except ImportError:                                        # pragma: no cover
        return
    gloss = corpus.any_for(code)
    if not gloss:
        return
    need = {h["headword"] for w in words if len(w.get("hits") or []) > 1
            for h in w["hits"]}
    if not need:
        return
    n = corpus.counts(code, gloss, need)
    if not n:
        return
    for w in words:
        hits = w.get("hits") or []
        if len(hits) > 1:
            # A TIEBREAK AND NEVER AN OVERRIDE.  _hits_for already puts the
            # entry the word IS above the entries it merely inflects to, and
            # that rule outranks any count: بنده is a servant, and بستن (to
            # close) is commoner in every corpus, so sorting on the count
            # alone told a reader that بنده was two prefixes off `to close`.
            # So the count only orders hits that the dictionary had no reason
            # to separate, and it is stable inside that.
            #
            # "The entry the word IS" is `_tier` (see _hits_for), and was an
            # empty note.  The two agreed only by accident: Spanish hacer,
            # ser and poder are their own infinitives, so the verb carried a
            # note and the empty-note test put "a being" above "to be" and
            # "power" above "can"; جوان, keeping its ezafe row, sent "young"
            # below "a youth".
            hits.sort(key=lambda h: (h.get("_tier", 1 if h.get("note") else 0),
                                     -n.get(h["headword"], 0)))


def _explained(c, piece, L):
    """Could a rule of the language account for this piece at all?

    Not "did a rule find it" -- `_resolve` stops at the first route that
    resolves, and for an inflected form that is very often the surface one,
    because dictionaries list inflections too.  `して` is IN the form table,
    so it was found as written and the te-form rule that also explains it was
    never reached; the cut `して` + `ください` therefore looked like two
    coincidences and a correct reading was thrown away.  What the guard below
    wants to know is whether the language can ACCOUNT for the piece, which is
    a question about the rules and not about which route happened to win.
    """
    for form, _why, kind, _rule, _base in _routes(piece, L):
        if kind == "affix" and _known(c, form):
            return True
    return False


# A form row that says only "this is how that word can also be written" is
# not evidence that the string is a word where it was found.  Anything else
# -- a conjugation, a conditional, an imperative stem -- is.
_ONLY_A_SPELLING = ("", "another spelling", "canonical")


def _stands(c, piece, L):
    """Is this piece a word HERE, or only a string somebody indexed?

    The difference between a cut worth showing and a coincidence.  `いさん`
    is in the dictionary four times and is a word none of them: every row is
    `another spelling` of a kanji noun read that way -- 遺産, 違算, 胃酸 --
    so it is a READING and never something written in a sentence.  `の`, two
    characters shorter and far commoner, has three entries under its own
    spelling, one of them the particle.  `ください` has none, but its rows
    say `imperative stem` of 下さる, which is a grammatical fact about the
    string and not a note about how to spell something else.

    So a piece stands if the dictionary has it under its own spelling, or
    ties it to a word by an inflection, or the language's own rules reach it.
    """
    for note, head in c.execute(
            "SELECT f.note, e.headword FROM form f JOIN entry e ON "
            "e.id = f.entry_id WHERE f.form = ? LIMIT 40", (piece,)):
        if head == piece:
            return True
        if (note or "").strip() not in _ONLY_A_SPELLING:
            return True
    return _explained(c, piece, L)


def _join_rule(L):
    """The language's `join_next`, as (the words, folded; the parts of speech
    the two must make together, empty for any), or None where it has none."""
    R = rules(L.code).get("join_next") or {}
    if isinstance(R, list):
        R = {"words": R}
    words = frozenset(_fold(w, L) for w in R.get("words") or () if w)
    return (words, frozenset(R.get("pos") or ())) if words else None


def _joined(c, raw, nxt, L, rule):
    """This word and the next looked up as ONE word, where this one is a
    word the language writes apart from the word it belongs to (`join_next`)
    -- or None where it is not one, and a word with no hits where the two
    together are nothing the rule allows.

    PERSIAN WRITES ITS VERB PREFIX APART as often as joined.  The joiner
    (ZWNJ) is what the spelling wants -- نمی‌سوزانند -- and a plain space is
    what a typewriter, an old printing and a good part of the Web give
    instead: 13 of the fixture book's 299 chunks have a نمی or می standing
    alone, and 191 of 1,500 Tatoeba sentences have 210.  Split at the
    space, می was "wine" (and a preposition, a conjunction and a name), نمی
    was نم "moisture" with an -i taken off, and the verb was looked for
    without its prefix: `کنم` is کردن and کندن (to dig), `می‌کنم` only
    کردن; `برد` is رفتن, بردن, بریدن and خواب رفتن, `می‌برد` only بردن.
    Joined, 11 of the 13 and 207 of the 210 are read as their verb.

    NOTHING BUT THE SPACE BETWEEN THEM.  `می،` is the wine and a comma, and
    a quotation opening on the next word is not the rest of this one.

    WHAT THE TWO MAKE MUST BE WHAT THE RULE SAYS (`pos`), and the routes
    are walked until something of it is found.  می is a prefix rule of its
    own, so ANY word of the dictionary was found again behind it: `می ناب`
    (pure wine) came back as ناب, the fixture's `با هَم می سوزانَد` as
    سوزان "burning" and Tatoeba's `نمی یاد` as یاد "memory", each "found" by
    taking a verb prefix off something that is not a verb.  The same
    filter drops what only shares the spelling -- `می زد` is زدن, not also
    میزد, a banquet -- and walking on past a route that finds nothing of it
    is what reaches دانستن under the phrase page نمی‌دانم ("I don't know",
    where the word written with the joiner stops).
    """
    words, pos = rule
    a, b = _bare(raw, L), _bare(nxt, L)
    if not a or not b or _fold(a, L) not in words:
        return None
    if not (_keeps(raw[-1]) and _keeps(nxt[0])):
        return None
    whole = a + "\u200c" + b
    word = "%s %s" % (raw, nxt)
    tried = []
    for rt in _routes(whole, L):
        tried.append(rt.form)
        hits = [h for h in _route_hits(c, rt.form, rt.rule)
                if not pos or (h.get("pos") or "") in pos]
        if hits:
            return {"word": word, "hits": hits, "tried": tried, "kind": rt.kind,
                    "via": "as one word (%s)%s" % (
                        whole, "" if rt.how == "as written" else ", " + rt.how)}
    return {"word": word, "hits": [], "via": "", "tried": tried, "kind": ""}


def _only_spellings(hits, L):
    """Is everything the whole word found a page that only spells two words
    as one -- a contraction, a phrase -- by the language's `also_peel`?"""
    R = rules(L.code).get("also_peel") or {}
    pos = set(R.get("pos") or ())
    has = tuple(R.get("note_has") or ())
    if not (pos or has):
        return False
    return all((h.get("pos") in pos)
               or any(x in (h.get("note") or "") for x in has) for h in hits)


def _route_hits(c, form, rule):
    """Apply optional grammatical guards to one affix route's dictionary hits.

    The Persian colloquial copula -e is a nominal/adjectival ending. Merely
    sharing the remaining letters with a verb, a name or a preposition is
    insufficient evidence that the dictionary recognises this form.
    """
    rule = rule or {}
    hits = _hits_for(c, form, rule.get("prefer") or ())
    pos = rule.get("pos") or ()
    return [h for h in hits if not pos or h.get("pos") in pos]


def _resolve(c, raw, alts, L, from_model, initial=False):
    """One piece of the text, looked up: itself, then the spellings offered
    with it, and only then -- for a piece a model proposed and nothing
    matched -- cut again by the offline reading.

    That last fallback is why a better segmentation cannot make things
    worse.  A model asked to read `住んでいました` may hand it back whole,
    which is a defensible word and a dictionary entry nowhere; the offline
    cut has `住んで` and `いました` and resolves both.  So the model's reading
    is preferred where it lands and the old one still catches it where it
    does not.

    `initial` says the word may open a sentence (see `_starts`), which is
    what a capital there may mean and nothing else does.
    """
    w = _bare(raw, L)
    if not w:
        return []
    hits, tried, via, kind = [], [], "", ""
    # the rule the answering route took an affix off with: the spoken pass (lib/spoken.py) reads it, to tell a
    # guess of one letter from an ending the language knows (taken off the answer again by look_up)
    used = None
    routes = _routes(w, L)
    for n, rt in enumerate(routes):
        tried.append(rt.form)
        found = _route_hits(c, rt.form, rt.rule)
        if not found:
            continue
        hits, via, kind, used = found, rt.how, rt.kind, rt.rule
        later = routes[n + 1:]
        # A CAPITAL THAT OPENS A SENTENCE IS NOT A NAME'S.  `Seppe la
        # verità` answered with the name Seppe alone and never with sapere,
        # whose past `seppe` is what the sentence says -- the word was found
        # as written, and the lower case was never asked.  Where everything
        # the capital found is a name, the lower case is asked too, and its
        # answer is taken if it has anything that is not -- with the name
        # after it, even past the four: `Bill will win` is a name, and the
        # lower case's four answers were all the bill, so a name kept only
        # "where there is room" was a name lost.  One past the four, not
        # every name: `Vale` is four clippings (Valentino, Valeria...).
        if (initial and rt.base == "as written" and w[:1].isupper()
                and all(h["pos"] == "name" for h in found)):
            for low in later:
                if low.base == "as written":
                    continue
                tried.append(low.form)
                more = _route_hits(c, low.form, low.rule)
                if more and not all(h["pos"] == "name" for h in more):
                    have = {h["entry"] for h in more}
                    for h in found:
                        if h["entry"] not in have and len(more) <= MAX_HITS:
                            h["_tier"] = max(h.get("_tier", 0), T_CASE)
                            more.append(h)
                    hits, via, kind, used = more, low.how, low.kind, low.rule
                    break
        # A WORD THAT IS ONLY TWO WORDS WRITTEN AS ONE is taken apart as
        # well, where the language says which pages those are (`also_peel`).
        # Wiktionary has n'avait and n'ai as pages of their own -- pointers
        # at ne -- and j'ai as a phrase, so the elided pronoun's rule never
        # ran: a word found as written is not looked for again, and avoir,
        # the word a reader of n'avait needs, was never among the answers.
        elif rt.kind == "surface" and _only_spellings(found, L):
            for part in later:
                # the word written onto the front, and nothing else: an
                # Italian enclitic rule read the name Natale as nata + -le
                if part.kind != "affix" or not (part.rule or {}).get("prefix"):
                    continue
                tried.append(part.form)
                more = _route_hits(c, part.form, part.rule)
                if more:
                    # the whole word's pages first, as the text writes it
                    # (n'avait: ne, then avoir) -- except a capital's lower
                    # case, which is not the word at all: dell'acqua's water
                    # comes before the surname Dell'Acqua
                    have = {h["entry"] for h in found}
                    ahead = [h for h in found if h.get("_tier", 0) < T_CASE]
                    after = [h for h in found if h.get("_tier", 0) >= T_CASE]
                    hits = (ahead[:MAX_HITS - 1]
                            + [h for h in more if h["entry"] not in have]
                            + after)[:MAX_HITS]
                    via = "as it stands, and %s" % part.how
                    break
        break
    if not hits:
        # the spellings the model offered: `おじいさん` is in no dictionary
        # and `お爺さん` is, and a reader told the second has been told
        # something true about the first
        for alt in alts:
            a = _bare(alt, L)
            if not a or a == w:
                continue
            for form, why, k, rule, _base in _routes(a, L):
                tried.append(form)
                found = _route_hits(c, form, rule)
                if found:
                    hits, kind, used = found, k, rule
                    via = ("under %s" % alt if why == "as written"
                           else "under %s (%s)" % (alt, why))
                    break
            if hits:
                break
    mine = [{"word": raw, "hits": hits, "via": via, "tried": tried,
             "kind": kind, "_rule": used}]
    if hits or not from_model or L.spaced:
        return mine

    # A word the model read that the dictionary does not have.  The offline
    # cut may still know something -- but it may equally invent something,
    # and telling the two apart is the whole difficulty here:
    #
    #   住んでいました  cuts as 住んで + いました, and 住んで resolves BECAUSE
    #                  the language's own rule takes the te-form off.  The
    #                  cut is accounted for; take it.
    #   おじいさん      cuts as おじ + いさん, both of which happen to be
    #                  strings in the dictionary and neither of which is a
    #                  word here.  A reader is then told a grandfather is an
    #                  inheritance.  Nothing accounts for that cut; leave the
    #                  word as the model read it, unfound and honest.
    #
    # The question is whether a rule COULD explain a piece, not whether one
    # did the finding -- see `_explained`.  Asking the narrower question cost
    # してください, 待っている and 書いてある, all three of which the offline
    # cut had right and the model, reading them whole, then lost.
    #
    # So the fallback is allowed only when the language can EXPLAIN at least
    # one piece of it -- when some sub-piece resolved through an affix rule
    # rather than by being, coincidentally, a string somebody indexed.
    parts = _segment(c, w, L)
    if len(parts) <= 1:
        return mine
    sub = []
    for part in parts:
        sub.extend(_resolve(c, part, [], L, False))
    if not sub or not all(x["hits"] for x in sub):
        return mine
    # EVERY piece has to be a word, not just one of them.  Asking whether
    # ANY piece came through an affix rule was a proxy for "the cut is not
    # invented", and it misfired both ways: it threw away 子供 + の and
    # 日本 + の, where both halves are plainly words, and it accepted
    # することができます as するこ + とが + できます, which reads 𣑑子.  Asking
    # of each piece whether it is a word here keeps the first two and
    # refuses the third, and still refuses おじ + いさん.
    if not all(_stands(c, x["word"], L) for x in sub):
        return mine
    return sub


# ------------------------------------------------------------------- writing
def create(path):
    """A new, empty dictionary at `path`.  Used by getdict.py and by the
    tests, which build a small one rather than download 35 MB."""
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    if os.path.exists(path):
        os.unlink(path)
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    return c


def _cli(argv):
    """`python3 lib/lookup.py <code> <text>` -- what a reader would be shown.

    Reads and never writes, like texwrite.py's own command line: it is the
    quickest way to see whether a dictionary is installed and what it knows.
    """
    if len(argv) < 2:
        print("usage: lookup.py <language code> [text]")
        print("")
        for L in languages.LANGS.values():
            m = about(L.code)
            print("  %-3s %-9s %s" % (
                L.code, L.name,
                ("%s entries, %s" % (m.get("entries", "?"), m.get("source", "?")))
                if m else "no dictionary installed"))
        return 0
    code = argv[1]
    if not available(code):
        print("no dict/%s.db -- build one with: python3 lib/getdict.py %s"
              % (languages.get_or_default(code).code, code))
        return 1
    if len(argv) < 3:
        m = about(code)
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0
    r = look_up(code, " ".join(argv[2:]))
    print("%s, %s" % (r["source"].get("source", "?"), r["source"].get("licence", "?")))
    for w in r["words"]:
        print("\n%s" % w["word"])
        if not w["hits"]:
            print("    (nothing; tried %s)" % ", ".join(w["tried"]))
        for h in w["hits"]:
            head = h["headword"] + (" %s" % h["translit"] if h["translit"] else "")
            print("    %s%s%s" % (head,
                                  "  [%s]" % h["pos"] if h["pos"] else "",
                                  "  — %s" % h["note"] if h["note"] else ""))
            for s in h["senses"]:
                print("        %s" % s)
        if w["via"] and w["via"] != "as written":
            print("    found %s" % w["via"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
