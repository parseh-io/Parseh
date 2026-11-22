#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Devanagari to the Roman of the dictionaries.

    import translit
    translit.deva_to_iast("एवं मे सुतं")      -> "evaṃ me sutaṃ"

WHY THIS EXISTS, AND WHY ONLY FOR ONE SCRIPT.  lib/lookup.py needs the form a
dictionary is keyed by, and that is not always the form on the page.  The
case this was written for is a dictionary keyed in the Roman of the
scholarly editions while the edition itself prints Devanagari -- which is
what Wiktionary does with the classical Indic languages, keeping the
meanings under the romanised lemma and leaving the Devanagari page as a
pointer at it.  Measured on the extract this was built against, the Roman
entries outnumbered the Devanagari ones six to one (9129 against 1473), so a
lookup without this missed six times out of seven.

It is safe to do here and it would not be safe for most scripts, because
Devanagari spelling of the classical Indic languages is PHONEMIC: one
letter, one sound, no silent letters, no ambiguity to resolve.  The
transliteration is a table walk and a rule about the inherent vowel, and the
answer is the same answer every edition prints.  Nothing of the kind is true
of, say, Arabic script, where the vowels are not written; there is no
function here for it and there should not be.

WHAT IT IS NOT FOR.  Not for showing a reader -- the transliteration a reader
sees is the one an annotator wrote, in the `tr` field, under the conventions
of docs/lang/<code>.md, which is a person's reading and not a table's.  This
is a lookup key and lives where lookup keys live.

WHO CALLS IT.  Whichever language asks, by setting `"fold": "deva-iast"` in
its lib/lang/<code>.lookup.json -- and no language shipped today does, so
this waits for the next one that is printed in Devanagari and looked up in
Roman.  HINDI takes the same walk and gets a defensible answer, but Hindi's
dictionary is in Devanagari already, so it does not ask.  It would in any
case be the wrong answer for Hindi, whose inherent vowel is very often not
pronounced (`कमल` is *kamal*, not *kamala*, docs/lang/hi.md) -- a rule this
does not know and deliberately does not guess at.

THE OTHER HALF IS FOR SHOWING, and is the dictionary's sound written the
way the edition writes one: `from_ipa` walks a pronunciation through the
language's table (lib/lang/<code>.ipa.json) or its own respelling (French,
`respell_fr`); `tidy_roman` puts a romanisation the source gives into the
edition's letters; `form_sound` chooses, among the rows that reached a word,
which of them says how THAT word is said.  None of it guesses: a language
with no ipa.json has no sound here, and says nothing rather than something
wrong.
"""
import io
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))

# The independent vowels, which stand alone at the head of a word.
VOWELS = {
    "अ": "a", "आ": "ā", "इ": "i", "ई": "ī", "उ": "u", "ऊ": "ū",
    "ऋ": "r̥", "ॠ": "r̥̄", "ऌ": "l̥", "ऍ": "ê", "ऎ": "e",
    "ए": "e", "ऐ": "ai", "ऑ": "ô", "ऒ": "o", "ओ": "o", "औ": "au",
}

# The dependent vowel signs, which replace a consonant's inherent `a`.
MATRAS = {
    "ा": "ā", "ि": "i", "ी": "ī", "ु": "u", "ू": "ū",
    "ृ": "r̥", "ॄ": "r̥̄", "ॢ": "l̥",
    "ॅ": "ê", "ॆ": "e", "े": "e", "ै": "ai",
    "ॉ": "ô", "ॊ": "o", "ो": "o", "ौ": "au",
}

# The consonants, each carrying an inherent `a` that a matra or a virama
# takes away.  ळ is in the list because the classical languages use it and
# Hindi effectively does not -- dropping it would silently turn `कीळति` into
# `kīati`.
CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ṅ",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ñ",
    "ट": "ṭ", "ठ": "ṭh", "ड": "ḍ", "ढ": "ḍh", "ण": "ṇ",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "ऩ": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ऱ": "r", "ल": "l", "ळ": "ḷ", "ऴ": "ḷ",
    "व": "v", "श": "ś", "ष": "ṣ", "स": "s", "ह": "h",
    # the nukta letters, which the classical languages have none of and Hindi
    # writes for the Perso-Arabic layer; docs/lang/hi.md settles what each
    # stands for
    "क़": "q", "ख़": "x", "ग़": "ġ", "ज़": "z", "ड़": "ṛ", "ढ़": "ṛh",
    "फ़": "f", "य़": "y",
}

VIRAMA = "्"
SIGNS = {
    "ं": "ṃ",        # anusvāra -- the nasal, Hindi's and the canon's alike
    "ँ": "ṁ",        # candrabindu
    "ः": "ḥ",        # visarga
    "ऽ": "'",        # avagraha, the mark Devanagari prints for an elided a
    "़": "",         # a bare nukta, when it did not compose into a letter
    "्": "",         # a trailing virama (a half-form at the end of a word)
}

_DEVA = re.compile(r"[ऀ-ॿ᳐-᳿꣠-ꣿ]")


def has_devanagari(s):
    return bool(_DEVA.search(s or ""))


def deva_to_iast(s):
    """One Devanagari string in the Roman of the dictionaries.

    Anything that is not Devanagari -- a space, a Latin letter, a digit, a
    danda -- comes through as it is, so a mixed line is not destroyed.  The
    text is composed first (NFC), because `क़` reaches this either as one
    code point or as `क` plus a nukta and the two must not transliterate
    differently.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    out = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in CONS:
            out.append(CONS[ch])
            i += 1
            # what follows the consonant decides its vowel: a virama kills
            # it, a matra replaces it, anything else leaves the inherent `a`
            if i < n and s[i] == VIRAMA:
                i += 1
            elif i < n and s[i] in MATRAS:
                out.append(MATRAS[s[i]])
                i += 1
            else:
                out.append("a")
            continue
        if ch in VOWELS:
            out.append(VOWELS[ch])
            i += 1
            continue
        if ch in SIGNS:
            out.append(SIGNS[ch])
            i += 1
            continue
        if ch in MATRAS:
            # a matra with no consonant before it is a broken string; keep
            # the sound rather than dropping it silently
            out.append(MATRAS[ch])
            i += 1
            continue
        if ch == "।":
            out.append(".")
            i += 1
            continue
        if ch == "॥":
            out.append("||")
            i += 1
            continue
        if "०" <= ch <= "९":            # the Devanagari figures
            out.append(chr(ord(ch) - 0x0966 + 0x30))
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tidy_roman(code, s, head=""):
    """A romanisation the source gives, written the way this edition writes.

    THE ONE THING A PRONUNCIATION CANNOT GIVE.  IPA is recorded per lemma, so
    it romanises `ساختن` and never `می‌سازمت`; the source's FORM table does
    carry the inflected form -- میسازم is `mí-sâzam` -- which is exactly what
    a reader meeting that word needs, and exactly what a model asked to
    invent it got wrong (it answered with the infinitive).

    The conventions differ in two small ways and both are mechanical: the
    source marks stress with an acute and this edition marks none, and it
    writes long a as â where this edition writes ā.  The acute goes FIRST,
    because stripping combining marks afterwards would take the macron of ā
    with it.

    A LETTER NO WORD OF THE EDITION BEGINS WITH (`roman.drop_initial`) goes
    last, at the start of the string and after every space: Wiktionary writes
    Arabic's hamza on every word that begins with a vowel -- أَرَى is `ʔarā`,
    which the map makes `ʾarā` -- and docs/lang/ar.md writes `arā`, keeping
    the hamza only inside a word, where it is a consonant somebody says
    (`saʾala`).  After the map, so that it is the edition's own letter that
    is dropped whichever of the two the source wrote.

    EXCEPT WHERE THE WORD IS WRITTEN WITH A LETTER THAT IS SAID AS THAT
    HAMZA (`roman.keep_initial`, letters of the script, and `head`, the
    word as written): Egyptian and Levantine say ق as a glottal stop, and
    the Egyptian dictionary's قلب is `ʔalb`, whose ʾ is the word's first
    consonant, not a vowel's onset.  Only the first word's.
    """
    R = (ipa_rules(code).get("roman") or {})
    if not s or not R:
        return s or ""
    drop = set(R.get("drop_marks") or ())
    out = "".join(ch for ch in unicodedata.normalize("NFD", s)
                  if ch not in drop)
    out = unicodedata.normalize("NFC", out)
    for a, b in (R.get("map") or {}).items():
        out = out.replace(a, b)
    lead = R.get("drop_initial") or ""
    if lead:
        keep = R.get("keep_initial") or ""
        first = (head or "").strip()[:1]
        kept = ""
        if keep and first and first in keep:
            m = re.match(r"[%s]+" % re.escape(lead), out)
            kept = m.group(0) if m else ""
        out = kept + re.sub(r"(^|\s)[%s]+" % re.escape(lead), r"\1", out[len(kept):])
    return out


def in_variety(key, s):
    """A romanisation of the standard language, said as a variety says its
    letters -> the same string where the variety says nothing.

    For the standard dictionary's hits shown in a text written in a variety
    (lib/lookup.py _said_in_variety): `from_standard.map` in the variety's
    lib/lang/<key>.ipa.json, letters of the standard romanisation to the
    variety's, each correspondence cited in that file.  The standard
    romanisation writes one letter for one Arabic letter (q for ق, j for ج,
    ṯ ḏ ẓ for ث ذ ظ), so the walk is a letter for a letter; vowels and
    endings are not touched.  A key with no file (`ar`, any language without
    varieties) gets `s` back unchanged."""
    if not s or "." not in (key or ""):
        return s or ""
    M = ((ipa_rules(key).get("from_standard") or {}).get("map") or {})
    if not M:
        return s
    out = unicodedata.normalize("NFC", s)
    return "".join(M.get(ch, ch) for ch in out)


def form_sound(code, romans, ipas=(), words=False, head=""):
    """How a form the text holds is said, as this edition writes it, from
    the rows that reached it -- "" where none of them says.

    `romans` and `ipas` are those rows' two columns, in the source's order.
    What the lemma's pronunciation cannot give is exactly this: `said`
    romanises ساختن, and the word on the page is می‌سازم.

    THE SOURCE'S ROMANISATION FIRST, AND THE FIRST ROW'S, as it always was --
    except where the language says which register it wants (`roman.prefer`,
    a pattern) and where one reading of a cell ends and the next begins
    (`roman.after_last`).  Wiktionary's Persian writes the Dari table before
    the Iranian one for some verbs, so the first row of نمی‌دانستم was
    `dānistam`, and it gives both readings in one cell as `būd /bud`, the
    classical first: the first reading that matches is taken, and failing
    one the first row's, cut at its last /.  An EMPTY first row stays
    empty: بدهید's first row carries no romanisation and its later ones are
    Dari (`bídihēd`), and printing those as the word's sound is what the
    first-row rule was written against.

    THE FORM'S OWN PRONUNCIATION ONLY WHERE THERE IS NO ROMANISATION AT ALL,
    written the way the language writes one: a French conjugation row has
    none and carries its IPA (vint /vɛ̃/ is `vẽ`).  Not in place of one: a
    pointer page's IPA is the page's first pronunciation, and the page may
    be another word's -- و, colloquial را `o`, carries /vɑːv/, the name of
    the letter.
    """
    R = ipa_rules(code).get("roman") or {}
    cut = R.get("after_last") or ""
    got = []
    for r in romans:
        r = (r or "").strip()
        if cut and cut in r:
            r = r.rsplit(cut, 1)[1].strip()
        got.append(r)
    want = _pattern(R.get("prefer") or "")
    if want is not None:
        for r in got:
            if r and want.search(unicodedata.normalize("NFC", r)):
                return tidy_roman(code, r, head)
    if got and got[0]:
        return tidy_roman(code, got[0], head)
    if any(got):
        return ""
    for ipa in ipas:
        s = from_ipa(code, ipa or "", words) if ipa else ""
        if s:
            return s
    return ""


_PATTERNS = {}


def _pattern(src):
    """A language file's pattern, compiled once; None where there is none
    or it does not compile (a typo in a data file costs the preference, not
    the lookup)."""
    if not src:
        return None
    if src not in _PATTERNS:
        try:
            _PATTERNS[src] = re.compile(src)
        except re.error:
            _PATTERNS[src] = None
    return _PATTERNS[src]


# ------------------------------------------------ pronunciation -> the page
_IPA = {}


def _read_ipa(key):
    try:
        with io.open(os.path.join(HERE, "lang", "%s.ipa.json" % key), encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def ipa_rules(code):
    """How this language turns a pronunciation into its own transliteration:
    lib/lang/<code>.ipa.json, optional like every file of that name.

    A VARIETY'S FILE FIRST AND THE LANGUAGE'S AFTER IT (`code` a variety's key,
    ar.egy, lib/languages.py with_variety), as lookup reads its rules: a
    section both have (`roman`) is the language's with the variety's keys
    over it, and whatever the variety does not say is the language's."""
    if code not in _IPA:
        d = _read_ipa(code)
        base, dot, _v = (code or "").partition(".")
        if dot:
            own, d = d, dict(_read_ipa(base))
            for k, v in own.items():
                d[k] = dict(d[k], **v) if isinstance(v, dict) and isinstance(d.get(k), dict) else v
        _IPA[code] = d
    return _IPA[code]


def prefers(code):
    """(wanted, unwanted) pronunciation tags for this language.

    WHY A LANGUAGE HAS MORE THAN ONE.  Wiktionary gives Persian five --
    Classical-Persian, Dari, Kabuli, Tajik, Iran -- and the source's own
    romanisation field is the CLASSICAL one.  That is where `kitāb`,
    `xwāndan` and `dōst` come from: correct romanisations of a Persian nobody
    in Tehran speaks, copied faithfully into every gloss.  A language says
    here which reading its editions are written in.
    """
    R = ipa_rules(code)
    return (tuple(R.get("prefer") or ()), tuple(R.get("avoid") or ()))


def speaks(code):
    """Can `from_ipa` write this language's pronunciations at all -- by a
    table (`map`) or by a respelling of its own (`respell`)?"""
    R = ipa_rules(code)
    return bool(R.get("map")) or R.get("respell") in RESPELL


def from_ipa(code, ipa, words=False):
    """A pronunciation, as this edition writes it -> "" where it cannot be.

    The whole point of asking the dictionary rather than a model: a
    transliteration is a mechanical fact about a pronunciation, and the
    pronunciation is in the dictionary for four words in five.  A 4B model
    asked to invent one produces the register it saw most of in training,
    which for Persian is the classical one.

    A LANGUAGE A TABLE CANNOT WRITE names its respelling instead
    (`"respell": "fr"`, and RESPELL below): French needs the final-schwa, the
    elision-and-liaison and the no-double rules, and its nasal vowels are a
    vowel and a combining tilde that the table walk strips as a diacritic of
    manner -- ɑ̃ ɛ̃ ɔ̃ came out a è ò.

    `words` says the pronunciation is of several words, for a headword or a
    form that is several.  The table walk drops a space like any other
    separator, so فکر کردن came out `fekrkardan`, and the \\dw the sidebar
    wrote for it printed that: each word is walked on its own now, so the
    rule about a leading glottal stop is a rule about each word, as it should
    be.  A respelling is handed the ties (‿) only then: in one word a tie is
    an elision the spelling has (aujourd'hui, jusqu'à), and the respelling
    would have read it as a liaison and hyphenated the word.
    """
    R = ipa_rules(code)
    how = RESPELL.get(R.get("respell") or "")
    if how is not None:
        # a tie inside ONE word is an elision the word is spelt with, not a
        # liaison to the next: aujourd'hui /o.ʒuʁ.d‿ɥi/ came out `oʒou-rdüi`
        return how((ipa or "") if words else (ipa or "").replace("‿", ""))
    table = R.get("map") or {}
    if not table or not ipa:
        return ""
    if words and len(ipa.split()) > 1:
        return " ".join(w for w in (from_ipa(code, p) for p in ipa.split()) if w)
    drop = set(R.get("drop") or "")
    # the combining marks a narrow transcription carries: dentalisation,
    # devoicing, the acute of a stressed syllable.  They say how a sound is
    # made, not which sound it is.
    text = "".join(ch for ch in unicodedata.normalize("NFD", ipa)
                   if not unicodedata.combining(ch) and ch not in drop)
    keys = sorted(table, key=len, reverse=True)
    out, i = [], 0
    while i < len(text):
        for k in keys:
            if k and text.startswith(k, i):
                out.append(table[k])
                i += len(k)
                break
        else:
            ch = text[i]
            out.append("" if unicodedata.category(ch)[0] in "PZC" else ch)
            i += 1
    got = "".join(out).strip()
    # a sound every word of this language begins with is not written down
    for ch in (R.get("strip_leading") or ""):
        if got.startswith(ch):
            got = got[1:]
            break
    return got


# ------------------------------------------------- French, by its own rules
# IPA to the respelling of docs/lang/fr.md.  One letter or two per sound, as
# the file's own tables give them; /ɑ/ is /a/ there (the scheme has one a),
# and the nasals are the vowel and its tilde, which NFD keeps apart.
# Written for lib/verbs/fr.py, which prints a sound in every slot of a \vb,
# and moved here when the reading panel wanted the same sounds: a French hit
# had none at all (no table can write French, see `from_ipa`), and the
# sidebar's \dw for a French noun went out with an empty sound.  Checked
# against every sound the French fixture book writes by hand for a verb: 26
# of 27 identical, and the 27th is Wiktionary giving aurai /ɔ.ʁe/ where the
# book says oré.
_FR_V = {"a": "a", "ɑ": "a", "e": "é", "ɛ": "è", "ə": "e", "i": "i", "o": "o",
         "ɔ": "ò", "u": "ou", "y": "ü", "ø": "eu", "œ": "eu"}
_FR_NASAL = {"a": "ã", "ɑ": "ã", "e": "ẽ", "ɛ": "ẽ", "œ": "ẽ", "o": "õ", "ɔ": "õ"}
_FR_C = {"b": "b", "d": "d", "f": "f", "ɡ": "g", "g": "g", "k": "k", "l": "l",
         "m": "m", "n": "n", "p": "p", "s": "s", "t": "t", "v": "v", "z": "z",
         "ʁ": "r", "r": "r", "ʀ": "r", "ɾ": "r", "ʃ": "ʃ", "ʒ": "ʒ", "ɲ": "ɲ",
         "j": "y", "w": "w", "ɥ": "ü"}
# What a transcription writes that is not a sound: the slashes, the
# syllable dots, stress and length, a tie bar.  The brackets of an optional
# sound go and the sound stays -- /su.v(ə).niʁ/ is `souvenir`: a vocabulary
# line is "a page read carefully", which docs/lang/fr.md rule 5 says keeps
# its mute e.
_FR_SKIP = set("/[].ˈˌː()͡")
_FR_TILDE = "\u0303"                # the nasal's, in NFD
_FR_DOUBLE = re.compile(r"([bdfgklmnprstvzʃʒɲ])\1+")


def respell_fr(ipa):
    """One French pronunciation in the book's scheme, or "" where it cannot be.

    The rules the table needs, all docs/lang/fr.md's own:
      a word-final mute e is not said (/pʁɑ̃.dʁə/ is `prãdr`), in a word
        that has another vowel (the pronoun /mə/ is `me`);
      `‿` after a pronoun that is one consonant is an elision and joins
        (/s‿ɑ̃/ is `sã`), and anywhere else a liaison, whose consonant starts
        the next word after a hyphen (/nu.z‿ɑ̃/ is `nou-zã`);
      no letter is doubled (mourrai /muʁ.ʁe/ is `mouré`);
      a sound the scheme has no letter for is not made into one: the whole
        answer is "", and the caller says so.
    """
    s = unicodedata.normalize("NFD", (ipa or "").strip())
    s = re.split(r"[,~]", s)[0].replace("|", " ")      # the first reading
    words, cur = [], []                 # units: (kind, IPA letter, nasal?)
    i = 0
    while i < len(s):
        ch = s[i]
        i += 1
        if ch in _FR_SKIP:
            continue
        if ch.isspace():
            if cur:
                words.append(cur)
            cur = []
            continue
        if ch == "‿":
            # an elision if all that precedes it in this word is consonants
            # (the s of s'en), else a liaison: its consonants move on
            if cur and all(k == "C" for k, _c, _n in cur):
                continue
            tail = []
            while cur and cur[-1][0] == "C":
                tail.insert(0, cur.pop())
            cur = cur + [("-", "", False)] + tail
            continue
        if unicodedata.combining(ch):
            if ch == _FR_TILDE and cur and cur[-1][0] == "V" and cur[-1][1] in _FR_NASAL:
                cur[-1] = ("V", cur[-1][1], True)
            continue                    # a diacritic of manner: devoicing, ...
        if ch in _FR_V:
            cur.append(("V", ch, False))
        elif ch in _FR_C:
            cur.append(("C", ch, False))
        else:
            return ""                   # /x/, /ŋ/, /h/: no letter in the scheme
    if cur:
        words.append(cur)
    out = []
    for w in words:
        # the final mute e: dropped from a part of a word that has another vowel
        parts, part = [], []
        for u in w:
            if u[0] == "-":
                parts.append(part)
                part = []
            else:
                part.append(u)
        parts.append(part)
        text = []
        for part in parts:
            if (len(part) > 1 and part[-1][:2] == ("V", "ə")
                    and any(k == "V" for k, _c, _n in part[:-1])):
                part = part[:-1]
            text.append("".join(_FR_NASAL[c] if n else (_FR_V[c] if k == "V" else _FR_C[c])
                                for k, c, n in part))
        out.append("-".join(text))
    return _FR_DOUBLE.sub(r"\1", " ".join(out)).strip()


# The respellings a language's ipa.json may name instead of a table.
RESPELL = {"fr": respell_fr}


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:] or ["एवं मे सुतं", "अनाथपिण्डिकस्स", "कीळति", "हिन्दी"]:
        print("%s\t%s" % (arg, deva_to_iast(arg)))
