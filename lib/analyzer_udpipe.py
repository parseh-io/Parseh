# SPDX-License-Identifier: GPL-3.0-or-later
"""UDPipe 1 behind lib/analyzer.py: lemma, part of speech, features and, when
asked, dependencies, for the nine languages lib/analysispins.py has a model of.

Runs in lib/analyzerworker.py, the one program that imports ufal.udpipe.

`tokenizer=ranges` makes UDPipe print where each token is, and those numbers are
the only source of a span here: nothing is searched for in the text.  A token
whose range does not slice to its form is a failed analysis, which validate()
would say too; it is said here first so the message names UDPipe.
"""
import os
import re
import threading
from collections import OrderedDict

import analysispins
import analyzer

NAME = "udpipe"
MODELS_KEPT = 3     # the languages held in memory, oldest use first out
_RANGE = re.compile(r"(?:^|\|)TokenRange=(\d+):(\d+)(?:\||$)")


def parse_feats(s):
    if not s or s == "_":
        return {}
    out = {}
    for part in s.split("|"):
        k, _, v = part.partition("=")
        if k and v:
            out[k] = v
    return out


def _column(v):
    return None if v == "_" else v


def from_conllu(conllu, code, text, syntax, context="", resources=()):
    """The output of a UDPipe pipeline -> a Result.  Raises analyzer.AlignmentError
    when a token has no range or its range is not its form."""
    tokens, sentences, notes = [], [], []
    n_sent = 0
    for block in conllu.split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln and not ln.startswith("#")]
        if not lines:
            continue
        sid = "s%d" % n_sent
        n_sent += 1
        mwt = {}            # a range line's words, by the id of the word it ends at
        pending = []        # (range_id, start, end, form)
        rows = []
        for ln in lines:
            col = ln.split("\t")
            if len(col) != 10:
                raise analyzer.AlignmentError("a CoNLL-U line of %d columns" % len(col))
            wid = col[0]
            if "." in wid:
                # an empty node has no place in the text and is nobody's parent
                notes.append("an empty node in %s was left out" % sid)
                continue
            if "-" in wid:
                first, last = wid.split("-", 1)
                at = _RANGE.search(col[9])
                if not at:
                    raise analyzer.AlignmentError("a multiword token with no range: %r" % col[1])
                mwt[int(first)] = (int(last), int(at.group(1)), int(at.group(2)), col[1])
                continue
            rows.append(col)
        ids = {col[0] for col in rows}
        words_of = []
        i = 0
        while i < len(rows):
            col = rows[i]
            wid = int(col[0])
            if wid in mwt:
                last, start, end, form = mwt[wid]
                group = [c for c in rows[i:] if int(c[0]) <= last]
                i += len(group)
                words_of.append((start, end, form, group, True))
                continue
            at = _RANGE.search(col[9])
            if not at:
                raise analyzer.AlignmentError("a token with no range: %r" % col[1])
            words_of.append((int(at.group(1)), int(at.group(2)), col[1], [col], False))
            i += 1
        if not words_of:
            continue
        sentences.append((sid, words_of[0][0], words_of[-1][1]))
        for start, end, form, group, multi in words_of:
            if text[start:end] != form:
                raise analyzer.AlignmentError("UDPipe says %r at [%d, %d) where the text has %r"
                                              % (form, start, end, text[start:end]))
            tid = "t%d" % len(tokens)
            words = []
            for col in group:
                head = relation = None
                if syntax and col[6] not in ("_", "0"):
                    if col[6] not in ids:
                        raise analyzer.AlignmentError("a head outside its sentence: %s" % col[6])
                    head = "%s.w%s" % (sid, col[6])
                if syntax:
                    relation = _column(col[7])
                words.append(analyzer.Word(
                    id="%s.w%s" % (sid, col[0]), token=tid, source=NAME, status=analyzer.CONTEXTUAL,
                    lemma=_column(col[2]), upos=_column(col[3]), native=_column(col[4]),
                    feats=parse_feats(col[5]), head=head, relation=relation,
                    start=None if multi else start, end=None if multi else end,
                    surface=None if multi else form))
            selection = None
            if len(words) == 1 and words[0].lemma:
                selection = analyzer.Selection(source=NAME, lemma=words[0].lemma,
                                               lemma_status=analyzer.CONTEXTUAL,
                                               analysis_status=analyzer.CONTEXTUAL)
            tokens.append(analyzer.Token(id=tid, start=start, end=end, surface=form, sentence=sid,
                                         words=tuple(words), selection=selection))
    return analyzer.Result(language=code, text=text, outcome=analyzer.OK, context=context,
                           backend=NAME, resources=resources, diagnostics=tuple(notes),
                           sentences=tuple(sentences), tokens=tuple(tokens))


class Backend:
    name = NAME

    def __init__(self, folder):
        self.folder = folder
        self._lock = threading.Lock()   # one inference at a time: the binding promises no more
        self._models = OrderedDict()

    def languages(self):
        return tuple(analysispins.UDPIPE_MODELS)

    def loaded(self):
        return tuple(self._models)

    def _path(self, code):
        pin = analysispins.UDPIPE_MODELS.get(code)
        return os.path.join(self.folder, pin["file"]) if pin else ""

    def status(self, code):
        import importlib.util
        pin = analysispins.UDPIPE_MODELS.get(code)
        package = importlib.util.find_spec("ufal.udpipe") is not None
        path = self._path(code)
        resource = bool(pin) and os.path.isfile(path) and os.path.getsize(path) == pin["bytes"]
        return {"package": package, "resource": resource, "usable": package and resource,
                "loaded": code in self._models, "version": analysispins.UDPIPE_VERSION,
                "resource_id": pin["file"] if pin else "",
                "why": "" if package and resource else
                       ("the UDPipe program is not installed" if not package
                        else "the model for %s is not here" % code)}

    def _model(self, code):
        from ufal.udpipe import Model
        got = self._models.get(code)
        if got is None:
            path = self._path(code)
            got = Model.load(path) if os.path.isfile(path) else None
            if got is None:
                raise analyzer.BackendError("the model %s could not be loaded: remove it on Settings -> Linguistic "
                                            "analysis, and get it again" % os.path.basename(path))
            self._models[code] = got
            while len(self._models) > MODELS_KEPT:
                self._models.popitem(last=False)
        self._models.move_to_end(code)
        return got

    def analyze(self, code, text, syntax=False, context=""):
        from ufal.udpipe import Pipeline, ProcessingError
        pin = analysispins.UDPIPE_MODELS[code]
        with self._lock:
            model = self._model(code)
            parser = Pipeline.DEFAULT if syntax else Pipeline.NONE
            pipe = Pipeline(model, "tokenizer=ranges", Pipeline.DEFAULT, parser, "conllu")
            error = ProcessingError()
            out = pipe.process(text, error)
            if error.occurred():
                raise analyzer.BackendError(error.message)
        res = (analyzer.Resource(NAME, analysispins.UDPIPE_VERSION, pin["file"], pin["licence"]),)
        try:
            return from_conllu(out, code, text, syntax, context, res)
        except analyzer.AlignmentError as e:
            return analyzer.refusal(code, text, analyzer.FAILED, "udpipe: %s" % e, context, NAME)
