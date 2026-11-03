#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What a linguistic analyzer may say about a text, whichever analyzer says it.

    analyzer.available("de")              can something analyze German here, now?
    analyzer.about("de")                  what would, what it lacks, and why
    analyzer.analyze("de", text)          morphology -> Result
    analyzer.analyze("de", text, syntax=True)        ...and dependencies
    analyzer.clear_cache()                after an install, a removal, a new model

Standard library only, and it imports no analyzer: serve.py may be running a
Python that has none of them.  UDPipe, Farahidi and Starlang run in a program
of their own (lib/analyzerworker.py, in the environment lib/getanalysis.py
makes), and everything that uses them -- lookup, the chunker, the evidence of a
prompt -- knows only the records below.  Adding or repairing an analyzer
changes none of those.

THE SOURCE IS NEVER REWRITTEN.  A token is a half-open slice [start, end) of the
exact text that was asked about, in Python's Unicode characters, and validate()
holds every result to `text[start:end] == surface`.  Nothing is normalised on
the way: not the marks, not a ZWNJ, not the spaces, which remain in the gaps
between the tokens.  A result that cannot prove that is a failure, not an
approximation.

A TOKEN IS NOT A WORD.  `Zum` is one token of the text and two syntactic words,
`zu` and `dem`, neither of them a piece of what was written: such a word has no
span of its own, only its parent token.

WHAT WAS CHOSEN, AND BY WHAT, IS SAID.  A candidate is what a word can be; a
Selection is what a backend chose for this sentence, and its `lemma_status` and
`analysis_status` are separate because Farahidi chooses a lemma by context and
leaves the rest of the analysis to frequency.  CONTEXTUAL means chosen by the
sentence; LEXICAL means true of the word anywhere.  No backend's order is a
confidence, and none is invented here.

TWO BACKENDS, TWO VOICES.  Arabic and Turkish take their morphology from one
backend and may take their syntax from UDPipe.  The two are paired only where
their tokens are the same span of the same text, never by position in a list,
and UDPipe's words go in `Token.syntax` beside the first backend's, each saying
whose it is: a disagreement between them stays visible.

AN ANSWER IS ALWAYS GIVEN.  `analyze` raises for a programming error and for
nothing else: no package, no model, a language nobody covers, an analyzer that
fell over -- each is a Result whose `outcome` says so, and the caller goes on
the way it went before there were analyzers.

Dependencies stay inside their sentence.  A word's id is "s<sentence>.w<n>" and
its head an id of the same sentence and the same source, or None for the root;
validate() refuses anything else.  An empty CoNLL-U node is dropped by the
adapter that met it, with a diagnostic, and nothing may point at it.
"""
import collections
import threading
import types
from dataclasses import dataclass, field

import languages

SCHEMA = 1

# what became of the request
OK = "ok"                    # tokens, proved against the text
EMPTY = "empty"              # nothing in the text to analyze: an answer, not a fault
UNAVAILABLE = "unavailable"  # the language has a backend, and it is not ready here
UNSUPPORTED = "unsupported"  # no backend covers this language at all
FAILED = "failed"            # a backend ran and its answer could not be used
OUTCOMES = (OK, EMPTY, UNAVAILABLE, UNSUPPORTED, FAILED)

CONTEXTUAL = "contextual"    # chosen by this sentence
LEXICAL = "lexical"          # true of the word anywhere; an order is frequency at best
STATUSES = (CONTEXTUAL, LEXICAL)

# who speaks for a language, when nobody asks for a backend by name: the
# registry's `analysis` (lib/languages.json), so a language is added in one place
MORPHOLOGY = {L.code: L.analysis["morphology"] for L in languages.LANGS.values() if L.analysis["morphology"]}
SYNTAX = {L.code: L.analysis["syntax"] for L in languages.LANGS.values() if L.analysis["syntax"]}

MAX_TEXT = 200_000           # characters in one request: a chapter, not a shelf
MAX_RESULTS = 256            # results kept, oldest use first out


class AlignmentError(ValueError):
    """A backend's answer does not fit the text it was asked about."""


class BackendError(RuntimeError):
    """A backend could not answer, for a reason a person can be told."""


def _frozen(mapping):
    return types.MappingProxyType(dict(mapping or {}))


@dataclass(frozen=True)
class Word:
    """One syntactic word.  `start` and `end` are there only where the word is
    a literal piece of the text; `token` is always there."""
    id: str
    token: str
    source: str
    status: str = LEXICAL
    lemma: str = None
    upos: str = None
    native: str = None
    feats: object = field(default_factory=lambda: _frozen({}))
    head: str = None
    relation: str = None
    start: int = None
    end: int = None
    surface: str = None

    def __post_init__(self):
        object.__setattr__(self, "feats", _frozen(self.feats))

    @property
    def sentence(self):
        return self.id.split(".", 1)[0]


@dataclass(frozen=True)
class Candidate:
    """What a word can be, in the backend's own order.  `rank` is that order
    and nothing more.  `raw` keeps what the backend said in its own words,
    including any tag this code has no name for."""
    source: str
    rank: int
    lemma: str = None
    root: str = None
    stem: str = None
    vocalized: str = None
    upos: str = None
    native: str = None
    feats: object = field(default_factory=lambda: _frozen({}))
    clitics: tuple = ()
    frequency: float = None
    raw: object = field(default_factory=lambda: _frozen({}))

    def __post_init__(self):
        object.__setattr__(self, "feats", _frozen(self.feats))
        object.__setattr__(self, "raw", _frozen(self.raw))
        object.__setattr__(self, "clitics", tuple(self.clitics or ()))


@dataclass(frozen=True)
class Selection:
    """What a backend chose among a token's candidates.  `analysis` is an index
    into them, or None where only a lemma was chosen."""
    source: str
    lemma: str = None
    lemma_status: str = LEXICAL
    analysis: int = None
    analysis_status: str = LEXICAL
    stem: str = None
    root: str = None


@dataclass(frozen=True)
class Token:
    id: str
    start: int
    end: int
    surface: str
    sentence: str
    words: tuple = ()        # the first backend's syntactic words
    candidates: tuple = ()   # all of them, however many
    selection: Selection = None
    syntax: tuple = ()       # another backend's words over this same span
    analyzed: bool = True    # False: the backend knows nothing of this token

    def __post_init__(self):
        for name in ("words", "candidates", "syntax"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))

    def parsed(self):
        """The words that carry dependencies: another backend's where there
        are any, else this backend's own."""
        return self.syntax or self.words

    def lemmas(self):
        """Every lemma on offer, what a sentence chose first, then what the word
        can be anywhere in the backend's own order, each once."""
        out = []
        if self.selection and self.selection.lemma:
            out.append(self.selection.lemma)
        out.extend(w.lemma for w in self.words + self.syntax if w.lemma)
        out.extend(c.lemma for c in self.candidates if c.lemma)
        return list(dict.fromkeys(out))


@dataclass(frozen=True)
class Resource:
    """What produced an answer: enough to tell it from the answer of any other
    version, and for a person to see where it came from."""
    backend: str
    version: str = ""
    resource: str = ""
    licence: str = ""


@dataclass(frozen=True)
class Result:
    language: str
    text: str
    outcome: str
    context: str = ""
    backend: str = ""
    resources: tuple = ()
    diagnostics: tuple = ()
    sentences: tuple = ()    # ((id, start, end), ...)
    tokens: tuple = ()
    schema: int = SCHEMA

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError("no such outcome: %r" % (self.outcome,))
        for name in ("resources", "diagnostics", "sentences", "tokens"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))

    @property
    def ok(self):
        return self.outcome == OK

    def within(self, start, end):
        """The tokens wholly inside a span of the text, in order."""
        return [t for t in self.tokens if t.start >= start and t.end <= end]

    def crossing(self, start, end):
        """The tokens that begin inside a span and end outside it, or the
        reverse: what a chunk's seam cuts through."""
        return [t for t in self.tokens if t.start < end and t.end > start
                and not (t.start >= start and t.end <= end)]


def validate(result):
    """Raise AlignmentError unless every token is what the text says it is and
    every dependency stays in its sentence.  Returns the result."""
    text = result.text
    at = 0
    ids, word_ids = set(), {}
    spans = {sid: (s, e) for sid, s, e in result.sentences}
    if len(spans) != len(result.sentences):
        raise AlignmentError("two sentences share an id")
    for t in result.tokens:
        if t.id in ids:
            raise AlignmentError("token id %s twice" % t.id)
        ids.add(t.id)
        if not (isinstance(t.start, int) and isinstance(t.end, int)) or t.start < at or t.end <= t.start:
            raise AlignmentError("token %s [%r, %r) is out of order or empty" % (t.id, t.start, t.end))
        if t.end > len(text) or text[t.start:t.end] != t.surface:
            raise AlignmentError("token %s says %r where the text has %r"
                                 % (t.id, t.surface, text[t.start:t.end]))
        if t.sentence not in spans:
            raise AlignmentError("token %s is in a sentence that was not declared" % t.id)
        if t.start < spans[t.sentence][0] or t.end > spans[t.sentence][1]:
            raise AlignmentError("token %s stands outside its sentence" % t.id)
        at = t.end
        for w in t.words + t.syntax:
            if w.token != t.id:
                raise AlignmentError("word %s claims token %s from token %s" % (w.id, w.token, t.id))
            if (w.source, w.id) in word_ids:
                raise AlignmentError("word id %s twice" % w.id)
            word_ids[(w.source, w.id)] = w
            if w.status not in STATUSES:
                raise AlignmentError("word %s has no status" % w.id)
            if (w.start is None) != (w.end is None):
                raise AlignmentError("word %s has half a span" % w.id)
            if w.start is not None:
                if w.start < t.start or w.end > t.end or text[w.start:w.end] != w.surface:
                    raise AlignmentError("word %s says %r where the text has %r"
                                         % (w.id, w.surface, text[w.start:w.end]))
        if t.selection is not None:
            s = t.selection
            if s.lemma_status not in STATUSES or s.analysis_status not in STATUSES:
                raise AlignmentError("token %s has a selection of no status" % t.id)
            if s.analysis is not None and not 0 <= s.analysis < len(t.candidates):
                raise AlignmentError("token %s selects a candidate it does not have" % t.id)
    for (source, wid), w in word_ids.items():
        if w.head is None:
            continue
        target = word_ids.get((source, w.head))
        if target is None:
            raise AlignmentError("word %s has a head that is not there: %s" % (wid, w.head))
        if target.sentence != w.sentence:
            raise AlignmentError("word %s has its head in another sentence" % wid)
    return result


def refusal(code, text, outcome, why, context="", backend=""):
    return Result(language=code, text=text, outcome=outcome, context=context,
                  backend=backend, diagnostics=(why,) if why else ())


# ---------------------------------------------------------------- the backends
#
# A backend is anything with
#     name                       "udpipe"
#     languages()                the codes it covers
#     status(code)               {"package", "resource", "usable", "loaded", "why", "version", "resource_id"}
#     analyze(code, text, syntax, context) -> Result (unvalidated)
# `status` imports nothing heavy, loads nothing and asks nobody over a network.
# It may raise only for a programming error.

_LOCK = threading.RLock()
_BACKENDS = {}
_defaults_loaded = False
_CACHE = collections.OrderedDict()
_generation = 0


def register(backend):
    """Add or replace a backend: what it answered before does not stand."""
    with _LOCK:
        _BACKENDS[backend.name] = backend
    clear_cache()


def unregister(name):
    with _LOCK:
        _BACKENDS.pop(name, None)
    clear_cache()


def reset(backends=()):
    """Exactly these backends, and no defaults: what a test asks for."""
    global _defaults_loaded
    with _LOCK:
        _BACKENDS.clear()
        _defaults_loaded = True
        for b in backends:
            _BACKENDS[b.name] = b
    clear_cache()


def _loaded():
    """The backends, the real ones arriving the first time anybody asks."""
    global _defaults_loaded
    with _LOCK:
        if not _defaults_loaded:
            _defaults_loaded = True
            import getanalysis
            for b in getanalysis.backends():
                _BACKENDS.setdefault(b.name, b)
        return dict(_BACKENDS)


def clear_cache():
    """Forget every result.  A request already running will not put its answer
    back: it was asked of what has just changed."""
    global _generation
    with _LOCK:
        _generation += 1
        _CACHE.clear()


def _status(backend, code):
    st = dict(backend.status(code) or {})
    st.setdefault("usable", False)
    st.setdefault("why", "")
    return st


def _chosen(code, backend=None):
    """(morphology backend name, syntax backend name), by request or by table."""
    return backend or MORPHOLOGY.get(code), SYNTAX.get(code)


def available(code, backend=None, syntax=False):
    """Is there a usable backend for this language now?  It loads nothing."""
    backends = _loaded()
    name, syn = _chosen(code, backend)
    b = backends.get(name)
    if b is None or code not in b.languages() or not _status(b, code)["usable"]:
        return False
    if syntax and name != syn:
        s = backends.get(syn)
        return bool(s and code in s.languages() and _status(s, code)["usable"])
    return True


def about(code, backend=None):
    """Who would answer for this language, and how ready each is.  It loads
    nothing and asks nobody: {"language", "morphology": {...}, "syntax": {...}}."""
    backends = _loaded()
    name, syn = _chosen(code, backend)
    out = {"language": code, "morphology": None, "syntax": None}
    for key, who in (("morphology", name), ("syntax", syn)):
        b = backends.get(who)
        if b is not None and code in b.languages():
            out[key] = dict(_status(b, code), backend=who)
    return out


def _identity(backend, code):
    st = _status(backend, code)
    return (backend.name, str(st.get("version") or ""), str(st.get("resource_id") or ""))


def analyze(code, text, syntax=False, backend=None, context=""):
    """A Result for `text`, always: see the top of this file.  `context` tells
    apart two requests for the same words from different places, if that ever
    matters to a backend; it is part of what a result is remembered by."""
    text = text if isinstance(text, str) else ""
    backends = _loaded()
    name, syn = _chosen(code, backend)
    primary = backends.get(name)
    if primary is None or code not in primary.languages():
        return refusal(code, text, UNSUPPORTED, "no analyzer covers %s" % code, context, name or "")
    if not text.strip():
        return Result(language=code, text=text, outcome=EMPTY, context=context, backend=name)
    if len(text) > MAX_TEXT:
        return refusal(code, text, FAILED, "%d characters is more than one request may ask about"
                       % len(text), context, name)
    st = _status(primary, code)
    if not st["usable"]:
        return refusal(code, text, UNAVAILABLE, st["why"] or "%s is not ready" % name, context, name)
    second = backends.get(syn) if syntax and syn != name else None
    if second is not None and (code not in second.languages() or not _status(second, code)["usable"]):
        second = None
    key = (SCHEMA, code, text, context, syntax, _identity(primary, code),
           _identity(second, code) if second else None)
    with _LOCK:
        got = _CACHE.get(key)
        if got is not None:
            _CACHE.move_to_end(key)
            return got
        generation = _generation
    result = _run(primary, code, text, syntax and syn == name, context)
    if result.ok and syntax and syn != name:
        result = _with_syntax(result, second, code, text, context, syn)
    if result.outcome in (OK, EMPTY):
        # a failure is not remembered: the next request may find it mended
        with _LOCK:
            if generation == _generation:
                _CACHE[key] = result
                while len(_CACHE) > MAX_RESULTS:
                    _CACHE.popitem(last=False)
    return result


def _run(backend, code, text, syntax, context):
    try:
        got = backend.analyze(code, text, syntax, context)
    except BackendError as e:
        return refusal(code, text, FAILED, "%s: %s" % (backend.name, e), context, backend.name)
    if got.text != text or got.language != code:
        return refusal(code, text, FAILED, "%s answered about another text" % backend.name,
                       context, backend.name)
    if got.outcome == OK and not got.tokens:
        return Result(language=code, text=text, outcome=EMPTY, context=context,
                      backend=backend.name, resources=got.resources, diagnostics=got.diagnostics)
    try:
        return validate(got)
    except AlignmentError as e:
        return refusal(code, text, FAILED, "%s: %s" % (backend.name, e), context, backend.name)


def _with_syntax(result, second, code, text, context, syn):
    """A morphology Result with another backend's words beside its own, on the
    tokens that are the same span in both.  Its failure costs only the syntax."""
    if second is None:
        return _noted(result, "%s is not ready: no syntax" % syn)
    other = _run(second, code, text, True, context)
    if not other.ok:
        return _noted(result, *(other.diagnostics or ("%s: %s" % (syn, other.outcome),)))
    composed = compose(result, other)
    try:
        return validate(composed)
    except AlignmentError as e:
        return _noted(result, "the syntax of %s does not fit: %s" % (syn, e))


def _noted(result, *why):
    return Result(**dict(_fields(result), diagnostics=result.diagnostics + tuple(why)))


def _fields(record):
    return {f: getattr(record, f) for f in record.__dataclass_fields__}


def compose(morphology, syntax):
    """`morphology`'s tokens, each with the words `syntax` has over the SAME
    span.  Any other pairing would be a guess, so a token the two cut differently
    keeps only its own words, and a word whose head fell out with such a token
    loses the arc rather than point at nothing.  Sentences are the second
    backend's for its words: their ids say whose they are, by `source`."""
    by_span = {(t.start, t.end): t for t in syntax.tokens}
    kept = {}
    tokens = []
    missed = 0
    for t in morphology.tokens:
        other = by_span.get((t.start, t.end))
        if other is None or not other.words:
            missed += 1
            tokens.append(t)
            continue
        kept[t.id] = other
        tokens.append(t)
    present = {w.id for o in kept.values() for w in o.words}
    done = []
    for t in tokens:
        other = kept.get(t.id)
        if other is None:
            done.append(t)
            continue
        words = tuple(Word(**dict(_fields(w), token=t.id,
                                  head=w.head if w.head in present else None,
                                  relation=w.relation if w.head is None or w.head in present else None))
                      for w in other.words)
        done.append(Token(**dict(_fields(t), syntax=words)))
    notes = morphology.diagnostics
    if missed:
        notes = notes + ("%d token(s) cut differently by %s: no syntax for them"
                         % (missed, syntax.backend),)
    return Result(**dict(_fields(morphology), tokens=tuple(done), diagnostics=notes,
                         backend="%s+%s" % (morphology.backend, syntax.backend),
                         resources=morphology.resources + syntax.resources))


# ---------------------------------------------------------------- across a pipe
#
# A Result crosses from lib/analyzerworker.py to the server as JSON, and back
# through validate(): what comes down the pipe is held to the text like
# anything else.

def to_plain(result):
    def word(w):
        return {k: (dict(v) if k == "feats" else v) for k, v in _fields(w).items() if v not in (None, {})}

    def cand(c):
        out = {}
        for k, v in _fields(c).items():
            if k in ("feats", "raw"):
                v = dict(v)
            if k == "clitics":
                v = [dict(x) if not isinstance(x, str) else x for x in v]
            if v not in (None, {}, [], ""):
                out[k] = v
        return out

    return {"schema": result.schema, "language": result.language, "text": result.text,
            "outcome": result.outcome, "context": result.context, "backend": result.backend,
            "resources": [_fields(r) for r in result.resources],
            "diagnostics": list(result.diagnostics),
            "sentences": [list(s) for s in result.sentences],
            "tokens": [{"id": t.id, "start": t.start, "end": t.end, "surface": t.surface,
                        "sentence": t.sentence, "analyzed": t.analyzed,
                        "words": [word(w) for w in t.words],
                        "syntax": [word(w) for w in t.syntax],
                        "candidates": [cand(c) for c in t.candidates],
                        "selection": _fields(t.selection) if t.selection else None}
                       for t in result.tokens]}


def from_plain(d):
    if d.get("schema") != SCHEMA:
        raise AlignmentError("schema %r, and this code reads %d" % (d.get("schema"), SCHEMA))
    return Result(
        language=d["language"], text=d["text"], outcome=d["outcome"], context=d.get("context", ""),
        backend=d.get("backend", ""), resources=tuple(Resource(**r) for r in d.get("resources", ())),
        diagnostics=tuple(d.get("diagnostics", ())),
        sentences=tuple(tuple(s) for s in d.get("sentences", ())),
        tokens=tuple(Token(id=t["id"], start=t["start"], end=t["end"], surface=t["surface"],
                           sentence=t["sentence"], analyzed=t.get("analyzed", True),
                           words=tuple(Word(**w) for w in t.get("words", ())),
                           syntax=tuple(Word(**w) for w in t.get("syntax", ())),
                           candidates=tuple(Candidate(**c) for c in t.get("candidates", ())),
                           selection=Selection(**t["selection"]) if t.get("selection") else None)
                     for t in d.get("tokens", ())))


# ---------------------------------------------------------------- source tokens
#
# Two backends take tokens from Parseh rather than making their own, and these
# are those tokens: a run of letters, digits and marks, with what joins a word
# from inside (ZWNJ, an apostrophe or hyphen between letters), and every other
# non-space character alone.  Nothing is decided about a word here.

_JOINERS = "‌‍'’-ـ"
_ENDS = ".!?…؟۔।。！？\n"


def _is_wordy(ch):
    import unicodedata
    cat = unicodedata.category(ch)
    return cat[0] in "LNM"


def source_tokens(text):
    """[(start, end)] of the tokens of `text`."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if not _is_wordy(ch):
            out.append((i, i + 1))
            i += 1
            continue
        j = i + 1
        while j < n:
            if _is_wordy(text[j]):
                j += 1
            elif text[j] in _JOINERS and j + 1 < n and _is_wordy(text[j + 1]):
                j += 2
            else:
                break
        out.append((i, j))
        i = j
    return out


def source_sentences(text, spans):
    """Group token spans into sentences -> [[(start, end), ...]]: a sentence
    ends after a token that is a sentence's closing mark, and at a line end."""
    out, cur = [], []
    prev_end = 0
    for s, e in spans:
        if cur and "\n" in text[prev_end:s]:
            out.append(cur)
            cur = []
        cur.append((s, e))
        prev_end = e
        if e - s == 1 and text[s] in _ENDS:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out
