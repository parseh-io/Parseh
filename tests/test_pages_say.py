# SPDX-License-Identifier: GPL-3.0-or-later
"""What the pages say that they did not before (a0.6.3, lane J2): TO-DO 6.11, 6.12, 6.19, 7.6, 10.7.

    python3 -m unittest tests.test_pages_say

The answers the pages read, asked of the modules behind them; tests/pages_say.mjs drives the pages.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import chunker    # noqa: E402
import draft      # noqa: E402
import languages  # noqa: E402
import lookup     # noqa: E402
import segmenter  # noqa: E402

# one sentence a language, long enough to have a phrase to cut, and no comma in it
SENTENCE = {
    'fa': 'من دیروز با دوستم به کتابخانه‌ی بزرگ شهر رفتم و چند کتاب خریدم.',
    'ar': 'ذهبت أمس مع صديقي إلى المكتبة الكبيرة في المدينة واشتريت بعض الكتب.',
    'it': 'Ieri sono andato con il mio amico alla grande biblioteca della città e ho comprato alcuni libri.',
    'ja': '昨日友達と一緒に町の大きな図書館へ行って本を何冊か買いました。',
    'fr': 'Hier je suis allé avec mon ami à la grande bibliothèque de la ville et j’ai acheté quelques livres.',
    'de': 'Gestern bin ich mit meinem Freund in die große Bibliothek der Stadt gegangen und habe Bücher gekauft.',
    'tr': 'Dün arkadaşımla şehrin büyük kütüphanesine gittim ve birkaç kitap aldım.',
    'en': 'Yesterday I went with my friend to the big library of the town and bought some books.',
    'hi': 'कल मैं अपने दोस्त के साथ शहर के बड़े पुस्तकालय गया और कुछ किताबें खरीदीं।',
    'es': 'Ayer fui con mi amigo a la gran biblioteca de la ciudad y compré algunos libros.',
    'zh': '昨天我和朋友一起去了城里的大图书馆买了几本书。',
    'ca': 'Ahir vaig anar amb el meu amic a la gran biblioteca de la ciutat i vaig comprar uns llibres.',
}


class SenseGroupsFellBack(unittest.TestCase):
    """6.11: "sense groups" asked, one chunk per sentence given -- the answer says which was USED, and why."""

    def test_every_language_has_a_sentence_here(self):
        self.assertEqual(set(SENTENCE), {c for c in __import__('json').loads(Path(languages.REGISTRY).read_text(encoding='utf-8')) if not c.startswith('_')})

    def test_every_language_without_a_dictionary(self):
        with patch.object(lookup, 'available', lambda code: False):
            for code, text in SENTENCE.items():
                with self.subTest(code=code):
                    r = draft.book_from_text(text, code, 'T', how='phrase')
                    self.assertEqual(r['how'], 'phrase', 'the way asked is still said')
                    cut = chunker.chunk(text, code, 'phrase')
                    if len(cut) == 1:
                        # one chunk: the answer says the way used, and a sentence of why naming the language
                        self.assertEqual(r['how_used'], 'sentence')
                        self.assertIn('every sentence stayed one chunk', r['cut_note'])
                        self.assertIn(languages.get(code).name, r['cut_note'])
                        self.assertIn('Settings → Reading help', r['cut_note'])
                    else:
                        self.assertEqual(r['how_used'], 'phrase')

    def test_the_six_without_word_lists_say_why(self):
        with patch.object(lookup, 'available', lambda code: False):
            for code in ('fr', 'de', 'es', 'ca', 'hi', 'ar'):
                with self.subTest(code=code):
                    why = chunker.phrase_short(code)
                    self.assertIn('no %s dictionary is installed' % languages.get(code).name, why)
            for code in ('fa', 'it', 'en', 'tr', 'ja', 'zh'):
                with self.subTest(code=code):
                    self.assertEqual(chunker.phrase_short(code), '', 'its own lists (or rules) cut it')

    def test_an_arabic_variety_is_asked_by_its_own_key(self):
        with patch.object(lookup, 'available', lambda code: False):
            r = draft.book_from_text(SENTENCE['ar'], 'ar', 'T', how='phrase', variety='egy')
            self.assertEqual(r['how_used'], 'sentence')
            self.assertIn('Arabic', r['cut_note'])

    def test_a_dictionary_answers_the_why(self):
        with patch.object(lookup, 'available', lambda code: True):
            self.assertEqual(chunker.phrase_short('de'), '')

    def test_one_chunk_per_sentence_asked_says_nothing(self):
        r = draft.book_from_text(SENTENCE['de'], 'de', 'T', how='sentence')
        self.assertEqual((r['how_used'], r['cut_note']), ('sentence', ''))

    def test_a_video_and_more_text_answer_the_same(self):
        with patch.object(lookup, 'available', lambda code: False):
            v = draft.video_from_transcript('0:00\n' + SENTENCE['es'] + '\n0:05\n' + SENTENCE['es'] + '\n', 'es',
                                            video_id='abcdefghijk', how='phrase')
            self.assertEqual(v['how_used'], 'sentence')
            self.assertIn('Spanish', v['cut_note'])


class NoProposeSaysWhy(unittest.TestCase):
    """6.12: with no analyzers, the answer the word strip reads says why, and where they come from."""

    def test_without_the_analyzers(self):
        with patch.object(segmenter, 'available', lambda code: False):
            for code, name in (('ja', 'SudachiPy'), ('zh', 'spacy-pkuseg and pypinyin')):
                with self.subTest(code=code):
                    why = segmenter.why_not(code, 'Parseh')
                    self.assertIn(name, why)
                    self.assertIn(sys.executable, why)
                    self.assertIn('installer', why)
                    self.assertNotIn('pip', why, 'no command to type')

    def test_with_them_or_another_language(self):
        with patch.object(segmenter, 'available', lambda code: True):
            self.assertEqual(segmenter.why_not('ja'), '')
        self.assertEqual(segmenter.why_not('fa'), '')


if __name__ == '__main__':
    unittest.main()
