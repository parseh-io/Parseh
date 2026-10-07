# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline copy/paste and dependency-free downloadable workspace contracts."""
import copy
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import asrcorrection as correction
import asrexternal
import asrworkspace
import llmconfig
import sttjobs
import sttpanel


def source(*texts, language="it"):
    segments = []
    for i, text in enumerate(texts or ("Loro anno detto ciao.",)):
        words = [{"text": word, "start": i * 5 + j * .3, "end": i * 5 + j * .3 + .2,
                  "score": .2 if word == "anno" else .9,
                  "asr_alternatives": [{"text": "hanno", "score": None, "sequence_score": -2.5,
                      "score_kind": "sequence_log_score"}] if word == "anno" else [],
                  "alternatives_available": word == "anno"}
                 for j, word in enumerate(text.split())]
        segments.append({"start": i * 5, "end": i * 5 + 4, "text": text, "asr_words": words})
    panel, _ = sttpanel.segments_to_panel(segments)
    return panel, correction.evidence(segments, panel, language)


class ExternalAnswers(unittest.TestCase):
    def test_three_prompt_contracts_keep_evidence_and_threshold(self):
        _, request = source()
        original = copy.deepcopy(request)
        for task in asrexternal.TASKS:
            with self.subTest(task=task):
                # a reasoning workspace puts its evidence in the prompt only when divided into prompts
                units = asrexternal.batches(request, task, divide=True)[0]
                text = asrexternal.prompt(request, task, units, divided=True)
                self.assertIn("Language: Italian (it).", text)
                self.assertIn("hanno", text)
                self.assertIn("sequence", text)
                self.assertIn("Never translate", text)
                self.assertNotIn("{{", text)
                self.assertLessEqual(len(text.encode("utf-8")), asrexternal.MAX_PROMPT)
        self.assertEqual(request, original)
        self.assertEqual(correction.LOW_SCORE, .5)

    def test_sentence_answers_offer_local_edits_without_applying_them(self):
        panel, request = source()
        for task in ("suspect", "full"):
            units = asrexternal.batches(request, task)[0]
            result = asrexternal.parse(request, task, units, "```text\nsentence0: Loro hanno detto ciao.\n```")
            self.assertEqual(result["suggestions"][0]["original"], "anno")
            self.assertIsNone(result["suggestions"][0]["candidates"][0]["confidence"])
            unchanged, _ = correction.apply(panel, request, result, {})
            self.assertEqual(unchanged, panel)
            edited, _ = correction.apply(panel, request, result, {"s0w1": 0})
            self.assertIn("Loro hanno detto ciao.", edited)
        empty = asrexternal.parse(request, "suspect", units, "sentence0: Loro anno detto ciao.")
        self.assertEqual(empty["suggestions"], [])

    def test_missing_and_invalid_sentence_do_not_lose_valid_sentences(self):
        _, request = source("Loro anno detto ciao.", "Loro anno detto ciao.")
        units = asrexternal.batches(request, "suspect")[0]
        result = asrexternal.parse(request, "suspect", units, "sentence0: Loro hanno detto ciao.")
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(result["failed_word_ids"], ["s1w1"])
        invalid = 'sentence0: Loro hanno detto ciao.\nsentence1: {"rewritten": "invalid answer format"}'
        result = asrexternal.parse(request, "suspect", units, invalid)
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(result["failed_word_ids"], ["s1w1"])
        for answer in ("sentence99: Wrong label.", "sentence0: Loro anno detto ciao.\nsentence0: Duplicate.",
                       "Here are the corrections:\nsentence0: Loro hanno detto ciao.", "", "x" * (asrexternal.MAX_ANSWER + 1), "\ud800"):
            with self.subTest(answer=answer[:40]), self.assertRaises(llmconfig.LLMError):
                asrexternal.parse(request, "suspect", units, answer)

    def test_unicode_and_missing_scores_in_whole_text_review(self):
        _, request = source("او به مدرسه رفت.", language="fa")
        for word in correction.index(request).values():
            word.update(asr_confidence=None, low_asr_score=False)
        units = asrexternal.batches(request, "full")[0]
        result = asrexternal.parse(request, "full", units, "sentence0: او به مدرسه رفت.")
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(len(result["reviewed_word_ids"]), 4)
        self.assertEqual(asrexternal.batches(request, "suspect"), [])

    def test_workspace_csv_is_validated_and_never_executed(self):
        _, request = source()
        units = asrexternal.batches(request, "workspace")[0]
        row = {"word_ids": "s0w1", "original": "anno", "replacement": "hanno", "reason": "Context, optionally supported by Whisper."}
        with mock.patch("asrworkspace.Workspace.python", side_effect=AssertionError("Must never execute pasted code")):
            result = asrexternal.parse(request, "workspace", units, asrworkspace._csv([row], asrworkspace.FIELDS))
        self.assertEqual(result["suggestions"][0]["candidates"][0]["text"], "hanno")
        self.assertEqual(result["failed_word_ids"], [])
        for rows in ([row, row], [dict(row, word_ids="unknown")], [dict(row, original="different")]):
            with self.assertRaises(llmconfig.LLMError):
                asrexternal.parse(request, "workspace", units, asrworkspace._csv(rows, asrworkspace.FIELDS))
        missing = asrexternal.parse(request, "workspace", units, "word_ids,original,replacement,reason\n")
        self.assertEqual(missing["failed_word_ids"], ["s0w1"])

    def test_a_row_that_keeps_whispers_word_is_an_answer_with_its_reason_and_confidence(self):
        # "the model looked and Whisper is right" and "the model could not tell" are answers the review shows;
        # only a word with no row is silence (it is a failure, to retry)
        _, request = source("Loro anno detto ciao e anno poi.")
        units = asrexternal.batches(request, "workspace")[0]
        self.assertEqual(asrexternal.workspace_files(request, units)["input/required.txt"].split(), ["s0w1", "s0w5"])
        def csv_of(rows):
            return asrworkspace._csv(rows, asrworkspace.FIELDS)
        change = {"word_ids": "s0w1", "original": "anno", "replacement": "hanno", "reason": "needs the verb", "confidence": "Sure"}
        agree = {"word_ids": "s0w5", "original": "anno", "replacement": "anno", "reason": "a year, as it should be", "confidence": "sure"}
        done = asrexternal.parse(request, "workspace", units, csv_of([change, agree]))
        self.assertEqual([(s["word_id"], s["rating"], s["reason"]) for s in done["suggestions"]], [("s0w1", "sure", "needs the verb")])
        self.assertEqual(done["kept"], [{"word_ids": ["s0w5"], "original": "anno", "rating": "sure", "reason": "a year, as it should be"}])
        self.assertEqual(done["failed_word_ids"], [])
        doubt = asrexternal.parse(request, "workspace", units, csv_of([dict(change, confidence="unsure"), dict(agree, confidence="unsure", reason="cannot tell")]))
        self.assertEqual((doubt["suggestions"][0]["rating"], doubt["kept"][0]["rating"], doubt["kept"][0]["reason"]), ("unsure", "unsure", "cannot tell"))
        # an answer without the column (older chatbots, older skills) is read, its rows unrated
        old = asrexternal.parse(request, "workspace", units, "word_ids,original,replacement,reason\ns0w1,anno,hanno,x\ns0w5,anno,anno,y\n")
        self.assertEqual((old["suggestions"][0]["rating"], old["kept"][0]["rating"]), (None, None))
        # a word with no row at all is still no answer, and a rating that is neither word is refused
        silent = asrexternal.parse(request, "workspace", units, csv_of([agree]))
        self.assertEqual((silent["failed_word_ids"], [k["word_ids"] for k in silent["kept"]]), (["s0w1"], [["s0w5"]]))
        with self.assertRaises(llmconfig.LLMError):
            asrexternal.parse(request, "workspace", units, csv_of([dict(change, confidence="maybe")]))
        # the sentence methods have no rows to keep
        self.assertEqual(asrexternal.parse(request, "suspect", asrexternal.batches(request, "suspect")[0], "sentence0: Loro hanno detto ciao e anno poi.")["kept"], [])

    def test_a_sentence_the_importer_refuses_says_why_for_each_of_its_words(self):
        _, request = source("Loro anno detto ciao e anno poi.", "Una frase pulita.")
        units = asrexternal.batches(request, "suspect")[0]
        arrow = asrexternal.parse(request, "suspect", units, "sentence0: Loro hanno detto ciao (anno \u2192 hanno)")
        self.assertEqual(sorted(arrow["failed_word_ids"]), ["s0w1", "s0w5"])
        self.assertEqual(set(arrow["failed_reasons"]), {"s0w1", "s0w5"})
        self.assertTrue(all("arrow" in say for say in arrow["failed_reasons"].values()), arrow["failed_reasons"])
        # the other sentence of the prompt was not answered at all, and that is the reason it says
        own = [u for u in units if u["sentence_id"] == "sentence0"]
        self.assertEqual(asrexternal.parse(request, "suspect", own, "sentence0: Loro hanno detto ciao e anno poi.")["failed_reasons"], {})
        words = asrexternal.workspace_files(request, asrexternal.batches(request, "workspace")[0])["input/required.txt"].split()
        silent = asrexternal.parse(request, "workspace", asrexternal.batches(request, "workspace")[0], "word_ids,original,replacement,reason,confidence\n")
        self.assertEqual(silent["failed_reasons"], {w: "the answer has no row for this word" for w in words})

    def test_workspace_zip_is_text_only_with_fixed_names(self):
        _, request = source()
        units = asrexternal.batches(request, "workspace")[0]
        with zipfile.ZipFile(io.BytesIO(asrexternal.bundle(request, units, asrexternal.prompt(request, "workspace", units)))) as archive:
            self.assertIn("parseh-review/PROMPT.txt", archive.namelist())
            self.assertIn("parseh-review/review.py", archive.namelist())
            self.assertIn("parseh-review/input/required.txt", archive.namelist())
            self.assertIn("parseh-review/README.txt", archive.namelist())
            self.assertTrue(all(name.startswith("parseh-review/") and ".." not in name for name in archive.namelist()))
            text = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())
            self.assertIn("Loro [1] detto ciao.", text)
            self.assertNotIn("0:00", text)
            self.assertNotIn("/private/", text)
            self.assertNotIn("api_key", text)

    def test_extracted_workspace_checker_runs_without_dependencies_and_distinguishes_completion(self):
        _, request = source()
        units = asrexternal.batches(request, 'workspace')[0]
        content = asrexternal.bundle(request, units, asrexternal.prompt(request, 'workspace', units))
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                archive.extractall(folder)
            root = Path(folder) / 'parseh-review'
            self.assertEqual((root / 'input/required.txt').read_text(), 's0w1')
            self.assertEqual(len((root / 'input/targets.txt').read_text().split()), 4)
            def check(*args):
                return subprocess.run([sys.executable, '-I', '-S', '-B', 'review.py', '--check', *args],
                                      cwd=root, capture_output=True, text=True, timeout=10)
            draft = check()
            self.assertEqual(draft.returncode, 0, draft.stderr)
            self.assertIn('s0w1', draft.stdout)
            self.assertNotEqual(check('--complete').returncode, 0)
            row = {'word_ids': 's0w1', 'original': 'anno', 'replacement': 'hanno', 'reason': 'Synthetic fixture.'}
            (root / 'out/result.csv').write_text(asrworkspace._csv([row], asrworkspace.FIELDS), encoding='utf-8')
            complete = check('--complete')
            self.assertEqual(complete.returncode, 0, complete.stderr)
            # The helper checks all rows, even after an otherwise valid target.
            unsafe = dict(row, word_ids='s0w2', original='detto', replacement='detto!')
            (root / 'out/result.csv').write_text(asrworkspace._csv([row, unsafe], asrworkspace.FIELDS), encoding='utf-8')
            self.assertNotEqual(check('--complete').returncode, 0)
            with self.assertRaises(llmconfig.LLMError):
                asrexternal.parse(request, 'workspace', units, (root / 'out/result.csv').read_text())
            # Uploaded evidence files cannot authorize additional edits. Server
            # revalidates the immutable request, not the mutable extracted ZIP.
            tampered = dict(row, original='other')
            (root / 'input/words.csv').write_text('tampered evidence', encoding='utf-8')
            with self.assertRaises(llmconfig.LLMError):
                asrexternal.parse(request, 'workspace', units, asrworkspace._csv([tampered], asrworkspace.FIELDS))

    def test_workspace_join_and_selected_span_are_validated(self):
        panel, request = source('A note book arrived.', language='en')
        units = asrexternal.batches(request, 'workspace')[0]
        row = {'word_ids': 's0w1 s0w2', 'original': 'note book', 'replacement': 'notebook', 'reason': 'Split word.'}
        answer = asrworkspace._csv([row], asrworkspace.FIELDS)
        result = asrexternal.parse(request, 'workspace', units, answer)
        edited, _ = correction.apply(panel, request, result, {'s0w1': 0})
        self.assertEqual(edited, panel.replace('note book', 'notebook'))
        selected = asrexternal.batches(request, 'workspace', ['s0w1'])[0]
        with self.assertRaises(llmconfig.LLMError):
            asrexternal.parse(request, 'workspace', selected, answer)

    def test_hint_heavy_batches_cover_source_words_once(self):
        _, request = source(" ".join("anno" for _ in range(48)))
        for word in correction.index(request).values():
            word["asr_alternatives"] = [{"text": "a" * 400, "score": None} for _ in range(10)]
        batches = asrexternal.batches(request, "suspect")
        all_ids = [ident for batch in batches for ident in asrexternal.ids(batch)]
        self.assertEqual(len(all_ids), 48)
        self.assertEqual(len(set(all_ids)), 48)
        for batch in batches:
            self.assertLessEqual(len(asrexternal.prompt(request, "suspect", batch).encode("utf-8")), asrexternal.MAX_PROMPT)


class WorkspaceIsNotDividedUnlessAsked(unittest.TestCase):
    """The workspace's files hold the whole transcript, which is what a workspace is for: it is handed
    to the chatbot at once, and dividing it into prompts is an option for a chatbot with no file tools."""

    def long_request(self, captions=60):
        return source(*("Loro anno detto ciao e poi anno detto di nuovo %d." % n for n in range(captions)))[1]

    def test_by_default_one_prompt_holds_every_word_and_the_others_are_still_divided(self):
        request = self.long_request()
        every = {ident for ident, word in correction.index(request).items() if word["reviewable"]}
        whole = asrexternal.batches(request, "workspace")
        self.assertEqual(len(whole), 1)
        self.assertEqual(asrexternal.ids(whole[0]), every)
        divided = asrexternal.batches(request, "workspace", divide=True)
        self.assertGreater(len(divided), 1)
        self.assertEqual(asrexternal.ids([u for batch in divided for u in batch]), asrexternal.ids(whole[0]))
        for task in ("suspect", "full"):
            self.assertGreater(len(asrexternal.batches(request, task)), 1, task)
            self.assertEqual(len(asrexternal.batches(request, task, divide=False)), len(asrexternal.batches(request, task, divide=True)), task)
        self.assertEqual(asrexternal.batches(source("")[1], "workspace"), [])

    def test_the_whole_prompt_says_where_the_evidence_is_and_repeats_none_of_it(self):
        request = self.long_request(400)
        units = asrexternal.batches(request, "workspace")[0]
        text = asrexternal.prompt(request, "workspace", units)
        self.assertLessEqual(len(text.encode("utf-8")), asrexternal.MAX_PROMPT)
        self.assertIn("What is in the workspace follows.", text)
        self.assertNotIn("Current batch", text)
        self.assertNotIn("this batch", text)
        self.assertNotIn("word_id,", text)
        self.assertIn("First skim the whole transcript", text)
        self.assertIn("None of it is repeated in this prompt", text)
        self.assertNotIn("{{", text)
        # the same evidence, divided into prompts, is in each prompt and each batch's words are its own
        batch = asrexternal.batches(request, "workspace", divide=True)[0]
        piece = asrexternal.prompt(request, "workspace", batch, divided=True)
        self.assertIn("Current batch and read-only evidence follow.", piece)
        self.assertIn("this batch", piece)
        self.assertNotIn("What is in the workspace follows.", piece)

    def test_the_zip_of_the_whole_holds_all_of_it_and_a_csv_for_every_entry_is_accepted(self):
        request = self.long_request(40)
        units = asrexternal.batches(request, "workspace")[0]
        files = asrexternal.workspace_files(request, units)
        required = files["input/required.txt"].split()
        self.assertEqual(len(required), sum(1 for u in units for w in u["targets"] if correction.suspect(w)))
        self.assertGreater(len(required), 40)
        self.assertEqual(files["input/allowed.txt"].split(), sorted(asrexternal.ids(units), key=files["input/allowed.txt"].split().index))
        with zipfile.ZipFile(io.BytesIO(asrexternal.bundle(request, units, asrexternal.prompt(request, "workspace", units)))) as archive:
            names = {name.split("/", 1)[1] for name in archive.namelist()}
            words = archive.read("parseh-review/input/words.csv").decode("utf-8")
        self.assertLessEqual({"PROMPT.txt", "review.py", "input/required.txt", "input/words.csv", "out/result.csv"}, names)
        self.assertEqual(words.count("\n") - 1, sum(len(u["words"]) for u in units))
        rows = [{"word_ids": ident, "original": correction.index(request)[ident]["text"], "replacement": "hanno", "reason": "x"} for ident in required]
        done = asrexternal.parse(request, "workspace", units, asrworkspace._csv(rows, asrworkspace.FIELDS))
        self.assertEqual(len(done["suggestions"]), len(required))
        self.assertEqual(done["failed_word_ids"], [])


class ExternalJobs(unittest.TestCase):
    def setUp(self):
        private = tempfile.TemporaryDirectory()
        self.addCleanup(private.cleanup)
        videos = mock.patch('ytpages.VIDEOS', private.name)
        videos.start(); self.addCleanup(videos.stop)
        self.panel, self.request = source(*("Loro anno detto ciao." for _ in range(13)))
        self.token = "ABCDEFGHIJKLMNOP"
        self.job = {"id": self.token, "kind": "film", "source": {"kind": "film", "path": "/private/film.mp4"},
                    "lang": "it", "model": "large-v3-turbo", "state": sttjobs.REVIEW_CHOICE,
                    "review_evidence": self.request, "review_choice": None, "correction": {},
                    "text": self.panel, "facts": {}, "cancelled": False, "finished": time.time(),
                    "device": "cpu", "fell_back": False, "words": None, "notes": [], "warning": ""}
        for patch in (mock.patch.dict(sttjobs.JOBS, {self.token: self.job}, clear=True),
                      mock.patch("wavefile.held", return_value=False), mock.patch("wordtimes.load", return_value=None),
                      mock.patch("llmadapter.adapter", side_effect=AssertionError("No endpoint request")),
                      mock.patch("llmconfig.load", return_value=None)):
            patch.start(); self.addCleanup(patch.stop)
        self.hash = self.request["source_sha256"]

    def test_import_and_finish_leave_source_intact_until_explicit_use(self):
        view = sttjobs.external_start(self.token, self.hash, "suspect")
        ext = view["review"]["external"]
        self.assertEqual(ext["batches"], 2)
        self.assertNotIn(self.job["state"], sttjobs.ACTIVE)
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.use_review(self.token, self.hash, {})
        view = sttjobs.external_action(self.token, self.hash, ext["id"], "answer", 0, "sentence0: Loro hanno detto ciao.")
        self.assertEqual(self.job["text"], self.panel)
        self.assertEqual(len(view["review"]["result"]["suggestions"]), 1)
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.external_action(self.token, self.hash, ext["id"], "answer", 1, "An explanation instead of the answer")
        self.assertEqual(len(self.job["correction_result"]["suggestions"]), 1)
        view = sttjobs.external_action(self.token, self.hash, ext["id"], "finish")
        self.assertIn("s12w1", view["review"]["result"]["failed_word_ids"])
        used = sttjobs.use_review(self.token, self.hash, {"s0w1": 0})
        self.assertIn("Loro hanno detto ciao.", used["text"])
        self.assertEqual(self.job["text"], self.panel)
        retry = sttjobs.external_start(self.token, self.hash, "suspect", ["s12w1"])
        self.assertEqual(len(retry["review"]["result"]["suggestions"]), 1)

    def test_a_workspace_review_is_one_prompt_unless_divided_and_the_choice_stays_with_its_session(self):
        whole = sttjobs.external_start(self.token, self.hash, "workspace")["review"]["external"]
        self.assertEqual((whole["batches"], whole["divided"]), (1, False))
        self.assertIn("What is in the workspace follows.", whole["prompt"])
        self.assertEqual(whole["words_total"], 13 * 4)
        files = sttjobs.external_files(self.token, self.hash, whole["id"], 0)
        with zipfile.ZipFile(io.BytesIO(files)) as archive:
            self.assertIn("What is in the workspace follows.", archive.read("parseh-review/PROMPT.txt").decode("utf-8"))
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.external_files(self.token, self.hash, whole["id"], 1)
        # an answer goes back to the same undivided prompt, and it finishes the review
        view = sttjobs.external_action(self.token, self.hash, whole["id"], "answer", 0, "word_ids,original,replacement,reason\ns0w1,anno,hanno,x\n")
        self.assertTrue(view["review"]["external"]["finished"] or view["review"]["external"]["submitted"] == [0])
        divided = sttjobs.external_start(self.token, self.hash, "workspace", None, True)["review"]["external"]
        self.assertTrue(divided["divided"])
        self.assertGreater(divided["batches"], 1)
        self.assertIn("Current batch and read-only evidence follow.", divided["prompt"])
        files = sttjobs.external_files(self.token, self.hash, divided["id"], 1)
        with zipfile.ZipFile(io.BytesIO(files)) as archive:
            self.assertIn("Current batch and read-only evidence follow.", archive.read("parseh-review/PROMPT.txt").decode("utf-8"))
        # the other methods take no such choice: they are divided either way
        for choice in (False, True):
            view = sttjobs.external_start(self.token, self.hash, "suspect", None, choice)["review"]["external"]
            self.assertEqual((view["batches"], view["divided"]), (2, True))

    def test_the_kept_words_of_each_prompt_are_merged_and_replaced_like_the_proposals(self):
        whole = sttjobs.external_start(self.token, self.hash, "workspace", None, True)["review"]["external"]
        self.assertGreater(whole["batches"], 1)
        first = sttjobs.external_files(self.token, self.hash, whole["id"], 0)
        rows = "word_ids,original,replacement,reason,confidence\ns0w1,anno,anno,fine,sure\ns1w1,anno,hanno,verb,unsure\n"
        view = sttjobs.external_action(self.token, self.hash, whole["id"], "answer", 0, rows)
        out = view["review"]["result"]
        self.assertEqual([k["word_ids"] for k in out["kept"]], [["s0w1"]])
        self.assertEqual([(s["word_id"], s["rating"]) for s in out["suggestions"]], [("s1w1", "unsure")])
        # importing the same prompt again replaces its rows; the other prompts' stay
        again = sttjobs.external_action(self.token, self.hash, whole["id"], "answer", 0,
                                        "word_ids,original,replacement,reason,confidence\ns0w1,anno,hanno,changed my mind,sure\ns1w1,anno,anno,fine,sure\n")["review"]["result"]
        self.assertEqual(again["kept"], [{"word_ids": ["s1w1"], "original": "anno", "rating": "sure", "reason": "fine"}])
        self.assertEqual([(s["word_id"], s["rating"]) for s in again["suggestions"]], [("s0w1", "sure")])

    def test_three_methods_work_without_config_and_bad_prepare_is_atomic(self):
        for task in asrexternal.TASKS:
            view = sttjobs.external_start(self.token, self.hash, task)
            self.assertIn("asr-" + task, view["review"]["external"]["prompt"])
        original = copy.deepcopy(self.job)
        with mock.patch("asrexternal.prompt", side_effect=llmconfig.LLMError("too-large", "Oversized prompt.")):
            with self.assertRaises(sttjobs.Refusal):
                sttjobs.external_start(self.token, self.hash, "full")
        self.assertEqual(self.job["correction_result"], original["correction_result"])
        self.assertEqual(self.job["external_review"]["id"], original["external_review"]["id"])

    def test_stale_session_source_and_cancel_preserve_whisper(self):
        ext = sttjobs.external_start(self.token, self.hash, "workspace")["review"]["external"]
        for session, hash_value in ((None, self.hash), ("replaced", self.hash), (ext["id"], "changed")):
            with self.assertRaises(sttjobs.Refusal):
                sttjobs.external_action(self.token, hash_value, session, "finish")
        with mock.patch("sttjobs._review_source_current", return_value=False), self.assertRaises(sttjobs.Refusal):
            sttjobs.external_files(self.token, self.hash, ext["id"], 0)
        cancelled = sttjobs.external_action(self.token, self.hash, ext["id"], "cancel")
        self.assertIsNone(cancelled["review"]["external"])
        self.assertEqual(cancelled["text"], self.panel)
        self.assertEqual(self.job["state"], sttjobs.REVIEW_CHOICE)

    def test_open_external_review_refreshes_retention_without_inference(self):
        ext = sttjobs.external_start(self.token, self.hash, "full")["review"]["external"]
        before = self.job["finished"]
        with mock.patch("sttjobs._now", return_value=before + 600):
            sttjobs.external_action(self.token, self.hash, ext["id"], "keep-alive")
        self.assertEqual(self.job["finished"], before + 600)
        self.assertNotIn(self.job["state"], sttjobs.ACTIVE)

    def test_pasted_diagnostics_redact_saved_credentials(self):
        ext = sttjobs.external_start(self.token, self.hash, "workspace")["review"]["external"]
        key = 'private-"key'
        answer = asrworkspace._csv([{"word_ids": "s0w1", "original": "anno", "replacement": "hanno", "reason": key}], asrworkspace.FIELDS)
        with mock.patch("llmconfig.load", return_value={"api_key": key}):
            sttjobs.external_action(self.token, self.hash, ext["id"], "answer", 0, answer)
        self.assertNotIn(key, str(self.job["llm_diagnostics"]))
        self.assertNotIn(key, json.dumps(self.job["llm_diagnostics"], ensure_ascii=False))
        self.assertIn("[redacted credential]", str(self.job["llm_diagnostics"]))


if __name__ == "__main__":
    unittest.main()
