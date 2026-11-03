#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The languages Parseh teaches -- one registry, read everywhere.

    from languages import get, LANGS, DEFAULT, by_folder, detect_from_path
    L = get("ja")
    L.name, L.native, L.folder, L.dir, L.rtl        # Japanese, 日本語, japanese, ltr, False
    L.has_script("漢字")                             # True: a run of the target script
    L.run_re                                        # compiled: maximal runs of the target script
    L.strip("دَر")                                  # marks off (harakat for fa/ar; identity for ja/it)
    L.to_latin_digits("۳.۱۲") / L.to_native_digits("3.12")
    L.reading                                       # True when the language has a kana-like reading
    L.passes                                        # the reading editions' passes, in order: each has a key,
                                                    # a name (what its button says), a label (its digit, the
                                                    # PDF's) and a title (one line saying what it shows)
    L.vb_labels                                     # the two labels a \vb gloss prints
    L.vb_forms                                      # what its three forms are, in words
    L.vb_video_bare                                 # a video's \vb line without the marks (ar)
    L.as_json()                                     # what a page embeds for its script

    from languages import gloss, GLOSS_CODES, DEFAULT_GLOSS
    G = gloss("it")                                 # what the glosses are WRITTEN in
    G.name, G.dir, G.babel, G.taught                # Italian, ltr, italian, True

The table itself is lib/languages.json, beside this file: names, folders,
scripts, digits, fonts, TeX names, passes, Anki note-type ids.  Nothing else
in the toolbox holds a list of languages; adding one means adding an entry
there (docs/languages.md says what each field does and what else a new
language needs).

    L.mine                                          # True for a language added on this machine
    PERSONAL                                        # config/languages.json: where those live
    migrate()                                       # a hand-added row of lib/ moved there, once

The table has a second half, config/languages.json, for the languages a
person adds on their own machine (lib/newlang.py writes it): lib/languages.json
is Parseh's own and an update replaces it, so a row written into it would
vanish with the next version.  Both are read here, Parseh's first, and to
every tool the two are one registry.

The target-language text is stored under the key `fa` in every data format
(video chunks, Anki cards, the .tex chunks read by texparse) -- the name is
from the days the toolbox knew Persian alone, and it is kept because every
tool and every stored file uses it.  Read it as "the foreign text".  Its
opposite number, the meaning, is stored under `en` for the same historical
reason and is read as "the gloss": which language the gloss is actually
WRITTEN in is `gloss()` below, and it is a per-book, per-video choice.

Standard library only: this is imported by the server, which has nothing
else.
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
REGISTRY = os.path.join(HERE, "languages.json")
DEFAULT = "fa"          # the toolbox's first language: what undeclared content is

# THE LANGUAGES A PERSON ADDS LIVE BESIDE THE SOFTWARE, NOT INSIDE IT.
# lib/languages.json ships with Parseh, and updating Parseh replaces every
# file a release carries -- so a row lib/newlang.py once spliced into it was
# a row the next update took away, while the lib/lang/<code>.tex and
# docs/lang/<code>.md written beside it stayed behind, orphaned.  A person's
# languages are that person's, like their preferences and their network
# settings, and they are kept where those are: config/, which no release
# carries and no update touches.
#
# Found the way lib/prefs.py finds config/ -- from this file's path as it was
# imported, not as symlinks resolve it -- so a test tree that links lib/ in
# from a checkout still reads the config/ of its own tree and not the
# owner's.  (REGISTRY above resolves symlinks, as it always has: Parseh's own
# table is the same file whichever tree imports it.)
PERSONAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config", "languages.json")
# What config/languages.json says it is.  Bumped only when a reader of /1
# would read a newer store wrongly; lib/version.formats() reports it, so an
# update to a Parseh that reads an older shape is told so before it runs.
STORE_FORMAT = "parseh-languages/1"
STORE_COMMENT = ("The languages added on this machine (lib/newlang.py writes "
                 "them), in the shape of lib/languages.json's rows. Parseh's "
                 "own table is read first and wins for a code both hold; an "
                 "update never touches this file.")


# THE LEVELS' NAMES (a0.5.0).  A reading edition sets the same passage in
# several passes, and to the person reading it each is a LEVEL: a button that
# says what it shows.  The button says it in a NAME -- "With vowels", "Chunks",
# "Plain" -- and never in a digit, which meant one thing in Persian and another
# in Chinese (docs/languages.md, "A pass label is an identity") and is not
# printed on a page any more.  `label`, the digit, stays for what still counts
# the passes (the PDF's front matter, the checkers); `title` is one line saying
# what the level shows, printed beside the name.  THE NAME HERE IS THE DEFAULT:
# a person renames a level on their own pages (the prefs key
# bk_lvl:<language>:<pass key>, lib/prefs.py), and this is what comes back when
# they empty the field.
LEVEL_NAME_MAX = 12     # what a button holds; lib/prefs.py refuses a longer rename too


def _reading_word(d):
    """What the language calls its reading, capitalised, for the names of the
    levels that show it ("Furigana", "Pinyin") -- or "Reading" where its own
    word is too long for a button ("Transliteration" is fifteen characters)."""
    sound = ((d.get("reading_label") or "reading") if d.get("reading")
             else (d.get("translit_label") or "reading")).strip() or "reading"
    word = sound[:1].upper() + sound[1:]
    return word if len(word) <= LEVEL_NAME_MAX else "Reading"


def default_level_name(d, p):
    """The name a pass of the row `d` is given where nobody has chosen one --
    the one rule lib/newlang.py writes a new language's names by, and the one
    a row from before the names existed is read by (_with_level_names).

    By the pass's KEY, as everything about a pass is: vocal is the sentence
    itself, with what helps (the reading over each word where the chunks carry
    words or the language has a reading -- named as the row's `vocal_label`
    names it where that says "with <reading>", as Japanese's "with furigana"
    does -- the vowels where marks come off in a script that writes them as
    marks, otherwise nothing); aloud is that reading alone; chunks, bare and the
    alternate face are what they are.  Every name the registry ships is what
    this gives (tests/test_level_names.py holds the two together)."""
    key = (p or {}).get("key")
    word = _reading_word(d)
    if key == "vocal":
        if d.get("words") or d.get("reading"):
            said = (d.get("vocal_label") or "").strip()
            if said.lower().startswith("with "):
                own = said[5:].strip()
                own = own[:1].upper() + own[1:]
                if 0 < len(own) <= LEVEL_NAME_MAX:
                    return own
            return word
        if d.get("strip"):
            return "With vowels" if d.get("script") == "arabic" else "With marks"
        return "Sentence"
    if key == "aloud":
        only = word + " only"
        return only if len(only) <= LEVEL_NAME_MAX else "Reading only"
    if key == "chunks":
        return "Chunks"
    if key == "bare":
        return "Plain"
    if key == "alt":
        if (p or {}).get("kind") == "vertical":
            return "Vertical"
        face = ((d.get("fonts") or {}).get("alt_key") or "").strip()
        if face.isalpha() and face.lower() != "alt" and len(face) <= LEVEL_NAME_MAX:
            return face.capitalize()
        return "Other font"
    return (str(key or "").strip().capitalize() or "Level")[:LEVEL_NAME_MAX]


def unnamed_passes(passes):
    """True when NO pass of this list has a `name` at all: the shape of a row
    written before the levels had names, which is not the same fault as a row
    that names some and not others, or names one badly."""
    return bool(passes) and all(isinstance(p, dict) and "name" not in p for p in passes)


def level_name_problems(passes):
    """What is wrong with the names of a row's passes -> [str], empty when all
    is well.  Every pass needs one: 1 to LEVEL_NAME_MAX characters, on one line,
    and no two of a language's passes may share one -- a button shows nothing
    but its name, so two the same would be two buttons nobody can tell apart."""
    out, seen = [], {}
    for p in passes or []:
        if not isinstance(p, dict):
            out.append("a pass is %s, not a table" % type(p).__name__)
            continue
        key, name = p.get("key"), p.get("name")
        if not isinstance(name, str) or not name.strip():
            out.append("pass %r has no \"name\": the word its button wears, 1 to %d "
                       "characters" % (key, LEVEL_NAME_MAX))
            continue
        name = name.strip()
        if len(name) > LEVEL_NAME_MAX:
            out.append("pass %r is named %r, which is %d characters: %d is the most a "
                       "button holds" % (key, name, len(name), LEVEL_NAME_MAX))
        elif any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in name):
            out.append("pass %r has a name that is not one plain line" % (key,))
        elif name.casefold() in seen:
            out.append("passes %r and %r are both named %r: a button shows nothing but "
                       "its name" % (seen[name.casefold()], key, name))
        else:
            seen[name.casefold()] = key
    return out


def _with_level_names(d):
    """A person's row written before the levels had names, read as the same row
    with the default ones -- so that updating Parseh does not take away a
    language somebody added on their own machine, which an older newlang.py
    wrote without them and which no update may rewrite (config/ is theirs).
    Only a row that has none AT ALL is mended: one that names some passes and
    not others, or names one badly, is a row that is wrong, and is left to be
    refused like any other."""
    passes = d.get("passes")
    if not unnamed_passes(passes):
        return d
    return dict(d, passes=[dict(p, name=default_level_name(d, p)) for p in passes])


class Lang:
    # True for a language this machine's person added (config/languages.json,
    # or a row of lib/languages.json that Parseh does not ship): set by
    # _load, so a Lang built by hand is Parseh's own
    mine = False

    def __init__(self, code, d):
        self.code = code
        self.name = d["name"]
        self.native = d.get("native") or d["name"]
        # ISO 639-3, because the corpora are keyed by it and Parseh is
        # keyed by 639-1.  For Persian the two differ by more than
        # length: `pes` is Western Persian and `fas` the macrolanguage,
        # and only the first has an export to download.
        self.iso3 = d.get("iso3") or ""
        self.folder = d["folder"]
        self.tag = d.get("tag") or d["folder"]
        self.dir = d.get("dir", "ltr")
        self.script = d.get("script", "latin")
        self.chars = d.get("chars")                 # regex ranges, or None (Latin script)
        # WHAT THE READING IS WRITTEN IN, where the language has one at all.
        # `chars` is the whole script -- for Japanese that is kana AND kanji
        # -- so it cannot tell a reading from the text it is the reading OF.
        # にほんご is a reading of 日本語 and 日本語 is not.
        self.reading_chars = d.get("reading_chars")
        self.word_sep = d.get("word_sep", " ")
        self.digits = d.get("digits") or "0123456789"
        self.strip_range = d.get("strip")           # regex ranges of marks the bare pass drops
        self.reading = bool(d.get("reading"))
        self.vertical = bool(d.get("vertical"))
        # WHETHER A CHUNK IS DIVIDED INTO WORDS, each with its own reading
        # (lib/wordline.py): kana over a Japanese word, pinyin over a Chinese
        # one.  A language that writes spaces has its words already.
        self.words = bool(d.get("words"))
        self.require_tr = bool(d.get("require_tr", True))
        self.translit_label = d.get("translit_label") or "transliteration"
        # WHAT THE PROMPTS' IPA SETTING MAKES OF THIS LANGUAGE (lib/promptkit.py OPTIONS): "offered"
        # (a row that says nothing: a person may ask for IPA in place of the usual scheme), "usual"
        # (the usual scheme already IS IPA: English) or "none" (the setting is not offered: Chinese,
        # whose word line is written in pinyin, which no converter turns into IPA yet)
        self.ipa = d.get("ipa") if d.get("ipa") in ("usual", "none") else "offered"
        # which analyzer speaks for the language's morphology and its syntax
        # (lib/analyzer.py), by name: "udpipe", "farahidi", "starlang", "native"
        # (the word line), or nothing -- a language added without the key has none
        an = d.get("analysis") or {}
        self.analysis = {"morphology": an.get("morphology") or None, "syntax": an.get("syntax") or None}
        # one example per kind, in the language itself: what a row of the lookup
        # page would add (dict, corpus, model) and what a gloss button writes
        # (macros: dw, vb, bw, pw).  A language without them is shown without.
        self.examples = dict(d.get("examples") or {})
        # how a compound is glossed: "parts" (the whole with its parts: German,
        # Japanese, Chinese, Arabic) or "verb" (a light verb with the word it
        # carries: the default)
        self.compounds = "parts" if d.get("compounds") == "parts" else "verb"
        # the related language it was started from (newlang.py --like): whose
        # files the prompts for its prose show as the model
        self.like = d.get("like") or None
        # THE VARIETIES A TEXT MAY BE WRITTEN IN, besides the standard one
        # (Arabic's dialects): each {key, name, kaikki: [[extract name,
        # lang_code], ...]}.  A book or a video names one in its `variety`;
        # its lookups then try that variety's dictionary and rules first.
        self.varieties = [dict(v) for v in (d.get("varieties") or []) if isinstance(v, dict) and v.get("key")]
        self.standard_name = d.get("standard_name") or ""
        self.variety = None               # set on the copy with_variety() returns
        self.variety_name = ""
        self.key = code                   # the dictionary's and the rules' file stem: ar, or ar.egy
        self.reading_label = d.get("reading_label")
        self.vocal_label = d.get("vocal_label") or "the sentence"
        self.bare_label = d.get("bare_label")
        # the two words a gloss prints before \vb's second and third forms
        # (fa pres./past, ar impf./masdar, ja stem/-te).  The same pair
        # lib/lang/<code>.tex sets as \FrankVbPres / \FrankVbPast, so the
        # reader and the PDF of one book label the same forms; the Persian
        # labels stand in for an entry written before the field existed.
        self.vb_labels = list(d.get("vb_labels") or ["pres.", "past"])[:2]
        # WHAT THE THREE FORMS ARE, in words -- fa infinitive / present stem /
        # past stem, zh verb / A了B / A不B.  The labels above are what the page
        # prints and are two abbreviations by design; the chunk editor also
        # has to tell whoever types a \vb what goes in each of the seven
        # slots, and it used to build that out of the labels -- "infinitive,
        # pres. stem, past stem" -- which told a Turkish annotator "stem
        # stem, aor. stem" and a Chinese one to give an infinitive Chinese
        # does not have.  Three strings, always: a row written
        # before the field existed reads as the neutral names below rather
        # than as Persian's, which would be a claim about its grammar.
        forms = [str(x) for x in (d.get("vb_forms") or []) if str(x).strip()]
        self.vb_forms = forms[:3] if len(forms) >= 3 else \
            ["dictionary form", "second form", "third form"]
        # A VIDEO'S VERB LINE WITHOUT THE MARKS, where the language's videos
        # are written without them: an Arabic caption is unvowelled and
        # docs/lang/ar.md's video line is `أراد arāda (IV) · impf. يريد
        # yurīdu · …`, while the dictionary's forms, and a book's \vb, carry
        # every haraka.  lib/verbs takes `strip` off the video's forms when
        # this is true; false, the default, leaves them as the book has them.
        self.vb_video_bare = bool(d.get("vb_video_bare", False))
        self.fonts = dict(d.get("fonts") or {})
        self.tex = dict(d.get("tex") or {})
        # EVERY PASS HAS A NAME (see LEVEL_NAME_MAX above): a row without one is
        # refused here -- Parseh's own at import, as any fault of the release is,
        # and a person's by _load, which leaves the language out and says why
        self.passes = [dict(p) for p in d.get("passes") or []]
        bad = level_name_problems(self.passes)
        if bad:
            raise ValueError("%s (%s): %s" % (self.name, code, "; ".join(bad)))
        for p in self.passes:
            p["name"] = p["name"].strip()
        self.anki = dict(d.get("anki") or {})
        self.duration_units = list(d.get("duration_units") or [])
        self.chapter_words = list(d.get("chapter_words") or [])
        self.re_chars = re.compile("[%s]" % self.chars) if self.chars else None
        self.re_reading = (re.compile("^[%s\\s]+$" % self.reading_chars)
                           if self.reading_chars else None)
        if self.chars:
            if self.word_sep:
                self.run_re = re.compile(
                    "[%s]+(?:%s[%s]+)*" % (self.chars, re.escape(self.word_sep), self.chars))
            else:
                self.run_re = re.compile("[%s]+" % self.chars)
        else:
            self.run_re = None
        self._strip_re = re.compile("[%s]" % self.strip_range) if self.strip_range else None
        self._to_latin = str.maketrans(self.digits, "0123456789") \
            if self.digits != "0123456789" else None
        self._to_native = str.maketrans("0123456789", self.digits) \
            if self.digits != "0123456789" else None

    # --- script -----------------------------------------------------------
    @property
    def rtl(self):
        return self.dir == "rtl"

    @property
    def spaced(self):
        """Words are separated by spaces (Persian, Arabic, Italian); Japanese
        has no word separator, so a chunk is one word for every tool."""
        return bool(self.word_sep)

    @property
    def alt_pass(self):
        """The 'alt' pass, when the language has one: nastaliq for Persian,
        vertical for Japanese; None otherwise."""
        for p in self.passes:
            if p.get("key") == "alt":
                return p
        return None

    @property
    def pass_keys(self):
        return [p["key"] for p in self.passes]

    def has_script(self, s):
        """True when the text carries at least one character of the target
        script.  Always False for a Latin-script language: its text cannot
        be told from the prose around it, so it is marked, never detected."""
        return bool(self.re_chars and s and self.re_chars.search(s))

    def is_reading(self, s):
        """Is this written in what this language's READING is written in?

        A language with no reading, or one that has not said what its reading
        looks like, answers False to everything: there is nothing to check
        against, and guessing would refuse good answers.
        """
        return bool(self.re_reading and s and self.re_reading.match(s.strip()))

    def strip(self, s):
        """The bare form: the marks the vowelled pass carries taken off
        (harakat for Persian and Arabic).  Identity for the others."""
        return self._strip_re.sub("", s) if self._strip_re else s

    def to_latin_digits(self, s):
        return s.translate(self._to_latin) if self._to_latin else s

    def to_native_digits(self, s):
        return str(s).translate(self._to_native) if self._to_native else str(s)

    def split_words(self, s):
        """The words of a chunk, for the tools that count or address them.
        Japanese has no separator, so the chunk is its own single word."""
        if not self.spaced:
            return [s] if s else []
        return s.split()

    def css_font(self, alt=False):
        if alt:
            return self.fonts.get("css_alt") or self.fonts.get("css_main") or "serif"
        return self.fonts.get("css_main") or "serif"

    def html_attrs(self):
        return ' lang="%s" dir="%s"' % (self.code, self.dir)

    def as_json(self):
        """The record a page embeds for its script: everything the browser
        may need, the compiled regexes as their source strings."""
        return {"code": self.code, "name": self.name, "native": self.native,
                "folder": self.folder, "tag": self.tag, "dir": self.dir,
                "script": self.script, "chars": self.chars,
                "reading_chars": self.reading_chars,
                "word_sep": self.word_sep, "digits": self.digits,
                "iso3": self.iso3,
                "strip": self.strip_range, "reading": self.reading,
                "vertical": self.vertical, "words": self.words,
                "require_tr": self.require_tr,
                "translit_label": self.translit_label,
                "reading_label": self.reading_label,
                "vocal_label": self.vocal_label, "bare_label": self.bare_label,
                "vb_labels": self.vb_labels, "vb_forms": self.vb_forms,
                "fonts": {"css_main": self.css_font(), "css_alt": self.fonts.get("css_alt"),
                          "alt_key": self.fonts.get("alt_key"),
                          "alt_line_height": self.fonts.get("alt_line_height")},
                "passes": self.passes, "anki": self.anki,
                "examples": self.examples, "compounds": self.compounds,
                "varieties": [{"key": v["key"], "name": v.get("name") or v["key"]} for v in self.varieties],
                "standard_name": self.standard_name}

    def variety_of(self, key):
        """The row of one variety (`egy`), or None."""
        key = (key or "").strip().lower()
        return next((v for v in self.varieties if v["key"] == key), None)

    def with_variety(self, key):
        """This language as written in one of its varieties: the same Lang in
        everything (code, script, folder, every page), but for `key` -- the
        stem of its own dictionary and rules (ar.egy) -- and its name.  The
        language itself for an unknown or empty key."""
        v = self.variety_of(key)
        if v is None:
            return self
        import copy
        V = copy.copy(self)
        V.variety, V.variety_name = v["key"], v.get("name") or v["key"]
        V.key = "%s.%s" % (self.code, v["key"])
        return V

    def __repr__(self):
        return "<Lang %s %s>" % (self.key, self.name)


def read_store(path=None):
    """The rows of config/languages.json -> {code: row}, in its order; {} when
    there is no such file, which is every machine where nobody has added a
    language.  A file that is there and cannot be read raises (OSError,
    ValueError): the caller decides whether that is a note or a refusal,
    and the one that writes must never write over a file it could not read."""
    try:
        with open(path or PERSONAL, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    if not isinstance(doc, dict):
        raise ValueError("it holds %s, not a table of languages" % type(doc).__name__)
    return {k: v for k, v in doc.items() if not k.startswith("_")}


def write_store(rows, path=None):
    """Write config/languages.json: the rows given, in their order, under
    the store's own comment and format stamp.  Whole, through a temporary
    file and a rename, so a crash leaves the old store or the new one and
    never half of either.  The store is Parseh's to write, so it is simply
    dumped -- unlike lib/languages.json, whose hand-set layout newlang.py
    splices round."""
    path = path or PERSONAL
    doc = {"_comment": STORE_COMMENT, "_format": STORE_FORMAT}
    doc.update((k, v) for k, v in rows.items() if not k.startswith("_"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def read_rows(shipped=None, personal=None):
    """Every row of the registry, as data -> (rows, mine, problems).

    `rows` is {code: row} in display order: lib/languages.json's rows as that
    file has them, then config/languages.json's.  `mine` is the set of codes
    that are the person's -- every row of config/, and a row of lib/ that its
    `_shipped` does not name (one an older newlang.py wrote there, or a hand;
    migrate() moves it).  `problems` is [(code, why)]: the person's rows left
    out, each with the reason in words, for newlang.py --check and the
    server's log.

    PARSEH'S OWN ROW WINS A CODE BOTH HOLD.  The day Parseh ships Korean, a
    Korean somebody added for themselves is passed over, not merged: two
    rows for one code would be two answers to every question a tool asks,
    and the one that is kept is the one the release was tested with.  A
    row of the person's that takes a folder somebody already has is left
    out too, because a folder is how a book is found to BE in a language.

    A PERSON'S ROW NEVER STOPS PARSEH.  lib/languages.json is part of the
    release and a fault in it is a fault of the release, so it raises, as
    it always has.  config/languages.json is written on this machine, and
    by hand as often as not: a store that is not JSON, or a row missing a
    field, is left out and said, and every other language goes on working.
    """
    with open(shipped or REGISTRY, encoding="utf-8") as f:
        raw = json.load(f)
    own = raw.get("_shipped")
    # a file with no _shipped is one written before the list existed: every
    # row of it is then taken as Parseh's, which is what it was
    own = set(own) if isinstance(own, list) else None
    rows, mine, problems = {}, set(), []
    for code, d in raw.items():
        if code.startswith("_") or not isinstance(d, dict):
            continue
        rows[code] = d
        if own is not None and code not in own:
            mine.add(code)
    try:
        store = read_store(personal)
    except (OSError, ValueError) as e:
        problems.append(("", "config/languages.json cannot be read (%s): the languages "
                             "added on this machine are left out until it is mended" % e))
        store = {}
    folders = {d.get("folder"): c for c, d in rows.items()}
    for code, d in store.items():
        if not isinstance(d, dict):
            problems.append((code, "its row in config/languages.json is not a table"))
        elif code in rows and code in mine:
            problems.append((code, "lib/languages.json holds a row for it as well, and "
                                   "that one is read; config/languages.json's is not"))
        elif code in rows:
            problems.append((code, "Parseh itself now carries %r (%s), and its row is the "
                                   "one read: yours in config/languages.json is not"
                                   % (code, rows[code].get("name", code))))
        elif d.get("folder") in folders:
            problems.append((code, "its folder %r is %s's already, and one folder cannot "
                                   "hold two languages" % (d.get("folder"),
                                                           folders[d.get("folder")])))
        else:
            rows[code] = d
            mine.add(code)
            folders[d.get("folder")] = code
    return rows, mine, problems


def _load(shipped=None, personal=None):
    """The registry as Lang objects -> ({code: Lang}, problems)."""
    rows, mine, problems = read_rows(shipped, personal)
    out = {}
    for code, d in rows.items():
        if code in mine:
            try:
                L = Lang(code, _with_level_names(d))
            except (KeyError, TypeError, ValueError, AttributeError, re.error) as e:
                problems.append((code, "its row cannot be read (%s: %s), so it is left out"
                                       % (type(e).__name__, e)))
                continue
            L.mine = True
        else:
            L = Lang(code, d)
        out[code] = L
    if DEFAULT not in out:
        raise SystemExit("lib/languages.json has no entry for the default language %r" % DEFAULT)
    return out, problems


# PROBLEMS: [(code, why)] -- the person's rows that could not be taken in
# (read_rows says which and why); empty on nearly every machine
LANGS, PROBLEMS = _load()
CODES = list(LANGS)
FOLDERS = {L.folder: L.code for L in LANGS.values()}


def reload():
    """Read the registry again, in place: every module that holds LANGS, CODES,
    FOLDERS or GLOSSES sees the new table, and lib/langs.css is written again.
    For a language added on this machine from Settings -> Languages, so that it
    is in every page at once; what a module worked out from the table when it
    was imported (an analyzer's language, say) is the next start's."""
    fresh, problems = _load()
    LANGS.clear()
    LANGS.update(fresh)
    PROBLEMS[:] = problems
    CODES[:] = list(LANGS)
    FOLDERS.clear()
    FOLDERS.update({L.folder: L.code for L in LANGS.values()})
    GLOSSES.clear()
    GLOSSES.update(_glosses())
    try:
        write_css()
    except OSError:
        pass
    return LANGS


def get(code, default=None):
    """The language with this code.  Unknown -> the default when one is
    given, else KeyError: a misspelled code must not quietly become
    Persian in a tool that writes files."""
    code = (code or "").strip().lower()
    if code in LANGS:
        return LANGS[code]
    # a variety, by the key its dictionary and rules are filed under (ar.egy)
    base, dot, v = code.partition(".")
    if dot and base in LANGS and LANGS[base].variety_of(v):
        return LANGS[base].with_variety(v)
    if default is not None:
        return LANGS[default] if isinstance(default, str) else default
    raise KeyError("unknown language %r (known: %s)" % (code, ", ".join(CODES)))


def get_or_default(code):
    """The language with this code, or the toolbox's default -- for content
    written before languages were declared, which is all Persian."""
    return get(code, DEFAULT)


def by_folder(folder):
    """The language whose folder this is ("persian" -> fa), or None."""
    code = FOLDERS.get((folder or "").strip().lower())
    return LANGS[code] if code else None


def detect_from_path(path):
    """The language a path sits under: the nearest component that is a
    language folder (books/japanese/<slug>, videos/persian/<id>,
    library/arabic/<id>).  None when no component is one."""
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    for p in reversed(parts):
        L = by_folder(p)
        if L:
            return L
    return None


def mine():
    """The codes of the languages added on this machine, in registry order."""
    return [L.code for L in LANGS.values() if L.mine]


# ------------------------------------------------------- a person's row, moved
# Before config/languages.json existed, lib/newlang.py spliced a new language
# into lib/languages.json itself, and somebody may have added a row there by
# hand since.  Either way the row sits in the one file an update replaces.
# migrate() moves it: every row lib/languages.json holds that its `_shipped`
# does not name is written into config/languages.json and then taken out of
# lib/languages.json, whose own rows come out byte for byte -- so the file is
# again the one the release shipped, and the update that follows has nothing
# of the person's to replace.  serve.py calls it as Parseh starts; a file
# with nothing to move costs one read and writes nothing, which is how it
# happens "once".


def _members(text):
    """The top-level members of a JSON object's text -> [(key, start, end)],
    `start` at the key's opening quote and `end` just past its value, so a
    row can be cut out of the text without re-dumping the rest."""
    dec = json.JSONDecoder()
    ws = re.compile(r"[ \t\r\n]*")
    i = ws.match(text, 0).end()
    if text[i:i + 1] != "{":
        raise ValueError("not a JSON object")
    i += 1
    out = []
    while True:
        i = ws.match(text, i).end()
        if text[i:i + 1] == "}":
            return out
        if text[i:i + 1] != '"':
            raise ValueError("a key was expected at %d" % i)
        start = i
        key, i = json.decoder.scanstring(text, i + 1)
        i = ws.match(text, i).end()
        if text[i:i + 1] != ":":
            raise ValueError("a colon was expected at %d" % i)
        _, i = dec.raw_decode(text, ws.match(text, i + 1).end())
        out.append((key, start, i))
        i = ws.match(text, i).end()
        if text[i:i + 1] == ",":
            i += 1
        elif text[i:i + 1] != "}":
            raise ValueError("a comma or a closing brace was expected at %d" % i)


def _without(text, codes):
    """The registry's text with these rows cut out, everything else as it
    was.  A row goes with the comma and the white space that lead up to it
    -- the exact inverse of newlang.insert_entry, which adds ",\\n" and the
    row before the closing brace -- or, first in the table, with what
    follows it up to the next key."""
    members = _members(text)
    for n in range(len(members) - 1, -1, -1):
        key, start, end = members[n]
        if key not in codes:
            continue
        if n > 0:
            text = text[:members[n - 1][2]] + text[end:]
        elif len(members) > 1:
            text = text[:start] + text[members[1][1]:]
        else:
            text = text[:start] + text[end:]
        members = _members(text)
    return text


def migrate(shipped=None, personal=None, force=False):
    """Move the rows of lib/languages.json that Parseh does not ship into
    config/languages.json -> the lines saying what was done ([] when
    nothing was).

    NOT IN A GIT CHECKOUT, unless forced (newlang.py --migrate).  There the
    tree is somebody's working copy of Parseh itself: a row in
    lib/languages.json that `_shipped` does not name is a language being
    added to Parseh by hand, and moving it out from under its author at the
    next start would be the tool deciding what the change is.  A release
    install has no .git (the updater refuses one that has), and that is
    where a row can be lost to an update.

    A row config/ already holds, the same, is only taken out of lib/; one it
    holds DIFFERENTLY is left in both and said -- which of two hand edits is
    the right one is not a thing to guess."""
    shipped = shipped or REGISTRY
    personal = personal or PERSONAL
    root = os.path.dirname(os.path.dirname(os.path.abspath(shipped)))
    if not force and os.path.exists(os.path.join(root, ".git")):
        return []
    with open(shipped, encoding="utf-8") as f:
        text = f.read()
    raw = json.loads(text)
    own = raw.get("_shipped")
    if not isinstance(own, list):
        return []                     # which rows are Parseh's cannot be told
    extra = [c for c, d in raw.items()
             if not c.startswith("_") and isinstance(d, dict) and c not in own]
    if not extra:
        return []
    try:
        store = read_store(personal)
    except (OSError, ValueError) as e:
        return ["!! languages: %s is Parseh's own file and holds %s, which Parseh does "
                "not ship; they were not moved, because config/languages.json cannot "
                "be read (%s)" % (shipped, ", ".join(extra), e)]
    said, move, added = [], [], False
    for code in extra:
        if code not in store:
            store[code] = raw[code]
            move.append(code)
            added = True
        elif store[code] == raw[code]:
            move.append(code)
        else:
            said.append("!! languages: %s (%s) is in lib/languages.json and in "
                        "config/languages.json, and the two rows differ: both are left as "
                        "they are, and lib/'s is the one read" % (code, raw[code].get("name")))
    if added:
        write_store(store, personal)
        back = read_store(personal)
        if any(back.get(c) != raw[c] for c in move):
            return said + ["!! languages: config/languages.json did not read back as "
                           "written; lib/languages.json was left as it is"]
    if move:
        out = _without(text, set(move))
        want = [(k, v) for k, v in raw.items() if k not in move]
        if list(json.loads(out).items()) != want:
            return said + ["!! languages: %s could not be taken out of lib/languages.json "
                           "cleanly; it is in config/languages.json as well now, and "
                           "lib/'s row is the one read" % ", ".join(move)]
        tmp = shipped + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(out)
        os.replace(tmp, shipped)
        for code in move:
            said.append("languages: %s (%s) moved from lib/languages.json to "
                        "config/languages.json, where a language added on this machine "
                        "is kept and an update cannot take it away"
                        % (code, raw[code].get("name", code)))
    return said


# ------------------------------------------------------------------ the gloss
# A book or a video declares TWO languages: the one it TEACHES (`language`, a
# registry code) and the one its glosses are WRITTEN IN (`gloss`).  They are
# different questions -- an Italian learning English wants the meanings in
# Italian -- and the studio has asked them apart since it had a front matter
# (`target:` and `lang:`, docs/languages.md section 5).  This is that same
# answer, for the two doors that used to assume English.
#
# ABSENT MEANS ENGLISH.  Everything written before the field existed is
# glossed in English and says nothing, so no file has to be migrated and
# nothing that is in the toolbox today changes meaning.
DEFAULT_GLOSS = "en"

# A gloss language is PROSE, not a subject: somebody may gloss Persian in
# Spanish, and nobody studies Spanish here.  So what may be written in is the
# registry's languages PLUS the prose-only codes below -- the same set the
# studio accepts for `lang:`, because it is the same question at the other
# door and one document must not be sayable there and unsayable here.
#
# WHY THE TABLE IS HERE AND NOT READ OUT OF THE STUDIO'S COPY.  The studio's
# is `texgen._HYPHEN_PROSE`, and it answers the other half of the question --
# what TeX calls the patterns, and how few letters may be left on a line.
# Two things stop lib/ reading it.  It sits inside the studio, and importing
# it pulls the whole studio in behind it (the reason draft.slugify is written
# out a third time), and lib/ is what the server imports, so it may depend on
# nothing but the standard library and itself.
# And the dependency already runs the other way: texgen.py imports THIS file,
# and for a code the registry teaches its table holds None and takes the name
# from `tex.hyphen` -- so this is the end both doors can already reach, and
# the same deferral covers the codes when somebody comes to write it.
#
# A prose language cannot be a registry entry instead.  An entry there is a
# language somebody STUDIES: a folder under books/, a script, digits, fonts,
# passes, Anki note types, lib/lang/<code>.tex and docs/lang/<code>.md, every
# one of them checked by `newlang.py --check`.  Spanish has none of that and
# needs none -- it is a language the toolbox WRITES IN, not one it teaches --
# and inventing the rest of an entry to hold two strings would put a books/
# directory and a pair of Anki model ids in the way of a gloss.  Nothing here
# is a second list of the languages taught, either: a language the registry
# holds is not repeated below, and where a gloss code is one of them the
# registry names it, gives its direction and says what babel calls it.
# `_glosses()` takes the registry first and only then these, so a row here
# for a language that has since been TAUGHT is dead weight that says the
# opposite of this paragraph -- Spanish sat here until it became a language
# of its own, and was removed the day it did.
#
# Every row is left to right, and lib/frank-preamble.tex says so out loud:
# a gloss code the registry does not carry is taken there as Latin-script and
# LTR, because guessing otherwise would set a page backwards without a word.
# An RTL prose language added here is that file's business as well as this
# one's -- which is why the direction is a column and not an assumption.
#
# code -> (name, native name, what babel calls it, direction)
_PROSE = {
    "pt": ("Portuguese", "português", "portuguese", "ltr"),
    "nl": ("Dutch", "Nederlands", "dutch", "ltr"),
    "ro": ("Romanian", "română", "romanian", "ltr"),
    "pl": ("Polish", "polski", "polish", "ltr"),
    "ru": ("Russian", "русский", "russian", "ltr"),
    # the two spellings of English that hyphenate differently: babel's
    # `english` is the American set, so a book glossed for British readers
    # has to be able to say so
    "en-gb": ("British English", "British English", "british", "ltr"),
    "en-us": ("American English", "American English", "USenglish", "ltr"),
}

# The ISO 639-2 spellings, resolved to the two-letter code: a writer told to
# give "the ISO code" sometimes gives three letters, and the studio's table
# has taken both for as long as it has existed.
_GLOSS_ALIAS = {"eng": "en", "ita": "it", "fra": "fr", "deu": "de", "spa": "es"}


class Gloss:
    """The language a book's or a video's glosses are written in.

    Deliberately not a `Lang`: a Lang has a folder, a script, digits, fonts
    and note types, and handing one back for Spanish would be a promise this
    toolbox cannot keep.  What a gloss needs is what a page and a preamble
    ask of it -- what to call it, which way it runs, what babel calls it --
    and `lang` when it happens to be a language the toolbox also teaches.
    """

    def __init__(self, code, name, native, babel, direction, lang=None):
        self.code = code
        self.name = name
        self.native = native or name
        self.babel = babel
        self.dir = direction
        self.lang = lang                # the Lang, when the toolbox teaches it too

    @property
    def rtl(self):
        return self.dir == "rtl"

    @property
    def taught(self):
        """True when the gloss language is also one of the eleven: an English
        edition glossed in Persian has a registry record to draw a font from,
        a Spanish one has not (the roman sets it, as it sets every gloss)."""
        return self.lang is not None

    def html_attrs(self):
        return ' lang="%s" dir="%s"' % (self.code, self.dir)

    def as_json(self):
        """What a page embeds beside the target language's record: enough to
        label the gloss row and set a card's lang and dir."""
        return {"code": self.code, "name": self.name, "native": self.native,
                "dir": self.dir, "babel": self.babel, "taught": self.taught}

    def __repr__(self):
        return "<Gloss %s %s>" % (self.code, self.name)


def _glosses():
    """Every code a gloss may be written in: the registry's eleven, each named
    by the registry, then the prose-only ones.  Registry first, so a prose
    row written for a code the registry teaches would be passed over rather
    than allowed to rename it -- there is one name for Italian on screen and
    it is the one the chip row shows."""
    out = {}
    for L in LANGS.values():
        out[L.code] = Gloss(L.code, L.name, L.native,
                            L.tex.get("babel") or L.code, L.dir, L)
    for code, (name, native, babel, direction) in _PROSE.items():
        if code not in out:
            out[code] = Gloss(code, name, native, babel, direction)
    return out


GLOSSES = _glosses()
GLOSS_CODES = list(GLOSSES)


def gloss(code=None):
    """The gloss language of a book or a video: THE function that answers it.

    Nothing said -> English, which is what every book and video written
    before the field existed means (docs/languages.md section 3).  An unknown
    code raises KeyError, exactly as `get` does and for the same reason: a
    tool that WRITES files must not gloss in a guessed language, and a typo
    quietly becoming English is the very thing the field exists to stop.
    Callers that must show the thing anyway ask `gloss_or_default` and report
    the code separately (books.Book.gloss_problem).
    """
    # A value that is not a string at all -- a number or a list in a
    # hand-edited book.json, a JSON body arriving at a route -- is spelled
    # out rather than tripped over: it is an unknown gloss language and a
    # sentence to read, never a traceback out of a request.  That is
    # check_annotations.lang_code's rule, one door earlier and for the same
    # field.
    if code is not None and not isinstance(code, str):
        code = str(code)
    key = (code or "").strip().lower().replace("_", "-")
    if not key:
        return GLOSSES[DEFAULT_GLOSS]
    key = _GLOSS_ALIAS.get(key, key)
    if key in GLOSSES:
        return GLOSSES[key]
    raise KeyError("unknown gloss language %r (a gloss may be written in: %s)"
                   % (code, ", ".join(GLOSS_CODES)))


def gloss_or_default(code):
    """The gloss language, or English when the code is one this toolbox
    cannot set -- for a reader that has to render the book regardless."""
    try:
        return gloss(code)
    except KeyError:
        return GLOSSES[DEFAULT_GLOSS]


_ALL_NATIVE = "".join(L.digits for L in LANGS.values() if L.digits != "0123456789")
_ALL_TO_LATIN = str.maketrans(
    _ALL_NATIVE, "".join("0123456789" for L in LANGS.values() if L.digits != "0123456789"))


def any_to_latin_digits(s):
    """Every language's digits -> Latin, for a tool that reads a label before
    it knows which language wrote it (\\parnum{۳.۱}, \\parnum{٣.١})."""
    return s.translate(_ALL_TO_LATIN)


# ------------------------------------------------------------------ case
# Unicode's locale-blind lower-casing spells the small form of Turkish's
# dotted capital İ (U+0130) as "i" + U+0307 -- two characters nobody types
# and nothing else matches.  Python and every browser do this, so any tool
# that lower-cases target text (a slug, a search key, a sort key) breaks on
# the commonest capital letter in Turkish unless it goes through here.
_LOWER = str.maketrans({"İ": "i"})              # İ -> i, no stray dot
_FOLD = str.maketrans({"İ": "i", "ı": "i", "̇": ""})


def lower(s):
    """str.lower() without the combining dot Unicode leaves behind: the
    lower case of İ is i, and the trailing U+0307 is an artefact of the
    default rule, not a letter anyone writes.  Loses nothing -- ı stays ı
    -- so a stored tag or title keeps its own spelling.  NFC first, so a
    decomposed İ (I + U+0307, which is what a Mac filename hands over) is
    the same letter as a typed one."""
    return unicodedata.normalize("NFC", s or "").translate(_LOWER).lower()


def fold(s):
    """The comparison form: `lower`, plus the dotted and dotless i folded
    together (İ I i ı all become i) and any stray combining dot dropped.

    For matching only -- a search box, a filter key, a slug, an alignment
    token -- never for anything displayed or stored as the user wrote it.
    A Turk types "iyi" for a heading that opens "İyi", and a keyboard
    without ı types "isik" for "ışık"; folding matches too generously,
    which for a filter is the harmless direction.  Every other language is
    untouched: none of them uses ı or İ, so their text folds to exactly
    what it always lower-cased to.  The dot is dropped after NFC has had
    its chance to compose it, so a transliteration's ṡ keeps its own."""
    return unicodedata.normalize("NFC", s or "").translate(_FOLD).lower()


# The same fold, as JavaScript, for the pages that filter text in the
# browser and must agree character for character with what a tool wrote
# into them (the reading edition's contents panel).  Kept beside `fold`
# because the two have to be read together to stay the same function.
FOLD_JS = ("s => (s || '').normalize('NFC')"
           ".replace(/[\\u0130\\u0131]/g, 'i')"
           ".replace(/\\u0307/g, '').toLowerCase()")


def digit_class():
    """A regex character class matching a digit of any known language."""
    return "0-9" + _ALL_NATIVE


def chips(counts=None):
    """[{code, name, native, folder, count}] for an index page's language
    row, in registry order.  `counts` maps code -> number of items."""
    counts = counts or {}
    return [{"code": L.code, "name": L.name, "native": L.native,
             "folder": L.folder, "dir": L.dir, "count": int(counts.get(L.code, 0))}
            for L in LANGS.values()]


if __name__ == "__main__":
    for L in LANGS.values():
        print("%-3s %-9s %-9s %s  digits=%s  passes=%s%s%s%s"
              % (L.code, L.name, L.folder, L.dir, L.digits, "/".join(L.pass_keys),
                 "  reading" if L.reading else "", "  vertical" if L.vertical else "",
                 "  (added on this machine)" if L.mine else ""))
    print("glosses may be written in: %s" % ", ".join(GLOSS_CODES))
    for code, why in PROBLEMS:
        print("left out%s: %s" % ((" " + code) if code else "", why))


# ---------------------------------------------------------------- the pages
def css():
    """The per-language CSS tokens every page links (served as /lib/langs.css
    by the Parseh server and as static/langs.css by the studio alone).

    An element that carries data-lang="<code>" gets --tl-font (the main face),
    --tl-alt (the alternate face, or the main one again), --tl-dir and
    --tl-alt-lh (the leading the alternate face wants), and --tl-name, the
    English name as a CSS string, so a script on a page that was not handed
    the registry can still say "Catalan" rather than "ca".  The stacks and
    the names come from the registry, so no stylesheet and no script names
    a font or a language of its own.
    """
    out = ["/* generated from lib/languages.json -- do not edit */", ":root{"]
    for L in LANGS.values():
        out.append("  --tl-font-%s:%s;" % (L.code, L.css_font()))
        out.append("  --tl-alt-%s:%s;" % (L.code, L.css_font(alt=True)))
    out.append("}")
    for L in LANGS.values():
        lh = L.fonts.get("alt_line_height") or 1
        out.append("[data-lang=%s]{--tl-font:var(--tl-font-%s);--tl-alt:var(--tl-alt-%s);"
                   "--tl-dir:%s;--tl-alt-lh:%s;--tl-name:%s}"
                   % (L.code, L.code, L.code, L.dir, lh, json.dumps(L.name)))
    return "\n".join(out) + "\n"


def write_css(path=None):
    """Write css() to lib/langs.css (or `path`), so a reader opened straight
    off the disk -- or served as a plain file -- finds the tokens beside
    parseh.css.  Idempotent: rewritten only when the text changed."""
    path = path or os.path.join(HERE, "langs.css")
    text = css()
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return path
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


def chips_html(counts=None, current=None, cls="parseh-langs", selector="[data-lang]"):
    """The language row of an index page: one chip per nonempty language, with a
    count, plus 'all'.  lib/parseh.js wires the clicks (the shared
    `parseh_lang` preference, Parseh.lang) and hides every element matching
    `selector` (inside <main>, or <body> without one; the row itself never)
    whose data-lang is not the picked language.  `selector` None makes a
    row that only records the preference (an add page's default, say).
    `current` pre-selects a chip server-side (else the script does)."""
    import html as _h
    counts = counts or {}
    cur = current or "all"
    if cur not in LANGS or int(counts.get(cur, 0)) <= 0:
        cur = "all"
    total = sum(int(v) for v in counts.values())
    bits = ['<div class="%s" role="group" aria-label="language"%s>'
            % (cls, (' data-lang-filter="%s"' % _h.escape(selector, quote=True))
               if selector else "")]
    bits.append('<button type="button" class="chip%s" data-pick="all">all'
                '<span class="n">%d</span></button>' % (" on" if cur == "all" else "", total))
    for L in LANGS.values():
        n = int(counts.get(L.code, 0))
        if n <= 0:
            continue
        # data-lang gives the native name (the .native span, which the
        # stylesheets set in var(--tl-font)) its own face through langs.css;
        # parseh.js never filters a chip (anything inside .parseh-langs is
        # excluded), so the attribute cannot hide the chip itself
        bits.append('<button type="button" class="chip%s" data-pick="%s" lang="%s" '
                    'data-lang="%s" title="%s"><span class="native">%s</span>'
                    '<span class="n">%d</span></button>'
                    % (" on" if cur == L.code else "", L.code, L.code, L.code,
                       _h.escape(L.name, quote=True), _h.escape(L.native), n))
    bits.append("</div>")
    return "".join(bits)
