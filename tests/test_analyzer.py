# SPDX-License-Identifier: GPL-3.0-or-later
"""The optional analyzers, from the common records to what uses them (a0.6.0).

    python3 -m unittest discover -s tests -p test_analyzer.py

Standard library only, under any Python: the backends here are fakes, and the three
real adapters are held to saved output or to fakes of the two calls they make.  What
the real programs answer is tests/analyzer_real.py's business, in their environment.
Temporary stores and dictionaries throughout; nothing under config/ is touched.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import analysisconfig      # noqa: E402
import analysispins        # noqa: E402
import analyzer as A       # noqa: E402
import analyzer_farahidi   # noqa: E402
import analyzer_starlang   # noqa: E402
import analyzer_udpipe     # noqa: E402
import chunker             # noqa: E402
import evidence            # noqa: E402
import getanalysis         # noqa: E402
import lookup              # noqa: E402
import lookupassist        # noqa: E402


class Fake:
    """A backend that reads each space-separated word as itself, upper-cased as a
    lemma, each word's head the next word, and can be told to misbehave."""
    def __init__(self, name="udpipe", codes=("en", "de", "fa", "ar", "tr", "it", "hi", "es", "fr"), usable=True):
        self.name, self.codes, self.usable = name, codes, usable
        self.calls, self.version, self.mangle, self.fail = 0, "1", None, None

    def languages(self):
        return self.codes

    def status(self, code):
        return {"package": True, "resource": self.usable, "usable": self.usable, "loaded": False,
                "version": self.version, "resource_id": "fake", "why": "" if self.usable else "not here"}

    def analyze(self, code, text, syntax=False, context=""):
        self.calls += 1
        if self.fail:
            raise A.BackendError(self.fail)
        tokens = []
        spans = A.source_tokens(text)
        for i, (s, e) in enumerate(spans):
            word = A.Word(id="s0.w%d" % (i + 1), token="t%d" % i, source=self.name, status=A.CONTEXTUAL,
                          lemma=text[s:e].upper(), upos="NOUN", feats={"Number": "Sing"},
                          head="s0.w%d" % (i + 2) if syntax and i + 1 < len(spans) else None,
                          relation="det" if syntax and i + 1 < len(spans) else "root" if syntax else None,
                          start=s, end=e, surface=text[s:e])
            tokens.append(A.Token(id="t%d" % i, start=s, end=e, surface=text[s:e], sentence="s0", words=(word,)))
        r = A.Result(language=code, text=text, outcome=A.OK, context=context, backend=self.name,
                     resources=(A.Resource(self.name, self.version, "fake"),),
                     sentences=(("s0", 0, len(text)),), tokens=tuple(tokens))
        return self.mangle(r) if self.mangle else r


def simple(text, tokens=()):
    return A.Result(language="en", text=text, outcome=A.OK, sentences=(("s0", 0, len(text)),), tokens=tuple(tokens))


class Records(unittest.TestCase):
    def tok(self, s, e, surface, i=0, **kw):
        return A.Token(id="t%d" % i, start=s, end=e, surface=surface, sentence="s0", **kw)

    def test_exact_slices_are_held_to_the_text_not_to_a_normal_form(self):
        cases = ["نمی‌خوانم", "éa", "كَتَبَ", "a  b", "日本語 abc", "😀 x"]
        for text in cases:
            for s, e in A.source_tokens(text):
                self.assertEqual(text[s:e], text[s:e])
            spans = A.source_tokens(text)
            result = simple(text, [self.tok(s, e, text[s:e], i) for i, (s, e) in enumerate(spans)])
            A.validate(result)
        # the same letters in another normal form are another text
        with self.assertRaises(A.AlignmentError):
            A.validate(simple("é", [self.tok(0, 2, "é")]))

    def test_tokens_keep_joiners_and_marks_inside_and_punctuation_apart(self):
        text = "نمی‌خوانم، l'uomo؟"
        self.assertEqual([text[s:e] for s, e in A.source_tokens(text)], ["نمی‌خوانم", "،", "l'uomo", "؟"])

    def test_a_repeated_word_is_two_tokens_at_two_places(self):
        text = "the cat the"
        spans = A.source_tokens(text)
        self.assertEqual(spans[0], (0, 3))
        self.assertEqual(spans[2], (8, 11))

    def test_out_of_order_overlap_and_outside_sentence_are_refused(self):
        with self.assertRaises(A.AlignmentError):
            A.validate(simple("ab cd", [self.tok(3, 5, "cd", 0), self.tok(0, 2, "ab", 1)]))
        with self.assertRaises(A.AlignmentError):
            A.validate(A.Result(language="en", text="ab cd", outcome=A.OK, sentences=(("s0", 0, 2),),
                                tokens=(self.tok(3, 5, "cd"),)))

    def test_a_multiword_token_has_words_without_spans_of_their_own(self):
        words = (A.Word(id="s0.w1", token="t0", source="x", lemma="zu"),
                 A.Word(id="s0.w2", token="t0", source="x", lemma="dem"))
        result = simple("Zum", [self.tok(0, 3, "Zum", words=words)])
        A.validate(result)
        self.assertEqual(result.tokens[0].lemmas(), ["zu", "dem"])
        bad = (A.Word(id="s0.w1", token="t0", source="x", start=0, end=2, surface="zz"),)
        with self.assertRaises(A.AlignmentError):
            A.validate(simple("Zum", [self.tok(0, 3, "Zum", words=bad)]))

    def test_a_head_must_exist_and_stay_in_its_sentence(self):
        loose = (A.Word(id="s0.w1", token="t0", source="x", head="s0.w9"),)
        with self.assertRaises(A.AlignmentError):
            A.validate(simple("a", [self.tok(0, 1, "a", words=loose)]))
        far = A.Result(language="en", text="a b", outcome=A.OK, sentences=(("s0", 0, 1), ("s1", 2, 3)), tokens=(
            A.Token(id="t0", start=0, end=1, surface="a", sentence="s0",
                    words=(A.Word(id="s0.w1", token="t0", source="x", head="s1.w1"),)),
            A.Token(id="t1", start=2, end=3, surface="b", sentence="s1",
                    words=(A.Word(id="s1.w1", token="t1", source="x"),))))
        with self.assertRaises(A.AlignmentError):
            A.validate(far)

    def test_a_result_cannot_be_changed_after_it_is_made(self):
        w = A.Word(id="s0.w1", token="t0", source="x", feats={"a": "b"})
        with self.assertRaises(TypeError):
            w.feats["a"] = "c"
        with self.assertRaises(Exception):
            w.lemma = "z"

    def test_the_plain_form_comes_back_the_same(self):
        c = A.Candidate(source="x", rank=0, lemma="a", feats={"Case": "Nom"}, clitics=({"kind": "p", "form": "و"},),
                        raw={"tag": "UNKNOWN"})
        t = A.Token(id="t0", start=0, end=1, surface="a", sentence="s0", candidates=(c,),
                    selection=A.Selection(source="x", lemma="a", lemma_status=A.CONTEXTUAL))
        r = simple("a", [t])
        back = A.from_plain(json.loads(json.dumps(A.to_plain(r))))
        self.assertEqual(back.tokens[0].candidates[0].raw["tag"], "UNKNOWN")
        self.assertEqual(back.tokens[0].selection.lemma_status, A.CONTEXTUAL)
        self.assertEqual(dict(back.tokens[0].candidates[0].feats), {"Case": "Nom"})


class Requests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(A.reset)

    def test_every_outcome_is_an_answer(self):
        A.reset([Fake()])
        self.assertEqual(A.analyze("zz", "x").outcome, A.UNSUPPORTED)
        self.assertEqual(A.analyze("en", "   ").outcome, A.EMPTY)
        self.assertEqual(A.analyze("en", "x y").outcome, A.OK)
        A.reset([Fake(usable=False)])
        r = A.analyze("en", "x")
        self.assertEqual(r.outcome, A.UNAVAILABLE)
        self.assertIn("not here", r.diagnostics[0])
        A.reset([Fake()])
        self.assertEqual(A.analyze("en", "x" * (A.MAX_TEXT + 1)).outcome, A.FAILED)

    def test_nothing_is_asked_of_a_backend_for_status(self):
        f = Fake()
        A.reset([f])
        self.assertTrue(A.available("en"))
        self.assertFalse(A.available("zz"))
        self.assertTrue(A.about("en")["morphology"]["usable"])
        self.assertEqual(f.calls, 0)

    def test_a_failure_is_a_result_and_is_not_remembered(self):
        f = Fake()
        f.fail = "it fell over"
        A.reset([f])
        r = A.analyze("en", "a b")
        self.assertEqual(r.outcome, A.FAILED)
        self.assertIn("it fell over", r.diagnostics[0])
        f.fail = None
        self.assertEqual(A.analyze("en", "a b").outcome, A.OK)

    def test_an_answer_that_does_not_fit_is_a_failure(self):
        f = Fake()
        A.reset([f])

        def wrong_offset(r):
            t = r.tokens[0]
            return A.Result(**dict(A._fields(r), tokens=(A.Token(**dict(A._fields(t), start=t.start + 1)),)))
        f.mangle = wrong_offset
        r = A.analyze("en", "ab cd")
        self.assertEqual(r.outcome, A.FAILED)
        f.mangle = lambda r: A.Result(**dict(A._fields(r), text="other"))
        self.assertEqual(A.analyze("en", "ab cd e").outcome, A.FAILED)

    def test_the_cache_is_exact_and_bounded(self):
        f = Fake()
        A.reset([f])
        a = A.analyze("en", "a b")
        self.assertIs(A.analyze("en", "a b"), a)
        self.assertEqual(f.calls, 1)
        A.analyze("en", "a b ")                # one more space is another text
        A.analyze("en", "a b", syntax=True)    # another question
        A.analyze("en", "a b", context="here") # another context
        self.assertEqual(f.calls, 4)
        f.version = "2"                        # a new model is another answer
        self.assertIsNot(A.analyze("en", "a b"), a)
        with mock.patch.object(A, "MAX_RESULTS", 3):
            for i in range(10):
                A.analyze("en", "w%d" % i)
            self.assertLessEqual(len(A._CACHE), 3)

    def test_clear_cache_stops_a_running_request_putting_its_answer_back(self):
        f = Fake()
        A.reset([f])
        real = f.analyze

        def slow(*a, **k):
            A.clear_cache()
            return real(*a, **k)
        f.analyze = slow
        A.analyze("en", "a")
        f.analyze = real
        calls = f.calls
        A.analyze("en", "a")
        self.assertEqual(f.calls, calls + 1)

    def test_concurrent_requests_all_get_good_answers(self):
        f = Fake()
        A.reset([f])
        got = []

        def ask(i):
            got.append(A.analyze("en", "w%d x" % (i % 5)).ok)
        ts = [threading.Thread(target=ask, args=(i,)) for i in range(40)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(got, [True] * 40)

    def test_two_backends_pair_only_on_the_same_span_and_stay_apart(self):
        morph, syn = Fake("farahidi", ("ar",)), Fake("udpipe", ("ar",))

        def merge_two(r):       # UDPipe reads the first two words as one token
            t0, t1 = r.tokens[0], r.tokens[1]
            word = A.Word(id="s0.w1", token="t0", source="udpipe", lemma="JOINED", status=A.CONTEXTUAL)
            joined = A.Token(id="t0", start=t0.start, end=t1.end, surface=r.text[t0.start:t1.end], sentence="s0",
                             words=(word,))
            return A.Result(**dict(A._fields(r), tokens=(joined,) + r.tokens[2:]))
        syn.mangle = merge_two
        A.reset([morph, syn])
        r = A.analyze("ar", "a b c", syntax=True)
        self.assertEqual(r.backend, "farahidi+udpipe")
        self.assertEqual(r.tokens[0].syntax, ())
        self.assertEqual(r.tokens[0].words[0].source, "farahidi")
        self.assertEqual(r.tokens[2].syntax[0].source, "udpipe")
        self.assertEqual(r.tokens[2].words[0].source, "farahidi")
        self.assertTrue(any("cut differently" in d for d in r.diagnostics))

    def test_syntax_that_cannot_be_had_costs_only_the_syntax(self):
        morph, syn = Fake("farahidi", ("ar",)), Fake("udpipe", ("ar",), usable=False)
        A.reset([morph, syn])
        self.assertEqual(A.analyze("ar", "a b", syntax=True).outcome, A.OK)
        self.assertFalse(A.available("ar", syntax=True))
        self.assertTrue(A.available("ar"))


CONLLU = """# newdoc
# sent_id = 1
# text = Zum Haus  gehen wir.
1-2\tZum\t_\t_\t_\t_\t_\t_\t_\tTokenRange=0:3
1\tZu\tzu\tADP\tAPPR\t_\t3\tcase\t_\t_
2\tdem\tder\tDET\tART\tCase=Dat\t3\tdet\t_\t_
3\tHaus\tHaus\tNOUN\tNN\tCase=Dat|Number=Sing\t0\troot\t_\tSpacesAfter=\\s\\s|TokenRange=4:8
3.1\tleer\t_\t_\t_\t_\t_\t_\t_\t_
4\tgehen\tgehen\tVERB\tVVFIN\t_\t3\tacl\t_\tTokenRange=10:15

# sent_id = 2
1\tgehen\tgehen\tVERB\tVVFIN\t_\t0\troot\t_\tTokenRange=16:21

"""


class Udpipe(unittest.TestCase):
    TEXT = "Zum Haus  gehen gehen"

    def test_a_multiword_token_its_words_and_an_empty_node(self):
        r = analyzer_udpipe.from_conllu(CONLLU, "de", self.TEXT, True)
        A.validate(r)
        self.assertEqual([t.surface for t in r.tokens], ["Zum", "Haus", "gehen", "gehen"])
        zum = r.tokens[0]
        self.assertEqual([w.lemma for w in zum.words], ["zu", "der"])
        self.assertIsNone(zum.words[0].start)
        self.assertEqual(zum.words[0].head, "s0.w3")
        self.assertIsNone(r.tokens[1].words[0].head)
        self.assertEqual(r.tokens[1].words[0].relation, "root")
        self.assertEqual(r.tokens[3].sentence, "s1")
        self.assertTrue(any("empty node" in d for d in r.diagnostics))

    def test_without_syntax_no_dependency_is_kept(self):
        r = analyzer_udpipe.from_conllu(CONLLU, "de", self.TEXT, False)
        self.assertTrue(all(w.head is None and w.relation is None for t in r.tokens for w in t.words))

    def test_a_range_that_is_not_the_form_fails(self):
        with self.assertRaises(A.AlignmentError):
            analyzer_udpipe.from_conllu(CONLLU, "de", "Xum Haus  gehen gehen", True)
        with self.assertRaises(A.AlignmentError):
            analyzer_udpipe.from_conllu("1\tHaus\tHaus\tNOUN\t_\t_\t0\troot\t_\t_\n", "de", "Haus", True)


class Parsed:
    pass


def arabic(**kw):
    from dataclasses import make_dataclass
    a = dict(diacritized="كَتَبَ", lemma="كَتَبَ", root="كتب", stem="كَتَب", pos="فعل", tense="ماض", gender=None,
             number=None, person="غائب", voice="معلوم", proclitics=(), enclitics=(), inflections=(), score=0.5)
    a.update(kw)
    return make_dataclass("Analysis", list(a))(**a)


class Farahidi(unittest.TestCase):
    def pick(self, token, lemma="كَتَبَ", analyzed=True, root="كتب"):
        p = Parsed()
        p.token, p.lemma, p.stem, p.root, p.analyzed = token, lemma, "كَتَب", root, analyzed
        return p

    def result(self, text, analyses):
        spans = A.source_sentences(text, A.source_tokens(text))
        return analyzer_farahidi.build("ar", text, spans, analyses,
                                       lambda ws: [self.pick(w, analyzed=w != "." and w != "قفزخ") for w in ws])

    def test_only_the_lemma_is_contextual_and_every_candidate_stays(self):
        text = "كتب كتب ."
        r = self.result(text, lambda w: [arabic(), arabic(lemma="كِتَاب", pos="اسم", voice=None, tense=None)])
        A.validate(r)
        s = r.tokens[0].selection
        self.assertEqual(s.lemma_status, A.CONTEXTUAL)
        self.assertEqual(s.analysis_status, A.LEXICAL)
        self.assertIsNone(s.analysis)
        self.assertEqual(len(r.tokens[0].candidates), 2)
        self.assertEqual(r.tokens[1].start, 4)   # a repeated word keeps its own place
        self.assertEqual(r.tokens[0].candidates[0].feats["Voice"], "Act")
        self.assertEqual(r.tokens[0].candidates[0].raw["voice"], "معلوم")

    def test_an_unknown_word_says_nothing_rather_than_that_it_is_its_own_lemma(self):
        r = self.result("قفزخ .", lambda w: [])
        self.assertFalse(r.tokens[0].analyzed)
        self.assertEqual(r.tokens[0].lemmas(), [])

    def test_a_sentinel_is_no_root_and_a_changed_token_is_a_failure(self):
        self.assertIsNone(analyzer_farahidi.candidate(0, arabic(root="-")).root)
        self.assertIsNone(analyzer_farahidi.candidate(0, arabic(root="#")).root)
        with self.assertRaises(A.AlignmentError):
            analyzer_farahidi.build("ar", "كتب", [[(0, 3)]], lambda w: [],
                                    lambda ws: [self.pick("كتاب")])


class Starlang(unittest.TestCase):
    def test_the_parse_string_keeps_all_its_groups_and_tags(self):
        c = analyzer_starlang.candidate(0, "yap", "yap+VERB^DB+VERB+PASS+NEG+FUT+A3PL+PAST", "VERB")
        self.assertEqual(c.root, "yap")
        self.assertEqual(c.lemma, "yapmak")
        self.assertEqual(c.raw["groups"], ["VERB", "VERB+PASS+NEG+FUT+A3PL+PAST"])
        for k, v in (("Voice", "Pass"), ("Polarity", "Neg"), ("Tense", "Past"), ("Person", "3"), ("Number", "Plur")):
            self.assertEqual(c.feats[k], v)

    def test_possession_is_not_the_subject(self):
        c = analyzer_starlang.candidate(0, "ev", "ev+NOUN+A3PL+P1PL+ABL", "NOUN")
        self.assertEqual(c.lemma, "ev")
        self.assertEqual(dict(c.feats), {"Person": "3", "Number": "Plur", "Person[psor]": "1", "Number[psor]": "Plur",
                                         "Case": "Abl"})

    def test_the_citation_form_follows_the_last_vowel(self):
        self.assertEqual(analyzer_starlang.citation("gel"), "gelmek")
        self.assertEqual(analyzer_starlang.citation("otur"), "oturmak")

    def test_no_parse_is_chosen_and_all_are_kept(self):
        text = "yüz xqzt"
        parses = {"yüz": [("yüz", "yüz+ADJ", "ADJ"), ("yüz", "yüz+NOUN+A3SG+PNON+NOM", "NOUN")], "xqzt": []}
        r = analyzer_starlang.build("tr", text, A.source_sentences(text, A.source_tokens(text)), parses.get)
        A.validate(r)
        self.assertIsNone(r.tokens[0].selection)
        self.assertEqual(len(r.tokens[0].candidates), 2)
        self.assertFalse(r.tokens[1].analyzed)


def dictionary(folder, code, rows):
    """A small dictionary: [(headword, pos, sense, [forms])]."""
    path = os.path.join(folder, "%s.db" % code)
    c = lookup.create(path)
    for head, pos, sense, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, translit, ipa, pos, sense, sense_tags) VALUES (?,?,?,?,?,?)",
                        (head, "", "", pos, sense, ""))
        for f in list(forms) + [head]:
            c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (f, cur.lastrowid, ""))
    c.commit()
    c.close()


class Lemmas(Fake):
    """A backend that reads each word as the table says."""
    def __init__(self, table, contextual=True, upos="VERB", **kw):
        super().__init__(**kw)
        self.table, self.contextual, self.upos = table, contextual, upos

    def analyze(self, code, text, syntax=False, context=""):
        r = super().analyze(code, text, syntax, context)
        toks = []
        for t in r.tokens:
            lemma = self.table.get(t.surface)
            status = A.CONTEXTUAL if self.contextual else A.LEXICAL
            word = A.Word(id=t.words[0].id, token=t.id, source=self.name, status=status, lemma=lemma, upos=self.upos,
                          start=t.start, end=t.end, surface=t.surface)
            sel = A.Selection(source=self.name, lemma=lemma, lemma_status=status) if lemma else None
            toks.append(A.Token(**dict(A._fields(t), words=(word,), selection=sel)))
        return A.Result(**dict(A._fields(r), tokens=tuple(toks)))


class Lookup(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        p = mock.patch.object(lookup, "DICT_DIR", self.td.name)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(A.reset)
        dictionary(self.td.name, "it", [("andare", "verb", "to go", ["vado"]),
                                        ("casa", "noun", "house", []), ("cane", "noun", "dog", ["cani"]),
                                        ("canare", "verb", "to bay", ["cane"])])

    def look(self, text, mode, table, sentence="", **kw):
        A.reset([Lemmas(table, **kw)])
        r = lookup.look_up("it", text)
        return lookupassist.apply("it", r, text, sentence, mode)

    def test_a_word_not_found_is_found_under_its_lemma_and_says_so(self):
        r = lookup.look_up("it", "andiamo")
        self.assertFalse(r["words"][0]["hits"])
        r = self.look("andiamo", "assist", {"andiamo": "andare"})
        w = r["words"][0]
        self.assertEqual(w["hits"][0]["headword"], "andare")
        self.assertEqual(w["kind"], "analyzer")
        self.assertIn("andare", w["via"])
        self.assertTrue(w["machine"]["rescued"])

    def test_show_changes_no_row_and_off_nothing_at_all(self):
        r = self.look("andiamo", "show", {"andiamo": "andare"})
        self.assertFalse(r["words"][0]["hits"])
        self.assertEqual(r["words"][0]["machine"]["lemma"], "andare")
        r = self.look("andiamo", "off", {"andiamo": "andare"})
        self.assertNotIn("machine", r["words"][0])
        self.assertNotIn("analysis", r)

    def test_a_lemma_no_entry_has_finds_nothing(self):
        r = self.look("andiamo", "assist", {"andiamo": "volare"})
        w = r["words"][0]
        self.assertFalse(w["hits"])
        self.assertFalse(w["machine"]["rescued"])
        self.assertIn("volare", w["tried"])

    def test_a_word_the_dictionary_found_keeps_what_it_found_whatever_the_analyzer_says(self):
        before = lookup.look_up("it", "casa")["words"][0]["hits"]
        r = self.look("casa", "assist", {"casa": "volare"})
        self.assertEqual(r["words"][0]["hits"], before)
        self.assertNotIn("kind", {k: v for k, v in r["words"][0].items() if v == "analyzer"})

    def test_a_lemma_alone_marks_and_moves_nothing(self):
        was = [h["headword"] for h in lookup.look_up("it", "cane")["words"][0]["hits"]]
        for other in was:
            r = self.look("cane", "assist", {"cane": other}, upos="X")
            self.assertEqual([h["headword"] for h in r["words"][0]["hits"]], was)
            self.assertFalse(any(h.get("fits") for h in r["words"][0]["hits"]))

    def test_the_part_of_speech_marks_the_entry_that_fits_and_assist_moves_it_first(self):
        was = lookup.look_up("it", "cane")["words"][0]["hits"]
        self.assertEqual({h["headword"]: h["pos"] for h in was}, {"cane": "noun", "canare": "verb"})
        for upos, head in (("VERB", "canare"), ("NOUN", "cane")):
            r = self.look("cane", "show", {"cane": head}, upos=upos)
            self.assertEqual([h["headword"] for h in r["words"][0]["hits"]], [h["headword"] for h in was], "show moves nothing")
            self.assertEqual([h["headword"] for h in r["words"][0]["hits"] if h.get("fits")], [head])
            r = self.look("cane", "assist", {"cane": head}, upos=upos)
            self.assertEqual(r["words"][0]["hits"][0]["headword"], head)
            self.assertEqual(len(r["words"][0]["hits"]), 2, "none dropped")
            self.assertEqual(r["words"][0]["machine"]["pos"], {"VERB": "verb", "NOUN": "noun"}[upos])

    def test_a_part_of_speech_nobody_read_in_the_sentence_marks_nothing(self):
        r = self.look("cane", "assist", {"cane": "x"}, upos="VERB", contextual=False)
        self.assertFalse(any(h.get("fits") for h in r["words"][0]["hits"]))

    def test_a_verbs_particle_marks_nothing(self):
        self.assertIsNone(lookupassist._wanted({"here": True, "upos": "ADP", "relation": "compound:prt"}))
        self.assertTrue(lookupassist._wanted({"here": True, "upos": "ADP", "relation": "case", "lemma": "x"}))

    def test_when_every_entry_is_that_part_of_speech_nothing_is_marked(self):
        dictionary(self.td.name, "es", [("uno", "noun", "a", []), ("due", "noun", "b", ["uno"])])
        A.reset([Lemmas({"uno": "due"}, upos="NOUN", codes=("es",))])
        r = lookup.look_up("es", "uno")
        lookupassist.apply("es", r, "uno", "", "assist")
        self.assertEqual(len(r["words"][0]["hits"]), 2)
        self.assertFalse(any(h.get("fits") for h in r["words"][0]["hits"]), "a mark on every entry says nothing")

    def test_among_that_part_of_speech_the_lemmas_own_entry_alone(self):
        dictionary(self.td.name, "fr", [("uno", "verb", "a", []), ("due", "verb", "b", ["uno"]), ("tre", "noun", "c", ["uno"])])
        A.reset([Lemmas({"uno": "due"}, upos="VERB", codes=("fr",))])
        r = lookup.look_up("fr", "uno")
        lookupassist.apply("fr", r, "uno", "", "assist")
        self.assertEqual([h["headword"] for h in r["words"][0]["hits"] if h.get("fits")], ["due"])

    def test_an_entry_none_of_the_readings_names_does_not_fit(self):
        said = {"here": True, "upos": "NOUN", "lemma": "erken", "readings": 1, "can_be": ["erken"]}
        dictionary(self.td.name, "tr", [("erkenden", "adv", "early", []), ("erke", "noun", "power", ["erkenden"])])
        row = lookup.look_up("tr", "erkenden")["words"][0]
        self.assertEqual(lookupassist._fits(row, said, "tr", lookup.languages.get_or_default("tr")), 0)
        self.assertFalse(any(h.get("fits") for h in row["hits"]))

    def test_a_word_found_only_as_something_else_gets_its_lemmas_entry(self):
        dictionary(self.td.name, "de", [("facendo", "noun", "not it", []), ("fare", "verb", "to do", [])])
        A.reset([Lemmas({"facendo": "fare"}, upos="VERB", codes=("de",))])
        r = lookup.look_up("de", "facendo")
        lookupassist.apply("de", r, "facendo", "", "assist")
        heads = [(h["headword"], h["pos"], bool(h.get("fits"))) for h in r["words"][0]["hits"]]
        self.assertEqual(heads, [("fare", "verb", True), ("facendo", "noun", False)])
        self.assertTrue(r["words"][0]["machine"]["added"])

    def test_with_no_analyzer_the_result_is_the_old_one(self):
        A.reset([Fake(usable=False)])
        before = lookup.look_up("it", "andiamo")
        after = lookup.look_up("it", "andiamo")
        lookupassist.apply("it", after, "andiamo", "", "assist")
        self.assertEqual(after.pop("analysis")["outcome"], A.UNAVAILABLE)
        self.assertEqual(before, after)

    def test_a_chunk_reads_its_word_in_the_sentence_and_at_its_own_place(self):
        seen = {}
        table = {"andiamo": "andare"}
        f = Lemmas(table)
        real = f.analyze

        def spy(code, text, syntax=False, context=""):
            seen["text"] = text
            return real(code, text, syntax, context)
        f.analyze = spy
        A.reset([f])
        r = lookup.look_up("it", "andiamo")
        lookupassist.apply("it", r, "andiamo", "noi andiamo a casa", "assist")
        self.assertEqual(seen["text"], "noi andiamo a casa")
        self.assertTrue(r["words"][0]["hits"])
        # a chunk that is not once in the sentence is read alone
        r = lookup.look_up("it", "andiamo")
        lookupassist.apply("it", r, "andiamo", "tutt'altro", "assist")
        self.assertEqual(seen["text"], "andiamo")

    def test_persian_stems_are_asked_as_the_infinitive(self):
        self.assertEqual(lookupassist._forms("fa", "رفت#رو"), ["رفتن"])
        self.assertEqual(lookupassist._forms("de", "gehen"), ["gehen"])

    def test_pieces_are_not_how_it_works_so_a_persian_join_survives(self):
        dictionary(self.td.name, "fa", [("سوزاندن", "verb", "to burn", ["نمی‌سوزانند"])])
        A.reset([Lemmas({})])
        r = lookup.look_up("fa", "نمی سوزانند")
        hits = [w for w in r["words"] if w["hits"]]
        self.assertTrue(hits, r)
        lookupassist.apply("fa", r, "نمی سوزانند", "", "assist")
        self.assertEqual([w["word"] for w in r["words"] if w["hits"]], [hits[0]["word"]])


class Chunking(unittest.TestCase):
    def setUp(self):
        self.addCleanup(A.reset)
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        p = mock.patch.object(lookup, "DICT_DIR", self.td.name)
        p.start()
        self.addCleanup(p.stop)

    def parse(self, text, arcs):
        """A Result from [(lemma, upos, head index or None, relation)], one per token."""
        spans = A.source_tokens(text)
        tokens = []
        for i, ((s, e), (lemma, upos, head, rel)) in enumerate(zip(spans, arcs)):
            w = A.Word(id="s0.w%d" % (i + 1), token="t%d" % i, source="u", status=A.CONTEXTUAL, lemma=lemma, upos=upos,
                       head=None if head is None else "s0.w%d" % (head + 1), relation=rel, start=s, end=e, surface=text[s:e])
            tokens.append(A.Token(id="t%d" % i, start=s, end=e, surface=text[s:e], sentence="s0", words=(w,)))
        return A.Result(language="en", text=text, outcome=A.OK, sentences=(("s0", 0, len(text)),), tokens=tuple(tokens))

    def test_a_dependency_holds_a_seam_that_the_rules_would_cut(self):
        text = "Maria Rossi lavora molto bene oggi qui"
        arcs = [("Maria", "PROPN", 2, "nsubj"), ("Rossi", "PROPN", 0, "flat:name"), ("lavorare", "VERB", None, "root"),
                ("molto", "ADV", 4, "advmod"), ("bene", "ADV", 2, "advmod"), ("oggi", "ADV", 2, "advmod"),
                ("qui", "ADV", 2, "advmod")]
        r = self.parse(text, arcs)
        got = chunker.chunk(text, "it", "phrase", lambda t: r)
        self.assertTrue(any("Maria Rossi" in c for c in got), got)
        self.assertTrue(chunker.exact(got, text))

    def test_the_writers_punctuation_is_not_overruled(self):
        text = "il cane mangia molta carne, il gatto beve molto latte"
        words = text.split()
        spans = A.source_tokens(text)
        # the analyzer says the seam after the comma is inside something: the writer said otherwise
        arcs = []
        for i, (s_, e_) in enumerate(spans):
            arcs.append((text[s_:e_], "NOUN", i + 1 if i + 1 < len(spans) else None,
                         "flat" if i + 1 < len(spans) else "root"))
        r = self.parse(text, arcs)
        toks = chunker._tokens(text, chunker.languages.get_or_default("it"))
        self.assertIn(5, chunker._assist(toks, r)[0])
        got = chunker.chunk(text, "it", "phrase", lambda t: r)
        self.assertTrue(any(c.endswith("carne,") for c in got), got)
        self.assertTrue(chunker.exact(got, text), (got, words))

    def test_failure_of_any_kind_gives_the_old_suggestion(self):
        text = "il cane mangia la carne in cucina oggi"
        old = chunker.chunk(text, "it", "phrase")
        self.assertEqual(chunker.chunk(text, "it", "phrase", None), old)
        self.assertEqual(chunker.chunk(text, "it", "phrase", lambda t: None), old)
        self.assertEqual(chunker.chunk(text, "it", "phrase", lambda t: A.refusal("it", t, A.FAILED, "no")), old)
        other = A.Result(language="it", text="altro", outcome=A.OK)
        self.assertEqual(chunker.chunk(text, "it", "phrase", lambda t: other), old)

    def test_exact_is_stricter_than_reproduces(self):
        self.assertTrue(chunker.reproduces(["a", "b"], "a   b", "it"))
        self.assertTrue(chunker.exact(["a", "b"], "a   b"))
        self.assertFalse(chunker.exact(["b", "a"], "a b"))
        self.assertFalse(chunker.exact(["a", "c"], "a b c"))
        self.assertFalse(chunker.exact(["é"], "é"))

    def test_spaces_and_marks_come_through_as_slices(self):
        text = "کتاب‌ها   را  می‌خوانم"
        arcs = [("کتاب", "NOUN", 2, "obj"), ("را", "ADP", 0, "case"), ("خواندن", "VERB", None, "root")]
        r = self.parse(text, arcs)
        got = chunker.chunk(text, "fa", "phrase", lambda t: r)
        self.assertTrue(chunker.exact(got, text), got)

    def test_japanese_and_chinese_are_never_asked_to_listen(self):
        text = "寒い朝に窓を開ける"
        asked = []

        def assist(t):
            asked.append(t)
            return A.Result(language="ja", text=t, outcome=A.OK, sentences=(("s0", 0, len(t)),))
        old = chunker.chunk(text, "ja", "phrase")
        self.assertEqual(chunker.chunk(text, "ja", "phrase", assist), old)

    def test_nothing_is_asked_while_it_is_off(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(analysisconfig, "STORE", os.path.join(td, "a.json")):
            self.assertIsNone(chunker.assisting("it"))
            A.reset([Fake()])
            self.assertIsNone(chunker.assisting("it"))
            analysisconfig.save({"chunking": "assist"})
            self.assertIsNotNone(chunker.assisting("it"))
            A.reset([Fake(usable=False)])
            self.assertIsNone(chunker.assisting("it"))


class Evidence(unittest.TestCase):
    def setUp(self):
        self.addCleanup(A.reset)

    def units(self, *chunks):
        return [{"key": "k", "at": "ch1:1.1",
                 "chunks": [{"j": j, "fa": c} for j, c in enumerate(chunks)]}]

    def test_the_sentence_is_analyzed_once_and_handed_to_its_chunks(self):
        f = Fake()
        A.reset([f])
        ev = evidence.for_units("it", self.units("il cane", "mangia"), lambda ch: True)
        self.assertEqual(f.calls, 1)
        self.assertEqual([e["w"] for e in ev.chunks[("k", 0)]], ["il", "cane"])
        self.assertEqual([e["w"] for e in ev.chunks[("k", 1)]], ["mangia"])

    def test_a_repeated_word_goes_to_its_own_chunk(self):
        f = Fake()
        A.reset([f])
        ev = evidence.for_units("it", self.units("il cane", "il gatto"), lambda ch: ch["j"] == 1)
        self.assertNotIn(("k", 0), ev.chunks)
        self.assertEqual([e["w"] for e in ev.chunks[("k", 1)]], ["il", "gatto"])

    def test_a_chunk_with_nothing_to_do_gives_context_and_gets_nothing(self):
        f = Fake()
        A.reset([f])
        ev = evidence.for_units("it", self.units("il cane", "mangia"), lambda ch: ch["j"] == 0)
        self.assertEqual(list(ev.chunks), [("k", 0)])
        self.assertIn("il cane mangia", [c for c in ["il cane mangia"]])

    def test_a_token_across_a_seam_is_left_out_and_counted(self):
        f = Fake()
        A.reset([f])

        def across(r):
            t = A.Token(id="t0", start=0, end=len(r.text), surface=r.text, sentence="s0",
                        words=(A.Word(id="s0.w1", token="t0", source="udpipe", lemma="L", upos="X"),))
            return A.Result(**dict(A._fields(r), tokens=(t,)))
        f.mangle = across
        ev = evidence.for_units("it", self.units("il", "cane"), lambda ch: True)
        self.assertFalse(ev.chunks)
        self.assertTrue(any("seam" in d for d in ev.diagnostics))

    def test_budgets_cut_the_same_way_each_time_and_say_so(self):
        f = Fake()
        A.reset([f])
        long_chunk = " ".join("parola%d" % i for i in range(30))
        one = evidence.for_units("it", self.units(long_chunk), lambda ch: True)
        two = evidence.for_units("it", self.units(long_chunk), lambda ch: True)
        self.assertEqual(one.chunks, two.chunks)
        self.assertLessEqual(len(one.chunks[("k", 0)]), evidence.MAX_ENTRIES)
        self.assertLessEqual(len(json.dumps(one.chunks[("k", 0)], ensure_ascii=False)), evidence.MAX_CHUNK_CHARS)
        self.assertTrue(any("budget" in d for d in one.diagnostics))
        with mock.patch.object(evidence, "MAX_REGION_CHARS", 60):
            few = evidence.for_units("it", self.units("a b", "c d", "e f", "g h"), lambda ch: True)
        self.assertLess(len(few.chunks), 4)
        self.assertTrue(any("spent" in d for d in few.diagnostics))

    def test_a_selection_says_who_chose_and_candidates_are_bounded(self):
        cands = tuple(A.Candidate(source="farahidi", rank=i, lemma="l%d" % i, upos="NOUN") for i in range(9))
        t = A.Token(id="t0", start=0, end=1, surface="x", sentence="s0", candidates=cands,
                    selection=A.Selection(source="farahidi", lemma="l0", lemma_status=A.CONTEXTUAL, root="r"))
        e = evidence.entry(t)
        self.assertEqual((e["lemma"], e["by"], e["root"]), ("l0", "sentence", "r"))
        self.assertEqual(len(e["others"]), evidence.MAX_OTHERS)
        self.assertEqual(e["more"], 8 - evidence.MAX_OTHERS)
        t = A.Token(id="t0", start=0, end=1, surface="x", sentence="s0", candidates=cands)
        e = evidence.entry(t)
        self.assertEqual(e["by"], "word alone")
        self.assertEqual(len(e["readings"]), evidence.MAX_OTHERS)

    def test_a_separable_verb_says_what_it_is_part_of_and_punctuation_says_nothing(self):
        text = "Ich rufe an ."
        def word(i, surf, lemma, upos, head, rel):
            return A.Word(id="s0.w%d" % i, token="t%d" % i, source="u", status=A.CONTEXTUAL, lemma=lemma, upos=upos,
                          head=head, relation=rel)
        toks = (A.Token(id="t1", start=4, end=8, surface="rufe", sentence="s0", words=(word(1, "rufe", "rufen", "VERB", None, "root"),)),
                A.Token(id="t2", start=9, end=11, surface="an", sentence="s0", words=(word(2, "an", "an", "ADP", "s0.w1", "compound:prt"),)),
                A.Token(id="t3", start=12, end=13, surface=".", sentence="s0", words=(word(3, ".", ".", "PUNCT", "s0.w1", "punct"),)))
        r = A.Result(language="de", text=text, outcome=A.OK, sentences=(("s0", 0, 13),), tokens=toks)
        said = [evidence.entry(t, evidence._surfaces(r)) for t in toks]
        self.assertEqual(said[1]["part_of"], "compound:prt of rufe")
        self.assertIsNone(said[2])

    def test_with_no_backend_there_is_nothing_and_a_reason(self):
        A.reset([Fake(usable=False)])
        ev = evidence.for_units("it", self.units("il cane"), lambda ch: True)
        self.assertFalse(ev)
        self.assertTrue(ev.diagnostics)
        self.assertEqual(evidence.for_units("ja", self.units("日本語"), lambda ch: True).chunks, {})

    def test_the_helper_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("un testo.\n")
            before = os.stat(src).st_mtime_ns
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            out = subprocess.run([sys.executable, os.path.join(ROOT, "lib", "evidence.py"), "xx", "--file", src],
                                 capture_output=True, text=True, env=env, cwd=td)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["outcome"], A.UNSUPPORTED)
            self.assertEqual(os.listdir(td), ["src.txt"])
            self.assertEqual(os.stat(src).st_mtime_ns, before)


class Store(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        for mod, name, val in ((analysisconfig, "STORE", os.path.join(self.td.name, "cfg", "analysis.json")),
                               (getanalysis, "FOLDER", os.path.join(self.td.name, "analysis"))):
            p = mock.patch.object(mod, name, val)
            p.start()
            self.addCleanup(p.stop)

    def test_everything_is_off_until_somebody_changes_it(self):
        self.assertEqual(analysisconfig.load(), {"lookup": "off", "chunking": "off", "evidence": "off"})
        analysisconfig.save({"lookup": "show"})
        self.assertEqual(analysisconfig.choice("lookup"), "show")
        self.assertEqual(analysisconfig.choice("evidence"), "off")
        for bad in ({"lookup": "everything"}, {"nonsense": "on"}, "x"):
            with self.assertRaises(ValueError):
                analysisconfig.save(bad)

    def test_a_store_that_cannot_be_read_is_off(self):
        os.makedirs(os.path.dirname(analysisconfig.STORE))
        with open(analysisconfig.STORE, "w") as f:
            f.write("{nonsense")
        self.assertEqual(analysisconfig.choice("lookup"), "off")

    def test_status_imports_nothing_and_says_what_is_missing(self):
        before = set(sys.modules)
        st = getanalysis.status()
        self.assertFalse(st["runtime"])
        self.assertFalse(st["programs"]["farahidi"]["have"])
        self.assertFalse(any(m["have"] for m in st["models"]))
        self.assertFalse(set(sys.modules) - before & {"ufal", "farahidi", "MorphologicalAnalysis"})

    def test_a_model_of_the_wrong_size_is_not_here(self):
        path = getanalysis.model_path("de")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(b"<html>a web page answered with status 200</html>")
        self.assertFalse(getanalysis.model_here("de"))

    def test_only_what_is_listed_can_be_asked_for(self):
        for bad in (["../../etc/passwd"], ["udpipe:xx"], "farahidi", [], None, ["http://example.com/x"]):
            with self.assertRaises(getanalysis.AnalysisError):
                getanalysis.check_items(bad)
        self.assertEqual(getanalysis.check_items(["farahidi", "farahidi", "udpipe:de"]), ["farahidi", "udpipe:de"])
        with self.assertRaises(getanalysis.AnalysisError):
            getanalysis.remove("../config")

    def test_removing_touches_nothing_outside_its_folder(self):
        beside = os.path.join(self.td.name, "beside.txt")
        with open(beside, "w") as f:
            f.write("x")
        os.makedirs(getanalysis.models_dir())
        getanalysis.remove("all")
        self.assertFalse(os.path.exists(getanalysis.FOLDER))
        self.assertTrue(os.path.exists(beside))

    def test_a_pinned_model_is_listed_with_all_it_takes_to_check_it(self):
        self.assertEqual(sorted(analysispins.UDPIPE_MODELS), sorted(A.SYNTAX))
        for pin in analysispins.UDPIPE_MODELS.values():
            self.assertEqual(len(pin["sha256"]), 64)
            self.assertGreater(pin["bytes"], 1000000)


class Prompts(unittest.TestCase):
    """Evidence through the real prompts and the real appliers, on copies of the fixtures."""
    def setUp(self):
        import test_glossregion as TG
        self.TG = TG
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.td = td.name
        cfg = tempfile.TemporaryDirectory()
        self.addCleanup(cfg.cleanup)
        p = mock.patch.object(analysisconfig, "STORE", os.path.join(cfg.name, "analysis.json"))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(A.reset)
        A.reset([Fake(codes=tuple(A.SYNTAX)), Fake("farahidi", ("ar",)), Fake("starlang", ("tr",))])

    def on(self):
        analysisconfig.save({"evidence": "on"})

    def spaced_book(self):
        import languages
        for bj in self.TG.BOOKS:
            b = self.TG.Book(self, bj)
            if b.L.code in evidence.LANGUAGES and languages.get_or_default(b.L.code).spaced:
                return b
        self.skipTest("no fixture edition in an analyzed language")

    def spaced_video(self):
        for vj in self.TG.VIDEOS:
            v = self.TG.Video(self, vj)
            if v.L.code in evidence.LANGUAGES:
                return v
        self.skipTest("no fixture video in an analyzed language")

    def test_off_gives_the_prompt_there_always_was(self):
        b = self.spaced_book()
        b.delete()
        off = b.prompt()["prompt"]
        self.assertNotIn('"analysis"', off)
        self.assertNotIn("What `analysis` is", off)
        self.on()
        A.reset([Fake(usable=False, codes=tuple(A.SYNTAX))])
        self.assertEqual(b.prompt()["prompt"], off, "not ready: nothing changes, nothing is demanded")

    def test_each_mode_has_it_on_chunks_to_do_and_the_rule_with_it(self):
        b = self.spaced_book()
        b.delete()
        self.on()
        for mode in ({}, {"perfield": True}, {"regloss": True}):
            r = b.prompt(**mode)
            self.assertIn('"analysis"', r["prompt"], mode)
            self.assertIn("What `analysis` is", r["prompt"], mode)
            data = json.loads(r["prompt"][r["prompt"].rindex('{"sentences"'):].split("\n```")[0])
            for u in data["sentences"]:
                for ch in u["chunks"]:
                    if "analysis" in ch:
                        self.assertTrue(ch.get("todo"), "evidence only on a chunk to do")

    def test_the_rule_survives_a_person_replacing_the_instructions(self):
        import glossregion
        b = self.spaced_book()
        b.delete()
        self.on()
        ctx, units, _f, _k = glossregion._book_units(b.d, b.first, b.last)
        made, _c = glossregion.assembled(ctx, units, "fill", instructions="Gloss as you like.", custom="mine")
        self.assertNotIn("The meaning (`en`) is a gloss", made.instructions)
        self.assertIn("What `analysis` is", made.contract)
        self.assertIn('"analysis"', made.data)

    def test_the_short_request_carries_the_same_data(self):
        b = self.spaced_book()
        b.delete()
        self.on()
        r = b.prompt()
        data = r["prompt"][r["prompt"].rindex('{"sentences"'):].split("\n```")[0]
        self.assertIn('"analysis"', r["skill"]["text"])
        self.assertIn(data.strip(), r["skill"]["text"])

    def test_an_answer_that_echoes_or_changes_analysis_stores_none_of_it(self):
        v = self.spaced_video()
        v.delete()
        self.on()
        for how in ("echo", "altered"):
            with self.subTest(how):
                r = v.prompt()
                doc = self._doc(r["prompt"], "captions")
                filled = 0
                for u in doc["captions"]:
                    for ch in u.get("chunks") or []:
                        if ch.get("todo"):
                            filled += 1
                            ch.update({f: "x" for f in ("tr", "voc", "en")})
                            if v.L.reading:
                                ch["kana"] = "x"
                            ch.pop("todo")
                            if how == "altered":
                                ch["analysis"] = [{"w": "evil", "lemma": "evil"}]
                self.assertTrue(filled)
                v.apply(doc, confirm=True)
                saved = json.dumps(self.TG.A.read(v.d), ensure_ascii=False)
                self.assertNotIn('"analysis"', saved)
                self.assertNotIn("evil", saved)
                v.delete()

    def _doc(self, prompt, key):
        return json.loads(prompt[prompt.rindex('{"%s"' % key):].split("\n```")[0])

    def test_an_answer_with_no_analysis_is_accepted_the_same(self):
        v = self.spaced_video()
        v.delete()
        self.on()
        doc = self._doc(v.prompt()["prompt"], "captions")
        for u in doc["captions"]:
            for ch in u.get("chunks") or []:
                if ch.pop("analysis", None) is not None or ch.get("todo"):
                    ch.update({f: "x" for f in ("tr", "voc", "en")})
                    ch.pop("todo", None)
        v.apply(doc, confirm=True)
        self.assertEqual(v.chunk()["en"], "x")

    def test_the_skill_has_the_rule_once_and_only_as_a_reference(self):
        import skills
        sk = skills.build("parseh-gloss")
        self.assertIn("references/analysis-evidence.md", sk.files)
        self.assertIn("analysis-evidence.md", sk.files["SKILL.md"])
        self.assertNotIn("What `analysis` is", sk.files["SKILL.md"])
        for path, text in sk.files.items():
            if path.startswith("references/stretch/"):
                self.assertNotIn("is evidence, and it can be wrong", text, path)

    def test_the_book_method_says_nothing_of_it_until_it_is_in_use(self):
        import languages
        import making
        L = languages.get_or_default("de")
        facts = {"python": "python3", "lib": "/lib"}
        self.assertEqual(making.evidence_helper(facts, L), "")
        self.on()
        line = making.evidence_helper(facts, L)
        self.assertIn("evidence.py de", line)
        self.assertIn("writes nothing", line)
        self.assertNotIn("](", line, "a link in it would point at a file a book's folder does not have")

    def fill(self, doc, key, how, reading):
        for u in doc[key]:
            for ch in u.get("chunks") or []:
                if ch.get("todo"):
                    ch.update({f: "x" for f in ("tr", "voc", "en")})
                    if reading:
                        ch["kana"] = "x"
                    ch.pop("todo")
                    if how == "altered":
                        ch["analysis"] = [{"w": "evil", "lemma": "evil"}]
                    if how == "none":
                        ch.pop("analysis", None)
        return doc

    def test_a_book_answer_that_echoes_or_changes_analysis_stores_none_of_it(self):
        import glob
        for how in ("echo", "altered", "none"):
            with self.subTest(how):
                b = self.spaced_book()
                b.delete()
                self.on()
                doc = self.fill(self._doc(b.prompt()["prompt"], "sentences"), "sentences", how, b.L.reading)
                b.apply(doc, confirm=True)
                self.assertEqual(b.recs()[b.k]["en"], "x", "the gloss went in")
                for path in glob.glob(os.path.join(b.d, "*")):
                    if os.path.isfile(path):
                        with open(path, "rb") as f:
                            data = f.read()
                        self.assertNotIn(b"evil", data, path)
                        self.assertNotIn(b'"analysis"', data, path)

    def test_a_persons_added_instructions_keep_the_rule_and_the_request_carries_them(self):
        import glossregion
        import prompts
        b = self.spaced_book()
        b.delete()
        self.on()
        with tempfile.TemporaryDirectory() as td, mock.patch.object(prompts, "STORE", os.path.join(td, "p.json")):
            p = prompts.save({"name": "mine", "surface": "book-region", "kind": "added", "text": "Be brief."})
            r = glossregion.book_prompt(b.d, b.first, b.last, prompt=(p.get("id") if isinstance(p, dict) else p.id))
        self.assertIn("Be brief.", r["prompt"])
        self.assertIn("What `analysis` is", r["prompt"])
        self.assertIn('"analysis"', r["skill"]["text"])
        self.assertIn("Be brief.", r["skill"]["text"])

    def test_it_stands_beside_the_scheme_and_the_short_vowels(self):
        import languages
        for bj in self.TG.BOOKS:
            b = self.TG.Book(self, bj)
            if not languages.get_or_default(b.L.code).strip_range or b.L.code not in evidence.LANGUAGES:
                continue
            b.delete()
            self.on()
            r = b.prompt(translit="ipa", marks="marks")
            self.assertIn('"analysis"', r["prompt"])
            self.assertIn("IPA", r["prompt"])
            self.assertIn("What `analysis` is", r["prompt"])
            self.assertIn("marks: on", r["skill"]["text"])
            return
        self.skipTest("no fixture with short vowels in an analyzed language")

    def test_an_altered_vowelled_lemma_cannot_slip_into_the_text(self):
        b = self.spaced_book()
        b.delete()
        self.on()
        before = b.recs()[b.k]["fa"]
        doc = self.fill(self._doc(b.prompt()["prompt"], "sentences"), "sentences", "altered", b.L.reading)
        b.apply(doc, confirm=True)
        self.assertEqual(b.recs()[b.k]["fa"], before)

    def test_the_skills_hash_moves_with_the_rule(self):
        import promptkit
        import skills
        was = skills.build("parseh-gloss").hash
        with mock.patch.object(promptkit, "_evidence_rule", lambda: "another rule"), \
                mock.patch.object(skills, "_fingerprint", lambda: "another"):
            self.assertNotEqual(skills.build("parseh-gloss").hash, was)
        skills._CACHE.clear()

    def test_the_prompt_says_what_it_holds_or_why_it_holds_none(self):
        b = self.spaced_book()
        b.delete()
        self.assertFalse([n for n in b.prompt()["notes"] if "analyzer" in n], "off: no word of it")
        self.on()
        self.assertTrue([n for n in b.prompt()["notes"] if "carr" in n and "analyzer" in n])
        A.reset([Fake(usable=False, codes=tuple(A.SYNTAX))])
        self.assertTrue([n for n in b.prompt()["notes"] if n.startswith("no analyzer's reading")])

    def test_a_literal_mark_in_the_text_stays_data(self):
        b = self.spaced_book()
        self.on()
        said = [{"w": "{{DATA}}", "lemma": "{{LANGUAGE}}"}]
        with mock.patch("evidence.entry", lambda t, s=None: said[0]):
            r = b.prompt(regloss=True)
        self.assertIn("{{DATA}}", self._doc(r["prompt"], "sentences")["sentences"][0]["chunks"][0]["analysis"][0]["w"])


class MoreEvidence(unittest.TestCase):
    def setUp(self):
        self.addCleanup(A.reset)
        self.f = Fake()
        A.reset([self.f])

    def captions(self, *texts):
        return [{"i": i, "chunks": [{"j": 0, "fa": t}]} if t else {"i": i, "plain": True, "chunks": []}
                for i, t in enumerate(texts)]

    def seen(self):
        real, out = self.f.analyze, []

        def spy(code, text, syntax=False, context=""):
            out.append(text)
            return real(code, text, syntax, context)
        self.f.analyze = spy
        return out

    def test_a_caption_is_read_with_those_it_runs_on_into(self):
        out = self.seen()
        ev = evidence.for_units("it", self.captions("il cane", "mangia la", "carne.", "poi dorme"), lambda ch: True)
        self.assertEqual(out, ["il cane mangia la carne.", "poi dorme"])
        self.assertEqual([e["w"] for e in ev.chunks[(1, 0)]], ["mangia", "la"])
        self.assertEqual([e["w"] for e in ev.chunks[(3, 0)]], ["poi", "dorme"])

    def test_a_plain_caption_parts_them_and_a_book_sentence_stands_alone(self):
        out = self.seen()
        evidence.for_units("it", self.captions("il cane", "", "mangia"), lambda ch: True)
        self.assertEqual(out, ["il cane", "mangia"])
        del out[:]
        units = [{"key": "a", "chunks": [{"j": 0, "fa": "senza punto"}]}, {"key": "b", "chunks": [{"j": 0, "fa": "altra"}]}]
        evidence.for_units("it", units, lambda ch: True)
        self.assertEqual(out, ["senza punto", "altra"])

    def test_a_run_has_a_limit(self):
        out = self.seen()
        evidence.for_units("it", self.captions(*[("parola%d " % i) * 100 for i in range(3)]), lambda ch: True)
        self.assertEqual(len(out), 3)

    def test_a_language_added_later_has_none_of_this(self):
        import languages
        self.assertEqual(A.analyze("xx", "abc").outcome, A.UNSUPPORTED)
        self.assertFalse(A.available("xx"))
        self.assertFalse(evidence.for_units("xx", self.captions("abc"), lambda ch: True))
        with tempfile.TemporaryDirectory() as td, mock.patch.object(analysisconfig, "STORE", os.path.join(td, "a.json")):
            analysisconfig.save({"chunking": "assist"})
            self.assertIsNone(chunker.assisting("xx"))
        self.assertIsNotNone(languages)


class PlainWords(unittest.TestCase):
    def test_the_grammar_is_said_in_a_readers_words_and_a_tag_nobody_named_is_left_out(self):
        self.assertEqual(lookupassist.words_for("VERB", {"Tense": "Past", "Person": "1", "Number": "Sing", "Polarity": "Neg"}),
                         "verb, past, negative, 1st person, singular")
        self.assertEqual(lookupassist.words_for("NOUN", {"Case": "Abl", "Person[psor]": "1", "Whatever": "X"}),
                         "noun, ablative, possessed by the 1st person")
        self.assertEqual(lookupassist.words_for("", {}), "")


class TheyDisagree(unittest.TestCase):
    def token(self, udpipe, *lemmas):
        c = tuple(A.Candidate(source="starlang", rank=i, lemma=x, root=x[:-3] if x.endswith("mak") else x) for i, x in enumerate(lemmas))
        w = A.Word(id="s0.w1", token="t0", source="udpipe", status=A.CONTEXTUAL, lemma=udpipe, upos="VERB")
        return A.Token(id="t0", start=0, end=4, surface="word", sentence="s0", candidates=c, syntax=(w,))

    def test_the_sentence_chooses_among_the_readings_by_lemma_or_root(self):
        m = lookupassist._machine(self.token("adam", "ada", "adam"))
        self.assertEqual((m["lemma"], m["others"], m["status"]), ("adam", ["ada"], A.CONTEXTUAL))
        m = lookupassist._machine(self.token("gel", "gelmak"))
        self.assertEqual(m["lemma"], "gelmak")

    def test_a_lemma_no_reading_has_is_no_choice_and_both_stay_seen(self):
        m = lookupassist._machine(self.token("ok", "okumak"))
        self.assertEqual((m["lemma"], m["others"]), ("", ["okumak", "ok"]))


class MainWord(unittest.TestCase):
    def tok(self, i, s, e, surface, upos, lemma):
        w = A.Word(id="s0.w%d" % i, token="t%d" % i, source="u", status=A.CONTEXTUAL, lemma=lemma, upos=upos)
        return A.Token(id="t%d" % i, start=s, end=e, surface=surface, sentence="s0", words=(w,))

    def test_a_row_is_about_its_word_of_content(self):
        toks = [self.tok(0, 0, 2, "L'", "DET", "le"), self.tok(1, 2, 7, "homme", "NOUN", "homme")]
        self.assertEqual(lookupassist._main_token(toks).surface, "homme")

    def test_inside_one_token_too_and_a_contraction_is_its_preposition(self):
        w = lambda i, u, l: A.Word(id="s0.w%d" % i, token="t0", source="u", status=A.CONTEXTUAL, lemma=l, upos=u)
        t = A.Token(id="t0", start=0, end=4, surface="وكتب", sentence="s0", words=(w(1, "CCONJ", "و"), w(2, "VERB", "كتب")))
        self.assertEqual(lookupassist._machine(t)["upos"], "VERB")
        t = A.Token(id="t0", start=0, end=3, surface="Zum", sentence="s0", words=(w(1, "ADP", "zu"), w(2, "DET", "der")))
        self.assertEqual(lookupassist._machine(t)["upos"], "ADP")


class SpokenAndAnalyzers(unittest.TestCase):
    """The normaliser reads for the analyzer, the analyzer chooses among the normaliser's readings (a0.6.0)."""
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        p = mock.patch.object(lookup, "DICT_DIR", self.td.name)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(A.reset)
        dictionary(self.td.name, "fa", [("خانه", "noun", "house", []), ("خون", "noun", "blood", []),
                                        ("کتاب", "noun", "book", [])])
        self.seen = []

    def backend(self, table):
        seen = self.seen

        class B(Fake):
            def analyze(s, code, text, syntax=False, context=""):
                seen.append(text)
                toks = []
                for i, (a, b) in enumerate(A.source_tokens(text)):
                    lemma, upos = table.get(text[a:b], (None, "NOUN"))
                    w = A.Word(id="s0.w%d" % (i + 1), token="t%d" % i, source="udpipe", status=A.CONTEXTUAL, lemma=lemma, upos=upos,
                               start=a, end=b, surface=text[a:b])
                    toks.append(A.Token(id="t%d" % i, start=a, end=b, surface=text[a:b], sentence="s0", words=(w,)))
                return A.Result(language=code, text=text, outcome=A.OK, backend="udpipe",
                                sentences=(("s0", 0, len(text)),), tokens=tuple(toks))
        A.reset([B(codes=("fa", "it"))])

    def test_a_language_with_no_spoken_rules_is_read_as_it_is(self):
        self.backend({})
        dictionary(self.td.name, "it", [("casa", "noun", "x", [])])
        self.assertEqual(lookupassist.formal_view("it", "la casa"), ("la casa", None))

    def test_with_no_dictionary_nothing_is_changed(self):
        self.backend({})
        self.assertEqual(lookupassist.formal_view("de", "das Haus"), ("das Haus", None))

    def test_a_spoken_word_is_read_formally_and_the_answer_comes_back_to_the_pages_word(self):
        self.backend({"خونه": (None, "NOUN")})
        text = "خونشون بزرگ"
        read, spans = lookupassist.formal_view("fa", text, "spoken")
        if spans:
            self.assertNotEqual(read, text)
            for (s, e), (a, b) in spans.items():
                self.assertEqual(text[s:e], text[s:e])
                self.assertGreater(b, a)

    def test_the_model_reads_the_first_reading_even_with_rivals(self):
        # given the page's letters it invents (میشه is میش); measured in tests/analysis_bench.py
        self.backend({"خونشون": ("خانه", "NOUN")})
        read, spans = lookupassist.formal_view("fa", "خونشون", "spoken")
        self.assertNotEqual(read, "خونشون")
        self.assertEqual(spans[(0, 6)], (0, len(read)))

    def test_on_a_word_the_normaliser_read_the_lemma_chooses_nothing(self):
        row = {"word": "خونه", "hits": [{"headword": "خانه", "pos": "noun", "spoken": {"as": "خانه"}},
                                        {"headword": "خون", "pos": "noun", "spoken": {"as": "خون"}},
                                        {"headword": "خواندن", "pos": "verb", "spoken": {"as": "خواند"}}]}
        said = {"here": True, "upos": "NOUN", "lemma": "خون", "readings": 0, "can_be": [], "relation": ""}
        L = lookup.languages.get_or_default("fa")
        self.assertEqual(lookupassist._fits(row, said, "fa", L), 2)
        self.assertTrue(row["hits"][0].get("fits"), "the lemma would have left only the second")

    def test_an_infinitive_a_treebank_calls_a_noun_is_the_verb_it_is_spelled(self):
        L = lookup.languages.get_or_default("fa")
        row = {"word": "رفتن", "hits": [{"headword": "رفتن", "pos": "verb"}, {"headword": "رف", "pos": "noun"}]}
        said = {"here": True, "upos": "NOUN", "lemma": "رف", "readings": 0, "can_be": [], "relation": ""}
        lookupassist._fits(row, said, "fa", L)
        self.assertEqual([h["headword"] for h in row["hits"] if h.get("fits")], ["رفتن"])
        row = {"word": "دست", "hits": [{"headword": "دست", "pos": "noun"}, {"headword": "دست", "pos": "verb"}, {"headword": "دس", "pos": "noun"}]}
        lookupassist._fits(row, said, "fa", L)
        self.assertEqual([h["pos"] for h in row["hits"] if h.get("fits")], ["noun", "noun"], "a noun spelled so is the word as it stands")


class TurkishTwoReaders(unittest.TestCase):
    """Starlang knows what a word can be, UDPipe what the sentence reads it as."""
    def token(self, surface, ud, parses):
        import analyzer_starlang as S
        word = A.Word(id="s0.w1", token="t0", source="udpipe", status=A.CONTEXTUAL, lemma=ud[0], upos=ud[1])
        return A.Token(id="t0", start=0, end=len(surface), surface=surface, sentence="s0", words=(word,),
                       candidates=tuple(S.candidate(i, *p) for i, p in enumerate(parses)))

    L = lookup.languages.get_or_default("tr")

    def test_a_word_derived_from_a_verb_is_read_as_the_verb_a_dictionary_files(self):
        m = lookupassist._machine(self.token("okumak", ("oku", "VERB"), [("oku", "oku+VERB+POS^DB+NOUN+INF+A3SG+PNON+NOM", "NOUN")]))
        self.assertEqual((m["upos"], m["here"], m["lemma"]), ("VERB", True, "okumak"))

    def test_the_sentence_chooses_between_readings_with_one_root(self):
        m = lookupassist._machine(self.token("kırdım", ("kır", "VERB"), [("kır", "kır+NOUN+A3SG+P1SG+NOM^DB+VERB+ZERO+PAST+A1SG", "VERB"),
                                                                       ("kır", "kır+VERB+POS+PAST+A1SG", "VERB")]))
        self.assertEqual(m["lemma"], "kırmak")

    def test_two_readers_agreeing_on_a_lemma_tell_nouns_apart(self):
        m = lookupassist._machine(self.token("adamı", ("adam", "NOUN"), [("ada", "ada+NOUN+A3SG+P1SG+ACC", "NOUN"), ("adam", "adam+NOUN+A3SG+PNON+ACC", "NOUN")]))
        self.assertTrue(m["agreed"])
        row = {"word": "adamı", "hits": [{"headword": "ada", "pos": "noun"}, {"headword": "adam", "pos": "noun"}]}
        self.assertEqual(lookupassist._fits(row, m, "tr", self.L), 1)
        self.assertTrue(lookupassist._first(row))
        self.assertEqual(row["hits"][0]["headword"], "adam")

    def test_agreeing_on_a_lemma_the_panel_lacks_marks_no_other(self):
        m = lookupassist._machine(self.token("erkenden", ("erken", "NOUN"), [("erke", "erke+NOUN+A3SG+P2SG+ABL", "NOUN"), ("erken", "erken+ADJ^DB+NOUN+ZERO+A3SG+PNON+ABL", "NOUN")]))
        row = {"word": "erkenden", "hits": [{"headword": "erkenden", "pos": "adv"}, {"headword": "erke", "pos": "noun"}]}
        self.assertEqual(lookupassist._fits(row, m, "tr", self.L), 0)

    def test_the_rescue_starts_from_what_the_sentence_allows_and_leaves_least_to_the_endings(self):
        m = lookupassist._machine(self.token("öğretmenimdir", ("öğretmenimdir", "NOUN"), [
            ("öğret", "öğret+VERB+POS^DB+NOUN+INF2+A3SG+P2SG+NOM^DB+VERB+ZERO+PRES+COP+A3SG", "VERB"),
            ("öğretme", "öğretme+NOUN+A3SG+P2SG+NOM^DB+VERB+ZERO+PRES+COP+A3SG", "VERB"),
            ("öğretmen", "öğretmen+NOUN+A3SG+P1SG+NOM^DB+VERB+ZERO+PRES+COP+A3SG", "VERB")]))
        self.assertEqual(m["can_be"][0], "öğretmen")


class SpokenAndAnalyzersMore(SpokenAndAnalyzers):
    def test_a_word_the_model_only_guesses_marks_no_entry(self):
        self.assertIsNone(lookupassist._wanted({"here": True, "upos": "VERB", "lemma": "", "readings": 0}))
        self.assertTrue(lookupassist._wanted({"here": True, "upos": "VERB", "lemma": "", "readings": 2}))
        self.assertTrue(lookupassist._wanted({"here": True, "upos": "VERB", "lemma": "x", "readings": 0}))

    def test_a_part_of_speech_needs_no_lemma(self):
        w = A.Word(id="s0.w1", token="t0", source="udpipe", status=A.CONTEXTUAL, upos="VERB")
        m = lookupassist._machine(A.Token(id="t0", start=0, end=4, surface="دیدم", sentence="s0", words=(w,)))
        self.assertEqual((m["pos"], m["here"], m["lemma"]), ("verb", True, ""))


class TwoBackends(unittest.TestCase):
    def tok(self, upos, cands, sel=None):
        w = A.Word(id="s0.w1", token="t0", source="udpipe", status=A.CONTEXTUAL, lemma="x", upos=upos)
        src = "farahidi" if sel else "starlang"
        c = tuple(A.Candidate(source=src, rank=i, lemma=l, upos=u) for i, (l, u) in enumerate(cands))
        s = A.Selection(source=src, lemma=sel, lemma_status=A.CONTEXTUAL) if sel else None
        return A.Token(id="t0", start=0, end=1, surface="x", sentence="s0", syntax=(w,), candidates=c, selection=s)

    def read(self, *a, **k):
        m = lookupassist._machine(self.tok(*a, **k))
        return m["upos"], m["here"]

    def test_morphology_knows_what_it_can_be_and_the_sentence_which(self):
        self.assertEqual(self.read("VERB", [("sinema", "NOUN")]), ("NOUN", True), "only a noun, whatever UDPipe says")
        self.assertEqual(self.read("NOUN", [("yüz", "NOUN"), ("yüz", "NUM")]), ("NOUN", True))
        self.assertEqual(self.read("VERB", [("yüz", "NOUN"), ("yüz", "NUM")]), ("VERB", False), "neither: nobody knows")
        self.assertEqual(self.read("AUX", [("olmak", "VERB")]), ("AUX", True), "an auxiliary is a verb")

    def test_arabic_when_the_two_disagree_nothing_is_claimed(self):
        self.assertEqual(self.read("NOUN", [("ضرب", "VERB")], sel="ضرب"), ("NOUN", False))
        self.assertEqual(self.read("VERB", [("ضرب", "VERB"), ("ضرب2", "NOUN")], sel="ضرب"), ("VERB", True))
        self.assertEqual(self.read("ADJ", [("كبير", "NOUN")], sel="كبير"), ("ADJ", True), "Farahidi's noun is every nominal")


class Loaded(unittest.TestCase):
    def test_loaded_is_said_language_by_language_and_goes_with_the_program(self):
        w = getanalysis.WORKER_PROGRAM
        b = getanalysis.backends()[0]
        with mock.patch.object(w, "alive", lambda: True), mock.patch.object(w, "loaded", {"udpipe": ["de"]}):
            self.assertTrue(b.status("de")["loaded"])
            self.assertFalse(b.status("fa")["loaded"])
        w.loaded = {"udpipe": ["de"]}
        w._stop()
        self.assertEqual(w.loaded, {})


class Fetching(unittest.TestCase):
    """The real fetch of a model, from a host on this machine that misbehaves as hosts do."""
    BODY = os.urandom(200000)

    def setUp(self):
        import hashlib
        import http.server
        test = self
        self.mode, self.asked = "good", 0

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                test.asked += 1
                body = test.BODY
                if test.mode == "page":
                    body = b"<html>a page, status 200</html>" * 100
                if test.mode == "500":
                    self.send_response(500)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if test.mode == "cut":
                    self.wfile.write(body[:1000])
                    self.close_connection = True
                    return
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        pin = dict(analysispins.UDPIPE_MODELS["de"], bytes=len(self.BODY), sha256=hashlib.sha256(self.BODY).hexdigest())
        for p in (mock.patch.object(getanalysis, "FOLDER", td.name),
                  mock.patch.dict(analysispins.UDPIPE_MODELS, {"de": pin}),
                  mock.patch.object(analysispins, "MODEL_HOST", "http://127.0.0.1:%d/%%s" % self.srv.server_address[1])):
            p.start()
            self.addCleanup(p.stop)
        getanalysis._cancel.clear()

    def get(self):
        getanalysis._get_model("de", lambda s: None)

    def test_a_good_file_arrives_and_a_second_asking_fetches_nothing(self):
        self.get()
        self.assertTrue(getanalysis.model_here("de"))
        n = self.asked
        self.get()
        self.assertEqual(self.asked, n)

    def test_a_web_page_answering_200_is_not_a_model_and_leaves_nothing(self):
        self.mode = "page"
        with self.assertRaises((getanalysis.AnalysisError, ValueError)):
            self.get()
        self.assertFalse(getanalysis.model_here("de"))
        self.assertFalse(os.path.exists(getanalysis.model_path("de")))

    def test_a_host_that_fails_is_said_and_asking_again_works(self):
        self.mode = "500"
        with self.assertRaises(getanalysis.AnalysisError):
            self.get()
        self.assertFalse(getanalysis.model_here("de"))
        self.mode = "good"
        self.get()
        self.assertTrue(getanalysis.model_here("de"))

    def test_a_line_that_drops_looks_ready_to_nobody_and_asking_again_finishes(self):
        self.mode = "cut"
        with self.assertRaises(getanalysis.AnalysisError):
            self.get()
        self.assertFalse(getanalysis.model_here("de"))
        self.mode = "good"
        self.get()
        self.assertTrue(getanalysis.model_here("de"))
        with open(getanalysis.model_path("de"), "rb") as f:
            self.assertEqual(f.read(), self.BODY)

    def test_stop_keeps_what_came_and_is_no_failure(self):
        import download
        getanalysis._cancel.set()
        with self.assertRaises(download.Cancelled):
            self.get()
        self.assertFalse(getanalysis.model_here("de"))


class MoreLookup(Lookup):
    """Turkish, Arabic and a person's word line, on real small dictionaries."""
    def test_a_turkish_light_verb_keeps_its_own_rows(self):
        dictionary(self.td.name, "tr", [("teşekkür", "noun", "thanks", []), ("etmek", "verb", "to do", ["ederim"])])
        before = lookup.look_up("tr", "teşekkür ederim")
        A.reset([Lemmas({"teşekkür": "teşekkür", "ederim": "etmek"}, contextual=False, name="starlang", codes=("tr",))])
        after = lookup.look_up("tr", "teşekkür ederim")
        lookupassist.apply("tr", after, "teşekkür ederim", "", "assist")
        self.assertEqual([[h["headword"] for h in w["hits"]] for w in after["words"]],
                         [[h["headword"] for h in w["hits"]] for w in before["words"]])
        self.assertEqual(after["words"][1]["machine"]["others"], ["etmek"])

    def test_a_turkish_root_alone_is_not_asked_as_a_word(self):
        dictionary(self.td.name, "tr", [("gel", "noun", "not the verb", [])])
        c = A.Candidate(source="starlang", rank=0, lemma="gelmek", root="gel", stem="gel", upos="VERB")

        class B(Fake):
            def analyze(self, code, text, syntax=False, context=""):
                t = A.Token(id="t0", start=0, end=len(text), surface=text, sentence="s0", candidates=(c,))
                return A.Result(language=code, text=text, outcome=A.OK, backend="starlang",
                                sentences=(("s0", 0, len(text)),), tokens=(t,))
        A.reset([B("starlang", ("tr",))])
        r = lookup.look_up("tr", "geldimx")
        lookupassist.apply("tr", r, "geldimx", "", "assist")
        self.assertFalse(r["words"][0]["hits"], "the root found nothing because it was never a lemma")

    def test_arabic_every_reading_stays_in_the_dictionarys_order_and_a_lost_word_is_found(self):
        dictionary(self.td.name, "ar", [("كتاب", "noun", "book", ["كتب"]), ("كتب", "verb", "to write", [])])
        was = [h["headword"] for h in lookup.look_up("ar", "كتب")["words"][0]["hits"]]
        cands = (A.Candidate(source="farahidi", rank=0, lemma="كَتَبَ", upos="VERB"),
                 A.Candidate(source="farahidi", rank=1, lemma="كِتَاب", upos="NOUN"))

        class B(Fake):
            def analyze(self, code, text, syntax=False, context=""):
                sel = A.Selection(source="farahidi", lemma="كِتَاب", lemma_status=A.CONTEXTUAL)
                t = A.Token(id="t0", start=0, end=len(text), surface=text, sentence="s0", candidates=cands, selection=sel)
                return A.Result(language=code, text=text, outcome=A.OK, backend="farahidi",
                                sentences=(("s0", 0, len(text)),), tokens=(t,))
        A.reset([B("farahidi", ("ar",))])
        r = lookup.look_up("ar", "كتب")
        lookupassist.apply("ar", r, "كتب", "", "assist")
        self.assertEqual([h["headword"] for h in r["words"][0]["hits"]], was)
        self.assertEqual(r["words"][0]["machine"]["others"], ["كَتَبَ"])
        r = lookup.look_up("ar", "وبقفلان")
        self.assertFalse(r["words"][0]["hits"])
        lookupassist.apply("ar", r, "وبقفلان", "", "assist")
        self.assertEqual(r["words"][0]["hits"][0]["headword"], "كتاب", "marks are not what keeps a lemma from its row")

    def test_a_reading_nobody_chose_is_not_said_as_if_it_had_been(self):
        c = (A.Candidate(source="starlang", rank=0, lemma="ada", upos="NOUN"),
             A.Candidate(source="starlang", rank=1, lemma="adam", upos="NOUN"))
        t = A.Token(id="t0", start=0, end=4, surface="adam", sentence="s0", candidates=c)
        m = lookupassist._machine(t)
        self.assertEqual((m["lemma"], m["others"], m["status"]), ("", ["ada", "adam"], A.LEXICAL))
        w = A.Word(id="s0.w1", token="t0", source="udpipe", status=A.CONTEXTUAL, lemma="adam", upos="NOUN")
        m = lookupassist._machine(A.Token(id="t0", start=0, end=4, surface="adam", sentence="s0", candidates=c, syntax=(w,)))
        self.assertEqual((m["lemma"], m["source"], m["others"]), ("adam", "udpipe", ["ada"]))

    def test_a_persons_word_line_never_reaches_the_analyzer(self):
        import serve
        dictionary(self.td.name, "ja", [("山", "noun", "mountain", [])])
        f = Fake(name="native", codes=("ja",))
        A.reset([f])
        with tempfile.TemporaryDirectory() as td, mock.patch.object(analysisconfig, "STORE", os.path.join(td, "a.json")):
            analysisconfig.save({"lookup": "assist"})
            h = serve.Handler.__new__(serve.Handler)
            h.send_json = lambda out, code=200: out
            out = h._lookup("ja", {"text": "山へ", "words": "山(やま) へ"}, "en")
            self.assertEqual(f.calls, 0)
            self.assertFalse(any("machine" in w for w in out["words"]))
            plain = h._lookup("ja", {"text": "山"}, "en")
            self.assertEqual(f.calls, 1, "the same language, with no word line, is asked")
            self.assertTrue(plain["words"])


class NewText(unittest.TestCase):
    """The real way new text is cut (lib/draft.py), with the choice on."""
    TEXT = "Il vecchio cane mangia la carne in cucina."

    def setUp(self):
        import draft
        self.draft = draft
        self.addCleanup(A.reset)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        p = mock.patch.object(analysisconfig, "STORE", os.path.join(td.name, "a.json"))
        p.start()
        self.addCleanup(p.stop)
        d = mock.patch.object(lookup, "DICT_DIR", td.name)
        d.start()
        self.addCleanup(d.stop)
        self.f = Fake()
        A.reset([self.f])

    def cut(self, how):
        return self.draft._cut_all([self.TEXT], "it", how)[0]

    def test_off_asks_nobody(self):
        self.cut("phrase")
        self.assertEqual(self.f.calls, 0)

    def test_on_asks_once_for_phrases_and_never_for_sentences(self):
        analysisconfig.save({"chunking": "assist"})
        got = self.cut("phrase")
        self.assertEqual(self.f.calls, 1)
        self.assertTrue(chunker.exact(got, self.TEXT))
        self.cut("sentence")
        self.assertEqual(self.f.calls, 1)

    def test_a_whole_book_from_text_goes_through_it(self):
        analysisconfig.save({"chunking": "assist"})
        r = self.draft.book_from_text(self.TEXT, "it", "title", slug="t", how="phrase")
        self.assertEqual(self.f.calls, 1)
        self.assertIn("carne", r["files"]["ch1.tex"])


class Boundaries(unittest.TestCase):
    def test_no_analyzer_is_imported_by_the_server_side_or_the_consumers(self):
        code = ("import sys; sys.path.insert(0, %r); import analyzer, getanalysis, evidence, lookupassist, chunker;"
                "print([m for m in ('ufal', 'farahidi', 'MorphologicalAnalysis', 'analyzer_udpipe', 'analyzer_farahidi',"
                " 'analyzer_starlang') if m in sys.modules])" % os.path.join(ROOT, "lib"))
        out = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "[]", out.stderr)

    def test_the_analysis_folder_is_personal_to_updates_and_releases_and_git(self):
        import release
        import updater
        self.assertIn("analysis/", updater.PERSONAL)
        with open(os.path.join(ROOT, "lib", "release.py"), encoding="utf-8") as f:
            self.assertIn('"analysis/"', f.read())
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("\nanalysis/\n", f.read())
        self.assertTrue(release)


if __name__ == "__main__":
    unittest.main()
