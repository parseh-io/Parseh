#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What an analyzer says of a stretch of text, small enough to go in a prompt.

    evidence.for_units("de", units, todo)    -> Evidence: {(unit key, chunk index): [entry, ...]}, diagnostics
    python3 lib/evidence.py de --text "Ich rufe dich morgen an."
    python3 lib/evidence.py de --file chapter.txt

THE SENTENCE IS ANALYZED ONCE, WHOLE, and what is said of it is then handed to the
chunks it was already cut into.  Chunking a sentence again, or analyzing a chunk as
if it were one, would read `an` without `rufe`.  The text analyzed is the sentence's
chunks joined as a reader meets them, so every offset here is a place in a string
made here from those chunks, and nothing is searched for by its spelling: a word
written twice is two entries in its own two chunks.

A TOKEN ACROSS A CHUNK'S SEAM IS NOT ATTACHED TO EITHER SIDE.  An edited seam may
stand inside what an analyzer calls one token; that token's evidence is left out and
counted in the diagnostics.  The seam is the person's and stays.

ONLY WHAT HELPS, AND A BUDGET.  Punctuation and a word with nothing to say beyond
itself are left out; so are trees and dictionary senses.  What is left is cut by the
limits below, the same way each time: the backends' own order within a token, the
words of the chunk in reading order.  The full candidates stay in the Result; what
was cut is counted.  An entry looks like:

    {"w": "rufe", "lemma": "rufen", "pos": "VERB", "feats": "Mood=Ind Person=1", "by": "sentence"}
    {"w": "an", "lemma": "an", "pos": "ADP", "part_of": "compound:prt of rufe", "by": "sentence"}
    {"w": "كتب", "lemma": "كَتَبَ", "by": "sentence", "root": "كتب", "others": [{"lemma": "كِتَاب", "pos": "NOUN"}]}
    {"w": "yüz", "by": "word alone", "readings": [{"lemma": "yüz", "pos": "NOUN", "parse": "..."}, ...]}

`by` says who chose: "sentence" is what the sentence chose, of the lemma where the
entry says no more; "word alone" is what the word can be anywhere.  No number
pretends to be a confidence.

This module writes nothing, and neither does its command line: an agent making a
book in place may run it over a text, and every file stays as it was.  It is never
an answer's field (lib/glossregion.py takes only the fields it knows), and Japanese
and Chinese have their words and readings in the chunk already, so they get none.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field

import analyzer

# the budgets: chosen by reading a page of each language's prompt, and tests hold them
MAX_ENTRIES = 5          # to a chunk
MAX_OTHERS = 3           # other readings of one word
MAX_CHUNK_CHARS = 420    # of JSON, to a chunk
MAX_REGION_CHARS = 16000 # of JSON, to a prompt: past this the chunks go without

USEFUL = ("Case", "Number", "Person", "Tense", "Aspect", "Mood", "Voice", "VerbForm", "Polarity",
          "Evident", "Person[psor]", "Number[psor]", "Gender", "Definite")
BINDS = ("compound:prt", "compound:lvc", "compound", "fixed", "flat", "aux", "cop")
LANGUAGES = tuple(analyzer.SYNTAX)      # Japanese and Chinese have their word line


@dataclass
class Evidence:
    chunks: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    resources: tuple = ()
    chars: int = 0

    def __bool__(self):
        return bool(self.chunks)


def _feats(feats):
    return " ".join("%s=%s" % (k, feats[k]) for k in USEFUL if k in feats)


def entry(token, by_id=None):
    """A token, as a prompt is told it -> {...}, or None where it says nothing
    worth the characters."""
    by_id = by_id or {}
    parsed = token.parsed()
    if parsed and all(w.upos == "PUNCT" for w in parsed):
        return None
    if not token.analyzed and not parsed:
        return None
    if token.candidates and all(c.upos == "PUNCT" for c in token.candidates):
        return None
    out = {"w": token.surface}
    sel = token.selection
    if sel and sel.lemma:
        out["lemma"] = sel.lemma
    if sel and sel.lemma_status == analyzer.CONTEXTUAL:
        out["by"] = "sentence"
    if parsed:
        if len(parsed) == 1:
            w = parsed[0]
            out.setdefault("lemma", w.lemma)
            if w.upos:
                out["pos"] = w.upos
            f = _feats(w.feats)
            if f:
                out["feats"] = f
        else:
            out["words"] = [{k: v for k, v in (("lemma", w.lemma), ("pos", w.upos), ("feats", _feats(w.feats))) if v}
                            for w in parsed]
        if any(w.status == analyzer.CONTEXTUAL for w in parsed):
            out["by"] = "sentence"
        for w in parsed:
            target = by_id.get((w.source, w.head))
            if target is not None and w.relation in BINDS:
                out["part_of"] = "%s of %s" % (w.relation, target)
                break
    if token.candidates:
        family = token.candidates
        if sel and sel.lemma:
            root = sel.root
            if root:
                out["root"] = root
            others = list(dict.fromkeys((c.lemma, c.upos) for c in family if c.lemma and c.lemma != sel.lemma))
            if others:
                out["others"] = [{k: v for k, v in (("lemma", a), ("pos", b)) if v} for a, b in others[:MAX_OTHERS]]
                if len(others) > MAX_OTHERS:
                    out["more"] = len(others) - MAX_OTHERS
        else:
            out.setdefault("by", "word alone")
            readings = []
            for c in family[:MAX_OTHERS]:
                r = {k: v for k, v in (("lemma", c.lemma), ("root", c.root if c.root != c.lemma else None),
                                       ("pos", c.upos), ("feats", _feats(c.feats))) if v}
                readings.append(r)
            out["readings"] = readings
            if len(family) > MAX_OTHERS:
                out["more"] = len(family) - MAX_OTHERS
    interesting = (out.get("feats") or out.get("words") or out.get("others") or out.get("readings")
                   or out.get("part_of") or (out.get("lemma") and out["lemma"] != token.surface))
    return out if interesting else None


def _surfaces(result):
    """{(source, word id): the surface of that word's token}: what a `part_of` is said of."""
    out = {}
    for t in result.tokens:
        for w in t.words + t.syntax:
            out[(w.source, w.id)] = t.surface
    return out


def _within_budget(entries):
    out = []
    size = 2
    for e in entries:
        n = len(json.dumps(e, ensure_ascii=False)) + 1
        if size + n > MAX_CHUNK_CHARS or len(out) >= MAX_ENTRIES:
            return out, len(entries) - len(out)
        out.append(e)
        size += n
    return out, 0


def project(result, spans):
    """A sentence's Result, and {key: (start, end)} of its chunks in that text ->
    ({key: [entry]}, {"seam": tokens cut by a seam, "cut": entries over a budget})."""
    surfaces = _surfaces(result)
    out, seam, cut = {}, 0, 0
    for key, (start, end) in spans.items():
        seam += sum(1 for t in result.crossing(start, end) if t.start >= start)
        entries = [e for e in (entry(t, surfaces) for t in result.within(start, end)) if e]
        kept, lost = _within_budget(entries)
        cut += lost
        if kept:
            out[key] = kept
    return out, {"seam": seam, "cut": cut}


def for_units(code, units, todo):
    """Evidence for every chunk `todo(chunk)` says is to do.  `units` are the
    sentences or captions of lib/glossregion.py, in order; a plain caption or a
    chunk with nothing to do gives context and asks nothing."""
    ev = Evidence()
    if code not in LANGUAGES:
        return ev
    L_sep = " "
    for u in units:
        chunks = u.get("chunks") or []
        if not chunks:
            continue
        pieces, spans, at = [], {}, 0
        for ch in chunks:
            spans[ch["j"]] = (at, at + len(ch["fa"]))
            pieces.append(ch["fa"])
            at += len(ch["fa"]) + len(L_sep)
        text = L_sep.join(pieces)
        wanted = {ch["j"] for ch in chunks if todo(ch)}
        if not wanted:
            continue
        got = analyzer.analyze(code, text, syntax=True)
        if not got.ok:
            for why in got.diagnostics or (got.outcome,):
                if why not in ev.diagnostics:
                    ev.diagnostics.append(why)
            continue
        ev.resources = got.resources or ev.resources
        said, counts = project(got, {j: spans[j] for j in wanted})
        if counts["seam"]:
            ev.diagnostics.append("%s: %d token(s) cross a chunk's seam, left out"
                                  % (u.get("at") or u.get("i"), counts["seam"]))
        if counts["cut"]:
            ev.diagnostics.append("%s: %d word(s) over a chunk's budget, left out"
                                  % (u.get("at") or u.get("i"), counts["cut"]))
        for j in sorted(said):
            size = len(json.dumps(said[j], ensure_ascii=False))
            if ev.chars + size > MAX_REGION_CHARS:
                ev.diagnostics.append("the region's budget of %d characters is spent: the rest go without"
                                      % MAX_REGION_CHARS)
                return ev
            ev.chars += size
            ev.chunks[(u.get("key", u.get("i")), j)] = said[j]
    return ev


def for_text(code, text):
    """What the helper prints: every sentence of a text with what is said of it."""
    got = analyzer.analyze(code, text, syntax=True)
    out = {"language": code, "outcome": got.outcome, "backend": got.backend,
           "diagnostics": list(got.diagnostics), "sentences": []}
    if got.ok:
        surfaces = _surfaces(got)
        for sid, s, e in got.sentences:
            said = [x for x in (entry(t, surfaces) for t in got.tokens if t.sentence == sid) if x]
            out["sentences"].append({"text": text[s:e], "analysis": said})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="What an analyzer says of a text.  Reads; writes nothing.")
    p.add_argument("language")
    p.add_argument("--text")
    p.add_argument("--file")
    a = p.parse_args(argv)
    if (a.text is None) == (a.file is None):
        p.error("give --text or --file")
    text = a.text
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    json.dump(for_text(a.language, text), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
