# SPDX-License-Identifier: GPL-3.0-or-later
"""What the pages say that they did not before (a0.6.3, lane J2): TO-DO 6.11, 6.12, 6.19, 7.6, 10.7.

    python3 -m unittest tests.test_pages_say

The answers the pages read, asked of the modules behind them; tests/pages_say.mjs drives the pages.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT / 'youtube' / 'lib'))
import anki_store  # noqa: E402
import books      # noqa: E402
import chunker    # noqa: E402
import draft      # noqa: E402
import languages  # noqa: E402
import lookup     # noqa: E402
import make_index  # noqa: E402
import segmenter  # noqa: E402
import ytpages    # noqa: E402

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


class BookCardGlossing(unittest.TestCase):
    """6.19: a book's card says how far its glossing has come, from two numbers its reader carries."""

    def build(self, book_dir):
        r = subprocess.run([sys.executable, str(ROOT / 'lib' / 'tex2html.py'), '--book', str(book_dir)],
                           capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr)
        return make_index.stats(books.Book(str(book_dir)))

    def test_a_draft_and_a_glossed_book(self):
        with tempfile.TemporaryDirectory() as td:
            got = draft.book_from_text(SENTENCE['de'] + chr(10) * 2 + SENTENCE['de'], 'de', 'Zwei', into=td)
            st = self.build(got['dir'])
            self.assertEqual((st['glossed'], st['glossable']), (0, got['chunks']))
            tag = ''.join(make_index.gloss_tag(st, 'german/zwei'))
            self.assertIn('0 of %d chunks glossed' % got['chunks'], tag)
            self.assertIn('data-book="german/zwei"', tag)
            fa = Path(td) / 'persian' / 'mini-fa'
            shutil.copytree(ROOT / 'tests' / 'fixtures' / 'books' / 'persian' / 'mini-fa', fa)
            st = self.build(fa)
            self.assertGreater(st['glossable'], 0)
            self.assertEqual(st['glossed'], st['glossable'])
            self.assertIn('>%d chunks glossed<' % st['glossable'], ''.join(make_index.gloss_tag(st)))

    def test_a_reader_built_before_says_nothing(self):
        self.assertEqual(make_index.gloss_tag({'built': True, 'chunks': 12, 'subs': 3}), [])


class StartItEmptyFetches(unittest.TestCase):
    """7.6: the oEmbed answer, and which of two reasons it has none: no network, or YouTube said no."""

    def answer(self, raised=None, body=b'{"title": "T", "author_name": "C"}'):
        import io
        import urllib.error

        def urlopen(url, timeout=None):
            self.assertIn('oembed', url)
            if raised:
                raise raised
            return io.BytesIO(body)
        with patch('urllib.request.urlopen', urlopen):
            return ytpages.oembed_why('abcdefghijk')

    def test_the_three_answers(self):
        import urllib.error
        self.assertEqual(self.answer(), ({'title': 'T', 'channel': 'C'}, ''))
        self.assertEqual(self.answer(urllib.error.URLError('no network')), ({}, 'offline'))
        self.assertEqual(self.answer(TimeoutError()), ({}, 'offline'))
        self.assertEqual(self.answer(urllib.error.HTTPError('u', 404, 'Not Found', {}, None)), ({}, 'refused'))
        self.assertEqual(self.answer(body=b'{}'), ({}, 'refused'))

    def test_each_reason_is_said(self):
        for why in ('offline', 'refused'):
            self.assertIn('video info', ytpages.FETCH_SAID[why])
            self.assertIn('Unknown channel', ytpages.FETCH_SAID[why])


class AnkiDuplicateAsked(unittest.TestCase):
    """10.7: a card the Anki deck already has is asked about, as an exercise deck asks; `force` adds it again."""

    def add(self, anki, deck='Mots', **card):
        c = dict({'lang': 'fr', 'kind': 'vocab', 'fa': 'la ville', 'en': 'the town'}, **card)
        force = c.pop('force', False)
        return anki_store.add_card(anki, {'deck': deck, 'deck_lang': 'fr', 'card': c, 'force': force})

    def test_asked_then_added_again(self):
        with tempfile.TemporaryDirectory() as anki:
            self.assertEqual(self.add(anki)[1], 200)
            res, status = self.add(anki, fa='  la\u00a0ville ', en='another meaning')
            self.assertEqual((status, res.get('conflict')), (409, 'duplicate'), res)
            self.assertIn('already in \u201cMots\u201d', res['error'])
            cards = Path(anki) / 'french' / 'mots' / 'cards'
            self.assertEqual(len(list(cards.glob('*.json'))), 1, 'nothing was written')
            res, status = self.add(anki, force=True)
            self.assertEqual(status, 200, res)
            self.assertEqual(res['deck']['cards'], 2)

    def test_not_a_duplicate(self):
        with tempfile.TemporaryDirectory() as anki:
            self.assertEqual(self.add(anki)[1], 200)
            self.assertEqual(self.add(anki, fa='la vile')[1], 200, 'another front')
            self.assertEqual(self.add(anki, kind='opposites', opp='le village')[1], 200, 'another note type')
            self.assertEqual(self.add(anki, deck='Autres')[1], 200, 'another deck')

    def test_every_language(self):
        """The front is compared as it is written: right to left, CJK, decomposed marks alike."""
        import unicodedata
        with tempfile.TemporaryDirectory() as anki:
            for code, text in SENTENCE.items():
                with self.subTest(code=code):
                    word = text.split()[0] if ' ' in text else text[:3]
                    card = {'lang': code, 'kind': 'vocab', 'fa': word, 'en': 'x'}
                    if languages.get(code).reading:
                        card['kana'] = 'かな'
                    body = {'deck': 'All', 'deck_lang': code, 'card': card}
                    self.assertEqual(anki_store.add_card(anki, body)[1], 200)
                    again = dict(body, card=dict(card, fa=unicodedata.normalize('NFD', word)))
                    self.assertEqual(anki_store.add_card(anki, again)[1], 409)


class NoProposeSaysWhy(unittest.TestCase):
    """6.12: with no analyzers, the answer the word strip reads says why, and where they come from."""

    def test_without_the_analyzers(self):
        with patch.object(segmenter, 'available', lambda code: False):
            for code, name in (('ja', 'SudachiPy'), ('zh', 'spacy-pkuseg and pypinyin')):
                with self.subTest(code=code):
                    why = segmenter.why_not(code, 'Parseh')
                    self.assertIn(name, why)
                    self.assertIn(sys.executable, why)
                    self.assertIn('Packages this Parseh lacks', why)
                    self.assertNotIn('pip', why, 'no command to type')

    def test_with_them_or_another_language(self):
        with patch.object(segmenter, 'available', lambda code: True):
            self.assertEqual(segmenter.why_not('ja'), '')
        self.assertEqual(segmenter.why_not('fa'), '')


if __name__ == '__main__':
    unittest.main()
