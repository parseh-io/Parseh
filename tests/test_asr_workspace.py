# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline workspace, source-span and completion contracts."""
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import asrcorrection
import asrworkspace
import llmadapter
import llmconfig


def evidence():
    text = "Thay anno detto ciao."
    words = [{"text": t, "start": i, "end": i + .5, "score": .2 if t == "anno" else .9}
             for i, t in enumerate(text.split())]
    return text, asrcorrection.evidence([{"text": text, "start": 0, "end": 4, "words": words}], text, "it")


def config():
    return {"format_version": 1, "provider_preset": "unsloth", "adapter": "unsloth-studio",
            "base_url": "http://localhost:8888/v1", "selected_model": "coder",
            "api_key": "dummy-private-key", "timeout_seconds": 60}


class WorkspaceContracts(unittest.TestCase):
    def test_resolve_can_join_suspect_with_confident_neighbor(self):
        text = "A note book arrived."
        raw = [{"text": text, "start": 0, "end": 4, "words": [
            {"text": word, "score": .2 if word == 'note' else .95, "start": i, "end": i + .5}
            for i, word in enumerate(text.split())]}]
        request = asrcorrection.evidence(raw, text, 'en'); original = copy.deepcopy(request)
        phases = []
        def phase(workspace, request, adapter, name, allowed, context, diagnostic, key):
            phases.append(name)
            rows = [] if name == 'skim' else [{"word_ids": "s0w1 s0w2", "original": "note book",
                    "replacement": "notebook", "reason": "One word split into two source pieces."}]
            self.assertIn('s0w2', allowed)
            (workspace.root / 'out/result.csv').write_text(asrworkspace._csv(rows, asrworkspace.FIELDS))
            return asrworkspace._proposals(workspace.root, request, allowed, workspace.targets)
        progress = []
        with mock.patch('asrworkspace.sandbox_status', return_value={'available': True}), mock.patch('asrworkspace._phase', side_effect=phase):
            result = asrworkspace.correct(request, object(), llmadapter.Cancellation(), lambda *p: progress.append(p))
        self.assertEqual(phases, ['skim', 'resolve'])
        self.assertEqual(result['suggestions'][0]['word_ids'], ['s0w1', 's0w2'])
        self.assertEqual(result['failed_word_ids'], [])
        self.assertEqual(progress[-1][:2], (4, 4))
        self.assertEqual(request, original)
        edited, changed = asrcorrection.apply(text, request, result, {'s0w1': 0})
        self.assertEqual(edited, 'A notebook arrived.'); self.assertTrue(changed)

    def test_skim_join_is_not_overwritten_by_resolve(self):
        text = 'A note book arrived.'
        request = asrcorrection.evidence([{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .2 if word == 'note' else .95}
            for word in text.split()]}], text, 'en')
        phases = []
        def phase(workspace, request, adapter, name, allowed, context, diagnostic, key):
            phases.append(name); self.assertEqual(name, 'skim')
            row = {'word_ids': 's0w1 s0w2', 'original': 'note book', 'replacement': 'notebook', 'reason': 'Synthetic split word.'}
            (workspace.root / 'out/result.csv').write_text(asrworkspace._csv([row], asrworkspace.FIELDS))
            return asrworkspace._proposals(workspace.root, request, allowed, workspace.targets)
        with mock.patch('asrworkspace.sandbox_status', return_value={'available': True}), mock.patch('asrworkspace._phase', side_effect=phase):
            result = asrworkspace.correct(request, object(), llmadapter.Cancellation(), lambda *p: None)
        self.assertEqual(phases, ['skim']); self.assertEqual(len(result['suggestions']), 1)
        self.assertEqual(result['words_reviewed'], result['words_total'])
        self.assertNotIn('s0w1', result['uncertain_word_ids'])

    def test_span_must_stay_within_selected_words_and_include_phase_target(self):
        text = 'A note book arrived.'
        request = asrcorrection.evidence([{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .2 if word == 'note' else .95}
            for word in text.split()]}], text, 'en')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'out').mkdir()
            row = {'word_ids': 's0w1 s0w2', 'original': 'note book', 'replacement': 'notebook', 'reason': 'Synthetic split word.'}
            (root / 'out/result.csv').write_text(asrworkspace._csv([row], asrworkspace.FIELDS))
            for allowed, targets in [({'s0w1'}, {'s0w1'}), ({'s0w1', 's0w2', 's0w3'}, {'s0w3'})]:
                with self.assertRaises(llmconfig.LLMError):
                    asrworkspace._proposals(root, request, allowed, targets)

    def test_downloaded_helper_checks_adjacent_ids_and_copies_exact_original(self):
        text = 'A note book arrived.'
        request = asrcorrection.evidence([{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .2 if word == 'note' else .95}
            for word in text.split()]}], text, 'en')
        _, suspects, words, captions, _ = asrworkspace._files(request)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'input').mkdir(); (root / 'out').mkdir()
            for name, rows, fields in [('words', words, asrworkspace.WORD_FIELDS),
                                       ('suspects', suspects, asrworkspace.SUSPECT_FIELDS),
                                       ('captions', captions, ['segment_id', 'text']), ('skim', [], asrworkspace.FIELDS)]:
                (root / 'input' / (name + '.csv')).write_text(asrworkspace._csv(rows, fields))
            (root / 'input/allowed.txt').write_text('s0w0 s0w1 s0w2 s0w3')
            (root / 'input/targets.txt').write_text('s0w1')
            shutil.copyfile(ROOT / 'lib/asrskill/parseh-asr-workspace/scripts/review.py', root / 'review.py')
            def save(ids):
                code = 'import sys; sys.path.insert(0, %r); import review; review.save([(%r, "notebook", "Split word")])' % (folder, ids)
                return subprocess.run([sys.executable, '-I', '-c', code], cwd=root, capture_output=True, text=True)
            self.assertEqual(save('s0w1 s0w2').returncode, 0)
            proposals, _ = asrworkspace._proposals(root, request, {'s0w0', 's0w1', 's0w2', 's0w3'}, {'s0w1'})
            self.assertEqual(proposals[0]['original'], 'note book')
            for ids in ('s0w1 s0w3', 's0w2 s0w1', 's0w1 s0w1', 's0w2'):
                self.assertNotEqual(save(ids).returncode, 0)

    def test_resolve_finish_requires_targets_not_all_adjacent_context_words(self):
        text = 'A note book arrived.'
        request = asrcorrection.evidence([{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .2 if word == 'note' else .95}
            for word in text.split()]}], text, 'en')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'out').mkdir()
            workspace = asrworkspace.Workspace(root, llmadapter.Cancellation()); workspace.targets = {'s0w1'}
            def tool(name, args):
                workspace.ran = True
                row = {'word_ids': 's0w1 s0w2', 'original': 'note book', 'replacement': 'notebook', 'reason': 'Synthetic split word.'}
                (root / 'out/result.csv').write_text(asrworkspace._csv([row], asrworkspace.FIELDS))
                return 'CSV saved.'
            adapter = mock.Mock()
            adapter.agent_turn.return_value = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'write', 'type': 'function', 'function': {'name': 'python', 'arguments': '{"code":"write CSV"}'}},
                {'id': 'finish', 'type': 'function', 'function': {'name': 'finish_review', 'arguments': '{}'}}]}
            with mock.patch.object(workspace, 'call', side_effect=tool):
                proposals, seen = asrworkspace._phase(workspace, request, adapter, 'resolve',
                    {'s0w0', 's0w1', 's0w2', 's0w3'}, 8192, None, 'region0')
            self.assertEqual(seen, {'s0w1', 's0w2'})
            self.assertEqual(proposals[0]['candidates'][0]['text'], 'notebook')
            self.assertEqual(adapter.agent_turn.call_count, 1)

    def test_blanks_keep_threshold_scores_and_missing_alternatives(self):
        _, request = evidence()
        original = copy.deepcopy(request)
        transcript, rows, words, captions, slots = asrworkspace._files(request)
        self.assertIn("Thay [1] detto ciao.", transcript)
        self.assertNotIn("0:00", transcript)
        self.assertEqual(rows[0]["whisper_score"], .2)
        self.assertIn("alternatives unavailable", rows[0]["whisper_hints"])
        self.assertEqual(slots, {"s0w1": "1"})
        self.assertEqual(request, original)
        self.assertEqual(asrcorrection.LOW_SCORE, .5)
        request["segments"][0]["words"][0].update(dictionary_miss=True, asr_confidence=None)
        _, rows, _, _, _ = asrworkspace._files(request)
        self.assertEqual(rows[0]["whisper_score"], "unavailable")
        self.assertTrue(rows[0]["dictionary_miss"])

    def test_unicode_spans_and_unavailable_scores_remain_explicit(self):
        text = "彼は 学校に 行く。"
        segment = {"text": text, "start": 0, "end": 3, "words": [
            {"text": "彼は", "score": None}, {"text": "学校に", "score": .4}, {"text": "行く。", "score": .9}]}
        request = asrcorrection.evidence([segment], text, "ja")
        transcript, rows, _, _, _ = asrworkspace._files(request)
        self.assertIn("彼は [1] 行く。", transcript)
        self.assertEqual(rows[0]["guess"], "学校に")
        self.assertIsNone(request["segments"][0]["words"][0]["asr_confidence"])

    def test_external_tools_request_reasoning_without_endpoint_host_tools(self):
        client = llmadapter.UnslothStudio(config())
        call = {"id": "call_1", "type": "function", "function": {"name": "python", "arguments": '{"code":"print(1)"}'}}
        response = {"choices": [{"finish_reason": "tool_calls", "message": {"content": None,
                     "tool_calls": [call], "reasoning_content": "dummy-private-key"}}]}
        traces = []
        with mock.patch.object(client, "request", return_value=response) as request:
            answer = client.agent_turn([{"role": "user", "content": "Synthetic data"}], asrworkspace.TOOLS[1:], observe=traces.append)
        payload = request.call_args.args[1]
        self.assertTrue(payload["enable_thinking"])
        self.assertFalse(payload["enable_tools"])
        self.assertFalse(payload["mcp_enabled"])
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(answer["tool_calls"], [call])
        self.assertNotIn("dummy-private-key", json.dumps(traces))
        response["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "terminal"
        with mock.patch.object(client, "request", return_value=response), self.assertRaises(llmconfig.LLMError):
            client.agent_turn([], asrworkspace.TOOLS[1:])

    def test_csv_rejects_unknown_duplicate_and_mismatched_spans(self):
        _, request = evidence()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "out").mkdir()
            def write(rows):
                (root / "out/result.csv").write_text(asrworkspace._csv(rows, asrworkspace.FIELDS), encoding="utf-8")
            row = {"word_ids": "s0w1", "original": "anno", "replacement": "hanno", "reason": "Fits the sentence."}
            write([row]); proposals, seen = asrworkspace._proposals(root, request, {"s0w1"})
            self.assertEqual(proposals[0]["candidates"][0]["text"], "hanno")
            self.assertIsNone(proposals[0]["error_likelihood"])
            for rows in ([row, row], [dict(row, word_ids="s99w0")], [dict(row, original="other")], [dict(row, replacement="hanno!")]):
                write(rows)
                with self.assertRaises(llmconfig.LLMError):
                    asrworkspace._proposals(root, request, {"s0w1"})

    def test_csv_checker_and_server_reject_unsafe_rows_before_returning_proposals(self):
        text = 'ما "کو چیکه" گفتیم.'
        request = asrcorrection.evidence([{'text': text, 'start': 0, 'end': 4, 'words': [
            {'text': word, 'score': .2, 'start': i, 'end': i + .5}
            for i, word in enumerate(text.split())]}], text, 'fa')
        words = asrcorrection.index(request)
        allowed = set(words)
        valid = {'word_ids': 's0w1 s0w2', 'original': '"کو چیکه"', 'replacement': '"کوچیکه"',
                 'reason': 'Synthetic split-word fixture.'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'out').mkdir()
            def proposals(rows, **kwargs):
                (root / 'out/result.csv').write_text(asrworkspace._csv(rows, asrworkspace.FIELDS), encoding='utf-8')
                return asrworkspace._proposals(root, request, allowed, {'s0w1'}, **kwargs)
            edits, seen = proposals([valid])
            self.assertEqual(seen, {'s0w1', 's0w2'})
            self.assertEqual(edits[0]['original'], valid['original'])
            legacy, _ = proposals([dict(valid, reason='')])
            self.assertEqual(legacy[0]['reason'], '')
            for rows in ([valid, dict(valid, word_ids='s0w2', original='چیکه"', replacement='چیکه"')],
                         [dict(valid, replacement='کوچیکه')], [dict(valid, replacement='"کو\nچیکه"')],
                         [dict(valid, reason='\x01')], [dict(valid, reason='x' * 501)],
                         [dict(valid, original='"کو\u200cچیکه"')],
                         [valid, dict(valid, word_ids='s0w0', original='ما', replacement='آن')]):
                with self.subTest(rows=rows), self.assertRaises(llmconfig.LLMError):
                    proposals(rows)
            proposals([valid], required={'s0w1'}, complete=True)
            with self.assertRaises(llmconfig.LLMError):
                proposals([valid], required={'s0w1', 's0w3'}, complete=True)

    def test_finish_rechecks_missing_targets_and_does_not_trust_prior_python_success(self):
        _, request = evidence()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'out').mkdir()
            workspace = asrworkspace.Workspace(root, llmadapter.Cancellation())
            workspace.ran = True; workspace.targets = {'s0w1'}
            (root / 'out/result.csv').write_text(asrworkspace._csv([], asrworkspace.FIELDS), encoding='utf-8')
            adapter = mock.Mock()
            adapter.agent_turn.return_value = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'finish', 'type': 'function', 'function': {'name': 'finish_review', 'arguments': '{}'}}]}
            with self.assertRaises(llmconfig.LLMError) as error:
                asrworkspace._phase(workspace, request, adapter, 'resolve', {'s0w1'}, 8192, None, 'region0')
            self.assertEqual(error.exception.code, 'tool-limit')
            self.assertTrue(any('s0w1' in json.dumps(call.args[0]) for call in adapter.agent_turn.call_args_list))
            # The same empty edit list is valid for a skim phase; numbering
            # coverage applies only to resolution, never unrelated context.
            edits, seen = asrworkspace._phase(workspace, request, adapter, 'skim', {'s0w1'}, 8192, None, 'region0')
            self.assertEqual(edits, []); self.assertEqual(seen, set())

    def test_two_pass_order_failure_salvage_progress_and_cleanup(self):
        text, request = evidence()
        original = copy.deepcopy(request)
        calls, folders, progress = [], [], []
        def phase(workspace, request, adapter, name, allowed, context, diagnostic, key):
            calls.append(name); folders.append(workspace.root)
            self.assertIn("[1]", (workspace.root / "input/transcript.txt").read_text())
            required = (workspace.root / 'input/required.txt').read_text().split()
            self.assertEqual(set(required), workspace.targets if name == 'resolve' else set())
            self.assertTrue((workspace.root / 'review.py').is_file())
            row = {"word_ids": "s0w0", "original": "Thay", "replacement": "They", "reason": "Synthetic fixture"} if name == "skim" else {
                  "word_ids": "s0w1", "original": "anno", "replacement": "hanno", "reason": "Synthetic fixture"}
            (workspace.root / "out/result.csv").write_text(asrworkspace._csv([row], asrworkspace.FIELDS))
            workspace.ran = True
            if name == "resolve":
                raise llmconfig.LLMError("timeout", "Synthetic interrupted phase.")
            return asrworkspace._proposals(workspace.root, request, allowed)
        with mock.patch("asrworkspace.sandbox_status", return_value={"available": True}), mock.patch("asrworkspace._phase", side_effect=phase):
            result = asrworkspace.correct(request, object(), llmadapter.Cancellation(), lambda *p: progress.append(p))
        self.assertEqual(calls, ["skim", "resolve"])
        self.assertEqual(len(result["suggestions"]), 2)
        self.assertEqual(progress[-1][:2], (4, 4))
        self.assertEqual(result["failed_word_ids"], [])
        # the row written before the run broke is used as it stood, and ITS WORD SAYS SO (the clean skim row does not)
        self.assertEqual(list(result["allowances"]), ["s0w1"])
        self.assertTrue(any("Synthetic interrupted phase" in say for say in result["allowances"]["s0w1"]), result["allowances"])
        self.assertTrue(all(not p.exists() for p in folders))
        self.assertEqual(request, original)
        panel, changed = asrcorrection.apply(text, request, result, {"s0w0": 0, "s0w1": 0})
        self.assertEqual(panel, "They hanno detto ciao.")
        self.assertTrue(changed)

    def test_the_workspace_is_one_region_unless_asked_to_be_divided(self):
        # THE WHOLE TRANSCRIPT IS ONE REGION (as a workspace is for); small regions are the option, and are what this always did
        text = "Thay anno detto ciao."
        captions = [{"text": text, "start": n * 5, "end": n * 5 + 4, "words": [
            {"text": t, "start": n * 5 + i, "end": n * 5 + i + .5, "score": .2 if t == "anno" else .9} for i, t in enumerate(text.split())]}
            for n in range(60)]
        request = asrcorrection.evidence(captions, "\n".join(text for _ in captions), "it")
        for divide in (False, True):
            seen = []
            def phase(workspace, request, adapter, name, allowed, context, diagnostic, key):
                seen.append((name, key, len(allowed), workspace.divided, workspace.seconds, workspace.turns,
                             len((workspace.root / "input/targets.txt").read_text().split())))
                return [], set()
            with mock.patch("asrworkspace.sandbox_status", return_value={"available": True}), mock.patch("asrworkspace._phase", side_effect=phase):
                asrworkspace.correct(request, object(), llmadapter.Cancellation(), lambda *p: None, divide=divide)
            keys = {key for _, key, *_ in seen}
            if divide:
                self.assertGreater(len(keys), 1, "divided: several regions, as before")
                self.assertTrue(all(row[3] is True and row[4] == 300 and row[5] == 12 for row in seen), "each with the budget it always had")
            else:
                self.assertEqual(keys, {"region0"}, "undivided: one region")
                self.assertEqual([row[0] for row in seen], ["skim", "resolve"], "for each of the two phases, once")
                self.assertTrue(all(row[3] is False for row in seen))
                self.assertEqual(seen[1][6], 60, "and its targets are every flagged word of the transcript")
                many = len({k for _, k, *_ in self._regions(request)})
                self.assertEqual((seen[0][4], seen[0][5]), (min(3600, 300 * many), min(60, 12 * many)), "with the time and tool calls of the regions it replaces")
        # the message of the whole does not name hundreds of IDs: they are in the files; a region's message names them, as ever
        _, one = evidence()
        for divided, expect in ((True, "Phase target IDs: s0w1."), (False, "input/targets.txt")):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder); (root / "out").mkdir()
                workspace = asrworkspace.Workspace(root, llmadapter.Cancellation()); workspace.targets = {"s0w1"}; workspace.divided = divided
                adapter = mock.Mock(); adapter.agent_turn.side_effect = llmconfig.LLMError("stop", "stop")
                with self.assertRaises(llmconfig.LLMError):
                    asrworkspace._phase(workspace, one, adapter, "skim", {"s0w1"}, 8192, None, "region0")
                sent = json.dumps(adapter.agent_turn.call_args.args[0])
                self.assertIn(expect, sent)
                self.assertEqual("Editable IDs" in sent, divided)
        self.assertEqual(asrworkspace._some([f"s{n}" for n in range(100)], False).split(" and ")[1], "60 more (all in input/required.txt)")
        self.assertEqual(len(asrworkspace._some([f"s{n}" for n in range(100)], True).split()), 100)

    def _regions(self, request):
        """The regions the divided route would make, counted the way test_the_workspace_is_one_region… does, by running it."""
        seen = []
        def phase(workspace, request, adapter, name, allowed, context, diagnostic, key):
            seen.append((name, key)); return [], set()
        with mock.patch("asrworkspace.sandbox_status", return_value={"available": True}), mock.patch("asrworkspace._phase", side_effect=phase):
            asrworkspace.correct(request, object(), llmadapter.Cancellation(), lambda *p: None, divide=True)
        return seen

    def test_cancellation_cleans_workspace_and_preserves_source(self):
        _, request = evidence()
        folders = []
        cancel = llmadapter.Cancellation()
        def phase(workspace, *args):
            folders.append(workspace.root); cancel.cancel(); cancel.check()
        with mock.patch("asrworkspace.sandbox_status", return_value={"available": True}), mock.patch("asrworkspace._phase", side_effect=phase):
            with self.assertRaises(llmconfig.LLMError) as error:
                asrworkspace.correct(request, object(), cancel, lambda *p: None)
        self.assertEqual(error.exception.code, "cancelled")
        self.assertTrue(all(not p.exists() for p in folders))

    def test_optional_os_sandbox_hides_host_files_and_keeps_inputs_read_only(self):
        if not asrworkspace.sandbox_status()["available"]:
            self.skipTest("Optional OS isolation is unavailable")
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as folder:
            secret = Path(outside) / "sentinel"; secret.write_text("not available to the model")
            root = Path(folder); (root / "input").mkdir(); (root / "out").mkdir()
            (root / "input/transcript.txt").write_text("source"); (root / "out/result.csv").touch()
            workspace = asrworkspace.Workspace(root, llmadapter.Cancellation())
            output = workspace.python("from pathlib import Path\nprint(Path(%r).exists())\ntry:\n Path('input/transcript.txt').write_text('modified')\nexcept OSError:\n print('read-only')\nPath('out/result.csv').write_text('allowed')" % str(secret))
            self.assertIn("False", output); self.assertIn("read-only", output)
            self.assertEqual((root / "input/transcript.txt").read_text(), "source")
            self.assertEqual((root / "out/result.csv").read_text(), "allowed")


if __name__ == "__main__":
    unittest.main()
