# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline contracts for native alternatives and local dictionary review cues.

Added for later validation; not run during the requested release rehearsal.
"""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "lib"),
                str(Path(__file__).resolve().parents[1] / "youtube/lib")]
import asrcorrection
import asrdictionary
import asralternatives
import sttworker
import sttjobs


def dictionary_row(word, headword=None):
    return {"word": word, "tried": [word], "hits":
            [{"headword": headword, "pos": "verb", "senses": ["to burn"]}] if headword else []}


class DictionaryEvidence(unittest.TestCase):
    def test_review_resolves_native_and_llm_alternatives_from_saved_evidence(self):
        words = [{"word_id": "s0w0", "segment_id": "s0", "text": "loro", "asr_alternatives": []},
                 {"word_id": "s0w1", "segment_id": "s0", "text": "anno", "asr_alternatives": [{"text": "hanno", "score": None}]},
                 {"word_id": "s0w2", "segment_id": "s0", "text": "detto", "asr_alternatives": []}]
        job = {"kind": "youtube", "lang": "it", "review_evidence": {"source_sha256": "source", "segments": [{"segment_id": "s0", "words": words}]},
               "correction_result": {"suggestions": [{"word_id": "s0w1", "original": "anno", "candidates": [{"text": "hanno"}]}]}}
        resolver = mock.Mock()
        resolver.word.return_value = {"state": "found", "words": []}
        job["dictionary_resolver"] = resolver
        with mock.patch("sttjobs._job", return_value=job):
            result = sttjobs.review_dictionary("job", "source", "s0w1")
            with self.assertRaises(sttjobs.Refusal):
                sttjobs.review_dictionary("job", "stale", "s0w1")
        self.assertEqual(result["asr_alternatives"][0]["text"], "hanno")
        self.assertEqual(result["candidates"][0]["text"], "hanno")
        self.assertIn(mock.call("hanno", "loro", "detto"), resolver.word.call_args_list)
        self.assertEqual(words[1]["asr_alternatives"], [{"text": "hanno", "score": None}])

    def test_high_score_dictionary_miss_is_target_without_changing_evidence(self):
        word = {"word_id": "s0w0", "segment_id": "s0", "text": "zzword",
                "start": 0, "end": .5, "asr_confidence": .99, "low_asr_score": False,
                "reviewable": True, "asr_alternatives": [], "alternatives_available": False}
        evidence = {"segments": [{"segment_id": "s0", "text": "zzword", "words": [word]}]}
        saved = copy.deepcopy(word)
        with mock.patch("lookup.look_up", return_value={"words": [dictionary_row("zzword")], "source": {}}):
            self.assertTrue(asrdictionary.Resolver("it").enrich(evidence))
        self.assertTrue(asrcorrection.suspect(word))
        self.assertEqual({k: word[k] for k in saved}, saved)
        self.assertEqual(asrcorrection.sentence_units(evidence)[0]["targets"][0]["word_id"], "s0w0")

    def test_absence_failure_and_punctuation_do_not_flag_a_word(self):
        for response in (None, RuntimeError("unavailable")):
            with mock.patch("lookup.look_up", **({"side_effect": response} if isinstance(response, Exception) else {"return_value": response})):
                self.assertNotEqual(asrdictionary.Resolver("fa").word("اسم")["state"], "missing")
        with mock.patch("lookup.look_up", return_value={"words": [], "source": {}}):
            self.assertEqual(asrdictionary.Resolver("fa").word("،")["state"], "not-word")

    def test_separated_prefix_uses_reader_join_rules_not_a_neighbours_meaning(self):
        def lookup(code, text, **how):          # (the review asks as speech: register="spoken")
            row = dictionary_row(text, "سوختن") if text == "نمی سوزانند" else dictionary_row(text)
            return {"words": [row], "source": {}}
        with mock.patch("lookup.look_up", side_effect=lookup):
            resolver = asrdictionary.Resolver("fa")
            self.assertEqual(resolver.word("سوزانند", previous="نمی")["state"], "found")
            self.assertEqual(resolver.word("zzword", previous="نمی")["state"], "missing")


class NativeAlternatives(unittest.TestCase):
    def test_word_insertions_and_unicode_map_but_cross_word_edits_do_not(self):
        found = asralternatives.substitutions("loro anno deto", "loro hanno detto",
                                              [("a", 5, 9), ("b", 10, 14)], -.7)
        self.assertEqual([found[k]["text"] for k in ("a", "b")], ["hanno", "detto"])
        self.assertIsNone(found["a"]["score"])
        self.assertEqual(found["a"]["sequence_score"], -.7)
        self.assertFalse(asralternatives.substitutions("due parole", "qualcosa", [("a", 0, 3), ("b", 4, 10)], -.4))
        self.assertEqual(asralternatives.substitutions("猫は眠る", "犬は眠る", [("a", 0, 1)], -.2)["a"]["text"], "犬")

    def test_native_primary_and_word_timing_survive_the_capability_and_vad(self):
        decoder = SimpleNamespace()
        calls = []
        generation = SimpleNamespace(sequences_ids=[["anno"], ["hanno"]], scores=[-.1, -.3])
        def generate(*args, **kwargs):
            calls.append(kwargs)
            return [generation]
        decoder.generate = generate
        tokenizer = SimpleNamespace(decode=lambda tokens: " ".join(tokens))

        class Native:
            def __init__(self):
                self.model = decoder
            def generate_with_fallback(self, encoded, prompt, tokenizer, options):
                return self.model.generate(encoded, [prompt], beam_size=5, patience=1, return_scores=True)[0], -.1, 0, 1
            def add_word_timestamps(self, segments, *args, **kwargs):
                return .5
            def generate_segments(self):
                self.generate_with_fallback(None, [], tokenizer, None)
                segments = [[{"words": [{"start": 0, "end": .5, "word": "anno", "probability": .3}]}]]
                self.add_word_timestamps(segments)
                yield SimpleNamespace(text="anno", words=[SimpleNamespace(**segments[0][0]["words"][0])])

        native = asralternatives.capable_model(Native)()
        segment = next(native.generate_segments())
        word = segment.words[0]
        self.assertEqual((segment.text, word.start, word.end, word.probability), ("anno", 0, .5, .3))
        word.start += 2; word.end += 2  # native VAD remaps the same word object
        evidence = sttworker.word_alternatives(word)
        self.assertTrue(evidence["alternatives_available"])
        self.assertEqual(evidence["asr_alternatives"][0]["text"], "hanno")
        self.assertIsNone(evidence["asr_alternatives"][0]["score"])
        self.assertIs(native.model, decoder)
        self.assertEqual(calls[0]["num_hypotheses"], 5)
        self.assertEqual(calls[0]["beam_size"], 5)

    def test_sequence_scores_are_not_coerced_into_word_probabilities(self):
        raw = [{"text": "hanno", "score": None, "sequence_score": -.5, "score_kind": "sequence_log_score"},
               {"text": "alt", "sequence_score": float("nan"), "score_kind": "sequence_log_score"}]
        candidates, available = asrcorrection.alternatives(raw)
        self.assertTrue(available)
        self.assertIsNone(candidates[0]["score"])
        self.assertEqual(candidates[0]["sequence_score"], -.5)
        self.assertNotIn("sequence_score", candidates[1])


if __name__ == "__main__":
    unittest.main()
