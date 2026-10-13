# SPDX-License-Identifier: GPL-3.0-or-later
"""The Persian colloquial normaliser, against its fixture (tests/fixtures/fa_colloquial/).

    python3 -m unittest tests.test_fa_colloquial          # the suite
    python3 tests/test_fa_colloquial.py --report          # every layer: rows due / passing / waiting
    python3 tests/test_fa_colloquial.py --record          # pin every row that passes now (state.json)

THE FIXTURE CAME FIRST.  Each row is a sentence of the note's families with the formal word
beside it (tests/fixtures/fa_colloquial/README.md says how a row reads); the normaliser is built
layer by layer, and a layer's rows go from waiting to due when `state.json`'s `built_layer`
reaches them.  A row that is due and red fails the suite.  A row that is not due yet is run all the
same and counted, so that the report says how far there is to go, and a row that PASSES today is
pinned (`state.json`, `pinned`) so that nothing already right is lost on the way.

Not here: how often a rule invents an answer in the real dictionary.  `dict/` is empty in a
checkout, the brief leaves measuring out, and these rows are what guards the traps.
"""
import glob
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "tests", ROOT / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import fa_colloquial_dict as fd      # noqa: E402
import lookup                        # noqa: E402
import spoken                        # noqa: E402
import spokenpeel                    # noqa: E402
import spokensound                   # noqa: E402
import spokenverb                    # noqa: E402

STATE = fd.FIXTURES / "state.json"
JOINERS = "‌‍"
# every family of the note, so that none can be left without a row
FAMILIES = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
            "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
            "E", "F", "G1", "G2", "G3", "G4", "G5", "G6", "H", "I"]
# the words of the note's section 14 (known traps), each of which needs a row; ده / دِ is left out, since the
# spoken particle has no formal word to land on
TRAP_WORDS = ["رفتن", "بودن", "بده", "بدم", "بدن", "گردن", "میان", "شن", "شم", "بدین", "باش", "نکنه", "بسم",
              "خون", "خونش", "خونها", "نون", "جون", "شون", "دون", "بوم", "دس", "درس", "راس", "هش", "چش", "چن", "چو",
              "قوه", "شر", "ما", "کو", "را", "منو", "رو", "تو", "کی", "چی", "چطوری", "باهم", "اینه", "مثلا", "اولا", "همچی",
              "مامانم", "خوبی", "خونه", "کتابا", "کتابو", "خوبن", "بچه‌ام",
              "نان", "منظوره", "بادی", "باورم", "حیاط", "حیات", "غذا", "قضا", "هال", "حال", "عالی", "آلی", "زهر", "ظهر"]


def norm(text):
    """A word without its joiners: the answer and the row may write a ZWNJ differently."""
    return "".join(c for c in (text or "") if c not in JOINERS)


def load_rows():
    """[(id, family id, layer, row)] in the files' order."""
    out = []
    for path in sorted(glob.glob(str(fd.FIXTURES / "rows" / "*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for fid, family in data.items():
            if fid.startswith("_"):
                continue
            for n, row in enumerate(family["rows"]):
                opts = row[3] if len(row) > 3 else {}
                out.append(("%s:%d" % (fid, n), fid, opts.get("layer", family["layer"]), row))
    return out


def state():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------ one row against one answer
def _mode(expectation):
    """('=', head) a direct hit · ('~', head) a direct hit with a second spoken line · ('!', head) no hit · ('s', head) a spoken hit"""
    if expectation[:1] in "=~!":
        return expectation[0], expectation[1:]
    return "s", expectation


def _matches(mode, hit):
    spoken = hit.get("spoken")
    if mode == "=":
        return not spoken
    if mode == "~":
        return bool(spoken) and bool(spoken.get("same"))
    return bool(spoken) and not spoken.get("same")


def evaluate(row, word):
    """The reasons `word` (the answer's entry for the row's word, or None) is not what the row says: [] when it is."""
    expect = row[2]
    opts = row[3] if len(row) > 3 else {}
    if word is None:
        return ["the answer has no word %r" % row[1]]
    hits = list(word.get("hits") or [])
    wanted = [_mode(e) for e in expect]
    positive = [(m, h) for m, h in wanted if m != "!"]
    fails = []
    for m, h in wanted:
        if m == "!" and any(x["headword"] == h for x in hits):
            fails.append("there is a hit of %s, and the row says there is none" % h)
    if opts.get("loose"):
        for m, h in positive:
            if not any(x["headword"] == h and _matches(m, x) for x in hits):
                fails.append("no %s hit of %s among %s" % ({"s": "spoken", "=": "direct", "~": "direct+second"}[m], h,
                                                          [x["headword"] + ("*" if x.get("spoken") else "") for x in hits]))
    else:
        for i, (m, h) in enumerate(positive):
            if i >= len(hits) or hits[i]["headword"] != h or not _matches(m, hits[i]):
                got = [x["headword"] + ("*" if x.get("spoken") else "") for x in hits]
                fails.append("hit %d should be %s%s, the hits are %s" % (i + 1, {"s": "spoken ", "=": "direct ", "~": "direct+second "}[m], h, got))
                break
    strict = opts.get("strict", not any(m == "s" for m, _h in positive))
    if strict:
        listed = [(m, h) for m, h in positive]
        for x in hits:
            if x.get("spoken") and not any(h == x["headword"] and m in "s~" for m, h in listed):
                fails.append("an unwanted spoken reading: %s" % x["headword"])
    if opts.get("noise") and hits:
        fails.append("something was found for a word that is noise: %s" % [x["headword"] for x in hits])
    # what the first spoken hit says of itself
    chosen = next((x for x in hits if x.get("spoken") and any(x["headword"] == h and m in "s~" for m, h in positive)), None)
    if chosen is None:
        chosen = next((x for x in hits if x.get("spoken")), None)
    said = (chosen or {}).get("spoken") or {}
    if "as" in opts and norm(said.get("as")) != norm(opts["as"]):
        fails.append("read as %r, the row says %r" % (said.get("as"), opts["as"]))
    if "why" in opts and opts["why"] not in (said.get("why") or ""):
        fails.append("the reason %r does not say %r" % (said.get("why"), opts["why"]))
    if "kind" in opts and said.get("kind") != opts["kind"]:
        fails.append("kind %r, the row says %r" % (said.get("kind"), opts["kind"]))
    if "sound" in opts and said.get("sound") != opts["sound"]:
        fails.append("sound %r, the row says %r" % (said.get("sound"), opts["sound"]))
    if "sound_kind" in opts and said.get("sound_kind") != opts["sound_kind"]:
        fails.append("the sound is %r, the row says it is %r" % (said.get("sound_kind"), opts["sound_kind"]))
    if "parts" in opts and [norm(p) for p in said.get("parts") or []] != [norm(p) for p in opts["parts"]]:
        fails.append("the pieces are %s, the row says %s" % (said.get("parts"), opts["parts"]))
    if "pieces" in opts:
        roles = {p.get("role") for p in said.get("pieces") or []}
        if not set(opts["pieces"]) <= roles:
            fails.append("the pieces named are %s, the row wants %s" % (sorted(roles), opts["pieces"]))
    if "readings" in opts:
        offered = {norm(x.get("as")) for hit in hits for x in ((hit.get("spoken") or {}).get("readings") or [])}
        offered |= {norm((x.get("spoken") or {}).get("as")) for x in hits if x.get("spoken")}
        missing = [r for r in opts["readings"] if norm(r) not in offered]
        if missing:
            fails.append("readings not offered: %s" % missing)
    return fails


def ask(row):
    """The answer's entry for the row's word -> (entry or None, a reason when the question could not be asked)."""
    text, word = row[0], row[1]
    opts = row[3] if len(row) > 3 else {}
    kwargs = {"register": opts["reg"]} if opts.get("reg") else {}
    try:
        answer = lookup.look_up("fa", text, **kwargs)
    except TypeError as error:
        return None, "look_up does not take %s yet (%s)" % (", ".join(kwargs) or "that", error)
    for w in (answer or {}).get("words") or []:
        # the answer's word is the token as the text wrote it, with the punctuation round it (واقن؟)
        if norm(w["word"]) == norm(word) or norm(lookup._bare(w["word"], lookup.languages.get_or_default("fa"))) == norm(word):
            return w, ""
    return None, ""


def judge(row):
    """[] when the row passes, else the reasons."""
    word, why = ask(row)
    return [why] if why else evaluate(row, word)


# ------------------------------------------------------------------ the dictionary
class Dictionary:
    """The fixture dictionary, in a folder of its own for as long as the suite runs."""
    folder = None

    @classmethod
    def open(cls):
        cls.folder = tempfile.TemporaryDirectory()
        fd.build(os.path.join(cls.folder.name, "fa.db"))
        cls.was = lookup.DICT_DIR
        lookup.DICT_DIR = cls.folder.name
        lookup._CONNS.map = {}

    @classmethod
    def close(cls):
        lookup.DICT_DIR = cls.was
        lookup._CONNS.map = {}
        cls.folder.cleanup()


def setUpModule():
    Dictionary.open()


def tearDownModule():
    Dictionary.close()


def headwords():
    """The headwords and forms of the fixture dictionary, folded as the lookup folds them."""
    import sqlite3
    c = sqlite3.connect(os.path.join(Dictionary.folder.name, "fa.db"))
    try:
        heads = {r[0] for r in c.execute("SELECT headword FROM entry")}
        forms = {r[0] for r in c.execute("SELECT form FROM form")}
    finally:
        c.close()
    return heads, forms


# ------------------------------------------------------------------------- the tests
class TheFixture(unittest.TestCase):
    def test_every_row_is_well_formed_and_asks_about_a_word_of_its_own_text(self):
        seen = set()
        for rid, fid, layer, row in load_rows():
            with self.subTest(row=rid):
                self.assertIn(len(row), (3, 4), rid)
                text, word, expect = row[0], row[1], row[2]
                opts = row[3] if len(row) > 3 else {}
                self.assertTrue(isinstance(text, str) and isinstance(word, str) and isinstance(expect, list), rid)
                self.assertIn(word, text, "the word %r is not in its text" % word)
                self.assertTrue(0 <= layer <= 9, rid)
                self.assertNotIn(rid, seen)
                seen.add(rid)
                for e in expect:
                    self.assertTrue(isinstance(e, str) and e.lstrip("=!~"), "%s: %r" % (rid, e))
                known = {"layer", "reg", "as", "why", "kind", "pieces", "parts", "readings", "sound", "sound_kind", "table", "loose",
                         "strict", "noise", "neutral", "stretch"}
                self.assertFalse(set(opts) - known, "%s: unknown options %s" % (rid, sorted(set(opts) - known)))

    def test_every_family_of_the_note_has_rows_and_every_trap_word_has_one(self):
        rows = load_rows()
        have = {fid for _rid, fid, _l, _r in rows}
        for fid in FAMILIES:
            self.assertIn(fid, have, "the family %s has no row" % fid)
        words = {norm(r[1]) for _rid, _f, _l, r in rows} | {norm(w) for _rid, _f, _l, r in rows for w in r[1].split()}
        for trap in TRAP_WORDS:
            with self.subTest(trap=trap):
                self.assertIn(norm(trap), words, "the trap word %s has no row" % trap)
        for fid in FAMILIES:
            n = sum(1 for _rid, f, _l, _r in rows if f == fid)
            self.assertGreaterEqual(n, 2, "%s has %d row(s)" % (fid, n))

    def test_every_headword_a_row_expects_is_in_the_dictionary_unless_the_row_says_it_is_not(self):
        heads, forms = headwords()
        folded = {norm(h) for h in heads} | {norm(f) for f in forms}
        for rid, _fid, _layer, row in load_rows():
            opts = row[3] if len(row) > 3 else {}
            for e in row[2]:
                mode, head = _mode(e)
                if mode == "!" or opts.get("table"):
                    continue
                with self.subTest(row=rid, head=head):
                    self.assertIn(norm(head), folded, "%s expects %s, which the dictionary does not have" % (rid, head))

    def test_a_spoken_word_is_not_an_entry_of_the_dictionary_unless_the_row_knows_it(self):
        """Nothing is easy because the dictionary happens to hold the spoken word: a row whose word IS a word of the
        dictionary must say so, by expecting the direct hit (`=` or `~`) or by saying it is the dictionary's own colloquial page."""
        heads, forms = headwords()
        folded = {norm(h) for h in heads} | {norm(lookup._fold(f, lookup.languages.get_or_default("fa"))) for f in forms}
        own = {norm(e[0]) for e in fd.load("colloquial.json")["entries"]}
        for rid, fid, _layer, row in load_rows():
            opts = row[3] if len(row) > 3 else {}
            word = norm(row[1])
            spoken_expected = any(_mode(e)[0] == "s" for e in row[2])
            if not spoken_expected or " " in row[1] or opts.get("noise"):
                continue
            if word in folded and word not in own and not any(_mode(e)[0] in "=~" for e in row[2]):
                with self.subTest(row=rid):
                    self.fail("%s: %r is already a word of the dictionary, and the row does not expect its direct reading" % (rid, row[1]))


    def test_every_case_of_the_panel_file_names_a_row_that_exists(self):
        rows = load_rows()
        cases = fd.load("panel.json")["cases"]
        self.assertGreaterEqual(len(cases), 10)
        ids = set()
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertNotIn(case["id"], ids)
                ids.add(case["id"])
                family, word = case["row"]
                matches = [r for _rid, fid, _l, r in rows if fid == family and norm(r[1]) == norm(word)]
                self.assertTrue(matches, "no row of %s is about %s" % (family, word))
                self.assertLess(case.get("at", 0), len(matches), "the case asks for a row there is not")
                self.assertTrue(case.get("shows"), "a case says what the panel shows")


class TheDictionary(unittest.TestCase):
    def test_it_is_shaped_like_wiktionarys_and_answers_formal_persian_as_the_lookup_does_today(self):
        r = lookup.look_up("fa", "او می‌رود")
        self.assertEqual([w["word"] for w in r["words"]], ["او", "می‌رود"])
        self.assertEqual(r["words"][1]["hits"][0]["headword"], "رفتن")
        # the table is generated, and every verb of it is reached in its simple forms
        for text, head in (("رفته‌اند", "رفتن"), ("بیایید", "آمدن"), ("نمی‌گویند", "گفتن"), ("برمی‌گردم", "برگشتن"),
                           ("می‌کنم", "کردن"), ("بنشین", "نشستن"), ("ببخشید", "بخشیدن")):
            with self.subTest(text=text):
                heads = [h["headword"] for w in lookup.look_up("fa", text)["words"] for h in w["hits"]]
                self.assertIn(head, heads)

    def test_the_spoken_forms_are_not_in_it(self):
        for spoken in ("میگه", "خونه", "اونجا", "میرم", "نمیدونم", "اومد", "گشنمه"):
            with self.subTest(spoken=spoken):
                hits = [h for w in lookup.look_up("fa", spoken)["words"] for h in w["hits"]]
                self.assertFalse([h for h in hits if h["headword"] == spoken], "%s is an entry" % spoken)


class TheHarness(unittest.TestCase):
    """The checker has to be able to FAIL: a suite that cannot say no says nothing."""
    HIT = {"headword": "خانه", "pos": "noun", "spoken": {"kind": "rule", "as": "خانه", "why": "ā → u", "sound": "xune", "sound_kind": "spoken", "parts": ["خانه", "شان"],
                                                         "pieces": [{"role": "emphatic"}], "readings": [{"as": "A"}, {"as": "B"}]}}

    def word(self, *hits):
        return {"word": "x", "hits": list(hits)}

    def test_a_row_passes_on_the_answer_it_describes_and_fails_on_every_other(self):
        row = ["t", "x", ["خانه"], {"as": "خانه", "why": "ā", "kind": "rule", "sound": "xune", "sound_kind": "spoken", "parts": ["خانه", "شان"],
                                    "pieces": ["emphatic"], "readings": ["A", "B"]}]
        self.assertEqual(evaluate(row, self.word(self.HIT)), [])
        self.assertTrue(evaluate(row, None))
        self.assertTrue(evaluate(row, self.word()), "no hit at all")
        self.assertTrue(evaluate(row, self.word(dict(self.HIT, headword="خان"))), "another headword")
        self.assertTrue(evaluate(row, self.word({"headword": "خانه"})), "a direct hit is not a spoken one")
        for key, value in (("as", "x"), ("why", "x"), ("kind", "entry"), ("sound", "x"), ("sound_kind", "formal"), ("parts", ["x"])):
            with self.subTest(option=key):
                bad = dict(self.HIT, spoken=dict(self.HIT["spoken"], **{key: value}))
                self.assertTrue(evaluate(row, self.word(bad)))
        self.assertTrue(evaluate(row, self.word(dict(self.HIT, spoken=dict(self.HIT["spoken"], pieces=[])))))
        self.assertTrue(evaluate(row, self.word(dict(self.HIT, spoken=dict(self.HIT["spoken"], readings=[])))))

    def test_order_direct_and_second_line_and_absence(self):
        direct, spoken = {"headword": "خون"}, dict(self.HIT, headword="خان")
        self.assertEqual(evaluate(["t", "x", ["=خون", "خان"]], self.word(direct, spoken)), [])
        self.assertTrue(evaluate(["t", "x", ["=خون", "خان"]], self.word(spoken, direct)), "the order is part of the row")
        self.assertEqual(evaluate(["t", "x", ["=خون", "خان"], {"loose": True}], self.word(spoken, direct)), [])
        # a row of direct hits only allows no spoken reading, unless it says so
        self.assertEqual(evaluate(["t", "x", ["=خون"]], self.word(direct)), [])
        self.assertTrue(evaluate(["t", "x", ["=خون"]], self.word(direct, spoken)), "strict by default")
        self.assertEqual(evaluate(["t", "x", ["=خون"], {"strict": False}], self.word(direct, spoken)), [])
        same = {"headword": "رفتن", "spoken": {"same": True, "as": "رفتند"}}
        self.assertEqual(evaluate(["t", "x", ["~رفتن"], {"as": "رفتند"}], self.word(same)), [])
        self.assertTrue(evaluate(["t", "x", ["~رفتن"]], self.word({"headword": "رفتن"})), "a second line is required by ~")
        self.assertTrue(evaluate(["t", "x", ["خانه", "!خان"]], self.word(self.HIT, spoken)), "! says there is no such hit")
        self.assertTrue(evaluate(["t", "x", [], {"noise": True}], self.word(direct)), "noise finds nothing")
        self.assertEqual(evaluate(["t", "x", [], {"noise": True}], self.word()), [])

    def test_the_joiners_do_not_decide_a_comparison(self):
        row = ["t", "x", ["خانه"], {"as": "می‌کند"}]
        self.assertEqual(evaluate(row, self.word(dict(self.HIT, spoken=dict(self.HIT["spoken"], **{"as": "میکند"})))), [])


class TheSuiteCanFail(unittest.TestCase):
    def test_the_rows_are_about_the_engine_and_not_about_the_fixture_dictionary(self):
        """Switch a stage of the pass off and the rows that stage is for turn red (a row that stays green was never testing it)."""
        from unittest import mock
        def red(family):
            # the rows built so far: a family's later layers are red until they are built
            return [rid for rid, fid, layer, row in load_rows() if fid == family and layer <= state()["built_layer"] and judge(row)]
        self.assertEqual(red("F"), [])
        with mock.patch.object(spoken.Rules, "_table", return_value=[]):
            self.assertGreater(len(red("F")), 10, "the word table is what F's rows read")
        self.assertEqual(red("A1"), [])
        with mock.patch.object(spoken.Rules, "_rules", return_value=[]):
            self.assertGreater(len(red("A1")), 6, "the writing-level rules are what A1's rows read (the swaps of ت and ط are the by-ear stage's too)")
        with mock.patch.object(spoken.Rules, "window", return_value=None):
            self.assertGreater(len(red("G5")) + len(red("G6")), 3, "the windows are what G5 and G6 read")
        # and each family of endings is what its own rows read
        for family, generator, least in (("G1", "_g_hem", 3), ("D3", "_g_object", 3), ("C6", "_g_copula", 8), ("D2", "_g_clitic", 10),
                                         ("D1", "_g_plural", 5), ("D4", "_g_definite", 3), ("G3", "_g_emphatic", 1)):
            self.assertEqual(red(family), [], family)
            with mock.patch.object(spokenpeel.Peeler, generator, lambda *a, **k: iter(())):
                self.assertGreaterEqual(len(red(family)), least, "%s is what the rows of %s read" % (generator, family))


    def test_the_verb_and_the_sound_layers_are_what_their_rows_read(self):
        """The same for layers 7 and 8: the verb table's analysis, the progressive and the perfect, the sound rules."""
        from unittest import mock

        def red(*families):
            return len([rid for rid, fid, layer, row in load_rows()
                        if fid in families and layer <= state()["built_layer"] and judge(row)])
        self.assertEqual(red("C1", "C2", "C3", "C4", "C5", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "T2"), 0)
        with mock.patch.object(spokenverb.Verbs, "analyze", return_value=[]):
            self.assertGreater(red("C2"), 15, "the spoken verb stems are what C2's rows read")
            self.assertGreater(red("C1", "C3", "C4"), 10, "and the endings, the past and the prefixes of C1, C3 and C4")
        with mock.patch.object(spoken.Rules, "_progressive_window", return_value=None):
            self.assertGreaterEqual(red("C4"), 2, "the helper داشتن and a verb is what C4's progressive rows read")
        with mock.patch.object(spoken.Rules, "_perfect", return_value=None):
            self.assertGreaterEqual(red("C5"), 1, "the perfect said as the past is C5's second reading")
        for family, least in (("B1", 6), ("B2", 5), ("B4", 8), ("B6", 3)):
            with mock.patch.object(spokensound.Sounds, "raw", return_value=[]):
                self.assertGreaterEqual(red(family), least, "the sound rules are what %s's rows read" % family)
        with mock.patch.object(spokenpeel.Peeler, "_sound", return_value=[]):
            self.assertGreater(red("B1", "B2", "B4", "T2"), 20, "the peeler asks the sound rules of every stem it reaches")

    def test_the_layer_nine_stages_are_what_their_rows_read(self):
        """The by-ear stage, the window of spaced letters, the words run together, the one-letter table rows, the doubled clitic,
        the modal and the reduced می-."""
        from unittest import mock

        def red(*families):
            return len([rid for rid, fid, layer, row in load_rows()
                        if fid in families and layer <= state()["built_layer"] and judge(row)])
        self.assertEqual(red("A3", "A4", "C4", "C7", "C9", "T1"), 0)
        real = spokensound.Sounds.raw
        with mock.patch.object(spokensound.Sounds, "raw", lambda self, word, stage=None: real(self, word, 8 if stage is None else stage)
                               if stage != 9 else []):
            self.assertGreaterEqual(red("A4"), 10, "the spellings by ear are the stage A4's rows read")
        with mock.patch.object(spoken.Rules, "_spaced_window", return_value=None):
            self.assertGreaterEqual(red("A3"), 1)
        with mock.patch.object(spoken.Rules, "_run_together", return_value=[]):
            self.assertGreaterEqual(red("A3"), 1)
        with mock.patch.object(spoken.Rules, "_table", return_value=[]):
            self.assertGreaterEqual(red("A4", "T1"), 4, "the one-letter words and بسم are rows of the table that need the page to be speech")
        with mock.patch.object(spoken.Rules, "_doubled", return_value=None):
            self.assertGreaterEqual(red("C7"), 1)
        with mock.patch.object(spoken.Rules, "_modal", return_value=None):
            self.assertGreaterEqual(red("C9"), 1)
        with mock.patch.object(spokenverb.Verbs, "analyze", return_value=[]):
            self.assertGreaterEqual(red("C4"), 2, "م- for می- is the verb table's prefix")

    def test_a_lookup_that_answers_nothing_turns_the_pinned_rows_red(self):
        from unittest import mock
        pinned = set(state()["pinned"])
        rows = [row for rid, _f, _l, row in load_rows() if rid in pinned and not (len(row) > 3 and row[3].get("noise"))]
        self.assertGreater(len(rows), 30)
        with mock.patch("lookup.look_up", return_value={"words": []}):
            self.assertTrue(all(judge(row) for row in rows), "a row passed with no answer at all")
        with mock.patch("lookup.look_up", return_value={"words": [{"word": "x", "hits": [{"headword": "zzz"}]}]}):
            self.assertTrue(all(judge(row) for row in rows), "a row passed on a wrong answer")


class ThePassKeepsItsPromises(unittest.TestCase):
    """What lib/spoken.py promises (its docstring), tested apart from the rows: the rows say what it reaches, these say
    what it must leave alone."""
    FORMAL = ["او می‌رود به خانه", "آنها رفته‌اند و کتاب‌ها را خواندند", "من نمی‌دانم که او چه می‌گوید", "می‌خواهم بروم",
              "بچه‌ها آمدند", "او در خانه بود و کتاب خواند", "همه چیز خوب است", "که", "همه", "کتاب را به او داد",
              "کِتاب خوب", "نمی‌بینمش", "می‌سازمت", "خون از زخم جاری شد", "نان و پنیر", "داداش آمد", "آری"]

    def words(self, text, **kw):
        return lookup.look_up("fa", text, **kw)["words"]

    def test_formal_text_answers_as_it_did_without_the_pass(self):
        rows = [r[0] for _rid, fid, _l, r in load_rows() if fid == "HAS"] + self.FORMAL
        spoken.forget()
        with_pass = [lookup.look_up("fa", text) for text in rows]
        try:
            spoken._RULES["fa"] = None
            without = [lookup.look_up("fa", text) for text in rows]
        finally:
            spoken.forget()
        for text, a, b in zip(rows, with_pass, without):
            with self.subTest(text=text):
                self.assertEqual(a, b)

    def test_a_hit_the_pass_made_says_so_and_a_dictionary_hit_does_not(self):
        said = {"kind", "as", "why", "sound", "sound_kind"}
        seen = 0
        for _rid, _fid, _layer, row in load_rows():
            for w in self.words(row[0]):
                for h in w["hits"]:
                    s = h.get("spoken")
                    if s is None:
                        continue
                    seen += 1
                    self.assertLessEqual(said, set(s), (row[0], h["headword"]))
                    self.assertIn(s["kind"], ("entry", "table", "rule", "spelling"), row[0])
                    self.assertTrue(s["why"] and s["as"], row[0])
                    self.assertIn(s["sound_kind"], ("spoken", "formal"))
                    if not s.get("same"):
                        # (a second line on the dictionary's own hit leaves that hit's note as it was)
                        self.assertTrue(h["note"].startswith(s["why"]), "a panel that cannot draw it yet still prints the reason: " + row[0])
        self.assertGreater(seen, 100)

    def test_a_word_the_dictionary_knows_keeps_its_first_answer(self):
        for text in ("کتاب", "خانه", "خون", "داداش", "تو", "نان", "که", "همه", "او", "کتاب‌ها", "رفتند", "می‌رود"):
            with self.subTest(text=text):
                first = self.words(text)[0]["hits"][0]
                self.assertNotIn("spoken", first)

    def test_nothing_is_swapped_for_another_word_of_its_own_family(self):
        # the rules land on real entries, and a real word that is one letter from another is not that other
        for text, never in (("باد", "بود"), ("پس", "بس"), ("سیم", "سوم"), ("زور", "زیر"), ("گرد", "کرد"), ("که", "ک")):
            with self.subTest(text=text):
                heads = [h["headword"] for w in self.words(text) for h in w["hits"] if h.get("spoken")]
                self.assertNotIn(never, heads)

    def test_laughter_links_and_names_are_not_looked_up_and_words_that_look_like_them_are(self):
        for text in ("خخخ", "ههههه", "@علی", "https://example.com", "www.x.ir", ":د", ":)"):
            with self.subTest(text=text):
                self.assertEqual([h for w in self.words(text) for h in w["hits"]], [])
        self.assertTrue(self.words("که")[0]["hits"] and self.words("همه")[0]["hits"] and self.words("کهکشان خوب")[0])

    def test_odd_input_does_not_raise(self):
        for text in ("", " ", "ـــ", "۱۲۳", "۱۲۳۴۵۶۷۸۹۰تا", "ا" * 500, "؟؟؟", "#", "#_", "@", "ء", "\u200c", "ٌ", "hello world",
                     "ییییی", "🙂", "۰تا", "۹۹۹۹۹۹۹تا", "ب" * 40, "ابی" * 30, "_", "#_ _#", "تا", "دو تا", "لایک", "حال کردن", "کتاب کتاب",
                     "کتاب متاب پول مول", "بی", "هیچ", "بی شعور بی شعور"):
            with self.subTest(text=text):
                lookup.look_up("fa", text)

    def test_the_pages_hint_adds_a_reading_and_changes_nothing_else(self):
        formal = "او کتاب خوب خواند و به خانه رفت"      # (no word of the note's traps: را is one, and a page that says it is speech reads it as راه)
        self.assertEqual(lookup.look_up("fa", formal), lookup.look_up("fa", formal, register="spoken"))
        plain = [h["headword"] for w in self.words("مثلا") for h in w["hits"]]
        hinted = [h["headword"] for w in self.words("مثلا", register="spoken") for h in w["hits"]]
        self.assertEqual(plain, ["مثلاً"])
        self.assertEqual(hinted, ["مثلاً", "مثل"])

    def test_the_formal_endings_of_formal_words_say_nothing(self):
        """A formal ending is a rule of the peel too, so that it competes; it must also win, and leave the old answer as it was."""
        for text in ("خوبم", "خوبی", "خوبیم", "کتابم", "کتابت", "کتابش", "کتابمان", "کتاب‌ها", "کتاب‌هایش", "کتاب‌هایی", "بزرگتر",
                     "بزرگ‌ترین", "دستشان", "صدای", "خودم", "خودش", "خسته‌ام", "کتابی", "پدرم", "او کتابش را برد"):
            with self.subTest(text=text):
                words = self.words(text)
                self.assertTrue(all("spoken" not in h for w in words for h in w["hits"]),
                                [(w["word"], [h["headword"] + "*" for h in w["hits"] if "spoken" in h]) for w in words])

    def test_formal_words_a_sound_rule_could_reach_say_nothing(self):
        """The dictionary decides a sound rule: a word it has (استخوان, دوست, نگاه) is read as itself, in every spelling a rule could
        have been asked about, with and without the page's hint."""
        for text in ("استخوان", "خانه", "دوست", "وقتی", "هفت", "نگاه", "فکر", "آقایان", "بدتر", "تهران", "ایرانی", "دیوانه", "مسجد",
                     "او دوست دارد", "آنجا نگاه کرد", "وقتی آمد، فکر کرد"):
            for kw in ({}, {"register": "spoken"}):
                with self.subTest(text=text, **kw):
                    words = self.words(text, **kw)
                    self.assertTrue(all("spoken" not in h for w in words for h in w["hits"]),
                                    [(w["word"], [h["headword"] + "*" for h in w["hits"] if "spoken" in h]) for w in words])

    def test_a_one_letter_word_is_read_only_where_the_page_is_speech(self):
        def told(text, formal, **kw):
            return [h for w in self.words(text, **kw) for h in w["hits"] if h.get("spoken") and h["headword"] == formal]
        # the page's hint, or a word only speech writes beside it, is what says so
        self.assertTrue(told("من ب تو گفتم", "به", register="spoken"))
        self.assertTrue(told("گفتم ک نمیام", "که"))
        self.assertTrue(told("بسم دیگه", "بس"))
        # and a letter is a letter in a text with no sign of speech: no one-letter word is told as another
        for text in ("من ب تو گفتم", "کتاب ک", "حرف ن", "خانه ب و خانه ک"):
            with self.subTest(text=text):
                self.assertTrue(all(not h.get("spoken") for w in self.words(text) for h in w["hits"]),
                                [(w["word"], [h["headword"] for h in w["hits"] if h.get("spoken")]) for w in self.words(text)])

    def test_words_run_together_are_cut_only_where_the_cut_is_more_than_a_coincidence(self):
        cut = self.words("تورادوست‌دارم")[0]["hits"]
        self.assertEqual([h["headword"] for h in cut], ["تو", "را", "دوست", "داشتن"])
        # a word of the dictionary, a name, and a word with one function word in two pieces are not cut
        for text in ("بنیاد", "مهراز", "پدرام", "نادر", "استخوان"):
            with self.subTest(text=text):
                words = self.words(text)
                self.assertTrue(all(h.get("spoken", {}).get("kind") != "rule" or " " not in h["spoken"]["as"]
                                    for w in words for h in w["hits"]), text)

    def test_letters_spaced_out_are_one_word_only_where_that_is_a_word(self):
        words = self.words("ن ه نمیشه")
        self.assertEqual(words[0]["word"], "ن ه")
        self.assertEqual(words[0]["hits"][0]["headword"], "نه")
        # two letters that are no word together stay two letters
        self.assertEqual([w["word"] for w in self.words("ب ک")], ["ب", "ک"])

    def test_a_spoken_verb_form_says_what_it_stands_for(self):
        hit = self.words("میگم")[0]["hits"][0]
        self.assertEqual((hit["headword"], hit["spoken"]["kind"]), ("گفتن", "rule"))
        self.assertEqual(norm(hit["spoken"]["as"]), norm("می‌گویم"))
        self.assertIn("گ", hit["spoken"]["why"])
        # the formal form of the same verb is a form of the dictionary's own, and the word is unmarked
        self.assertNotIn("spoken", self.words("می‌گویم")[0]["hits"][0])
        # an imperative with no ب is told as that, and the plural ending as the one it is
        said = self.words("بگین")[0]["hits"][0]["spoken"]["why"]
        self.assertIn("ین", said)

    def test_two_readings_of_one_letter_are_both_told(self):
        hits = self.words("اونا میگن مامانم اومد")[2]["hits"]
        spoken_hit = next(h for h in hits if h.get("spoken"))
        self.assertEqual({r["as"] for r in spoken_hit["spoken"]["readings"]}, {"مامان هم", "مامان هستم", "مامانم"})
        # without anything that says the page is speech, the word is `my mum` and nothing else
        self.assertTrue(all("spoken" not in h for h in self.words("مامانم اومد")[0]["hits"]) or
                        not self.words("مامانم")[0]["hits"][0].get("spoken"))
        # the object marker and `and`: both, in the order the next word says
        by_noun = self.words("کتابو تو")[0]["hits"][0]["spoken"]
        by_verb = self.words("کتابو بیار")[0]["hits"][0]["spoken"]
        self.assertEqual((by_noun["as"], by_verb["as"]), ("کتاب و", "کتاب را"))
        self.assertEqual({r["as"] for r in by_noun["readings"]}, {"کتاب و", "کتاب را"})

    def test_the_vb_of_a_spoken_answer_never_raises(self):
        import verbs
        r = lookup.look_up("fa", "خدافظ ببخشین فک میکنم دوس دارم اومد")
        self.assertTrue(verbs.attach(r, "fa", "خدافظ ببخشین فک میکنم دوس دارم اومد"))


class TheSoundRules(unittest.TestCase):
    """Layer 8, the engine alone (lib/spokensound.py): what a rule makes of a word, with no dictionary asked."""

    @classmethod
    def setUpClass(cls):
        L = lookup.languages.get_or_default("fa")
        cls.sounds = spoken.rules(lookup, L).sounds

    def test_the_rules_stand_in_the_notes_order_and_each_says_what_it_is(self):
        rules = self.sounds.rules
        self.assertGreater(len(rules), 20)
        self.assertEqual(len({r.id for r in rules}), len(rules))
        self.assertTrue(rules[0].id.startswith("B1"), "B1, the largest family, is first")
        sound = [r for r in rules if r.stage == 8]
        groups = [int(r.id[1]) for r in sound]
        self.assertEqual(groups, sorted(groups), "B1 to B8, as the note has them")
        self.assertEqual([r.stage for r in rules], sorted(r.stage for r in rules), "the spellings by ear (A4) come after the sound changes")
        self.assertTrue(any(r.stage == 9 for r in rules))
        for r in rules:
            with self.subTest(rule=r.id):
                self.assertTrue(r.note, "a rule says in words what changed")
                self.assertIn(r.cost, (1, 2, 3))

    def test_a_rule_gives_what_it_makes_of_a_word_at_every_place_it_fits(self):
        for word, formal in (("خونه", "خانه"), ("دوس", "دوست"), ("قلف", "قفل"), ("نگا", "نگاه"), ("کوچیک", "کوچک"), ("وخت", "وقت"),
                             ("دمبال", "دنبال"), ("استخون", "استخوان"), ("اسپ", "اسب"), ("بضی", "بعضی"), ("چار", "چهار")):
            with self.subTest(word=word):
                self.assertIn(formal, [v for v, _r in self.sounds.raw(word)])
                self.assertNotIn(word, [v for v, _r in self.sounds.raw(word)])
        # the spellings by ear are a stage of their own
        self.assertIn("مرسی", [v for v, _r in self.sounds.raw("مرصی", stage=9)])
        self.assertNotIn("مرسی", [v for v, _r in self.sounds.raw("مرصی", stage=8)])
        self.assertIn("خواب", [v for v, _r in self.sounds.raw("خاب", stage=9)])
        self.assertIn("شما", [v for v, _r in self.sounds.raw("شوما", stage=9)])
        self.assertLessEqual(len(self.sounds.raw("ا" * 200)), self.sounds.cap)
        self.assertEqual(self.sounds.raw(""), [])

    def test_two_rules_on_one_word_are_not_tried(self):
        # دوسه is دسته's cousin and needs one rule; a word that needs two is in the table (a guess upon a guess invents words)
        variants = {v for v, _r in self.sounds.raw("خونس")}
        self.assertNotIn("خانست", variants)

    def test_explain_names_the_rule_and_the_sound_follows_it(self):
        fold = lambda t: norm(t)
        rules = self.sounds.explain("خونه", "خانه", fold)
        self.assertEqual([r.id for r in rules], ["B1-an"])
        self.assertEqual(self.sounds.spoken_sound("xāne", rules), "xune")
        self.assertIn("ā", self.sounds.note(rules))
        rules = self.sounds.explain("دوس", "دوست", fold)
        self.assertEqual(self.sounds.spoken_sound("dust", rules), "dus")
        self.assertEqual(self.sounds.explain("خانه", "خانه", fold), [])
        self.assertEqual(self.sounds.explain("خونه", "دوست", fold), [])
        # a rule that gives no sound change leaves the formal sound (the answer says it is the formal one)
        self.assertEqual(self.sounds.spoken_sound("negāh", self.sounds.explain("نگا", "نگاه", fold)), "")
        self.assertEqual(self.sounds.spoken_sound("", rules), "")


class TheVerbTable(unittest.TestCase):
    PATH = fd.ROOT / "lib" / "lang" / "fa.spoken.verbs.tsv"

    def test_every_verb_is_whole(self):
        header, seen = None, set()
        for line in self.PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cells = line.split("\t")
            if header is None:
                header = cells
                self.assertEqual(header, ["infinitive", "past", "present", "spoken_present", "spoken_past", "formal", "flags", "src"])
                continue
            r = dict(zip(header, cells + [""] * (len(header) - len(cells))))
            with self.subTest(verb=r["infinitive"]):
                self.assertTrue(r["infinitive"].endswith("ن"))
                pre = next((f[4:] for f in r["flags"].split(",") if f.startswith("pre=")), "")
                self.assertEqual(pre + r["past"], r["infinitive"][:-1], "the past stem is the infinitive without its nun (and its preverb)")
                self.assertTrue(r["present"])
                self.assertNotIn(r["infinitive"], seen)
                seen.add(r["infinitive"])
                self.assertIn(r["src"], ("note", "hazm", "note+hazm"))
                for part in filter(None, r["formal"].split(";")):
                    self.assertIn(part.partition("=")[0], ("subj", "neg", "neg_past", "imp", "negimp"))
                for flag in filter(None, r["flags"].split(",")):
                    self.assertIn(flag.partition("=")[0], ("bare", "pre", "spoken_imp", "mi_stem"))
        self.assertGreater(len(seen), 60)

    def test_what_comes_from_hazms_verbs_travels_with_its_licence(self):
        import notices
        self.assertIn("iverbs.dat", (fd.ROOT / "lib" / "lang" / "fa.spoken.HAZM-LICENSE.txt").read_text(encoding="utf-8"))
        self.assertIn("iverbs.dat", notices.carried())
        self.assertIn("fa.spoken.verbs.tsv", (fd.ROOT / "html-guide" / "markdown" / "reference" / "licences.md").read_text(encoding="utf-8"))


class TheReviewOfATranscript(unittest.TestCase):
    """The ASR review's dictionary card (lib/asrdictionary.py): a transcript is speech, and a spoken reading reaches the card."""

    def test_a_spoken_hit_keeps_what_the_card_draws_of_it(self):
        import asrdictionary
        got = asrdictionary.Resolver("fa").lookup("خونه")
        self.assertEqual(got["state"], "found")
        hit = next(h for row in got["words"] for h in row["hits"] if h["headword"] == "خانه")
        self.assertEqual(norm(hit["spoken"]["as"]), norm("خانه"))
        self.assertIn("ā", hit["spoken"]["why"])
        self.assertEqual((hit["spoken"]["sound"], hit["spoken"]["sound_kind"]), ("xune", "spoken"))
        self.assertTrue(hit["note"].startswith(hit["spoken"]["why"]), "a card that cannot draw it still prints the reason")

    def test_a_hit_that_is_not_spoken_has_no_spoken_object(self):
        import asrdictionary
        got = asrdictionary.Resolver("fa").lookup("کتاب")
        self.assertTrue(all("spoken" not in h for row in got["words"] for h in row["hits"]))

    def test_what_is_kept_is_cut_to_size(self):
        import asrdictionary
        out = asrdictionary.spoken_of({"kind": "rule", "as": "x" * 900, "why": "y" * 900, "parts": ["p"] * 20, "same": True,
                                       "pieces": [{"text": "t", "role": "r", "note": "n" * 900}] * 10,
                                       "readings": [{"as": "a" * 900, "why": "w" * 900}] * 10})
        self.assertLessEqual(len(out["as"]), 200)
        self.assertLessEqual(len(out["why"]), 300)
        self.assertLessEqual(len(out["parts"]), 6)
        self.assertLessEqual(len(out["pieces"]), 4)
        self.assertLessEqual(len(out["readings"]), 4)
        self.assertTrue(out["same"])


class TheDoor(unittest.TestCase):
    """The book's and the player's lookup door (serve.py `_lookup`): what the readers are sent, as JSON."""

    def ask(self, body):
        import json
        import serve
        h = object.__new__(serve.Handler)
        sent = []
        h.send_json = lambda payload, status=200: sent.append(payload)
        h._lookup("fa", body, "en")
        return json.loads(json.dumps(sent[-1], ensure_ascii=False))     # what crosses the wire

    def test_a_spoken_word_comes_back_marked_and_with_its_reason(self):
        answer = self.ask({"text": "خدافظ اونا میگن"})
        first = answer["words"][0]
        self.assertEqual((first["word"], first["kind"]), ("خدافظ", "spoken"))
        self.assertIn("spoken Persian", first["via"])
        hit = first["hits"][0]
        self.assertEqual(hit["headword"], "خداحافظ")
        self.assertEqual((hit["spoken"]["kind"], hit["spoken"]["as"]), ("table", "خداحافظ"))
        self.assertTrue(hit["note"].startswith("spoken for"), "a panel that does not know `spoken` yet prints the reason as the note")
        self.assertNotIn("_tier", hit)
        self.assertNotIn("_rule", first)

    def test_a_window_of_words_is_one_word_of_the_answer(self):
        words = [w["word"] for w in self.ask({"text": "فک میکنم دوس دارم"})["words"]]
        self.assertEqual(words, ["فک میکنم", "دوس دارم"])

    def test_the_pages_register_is_read_and_nothing_else_is(self):
        def heads(register):
            body = {"text": "مثلا"}
            if register is not None:
                body["register"] = register
            return [h["headword"] for h in self.ask(body)["words"][0]["hits"]]
        self.assertEqual(heads(None), ["مثلاً"])
        self.assertEqual(heads("spoken"), ["مثلاً", "مثل"])
        for other in ("formal", "", 1, ["spoken"], {"x": 1}):
            self.assertEqual(heads(other), ["مثلاً"], other)

    def test_formal_text_is_sent_as_it_always_was(self):
        answer = self.ask({"text": "او کتاب را به خانه برد"})
        self.assertTrue(all("spoken" not in h for w in answer["words"] for h in w["hits"]))
        self.assertTrue(all(w["kind"] != "spoken" for w in answer["words"]))


class TheTables(unittest.TestCase):
    PATH = fd.ROOT / "lib" / "lang" / "fa.spoken.words.tsv"

    def rows(self):
        header, out = None, []
        for line in self.PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cells = line.split("\t")
            if header is None:
                header = cells
                continue
            self.assertEqual(len(cells), len(header), line)
            out.append(dict(zip(header, cells)))
        self.assertEqual(header, ["spoken", "formal", "kind", "flags", "gloss", "note", "src"])
        return out

    def test_every_row_is_whole(self):
        seen = set()
        for r in self.rows():
            with self.subTest(row=r["spoken"]):
                self.assertTrue(r["spoken"].strip() and r["formal"].strip())
                self.assertIn(r["kind"], ("word", "phrase", "formula", "cv", "standalone", "policy"))
                self.assertIn(r["src"], ("hazm", "note", "own"))
                self.assertNotIn((r["spoken"], r["formal"]), seen)
                seen.add((r["spoken"], r["formal"]))
                if r["kind"] in ("standalone", "formula"):
                    self.assertTrue(r["gloss"], "a row that has no formal twin says what it means")
                for flag in filter(None, r["flags"].split(",")):
                    self.assertIn(flag.partition("=")[0], ("certain", "show", "likelier", "pos", "with", "glue", "needs"))
                    if flag.startswith("show="):
                        self.assertIn(flag[5:], ("always", "spoken", "never"))
                    if flag.startswith("needs="):
                        self.assertEqual(flag[6:], "spoken")
                if r["kind"] in ("word", "phrase"):
                    folded = lambda t: "".join(c for c in t if c not in JOINERS and not 0x64B <= ord(c) <= 0x652)
                    self.assertNotEqual(folded(r["spoken"]), folded(r["formal"]), "an identity row: the dictionary reaches it already")

    def test_what_comes_from_hazm_travels_with_its_licence(self):
        import notices
        rows = [r for r in self.rows() if r["src"] == "hazm"]
        self.assertGreater(len(rows), 100)
        text = (fd.ROOT / "lib" / "lang" / "fa.spoken.HAZM-LICENSE.txt").read_text(encoding="utf-8")
        for said in ("Copyright (c) 2013 Alireza Nourian", "Permission is hereby granted"):
            self.assertIn(said, text)
        self.assertIn("Alireza Nourian", notices.carried())
        guide = (fd.ROOT / "html-guide" / "markdown" / "reference" / "licences.md").read_text(encoding="utf-8")
        self.assertIn("Alireza Nourian", guide)
        self.assertIn("fa.spoken.HAZM-LICENSE.txt", guide)


class TheRows(unittest.TestCase):
    """The families, layer by layer.  A row is DUE once its layer is built or the row is pinned; a row that is due
    and red fails, a row that is not due is only counted (`--report`)."""

    def test_every_row_that_is_due_passes(self):
        built, pinned = state()["built_layer"], set(state()["pinned"])
        failed, waiting, due = [], 0, 0
        for rid, fid, layer, row in load_rows():
            is_due = layer <= built or rid in pinned
            reasons = judge(row)
            if is_due:
                due += 1
                if reasons:
                    failed.append("%s %s %r: %s" % (rid, "(layer %d)" % layer, row[1], "; ".join(reasons)))
            elif reasons:
                waiting += 1
        self.assertFalse(failed, "%d of %d due rows are red (%d more are not due yet):\n  %s" % (
            len(failed), due, waiting, "\n  ".join(failed[:40])))
        print("\n  fa colloquial: %d rows due and green, %d waiting for their layer (built layer %d)" % (due, waiting, built))


def report():
    rows = load_rows()
    built, pinned = state()["built_layer"], set(state()["pinned"])
    layers = {}
    for rid, fid, layer, row in rows:
        ok = not judge(row)
        a = layers.setdefault(layer, [0, 0])
        a[0] += 1
        a[1] += ok
    print("built layer %d, %d rows pinned" % (built, len(pinned)))
    for layer in sorted(layers):
        total, ok = layers[layer]
        print("  layer %d: %3d rows, %3d passing now%s" % (layer, total, ok, "   (due)" if layer <= built else ""))
    print("  all: %d rows, %d passing" % (len(rows), sum(v[1] for v in layers.values())))


def record():
    rows = load_rows()
    s = state()
    s["pinned"] = [rid for rid, _fid, _layer, row in rows if not judge(row)]
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("%d rows pinned" % len(s["pinned"]))


if __name__ == "__main__":
    if "--report" in sys.argv or "--record" in sys.argv:
        Dictionary.open()
        try:
            record() if "--record" in sys.argv else report()
        finally:
            Dictionary.close()
    else:
        unittest.main()
