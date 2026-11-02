# SPDX-License-Identifier: GPL-3.0-or-later
"""What an analyzer may add to a lookup, after the lookup has been made.

    lookupassist.apply("de", result, text, sentence, "assist")

AFTER, AND NOT THROUGH `pieces=`.  lib/lookup.py's `pieces` replaces the ordinary
pairing of words, and with it the joins of a prefix written apart (Persian
`نمی سوزانند`), the spoken pass and the capital at a sentence's start.  Everything
the old path finds, it finds here too, because it has already run: this function
receives its answer and only ever adds to it.

THREE THINGS, AND ONLY WHERE lib/analysisconfig.py SAYS:

  show      each word gets `machine`: what the analyzer read it as, saying which
            analyzer and whether its sentence chose that.  Nothing else changes.
  assist    the same, and a word the dictionary did NOT find is looked for under
            the analyzer's lemmas.  A lemma counts only if it lands on a real
            entry: a wrong lemma finds nothing or something the word's row says
            came from the analyzer (`kind`: "analyzer", `via`), never a silent
            replacement.  And where a word found several entries and the
            SENTENCE chose a lemma, the entries of that lemma move to the front;
            none is dropped.

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


def _machine(token):
    """What a row may say about its word, short: the first choice and who made it."""
    sel = token.selection
    word = next(iter(token.words), None) or next(iter(token.syntax), None)
    cand = token.candidates[0] if token.candidates else None
    lemma = (sel.lemma if sel else None) or (word.lemma if word else None) or (cand.lemma if cand else None)
    if not lemma:
        return None
    src = sel or word or cand
    status = (sel.lemma_status if sel else None) or (word.status if word else analyzer.LEXICAL)
    upos = (word.upos if word else None) or (cand.upos if cand else None)
    feats = dict(word.feats) if word else dict(cand.feats) if cand else {}
    return {"lemma": lemma, "upos": upos or "", "feats": feats, "source": src.source, "status": status,
            "readings": len(token.candidates)}


def _same(a, b, L):
    return lookup._bare(a, L) == lookup._bare(b, L) or _unmarked(a) == _unmarked(b)


def _unmarked(s):
    """Without its marks: كِتَاب and كتاب are one word to a row of the dictionary."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if not unicodedata.category(ch).startswith("M"))


def _rescue(c, row, tokens, code, L):
    """Look the row up under each lemma its tokens offer -> True if one lands."""
    tried = list(row.get("tried") or [])
    surfaces = {t.surface for t in tokens}
    offered = [x for t in tokens for x in t.lemmas()]
    for lemma in list(dict.fromkeys(offered))[:MAX_LEMMAS]:
        for form in _forms(code, lemma):
            # a form the old path tried, or the word itself, has already had its answer
            if form in surfaces or form in tried:
                continue
            bare = lookup._bare(form, L)
            hits = lookup._hits_for(c, bare) or lookup._hits_for(c, _unmarked(form))
            tried.append(form)
            if hits:
                row.update(hits=hits[:lookup.MAX_HITS], kind="analyzer", tried=tried,
                           via="by the analyzer's lemma %s" % form)
                for h in row["hits"]:
                    h.pop("_tier", None)
                return True
    row["tried"] = tried
    return False


def _rank(row, tokens, L):
    """The entries of the lemma this sentence chose, first -> True if any moved."""
    chosen = []
    for t in tokens:
        if t.selection and t.selection.lemma and t.selection.lemma_status == analyzer.CONTEXTUAL:
            chosen.append(t.selection.lemma)
    hits = row.get("hits") or []
    if not chosen or len(hits) < 2:
        return False
    def ours(h):
        return any(_same(h.get("headword") or "", lemma, L) for lemma in chosen)
    front = [h for h in hits if ours(h)]
    if not front or front[0] is hits[0] and all(ours(h) for h in hits[:len(front)]):
        return False
    row["hits"] = front + [h for h in hits if not ours(h)]
    return True


def apply(code, result, text, sentence="", mode="off"):
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
    got = analyzer.analyze(code, whole, syntax=False)
    result["analysis"] = {"outcome": got.outcome, "backend": got.backend,
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
        tokens = got.within(start, at)
        said = next((m for m in (_machine(t) for t in tokens) if m), None)
        if said is None:
            continue
        row["machine"] = said
        if mode == "assist":
            if not row.get("hits"):
                said["rescued"] = c is not None and _rescue(c, row, tokens, code, L)
            elif _rank(row, tokens, L):
                said["ranked"] = True
    return result
