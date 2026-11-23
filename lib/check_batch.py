#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check one annotated paragraph before it goes anywhere near assemble.py.

    python3 check_batch.py <para.json> [--book <dir-or-slug>] [--ch N]

ERRORs must be fixed; WARNs are judgement calls -- read each one and either fix
it or be able to say why it is right.  Exit status is the ERROR count.

The JSON is one paragraph:

  {"idx": 11, "ch": 3,
   "ann": {"sentences": [{"chunks": [{"fa":..., "tr":..., "voc":..., "en":...}]}]}}

`fa` is the chunk's text in the book's language (the key is named after
Persian, the toolbox's first language); a language with a reading (Japanese)
carries the chunk's kana under "kana" beside "tr".  A language with a word
layer (Japanese, Chinese) may carry the chunk's word line under "words"
(lib/wordline.py), and the line is checked by wordline.check and nothing
else: its refusals are errors, its doubts warnings, and a "words" that is
there and blank is an error -- a chunk without words has no key.  book.json's
"reorders": true (kanbun) is passed on, so the words are never compared with
a reading that reorders them.

Which book: --book, else $FRANK_BOOK, else the book the current directory is
in (books.find_book).  Which chapter: "ch" in the JSON, else --ch, else
$FRANK_CH, else 1.  Nothing about any one book is written into this file, so
it runs unchanged in a folder set up for a new edition.

What is checked depends on the book's language (docs/languages.md section 6):
sections 1 and 2 -- fidelity to the source, what LaTeX will accept, the empty
and the required fields -- run for every language, with the marks, the
digits and the word boundaries taken from the registry; sections 3 to 8 are
the Persian edition's own conventions (sukun, /ey/, /ow/, chashm, budan's
stem, the never-gloss list, verb heuristics written against Persian
morphology, the pointing sweep, the ezafe seams) and run only when the book
is Persian.  Arabic gets nothing Persian: its vowelled text is checked only
for the generic agreement that fa and tr both exist.

A CHUNK NOBODY HAS GLOSSED YET IS LEGAL.  lib/draft.py makes an edition out
of nothing but its text -- every chunk a whole sentence, every gloss blank --
and the reader fills it in a chunk or a region at a time, so a book spends
weeks with blank chunks in it, and a checker that failed it for them on the
day it was created would make the whole idea useless.  A chunk with NOTHING
written in it (no tr, no voc, no en, no kana) is therefore counted, in one
note per paragraph, and asked nothing else: not its required fields, and not
the warnings that would be certain in advance for it (a paragraph with no
word line, and in Persian a verb with no \\vb, a word pointed otherwise
elsewhere in the book, an ezafe at the seam after it).  One field written
makes it a chunk somebody is working on, and every field its language
requires is demanded: a translation with no transliteration beside it, in a
language that wants one, is exactly the half-done work this file exists to
catch, and it is an ERROR.  A language divided into words gives each drafted
chunk its reading from its words (kana, or tr for Chinese: lib/draft.py), and
that reading, unchanged, is not counted as written -- it does not make a
blank chunk a started one; once the chunk is started it counts as the
reading it is.

In such a language the words are part of the annotation: a paragraph with
some of its gloss written in which not one chunk has a word line is a
WARNING, answered by running lib/fill_words.py --json on the paragraph and
correcting what it proposes.  A single chunk without words stays legal --
the analyzer may have nothing to propose for it.

A note is neither an error nor a warning and counts towards neither: an error
must be fixed, a warning is a judgement call, and a note is the checker
saying what it did not check, and why.
"""
import collections
import glob
import io
import json
import os
import re
import sys
import unicodedata as ud

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import find_book                                     # noqa: E402
import languages                                                # noqa: E402
# UNDER ANOTHER NAME ON PURPOSE.  `reading` is already a word in this file --
# a chunk's reading line -- and main() binds it, which makes every mention of
# it in that function local: a plain `import reading` is shadowed there and
# raises UnboundLocalError on the one path this import exists for, a paragraph
# whose text does not match its source.
import reading as readingjson                                   # noqa: E402
import texesc                                                   # noqa: E402  a text field read escape by escape
from texparse import read_args                                  # noqa: E402
import wordline                                                 # noqa: E402

BOOK = None     # set in main(): the book's directory
LANG = None     # set in main(): the book's Lang record
REORDERS = False  # set in main(): book.json's "reorders" -- read out of order
IPA = False       # set in main(): book.json's "translit": "ipa" -- the transliteration is not the usual scheme

FATHA, DAMMA, KASRA, SHADDA, SUKUN = "\u064e", "\u064f", "\u0650", "\u0651", "\u0652"
ALLOWED  = {"dw", "vb", "bw", "pw", "textit", "nobreak", "emph"}
BADTEX   = re.compile(r"[$%&#_^~]|\\\\")

# NOTES section 4: ~45 function words that are already in dictionary form
NEVER_GLOSS = set("""در از با به که این آن و را تا هم یا ولی اما اگر نه هر یک من تو او ما شما
آنها خود چون زیرا پس چه خیلی فقط باز هنوز هیچ همه بی بر روی زیر جلو مثل وقتی حالا دیگر بعد قبل""".split())

# \ch{colour}{fa}{tr}{voc}{en} and \chr{colour}{fa}{kana}{tr}{voc}{en}, and
# \chw / \chrw, the same two with a word line last: the text is the SECOND
# argument of all four (the first is the colour, the reader's own mark).  Only
# the text is read here, so the pattern stops after it; the arguments that
# follow may nest braces and are not for a regex.  The longer names first.
CHUNK_RE = re.compile(r"\\ch(rw|w|r)?\{(.*?)\}\{" + texesc.FIELD + r"\}\{")
# ...and what follows the text, in each of the four's order, for the one
# question corpus() asks of those arguments: is anything written in them
AFTER_FA = {"": ("tr", "voc", "en"), "r": ("kana", "tr", "voc", "en"),
            "w": ("tr", "voc", "en", "words"),
            "rw": ("kana", "tr", "voc", "en", "words")}

errors, warns, notes = [], [], []
def err(msg):  errors.append(msg)
def warn(msg): warns.append(msg)
def note(msg): notes.append(msg)


def strip(s):
    """The bare form, with the language's marks taken off (harakat for
    Persian and Arabic; nothing for a language that carries none)."""
    return LANG.strip(s)


def unwritten(c):
    """True when not one part of this chunk's gloss has been written.

    The vocabulary counts even though no language requires it: a field
    somebody has typed into is a chunk somebody is working on, and from then
    on everything the language asks for is asked for.  The one exception is
    the reading a draft gave the chunk from its words (wordline.seed), while
    it still says exactly that: nobody wrote it.  A chunk that is unwritten
    in this sense is counted and passed over; any other is checked in full."""
    field, seeded = wordline.seed(c, LANG)
    return not any((c.get(f, "") or "").strip()
                   and not (f == field and seeded and (c.get(f, "") or "").strip() == seeded)
                   for f in ("tr", "voc", "en", "kana"))


def norm(s):
    """Whitespace normalised for the fidelity comparison.  A language whose
    words are separated by spaces keeps single spaces; one without a word
    separator (Japanese) loses every space, because the chunks are joined
    with nothing and the source has none to keep."""
    if LANG.spaced:
        return re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+", "", s)


def join_chunks(fas):
    """The chunks put back together the way the source was cut: with the
    language's word separator."""
    return (LANG.word_sep or "").join(fas)


def count_args(s, i):
    """How many {...} groups follow position i.  A gloss may nest \\textit
    inside an argument, so brace-counting is the only way to get this right."""
    n = 0
    while i < len(s) and s[i] == "{":
        depth = 0
        while i < len(s):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        else:
            return n                      # unbalanced; caught separately
        n += 1
    return n


def corpus():
    """How the already-built chapters point each word, and which stems they use.

    A chunk nobody has glossed yet is left out of the pointing count: its
    text is the source's as it stands, unpointed until somebody glosses it,
    and counting it would set every pointed word of the finished chapters
    against the bare spelling of the same word in the blank ones -- a
    POINTING warning for nearly every word of a book with a chapter still to
    be glossed.  (It has no \\vb either, so the stems are not touched.)"""
    words = collections.defaultdict(collections.Counter)
    verbs = collections.defaultdict(collections.Counter)
    for f in sorted(glob.glob(os.path.join(BOOK, "ch*.tex"))):
        body = io.open(f, encoding="utf-8").read()
        for m in CHUNK_RE.finditer(body):
            names = AFTER_FA[m.group(1) or ""]
            try:
                rest, _end = read_args(body, m.end() - 1, len(names))
            except (AssertionError, IndexError, ValueError):
                rest = None             # not read: counted, as it always was
            if rest is not None and unwritten(dict(zip(names, rest))):
                continue
            for w in LANG.split_words(m.group(3)):
                words[strip(w)][w] += 1
        for m in re.finditer(r"\\vb\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}"
                             r"\{([^{}]*)\}\{([^{}]*)\}", body):
            verbs[m.group(1)][m.groups()[1:]] += 1
    return words, verbs


def main(path, book=None, ch_opt=None):
    global BOOK, LANG, REORDERS, IPA
    b = find_book(book or os.environ.get("FRANK_BOOK") or None)
    BOOK, LANG, REORDERS, IPA = b.dir, b.lang, b.reorders, b.translit == "ipa"
    blob = json.load(io.open(path, encoding="utf-8"))
    idx  = blob["idx"]
    # Which chapter the paragraph belongs to: the JSON's own "ch" wins, then
    # --ch, then $FRANK_CH.  (It was once hard-wired to 3, for the chapter
    # that was being annotated at the time; a new book starts at 1.)
    ch    = int(blob.get("ch") or ch_opt or os.environ.get("FRANK_CH") or 1)
    spath = os.path.join(BOOK, "source", "paras", "ch%d_p%02d.txt" % (ch, idx))
    if not os.path.exists(spath):
        sys.exit("no source paragraph at %s -- wrong chapter or wrong book?  "
                 "put \"ch\" in the JSON, or pass --ch N / --book <slug>." % spath)
    src   = io.open(spath, encoding="utf-8").read().strip()
    sents  = blob["ann"]["sentences"]
    chunks = [c for s in sents for c in s["chunks"]]

    # ---- 1. source fidelity: the one check that cannot be argued with -------
    rebuilt = norm(strip(join_chunks(c.get("fa", "") for c in chunks)))
    want    = norm(strip(src))
    # ...unless somebody has taken charge of this paragraph in the reader
    # (lib/reading.py).  texwrite and verify_book.py honour the same file, and
    # the third checker of one rule may not be the one that refuses what the
    # reader's own editor allowed.  The mark is 1-based, as \parnum counts;
    # idx here is the 0-based number in the source filename.
    if rebuilt != want and readingjson.is_free(BOOK, ch, idx + 1):
        print("FIDELITY NOT CHECKED -- paragraph %d is marked as departing "
              "from its source, in reading.json" % (idx + 1))
    elif rebuilt != want:
        i = next((i for i, (a, b) in enumerate(zip(rebuilt, want)) if a != b),
                 min(len(rebuilt), len(want)))
        err("TEXT MISMATCH at char %d of %d\n"
            "        got:  ...%s...\n"
            "        want: ...%s..." % (i, len(want),
                                        rebuilt[max(0, i - 60):i + 60],
                                        want[max(0, i - 60):i + 60]))

    # ---- 2. what LaTeX will accept, and the fields every language needs ----
    # The marks that "leak" are the language's own strip range: a haraka in
    # the romanisation of a Persian or Arabic chunk.  A language that strips
    # nothing has nothing to leak.
    marks_name = "harakat" if LANG.script == "arabic" else "marks"
    blank = 0                       # chunks with no gloss written at all
    for c in chunks:
        fa = c.get("fa", "")
        if not fa.strip():
            err("empty fa in a chunk (tr %r, en %r)" % (c.get("tr", ""), c.get("en", "")))
        # en, tr and kana are text: a TeX special in them is written escaped
        # (lib/texesc.py) and read back as typed.  Only the vocabulary is
        # LaTeX, and only there is a raw one a fault (TO-DO §6.6)
        if BADTEX.search(c.get("voc", "") or ""):
            err("unescaped TeX char in voc of %r" % fa)
        voc = c.get("voc", "")
        for m in re.finditer(r"\\([a-zA-Z]+)", voc):
            if m.group(1) not in ALLOWED:
                err("macro \\%s not allowed, in %r" % (m.group(1), fa))
        if voc.count("{") != voc.count("}"):
            err("unbalanced braces in voc of %r" % fa)
        tr = c.get("tr", "") or ""
        if strip(tr) != tr:
            err("%s leaked into tr of %r" % (marks_name, fa))
        for name, n in (("dw", 2), ("bw", 3), ("vb", 7)):
            for m in re.finditer(r"\\%s(?![a-zA-Z])" % name, voc):
                if count_args(voc, m.end()) < n:
                    err(r"\%s needs %d args, got %d, in %r"
                        % (name, n, count_args(voc, m.end()), fa))
        # The word line answers to wordline.check alone -- BADTEX above is a
        # gloss's rule, and the line has its own for what LaTeX may not see.
        # It is not a gloss, so unwritten() does not count it, and it is
        # checked in a blank chunk all the same: a line that cannot be set
        # stops the PDF whether or not anybody has glossed the chunk yet.
        if "words" in c:
            words = c["words"]
            if words is None or (isinstance(words, str) and not words.strip()):
                err("blank words for %r -- a chunk without words carries no "
                    "\"words\" key, and is written \\ch / \\chr" % fa)
            else:
                reading = (c.get("kana", "") or "") if LANG.reading else tr
                bad, doubts = wordline.check(fa, words, LANG, reading=reading,
                                             reorders=REORDERS, door=wordline.BOOK)
                for e in bad:
                    err("words of %r: %s" % (fa, e))
                for w in doubts:
                    warn("words of %r: %s" % (fa, w))
        # A chunk with not one of its gloss fields written is a chunk nobody
        # has started, which is a different thing from one written wrong: it
        # is counted and passed over (see the header).  One field written --
        # even the vocabulary, which no language requires -- means somebody
        # is working on this chunk, and then everything its language asks for
        # is asked for, because a translation with no transliteration beside
        # it is the half-done work these three checks are here to find.
        if unwritten(c):
            blank += 1
            continue
        if not (c.get("en", "") or "").strip():
            err("empty en for %r" % fa)
        # tr is required where the language says so (require_tr): a
        # language written in its own script always romanises, one written
        # in the Latin alphabet is read as it stands
        if LANG.require_tr and not tr.strip():
            err("empty tr for %r" % fa)
        # a reading language (Japanese) carries the kana of the whole chunk
        # beside the romanisation: pass 1 sets it as ruby, the gloss shows
        # it as a line, so a chunk without it is an error, not a gap
        if LANG.reading and not (c.get("kana", "") or "").strip():
            err("no kana for %r -- %s needs the reading of every chunk"
                % (fa, LANG.name))

    # In a language divided into words the words are part of the annotation,
    # started from the machine's proposal and corrected: a paragraph somebody
    # has started glossing in which not one chunk has a word line skipped
    # that step.  One nobody has started is not warned -- the warning would
    # be certain in advance for every such paragraph.  One chunk without
    # words is legal -- the analyzer may propose nothing for it.
    if (LANG.words and blank < len(chunks)
            and not any("words" in c for c in chunks)
            and any((c.get("fa", "") or "").strip()
                    and (LANG.has_script(c["fa"]) if LANG.chars else True) for c in chunks)):
        warn("no chunk of this paragraph has words -- %s divides its chunks into "
             "words: run lib/fill_words.py --json on this file for the machine's "
             "proposal, then correct every line" % LANG.name)

    if blank:
        note("%d of %d chunks have no gloss yet." % (blank, len(chunks)))

    if LANG.code != "fa":
        return report(idx, sents, chunks, src)

    # ======================================================================
    # From here on: the Persian edition's settled conventions (NOTES
    # sections 4 and 5).  Sukun, the diphthong spellings, chashm, budan's
    # stem, the never-gloss list, the verb heuristics, the pointing sweep and
    # the ezafe seams are all written against Persian orthography and
    # morphology, so they run for Persian alone.
    # ======================================================================
    WORDS, VERBS = corpus()

    # ---- 3. the edition's settled conventions ------------------------------
    # THE CHECKS THAT READ THE ROMANISATION are written for the usual scheme (/ey/ as "ey", čašm), and an
    # IPA book spells those sounds otherwise: they are not run for it, and the checker says so once, as a
    # note -- the checks of the Persian TEXT (sukun, chashm's spelling, budan's stem) run as always
    if IPA:
        note("this book's transliteration is IPA (book.json): the checks that read it in the usual scheme "
             "-- /ey/ and /ow/ against the text, čašm -- are not run")
    for c in chunks:
        fa, tr = c["fa"], c.get("tr", "")
        if SUKUN in fa:
            err("sukun in %r -- this edition never uses it" % fa)
        if "ey" in tr and FATHA + "\u06cc" in fa and not IPA:
            err("/ey/ needs KASRA+ya, not fatha: %r (%s)" % (fa, tr))
        if "ow" in tr and KASRA + "\u0648" in fa and not IPA:
            err("/ow/ needs FATHA+vav, not kasra: %r (%s)" % (fa, tr))
        if "\u0686" + FATHA + "\u0634\u0645" in fa or (re.search(r"\bča[sš]m", tr) and not IPA):
            err("chashm must be češm / \u0686\u0650\u0634\u0645 in %r" % fa)
        if re.search(r"\\vb\{بودن\}\{[^}]*\}\{هست\}", c.get("voc", "")):
            err("budan's present stem is باش, not هست, in %r" % fa)

    # ---- 4. glossing rules -------------------------------------------------
    seen_dw = {}
    for n, c in enumerate(chunks):
        for m in re.finditer(r"\\dw\{([^{}]*)\}", c.get("voc", "")):
            head = m.group(1)
            if head in NEVER_GLOSS:
                err("%r is on the never-gloss list, glossed in %r" % (head, c["fa"]))
            if head in seen_dw:
                warn("%r glossed twice in this paragraph (chunks %d and %d)"
                     % (head, seen_dw[head], n))
            else:
                seen_dw[head] = n

    # ---- 4b. gloss-shape rules the conventions reader used to hunt by hand ---
    # NOTES section 4: one English equivalent, not a string of synonyms; no
    # repeated gloss inside a paragraph.  These were 26 of the 98 findings the
    # second proof-reader raised, so they are worth catching mechanically.
    seen_bw = {}
    for n, c in enumerate(chunks):
        voc = c.get("voc", "")
        for m in re.finditer(r"\\bw\{([^{}]*)\}", voc):
            base = m.group(1)
            if base in seen_bw:
                warn("\\bw{%s} repeated in this paragraph (chunks %d and %d) -- "
                     "NOTES: no repeated gloss inside a paragraph" % (base, seen_bw[base], n))
            else:
                seen_bw[base] = n
        # a comma inside the meaning slot of \dw/\bw/\vb is usually two equivalents
        for mac, argn in (("bw", 3), ("vb", 7)):
            for m in re.finditer(r"\\%s(?![a-zA-Z])" % mac, voc):
                args, i = [], m.end()
                while i < len(voc) and voc[i] == "{":
                    d, j = 0, i
                    while j < len(voc):
                        if voc[j] == "{": d += 1
                        elif voc[j] == "}":
                            d -= 1
                            if d == 0: j += 1; break
                        j += 1
                    args.append(voc[i + 1:j - 1]); i = j
                if len(args) >= argn:
                    meaning = args[argn - 1]
                    if re.match(r"^[a-zA-Z' ]+, [a-zA-Z' ]+$", meaning.strip()):
                        warn("two English equivalents where the rule wants one: "
                             "\\%s ... {%s}  (in %r)" % (mac, meaning, c["fa"]))
        for m in re.finditer(r"\\dw\{[^{}]*\}\{[^{}]*\}\s*([^;\\]{3,})", voc):
            g = m.group(1).strip().rstrip(";")
            if re.match(r"^[a-zA-Z' ]+, [a-zA-Z' ]+$", g):
                warn("two English equivalents where the rule wants one: "
                     "\\dw ... %s  (in %r)" % (g, c["fa"]))

    # ---- 5. every verb gets a \vb -----------------------------------------
    VERBISH = re.compile(r"(^|\s)(ن?می‌?\S+|\S+(?:ید|اند|یم|ند)$)")
    for c in chunks:
        # a chunk nobody has glossed yet has no \vb by definition, so this
        # would fire on every one of them: a warning that is certain in
        # advance teaches its reader to skip warnings, which is the one thing
        # this list cannot afford
        if unwritten(c):
            continue
        bare = strip(c["fa"])
        looks = re.search(r"(?:^|\s)ن?می‌?[؀-ۿ]+", bare) or \
                re.search(r"[؀-ۿ]+(?:َم|ی|د|یم|ید|َند)(?:\.|،|$)", c["fa"])
        if looks and "\\vb{" not in c.get("voc", ""):
            warn("looks like it carries a verb but has no \\vb: %r  (%s)"
                 % (c["fa"], c.get("tr", "")))

    # ---- 6. verb stems must match the rest of the book ---------------------
    for c in chunks:
        for m in re.finditer(r"\\vb\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}"
                             r"\{([^{}]*)\}\{([^{}]*)\}", c.get("voc", "")):
            inf, rest = m.group(1), m.groups()[1:]
            known = VERBS.get(inf)
            if known and rest not in known:
                warn("stem/romanisation for %s differs from the book: new %s vs %s  (in %r)"
                     % (inf, rest, list(known), c["fa"]))

    # ---- 7. NOTES 5.4: a word pointed two ways across batches --------------
    # \u0648 is deliberately both \u0648\u064e (va) and \u0648\u064f (o), and \u062f\u0631 the preposition is not
    # \u062f\u0631\u0650 the door.  Everything else pointed two ways is worth a look.
    BY_DESIGN = {"\u0648", "\u062f\u0631"}
    reported = set()
    for c in chunks:
        # a chunk nobody has glossed yet is the source's text, unpointed: set
        # against the book's pointed words it would compete on every one of
        # them, a warning certain in advance (section 5 says why that is the
        # one kind this list cannot carry)
        if unwritten(c):
            continue
        for w in c["fa"].split():
            b = strip(w)
            if b in BY_DESIGN or w in reported:
                continue
            others = {k: v for k, v in WORDS.get(b, {}).items() if k != w}
            others = {k: v for k, v in others.items()
                      if k.rstrip(KASRA) != w.rstrip(KASRA)}
            if others:
                reported.add(w)
                mine = WORDS.get(b, {}).get(w, 0)
                warn("POINTING %s (x%d elsewhere) competes with %s"
                     % (w, mine, ", ".join("%s x%d" % kv for kv in
                                           sorted(others.items(), key=lambda x: -x[1]))))

    # ---- 8. NOTES 5.1, the error that matters: an ezafe dropped at a seam ---
    # Nothing mechanical can settle this -- stripping the harakat, which the
    # fidelity test does to both sides, hides it exactly.  So narrow the report
    # to the seams that could plausibly carry one, and let a reader judge those.
    PREP  = set("\u062f\u0631 \u0627\u0632 \u0628\u0627 \u0628\u0647 \u06a9\u0647 \u0627\u06cc\u0646 \u0622\u0646 \u0648 \u0631\u0627 \u062a\u0627 \u06cc\u0627 \u0627\u0645\u0627 \u0648\u0644\u06cc \u0627\u06af\u0631 \u067e\u0633 \u0686\u0648\u0646 \u0632\u06cc\u0631\u0627 "
                "\u0648\u0642\u062a\u06cc \u062d\u0627\u0644\u0627 \u0628\u0639\u062f \u0642\u0628\u0644 \u0647\u0645 \u0628\u0627\u0632 \u0647\u0646\u0648\u0632 \u0641\u0642\u0637 \u062e\u06cc\u0644\u06cc \u0646\u0647 \u0647\u06cc\u0686 \u0628\u0644\u06a9\u0647 \u06cc\u0639\u0646\u06cc \u0686\u0648\u0646".split())
    VERBY = re.compile("^\u0646?\u0645\u06cc|(?:\u0645|\u06cc|\u062f|\u06cc\u0645|\u06cc\u062f|\u0646\u062f|\u0633\u062a|\u0628\u0648\u062f|\u0634\u062f|\u06a9\u0631\u062f)$")
    risky = 0
    for n in range(len(chunks) - 1):
        cur, nxt = chunks[n], chunks[n + 1]
        # the ezafe is read off the first chunk's final kasra and its tr, and
        # a chunk nobody has glossed has neither yet: every seam after one
        # would be flagged, certain in advance.  An empty text is an error in
        # section 2 already, and has no last word to read.
        if unwritten(cur) or not cur["fa"].split() or not nxt["fa"].split():
            continue
        last  = cur["fa"].split()[-1]
        first = strip(nxt["fa"].split()[0])
        if last[-1] in "\u060c\u061b.!\u061f:\u2013\u00bb":
            continue                                   # punctuation closes the phrase
        # the ezafe is read off the text's final kasra, and -- in the usual scheme -- off the
        # romanisation's "-e" / "-ye"; an IPA book writes its ezafe as its own file says, so only the
        # text is read there
        if last.endswith((KASRA, "\u06c0")) \
                or (not IPA and (cur.get("tr", "") or "").rstrip().endswith(("-e", "-ye"))):
            continue                                   # the ezafe is already there
        if strip(last) in PREP or first in PREP:
            continue                                   # a function word is no qualifier
        if VERBY.search(strip(last)):
            continue                                   # a verb ends its clause
        risky += 1
        warn("SEAM %d/%d  %s | %s   <- read together: if %s qualifies %s, the "
             "ezafe on %s is missing"
             % (n, n + 1, cur["fa"], nxt["fa"], nxt["fa"].split()[0], last, last))
    if risky:
        warn("%d seams flagged above. NOTES 5.1 calls this the error class no "
             "automatic check can find -- read each one." % risky)

    return report(idx, sents, chunks, src)


def report(idx, sents, chunks, src):
    # "source words" is what the source counts as words: for Japanese, which
    # has no separator, the whole paragraph is one -- so count characters
    # of the script there, and say so
    if LANG.spaced:
        size = "%d source words" % len(src.split())
    else:
        size = "%d source characters" % len(re.sub(r"\s+", "", src))
    print("paragraph %d (printed as %d): %d sentences, %d chunks, %s"
          % (idx, idx + 1, len(sents), len(chunks), size))
    for e in errors:
        print("  ERROR %s" % e)
    for w in warns:
        print("  warn  %s" % w)
    for n in notes:
        print("  note  %s" % n)
    # the count line is what a script greps, and it says what it always said
    # when there is nothing new to say: a book with no notes prints the line
    # it printed before this paragraph of the file existed
    print("\n%d errors, %d warnings%s"
          % (len(errors), len(warns),
             "" if not notes else ", %d note%s"
             % (len(notes), "" if len(notes) == 1 else "s")))
    if not errors:
        if LANG.strip_range:
            print("FIDELITY OK -- reproduces the source exactly once %s are stripped"
                  % ("harakat" if LANG.script == "arabic" else "the marks"))
        else:
            print("FIDELITY OK -- reproduces the source exactly")
    return len(errors)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("para", help="the paragraph's JSON")
    ap.add_argument("--book", default=None, help="book directory, slug or <folder>/<slug>")
    ap.add_argument("--ch", type=int, default=None, help="chapter number")
    a = ap.parse_args()
    sys.exit(min(main(a.para, a.book, a.ch), 120))
