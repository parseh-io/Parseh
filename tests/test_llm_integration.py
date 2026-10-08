# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline LLM contracts: local fake HTTP, immutable evidence and review jobs.

These tests are added for the feature, but intentionally not run during the
user's requested release rehearsal. No external model or network is needed.
"""
import copy
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import asrcorrection as correction
import asrworkspace
import llmadapter
import llmconfig
import llmprofiles
import settingspage
import sttjobs
import sttworker
import sttpanel


def config(base="http://127.0.0.1:11434/v1", preset="ollama", key="private-key", timeout=2):
    return {"format_version": 1, "provider_preset": preset, "base_url": base,
            "selected_model": "served/model", "api_key": key, "timeout_seconds": timeout}


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


class FakeHTTP:
    def __init__(self):
        self.calls, self.status, self.delay, self.body = [], 200, 0, None
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.respond(None)

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.respond(data)

            def respond(self, body):
                owner.calls.append((self.path, dict(self.headers), body))
                time.sleep(owner.delay)
                data = owner.body or ({"data": [{"id": "served/model"}]} if body is None else
                    {"choices": [{"finish_reason": "stop", "message": {"content": 'Parseh connection OK'}}]})
                raw = data if isinstance(data, bytes) else json.dumps(data).encode()
                try:
                    self.send_response(owner.status)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = "http://127.0.0.1:%d/prefix/v1/" % self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Adapter(unittest.TestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.addCleanup(self.http.close)

    def test_presets_share_adapter_and_saved_model_text_request(self):
        for preset in ("ollama", "unsloth", "generic"):
            adapter = llmadapter.adapter(config(self.http.base, preset))
            self.assertIsInstance(adapter, llmadapter.OpenAICompatible)
            self.assertEqual(adapter.models(), ["served/model"])
            self.assertIn("returned the requested text", adapter.test()["say"])
        path, headers, payload = self.http.calls[-1]
        self.assertEqual(path, "/prefix/v1/chat/completions")
        self.assertEqual(payload["model"], "served/model")
        self.assertEqual(payload["temperature"], 0)
        self.assertNotIn("response_format", payload)
        self.assertEqual(headers["Authorization"], "Bearer private-key")
        self.assertEqual(len(payload["messages"]), 2)

    def test_http_errors_redact_endpoint_body_and_key(self):
        self.http.status, self.http.body = 401, b'private-key transcript contents'
        with self.assertRaises(llmconfig.LLMError) as e:
            llmadapter.adapter(config(self.http.base)).models()
        self.assertEqual(e.exception.status, 401)
        self.assertNotIn("private-key", str(e.exception))
        self.assertNotIn("transcript", str(e.exception))

    def test_unloaded_model_is_explained_without_echo_or_json_mode_retry(self):
        for error in ("No model loaded. private-key transcript contents",
                      {"code": "model_not_loaded", "message": "private-key transcript contents"}):
            with self.subTest(error=error):
                self.http.status, self.http.body = 400, {"error": error}
                self.http.calls.clear()
                with self.assertRaises(llmconfig.LLMError) as e:
                    llmadapter.adapter(config(self.http.base)).test()
                self.assertEqual(e.exception.code, "model-not-loaded")
                self.assertIn("Load the selected model", str(e.exception))
                self.assertNotIn("private-key", str(e.exception))
                self.assertNotIn("transcript", str(e.exception))
                self.assertEqual(len(self.http.calls), 1)

    def test_unknown_or_oversized_http_error_remains_redacted(self):
        for body in (b'private-key transcript contents',
                     {"error": {"message": "private-key transcript contents"}},
                     b'x' * (llmadapter.MAX_ERROR + 1)):
            self.http.status, self.http.body = 400, body
            with self.assertRaises(llmconfig.LLMError) as e:
                llmadapter.adapter(config(self.http.base)).models()
            self.assertEqual(e.exception.code, "http-error")
            self.assertNotIn("private-key", str(e.exception))
            self.assertNotIn("transcript", str(e.exception))

    def test_size_limit_and_malformed_json(self):
        for raw in (b"x" * (llmadapter.MAX_RESPONSE + 1), b"not JSON", b'{"ok":NaN}'):
            self.http.body = raw
            with self.assertRaises(llmconfig.LLMError):
                llmadapter.adapter(config(self.http.base)).models()

    def test_cancellation_interrupts_a_waiting_response(self):
        self.http.delay = 2
        token, errors = llmadapter.Cancellation(), []

        def work():
            try:
                llmadapter.adapter(config(self.http.base)).models(token)
            except llmconfig.LLMError as e:
                errors.append(e.code)

        thread = threading.Thread(target=work)
        thread.start()
        deadline = time.monotonic() + 1
        while not self.http.calls and time.monotonic() < deadline:
            time.sleep(.01)
        token.cancel()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, ["cancelled"])

    def test_wall_clock_timeout(self):
        self.http.delay = 2
        with self.assertRaises(llmconfig.LLMError) as e:
            llmadapter.adapter(config(self.http.base, timeout=1)).models()
        self.assertIn(e.exception.code, ("timeout", "connection"))

    def test_absent_key_and_incomplete_response(self):
        adapter = llmadapter.adapter(config(self.http.base, key=None))
        adapter.models()
        self.assertNotIn("Authorization", self.http.calls[-1][1])
        self.http.body = {"choices": [{"finish_reason": "length", "message": {"content": '{"ok":true}'}}]}
        with self.assertRaises(llmconfig.LLMError):
            adapter.test()

    def test_reasoning_is_separate_inspectable_and_credentials_redacted(self):
        self.http.body = {"choices": [{"finish_reason": "length", "message": {
            "content": None, "reasoning_content": "private-key reasoning"}}]}
        traces = []
        with self.assertRaises(llmconfig.LLMError) as e:
            llmadapter.adapter(config(self.http.base)).generate_text([], observe=traces.append)
        self.assertEqual(e.exception.code, "output-limit")
        self.assertEqual(traces[0]["answer"], "")
        self.assertNotIn("private-key", traces[0]["reasoning"])
        self.assertIn("reasoning", traces[0]["reasoning"])

    def test_timeout_does_not_cancel_the_remaining_requests(self):
        token = llmadapter.Cancellation()
        self.http.delay = 2
        adapter = llmadapter.adapter(config(self.http.base, timeout=1))
        with self.assertRaises(llmconfig.LLMError):
            adapter.models(token)
        self.assertFalse(token.event.is_set())
        self.http.delay = 0
        self.assertEqual(adapter.models(token), ["served/model"])

    def test_structured_generation_remains_available_to_other_features(self):
        self.http.body = {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]}
        out = llmadapter.adapter(config(self.http.base)).generate([])
        self.assertEqual(out, {"ok": True})
        self.assertEqual(self.http.calls[-1][2]["response_format"], {"type": "json_object"})

    def test_native_skill_adapter_uses_only_read_skill_and_never_overwrites(self):
        client = llmadapter.adapter(dict(config(self.http.base), adapter="unsloth-agent-skills"))
        self.assertEqual(client._skills().config["base_url"], self.http.base.rstrip("/")[:-3] + "/api")
        self.http.body = [{"name": correction.SKILL_NAME, "valid": True, "enabled": True}]
        self.assertTrue(client.skill_status(correction.SKILL_NAME)["ready"])
        self.assertEqual(self.http.calls[-1][0], "/prefix/api/skills")
        with self.assertRaises(llmconfig.LLMError) as e:
            client.install_skill(correction.SKILL_NAME, correction.SKILL_DESCRIPTION, correction.skill_instructions())
        self.assertEqual(e.exception.code, "skill-exists")
        self.http.body = {"choices": [{"finish_reason": "stop", "message": {"content": "loro hanno detto ciao"}}]}
        with mock.patch.object(client, "skill_status", return_value={"ready": True}):
            client.generate_text([{ "role": "user", "content": "@" + correction.SKILL_NAME}], skill=correction.SKILL_NAME)
        payload = self.http.calls[-1][2]
        self.assertEqual(payload["enabled_tools"], ["read_skill"])
        self.assertTrue(payload["enable_tools"])
        self.assertFalse(payload["mcp_enabled"])
        self.assertNotIn("bypass_permissions", payload)
        self.assertNotIn("response_format", payload)


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
            with self.subTest(answer=answer), self.assertRaises(llmconfig.LLMError):
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
            with self.assertRaises(llmconfig.LLMError):
                correction.apply(self.panel, self.request, {"suggestions": []}, {}, edits)

    def test_prompt_is_short_plain_text_and_hints_only_targets(self):
        unit = correction.sentence_units(self.request)[0]
        prompt = correction.messages(self.request, unit)
        self.assertLess(len(correction.SYSTEM.split()), 90)
        self.assertIn("complete", correction.SYSTEM)
        self.assertIn("Do not\ntranslate", correction.SYSTEM)
        self.assertIn("optional", correction.SYSTEM)
        self.assertIn("hanno", prompt[1]["content"])
        self.assertNotIn('"word_id"', prompt[1]["content"])
        self.assertNotIn("loro (", prompt[1]["content"])
        self.assertIn("If unsure", correction.SYSTEM)
        skill_prompt = correction.messages(self.request, unit, use_skill=True)
        self.assertEqual(len(skill_prompt), 1)
        self.assertTrue(skill_prompt[0]["content"].startswith("@" + correction.SKILL_NAME))
        self.assertNotIn(correction.SYSTEM, skill_prompt[0]["content"])

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
            with self.subTest(ids=ids), self.assertRaises(llmconfig.LLMError):
                correction.apply(panel, req, {'suggestions': []}, {}, {'s0w1': {'text': 'notebook', 'word_ids': ids}})
        with self.assertRaises(llmconfig.LLMError):
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
        with self.assertRaises(llmconfig.LLMError):
            correction.apply(panel, req, {"suggestions": proposals}, {"s0w0": 0}, {"s0w1": "other"})
        out, _ = correction.apply(panel, req, {"suggestions": []}, {}, {"s0w0": {"text": "テスト期間", "word_ids": ["s0w0", "s0w1", "s0w2"]}})
        self.assertEqual(out, panel.replace("鉄石缶", "テスト期間"))

    def test_whole_text_prompt_skill_and_bounded_context(self):
        unit = correction.sentence_units(self.request, task="full")[0]
        prompt = correction.messages(self.request, unit, task="full")
        self.assertIn("high Whisper score", prompt[0]["content"])
        self.assertNotIn('"word_id"', prompt[1]["content"])
        prompt = correction.messages(self.request, unit, True, "full")
        self.assertTrue(prompt[0]["content"].startswith("@parseh-asr-audit"))
        for answer in ("loro hanno detto ciao -> loro hanno detto ciao", "translated explanation\nanswer"):
            with self.assertRaises(llmconfig.LLMError):
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
                with self.assertRaises(llmconfig.LLMError) as caught:
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
        with self.assertRaises(llmconfig.LLMError) as caught:
            correction.sentence_result("a translation:\nthey said hello\nand a year later", unit)
        self.assertIn("several lines", caught.exception.say)
        # and what is refused when the choices are applied says so as well
        panel = "0:00\nloro anno detto ciao e anno poi.\n"
        with self.assertRaises(llmconfig.LLMError) as caught:
            correction.apply(panel + "changed", req, {"suggestions": []}, {})
        self.assertIn("not the text that was reviewed", caught.exception.say)
        self.assertNotIn("The model's reply", caught.exception.say)

    def test_a_refused_sentence_leaves_its_words_with_no_answer_and_the_reason(self):
        _, req = evidence("loro anno detto ciao")
        adapter = mock.Mock()
        adapter.generate_text.return_value = "hanno (anno \u2192 hanno)"
        result = correction.correct(req, adapter, llmadapter.Cancellation(), lambda a, b: None)
        self.assertEqual(result["failed_word_ids"], ["s0w1"])
        self.assertIn("arrow", result["failed_reasons"]["s0w1"])

    def test_what_the_reader_let_pass_or_left_out_is_told_on_the_words_it_touched(self):
        # THE LENIENCY IS NEVER SILENT.  A reply read generously says so on its words, so that a person can ask again for them;
        # a change that could not be used leaves the word with no answer -- it must not look like a word the model agreed with.
        _, req = evidence("loro anno detto ciao e anno poi.")
        unit = correction.sentence_units(req)[0]
        # a clean reply carries nothing
        proposals, ignored = correction.sentence_result("loro hanno detto ciao e anno poi.", unit)
        self.assertEqual((len(proposals), correction.reading_notes(ignored)), (1, ({}, {})))
        # one line picked out of several: both words of the sentence are told, whatever the model said of them
        proposals, ignored = correction.sentence_result("Here is the corrected sentence:\nloro hanno detto ciao e anno poi.\nHope it helps", unit)
        refused, loose = correction.reading_notes(ignored)
        self.assertEqual((refused, sorted(loose)), ({}, ["s0w1", "s0w5"]))
        self.assertIn("3 lines", loose["s0w1"][0])
        self.assertEqual([p["word_id"] for p in proposals], ["s0w1"], "the word it changed is still proposed")
        # two flagged words changed into one: it cannot be tied to either, so neither has an answer, and the reason is the model's own words
        flagged = [dict(unit["words"][1], region_start=5, region_end=9), dict(unit["words"][1], word_id="s0w2", region_start=10, region_end=14)]
        one = {"sentence_id": "sentence0", "text": "loro anno anno detto", "words": flagged, "targets": flagged}
        proposals, ignored = correction.sentence_result("loro hanno detto", one)
        refused, loose = correction.reading_notes(ignored)
        self.assertEqual((proposals, sorted(refused)), ([], ["s0w1", "s0w2"]))
        self.assertIn("\u201canno anno\u201d", refused["s0w1"])
        # the same through the endpoint: those words are failed words with their reason, not silent "gave it back unchanged"
        adapter = mock.Mock()
        adapter.generate_text.return_value = "Here you go:\nloro hanno detto ciao e anno poi."
        result = correction.correct(req, adapter, llmadapter.Cancellation(), lambda a, b: None)
        self.assertEqual(sorted(result["allowances"]), ["s0w1", "s0w5"])
        self.assertEqual(result["failed_word_ids"], [])
        # a neighbour changed with it: only the flagged word is taken, and it says the neighbour was left
        proposals, ignored = correction.sentence_result("loro hanno ditto ciao e anno poi.", unit)
        loose = correction.reading_notes(ignored)[1]
        self.assertEqual(sorted(loose), ["s0w1"])
        self.assertIn("around this one", loose["s0w1"][0])
        # a whole-text answer that reaches words the question did not ask about
        _, full_req = evidence("loro anno detto ciao e anno poi.")
        full_unit = correction.sentence_units(full_req, task="full")[0]
        only = dict(full_unit, targets=[w for w in full_unit["targets"] if w["word_id"] == "s0w1"])
        proposals, ignored = correction.full_sentence_result("loro hanno detto ciao e anno poi.", only)
        self.assertEqual(len(proposals), 1, "inside what was asked: used")
        proposals, ignored = correction.full_sentence_result("loro anno detto cena e anno poi.", only)
        self.assertEqual(proposals, [], "outside what was asked: left out")
        self.assertTrue(any(not e.get("word_ids") for e in ignored), "and said, for the record of the answer")
        self.assertEqual(correction.reading_notes(ignored), ({}, {}), "it touched none of the words that were asked about")
        # ... and a change that reaches over a word that was asked about AND one that was not leaves the first with no answer, and why
        proposals, ignored = correction.full_sentence_result("loro hanno ciao e anno poi.", only)
        refused = correction.reading_notes(ignored)[0]
        self.assertEqual((proposals, sorted(refused)), ([], ["s0w1"]))
        self.assertIn("not part of this question", refused["s0w1"])

    def test_failure_is_local_progress_counts_words_and_retry_filters(self):
        _, req = evidence("loro anno detto ciao")
        second = copy.deepcopy(req["segments"][0]); second["start"] = 10; second["end"] = 12
        for w in second["words"]:
            w["word_id"] += "b"; w["segment_id"] = "s1"
        req["segments"].append(second)
        adapter, progress, diagnostics = mock.Mock(), [], []
        adapter.generate_text.side_effect = [llmconfig.LLMError("timeout", "Timed out."), "loro hanno detto ciao"]
        result = correction.correct(req, adapter, llmadapter.Cancellation(), lambda a,b: progress.append((a,b)), diagnostic=diagnostics.append)
        self.assertEqual(progress, [(0,2), (1,2), (2,2)])
        self.assertEqual(result["failed_word_ids"], ["s0w1"])
        self.assertEqual([s["word_id"] for s in result["suggestions"]], ["s0w1b"])
        self.assertEqual(len(diagnostics), 2)
        adapter.generate_text.side_effect = None; adapter.generate_text.return_value = "loro hanno detto ciao"
        result = correction.correct(req, adapter, llmadapter.Cancellation(), lambda a,b: None, target_word_ids=["s0w1"])
        self.assertEqual(result["words_total"], 1)
        self.assertEqual(result["failed_word_ids"], [])

    def test_cancellation_stops_the_run_and_truncation_is_inspectable(self):
        adapter = mock.Mock()
        adapter.generate_text.side_effect = llmconfig.LLMError("cancelled", "Cancelled.")
        with self.assertRaises(llmconfig.LLMError):
            correction.correct(self.request, adapter, llmadapter.Cancellation(), lambda a,b: None)
        adapter.generate_text.side_effect = llmconfig.LLMError("output-limit", "Output limit.")
        diagnostics = []
        out = correction.correct(self.request, adapter, llmadapter.Cancellation(), lambda a,b: None, diagnostic=diagnostics.append)
        self.assertEqual(out["failed_word_ids"], ["s0w1"])
        self.assertEqual(len(diagnostics), 2)

    def test_backend_alternative_capability_and_remapping_preserve_scores(self):
        absent = sttworker.word_alternatives(type("Word", (), {})())
        self.assertEqual(absent, {"asr_alternatives": [], "alternatives_available": False})
        present = sttworker.word_alternatives(type("Word", (), {"alternatives": [{"text": "hanno", "score": .37}]})())
        self.assertEqual(present["asr_alternatives"][0]["score"], .37)
        seg = {"start": 2, "end": 3, "text": "anno", "asr_words": [{"start": 2, "end": 2.2, "text": "anno", "score": .3}]}
        out = sttpanel.remap([seg], [[32000, 1], [48000, 2]])[0]
        self.assertEqual(out["asr_words"][0]["score"], .3)
        self.assertEqual(out["asr_words"][0]["start"], 1)


class Settings(unittest.TestCase):
    def test_model_only_save_cannot_redirect_or_replace_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            body = dict(config(), key_action="replace"); body.pop("format_version")
            llmconfig.save(body, root)
            out = llmconfig.select_model({"selected_model": "another/model"}, root)
            saved = llmconfig.load(root)
            self.assertEqual(saved["base_url"], config()["base_url"])
            self.assertEqual(saved["api_key"], "private-key")
            self.assertEqual(saved["selected_model"], "another/model")
            self.assertNotIn("api_key", out)
            for extra in ("base_url", "api_key", "timeout_seconds"):
                with self.assertRaises(llmconfig.LLMError):
                    llmconfig.select_model({"selected_model": "another/model", extra: "override"}, root)

    def test_default_disabled_key_redaction_and_risky_routes(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(llmconfig.view(root)["configured"])
            body = dict(config(), key_action="replace")
            body.pop("format_version")
            view = llmconfig.save(body, root)
            self.assertNotIn("api_key", view)
            self.assertTrue(view["has_api_key"])
            self.assertEqual(view["connection_id"], llmconfig.view(root)["connection_id"])
            self.assertNotEqual(view["connection_id"], llmconfig.fingerprint(llmconfig.load(root)))
            self.assertEqual(llmconfig.load(root)["api_key"], "private-key")
            Path(llmconfig.path(root)).write_text('{"format_version":99}')
            self.assertIsNone(llmconfig.load(root))
        for name in ("save", "reset", "models", "import-link"):
            self.assertFalse(settingspage.may_post("/settings/api/llm/" + name, "lan")[0])
        for name in ("status", "test", "models-saved", "select-model", "profile-save", "profile-remove", "profile-apply", "review-model", "review-prepare", "audit-skill-status"):
            self.assertTrue(settingspage.may_post("/settings/api/llm/" + name, "lan")[0])
        self.assertFalse(settingspage.may_post("/settings/api/llm/audit-skill-install", "lan")[0])

    def test_review_models_are_independent_and_cannot_override_destination(self):
        with tempfile.TemporaryDirectory() as root:
            body = dict(config(), key_action="replace"); body.pop("format_version")
            llmconfig.save(body, root)
            llmconfig.review_model({"task": "suspect", "model_id": "small/model", "profile_id": None}, root)
            out = llmconfig.review_model({"task": "full", "model_id": "larger/model", "profile_id": None}, root)
            saved = llmconfig.load(root)
            self.assertEqual(llmconfig.for_review(saved, "suspect")["selected_model"], "small/model")
            self.assertEqual(llmconfig.for_review(saved, "full")["selected_model"], "larger/model")
            self.assertEqual(saved["api_key"], "private-key")
            self.assertNotIn("api_key", out)
            with self.assertRaises(llmconfig.LLMError):
                llmconfig.review_model({"task": "full", "model_id": "other", "profile_id": None, "base_url": "http://override/v1"}, root)
            with self.assertRaises(llmconfig.LLMError):
                llmprofiles.prepare({"task": "full", "connection_id": "stale"}, root)

    def test_bad_url_model_config_and_share_link(self):
        for base in ("ftp://host", "http://user:secret@host/v1", "http://host:99999", "http://host/v1?api_key=secret", "http://host/\n"):
            with self.subTest(base=base), self.assertRaises(llmconfig.LLMError):
                llmconfig.validate(config(base))
        link = "http://localhost:8888/chat?run=1#run?v=1&model=unsloth%2FQwen3.5-0.8B-GGUF&ggufVariant=Q8_0&kvCacheDtype=q8_0"
        imported = llmconfig.share_link(link)
        self.assertEqual(imported["base_url"], "http://localhost:8888/v1")
        self.assertEqual(imported["gguf_variant"], "Q8_0")
        self.assertEqual(imported["kv_cache_dtype"], "q8_0")
        self.assertEqual(imported["model_hint"], "unsloth/Qwen3.5-0.8B-GGUF")
        longer = llmconfig.share_link(link + "&customContextLength=20096&disableVision=true")
        self.assertEqual(longer["context_tokens"], 20096)
        self.assertIn("customContextLength=20096", longer["studio_link"])
        self.assertIn("disableVision=true", longer["studio_link"])


class ModelProfiles(unittest.TestCase):
    LINK = "http://localhost:8888/chat?run=1#run?v=1&model=served%2Fmodel&ggufVariant=Q4_1&kvCacheDtype=q4_1&customContextLength=8192&disableVision=true"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = self.directory.name
        body = dict(config("http://localhost:8888/v1"), adapter="unsloth-studio", key_action="replace")
        body.pop("format_version")
        llmconfig.save(body, self.root)
        self.saved = llmprofiles.save({"name": "Installed model", "link": self.LINK}, self.root)
        self.ident = self.saved["saved_profile"]

    def test_profiles_are_local_links_not_new_endpoints_and_preserve_credentials(self):
        self.assertNotIn("api_key", self.saved)
        self.assertEqual(llmconfig.load(self.root)["api_key"], "private-key")
        with self.assertRaises(llmconfig.LLMError):
            llmprofiles.save({"name": "Redirect", "link": self.LINK.replace("localhost:8888", "other:9999")}, self.root)
        with self.assertRaises(llmconfig.LLMError):
            llmprofiles.save({"name": "Unsupported", "link": self.LINK + "&llamaExtraArgs=evil"}, self.root)
        with self.assertRaises(llmconfig.LLMError):
            llmprofiles.apply({"profile_id": self.ident, "base_url": "http://other/v1"}, self.root)
        self.assertEqual(len(llmprofiles.save({"name": "Renamed", "link": self.LINK}, self.root)["model_profiles"]), 1)
        client = llmadapter.adapter(llmconfig.load(self.root))
        self.assertEqual(client._api().config["base_url"], "http://localhost:8888/api")

    def test_exact_installed_file_and_options_reach_native_load_and_are_verified(self):
        client = llmadapter.adapter(llmconfig.load(self.root))
        api = mock.Mock()
        api.request.side_effect = [
            {"cached": [{"repo_id": "served/model", "task": "text-generation"}]},
            {"variants": [{"quant": "Q4_1", "downloaded": True}]},
            {"path": "/installed/model-Q4_1.gguf", "is_dir": False},
            {"status": "success"},
            {"loaded": ["served/model"], "loading": [], "model_identifier": "/installed/model-Q4_1.gguf",
             "gguf_variant": "Q4_1", "cache_type_kv": "q4_1", "disable_vision": True, "context_length": 8192},
        ]
        with mock.patch.object(client, "_api", return_value=api), mock.patch.object(client, "request", return_value={"data": [{"id": "served/model", "loaded": True}]}), mock.patch.object(llmadapter, "adapter", return_value=client):
            out = llmprofiles.apply({"profile_id": self.ident}, self.root)
        payload = api.request.call_args_list[3].args[1]
        self.assertEqual(payload["model_path"], "/installed/model-Q4_1.gguf")
        self.assertEqual(payload["max_seq_length"], 8192)
        self.assertEqual(payload["cache_type_kv"], "q4_1")
        self.assertTrue(payload["disable_vision"])
        self.assertFalse(payload["trust_remote_code"])
        self.assertEqual(payload["speculative_type"], "off")
        self.assertNotIn("pending_profile", out)
        self.assertNotIn("/installed", json.dumps(out))
        self.assertNotIn("private-key", json.dumps(out))
        self.assertEqual(out["selected_profile"], self.ident)

    def test_missing_variant_never_calls_load_and_failure_remains_pending(self):
        client = llmadapter.adapter(llmconfig.load(self.root))
        api = mock.Mock()
        api.request.side_effect = [{"cached": [{"repo_id": "served/model"}]}, {"variants": [{"quant": "Q8_0", "downloaded": True}]}]
        with mock.patch.object(client, "_api", return_value=api), self.assertRaises(llmconfig.LLMError) as e:
            client.resolve_profile(self.saved["model_profiles"][0])
        self.assertEqual(e.exception.code, "variant-not-installed")
        self.assertFalse(any("load" in call.args[0] for call in api.request.call_args_list))
        info = llmconfig.share_link(self.LINK)
        with mock.patch.object(llmadapter, "adapter", return_value=client), mock.patch.object(client, "resolve_profile", return_value=(info, "/installed/model-Q4_1.gguf")), mock.patch.object(client, "load_profile", side_effect=llmconfig.LLMError("timeout", "Timed out.")), self.assertRaises(llmconfig.LLMError):
            llmprofiles.apply({"profile_id": self.ident}, self.root)
        pending = llmconfig.load(self.root)
        self.assertEqual(pending["pending_profile"], self.ident)
        with self.assertRaises(llmconfig.LLMError) as e:
            llmadapter.adapter(pending).generate_text([])
        self.assertEqual(e.exception.code, "model-profile-pending")
        restored = llmconfig.select_model({"selected_model": "served/model"}, self.root)
        self.assertNotIn("pending_profile", restored)


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
        with mock.patch("llmadapter.adapter") as generate, mock.patch("wavefile.held", return_value=False):
            out = sttjobs.use_review(self.token, self.job["review_evidence"]["source_sha256"], {})
            self.assertEqual(out["text"], self.panel)
            generate.assert_not_called()

    def test_failed_sentences_leave_whisper_intact_and_slot_free(self):
        cancellation = llmadapter.Cancellation()
        self.job.update(state=sttjobs.CORRECTING, llm_generation=1)
        c = config()
        with mock.patch("llmconfig.load", return_value=c), mock.patch("llmadapter.adapter") as adapter:
            adapter.return_value.generate_text.side_effect = llmconfig.LLMError("invalid-response", "Invalid response.")
            sttjobs._correct(self.job, c, cancellation, 1)
        self.assertEqual(self.job["state"], sttjobs.DONE)
        self.assertEqual(self.job["text"], self.panel)
        self.assertEqual(self.job["correction_result"]["failed_word_ids"], ["s0w1"])
        self.assertFalse(sttjobs.busy())

    def test_cancel_preserves_pending_asr_and_invalidates_late_results(self):
        token = llmadapter.Cancellation()
        self.job.update(state=sttjobs.CORRECTING, llm_cancel=token, llm_generation=1,
                        review_choice="llm", correction_result={"suggestions": []})
        sttjobs.cancel_review(self.token)
        self.assertTrue(token.event.is_set())
        self.assertEqual(self.job["state"], sttjobs.DONE, 'review tools remain usable after cancelling one tool')
        self.assertEqual(self.job["text"], self.panel)
        self.assertIsNone(self.job["correction_result"])
        self.assertEqual(self.job["llm_generation"], 2)
        self.assertFalse(sttjobs.busy())

    def test_a_connected_workspace_review_is_whole_unless_the_request_says_to_divide(self):
        c = config(); seen = llmconfig.revision(c); evidence_hash = self.job["review_evidence"]["source_sha256"]
        for divide, want in ((False, False), (True, True)):
            self.job.update(state=sttjobs.REVIEW_CHOICE, correction={}, review_choice=None)
            with mock.patch("llmconfig.load", return_value=c), mock.patch("llmconfig.for_review", side_effect=lambda cfg, task: cfg), \
                 mock.patch("asrworkspace.sandbox_status", return_value={"available": True}), mock.patch("sttjobs.threading.Thread") as thread, \
                 mock.patch("sttjobs._save_pending"):
                sttjobs.review(self.token, "llm", evidence_hash, seen, task="workspace", divide=divide)
                self.assertEqual(self.job["correction"]["divided"], want)
                run = thread.call_args.kwargs["args"]
            with mock.patch("asrworkspace.correct", return_value={"suggestions": [], "failed_word_ids": [], "uncertain_word_ids": [], "assessment": "kept_original",
                                                                   "reviewed_word_ids": []}) as correct, mock.patch("llmadapter.adapter"), \
                 mock.patch("llmconfig.load", return_value=c), mock.patch("llmconfig.for_review", side_effect=lambda cfg, task: cfg), mock.patch("sttjobs._save_pending"):
                sttjobs._correct(*run)
            self.assertEqual(correct.call_args.args[-1], want, "the choice reaches the workspace")
        # only true or false, and only a workspace can be divided
        self.job.update(state=sttjobs.REVIEW_CHOICE, correction={})
        with self.assertRaises(sttjobs.Refusal) as e:
            sttjobs.review(self.token, "llm", evidence_hash, seen, task="workspace", divide="yes")
        self.assertEqual(e.exception.code, "bad-review")
        with mock.patch("llmconfig.load", return_value=c), mock.patch("llmconfig.for_review", side_effect=lambda cfg, task: cfg), \
             mock.patch("sttjobs.threading.Thread"), mock.patch("sttjobs._save_pending"):
            sttjobs.review(self.token, "llm", evidence_hash, seen, task="full", divide=True)
        self.assertFalse(self.job["correction"]["divided"], "another method is not divided by it")

    def test_changed_source_hash_is_refused(self):
        with self.assertRaises(sttjobs.Refusal) as e:
            sttjobs.review(self.token, "whisper", "another-source")
        self.assertEqual(e.exception.code, "stale-review")

    def test_changed_connection_before_choice_sends_no_text(self):
        c = config()
        seen = llmconfig.revision(c)
        changed = dict(c, selected_model="another-model")
        with mock.patch("llmconfig.load", return_value=changed), mock.patch("llmadapter.adapter") as adapter:
            with self.assertRaises(sttjobs.Refusal) as e:
                sttjobs.review(self.token, "llm", self.job["review_evidence"]["source_sha256"], seen)
            self.assertEqual(e.exception.code, "settings-changed")
            adapter.assert_not_called()
        self.assertEqual(self.job["state"], sttjobs.REVIEW_CHOICE)
        self.assertEqual(self.job["text"], self.panel)


if __name__ == "__main__":
    unittest.main()
