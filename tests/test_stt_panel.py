# SPDX-License-Identifier: GPL-3.0-or-later
"""What a transcription becomes on the add page: the panel, the clock, the waveform hold.

    python3 -m unittest tests/test_stt_panel.py

  * youtube/lib/sttpanel.py -- `segments_to_panel` (brief test 16: a mocked
    timed Whisper result becomes a transcript the REAL parser accepts, in all
    eleven languages, with the three traps the real parser sets), `remap`
    (recording time onto the video's clock: a start lag, a stall, jitter,
    hostile marks) and `facts`;
  * youtube/lib/wavefile.py -- the one cleaner (the sentences the waveform
    door has always had), the canonical file, the hold: hold / adopt / drop /
    sweep.

Standard library only.
"""
import json
import math
import os
import random
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _p in (os.path.join(ROOT, "lib"), os.path.join(ROOT, "youtube", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import check_annotations as CA                                # noqa: E402
import languages                                              # noqa: E402
import sttpanel                                               # noqa: E402
import wavefile                                               # noqa: E402
import ytpages                                                # noqa: E402

# two lines of speech in each of the languages Parseh teaches, in its
# own script: Whisper's text is kept exactly as it is given
SPEECH = {
    "fa": ("سلام، ببخشید سیب چند است", "کیلویی سی هزار تومان، تازه آمده"),
    "ar": ("مرحبا بكم في الدرس الأول", "اليوم سنتعلم كلمات جديدة"),
    "it": ("Ciao a tutti", "Oggi andiamo al mercato"),
    "ja": ("こんにちは、みなさん", "今日は天気がいいですね"),
    "fr": ("Bonjour à tous", "Aujourd'hui nous allons au marché"),
    "de": ("Guten Morgen zusammen", "Heute gehen wir auf den Markt"),
    "tr": ("Herkese merhaba", "Bugün pazara gidiyoruz"),
    "en": ("Welcome back", "Today we go to the market"),
    "hi": ("सभी को नमस्ते", "आज हम बाज़ार जा रहे हैं"),
    "es": ("Hola a todos", "Hoy vamos al mercado"),
    "zh": ("大家好，欢迎回来", "今天我们去市场"),
    "ca": ("Bon dia a tothom", "Avui anem al mercat de la plaça"),
}


def segs(*rows):
    return [{"start": a, "end": b, "text": t} for a, b, t in rows]


def read_back(panel, lang):
    return ytpages.parse_transcript_text(ytpages.as_transcript(panel), lang)


class Panel(unittest.TestCase):
    def test_every_language_parseh_ships_is_here(self):
        shipped = [c for c in languages.LANGS if not getattr(languages.LANGS[c], "mine", False)]
        self.assertEqual(sorted(SPEECH), sorted(shipped))

    def test_a_timed_result_becomes_a_transcript_the_real_parser_accepts(self):
        # brief test 16, once for each language Parseh teaches, Whisper's leading
        # space and all
        for code, (a, b) in SPEECH.items():
            with self.subTest(lang=code):
                panel, notes = sttpanel.segments_to_panel(
                    segs((0.0, 2.5, " " + a), (3.24, 6.0, " " + b), (65.4, 70.0, " " + a)))
                self.assertEqual(notes, [])
                caps = read_back(panel, code)
                self.assertEqual([c["text"] for c in caps], [a, b, a])
                self.assertEqual([c["start"] for c in caps], [0, 3.24, 65.4])
                self.assertFalse(any(c["plain"] for c in caps), "the script is the language's")
                # the checker's own writer gives the same panel back: the editor's
                # round trip, so the box a person edits is still a panel
                self.assertEqual(CA.transcript_text(caps), panel)

    def test_it_is_the_checkers_own_format_not_a_subtitle_file(self):
        panel, _ = sttpanel.segments_to_panel(segs((0, 2, " Ciao"), (2.5, 4, " Ciao a tutti")))
        self.assertEqual(panel, "0:00\nCiao\n0:02.5\nCiao a tutti\n")
        self.assertFalse(ytpages.looks_like_subtitles(panel))
        # the very words a .srt would have lost survive
        self.assertEqual([c["text"] for c in read_back(panel, "it")], ["Ciao", "Ciao a tutti"])

    def test_clock_lines_are_the_checkers(self):
        panel, _ = sttpanel.segments_to_panel(segs((0, 1, " a"), (59.999, 61, " b"),
                                                   (3605.25, 3606, " c")))
        self.assertEqual(panel.split("\n")[::2][:3], ["0:00", "0:59.999", "1:00:05.25"])

    def test_words_that_read_as_the_panels_furniture_are_kept_not_eaten(self):
        hazards = ["12:30", "10 minutes", "1 minuto e 6 secondi", "۵ دقیقه",
                   "Chapter 3: fruit", "00:00:01,500 --> 00:00:03,000", "1:02:03"]
        for text in hazards:
            with self.subTest(text=text):
                panel, notes = sttpanel.segments_to_panel(
                    segs((0, 2, " Hello there"), (3, 4, " " + text), (5, 7, " Goodbye")))
                caps = read_back(panel, "en")
                self.assertEqual(len(caps), 2, panel)
                self.assertEqual(caps[0]["text"], "Hello there " + text)
                self.assertEqual(caps[1]["text"], "Goodbye")
                self.assertEqual(len(notes), 1)
                self.assertIn(text, notes[0])
                self.assertFalse(ytpages.looks_like_subtitles(panel))

    def test_such_a_line_first_goes_with_the_caption_after_it(self):
        panel, notes = sttpanel.segments_to_panel(segs((0, 1, " 12:30"), (2, 3, " We meet")))
        caps = read_back(panel, "en")
        self.assertEqual([c["text"] for c in caps], ["12:30 We meet"])
        self.assertIn("after it", notes[0])

    def test_such_a_line_with_nothing_to_join_is_said_to_be_left_out(self):
        panel, notes = sttpanel.segments_to_panel(segs((0, 1, " 12:30")))
        self.assertEqual(panel, "")
        self.assertIn("left out", notes[0])

    def test_two_captions_never_start_together(self):
        # the editor refuses an equal start, the checker allows it
        panel, _ = sttpanel.segments_to_panel(segs((5, 6, " a"), (5, 7, " b"), (5.0004, 8, " c")))
        starts = [c["start"] for c in read_back(panel, "en")]
        self.assertEqual(starts, [5, 5.001, 5.002])
        self.assertTrue(all(b > a for a, b in zip(starts, starts[1:])))

    def test_empty_segments_and_odd_whitespace(self):
        panel, notes = sttpanel.segments_to_panel(
            segs((0, 1, "  "), (1, 2, ""), (2, 3, " one\n two\t three ")) + [None, "x", {}])
        self.assertEqual(panel, "0:02\none two three\n")
        self.assertEqual(notes, [])
        self.assertEqual(sttpanel.segments_to_panel(None), ("", []))
        self.assertEqual(sttpanel.segments_to_panel([]), ("", []))

    def test_a_start_that_is_not_a_number_is_not_fabricated(self):
        panel, _ = sttpanel.segments_to_panel(
            [{"start": "x", "end": 1, "text": " a"}, {"start": float("nan"), "text": " b"},
             {"start": -3, "text": " c"}])
        self.assertEqual([c["start"] for c in read_back(panel, "en")], [0, 0.001, 0.002])

    def test_the_facts_are_the_ones_prepare_gives(self):
        panel, _ = sttpanel.segments_to_panel(
            segs((0, 1, " سلام"), (61, 62, " hello"), (3725, 3730, " خداحافظ")))
        f = sttpanel.facts(panel, "fa")
        self.assertEqual((f["captions"], f["want"], f["plain"], f["duration"]), (3, 2, 1, "62:05"))
        self.assertEqual(sttpanel.facts("", "fa")["captions"], 0)


# --------------------------------------------------------------------- the clock
def _video_clock(lag0, stall_at, stall_len):
    def video_of(rec):
        if rec < lag0:
            return 0.0
        if rec < stall_at:
            return rec - lag0
        if rec < stall_at + stall_len:
            return stall_at - lag0
        return rec - lag0 - stall_len
    return video_of


def _marks(video_of, stall_at, stall_len, seconds=40, jitter=0.1, every=0.25, seed=7):
    """What the browser would send: a mark a quarter second while the video
    plays and none while it stands still, each reading a tenth of a second off."""
    rnd = random.Random(seed)
    out, t = [], 0.0
    while t < seconds:
        if not (stall_at <= t < stall_at + stall_len) and video_of(t) > 0:
            out.append([int(t * 16000), max(0.0, video_of(t) + rnd.uniform(-jitter, jitter))])
        t += every
    return out


class Remap(unittest.TestCase):
    LAG, AT, LEN = 0.4, 10.0, 2.0

    def spoken(self, video_seconds):
        """The segment a speaker at video time `v` makes in the RECORDING."""
        rec = video_seconds + self.LAG + (self.LEN if video_seconds >= self.AT - self.LAG else 0)
        return {"start": rec, "end": rec + 1.0, "text": " v%.1f" % video_seconds}

    def test_a_start_lag_a_stall_and_jitter_are_all_taken_out(self):
        video_of = _video_clock(self.LAG, self.AT, self.LEN)
        marks = _marks(video_of, self.AT, self.LEN)
        want = (0.5, 5.0, 9.0, 10.5, 15.0, 25.0, 35.0)
        got = sttpanel.remap([self.spoken(v) for v in want], marks)
        self.assertEqual(len(got), len(want))
        for v, s in zip(want, got):
            self.assertAlmostEqual(s["start"], v, delta=0.15, msg="the caption at video %.1f" % v)
        # a stall must not shift what comes after it: the last is as good as the first
        self.assertLess(abs(got[-1]["start"] - 35.0), 0.15)

    def test_what_was_heard_inside_a_stall_was_never_said(self):
        video_of = _video_clock(self.LAG, self.AT, self.LEN)
        marks = _marks(video_of, self.AT, self.LEN)
        ghost = {"start": self.AT + 0.3, "end": self.AT + 1.7, "text": " ghost"}
        got = sttpanel.remap([self.spoken(5.0), ghost, self.spoken(15.0)], marks)
        self.assertEqual([s["text"] for s in got], [" v5.0", " v15.0"])

    def test_starts_never_go_backwards(self):
        marks = _marks(_video_clock(0.4, 10, 2), 10, 2, jitter=0.12)
        rows = [{"start": 1 + i * 0.01, "end": 1.2 + i * 0.01, "text": " w%d" % i}
                for i in range(50)]
        got = sttpanel.remap(rows, marks)
        starts = [s["start"] for s in got]
        self.assertEqual(starts, sorted(starts))
        self.assertTrue(all(s["end"] >= s["start"] for s in got))

    def test_without_marks_the_segments_come_back_as_they_are(self):
        rows = segs((1, 2, " a"), (3, 4, " b"))
        for marks in (None, [], "x", 5, {}):
            self.assertEqual(sttpanel.remap(rows, marks), rows)
        self.assertIsNot(sttpanel.remap(rows, None)[0], rows[0], "a copy: the caller's are kept")

    def test_a_single_mark_gives_a_constant_lag(self):
        got = sttpanel.remap(segs((2.4, 3, " a")), [[int(0.5 * 16000), 0.1]])
        self.assertAlmostEqual(got[0]["start"], 2.0, places=3)

    def test_marks_are_not_believed_blindly(self):
        good = [[16000 * k, k - 0.4] for k in range(1, 20)]
        hostile = [None, "x", 5, [1], [1, 2, 3], ["a", 2], [1, "b"], [True, 1], [1, False],
                   [float("nan"), 1], [1, float("inf")], [-5, 1], [16000, -1],
                   [16000, 10 ** 9], {"a": 1}, [[1, 2]], [16000 * 3, 2.6],
                   [10 ** 400, 1], [1, 10 ** 400]]        # what no float can hold
        rows = segs((5, 6, " a"))
        clean = sttpanel.remap(rows, good)
        self.assertEqual(sttpanel.remap(rows, good + hostile), clean)
        # a frame that does not move forward is dropped, not trusted
        self.assertEqual(sttpanel.clean_marks([[100, 1], [100, 2], [50, 3], [200, 4]]),
                         [[100, 1.0], [200, 4.0]])
        self.assertEqual(sttpanel.clean_marks("nope"), [])

    def test_a_huge_list_of_marks_is_capped_and_still_quick(self):
        marks = [[i * 4000, 1.0] for i in range(sttpanel.MAX_MARKS + 5000)]
        began = time.time()
        got = sttpanel.clean_marks(marks)
        self.assertEqual(len(got), sttpanel.MAX_MARKS)
        self.assertLess(time.time() - began, 5)

    def test_marks_of_an_hour_are_remapped_in_a_moment(self):
        marks = [[int(i * 0.25 * 16000), i * 0.25 - 0.4] for i in range(2, 14400)]
        rows = [{"start": i * 2.0, "end": i * 2.0 + 1.5, "text": " x"} for i in range(1800)]
        began = time.time()
        got = sttpanel.remap(rows, marks)
        self.assertLess(time.time() - began, 5)
        self.assertAlmostEqual(got[900]["start"], 1800 - 0.4, delta=0.01)


# -------------------------------------------------------------------- waveform
class Wave(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.videos = os.path.join(self.td.name, "videos")
        os.makedirs(self.videos)
        self.token = "A" * 16

    def test_the_cleaner_says_what_the_waveform_door_always_said(self):
        for rate, peaks, said in [
                (20, None, "no waveform was sent"), (20, [], "no waveform was sent"),
                (20, "x", "no waveform was sent"), (20, {"a": 1}, "no waveform was sent"),
                (20, [0] * 2000001, "that waveform is too fine to keep"),
                (None, [0.1], "a waveform says how many numbers a second it has"),
                ("fast", [0.1], "a waveform says how many numbers a second it has"),
                ([1], [0.1], "a waveform says how many numbers a second it has"),
                (0.5, [0.1], "a waveform carries between 1 and 200 numbers a second"),
                (201, [0.1], "a waveform carries between 1 and 200 numbers a second"),
                (float("nan"), [0.1], "a waveform carries between 1 and 200 numbers a second")]:
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError) as cm:
                    wavefile.clean(rate, peaks)
                self.assertEqual(str(cm.exception), said)

    def test_the_cleaner_clamps_rounds_and_zeroes_what_is_not_a_number(self):
        rate, out = wavefile.clean("20", [0.12345, 5, -1, "x", None, True, 0.5, float("nan")])
        self.assertEqual((rate, out), (20.0, [0.123, 1.0, 0.0, 0.0, 0.0, 1.0, 0.5, 0.0]))
        self.assertIsInstance(rate, float)

    def test_the_file_has_the_canonical_shape(self):
        d = os.path.join(self.td.name, "vid")
        os.makedirs(d)
        rate, peaks = wavefile.clean(20, [0, 0.5, 1])
        wavefile.write(d, rate, peaks)
        with open(os.path.join(d, "waveform.json"), encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"rate": 20.0, "peaks": [0.0, 0.5, 1.0]}')
        self.assertEqual(wavefile.read(os.path.join(d, "waveform.json")), (20.0, [0.0, 0.5, 1.0]))
        self.assertFalse(os.path.exists(os.path.join(d, "waveform.json.tmp")))

    def test_read_gives_none_for_what_is_not_a_waveform(self):
        for text in ("", "not json", "[1]", '{"rate": 20}', '{"rate": 0, "peaks": [1]}',
                     '{"rate": 20, "peaks": []}', "[" * 100000):
            p = os.path.join(self.td.name, "w.json")
            with open(p, "w") as f:
                f.write(text)
            self.assertIsNone(wavefile.read(p), text[:20])
        self.assertIsNone(wavefile.read(os.path.join(self.td.name, "missing.json")))

    def test_a_held_waveform_is_adopted_by_the_video_made_from_it(self):
        n = wavefile.hold(self.token, 20, [0, 0.25, 1], videos=self.videos)
        self.assertEqual(n, 3)
        held = os.path.join(self.videos, ".waveforms", self.token + ".json")
        self.assertTrue(os.path.isfile(held))
        self.assertTrue(wavefile.held(self.token, videos=self.videos))
        video = os.path.join(self.videos, "persian", "abc-123456")
        os.makedirs(video)
        got = wavefile.adopt(self.token, video, videos=self.videos)
        self.assertEqual(got, {"kept": True, "buckets": 3})
        with open(os.path.join(video, "waveform.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"rate": 20.0, "peaks": [0.0, 0.25, 1.0]})
        self.assertFalse(os.path.exists(held), "adopted: no longer held")
        self.assertIsNone(wavefile.adopt(self.token, video, videos=self.videos),
                          "there is nothing left to adopt")

    def test_nothing_to_adopt_is_none_and_never_an_error(self):
        video = os.path.join(self.videos, "x")
        os.makedirs(video)
        for token in (None, "", 5, [], "short", "../../etc/passwd", "A" * 15, "A" * 17,
                      "A" * 15 + "/", "A" * 15 + "\0", "unknown-token-abc"):
            self.assertIsNone(wavefile.adopt(token, video, videos=self.videos), token)
        self.assertEqual(os.listdir(video), [])

    def test_a_hold_that_is_not_a_waveform_is_dropped_not_adopted(self):
        os.makedirs(wavefile.hold_dir(self.videos))
        with open(wavefile.hold_path(self.token, self.videos), "w") as f:
            f.write('{"rate": 20, "peaks": "loud"}')
        video = os.path.join(self.videos, "x")
        os.makedirs(video)
        self.assertIsNone(wavefile.adopt(self.token, video, videos=self.videos))
        self.assertFalse(wavefile.held(self.token, videos=self.videos))
        self.assertEqual(os.listdir(video), [])

    def test_the_hold_stays_when_the_video_cannot_take_it(self):
        wavefile.hold(self.token, 20, [0.5], videos=self.videos)
        self.assertIsNone(wavefile.adopt(self.token, os.path.join(self.videos, "nowhere"),
                                         videos=self.videos))
        self.assertTrue(wavefile.held(self.token, videos=self.videos))

    def test_a_token_that_would_be_a_path_is_refused_to_hold(self):
        for token in ("../../../../tmp/x", "/etc/passwd", "a" * 16 + "\0", "A" * 200, None, 7, ""):
            with self.assertRaises(ValueError):
                wavefile.hold(token, 20, [0.5], videos=self.videos)
            self.assertIsNone(wavefile.hold_path(token, self.videos))
        self.assertFalse(os.path.exists(wavefile.hold_dir(self.videos)), "not even the folder")

    def test_a_hold_is_dropped_and_dropping_twice_is_fine(self):
        wavefile.hold(self.token, 20, [0.5], videos=self.videos)
        self.assertTrue(wavefile.drop(self.token, self.videos))
        self.assertFalse(wavefile.drop(self.token, self.videos))
        self.assertFalse(wavefile.drop("../x", self.videos))

    def test_the_sweep_lets_go_of_old_holds_and_half_files_only(self):
        wavefile.hold(self.token, 20, [0.5], videos=self.videos)
        wavefile.hold("B" * 16, 20, [0.5], videos=self.videos)
        old = wavefile.hold_path("B" * 16, self.videos)
        then = time.time() - 31 * 86400
        os.utime(old, (then, then))
        half = os.path.join(wavefile.hold_dir(self.videos), "C" * 16 + ".json.tmp")
        open(half, "w").close()
        self.assertEqual(wavefile.sweep(videos=self.videos), 2)
        self.assertEqual(sorted(os.listdir(wavefile.hold_dir(self.videos))), [self.token + ".json"])
        self.assertEqual(wavefile.sweep(videos="/no/such/place"), 0)

    def test_the_hold_follows_ytpages_videos_at_the_moment_of_asking(self):
        before = ytpages.VIDEOS
        try:
            ytpages.VIDEOS = self.videos
            self.assertEqual(wavefile.hold_dir(), os.path.join(self.videos, ".waveforms"))
        finally:
            ytpages.VIDEOS = before

    def test_a_dot_directory_is_never_a_video(self):
        before = ytpages.VIDEOS
        try:
            ytpages.VIDEOS = self.videos
            wavefile.hold(self.token, 20, [0.5])
            self.assertEqual(list(ytpages.video_dirs()), [])
        finally:
            ytpages.VIDEOS = before


if __name__ == "__main__":
    unittest.main()
