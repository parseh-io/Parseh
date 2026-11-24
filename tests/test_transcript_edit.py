# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcript, read and written back: what the add page's editor edits.

    python3 -m unittest discover -s tests -p test_transcript_edit.py

Standard library only.  Two halves:

  * the pair of functions themselves (check_annotations.parse_transcript_text
    and transcript_text) -- and above all that they are INVERSES, since the
    editor's whole safety is that a panel it has been through is still a
    panel, read the same way by the prompt, the draft and the checker;
  * the one route the editor has, through a running serve.py.
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _p in (os.path.join(ROOT, "lib"), os.path.join(ROOT, "youtube", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import check_annotations as CA                                # noqa: E402
import draft                                                  # noqa: E402
import languages                                              # noqa: E402
import lookup                                                 # noqa: E402
import tidy                                                   # noqa: E402
import ytpages                                                # noqa: E402

CA_SENT = draft.SENT_END + draft.SENT_END_WIDE + ",،؛;:" 

PANEL = """0:08
Ciao a tutti
0:15
2 minuti e 3 secondi
Oggi andiamo al mercato
Capitolo 2: Al mercato
1:02:03
Va bene, ne prendo tre
"""


class Panel(unittest.TestCase):
    """parse_transcript_text and transcript_text."""

    def caps(self, text, lang="it"):
        return CA.parse_transcript_text(text, lang)

    def test_the_two_are_inverses(self):
        caps = self.caps(PANEL)
        self.assertEqual([c["start"] for c in caps], [8, 15, 3723])
        self.assertEqual(caps[1]["text"], "Oggi andiamo al mercato",
                         "the spoken-duration line under a timestamp is not speech")
        self.assertEqual(caps[2]["chapter"], "Al mercato")
        written = CA.transcript_text(caps)
        self.assertEqual(self.caps(written), caps,
                         "what transcript_text writes, parse_transcript_text reads back")
        self.assertEqual(self.caps(CA.transcript_text(self.caps(written))), caps,
                         "and again, so the editor may be opened twice")

    def test_what_it_writes(self):
        self.assertEqual(CA.transcript_text([{"start": 8, "text": "Ciao", "chapter": None},
                                             {"start": 3723, "text": "A dopo", "chapter": "Fine"}]),
                         "0:08\nCiao\nChapter 1: Fine\n1:02:03\nA dopo\n")
        self.assertEqual(CA.transcript_text([]), "", "nothing written for nothing")

    def test_a_caption_with_no_words_is_no_caption(self):
        text = CA.transcript_text([{"start": 1, "text": "  ", "chapter": None},
                                   {"start": 2, "text": "Ciao", "chapter": None}])
        self.assertEqual(text, "0:02\nCiao\n")

    def test_the_stamps(self):
        self.assertEqual([CA.stamp_of(x) for x in (0, 8, 59, 60, 61, 3599, 3600, 3723)],
                         ["0:00", "0:08", "0:59", "1:00", "1:01", "59:59", "1:00:00", "1:02:03"])
        self.assertEqual(CA.stamp_of(-3), "0:00", "never before the video")

    def test_a_fraction_of_a_second(self):
        """The editor moves a caption by a tenth, so the line carries one --
        and only where there is one, so every panel written before reads and
        writes exactly as it did."""
        for x, said in ((8.4, "0:08.4"), (8.45, "0:08.45"), (8.125, "0:08.125"),
                        (3723.5, "1:02:03.5"), (8.0, "0:08"), (8.9999, "0:09")):
            self.assertEqual(CA.stamp_of(x), said, x)
            self.assertEqual(CA.to_seconds(CA.TIMESTAMP.match(CA.stamp_of(x))),
                             round(x) if x == 8.9999 else x, said)
        # a comma is a keyboard's decimal point, and read as one
        self.assertEqual(CA.to_seconds(CA.TIMESTAMP.match("0:08,4")), 8.4)
        # whole seconds stay int, so nothing that compared them ever sees a float
        self.assertIsInstance(CA.to_seconds(CA.TIMESTAMP.match("0:08")), int)
        for bad in ("0:08.", "0:08.1234", "8", "0:8"):
            self.assertIsNone(CA.TIMESTAMP.match(bad), bad)
        caps = self.caps("0:08.4\nCiao\n0:15\nA dopo\n")
        self.assertEqual([c["start"] for c in caps], [8.4, 15])
        self.assertEqual(CA.transcript_text(caps), "0:08.4\nCiao\n0:15\nA dopo\n")

    def test_a_line_break_inside_a_caption_becomes_one_line(self):
        # the panel puts a long caption on two lines; the editor shows one
        # box, and what it writes back has to read as that one caption
        caps = self.caps("0:05\nOggi andiamo\nal mercato\n")
        self.assertEqual(caps[0]["text"], "Oggi andiamo al mercato")
        self.assertEqual(CA.transcript_text(caps), "0:05\nOggi andiamo al mercato\n")

    def test_plain_is_worked_out_and_never_written(self):
        caps = CA.parse_transcript_text("0:00\nWelcome to the lesson\n0:09\nسلام دوستان\n", "fa")
        self.assertEqual([c["plain"] for c in caps], [True, False])
        written = CA.transcript_text(caps)
        self.assertNotIn("plain", written)
        self.assertEqual(CA.parse_transcript_text(written, "fa"), caps,
                         "a caption is plain because of its letters, not because a file said so")

    def test_a_subtitle_file_comes_in_by_the_same_door(self):
        srt = ("1\n00:00:01,000 --> 00:00:03,500\nHello there\n\n"
               "2\n00:00:04,250 --> 00:00:06,000\nSecond line\n")
        caps = self.caps(ytpages.as_transcript(srt), "en")
        self.assertEqual([(c["start"], c["text"]) for c in caps],
                         [(1, "Hello there"), (4.25, "Second line")],
                         "a cue's own fraction is kept: the line carries one now")
        self.assertEqual(self.caps(CA.transcript_text(caps), "en"), caps)

    def test_the_page_reads_the_panel_with_the_checker(self):
        self.assertEqual(ytpages.parse_transcript_text(PANEL, "it"), self.caps(PANEL))


# A REAL AUTOMATIC TRANSCRIPT, as YouTube gives one: no punctuation, cut
# where it ran out of room, a sentence split across three captions and two
# sentences inside one.  Fifteen captions of a Persian teaching video.
AUTO = """0:02
این
0:04
زال است من سارا هستم زال سارا این
0:13
سامرا
0:18
هستم این سامرا
0:37
این همسر
0:40
سام است همسر
0:48
همسر سام همسر سام
0:52
باردار است
0:56
باردار
0:59
باردار یعنی چه
1:09
او یک دو نه نه نه یک یک
1:15
بچه بچه
1:18
دارد در شکم شکم شکم شکم شکم همسر در سام
1:32
شکم دارد در شکم او یک بچه است اه آیا در
1:44
شکم او غذا است
"""


class Tidy(unittest.TestCase):
    """youtube/lib/tidy.py: an automatic transcript cut into sentences."""

    @classmethod
    def setUpClass(cls):
        if not tidy.can_tidy("fa"):
            raise unittest.SkipTest("no Persian dictionary installed: " + tidy.why_not("fa"))
        cls.verbal = True

    def caps(self, text=AUTO):
        return CA.parse_transcript_text(text, "fa")

    def bag(self, caps):
        """Every word, the punctuation off: what may not change."""
        import re as _re
        off = _re.compile("[%s]+$" % _re.escape(CA_SENT))
        return [off.sub("", w) for c in caps for w in (c["text"] or "").split()
                if off.sub("", w)]

    def test_it_cuts_where_the_verb_is(self):
        caps = self.caps()
        out, notes = tidy.tidy(caps, "fa")
        said = [c["text"] for c in out]
        self.assertIn("این زال است.", said, said)
        self.assertIn("من سارا هستم.", said, said)
        self.assertIn("همسر همسر سام همسر سام باردار است.", said, said)
        self.assertIn("اه آیا در شکم او غذا است؟", said,
                      "a question asked with آیا ends with a question mark")
        self.assertTrue(len(out) > len(caps) / 3, "the captions are not all run together")
        self.assertEqual(notes, ["%d captions became %d" % (len(caps), len(out))])

    def test_not_one_word_changes(self):
        caps = self.caps()
        out, _n = tidy.tidy(caps, "fa")
        self.assertEqual(self.bag(caps), self.bag(out),
                         "the words that come out are the words that went in, in order")

    def test_the_times_rise_and_land_on_a_tenth(self):
        out, _n = tidy.tidy(self.caps(), "fa")
        starts = [c["start"] for c in out]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(set(starts)), len(starts), "no two captions open together")
        for t in starts:
            self.assertEqual(round(t, 1), t, t)
        self.assertGreaterEqual(starts[0], 2, "and none before the first word was spoken")

    def test_a_question_gets_its_own_mark(self):
        out, _n = tidy.tidy(self.caps(), "fa")
        asked = [c["text"] for c in out if c["text"].endswith("؟")]
        self.assertTrue(asked, [c["text"] for c in out])
        self.assertTrue(all(any(w.strip("؟.") in ("آیا", "چه", "چرا", "چیست")
                                for w in t.split()) for t in asked), asked)

    def test_tidying_a_tidy_changes_nothing(self):
        once, _n = tidy.tidy(self.caps(), "fa")
        twice, _n2 = tidy.tidy(once, "fa")
        self.assertEqual([(c["start"], c["text"]) for c in once],
                         [(c["start"], c["text"]) for c in twice])

    def test_a_panel_that_is_already_written_is_left_alone(self):
        caps = CA.parse_transcript_text(
            "0:02\nاین زال است.\n0:06\nمن سارا هستم.\n", "fa")
        out, _n = tidy.tidy(caps, "fa")
        self.assertEqual([c["text"] for c in out], ["این زال است.", "من سارا هستم."])

    def test_a_tag_the_transcript_put_alone_stays_alone(self):
        caps = CA.parse_transcript_text(
            "0:00\n[گریان]\n0:02\nاین زال است\n", "fa")
        out, _n = tidy.tidy(caps, "fa")
        self.assertEqual([c["text"] for c in out], ["[گریان]", "این زال است."],
                         "and no full stop is put after a sound nobody said")

    def test_the_gate_is_the_dictionary_and_nothing_else(self):
        """Every language the toolbox teaches gets this; what decides whether
        the button works is whether its dictionary is installed."""
        for code in languages.CODES:
            self.assertEqual(tidy.can_tidy(code), lookup.available(code), code)
            if not lookup.available(code):
                self.assertIn("dictionary", tidy.why_not(code), code)
                caps = self.caps()
                out, notes = tidy.tidy(caps, code)
                self.assertEqual(out, caps, "the captions come back untouched")
                self.assertIn("dictionary", notes[0])

    def test_a_punctuated_transcript_is_cut_at_its_own_stops(self):
        """What YouTube gives for English, Italian, Japanese and the rest: the
        stops are already there, and they are the first cue -- across the
        caption edges, which is what the transcript itself cannot do."""
        if not tidy.can_tidy("en"):
            self.skipTest("no English dictionary installed")
        caps = CA.parse_transcript_text(
            "0:00\nhello everyone and welcome back. today\n"
            "0:06\nwe are going to the market. what\n"
            "0:11\nshould we buy? some apples maybe.\n", "en")
        out, _n = tidy.tidy(caps, "en")
        self.assertEqual([c["text"] for c in out],
                         ["hello everyone and welcome back.",
                          "today we are going to the market.",
                          "what should we buy?",
                          "some apples maybe."])
        self.assertEqual([c["start"] for c in out], sorted(c["start"] for c in out))

    def test_a_language_written_without_spaces(self):
        """Laid out character by character, as lib/timestamp.py lays out such
        a book: a 。 inside a caption is a cut like any other."""
        if not tidy.can_tidy("ja"):
            self.skipTest("no Japanese dictionary installed")
        caps = CA.parse_transcript_text(
            "0:02\nこんにちは、みなさん。今日は\n0:07\n天気がいいですね。\n", "ja")
        out, _n = tidy.tidy(caps, "ja")
        self.assertEqual([c["text"] for c in out],
                         ["こんにちは、みなさん。", "今日は天気がいいですね。"])


BOOT = """
import os, runpy, sys
# a0.7.0: a server start makes this computer's sync identity and change log beside config/ (lib/synclog.py
# home()); a test's server keeps them in a temporary folder instead, so config/ stays as the run found it
import atexit, shutil, tempfile
sys.path.insert(0, os.path.join(os.getcwd(), "lib"))
import synclog
synclog.HOME = tempfile.mkdtemp(prefix="parseh-test-sync-")
atexit.register(shutil.rmtree, synclog.HOME, True)
sys.argv = ["serve.py", "--http", "--local", sys.argv[1]]
runpy.run_path("serve.py", run_name="__main__")
"""


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Route(unittest.TestCase):
    """POST /youtube/api/transcript, through a running serve.py."""

    @classmethod
    def setUpClass(cls):
        cls.log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
        cls.addClassCleanup(os.unlink, cls.log.name)
        cls.port = _free_port()
        cls.proc = subprocess.Popen([sys.executable, "-u", "-c", BOOT, str(cls.port)],
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

    def post(self, body):
        data = json.dumps(body).encode("utf-8")
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            c.request("POST", "/youtube/api/transcript", data,
                      {"Content-Type": "application/json", "Content-Length": str(len(data))})
            r = c.getresponse()
            return r.status, json.loads(r.read().decode("utf-8"))
        finally:
            c.close()

    def test_a_panel_read_and_written_back(self):
        code, j = self.post({"transcript": PANEL, "lang": "it"})
        self.assertEqual(code, 200)
        self.assertEqual([c["start"] for c in j["captions"]], [8, 15, 3723])
        self.assertEqual(j["lang"], "it")
        self.assertEqual(j["text"], CA.transcript_text(j["captions"]))

    def test_the_captions_being_edited_come_back_as_a_panel(self):
        caps = self.post({"transcript": PANEL, "lang": "it"})[1]["captions"]
        caps[1]["start"] = 17
        caps[1]["text"] = "Oggi andiamo al mercato insieme"
        code, j = self.post({"captions": caps, "lang": "it"})
        self.assertEqual(code, 200)
        self.assertIn("0:17\nOggi andiamo al mercato insieme\n", j["text"])
        self.assertEqual([c["start"] for c in j["captions"]], [8, 17, 3723],
                         "the answer is read back from what was written, not from what was sent")

    def test_the_answer_is_what_the_pipeline_will_see(self):
        # a caption whose text is emptied is no caption, and the count says so
        caps = self.post({"transcript": PANEL, "lang": "it"})[1]["captions"]
        caps[0]["text"] = "   "
        j = self.post({"captions": caps, "lang": "it"})[1]
        self.assertEqual(len(j["captions"]), 2)

    def test_what_it_refuses(self):
        for body, said in (
                ({"transcript": "no stamps here at all", "lang": "it"}, "no captions found"),
                ({"transcript": 7, "lang": "it"}, "transcript must be text"),
                ({"captions": {"a": 1}, "lang": "it"}, "captions must be a list"),
                ({"captions": [{"start": "x", "text": "a"}], "lang": "it"},
                 "start must be a number"),
                ({"captions": [{"start": 1, "text": 7}], "lang": "it"}, "text must be text"),
                ({"captions": [{"start": 1, "text": "a", "chapter": 7}], "lang": "it"},
                 "chapter must be text"),
                ({"transcript": PANEL, "lang": "klingon"}, "klingon")):
            code, j = self.post(body)
            self.assertEqual(code, 400, (body, j))
            self.assertFalse(j["ok"])
            self.assertIn(said, j["error"], (body, j))

    def test_the_tidy_comes_through_the_same_door(self):
        code, j = self.post({"transcript": PANEL, "lang": "it"})
        self.assertEqual(code, 200)
        self.assertEqual(j["can_tidy"], lookup.available("it"),
                         "the dictionary decides, and nothing else")
        self.assertEqual(bool(j["why"]), not j["can_tidy"])
        self.assertEqual(j["notes"], [], "a read is not a tidy")
        code, j2 = self.post({"transcript": PANEL, "lang": "it", "tidy": True})
        self.assertEqual(code, 200)
        self.assertTrue(j2["notes"], "asked for a tidy, it says what it did")
        if not j["can_tidy"]:
            self.assertEqual(j2["text"], j["text"], "and without the dictionary, nothing")
            self.assertIn("dictionary", j2["notes"][0])

    def test_the_tidy_itself(self):
        if not tidy.can_tidy("fa"):
            self.skipTest("no Persian dictionary installed")
        code, j = self.post({"transcript": AUTO, "lang": "fa", "tidy": True})
        self.assertEqual(code, 200)
        self.assertTrue(j["can_tidy"])
        self.assertIn("captions became", j["notes"][0])
        self.assertIn("این زال است.", j["text"])
        self.assertEqual(j["captions"], CA.parse_transcript_text(j["text"], "fa"),
                         "the answer is read back from the panel it wrote")

    def test_the_prompt_for_a_model(self):
        """The other road, and it needs nothing installed: the prompt is text
        about the captions, so every language has it whatever is in dict/."""
        for code in ("fa", "it", "ja"):
            code_, j = self.post({"transcript": AUTO, "lang": code, "prompt": True})
            self.assertEqual(code_, 200, code)
            p = j["prompt"]
            self.assertIn(languages.get(code).name, p)
            self.assertIn("one caption per SENTENCE", p)
            self.assertIn("KEEP THE WORDS", p)
            self.assertIn("0:04\nزال است من سارا هستم زال سارا این", p,
                          "the transcript itself is in the prompt, as it stands")
            self.assertNotIn("captions", j, "a prompt is not a tidy")

    def test_the_answer_comes_back_as_an_ordinary_panel(self):
        """Whatever the model writes goes back through the door the pasted
        panel came in by -- there is no second reader of a transcript."""
        answer = "0:02\nاین زال است.\n0:06.5\nمن سارا هستم.\n"
        code, j = self.post({"transcript": answer, "lang": "fa"})
        self.assertEqual(code, 200)
        self.assertEqual([(c["start"], c["text"]) for c in j["captions"]],
                         [(2, "این زال است."), (6.5, "من سارا هستم.")])

    def test_the_editor_is_served(self):
        for path in ("/youtube/lib/subedit.js", "/youtube/lib/subedit.css",
                     "/youtube/lib/addstt.js", "/youtube/lib/addstt.css"):
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            c.request("GET", path)
            r = c.getresponse()
            body = r.read()
            c.close()
            self.assertEqual(r.status, 200, path)
            self.assertTrue(len(body) > 500, path)

    def test_the_add_page_asks_for_it(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", "/youtube/add/")
        r = c.getresponse()
        page = r.read().decode("utf-8")
        c.close()
        self.assertEqual(r.status, 200)
        for want in ('/youtube/lib/subedit.js', '/youtube/lib/subedit.css', 'id="subedit"'):
            self.assertIn(want, page, want)
        self.assertNotIn("cardkit", page,
                         "the editor records nothing: the card kit is the player's, not this page's")
        # and speech to text, which is optional: its module and its place, and the one
        # recording of a tab's sound that the player's waveform is made from too
        for want in ('/youtube/lib/addstt.js', '/youtube/lib/addstt.css',
                     '/youtube/lib/tabcapture.js', '<div id="stt" class="stt" hidden></div>'):
            self.assertIn(want, page, want)
        self.assertNotIn("/api/transcribe", page, "the page names no endpoint of it: the module does")

    def test_no_traceback(self):
        self.assertNotIn("Traceback", self._log())


if __name__ == "__main__":
    unittest.main()
