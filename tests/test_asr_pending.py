# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import sys
import tempfile
import time
import unittest
from unittest import mock
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / p) for p in ('lib', 'youtube/lib')]
import aboutpage
import asrcorrection
import asrpending
import lmlikelihood
import lmlikelihoodconfig
import lmlikelihoodcore
import lmsound
import network
import sttjobs
import ytpages


class Pending(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.patch = mock.patch.object(ytpages, 'VIDEOS', self.temp.name); self.patch.start(); self.addCleanup(self.patch.stop)
        self.token = 'PendingReview001'
        self.panel = '0:00\nLoro anno detto ciao.\n'
        self.evidence = asrcorrection.evidence([{'start':0,'end':3,'text':'Loro anno detto ciao.', 'words':[
            {'text':'Loro','score':.9},{'text':'anno','score':.2},{'text':'detto','score':.2},{'text':'ciao.','score':.9}]}],self.panel,'it')
        self.job = dict(id=self.token,kind='youtube',source={'kind':'youtube','id':'dQw4w9WgXcQ'},film=None,
            lang='it',model='large-v3-turbo',mode='cpu',device='cpu',device_name='',fell_back=False,
            text=self.panel,review_evidence=self.evidence,review_choice='whisper',correction={'state':'not-requested'},
            state=sttjobs.DONE,finished=time.time(),created=1,started=1,total=3,done=3,have=0,sealed=True,
            facts={},notes=[],warning='',words=None,proc=None,error=None,cancelled=False)
        sttjobs.JOBS[self.token]=self.job
        self.addCleanup(sttjobs.JOBS.pop,self.token,None)

    def test_round_trip_only_allowlisted_data_no_audio_or_credentials(self):
        self.job.update(api_key='secret-test',pcm='/private/audio',unrelated='secret-other')
        asrpending.save(self.job)
        raw=asrpending.path(self.token).read_text()
        self.assertNotIn('secret-test',raw);self.assertNotIn('/private/audio',raw);self.assertNotIn('secret-other',raw)
        self.assertEqual(asrpending.load(self.token)['job']['text'],self.panel)
        self.assertEqual(asrpending.listing()[0]['job'],self.token)

    def test_obsolete_audio_evidence_is_not_restored_or_saved(self):
        draft = {'manual_edits': {'s0w1': 'hanno'}, 'locked_word_ids': ['s0w1'],
                 'phonetic_filter': False}
        self.job['review_draft'] = draft
        self.job['external_review'] = {'task': 'workspace', 'prompt': 'heard_ipa,ipa_attribution'}
        self.job['automatic_phonetic'] = True
        self.job['phonetic'] = {'state': 'complete'}
        self.evidence['phonetic'] = {'state': 'complete'}
        self.evidence['segments'][0]['words'][1]['phonetic'] = {'state': 'complete', 'ipa': 'old'}
        asrpending.save(self.job)
        stored = json.loads(asrpending.path(self.token).read_text())
        self.assertNotIn('phonetic', stored['job'])
        self.assertNotIn('external_review', stored['job'])
        self.assertNotIn('automatic_phonetic', stored['job'])
        self.assertNotIn('phonetic', stored['job']['review_evidence'])
        self.assertNotIn('phonetic', stored['job']['review_evidence']['segments'][0]['words'][1])
        self.assertEqual(stored['job']['review_draft'], draft)
        # Also migrate a pre-removal record, retaining text, times and edits.
        stored['job']['external_review'] = {'prompt': 'heard_ipa,ipa_audio_start'}
        stored['job']['automatic_phonetic'] = True
        stored['job']['phonetic'] = {'state': 'complete'}
        stored['job']['review_evidence']['segments'][0]['words'][1]['phonetic'] = {'ipa': 'old'}
        asrpending.path(self.token).write_text(json.dumps(stored))
        restored = asrpending.load(self.token)['job']
        self.assertNotIn('phonetic', restored)
        self.assertNotIn('external_review', restored)
        self.assertNotIn('phonetic', restored['review_evidence']['segments'][0]['words'][1])
        self.assertEqual(restored['review_draft'], draft)
        self.assertEqual(restored['text'], self.panel)
        self.assertIn('phonetic', self.evidence['segments'][0]['words'][1])

    def test_restore_after_server_memory_loss_never_starts_model(self):
        asrpending.save(self.job);sttjobs.JOBS.pop(self.token)
        with mock.patch('lmlikelihood.Session') as worker:
            restored=sttjobs.result(self.token)
            worker.assert_not_called()
        self.assertEqual(restored['text'],self.panel)
        self.assertEqual(sttjobs.resume_review(self.token)['source'],self.job['source'])

    def test_manual_edits_locks_and_selection_survive_reload(self):
        draft={'manual_edits':{'s0w1':'hanno'},'decisions':{},'locked_word_ids':['s0w1'],'selection':['s0w1','s0w2'],'browser':{'transcript':'previous box','hash':'kept'}}
        sttjobs.save_review_draft(self.token,self.evidence['source_sha256'],draft,0)
        sttjobs.JOBS.pop(self.token)
        restored=sttjobs.result(self.token)
        self.assertEqual(restored['review']['draft'],draft)
        self.assertEqual(sttjobs._review_targets(sttjobs.JOBS[self.token],'likelihood',None),['s0w2'])
        self.assertEqual(sttjobs._review_targets(sttjobs.JOBS[self.token],'full',['s0w0','s0w1']),['s0w0'])

    def test_source_generation_and_invalid_lock_rejected(self):
        for source,generation,draft in [('wrong',0,{}),(self.evidence['source_sha256'],99,{}),(self.evidence['source_sha256'],0,{'locked_word_ids':['unknown']}),(self.evidence['source_sha256'],0,{'locked_word_ids':[{}]})]:
            with self.assertRaises(sttjobs.Refusal):sttjobs.save_review_draft(self.token,source,draft,generation)

    def test_corrupt_record_refused_without_destroying_it(self):
        asrpending.save(self.job);p=asrpending.path(self.token);d=json.loads(p.read_text());d['job']['text']='changed';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):asrpending.load(self.token)
        self.assertTrue(p.exists())

    def test_storage_budget_does_not_delete_existing_draft(self):
        asrpending.save(self.job)
        with mock.patch.object(asrpending, 'TOTAL_LIMIT', 1):
            with self.assertRaises(ValueError): asrpending.save(self.job)
        self.assertEqual(asrpending.load(self.token)['job']['text'], self.panel)
        another=dict(self.job,id='PendingReview002')
        with mock.patch.object(asrpending, 'RECORD_LIMIT', 1):
            with self.assertRaises(ValueError): asrpending.save(another)
        self.assertFalse(asrpending.path(another['id']).exists())

    def test_pasted_answer_and_scope_saved_with_size_validation(self):
        draft={'scope':'all','external_drafts':{'session:0':'متن فارسی'}}
        sttjobs.save_review_draft(self.token,self.evidence['source_sha256'],draft)
        self.assertEqual(asrpending.load(self.token)['job']['review_draft'],draft)
        for invalid in ({'scope':'wrong'},{'selected_word':[]},{'external_drafts':{'s': 'x'*131073}}):
            with self.assertRaises(sttjobs.Refusal): sttjobs.save_review_draft(self.token,self.evidence['source_sha256'],invalid)

    def test_the_walk_through_the_answers_is_saved_with_the_draft_and_only_of_words_that_exist(self):
        word = next(iter(self.evidence['segments'][0]['words']))['word_id']
        draft = {'walk': {'kept': [word], 'skipped': [], 'include_agree': True}}
        sttjobs.save_review_draft(self.token, self.evidence['source_sha256'], draft)
        self.assertEqual(asrpending.load(self.token)['job']['review_draft'], draft)
        for invalid in ({'walk': {'kept': ['nowhere']}}, {'walk': {'skipped': 'all'}}, {'walk': {'include_agree': 'yes'}},
                        {'walk': {'unknown': []}}, {'walk': []}, {'walk': {'kept': [word, 7]}}):
            with self.assertRaises(sttjobs.Refusal, msg=str(invalid)):
                sttjobs.save_review_draft(self.token, self.evidence['source_sha256'], invalid)

    def test_traversal_rejected_and_missing_list_is_empty(self):
        self.assertEqual(asrpending.listing(),[])
        with self.assertRaises(ValueError):asrpending.load('../elsewhere')

    def test_interrupted_review_restores_without_resuming_inference(self):
        self.job.update(state=sttjobs.CORRECTING,review_choice='likelihood',correction={'state':'running'})
        asrpending.save(self.job);sttjobs.JOBS.pop(self.token)
        view=sttjobs.result(self.token)
        self.assertEqual(view['review']['correction']['state'],'interrupted')
        self.assertEqual(sttjobs.status(self.token)['state'],sttjobs.DONE)

    def test_explicit_discard_removes_disk_draft(self):
        asrpending.save(self.job);sttjobs.cancel(self.token)
        with self.assertRaises(sttjobs.Refusal):
            sttjobs.result(self.token)
        self.assertFalse(asrpending.path(self.token).exists())

    def test_discard_llm_review_does_not_recreate_draft(self):
        self.job.update(review_choice='llm',llm_generation=0,stop_review=__import__('threading').Event())
        asrpending.save(self.job)
        sttjobs.cancel(self.token)
        self.assertFalse(asrpending.path(self.token).exists())

    def test_selected_targets_keep_full_context_and_confident_single_word(self):
        all_requests=lmlikelihood.requests(self.evidence,self.panel,lmlikelihoodconfig.DEFAULTS)
        single=lmlikelihood.requests(self.evidence,self.panel,lmlikelihoodconfig.DEFAULTS,['s0w1'])[0]
        self.assertEqual(single['left'],all_requests[0]['left']);self.assertEqual(single['right'],all_requests[0]['right'])
        self.assertIn('Loro',single['left']);self.assertIn('ciao',single['right'])
        self.assertEqual(len(lmlikelihood.requests(self.evidence,self.panel,lmlikelihoodconfig.DEFAULTS,['s0w0'])),1)

    def test_full_text_edits_cannot_escape_selected_words(self):
        unit=asrcorrection.sentence_units(self.evidence,task='full')[0]
        unit['targets']=[w for w in unit['targets'] if w['word_id']=='s0w1']
        props,_=asrcorrection.full_sentence_result('Loro hanno detto salve.',unit)
        self.assertEqual([p['word_id'] for p in props],['s0w1'])

    def test_mandatory_candidates_bypass_search_filters(self):
        word={'text':'anno','asr_alternatives':[{'text':'completelydifferent','score':.001}]}
        entries=lmlikelihoodcore.candidates(word,[])
        self.assertEqual([c['text'] for c in entries],['anno','completelydifferent'])
        self.assertTrue(all(c['mandatory'] for c in entries))

    def test_sound_approximation_unicode_and_invalid_settings(self):
        self.assertGreater(lmsound.similarity('جل','جلو'),.55)
        self.assertEqual(lmsound.similarity('حس','هث'),1)
        self.assertEqual(lmsound.sound_similarity('カ','か','ja'),1)
        self.assertIsNone(lmsound.sound_similarity('科','化','ja'))
        with mock.patch.object(lmsound, 'readings', side_effect=lambda text,language: ('か',)):
            self.assertEqual(lmsound.sound_similarity('科','化','ja'),1)
        for value in (-1,2,float('nan'),float('inf')):
            with self.assertRaises(Exception):lmlikelihoodconfig.validate(dict(lmlikelihoodconfig.DEFAULTS,minimum_candidate_probability=value))

    def test_about_paths_escaped_and_host_platform_neutral(self):
        with mock.patch('settingspage.ROOT','/Applications/Parseh & data'):
            page=aboutpage.page(network.SELF)
        self.assertIn('/Applications/Parseh &amp; data/serve.sh',page);self.assertIn('serve.bat',page)
        with mock.patch('settingspage.ROOT',r'C:\Users\Person\Parseh'),mock.patch.object(aboutpage,'Path',PureWindowsPath):
            page=aboutpage.page(network.SELF)
        self.assertIn(r'C:\Users\Person\Parseh\serve.sh',page)
        self.assertIn(r'C:\Users\Person\Parseh\serve.bat',page)

if __name__=='__main__':unittest.main()
