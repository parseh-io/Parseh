# SPDX-License-Identifier: GPL-3.0-or-later
"""Starlang's Turkish morphology behind lib/analyzer.py: every parse a word can
have, none of them chosen.

Runs in lib/analyzerworker.py, the one program that imports it.

NOTHING HERE IS CONTEXTUAL.  The analyzer reads a word alone, and the first
parse is the first it found (`için` is `iç` before it is the postposition).
Starlang's disambiguation package ships no trained model, only a root list, so
no Selection is made: the sentence's say, where anyone has it, is UDPipe's
words beside these (lib/analyzer.py compose).

A ROOT IS NOT A HEADWORD.  `gel` is the root of `geldim`, and a dictionary has
`gelmek`.  A verb's candidate carries both, `root` and `lemma`, the citation
form made by vowel harmony alone; only a dictionary can say it exists
(lib/lookup.py asks).
"""
import threading

import analysispins
import analyzer

NAME = "starlang"

UPOS = {"NOUN": "NOUN", "PROP": "PROPN", "ADJ": "ADJ", "VERB": "VERB", "ADVERB": "ADV", "ADV": "ADV",
        "NUM": "NUM", "PRON": "PRON", "CONJ": "CCONJ", "POSTP": "ADP", "INTERJ": "INTJ",
        "DET": "DET", "QUES": "AUX", "PUNC": "PUNCT"}
_CASE = {"NOM": "Nom", "ACC": "Acc", "DAT": "Dat", "LOC": "Loc", "ABL": "Abl", "GEN": "Gen", "INS": "Ins",
         "EQU": "Equ"}
_TENSE = {"PAST": ("Tense", "Past"), "NARR": ("Evident", "Nfh"), "FUT": ("Tense", "Fut"),
          "PROG1": ("Aspect", "Prog"), "PROG2": ("Aspect", "Prog"), "AOR": ("Aspect", "Hab"),
          "PRES": ("Tense", "Pres")}
_MOOD = {"IMP": "Imp", "OPT": "Opt", "NEC": "Nec", "DESR": "Des", "ABLE": "Pot", "COND": "Cnd"}
_VOICE = {"PASS": "Pass", "CAUS": "Cau", "REFLEX": "Rfl", "RECIP": "Rcp"}
_FORM = {"PRESPART": "Part", "PASTPART": "Part", "FUTPART": "Part", "NARRPART": "Part", "AORPART": "Part",
         "BYDOINGSO": "Conv", "WHILE": "Conv", "WHEN": "Conv", "SINCEDOINGSO": "Conv", "ADAMANTLY": "Conv",
         "AFTERDOINGSO": "Conv", "WITHOUTHAVINGDONESO": "Conv", "INF": "Vnoun", "INF2": "Vnoun", "INF3": "Vnoun",
         "PASTPARTICIPLE": "Part"}
_BACK = "aıou"
_VOWELS = "aeıioöuü"


def citation(root):
    """gel -> gelmek, yap -> yapmak."""
    last = next((ch for ch in reversed(root.lower()) if ch in _VOWELS), "e")
    return root + ("mak" if last in _BACK else "mek")


def feats_of(tags):
    """The features the transition's tags name, the last one of a kind standing:
    `evlerimizden` is Plur, Psor 1 Plur, Abl.  A tag this table lacks stays in
    the candidate's `raw`."""
    out = {}
    for tag in tags:
        if tag in _CASE:
            out["Case"] = _CASE[tag]
        elif tag in _TENSE:
            key, val = _TENSE[tag]
            out[key] = val
        elif tag in _MOOD:
            out["Mood"] = _MOOD[tag]
        elif tag in _VOICE:
            out["Voice"] = _VOICE[tag]
        elif tag in _FORM:
            out["VerbForm"] = _FORM[tag]
        elif tag == "NEG":
            out["Polarity"] = "Neg"
        elif tag == "POS":
            out["Polarity"] = "Pos"
        elif len(tag) == 4 and tag[0] == "A" and tag[1] in "123" and tag[2:] in ("SG", "PL"):
            out["Person"] = tag[1]
            out["Number"] = "Sing" if tag[2:] == "SG" else "Plur"
        elif len(tag) == 4 and tag[0] == "P" and tag[1] in "123" and tag[2:] in ("SG", "PL"):
            out["Person[psor]"] = tag[1]
            out["Number[psor]"] = "Sing" if tag[2:] == "SG" else "Plur"
    return out


def candidate(rank, root, parse_text, final_pos):
    """A candidate from Starlang's own string, `yap+VERB^DB+VERB+PASS+NEG+FUT+A3PL+PAST`:
    the root, then its inflectional groups between each `^DB`."""
    groups = parse_text.split("+", 1)[1].split("^DB+") if "+" in parse_text else []
    tags = [t for g in groups for t in g.split("+")]
    first = tags[0] if tags else None
    upos = UPOS.get("PROP" if "PROP" in tags else (final_pos or first))
    lemma = citation(root) if first == "VERB" else root
    return analyzer.Candidate(source=NAME, rank=rank, lemma=lemma, root=root, stem=root, upos=upos,
                              native=final_pos or first, feats=feats_of(tags),
                              raw={"parse": parse_text, "groups": groups})


def build(code, text, sentences, parses_of, context="", resources=()):
    """The Result; `parses_of(surface)` -> [(root, parse string, final part of speech)]."""
    tokens, sents = [], []
    for n, spans in enumerate(sentences):
        sid = "s%d" % n
        sents.append((sid, spans[0][0], spans[-1][1]))
        for s, e in spans:
            surface = text[s:e]
            cands = tuple(candidate(i, *p) for i, p in enumerate(parses_of(surface)))
            tokens.append(analyzer.Token(id="t%d" % len(tokens), start=s, end=e, surface=surface,
                                         sentence=sid, candidates=cands, analyzed=bool(cands)))
    return analyzer.Result(language=code, text=text, outcome=analyzer.OK, context=context, backend=NAME,
                           resources=resources, sentences=tuple(sents), tokens=tuple(tokens))


class Backend:
    name = NAME

    def __init__(self):
        self._lock = threading.Lock()
        self._fsm = None

    def languages(self):
        return ("tr",)

    def status(self, code):
        import importlib.util
        package = importlib.util.find_spec("MorphologicalAnalysis") is not None
        return {"package": package, "resource": package, "usable": package, "loaded": self._fsm is not None,
                "version": analysispins.STARLANG_VERSION, "resource_id": "bundled",
                "why": "" if package else "Starlang's Turkish analyzer is not installed"}

    def _parses(self, surface):
        got = self._fsm.morphologicalAnalysis(surface)
        out = []
        for i in range(got.size()):
            p = got.getFsmParse(i)
            out.append((p.getWord().getName(), str(p), p.getFinalPos()))
        return out

    def analyze(self, code, text, syntax=False, context=""):
        with self._lock:
            if self._fsm is None:
                from MorphologicalAnalysis.FsmMorphologicalAnalyzer import FsmMorphologicalAnalyzer
                self._fsm = FsmMorphologicalAnalyzer()
            res = (analyzer.Resource(NAME, analysispins.STARLANG_VERSION, "bundled", "GPL-3.0"),)
            spans = analyzer.source_sentences(text, analyzer.source_tokens(text))
            return build(code, text, spans, self._parses, context, res)
