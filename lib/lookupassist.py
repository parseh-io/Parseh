# SPDX-License-Identifier: GPL-3.0-or-later
"""What an analyzer may add to a lookup, after the lookup has been made.

    lookupassist.apply("de", result, text, sentence, "assist")

AFTER, AND NOT THROUGH `pieces=`.  lib/lookup.py's `pieces` replaces the ordinary
pairing of words, and with it the joins of a prefix written apart (Persian
`نمی سوزانند`), the spoken pass and the capital at a sentence's start.  Everything
the old path finds, it finds here too, because it has already run: this function
receives its answer and only ever adds to it.

WHAT IT IS FOR: THE PART OF SPEECH.  A dictionary lists what a word can be, one entry to
a part of speech; the sentence says which.  So the part of speech the analyzer read here
is the first thing a row says, and an entry of that part of speech is marked as the one that
fits.  Only where that tells entries apart: a mark on every entry says nothing.  Where the part
of speech cannot tell them apart nothing is marked: the same-part-of-speech choice by lemma was
tried and put `كاتب` before `كتاب` for `كتابا`.

WHAT EACH CHOICE ADDS, WHERE lib/analysisconfig.py SAYS:

  show      each word gets `machine`: the part of speech, the grammar, the lemma and whose they
            are; and the entries that fit get `fits`.  The order does not change.
  assist    the same; the entries that fit move to the front, none dropped.  A word whose
            entries are none of that part of speech has its lemma's entry of that part of speech
            added.  And a word the dictionary did NOT find is looked for under the analyzer's
            lemmas.  A lemma counts only if it lands on a real entry, and the row says that is
            how it was found (`kind`: "analyzer", `via`).

A person's own word line (Japanese, Chinese, `authoritative`) never comes here:
the route does not call this for it.  An analyzer's root or stem is not looked up
as a word, only what it offers as a lemma.  Any outcome but a good one leaves the
result exactly as it was.
"""
import unicodedata

import analyzer
import lookup

MAX_LEMMAS = 6


def _forms(code, lemma):
    """The headwords a dictionary may keep this lemma under.  The Persian
    treebank writes a verb's lemma as its two stems, `رفت#رو`, and a Persian
    dictionary has the infinitive, رفتن."""
    if code == "fa" and "#" in lemma:
        past = lemma.split("#", 1)[0]
        return [past + "ن"] if past else []
    return [lemma]


# which of the dictionary's parts of speech (lib/getdict.py) each of the analyzers' can be
ENTRY_POS = {"NOUN": ("noun",), "PROPN": ("name", "noun"), "VERB": ("verb",), "AUX": ("verb",), "ADJ": ("adj",),
             "ADV": ("adv", "adv_phrase"), "PRON": ("pron",), "DET": ("det", "article", "adnominal"),
             "ADP": ("prep", "postp", "prep_phrase", "circumpos"), "CCONJ": ("conj",), "SCONJ": ("conj",), "NUM": ("num",),
             "PART": ("particle",), "INTJ": ("intj",)}
CONTENT = ("NOUN", "PROPN", "VERB", "ADJ", "ADV", "AUX", "NUM")
WHO = {"udpipe": "UDPipe", "farahidi": "Farahidi", "starlang": "Starlang", "native": "Parseh's own analyzer"}
POS = {"NOUN": "noun", "PROPN": "name", "VERB": "verb", "AUX": "auxiliary", "ADJ": "adjective", "ADV": "adverb", "PRON": "pronoun",
       "DET": "determiner", "ADP": "adposition", "CCONJ": "conjunction", "SCONJ": "conjunction", "NUM": "number", "PART": "particle",
       "INTJ": "interjection", "PUNCT": "punctuation"}
# THE GRAMMAR IN WORDS A READER HAS, in the order they are said; a value not here is left out of the line (never of the record)
GRAMMAR = (
    ("VerbForm", {"Inf": "infinitive", "Part": "participle", "Conv": "converb", "Ger": "gerund", "Vnoun": "verbal noun"}),
    ("Tense", {"Past": "past", "Pres": "present", "Fut": "future", "Imp": "imperfect", "Pqp": "pluperfect"}),
    ("Aspect", {"Prog": "progressive", "Perf": "perfect", "Hab": "habitual"}),
    ("Evident", {"Nfh": "reported"}),
    ("Mood", {"Imp": "imperative", "Sub": "subjunctive", "Cnd": "conditional", "Opt": "optative", "Nec": "necessitative",
              "Pot": "potential", "Jus": "jussive"}),
    ("Voice", {"Pass": "passive", "Cau": "causative", "Rfl": "reflexive", "Rcp": "reciprocal"}),
    ("Polarity", {"Neg": "negative"}),
    ("Person", {"1": "1st person", "2": "2nd person", "3": "3rd person"}),
    ("Number", {"Sing": "singular", "Plur": "plural", "Dual": "dual"}),
    ("Gender", {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter"}),
    ("Case", {"Nom": "nominative", "Acc": "accusative", "Dat": "dative", "Gen": "genitive", "Loc": "locative", "Abl": "ablative",
              "Ins": "instrumental", "Equ": "equative"}),
)


def words_for(upos, feats):
    """`verb, past, 1st person, singular`, or without the part of speech: what a line says of a word."""
    out = [POS[upos]] if upos in POS else []
    for key, table in GRAMMAR:
        v = (feats or {}).get(key)
        if v in table:
            out.append(table[v])
    if (feats or {}).get("Person[psor]"):
        out.append("possessed by the %s person" % {"1": "1st", "2": "2nd", "3": "3rd"}.get(feats["Person[psor]"], feats["Person[psor]"]))
    return ", ".join(out)


def _main_word(words):
    """Of the syntactic words of one token, the one a reader looks up: `وكتب` is `و` and the word after it, and `zum`,
    with no word of content in it, is its preposition."""
    words = list(words)
    return next((w for w in words if w.upos in CONTENT and w.lemma), None) or (words[0] if words else None)


def _main_token(tokens):
    """Of the tokens a row covers, the one it is looked up for: `L'homme` is `homme`, and `l'a` is `a`."""
    for t in tokens:
        if _main_word(t.parsed()) is not None and _main_word(t.parsed()).upos in CONTENT:
            return t
    return next((t for t in tokens if t.parsed() or t.candidates), None)


def _named(hit, lemma, code, L):
    """Is this entry the lemma itself?  Marks and capitals aside: كِتَاب is كتاب, `Ich` is `ich`."""
    head = hit.get("headword") or ""
    return any(_unmarked(lookup._bare(f, L)).casefold() == _unmarked(head).casefold() for f in _forms(code, lemma))


_SAME = ({"VERB", "AUX"}, {"NOUN", "PROPN"})
# Farahidi's three kinds: its `اسم` is every nominal, and its `حرف` every particle
_KINDS = {"farahidi": ({"NOUN", "PROPN", "ADJ", "ADV", "NUM", "PRON", "DET"}, {"PART", "ADP", "CCONJ", "SCONJ", "INTJ"})}


def _agree(a, b, source=None):
    return a == b or any(a in k and b in k for k in _SAME + _KINDS.get(source, ()))


def _base(cand):
    """What the word was before its derivation, which is what a dictionary files it as: Starlang's `okumak` is a noun at
    the end of `oku+VERB^DB+NOUN+INF`, and a verb to look up."""
    return cand.raw.get("base") or cand.upos


def _read_part_of_speech(token, parsed):
    """(part of speech, read in this sentence?) when two backends speak of one word.  The one that holds the word's
    morphology knows what it CAN be, and the sentence's reader which of those it is here:
      `sinemaya`: UDPipe says verb, and Starlang knows only a noun.  It is a noun.
      a word Farahidi's sentence says is one thing and UDPipe another: nobody knows, so nothing is claimed.  On real
      sentences each was right about as often as the other, and a mark that is wrong costs more than no mark."""
    upos = parsed.upos if parsed else None
    sel = token.selection
    if not token.candidates or not parsed or parsed.source == token.candidates[0].source:
        return upos, bool(parsed)
    source = token.candidates[0].source
    if sel and sel.lemma_status == analyzer.CONTEXTUAL:
        own = {c.upos for c in token.candidates if c.lemma == sel.lemma and c.upos}
        if own and not any(_agree(upos, x, source) for x in own):
            return upos, False
        return upos, True
    kinds = {c.upos for c in token.candidates if c.upos} | {_base(c) for c in token.candidates if _base(c)}
    if not kinds or any(_agree(upos, x, source) for x in kinds):
        return upos, True
    bases = {_base(c) for c in token.candidates if _base(c)}
    return (bases.pop(), True) if len(bases) == 1 else (upos, False)


def _machine(token):
    """What a row may say about its word, short: the part of speech and the lemma this sentence chose and whose
    choice they are, else what the word can be, with no reading put first as if it had been chosen: `adam` is `adam`
    or `ada`.  A treebank's model has a part of speech for a word whose lemma it does not know (`دیدم`), and says it."""
    sel = token.selection
    words = token.parsed()
    parsed = _main_word(w for w in words if w.status == analyzer.CONTEXTUAL)
    cand = token.candidates[0] if token.candidates else None
    lemma = (sel.lemma if sel and sel.lemma_status == analyzer.CONTEXTUAL else None) or (parsed.lemma if parsed else None)
    # WHERE ANOTHER BACKEND HOLDS THE WORD'S MORPHOLOGY, THE SENTENCE CHOOSES AMONG ITS READINGS AND NOTHING ELSE.  UDPipe's
    # lemma of `okuyordu` is `ok`, and Starlang's one reading is `okumak`: said as chosen, the wrong one would stand first.
    # A lemma none of the readings has is not a choice among them; it stays in `others`, so the two are both seen.
    agreed = False
    if lemma and cand and not (sel and sel.lemma == lemma) and parsed.source != cand.source:
        same = [c for c in token.candidates if lemma in (c.lemma, c.root)]
        # `kırdım` is the verb, and the noun `kır` has the same root: what the sentence read it as chooses between them
        same.sort(key=lambda c: not _agree(parsed.upos, _base(c)))
        lemma = same[0].lemma if same else None
        # one read the word alone, the other the sentence, and they name the same lemma: nothing here knows better
        agreed = bool(same)
    word = parsed or _main_word(token.words)
    anyone = (sel if lemma and sel and sel.lemma == lemma else None) or parsed or cand or word
    if anyone is None:
        return None
    others = [x for x in dict.fromkeys(w.lemma for w in token.candidates + words if w.lemma) if x != lemma]
    upos, here = _read_part_of_speech(token, parsed)
    if not lemma and not others and not upos:
        return None
    feats = dict(word.feats) if word else {}
    # what the word can be, what the sentence's part of speech allows first, and of those what leaves least to the endings
    can_be = sorted((c for c in token.candidates if c.lemma), key=lambda c: (not _agree(upos, _base(c)), -len(c.lemma)))
    return {"lemma": lemma or "", "others": others[:3], "upos": upos or "", "feats": feats, "pos": POS.get(upos, ""), "agreed": agreed,
            "here": here, "can_be": list(dict.fromkeys(c.lemma for c in can_be)), "relation": (word.relation if word else None) or "", "grammar": words_for(None, feats),
            "source": anyone.source, "who": WHO.get(anyone.source, anyone.source),
            "status": analyzer.CONTEXTUAL if lemma or here else analyzer.LEXICAL, "readings": len(token.candidates)}


def _unmarked(s):
    """Without its marks: كِتَاب and كتاب are one word to a row of the dictionary."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if not unicodedata.category(ch).startswith("M"))


def formal_view(code, text, register=None):
    """`text` as the analyzers should read it -> (text, {(start, end) of a word in `text`: its (start, end) in the new
    one}), or (text, None) with nothing to change.

    THE NORMALISER READS FOR THE ANALYZER (lib/spoken.py).  A treebank's model has seen written Persian only, and takes
    `اونو` for a noun; `آن را` it knows.  So where a word's first reading is a spoken one its formal spelling goes in its
    place, the rest of the sentence stays, and the model reads a sentence it can read.  ALSO WHERE THE READING HAS RIVALS:
    the model given the page's own letters invents (`میشه` is `میش`, `بگو` is `بیگ`), and a word it reads wrongly takes its
    neighbours with it.  Measured on hand-judged sentences (tests/analysis_bench.py) this is what makes the part of speech
    worth showing: 99% against 93%.  This string is seen by nobody: what comes back is held against these spans, and the
    page's words are the page's.  A language with no spoken rules is as it was."""
    L = lookup.languages.get_or_default(code)
    c = lookup._conn(code)
    if c is None or not L.spaced:
        return text, None
    import spoken
    if not spoken.rules(lookup, L):
        return text, None
    got = lookup.look_up(code, text, register=register) or {}
    out, spans, at, changed, length = [], {}, 0, False, 0
    for row in got.get("words") or []:
        word = row.get("word") or ""
        start = text.find(word, at) if word else -1
        if start < 0:
            continue
        hits = row.get("hits") or [{}]
        said = hits[0].get("spoken") or {}
        formal = said.get("as") or ""
        # the dictionary's own page of a colloquial spelling is still that spelling: `نمی‌دونم`, and the model wants what it points at
        if said.get("kind") == "entry" and len(hits) > 1 and (hits[1].get("spoken") or {}).get("as"):
            formal = hits[1]["spoken"]["as"]
        gap = text[at:start]
        out.append(gap)
        length += len(gap)
        core = word.rstrip(".,!?؟،؛:…»)\"'")
        new = (formal + word[len(core):]) if formal else word
        changed = changed or bool(formal)
        spans[(start, start + len(word))] = (length, length + len(new))
        out.append(new)
        length += len(new)
        at = start + len(word)
    out.append(text[at:])
    return ("".join(out), spans) if changed else (text, None)


def _wanted(said):
    """The dictionary's parts of speech this reading asks for, or None.  A separable verb's particle is an adposition
    to the treebanks, and its dictionary entry is not what `steht ... auf` means: it asks for nothing."""
    if not said.get("here") or said.get("relation") == "compound:prt":
        return None
    # A WORD THE MODEL HAS NEVER SEEN IS GUESSED FROM ITS LOOKS: it has no lemma for it, and no other backend's readings
    # to hold it to.  In spoken Persian those guesses chose `خواندن` for `خونه`.  Enough for a chip that the entries bear
    # out, and not for telling entries apart.
    if not said.get("lemma") and not said.get("readings"):
        return None
    return ENTRY_POS.get(said["upos"])


def _spelled(hit, word, L):
    return (hit.get("headword") or "").casefold() == lookup._bare(word, L).casefold()


def _fits(row, said, code, L):
    """Mark the entries of the part of speech the sentence chose -> how many.  Nothing where it cannot tell them
    apart, or was not read in the sentence.  Among those, the lemma's own where it names one: `give` and not `gyve`.
    The lemma narrows and never decides: alone it put كاتب before كتاب for `كتابا`, all of them nouns."""
    wanted = _wanted(said)
    hits = row.get("hits") or []
    # TWO BACKENDS AGREED ON THE LEMMA (`adamı`: adam, and Starlang also knows ada), so it tells entries of one part of
    # speech apart, as a lemma alone may not.  If the dictionary has no such entry, none of the others fits instead.
    if said.get("agreed") and said["lemma"] and len(hits) >= 2:
        named = [h for h in hits if _named(h, said["lemma"], code, L)]
        if not named:
            return 0
        if len(named) < len(hits):
            for h in named:
                h["fits"] = True
            return len(named)
    if not wanted or len(hits) < 2:
        return 0
    good = [h for h in hits if h.get("pos") in wanted]
    # A TREEBANK CALLS AN INFINITIVE A NOUN (`رفتن`, `okumak`): the verb spelled as the page spells it is that word, and
    # `رف`, a noun only once letters are taken off it, is not.  A noun spelled so is the word as it stands (`Essen`).
    word = row.get("word") or ""
    if said["upos"] == "NOUN" and not any(_spelled(h, word, L) for h in good):
        good = [h for h in hits if h.get("pos") == "verb" and _spelled(h, word, L)] or good
    if not good or len(good) == len(hits):
        return 0
    # WHERE THE NORMALISER HAS READ THE WORD THE MODEL'S LEMMA CHOOSES NOTHING: it is of a word the model was shown instead
    # of the page's, and a treebank guesses a lemma for what it has not seen.  Its part of speech is what it is good for.
    named = [] if any(h.get("spoken") for h in hits) else [h for h in good if said["lemma"] and _named(h, said["lemma"], code, L)]
    # WHERE A BACKEND LISTS WHAT THE WORD CAN BE, AN ENTRY NONE OF ITS READINGS NAMES DOES NOT FIT, whatever its part of
    # speech: Starlang reads `erkenden` as a form of erken, and `erke` is a noun only by an accident of its letters.
    can_be = said.get("can_be") or ()
    if can_be and not named:
        good = [h for h in good if any(_named(h, x, code, L) for x in can_be)]
        if not good:
            return 0
    for h in named or good:
        h["fits"] = True
    return len(named or good)


def _first(row):
    """What fits first, in the order it had, and nothing lost.  Of a word's spoken readings too (lib/spoken.py): theirs
    is an order of likelier in general, and this sentence knows better."""
    hits = row.get("hits") or []
    good = [h for h in hits if h.get("fits")]
    moved = good + [h for h in hits if not h.get("fits")]
    if moved == hits:
        return False
    row["hits"] = moved
    return True


def _add_the_one_that_fits(c, row, tokens, code, L, said):
    """A word found only as other parts of speech than the sentence's: its lemma's entry of that part of speech, if
    the dictionary has one, joins them at the front -> True.  `fare` found only as a noun, in a sentence where it is a
    verb, is the case this is for; an entry found this way is real, and the others stay.  The lemma the sentence chose
    and no other: `değil` is also the imperative of `değmek` to a backend that reads it alone, and is not that here.
    A lemma two backends agreed on needs no part of speech: `erkenden` is erken, an adjective the sentence made a noun."""
    wanted = _wanted(said)
    hits = row.get("hits") or []
    lemma = said["lemma"]
    agreed = said.get("agreed") and lemma and not any(_named(h, lemma, code, L) for h in hits)
    # a word of content only: `چی` is a pronoun the model called an adverb, and چه, the adverb, is not what it means
    if not lemma or (not agreed and said["upos"] not in ("VERB", "AUX", "NOUN", "ADJ")):
        return False
    if not hits or any(h.get("spoken") for h in hits) or not (agreed or wanted) or (not agreed and any(h.get("pos") in wanted for h in hits)):
        return False
    have = {h.get("entry") for h in hits}
    surfaces = {t.surface for t in tokens}
    for form in _forms(code, lemma):
        if form in surfaces:
            continue
        found = lookup._hits_for(c, lookup._bare(form, L)) or lookup._hits_for(c, _unmarked(form))
        good = [h for h in found if (agreed or h.get("pos") in wanted) and h.get("entry") not in have]
        good = [h for h in good if _named(h, lemma, code, L)] or ([] if agreed else good[:1])
        if good:
            for h in good:
                h.pop("_tier", None)
                h["fits"] = True
            row["hits"] = (good + hits)[:lookup.MAX_HITS + 1]
            return True
    return False


def _rescue(c, row, tokens, code, L, said):
    """Look the row up under the lemmas its tokens offer -> True if one lands.  The lemma the sentence chose, and that is
    enough; else every reading that lands, in the order `_machine` put them: `öğretmenimdir` is öğretmen before it is
    öğretmek, and none of them has been ruled out."""
    tried = list(row.get("tried") or [])
    surfaces = {t.surface for t in tokens}
    offered = [said["lemma"]] if said["lemma"] else []
    offered += list(said.get("can_be") or ()) + [x for t in tokens for x in t.lemmas()]
    found, by = [], None
    for lemma in list(dict.fromkeys(x for x in offered if x))[:MAX_LEMMAS]:
        for form in _forms(code, lemma):
            # a form the old path tried, or the word itself, has already had its answer
            if form in surfaces or form in tried:
                continue
            bare = lookup._bare(form, L)
            hits = lookup._hits_for(c, bare) or lookup._hits_for(c, _unmarked(form))
            tried.append(form)
            if hits:
                by = by or form
                have = {h.get("entry") for h in found}
                found += [h for h in hits if h.get("entry") not in have]
        if found and lemma == said["lemma"]:
            break
    if found:
        row.update(hits=found[:lookup.MAX_HITS], kind="analyzer", tried=tried, via="by the analyzer's lemma %s" % by)
        for h in row["hits"]:
            h.pop("_tier", None)
        return True
    row["tried"] = tried
    return False


def apply(code, result, text, sentence="", mode="off", register=None):
    """The lookup's answer, with what `mode` allows.  The same object, whatever
    happens; `result["analysis"]` says why nothing was added, for whoever is
    looking into it."""
    if not result or mode not in ("show", "assist"):
        return result
    words = result.get("words") or []
    if not words:
        return result
    L = lookup.languages.get_or_default(code)
    source = unicodedata.normalize("NFC", text or "")
    context = unicodedata.normalize("NFC", sentence or "")
    # THE WHOLE SENTENCE, where the page sent one and the chunk is really in it
    # once.  These offsets are of this internal copy; nothing is written back.
    offset = 0
    whole = source
    if context and context.count(source) == 1:
        offset, whole = context.index(source), context
    read, spans = formal_view(code, whole, register)
    # with the syntax, where there is any: Turkish's morphology chooses nothing, and UDPipe's reads the sentence
    got = analyzer.analyze(code, read, syntax=True)
    result["analysis"] = {"outcome": got.outcome, "backend": got.backend, "formal": spans is not None,
                          "diagnostics": list(got.diagnostics)}
    if not got.ok:
        return result
    c = lookup._conn(code)
    at = offset
    end_of_chunk = offset + len(source)
    for row in words:
        word = row.get("word") or ""
        start = whole.find(word, at, end_of_chunk) if word else -1
        if start < 0:
            continue
        at = start + len(word)
        lo, hi = spans.get((start, at), (start, at)) if spans else (start, at)
        if spans and (start, at) not in spans:
            continue
        main = _main_token(got.within(lo, hi))
        said = _machine(main) if main is not None else None
        if said is None:
            continue
        tokens = [main]
        row["machine"] = said
        said["fit"] = _fits(row, said, code, L)
        if mode == "assist" and c is not None:
            if not row.get("hits"):
                said["rescued"] = _rescue(c, row, tokens, code, L, said)
            elif not said["fit"]:
                said["added"] = _add_the_one_that_fits(c, row, tokens, code, L, said)
            said["moved"] = _first(row)
        # THE DICTIONARY HAS THE LAST WORD ON WHAT A WORD CAN BE: a chip saying `noun` over entries that are all verbs is
        # the model's mistake on show.  It is not claimed, and what the model said stays in the record.
        wanted = ENTRY_POS.get(said["upos"])
        kinds = {h.get("pos") for h in row.get("hits") or []}
        if kinds and wanted and not kinds & set(wanted):
            said["here"] = False
        elif not said["lemma"] and not said["readings"] and len(kinds) > 1:
            said["here"] = False        # a guess, over entries of several kinds: nobody knows which
    return result
