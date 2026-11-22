# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline second-pass rules and real worker/job protocol with fake Whisper."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/p) for p in ('lib', 'youtube/lib', 'tests')]
import asrcorrection
import asrdictionary
import sttjobs
import stt_fakes
import whispersecond as rules
from test_stt_jobs import Base
from test_stt_worker import Worker


def word(text, start, end, **extra):
    return {'text': text, 'start': start, 'end': end, 'score': .2, **extra}


class Rules(unittest.TestCase):
    def test_finite_numpy_scalars_are_normalized_without_accepting_invalid_values(self):
        import numpy as np
        for scalar in (np.float16, np.float32, np.float64, np.longdouble, np.int32, np.int64, np.uint64):
            with self.subTest(scalar=scalar.__name__):
                self.assertEqual(rules.number(scalar(2)), 2.0)
                self.assertIs(type(rules.number(scalar(2))), float)
        for value in (True, False, np.bool_(True), None, '2', 1+2j, np.complex64(2),
                      np.array(2.), np.array([2.]), float('nan'), float('inf'),
                      np.float32('nan'), np.float64('inf'), np.float32('-inf'), 10**10000):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(rules.number(value))

    def test_crop_is_about_15_seconds_snaps_to_pauses_and_contains_target(self):
        words = [word('before', 2, 3), word('target', 9.9, 10.2), word('after', 17, 18)]
        a, b = rules.crop_bounds(words, words[1], 40, [1.9, 18.2])
        self.assertEqual((a, b), (1.9, 18.2))
        self.assertLess(a, 9.9)
        self.assertGreater(b, 10.2)

    def test_crop_at_edges_long_targets_and_no_pause_never_cut_known_words(self):
        for duration, target in [(3, word('short', 0, .4)), (40, word('long', 8, 26)), (40, word('end', 39, 40))]:
            a, b = rules.crop_bounds([target], target, duration)
            self.assertTrue(0 <= a <= target['start'] <= target['end'] <= b <= duration)
        words = [word('edge', 1, 4), word('suspect', 10, 11), word('edge2', 17, 19)]
        a, b = rules.crop_bounds(words, words[1], 40)
        self.assertLessEqual(a, 1)
        self.assertGreaterEqual(b, 19)
        with self.assertRaisesRegex(ValueError, 'missing-timestamps'):
            rules.crop_bounds([], word('missing', None, None), 20)

    def test_alignment_preserves_punctuation_and_all_native_alternatives(self):
        original = [word('Loro', 1, 2), word('anno,', 2, 3), word('detto', 3, 4)]
        decoded = [word('Loro', 0, 1), word('hanno.', 1, 2, asr_alternatives=[{'text': 'han', 'score': None, 'sequence_score': -.4, 'score_kind': 'sequence_log_score'}]), word('detto', 2, 3)]
        before = copy.deepcopy(original)
        got = rules.attributable(original, 1, decoded, 1, 5)
        self.assertEqual([w['text'] for w in got], ['hanno,', 'han,'])
        self.assertEqual(got[1]['sequence_score'], -.4)
        self.assertEqual(original, before)

    def test_multitoken_unicode_replacement_is_one_source_span(self):
        a = [word('او', 0, 1), word('میرود،', 1, 2), word('خانه', 2, 3)]
        b = [word('او', 0, 1), word('می', 1, 1.4), word('رود.', 1.4, 2), word('خانه', 2, 3)]
        got = rules.attributable(a, 1, b, 0, 3)
        self.assertEqual(got[0]['text'], 'می رود،')
        self.assertIsNone(got[0]['score'])
        a = [word('他', 0, 1), word('睡', 1, 2), word('了', 2, 3)]
        b = [word('他', 0, 1), word('睡', 1, 1.4), word('觉', 1.4, 2, space_before=False), word('了', 2, 3)]
        self.assertEqual(rules.attributable(a, 1, b, 0, 3)[0]['text'], '睡觉')

    def test_ambiguous_crossword_repeated_or_wrong_time_results_are_rejected(self):
        a = [word('loro', 0, 1), word('anno', 1, 2), word('deto', 2, 3), word('ciao', 3, 4)]
        b = [word('loro', 0, 1), word('hanno', 1, 2), word('detto', 2, 3), word('ciao', 3, 4)]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            rules.attributable(a, 1, b, 0, 4)
        b = [word('loro', 8, 9), word('hanno', 9, 10), word('deto', 10, 11), word('ciao', 11, 12)]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            rules.attributable(a, 1, b, 0, 15)
        a = [word('go', 0, 1), word('go', 1, 2), word('home', 2, 3)]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            rules.attributable(a, 0, a, 0, 3)

    def test_dedup_retains_original_every_existing_alternative_and_provenance(self):
        target = word('anno', 0, 1, asr_alternatives=[{'text': 'option%d' % i, 'score': .1} for i in range(20)])
        target['asr_alternatives'].append({'text': 'hanno', 'score': None})
        extra = [{'text': 'hanno', 'score': .8, 'origins': [{'kind': 'whisper-second-pass', 'hypothesis': 'original', 'score': .8}]}]
        kept = rules.merge(target, extra)
        self.assertEqual(len(kept), 22)
        self.assertEqual(kept[0]['text'], 'anno')
        self.assertIsNone(kept[-1]['score'])
        self.assertEqual(len(kept[-1]['origins']), 2)
        clean, _ = asrcorrection.alternatives(kept)
        self.assertEqual(clean[-1]['origins'], kept[-1]['origins'])

    def test_candidate_application_changes_only_source_span_and_rejects_stale_text(self):
        import sttpanel
        from reviewerror import LLMError
        words = [word('Loro', 0, 1), word('anno,', 1, 2), word('detto', 2, 3)]
        segments = [{'start': 0, 'end': 3, 'text': 'Loro anno, detto', 'asr_words': words}]
        panel, _ = sttpanel.segments_to_panel(segments)
        evidence = asrcorrection.evidence(segments, panel, 'it')
        replacement = rules.attributable(words, 1, [word('Loro', 0, 1), word('hanno.', 1, 2), word('detto', 2, 3)], 0, 3)[0]['text']
        applied, changed = asrcorrection.apply(panel, evidence, {'suggestions': []}, {}, {'s0w1': replacement})
        self.assertTrue(changed)
        self.assertEqual(applied, panel.replace('anno,', 'hanno,'))
        with self.assertRaises(LLMError):
            asrcorrection.apply(panel+' changed', evidence, {'suggestions': []}, {}, {'s0w1': replacement})


class WorkerSecond(Worker):
    @staticmethod
    def source_fields(segments):
        return [{key: segment[key] for key in ('text', 'start', 'end', 'words')} for segment in segments]

    def test_numpy_crop_timestamps_produce_candidates_and_keep_first_pass_times(self):
        for scalar_type in ('float32', 'float64'):
            with self.subTest(scalar_type=scalar_type):
                stt_fakes.configure(self.root, fake={
                    'segments': [[0, 3, ' loro anno detto']],
                    'word_evidence': {'anno': {'score': .2}},
                    'second_pass': [{'segments': [[.125, 2.75, ' loro hanno detto']],
                                     'numpy_word_scalars': scalar_type, 'word_evidence': {'hanno': {'score': .75}}}]})
                rc, messages, err = self.run_spec(self.spec(second_pass=True),
                                                input_text=json.dumps({'word_ids': ['s0w1']})+'\n')
                self.assertEqual(rc, 0, err)
                first, done = self.last(messages, 'first-pass'), self.last(messages, 'done')
                self.assertEqual(done['second_pass']['failures'], [])
                self.assertEqual(self.source_fields(done['segments']), self.source_fields(first['segments']))
                word = done['segments'][0]['asr_words'][1]
                self.assertEqual((word['text'], word['start'], word['end'], word['score']), ('anno', 1., 2., .2))
                alternative = next(a for a in word['asr_alternatives'] if a['text'] == 'hanno')
                self.assertEqual(alternative['score'], .75)
                self.assertIs(type(alternative['score']), float)

    def test_shifted_crop_timestamps_never_replace_any_original_word_times(self):
        for crop_text in (' Loro hanno, detto ciao.', ' Loro hanno proprio, detto ciao.'):
            with self.subTest(crop_text=crop_text):
                stt_fakes.configure(self.root, fake={
                    'segments': [[1, 5, ' Loro anno, detto ciao.']],
                    'word_evidence': {'anno,': {'score': .2}},
                    'second_pass': [{'segments': [[1.2, 5.2, crop_text]], 'leading_word_spaces': True}]})
                rc, messages, err = self.run_spec(self.spec(source_path=self.pcm(6), second_pass=True),
                                                input_text=json.dumps({'word_ids': ['s0w1']})+'\n')
                self.assertEqual(rc, 0, err)
                first, done = self.last(messages, 'first-pass'), self.last(messages, 'done')
                self.assertEqual(self.source_fields(done['segments']), self.source_fields(first['segments']))
                for original, final in zip(first['segments'][0]['asr_words'], done['segments'][0]['asr_words']):
                    self.assertEqual({k: final[k] for k in ('text', 'start', 'end', 'score')},
                                     {k: original[k] for k in ('text', 'start', 'end', 'score')})
                replacement = 'hanno proprio,' if 'proprio' in crop_text else 'hanno,'
                self.assertIn(replacement, [a['text'] for a in done['segments'][0]['asr_words'][1]['asr_alternatives']])
                self.assertEqual(done['second_pass']['failures'], [])

    def test_optional_alignment_uses_its_own_times_and_keeps_whisper_evidence(self):
        # An offline aligner deliberately chooses times different from both
        # Whisper passes. Enabling candidate collection must not change them.
        runtime = Path(self.root)/'align-runtime'
        runtime.mkdir()
        (runtime/'ctcalign.py').write_text('''
def align_segments(audio, segments, folder, progress=None):
    out = []
    for segment in segments:
        row = dict(segment)
        row['words'] = [dict(w, start=w['start']+.05, end=w['end']-.05, score=.98)
                        for w in segment['words']]
        out.append(row)
    return out, sum(len(s['words']) for s in out), 0
''', encoding='utf-8')
        aligner = Path(self.root)/'aligner'
        aligner.mkdir()
        (aligner/'model.int8.onnx').write_bytes(b'offline fixture')
        stt_fakes.configure(self.root, fake={
            'segments': [[1, 5, ' Loro anno, detto ciao.']],
            'second_pass': [{'segments': [[1.2, 5.2, ' Loro hanno, detto ciao.']]}]})
        env = self.fake.worker_env()
        env['PYTHONPATH'] = str(runtime)+os.pathsep+env['PYTHONPATH']
        with mock.patch.object(self.fake, 'worker_env', return_value=env):
            rc, baseline, err = self.run_spec(self.spec(source_path=self.pcm(6), aligner_path=str(aligner)))
            self.assertEqual(rc, 0, err)
            rc, reviewed, err = self.run_spec(self.spec(source_path=self.pcm(6), aligner_path=str(aligner), second_pass=True),
                                             input_text=json.dumps({'word_ids': ['s0w1']})+'\n')
            self.assertEqual(rc, 0, err)
        before, after = self.last(baseline, 'done'), self.last(reviewed, 'done')
        self.assertEqual((before['word_source'], after['word_source']), ('aligner', 'aligner'))
        self.assertEqual(self.source_fields(after['segments']), self.source_fields(before['segments']))
        self.assertEqual(after['segments'][0]['words'][1]['start'], 2.05)
        self.assertEqual(after['segments'][0]['asr_words'][1]['start'], 2)
        self.assertEqual(after['segments'][0]['asr_words'][1]['end'], 3)
        self.assertEqual(after['segments'][0]['asr_words'][1]['text'], 'anno,')
        self.assertEqual(after['segments'][0]['asr_words'][1]['asr_alternatives'][-1]['text'], 'hanno,')

    def test_independent_decoding_flags_same_model_and_unchanged_transcript(self):
        stt_fakes.configure(self.root, fake={
            'segments': [[0, 3, ' loro anno detto']],
            'word_evidence': {'anno': {'score': .2}},
            'second_pass': [{'segments': [[0, 3, ' loro hanno detto']]}]})
        rc, messages, err = self.run_spec(self.spec(second_pass=True), input_text=json.dumps({'word_ids': ['s0w1']})+'\n')
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(stt_fakes.records(self.root, 'construct')), 1)
        calls = stt_fakes.records(self.root, 'transcribe')
        self.assertEqual(len(calls), 2)
        c = calls[1]
        self.assertEqual((c['beam_size'], c['language'], c['vad_filter']), (10, 'fa', False))
        self.assertEqual(c['options'], {'temperature': 0, 'word_timestamps': True, 'condition_on_previous_text': False, 'initial_prompt': None, 'prefix': None})
        done = self.last(messages, 'done')
        self.assertEqual(done['segments'][0]['text'], ' loro anno detto')
        w = done['segments'][0]['asr_words'][1]
        self.assertEqual((w['text'], w['score'], w['start'], w['end']), ('anno', .2, 1, 2))
        self.assertEqual([a['text'] for a in w['asr_alternatives']], ['anno', 'hanno'])
        self.assertEqual(done['second_pass'], {'done': 1, 'total': 1, 'failures': []})


class JobsSecond(Base):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(asrdictionary.Resolver, 'word', side_effect=lambda text, *args: {'state': 'missing' if text == 'strano' else 'found', 'words': []})
        patch.start()
        self.addCleanup(patch.stop)

    def configure(self, first_error=False, delay=0):
        alternatives = [{'text': 'existing%d' % i, 'score': None} for i in range(12)]
        self.fake(segments=[[0, 4, ' loro anno detto strano']], word_evidence={'anno': {'score': .2, 'alternatives': alternatives}}, second_pass=[
            {'segments': [[0, 4, ' loro hanno detto strano']], 'word_evidence': {'hanno': {'score': .1, 'alternatives': [{'text': 'han', 'score': .3}]}}, 'second_error': first_error, 'delay': delay},
            {'segments': [[0, 4, ' loro anno detto strana']], 'delay': delay}])

    def result_choice(self, token):
        self.assertEqual(self.wait(token, ('done', 'failed'))['state'], 'done')
        return sttjobs.result(token)

    def test_saved_review_and_playback_timing_tape_match_first_pass_exactly(self):
        import wordtimes
        self.fake(segments=[[1, 5, ' Loro anno, detto ciao.']], word_evidence={'anno,': {'score': .2}},
                  second_pass=[{'segments': [[1.2, 5.2, ' Loro hanno, detto ciao.']]}])
        spec = sttjobs._spec
        with mock.patch.object(sttjobs, '_spec', side_effect=lambda gs, job: dict(spec(gs, job), second_pass=False)):
            baseline_job = self.start_film(lang='it', seconds=6)['job']
            before = self.result_choice(baseline_job)
        reviewed_job = self.start_film(lang='it', seconds=6)['job']
        after = self.result_choice(reviewed_job)
        self.assertEqual(after['text'], before['text'])
        self.assertEqual(sttjobs.JOBS[reviewed_job]['facts'], sttjobs.JOBS[baseline_job]['facts'])
        original, reviewed = asrcorrection.index(before['review']['evidence']), asrcorrection.index(after['review']['evidence'])
        fields = ('text', 'start', 'end', 'asr_confidence', 'span_start', 'span_end')
        self.assertEqual({wid: {k: w[k] for k in fields} for wid, w in reviewed.items()},
                         {wid: {k: w[k] for k in fields} for wid, w in original.items()})
        self.assertIn('hanno,', [a['text'] for a in reviewed['s0w1']['asr_alternatives']])
        timing_fields = ('surface', 'start', 'end', 'time_source', 'score')
        for tape in ('raw_atoms', 'atoms'):
            self.assertEqual([{k: a.get(k) for k in timing_fields} for a in wordtimes.load(reviewed_job)[tape]],
                             [{k: a.get(k) for k in timing_fields} for a in wordtimes.load(baseline_job)[tape]])

    def test_automatic_fixed_suspects_includes_dictionary_miss_and_low_score(self):
        self.configure()
        token = self.start_film(lang='it', seconds=4)['job']
        result = self.result_choice(token)
        words = asrcorrection.index(result['review']['evidence'])
        self.assertTrue(words['s0w3']['dictionary_miss'])
        self.assertEqual(len(self.records('transcribe')), 3, 'two fixed suspects, no recursive new suspects')
        self.assertEqual(len(self.records('construct')), 1)
        self.assertEqual([a['text'] for a in words['s0w1']['asr_alternatives']], ['anno']+['existing%d' % i for i in range(12)]+['hanno', 'han'])
        self.assertEqual(words['s0w3']['asr_alternatives'][-1]['text'], 'strana')
        self.assertIn('loro anno detto strano', result['text'])
        self.assertEqual(result['review']['evidence']['second_pass']['done'], 2)
        self.assertEqual(sttjobs.status(token)['second_pass'], {'done': 2, 'total': 2, 'failed': 0})

    def test_failure_is_local_and_completion_waits_for_second_pass(self):
        self.configure(first_error=True, delay=.3)
        token = self.start_film(lang='it', seconds=4)['job']
        state = self.wait(token, (sttjobs.SECOND_PASS,))
        self.assertEqual(state['second_pass']['total'], 2)
        self.assertTrue(sttjobs.busy())
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.result(token)
        result = self.result_choice(token)
        p = result['review']['evidence']['second_pass']
        self.assertEqual((p['done'], p['failed']), (2, 1))
        self.assertEqual(p['failures'], [{'word_id': 's0w1', 'reason': 'transcription-failed'}])
        words = asrcorrection.index(result['review']['evidence'])
        self.assertEqual(words['s0w1']['second_pass']['state'], 'failed')
        self.assertEqual(words['s0w3']['asr_alternatives'][-1]['text'], 'strana')
        self.assertFalse(sttjobs.busy())

    def test_cancellation_kills_native_crop_and_disallows_results(self):
        self.configure(delay=5)
        token = self.start_film(lang='it', seconds=4)['job']
        self.wait(token, (sttjobs.SECOND_PASS,))
        self.assertTrue(sttjobs.cancel(token)['cancelled'])
        self.assertEqual(sttjobs.status(token)['state'], 'cancelled')
        self.assertNotIn(token, sttjobs.JOBS)
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.result(token)
        self.assertFalse(sttjobs.busy())

    def test_missing_word_timestamps_and_scores_are_recorded_without_fabrication(self):
        self.fake(segments=[[0, 4, ' loro anno detto strano']], no_words=True)
        token = self.start_film(lang='it', seconds=4)['job']
        result = self.result_choice(token)
        w = asrcorrection.index(result['review']['evidence'])['s0w3']
        self.assertTrue(w['dictionary_miss'])
        self.assertIsNone(w['asr_confidence'])
        self.assertEqual(w['asr_alternatives'], [])
        self.assertFalse(w['alternatives_available'])
        self.assertEqual(w['second_pass']['reason'], 'missing-timestamps')
        self.assertEqual(result['review']['evidence']['second_pass']['done'], 1)
        self.assertEqual(len(self.records('transcribe')), 1)

    def test_native_crash_keeps_completed_candidates_and_marks_remaining_words(self):
        self.fake(segments=[[0, 4, ' loro anno detto strano']], word_evidence={'anno': {'score': .2}},
                  second_pass=[{'segments': [[0, 4, ' loro hanno detto strano']]}, {'second_exit': True}])
        token = self.start_film(lang='it', seconds=4)['job']
        result = self.result_choice(token)
        p = result['review']['evidence']['second_pass']
        self.assertEqual(p['failures'], [{'word_id': 's0w3', 'reason': 'worker-stopped'}])
        self.assertEqual(p['done'], 2)
        words = asrcorrection.index(result['review']['evidence'])
        self.assertEqual(words['s0w1']['asr_alternatives'][-1]['text'], 'hanno')
        self.assertIn('loro anno detto strano', result['text'])

    def test_no_suspects_finishes_without_any_second_decoding(self):
        self.fake(segments=[[0, 3, ' loro hanno detto']])
        token = self.start_film(lang='it')['job']
        self.result_choice(token)
        self.assertEqual(sttjobs.status(token)['second_pass'], {'done': 0, 'total': 0, 'failed': 0})
        self.assertEqual(len(self.records('transcribe')), 1)

    def test_changed_source_discards_inflight_second_pass(self):
        self.configure(delay=.4)
        token = self.start_film(lang='it', seconds=4)['job']
        self.wait(token, (sttjobs.SECOND_PASS,))
        with open(sttjobs.JOBS[token]['source']['path'], 'ab') as f:
            f.write(b'changed')
        state = self.wait(token, ('failed', 'done'))
        self.assertEqual(state['state'], 'failed')
        self.assertEqual(state['code'], 'film-changed')
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.result(token)

    def test_youtube_crops_use_audio_clock_even_when_video_clock_differs(self):
        self.fake(segments=[[10.3, 11.7, ' stall'], [13, 14.6, ' loro anno detto']], word_evidence={'anno': {'score': .2}},
                  second_pass=[{'segments': [[5.5, 6.9, ' stall'], [8.2, 9.8, ' loro hanno detto']]}])
        token = self.start_yt(lang='it')['job']
        sttjobs.marks(token, [[4000*i, 100+i/4-.4-(2 if i/4 >= 12 else 0)] for i in range(81) if not 10 <= i/4 < 12])
        sttjobs.audio(token, 0, stt_fakes.pcm(20), True)
        result = self.result_choice(token)
        words = asrcorrection.index(result['review']['evidence'])
        self.assertEqual(result['review']['evidence']['second_pass']['total'], 1)
        self.assertIn('s0w1', words, repr(result['review']['evidence']))
        self.assertEqual(words['s0w1']['asr_alternatives'][-1]['text'], 'hanno')
        self.assertEqual((words['s0w1']['start'], words['s0w1']['end']), (111.133, 111.667))


if __name__ == '__main__':
    unittest.main()
