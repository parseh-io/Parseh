#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cut a sentence into the phrases a reader should meet it in.

    chunker.chunk(text, "fa")                 -> one chunk per sentence
    chunker.chunk(text, "fa", "phrase")       -> sense groups
    chunker.WAYS                              -> what may be asked for

WHAT A CHUNK IS FOR.  In Frank's method the reader meets a piece of the
foreign text and then its gloss, and the chunk is the unit of that mapping.
That fixes what a good one is from both sides at once: it has to be small
enough to hold in the head while the eye moves to the gloss, and whole
enough that the gloss is a natural translation OF EXACTLY THAT SPAN.  A cut
through the middle of a phrase fails the second test -- half a prepositional
phrase has no honest gloss -- and a whole sentence fails the first, because
the reader stops mapping and starts reading the translation.

So the rule is: CUT AT THE EDGES OF PHRASES, NEVER INSIDE ONE, and aim for
two to five words.  Everything below is that rule made mechanical.

WHAT HOLDS A PHRASE TOGETHER, in the order the rules are worth:

  1  A FUNCTION WORD IS NEVER ALONE.  An adposition goes with its object
     (`in the house`, `به خانه`, `家に`), a particle or case marker with the
     word before it, an article or determiner with its noun, a Persian ezafe
     with what it governs.  Alone, none of them can be glossed at all.  This
     is the highest-frequency rule there is and the cheapest to get right.
  2  A FIXED EXPRESSION IS ONE CHUNK even where that breaks the syntax.  A
     light-verb compound (`فکر کردن`, `勉強する`), an idiom, a phrasal verb:
     the meaning is not in the pieces, and showing the pieces teaches a
     reader something untrue.  This one needs the dictionary, and where the
     dictionary is silent it is the model's job -- the prompts say so.
  3  THE VERB GROUP IS THE UNIT, NOT THE VERB.  Auxiliaries, negation, a
     separable prefix, the light verb of a compound: a tense is one thing.
     `نمی‌روم` is one word; `می‌خواهم بروم` and `食べている` are one verb each
     in two pieces, and cutting between them leaves two halves that mean
     nothing on their own.
  4  A NOUN KEEPS ITS MODIFIERS.  Adjectives, numerals, demonstratives,
     possessives -- on whichever side the language puts them.
  5  A CLAUSE BOUNDARY IS ALWAYS A CHUNK BOUNDARY, and a conjunction or
     relativiser opens the chunk it introduces rather than closing the one
     before it.
  6  AN ADVERB JOINS THE VERB IT MODIFIES when it stands next to it, and
     otherwise stands on its own: a manner adverb belongs to the verb group,
     a sentence adverb (`yesterday`, `فردا`) modifies the whole clause and
     glosses perfectly well alone.

AND WHAT A CHUNK MUST NOT BE.  Not one word per word -- that is a dictionary
with the text interleaved, and the reader never learns how the language
phrases anything.  Not a whole clause.  A one-word chunk is right only when
the word IS the utterance (`Yes`, `Stop`, `بله`) or when nothing may attach
to it.

HOW MUCH OF THAT CAN BE DONE WITHOUT A PARSER.  None is required: this
toolbox is stdlib Python.  What there is instead, asked in this order:

  * PUNCTUATION, in every language and with nothing installed.  A comma, a
    semicolon, a colon, a 、 or a ， ends a clause, and rule 5 makes that a
    chunk boundary.  It is the one cue every writer prints, and a cut blind
    to it lands inside the next phrase instead: `寒い朝に、窓を | 開ける。`,
    `When I got | home, my mother`.
  * THE LANGUAGE'S OWN FUNCTION WORDS, listed in lib/lang/<code>.chunk.json:
    its articles, prepositions, conjunctions, pronouns and auxiliaries, a
    closed list of a few hundred words that a dictionary is the wrong
    authority on -- Wiktionary files `man` under an interjection and `not`
    under a conjunction, and whichever reading it listed first used to decide
    the cut.  A word under two headings is read in its place: `that man`,
    `that he`, `that is`; `la casa`, `la vedo`.
  * THE DICTIONARY the reading panel already uses, for everything else: a
    part of speech for every word it holds, weighted by how many senses it
    gives each reading, and an inflected form reached through the language's
    own affix rules.  Parts of speech plus adjacency get rules 1, 3, 4, 5 and
    6 right most of the time; rule 2 needs more than a word list and is left
    to the model, which is why the offline cut is offered as a CHOICE and
    never imposed.  A spaced language with neither a list nor a dictionary is
    cut at its punctuation and nowhere else, rather than at random.
  * FOR A LANGUAGE WRITTEN WITHOUT SPACES, the words lib/words.py divides it
    into where its analyzer is installed -- SudachiPy for Japanese, pkuseg
    with its part-of-speech model for Chinese: the words the word strip shows
    -- with the part of speech it names for each piece, so that a chunk never
    ends inside a word and a particle, a modifier, a coverb and a verb's
    auxiliaries are known for what they are.  Without it the characters are
    read against the language's own lists (lib/lang/<code>.chunk.json):
    Japanese's particles and marks, Chinese's punctuation.

THE INVARIANT.  Chunks are slices of the source, joined by the language's
own separator, and `chunk()` is checked against the text it was given: the
whole toolbox rests on a chunk sequence reproducing what it came from, so a
chunker that cannot promise that returns one chunk and says nothing clever.
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import languages                                              # noqa: E402
import lookup                                                 # noqa: E402
import words                                                  # noqa: E402

WAYS = ("sentence", "phrase")
DEFAULT_WAY = "sentence"

# What each way is called where somebody has to choose one.
WAY_LABEL = {
    "sentence": "one chunk per sentence",
    "phrase": "sense groups (the dictionary reads the parts of speech)",
}

# The dictionary's own parts of speech, in the handful of classes the rules
# above are written in.  Anything unlisted is a content word, which is the
# safe answer: content words are what chunks are built around.
CLASS = {
    "prep": "ADP", "postp": "ADP",
    "particle": "PART", "suffix": "PART", "affix": "PART", "prefix": "PART",
    "conj": "CONJ",
    "det": "DET", "article": "DET", "num": "NUM",
    "adj": "ADJ", "adnominal": "ADJ",
    "verb": "VERB", "aux": "VERB",
    "adv": "ADV",
    "pron": "PRON",
    "intj": "INTJ",
    "noun": "NOUN", "name": "NOUN", "counter": "NOUN",
}

JOIN, LEAN, CUT = 0, 45, 100      # how willing the gap is to be a boundary
CUT_AT = 55                       # a gap at least this willing becomes one
FIRM = 70                         # unspaced: a seam only a last short piece crosses

# The marks a spaced language ends a clause with inside a sentence.  They are
# written against the word before them (`home,`), so they are looked for at
# the END of a token, under any quote or bracket closing there (`said,"`).
# The full stop is not here: inside one sentence it is an abbreviation --
# `Mr.`, `e.g.` -- which ends nothing.
CLAUSE_MARKS = ",;:،؛"
STOP_MARKS = "!?…؟।॥۔"

_RULES = {}


def rules(code):
    """What this language says about its own phrases: lib/lang/<code>.chunk.json,
    optional like every file of that name."""
    if code not in _RULES:
        d = {}
        path = os.path.join(HERE, "lang", "%s.chunk.json" % code)
        try:
            with open(path, encoding="utf-8") as f:
                got = json.load(f)
            if isinstance(got, dict):
                d = got
        except (OSError, ValueError):
            d = {}
        _RULES[code] = d
    return _RULES[code]


def _is_punct(tok):
    return all(unicodedata.category(ch)[0] in "PSZ" for ch in tok) and bool(tok)


def _closing(ch):
    """A quote or a bracket that closes, and so stands after the mark it
    closes on."""
    return unicodedata.category(ch) in ("Pe", "Pf") or ch in "\"'"


def _mark_gap(tok):
    """What punctuation at the end of a spaced token says of the gap after
    it: CUT after a stop, a cut after a clause mark or a dash standing on its
    own, and None where it says nothing."""
    bare = tok.rstrip()
    while bare and _closing(bare[-1]):
        bare = bare[:-1]
    end = bare[-1:]
    if end and end in STOP_MARKS:
        return CUT
    if end and end in CLAUSE_MARKS:
        return LEAN + 20
    if tok and all(unicodedata.category(ch) == "Pd" for ch in tok):
        return LEAN + 20
    return None


def _tokens(text, L):
    """(token, start, end) over the source, so every chunk is a SLICE of it
    and the invariant is kept by construction rather than by rejoining."""
    if L.spaced:
        return [(m.group(0), m.start(), m.end())
                for m in re.finditer(r"\S+", text or "")]
    # an unspaced language is cut by the dictionary's own word list, which is
    # the same cut the reading panel shows
    at, out = 0, []
    for piece in lookup._segment(lookup._conn(L.code), text or "", L) or []:
        i = (text or "").find(piece, at)
        if i < 0:
            continue
        out.append((piece, i, i + len(piece)))
        at = i + len(piece)
    return out


def _class(tok, code):
    """One of the classes above for one token read on its own: the
    language's own list of function words first, then the dictionary.  The
    cut itself reads every token in its place (_spaced)."""
    L = languages.get_or_default(code)
    return _candidates(tok, False, L, rules(code), _lexicon(code),
                       lookup.available(code))[0]


# THE LANGUAGE'S OWN FUNCTION WORDS.  A dictionary is the wrong authority on
# them.  Wiktionary files `man` under an interjection and a pronoun as well as
# a noun, `not` under a conjunction, Italian `la` with more senses as a
# pronoun than as the article, Turkish `için` as a noun before the
# postposition it nearly always is -- and whichever reading it listed first
# used to decide the cut: `The old | man wound the clock`.  The articles,
# prepositions, conjunctions, pronouns and auxiliaries of a language are a
# closed list of a few hundred words that do not change, so lib/lang/<code>.
# chunk.json lists them ("function_words"), and the dictionary is asked about
# the open classes only, each reading weighted by how many senses it has.  A
# word under two headings is read in its place (_in_context).
_LEXICONS = {}
_LISTS = {}
_LIGHT = {}
_CLOSED_CLASSES = ("ADP", "DET", "CONJ", "PRON", "PART", "AUX", "NEG", "PREF", "PRT")
_NOMINAL = ("NOUN", "ADJ", "NUM", "OTHER", "DET", "PRON")


def _key(word, L):
    """A word as the lists and the dictionary are searched for it: folded,
    and with the typewriter's apostrophe."""
    return lookup._fold(word, L).replace("’", "'")


def _lexicon(code):
    """{word: [class, ...]} from the language's "function_words", the classes
    in the order the file gives their headings."""
    if code not in _LEXICONS:
        L = languages.get_or_default(code)
        lex = {}
        for cls, ws in (rules(code).get("function_words") or {}).items():
            if cls.startswith("_") or not isinstance(ws, list):
                continue
            for w in ws:
                got = lex.setdefault(_key(w, L), [])
                if cls not in got:
                    got.append(cls)
        _LEXICONS[code] = lex
    return _LEXICONS[code]


def _listed(L, R, name):
    """One of the language's word lists ("ties", "closing"), as a set."""
    k = (L.code, name)
    if k not in _LISTS:
        _LISTS[k] = frozenset(_key(w, L) for w in (R.get(name) or []))
    return _LISTS[k]


def _light(L, R, word):
    """Is this a light verb, the half of a compound verb that makes a verb of
    the noun before it (فکر کردن, teşekkür etmek)?"""
    if L.code not in _LIGHT:
        _LIGHT[L.code] = [re.compile(p) for p in (R.get("light_verbs") or [])]
    key = _key(lookup._bare(word, L), L)
    return any(p.search(key) for p in _LIGHT[L.code])


def _cased(word):
    ch = word[:1]
    return ch.lower() != ch.upper()


def _clitics(tok, L, R):
    """(clitic before, the word, clitic after) of one token, a clitic being
    one the language writes into the word it leans on -- `l'uomo`,
    `dell'anno`, `don't`, `he's` -- and ("", token, "") where there is none."""
    bare = lookup._bare(tok, L)
    low = _key(bare, L)
    for pre in sorted(R.get("elisions") or [], key=len, reverse=True):
        if low.startswith(pre) and len(low) > len(pre):
            return pre, low[len(pre):], ""
    for post in sorted(R.get("enclitics") or {}, key=len, reverse=True):
        if low.endswith(post) and len(low) > len(post):
            return "", low[:-len(post)], post
    return "", tok, ""


def _candidates(tok, first, L, R, lex, have_dict):
    """The classes one token may be, likeliest first."""
    bare = lookup._bare(tok, L)
    if not bare:
        return ["PUNCT"]
    key = _key(bare, L)
    if key in lex:
        return list(lex[key])
    got = []
    if have_dict:
        ranked = (lookup.pos_weights(L.code, bare) if lex
                  else [(p, 0) for p in lookup.pos_of(L.code, bare)])
        for pos, _n in ranked:
            cls = CLASS.get(pos)
            if cls is None or cls in got:
                continue
            if lex and cls in _CLOSED_CLASSES:
                continue            # the language's own list is the authority
            if pos == "name" and _cased(bare) and (first or not bare[:1].isupper()):
                continue            # a name is a capital inside the sentence
            got.append(cls)
    return got or ["OTHER"]


def _in_context(c, prev, nxt, after, particle=False):
    """One class for a token that may be several, from its neighbours: the
    class of the token before it, as already read, and the class of the one
    after it.  `after` is whether the language's adpositions follow their
    noun, and `particle` whether this word is one of the language's verb
    particles ("particles": `up`, `in`, `off`)."""
    s = set(c)
    if len(s) < 2 and "ADP" not in s:
        return c[0]
    if "PREF" in s and nxt in ("VERB", "AUX", "OTHER"):
        return "PREF"                        # `to go`
    if "DET" in s and (nxt in ("NOUN", "ADJ", "NUM", "OTHER")
                       or (c[0] == "DET" and nxt == "DET")):
        return "DET"                         # `that man`, `la casa`, `le sue emozioni`
    if "PRON" in s and nxt in ("VERB", "AUX", "NEG"):
        return "PRON"                        # `that is`, `la vedo`
    if c[0] == "DET" and "PRON" in s:
        return "PRON"                        # with no noun after it, it stands for one: `در آن`
    if "ADP" in s:
        if after or nxt in _NOMINAL:
            return "ADP"
        if particle or nxt in (None, "PUNCT", "CONJ", "AUX"):
            # a preposition with no noun after it is the verb's particle, or
            # an adverb: `came in and`, `put it down.`, `given up counting`,
            # `the wind outside had` -- where one before a verb is a
            # preposition still: `di fare`, `of having stolen`
            rest = [x for x in c if x not in ("ADP", "PREF")]
            return rest[0] if rest and rest[0] in ("CONJ", "ADV") else "PRT"
        return "ADP"
    if "NOUN" in s and "VERB" in s:
        if prev in ("DET", "ADJ", "NUM"):
            return "NOUN"
        if prev in ("PRON", "AUX", "NEG", "PREF"):
            return "VERB"
    if "ADJ" in s and nxt == "NOUN":
        return "ADJ"
    return c[0]


def _closes_adposition(cls, k, reach=4):
    """Does token k end a phrase an adposition opened (`در تاریکی`), rather
    than stand as an argument of the verb after it?  Looked for back across
    the nominal words before it, a few at most."""
    for j in range(k - 1, max(-1, k - 1 - reach), -1):
        if cls[j] == "ADP":
            return True
        if cls[j] not in ("NOUN", "ADJ", "DET", "NUM", "OTHER", "PRON", "PART"):
            return False
    return False


def _gap(toks, left, right, lead, i, L, R, have_dict):
    """How willing the space before token i is to become a boundary.

    left[k] is token k's class as the token before it sees it and right[k]
    as the one after it does -- the two differ only where a clitic is written
    into the token: `l'uomo` is an article to what precedes it and a noun to
    what follows.  lead[k] is the word the token begins with, as the
    language's lists spell it."""
    head_final = (R.get("np_head") or "final") == "final"
    after = (R.get("adposition") or ("after" if head_final else "before")) == "after"
    verb_final = bool(R.get("verb_final"))
    a = toks[i - 1][0]
    ca, cb = right[i - 1], left[i]
    word = i

    if cb == "PUNCT":                       # punctuation stays with its words
        return JOIN
    marked = _mark_gap(a)
    if marked is not None:
        # 5 -- the mark a writer ends a clause with, and it is written against
        # the word before it: `home,` is a noun to the dictionary, and a cut
        # that asked only the dictionary went `When I got | home, my mother`
        return marked
    if not L.spaced:
        # AN UNSPACED LANGUAGE BREATHES AFTER ITS PARTICLES.  Japanese
        # is read in bunsetsu -- a content word with the particles that
        # follow it -- and that is exactly `cut after a particle, and after a
        # finished verb'.  Saying it this way round also keeps the offline
        # cut from AMPLIFYING a bad segmentation: where longest-match has
        # split a word into pieces the dictionary happens to hold, those
        # pieces stay in one chunk instead of becoming three.
        if "OTHER" in (ca, cb):
            return LEAN
        if ca == "PART" and cb != "PART":
            return CUT
        if ca == "VERB" and cb not in ("VERB", "PART", "PUNCT"):
            return CUT
        if cb == "CONJ":
            return CUT
        return JOIN
    if ca == "PUNCT":
        # a full stop inside a caption ends the phrase; a comma leans that way
        return CUT if a[-1:] in ".!?…؟۔。！？।" else LEAN + 20
    if ca == "PREF":
        return JOIN                          # می, `to`: bound to the word after
    if cb == "PREF" and i + 1 < len(toks):
        word = i + 1                         # the seam before a prefix is the
        cb = left[word]                      # seam before the word it binds to
    # 1 -- a function word is never alone
    if cb in ("PART", "PRT"):
        return JOIN                          # را, the clitics, `put it down`
    if ca == "PART":
        return CUT if lead[i - 1] in _listed(L, R, "closing") else LEAN
    # 5 -- a clause boundary, and the conjunction opens what follows, whatever
    # follows it: `and to the sea`, `یا به هیچ چیز`
    if cb == "CONJ":
        return CUT
    if ca == "CONJ":
        return JOIN
    if cb == "ADP" and ca in ("NOUN", "PRON", "NUM", "ADJ", "OTHER") \
            and lead[i] in _listed(L, R, "ties"):
        return LEAN - 10                     # un pezzo di legno, a pound of apples
    if ca == "ADP":
        return CUT if after else JOIN        # a preposition binds forward
    if cb == "ADP":
        return JOIN if after else CUT_AT     # a postposition binds back
    if ca in ("DET", "NUM"):
        return LEAN if cb in ("VERB", "AUX") else JOIN   # this/three + what it counts
    for pat in (R.get("bind_forward") or []):
        if re.search(pat, a):
            return JOIN                      # the Persian ezafe, marked
    # 3 -- the verb group: its negation, its auxiliaries, a compound's noun
    verbal = ("VERB", "AUX")
    if ca == "NEG":
        return JOIN
    if cb == "NEG":
        return JOIN if after or ca in verbal else LEAN
    if cb in ("VERB", "AUX", "OTHER") and ca in ("NOUN", "ADJ", "ADV", "OTHER") \
            and _light(L, R, toks[word][0]):
        return JOIN                          # فکر کردن, teşekkür etmek
    if ca in verbal and cb in verbal:
        return JOIN
    if (ca == "ADV" and cb in verbal) or (ca in verbal and cb == "ADV"):
        return JOIN                          # 6 -- adjacent, so it is the verb's
    if ca == "PRON" and cb in verbal:
        return LEAN - 10                     # he said, lo vedo -- closer than
    if ca in verbal and cb == "PRON":
        return LEAN                          # saw him
    # 4 -- a noun keeps its modifiers, on the side this language puts them
    if head_final and ca == "ADJ" and cb in ("NOUN", "PRON"):
        return JOIN
    if not head_final and ca in ("NOUN", "PRON") and cb == "ADJ":
        return JOIN
    if ca in ("NOUN", "PRON") and cb == "DET":
        return LEAN if verb_final else CUT_AT   # a new noun phrase begins
    if "OTHER" in (ca, cb):
        # a word nobody knows.  With a dictionary it is one word it lacks, and
        # the rules around it still stand; with none, two unknown words side
        # by side are all there is to go on, and a cut between them would be
        # made at random
        return LEAN if have_dict or ca != cb else JOIN
    if verb_final:
        if ca in ("NOUN", "PRON", "ADJ") and cb in verbal:
            # the object, with its verb -- but a noun that closes a phrase an
            # adposition opened is not the verb's object: در تاریکی | نشسته بود
            return CUT_AT if _closes_adposition(right, i - 1) else LEAN
        if ca in verbal and cb in ("NOUN", "PRON", "ADJ"):
            return CUT                       # the verb closed its clause
    else:
        if ca in verbal and cb in ("NOUN", "ADJ", "NUM"):
            return LEAN                      # the verb, with its object
        if ca == "NOUN" and cb in verbal:
            return CUT_AT                    # the subject, and its verb
    # two content words with nothing binding them: the likeliest boundary
    if ca in ("NOUN", "PRON", "VERB") and cb in ("NOUN", "PRON", "VERB"):
        return CUT
    return LEAN


def _counted(g):
    """How many words a group is: a mark standing on its own (`Oui , monsieur`)
    is a token and no word."""
    return sum(1 for m in g if not _is_punct(m[0]))


def _ends_clause(g):
    """Does this group end on a mark that closes a clause?"""
    return _mark_gap(g[-1][0]) is not None


def _alone(g):
    """A group of one interjection: `Yes,`, `Buongiorno,`.  Standing
    between marks, or last, it is a chunk of its own however short, the word
    being the utterance; `Thanks | to today's sponsor` is not that."""
    said = [m for m in g if not _is_punct(m[0])]
    return len(said) == 1 and len(said[0]) > 4 and said[0][4] == "INTJ"


def _sized(groups, lo, hi):
    """Merge what is too small and split what is too large -- the size band
    is a preference and the rules above are not, so nothing here may cut a
    gap the rules called JOIN.

    A group too small goes to a neighbour: the one it shares no mark with,
    where one side has a mark and the other has not (`tired and hungry, |
    sat | in the darkness` gives `sat` to the darkness), and else the
    smaller.  A clause of one interjection stands alone and takes nobody in.
    A group too large is split at its strongest seam, and of seams equally
    strong at the one that halves it most evenly."""
    out = [list(g) for g in groups]

    def stands(k):
        return _alone(out[k]) and (_ends_clause(out[k]) or k == len(out) - 1)

    i = 0
    while i < len(out):                      # too small: fold into a neighbour
        if _counted(out[i]) >= lo or len(out) == 1 or stands(i):
            i += 1
            continue
        sides = []                           # (crosses a mark, its size, which)
        if i and not stands(i - 1):
            sides.append((_ends_clause(out[i - 1]), _counted(out[i - 1]), 0))
        if i + 1 < len(out) and not stands(i + 1):
            sides.append((_ends_clause(out[i]), _counted(out[i + 1]), 1))
        if not sides:
            i += 1
            continue
        if min(sides)[2] == 0:
            out[i - 1] = out[i - 1] + out[i]
            del out[i]
            i = max(0, i - 1)
        else:
            out[i] = out[i] + out[i + 1]
            del out[i + 1]
    i = 0
    while i < len(out):                      # too large: split at the strongest
        g = out[i]
        if _counted(g) <= hi:
            i += 1
            continue
        best, where = None, None
        for k in range(1, len(g)):
            if lo <= k <= len(g) - lo:
                key = (g[k][3], -abs(len(g) - 2 * k))
                if best is None or key > best:
                    best, where = key, k
        if where is None or best[0] <= JOIN:
            i += 1                           # nothing may be cut; leave it long
            continue
        out[i:i + 1] = [g[:where], g[where:]]
    return out


def _clauses(text, L, R):
    """A spaced sentence cut at its punctuation and nowhere else -> [chunk],
    or [] where it has none to cut at: what can be said with no dictionary to
    read a part of speech from.  A clause shorter than the language's `min`
    (`Yes,`) goes to its neighbour, as in the dictionary's cut."""
    toks = _tokens(text, L)
    if len(toks) < 2:
        return []
    marked = [toks[0] + (CUT,)] + [toks[i] + (_mark_gap(toks[i - 1][0]) or JOIN,)
                                   for i in range(1, len(toks))]
    groups, cur = [], [marked[0]]
    for m in marked[1:]:
        if m[3] >= CUT_AT:
            groups.append(cur)
            cur = [m]
        else:
            cur.append(m)
    groups.append(cur)
    if len(groups) > 1:
        groups = _sized(groups, int(R.get("min") or 2), len(toks))
    return [text[g[0][1]:g[-1][2]] for g in groups if g] if len(groups) > 1 else []


# WHAT A DEPENDENCY MAY SAY OF A SEAM (a0.6.0, lib/analyzer.py), and it says only this.  Dependencies are not
# reading groups: a subtree can be a whole clause, so no boundary is ever made from one.  These few say that
# a seam lies inside what cannot be glossed apart, or that a word opens what follows.  Each is here because of
# a sentence that needed it: `die alte Frau` (det, amod), `in dem Haus` (case), `has been seen` (aux),
# `فکر کردم` and `teşekkür ederim` (compound, compound:lvc), `New York` (flat), `because of` (fixed).
_DEP_JOIN = ("det", "det:predet", "case", "amod", "nummod", "aux", "aux:pass", "cop", "compound", "compound:lvc", "compound:prt",
             "compound:svc", "fixed", "flat", "flat:name", "goeswith", "clitic")
_DEP_REACH = 4                                  # a seam this many tokens from its head is not held by it
_DEP_OPENS = ("cc", "mark")                     # `and`, `because`: what opens the chunk it introduces
_UPOS_CLASS = {"NOUN": "NOUN", "PROPN": "NOUN", "VERB": "VERB", "AUX": "AUX", "ADJ": "ADJ", "ADV": "ADV", "PRON": "PRON",
               "DET": "DET", "ADP": "ADP", "CCONJ": "CONJ", "SCONJ": "CONJ", "NUM": "NUM", "PUNCT": "PUNCT"}


def _token_at(toks, spans):
    """{word's token id: index in toks}, for the analyzer's tokens wholly inside one of ours."""
    out = {}
    for t in spans:
        for i, (_w, s, e) in enumerate(toks):
            if s <= t.start and t.end <= e:
                out[t.id] = i
                break
    return out


def _assist(toks, analysis):
    """What an analysis says of these tokens -> ({seam index: "join" or "opens"}, {token index: class}).  A seam
    is the one before token i.  Only what proved to be inside our tokens counts; nothing here can move a token."""
    seams, classes = {}, {}
    at = _token_at(toks, analysis.tokens)
    words = {}
    for t in analysis.tokens:
        if t.id in at:
            for w in t.parsed():
                words[(w.source, w.id)] = (at[t.id], w)
    for (source, _id), (i, w) in words.items():
        if w.upos in _UPOS_CLASS and i not in classes:
            classes[i] = _UPOS_CLASS[w.upos]
        target = words.get((source, w.head))
        if target is None or target[0] == i:
            continue
        lo, hi = sorted((i, target[0]))
        if w.relation in _DEP_JOIN and hi - lo <= _DEP_REACH:
            for seam in range(lo + 1, hi + 1):
                seams[seam] = "join"
        elif w.relation in _DEP_OPENS and seams.get(i) != "join":
            seams[i] = "opens"
    return seams, classes


def _spaced(text, L, R, have_dict, analysis=None):
    """A sentence cut at the seams between its tokens -> [chunk]: its
    punctuation, the language's function words, and -- where a dictionary is
    installed -- the parts of speech it gives the rest.  `have_dict` False
    is a language cut by its lists alone.

    `analysis` is what an analyzer read in this very text, or nothing: a word the
    rules cannot place takes its part of speech from it, and a seam it
    speaks for moves the way it says, as long as the writer's punctuation
    has not already said otherwise."""
    toks = _tokens(text, L)
    if len(toks) < 2:
        return [text.strip()] if text.strip() else []
    lex = _lexicon(L.code)
    head_final = (R.get("np_head") or "final") == "final"
    after = (R.get("adposition") or ("after" if head_final else "before")) == "after"
    pieces, cands = [], []
    for i, (tok, _start, _end) in enumerate(toks):
        pre, word, post = _clitics(tok, L, R) if L.spaced else ("", tok, "")
        key = _key(lookup._bare(tok, L), L)
        if (pre or post) and key not in lex:
            cands.append(_candidates(word, i == 0, L, R, lex, have_dict))
        else:
            pre = post = ""
            cands.append(_candidates(tok, i == 0, L, R, lex, have_dict))
        pieces.append((pre, post, key))
    # read twice: the first pass guesses each token from its neighbours'
    # likeliest classes, the second from what the first made of them -- so
    # `in that tone` sees `that` already read as the determiner it is
    parts = [key in _listed(L, R, "particles") for _pre, _post, key in pieces]
    guess = []
    for i, c in enumerate(cands):
        nxt = cands[i + 1][0] if i + 1 < len(cands) else None
        guess.append(_in_context(c, guess[i - 1] if i else None, nxt, after, parts[i]))
    cls = []
    for i, c in enumerate(cands):
        nxt = guess[i + 1] if i + 1 < len(cands) else None
        cls.append(_in_context(c, cls[i - 1] if i else None, nxt, after, parts[i]))
    seams, known = _assist(toks, analysis) if analysis is not None else ({}, {})
    cls = [known.get(i, c) if c == "OTHER" else c for i, c in enumerate(cls)]
    left, right, lead = list(cls), list(cls), []
    for i, (pre, post, key) in enumerate(pieces):
        if pre:
            left[i] = _in_context(lex.get(pre) or ["DET"], cls[i - 1] if i else None,
                                  cls[i], after)
        if post:
            right[i] = (R.get("enclitics") or {}).get(post) or cls[i]
        lead.append(pre or key)
    marked = [toks[0] + (CUT, right[0])]     # (tok, start, end, gap-before, class)
    for i in range(1, len(toks)):
        gap = _gap(toks, left, right, lead, i, L, R, have_dict)
        if i in seams and left[i] != "PUNCT" and _mark_gap(toks[i - 1][0]) is None:
            gap = JOIN if seams[i] == "join" else max(gap, CUT)
        marked.append(toks[i] + (gap, right[i]))
    groups, cur = [], [marked[0]]
    for m in marked[1:]:
        if m[3] >= CUT_AT:
            groups.append(cur)
            cur = [m]
        else:
            cur.append(m)
    groups.append(cur)
    lo = int(R.get("min") or (2 if L.spaced else 1))
    hi = int(R.get("max") or (5 if L.spaced else 4))
    groups = _sized(groups, lo, hi)
    return [text[g[0][1]:g[-1][2]] for g in groups if g]


def _weight(s):
    """How long a piece of an unspaced sentence is to read: its characters,
    the punctuation and the spacing not counted."""
    return sum(1 for ch in s if unicodedata.category(ch)[0] not in "PZC")


def _grow(texts, seams, most):
    """The pieces of an unspaced sentence joined into its chunks.  seams[k]
    says how firmly texts[k] is closed off from texts[k + 1].

    A JOIN seam is closed first, whatever comes of it.  Then, while a chunk
    can grow, the weakest seam left is closed, the smallest result first, as
    long as the two sides together stay within `most` characters.  Cut after
    every particle a sentence falls into a word and its particle at a time;
    grown, an object keeps its verb (窓を開ける。) and a chunk comes to the
    two to eight characters docs/lang/ja.md asks for.  A seam at CUT -- a
    clause's end -- is never closed.  One at FIRM, after a topic or a
    subject, is closed only for the sentence's last piece, so that 雨が降る。
    stays one chunk and おばあさんが | 川で two.  `most` 0 grows nothing but
    the JOIN seams."""
    texts, seams = list(texts), list(seams)
    k = 0
    while k < len(seams):
        if seams[k] <= JOIN:
            texts[k:k + 2] = [texts[k] + texts[k + 1]]
            del seams[k]
        else:
            k += 1
    while most:
        best = None
        for k, seam in enumerate(seams):
            if seam == FIRM and k + 2 == len(texts):
                seam = LEAN
            if seam >= FIRM:
                continue
            size = _weight(texts[k]) + _weight(texts[k + 1])
            if size <= most and (best is None or (seam, size) < best[0]):
                best = ((seam, size), k)
        if best is None:
            break
        k = best[1]
        texts[k:k + 2] = [texts[k] + texts[k + 1]]
        del seams[k]
    return texts


def _bunsetsu(text, R):
    """An unspaced language cut where it breathes -> [(piece, seam)]: after a
    mark, and after a particle when a content word begins next.  The seam is
    how firmly the piece is closed off from the next one, for _grow().

    Read off the CHARACTERS, deliberately, where lib/words.py has no analyzer
    to ask.  The dictionary's word list is matched longest-first, which reads
    `へし` as a verb and `ています` as a noun, and a cut that trusted it
    inherited both mistakes and turned one into three chunks.  The particles
    are a closed list of a dozen and a half, they are single characters or
    two, and they do not change.

    A MARK (the language's `marks`: 、 。 ！ ？) ends a clause and cuts
    whatever follows it, kana included -- `柴刈りに、| おばあさんは` -- and it
    is read before the particles, so that `に、` is closed by its comma rather
    than left open because a comma is no content word.  More punctuation
    stays with it; a quote or bracket closing on it cuts only where a content
    word follows, because Japanese quotes into a particle: `待ってくれ！」と`.
    """
    closes = sorted(R.get("closes") or [], key=len, reverse=True)
    marks = sorted(R.get("marks") or [], key=len, reverse=True)
    if not closes and not marks:
        return []
    firm = set(R.get("firm") or [])
    opens = re.compile(R.get("opens_content") or r"[^\u3040-\u309f]")
    wide = int(R.get("max_chars") or 12)
    out, start, i, n = [], 0, 0, len(text)
    while i < n:
        mark = next((p for p in marks if text.startswith(p, i)), "")
        if mark:
            j, quoted = i + len(mark), False
            while j < n:
                more = next((p for p in marks if text.startswith(p, j)), "")
                if more:
                    j += len(more)
                elif _closing(text[j]):
                    j, quoted = j + 1, True
                else:
                    break
            if (j < n and _weight(text[start:j])
                    and (not quoted or opens.match(text[j]))):
                out.append((text[start:j], CUT))
                start = j
            i = j
            continue
        hit = next((p for p in closes if text.startswith(p, i)), "")
        if hit:
            j = i + len(hit)
            grown = j - start
            if j < n and grown > 1 and (opens.match(text[j]) or grown >= wide):
                out.append((text[start:j], CUT if _is_punct(hit)
                            else FIRM if hit in firm else LEAN))
                start = j
            i = j
            continue
        i += 1
    if start < n:
        out.append((text[start:], CUT))
    return [(p, s) for p, s in out if p]


# SudachiPy's parts of speech, as lib/words.py hands them over: six fields,
# the first the part of speech and the sixth an inflected word's form.
_JA_MARK = ("補助記号", "記号")
_JA_FUNCTION = ("助詞", "助動詞", "接尾辞")
_JA_PREDICATE = ("動詞", "形容詞", "形状詞")
_JA_INFLECTS = ("動詞", "形容詞", "助動詞", "形状詞")


def _ja_seam(a, b):
    """How firmly two neighbouring Japanese words hold together, from what
    SudachiPy says of their pieces: a, b are the [(morpheme, part_of_speech,
    dictionary_form)] of each, as words.parsed() gives them.

    JOIN where they may never be parted; CUT at the end of a clause; FIRM
    after a topic or a subject; and in between, the lower the likelier the
    two are one phrase -- a word leaning toward the verb after it most of
    all."""
    head, last, then = a[0][1], a[-1][1], b[0][1]
    said = a[-1][0]
    form = (tuple(last) + ("*",) * 6)[5]
    predicate = then[0] in _JA_PREDICATE
    # 1 -- punctuation, particles, the copula and suffixes attach back, and
    # an opening bracket or a prefix forward
    if head[0] == "補助記号" and head[1] == "括弧開":
        return JOIN
    if then[0] in _JA_MARK and then[1] != "括弧開":
        return JOIN
    if then[0] in _JA_FUNCTION or last[0] == "接頭辞":
        return JOIN
    if head[0] in _JA_MARK:
        return CUT                            # 5 -- 、 。 ！ 」 end a clause
    # 4 -- a modifier binds forward: この本, 大きな桃, 寒い朝, 元気な男の子,
    # 私の本, and a figure its counter, 三人
    if last[0] == "連体詞" or (last[0] in _JA_INFLECTS and form.startswith("連体形")):
        return JOIN
    if (last[0] == "助詞" and said == "の") or (last[0] == "名詞" and last[1] == "数詞"):
        return JOIN
    # 2, 3 -- a noun with the する that makes it a verb (勉強 している), and a
    # dependent verb after anything but a particle (ありがとう ございました)
    if last[0] == "名詞" and then[0] == "動詞" and b[0][2] in ("する", "出来る"):
        return JOIN
    if then[0] == "動詞" and then[1] == "非自立可能" and last[0] != "助詞":
        return JOIN
    if last[0] in ("名詞", "代名詞") and then[0] in ("名詞", "代名詞"):
        # a compound the analyzer left in two, unless the first is a noun
        # used as an adverb: 毎日 | 日本語を
        return LEAN if last[2] == "副詞可能" else JOIN
    if last[0] == "助詞":
        if last[1] == "係助詞":
            return FIRM                       # は も: the topic
        if last[1] == "格助詞":
            if said == "が":
                return CUT_AT if predicate else FIRM
            return LEAN - 5 if predicate else LEAN + 5
        if last[1] == "副助詞":
            return LEAN if predicate else LEAN + 5
        if last[1] == "接続助詞":
            if said in ("て", "で"):         # 持って帰る: a verb in two words
                return LEAN - 15 if predicate else CUT_AT
            return FIRM                       # ば と けど ながら: a clause
        if last[1] == "終助詞":
            return CUT
        return LEAN + 5
    if last[0] in _JA_INFLECTS:
        if form.startswith(("終止形", "命令形", "意志推量形")):
            return CUT                        # a finished clause
        if form.startswith("連用形"):
            return LEAN - 5 if predicate else CUT_AT   # 6 -- 大切に育てる
        return CUT_AT
    if head[0] == "副詞":
        return LEAN - 5 if predicate else LEAN + 5     # 6
    if head[0] == "接続詞":
        return LEAN + 15
    if head[0] == "感動詞":
        return CUT
    return LEAN + 5


# pkuseg's parts of speech (the PKU tag set), in the few kinds the Chinese cut
# is written in.  A time word, a place word, a localizer, a numeral and a
# measure word are nominal; an adjective is a predicate in Chinese as often as
# a modifier, and is read as one where no noun follows it.
_ZH_NOMINAL = frozenset("n nr ns nt nz nx s f t r vn an j i l m q b".split())
_ZH_VERBAL = frozenset("v vd vx a ad z".split())
_ZH_DET = frozenset("这 那 哪 每 某 各 该 此 这个 那个 这些 那些 哪个 哪些 "
                    "什么 其他 其它 有些 所有 任何 整个 一些".split())
_ZH_COORD = frozenset("和 与 跟 同 及 以及 或 或者 还是 并".split())
_ZH_OPEN = "「『（《〈【“‘"


def _zh_seam(a, ta, b, tb, tc, pred):
    """How firmly two neighbouring Chinese words hold, from their tags; tc
    is the tag of the word after b, and `pred` whether a verb or a coverb has
    already come in this clause before a."""
    nominal = ta in _ZH_NOMINAL
    if tb == "w":
        return CUT if b[:1] in _ZH_OPEN else JOIN   # a mark stays with its words
    if ta == "w":
        return JOIN if a[:1] in _ZH_OPEN else CUT   # 5 -- and ends the clause
    if tb in ("u", "y", "k"):
        return JOIN                           # 的 了 着 过, 吗 呢 吧, a suffix
    if ta in ("y", "e", "o"):
        return CUT                            # a sentence particle, an interjection
    if ta == "u":
        if a in ("的", "地", "之", "得"):
            return JOIN                       # the modifier, bound to its head
        return LEAN - 5 if tb in _ZH_NOMINAL else CUT_AT   # 住着 一位老人
    if tb == "c":
        return CUT_AT if b in _ZH_COORD else FIRM   # 和他的猫; 但是 opens a clause
    if ta in ("c", "p", "h"):
        return JOIN                           # a conjunction opens, a coverb takes its object
    if tb == "p":
        return JOIN if ta == "d" else LEAN    # 都在; 他 在灯下
    if tb == "a" and nominal and tc in _ZH_NOMINAL:
        return JOIN                           # 一个 小 村子: the adjective is its noun's
    if ta in ("m", "q"):
        return LEAN if tb in _ZH_VERBAL else JOIN   # 一位老人, 两分钟就好
    if ta == "r" and a in _ZH_DET:
        return JOIN                           # 什么茶, 这本书
    if ta in ("a", "b") and tb in _ZH_NOMINAL:
        return JOIN                           # 小村子
    if ta == "d":
        return JOIN if tb in _ZH_VERBAL or tb == "d" else LEAN   # 很好, 不去
    if ta == "f" and tb in _ZH_VERBAL:
        return FIRM                           # 村子里 | 住着
    if nominal and tb == "f":
        return JOIN                           # 桌子 上
    if nominal and tb in _ZH_NOMINAL:
        return LEAN if "t" in (ta, tb) else JOIN   # 我 昨天; 河边, 灯下
    if ta in _ZH_VERBAL and tb in _ZH_VERBAL:
        return LEAN - 15                      # 想要: two verbs, one predicate
    if ta in _ZH_VERBAL and tb in _ZH_NOMINAL:
        return LEAN - 5                       # 看书: the verb, with its object
    if nominal and tb in _ZH_VERBAL:
        # the subject leans toward its verb; a noun that already follows a
        # verb or a coverb in this clause ends that phrase, and the verb after
        # it begins the next: 他在灯下 | 看书, 老人去河边 | 打水
        return FIRM if pred else LEAN
    return LEAN + 5


def _zh_seams(tagged):
    """[(word, tag)] -> a seam for every gap between two words.

    A coverb binds its object and 的 its head, a measure word its number and
    its noun, an adverb the verb after it.  A verb takes its object, leaning;
    a subject leans toward its verb.  Where a verb or a coverb has already
    come in the clause, the noun before the next verb closes a phrase, FIRM,
    and the pieces grow no further across it than across a topic in
    Japanese.  Measured on this toolbox's own Chinese fixtures, the cut is
    the hand's: 每天早上， | 老人去河边 | 打水。 and 你好， | 我想要一杯茶."""
    seams, pred = [], False
    for k in range(1, len(tagged)):
        (a, ta), (b, tb) = tagged[k - 1], tagged[k]
        tc = tagged[k + 1][1] if k + 1 < len(tagged) else ""
        seams.append(_zh_seam(a, ta, b, tb, tc, pred))
        if ta == "w" and a[:1] not in _ZH_OPEN:
            pred = False
        elif ta in ("v", "vd", "vx", "p"):
            pred = True
    return seams


def _by_words(text, L, R):
    """A sentence cut between the words lib/words.py divides it into, by the
    parts of speech its analyzer names -> [chunk]; [] where no analyzer here
    names them, and the characters are read instead."""
    got = words.parsed(text, L.code)
    if not got:
        return []
    starts, at = [], 0
    for surface, _pieces in got:
        i = text.find(surface, at)
        if i < 0:
            return []
        starts.append(i)
        at = i + len(surface)
    ends = starts[1:] + [len(text)]
    texts = [text[(starts[k] if k else 0):ends[k]] for k in range(len(got))]
    if words.rules(L.code).get("analyzer") == "spacy_pkuseg":
        between = _zh_seams([(w, pieces[0][1][0] if pieces else "")
                             for w, pieces in got])
    else:
        between = [_ja_seam(got[k - 1][1], got[k][1]) for k in range(1, len(got))]
    seams = []
    for k in range(1, len(got)):
        seam = between[k - 1]
        if seam < CUT and text[starts[k - 1] + len(got[k - 1][0]):starts[k]].isspace():
            seam = max(seam, CUT_AT)          # a space the writer left: a seam, not a wall
        seams.append(seam)
    grown = _grow(texts, seams, int(R.get("grow_to") or 0))
    return [c.strip() for c in grown if c.strip()]


def phrase(text, lang, analysis=None):
    """The sense groups of one sentence -> [str], or [] where nothing can be
    said (a spaced sentence with no dictionary and no punctuation to cut at,
    or nothing to cut).  `analysis`, a good analyzer.Result of exactly this text,
    is listened to by a spaced language; Japanese and Chinese are cut by their
    own analyzers whatever is said here."""
    L = languages.get_or_default(lang)
    if not (text or "").strip():
        return []
    R = rules(L.code)
    if not L.spaced and (R.get("closes") or R.get("marks")):
        got = _by_words(text, L, R)
        if not got:
            pieces = _bunsetsu(text, R)
            got = [c.strip() for c in _grow([p for p, _s in pieces],
                                            [s for _p, s in pieces[:-1]],
                                            int(R.get("grow_to") or 0))
                   if c.strip()]
        return got if len(got) > 1 else [text.strip()]
    have_dict = lookup.available(L.code)
    if L.spaced:
        if analysis is not None or have_dict or _lexicon(L.code):
            return _spaced(text, L, R, have_dict, analysis)
        # nothing to read a class from: the punctuation is all there is
        return _clauses(text, L, R)
    return _spaced(text, L, R, True) if have_dict else []


def word_class(token, lang):
    """The class this chunker reads one word as -- "AUX", "VERB", "NOUN",
    "ADP" and the rest -- or "" where nothing can say.

    The cut itself reads every word IN ITS PLACE (_spaced), which is what
    makes `that man` and `that he` come out differently; this answers for a
    word standing alone, which is all a caller wants that is asking a
    different question about the same text.  The video door's transcript
    tidier asks it where a sentence ends: in a verb-final language a finite
    verb or a copula is the end of one, and that is a class away.
    """
    if not (token or "").strip():
        return ""
    try:
        return _class(token.strip(), languages.get_or_default(lang).code) or ""
    except Exception:
        return ""


def verb_final(lang):
    """Does this language put its verb at the end of the sentence?  The
    language's own rules say so (lib/lang/<code>.chunk.json)."""
    return bool(rules(languages.get_or_default(lang).code).get("verb_final"))


def chunk_all(texts, lang, how=DEFAULT_WAY, assist=None):
    """Every sentence of a text, cut the asked-for way -> [[chunk, ...], ...].

    One entry point for a whole text, so a caller cannot accidentally cut a
    book one way and one of its chapters another.  `assist` as in chunk().
    """
    if how not in WAYS:
        raise ValueError("no such way of chunking: %r (%s)"
                         % (how, ", ".join(WAYS)))
    return [chunk(t, lang, how, assist) for t in (texts or [])]


def exact(chunks, text):
    """Is each chunk a slice of `text`, in order, with only white space left
    between them?  `reproduces` folds white space, so it cannot say this."""
    at = 0
    for c in chunks:
        i = text.find(c, at)
        if i < 0 or text[at:i].strip():
            return False
        at = i + len(c)
    return not text[at:].strip()


def assisting(code):
    """The `assist` of chunk() if somebody chose it on Settings -> Linguistic
    analysis and this language has an analyzer ready, else None."""
    import analysisconfig
    import analyzer
    if analysisconfig.choice("chunking") != "assist" or not analyzer.available(code, syntax=True):
        return None
    return lambda text: analyzer.analyze(code, text, syntax=True)


def chunk(text, lang, how=DEFAULT_WAY, assist=None):
    """One sentence, cut the asked-for way.  Always reproduces `text`.

    `assist`, a function from text to analyzer.Result, is for new text only: an
    edited chunk is never cut again by anything.  Whatever goes wrong with it
    -- no answer, an answer that fails, a cut that is not a slice of the text
    -- the cut is the one there would have been without it."""
    text = (text or "").strip()
    if not text:
        return []
    if how not in WAYS:
        raise ValueError("no such way of chunking: %r (%s)"
                         % (how, ", ".join(WAYS)))
    if how == "sentence":
        return [text]
    if assist is not None:
        result = assist(text)
        if result is not None and result.ok and result.text == text:
            got = phrase(text, lang, result) or []
            if got and exact(got, text):
                return got
    got = phrase(text, lang) or [text]
    return got if reproduces(got, text, lang) else [text]


def reproduces(chunks, text, lang):
    """Do these chunks add up to that text?  The invariant the whole toolbox
    rests on, asked here so that a chunker which loses a word can be caught
    by the thing that wrote it rather than by a checker two steps later."""
    L = languages.get_or_default(lang)
    if L.spaced:
        return " ".join(" ".join(chunks).split()) == " ".join((text or "").split())
    return re.sub(r"\s+", "", "".join(chunks)) == re.sub(r"\s+", "", text or "")


def _cli(argv):
    if not argv:
        print(__doc__.strip().split("\n\n")[0])
        print("\n  python3 lib/chunker.py <code> [--way sentence|phrase] <text>")
        return 2
    code, argv = argv[0], argv[1:]
    how = "phrase"
    if argv and argv[0] == "--way":
        how, argv = argv[1], argv[2:]
    text = " ".join(argv)
    for c in chunk(text, code, how):
        print("  |%s|" % c)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
