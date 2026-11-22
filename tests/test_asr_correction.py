# SPDX-License-Identifier: GPL-3.0-or-later
"""The transcript review's evidence, its reading of a sentence answer and the applying of chosen edits.

These are the parts of the copy/paste review (asrexternal) that asrcorrection holds.  They were
tested in test_llm_integration.py until a0.6.3 removed the connection to a model service; the
tests of that connection went with it."""
import copy
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import asrcorrection as correction
from reviewerror import Cancellation, LLMError
import sttjobs
import sttworker
import sttpanel



def evidence(text="loro anno detto ciao"):
    words, at = [], 0
    for value in text.split():
        words.append({"text": value, "start": at, "end": at + .2,
                      "score": .3 if value == "anno" else None,
                      "asr_alternatives": [{"text": "hanno", "score": .37}] if value == "anno" else [],
                      "alternatives_available": value == "anno"})
        at += .25
    segments = [{"start": 0, "end": at, "text": text, "asr_words": words}]
    panel, _ = sttpanel.segments_to_panel(segments)
    return panel, correction.evidence(segments, panel, "it")


def proposal(request):
    w = next(w for w in correction.index(request).values() if w["text"] == "anno")
    return {"schema_version": 1, "suggestions": [{"segment_id": w["segment_id"],
            "word_id": w["word_id"], "original": w["text"], "error_likelihood": .8,
            "reason": "Context and the ASR alternative support a correction.",
            "candidates": [{"text": "hanno", "confidence": .7, "reason": "Matches the subject."}]}]}


class Schema(unittest.TestCase):
    def setUp(self):
        self.panel, self.request = evidence()
        self.targets = set(correction.index(self.request))

    def test_sentence_rehydrates_source_and_applies_only_selected_span(self):
        unit = correction.sentence_units(self.request)[0]
        proposals, ignored = correction.sentence_result("loro hanno detto ciao", unit)
        word = proposals[0]
        self.assertEqual(word["asr_confidence"], .3)
        self.assertEqual(word["asr_alternatives"], [{"text": "hanno", "score": .37}])
        result = {"suggestions": proposals}
        panel, changed = correction.apply(self.panel, self.request, result, {word["word_id"]: 0})
        self.assertTrue(changed)
        self.assertEqual(panel, self.panel.replace("anno", "hanno"))
        self.assertEqual(correction.apply(self.panel, self.request, result, {})[0], self.panel)
        self.assertIsNone(word["error_likelihood"])
        self.assertIsNone(word["candidates"][0]["confidence"])

    def test_ignore_edits_outside_targets_and_reject_unrelated_or_json_answers(self):
        unit = correction.sentence_units(self.request)[0]
        proposals, ignored = correction.sentence_result("loro hanno detto buongiorno", unit)
        self.assertEqual([s["original"] for s in proposals], ["anno"])
        self.assertTrue(ignored)
        for answer in ('{"suggestions":[]}', "Completely unrelated output", "x" * 6001, "line\nbreak"):
            with self.subTest(answer=answer), self.assertRaises(LLMError):
                correction.sentence_result(answer, unit)

    def test_unicode_manual_edit_without_llm_or_asr_alternatives(self):
        for text in ("سلام دنیا", "日本語の名前", "caffè e tè", "🙂 parola"):
            panel, req = evidence(text)
            word = list(correction.index(req).values())[-1]
            self.assertIsNone(word["asr_confidence"])
            self.assertFalse(word["low_asr_score"])
            result, changed = correction.apply(panel, req, {"suggestions": []}, {}, {word["word_id"]: "corretto"})
            self.assertTrue(changed)
            self.assertEqual(result, panel[:word["span_start"]] + "corretto" + panel[word["span_end"]:])
        for edits in ({"unknown": "word"}, {"s0w1": "two words"}, {"s0w1": ""}, {"s0w1": "x" * 201}, {"s0w1": "x\ny"}):
            with self.assertRaises(LLMError):
                correction.apply(self.panel, self.request, {"suggestions": []}, {}, edits)

    def test_prompt_is_short_plain_text_and_hints_only_targets(self):
        unit = correction.sentence_units(self.request)[0]
        prompt = correction.messages(self.request, unit)
        # the evidence of one sentence, which the copy/paste prompt carries under its label
        self.assertEqual([m["role"] for m in prompt], ["user"])
        self.assertIn("Target sentence: loro anno detto ciao", prompt[-1]["content"])
        self.assertIn("hanno", prompt[-1]["content"])
        self.assertNotIn('"word_id"', prompt[-1]["content"])
        self.assertNotIn("loro (", prompt[-1]["content"])

    def test_manual_neighbor_merge_is_exact_and_rejects_invalid_ranges(self):
        text = 'A note book arrived.'
        segments = [{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .95, 'start': i, 'end': i + .5}
            for i, word in enumerate(text.split())]},
            {'text': 'Keep this caption.', 'start': 5, 'end': 8, 'words': []}]
        panel, _ = sttpanel.segments_to_panel(segments)
        req = correction.evidence(segments, panel, 'en'); before = copy.deepcopy(req)
        edited, changed = correction.apply(panel, req, {'suggestions': []}, {},
            {'s0w1': {'text': 'notebook', 'word_ids': ['s0w1', 's0w2']}})
        self.assertEqual(edited, panel.replace('note book', 'notebook'))
        self.assertTrue(changed); self.assertEqual(req, before)
        for ids in (['s0w1', 's0w3'], ['s0w2', 's0w1'], ['s0w1', 's0w1'], ['s0w1', 's1w0']):
            with self.subTest(ids=ids), self.assertRaises(LLMError):
                correction.apply(panel, req, {'suggestions': []}, {}, {'s0w1': {'text': 'notebook', 'word_ids': ids}})
        with self.assertRaises(LLMError):
            correction.apply(panel, req, {'suggestions': []}, {}, {
                's0w1': {'text': 'notebook', 'word_ids': ['s0w1', 's0w2']}, 's0w2': 'volume'})

    def test_manual_persian_merge_keeps_unicode_and_source_evidence(self):
        panel, request = evidence('این کو چیکه و خوبه.')
        before = copy.deepcopy(request)
        result, changed = correction.apply(panel, request, {'suggestions': []}, {}, {
            's0w1': {'text': 'کوچیکه', 'word_ids': ['s0w1', 's0w2']}})
        self.assertTrue(changed)
        self.assertEqual(result, panel.replace('کو چیکه', 'کوچیکه'))
        self.assertEqual(request, before)

    def test_long_caption_splits_keep_each_target_owned_once(self):
        _, req = evidence(" ".join("word%d" % i for i in range(240)))
        for w in correction.index(req).values():
            w["low_asr_score"] = True
        units = correction.sentence_units(req, 600)
        ids = [w["word_id"] for u in units for w in u["targets"]]
        self.assertEqual(len(ids), 240)
        self.assertEqual(len(set(ids)), 240)
        self.assertTrue(all(len(u["text"].encode("utf-8")) <= 600 for u in units))

    def test_whole_text_includes_confident_words_and_maps_japanese_span(self):
        text = "鉄石缶だから行く"
        raw = [{"start": 0, "end": 3, "text": text, "asr_words": [
            {"text": t, "score": .2 if i == 0 else .95, "start": i / 10, "end": (i + 1) / 10}
            for i, t in enumerate(text)]}]
        panel, _ = sttpanel.segments_to_panel(raw)
        req = correction.evidence(raw, panel, "ja")
        unit = correction.sentence_units(req, task="full")[0]
        self.assertEqual(len(unit["targets"]), len(text))
        proposals, _ = correction.full_sentence_result("テスト期間だから行く", unit)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["word_ids"], ["s0w0", "s0w1", "s0w2"])
        out, changed = correction.apply(panel, req, {"suggestions": proposals}, {"s0w0": 0})
        self.assertTrue(changed)
        self.assertEqual(out, panel.replace("鉄石缶", "テスト期間"))
        with self.assertRaises(LLMError):
            correction.apply(panel, req, {"suggestions": proposals}, {"s0w0": 0}, {"s0w1": "other"})
        out, _ = correction.apply(panel, req, {"suggestions": []}, {}, {"s0w0": {"text": "テスト期間", "word_ids": ["s0w0", "s0w1", "s0w2"]}})
        self.assertEqual(out, panel.replace("鉄石缶", "テスト期間"))

    def test_whole_text_prompt_and_bounded_context(self):
        unit = correction.sentence_units(self.request, task="full")[0]
        prompt = correction.messages(self.request, unit, task="full")
        self.assertIn("Target sentence:", prompt[-1]["content"])
        self.assertNotIn('"word_id"', prompt[-1]["content"])
        for answer in ("loro hanno detto ciao -> loro hanno detto ciao", "translated explanation\nanswer"):
            with self.assertRaises(LLMError):
                correction.full_sentence_result(answer, unit)

    def test_every_refusal_of_a_reply_says_its_own_reason_and_a_chatty_reply_is_read(self):
        # one sentence used to cover them all: "could not be tied to the original words"
        _, req = evidence("loro anno detto ciao e anno poi.")
        unit = correction.sentence_units(req)[0]
        refused = {
            "": "it is empty",
            "hanno": "less than half of the sentence's other letters",
            "loro hanno detto ciao e anno poi. (anno \u2192 hanno)": "an arrow",
            "loro hanno detto ciao e anno poi. Explanation: " + "the verb must agree with its subject. " * 8: "much longer than the sentence",
            '{"sentence": "loro hanno detto ciao e anno poi."}': "JSON or a list",
            "[Corrected] loro hanno detto ciao e anno poi.": "JSON or a list",
            "x" * 6001: "longer than 6000",
            "loro hanno\ndetto\x01 ciao e anno poi.": "control characters",
        }
        for answer, why in refused.items():
            with self.subTest(answer=answer[:40]):
                with self.assertRaises(LLMError) as caught:
                    correction.sentence_result(answer, unit)
                self.assertEqual(caught.exception.code, "invalid-suggestions")
                self.assertIn(why, caught.exception.say)
                self.assertIn("The model's reply was refused", caught.exception.say)
                self.assertNotIn("could not be tied", caught.exception.say)
        # the sentence is the line that resembles the one asked about: a preface or a note on a line of its own is not the sentence
        for answer in ("Here is the corrected sentence:\nloro hanno detto ciao e anno poi.",
                       "loro hanno detto ciao e anno poi.\n(the verb needed to be plural)",
                       "Sure!\n\n\"loro hanno detto ciao e anno poi.\"\n\nanno \u2192 hanno: the verb",
                       "loro hanno detto ciao e anno poi.\n\nExplanation: " + "the verb must agree with its subject. " * 8):
            with self.subTest(answer=answer[:30]):
                proposals, _ = correction.sentence_result(answer, unit)
                self.assertEqual([p["candidates"][0]["text"] for p in proposals], ["hanno"])
        # ... but a reply of several lines of which none is the sentence is still refused, with its reason
        with self.assertRaises(LLMError) as caught:
            correction.sentence_result("a translation:\nthey said hello\nand a year later", unit)
        self.assertIn("several lines", caught.exception.say)
        # and what is refused when the choices are applied says so as well
        panel = "0:00\nloro anno detto ciao e anno poi.\n"
        with self.assertRaises(LLMError) as caught:
            correction.apply(panel + "changed", req, {"suggestions": []}, {})
        self.assertIn("not the text that was reviewed", caught.exception.say)
        self.assertNotIn("The model's reply", caught.exception.say)

    def test_backend_alternative_capability_and_remapping_preserve_scores(self):
        absent = sttworker.word_alternatives(type("Word", (), {})())
        self.assertEqual(absent, {"asr_alternatives": [], "alternatives_available": False})
        present = sttworker.word_alternatives(type("Word", (), {"alternatives": [{"text": "hanno", "score": .37}]})())
        self.assertEqual(present["asr_alternatives"][0]["score"], .37)
        seg = {"start": 2, "end": 3, "text": "anno", "asr_words": [{"start": 2, "end": 2.2, "text": "anno", "score": .3}]}
        out = sttpanel.remap([seg], [[32000, 1], [48000, 2]])[0]
        self.assertEqual(out["asr_words"][0]["score"], .3)
        self.assertEqual(out["asr_words"][0]["start"], 1)


class Jobs(unittest.TestCase):
    def setUp(self):
        private = tempfile.TemporaryDirectory()
        self.addCleanup(private.cleanup)
        videos = mock.patch('ytpages.VIDEOS', private.name)
        videos.start(); self.addCleanup(videos.stop)
        self.panel, request = evidence()
        self.token = "ABCDEFGHIJKLMNOP"
        self.job = {"id": self.token, "kind": "film", "source": {"kind": "film", "path": "/private/film.mp4"},
                    "lang": "it", "model": "large-v3-turbo", "state": sttjobs.REVIEW_CHOICE,
                    "review_evidence": request, "review_choice": None, "correction": {},
                    "text": self.panel, "facts": {"captions": 1}, "cancelled": False,
                    "finished": time.time(), "created": time.time(), "total": 1, "done": 1,
                    "device": "cpu", "fell_back": False, "have": 0, "words": None,
                    "notes": [], "warning": "", "error": None}
        patch = mock.patch.dict(sttjobs.JOBS, {self.token: self.job}, clear=True)
        patch.start(); self.addCleanup(patch.stop)

    def test_asr_result_can_be_used_explicitly_without_a_method_choice_gate(self):
        with mock.patch("wavefile.held", return_value=False):
            out = sttjobs.use_review(self.token, self.job["review_evidence"]["source_sha256"], {})
            self.assertEqual(out["text"], self.panel)

    def test_cancel_preserves_pending_asr_and_invalidates_late_results(self):
        token = Cancellation()
        self.job.update(state=sttjobs.CORRECTING, llm_cancel=token, llm_generation=1,
                        review_choice="likelihood", correction_result={"suggestions": []})
        sttjobs.cancel_review(self.token)
        self.assertTrue(token.event.is_set())
        self.assertEqual(self.job["state"], sttjobs.DONE, 'review tools remain usable after cancelling one tool')
        self.assertEqual(self.job["text"], self.panel)
        self.assertIsNone(self.job["correction_result"])
        self.assertEqual(self.job["llm_generation"], 2)
        self.assertFalse(sttjobs.busy())

    def test_changed_source_hash_is_refused(self):
        with self.assertRaises(sttjobs.Refusal) as e:
            sttjobs.review(self.token, "whisper", "another-source")
        self.assertEqual(e.exception.code, "stale-review")


if __name__ == "__main__":
    unittest.main()
