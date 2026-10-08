# SPDX-License-Identifier: GPL-3.0-or-later
"""Numerically checkable offline contracts. No installed model or network needed."""
import copy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'lib'), str(ROOT / 'youtube/lib'), str(ROOT / 'tests')]
import asrcorrection
import llmadapter
import lmgguf
import lmlikelihood
import lmlikelihoodconfig as config
import lmlikelihoodcore as core
import sttjobs
import sttworker
import lmlikelihoodworker
import lmlikelihoodhardware as hardware
import test_llm_integration as existing_tests


class TinyModel:
    """BOS + greedy pieces; logits predict the next supplied token."""
    context_tokens = 100
    def __init__(self, pieces=('B', ' ', 'x', 'y', '!', 'a', 'b', "'", 'é'), bos=True, probabilities=None):
        self.pieces = [''] + list(pieces)
        self.bos = bos
        self.probabilities = probabilities or (lambda text: None)
        self.begins = []
        self.state = []
    def tokenize(self, text):
        tokens = [0] if self.bos else []
        while text:
            matching = [i for i, p in enumerate(self.pieces) if p and text.startswith(p)]
            if not matching:
                raise lmgguf.ScoringError('unsupported-token', 'A test candidate cannot be tokenized.')
            t = max(matching, key=lambda i: len(self.pieces[i]))
            tokens.append(t); text = text[len(self.pieces[t]):]
        return tokens
    def decode(self, tokens):
        return ''.join(self.pieces[t] for t in tokens).encode()
    def begin(self, tokens):
        self.state = list(tokens); self.begins.append(list(tokens))
    def logits(self):
        probs = self.probabilities(self.decode(self.state).decode())
        if probs is None:
            return [0.] * len(self.pieces)
        # Reserve all leftover probability uniformly, including unused IDs.
        missing = (1 - sum(probs.values())) / (len(self.pieces) - len(probs))
        return [math.log(probs.get(p, missing)) for p in self.pieces]
    def push(self, token):
        self.state.append(token)
    def is_eog(self, token):
        return token == 0


def word(original='x', alternatives=None):
    return {'word_id': 's0w1', 'segment_id': 's0', 'text': original, 'asr_confidence': .2,
            'asr_alternatives': alternatives or [], 'alternatives_available': alternatives is not None,
            'reviewable': True, 'low_asr_score': True}


class Numerical(unittest.TestCase):
    def test_stable_full_vocabulary_log_softmax(self):
        logits = [1000., 1001., 998.]
        expected = 1 - math.log(math.exp(0) + math.exp(1) + math.exp(-2))
        self.assertAlmostEqual(core.log_probability(logits, 1), expected, places=13)
        self.assertAlmostEqual(core.log_probability([0, 0, 0, 0], 0), -math.log(4))
        for invalid in ([math.nan, 0], [math.inf, 0], [-math.inf, -math.inf]):
            with self.assertRaises(lmgguf.ScoringError):
                core.log_probability(invalid, 0)

    def test_following_context_reverses_preceding_only_ranking(self):
        def probs(text):
            return {'x': .8, 'y': .19} if text == 'B ' else {'!': .01} if text == 'B x' else {'!': .9} if text == 'B y' else None
        model = TinyModel(probabilities=probs)
        entries = core.candidates(word(alternatives=[{'text': 'y', 'score': .001}]), [])
        preceding = core.evaluate(model, 'B ', '', copy.deepcopy(entries))
        following = core.evaluate(model, 'B ', '!', copy.deepcopy(entries))
        self.assertEqual(preceding['tied_best'], ['x'])
        self.assertEqual(following['tied_best'], ['y'])
        values = {c['text']: c for c in following['candidates']}
        self.assertAlmostEqual(values['x']['log_likelihood'], math.log(.8) + math.log(.01))
        self.assertAlmostEqual(values['y']['log_likelihood'], math.log(.19) + math.log(.9))
        self.assertEqual(values['x']['evaluated_tokens'], 2)
        self.assertAlmostEqual(values['y']['delta_original'], math.log(.19 * .9 / (.8 * .01)))
        self.assertEqual(following['coverage']['state'], 'complete')

    def test_original_wins_and_ties_are_explicit(self):
        model = TinyModel()
        entries = core.candidates(word(alternatives=[{'text': 'y'}]), [])
        out = core.evaluate(model, 'B ', '!', entries)
        self.assertEqual(out['tied_best'], ['x', 'y'])
        self.assertTrue(all(c['rank'] == 1 for c in out['candidates']))
        model.probabilities = lambda text: {'x': .9} if text == 'B ' else None
        out = core.evaluate(model, 'B ', '!', core.candidates(word(), ['y']))
        self.assertEqual(out['tied_best'], ['x'])
        self.assertEqual(next(c for c in out['candidates'] if c['text'] == 'x')['delta_original'], 0)
        self.assertEqual(core.replacement('!', '!'), '!')

    def test_multi_token_and_boundary_retokenization(self):
        model = TinyModel(pieces=('B', ' ', 'x', 'y', '!', 'a', 'b', ' x', ' yab'))
        entries = core.candidates(word(alternatives=[{'text': 'yab'}]), [])
        out = core.evaluate(model, 'B ', '!', entries)
        self.assertEqual(out['excluded_prefix_tokens'], 2)  # BOS + B; space merges with replacement
        self.assertEqual(out['retokenized_preceding_bytes'], 1)
        self.assertEqual(model.begins, [[0, 1], [0, 1]])
        self.assertTrue(all(c['evaluated_tokens'] == 2 for c in out['candidates']))
        out = core.evaluate(TinyModel(), 'B ', '!', core.candidates(word(), ['ab']))
        counts = {c['text']: c['evaluated_tokens'] for c in out['candidates']}
        self.assertEqual(counts, {'x': 2, 'ab': 3})

    def test_dummy_prefix_space_is_excluded_without_changing_continuations(self):
        class SentencePieces(TinyModel):
            def tokenize(self, text):
                return super().tokenize(' ' + text)
            def decode_prefix(self, tokens):
                raw = self.decode(tokens)
                return raw[1:] if raw.startswith(b' ') else raw
        def probs(text):
            return {'y': .9} if text == ' B ' else {' ': .9} if text == ' B y' else None
        model = SentencePieces(probabilities=probs)
        # Both real source spaces survive; only the artificial initial one
        # disappears from prefix matching. Scores exclude constant L.
        prefix = core.safe_prefix(model, ' B ', [model.tokenize(' B x!')])
        self.assertEqual(core.decoded_prefix(model, prefix), b' B ')
        out = core.evaluate(model, 'B ', '!', core.candidates(word(), ['y']))
        self.assertEqual(out['excluded_prefix_bytes'], 2)
        self.assertEqual(out['retokenized_preceding_bytes'], 0)
        self.assertTrue(all(c['evaluated_tokens'] == 2 for c in out['candidates']))
        extra = core.beam_candidates(model, 'B ', word(),
            dict(config.DEFAULTS, beam_width=1, phonetic_filter=False, minimum_candidate_probability=0),
            lambda: None, time.monotonic()+3)
        self.assertEqual(extra, ['y'])
        self.assertEqual(model.decode(model.tokenize(' B ')), b'  B ')
        self.assertEqual(model.decode([2]), b' ')  # Continuation space retained.

    def test_native_prefix_decoding_retains_real_spaces_and_partial_unicode(self):
        backend = object.__new__(lmlikelihoodworker.Backend)
        backend.prefix_space = True
        backend.decode = lambda tokens: b'  \xd8' if tokens else b''
        self.assertEqual(backend.decode_prefix([1, 2]), b' \xd8')
        self.assertEqual(backend.decode([1, 2]), b'  \xd8')
        self.assertEqual(backend.decode_prefix([]), b'')
        backend.prefix_space = False
        self.assertEqual(backend.decode_prefix([1, 2]), b'  \xd8')

    def test_independent_reset_and_order_isolation(self):
        model = TinyModel(probabilities=lambda text: {'!': .8} if text.endswith('x') else None)
        entries = core.candidates(word(), ['y', 'ab'])
        forward = core.evaluate(model, 'B ', '!', copy.deepcopy(entries))
        backward = core.evaluate(model, 'B ', '!', list(reversed(copy.deepcopy(entries))))
        self.assertEqual({c['text']: c['log_likelihood'] for c in forward['candidates']},
                         {c['text']: c['log_likelihood'] for c in backward['candidates']})
        self.assertTrue(all(b == [0, 1, 2] for b in model.begins))

    def test_all_whisper_alternatives_outside_search_limit_and_origins(self):
        alternatives = [{'text': 'a' * n, 'score': 0} for n in range(1, 16)] + [{'text': 'x'}, {'text': 'a'}]
        entries = core.candidates(word(alternatives=alternatives), ['a', 'b'])
        out = core.evaluate(TinyModel(), 'B ', '!', entries)
        self.assertEqual(out['coverage']['mandatory_total'], 16)
        self.assertEqual(out['coverage']['mandatory_scored'], 16)
        self.assertEqual(len(next(c for c in entries if c['text'] == 'a')['origins']), 3)
        self.assertEqual([o['kind'] for o in next(c for c in entries if c['text'] == 'x')['origins']], ['original', 'whisper'])
        self.assertEqual(out['coverage']['omitted'], [])

    def test_missing_alternatives_and_incomplete_coverage(self):
        self.assertEqual(len(core.candidates(word(), [])), 1)
        entries = core.candidates(word(alternatives=[{'text': 'not-in-vocabulary'}, {'text': 'y'}]), [])
        out = core.evaluate(TinyModel(), 'B ', '!', entries)
        self.assertEqual(out['coverage']['state'], 'partial')
        self.assertEqual(out['coverage']['omitted'][0]['text'], 'not-in-vocabulary')
        self.assertEqual(out['winner_scope'], 'evaluated candidates only')
        timeout = core.evaluate(TinyModel(), 'B ', '!', core.candidates(word(), ['y']), deadline=time.monotonic() - 1)
        self.assertEqual(timeout['coverage']['mandatory_scored'], 0)
        self.assertTrue(timeout['coverage']['omitted'][0]['reason'])

    def test_missing_first_token_is_not_silently_ignored(self):
        out = core.evaluate(TinyModel(bos=False), '', '!', core.candidates(word(), []))
        self.assertEqual(out['coverage']['state'], 'failed')
        self.assertIn('first token', out['coverage']['omitted'][0]['reason'])

    def test_candidate_probability_and_sound_filters_never_remove_mandatory_words(self):
        def probs(text):
            return {'a': .9} if text == 'B ' else {'b': .9} if text == 'B a' else {' ': .9} if text == 'B ab' else None
        cfg = dict(config.DEFAULTS, beam_width=1, candidate_count=2, replacement_tokens=2, phonetic_filter=False)
        extra = core.beam_candidates(TinyModel(probabilities=probs), 'B ', word(), dict(cfg, minimum_candidate_probability=1), lambda: None, time.monotonic()+3)
        self.assertEqual(extra, [])
        extra = core.beam_candidates(TinyModel(probabilities=probs), 'B ', word(), dict(cfg, phonetic_filter=True), lambda: None, time.monotonic()+3)
        self.assertEqual(extra, [])
        self.assertEqual([c['text'] for c in core.candidates(word(alternatives=[{'text':'ab','score':None}]), extra)], ['x', 'ab'])

    def test_deterministic_beam_discovers_complete_multi_token_words(self):
        def probs(text):
            return {'a': .9} if text == 'B ' else {'b': .9} if text == 'B a' else {' ': .9} if text == 'B ab' else None
        cfg = dict(config.DEFAULTS, beam_width=1, candidate_count=2, replacement_tokens=2, phonetic_filter=False)
        found = core.beam_candidates(TinyModel(probabilities=probs), 'B ', word(), cfg, lambda: None, time.monotonic() + 3)
        self.assertEqual(found, ['ab'])  # a, ab fragments only complete after space
        again = core.beam_candidates(TinyModel(probabilities=probs), 'B ', word(), cfg, lambda: None, time.monotonic() + 3)
        self.assertEqual(found, again)
        def joined_probs(text):
            return {' ab': .9} if text == 'B' else {' ': .9} if text == 'B ab' else None
        joined = TinyModel(pieces=('B', ' ', ' x', ' ab', 'a', 'b'), probabilities=joined_probs)
        self.assertEqual(core.beam_candidates(joined, 'B ', word(), cfg, lambda: None, time.monotonic() + 3), ['ab'])
        self.assertEqual(joined.begins[0], [0, 1])  # residual space searched with word

    def test_search_probability_floor_counts_whole_path_and_boundary(self):
        def probs(text):
            return {'a': .6} if text == 'B ' else {'b': .6} if text == 'B a' else {' ': .6} if text == 'B ab' else None
        cfg=dict(config.DEFAULTS,beam_width=1,candidate_count=2,replacement_tokens=2,phonetic_filter=False)
        discovery=[]
        kept=core.beam_candidates(TinyModel(probabilities=probs),'B ',word(),dict(cfg,minimum_candidate_probability=.2),lambda:None,time.monotonic()+3,discovery)
        self.assertEqual(kept,['ab']);self.assertAlmostEqual(discovery[0]['search_probability'],.6**3)
        dropped=core.beam_candidates(TinyModel(probabilities=probs),'B ',word(),dict(cfg,minimum_candidate_probability=.22),lambda:None,time.monotonic()+3)
        self.assertEqual(dropped,[])

    def test_unicode_apostrophes_and_attached_punctuation(self):
        self.assertEqual(core.replacement('«x,»', 'é'), '«é,»')
        self.assertEqual(core.replacement('x!', "a'b"), "a'b!")
        model = TinyModel()
        out = core.evaluate(model, 'B ', '!', core.candidates(word(), ["a'b", 'é']))
        self.assertEqual(out['coverage']['state'], 'complete')
        self.assertTrue(all(c['applicable'] for c in out['candidates']))
        for bad in (' y', 'y ', 'y?', '', '\ud800'):
            with self.assertRaises(lmgguf.ScoringError):
                core.replacement('x!', bad)
        entries = core.candidates(word(alternatives=[{'text': ' y '}]), [])
        self.assertEqual(entries[1]['text'], 'y')
        self.assertEqual(entries[1]['origins'][0]['evidence']['text'], ' y ')
        self.assertEqual(entries[1]['origins'][0]['boundary_spaces'], {'leading': 1, 'trailing': 1})
        self.assertEqual(core.evaluate(TinyModel(), 'B ', '!', entries)['coverage']['state'], 'complete')

    def test_cancellation_is_global_during_search_and_evaluation(self):
        def cancel():
            raise lmgguf.ScoringError('cancelled', 'Cancelled.')
        with self.assertRaises(lmgguf.ScoringError):
            core.evaluate(TinyModel(), 'B ', '!', core.candidates(word(), []), cancel)
        with self.assertRaises(lmgguf.ScoringError):
            core.beam_candidates(TinyModel(), 'B ', word(), config.DEFAULTS, cancel, time.monotonic() + 2)


def write_gguf(path, split=1, adapter=False, incomplete=False, architecture='llama'):
    def string(s):
        b = s.encode(); return struct.pack('<Q', len(b)) + b
    values = [('general.architecture', 8, architecture), ('llama.block_count', 4, 1), ('split.count', 4, split),
              ('general.type', 8, 'adapter' if adapter else 'model'), ('tokenizer.ggml.tokens', 9, None)]
    data = b'GGUF' + struct.pack('<IQQ', 3, 1, len(values))
    for name, kind, value in values:
        data += string(name) + struct.pack('<I', kind)
        data += string(value) if kind == 8 else struct.pack('<IQ', 8, 1) + string('x') if kind == 9 else struct.pack('<I', value)
    data += string('token_embd.weight') + struct.pack('<IQIQ', 1, 1, 0, 0)
    data += b'\0' * ((-len(data)) % 32)
    data += b'\0' * (2 if incomplete else 4)
    path.write_bytes(data)


class Models(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'sha256-no-extension'
        write_gguf(self.path)

    def test_content_format_not_extension_and_replacement_identity(self):
        model = lmgguf.inspect(self.path)
        self.assertEqual(model['format'], 'GGUF')
        lmgguf.revalidate(model)
        self.path.write_bytes(self.path.read_bytes() + b'x')
        with self.assertRaises(lmgguf.ScoringError) as e:
            lmgguf.revalidate(model)
        self.assertEqual(e.exception.code, 'model-changed')
        self.path.write_bytes(b'not GGUF')
        with self.assertRaises(lmgguf.ScoringError):
            lmgguf.inspect(self.path)

    def test_selected_symlink_deletion_and_replacement_are_revalidated(self):
        link = self.path.with_name('selected.gguf')
        try:
            link.symlink_to(self.path)
        except OSError:
            self.skipTest('Symlinks unavailable')
        model = lmgguf.inspect(link)
        self.assertEqual(model['path'], str(self.path))
        lmgguf.revalidate(model)
        link.unlink()
        with self.assertRaises(lmgguf.ScoringError):
            lmgguf.revalidate(model)
        other = self.path.with_name('other-blob'); write_gguf(other)
        link.symlink_to(other)
        with self.assertRaises(lmgguf.ScoringError) as caught:
            lmgguf.revalidate(model)
        self.assertEqual(caught.exception.code, 'model-changed')

    def test_inaccessible_split_adapter_and_incomplete_models(self):
        with self.assertRaises(lmgguf.ScoringError) as e:
            lmgguf.inspect(self.path.with_name('absent.gguf'))
        self.assertEqual(e.exception.code, 'model-inaccessible')
        for kw in ({'split': 2}, {'adapter': True}, {'incomplete': True}):
            write_gguf(self.path, **kw)
            with self.assertRaises(lmgguf.ScoringError):
                lmgguf.inspect(self.path)

    def test_ollama_backing_file_and_metadata_only_requests(self):
        shown = {'modelfile': '# metadata\nFROM ' + str(self.path), 'capabilities': ['completion']}
        with mock.patch('lmgguf.metadata_request', side_effect=[{'models': [{'name': 'local-qwen', 'digest': 'digest'}]}, shown]) as api:
            rows, errors = lmgguf.discover('ollama', 'http://127.0.0.1:11434')
        self.assertEqual(rows[0]['path'], str(self.path))
        self.assertEqual(errors, [])
        self.assertEqual([c.args[1] for c in api.call_args_list], ['api/tags', 'api/show'])
        with self.assertRaises(lmgguf.ScoringError):
            lmgguf.ollama_model({'name': 'x'}, dict(shown, modelfile=shown['modelfile'] + '\nADAPTER /other/file'))

    def test_ollama_multiline_templates_are_never_parsed_as_model_paths(self):
        modelfile = 'FROM "' + str(self.path) + '"\nTEMPLATE """{{ if .System }}\nFROM /template/not/a/model\nADAPTER /template/not/an/adapter\n{{ .Prompt }} "unmatched\n"""\nPARAMETER stop "<|end|>"'
        shown = {'modelfile': modelfile, 'capabilities': ['completion']}
        model = lmgguf.ollama_model({'name': 'local-qwen'}, shown)
        self.assertEqual(model['path'], str(self.path))
        with self.assertRaises(lmgguf.ScoringError) as failure:
            lmgguf.ollama_model({'name': 'local-qwen'}, dict(shown, modelfile=modelfile + '\nADAPTER /required/adapter'))
        self.assertEqual(failure.exception.code, 'unsupported-model')
        with self.assertRaises(lmgguf.ScoringError):
            lmgguf.ollama_model({'name': 'local-qwen'}, dict(shown, modelfile='FROM "unclosed'))
        with mock.patch('lmgguf.metadata_request', return_value={'models': [None, {'name': None}]}):
            rows, errors = lmgguf.discover('ollama', 'http://127.0.0.1:11434')
        self.assertFalse(rows); self.assertEqual(len(errors), 2)

    def test_unsloth_installed_manifest_without_commit_and_remote_path(self):
        root = Path(self.temp.name)
        cache = root / 'cache/models--owner--model/snapshots/revision'
        cache.mkdir(parents=True)
        installed = cache / 'weights.gguf'; installed.write_bytes(self.path.read_bytes())
        manifests = root / 'manifests'; manifests.mkdir()
        (manifests / 'installed.json').write_text(json.dumps({'repo_id': 'owner/model', 'variant': 'Q4_1',
            'hub_cache': str(root / 'cache'), 'commit_hash': None, 'expected_files': [{'path': 'weights.gguf', 'size': installed.stat().st_size}]}))
        rows, errors = lmgguf.discover('unsloth', manifests=manifests)
        self.assertEqual(rows[0]['model_id'], 'owner/model / Q4_1'); self.assertFalse(errors)
        installed.unlink()
        rows, errors = lmgguf.discover('unsloth', manifests=manifests)
        self.assertFalse(rows); self.assertTrue(errors)

    def test_explicit_text_only_configuration_with_optional_vision_projector(self):
        root = Path(self.temp.name)
        cache = root / 'cache/models--owner--model/snapshots/revision'; cache.mkdir(parents=True)
        primary, vision = cache / 'weights.gguf', cache / 'projector.gguf'
        write_gguf(primary); write_gguf(vision, architecture='clip')
        manifests = root / 'manifests'; manifests.mkdir()
        manifest = {'repo_id': 'owner/model', 'variant': 'Q4_1', 'hub_cache': str(root / 'cache'), 'commit_hash': None,
                    'expected_files': [{'path': p.name, 'size': p.stat().st_size} for p in (primary, vision)]}
        entry = manifests / 'installed.json'; entry.write_text(json.dumps(manifest))
        rows, errors = lmgguf.discover('unsloth', manifests=manifests)
        self.assertFalse(errors); self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['text_only']); self.assertEqual(rows[0]['unused_vision_projectors'], ['projector.gguf'])
        self.assertEqual(rows[0]['path'], str(primary))
        # A second causal decoder is not mistaken for an optional projector.
        write_gguf(vision); manifest['expected_files'][1]['size'] = vision.stat().st_size
        entry.write_text(json.dumps(manifest))
        rows, errors = lmgguf.discover('unsloth', manifests=manifests)
        self.assertFalse(rows); self.assertEqual(errors[0]['code'], 'unsupported-model')

    def test_settings_default_disabled_bounds_host_local_and_model_choice(self):
        path = Path(self.temp.name) / 'settings.json'
        with mock.patch.object(config, 'CONFIG', path), mock.patch('lmlikelihood.unload_all'):
            self.assertIsNone(config.load()['model'])
            path.write_text('{broken')
            self.assertIsNone(config.load()['model'])
            selected = config.save({'path': str(self.path)})
            self.assertEqual(selected['model']['path'], str(self.path))
            self.assertEqual(config.load(), selected)
            with self.assertRaises(lmgguf.ScoringError):
                config.save({'model': selected['model']})  # arbitrary model objects forbidden
            for kw in ({'beam_width': 0}, {'manager_url': 'http://user:secret@host'}, {'python': 'relative'}, {'gpu_layers': 1}, {'format_version': 2}):
                with self.assertRaises(lmgguf.ScoringError):
                    config.save(kw)
            with mock.patch('lmlikelihoodconfig.discover', return_value=([dict(selected['model'], source='unsloth', model_id='installed')], [])):
                config.write(dict(config.load(), source='unsloth'))
                models = config.inventory()['models']
                self.assertEqual(config.select(models[0]['id'])['model']['model_id'], 'installed')
                self.assertNotIn('path', models[0])


class SourceFlow(unittest.TestCase):
    def setUp(self):
        self.panel = '0:00\nB x!\n\n0:02\nB y!\n'
        segments = [{'start': i * 2, 'end': i * 2 + 1, 'text': text,
                     'words': [{'text': 'B', 'score': .9}, {'text': last, 'score': .2,
                                'asr_alternatives': [{'text': 'y' if i == 0 else 'x', 'score': None}]}]}
                    for i, (text, last) in enumerate([('B x!', 'x!'), ('B y!', 'y!')])]
        self.evidence = asrcorrection.evidence(segments, self.panel, 'it')

    def test_immutable_target_context_and_exact_span_apply(self):
        reqs = lmlikelihood.requests(self.evidence, self.panel, config.DEFAULTS)
        self.assertEqual(len(reqs), 2)
        self.assertEqual(reqs[1]['left'], 'B x!\nB ')
        req = reqs[0]
        data = core.evaluate(TinyModel(), req['left'], '', core.candidates(req['word'], []))
        suggestion = lmlikelihood.proposal(req, data, {'model_id': 'tiny'})
        result = {'task': 'likelihood', 'suggestions': [suggestion]}
        choice = next(i for i, c in enumerate(suggestion['candidates']) if c['text'] == 'y!')
        edited, changed = asrcorrection.apply(self.panel, self.evidence, result, {req['word']['word_id']: choice})
        self.assertEqual(edited, self.panel.replace('B x!', 'B y!', 1)); self.assertTrue(changed)
        self.assertEqual(lmlikelihood.requests(self.evidence, self.panel, config.DEFAULTS)[1]['left'], reqs[1]['left'])
        original = next(i for i, c in enumerate(suggestion['candidates']) if c['text'] == 'x!')
        unchanged, changed = asrcorrection.apply(self.panel, self.evidence, result, {req['word']['word_id']: original})
        self.assertEqual(unchanged, self.panel); self.assertFalse(changed)
        with self.assertRaises(Exception):
            asrcorrection.apply(edited, self.evidence, result, {})
        suggestion['candidates'][choice]['applicable'] = False
        with self.assertRaises(Exception):
            asrcorrection.apply(self.panel, self.evidence, result, {req['word']['word_id']: choice})

    def test_worker_and_evidence_keep_every_alternative_and_original_score(self):
        from types import SimpleNamespace
        alternatives = [{'text': 'candidate' + str(i), 'score': None} for i in range(21)] + [{'text': 'x' * 500, 'score': .9}]
        held = sttworker.word_alternatives(SimpleNamespace(alternatives=alternatives))
        normalized, available = asrcorrection.alternatives(held['asr_alternatives'])
        self.assertTrue(available); self.assertEqual(len(normalized), 22)
        self.assertEqual(normalized[-1]['text'], 'x' * 500)
        self.assertIsNone(normalized[0]['score'])

    def test_local_failure_continues_other_targets_and_unloads(self):
        targets = lmlikelihood.requests(self.evidence, self.panel, config.DEFAULTS)
        class FakeSession:
            closed = False
            count = 0
            def __init__(self, *args): pass
            def request(self, packet, timeout):
                self.count += 1
                if self.count == 1:
                    raise lmgguf.ScoringError('target-failed', 'Target failed.')
                return {'op': 'target', 'result': core.evaluate(TinyModel(), 'B ', '', core.candidates(packet['request']['word'], []))}
            def close(self): self.closed = True
        progress = mock.Mock()
        with mock.patch('lmlikelihood.Session', FakeSession), mock.patch('lmlikelihood.revalidate'):
            result = lmlikelihood.correct(self.evidence, self.panel, dict(config.DEFAULTS, model={'model_id': 'tiny'}), lambda: None, progress, lambda _: None)
        self.assertEqual(result['failed_word_ids'], ['s0w1'])
        self.assertEqual(result['reviewed_word_ids'], ['s0w1', 's1w1'])
        self.assertEqual(progress.call_args.args[:2], (2, 2))
        self.assertFalse(result['complete'])

    def test_retained_candidate_storage_is_bounded_and_never_claims_coverage(self):
        class FakeSession:
            closed = False
            def __init__(self, *args): pass
            def request(self, packet, timeout):
                return {'op': 'target', 'result': core.evaluate(TinyModel(), 'B ', '', core.candidates(packet['request']['word'], []))}
            def close(self): self.closed = True
        with mock.patch('lmlikelihood.Session', FakeSession), mock.patch('lmlikelihood.revalidate'), \
                mock.patch('lmlikelihood.MAX_REVIEW_BYTES', 1):
            result = lmlikelihood.correct(self.evidence, self.panel, dict(config.DEFAULTS, model={'model_id': 'tiny'}), lambda: None, lambda *args: None, lambda _: None)
        self.assertEqual(result['suggestions'], [])
        self.assertEqual(result['storage_failed_word_ids'], ['s0w1', 's1w1'])
        self.assertEqual(result['failed_word_ids'], ['s0w1', 's1w1'])
        self.assertFalse(result['complete'])


class Hardware(unittest.TestCase):
    def test_fast_token_ranking_matches_full_vocabulary_sort_and_ties(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('NumPy equivalence is also checked by the isolated real-model smoke')
        backend = object.__new__(lmlikelihoodworker.Backend)
        backend.np = np
        for values in ([2., 5., 5., -1., 5., 0.], [0.] * 20, [-math.inf, -2., -3., -4.]):
            logits = np.array(values)
            backend.vocab_size = len(values)
            for n in (1, 2, len(values)):
                expected = np.lexsort((np.arange(len(values)), -logits))[:n].tolist()
                self.assertEqual(backend.top_tokens(logits, n), expected)

    def test_native_gpu_work_is_synchronized_before_reset_and_free(self):
        calls = []
        backend = object.__new__(lmlikelihoodworker.Backend)
        backend.ctx, backend.model, backend.position, backend.context_tokens = 1, 2, 9, 100
        backend.C = SimpleNamespace(llama_synchronize=lambda ctx: calls.append('synchronize'),
            llama_get_memory=lambda ctx: 3, llama_memory_clear=lambda memory, clear: calls.append('clear'),
            llama_free=lambda ctx: calls.append('free-context'), llama_model_free=lambda model: calls.append('free-model'))
        backend._eval = lambda tokens: calls.append(('evaluate', tokens))
        backend.begin([4, 5])
        self.assertEqual(calls, ['synchronize', 'clear', ('evaluate', [4, 5])])
        backend.close()
        self.assertEqual(calls[-3:], ['synchronize', 'free-context', 'free-model'])

    def test_missing_or_incomplete_offload_is_explicit(self):
        for request, actual in [(0, 0), (2, 2), (-1, 37), (1000, 37)]:
            hardware.verify_offload(request, actual, 36)
        for request, actual in [(0, 1), (2, 1), (-1, 2), (1000, 0)]:
            with self.assertRaises(lmgguf.ScoringError) as failure:
                hardware.verify_offload(request, actual, 36)
            self.assertEqual(failure.exception.code, 'backend-unavailable')

    def test_cuda_build_selects_compatible_host_compiler_and_architectures(self):
        cfg = dict(config.DEFAULTS, backend='cuda', cuda_host_compiler='/compiler path/g++', cuda_architectures='75;86')
        import shlex
        flags = shlex.split(config.build_flags(config.validate(cfg)))
        self.assertIn('-DGGML_CUDA=on', flags)
        self.assertIn('-DCMAKE_CUDA_HOST_COMPILER=/compiler path/g++', flags)
        self.assertIn('-DCMAKE_CUDA_ARCHITECTURES=75;86', flags)
        self.assertIn('-DGGML_NATIVE=on', flags)
        mmq = config.build_flags(config.validate(dict(cfg, cuda_architectures='61-virtual;80-virtual', cuda_force_mmq=True)))
        self.assertIn('-DGGML_CUDA_FORCE_MMQ=on', mmq)
        for key, value in [('cuda_host_compiler', 'relative/compiler'), ('cuda_architectures', '75 -DOTHER=on')]:
            with self.assertRaises(lmgguf.ScoringError):
                config.validate(dict(config.DEFAULTS, **{key: value}))

    def test_cpu_and_zero_layers_exclude_all_gpu_devices_and_context_offload(self):
        C = SimpleNamespace(LLAMA_SPLIT_MODE_NONE=0)
        found = [{'handle': 101, 'backend': 'cuda'}]
        for backend in ('cpu', 'cuda'):
            cfg = dict(config.DEFAULTS, backend=backend, gpu_layers=0)
            params = SimpleNamespace(offload_kqv=True, op_offload=True)
            pointers, selected = hardware.model_devices(C, cfg, found, params)
            hardware.context_devices(cfg, params)
            self.assertIsNone(selected); self.assertIsNone(pointers[0])
            self.assertEqual(params.n_gpu_layers, 0)
            self.assertFalse(params.offload_kqv); self.assertFalse(params.op_offload)

    def test_selected_backend_device_and_partial_full_offload_never_fall_back(self):
        C = SimpleNamespace(LLAMA_SPLIT_MODE_NONE=0)
        found = [{'handle': 101, 'backend': 'cuda'}, {'handle': 102, 'backend': 'vulkan'},
                 {'handle': 103, 'backend': 'cuda'}]
        for layers in (2, -1):
            cfg = dict(config.DEFAULTS, backend='cuda', gpu_layers=layers, gpu_device=1)
            params = SimpleNamespace()
            pointers, selected = hardware.model_devices(C, cfg, found, params)
            hardware.context_devices(cfg, params)
            self.assertEqual(list(pointers), [103, None])
            self.assertEqual(selected['handle'], 103)
            self.assertEqual(params.n_gpu_layers, layers)
            self.assertEqual(params.main_gpu, 0); self.assertEqual(params.split_mode, 0)
            self.assertTrue(params.offload_kqv); self.assertTrue(params.op_offload)
        for backend, index in [('cuda', 2), ('metal', 0)]:
            with self.assertRaises(lmgguf.ScoringError) as caught:
                hardware.model_devices(C, dict(config.DEFAULTS, backend=backend, gpu_layers=-1, gpu_device=index), found, SimpleNamespace())
            self.assertEqual(caught.exception.code, 'backend-unavailable')
        with self.assertRaises(lmgguf.ScoringError):
            config.validate(dict(config.DEFAULTS, gpu_device=-1))

    def test_native_device_inventory_uses_registered_device_types_and_hides_pointers(self):
        api = SimpleNamespace()
        rows = {10: ('cpu', 0), 11: ('cuda', 1), 12: ('metal', 2), 13: ('cuda', 3)}
        api.ggml_backend_dev_count = mock.Mock(return_value=4)
        api.ggml_backend_dev_get = mock.Mock(side_effect=lambda i: i + 10)
        api.ggml_backend_dev_type = mock.Mock(side_effect=lambda h: rows[h][1])
        api.ggml_backend_dev_backend_reg = mock.Mock(side_effect=lambda h: h)
        api.ggml_backend_reg_name = mock.Mock(side_effect=lambda h: rows[h][0].encode())
        api.ggml_backend_dev_name = mock.Mock(side_effect=lambda h: ('device-' + str(h)).encode())
        api.ggml_backend_dev_description = mock.Mock(return_value=b'Installed GPU')
        def memory(handle, free, total):
            ctypes.cast(free, ctypes.POINTER(ctypes.c_size_t))[0] = 1024
            ctypes.cast(total, ctypes.POINTER(ctypes.c_size_t))[0] = 4096
        api.ggml_backend_dev_memory = mock.Mock(side_effect=memory)
        found = hardware.devices(SimpleNamespace(_lib=api))
        self.assertEqual([d['handle'] for d in found], [11, 12])
        visible = hardware.public(found)
        self.assertTrue(all('handle' not in d for d in visible))
        self.assertEqual([d['index'] for d in visible], [0, 0])
        self.assertEqual(visible[0]['free_bytes'], 1024)


class ProcessLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.worker = Path(self.temp.name) / 'worker.py'
        self.cfg = dict(config.DEFAULTS, python=sys.executable, model={'model_id': 'fake'}, load_seconds=1)

    def test_loading_cancellation_kills_child_and_releases_registry(self):
        self.worker.write_text('import time\ntime.sleep(20)\n')
        calls = [0]
        def check():
            calls[0] += 1
            if calls[0] > 4:
                raise lmgguf.ScoringError('cancelled', 'Cancelled.')
        with mock.patch('lmlikelihood.WORKER', self.worker), mock.patch('lmlikelihood.revalidate'):
            with self.assertRaises(lmgguf.ScoringError) as caught:
                lmlikelihood.Session(self.cfg, check)
        self.assertEqual(caught.exception.code, 'cancelled')
        self.assertEqual(lmlikelihood.loaded_count(), 0)

    def test_dependency_and_native_load_failures_have_plain_categories(self):
        with mock.patch.dict(sys.modules, {'llama_cpp': None}), self.assertRaises(lmgguf.ScoringError) as caught:
            lmlikelihoodworker.Backend(self.cfg)
        self.assertEqual(caught.exception.code, 'runtime-missing')
        backend = object.__new__(lmlikelihoodworker.Backend)
        for failure, code in [('resources', 'insufficient-resources'), ('incomplete', 'incomplete-model'),
                              ('unsupported', 'unsupported-model'), (None, 'model-load-failed')]:
            backend.failure = failure
            with self.assertRaises(lmgguf.ScoringError) as caught:
                backend.load_error()
            self.assertEqual(caught.exception.code, code)

    def test_loading_timeout_unloads_and_model_is_loaded_once_for_requests(self):
        self.worker.write_text('import time\ntime.sleep(20)\n')
        with mock.patch('lmlikelihood.WORKER', self.worker), mock.patch('lmlikelihood.revalidate'):
            with self.assertRaises(lmgguf.ScoringError) as caught:
                lmlikelihood.Session(self.cfg, lambda: None)
        self.assertEqual(caught.exception.code, 'worker-timeout')
        self.assertEqual(lmlikelihood.loaded_count(), 0)
        self.worker.write_text('import sys,json\nfor line in sys.stdin:\n b=json.loads(line); print(json.dumps({"op":"loaded" if b["op"]=="load" else "target"}),flush=True)\n')
        with mock.patch('lmlikelihood.WORKER', self.worker), mock.patch('lmlikelihood.revalidate'):
            session = lmlikelihood.Session(self.cfg, lambda: None)
            try:
                pid = session.process.pid
                for _ in range(2):
                    self.assertEqual(session.request({'op': 'target'}, 1)['op'], 'target')
                    self.assertEqual(session.process.pid, pid)
            finally:
                session.close()
        self.assertEqual(lmlikelihood.loaded_count(), 0)


class ReviewJobs(unittest.TestCase):
    def setUp(self):
        # The existing job fixture represents ASR awaiting a deliberate choice.
        self.fixture = existing_tests.Jobs('test_changed_source_hash_is_refused')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.job, self.token = self.fixture.job, self.fixture.token
        self.cfg = dict(config.DEFAULTS, model={'model_id': 'installed-model'})
        self.source = self.job['review_evidence']['source_sha256']

    def test_explicit_method_no_chat_call_and_box_unchanged(self):
        with mock.patch('lmlikelihoodconfig.load', return_value=self.cfg), mock.patch('lmgguf.revalidate'), \
                mock.patch('llmadapter.adapter') as chat, mock.patch('sttjobs.threading.Thread') as thread:
            answer = sttjobs.review_likelihood(self.token, self.source, config.revision(self.cfg))
        self.assertEqual(answer['state'], sttjobs.CORRECTING)
        self.assertEqual(self.job['review_choice'], 'likelihood')
        self.assertEqual(self.job['text'], self.fixture.panel)
        chat.assert_not_called(); thread.return_value.start.assert_called_once()

    def test_changed_revision_or_source_refuses_before_worker(self):
        with mock.patch('lmlikelihoodconfig.load', return_value=self.cfg), mock.patch('lmlikelihood.Session') as worker:
            for source, rev in [(self.source, 'old-settings'), ('old-source', config.revision(self.cfg))]:
                with self.assertRaises(sttjobs.Refusal):
                    sttjobs.review_likelihood(self.token, source, rev)
            worker.assert_not_called()

    def test_new_model_drops_old_proposals_and_locks_limit_targets(self):
        self.job.update(state=sttjobs.DONE,review_choice='likelihood',likelihood_revision='older-model',
                        correction_result={'task':'likelihood','suggestions':[{'word_id':'s0w1'}]},
                        review_draft={'locked_word_ids':['s0w0']})
        with mock.patch('lmlikelihoodconfig.load',return_value=self.cfg), mock.patch('lmgguf.revalidate'), \
                mock.patch('sttjobs.threading.Thread') as thread:
            sttjobs.review_likelihood(self.token,self.source,config.revision(self.cfg),['s0w0','s0w1'],False)
        args=thread.call_args.kwargs['args']
        self.assertEqual(args[-2],['s0w1']);self.assertIsNone(args[-1])
        self.assertFalse(args[1]['phonetic_filter'])
        self.assertEqual(self.job['likelihood_revision'],config.revision(self.cfg))
        self.assertIsNone(self.job['correction_result'])

    def test_partial_completion_keeps_asr_and_releases_single_job_slot(self):
        self.job.update(state=sttjobs.CORRECTING, review_choice='likelihood', llm_generation=1)
        out = {'task': 'likelihood', 'suggestions': [], 'complete': False, 'failed_word_ids': ['s0w1']}
        with mock.patch('lmlikelihoodconfig.load', return_value=self.cfg), mock.patch('lmgguf.revalidate'), \
                mock.patch('lmlikelihood.correct', return_value=out):
            sttjobs._likelihood_correct(self.job, self.cfg, llmadapter.Cancellation(), 1, None, None)
        self.assertEqual(self.job['state'], sttjobs.DONE)
        self.assertEqual(self.job['correction']['state'], 'partial')
        self.assertFalse(sttjobs.busy()); self.assertEqual(self.job['text'], self.fixture.panel)

    def test_source_and_model_change_in_flight_discard_scores(self):
        for changed in ('source', 'model'):
            self.job.update(state=sttjobs.CORRECTING, review_choice='likelihood', llm_generation=1, correction={})
            current_cfg = dict(self.cfg, threads=5) if changed == 'model' else self.cfg
            with mock.patch('lmlikelihoodconfig.load', return_value=current_cfg), mock.patch('lmgguf.revalidate'), \
                    mock.patch('sttjobs._review_source_current', return_value=changed != 'source'), \
                    mock.patch('lmlikelihood.correct', return_value={'complete': True, 'failed_word_ids': []}):
                sttjobs._likelihood_correct(self.job, self.cfg, llmadapter.Cancellation(), 1, None, None)
            self.assertEqual(self.job['state'], sttjobs.REVIEW_CHOICE)
            self.assertIsNone(self.job['correction_result'])
            self.assertFalse(sttjobs.busy())

    def test_cancel_invalidates_late_results_and_use_checks_model(self):
        cancel = llmadapter.Cancellation()
        self.job.update(state=sttjobs.CORRECTING, review_choice='likelihood', llm_generation=1, llm_cancel=cancel)
        sttjobs.cancel_review(self.token)
        with mock.patch('lmlikelihoodconfig.load', return_value=self.cfg), mock.patch('lmgguf.revalidate'), mock.patch('lmlikelihood.correct') as worker:
            sttjobs._likelihood_correct(self.job, self.cfg, cancel, 1, None, None)
        self.assertEqual(self.job['state'], sttjobs.DONE, 'cancelling a tool preserves the open review workspace')
        self.assertIsNone(self.job['correction_result'])
        # the transcript is obtainable even when the model's settings changed since the review: what was accepted is checked
        # edit by edit, never refused for what the settings are now (and with nothing accepted it is the Whisper text itself)
        self.job.update(state=sttjobs.DONE, review_choice='likelihood', likelihood_revision='old-revision')
        with mock.patch('lmlikelihoodconfig.load', return_value=self.cfg):
            used = sttjobs.use_review(self.token, self.source, {})
        self.assertEqual(used['text'], self.fixture.panel)
        self.assertEqual(used['skipped'], [])


if __name__ == '__main__':
    unittest.main()
