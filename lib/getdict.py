#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the dictionary a language's lookup reads: dict/<code>.db.

    python3 lib/getdict.py                 what is installed, and what is not
    python3 lib/getdict.py zh              fetch Chinese and build it
    python3 lib/getdict.py hi --keep       ... and keep the download
    python3 lib/getdict.py es --from FILE  build from a file already here
    python3 lib/getdict.py es --from FILE --out PATH
                                           ... into PATH, leaving dict/ alone
    python3 lib/getdict.py --all           every language the toolbox teaches

The source is Wiktionary, through Tatu Ylönen's extracts at kaikki.org: one
JSONL file per language, the same shape for all eleven, so there is one
converter here and not eleven.  The URL is derived from the registry's English
name (lib/languages.json) -- nothing in this file is a list of languages.

WHY NOT SHIP THE RESULT.  A built dictionary is tens or hundreds of MB
depending on the language -- Persian 21 MB, German 342 MB, as built on
2026-09-10 -- it is somebody else's work under somebody else's licence, and the
repository has always shipped the doors and none of the content.  So
dict/ is in .gitignore, a language with no file simply has no lookup, and
both readers say so rather than breaking.  The licence travels IN the file,
in its meta table, and both readers print it under the entries.

WHAT IS KEPT, AND WHY SO LITTLE.  A Wiktionary entry carries etymology,
pronunciation, hyphenation, categories, a dozen translations and the wikitext
it came from.  A reader hovering over a word in a book wants the headword,
how it sounds, what part of speech it is and what it means.  Keeping the
rest would multiply the file by ten and be shown to nobody.

WHAT MAKES IT WORK is the third table.  Wiktionary lists inflected forms --
both as `forms` on a lemma and as pages of their own saying "genitive
singular of X" -- and those become `form` rows pointing at the lemma.  That
is most of the morphology of all eleven languages, already done, and it is
why lib/lookup.py needs so few rules of its own.  What the rows cannot hold
is a word with something written onto it -- Arabic's و ب ل and object
pronouns (وَقَالَ, أُرِيدُهُ), the French and Italian elisions (s'approcha,
l'uomo), Italian's enclitics (lavorarlo) -- and the forms a source leaves
out of its tables: Persian's object enclitics and its past tense (202 of
the 471 one-word infinitives in the 2026-09-10 fa.db have no past row at
all), Japanese's て and た forms, Italian's agreeing participles.  Those
five languages have a lib/lang/<code>.lookup.json of rules, and so does
Chinese, with no rule in it: it says which spelling is the word's own and
which senses are another lect's.  German, English, Spanish, Hindi and
Turkish have none.
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.error

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import translit                # noqa: E402  which reading, and how it is written
import lookup                                                  # noqa: E402
import download       # noqa: E402  resumable, stoppable, and says how far

# Wiktionary's text is CC BY-SA 4.0; the extraction is Tatu Ylönen's
# wiktextract.  Both are named in every built file's meta table and printed
# by both readers under the entries -- an entry with no provenance is a
# rumour, and a licence that travels only in a README travels nowhere.
SOURCE = "Wiktionary, extracted by kaikki.org (wiktextract)"
LICENCE = "CC BY-SA 4.0"
URL = "https://kaikki.org/dictionary/%s/kaikki.org-dictionary-%s.jsonl"

# WHAT A DICTIONARY COSTS, MEASURED: (the extract's download, the built
# dictionary), in bytes, None where nobody has measured it.  Read by plan(),
# so the Reading help page can say how big before anybody presses a button
# -- and it says "about", because kaikki rebuilds its extracts every week and
# they only grow.  The extracts are docs/languages.md's (German 1 077 MB,
# Spanish 1 038 MB) and lib/lookuppage.py's (Turkish 431 MB); the built sizes
# are the dictionaries built on 2026-09-24 (English, Persian, Italian,
# Japanese, Turkish), and the 2026-09-10 builds docs/languages.md lists for
# the others -- smaller than today's builder makes (Japanese was 62 MB then,
# 89 MB now), so read those four as floors.  A language not here is asked:
# plan() reads the extract's size from kaikki before anything is fetched.
MEASURED = {
    "tr": (431_000_000, 306_000_000),
    "de": (1_077_000_000, 342_000_000),
    "es": (1_038_000_000, 272_000_000),
    "en": (None, 293_000_000),
    "fa": (None, 21_000_000),
    "it": (None, 155_000_000),
    "ja": (None, 89_000_000),
    "hi": (None, 88_000_000),
    "zh": (None, 57_000_000),
}

# form rows that are not forms: kaikki puts the shape of the inflection
# table into the same list as the words in it.
NOT_A_FORM = {"table-tags", "inflection-template", "class"}

# A ROW THAT SAYS IT IS THE WORD IN LATIN LETTERS.  Its tags say so --
# `romanization` on a Japanese or Hindi head row, `Rōmaji, romanization` on
# the page Wiktionary gives a Japanese word's rōmaji -- and those are the
# only Latin rows a language written in its own script has any use for.
_ROMAN_NOTE = re.compile(r"roman|translit|r[oō]maji", re.I)

# WORD-STRUCTURE LABELS FILED AS ROMANISATIONS.  wiktextract reads the
# Chinese head line `看⫽見 (verb-complement)` and files the parenthesis as the
# word's romanisation: 118 `verb-complement`, 13 `modifier-verb`, 12
# `subject-predicate` and one `verb-complement-object`.  They were the
# translit of every one of those verbs, and the reader's panel printed a
# grammar label where the pinyin belonged.
NOT_A_ROMAN = {"verb-complement", "modifier-verb", "subject-predicate",
               "verb-complement-object"}

# WHICH MANDARIN READING.  A Chinese page lists a dozen romanisations of a
# dozen lects, and pinyin alone is not enough: 睡覺 has a Xi'an `fēijiāo`
# tagged Mandarin + Pinyin beside the standard shuìjiào, and 吃 a Nanjing
# `chii̊q`.  A standard reading carries these tags and nothing else -- an
# Erhua or toneless variant, a Bopomofo or Wade-Giles row, a place, all add
# one -- so the test is that the tags are a subset of these.
PINYIN_TAGS = {"Mandarin", "Pinyin", "Standard", "Standard-Chinese"}

# The Japanese verb class as the head template spells it (`type`): godan is
# 1, 1s or godan; ichidan 2 or ichidan; the two irregulars kuru and suru
# under their own names or the classical kahen and sahen.  The CLASSICAL
# types (shimo ni, kami ni, yo, rahen: 200 verbs) are no modern class, and
# are kept as the raw `type` so a verb builder can tell them apart rather
# than guess one.
JA_CLASS = {"1": "godan", "1s": "godan", "godan": "godan",
            "2": "ichidan", "ichidan": "ichidan",
            "suru": "suru", "sahen": "suru",
            "kuru": "irregular", "kahen": "irregular",
            "irr": "irregular", "irregular": "irregular"}

# ...and its transitivity, which the same template writes eleven ways --
# 2496 trans, 617 transitive, 257 tr, 1757 intrans, 411 intransitive, 301
# intr, 17 in, and the odd intans and instrans; 331 both.
TRANSITIVITY = {"trans": "tr.", "transitive": "tr.", "tr": "tr.",
                "intrans": "intr.", "intransitive": "intr.", "intr": "intr.",
                "in": "intr.", "intans": "intr.", "instrans": "intr.",
                "both": "tr./intr."}

# ...and the Hindi head template's one-letter code for the same thing (t, i,
# it, d on 1 026 of 1 634 verb pages), in the same words.  A ditransitive
# verb is transitive: देना takes ने like करना does.
HI_TRANSITIVITY = {"t": "tr.", "d": "tr.", "i": "intr.",
                   "it": "tr./intr.", "ti": "tr./intr."}

# The Persian conjugation table whose stems a reader of these editions
# wants.  A Persian verb page carries up to five tables -- literary Iranian,
# colloquial Tehrani, dialectal Isfahan, literary Dari, colloquial Kabuli --
# and only `args.header` says which one is which.
IRANIAN_TABLE = "(literary Iranian Persian)"

# A CELL THE EXTRACTOR COULD NOT NAME, WHOSE ONLY TAG IS A NUMBER, AND IN
# WHICH NONE OF THE VERB'S STEMS APPEARS is the person column of an
# old-style conjugation table, not a form of the verb.  The old tables of
# seven Persian verbs (آراستن, both جستن, افراشتن, پیراستن, ویراستن, نشسن,
# ششتن) head their rows with the pronouns من تو او وی آن ما شما ایشان آنان
# آنها, and wiktextract filed every one as a form of the verb tagged
# `error-unrecognized-form singular` (or `plural`) -- so every pronoun in a
# Persian sentence came back as a verb hit: 792 of the 4 291 verb-hit words
# in 2 000 Tatoeba sentences.  The tags alone are not enough: the same pair
# is on each table's optative (آرایاد, جویاد: may he adorn, may he seek),
# and on 14 298 cells of Turkish verb tables -- converbs, ekerken, ekerek --
# whose pages give no stem at all.  The stems are the page's own `stem`
# rows (آرا, آراست), so over the whole Persian extract this takes the 91
# pronoun cells and keeps the 8 optatives; a page with no stem row loses
# nothing.  بودن's cells tagged `error-unrecognized-form` and NOTHING else
# are its real forms (بودم, باشم, هستم) and are not asked.  Only a verb's
# table: the same pair on a noun's page is its ezafe (نام nām-i, اتای
# atā-yi).
_PERSON_COLUMN = (frozenset(("error-unrecognized-form", "singular")),
                  frozenset(("error-unrecognized-form", "plural")))

# A DERIVED VERB WITH A TABLE OF ITS OWN IS AN ENTRY, although its only
# sense points at the verb it comes from.  Turkish writes its passives and
# causatives that way -- yapılmak is `passive of yapmak: to be/become done
# or made`, pişirmek `causative of pişmek: to cook something` -- and gives
# each its own full conjugation table: 281 such pages, 261 066 form rows.
# Dropped as pointers (see _senses), the cells went with them, so yapılıyor,
# verildi and kullanılır reached nothing at all.  Named by the table's
# template, the one thing that says the page conjugates the word itself;
# a Persian or Hindi `alternative form of X` page that repeats X's table
# stays the pointer it always was.
OWN_TABLE = {"tr-conj"}

# THE MODERN HINDI SPELLING OF A GLIDE.  Wiktionary's Hindi tables write the
# y-glide of a vowel-final stem with य: दिखायी, दिखाये, दिखायेंगे, दिखाइये.
# Current Hindi mostly writes the vowel letter instead -- दिखाई, दिखाए,
# दिखाएँगे, दिखाइए -- and Wiktionary's own pointer pages say so (लायी is
# `alternative` to लाई, जायेंगे to जाएँगे, चाहिये to चाहिए).  A text in the
# modern spelling met only the pages that happen to exist: `अँगूठी दिखाई`
# reached the noun दिखाई (sight) and never दिखाना, whose table has दिखायी.
# A य counts as the glide after a letter or a vowel sign, never after a
# virama (दर्ये, a conjunct) and never at the start of a word (ये, these).
# ें becomes एँ, as the pages write it (जाएँ, होएँ); ीं keeps its dot (हुईं).
_GLIDE = re.compile("(?<=[\u0904-\u0939\u093c-\u094c\u0958-\u0963"
                    "\u0972-\u097f])\u092f([\u0940\u0947])([\u0901\u0902]?)")
_GLIDE_TO = {"\u0940": "\u0908", "\u0947": "\u090f"}     # ी -> ई, े -> ए


def url_for(L):
    """Where this language's extract lives.  kaikki names its files by the
    language's English name, which the registry already holds -- so a
    language added to the registry needs nothing added here.  A variety
    (lib/languages.py with_variety) has its own, named in its row: the first
    of them here, every one in urls_for()."""
    return urls_for(L)[0]


def urls_for(L):
    """Every extract this dictionary is made of: one for a language, one or
    more for a variety (Levantine is kaikki's South and North Levantine
    Arabic, two files with two codes)."""
    if L.variety:
        v = L.variety_of(L.variety) or {}
        names = [n for n, _code in v.get("kaikki") or []]
    else:
        names = [L.name]
    # the folder keeps the name's spaces and the file drops them: Egyptian%20Arabic/...-EgyptianArabic.jsonl
    return [URL % (n.replace(" ", "%20"), n.replace(" ", "")) for n in names]


def accepted_codes(L):
    """The `lang_code`s an extract's entries may carry: the language's own, or
    the variety's (arz for Egyptian Arabic, ajp and apc for Levantine) -- kaikki
    files a dialect under its own ISO code, and every one of them would be
    taken for a stray entry and skipped."""
    if L.variety:
        v = L.variety_of(L.variety) or {}
        return {c for _n, c in v.get("kaikki") or []} or {L.code}
    return {L.code}


_AUX = re.compile(r"\[auxiliary ([^\[\]]+)\]")


def _sense_facts(s):
    """What one sense says about how its verb is USED, as extra sense tags.

    Three facts live in a sense and nowhere else, and all three were thrown
    away with everything `_senses` does not read:

    THE AUXILIARY OF THIS MEANING.  German gives it per sense, at the end of
    the raw gloss: aufstehen `to get up [auxiliary sein]` but `to be open
    [auxiliary haben or sein]`.  kaikki strips it from `glosses`, so the only
    record of which auxiliary a dual verb takes in which meaning -- 201 of
    the 466 such lemmas settled by it -- was lost.  Kept as `aux:sein`,
    `aux:haben`, `aux:haben/sein`.

    THE OBJECT IT GOVERNS.  `{{+obj}}` in `info_templates`: helfen `dat`,
    warten `:auf(acc)`, Arabic `:إِلَى/acc<somewhere>`.  Kept as `obj:` and
    the template's own argument, commas made semicolons, because the line
    it goes into is comma-joined.

    THE CASE A TURKISH VERB TAKES, which Wiktionary writes as prose in the
    qualifier: `[with dative]`, `(intransitive, with ablative case)`, `(with
    -den)`, `(with ile or instrumental)`.  Kept as `with-dative` and so on,
    the spelling wiktextract itself uses where it did tag one.  Measured on
    the first sense of 2 560 Turkish verbs: 83 said what they govern from
    what was kept before, 145 with these.

    Nothing here demotes a sense: lookup.rank_senses reads registers, and a
    tag with a colon or a `with-` is neither.
    """
    raw = [g for g in (s.get("raw_glosses") or s.get("glosses") or [])
           if isinstance(g, str)]
    out = []
    for g in raw:
        for m in _AUX.findall(g):
            aux = [p.strip() for p in re.split(r"\s+or\s+|\s*,\s*", m.strip())]
            # one word each, or it is prose ("sein, rarely haben") and the
            # tag would be a guess about which word is the auxiliary
            if aux and all(re.fullmatch(r"\w+", p) for p in aux):
                out.append("aux:" + "/".join(aux))
    for t in s.get("info_templates") or []:
        if t.get("name") == "+obj":
            v = str((t.get("args") or {}).get("2") or "").strip()
            if v:
                out.append("obj:" + re.sub(r"\s+", " ", v.replace(",", ";")))
    for g in raw:
        out.extend("with-" + c for c in _government(g))
    seen = set()
    return [t for t in out if not (t in seen or seen.add(t))]


# A register tag is one lookup.rank_senses moves a sense for; nothing else
# is worth second-guessing here.
_REGISTERS = lookup._STALE | lookup._MARKED
_RARELY = re.compile(r"\brarely\s+[\w-]+", re.I)


def _not_this_sense(s):
    """The register tags wiktextract put on this sense that its gloss says
    about something ELSE -- a use of the verb, or its object.

    denken's first sense, `(intransitive or rarely transitive) to think
    [with an (+ accusative) ‘about something’ or (rare) accusative
    ‘something, e.g. a thought’]`, came out tagged `rare`: the rare thing is
    the transitive use (and, in the {{+obj}} after it, the bare accusative
    object), not thinking.  lookup.rank_senses put the sense in the last
    tier, and the commonest verb of German was offered as `not to forget`.
    So a register tag goes where the only places the gloss says it are
    `rarely X` (the adverb is about X: kuscheln `intransitive, rarely
    transitive`, perplex `rarely attributive`, markten `archaic or rarely
    literary`) or the +obj template's expansion and qualifier (`<q:rare>`).
    Measured over the German extract: 1 033 senses tagged rare, 6 of them
    this way, denken among them.  Where the gloss says `rare` of the sense
    itself -- `(literary, rare)`, `(rare) to exit a program` -- or does not
    say it at all (the tag came from somewhere the gloss does not show),
    the tag stays.
    """
    raw = " ".join(g for g in (s.get("raw_glosses") or []) if isinstance(g, str))
    tags = [t for t in (s.get("tags") or []) if isinstance(t, str)]
    if not raw or not any(t.lower() in _REGISTERS for t in tags):
        return set()
    rest, obj = raw, []
    for t in s.get("info_templates") or []:
        if t.get("name") == "+obj":
            e = str(t.get("expansion") or "")
            if e:
                rest = rest.replace(e, " ")
            obj.append(e + " " + str((t.get("args") or {}).get("2") or ""))
    rarely = bool(_RARELY.search(rest))
    rest = _RARELY.sub(" ", rest)
    out = set()
    for t in tags:
        low = t.lower()
        if low not in _REGISTERS:
            continue
        # the word the gloss writes it with: rare, obsolete, figurative(ly)
        said = re.compile(r"\b" + re.escape(low[:5]), re.I)
        if said.search(rest):
            continue                    # the gloss says it of the sense
        if any(said.search(x) for x in obj) or (low == "rare" and rarely):
            out.add(t)
    return out


# The cases as Wiktionary's English names them (one `accusaative` is in the
# data), and the Turkish case endings the same qualifiers use instead:
# `(with -den)`, `[with -e]`, `(with -le)`.  Whole words only: `(music, with
# instruments)` is not the instrumental.
_CASE_ENDINGS = {"dative": "dative", "ablative": "ablative",
                 "accusative": "accusative", "accusaative": "accusative",
                 "instrumental": "instrumental", "locative": "locative",
                 "genitive": "genitive"}
for _case, _ends in (("dative", "-e -a -ye -ya"),
                     ("ablative", "-den -dan -ten -tan"),
                     ("accusative", "-i -ı -u -ü -yi -yı -yu -yü"),
                     ("locative", "-de -da -te -ta"),
                     ("instrumental", "-le -la -yle -yla ile"),
                     ("genitive", "-in -ın -un -ün -nin -nın -nun -nün")):
    for _e in _ends.split():
        _CASE_ENDINGS[_e] = _case
_GLUE = {"or", "and", "with", "case", "cases", "used", "+"}


def _groups(text):
    """The outermost (...) and [...] groups of a gloss, each whole.

    Outermost, because a German bracket nests its preposition's case inside
    it -- `[with auf (+ accusative)]` -- and read as two groups the inner one
    would say warten governs an accusative, which it does not.
    """
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch in ")]" and depth:
            depth -= 1
            if depth == 0:
                out.append(text[start:i])
    return out


def _government(gloss):
    """The cases a qualifier of this gloss says the verb takes, or [].

    READ ONLY WHAT IS NOTHING BUT CASES.  After `with` (or a leading `+`)
    every word must be a case, a case ending, or glue (`or`, `and`, `case`);
    a comma closes the list.  Anything else and the qualifier is prose and
    says nothing about government: `(frequently with yalan)`, `(with
    possessive marker on object)`, `(to stroke with a tongue)`, and -- the
    one that taught the rule -- kalmak's `(those with -a, -e, -ıp, -ip)`,
    whose first two items look like the dative until the third says they are
    converb endings.
    """
    out = []
    for grp in _groups(gloss):
        toks = re.findall(r"‘[^’]*’|'[^']*'|[+,;]|[^\s,;+‘’'()\[\]]+", grp)
        if toks[:1] == ["+"]:
            i = 1
        elif "with" in toks:
            i = toks.index("with") + 1
        else:
            continue
        got, fresh, ok = [], False, True
        for t in toks[i:]:
            if t in (",", ";"):
                fresh = True            # a new item of the qualifier begins
                continue
            if t[:1] in "‘'":
                continue                # its gloss: `[with dative ‘someone’]`
            low = t.lower()
            case = _CASE_ENDINGS.get(low)
            if case:
                got.append(case)
                continue
            if low in _GLUE:
                continue
            if fresh and got and not t.startswith("-"):
                break                   # `(with dative, idiomatic)`: done
            ok = False
            break
        if ok:
            out.extend(c for c in got if c not in out)
    return out


def _senses(o):
    """The meanings, one per line, and the lemmas this page is a form of.

    A sense that is only "plural of X" or "Devanagari script form of X" is
    not a meaning: it is a pointer, and it is dropped from the text and kept
    as a form row instead, which is where it is useful.  Both kinds matter --
    `form_of` is the morphology, `alt_of` is the spelling -- and the second
    is the whole road to the meaning wherever a source keeps its senses under
    one spelling and gives the other script a page that only points at it,
    which is how Wiktionary treats a language written in two scripts.  A page
    whose senses are all pointers gets no entry of its own, so a reader is
    never shown "alternative spelling of X" where the meaning should be.
    """
    out, forms, seen = [], [], set()
    for s in o.get("senses") or []:
        gl = [g for g in (s.get("glosses") or []) if isinstance(g, str)]
        fo = [f.get("word") for f in (s.get("form_of") or []) if f.get("word")]
        al = [f.get("word") for f in (s.get("alt_of") or []) if f.get("word")]
        # A CONTRACTION IS TWO WORDS, NOT A SPELLING OF ONE, and its gloss is
        # the meaning ("Contraction of the preposition a and the article el.
        # to the").  Wiktionary tags Catalan's al, del, pel, can `alt-of`, with
        # a target that is either a sentence (no page: del was dropped
        # whole) or the first word alone, so `al` was filed under the letter
        # a and `can` under ca, "dog".  Its gloss is kept as a meaning.
        if (fo or al) and "contraction" in (s.get("tags") or []) and gl:
            fo = al = []
        if fo or al:
            note = ", ".join(t for t in (s.get("tags") or [])
                             if t not in ("form-of", "alt-of", "no-gloss"))
            for w in fo:
                forms.append((w, note or "a form of"))
            for w in al:
                forms.append((w, ("%s spelling" % note) if note else "another spelling"))
            continue
        # THE REGISTER TAGS COME WITH THE SENSE and used to be dropped.
        # They are the whole of what makes an ordering possible later
        # (lookup.rank_senses): the source itself says which senses are
        # obsolete, dialectal or figurative, and a reader of a living text
        # wants none of those first.
        elsewhere = _not_this_sense(s)
        have = [t for t in (s.get("tags") or [])
                if isinstance(t, str) and t not in ("no-gloss",)
                and t not in elsewhere]
        have += [t for t in _sense_facts(s) if t not in have]
        tags = ",".join(have)
        for g in gl:
            g = g.strip()
            if g and g not in seen:
                seen.add(g)
                out.append((g, tags))
    return out, forms


def _own_table_senses(o):
    """The pointer senses of a page that conjugates its word itself, as the
    senses of an entry -- [] for every other page (see OWN_TABLE).

    The pointer's own gloss is the meaning, and a good one: `passive of
    yapmak: to be/become done or made`.  Its tags stay as a sense's do
    (`form-of`, `passive`), so a reader can still tell it points.  The
    pointer row to the verb it comes from is written as well, as before:
    yapılmak still reaches yapmak.
    """
    if (o.get("pos") or "").strip() != "verb" or not any(
            t.get("name") in OWN_TABLE for t in o.get("inflection_templates") or []):
        return []
    out, seen = [], set()
    for s in o.get("senses") or []:
        tags = ",".join(t for t in (s.get("tags") or [])
                        if isinstance(t, str) and t != "no-gloss")
        for g in s.get("glosses") or []:
            g = g.strip() if isinstance(g, str) else ""
            if g and g not in seen:
                seen.add(g)
                out.append((g, tags))
    return out


def _pinyin(o):
    """A Chinese word's standard Mandarin pinyin, or "".

    CHINESE KEEPS ITS ROMANISATION WHERE NOTHING ELSE LOOKED: in
    `sounds[].zh_pron`, one row per lect and system.  Neither place
    `_translit` reads has it, so 189 032 of 189 192 Chinese entries had no
    translit at all, and the 160 that did had a grammar label (see
    NOT_A_ROMAN).  The first standard row is the record's own reading -- a
    polyphonic character is one record per reading, 了 le and 了 liǎo -- and
    it may carry the numbered form after it, `chī (chi¹)`, which goes.
    """
    for s in o.get("sounds") or []:
        v = str(s.get("zh_pron") or "").strip()
        tags = set(t for t in (s.get("tags") or []) if isinstance(t, str))
        if v and {"Mandarin", "Pinyin"} <= tags and tags <= PINYIN_TAGS:
            v = re.sub(r"\s*\([^()]*\)$", "", v).strip()
            if v:
                return v
    return ""


def _translit(o):
    """The romanisation the source gives, if it gives one.

    Three places carry it: a Chinese word's pinyin (`_pinyin`), a `forms` row
    tagged romanization, and the `tr` argument of the head template.
    Wiktionary writes `-` there to mean "no romanisation", which is not a
    romanisation.

    `tr` IS NOT A ROMANISATION IN A JAPANESE TEMPLATE.  ja-verb, ja-verb-suru,
    ja-verb form and ja-pos use it for transitivity -- which is how する came
    out romanised `both`, 擦る and 刷る `trans`, 所持 and 授受 `transitive`.
    The rōmaji is in the head line itself, `する • (suru) transitive or
    intransitive`, and that is where it is read for them.
    """
    v = _pinyin(o)
    if v:
        return v
    for f in o.get("forms") or []:
        tags = set(f.get("tags") or [])
        if tags & {"romanization", "transliteration", "romanisation"}:
            v = (f.get("form") or "").strip()
            if v and v != "-" and v not in NOT_A_ROMAN:
                return v
    for h in o.get("head_templates") or []:
        if str(h.get("name") or "").startswith("ja-"):
            m = re.search(r"•\s*\(([^()]+)\)", str(h.get("expansion") or ""))
            v = m.group(1).strip() if m else ""
        else:
            v = str((h.get("args") or {}).get("tr") or "").strip()
        if v and v != "-":
            return v
    return ""


def _said(o, code):
    """How THIS page's word is romanised, for a page that is only a pointer.

    The same rule the lookup follows for a lemma (lib/lookup.py _hits_for):
    where the language turns a pronunciation into its romanisation --
    Persian by the table in lib/lang/fa.ipa.json, French by the respelling
    lib/lang/fr.ipa.json names -- the pronunciation, because Persian's own
    romanisation in the source is the classical register (`hil` where
    Tehran says `hel`) and French has none; everywhere else the
    romanisation the source gives.  गया's page says `gayā` and nothing else
    in Wiktionary does: जाना has no table.
    """
    # translit.speaks, not the presence of a `map`: French writes its
    # pronunciations by a respelling of its own and has no table, and asking
    # for the map left every French pointer page without a sound.
    if translit.speaks(code):
        return translit.from_ipa(code, _ipa(o, code))
    return _translit(o)


def _ipa(o, code):
    """How this word is said, in the register this language's editions use.

    Wiktionary gives several per word, tagged: Persian has Classical-Persian,
    Dari, Kabuli, Tajik and Iran, and they are not small differences --
    classical `kitāb` against Tehran `ketāb`, classical `xwāndan` (with the و
    of خوا spoken) against `xāndan` (with it silent, as it has been for
    centuries).  The language says which it wants in lib/lang/<code>.ipa.json;
    a language that says nothing takes the first pronunciation given.

    A language whose .ipa.json says `"avoid_mode": "all"` is read by
    _ipa_tiered instead; every other one exactly as before.
    """
    want, avoid = translit.prefers(code)
    if (translit.ipa_rules(code) or {}).get("avoid_mode") == "all":
        return _ipa_tiered(o, want, avoid)
    best = ""
    for s in (o.get("sounds") or []):
        ipa = (s.get("ipa") or "").strip()
        if not ipa:
            continue
        tags = set(s.get("tags") or [])
        if want and tags & set(want):
            return ipa                       # exactly the register asked for
        if avoid and tags & set(avoid):
            continue                         # a register this edition is not in
        if not best:
            best = ipa                       # untagged, or tagged something else
    return best


def _ipa_tiered(o, want, avoid):
    """_ipa for a language with many accents and one it is written in:
    English, whose .ipa.json asks for General-American and avoids two dozen
    places.  Three things differ from the Persian reading, and each was
    measured on English:

    AVOIDED ONLY WHEN EVERY TAG IS.  A transcription is often tagged with
    every accent that shares it: fix's only one is Australia + Canada + UK
    + US, and read as "any tag avoided" it was thrown away for the
    Australia.  Persian keeps "any" -- its avoided registers are whole
    other languages (Dari, Tajik), and a sound tagged Dari is Dari.

    NEVER A WEAK FORM WHILE ANOTHER IS LEFT.  The first sound listed for do
    is the unstressed /də/, for was /wəz/, in /ən/, does /dəz/ -- each
    noted `weak form` -- and a vocabulary line gives the word as said on
    its own.

    /PHONEMIC/ BEFORE [NARROW] IN EACH TIER, and a narrow one only where it
    is all there is: prefer has only [pɹɪˈfɝ], pass's only General-American
    one is [pʰæs].

    The tiers: a sound in a preferred register, then any sound not wholly
    in avoided ones (untagged included).  Measured by the English verb
    recipe with exactly this rule: of 387 common verbs, 271 had every sound
    of their \\vb filled before and 351 after.
    The pointer pages' `heard` goes through here too, which is what gives
    the irregular forms (went, said) their sounds.
    """
    want, avoid = set(want), set(avoid)
    rows = []
    for s in o.get("sounds") or []:
        ipa = (s.get("ipa") or "").strip()
        if ipa:
            rows.append((ipa, set(t for t in (s.get("tags") or [])
                                  if isinstance(t, str)),
                         str(s.get("note") or "")))
    strong = [r for r in rows if "weak form" not in r[2]] or rows
    for ok in (lambda t: bool(t & want),
               lambda t: not (t and t <= avoid)):
        for narrow in (False, True):
            for ipa, tags, _note in strong:
                if ipa.startswith("[") == narrow and ok(tags):
                    return ipa
    return ""


def _reading(o, L):
    """How this word is read, for a language whose writing does not say.

    Wiktionary keeps a Japanese word's kana in the head template's first
    argument -- 日本語 is にほんご, 食べる is たべる -- and nowhere else that
    is easy to find.  It is checked against what the registry says a reading
    of this language looks like, so a template argument that is not one (a
    part of speech, a number) is not stored as though it were.
    """
    if not L.reading:
        return ""
    for h in (o.get("head_templates") or []):
        v = str((h.get("args") or {}).get("1") or "").strip()
        if v and L.is_reading(v):
            return v
    return ""


# wiktextract hands a template argument's < and > over as the private-use
# characters U+10203F and U+102040: `a<transitive>` arrives in them.
_ANGLE = str.maketrans({"\U0010203f": "<", "\U00102040": ">"})


def _it_aux(spec):
    """[[code, qualifier], ...] from it-verb's first argument, or [].

    THE AUXILIARY WITH ITS REASON, which the form rows lose.  it-verb opens
    with the auxiliaries, `:`-separated, each with an optional qualifier in
    angle brackets, before the first `/` or `\\` that starts the
    conjugation: prendere is `a:e<also in the meaning "to happen
    unexpectedly">\\@`, passare `e<intransitive>:a<transitive>/à`, volare
    `a<usually>:e<when accompanied by a location to or from, or in extended
    or figurative senses>/ó`.  wiktextract reduces those qualifiers to tags
    on the auxiliary's form row -- `also`, `goal`, `error-unknown-tag` -- and
    a builder deciding whether prendere takes essere was reading tags that
    had lost the sentence.  The codes are kept as written (`a`, `e`, and `-`
    for a verb with no participle), never mapped to a word here.
    """
    s = (spec or "").translate(_ANGLE)
    depth, cut = 0, len(s)
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">" and depth:
            depth -= 1
        elif ch in "/\\" and not depth:
            cut = i
            break
    out, item, depth = [], "", 0
    for ch in s[:cut] + ":":
        if ch == ":" and not depth:
            m = re.fullmatch(r"\s*([^<>\s]+)\s*(?:<(.*)>)?\s*", item, re.S)
            if m:
                out.append([m.group(1), (m.group(2) or "").strip()])
            item = ""
            continue
        depth += (ch == "<") - (ch == ">" and depth > 0)
        item += ch
    # A PRONOMINAL VERB HAS NO AUXILIARY PART: lavarsi's argument is `à`,
    # farsi's `@` -- the conjugation alone, essere being implied -- and read
    # as an auxiliary it gave {"aux": [["à", ""]]}.
    return out if out and all(code in ("a", "e", "-") for code, _q in out) else []


def _head(o, L):
    """What the head line says that no sense and no form row does, as the
    JSON text of entry.head ("" when it says nothing a reader could use).

    A verb builder needs these and they were not in the file at all:

      {"class": "godan", "tr": "tr."}      a Japanese verb, from ja-verb's
                                           `type` and `tr` (JA_CLASS,
                                           TRANSITIVITY); a classical type
                                           stays as {"type": "shimo ni"}
      {"type": "vo"}                       a Chinese verb, from zh-verb: vo
                                           is separable (睡⫽覺), vc takes a
                                           potential (看⫽見); the rest are not
                                           split in teaching
      {"tr": "tr."}                        a Hindi verb, from hi-verb's code
                                           (HI_TRANSITIVITY) -- the sense tags
                                           say it too, but only once rebuilt
      {"prs": "گو", "prs_tr": "gu", "ps": "گفت", "ps_tr": "goft",
       "inf_tr": "goftán"}                 a Persian verb's literary Iranian
                                           stems and their sounds
      {"vn_none": ["زَالَ"]}                 the Arabic perfects whose head
                                           says the verb has no verbal noun
                                           (ar-verb's `vn:-`)
      {"aux": [["a", "transitive"],
               ["e", "intransitive"]]}    an Italian verb's auxiliaries as
                                           it-verb spells them, each with
                                           its qualifier ("" for none)

    THE PERSIAN STEMS FROM ONE TABLE, AND THE RIGHT ONE.  The head row's
    stem is written in two registers at once (`šaw /šov`) and the form rows
    of five tables share their tags, so `دانستن` came out with a Dari
    infinitive and شدن with the colloquial `še` as its stem.  Only the
    table's header says which register it is in; the table is taken only
    when its infinitive is this headword -- خاموش کردن's page carries آزاد
    کردن's -- and the stems lose their harakat (نوِیس is نویس).
    """
    word = (o.get("word") or "").strip()
    out = {}
    for h in o.get("head_templates") or []:
        name = str(h.get("name") or "")
        a = h.get("args") or {}
        typ = str(a.get("type") or "").strip()
        if name == "zh-verb" and typ:
            out.setdefault("type", typ)
        elif name in ("ja-verb", "ja-verb-suru") and "class" not in out:
            cls = "suru" if name == "ja-verb-suru" else JA_CLASS.get(typ, "")
            if cls:
                out["class"] = cls
            elif typ:
                out["type"] = typ
            tr = TRANSITIVITY.get(str(a.get("tr") or "").strip())
            if tr:
                out["tr"] = tr
        elif name == "hi-verb":
            tr = HI_TRANSITIVITY.get(str(a.get("1") or "").strip())
            if tr:
                out.setdefault("tr", tr)
        elif name == "ar-verb" and "vn:-" in str(a.get("1") or ""):
            # THE SOURCE SAYS THIS VERB HAS NO VERBAL NOUN, and the file
            # kept no trace of it: `vn:-` in the head template's spec (زَالَ,
            # and idioms such as كَشَفَ النِّقَابَ: 28 heads) leaves no masdar
            # row, exactly as a page nobody has finished does (`verbal noun
            # ?`, 15 heads: بَنَّ, سَالَ) -- and lib/verbs/ar.py flagged all
            # of them `masdar` missing.  One list per entry, of the vowelled
            # perfect each such head line opens with (`زَالَ • (zāla) I ...`),
            # because an entry can hold several heads and only some say it.
            perf = str(h.get("expansion") or "").split(" • ")[0].strip()
            if perf:
                out.setdefault("vn_none", [])
                if perf not in out["vn_none"]:
                    out["vn_none"].append(perf)
        elif name == "it-verb" and "aux" not in out:
            aux = _it_aux(str(a.get("1") or ""))
            if aux:
                out["aux"] = aux

    def key(s):
        return L.strip(str(s or "")).replace(" ", "").replace("‌", "")
    for t in o.get("inflection_templates") or []:
        a = t.get("args") or {}
        if IRANIAN_TABLE not in str(a.get("header") or "") \
                or not word or key(a.get("inf")) != key(word):
            continue
        for k, arg in (("prs", "pr-stem"), ("prs_tr", "pr-stem-tr"),
                       ("ps", "ps-stem"), ("ps_tr", "ps-stem-tr"),
                       ("inf_tr", "inf-tr")):
            v = str(a.get(arg) or "").strip()
            if k in ("prs", "ps"):
                v = L.strip(v)
            if v and v != "-":
                out[k] = v
        break
    return json.dumps(out, ensure_ascii=False, sort_keys=True) if out else ""


# Letters of the alphabets a romanisation or a neighbouring language's
# spelling is written in: Latin with its extensions (ā, ḍ, ǎ), Greek,
# Cyrillic.
_ALPHABET = re.compile("[A-Za-zÀ-ɏͰ-ϿЀ-ӿḀ-ỿ]")


def _foreign(w, note, L):
    """A row in the Latin (or Cyrillic) alphabet and in none of the
    language's own letters, which does not say it is the word's romanisation
    either -- so it is nothing a page of this language can contain.

    Persian's table rows included `dah`, `bâš` and `tavân`, tagged `past
    stem`: the romanisation of an old-style table misfiled as a form.  A
    verb builder reading the stems found `bâš` as بودن's past stem.  So did
    the Tajik `додан` tagged Cyrillic (6 652 rows of Persian), and the Latin
    ghost of every row of a classical Japanese table (`kaka` tagged
    `irrealis stem`, 25 870 rows).

    AN ALPHABET, NOT "OUTSIDE `chars`".  The registry's Chinese ranges stop
    at the Basic Multilingual Plane, and Wiktionary's variant characters do
    not: 西 has 𠧜 and 𠧪, 南 has a second-round simplification past U+30000.
    Testing for the script alone refused 11 614 Chinese rows, and 401 of
    them were Latin.  A Latin-script language has no `chars` and nothing is
    refused; a word of a script language that is itself written in Latin
    (Chinese `OK`, Japanese `GDP`) is not asked -- see the callers.
    """
    return (L.re_chars is not None and not L.re_chars.search(w)
            and bool(_ALPHABET.search(w))
            and not _ROMAN_NOTE.search(note or ""))


def _common_end(a, b):
    """The longest ending two strings share."""
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return a[len(a) - n:] if n else ""


def _respelt(word, stem_past, kanji):
    """(form, note, roman) for the head line's stem and past in each of the
    verb's `alternative kanji` spellings.

    飲む HAS NO PAGE OF ITS OWN.  Wiktionary files it under the kana のむ,
    with 飲む, 呑む and 喫む as `alternative kanji` rows, and gives the stem
    and past in kana only (のみ nomi, のんだ nonda); so do わかる (分かる),
    やすむ (休む), とる (取る, 撮る) and うたう (歌う).  lib/lang/ja.lookup.json
    takes ます off 飲みます and asks for a stem `飲み` that no row had, so the
    polite forms of the commonest verbs reached nothing, and 分かった landed
    on 分かつ alone.  Each spelling differs from the headword in a front
    part only -- 飲 for の, the ending む shared -- and the stem and the past
    share that front part too, so they are the head line's own with it
    replaced: 飲み, 飲んだ.  lib/verbs/ja.py _respelling makes the same
    substitution for the \\vb, and under the same conditions: a shared
    ending, a front part on both sides, and a stem and past that begin with
    the headword's front part (する's し does not begin with す, so 為る
    gets nothing).  Noted exactly as the head's own rows are, `stem` and
    `past`, with their rōmaji; they are written after them, so the kana
    stem stays the entry's first.
    """
    out = []
    for alt in kanji:
        tail = _common_end(alt, word)
        front, head = alt[:len(alt) - len(tail)], word[:len(word) - len(tail)]
        if not (tail and front and head) or alt == word:
            continue
        if not all(w.startswith(head) for w, _t, _r in stem_past):
            continue
        out.extend((front + w[len(head):], t, r) for w, t, r in stem_past)
    return out


def _modern_glides(rows, word, seen, spelt):
    """The rows, each -यी/-ये cell followed by its modern -ई/-ए spelling
    (_GLIDE): same note, same romanisation, same pronunciation.

    A verb's table only.  On a noun or adjective the य is as often the
    stem's own -- अनुयायी (follower), विजयी, गाय's plural गायें -- and अनुयाई
    is no spelling of anything.  For the same reason a word of the headword
    itself is left alone (a table of विजयी होना would keep विजयी), and so is
    every cell of a verb whose stem ends in य (हयना: its हयी is hay-ī).
    """
    if word.endswith("यना"):
        return rows
    words = set(word.split())

    def vowel(g):
        # ें is एँ: the dot of ें sat on the matra, ए has room for the moon
        nasal = "\u0901" if g.group(1) == "\u0947" and g.group(2) else g.group(2)
        return _GLIDE_TO[g.group(1)] + nasal

    out = []
    for w, t, r, ipa in rows:
        out.append((w, t, r, ipa))
        m = " ".join(x if x in words else _GLIDE.sub(vowel, x)
                     for x in w.split(" "))
        if m != w and (m, t) not in seen:
            seen.add((m, t))
            spelt.add(m)
            out.append((m, t, r, ipa))
    return out


def _forms(o, L):
    """(form, note, roman) for every spelling of this lemma: `_form_rows`
    without the pronunciation, the shape the tests and older callers know."""
    return [(w, t, r) for w, t, r, _i in _form_rows(o, L)]


def _form_rows(o, L):
    """Every spelling of this lemma the source lists, with what each is.

    Two things are not in the `forms` list and have to be fetched from
    elsewhere or thrown away, and both were found by reading Japanese:

    THE READING IS IN THE HEAD TEMPLATE.  `犬` lists canonical, romanization,
    counter and an alternative kanji -- and not `いぬ`, which is how the word
    is actually written half the time.  It is in `head_templates[].args["1"]`,
    by Wiktionary's own convention for a language whose script needs one.
    Without it a kana-written sentence -- which is what a children's story
    is, and what a beginner reads -- matches nothing at all.

    An arg is taken only when every character of it is in the language's own
    script and it is not the word itself.  That is what keeps this general:
    a Latin-script language has no `chars` and contributes nothing, a
    romanisation is Latin and is excluded, and a gender or a number in some
    other language's template cannot look like a spelling.

    A FORM OF AN UNSPACED LANGUAGE CANNOT CONTAIN A SPACE.  `住む` came out
    with a "form" of `住む intransitive godan` -- the headword LINE, not a
    word -- which no lookup can ever match and which is pure weight.

    ONE ROW PER SPELLING AND MEANING, NOT PER SPELLING.  The same string is
    very often two forms -- walked is the past AND the past participle,
    German besucht the third person present AND the participle, èssere the
    canonical headword AND its own auxiliary -- and keeping only the first
    tag set lost the second.  Measured before this changed: the English past
    found for 8% of verbs instead of 99%, German's `participle past` gone on
    28% of verbs, Italian's essere and avere with no auxiliary row at all.
    Identical rows (the five Persian tables share their tags) still go.
    lookup._hits_for folds the several notes of one entry into one hit, so
    the reader still sees one entry.

    BUT THE HEAD LINE OUTRANKS THE TABLE FOR ONE SPELLING.  The head line
    (rows with no `source`) is what the page's editors wrote about the word;
    the conjugation table after it (`source: conjugation`) is generated, and
    says less: prendere's head line has `èssere` as `also auxiliary` -- only
    in the meaning "to happen unexpectedly" -- and its table has the same
    `èssere` as plain `auxiliary`, which read alone says prendere takes
    essere.  Spanish `tengo` is the head's `first-person present singular`
    and again the table's, Arabic يَذْهَبُ the head's `non-past` and again
    the table's third person.  So a table row whose spelling the head line
    already gave is left out, exactly as it always was; what (form, note)
    keeps is the head line's own repeats and the table's repeats of itself.

    AND ONLY A VERB'S TABLE IS KEPT CELL BY CELL.  lib/verbs reads a verb's
    table by what each cell is -- French inclus is the first person present
    AND the participle, finit the present AND the past historic -- and
    nothing reads an adjective's.  A German adjective fills a dozen cells
    with four spellings (freien is strong and weak, dative and genitive,
    singular and plural), and keeping every cell of it doubled German's
    adjective rows (+116% on 40 000 pages of the extract) for notes nobody
    is shown past the fourth.  A table that is not a verb's keeps its first
    cell per spelling, as it always did; its head line is kept whole.

    Each row carries its pronunciation where the source gives one -- French
    tables do, on 99.8% of conjugated verbs, and it is the only record of how
    `prends` or `aimons` is said.  A row with none borrows it from a row of
    the same spelling on the same page: `aime` the first person has no IPA in
    the source, `aime` the third has /ɛm/, and they are one word.
    """
    out, seen, spelt, headed = [], set(), set(), set()
    word = (o.get("word") or "").strip()
    verb = (o.get("pos") or "").strip() == "verb"
    # a word of this language written in Latin letters (Chinese OK, Japanese
    # GDP) spells its other forms in them too
    latin = _foreign(word, "", L)
    stem_past, kanji = [], []           # for _respelt, below
    stems = [(f.get("form") or "").strip() for f in o.get("forms") or []
             if "stem" in (f.get("tags") or []) and (f.get("form") or "").strip()]
    for f in o.get("forms") or []:
        w = (f.get("form") or "").strip()
        tags = [t for t in (f.get("tags") or [])
                if isinstance(t, str) and t not in NOT_A_FORM]
        if not w or w == "-" or len(w) > 120 or w in NOT_A_ROMAN:
            continue
        if set(f.get("tags") or []) & NOT_A_FORM:
            continue
        if (verb and f.get("source") and frozenset(tags) in _PERSON_COLUMN
                and stems and not any(x in w for x in stems)):
            continue            # من, تو, ما: a table's pronouns, not its forms
        if f.get("source"):
            if w in headed:
                continue        # the head line said it first, and better
            if w in spelt and not verb:
                continue        # a cell of a table nobody reads cell by cell
        else:
            headed.add(w)
            if verb and tags in (["stem"], ["past"]):
                stem_past.append((w, tags[0], (f.get("roman") or "").strip()))
            elif verb and {"alternative", "kanji"} <= set(tags):
                kanji.append(w)
        if not L.spaced and re.search(r"\s", w):
            continue
        note = " ".join(tags)
        if not latin and _foreign(w, note, L):
            continue
        # AN UNTAGGED REPEAT OF A SPELLING ALREADY TAGGED SAYS NOTHING, and
        # an empty note is what the headword's own row carries -- so it
        # would say the wrong thing.  هستند is `present` in بودن's head row
        # and again as a bare cell of a later table; kept, it made the
        # lookup believe هستند WAS بودن.
        if not note and w in spelt:
            continue
        if (w, note) not in seen:
            seen.add((w, note))
            spelt.add(w)
            ipa = f.get("ipa")
            out.append((w, note, (f.get("roman") or "").strip(),
                        ipa.strip() if isinstance(ipa, str) else ""))
    heard = {}
    for w, _t, _r, ipa in out:
        if ipa:
            heard.setdefault(w, ipa)
    out = [(w, t, r, ipa or heard.get(w, "")) for w, t, r, ipa in out]
    for w, t, r in _respelt(word, stem_past, kanji):
        if (w, t) not in seen and not (not L.spaced and re.search(r"\s", w)):
            seen.add((w, t))
            spelt.add(w)
            out.append((w, t, r, ""))
    if verb:
        out = _modern_glides(out, word, seen, spelt)
    if L.re_chars is not None:
        for h in o.get("head_templates") or []:
            for k in ("1", "2", "3", "head"):
                # `%` and `^` are Wiktionary's own markers inside a reading --
                # they say where the okurigana boundaries fall, so `お爺さん`
                # reads `お%じい%さん`.  Leaving them in was why every polite
                # noun's reading failed the script test and was dropped, and
                # why `おじいさん` in a children's story matched nothing.
                v = str((h.get("args") or {}).get(k) or "").replace("%", "")
                v = v.replace("^", "").strip()
                if (not v or v == word or v in spelt or len(v) > 40
                        or not all(L.re_chars.match(ch) for ch in v)):
                    continue
                spelt.add(v)
                out.append((v, "another spelling", "", ""))
    return out


# HOW A BUILD'S TIME DIVIDES, for the bar: reading the extract, then linking
# the form pages, then the VACUUM.  Measured on Turkish (a 435 MB extract,
# 2026-09-25): 13.1 s reading, 0.9 s linking and vacuuming together.
READ_SHARE, LINK_SHARE = 0.90, 0.05      # and the VACUUM the last 0.05


def convert(path, code, db_path, limit=0, say=print, progress=None,
            cancel=None):
    """One JSONL extract into one dictionary.  Returns how many entries.

    `progress(done, total, "build")` and `cancel` as lib/download.py means
    them: the bar is the extract's bytes, and Stop is honoured between any
    two lines (download.Cancelled; the caller removes the half-built file).

    THE FILE IS CLOSED HOWEVER THE BUILD ENDS, Stop included: the caller
    deletes the half-built file next, and Windows will not delete a file
    that is still open.
    """
    c = lookup.create(db_path)
    try:
        return _convert(c, path, code, limit, say, progress, cancel)
    finally:
        c.close()


def _convert(c, path, code, limit, say, progress, cancel):
    L = languages.get_or_default(code)
    accepted = accepted_codes(L)
    n = skipped = 0
    # (surface, lemma word, note, kind, the page's pos, how the page's own
    # word is romanised, how it is said)
    pending = []
    t0 = time.time()
    # ONE BAR FOR THREE STEPS.  Reading the extract is most of a build, and
    # its bytes are the one count known before it starts; the linking pass
    # and the VACUUM after it are given the rest of the bar in the shares
    # measured above READ_SHARE.
    meter = download.Meter(progress, cancel, total=os.path.getsize(path))
    reading, linking = meter.share(0, READ_SHARE), \
        meter.share(READ_SHARE, READ_SHARE + LINK_SHARE)
    size = float(meter.total or 1)
    got = 0
    # Read as bytes and decoded a line at a time, which is what the text
    # mode did, so that the bytes read so far are a sum and not a seek.
    with io.open(path, "rb") as f:
        for raw in f:
            got += len(raw)
            reading(got / size)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            word = (o.get("word") or "").strip()
            if not word or len(word) > 120:
                skipped += 1
                continue
            if o.get("lang_code") and o["lang_code"] not in accepted:
                skipped += 1          # a file that carries more than it says
                continue
            senses, of = _senses(o)
            pos = (o.get("pos") or "").strip()
            if of:
                said, heard = _said(o, L.code), _ipa(o, L.code)
            for lemma, note in of:
                pending.append((word, lemma, note, "form", pos, said, heard))
            # A SOFT REDIRECT IS A SPELLING, and it was being thrown away.
            # Wiktionary keeps its Chinese under the traditional characters
            # and gives the simplified ones a page of their own that says
            # only `{"word": "买", "redirects": ["買"], "pos":
            # "soft-redirect"}` -- no gloss, no form_of, nothing _senses can
            # see, so the entry was dropped and 买 (to buy), 书 (a book),
            # 读 (to read), 话 (speech) and 谁 (who) could not be looked up
            # at all in the script the language is actually written in.
            # Measured on Chinese: 88% of a list of common words before,
            # 100% after.
            #
            # ONLY FROM A PAGE THAT HAS NOTHING TO SAY OF ITS OWN.
            # `redirects` is not a spelling field: on a page that HAS glosses
            # it carries whatever the etymology cross-refers to, so taking it
            # everywhere told a reader that 明 (bright) and 夕 (evening) were
            # other spellings of 月 (moon) -- 122 209 rows of that, on the
            # commonest characters in the language.
            #
            # THE TEST IS THE GLOSSES AND NOT THE `pos`.  Asking for
            # `pos == "soft-redirect"` looked tighter and was wrong: 买 has
            # that pos, but 书, 谁, 话 and 读 are `pos: "character"` with no
            # gloss and a `redirects` -- the same kind of page wearing a
            # different label -- and requiring the label lost them again.
            # A page with no gloss of its own is not saying anything except
            # where to look instead.
            if not senses:
                for target in (o.get("redirects") or []):
                    target = str(target).strip()
                    if target and target != word:
                        pending.append((word, target, "another spelling",
                                        "spelling", pos, "", ""))
            if not senses:
                senses = _own_table_senses(o)     # yapılmak: see OWN_TABLE
            if not senses:
                continue              # a page that is only a form: its rows are above
            keep = senses[:12]
            # A VERB'S REFLEXIVE MEANINGS COME LAST, and the cap cut them.
            # Spanish lists the pronominal senses after the plain ones, so
            # twelve of `ir` were all plain and irse came out "to go (away
            # from speaker and listener)"; ir, hacer, tener, salir, dejar and
            # ten more lost every reflexive sense they had.  They are what
            # a reader of `se fue` is looking at.
            if pos == "verb":
                keep += [x for x in senses[12:]
                         if {"reflexive", "pronominal"} & set(x[1].split(","))]
            cur = c.execute(
                "INSERT INTO entry (headword, translit, ipa, reading, pos, "
                "sense, sense_tags, head) VALUES (?,?,?,?,?,?,?,?)",
                (word, _translit(o), _ipa(o, L.code), _reading(o, L), pos,
                 "\n".join(g for g, _t in keep),
                 "\n".join(t for _g, t in keep),
                 _head(o, L)))
            eid = cur.lastrowid
            rows = ([(word, eid, "", "", "")]
                    + [(w, eid, t, r, i) for w, t, r, i in _form_rows(o, L)])
            c.executemany("INSERT INTO form (form, entry_id, note, roman, ipa) "
                          "VALUES (?,?,?,?,?)", _folded(rows, L, word))
            n += 1
            if n % 20000 == 0:
                say("    %d entries (%.0fs)" % (n, time.time() - t0))
            if limit and n >= limit:
                break

    # the pages that are nothing but "genitive singular of X": now that every
    # lemma is in, point them at it
    say("    linking %d inflected forms" % len(pending))
    made, linked = 0, set()
    every = float(len(pending) or 1)
    for i, (surface, lemma, note, kind, pos, said, heard) in enumerate(pending):
        linking(i / every)
        # A ROW THE LANGUAGE'S OWN SCRIPT CANNOT CONTAIN is refused here as
        # it is on the lemma's own page (`_foreign`); a Japanese rōmaji page
        # says so in its note and stays, and so does `ok` pointing at
        # Chinese `OK`.
        if _foreign(surface, note, L) and not _foreign(lemma, "", L):
            continue
        # THE HOMOGRAPH WITH THE SAME PART OF SPEECH.  The first entry with
        # the lemma's spelling used to take every pointer: helped landed on
        # help the noun, खाया on खाना the noun (food), will on the adjective
        # wollen, and Turkish `ek` -- imperative of ekmek, to sow -- on
        # ekmek, bread.  The pointer page says what it is a form of; a verb
        # form of a verb goes to the verb.
        row = c.execute("SELECT id FROM entry WHERE headword = ? "
                        "ORDER BY (pos = ?) DESC, id LIMIT 1",
                        (lemma, pos)).fetchone()
        # once per page, lemma and note: गया's first sense names जाना twice
        # (`inflection of जाना (jānā)`, with the romanisation as a second
        # link), and each was a row of its own
        if row is None or (surface, row[0], note) in linked:
            continue
        linked.add((surface, row[0], note))
        # A WORD THAT STANDS ON ITS OWN IS NOT MERELY SOMEBODY ELSE'S
        # SPELLING.  Wiktionary redirects 日 to 時 as a second-round
        # simplification abandoned in 1977, and 日 is the sun -- so a reader
        # looking it up was offered `time` as well.  An inflection pointer is
        # different and is kept: a page that is only "genitive singular of X"
        # says so because the surface has no entry of its own.
        if kind == "spelling" and c.execute(
                "SELECT 1 FROM entry WHERE headword = ? LIMIT 1",
                (surface,)).fetchone():
            continue
        # THE SAME WORD, SPELT WITH AND WITHOUT ITS ZERO-WIDTH JOINER.  The
        # source's own form table has `میسازم` with its romanisation, and a
        # `form of` page has `می‌سازم` with none -- and the text a reader
        # meets is the second.  So a pointer row borrows the romanisation of
        # a row of the same entry that is the same word once the joiners are
        # taken out; without it the reader was shown the infinitive.
        got = c.execute(
            "SELECT roman FROM form WHERE entry_id = ? AND roman != '' AND "
            "replace(replace(form, char(8204), ''), char(8205), '') = "
            "replace(replace(?, char(8204), ''), char(8205), '') LIMIT 1",
            (row[0], surface)).fetchone()
        # AND WHERE THE LEMMA'S TABLE HAS NO SUCH ROW, THE PAGE'S OWN.  जाना
        # has no table on its page, so गया -- its perfective, and the word a
        # Hindi reader meets -- borrowed nothing and was shown with the
        # infinitive's sound; its own page says `gayā`.  The page's
        # pronunciation goes in too (helped /hɛlpt/), which is the only
        # record of how an English past is said.
        c.executemany("INSERT INTO form (form, entry_id, note, roman, ipa) "
                      "VALUES (?,?,?,?,?)",
                      _folded([(surface, row[0], note,
                                got[0] if got else said, heard)], L))
        made += 1
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)", [
        ("lang", L.code), ("language", L.name),
        ("variety", L.variety_name if L.variety else ""),
        ("source", SOURCE), ("licence", LICENCE), ("url", url_for(L)),
        ("built", time.strftime("%Y-%m-%d")),
        ("entries", str(n)), ("forms", str(made)),
    ])
    c.commit()
    linking(1.0)
    c.execute("VACUUM")
    c.close()
    meter.end()
    say("    %d entries, %d inflected forms linked, %d lines skipped"
        % (n, made, skipped))
    return n


def _folded(rows, L=None, head=None):
    """Each form row, plus its folded spelling when that differs.

    lib/lookup.py tries the surface form first and the folded one second, and
    tells the reader which of the two answered; both have to be in the table
    for that to mean anything -- so the fold is lookup's own (`_fold`), and
    never a second copy of it that could drift.

    THE MARKS GO, NOT ONLY THE CASE.  Arabic form rows are written vowelled
    and nothing else -- يَقُولُ, أُرِيدُ -- while a video's captions and an
    unvowelled page write يقول and أريد, which matched no row at all: only
    the bare page title did, and it returned every homograph of it.  lookup
    takes the harakat off what it reads (the registry's `strip` range), so
    the bare spelling of each row is stored as a row of its own, same entry,
    note and romanisation.  And the case goes the way lookup takes it off:
    str.casefold() writes the small of Turkish İ as i + U+0307, so `İzmir`
    was stored as a spelling no folded text could ever be.

    NOT WHERE IT IS ONLY THE HEADWORD AGAIN.  `head` is the entry's own
    word, whose row (note '') is in `rows` and is folded like any other.  A
    noted row that folds to that same spelling -- the vowelled `canonical`
    row مَن, كَتَبَ, whose bare spelling is the page title -- would reach
    nothing the headword does not, and would hang its note on every lookup
    of the word: the panel said `من (canonical)`.
    """
    fold = (lambda w: lookup._fold(w, L)) if L is not None else str.casefold
    same = fold(head) if head else None
    out, seen = [], set()
    for form, eid, note, roman, ipa in rows:
        for v in (form, fold(form)):
            if v != form and note and same is not None and v == same:
                continue
            k = (v, eid, note, roman, ipa)
            if v and k not in seen:
                seen.add(k)
                out.append(k)
    return out


def fetch(L, dest, say=print, progress=None, cancel=None):
    """Download the extract, reporting as it goes: these are big files and a
    silent hour is indistinguishable from a hang.

    RESUMED, NOT RESTARTED (TO-DO §11.4).  Turkish's extract is 431 MB and
    German's a gigabyte, and a line that dropped at 80% used to cost the
    whole of it again -- and worse, left a truncated extract at `dest`
    that the next build took for a whole one.  lib/download.py writes to
    `dest.part` and renames only a complete file, and the next fetch asks
    kaikki for the rest; Stop (`cancel`) is download.Cancelled, and keeps
    what came."""
    urls = urls_for(L)
    if len(urls) > 1:
        # A VARIETY OF SEVERAL EXTRACTS is fetched one file at a time beside the
        # first and joined into `dest`, which the build then reads as one: the
        # parts are kept until the whole is there, so Stop loses nothing
        parts = []
        for n, url in enumerate(urls):
            part = "%s.%d" % (dest, n)
            if not os.path.isfile(part):
                _fetch_one(url, part, say, progress, cancel)
            parts.append(part)
        with open(dest + ".join", "wb") as out:
            for part in parts:
                with open(part, "rb") as f:
                    shutil.copyfileobj(f, out)
        os.replace(dest + ".join", dest)
        for part in parts:
            os.unlink(part)
        return
    _fetch_one(urls[0], dest, say, progress, cancel)


def _fetch_one(url, dest, say, progress, cancel):
    say("  %s" % url)
    try:
        download.fetch(url, dest, say=say, progress=progress, cancel=cancel)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SystemExit(
                "getdict: kaikki has no extract at\n  %s\n"
                "Check the language's English name in lib/languages.json -- "
                "that is what the URL is built from." % url)
        raise SystemExit("getdict: %s" % e)
    except OSError as e:
        raise SystemExit("getdict: could not download (%s).  What came is "
                         "kept: the next try carries on from there." % e)


def _extract_for(L):
    """Where this language's extract is downloaded to, and kept by --keep."""
    return os.path.join(lookup.DICT_DIR, "%s.jsonl" % L.key)


def plan(code, src=None, limit=0, keep=False, out=None, *, probe=True):
    """What building this dictionary will cost, before anything is fetched:
    lib/download.py's plan() shape -- the download, whether that size is the
    MEASURED table's, the most room it needs at once, and what it keeps.

    The same arguments as build(), and `probe=False` for an answer that
    sends nothing anywhere (a page drawing its rows asks nobody): a
    language the table does not measure then has no download size.

    THE PEAK IS THE EXTRACT AND THE DICTIONARY TOGETHER: the one is read
    while the other is written beside the old one (about 740 MB for
    Turkish).  Where the built size is not measured, it is taken to be the
    extract's own -- a bound, not a guess: of every language measured, none
    built bigger than its extract (Turkish 306 of 431 MB, German 342 of
    1 077)."""
    L = languages.get_or_default(code)
    dl, kept = MEASURED.get(L.key, (None, None))
    measured, have = dl is not None, 0
    if src is not None:                   # built from a file already here
        dl, measured, bound = 0, False, os.path.getsize(src)
    else:
        tmp = _extract_for(L)
        if os.path.isfile(tmp):           # a whole extract, kept from before
            dl = have = os.path.getsize(tmp)
            measured = False
        else:
            have = download.leftover(tmp)
            if dl is None and probe:
                # every file of a variety of several (Levantine is two), summed
                sizes = [download.probe(u) for u in urls_for(L)]
                dl = sum(sizes) if all(x is not None for x in sizes) else None
        bound = dl
    built = kept if kept is not None else bound
    peak = None
    if dl is not None and built is not None:
        peak = max(dl - have, 0) + built
    if keep and src is None and kept is not None and dl is not None:
        kept += dl
    return download.plan(dl, measured=measured, kept=kept, have=have,
                         peak=peak)


def discard(code):
    """Throw away this language's extract: one cut short, waiting to be
    resumed, or a whole one left by a build that was stopped (or kept by
    --keep).  Returns the bytes freed; the dictionary itself is untouched."""
    tmp = _extract_for(languages.get_or_default(code))
    freed = download.leftover(tmp)
    download.discard(tmp)
    if os.path.isfile(tmp):
        freed += os.path.getsize(tmp)
        os.unlink(tmp)
    return freed


def build(code, src=None, limit=0, keep=False, say=print, out=None,
          progress=None, cancel=None):
    """Build this language's dictionary, from the download or from `src`.

    `out` puts it somewhere other than dict/<code>.db.  A test, or anybody
    checking what a change to this file does, builds from a sample of the
    extract into a scratch file -- and rebuilding the reader's own dictionary
    to find out was the only way there used to be.  Same conversion, same
    atomic rename, a different place.

    `progress(done, total, phase)` hears the download ("download") and then
    the build ("build"); `cancel` stops either, as download.Cancelled: an
    interrupted download is kept to be resumed, a half-built dictionary is
    removed, and the one that was there before is untouched.
    """
    L = languages.get_or_default(code)
    if out:
        db = os.path.abspath(out)
        os.makedirs(os.path.dirname(db), exist_ok=True)
    else:
        os.makedirs(lookup.DICT_DIR, exist_ok=True)
        db = lookup.path_for(L.key)
    tmp = None
    if src is None:
        tmp = _extract_for(L)
        os.makedirs(lookup.DICT_DIR, exist_ok=True)
        if os.path.isfile(tmp):
            say("  using the download already here: %s" % os.path.relpath(tmp, ROOT))
        else:
            fetch(L, tmp, say, progress=progress, cancel=cancel)
        src = tmp
    # BUILT BESIDE THE OLD ONE AND MOVED OVER IT.  lookup.create() unlinks
    # its target before it writes, so building straight onto dict/<code>.db
    # meant a download that failed at 80%, a bad extract or a Ctrl-C left the
    # reader with no dictionary at all -- having had a working one a minute
    # earlier.  The rename is atomic on every filesystem the toolbox runs on,
    # so the old file stands until the new one is whole.
    say("  building %s" % (os.path.relpath(db, ROOT)
                           if db.startswith(ROOT + os.sep) else db))
    part = db + ".part"
    try:
        n = convert(src, L.key, part, limit=limit, say=say,
                    progress=progress, cancel=cancel)
        os.replace(part, db)
    except BaseException:
        if os.path.isfile(part):
            os.unlink(part)
        raise
    if tmp and not keep and os.path.isfile(tmp):
        os.unlink(tmp)
    say("  %s: %s, %.0f MB" % (L.name, "{:,}".format(n).replace(",", " "),
                               os.path.getsize(db) / 1e6))
    return n


def status(say=print):
    say("Dictionaries, in %s/" % os.path.relpath(lookup.DICT_DIR, ROOT))
    say("")
    for L in languages.LANGS.values():
        m = lookup.about(L.code)
        if m:
            say("  %-3s %-9s %8s entries  %s  %s"
                % (L.code, L.name, m.get("entries", "?"),
                   m.get("built", ""), m.get("source", "")))
        else:
            say("  %-3s %-9s  --        python3 lib/getdict.py %s"
                % (L.code, L.name, L.code))
    say("")
    say("Nothing here is required.  A language without one is read exactly as")
    say("it is read today; the lookup simply is not offered for it.")


def main():
    p = argparse.ArgumentParser(prog="getdict", description=__doc__.splitlines()[0])
    p.add_argument("code", nargs="?", help="the language, or --all")
    p.add_argument("--all", action="store_true", help="every language in the registry")
    p.add_argument("--from", dest="src", help="a kaikki JSONL already downloaded")
    p.add_argument("--limit", type=int, default=0, help="stop after N entries (for a trial)")
    p.add_argument("--keep", action="store_true", help="keep the downloaded JSONL")
    p.add_argument("--out", help="write the dictionary to this file instead of "
                                 "dict/<code>.db (a sample, a test)")
    a = p.parse_args()
    if a.all and a.out:
        raise SystemExit("getdict: --out names one file, and --all builds "
                         "every language")
    if a.all:
        for L in languages.LANGS.values():
            print("== %s" % L.name)
            try:
                build(L.code, limit=a.limit, keep=a.keep)
            except SystemExit as e:
                print("  %s" % e)
        return 0
    if not a.code:
        status()
        return 0
    if a.code not in languages.LANGS:
        raise SystemExit("getdict: %r is not a language in the registry; "
                         "run with no arguments to see them" % a.code)
    build(a.code, src=a.src, limit=a.limit, keep=a.keep, out=a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
