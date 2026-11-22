#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Moving text from one line of an added video to the line before or after it.

    python3 -m unittest discover -s tests -p test_video_reflow.py

youtube/lib/reflow.py argues that moving a BOUNDARY between two captions, in
annotations.json and transcript.txt together, leaves every rule the checker
keeps exactly as true as before: the same number of captions, the same words
in the same order, the starts of the two files within the same tolerance.  That
argument is worth what its tests are worth, so:

  a) THE TWO FILES MOVE TOGETHER and the checker still ends with no error --
     for a whole phrase moved either way, and for a boundary that falls inside
     a phrase (which cuts it first, at a space).
  b) NO WORD IS WRITTEN OR LOST: the words of the whole transcript, read from
     top to bottom, are the same after as before.
  c) WHAT IT REFUSES it refuses whole -- the files are byte for byte what they
     were -- and says why in a sentence: the last line, the first line, a plain
     line, a chapter's start, a page that is out of date, nothing to move.
  d) THE START that moved is worked out from the text, lies between its
     neighbours, and drags with it everything that names a caption by its
     start: the notes anchored to it and a legacy video's batches.
  e) IT CAN BE TAKEN BACK, exactly, and only while nothing was written since.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for folder in ("youtube/lib", "lib", "markdown/app"):
    sys.path.insert(0, os.path.join(REPO, folder))

import check_annotations as CA                     # noqa: E402
import reflow                                      # noqa: E402


def chunk(fa, tr="x", en="y"):
    return {"fa": fa, "tr": tr, "en": en}


# four lines: the first two end in the middle of a sentence, the way a
# transcript YouTube cut at its own pace does
LINES = [
    (0, "سلام و درود به همه. چقدر دلم برای این لحظه",
     ["سلام و درود", "به همه.", "چقدر دلم", "برای این لحظه"]),
    (10, "برای صحبت کردن با شما. امیدوارم حال دلتون",
     ["برای صحبت کردن", "با شما.", "امیدوارم", "حال دلتون"]),
    (20, "خوب باشه و روزگار بر وفق مرادتون بگرده.",
     ["خوب باشه", "و روزگار", "بر وفق مرادتون بگرده."]),
    (30, "بعد از آن می‌گویم",
     ["بعد از آن", "می‌گویم"]),
]


def build(into, lines=LINES, extra_head=None, chapter_at=None, language="fa"):
    os.makedirs(into)
    segs, rows = [], []
    for k, (start, text, chunks) in enumerate(lines):
        seg = {"start": start, "text": text,
               "chunks": [chunk(c, tr="t%d" % i, en="e%d" % i) for i, c in enumerate(chunks)]}
        if chapter_at == k:
            seg["chapter"] = "فصل ۲"
            rows.append("Chapter 1: فصل ۲")
        segs.append(seg)
        rows.append(CA.stamp_of(start))
        rows.append(text)
    with io.open(os.path.join(into, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump({"video": "fixture", "language": language, "segments": segs},
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    with io.open(os.path.join(into, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    with io.open(os.path.join(into, "video.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "fixture", "title": "t", "channel": "c", "language": language,
                   "level": "beginner", "duration": "0:40"}, f)
    return into


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="parseh-reflow-")
        self.d = build(os.path.join(self.tmp, "fixture"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, name):
        with io.open(os.path.join(self.d, name), encoding="utf-8") as f:
            return f.read()

    def ann(self):
        return json.loads(self.read("annotations.json"))["segments"]

    def caps(self):
        return CA.parse_transcript_text(self.read("transcript.txt"), "fa")

    def files(self):
        return (self.read("annotations.json"), self.read("transcript.txt"))

    def words(self):
        return " ".join(c["text"] for c in self.caps()).split()

    def clean(self):
        errors, _w, _n = CA.check(self.d)
        self.assertEqual(errors, [], "the checker is happy")


class MovingAWholePhrase(Base):
    def test_the_fixture_starts_clean(self):
        self.clean()

    def test_the_end_of_a_line_goes_to_the_front_of_the_next(self):
        words = self.words()
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["moved"]["text"], "چقدر دلم برای این لحظه")
        self.assertEqual(out["moved"]["direction"], "next")
        a = self.ann()
        self.assertEqual(a[0]["text"], "سلام و درود به همه.")
        self.assertEqual([c["fa"] for c in a[0]["chunks"]], ["سلام و درود", "به همه."])
        self.assertEqual(a[1]["text"], "چقدر دلم برای این لحظه برای صحبت کردن با شما. امیدوارم حال دلتون")
        self.assertEqual([c["fa"] for c in a[1]["chunks"]][:3],
                         ["چقدر دلم", "برای این لحظه", "برای صحبت کردن"])
        self.assertEqual([c["text"] for c in self.caps()][:2], [a[0]["text"], a[1]["text"]],
                         "transcript.txt says the same")
        self.assertEqual(self.words(), words, "no word written, none lost")
        self.clean()

    def test_the_glosses_go_with_their_phrases(self):
        before = {c["fa"]: c for s in self.ann() for c in s["chunks"]}
        reflow.move(self.d, 0, "end", 1)
        for s in self.ann():
            for c in s["chunks"]:
                self.assertEqual(c, before[c["fa"]], "a phrase moves as it is")

    def test_the_start_of_the_next_line_is_worked_out_from_the_text(self):
        out = reflow.move(self.d, 0, "end", 1)
        now = out["start"]["now"]
        self.assertEqual(out["start"]["i"], 1)
        self.assertEqual(out["start"]["was"], 10)
        self.assertTrue(0 < now < 10, "inside the line the words came out of: %s" % now)
        self.assertTrue(out["estimated"])
        self.assertEqual(now, round(now, 1), "to a tenth, as the transcript writes it")
        self.assertEqual([c["start"] for c in self.caps()], [s["start"] for s in self.ann()])
        self.assertEqual(self.ann()[1]["start"], now)
        self.assertEqual(self.ann()[0]["start"], 0)

    def test_the_start_follows_the_share_of_the_words_that_moved(self):
        short = reflow.move(self.d, 0, "end", 2)["start"]["now"]
        shutil.rmtree(self.d)
        build(self.d)
        long_ = reflow.move(self.d, 0, "end", 1)["start"]["now"]
        self.assertGreater(short, long_, "more words moved out of the line, an earlier start")

    def test_the_start_of_a_line_goes_to_the_end_of_the_one_before(self):
        words = self.words()
        out = reflow.move(self.d, 1, "start", 2)       # the line begins at «امیدوارم»
        self.assertEqual(out["moved"]["text"], "برای صحبت کردن با شما.")
        self.assertEqual(out["moved"]["direction"], "previous")
        a = self.ann()
        self.assertEqual(a[0]["text"],
                         "سلام و درود به همه. چقدر دلم برای این لحظه برای صحبت کردن با شما.")
        self.assertEqual(a[1]["text"], "امیدوارم حال دلتون")
        self.assertEqual([c["fa"] for c in a[1]["chunks"]], ["امیدوارم", "حال دلتون"])
        self.assertEqual(self.words(), words)
        self.assertTrue(10 < a[1]["start"] < 20, a[1]["start"])
        self.assertEqual(a[0]["start"], 0)
        self.clean()

    def test_a_line_may_be_left_with_one_phrase(self):
        reflow.move(self.d, 1, "start", 3)
        self.assertEqual([c["fa"] for c in self.ann()[1]["chunks"]], ["حال دلتون"])
        self.clean()

    def test_the_last_line_takes_from_the_one_before_by_the_pace_of_the_rest(self):
        out = reflow.move(self.d, 3, "start", 1)
        self.assertEqual(out["moved"]["text"], "بعد از آن")
        self.assertGreater(out["start"]["now"], 30, "later than it was: its head moved up")
        self.clean()

    def test_a_line_moves_and_the_next_one_is_not_touched(self):
        was = self.ann()
        reflow.move(self.d, 0, "end", 1)
        self.assertEqual(self.ann()[2:], was[2:])


class CuttingAPhrase(Base):
    def test_a_line_may_end_inside_a_phrase(self):
        words = self.words()
        out = reflow.move(self.d, 0, "end", 0, word=0)  # ends after «سلام»
        self.assertTrue(out["moved"]["cut"])
        a = self.ann()
        self.assertEqual(a[0]["text"], "سلام")
        self.assertEqual([c["fa"] for c in a[0]["chunks"]], ["سلام"])
        self.assertEqual([c["fa"] for c in a[1]["chunks"]][:2], ["و درود", "به همه."][:2])
        self.assertEqual(self.words(), words)
        self.clean()

    def test_a_line_may_begin_inside_a_phrase(self):
        reflow.move(self.d, 1, "start", 0, word=2)      # begins at «کردن»
        a = self.ann()
        self.assertEqual(a[1]["text"], "کردن با شما. امیدوارم حال دلتون")
        self.assertEqual(a[0]["text"].split()[-2:], ["برای", "صحبت"])
        self.assertEqual([c["fa"] for c in a[1]["chunks"]][0], "کردن")
        self.clean()

    def test_the_second_half_is_left_with_its_meaning_to_write(self):
        reflow.move(self.d, 0, "end", 0, word=0)
        second = self.ann()[1]["chunks"][0]
        self.assertEqual(second["fa"], "و درود")
        self.assertNotIn("en", second, "all of the meaning went to the first half")

    def test_a_word_that_is_the_edge_of_the_phrase_cuts_nothing(self):
        out = reflow.move(self.d, 0, "end", 1, word=1)   # the last word of «به همه.»
        self.assertFalse(out["moved"]["cut"])
        out = reflow.move(self.d, 1, "start", 2, word=0)
        self.assertFalse(out["moved"]["cut"])

    def test_a_word_that_is_not_in_the_phrase(self):
        with self.assertRaises(ValueError) as e:
            reflow.move(self.d, 0, "end", 0, word=9)
        self.assertIn("no word", str(e.exception))


class Refusing(Base):
    def refused(self, *args, **kw):
        was = self.files()
        with self.assertRaises(ValueError) as e:
            reflow.move(self.d, *args, **kw)
        self.assertEqual(self.files(), was, "and nothing was written")
        return str(e.exception)

    def test_the_last_line_has_no_line_after_it(self):
        self.assertIn("last line", self.refused(3, "end", 0))

    def test_the_first_line_has_no_line_before_it(self):
        self.assertIn("first line", self.refused(0, "start", 1))

    def test_a_line_that_already_ends_there(self):
        self.assertIn("already ends there", self.refused(0, "end", 3))

    def test_a_line_that_already_begins_there(self):
        self.assertIn("already begins there", self.refused(1, "start", 0))

    def test_a_caption_or_a_phrase_that_is_not_there(self):
        self.refused(9, "end", 0)
        self.refused(0, "end", 9)
        self.refused(0, "sideways", 0)

    def test_a_page_that_is_out_of_date_is_refused_by_name(self):
        was = self.files()
        with self.assertRaises(reflow.Stale):
            reflow.move(self.d, 0, "end", 1, expect={"text": "something else"})
        with self.assertRaises(reflow.Stale):
            reflow.move(self.d, 0, "end", 1, expect={"chunk": "something else"})
        self.assertEqual(self.files(), was)
        reflow.move(self.d, 0, "end", 1, expect={"text": LINES[0][1], "chunk": "به همه."})

    def test_a_plain_line_takes_no_part(self):
        shutil.rmtree(self.d)
        build(self.d, lines=[(0, "Welcome back to the channel", []),
                             (6, "سلام ببخشید", ["سلام", "ببخشید"]),
                             (12, "سیب چند است", ["سیب", "چند است"])])
        for seg in self.ann():
            if seg["start"] == 0:
                seg.pop("chunks")
        with io.open(os.path.join(self.d, "annotations.json"), encoding="utf-8") as f:
            ann = json.load(f)
        ann["segments"][0].pop("chunks", None)
        ann["segments"][0]["plain"] = True
        with io.open(os.path.join(self.d, "annotations.json"), "w", encoding="utf-8") as f:
            json.dump(ann, f, ensure_ascii=False, indent=1)
        self.assertIn("plain", self.refused(1, "start", 1))

    def test_words_do_not_cross_the_start_of_a_chapter(self):
        shutil.rmtree(self.d)
        build(self.d, chapter_at=2)
        msg = self.refused(1, "end", 1)
        self.assertIn("chapter", msg)
        self.assertIn("فصل ۲", msg)
        self.refused(2, "start", 1)
        reflow.move(self.d, 2, "end", 0)                  # inside the chapter is fine

    def test_a_transcript_that_does_not_agree_is_refused(self):
        with io.open(os.path.join(self.d, "transcript.txt"), "a", encoding="utf-8") as f:
            f.write("0:40\nیک جمله دیگر\n")
        self.assertIn("transcript.txt carries", self.refused(0, "end", 1))

    def test_a_caption_whose_phrases_do_not_add_up_to_its_text(self):
        ann = json.loads(self.read("annotations.json"))
        ann["segments"][1]["chunks"][0]["fa"] = "برای"
        with io.open(os.path.join(self.d, "annotations.json"), "w", encoding="utf-8") as f:
            json.dump(ann, f, ensure_ascii=False, indent=1)
        self.refused(1, "start", 2)

    def test_a_move_that_would_leave_the_second_line_not_in_the_language(self):
        """The transcript calls a line with no letter of the script plain; a
        glossed line left with only English would then disagree with it, and
        the checker says so -- in its own words, and nothing is written."""
        shutil.rmtree(self.d)
        build(self.d, lines=[(0, "Hello سلام", ["Hello", "سلام"]),
                             (10, "ببخشید سیب", ["ببخشید", "سیب"])])
        msg = self.refused(0, "end", 0)
        self.assertIn("break the video", msg)


class Following(Base):
    def setUp(self):
        Base.setUp(self)
        note = os.path.join(self.d, "markdown", "persian", "a-note")
        os.makedirs(note)
        self.note = os.path.join(note, "source.md")
        with io.open(self.note, "w", encoding="utf-8") as f:
            f.write("---\ntitle: About this bit\nanchor: after cap 10\n---\n\nSomething.\n")

    def test_a_note_follows_the_caption_that_started_elsewhere(self):
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["notes"], 1)
        now = self.ann()[1]["start"]
        with io.open(self.note, encoding="utf-8") as f:
            self.assertIn("anchor: after cap %s" % (int(now) if now == int(now) else now),
                          f.read())

    def test_a_note_anchored_elsewhere_stays(self):
        with io.open(self.note, "w", encoding="utf-8") as f:
            f.write("---\ntitle: x\nanchor: after cap 20\n---\n\nSomething.\n")
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["notes"], 0)

    def test_the_batches_of_a_legacy_video_have_their_starts_kept(self):
        parts = os.path.join(self.d, "parts")
        os.makedirs(parts)
        batch = [{"start": s["start"], "chunks": s["chunks"]} for s in self.ann()]
        with io.open(os.path.join(parts, "01.json"), "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=1)
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["parts"], 1)
        with io.open(os.path.join(parts, "01.json"), encoding="utf-8") as f:
            got = json.load(f)
        self.assertEqual([b["start"] for b in got], [s["start"] for s in self.ann()])


class TakingItBack(Base):
    def test_a_move_is_undone_exactly(self):
        was = self.files()
        out = reflow.move(self.d, 0, "end", 0, word=0)
        self.assertNotEqual(self.files(), was)
        back = reflow.restore(self.d, out["pair"], out["segments"], out["before"])
        self.assertEqual(self.files(), was, "byte for byte what it was")
        self.assertEqual(back["segments"], out["before"])
        self.clean()

    def test_and_done_again(self):
        out = reflow.move(self.d, 1, "start", 2)
        after = self.files()
        reflow.restore(self.d, out["pair"], out["segments"], out["before"])
        again = reflow.move(self.d, 1, "start", 2)
        self.assertEqual(self.files(), after)
        self.assertEqual(again["start"]["now"], out["start"]["now"])

    def test_a_pair_written_since_is_refused(self):
        out = reflow.move(self.d, 0, "end", 1)
        reflow.move(self.d, 1, "end", 2)                  # touches the same second line
        was = self.files()
        with self.assertRaises(reflow.Stale):
            reflow.restore(self.d, out["pair"], out["segments"], out["before"])
        self.assertEqual(self.files(), was)

    def test_it_is_not_a_door_to_anything_else(self):
        out = reflow.move(self.d, 0, "end", 1)
        bad = [dict(out["before"][0], plain=True), out["before"][1]]
        was = self.files()
        with self.assertRaises(ValueError):
            reflow.restore(self.d, out["pair"], out["segments"], bad)
        with self.assertRaises(ValueError):
            reflow.restore(self.d, out["pair"], out["segments"], "no")
        self.assertEqual(self.files(), was)

    def test_a_state_the_checker_would_refuse_is_refused(self):
        out = reflow.move(self.d, 0, "end", 1)
        bad = [dict(out["before"][0], text="something else entirely"), out["before"][1]]
        was = self.files()
        with self.assertRaises(ValueError) as e:
            reflow.restore(self.d, out["pair"], out["segments"], bad)
        self.assertIn("break the video", str(e.exception))
        self.assertEqual(self.files(), was)


class AFilmOfItsOwn(unittest.TestCase):
    """Japanese writes no spaces: a phrase is the smallest piece that moves."""

    def test_whole_phrases_only(self):
        tmp = tempfile.mkdtemp(prefix="parseh-reflow-ja-")
        try:
            d = os.path.join(tmp, "fixture")
            os.makedirs(d)
            segs = [{"start": 0, "text": "今日は天気がいいですね。明日は",
                     "chunks": [{"fa": "今日は天気がいいですね。", "kana": "きょうはてんきがいいですね。", "tr": "kyō wa", "en": "today"},
                                {"fa": "明日は", "kana": "あしたは", "tr": "ashita wa", "en": "tomorrow"}]},
                    {"start": 8, "text": "雨でしょう。",
                     "chunks": [{"fa": "雨でしょう。", "kana": "あめでしょう。", "tr": "ame deshō", "en": "rain"}]}]
            with io.open(os.path.join(d, "annotations.json"), "w", encoding="utf-8") as f:
                json.dump({"video": "x", "language": "ja", "segments": segs}, f,
                          ensure_ascii=False, indent=1)
            with io.open(os.path.join(d, "transcript.txt"), "w", encoding="utf-8") as f:
                f.write("0:00\n今日は天気がいいですね。明日は\n0:08\n雨でしょう。\n")
            with io.open(os.path.join(d, "video.json"), "w", encoding="utf-8") as f:
                json.dump({"id": "x", "title": "t", "channel": "c", "language": "ja",
                           "level": "beginner"}, f)
            with self.assertRaises(ValueError) as e:
                reflow.move(d, 0, "end", 0, word=2)
            self.assertIn("without spaces", str(e.exception))
            reflow.move(d, 0, "end", 0)
            with io.open(os.path.join(d, "annotations.json"), encoding="utf-8") as f:
                a = json.load(f)["segments"]
            self.assertEqual(a[0]["text"], "今日は天気がいいですね。")
            self.assertEqual(a[1]["text"], "明日は雨でしょう。")
            errors, _w, _n = CA.check(d)
            self.assertEqual(errors, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# The times each word of LINES was heard, the way the speech to text keeps
# them (wordtimes.json): a long pause in the middle of the first two lines,
# which is where the share of letters puts a moved line's start worst.
HEARD = [
    ("سلام", 0.2), ("و", 0.6), ("درود", 0.8), ("به", 1.3), ("همه.", 1.6),
    ("چقدر", 6.8), ("دلم", 7.2), ("برای", 7.6), ("این", 8.1), ("لحظه", 9.1),
    ("برای", 10.1), ("صحبت", 10.5), ("کردن", 10.9), ("با", 11.3), ("شما.", 11.6),
    ("امیدوارم", 16.2), ("حال", 16.9), ("دلتون", 17.3),
    ("خوب", 20.1), ("باشه", 20.6), ("و", 21.1), ("روزگار", 21.4), ("بر", 22.0),
    ("وفق", 22.3), ("مرادتون", 22.7), ("بگرده.", 23.3),
    ("بعد", 30.1), ("از", 30.5), ("آن", 30.8), ("می‌گویم", 31.2),
]


def keep_words(d, words, lang, change=None):
    """wordtimes.json beside a fixture video, cut into its transcript's lines
    exactly as the add page adopts it."""
    import wordtimes as W
    doc = W.empty("fixturejob", lang, [{"word": w, "start": t, "end": t + 0.4}
                                       for w, t in words], "whisper", "test")
    with io.open(os.path.join(d, "transcript.txt"), encoding="utf-8") as f:
        caps = CA.parse_transcript_text(f.read(), lang)
    doc = W.sync(doc, caps, lang)
    if change:
        change(doc)
    W._write(os.path.join(d, "wordtimes.json"), doc)
    return doc


class TheWordsOwnTimes(Base):
    """Where the video kept the time each word was heard, a line that begins
    with another word begins when THAT word was heard -- not where the share
    of its letters would put it (the old way, which fails these)."""

    def setUp(self):
        Base.setUp(self)
        self.doc = keep_words(self.d, HEARD, "fa")

    def wt(self):
        return json.loads(self.read("wordtimes.json"))

    def test_the_end_of_a_line_moved_down_starts_when_its_first_word_was_heard(self):
        out = reflow.move(self.d, 0, "end", 1)            # «چقدر دلم برای این لحظه» goes down
        self.assertEqual(self.ann()[1]["start"], 6.8)
        self.assertEqual(self.caps()[1]["start"], 6.8)
        self.assertEqual(out["timed"]["by"], "words")
        self.assertEqual(out["timed"]["word"], "چقدر")
        self.assertFalse(out["estimated"], "a heard time is not settled into a pause")
        self.clean()

    def test_the_start_of_a_line_moved_up_starts_at_the_word_it_now_begins_with(self):
        out = reflow.move(self.d, 1, "start", 2)          # the line begins at «امیدوارم»
        self.assertEqual(self.ann()[1]["start"], 16.2)
        self.assertEqual(out["timed"], {"by": "words", "source": "whisper", "word": "امیدوارم"})
        self.clean()

    def test_inside_a_phrase_too(self):
        reflow.move(self.d, 1, "start", 0, word=2)        # begins at «کردن»
        self.assertEqual(self.ann()[1]["start"], 10.9)

    def test_the_word_times_are_cut_the_same_way_and_no_time_changes(self):
        reflow.move(self.d, 0, "end", 1)
        wt = self.wt()
        self.assertEqual([a["start"] for a in wt["atoms"]], [a["start"] for a in self.doc["atoms"]])
        self.assertEqual([c["text"] for c in wt["captions"]], [c["text"] for c in self.caps()])
        self.assertEqual(wt["atoms"][wt["captions"][1]["first"]]["surface"], "چقدر")
        self.assertEqual(wt["revision"], self.doc["revision"], "no word was said anew")

    def test_undo_gives_back_the_word_times_byte_for_byte(self):
        was = self.read("wordtimes.json"), self.files()
        out = reflow.move(self.d, 1, "start", 2)
        self.assertNotEqual(self.read("wordtimes.json"), was[0])
        reflow.restore(self.d, out["pair"], out["segments"], out["before"])
        self.assertEqual((self.read("wordtimes.json"), self.files()), was)

    def test_a_second_move_reads_the_tape_the_first_one_cut(self):
        reflow.move(self.d, 0, "end", 1)                  # line 1 now opens «چقدر …»
        out = reflow.move(self.d, 1, "start", 1)          # and now at «برای» of «برای این لحظه»
        self.assertEqual(out["timed"]["word"], "برای")
        self.assertEqual(self.ann()[1]["start"], 7.6)
        self.clean()

    def test_a_start_a_person_set_by_ear_wins(self):
        import wordtimes as W
        shutil.rmtree(self.d)
        build(self.d)
        keep_words(self.d, HEARD, "fa",
                   lambda doc: doc["pins"].update({doc["atoms"][5]["id"]: 6.55}))
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(self.ann()[1]["start"], 6.55)
        self.assertEqual(out["timed"]["source"], "person")
        self.assertTrue(W.clean(self.wt()))

    def test_a_word_written_in_afterwards_falls_back_to_the_share_and_says_why(self):
        shutil.rmtree(self.d)
        build(self.d)
        keep_words(self.d, HEARD, "fa",
                   lambda doc: doc["atoms"][5].update({"time_source": "interpolated"}))
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["timed"]["by"], "share")
        self.assertIn("written in afterwards", out["timed"]["why"])
        self.assertTrue(out["estimated"])
        self.assertNotEqual(self.ann()[1]["start"], 6.8)
        self.clean()

    def test_a_time_outside_the_two_lines_is_not_believed(self):
        shutil.rmtree(self.d)
        build(self.d)
        keep_words(self.d, HEARD, "fa", lambda doc: doc["atoms"][5].update({"start": 25.0}))
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["timed"]["by"], "share")
        self.assertIn("not between the lines", out["timed"]["why"])
        self.assertTrue(0 < self.ann()[1]["start"] < 10)

    def test_without_word_times_the_share_and_the_reason(self):
        os.unlink(os.path.join(self.d, "wordtimes.json"))
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["timed"]["by"], "share")
        self.assertIn("no word times", out["timed"]["why"])
        self.assertFalse(os.path.exists(os.path.join(self.d, "wordtimes.json")))

    def test_a_file_that_is_not_word_times_is_left_alone(self):
        with io.open(os.path.join(self.d, "wordtimes.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        out = reflow.move(self.d, 0, "end", 1)
        self.assertEqual(out["timed"]["by"], "share")
        self.assertEqual(self.read("wordtimes.json"), "{not json")


class PausesForFullStops(Base):
    """A transcript with no full stops has the pauses of its word times."""

    def test_the_pauses_and_the_heard_words(self):
        keep_words(self.d, HEARD, "fa")
        m = reflow.marks(self.d)
        self.assertTrue(m["words"])
        # «به همه.» is followed by the pause before «چقدر»; «لحظه» runs on into line 2
        self.assertEqual(m["lines"][0]["w"], [[1, 1, 1], [1, 3], [1, 1], [1, 1, 1]])
        self.assertFalse(m["lines"][0]["end"])
        self.assertTrue(m["lines"][1]["end"])
        self.assertTrue(m["lines"][3]["end"], "the last line ends the video")

    def test_none_without_word_times(self):
        self.assertEqual(reflow.marks(self.d)["words"], False)


class AFilmOfItsOwnWithWordTimes(unittest.TestCase):
    """Japanese writes no spaces: the phrase that moves begins at its first
    character's heard time."""

    def test_the_first_character_heard(self):
        tmp = tempfile.mkdtemp(prefix="parseh-reflow-ja-")
        try:
            d = os.path.join(tmp, "fixture")
            os.makedirs(d)
            segs = [{"start": 0, "text": "今日は天気がいいですね。明日は",
                     "chunks": [{"fa": "今日は天気がいいですね。", "kana": "きょうはてんきがいいですね。", "tr": "kyō wa", "en": "today"},
                                {"fa": "明日は", "kana": "あしたは", "tr": "ashita wa", "en": "tomorrow"}]},
                    {"start": 8, "text": "雨でしょう。",
                     "chunks": [{"fa": "雨でしょう。", "kana": "あめでしょう。", "tr": "ame deshō", "en": "rain"}]}]
            with io.open(os.path.join(d, "annotations.json"), "w", encoding="utf-8") as f:
                json.dump({"video": "x", "language": "ja", "segments": segs}, f,
                          ensure_ascii=False, indent=1)
            with io.open(os.path.join(d, "transcript.txt"), "w", encoding="utf-8") as f:
                f.write("0:00\n今日は天気がいいですね。明日は\n0:08\n雨でしょう。\n")
            with io.open(os.path.join(d, "video.json"), "w", encoding="utf-8") as f:
                json.dump({"id": "x", "title": "t", "channel": "c", "language": "ja",
                           "level": "beginner"}, f)
            keep_words(d, [("今日は天気がいいですね。", 0.1), ("明日は", 5.0), ("雨でしょう。", 8.1)], "ja")
            m = reflow.marks(d)
            self.assertEqual(m["lines"][0]["w"], [[3], [3]], "a phrase is one unit, a pause after each")
            out = reflow.move(d, 0, "end", 0)
            self.assertEqual(out["timed"]["by"], "words")
            self.assertEqual(out["timed"]["word"], "明")
            with io.open(os.path.join(d, "annotations.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["segments"][1]["start"], 5)
            errors, _w, _n = CA.check(d)
            self.assertEqual(errors, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
