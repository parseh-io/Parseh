# SPDX-License-Identifier: GPL-3.0-or-later
"""Numerically/model-independent checks of the standalone workspace validator."""
import contextlib
import copy
import csv
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'lib/asrskill/parseh-asr-workspace/scripts/review.py'
SPEC = importlib.util.spec_from_file_location('workspace_helper_contract', SOURCE)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)  # Import needs no input/working directory.


def source():
    captions = {'s0': '🙂 A note\u00a0book arrived.', 's1': 'بعد.'}
    words = {}
    for segment, text in captions.items():
        for index, match in enumerate(re.finditer(r'\S+', text)):
            ident = segment + 'w' + str(index)
            words[ident] = {'word_id': ident, 'segment_id': segment, 'original': match.group(),
                            'char_start': str(match.start()), 'char_end': str(match.end()), 'source_index': str(index)}
    return words, captions, set(words), {'s0w2'}, {'s0w2'}


def row(**changes):
    return dict({'word_ids': 's0w2 s0w3', 'original': 'note\u00a0book',
                 'replacement': 'notebook', 'reason': 'One word split into two source pieces.'}, **changes)


def csv_text(rows):
    output = io.StringIO(newline=''); writer = csv.DictWriter(output, fieldnames=review.FIELDS)
    writer.writeheader(); writer.writerows(rows); return output.getvalue()


@contextlib.contextmanager
def workspace(required='s0w2'):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder); (root / 'input').mkdir(); (root / 'out').mkdir()
        words, captions, allowed, targets, _ = source()
        inputs = {'words': (list(words.values()), ['word_id', 'segment_id', 'original', 'char_start', 'char_end', 'source_index']),
                  'captions': ([{'segment_id': ident, 'text': text} for ident, text in captions.items()], ['segment_id', 'text']),
                  'suspects': ([{'word_id': 's0w2', 'slot': '1', 'whisper_hints': 'score 0.2; alternatives unavailable',
                                'context': captions['s0']}], ['word_id', 'slot', 'whisper_hints', 'context']),
                  'skim': ([], review.FIELDS)}
        for name, (rows, fields) in inputs.items():
            with (root / 'input' / (name + '.csv')).open('w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        (root / 'input/allowed.txt').write_text(' '.join(sorted(allowed)), encoding='utf-8')
        (root / 'input/targets.txt').write_text(' '.join(targets), encoding='utf-8')
        (root / 'input/required.txt').write_text(required, encoding='utf-8')
        (root / 'input/active.txt').write_text('s0: 🙂 A [1] book arrived.', encoding='utf-8')
        (root / 'out/result.csv').write_text(csv_text([]), encoding='utf-8')
        shutil.copyfile(SOURCE, root / 'review.py')
        old = Path.cwd()
        try:
            os.chdir(root); yield root
        finally:
            os.chdir(old)


class WorkspaceHelper(unittest.TestCase):
    def validate(self, rows, **options):
        words, captions, allowed, targets, required = source()
        return review.validate_rows(rows, words, captions, allowed, targets, required, **options)

    def test_exact_unicode_span_merge_is_valid_and_source_stays_immutable(self):
        words, captions, allowed, targets, required = source(); original = copy.deepcopy((words, captions))
        checked, seen = review.validate_rows([row()], words, captions, allowed, targets, required, complete=True)
        self.assertEqual(checked[0]['original'], 'note\u00a0book'); self.assertEqual(seen, {'s0w2', 's0w3'})
        self.assertEqual((words, captions), original)
        for text in ('کوچیکه', 'می\u200cروم', '学校'):
            words = {'s0w0': {'word_id': 's0w0', 'segment_id': 's0', 'original': text, 'char_start': 0, 'char_end': len(text)}}
            self.assertEqual(review.validate_rows([row(word_ids='s0w0', original=text, replacement=text)],
                words, {'s0': text}, {'s0w0'}, {'s0w0'})[1], {'s0w0'})
            if '\u200c' in text:
                with self.assertRaises(ValueError):
                    review.validate_rows([row(word_ids='s0w0', original=text.replace('\u200c', ''), replacement=text)],
                        words, {'s0': text}, {'s0w0'}, {'s0w0'})

    def test_header_malformed_columns_unicode_and_size(self):
        for text in ('', 'original,word_ids,replacement,reason\n', 'word_ids,original,replacement,reason\n"unterminated',
                     'word_ids,original,replacement,reason\n' + 'x' * 65536, '\ud800'):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError): review.parse_csv(text)
        for text in ('word_ids,original,replacement,reason\ns0w2,note,noted\n',
                     'word_ids,original,replacement,reason\ns0w2,note,noted,reason,extra\n'):
            with self.assertRaises(ValueError): self.validate(review.parse_csv(text))
        with self.assertRaises(ValueError): review._csv([row(replacement='\ud800')])

    def test_more_than_eight_adjacent_words_is_rejected(self):
        text = ' '.join('word%d' % i for i in range(9)); words = {}
        for i, match in enumerate(re.finditer(r'\S+', text)):
            ident = 's0w%d' % i
            words[ident] = {'segment_id': 's0', 'original': match.group(), 'char_start': match.start(),
                            'char_end': match.end(), 'source_index': i}
        with self.assertRaises(ValueError):
            review.validate_rows([row(word_ids=' '.join(words), original=text, replacement='word')],
                words, {'s0': text}, set(words), set(words))

    def test_span_scope_order_overlap_and_source_mismatch(self):
        for rows in ([row(), row()], [row(word_ids='s0w2 s0w4')], [row(word_ids='s0w3 s0w2')],
                     [row(word_ids='s0w2 s0w2')], [row(word_ids='s0w2 s1w0')], [row(word_ids='unknown')],
                     [row(word_ids='s0w3', original='book', replacement='volume')], [row(original='note book')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError): self.validate(rows)
        words, captions, allowed, targets, required = source()
        with self.assertRaises(ValueError): review.validate_rows([row()], words, captions, {'s0w2'}, targets)
        words['s0w3']['source_index'] = '9'
        with self.assertRaises(ValueError): review.validate_rows([row()], words, captions, allowed, targets)

    def test_replacement_and_reason_limits_controls_and_punctuation(self):
        for changes in ({'replacement': ''}, {'replacement': 'x' * 201}, {'replacement': 'notebook!'},
                        {'replacement': 'note\nbook'}, {'replacement': '\ud800'}, {'replacement': 'note\x7fbook'},
                        {'reason': 'x' * 501}, {'reason': 'line\nline'}, {'reason': '\udfff'}, {'reason': 'reason\x85'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.validate([row(**changes)])

    def test_legacy_empty_reason_and_missing_source_index_are_preserved(self):
        words, captions, allowed, targets, required = source()
        for word in words.values(): word.pop('source_index')
        for reason in ('', ' '):
            checked, seen = review.validate_rows([row(reason=reason)], words, captions, allowed, targets, required, complete=True)
            self.assertEqual(checked[0]['reason'], reason); self.assertEqual(seen, {'s0w2', 's0w3'})

    def test_complete_requires_targets_but_partial_draft_is_allowed(self):
        self.assertEqual(self.validate([])[1], set())
        with self.assertRaises(ValueError): self.validate([], complete=True)
        self.assertEqual(self.validate([row()], complete=True)[1], {'s0w2', 's0w3'})

    def test_partial_check_reports_missing_ids_and_does_not_write(self):
        with workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            original = (root / 'out/result.csv').read_bytes()
            partial = review.check(); strict = review.check(require_complete=True)
            self.assertTrue(partial['structurally_valid']); self.assertTrue(partial['valid']); self.assertFalse(partial['complete'])
            self.assertEqual(partial['missing_required_ids'], ['s0w2']); self.assertFalse(strict['valid'])
            self.assertEqual((root / 'out/result.csv').read_bytes(), original)
            report = review.save([('s0w2 s0w3', 'notebook', 'One word split into two pieces.')], require_complete=True)
            self.assertTrue(report['valid']); self.assertTrue(report['complete'])
            self.assertIn('🙂 A notebook arrived.', report['preview'][0]['text'])

    def test_a_row_says_how_sure_it_is_and_an_answer_without_that_is_still_read(self):
        words, captions, allowed, targets, required = source()
        # the header with the fifth column, and the old one, are both read
        header5 = 'word_ids,original,replacement,reason,confidence\n"s0w2 s0w3","note\u00a0book",notebook,split,Sure\n'
        rows = review.parse_csv(header5)
        checked, _ = review.validate_rows(rows, words, captions, allowed, targets, required)
        self.assertEqual(checked[0]['confidence'], 'sure', 'the word is read whichever its case')
        old = review.parse_csv('word_ids,original,replacement,reason\n"s0w2 s0w3","note\u00a0book",notebook,split\n')
        self.assertNotIn('confidence', review.validate_rows(old, words, captions, allowed, targets, required)[0][0])
        with self.assertRaisesRegex(ValueError, 'Confidence must be sure or unsure'):
            self.validate([row(confidence='maybe')])
        self.assertEqual(self.validate([row(confidence='')])[0][0]['confidence'], '')
        with self.assertRaises(ValueError):
            review.parse_csv('word_ids,original,replacement,confidence\n')
        with workspace() as root, contextlib.redirect_stdout(io.StringIO()) as shown:
            report = review.save([('s0w2 s0w3', 'notebook', 'Split.', 'unsure')], require_complete=True)
            self.assertEqual((report['unsure_rows'], report['unrated_rows']), (1, 0))
            self.assertIn('1 marked unsure', shown.getvalue())
            self.assertTrue((root / 'out/result.csv').read_text(encoding='utf-8').startswith('word_ids,original,replacement,reason,confidence\n'))
            unrated = review.save([('s0w2 s0w3', 'notebook', 'Split.')], require_complete=True)
            self.assertEqual((unrated['unsure_rows'], unrated['unrated_rows']), (0, 1))
            self.assertTrue(unrated['valid'], 'a missing confidence is a note, not an error')
            self.assertIn('give every row sure or unsure', shown.getvalue())
            with self.assertRaises(ValueError):
                review.save([('s0w2 s0w3', 'notebook', 'Split.', 'sure', 'extra')])

    def test_invalid_save_late_row_leaves_previous_result_intact(self):
        with workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            review.save([('s0w2 s0w3', 'notebook', 'Split word.')]); before = (root / 'out/result.csv').read_bytes()
            before_files = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            for entries in ([('s0w2', 'noted', 'Fits.'), ('s0w3', 'volume', 'No phase target.')],
                            [('s0w2 s0w3', 'notebook', 'Split.'), ('s0w2', 'noted', 'Overlapping.')],
                            [('s0w2', 'noted', 'line\nline')], [('s0w2', 'x' * 100000, 'Oversized.')]):
                with self.assertRaises(ValueError): review.save(entries)
                self.assertEqual((root / 'out/result.csv').read_bytes(), before)
            after_files = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            self.assertEqual(before_files, after_files)

    def test_cli_checks_partial_and_complete_without_extra_files(self):
        with workspace() as root:
            def cli(*args): return subprocess.run([sys.executable, '-I', '-B', 'review.py', *args], cwd=root, capture_output=True, text=True)
            self.assertEqual(cli('--show').returncode, 0)
            self.assertEqual(cli('--check').returncode, 0)
            strict = cli('--check', '--complete'); self.assertEqual(strict.returncode, 1)
            self.assertIn('Missing required IDs: s0w2', strict.stdout)
            with contextlib.redirect_stdout(io.StringIO()): review.save([('s0w2 s0w3', 'notebook', 'Split word.')])
            strict = cli('--check', '--complete'); self.assertEqual(strict.returncode, 0)
            self.assertIn('does not judge linguistic accuracy', strict.stdout)
            self.assertFalse((root / '__pycache__').exists())


if __name__ == '__main__': unittest.main()
