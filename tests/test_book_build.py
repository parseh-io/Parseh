# SPDX-License-Identifier: GPL-3.0-or-later
"""A book built from a page: the job, the route, the card and the reader's button.

    python3 -m unittest discover -s tests -p test_book_build.py

Runs under any Python.  The build is stood in for everywhere but once: a
fixture's reader, built for real by the Python path Windows takes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT))
import bookbuild   # noqa: E402
import books       # noqa: E402
import make_index  # noqa: E402
import tex2html    # noqa: E402


class OneChapterAtATime(unittest.TestCase):
    """What a book of many chapters leaves beside its reader.

    The first chapter travels in the page and every other one is a file the
    page fetches when it is wanted; a book of ONE chapter is written exactly
    as it always was, which is what keeps every built fixture unchanged.
    """

    def chaps(self, n):
        return {"sections": [(i, '<section class="chapter" data-ch="%d">c%d'
                                 '</section>' % (i, i)) for i in range(n)],
                "tail": '<div class="gap last"></div>'}

    def test_one_chapter_is_written_as_it_always_was(self):
        shell, files = tex2html.one_chapter_at_a_time(self.chaps(1), "WHOLE BOOK")
        self.assertEqual(shell, "WHOLE BOOK")
        self.assertEqual(files, [])

    def test_the_first_travels_and_the_others_are_files(self):
        shell, files = tex2html.one_chapter_at_a_time(self.chaps(3), "WHOLE BOOK")
        self.assertIn("c0", shell, "the first chapter is in the page")
        for gone in ("c1", "c2"):
            self.assertNotIn(gone, shell, "the others are not")
        # a placeholder keeps its chapter index: that is what the page fetches by
        self.assertIn('data-ch="1" data-part="ch-1.html"', shell)
        self.assertIn('data-ch="2" data-part="ch-2.html"', shell)
        # the gap that closes the book belongs to the book, not to its last
        # chapter, so it stays in the page
        self.assertIn('<div class="gap last"></div>', shell)
        self.assertEqual([n for n, _ in files], ["ch-1.html", "ch-2.html"])
        self.assertIn("c1", files[0][1])
        self.assertIn("c2", files[1][1])


def wait(book, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        st = bookbuild.status(book)
        if st['state'] != 'running':
            return st
        time.sleep(0.02)
    raise AssertionError('the build never ended')


class Job(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.book = os.path.join(td.name, 'books', 'japanese', 'tale')
        os.makedirs(self.book)
        self.addCleanup(bookbuild.JOBS.clear)

    def test_a_build_runs_keeps_what_it_says_and_ends(self):
        def runner(cmd, say):
            say('== tale')
            say('   pdf: 0 overfull boxes, 19 pages')
            return 0
        job, started = bookbuild.start(self.book, 'pdf', runner=runner)
        self.assertTrue(started)
        self.assertEqual((job['state'], job['what']), ('running', 'pdf'))
        st = wait(self.book)
        self.assertEqual((st['state'], st['ok'], st['code']), ('done', True, 0))
        self.assertEqual(st['log'], ['== tale', '   pdf: 0 overfull boxes, 19 pages'])

    def test_the_endings_a_terminal_reads_reach_the_page_in_plain_words(self):
        # TO-DO §5.8: build.sh's own words, as it prints them
        def runner(cmd, say):
            say('== tale')
            say('   NO LOG at /books/german/tale/main.log -- lualatex did not run')
            say('   NO HYPHENATION PATTERNS for ngerman -- every line was broken at ENGLISH')
            say('   points.  The PDF is sound and the line breaks are wrong; fix it with')
            say('   ./install.sh --pdf and rebuild with --force.')
            say('   the PDF did not build -- writing the reader anyway')
            say('')
            say('0 book(s) built, 0 unchanged')
            say('Serve everything with:  ./serve.sh')
            return 1
        bookbuild.start(self.book, 'pdf', runner=runner)
        st = wait(self.book)
        said = '\n'.join(st['log'])
        for terminal in ('./serve.sh', './install.sh', 'NO LOG', 'NO HYPHENATION', '--force'):
            self.assertNotIn(terminal, said)
        self.assertIn('LaTeX could not run: LuaLaTeX is not on this computer', said)
        self.assertIn('no hyphenation patterns for German on this computer', said)
        self.assertIn('Parseh cannot install', said)
        # and the failure is said with it, as the making panel says a build's
        # failure (lib/making.py build_words, the mirror of parseh.js buildWhy)
        import making
        self.assertIn('the PDF was not made -- LaTeX could not run', making.build_words(st['log']))

    def test_one_build_a_book_at_a_time(self):
        gate = threading.Event()

        def runner(cmd, say):
            gate.wait(5)
            return 1
        bookbuild.start(self.book, 'pdf', runner=runner)
        job, started = bookbuild.start(self.book, 'html', runner=runner)
        self.assertFalse(started)
        self.assertEqual(job['what'], 'pdf', 'the build already running is the answer')
        gate.set()
        st = wait(self.book)
        self.assertEqual((st['state'], st['ok']), ('failed', False))
        _job, started = bookbuild.start(self.book, 'html', runner=lambda cmd, say: 0)
        self.assertTrue(started, 'and once it ends another may start')
        wait(self.book)

    def test_a_long_log_keeps_its_end(self):
        def runner(cmd, say):
            for i in range(bookbuild.KEEP + 50):
                say('line %d' % i)
            return 0
        bookbuild.start(self.book, runner=runner)
        st = wait(self.book)
        self.assertEqual(len(st['log']), bookbuild.KEEP)
        self.assertEqual(st['log'][-1], 'line %d' % (bookbuild.KEEP + 49))

    def test_an_unknown_build_is_refused_and_starts_nothing(self):
        with self.assertRaises(ValueError):
            bookbuild.start(self.book, 'sideways')
        self.assertEqual(bookbuild.status(self.book)['state'], 'idle')

    def test_build_sh_where_there_is_a_shell_and_python_where_there_is_none(self):
        book = str(ROOT / 'books' / 'japanese' / 'momotaro')
        with mock.patch.object(bookbuild.runtime, 'WIN', False), \
                mock.patch.object(bookbuild.shutil, 'which', lambda name: '/bin/sh'):
            self.assertEqual(bookbuild.command(book, 'pdf'),
                             ['sh', os.path.join(bookbuild.ROOT, 'build.sh'), 'japanese/momotaro'])
            self.assertEqual(bookbuild.command(book, 'html'),
                             ['sh', os.path.join(bookbuild.ROOT, 'build.sh'), '--html', 'japanese/momotaro'])
        with mock.patch.object(bookbuild.runtime, 'WIN', True):
            cmd = bookbuild.command(book, 'html')
            self.assertEqual(cmd[1:], [os.path.realpath(bookbuild.__file__), os.path.realpath(book), '--html'])


class Route(unittest.TestCase):
    def setUp(self):
        import serve
        self.serve = serve
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        book = root / 'books' / 'japanese' / 'tale'
        book.mkdir(parents=True)
        (book / 'book.json').write_text(json.dumps({'slug': 'tale'}), encoding='utf-8')
        patcher = mock.patch.object(serve._AtRoot, 'directory', str(root))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.book = str(book)
        self.addCleanup(bookbuild.JOBS.clear)

    def handler(self, body=None):
        h = object.__new__(self.serve.Handler)
        h._json_body = lambda: {} if body is None else body
        h.sent = []
        h.send_json = lambda payload, status=200: h.sent.append((status, payload))
        return h

    def test_a_build_is_started_from_the_card_or_the_reader_and_polled(self):
        calls = []

        def start(book, what='pdf', runner=None):
            calls.append((os.path.realpath(book), what))
            return {'state': 'running', 'what': what, 'log': []}, len(calls) == 1
        with mock.patch.object(self.serve.bookbuild, 'start', start):
            h = self.handler({'what': 'html'})
            h._route('POST', '/books/japanese/tale/__build')
            self.assertEqual(h.sent[-1][0], 200)
            self.assertTrue(h.sent[-1][1]['ok'])
            self.assertEqual(calls[0], (os.path.realpath(self.book), 'html'))
            h._route('POST', '/books/japanese/tale/reader/__build')
            self.assertEqual(h.sent[-1][0], 409, 'the reader asks relative to itself; one build at a time')
        h = self.handler()
        h._route('GET', '/books/japanese/tale/reader/__build/status')
        self.assertEqual(h.sent[-1], (200, {'state': 'idle', 'what': None, 'log': [], 'ok': True}))

    def test_what_is_not_a_book_or_not_a_build_is_refused(self):
        h = self.handler()
        h._route('POST', '/books/japanese/nothing/__build')
        self.assertEqual(h.sent[-1][0], 404)
        h._route('POST', '/books/%2e%2e%2fsomewhere/__build')
        self.assertEqual(h.sent[-1][0], 404)
        h = self.handler({'what': 'sideways'})
        h._route('POST', '/books/japanese/tale/__build')
        self.assertEqual(h.sent[-1][0], 400)
        h._route('GET', '/books/japanese/tale/__build')
        self.assertEqual(h.sent[-1][0], 405)
        self.assertEqual(bookbuild.JOBS, {}, 'and nothing started')


class Pages(unittest.TestCase):
    def test_an_unbuilt_card_is_all_button_and_a_built_one_rebuilds(self):
        b = books.Book(str(ROOT / 'tests' / 'fixtures' / 'books' / 'english' / 'mini-en'))
        url = 'data-build="%s/__build"' % b.rel_from_books()
        with mock.patch.object(make_index, 'stats', lambda book: {'built': False}):
            html = make_index.card(b)
        self.assertIn(url, html.split('>', 1)[0], 'the card itself builds')
        self.assertIn('>build</button>', html)
        with mock.patch.object(make_index, 'stats', lambda book: {'built': True, 'chapters': [1], 'subs': 3}):
            html = make_index.card(b)
        self.assertNotIn('data-build', html.split('>', 1)[0])
        self.assertIn('class="card-build"', html)
        self.assertIn('>rebuild</button>', html)

    def test_a_book_brought_back_goes_on_the_shelf_and_its_card_builds_it(self):
        """ONE WAY TO BUILD A BOOK, not two.

        The panel used to carry a build of its own, with its own ways of
        going wrong.  An installed book is now on the shelf at once, grey
        like any book nobody has built, and the `build` button on its card
        is the only one -- the same button, the same route, the same job.
        """
        panel = make_index.bundle_panel('book', '/books/__upload')
        self.assertNotIn('id="takebuild"', panel)
        self.assertNotIn('Parseh.buildBook', panel)
        self.assertNotIn("'/' + j.dir + '/__build'", panel)
        self.assertIn('on the shelf now', panel)
        self.assertIn('not built yet', panel)
        self.assertIn('id="takereload"', panel, 'the list, which is where that card is')
        self.assertNotIn('takecopy', panel, 'no command to copy into a terminal')
        self.assertNotIn('Parseh.copy(j.rebuild)', panel)

    def test_the_pages_carry_the_buttons_handlers(self):
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        self.assertIn("document.addEventListener('click', cardBuild, true)", js)
        self.assertIn('buildBook: buildBook', js)
        tex = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        self.assertIn('id="buildbook"', tex)
        self.assertIn("Parseh.buildBook('__build'", tex)
        self.assertNotIn('nothing on this page can run it', tex)


class BroughtBackIsOnTheShelf(unittest.TestCase):
    """A bundle installed is a CARD, not only a directory.

    The library page is a file make_index writes, and the upload used to
    leave it alone: a book brought back was on disk and on no page, which is
    what "the book does not appear" was.  The whole way through is walked
    here -- a fixture packed, installed into a toolbox of its own, and the
    page written again -- because the two halves were each fine on their own.
    """

    def test_an_installed_book_appears_grey_with_its_build_button(self):
        import books as booklib
        import bundle
        src = ROOT / 'tests' / 'fixtures' / 'books' / 'english' / 'mini-en'
        data, _ = bundle.pack_book(str(src))
        with tempfile.TemporaryDirectory() as td:
            r = bundle.install(data, root=td)
            self.assertTrue(r.get('ok'), r)
            self.assertEqual(r.get('kind'), 'book')
            shelf = os.path.join(td, 'books')
            # the page written for THAT toolbox, as _write_library writes it
            # for the real one
            with mock.patch.object(booklib, 'BOOKS_DIR', shelf), \
                    mock.patch.object(make_index, 'BOOKS_DIR', shelf), \
                    mock.patch.object(make_index, 'all_books',
                                      lambda: booklib.all_books(root=shelf)):
                make_index.main()
            html = Path(shelf, 'index.html').read_text(encoding='utf-8')
        self.assertIn('mini-en', html, 'the book brought back has a card')
        # grey, exactly like a book nobody has ever built: a bundle carries no
        # reader, so there is nothing for the card to open until it is built
        self.assertIn('class="book pending"', html)
        self.assertIn('not built yet', html)
        self.assertIn('>build</button>', html, 'and its own card builds it')
        self.assertNotIn('takebuild', html, 'while the panel below builds nothing')


class WithoutSh(unittest.TestCase):
    def test_the_python_build_makes_a_fixture_s_reader(self):
        src = ROOT / 'tests' / 'fixtures' / 'books' / 'english' / 'mini-en'
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td, 'books', 'english', 'mini-en')
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
                'reader', '*.pdf', '*.aux', '*.log', '*.toc', '*.out', '.build-key', '.reader-key'))
            said = []
            ok = bookbuild.build(str(dest), html_only=True, say=said.append, index=False)
            self.assertTrue(ok, '\n'.join(said))
            self.assertTrue((dest / 'reader' / 'index.html').is_file())
            self.assertIn('the reader', said)


class ReaderAudioCache(unittest.TestCase):
    def test_copying_audio_after_a_linked_restore_rebuilds_the_reader(self):
        src = ROOT / 'tests' / 'fixtures' / 'books' / 'english' / 'mini-en'
        shelf = ROOT / 'books' / 'english'
        shelf.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='audio-cache-', dir=shelf) as td:
            book = Path(td)
            shutil.copytree(src, book, dirs_exist_ok=True)
            meta_path = book / 'book.json'
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            meta.update(slug=book.name, audio='audio/voice.mp3')
            meta_path.write_text(json.dumps(meta), encoding='utf-8')

            def build():
                run = subprocess.run(['bash', 'build.sh', '--html', book.name],
                                     cwd=ROOT, text=True, capture_output=True,
                                     timeout=120)
                self.assertEqual(0, run.returncode, run.stdout + run.stderr)
                return run.stdout

            build()
            reader = book / 'reader' / 'index.html'
            self.assertIn('"audio": false', reader.read_text(encoding='utf-8'))
            (book / 'audio').mkdir()
            (book / 'audio' / 'voice.mp3').write_bytes(b'ID3')
            self.assertIn('reader/index.html', build())
            restored = reader.read_text(encoding='utf-8')
            self.assertIn('"audio": true', restored)
            self.assertIn('voice.mp3', restored)


if __name__ == '__main__':
    unittest.main()
