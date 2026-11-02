# SPDX-License-Identifier: GPL-3.0-or-later
"""Farahidi behind lib/analyzer.py: every analysis an Arabic word can have, and
the lemma its sentence chooses.

Runs in lib/analyzerworker.py, the one program that imports farahidi.

PARSEH CUTS THE TOKENS (analyzer.source_tokens) and hands them over a sentence at
a time, so that a span is Parseh's and no token is ever rejoined from Farahidi's
own cleaned-up spelling.

WHAT IS CONTEXTUAL (TO-DO handoffs/03-farahidi.md, read from version 0.4.0's
disambiguate.py): the Viterbi pass chooses a LEMMA.  The stem and the root it
returns beside that lemma are the most frequent among the analyses of that
lemma, not chosen by the sentence, so they are LEXICAL here and no candidate is
marked as the one chosen: several candidates may share the lemma, and which of
them this is -- which case, which clitics, active or passive -- nobody has said.
"""
import dataclasses
import threading

import analysispins
import analyzer

NAME = "farahidi"

# A value this table lacks is not lost: it stays in the candidate's `raw`.
UPOS = {"اسم": "NOUN", "فعل": "VERB", "حرف": "PART", "اسم علم": "PROPN", "أداة": "PART"}
_VALUES = {
    "gender": ("Gender", {"مذكر": "Masc", "مؤنث": "Fem"}),
    "number": ("Number", {"مفرد": "Sing", "مثنى": "Dual", "جمع": "Plur"}),
    "person": ("Person", {"متكلم": "1", "مخاطب": "2", "غائب": "3"}),
    "tense": ("Tense", {"ماض": "Past", "مضارع": "Pres", "أمر": "Imp"}),
    "voice": ("Voice", {"معلوم": "Act", "مجهول": "Pass"}),
}
_CASES = {"مرفوع": "Nom", "منصوب": "Acc", "مجرور": "Gen"}
_MOODS = {"مرفوع": "Ind", "منصوب": "Sub", "مجزوم": "Jus"}


def _none(v):
    """Farahidi's "-" means there is none, not a linguistic value."""
    return None if v in (None, "", "-") else v


def candidate(rank, a):
    feats = {}
    for name, (key, table) in _VALUES.items():
        v = getattr(a, name, None)
        if v in table:
            feats[key] = table[v]
    cases = sorted({_CASES[i.case] for i in a.inflections if i.case in _CASES})
    moods = sorted({_MOODS[i.mood] for i in a.inflections if i.mood in _MOODS})
    if cases:
        feats["Case"] = ",".join(cases)      # what the unvowelled word allows, not one of them
    if moods:
        feats["Mood"] = ",".join(moods)
    clitics = tuple({"kind": kind, "form": x.form, "what": x.description or ""}
                    for kind, group in (("proclitic", a.proclitics), ("enclitic", a.enclitics))
                    for x in group)
    raw = dataclasses.asdict(a)
    raw = {k: v for k, v in raw.items() if v not in (None, (), [], "")}
    return analyzer.Candidate(source=NAME, rank=rank, lemma=_none(a.lemma), root=_none(a.root),
                              stem=_none(a.stem), vocalized=_none(a.diacritized),
                              upos=UPOS.get(a.pos), native=a.pos, feats=feats, clitics=clitics,
                              frequency=a.score, raw=_plain(raw))


def _plain(v):
    """What dataclasses.asdict leaves, in the shapes JSON has."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def build(code, text, sentences, analyses_of, disambiguate, context="", resources=()):
    """The Result, from token spans grouped by sentence and the two calls that
    speak to Farahidi; tests hand in their own.  A token count that changes is
    an answer about something else, and is a failure."""
    tokens, sents = [], []
    for n, spans in enumerate(sentences):
        sid = "s%d" % n
        surfaces = [text[s:e] for s, e in spans]
        chosen = disambiguate(surfaces)
        if len(chosen) != len(surfaces):
            raise analyzer.AlignmentError("Farahidi answered %d tokens for %d" % (len(chosen), len(surfaces)))
        sents.append((sid, spans[0][0], spans[-1][1]))
        for (s, e), surface, pick in zip(spans, surfaces, chosen):
            if pick.token != surface:
                raise analyzer.AlignmentError("Farahidi answered %r for %r" % (pick.token, surface))
            tid = "t%d" % len(tokens)
            if not pick.analyzed:
                # its lemma is the token itself, which is no lemma
                tokens.append(analyzer.Token(id=tid, start=s, end=e, surface=surface, sentence=sid,
                                             analyzed=False))
                continue
            cands = tuple(candidate(i, a) for i, a in enumerate(analyses_of(surface)))
            family = [c for c in cands if c.lemma == pick.lemma]
            kinds = {c.upos for c in family}
            word = analyzer.Word(id="%s.w%d" % (sid, len(tokens) + 1), token=tid, source=NAME,
                                 status=analyzer.CONTEXTUAL, lemma=_none(pick.lemma),
                                 upos=kinds.pop() if len(kinds) == 1 else None,
                                 start=s, end=e, surface=surface)
            select = analyzer.Selection(source=NAME, lemma=_none(pick.lemma),
                                        lemma_status=analyzer.CONTEXTUAL, analysis=None,
                                        analysis_status=analyzer.LEXICAL,
                                        stem=_none(pick.stem), root=_none(pick.root))
            tokens.append(analyzer.Token(id=tid, start=s, end=e, surface=surface, sentence=sid,
                                         words=(word,), candidates=cands, selection=select))
    return analyzer.Result(language=code, text=text, outcome=analyzer.OK, context=context,
                           backend=NAME, resources=resources, sentences=tuple(sents),
                           tokens=tuple(tokens))


class Backend:
    name = NAME

    def __init__(self):
        self._lock = threading.Lock()
        self._analyzer = self._disambiguator = None

    def languages(self):
        return ("ar",)

    def status(self, code):
        import importlib.util
        package = importlib.util.find_spec("farahidi") is not None
        return {"package": package, "resource": package, "usable": package,
                "loaded": self._disambiguator is not None, "version": analysispins.FARAHIDI_VERSION,
                "resource_id": "bundled",
                "why": "" if package else "Farahidi is not installed"}

    def analyze(self, code, text, syntax=False, context=""):
        import farahidi
        with self._lock:
            if self._disambiguator is None:
                self._analyzer = farahidi.Analyzer()
                self._disambiguator = farahidi.Disambiguator(self._analyzer)
            res = (analyzer.Resource(NAME, analysispins.FARAHIDI_VERSION, "bundled", "GPL-3.0-or-later"),)
            spans = analyzer.source_sentences(text, analyzer.source_tokens(text))
            try:
                return build(code, text, spans, self._analyzer.analyze,
                             self._disambiguator.disambiguate, context, res)
            except analyzer.AlignmentError as e:
                return analyzer.refusal(code, text, analyzer.FAILED, "farahidi: %s" % e, context, NAME)
