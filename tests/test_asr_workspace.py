# SPDX-License-Identifier: GPL-3.0-or-later
"""The text workspace of the copy/paste review: its files, its checker, and the reading of a returned CSV."""
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "youtube/lib")]
import asrcorrection
import asrworkspace
from reviewerror import LLMError


def evidence():
    text = "Thay anno detto ciao."
    words = [{"text": t, "start": i, "end": i + .5, "score": .2 if t == "anno" else .9}
             for i, t in enumerate(text.split())]
    return text, asrcorrection.evidence([{"text": text, "start": 0, "end": 4, "words": words}], text, "it")




class WorkspaceContracts(unittest.TestCase):
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
                with self.assertRaises(LLMError):
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
                with self.assertRaises(LLMError):
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
                with self.subTest(rows=rows), self.assertRaises(LLMError):
                    proposals(rows)
            proposals([valid], required={'s0w1'}, complete=True)
            with self.assertRaises(LLMError):
                proposals([valid], required={'s0w1', 's0w3'}, complete=True)


if __name__ == "__main__":
    unittest.main()
