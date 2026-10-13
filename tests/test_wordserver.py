# SPDX-License-Identifier: GPL-3.0-or-later
"""The word line at the server: a lookup divided by a chunk's own words, and
the two routes that propose a line for a chunk that has none.

    python3 -m unittest discover -s tests -p test_wordserver.py

Standard library only, like the server.  The dictionaries are a few rows each,
built here the way tests/smoke.py builds one.  The server is serve.py on a
free port over plain http, with lib/lookup.py pointed at those dictionaries
before serve.py imports it, so nothing is written under dict/; a fixture book
and two fixture videos are parked on the shelf for the length of the class,
under names no real one has, and taken off again.

Under the machine's python3 the analyzers are not importable, and a proposal
must say so: `available: false`, no words.  Under the ilya-frank environment
the proposal must rejoin its text instead.
"""
import http.client
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LIB = os.path.join(ROOT, "lib")
FIX = os.path.join(ROOT, "tests", "fixtures")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import languages                                              # noqa: E402
import lookup                                                 # noqa: E402
import wordline                                               # noqa: E402
import words                                                  # noqa: E402


def _dict(path, code, rows):
    """tests/smoke.py's _fixture_dict: `rows` is [(headword, translit, pos,
    senses, [(form, note), ...])], each form written as spelt and folded."""
    c = lookup.create(path)
    for head, tr, pos, senses, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, translit, pos, sense) "
                        "VALUES (?,?,?,?)", (head, tr, pos, "\n".join(senses)))
        for form, note in [(head, "")] + list(forms):
            for v in {form, form.casefold()}:
                c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)",
                          (v, cur.lastrowid, note))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("lang", code), ("source", "a fixture"), ("licence", "none")])
    c.commit()
    c.close()


def _build(where):
    _dict(os.path.join(where, "ja.db"), "ja", [
        ("お爺さん", "ojiisan", "noun", ["grandfather"], []),
        ("と", "to", "particle", ["and"], []),
        ("住む", "sumu", "verb", ["to live, to dwell"], []),
        ("居る", "iru", "verb", ["to be"], [("いました", "polite past")]),
        ("子供", "kodomo", "noun", ["a child"], []),
        ("の", "no", "particle", ["of"], []),
    ])
    _dict(os.path.join(where, "zh.db"), "zh", [
        ("我", "wǒ", "pron", ["I"], []),
        ("要", "yào", "verb", ["to want"], []),
        ("一", "yī", "num", ["one"], []),
        ("杯", "bēi", "noun", ["a cup"], []),
        ("一杯", "yībēi", "phrase", ["a cup of"], []),
        ("茶", "chá", "noun", ["tea"], []),
    ])


def _said(r):
    return [w["word"] for w in r["words"]]


def _forget():
    for conn, _stamp in (getattr(lookup._CONNS, "map", None) or {}).values():
        if conn is not None:
            conn.close()
    lookup._CONNS.map = {}


ZH_LINE = "我(wǒ) 要(yào) 一(yì) 杯(bēi) 茶(chá)"


class PersianCopulaLookUpTests(unittest.TestCase):
    """Colloquial -e uses the ordinary dictionary route, with safe fallbacks."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.dict_path = os.path.join(td.name, "fa.db")
        _dict(self.dict_path, "fa", [
            ("کوچیک", "", "adj", ["small"], []),
            ("کتاب", "", "noun", ["book"], []),
            ("خسته", "", "adj", ["tired"], []),
            ("دانشجو", "", "noun", ["student"], []),
            ("اینجا", "", "adv", ["here"], []),
            ("پریدن", "", "verb", ["jump"], [(form, "present") for form in
                ("میپرد", "میپرند", "میپرید", "نمیپرد", "نمیپرند", "نمیپرید")]),
            ("آمدن", "", "verb", ["come"], [("میآد", "colloquial present")]),
            ("دید", "", "verb", ["saw"], []),
            ("در", "", "prep", ["in"], []),
            ("نام", "", "name", ["a name"], []),
            ("ب", "", "noun", ["a fixture one-letter stem"], []),
        ])
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()

        def restore():
            _forget()
            lookup.DICT_DIR = was
        self.addCleanup(restore)

    def row(self, word):
        return lookup.look_up("fa", word)["words"][0]

    def test_colloquial_copula_reaches_existing_stem(self):
        for word in ("کوچیکه", "کوچیکه،", "کوچیک‌ه", "کُوچیکه"):
            with self.subTest(word=word):
                row = self.row(word)
                self.assertEqual([h["headword"] for h in row["hits"]], ["کوچیک"])
                self.assertEqual(row["word"], word)
                # the spoken pass (lib/spokenpeel.py) now says what the old rule only did: it is spoken, and the ending is named
                self.assertEqual(row["kind"], "spoken")
                self.assertIn("copula", row["via"])
                spoken = row["hits"][0]["spoken"]
                self.assertEqual(spoken["as"], "کوچیک است")
                self.assertEqual([p["role"] for p in spoken["pieces"]], ["copula"])
        self.assertEqual(self.row("کتابه")["hits"][0]["headword"], "کتاب")

    def test_direct_entry_still_wins(self):
        # Add the exact spelling only to the scratch dictionary, never a real one.
        with sqlite3.connect(self.dict_path) as c:
            cur = c.execute("INSERT INTO entry (headword, pos, sense) VALUES (?,?,?)",
                            ("کوچیکه", "adj", "the exact fixture form"))
            c.execute("INSERT INTO form (form, entry_id) VALUES (?,?)",
                      ("کوچیکه", cur.lastrowid))
        _forget()
        row = self.row("کوچیکه")
        self.assertEqual([h["headword"] for h in row["hits"]], ["کوچیکه"])
        self.assertEqual(row["kind"], "surface")

    def test_short_or_non_nominal_stems_do_not_count_as_copulas(self):
        for word in ("به", "دیده", "دره", "نامه"):
            with self.subTest(word=word):
                self.assertEqual(self.row(word)["hits"], [])

    def test_copula_route_does_not_peel_its_stem_again(self):
        routes = lookup._routes("نکوچیکه", languages.get("fa"))
        copula_routes = [r for r in routes if "copula -e" in r.how]
        self.assertTrue(copula_routes)
        self.assertFalse(any("copula -e taken off, then" in r.how for r in routes))
        self.assertFalse(any(", then the colloquial copula -e" in r.how for r in routes))
        self.assertEqual(self.row("نکوچیکه")["hits"], [])
        self.assertEqual(self.row("زکوچیکه")["hits"], [])

    def test_nominal_copula_paradigms_and_vowel_hosts(self):
        for base, endings in (("کوچیک", ("م", "ی", "ه", "یم", "ید", "ند", "ین", "ن")),
                              ("خسته", ("ام", "ای", "ایم", "اید", "اند", "ست")),
                              ("دانشجو", ("ییم", "یید", "ست")),
                              ("اینجا", ("ست",))):
            for ending in endings:
                with self.subTest(base=base, ending=ending):
                    row = self.row(base + ending)
                    self.assertEqual([h["headword"] for h in row["hits"]], [base])
        self.assertEqual(self.row("کوچیکست")["hits"], [],
                         "contracted -st needs a vowel-ending host")

    def test_ordered_nominal_combinations(self):
        for base, forms in (("کتاب", ("کتابمونه", "کتابمونن", "کتابامون", "کتابامونه",
                                     "کتابهامونه", "کتابهایمونه")),
                            ("کوچیک", ("کوچیکتره", "کوچیکترینشونه"))):
            for word in forms:
                with self.subTest(word=word):
                    self.assertEqual([h["headword"] for h in self.row(word)["hits"]], [base])
        self.assertEqual(lookup.MAX_PEEL, 2)

    def test_nominal_guards_and_order_are_not_bypassed(self):
        for word in ("دیده", "دیدین", "دیدن", "نامه", "درن", "نکوچیکین", "نکوچیکن",
                     "کوچیکهتر", "کوچیکهه", "کتابمونهاه", "زززززین"):
            with self.subTest(word=word):
                self.assertEqual(self.row(word)["hits"], [])
        for word in ("دیده", "درن", "کتابا"):
            self.assertFalse(lookup._is_word(lookup._conn("fa"), word, languages.get("fa")))
        # a bare -ā is no rule's guess (the routes above still find nothing).  The spoken table (lib/spoken.py) holds
        # کتابا as a pair of its own, and then says so: the hit is marked as spoken, never taken for an entry
        hits = self.row("کتابا")["hits"]
        self.assertEqual([h["headword"] for h in hits], ["کتاب"])
        self.assertTrue(all(h.get("spoken") for h in hits))

    def test_spoken_verbs_require_an_attested_full_verb_form(self):
        for word in ("میپره", "میپرن", "میپرین", "نمیپره", "نمیپرن", "نمیپرین"):
            with self.subTest(word=word):
                self.assertEqual([h["headword"] for h in self.row(word)["hits"]], ["پریدن"])
        for word in ("میاد", "نمیاد"):
            self.assertEqual([h["headword"] for h in self.row(word)["hits"]], ["آمدن"])
        for word in ("پره", "میززززه", "میززززین", "نمیززززن"):
            self.assertEqual(self.row(word)["hits"], [])

    def test_all_direct_forms_still_have_precedence(self):
        with sqlite3.connect(self.dict_path) as c:
            for word in ("کوچیکین", "کوچیکن", "کتابمونه", "کوچیکتره", "میاد"):
                cur = c.execute("INSERT INTO entry (headword, pos, sense) VALUES (?,?,?)",
                                (word, "name", "the exact fixture form"))
                c.execute("INSERT INTO form (form, entry_id) VALUES (?,?)", (word, cur.lastrowid))
        _forget()
        for word in ("کوچیکین", "کوچیکن", "کتابمونه", "کوچیکتره", "میاد"):
            with self.subTest(word=word):
                self.assertEqual([h["headword"] for h in self.row(word)["hits"]], [word])
                self.assertEqual(self.row(word)["kind"], "surface")


class LookUpTests(unittest.TestCase):
    """lookup.look_up, handed a chunk's own words."""

    @classmethod
    def setUpClass(cls):
        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _build(td.name)
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()

        def back():
            lookup.DICT_DIR = was
            _forget()
        cls.addClassCleanup(back)

    def test_a_word_nobody_can_place_is_not_cut_again(self):
        given = [{"word": "住んでいました", "lemmas": []}]
        r = lookup.look_up("ja", "住んでいました", pieces=given)
        self.assertEqual(_said(r), ["住んで", "いました"],
                         "a model's piece is cut again where the rules account for it")
        r = lookup.look_up("ja", "住んでいました", pieces=given, authoritative=True)
        self.assertEqual(_said(r), ["住んでいました"])
        self.assertEqual(r["words"][0]["hits"], [])
        self.assertEqual(r["words"][0]["i"], 0)

    def test_one_row_per_piece_in_order(self):
        given = [{"word": w} for w in ("子供", "と", "子供", "の")]
        r = lookup.look_up("ja", "子供と子供の", pieces=given, authoritative=True)
        self.assertEqual(_said(r), ["子供", "と", "子供", "の"])
        self.assertEqual([w["i"] for w in r["words"]], [0, 1, 2, 3])
        self.assertTrue(r["words"][2]["hits"])
        self.assertIsNot(r["words"][0], r["words"][2])
        self.assertEqual(r["words"][0]["hits"], r["words"][2]["hits"])
        r = lookup.look_up("ja", "子供と子供の", pieces=given)
        self.assertEqual(_said(r), ["子供", "と", "の"], "without the flag a word is given once")
        self.assertTrue(all("i" not in w for w in r["words"]))

    def test_a_piece_of_no_letters_keeps_its_place(self):
        given = [{"word": "子供"}, {"word": "、"}, {"word": ""}, {"word": "の"}]
        r = lookup.look_up("ja", "子供、の", pieces=given, authoritative=True)
        self.assertEqual(_said(r), ["子供", "、", "", "の"])
        self.assertEqual([w["i"] for w in r["words"]], [0, 1, 2, 3])
        self.assertEqual(r["words"][1], {"word": "、", "hits": [], "via": "", "tried": [],
                                         "kind": "", "i": 1})
        self.assertEqual(_said(lookup.look_up("ja", "子供、の", pieces=given)), ["子供", "の"])

    def test_the_cap_is_far_above_a_cuts(self):
        distinct = [{"word": "語%d" % k} for k in range(30)]
        self.assertEqual(len(lookup.look_up("ja", "x", pieces=distinct)["words"]), 24)
        r = lookup.look_up("ja", "x", pieces=distinct, authoritative=True)
        self.assertEqual(len(r["words"]), 30)
        r = lookup.look_up("ja", "x", pieces=[{"word": "と"}] * (lookup.MAX_OWN_WORDS + 50),
                           authoritative=True)
        self.assertEqual(len(r["words"]), lookup.MAX_OWN_WORDS)
        self.assertEqual(r["words"][-1]["i"], lookup.MAX_OWN_WORDS - 1)

    def test_spellings_offered_are_still_tried(self):
        r = lookup.look_up("ja", "おじいさんと", authoritative=True, pieces=[
            {"word": "おじいさん", "lemmas": ["お爺さん"]}, {"word": "と"}])
        self.assertEqual(r["words"][0]["hits"][0]["headword"], "お爺さん")
        self.assertIn("under お爺さん", r["words"][0]["via"])

    def test_the_division_is_the_documents_and_not_longest_match(self):
        self.assertEqual(_said(lookup.look_up("zh", "我要一杯茶")), ["我", "要", "一杯", "茶"])
        given = [{"word": s} for s, _r in wordline.parse(ZH_LINE)]
        r = lookup.look_up("zh", "我要一杯茶", pieces=given, authoritative=True)
        self.assertEqual(_said(r), ["我", "要", "一", "杯", "茶"])
        self.assertTrue(all(w["hits"] for w in r["words"]))

    def test_no_pieces_is_no_rows(self):
        self.assertEqual(lookup.look_up("ja", "子供の", pieces=[], authoritative=True)["words"], [])
        self.assertEqual(_said(lookup.look_up("ja", "子供の", pieces=[])), ["子供", "の"])

    def test_no_dictionary_is_still_none(self):
        self.assertIsNone(lookup.look_up("fa", "کتاب"))
        self.assertIsNone(lookup.look_up("fa", "کتاب", pieces=[{"word": "کتاب"}],
                                         authoritative=True))

    def test_without_the_flag_nothing_changes(self):
        for code, text, pieces in (("ja", "おじいさんと", None), ("ja", "住んでいました。", None),
                                   ("ja", "子供と子供", [{"word": "子供"}, {"word": "子供"}]),
                                   ("zh", "我要一杯茶", None)):
            a = lookup.look_up(code, text, pieces=pieces)
            b = lookup.look_up(code, text, pieces=pieces, authoritative=False)
            self.assertEqual(json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False))
            self.assertTrue(all("i" not in w for w in a["words"]))


# serve.py, with lib/lookup.py pointed at the test's dictionaries first: the
# server imports the module this has already imported, and reads DICT_DIR
# from it on every lookup
BOOT = """
import os, runpy, sys
sys.path.insert(0, os.path.join(os.getcwd(), "lib"))
import lookup
lookup.DICT_DIR = sys.argv[1]
sys.argv = ["serve.py", "--http", "--local", sys.argv[2]]
runpy.run_path("serve.py", run_name="__main__")
"""


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _snapshot(d):
    out = []
    for top, dirs, files in os.walk(d):
        for name in sorted(dirs + files):
            p = os.path.join(top, name)
            st = os.stat(p)
            out.append((os.path.relpath(p, d), st.st_size, st.st_mtime_ns))
    return sorted(out)


def _serve_constant(name):
    """A number from serve.py, read from the file rather than by importing
    the server into this process."""
    with open(os.path.join(ROOT, "serve.py"), encoding="utf-8") as f:
        m = re.search(r"^%s = (\d+)" % name, f.read(), re.M)
    return int(m.group(1))


class ServerTests(unittest.TestCase):
    """The book's and the video's doors, through a running serve.py."""

    @classmethod
    def _park(cls, src, dst, ignore=None):
        if os.path.exists(dst):
            raise unittest.SkipTest("%s is on the shelf already" % os.path.relpath(dst, ROOT))
        shutil.copytree(src, dst, ignore=ignore)
        cls.addClassCleanup(shutil.rmtree, dst, True)

    @classmethod
    def setUpClass(cls):
        tag = "wordserver%d" % os.getpid()
        cls.book = os.path.join(ROOT, "books", "japanese", tag)
        cls._park(os.path.join(FIX, "books", "japanese", "mini-ja"), cls.book,
                  shutil.ignore_patterns("reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
        cls.reader = "/books/japanese/%s/reader/" % tag
        cls.vid = tag
        cls.video = os.path.join(ROOT, "youtube", "videos", "chinese", tag)
        cls._park(os.path.join(FIX, "videos", "chinese", "zH8cN2hA6nZ"), cls.video)
        cls.vid_fa = tag + "fa"                 # a language with no words at all
        cls._park(os.path.join(FIX, "videos", "persian", "fA6bK2mQ8sT"),
                  os.path.join(ROOT, "youtube", "videos", "persian", cls.vid_fa))

        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _build(td.name)
        cls.log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
        cls.addClassCleanup(os.unlink, cls.log.name)
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, "-u", "-c", BOOT, td.name, str(cls.port)],
            cwd=ROOT, stdout=cls.log, stderr=subprocess.STDOUT)

        def stop():
            cls.proc.terminate()
            try:
                cls.proc.wait(10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
                cls.proc.wait()
        cls.addClassCleanup(stop)
        deadline = time.time() + 60
        while True:
            if cls.proc.poll() is not None:
                raise RuntimeError("serve.py exited: " + cls._log())
            try:
                c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=2)
                c.request("GET", "/")
                r = c.getresponse()
                r.read()
                c.close()
                if r.status == 200:
                    break
            except OSError:
                pass
            if time.time() > deadline:
                raise RuntimeError("serve.py did not answer: " + cls._log())
            time.sleep(0.25)

    @classmethod
    def _log(cls):
        cls.log.flush()
        with open(cls.log.name, encoding="utf-8", errors="replace") as f:
            return f.read()

    def post(self, path, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        try:
            c.request("POST", path, data, {"Content-Type": "application/json",
                                           "Content-Length": str(len(data))})
            r = c.getresponse()
            return r.status, json.loads(r.read().decode("utf-8"))
        finally:
            c.close()

    # --- the page's own parser, served
    def test_the_wordline_script_is_served(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", "/lib/wordline.js")
        r = c.getresponse()
        body = r.read()
        c.close()
        self.assertEqual(r.status, 200)
        self.assertIn(b"ParsehWordline", body)

    # --- the proposals
    def assertProposal(self, status, j, text, code, door):
        self.assertEqual(status, 200, j)
        self.assertEqual(set(j), {"ok", "words", "available", "python"})
        self.assertIs(j["ok"], True)
        self.assertEqual(os.path.realpath(j["python"]), os.path.realpath(sys.executable))
        if words.available(code):
            self.assertIs(j["available"], True)
            errors, _ = wordline.check(text, j["words"], languages.get(code), door=door)
            self.assertTrue(j["words"])
            self.assertEqual(errors, [], j["words"])
        else:
            self.assertIs(j["available"], False, "no analyzer in %s" % sys.executable)
            self.assertEqual(j["words"], "")

    def test_a_book_proposes_a_line(self):
        text = "むかしむかし、山へ柴刈りに。"
        status, j = self.post(self.reader + "__words/propose", {"text": text})
        self.assertProposal(status, j, text, "ja", wordline.BOOK)
        status, j = self.post(self.reader + "__words/propose", {"text": ""})
        self.assertEqual((status, j["words"]), (200, ""))

    def test_a_video_proposes_a_line(self):
        text = "我要一杯茶"
        status, j = self.post("/youtube/api/words", {"video": self.vid, "text": text})
        self.assertProposal(status, j, text, "zh", wordline.VIDEO)

    def test_the_chunks_reading_reads_the_proposed_words(self):
        text, kana = "私は毎朝コーヒーを飲みます", "わたしはまいあさコーヒーをのみます"
        status, j = self.post(self.reader + "__words/propose", {"text": text, "reading": kana})
        self.assertEqual(status, 200, j)
        if j["available"]:
            self.assertIn("私(わたし)", j["words"])
        else:
            self.assertEqual(j["words"], "")
        longest = _serve_constant("PROPOSE_TEXT")
        for path, extra in ((self.reader + "__words/propose", {}),
                            ("/youtube/api/words", {"video": self.vid})):
            for bad in (5, ["や"], {"r": "や"}, "や" * (8 * longest + 1)):
                status, j = self.post(path, dict(extra, text="山", reading=bad))
                self.assertEqual(status, 400, "%s %r" % (path, bad))
                self.assertIs(j.get("ok"), False)

    def test_a_language_without_words_proposes_none(self):
        # whatever this Python has installed: Persian is not divided into words
        status, j = self.post("/youtube/api/words", {"video": self.vid_fa, "text": "سلام"})
        self.assertEqual(status, 200, j)
        self.assertEqual((j["ok"], j["available"], j["words"]), (True, False, ""))

    def test_a_proposal_refuses_what_is_not_a_chunks_text(self):
        longest = _serve_constant("PROPOSE_TEXT")
        for path, extra in ((self.reader + "__words/propose", {}),
                            ("/youtube/api/words", {"video": self.vid})):
            for bad in ({}, {"text": None}, {"text": 5}, {"text": ["山"]},
                        {"text": "山" * (longest + 1)}):
                status, j = self.post(path, dict(extra, **bad))
                self.assertEqual(status, 400, "%s %r" % (path, bad))
                self.assertIs(j.get("ok"), False)
            status, j = self.post(path, b"[1]")
            self.assertEqual(status, 400)
        for vid in ("noSuchVideoHere", 7, None):
            status, j = self.post("/youtube/api/words", {"video": vid, "text": "茶"})
            self.assertEqual(status, 404, repr(vid))
        status, j = self.post("/books/japanese/%s-none/reader/__words/propose" % self.vid,
                              {"text": "山"})
        self.assertEqual(status, 404)

    def test_a_proposal_writes_nothing(self):
        before = _snapshot(self.book), _snapshot(self.video)
        self.post(self.reader + "__words/propose", {"text": "山へ柴刈りに"})
        self.post("/youtube/api/words", {"video": self.vid, "text": "我要一杯茶"})
        self.assertEqual((_snapshot(self.book), _snapshot(self.video)), before)

    # --- the lookup, divided by the chunk's words, through both doors
    def said(self, path, body):
        status, j = self.post(path, body)
        self.assertEqual(status, 200, j)
        self.assertIs(j.get("available"), True, j)
        return [w["word"] for w in j["words"]], j["words"]

    def test_a_books_lookup_takes_the_chunks_words(self):
        path, text = self.reader + "__lookup", "住んでいました。"
        got, rows = self.said(path, {"text": text})
        self.assertEqual(got, ["住んで", "いました"])
        self.assertTrue(all("i" not in w for w in rows))
        got, rows = self.said(path, {"text": text, "words": "住んでいました(すんでいました) 。"})
        self.assertEqual(got, ["住んでいました"])
        self.assertEqual([w["i"] for w in rows], [0])
        # a line that does not parse is no line, and the text is looked up as today
        for bad in ("住んで(すんで)いました 。", "住んでいました(すんでいました", "", "  ",
                    5, ["住んでいました"]):
            got, rows = self.said(path, {"text": text, "words": bad})
            self.assertEqual(got, ["住んで", "いました"], repr(bad))
            self.assertTrue(all("i" not in w for w in rows))
        # a word written twice is two rows; punctuation is not asked, and `i`
        # is still the word's place in the LINE, so a page needs no filter
        line = "「 子供(こども) 、 と 子供(こども) 」"
        got, rows = self.said(path, {"text": "「子供、と子供」", "words": line})
        self.assertEqual(got, ["子供", "と", "子供"])
        self.assertEqual([w["i"] for w in rows], [1, 3, 4])
        self.assertEqual([wordline.parse(line)[w["i"]][0] for w in rows], got)
        self.assertTrue(rows[2]["hits"])
        # a line of punctuation alone is a line with nothing to look up
        got, rows = self.said(path, {"text": "、。", "words": "、 。"})
        self.assertEqual(got, [])
        # capped where the text is, in characters and not in UTF-16 units: a
        # kanji past U+FFFF is one of them
        cap = _serve_constant("LOOKUP_TEXT")
        got, rows = self.said(path, {"text": "と" * 500, "words": " ".join(["と"] * 500)})
        self.assertEqual(len(got), cap)
        got, rows = self.said(path, {"text": "𠮟" * 500, "words": " ".join(["𠮟"] * 500)})
        self.assertEqual(len(got), cap)
        self.assertEqual(rows[-1]["i"], cap - 1)
        # a line longer than any chunk's is no line either
        got, rows = self.said(path, {"text": "と" * 3, "words": "と " * 20001})
        self.assertEqual(got, ["と"])
        self.assertTrue(all("i" not in w for w in rows))

    def test_a_videos_lookup_takes_the_chunks_words(self):
        body = {"video": self.vid, "text": "我要一杯茶"}
        got, _rows = self.said("/youtube/api/lookup", body)
        self.assertEqual(got, ["我", "要", "一杯", "茶"])
        got, rows = self.said("/youtube/api/lookup", dict(body, words=ZH_LINE))
        self.assertEqual(got, ["我", "要", "一", "杯", "茶"])
        self.assertEqual([w["i"] for w in rows], [0, 1, 2, 3, 4])

    def test_zz_no_traceback_in_the_server_log(self):
        self.assertNotIn("Traceback", self._log())


if __name__ == "__main__":
    unittest.main()
