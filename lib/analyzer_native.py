# SPDX-License-Identifier: GPL-3.0-or-later
"""Japanese and Chinese behind lib/analyzer.py: what lib/words.py already knows,
in the same records, and nothing more.

SudachiPy and pkuseg stay what cuts these languages and a person's word line
stays what a chunk is read by; this only lets a consumer that speaks the common
records ask.  Everything is LEXICAL and there are no dependencies, because
neither is known.  Runs in the server, where lib/words.py always has.
"""
import analyzer
import segmenter
import words

NAME = "native"


class Backend:
    name = NAME

    def languages(self):
        return tuple(segmenter.BACKENDS)

    def status(self, code):
        about = segmenter.about(code)
        have = bool(about.get("have"))
        return {"package": have, "resource": have, "usable": have, "loaded": have,
                "version": "", "resource_id": about.get("analyzer", ""),
                "why": "" if have else "%s is not installed in %s" % (about.get("analyzer", code),
                                                                      about.get("python", "this Python"))}

    def analyze(self, code, text, syntax=False, context=""):
        got = words.parsed(text, code)
        if not got:
            return analyzer.refusal(code, text, analyzer.UNAVAILABLE,
                                    "%s said nothing about this text" % code, context, NAME)
        tokens, at = [], 0
        for surface, pieces in got:
            start = text.find(surface, at)
            # nothing but spaces may lie between two words: anything else means
            # the words are not this text, whatever a find could be made to say
            if start < 0 or text[at:start].strip():
                return analyzer.refusal(code, text, analyzer.FAILED,
                                        "the words do not follow the text at %r" % surface, context, NAME)
            end = start + len(surface)
            tid = "t%d" % len(tokens)
            lemma = pieces[0][2] if len(pieces) == 1 else None
            word = analyzer.Word(id="s0.w%d" % (len(tokens) + 1), token=tid, source=NAME, lemma=lemma,
                                 native="+".join(",".join(str(x) for x in p[1]) for p in pieces),
                                 start=start, end=end, surface=surface)
            tokens.append(analyzer.Token(id=tid, start=start, end=end, surface=surface, sentence="s0",
                                         words=(word,)))
            at = end
        return analyzer.Result(language=code, text=text, outcome=analyzer.OK, context=context, backend=NAME,
                               resources=(analyzer.Resource(NAME),), sentences=(("s0", tokens[0].start, at),),
                               tokens=tuple(tokens))
