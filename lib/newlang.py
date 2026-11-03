#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add a language to the toolbox: the registry entry and the files around it.

A language is one row of the registry (lib/languages.json for Parseh's own,
config/languages.json for one added on this machine) plus the two files that row
implies -- lib/lang/<code>.tex, what the reading editions' preamble leaves to
the language, and docs/lang/<code>.md, the conventions every annotation
prompt carries -- plus the three directories its content lives in.  Six
things, and the way to get it wrong is to forget one: the entry went in, the
server started, the chips appeared, and the first book of the new language
died in lualatex days later because lib/lang/<code>.tex had never been
written.  Nothing warned, because nothing looked.

So this writes all six at once from the flags, and --check is the other
half: it walks the registry and says, per language, what is there and what
is not, so "did I forget something" has one answer and it takes a second.

    python3 lib/newlang.py                    what it needs, and the languages there are
    python3 lib/newlang.py --check            every entry validated, every file it needs present
    python3 lib/newlang.py ko --name Korean --native 한국어
    python3 lib/newlang.py ko --name Korean --native 한국어 --script other \\
        --chars '\\uAC00-\\uD7AF\\u1100-\\u11FF\\u3130-\\u318F' \\
        --font 'Noto Serif KR' --web-font NotoSerifKR.woff2
    python3 lib/newlang.py ko ... --shipped   the row into Parseh's own table instead
    python3 lib/newlang.py --migrate          a hand-added row of lib/ moved to config/

WHERE THE ROW GOES.  A language added on a machine is that machine's, and
its row is written to config/languages.json -- the registry's second half,
which lib/languages.py reads after Parseh's own table and which no update
touches -- because lib/languages.json ships with Parseh and an update
replaces it: the row used to be spliced in there, and the next version would
have taken it away while the .tex and the .md stayed.  Those two files are
still written to lib/lang/ and docs/lang/, where the rest of the toolbox
looks for them; a release's manifest does not list them, so an update leaves
them alone.  --shipped is the other case, a developer adding a language to
Parseh itself for everyone: the row goes into lib/languages.json, and its
code into that file's `_shipped`.

It asks for nothing it can derive.  The folder is the English name in lower
case, the tag is the folder, the babel name is the English name, the Anki
model ids are the next free pair, the passes follow from what the language
has (the reading alone after pass 1 where the chunks carry words; a bare
pass where there are marks to strip or a reading to take off; a last pass
where there is an alternate face or a vertical setting), and the labels
follow the script.  Every pass gets the NAME its button will wear on a page
-- "Sentence", "Chunks", "Pinyin only", at most 12 characters, the same
rule languages.default_level_name gives an older row -- and a one-line title
that says what it shows; a person renames a level on their own pages, and
the name written here is what comes back when they empty the field.  It
derives nothing it should be told: the direction, the
script kind, the character ranges, the fonts, whether there is a reading,
whether the chunks carry words, whether the language is ever set vertically.
Those are the flags, and getting one wrong is not something a default can
rescue.

Validation is hard and the refusals are loud -- an existing code, a folder
already in use, a code that is not two or three letters, a `chars` range
that does not compile as a regex in Python AND as a JS RegExp source (the
same string is handed to both: lib/languages.py compiles it, player.js does
`new RegExp('[' + L.chars + ']')`), an Anki id already taken.  A font the
machine does not have is a WARNING and not a refusal: the entry may well be
written on one machine for another, and every font lookup in the toolbox
already falls back.

What it cannot write is the prose: the "How to read this" page of the
reading editions and the annotation conventions.  Those are the two
templates it fills, lib/lang/_template.tex and docs/lang/_template.md, and
the last thing it prints is the short list of what is still yours to do.
Nor does it write lib/verbs/<code>.py, the recipe that turns a dictionary's
verb into a \\vb -- that is the language's grammar, in code -- and until
somebody does, the new language's verbs are offered as \\dw; the same list
says so, and names the registry's `vb_video_bare`, which has no flag.

Standard library only, like everything the server imports.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
sys.path.insert(0, LIB)
import languages                                               # noqa: E402

REGISTRY = os.path.join(LIB, "languages.json")     # Parseh's own rows
PERSONAL = languages.PERSONAL                      # this machine's (config/languages.json)
LANG_TEX = os.path.join(LIB, "lang")
LANG_DOCS = os.path.join(ROOT, "docs", "lang")
FONT_DIR = os.path.join(LIB, "fonts")
STUDIO = os.path.join(ROOT, "markdown")

# The Anki note-type ids are a stamp plus ten per language, vocab and
# opposites: fa 1724563200001/2, ar ...011/12, it ...021/22, ja ...031/32.
# Ten apart so a language can grow a third note type without moving anyone,
# and never reused: an id is what Anki matches a note type by, so two
# languages sharing one would merge two people's decks (youtube/anki/README).
ANKI_BASE = 1724563200000
ANKI_STEP = 10
# A LANGUAGE ADDED ON ONE MACHINE TAKES ITS PAIR FROM ANOTHER PART OF THE GRID.
# Parseh's own languages walk up from slot 0, and the next one it ships will
# take the next free slot of THAT walk -- which, in the checkout it is added
# in, knows nothing of a Korean somebody added on their own machine.  Had the
# Korean taken the same walk it would have taken the same slot, and after the
# update Anki would merge the two note types.  So a person's language draws a
# slot at random from PERSONAL_SLOT up, where Parseh's walk never reaches, and
# at random rather than the next free one because two people who each add a
# language and then swap decks meet the same danger one step further on: a
# fixed "first personal slot" would be everybody's first, and ten million
# slots drawn from make that meeting a one-in-millions accident.
PERSONAL_SLOT = 1000
PERSONAL_SLOTS = 10 ** 7
_pick = random.SystemRandom().randrange            # tests patch it

# What a script kind decides when the flags do not.  `chars` is the regex
# character class the whole toolbox detects a run of the language by -- null
# for a Latin script, where a run cannot be told from the English round it
# and is marked by hand instead (docs/languages.md section 5).
SCRIPTS = {
    "arabic": {
        "dir": "rtl",
        "chars": ("\\u0600-\\u06FF\\u0750-\\u077F\\u08A0-\\u08FF"
                  "\\uFB50-\\uFDFF\\uFE70-\\uFEFF\\u200C"),
        "word_sep": " ",
        "digits": "٠١٢٣٤٥٦٧٨٩",
        "strip": "\\u064B-\\u0652",      # the harakat: what the bare pass drops
        "tex_script": "Arabic",
        "babel_options": "onchar=ids fonts",
        "require_tr": True,
        "translit_label": "transliteration",
        "vocal_label": "vowelled", "bare_label": "bare",
    },
    "cjk": {
        "dir": "ltr",
        "chars": ("\\u3000-\\u303F\\u3040-\\u309F\\u30A0-\\u30FF\\u31F0-\\u31FF"
                  "\\u3400-\\u4DBF\\u4E00-\\u9FFF\\uF900-\\uFAFF\\uFF00-\\uFFEF"
                  "\\u2E80-\\u2FDF"),
        "word_sep": "",                  # no separator: a chunk is one word
        "digits": "0123456789",
        "strip": None,
        "tex_script": "CJK",
        "babel_options": "onchar=ids fonts,intraspace=0 .1 0",
        "require_tr": True,
        "translit_label": "transliteration",
        "vocal_label": "the sentence", "bare_label": "plain",
    },
    "devanagari": {
        "dir": "ltr",
        # U+0900..097F is the block itself -- the letters, the vowel signs,
        # the virama, the danda and the double danda, and the ten figures.
        # The two extension blocks carry the Vedic accents an edition of a
        # canonical text may keep.  ZWNJ and ZWJ are IN the class and not
        # separators: in Devanagari they are how a writer says whether a
        # virama makes a conjunct or a half-form, so a run broken at one
        # would be two runs of a word that is one.
        "chars": "\\u0900-\\u097F\\uA8E0-\\uA8FF\\u1CD0-\\u1CFF\\u200C\\u200D",
        "word_sep": " ",
        "digits": "\u0966\u0967\u0968\u0969\u096A\u096B\u096C\u096D\u096E\u096F",
        # Nothing comes off: Devanagari writes its vowels, so there is no
        # layer to strip and pass 3 would reprint pass 1.  (An edition with
        # Vedic accents could strip \u0951-\u0954; no language here does.)
        "strip": None,
        "tex_script": "Devanagari",
        "babel_options": "onchar=ids fonts",
        "require_tr": True,
        "translit_label": "transliteration",
        "vocal_label": "the sentence", "bare_label": "plain",
    },
    "latin": {
        "dir": "ltr",
        "chars": None,
        "word_sep": " ",
        "digits": "0123456789",
        "strip": None,
        "tex_script": "Latin",
        "babel_options": "",
        "require_tr": False,             # the line is a pronunciation aid
        "translit_label": "pronunciation",
        "vocal_label": "the sentence", "bare_label": None,
    },
    "other": {
        "dir": "ltr",
        "chars": None,                   # --chars is then required
        "word_sep": " ",
        "digits": "0123456789",
        "strip": None,
        "tex_script": "",
        "babel_options": "onchar=ids fonts",
        "require_tr": True,
        "translit_label": "transliteration",
        "vocal_label": "the sentence", "bare_label": "plain",
    },
}


# --------------------------------------------------------------- the registry
def read_registry():
    """lib/languages.json as text, and the whole registry as data.

    The text is Parseh's own file, and it matters for --shipped: the entry is
    spliced into it rather than dumped over it, so the hand-formatted
    entries and the _comment key come out of this byte for byte.  The data
    is both halves -- that file's keys, then the rows of
    config/languages.json that lib/languages.py takes in -- because every
    question asked of it (is the code taken, the folder, the Anki ids?) is a
    question about every language this machine knows.  Two keys say which
    rows are whose: `_mine`, the person's codes in order, and `_problems`,
    the person's rows that were left out and why."""
    with open(REGISTRY, encoding="utf-8") as f:
        text = f.read()
    reg = json.loads(text)
    rows, mine, problems = languages.read_rows(REGISTRY, PERSONAL)
    for code, d in rows.items():
        reg.setdefault(code, d)
    reg["_mine"] = [c for c in rows if c in mine]
    reg["_problems"] = problems
    return text, reg


def entries(reg):
    """The language rows: everything but the _comment key."""
    return {k: v for k, v in reg.items()
            if not k.startswith("_") and isinstance(v, dict)}


def used_anki_ids(reg):
    """Every note-type id the registry names, whatever key it sits under --
    a language with a third note type one day must not be walked past."""
    out = {}
    for code, d in entries(reg).items():
        for key, val in (d.get("anki") or {}).items():
            if isinstance(val, int):
                out.setdefault(val, []).append("%s.%s" % (code, key))
    return out


# IDS THAT HAVE LEFT THE REGISTRY AND MAY NOT COME BACK.  A note-type id
# that was ever synced into somebody's Anki is retired for good: hand it to a
# new language and Anki merges the two note types on import, quietly, and the
# cards of the old language start wearing the fields of the new one.  A row
# removed from the registry takes its ids out of `used_anki_ids` with it, so
# the grid LOOKS free where it is not -- which is why the retired ones are
# written down here rather than left to a note in a document.
#
#   1724563200091/092  Pali (slot 9), removed 2026-09
RETIRED_ANKI_IDS = frozenset((1724563200091, 1724563200092))


def next_anki_pair(reg, personal=False):
    """The next free (vocab, opposites) pair on the 1724563200000 + 10n grid,
    checked against every id in the registry rather than against the number of
    languages: a language removed by hand would otherwise hand its ids to the
    next one, and Anki would merge the two note types on import.

    RETIRED_ANKI_IDS is checked too, so a slot a departed language once used
    is skipped rather than handed out again.

    `personal` -- a language added on this machine -- draws a free slot at
    random from PERSONAL_SLOT up instead (the constant says why); Parseh's own
    walk stops below it."""
    used = dict(used_anki_ids(reg))
    used.update({i: "retired" for i in RETIRED_ANKI_IDS})

    def pair(n):
        return ANKI_BASE + ANKI_STEP * n + 1, ANKI_BASE + ANKI_STEP * n + 2

    if personal:
        for _ in range(1000):
            n = PERSONAL_SLOT + _pick(PERSONAL_SLOTS)
            vocab, opp = pair(n)
            if vocab not in used and opp not in used:
                return vocab, opp, n
        raise SystemExit("newlang: no free Anki model id in the personal part of the grid")
    n = 0
    while True:
        vocab, opp = pair(n)
        if vocab not in used and opp not in used:
            return vocab, opp, n
        n += 1
        if n >= PERSONAL_SLOT:            # cannot happen; a runaway loop is worse
            raise SystemExit("newlang: no free Anki model id below the personal part "
                             "of the grid")


def insert_entry(text, code, entry):
    """Put the new row into the registry's text.

    json.dump over the whole table would reflow all four existing entries --
    every "name": ... "native": ... line that is deliberately packed four to a
    line becomes one key per line, and the diff of adding a fifth language is
    the whole file.  So only the new entry is dumped (indent=2,
    ensure_ascii=False, as the rest of the file is written) and spliced in
    before the closing brace; everything already there comes out unchanged.
    The result is parsed before it is written, and the row read back and
    compared, so a splice that got the commas wrong cannot reach the disk.
    """
    body = json.dumps(entry, indent=2, ensure_ascii=False)
    body = "\n".join(("  " + line) if i else line
                     for i, line in enumerate(body.splitlines()))
    chunk = '  "%s": %s' % (code, body)
    idx = text.rfind("}")
    head, tail = text[:idx], text[idx:]
    if head.rstrip().endswith("}"):
        out = head.rstrip() + ",\n" + chunk + "\n" + tail
    elif head.rstrip().endswith("{"):     # an empty table; cannot happen, but
        out = head.rstrip() + "\n" + chunk + "\n" + tail
    else:                                 # a shape this does not know: dump it all
        reg = json.loads(text)
        reg[code] = entry
        out = json.dumps(reg, indent=2, ensure_ascii=False) + "\n"
    back = json.loads(out)
    if back.get(code) != entry:
        raise SystemExit("newlang: the spliced registry does not read back as written")
    return out


SHIPPED_LINE = re.compile(r'^(\s*"_shipped":\s*)\[[^\]\n]*\](,?)\s*$', re.M)


def add_shipped(text, code):
    """lib/languages.json's text with `code` added to its `_shipped`, the list
    of the rows that are Parseh's own.  A row that is not named there is taken
    for one somebody added on their own machine, and moved out to
    config/languages.json when Parseh starts -- so --shipped has to say both
    things, the row and the name, or the language it adds for everybody would
    leave the table the first time an install started.  The line is rewritten
    in place, one line as it stands; the result is parsed and compared before
    it is let near the disk, like the splice above."""
    before = json.loads(text)
    have = before.get("_shipped")
    if not isinstance(have, list):
        raise SystemExit("newlang: lib/languages.json has no _shipped list to add %r to"
                         % code)
    if code in have:
        return text
    m = SHIPPED_LINE.search(text)
    if not m:
        raise SystemExit("newlang: lib/languages.json's _shipped is not the one line "
                         "this can rewrite; add %r to it by hand" % code)
    line = m.group(1) + json.dumps(have + [code], ensure_ascii=False) + m.group(2)
    out = text[:m.start()] + line + text[m.end():]
    back = json.loads(out)
    if back.get("_shipped") != have + [code] or \
            {k: v for k, v in back.items() if k != "_shipped"} != \
            {k: v for k, v in before.items() if k != "_shipped"}:
        raise SystemExit("newlang: _shipped did not read back as written")
    return out


# ------------------------------------------------------------------ validation
def class_body(chars):
    """Read the class body for what compiles and is still wrong.

    This runs BEFORE either engine and not instead of them, which cost an
    afternoon to learn: `a-z]` is accepted by Python re AND by JS, because
    both read it as the class [a-z] followed by a literal ], and the
    language would then have matched every character after the first range
    it was given.  A compiler cannot catch that; only reading the string
    can.  Returns (ok, why)."""
    for bad, why in (("\\u{", "\\u{...} needs JS's u flag and is not Python's syntax"),
                     ("\\p{", "\\p{...} is a Unicode property escape: neither engine "
                              "takes it inside a class here"),
                     ("[:", "a POSIX class ([:alpha:]) is not a range in either engine")):
        if bad in chars:
            return False, why
    if re.search(r"(?<!\\)\]", chars):
        return False, ("an unescaped ] closes the class early -- both engines accept "
                       "it and the rest of the range becomes literal text")
    if re.search(r"(?<!\\)\[", chars):
        return False, "an unescaped [ inside the class body"
    if re.search(r"(^|[^\\])(\\\\)*\\$", chars):
        return False, "the body ends with a lone backslash, which escapes the closing ]"
    return True, ""


def js_regex(chars):
    """Does this character class compile as a JS RegExp source?  The same
    string goes to Python's re and to the browser's `new RegExp('[' + chars +
    ']')` (youtube/lib/player.js), and the two accept different things -- so
    it is compiled in a real JS engine when there is one (deno, which the
    ilya-frank environment carries) and taken on trust when there is not.
    Returns (ok, how, detail)."""
    lit = json.dumps(chars)
    import runtime
    deno = runtime.tool("deno", runtime.find_env()[0])
    if deno:
        js = ("try { new RegExp('[' + %s + ']'); } "
              "catch (e) { console.log('ERR ' + e.message); Deno.exit(0); }\n"
              "try { new RegExp('[' + %s + ']', 'u'); } "
              "catch (e) { console.log('NOU ' + e.message); }\n" % (lit, lit))
        try:
            r = subprocess.run([deno, "eval", "--no-check", js],
                               capture_output=True, text=True, timeout=60)
            out = (r.stdout or "").strip()
            if out.startswith("ERR"):
                return False, "deno", out[4:]
            if out.startswith("NOU"):
                # the toolbox never sets the u flag, so this is a note, not a
                # failure; it would bite the day some page did
                return True, "deno", "compiles, but not with the u flag: " + out[4:]
            if r.returncode != 0:
                return False, "deno", (r.stderr or "").strip()[:200]
            return True, "deno", ""
        except (OSError, subprocess.SubprocessError):
            pass                          # deno is there but would not run
    return True, "read", "no JS engine here, so read but not compiled"


def check_chars(chars):
    """(ok, detail) for a character class: Python first, then JS."""
    if chars is None:
        return True, "none (a Latin-script language: runs are marked, not detected)"
    ok, why = class_body(chars)
    if not ok:
        return False, why
    try:
        re.compile("[%s]" % chars)
    except re.error as e:
        return False, "Python re refuses it: %s" % e
    ok, how, detail = js_regex(chars)
    if not ok:
        return False, "JS refuses it (%s): %s" % (how, detail)
    return True, ("compiles in Python and JS" + ((" -- " + detail) if detail else ""))


_FAMILIES = None


def families():
    """Every font family this machine has, lower-cased: fc-list where there
    is one, plus the faces that travel with the toolbox in lib/fonts (which
    fontconfig does not see -- the books put that directory on OSFONTDIR
    themselves, so a bundled face is installed for our purposes and not for
    fc-list's)."""
    global _FAMILIES
    if _FAMILIES is not None:
        return _FAMILIES
    fams = set()
    if shutil.which("fc-list"):
        try:
            r = subprocess.run(["fc-list", ":", "family"],
                               capture_output=True, text=True, timeout=60)
            for line in (r.stdout or "").splitlines():
                for name in line.split(","):
                    fams.add(name.strip().lower())
        except (OSError, subprocess.SubprocessError):
            pass
    for fn in (os.listdir(FONT_DIR) if os.path.isdir(FONT_DIR) else []):
        stem, ext = os.path.splitext(fn)
        if ext.lower() not in (".ttf", ".otf", ".woff2"):
            continue
        stem = re.sub(r"[-_](Regular|Bold|Italic|BoldItalic|Medium|Light)$", "", stem)
        fams.add(re.sub(r"[^a-z0-9]", "", stem.lower()))
    _FAMILIES = fams
    return fams


def has_font(name):
    """Is this family on the machine?  None when nothing could look."""
    if not name:
        return None
    if not shutil.which("fc-list") and not os.path.isdir(FONT_DIR):
        return None
    fams = families()
    flat = re.sub(r"[^a-z0-9]", "", name.lower())
    return name.lower() in fams or flat in fams


CODE_RE = re.compile(r"^[a-z]{2,3}$")
FOLDER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def refuse(msg):
    print("newlang: " + msg, file=sys.stderr)
    raise SystemExit(2)


# the titles of the two passes that read the same in every language: the
# shipped rows (lib/languages.json) say exactly this
CHUNKS_TITLE = "the sentence cut into chunks, each with its gloss beside it"
VERTICAL_TITLE = "the sentence in vertical columns (tategaki)"


# --------------------------------------------------------------- what to write
def build_entry(a, reg):
    """The registry row, in the key order the four existing ones use."""
    S = SCRIPTS[a.script]
    name = a.name.strip()
    folder = (a.folder or re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")).strip()
    tag = (a.tag or folder).strip()
    direction = a.dir or S["dir"]
    chars = a.chars if a.chars is not None else S["chars"]
    if isinstance(chars, str) and not chars.strip():
        chars = None
    word_sep = S["word_sep"] if a.word_sep is None else a.word_sep
    digits = a.digits or S["digits"]
    strip = S["strip"] if a.strip is None else (a.strip or None)
    reading = bool(a.reading)
    vertical = bool(a.vertical)
    words = bool(a.words)
    require_tr = S["require_tr"] if a.require_tr is None else a.require_tr
    # A bare pass exists only where its text differs from pass 1's: marks
    # that come off (Persian, Arabic), a reading that is taken away
    # (Japanese), or the readings over the words of a chunk that carries them
    # (Chinese).  Italian has none of these, so it would reprint pass 1.
    has_bare = bool(strip) or reading or words
    # A fourth pass is either the alternate face (nastaliq) or the vertical
    # setting (tategaki); a language may have an alternate face for the title
    # and the chapter numbers without a fourth pass of its own.
    alt = (a.alt_font or "").strip() or None
    alt_key = (a.alt_key or ("alt" if alt else None))
    vocab, opp, slot = next_anki_pair(reg, personal=not getattr(a, "shipped", False))
    # A RELATIVE (--like) lends what it shares with the new language and nothing
    # it could get wrong: the verb entry's shape and how compounds are glossed;
    # its chunking rules are copied by add() as a file to review.  Words,
    # conventions and lookup rules are the new language's own (lib/langprompts.py).
    like = languages.LANGS.get(a.like) if getattr(a, "like", None) else None
    if getattr(a, "like", None) and like is None:
        refuse("--like %r is not a language of this Parseh" % a.like)
    vb_labels = [s.strip() for s in (a.vb_labels or "").split(",") if s.strip()] \
        or (list(like.vb_labels) if like and like.vb_labels else ["pres.", "past"])
    if len(vb_labels) != 2:
        refuse("--vb-labels wants two, comma-separated: the label before the second "
               "form and the one before the third (got %s)" % ", ".join(vb_labels))
    vb_forms = [s.strip() for s in (a.vb_forms or "").split(",") if s.strip()] \
        or (list(like.vb_forms) if like and like.vb_forms else list(VB_FORMS_DEFAULT))
    if len(vb_forms) != 3:
        refuse("--vb-forms wants three, comma-separated: what the first, second and "
               "third form of a \\vb are (infinitive,present stem,past stem -- got %s)"
               % ", ".join(vb_forms))
    # Both lists are written into lib/lang/<code>.tex as they are -- the labels
    # as \FrankVbPres/\FrankVbPast, the forms into its comments and its
    # how-to placeholder -- so a character TeX reads as syntax would make the
    # scaffold a file that does not compile, days later, in somebody's book.
    for flag, vals in (("--vb-labels", vb_labels), ("--vb-forms", vb_forms)):
        bad = [v for v in vals if VB_TEXSPECIAL.search(v)]
        if bad:
            refuse("%s: %s carries a character TeX reads as syntax (\\ { } $ %% & "
                   "# _ ^ ~); write the words plainly" % (flag, ", ".join(bad)))

    css_main = a.css_font or (("'%s', serif" % a.font) if a.font else
                              ("'TeX Gyre Pagella', 'Palatino Linotype', "
                               "Palatino, Georgia, serif"
                               if a.script == "latin" else "serif"))
    css_alt = ("'%s', %s" % (alt, css_main)) if alt else None
    # A language whose chunks carry words (lib/wordline.py) sets each word's
    # reading over it in pass 1 and gives the reading alone right after it,
    # before the chunks: vocal, aloud, chunks, bare, alt.  The reading is the
    # kana where there is one and the transliteration where there is not.
    sound = ((a.reading_label or "reading") if reading
             else (a.translit_label or S["translit_label"]))
    # EVERY PASS CARRIES FOUR THINGS.  Its key, which is what the page and the
    # PDF tell it by; its NAME, the word a button wears (a level's name, 12
    # characters at most -- languages.default_level_name picks it from the key
    # and from what the row says the language has, the one rule an older row
    # is read by too); its label, the digit the PDF still counts by; and its
    # title, one line saying what the level shows.
    row = {"words": words, "reading": reading, "reading_label": a.reading_label,
           "translit_label": a.translit_label or S["translit_label"],
           "vocal_label": a.vocal_label or S["vocal_label"],
           "strip": strip, "script": a.script, "fonts": {"alt_key": alt_key}}
    passes = []

    def add_pass(key, title, **more):
        p = {"key": key}
        p["name"] = languages.default_level_name(row, dict(p, **more))
        # THE LABEL counts the passes this language actually has.  It used to be
        # a flat "4", which is right only for a language that also has a bare
        # pass at 3: Chinese has none, and its reader's buttons read 1, 2, 4.
        # (What each button HIDES is a separate thing, taken from the pass's
        # key -- see tex2html.pass_class.)
        p.update(label=str(len(passes) + 1), title=title, **more)
        passes.append(p)

    marks = ("vowels" if a.script == "arabic" else "marks")
    add_pass("vocal", a.vocal_label or (
        ("with %s over each word" % sound) if words
        else ("with %s over each chunk" % sound) if reading
        else ("the sentence with its %s, to read on its own" % marks) if strip
        else "the sentence, to read on its own"))
    if words:
        add_pass("aloud", "the reading alone, in %s" % sound)
    add_pass("chunks", CHUNKS_TITLE)
    if has_bare:
        add_pass("bare", a.bare_label or (
            ("the sentence as %s is ordinarily printed, with no marks" % name) if strip
            else "plain, as %s is written" % name))
    if vertical:
        add_pass("alt", VERTICAL_TITLE, kind="vertical")
    elif alt:
        add_pass("alt", "the same sentence in %s" % alt, kind="font")

    entry = {
        "name": name, "native": (a.native or name).strip(),
        # WHAT AN OUTSIDE SOURCE CALLS IT.  Parseh keys by ISO 639-1 and
        # Tatoeba keys its exports by 639-3, and the third letter is not
        # derivable: Persian is `pes` (Western Persian) where the
        # macrolanguage `fas` has no export at all.  Left empty here rather
        # than guessed; lib/getcorpus.py refuses by name until it is filled.
        "iso3": (a.iso3 or "").strip(),
        "folder": folder, "tag": tag,
        "dir": direction, "script": a.script,
        "chars": chars,
        "word_sep": word_sep, "digits": digits,
        "strip": strip,
        "reading": reading, "vertical": vertical, "words": words,
        "require_tr": bool(require_tr),
        "translit_label": a.translit_label or S["translit_label"],
        "reading_label": (a.reading_label or "reading") if reading else None,
        "vocal_label": a.vocal_label or S["vocal_label"],
        "bare_label": (a.bare_label or S["bare_label"] or "bare") if has_bare else None,
        # what \vb prints before its second and third forms.  The pair goes
        # into lib/lang/<code>.tex as \FrankVbPres / \FrankVbPast as well:
        # the PDF prints those, the reader takes these, and check() refuses to
        # let the two drift apart.
        "vb_labels": vb_labels,
        # and what its three forms ARE, in words, for whoever types one: the
        # chunk editor's \vb button names them (before this existed it built
        # "infinitive, pres. stem, past stem" out of the labels, and told
        # Turkish "stem stem, aor. stem"), and the scaffolded .tex and docs
        # name them too.
        "vb_forms": vb_forms,
        "fonts": {
            "main": a.font or None,
            "alt": alt, "alt_key": alt_key,
            "css_main": css_main,
            "css_alt": css_alt,
            "alt_line_height": a.alt_line_height,
            "web_files": list(a.web_font or []),
        },
        "tex": {
            "babel": a.babel or name.lower(),
            # Which locale babel takes the language's DATA from, which is not
            # always the language: babel ships no .ini for every language
            # there is, and one it has none for wants the locale of another
            # language written in the same script (a Devanagari one takes
            # sa-Deva).  \babelprovide[import=<this>]{<babel>} is
            # what lib/lang/<code>.tex issues, and an import naming an ini
            # that is not installed is a build that dies in lualatex with
            # "Unknown language", days later and nowhere near here.
            "import": a.babel_import or a.code,
            "options": S["babel_options"],
            "script": S["tex_script"],
            "language": a.tex_language or name,
            "main": a.font or None,
            "main_fallbacks": list(a.font_fallback or []),
            "alt": alt, "alt_options": ("" if alt else None),
            "hyphen": a.hyphen or (name.lower() if a.script == "latin" else None),
        },
        "passes": passes,
        "anki": {"field": a.anki_field or name,
                 "vocab_model": vocab, "opposites_model": opp,
                 "vocab_name": "Frank %s" % name,
                 "opposites_name": "Frank %s Opposites" % name},
        "duration_units": [s for s in (a.duration_units or "").split(",") if s.strip()],
        "chapter_words": [s for s in (a.chapter_words or "").split(",") if s.strip()],
    }
    entry["duration_units"] = [s.strip() for s in entry["duration_units"]]
    entry["chapter_words"] = [s.strip() for s in entry["chapter_words"]]
    if like:
        entry["like"] = like.code
        if like.compounds == "parts":
            entry["compounds"] = "parts"
    entry["_slot"] = slot                 # not part of the row; popped by the caller
    return entry


def lua_filters(entry):
    """The two Lua functions lib/frank-preamble.tex calls for every language:
    frank_strip (the bare form) and frank_latin (the label's digits as
    ASCII).  Written from `strip` and `digits`, which is the whole reason
    both are in the registry.  No #, % or literal backslash in a \\directlua
    body -- TeX reads it first (NOTES section 9 of the Persian book)."""
    strip, digits = entry["strip"], entry["digits"]
    # `not (a == b)` rather than a ~= b, and `--` rather than a TeX comment:
    # TeX reads the body before Lua does, and ~ is active there.
    if strip:
        m = re.match(r"^\\u([0-9A-Fa-f]{4})-\\u([0-9A-Fa-f]{4})(.*)$", strip)
        singles = re.findall(r"\\u([0-9A-Fa-f]{4})", m.group(3)) if m else []
        if m:
            cond = "c < 0x%s or c > 0x%s" % (m.group(1), m.group(2))
            for s in singles:
                cond += " and not (c == 0x%s)" % s
            body = ("  function frank_strip(s)\n"
                    "    local t, n = {}, 0\n"
                    "    for _, c in utf8.codes(s) do\n"
                    "      if %s then n = n + 1 ; t[n] = utf8.char(c) end\n"
                    "    end\n"
                    "    return table.concat(t)\n"
                    "  end" % cond)
        else:
            body = ("  -- TODO: the registry's strip is " + strip + ", which this scaffold\n"
                    "  -- could not read as a range; write the filter by hand, or pass 3\n"
                    "  -- will print pass 1 again.\n"
                    "  function frank_strip(s) return s end")
    else:
        body = "  function frank_strip(s) return s end"
    if digits and digits != "0123456789":
        code = ord(digits[0])
        body += ("\n  function frank_latin(s)\n"
                 "    local t, n = {}, 0\n"
                 "    for _, c in utf8.codes(s) do\n"
                 "      if c >= 0x%04X and c <= 0x%04X then c = c - 0x%04X + 0x30 end\n"
                 "      n = n + 1 ; t[n] = utf8.char(c)\n"
                 "    end\n"
                 "    return table.concat(t)\n"
                 "  end" % (code, code + 9, code))
    else:
        body += "\n  function frank_latin(s) return s end"
    return body


def font_block(code, entry):
    """The \\babelprovide / \\babelfont block of lib/lang/<code>.tex.  No font
    is NAMED here: \\FrankPickFont walks the registry's tex.main then
    tex.main_fallbacks and takes the first face installed (docs/languages.md
    section 12), so the .tex and the .json can never drift apart."""
    tex, babel = entry["tex"], entry["tex"]["babel"]
    opts = ("import=%s,%s" % (tex["import"], tex["options"])) if tex["options"] \
        else ("import=%s" % tex["import"])
    out = ["\\babelprovide[%s]{%s}" % (opts, babel)]
    feat = ",".join(x for x in ("Script=%s" % tex["script"] if tex["script"] else "",
                                "Language=%s" % tex["language"] if tex["language"] else "",
                                "Renderer=HarfBuzz") if x)
    if tex["main"]:
        out.append("\\FrankPickFont{\\FrankMainFontName}{%s}{main}{main_fallbacks}" % code)
        out.append("\\babelfont[%s]{rm}[%s]{\\FrankMainFontName}" % (babel, feat))
    else:
        out.append("%% No font of its own: tex.main is null in the registry, so the text is")
        out.append("%% set in the roman the core preamble already loaded -- the same face as")
        out.append("%% the glosses, which is right for a Latin script and wrong for any other.")
    if tex["alt"]:
        out.append("\\FrankPickFont{\\FrankAltFontName}{%s}{alt}{alt_fallbacks}" % code)
        out.append("\\newfontfamily\\FrankTheAltFont[%s]{\\FrankAltFontName}" % feat)
        out.append("\\newcommand{\\FrankAltFont}{\\FrankTheAltFont}")
    return "\n".join(out)


def fill(template, mapping):
    for k, v in mapping.items():
        template = template.replace("{{%s}}" % k, v)
    return template


def bool_switch(name, value):
    """The switch, padded so the five of them line their comments up: they are
    read as a block, and a ragged one hides which is true."""
    return ("\\Frank%s%s" % (name, "true" if value else "false")).ljust(24) + " "


def render_tex(code, entry):
    path = os.path.join(LANG_TEX, "_template.tex")
    if not os.path.isfile(path):
        refuse("the template lib/lang/_template.tex is missing; nothing to fill")
    with open(path, encoding="utf-8") as f:
        t = f.read()
    has_bare = any(p["key"] == "bare" for p in entry["passes"])
    has_alt = bool(entry["tex"]["alt"])
    todo = []
    if entry["reading"]:
        todo.append(
            "% TODO (reading): \\jruby{text}{kana} -- the reading set small and centred\n"
            "% over the chunk, used by \\chr in pass 1 and as the first line of the gloss.\n"
            "% Copy it from lib/lang/ja.tex: it measures the pair and stacks it when the\n"
            "% box is wider than the column, which is what stops the ruby running into\n"
            "% the gloss (14 overfull boxes before it did).")
    if entry["vertical"]:
        todo.append(
            "% TODO (vertical): \\FrankVertPass -- the last pass as a rotated box, and the\n"
            "% vertical-forms font it is set in.  Copy \\FrankVertFont, \\FrankVertHeight,\n"
            "% \\FrankVertColumn, frank_vert_columns and \\FrankVertPass from lib/lang/ja.tex;\n"
            "% they are tuned so a short sentence follows the plain pass on the same page.")
    if entry.get("words"):
        todo.append(
            "% TODO (words): \\FrankRuby{word}{reading} -- the reading over one word of\n"
            "% a \\chw or \\chrw, in pass 1 and the chunk column.  The core's default is\n"
            "% \\jruby, which prints the word alone where this file defines none: copy\n"
            "% lib/lang/zh.tex's (a transliteration over each word, measured and stacked\n"
            "% when too wide) or ja.tex's \\jruby (a reading), and zh.tex's\n"
            "% \\FrankAloudText, which sets a transliteration in pass 2.")
    if not entry["word_sep"]:
        todo.append(
            "% TODO (no word separator): \\FrankChunkSep is a space by default, which\n"
            "% would show as a gap the source does not have.  Japanese uses\n"
            "%   \\newcommand{\\FrankChunkSep}{\\hskip 0pt plus .1em\\relax}\n"
            "% -- glue of no width, and a place to break the line.")
    return fill(t, {
        "NAME": entry["name"],
        "NATIVE": entry["native"],
        "CODE": code,
        "BABEL": entry["tex"]["babel"],
        "RTL": bool_switch("RTL", entry["dir"] == "rtl"),
        "RTL_WHY": ("chunk right, gloss left; \\pw isolates with \\babelsublr"
                    if entry["dir"] == "rtl"
                    else "chunk left, gloss right; \\pw needs no bidi isolate"),
        "HAS_BARE": bool_switch("HasBare", has_bare),
        "HAS_BARE_WHY": ("pass 3 is the same text with the marks off" if has_bare
                         else "nothing comes off, so pass 3 would repeat pass 1"),
        "HAS_ALT": bool_switch("HasAlt", has_alt),
        "HAS_READING": bool_switch("HasReading", entry["reading"]),
        "HAS_VERT": bool_switch("HasVert", entry["vertical"]),
        "HAS_ALOUD": bool_switch("HasAloud", bool(entry.get("words"))),
        "FONT_BLOCK": font_block(code, entry),
        "LUA_FILTERS": lua_filters(entry),
        "TODO": ("\n\n".join(todo) + "\n\n") if todo else "",
        "VB_PRES": entry["vb_labels"][0],
        "VB_PAST": entry["vb_labels"][1],
        "VB_LABELS": ", ".join('"%s"' % s for s in entry["vb_labels"]),
        "VB_FORM1": entry["vb_forms"][0],
        "VB_FORM2": entry["vb_forms"][1],
        "VB_FORM3": entry["vb_forms"][2],
        "VB_FORMS": ", ".join('"%s"' % s for s in entry["vb_forms"]),
        # the titles, which now run to a clause of their own ("the sentence, to read
        # on its own"), so they are told apart by a semicolon and not by a comma
        "PASSES": "; ".join(p["title"] for p in entry["passes"]),
        "NPASSES": {1: "once", 2: "twice", 3: "three times", 4: "four times",
                    5: "five times"}.get(len(entry["passes"]), "%d times" % len(entry["passes"])),
    })


def render_doc(code, entry):
    path = os.path.join(LANG_DOCS, "_template.md")
    if not os.path.isfile(path):
        refuse("the template docs/lang/_template.md is missing; nothing to fill")
    with open(path, encoding="utf-8") as f:
        t = f.read()
    reading = ("Every glossed chunk carries a reading beside the transliteration, in\n"
               "the `kana` field.\n\n"
               "TODO: what it is written in, and the rule that it is the reading of the\n"
               "**whole chunk** and never a per-character alignment -- with an example of\n"
               "a chunk and its reading. `assemble.py` refuses a chunk without one and\n"
               "`check_batch.py` reports it, so this section is enforced."
               if entry["reading"] else
               "This language has no reading field: the `kana` key is ignored where it\n"
               "appears, and nothing asks for one.")
    return fill(t, {
        "NAME": entry["name"],
        "NATIVE": entry["native"],
        "CODE": code,
        "TR_LABEL": entry["translit_label"],
        "READING": reading,
        "MARKED": ("Runs of %s are **marked** in the studio (`[word]{tl}`): the script\n"
                   "cannot be told from the English round it." % entry["name"]
                   if entry["chars"] is None else
                   "Runs of %s are found by their script, so nothing is marked by hand."
                   % entry["name"]),
        "CHUNK_WORDS_SEAM": ("character boundaries -- there are no spaces to split at"
                             if not entry["word_sep"] else "spaces"),
        "CHUNK_WORDS": ("one chunk is one run of characters -- there are no spaces to split at"
                        if not entry["word_sep"] else
                        "roughly **2--6 words** -- a sense group: a verb with its object, a "
                        "noun with what qualifies it, a preposition with its noun"),
        # the verb's three forms and the two labels, as the registry row has
        # them, so the conventions start from what the page will print and
        # not from a blank the annotator has to reconcile with the .tex
        "VB_FORM1": entry["vb_forms"][0],
        "VB_FORM2": entry["vb_forms"][1],
        "VB_FORM3": entry["vb_forms"][2],
        "VB_PRES": entry["vb_labels"][0],
        "VB_PAST": entry["vb_labels"][1],
    })


def write_file(path, text, force):
    if os.path.exists(path) and not force:
        return False, "exists (use --force to overwrite)"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True, "written"


def content_dirs(folder):
    return [os.path.join(ROOT, "books", folder),
            os.path.join(ROOT, "youtube", "videos", folder),
            os.path.join(STUDIO, "library", folder)]


GITKEEP = ("# git carries no empty directory, and this one must survive a clone:\n"
           "# every tool that lists content walks <door>/<language>/<item>/.\n")


# ------------------------------------------------------------------ the modes
def show():
    """No arguments: what this needs, and what is already there."""
    text, reg = read_registry()
    langs = entries(reg)
    print("newlang -- add a language to Parseh.\n")
    print("  python3 lib/newlang.py --check")
    print("      every entry validated, every file it needs present.  "
          "Non-zero when one is missing.\n")
    print("  python3 lib/newlang.py <code> --name <English> --native <its own name> [flags]")
    print("      writes: the entry in config/languages.json (this machine's languages,")
    print("              which an update never touches), lib/lang/<code>.tex,")
    print("              docs/lang/<code>.md, and the three content directories.")
    print("      --shipped puts the entry in lib/languages.json instead: a language")
    print("              added to Parseh itself, for everybody.\n")
    print("  python3 lib/newlang.py --migrate")
    print("      moves the rows of lib/languages.json that Parseh does not ship to")
    print("      config/languages.json (Parseh does it itself as it starts, except in")
    print("      a git checkout).\n")
    print("  The flags that carry a decision no default can make:")
    print("      --dir rtl|ltr                  which side the chunk sits on")
    print("      --script arabic|devanagari|latin|cjk|other  picks chars, word_sep, digits, strip")
    print("      --chars '\\uXXXX-\\uYYYY...'      the script's ranges (required for --script other)")
    print("      --font 'Noto Serif X'          the face, for TeX and for the CSS stack")
    print("      --web-font File.woff2          a face bundled in lib/fonts (repeatable)")
    print("      --reading [--reading-label kana]  the language has a reading beside the")
    print("                                     transliteration (Japanese's kana)")
    print("      --vertical                     it can be set in columns (tategaki)")
    print("      --words                        its chunks carry words, each with its reading")
    print("                                     (a language written without spaces)")
    print("      --vb-forms a,b,c --vb-labels x,y  the three forms a \\vb gives and the two")
    print("                                     labels it prints before the second and third")
    print("      --force                        overwrite files that are already there")
    print("  Everything else is derived: the folder, the tag, the babel name, the passes")
    print("  (each with the name its button wears, 12 characters at most, and a one-line")
    print("  title), the labels, and the Anki model ids (the next free pair).  A person")
    print("  renames a level on their own pages; the name written here is its default.\n")
    print("  The whole process, end to end, is the guide's page \"Adding a language\"")
    print("  (/guide/ in Parseh); the design is docs/languages.md.\n")
    print("The languages there are (%d):\n" % len(langs))
    hdr = "  %-4s %-10s %-9s %-9s %-4s %-6s %-32s %s"
    print(hdr % ("code", "name", "folder", "script", "dir", "digits", "passes", "anki ids"))
    print("  " + "-" * 100)
    loaded, _ = languages._load(REGISTRY, PERSONAL)
    for code, d in langs.items():
        L = loaded.get(code)
        print(hdr % (code, d.get("name", "?"), d.get("folder", "?"), d.get("script", "?"),
                     d.get("dir", "?"),
                     "native" if d.get("digits") != "0123456789" else "latin",
                     ("/".join(L.pass_keys) +
                      ("  +reading" if L.reading else "") +
                      ("  +words" if L.words else "") +
                      ("  +vertical" if L.vertical else "")) if L else "(cannot be read)",
                     "%s/%s%s" % (d.get("anki", {}).get("vocab_model"),
                                  d.get("anki", {}).get("opposites_model"),
                                  "  added on this machine" if code in reg["_mine"] else "")))
    for code, why in reg["_problems"]:
        print("  left out%s: %s" % ((" " + code) if code else "", why))
    vocab, opp, slot = next_anki_pair(reg)
    print("\n  the next free Anki model ids for a language of Parseh's own (--shipped): "
          "%d / %d (slot %d)" % (vocab, opp, slot))
    print("  a language added on this machine draws a free pair at random from slot %d up"
          % PERSONAL_SLOT)
    return 0


REQUIRED = ("name", "folder", "dir", "script", "word_sep", "digits", "reading",
            "vertical", "fonts", "tex", "passes", "anki")

VB_TEX = re.compile(r"^\s*\\newcommand\{\\FrankVb(Pres|Past)\}\{(.*)\}\s*$", re.M)

# What a row without --vb-forms says its three forms are: languages.py falls
# back to the same three names, neutral on purpose -- Persian's "infinitive,
# present stem, past stem" would be a claim about a grammar nobody has looked
# at yet.
VB_FORMS_DEFAULT = ("dictionary form", "second form", "third form")
# The characters that are TeX syntax and cannot stand bare in a .tex file:
# the same set lib/check_batch.py refuses in a vocabulary line, plus braces.
VB_TEXSPECIAL = re.compile(r"[\\{}$%&#_^~]")


def tex_vb_labels(code):
    """The pair lib/lang/<code>.tex prints -- (\\FrankVbPres, \\FrankVbPast),
    either of them None when the file does not set it.

    A wrapping \\textit or \\emph comes off: the label is the word, and how
    it is set is the page's business (ja prints \\textit{-te} for "-te").
    tests/smoke.py imports this, so the .tex is read one way only."""
    path = os.path.join(LANG_TEX, code + ".tex")
    found = {}
    try:
        with open(path, encoding="utf-8") as f:
            for which, body in VB_TEX.findall(f.read()):
                found[which] = re.sub(r"^\\(?:textit|emph)\{(.*)\}$", r"\1", body.strip())
    except OSError:
        pass
    return found.get("Pres"), found.get("Past")


TEX_SWITCH = re.compile(r"^\\FrankHas(Bare|Aloud|Vert)(true|false)\b", re.M)


def tex_switches(code):
    """The pass switches lib/lang/<code>.tex sets, {"Bare": bool, "Aloud":
    bool, "Vert": bool}; one the file does not set is false, as \\newif
    leaves it."""
    found = {"Bare": False, "Aloud": False, "Vert": False}
    try:
        with open(os.path.join(LANG_TEX, code + ".tex"), encoding="utf-8") as f:
            for name, val in TEX_SWITCH.findall(f.read()):
                found[name] = val == "true"
    except OSError:
        pass
    return found


_BABEL_DIR = []


def has_babel(locale):
    """Does this TeX install carry babel's data for that locale?

    True / False / None when there is no kpsewhich to ask.  babel keeps them
    as locale/<two-letter>/babel-<locale>.ini, so `sa-Deva` lives under `sa`;
    the directory is found once through kpsewhich, the way the rest of the
    toolbox finds anything of TeX's.
    """
    if not _BABEL_DIR:
        kp = shutil.which("kpsewhich")
        root = ""
        if kp:
            try:
                r = subprocess.run([kp, "-var-value", "TEXMFDIST"],
                                   capture_output=True, text=True, timeout=60)
                root = (r.stdout or "").strip()
            except Exception:
                root = ""
        _BABEL_DIR.append(os.path.join(root, "tex", "generic", "babel", "locale")
                          if root else None)
    base = _BABEL_DIR[0]
    if not base or not os.path.isdir(base):
        return None
    return os.path.isfile(os.path.join(base, locale.split("-")[0],
                                       "babel-%s.ini" % locale))


def check(strict=False):
    """Walk the registry and report, per language, what is there.

    Two levels, because two things are missing for different reasons.  A
    MISSING file or a duplicate id is a fault: the toolbox will break on it,
    so the exit code is non-zero.  A content directory that is not there and
    a font this machine does not have are NOTES: git carries no empty
    directory (the first book, video or document makes it, and a language
    scaffolded here has a .gitkeep so it never comes up), and a registry
    entry may be written on one machine for another.  --strict makes the
    notes count too.
    """
    text, reg = read_registry()
    langs = entries(reg)
    faults, notes = [], []

    def fault(code, msg):
        faults.append((code, msg))
        print("      MISSING  " + msg)

    def note(code, msg):
        notes.append((code, msg))
        print("      note     " + msg)

    def good(msg):
        print("      ok       " + msg)

    print("checking %s (Parseh's own)\n     and %s (the languages added on this "
          "machine%s)\n" % (REGISTRY, PERSONAL,
                            "" if os.path.isfile(PERSONAL) else ": none yet"))
    mine = set(reg.get("_mine") or ())
    own_rows = json.loads(text)
    shipped_list = own_rows.get("_shipped")
    # read as lib/languages.py reads them, from the same two files, so a row
    # it would leave out is found here and not only in a server's log.  A row of
    # PARSEH'S OWN that it refuses (a pass without a name, say) is not left out:
    # it raises, as the server's import would, and the check says what it said
    try:
        loaded, problems = languages._load(REGISTRY, PERSONAL)
    except ValueError as e:
        print("      MISSING  lib/languages.json: %s" % e)
        print("\nwhat is missing:\n  %s" % e)
        return 1
    seen_folders = {}
    # AND THE VALIDATOR KNOWS THE RETIRED ONES TOO.  next_anki_pair refuses to
    # hand them out, but a row written by hand, pasted, or restored off an
    # older branch never asks it -- and --check would have called that clean,
    # which is the one silent Anki note-type merge this list exists to stop.
    seen_ids = {i: "retired (a departed language was synced under it)"
                for i in RETIRED_ANKI_IDS}
    for code, d in langs.items():
        print("  %s  %s (%s)%s" % (code, d.get("name", "?"), d.get("folder", "?"),
                                   "  -- added on this machine" if code in mine else ""))
        # A PERSON'S ROW IN PARSEH'S OWN FILE is one an older newlang.py wrote
        # there, or a hand did: the next update replaces that file, and the
        # row goes with it.  Parseh moves it to config/ as it starts; a git
        # checkout is left to its author, who is told here.
        if code in mine and code in own_rows:
            note(code, "its row is in lib/languages.json, which is Parseh's own and "
                       "which an update replaces, and _shipped does not name it: "
                       "Parseh moves it to config/languages.json when it starts (in a "
                       "git checkout, `newlang.py --migrate` does; or add it to "
                       "_shipped, if it is a language for everybody)")
        if code in mine and code not in loaded:
            fault(code, "every page goes without this language: %s"
                        % "; ".join(why for c, why in problems if c == code))
        if not (d.get("iso3") or "").strip():
            note(code, "no iso3: %s can have no parallel corpus until one is "
                       "written (Tatoeba keys its exports by ISO 639-3)" % code)
        for key in REQUIRED:
            if key not in d:
                fault(code, "the entry has no %r" % key)
        if not CODE_RE.match(code):
            fault(code, "the code is not two or three lower-case letters")
        if d.get("dir") not in ("rtl", "ltr"):
            fault(code, "dir is %r, not rtl or ltr" % d.get("dir"))
        if len(d.get("digits") or "") != 10:
            fault(code, "digits is %r: it must be the ten digits 0-9" % d.get("digits"))
        folder = d.get("folder")
        if folder in seen_folders:
            fault(code, "the folder %r is already %s's" % (folder, seen_folders[folder]))
        seen_folders[folder] = code
        # the two files
        for path, what in ((os.path.join(LANG_TEX, code + ".tex"),
                            "lib/lang/%s.tex (the reading editions' preamble)" % code),
                           (os.path.join(LANG_DOCS, code + ".md"),
                            "docs/lang/%s.md (the annotation conventions)" % code)):
            if os.path.isfile(path):
                good(what)
            else:
                fault(code, what)
        # the \vb labels, in two places that must say the same thing: the .tex
        # prints them in the PDF, the registry hands them to the reader
        vb, tex_vb = d.get("vb_labels"), tex_vb_labels(code)
        if not (isinstance(vb, list) and len(vb) == 2
                and all(isinstance(x, str) and x for x in vb)):
            fault(code, "vb_labels is %r: it must be the two labels a \\vb prints, "
                        "the same pair lib/lang/%s.tex sets" % (vb, code))
        elif None in tex_vb:
            fault(code, "lib/lang/%s.tex does not set %s, so the PDF labels the form "
                        "as the preamble's default and the reader as %r"
                        % (code, " or ".join(n for n, v in
                                             zip(("\\FrankVbPres", "\\FrankVbPast"), tex_vb)
                                             if v is None), vb))
        elif list(tex_vb) != vb:
            fault(code, "vb_labels is %s but lib/lang/%s.tex prints %s: one book would "
                        "teach two grammars" % (vb, code, list(tex_vb)))
        else:
            good("vb labels %r / %r: the registry and the .tex agree" % tuple(vb))
        # and what the three forms are, in words: the chunk editor names them
        # to whoever types a \vb, so a row that lost one would have the
        # editor describe two slots of seven, or languages.py quietly fall back
        # to the neutral names and tell a Persian annotator "second form"
        forms = d.get("vb_forms")
        if not (isinstance(forms, list) and len(forms) == 3
                and all(isinstance(x, str) and x.strip() for x in forms)):
            fault(code, "vb_forms is %r: it must be the three forms a \\vb gives, "
                        "in the order it prints them (fa: infinitive, present stem, "
                        "past stem)" % (forms,))
        else:
            good("vb forms: %s" % " / ".join(forms))
        # the passes, in two places that must say the same thing: the registry
        # gives the reader its buttons, the .tex switches the passes on in the
        # PDF.  A pass one has and the other has not is a button over nothing,
        # or a pass only one of the two editions of the book prints.
        plist = [p for p in d.get("passes") or [] if isinstance(p, dict)]
        keys = [p.get("key") for p in plist]
        sw = tex_switches(code)
        off = [what for what, has, tex_has in (
                   ("bare", "bare" in keys, sw["Bare"]),
                   ("aloud", "aloud" in keys, sw["Aloud"]),
                   ("vertical", any(p.get("key") == "alt" and p.get("kind") == "vertical"
                                    for p in plist), sw["Vert"]))
               if has != tex_has]
        if bool(d.get("words")) != ("aloud" in keys) or \
                ("aloud" in keys and keys[:2] != ["vocal", "aloud"]):
            fault(code, "words is %r and the passes are %s: a language whose chunks carry "
                        "words has the reading alone as its second pass, and no other "
                        "language has it" % (bool(d.get("words")), "/".join(map(str, keys))))
        elif off:
            fault(code, "the passes are %s but lib/lang/%s.tex switches %s the other way: "
                        "the PDF and the reader would not give the same passes"
                        % ("/".join(map(str, keys)), code, ", ".join(off)))
        else:
            good("passes %s: the registry and the .tex agree" % "/".join(map(str, keys)))
        # THE LEVELS' NAMES, what each pass's button says on a page.  A row
        # without them is refused by lib/languages.py -- Parseh's own at import,
        # a person's when it is loaded -- so here it is a fault.  The exception
        # is a person's row written before names existed: Parseh names its
        # passes as it reads it (languages._with_level_names), so that is a
        # note, with the names it will be read with
        if code in mine and languages.unnamed_passes(plist):
            note(code, "its passes have no names (the row was written before they had "
                       "any): Parseh reads them as %s; put a \"name\" in each pass in "
                       "config/languages.json to choose your own"
                       % ", ".join(repr(languages.default_level_name(d, p)) for p in plist))
        else:
            why = languages.level_name_problems(plist)
            for w in why:
                fault(code, "level names: " + w)
            if plist and not why:
                good("level names %s" % " / ".join(p["name"].strip() for p in plist))
        # the three directories
        missing = [p for p in content_dirs(folder or "") if not os.path.isdir(p)]
        if not missing:
            good("books/%s/, youtube/videos/%s/, library/%s/" % (folder, folder, folder))
        else:
            note(code, "no " + ", ".join(os.path.relpath(p, ROOT) + "/" for p in missing)
                 + "  (mkdir -p, or the first item makes it)")
        # the babel locale the .tex will import.  A row can name one babel
        # has no data for -- its own .ini is not shipped, or the row borrows
        # another language's on purpose -- and the failure is the worst kind:
        # nothing here notices, and lualatex says "Unknown language" over a
        # book, days later.  A note and not a fault, for the reason the font
        # check gives: the registry may be written on one machine for
        # another, and a TeX install missing a locale is that machine's
        # business.
        imp = (d.get("tex") or {}).get("import")
        if imp:
            state = has_babel(imp)
            if state is True:
                good("babel imports %r, which is installed" % imp)
            elif state is False:
                note(code, "tex.import is %r and babel has no such locale on this "
                           "machine: a book would die in lualatex with 'Unknown "
                           "language'" % imp)
            else:
                note(code, "cannot tell whether babel has %r (no kpsewhich)" % imp)
        # the fonts
        for label, name in (("tex.main", (d.get("tex") or {}).get("main")),
                            ("tex.alt", (d.get("tex") or {}).get("alt"))):
            if not name:
                continue
            state = has_font(name)
            if state is True:
                good("%s %r is installed" % (label, name))
            elif state is False:
                fallbacks = [f for f in ((d.get("tex") or {}).get("main_fallbacks") or [])
                             if has_font(f)] if label == "tex.main" else []
                note(code, "%s %r is not on this machine%s"
                     % (label, name, (" (fallback: %s)" % fallbacks[0]) if fallbacks else
                        " and no fallback is either"))
            else:
                note(code, "cannot tell whether %r is installed (no fc-list)" % name)
        for wf in ((d.get("fonts") or {}).get("web_files") or []):
            if os.path.isfile(os.path.join(FONT_DIR, wf)):
                good("lib/fonts/%s" % wf)
            else:
                fault(code, "fonts.web_files names lib/fonts/%s, which is not there" % wf)
        # the Anki ids
        clash = False
        for key, val in (d.get("anki") or {}).items():
            if not isinstance(val, int):
                continue
            if val in seen_ids:
                fault(code, "the Anki id %d is already %s" % (val, seen_ids[val]))
                clash = True
            seen_ids[val] = "%s.%s" % (code, key)
        if not clash and (d.get("anki") or {}).get("vocab_model"):
            good("Anki ids %s / %s are this language's alone"
                 % (d["anki"].get("vocab_model"), d["anki"].get("opposites_model")))
        # a language of this machine's on Parseh's own walk of the grid: what
        # an older newlang.py gave every language.  Nothing is wrong today;
        # the day Parseh ships a language on that slot, Anki merges the two.
        # A note and not a fault, and nothing is changed for it: the ids are
        # what this person's cards already carry in Anki, and new ones would
        # part the cards from the note type they were made with.
        vm = (d.get("anki") or {}).get("vocab_model")
        if code in mine and isinstance(vm, int) and \
                0 <= (vm - ANKI_BASE) // ANKI_STEP < PERSONAL_SLOT:
            note(code, "its Anki ids are slot %d of the part of the grid Parseh's own "
                       "languages are given, so a language Parseh ships later may be "
                       "given the same pair" % ((vm - ANKI_BASE) // ANKI_STEP))
        # the script
        ok, detail = check_chars(d.get("chars"))
        (good if ok else (lambda m: fault(code, m)))("chars: " + detail)
        print("")

    # what lib/languages.py could not take in, and why: a row of the person's
    # that Parseh's own now shadows is a note (nothing is broken, and theirs
    # can go); one that cannot be read, or takes a folder that is somebody
    # else's, is a language every page goes without -- a fault
    left = [(c, why) for c, why in problems if not (c in mine and c not in loaded)]
    if left:
        print("  left out of config/languages.json")
    for code, why in left:
        (note if code in own_rows else fault)(code, "%s%s" % ((code + ": ") if code else "",
                                                              why))
    if left:
        print("")
    # _shipped says which of lib/languages.json's rows are Parseh's own, and
    # a name in it with no row behind it is a list that has drifted from the
    # table it describes
    if isinstance(shipped_list, list):
        for code in shipped_list:
            if not isinstance(own_rows.get(code), dict):
                fault(code, "lib/languages.json's _shipped names %r, which has no row "
                            "there" % code)
    else:
        fault("", "lib/languages.json has no _shipped list, so no row of it can be told "
                  "from one somebody added on their own machine")

    if languages.DEFAULT not in langs:
        faults.append((languages.DEFAULT, "the default language is not in the registry"))
        print("  MISSING  the default language %r has no entry" % languages.DEFAULT)
    print("%d language%s: %d fault%s, %d note%s."
          % (len(langs), "" if len(langs) == 1 else "s",
             len(faults), "" if len(faults) == 1 else "s",
             len(notes), "" if len(notes) == 1 else "s"))
    if faults:
        print("\nwhat is missing:")
        for code, msg in faults:
            print("  %s: %s" % (code, msg))
    if not faults and not notes:
        print("nothing is missing.")
    return 1 if (faults or (strict and notes)) else 0


def add(a):
    # a row an older newlang.py (or a hand) left in Parseh's own file goes to
    # config/ first, as it would at the next start: the new row is then
    # written into a registry whose two halves already say whose is whose
    if not a.dry_run:
        for line in languages.migrate(REGISTRY, PERSONAL):
            print(line)
    text, reg = read_registry()
    langs = entries(reg)
    code = a.code.strip().lower()
    a.code = code
    # --- the refusals ------------------------------------------------------
    if not CODE_RE.match(code):
        refuse("%r is not a code: two or three lower-case letters (ko, fa, nap)" % a.code)
    if code in langs:
        refuse("%r is already %s%s.  An existing language is edited by hand, not "
               "scaffolded." % (code, langs[code].get("name", code),
                                " (added on this machine, in config/languages.json)"
                                if code in reg["_mine"] else ""))
    # the person's store has to be readable before anything is added to it:
    # a file that could not be read would be written over, and every language
    # in it lost -- and a row it holds that was left out (a folder somebody
    # else has, say) is still that code's, and is not to be overwritten either
    if not a.shipped:
        try:
            held = languages.read_store(PERSONAL)
        except (OSError, ValueError) as e:
            refuse("config/languages.json cannot be read (%s): mend it or move it aside "
                   "first -- nothing is written over a file of languages that cannot be "
                   "read" % e)
        if code in held:
            refuse("%r is already in config/languages.json, where it was left out: %s"
                   % (code, "; ".join(why for c, why in reg["_problems"] if c == code)
                         or "see newlang.py --check"))
    if not a.name:
        refuse("--name is required: the English name, which becomes the folder, the babel "
               "language, the Anki field and the label on every slider")
    if not a.native:
        refuse("--native is required: the language's own name for itself, which is what "
               "the chips show")
    entry = build_entry(a, reg)
    slot = entry.pop("_slot")
    folder = entry["folder"]
    if not FOLDER_RE.match(folder):
        refuse("%r is not a directory name; give --folder" % folder)
    for other, d in langs.items():
        if d.get("folder") == folder:
            refuse("the folder %r is %s's already; give --folder" % (folder, other))
        if d.get("tag") == entry["tag"]:
            refuse("the Anki tag %r is %s's already; give --tag" % (entry["tag"], other))
    if a.script == "other" and entry["chars"] is None:
        refuse("--script other needs --chars: without a character class the toolbox cannot "
               "find a run of the language, and every run would have to be marked by hand "
               "(which is what --script latin means)")
    ok, detail = check_chars(entry["chars"])
    if not ok:
        refuse("--chars does not compile: " + detail)
    if entry["reading"] and not entry["chars"]:
        refuse("--reading on a script the toolbox cannot detect: a reading is carried "
               "beside the transliteration of a run, and there are no runs without --chars")
    if entry["words"] and entry["word_sep"]:
        refuse("--words on a language written with spaces: its words are divided "
               "already, and a word line (lib/wordline.py) is for a text that does "
               "not show where they end")
    if len(entry["digits"]) != 10:
        refuse("--digits must be exactly ten characters, 0 to 9 in the language's own "
               "figures (got %r)" % entry["digits"])

    # --- the warnings (a font is never a refusal) --------------------------
    warnings = []
    for label, name in (("--font", entry["tex"]["main"]), ("--alt-font", entry["tex"]["alt"])):
        if name and has_font(name) is False:
            warnings.append("%s %r is not on this machine.  Kept: the entry may be for "
                            "another one, and \\FrankPickFont falls through tex.main_fallbacks."
                            % (label, name))
    for wf in entry["fonts"]["web_files"]:
        if not os.path.isfile(os.path.join(FONT_DIR, wf)):
            warnings.append("--web-font %s is not in lib/fonts/ yet: put the .woff2 there "
                            "(and the .ttf beside it, for lualatex) or the pages will fall "
                            "back to a system face." % wf)
    if entry["chars"] is None and a.script != "latin":
        warnings.append("no chars: every run of this language will have to be marked by "
                        "hand in the studio, as Italian's are.")

    # --- write -------------------------------------------------------------
    print("adding %s (%s, %s) to Parseh\n" % (entry["name"], code, entry["native"]))
    # the warnings go first, not last: they are about what the entry says, and
    # a --dry-run that printed the entry and swallowed them would be lying
    if warnings:
        print("warnings (none of them stopped anything):")
        for w in warnings:
            print("  - " + w)
        print("")
    out = add_shipped(insert_entry(text, code, entry), code) if a.shipped else None
    where = "lib/languages.json" if a.shipped else "config/languages.json"
    if a.dry_run:
        print(json.dumps({code: entry}, indent=2, ensure_ascii=False))
        print("\n--dry-run: nothing written (the row would go into %s)." % where)
        return 0
    if a.shipped:
        with open(REGISTRY + ".tmp", "w", encoding="utf-8") as f:
            f.write(out)
        os.replace(REGISTRY + ".tmp", REGISTRY)
        print("  %-20s entry added after %s, and named in _shipped:"
              % (where, [c for c in langs if c not in reg["_mine"]][-1]))
    else:
        held[code] = entry
        languages.write_store(held, PERSONAL)
        if languages.read_store(PERSONAL).get(code) != entry:
            raise SystemExit("newlang: config/languages.json does not read back as written")
        print("  %-20s entry added -- a language of this machine's, which an update "
              "leaves where it is:" % where)
    print("      folder %s/   tag %s   dir %s   script %s   digits %s"
          % (folder, entry["tag"], entry["dir"], entry["script"],
             "the language's own" if entry["digits"] != "0123456789" else "Latin"))
    # a pass is told by the name its button will wear; the digit is the PDF's
    print("      passes: %s" % "; ".join("%s (%s)" % (p["name"], p["title"])
                                         for p in entry["passes"]))
    print("              (each button wears its name; a person renames a level on their own "
          "pages, and this is the default)")
    print("      fonts:  main %s, alt %s, bundled %s"
          % (entry["fonts"]["main"] or "(the body roman)", entry["fonts"]["alt"] or "none",
             ", ".join(entry["fonts"]["web_files"]) or "none"))
    print("      anki:   %d / %d (slot %d), field %s"
          % (entry["anki"]["vocab_model"], entry["anki"]["opposites_model"], slot,
             entry["anki"]["field"]))

    for path, body in ((os.path.join(LANG_TEX, code + ".tex"), render_tex(code, entry)),
                       (os.path.join(LANG_DOCS, code + ".md"), render_doc(code, entry))):
        _, how = write_file(path, body, a.force)
        print("  %-20s %s" % (os.path.relpath(path, ROOT), how))
    if entry.get("like"):
        src = os.path.join(LANG_TEX, entry["like"] + ".chunk.json")
        dst = os.path.join(LANG_TEX, code + ".chunk.json")
        if os.path.exists(src) and (a.force or not os.path.exists(dst)):
            with open(src, encoding="utf-8") as f:
                rules = json.load(f)
            rules = dict([("_from", "Copied from lib/lang/%s.chunk.json by newlang.py --like %s: the "
                           "phrase shape of a relative, to be read and changed where %s differs."
                           % (entry["like"], entry["like"], entry["name"]))] + list(rules.items()))
            with open(dst, "w", encoding="utf-8") as f:
                f.write(json.dumps(rules, ensure_ascii=False, indent=2) + "\n")
            print("  %-20s copied from %s's, to review" % (os.path.relpath(dst, ROOT), entry["like"]))
    for d in content_dirs(folder):
        keep = os.path.join(d, ".gitkeep")
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(keep):
            with open(keep, "w", encoding="utf-8") as f:
                f.write(GITKEEP)
        print("  %-20s %s" % (os.path.relpath(d, ROOT) + "/", "made, with .gitkeep"))


    times = {1: "once", 2: "twice", 3: "three times", 4: "four times",
             5: "five times"}.get(len(entry["passes"]), "%d times" % len(entry["passes"]))
    todo_note = ("\n     The TODO blocks in it are the pieces that must be copied from\n"
                 "     lib/lang/ja.tex and zh.tex (the ruby, the vertical pass); they are not\n"
                 "     optional -- the book will not build without them, which is right."
                 if (entry["reading"] or entry["vertical"] or entry["words"]) else "")
    print("\nStill yours to write -- the scaffold filled the shape, not the prose:\n")
    print("  1. lib/lang/%s.tex  -- \\FrankHowTo, the \"How to read this\" page: a passage"
          % code)
    print("     comes %s (%s), and the reader is told why."
          % (times, "; ".join(p["title"] for p in entry["passes"])))
    print("     lib/lang/fa.tex is the voice.%s" % todo_note)
    print("  2. docs/lang/%s.md  -- the seven sections, the last a worked Example.  They"
          % code)
    print("     are read by the video prompt (youtube/docs/chat-prompt.md), the new-book")
    print("     prompt (docs/new-book-prompt.md) and the prompt that has an LLM gloss a")
    print("     stretch of a book or a video (docs/region-prompt.md, through")
    print("     lib/glossregion.py), each of which takes what it needs of them")
    print("     (lib/promptkit.py cuts them): they are instructions to an annotator, so")
    print("     write them so.  Every sound they show is written twice, for the usual")
    print("     scheme and for IPA, as docs/lang/fa.md does; a language with short vowels")
    print("     to mark (a `strip` in its row) writes its marks paragraphs twice as well.")
    print("     Its verb paragraph starts from the row: a \\vb gives %s, then"
          % ", ".join(entry["vb_forms"]))
    print("     the meaning, and prints %s / %s before the second and third (vb_forms,"
          % tuple(entry["vb_labels"]))
    print("     vb_labels) -- if that is not this language's verb, change the row, the")
    print("     .tex and the docs together.")
    print("  3. A fixture, if the smoke test is to cover %s: tests/fixtures/books/%s/,"
          % (entry["name"], folder))
    print("     tests/fixtures/videos/%s/, a card in tests/fixtures/anki/." % folder)
    print("  4. markdown/exlex/starters/%s.md -- the document the"
          % code)
    print("     studio's +New button opens on for this language: a guided tour, in")
    print("     English, of everything a document can hold, with every example in")
    print("     %s and one exercise of every kind, written like the ones already" % entry["name"])
    print("     there (it.md is the model for a Latin script, hi.md for a script of")
    print("     its own, ar.md for one written right to left).  Until it exists the")
    print("     studio builds a short generic one from the row, so nothing is broken")
    print("     meanwhile.")
    # THE VERB RECIPE IS NOT SCAFFOLDED, AND THIS LIST IS WHERE THAT IS SAID.
    # Which forms a \vb gives is the language's grammar -- Persian's two
    # stems, Arabic's masdar, a Chinese verb's split -- and a template would
    # write a wrong one with confidence, so none is written: without
    # lib/verbs/<code>.py nothing breaks, the language's verbs are simply
    # offered in the gloss editor's sources as \dw (verbs.recipe_for finds no
    # file), as every language's were before the recipes.  But this list
    # used to end at item 4 with no word of it, and every one of the eleven
    # languages here has a recipe (454-981 lines, lib/verbs/zh.py to en.py),
    # so a new language's author learnt only from docs/languages.md section
    # 10 why their verbs alone never came as \vb.  vb_video_bare is here for
    # the same reason: it has no flag, and it only means anything for a
    # language with marks to strip (lib/verbs takes `strip` off a video's
    # forms), so it is said only to one.
    print("  5. lib/verbs/%s.py -- the verb recipe: recipe(ctx), which reads a"
          % code)
    print("     dictionary hit's rows and returns the three forms above.  Without it")
    print("     nothing breaks, but every verb the dictionary finds is offered in")
    print("     the gloss editor's sources as \\dw, never \\vb.  Beside it, if the")
    print("     language needs one, lib/lang/%s.verbs.json: a hand table the recipe"
          % code)
    print("     reads with ctx.data().  The API is lib/verbs/__init__.py and")
    print("     docs/languages.md section 12; try it with")
    print("         python3 lib/verbs/__init__.py %s \"<a sentence>\"" % code)
    print("     and pin it with cases in tests/fixtures/verbs/%s.json." % code)
    if entry["strip"]:
        print("     If %s videos are written without the marks its dictionary keeps"
              % entry["name"])
        print("     (Arabic's are unvowelled), set \"vb_video_bare\": true in its row of")
        print("     %s by hand -- there is no flag for it -- and a" % where)
        print("     video's verb line drops them.")
    print("\nThe prose of 1, 2 and 4 -- and the examples, the lookup rules and the chunking rules --")
    print("can be drafted by a chatbot: Settings -> Languages gives a prompt for each piece, with")
    print("%s's file as the model, and takes the answer back in; on the command line," % (
        languages.LANGS.get(entry.get("like")).name if entry.get("like") and languages.LANGS.get(entry.get("like"))
        else "a related language"))
    print("    python3 lib/langprompts.py %s conventions          (then --answer FILE)" % code)
    print("\nThen:  python3 lib/newlang.py --features %s   (what it has, feature by feature)" % code)
    print("       python3 lib/newlang.py --check     (every language, its files and fonts)")
    print("       python3 tests/smoke.py             (the regression run)")
    print("The whole process is the guide's page \"Adding a language\".")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="newlang", add_help=True,
        description="Add a language to Parseh: the registry entry, its two files "
                    "and its three directories.  With no arguments, says what it "
                    "needs and lists the languages there are.")
    p.add_argument("code", nargs="?", help="the language code: two or three letters (ko)")
    p.add_argument("--check", action="store_true",
                   help="validate every registry entry and the files it needs")
    p.add_argument("--strict", action="store_true",
                   help="with --check: count the notes (missing directories, absent "
                        "fonts) as faults too")
    p.add_argument("--name", help="the English name (Korean): the folder, the babel "
                                  "language, the Anki field, every label")
    p.add_argument("--native", help="the language's own name for itself")
    p.add_argument("--iso3", help="the ISO 639-3 code (pes, jpn, deu): what "
                                  "outside sources key their files by. Without "
                                  "it the language has no parallel corpus.")
    p.add_argument("--folder", help="the content directory (default: the English name, "
                                    "lower case)")
    p.add_argument("--tag", help="the Anki tag stem (default: the folder)")
    p.add_argument("--dir", choices=("rtl", "ltr"), help="direction (default: the script's)")
    p.add_argument("--script", choices=tuple(SCRIPTS), default="latin",
                   help="the script kind, which picks chars, word_sep, digits and strip "
                        "(default: latin)")
    p.add_argument("--chars", help="the script's character ranges, as a regex class body")
    p.add_argument("--word-sep", dest="word_sep",
                   help="what separates words ('' for a language written without spaces)")
    p.add_argument("--digits", help="the ten digits in the language's own figures")
    p.add_argument("--strip", help="the ranges the bare pass drops (the harakat, say); "
                                   "'' for none")
    p.add_argument("--reading", action="store_true",
                   help="the language has a reading beside the transliteration (kana)")
    p.add_argument("--reading-label", dest="reading_label",
                   help="what that reading is called (kana)")
    p.add_argument("--vertical", action="store_true",
                   help="it can be set in columns, top to bottom (tategaki)")
    p.add_argument("--words", action="store_true",
                   help="its chunks carry a word line, each word with its own reading "
                        "(Japanese, Chinese): the reading over each word in pass 1, and "
                        "the reading alone as pass 2")
    p.add_argument("--font", help="the main face, for lualatex and the CSS stack")
    p.add_argument("--font-fallback", dest="font_fallback", action="append",
                   help="a face to try when the main one is not installed (repeatable)")
    p.add_argument("--alt-font", dest="alt_font",
                   help="an alternate face (nastaliq, gothic): the title, the chapter "
                        "numbers, and a fourth pass unless --vertical")
    p.add_argument("--alt-key", dest="alt_key",
                   help="what a studio block calls that face (font=nastaliq)")
    p.add_argument("--alt-line-height", dest="alt_line_height", type=float,
                   help="the leading the alternate face wants on the web (2.6 for nastaliq)")
    p.add_argument("--web-font", dest="web_font", action="append",
                   help="a face bundled in lib/fonts/ (repeatable): the .woff2 file name")
    p.add_argument("--css-font", dest="css_font", help="the whole CSS stack, if the "
                                                       "derived one is not right")
    p.add_argument("--babel", help="babel's name for the language (default: the English name)")
    p.add_argument("--import", dest="babel_import", metavar="LOCALE",
                   help="the babel locale to import its data from (default: the "
                        "code). A language babel ships no .ini for takes one from "
                        "another language in the same script (sa-Deva for a "
                        "Devanagari one)")
    p.add_argument("--tex-language", dest="tex_language",
                   help="fontspec's Language= tag (Parsi, Japanese)")
    p.add_argument("--hyphen", help="the hyphenation pattern name, for a Latin script")
    p.add_argument("--translit-label", dest="translit_label",
                   help="what the transliteration line is called (rōmaji, pronunciation)")
    p.add_argument("--vocal-label", dest="vocal_label",
                   help="the one-line title of pass 1 (the row's vocal_label); its NAME, "
                        "the word its button wears, is derived: Sentence, With vowels, "
                        "or the reading's own name (Pinyin)")
    p.add_argument("--bare-label", dest="bare_label",
                   help="the one-line title of the bare pass (the row's bare_label); its "
                        "name is Plain")
    p.add_argument("--vb-labels", dest="vb_labels",
                   help="comma-separated: the two labels a \\vb gloss prints before its "
                        "second and third forms (impf.,masdar -- default pres.,past)")
    p.add_argument("--vb-forms", dest="vb_forms",
                   help="comma-separated: what the three forms of a \\vb are, in the "
                        "order it prints them (perfect,imperfect,masdar -- default "
                        "dictionary form,second form,third form)")
    p.add_argument("--require-tr", dest="require_tr", action="store_true", default=None,
                   help="a transliteration is required on every chunk")
    p.add_argument("--no-require-tr", dest="require_tr", action="store_false",
                   help="a transliteration is optional (a Latin script)")
    p.add_argument("--anki-field", dest="anki_field",
                   help="the first field of the note types (default: the English name)")
    p.add_argument("--duration-units", dest="duration_units",
                   help="comma-separated: the words for second, minute, hour, as the "
                        "transcripts write them")
    p.add_argument("--chapter-words", dest="chapter_words",
                   help="comma-separated: the words a chapter heading uses")
    p.add_argument("--like", metavar="CODE",
                   help="a related language (es for Catalan): lends its verb entry's shape and "
                        "compounds, copies its chunking rules to review, and is the model the "
                        "prompts for the prose show (lib/langprompts.py)")
    p.add_argument("--features", action="store_true",
                   help="what each language has, feature by feature (all, or the code given)")
    p.add_argument("--force", action="store_true", help="overwrite files that are there")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="print the entry that would be added and write nothing")
    p.add_argument("--shipped", action="store_true",
                   help="a language added to Parseh itself, for everybody: the entry goes "
                        "into lib/languages.json and its _shipped, not into this "
                        "machine's config/languages.json")
    p.add_argument("--migrate", action="store_true",
                   help="move the rows of lib/languages.json that _shipped does not name "
                        "to config/languages.json (Parseh does it as it starts, except in "
                        "a git checkout)")
    a = p.parse_args(argv)

    if a.migrate:
        said = languages.migrate(REGISTRY, PERSONAL, force=True)
        print("\n".join(said) if said else
              "nothing to move: every row of lib/languages.json is named in its _shipped")
        return 1 if any(s.startswith("!!") for s in said) else 0
    if a.check:
        return check(a.strict)
    if a.features:
        import langfeatures
        if a.code and not languages.LANGS.get(a.code):
            refuse("%r is not a language of this Parseh" % a.code)
        print(langfeatures.render([a.code] if a.code else None))
        return 0
    if not a.code:
        return show()
    return add(a)


if __name__ == "__main__":
    sys.exit(main())
