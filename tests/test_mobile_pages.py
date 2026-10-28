# SPDX-License-Identifier: GPL-3.0-or-later
"""The mobile interface's books and exercises (docs/mobile.md), as the server
and the shared files write them: the mobile book shelf (lib/mobile.py,
/m/books/); the registry and the loader in lib/parseh.js that give every
book's reader its mobile layer (lib/mobilereader.js, lib/mobile.css); the
exercise decks' pages, each carrying both layouts (markdown/app/templates,
deckroutes.MODE_SCRIPT, static/mobile.css); and the mobile interface as an
app -- its manifest, icons, worker, pages, and the certificate a phone is
told to trust (serve.py's authority, over a real TLS connection).

    python3 -m unittest discover -s tests -p test_mobile_pages.py

Reads the shelf with the fixture editions of tests/fixtures/books standing on
it, and whether each reader is built stood in for, so nothing on the machine's
own shelf can move it.  What the pages DO -- on a phone, in either mode, in
the reader of each language -- is driven in a browser by
tests/mobile_pages.mjs.
"""
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "tests", "."):
    sys.path.insert(0, str(ROOT / p))
FIXTURES = ROOT / "tests" / "fixtures" / "books"

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'source', 'track', 'wbr'}


# THE PHONE-KEEPING MEMORIES GO TO A FOLDER OF THIS FILE'S OWN (TO-DO §2.25).
# The record tests below ask lib/offline.py what a book, a deck and the app
# are made of, and every file it hashes is remembered in `offline.DIGESTS`
# (and every book's places in `offline.WHERES`): config/digests.json and
# config/wheres.json beside the checkout, which are the owner's.  Left there,
# this file wrote into his digests at every run.  Patched for as long as the
# module runs, as tests/test_wave_estimate.py patches them -- and the memories
# themselves with them, which lib/offline.py keeps between calls, so that
# nothing learnt in here goes on into the next module to be written wherever
# the stores point by then.  What the SHIPPED constants say is read off the
# file itself, apart (test_the_digest_cache_is_never_written_inside_...).
_scratch = None
_patches = []


def setUpModule():
    global _scratch
    import offline
    _scratch = tempfile.TemporaryDirectory()
    config = Path(_scratch.name) / 'config'
    _patches[:] = [patch.object(offline, 'DIGESTS', str(config / 'digests.json')),
                   patch.object(offline, 'WHERES', str(config / 'wheres.json')),
                   patch.object(offline, '_digests', None),
                   patch.object(offline, '_digests_new', False),
                   patch.object(offline, '_wheres_store', None),
                   patch.object(offline, '_wheres_store_new', False)]
    for p in _patches:
        p.start()


def tearDownModule():
    for p in reversed(_patches):
        p.stop()
    _scratch.cleanup()


class Page(HTMLParser):
    """Every element of a page with the layout it sits in ('browser' or
    'mobile' under an element marked data-layout, None outside both), and
    its text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.els, self.body, self.text = [], [], {}, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'body':
            self.body = a
        where = a.get('data-layout') or next((w for w in reversed(self.stack) if w), None)
        self.els.append((where, tag, a))
        if tag not in VOID:
            self.stack.append(a.get('data-layout') or where)

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        self.text.append(data)

    def of(self, where):
        return [(t, a) for w, t, a in self.els if w == where]


def parse(html):
    p = Page()
    p.feed(html)
    return p


def top_level(css):
    """Every selector of a sheet, one to an item, split at top-level commas."""
    out = []
    for sel in re.findall(r'([^{}]+)\{', re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        if sel.strip().startswith('@'):           # a media query, with commas of its own
            continue
        depth, part = 0, ''
        for ch in sel:
            depth += ch == '('
            depth -= ch == ')'
            if ch == ',' and depth == 0:
                out.append(part.strip())
                part = ''
            else:
                part += ch
        out.append(part.strip())
    return [p for p in out if p and not p.startswith('@')]


# ------------------------------------------------------------ the shelf
def shelf(unbuilt=("mini-it",), found=None):
    """/m/books/ over the fixture editions, every one built but `unbuilt`."""
    import books
    import mobile
    stats = lambda b: ({"built": False} if b.slug in unbuilt  # noqa: E731
                       else {"built": True, "chapters": ["1", "2"], "subs": 12, "timed": 4})
    whole = books.all_books
    with patch.object(books, 'BOOKS_DIR', str(FIXTURES)), \
            patch.object(mobile.booklib, 'all_books',
                         found if found is not None else (lambda: whole(str(FIXTURES)))), \
            patch.object(mobile.make_index, 'stats', stats):
        return mobile.books_page()


class ShelfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import books
        cls.books = books.all_books(str(FIXTURES))
        cls.html = shelf()
        cls.page = parse(cls.html)

    def cards(self):
        return [(t, a) for w, t, a in self.page.els if 'm-book' in (a.get('class') or '').split()]

    def test_a_mobile_page_that_names_its_browser_page(self):
        self.assertIn('data-mobile-page', self.page.body)
        self.assertEqual(self.page.body.get('data-browser-page'), '/books/')
        order = [self.html.index(f) for f in ('/lib/parseh.css', '/lib/langs.css', '/lib/mobile.css',
                                               '/lib/parseh.js')]
        self.assertEqual(order, sorted(order), 'the palette, the tokens, the mobile sheet, then the script')

    def test_the_bar_is_the_hubs_mobile_bar(self):
        import mobile
        import serve
        self.assertIn('<div class="parseh-bar m-bar">', self.html)
        self.assertIn('<a class="home" href="/">', self.html)
        self.assertIn(mobile.mode_switch(), self.html)
        # one switch, written in one place for every page that carries it
        self.assertEqual(serve.mode_switch(), mobile.mode_switch())
        self.assertIn('data-parseh-theme', self.html)

    def test_a_built_book_opens_its_reader(self):
        cards = {a['data-lang']: (t, a) for t, a in self.cards()}
        self.assertEqual(sorted(cards), sorted(b.language for b in self.books))
        for b in self.books:
            t, a = cards[b.language]
            if b.slug == 'mini-it':
                continue
            self.assertEqual(t, 'a', b.slug)
            self.assertEqual(a['href'], '/books/%s/%s/reader/' % (Path(b.dir).parent.name, b.slug), b.slug)
            self.assertEqual(a['data-subs'], '12')
        # the title and the author in the book's own language and direction
        m = re.search(r'<a class="m-book" href="/books/persian/mini-fa/reader/"[^>]*>\s*'
                      r'<div class="m-btitle" lang="fa" dir="rtl">', self.html)
        self.assertIsNotNone(m)

    def test_a_book_never_built_is_no_link(self):
        cards = {a['data-lang']: (t, a) for t, a in self.cards()}
        t, a = cards['it']
        self.assertEqual((t, a['class']), ('div', 'm-book m-off'))
        self.assertNotIn('href', a)
        card = self.html[self.html.index('<div class="m-book m-off"'):]
        card = card[:card.index('</div>\n</div>') if '</div>\n</div>' in card else 800]
        self.assertIn('not built yet', card)
        self.assertIn('browser interface', card)

    def test_nothing_that_edits_or_manages_the_shelf(self):
        for t, a in [(t, a) for w, t, a in self.page.els]:
            for attr in ('data-del', 'data-build', 'data-parseh-stop'):
                self.assertNotIn(attr, a)
            self.assertNotIn(t, ('input', 'textarea', 'select', 'form'))
        for word in ('__upload', '__backup', '__restore', '__delete', '__build', '__download',
                     '/books/add', 'serve.sh', 'build.sh'):
            self.assertNotIn(word, self.html)
        hrefs = [a['href'] for w, t, a in self.page.els if t == 'a' and 'href' in a]
        self.assertEqual([h for h in hrefs if not h.endswith('/reader/')], ['/', '/books/'],
                         'besides the readers: home, and the library for the browser mode')

    def test_the_chips_filter_the_cards_by_language(self):
        import languages
        m = re.search(r'<div class="parseh-langs m-langs" role="group" aria-label="language" '
                      r'data-lang-filter="([^"]*)">', self.html)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '.m-book[data-lang], .m-lhead')
        picks = re.findall(r'data-pick="([a-z]+)"', self.html)
        order = [L.code for L in languages.LANGS.values()]
        have = sorted({b.language for b in self.books}, key=order.index)
        self.assertEqual(picks, ['all'] + have)
        heads = re.findall(r'<h2 class="m-lhead" data-lang="([a-z]+)">', self.html)
        self.assertEqual(heads, have, 'a heading a language, in the registry\'s order')

    def test_what_a_book_says_is_escaped(self):
        import languages

        class Stub:
            slug = 'x'
            language = 'en'
            lang = languages.get('en')
            title = '<img src=x onerror=alert(1)>'
            author = 'A & B'
            title_latin = '"quoted"'
            author_latin = ''
            has_audio = False
            meta = {'blurb': '<script>alert(2)</script>'}

            def rel_from_books(self):
                return 'english/x'
        html = shelf(unbuilt=(), found=lambda: [Stub()])
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>alert(2)', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('A &amp; B', html)
        self.assertIn('&quot;quoted&quot;', html)

    def test_an_empty_shelf_says_where_books_come_from(self):
        html = shelf(found=lambda: [])
        self.assertIn('class="m-empty"', html)
        self.assertIn('browser interface', html)
        self.assertNotIn('class="m-book', html)

    def test_the_reading_place_is_read_and_never_written(self):
        import mobile
        js = mobile.READ_ON_JS
        self.assertIn("localStorage.getItem('bk_pos:' + p)", js)
        self.assertIn("[base, base + 'index.html']", js)
        self.assertNotIn('setItem', js)
        self.assertNotIn('removeItem', js)
        # the reader keeps it so (lib/tex2html.py, save())
        tex2html = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        self.assertIn("const MINE = (k) => 'bk_' + k + ':' + location.pathname;", tex2html)
        self.assertIn("localStorage.setItem(MINE('pos'), JSON.stringify({i: cur}))", tex2html)


# ------------------------------------------------------------ the registry, the loader
def mobile_pages():
    """MOBILE_PAGES as parseh.js writes it: (pattern, to) pairs, the pattern
    turned into a Python one (these use nothing the two dialects differ in)."""
    js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
    block = js[js.index('var MOBILE_PAGES = ['):js.index('];', js.index('var MOBILE_PAGES = ['))]
    return [(re.compile(m.group(1)), m.group(2))
            for m in re.finditer(r"\{ match: /(.+?)/, to: '([^']*)' \}", block)]


def route(url):
    """Parseh.mode.route in the mobile mode, for a path on this site."""
    path, _, rest = url.partition('#')
    path, _, q = path.partition('?')
    for pat, to in mobile_pages():
        if pat.search(path):
            return pat.sub(to.replace('$', '\\'), path) + ('?' + q if q else '') + ('#' + rest if rest else '')
    return url


class RegistryTests(unittest.TestCase):
    def test_where_a_link_goes_in_the_mobile_mode(self):
        cases = {
            '/': '/', '/index.html': '/',
            '/books/': '/m/books/', '/books/index.html': '/m/books/', '/books/?x=1#y': '/m/books/?x=1#y',
            # a reader is its own mobile version, by either of its addresses
            '/books/persian/mini-fa/reader/': '/books/persian/mini-fa/reader/',
            '/books/persian/mini-fa/reader/index.html#par-2': '/books/persian/mini-fa/reader/#par-2',
            '/books/old-book/reader/index.html': '/books/old-book/reader/',
            # and so is every page of the decks
            '/exercises/': '/exercises/', '/exercises/deck/persian/words/study': '/exercises/deck/persian/words/study',
            # and the licences
            '/licences/': '/licences/',
            # the videos: the index and a channel have pages of their own
            # (lib/mobile.py), a video's page is its own mobile version
            '/youtube/': '/m/videos/', '/youtube/index.html': '/m/videos/',
            '/youtube/c/some-channel/': '/m/videos/some-channel/',
            '/youtube/v/abc123/': '/youtube/v/abc123/',
            '/youtube/v/abc123/index.html#t=12': '/youtube/v/abc123/#t=12',
            # the studio's library and its documents carry both layouts
            '/studio/': '/studio/', '/studio/doc/some-doc/': '/studio/doc/some-doc/',
            # a page with no mobile version keeps its address
            '/books/add/': '/books/add/',
            '/books/persian/mini-fa/': '/books/persian/mini-fa/',
        }
        for url, want in cases.items():
            self.assertEqual(route(url), want, url)

    def test_every_reader_is_given_the_mobile_layer(self):
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        loader = js[js.index("/* ---- a book's reader, in the mobile interface"):]
        m = re.search(r"!/(.+?)/\.test\(location\.pathname\)", loader)
        self.assertIsNotNone(m)
        reader = re.compile(m.group(1))
        for path in ('/books/persian/mini-fa/reader/', '/books/japanese/mini-ja/reader/index.html',
                     '/books/old-book/reader/'):
            self.assertTrue(reader.search(path), path)
        for path in ('/books/', '/books/add/', '/m/books/', '/books/persian/mini-fa/',
                     '/books/persian/mini-fa/reader/ch-2.html', '/youtube/v/abc/'):
            self.assertFalse(reader.search(path), path)
        # loaded from beside parseh.js, as activity.js is: a built reader links
        # lib/ relatively, and needs no rebuild to gain the layer
        self.assertIn("replace(/parseh\\.js(?=[?#]|$).*$/, '')", loader)
        self.assertIn("base + 'mobile.css'", loader)
        self.assertIn("base + 'mobilereader.js'", loader)
        self.assertIn("classList.add('m-reader')", loader)
        self.assertIn("setAttribute('blocking', 'render')", loader)

    def test_the_layer_is_on_the_web(self):
        import serve
        for f in ('/lib/mobile.css', '/lib/mobilereader.js'):
            self.assertIn(f, serve.STATIC_FILES)
            self.assertTrue(serve.static_ok(f))
            self.assertTrue((ROOT / f.lstrip('/')).is_file(), f)

    def test_a_mobile_only_page_goes_back_to_its_browser_page_on_a_switch_only(self):
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        apply = js[js.index('function modeApply()'):js.index('function modeSet(m)')]
        self.assertIn("getAttribute('data-browser-page')", apply)
        # inside the "the mode changed" branch, and only towards the browser
        changed = apply[apply.index('if (was !== null && was !== m) {'):]
        self.assertIn("m === 'browser'", changed)
        self.assertIn('location.replace(back)', changed)

    def test_the_readers_writing_gestures_are_refused_in_the_mobile_mode(self):
        js = (ROOT / 'lib' / 'mobilereader.js').read_text(encoding='utf-8')
        self.assertIn("window.addEventListener('click'", js)
        self.assertIn("window.addEventListener('keydown'", js)
        self.assertIn("e.key === 'e' || e.key === 'E'", js)
        # each refusal asks the mode first, and so does the dictionary's
        # button, which is the mobile mode's alone
        self.assertEqual(js.count('if (!mobile()'), 3, 'each refusal asks the mode first')
        # nothing of the reader's own is rewritten: the layer only adds
        # elements it made itself -- into the header's first row (the groups'
        # lines and the Browser | Mobile switch), the dictionary's button into
        # the gloss cloud beside "copy" (a0.3.1), and into those its own
        # pieces -- and, in a book with few glosses, it marks the glossed
        # chunks with a class of its own and takes it off again (a0.3.2).
        # The one thing of the reader's it takes out: the dictionary's panel
        # the reader pours into the cloud of a chunk with no vocabulary line,
        # where the chunk has a meaning or a reading written all the same
        # (a0.3.2: on a phone a gloss is any line of one), and so opens its
        # cloud with the button instead.  a0.4.1 adds one more control of its
        # own to the header's first row, in BOTH modes: hover ⏸, put beside
        # the reader's own hover with row.insertBefore -- the same receiver,
        # so the set below does not grow, and the count says it is only that
        receivers = re.findall(r'(\w+)\.(?:appendChild|insertBefore|replaceWith|replaceChildren|remove)\(', js)
        # (a0.5.0: the ⋯ menu, its group lines and the Browser | Mobile switch left this file for the
        # gear -- lib/gear-reader.js -- so what was put into the header for them, `sw`, is gone)
        self.assertEqual(set(receivers) - {'classList'}, {'row', 'none', 'box', 'auto'})
        # (the other row.insertBefore is the dictionary's button, in the CLOUD's
        # row of buttons; this one is the header's)
        hp = js[js.index('/* ---- pause on touch: hover'):js.index('/* ---- a book with few glosses')]
        self.assertEqual(hp.count('row.insertBefore('), 1, 'hover ⏸ is the one thing put beside a reader control')
        self.assertEqual(js.count('auto.remove();'), 1)
        self.assertEqual(re.findall(r"\.classList\.(?:add|remove)\('([\w-]+)'\)", js), ['m-gl', 'm-gl'])
        self.assertNotIn('parseh-mode', js)
        self.assertNotIn('m-rmore', js)
        self.assertIn("var b = el('button', 'mkdict', 'dictionary');", js)
        self.assertIn("var box = el('div', 'dict m-dict');", js)
        # THE ONE THING OF THE READER'S IT HANDS ON (a0.3.2, TO-DO §4.18): the
        # entry the reader's fillCloud pours into the cloud of a chunk with no
        # vocabulary line goes -- the very box, its answer on the way into it
        # -- to the dictionary's sheet (Parseh.dictSheet, lib/parseh.js), and
        # only for a tap, never a mouse at rest.  The cloud is HIDDEN while the
        # sheet is up and never closed under it, for the reader's dictInto
        # fills its box only while its cloud is open on that chunk; the sheet
        # gone, the cloud is closed with it -- once, and only if it is still
        # that chunk's
        self.assertIn('if (tapping && autoPanel()) toSheet(auto);', js)
        # -- and only for a chunk with nothing written at all
        auto = js[js.index("var auto = cloud.querySelector('.dict:not(.m-dict)');"):js.index('auto.remove();')]
        self.assertIn('if (!hasGloss(cloudC)) {', auto)
        self.assertIn('cloud.hidden = true;', js)
        self.assertIn("if (cloudC === n && typeof closeCloud === 'function') closeCloud();", js)
        self.assertEqual(js.count('closeCloud()'), 1)
        self.assertNotIn('innerHTML', js)
        # and the cloud the reader fills AGAIN while the sheet is up for its
        # chunk (a translation model found late opens it again) is hidden
        # again, for a shown cloud is one a tap in the sheet would close
        self.assertIn('if (sheet && sheet.open() && cloudC === sheetN) { cloud.hidden = true; return; }', js)
        # THE NARRATION WAITS while the sheet is up, through the reader's own
        # ▶ -- pressed, as the dock presses it, never driven from here
        self.assertIn("b = document.getElementById('play')", js)
        self.assertNotIn('.pause()', js)
        self.assertNotIn('.play()', js)
        # A FEW GLOSSES, COUNTED OVER THE WHOLE BOOK: from the reader's SRC
        # (every chunk of the book, any line of a gloss counting), not from
        # the chapters that happen to be on the page -- and a chapter that
        # comes later is marked as it comes, when the reader takes its
        # data-part off
        self.assertIn('if (srcGlossed(src[i])) { g[i] = 1; count++; }', js)
        self.assertIn("attributeFilter: ['data-part']", js)
        # which is what the reader writes into SRC, in that order, and what
        # every reader built since the first has carried
        tex = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        self.assertRegex(tex, r'src\.append\(\[HL\.get\(c\.col, ""\), c\.fa, c\.kana,\s+c\.tr, c\.voc, c\.en, c\.wordline\]\)')
        self.assertIn('delete sec.dataset.part;', tex)

    def test_on_a_phone_a_gloss_is_any_line_of_one(self):
        # THE OWNER, 2026-09-25: a chunk is glossed when ANY line of a gloss is
        # written -- a meaning, a transliteration (the kana, where the
        # language has a reading), a vocabulary line -- and only a chunk with
        # nothing written opens the dictionary's sheet by itself.  One rule
        # for the press and for the count of a book or a video with few
        # glosses, in both pages
        layer = (ROOT / 'lib' / 'mobilereader.js').read_text(encoding='utf-8')
        body = layer[layer.index('function srcGlossed(s) {'):layer.index('function rowGlossed(r) {')]
        # SRC's fields: [colour, text, kana, tr, voc, en, words]
        self.assertIn('if (line(4) || line(5) || (kana && line(3))) return true;', body)
        self.assertIn("var field = kana ? 'kana' : 'tr', v = line(kana ? 2 : 3), sd = null;", body)
        # a reading a draft seeded, with nothing else written, is nobody's
        # gloss -- asked of the one seed the player and the build ask
        self.assertIn("sd = W.seed({words: String(s[6] || '')}, L);", body)
        self.assertIn("r.hasAttribute('data-seed')", layer)
        player = (ROOT / 'youtube' / 'lib' / 'player.js').read_text(encoding='utf-8')
        self.assertIn('var dictShown = (mobileNow() ? !hasGloss(ch) : !ch.voc) && (DICT.ready || MT.ready) && opts.dict;',
                      player)
        mark = player[player.index('  function markGlossed() {'):]
        self.assertIn('if (ch && hasGloss(ch)) gl.push(w);', mark[:mark.index('\n  }\n')])
        # "Set any of them up": Settings, Reading help, wherever a phone's
        # cloud or sheet says nothing is set up
        self.assertIn("to.href = '/settings/reading-help/';", layer)
        self.assertNotIn("'/lookup/'", layer)
        self.assertEqual(player.count('<a href="/settings/reading-help/">Set any of them up</a>'), 2)
        self.assertNotIn('<a href="/lookup/">', player)

    def test_the_sheet_is_as_tall_as_its_entry_whatever_is_pinned(self):
        # THE OWNER, 2026-09-25: the dictionary's sheet always opens as tall as
        # the entry, up to 86% of the screen -- never cut short under what a
        # page pins at its top to leave the word a room (it once was, down to
        # 45% of the screen).  The word is scrolled clear where there is room
        # for it, and otherwise left where it was, under the sheet
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        clear = js[js.index('  function dsClear(s) {'):js.index('  function dsClose(s, how) {')]
        self.assertNotIn('maxHeight', clear)
        self.assertNotIn('0.45', clear)
        self.assertIn('if (top - ceil < r.height + 12) return;', clear)
        sheet = js[js.index("/* ---- the dictionary's sheet, on a phone"):js.index('dictSheet.close = function')]
        self.assertEqual(sheet.count('.style.maxHeight'), 1, "only the cloud's cut, cleared off the box it hands in")
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        self.assertRegex(css, r'\.m-dsheet\{[^}]*max-height:86dvh')

    def test_the_few_glosses_mark_is_a_second_mark_where_every_phrase_has_one(self):
        # THE OWNER, 2026-09-25: where every phrase already wears the faint
        # dotted line (a video's phrases; a book's first pass in hover mode),
        # the glossed ones wear it darker and the others KEEP it -- no rule of
        # the few-glosses mark makes a line transparent any more
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        few = css[css.index('/* A FEW GLOSSES, AND WHERE THEY ARE'):css.index('A VIDEO\'S PAGE, ON A PHONE')]
        self.assertNotIn('transparent', few)
        self.assertIn('html.m-reader[data-mode=mobile].m-sparse body.hovermode .p1 .w.m-gl:not(.hot):not(:hover),\n'
                      'html.m-player.m-sparse[data-mode=mobile] .w.m-gl:not(.hot):not(:hover){\n'
                      '  text-decoration-color:var(--dim)}', few)
        # where nothing is underlined, the faint line, as built
        self.assertIn('html.m-reader[data-mode=mobile].m-sparse :is(.pass .w.m-gl,.row.m-gl>.fa){\n'
                      '  text-decoration:underline dotted var(--faint) 1px;', few)

    def test_the_video_on_a_phone_offers_no_note_to_write(self):
        # the + between two captions writes a note into the video (player.js,
        # paintNotes); the book's reader hides its own, and so does the player
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        m = re.search(r"html\.m-player\[data-mode=mobile\] :is\(([^)]*)\)\{display:none!important\}", css)
        self.assertIsNotNone(m)
        shut = {s.strip() for s in m.group(1).split(',')}
        for door in ('#segs .gap .plus', '#ntedit', '#cloud .mkedit', '#cloud .colrow', '#subedit'):
            self.assertIn(door, shut)

    def test_the_recording_moves_by_the_seconds_asked_and_takes_the_reading_place_along(self):
        # ↺ and ↻ belong to BOTH modes now (lib/narrctl.js, TO-DO §4.15):
        # on a phone they float in the dock, on a computer they stand beside ▶
        js = (ROOT / 'lib' / 'narrctl.js').read_text(encoding='utf-8')
        # one number for every book, kept beside the reader's own habits
        self.assertIn("var RATE_KEY = 'bk_rate', SKIP_KEY = 'bk_skip', HINT_KEY = 'bk_skiphint';", js)
        # ONE LIST FOR EVERYTHING PARSEH ITSELF PLAYS (the owner, 2026-09-23):
        # a book's narration and a film on this machine offer the same speeds,
        # 0.25 among them.  A video still hosted by YouTube cannot: its player
        # takes only the rates it reports itself, so the chip asks the player
        # first (`speeds`) and falls back to this list.
        self.assertIn('var SPEEDS = [0.25, 0.5, 0.6, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];', js)
        self.assertIn('var own = video().rates && video().rates();', js)
        shim = (ROOT / 'youtube' / 'lib' / 'player.js').read_text(encoding='utf-8')
        # a film of this machine says it has no list of its own, and so is
        # given the toolbox's
        self.assertIn('getAvailablePlaybackRates: function () { return null; }', shim)
        # the owner asked for the two short ones (2026-09-23): a second and
        # two are what a phrase is worth, where five overshoots into the
        # line before
        self.assertIn('var SECS = [1, 2, 5, 10, 15, 30, 60];', js)
        skip = js[js.index('function skipBy(by)'):]
        skip = skip[:skip.index('\n  }\n') + 4]
        # listening has no reading place: only the fold ahead is worked out again
        self.assertIn('if (listening) {', skip)
        self.assertIn('if (!a.paused) armListen();', skip)
        # reading: the subparagraph the recording lands in is the place, and
        # where the playing stops
        self.assertIn('var i = subAtTime(to);', skip)
        self.assertIn('cur = i; hl(i, true); save();', skip)
        self.assertIn('stopAt = SUBS[i][1];', skip)
        # every binding of the reader's read before any is written
        self.assertLess(skip.index('void [waiting, atBound, previewing, cur, stopAt, hl, save, SUBS, seekTo];'),
                        skip.index('waiting = null;'))
        # the reader has each of them, at the top level of its script
        tex2html = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        for decl in ('let cur = -1, loop = false, cont = true, stopAt = null, gap = 0, waiting = null;',
                     'let listening = false, afterFold = null, seeking = false;', 'let previewing = false;',
                     'function subAtTime(t) {', 'function seekTo(t, done) {', 'function armListen() {',
                     'function hl(i, mayScroll) {', 'function save() {'):
            self.assertIn('\n' + decl, tex2html)
        # a book with no narration has nothing to move: no dock, no row
        css = (ROOT / 'lib' / 'parseh.css').read_text(encoding='utf-8')
        self.assertIn('body.noaudio :is(.nc-skip,.nc-chip,.nc-dock){display:none!important}', css)
        # the phone's row of skip distances is the gear's Skip distance now (a0.5.0): kept in the
        # header's DOM and not drawn there, in either layout
        mcss = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        self.assertIn('html.m-reader[data-mode=mobile] header :is(.kp-btn,.m-rskip){display:none!important}', mcss)
        self.assertRegex((ROOT / 'lib' / 'parseh.css').read_text(encoding='utf-8'), r'html\.pg-reader header :is\(#stopbnd,#hoverpause,#defmode,#defmt,#lookupset,\.m-rskip\)')

    def test_the_speed_never_changes_by_itself(self):
        """The owner's bug of 2026-09-22: a recording loaded put the rate back
        to 1× while the control still said 1.5×.  Both the reader built today
        and the layer every older reader loads set defaultPlaybackRate with the
        rate, and put the rate back after a load."""
        js = (ROOT / 'lib' / 'narrctl.js').read_text(encoding='utf-8')
        hold = js[js.index('  function hold() {'):js.index('  // somebody moved')]
        self.assertIn('a.defaultPlaybackRate = want;', hold)
        self.assertIn('a.playbackRate = want;', hold)
        watch = js[js.index('  function watchRate() {'):js.index('  /* ---------------- how far')]
        for event in ("'loadstart'", "'emptied'", "'loadedmetadata'", "'canplay'", "'play'", "'ratechange'"):
            self.assertIn(event, watch)
        # a rate changed at any other time is somebody meaning it: followed
        self.assertIn('adopt(a.playbackRate);', watch)
        # and the reader built today does the same on its own
        tex2html = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        self.assertIn('function setRate(v) {\n  A.playbackRate = v;\n  A.defaultPlaybackRate = v;\n}', tex2html)
        self.assertIn("['loadedmetadata', 'canplay', 'play'].forEach(n => A.addEventListener(n, () => {", tex2html)
        # the two speeds the owner asked for are in the menu itself
        self.assertIn('<option>1.25</option><option>1.5</option><option>1.75</option><option>2</option>',
                      tex2html)

    def test_the_header_stays_while_it_is_being_used(self):
        # the bars follow the scroll at every width in the mobile mode, and
        # stand down while a page holds them (a skip's own scroll, the dictionary's sheet)
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        bars = js[js.index('  function bars() {'):js.index('  function wire() {')]
        self.assertIn('var want = mq.matches || isMobile();', bars)
        self.assertIn('modeOnChange(follow);', bars)
        self.assertIn("document.body.hasAttribute('data-bars-held')", bars)
        # where the page is, kept even while held, before the hold is asked
        self.assertLess(bars.index('lastY = y;'), bars.index("hasAttribute('data-bars-held')"))
        # the ⋯ menu held the header while it was open; the gear's sheet does not need to (a0.5.0:
        # the page above it goes on being read, and the sheet is not in the header)
        layer = (ROOT / 'lib' / 'mobilereader.js').read_text(encoding='utf-8')
        self.assertNotIn('data-bars-held', layer)

    def test_the_reader_sheet_hides_every_writing_door(self):
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        m = re.search(r"html\.m-reader\[data-mode=mobile\] :is\(([^)]*)\)\{display:none!important\}", css)
        self.assertIsNotNone(m)
        shut = {s.strip() for s in m.group(1).split(',')}
        for door in ('#chpen', '#anki', '#bmbox', '#chbox', '#dvbox', '#fdbox', '#narrbox', '#naskbox',
                     '#secbox', '.dlsheet', '#ntedit', '.gap .plus', '.tocedit', '#tocsecs',
                     '#cloud .mkcard', '#cloud .mkedit'):
            self.assertIn(door, shut)
        # the header keeps what it names and nothing else
        keep = re.search(r"html\.m-reader\[data-mode=mobile\] header > \.hrow > :not\(([^)]*)\)", css)
        self.assertIsNotNone(keep)
        kept = {s.strip() for s in keep.group(1).split(',')}
        for gone in ('#bookinfo', '#buildbook', '#buildhtml', '#narr', '#fold', '#editmode', '#editbyear', '#stopsrv',
                     '.dl', '#lookupset', '#build'):
            self.assertNotIn(gone, kept)
        # THE FIRST LINE alone (a0.5.0): the contents, the text size and the gear.  The theme, the
        # levels, the glosses and the rest are in the gear's sheet, not on a phone's page
        for there in ('#toc', '#typo', '[data-parseh-gear]'):
            self.assertIn(there, kept)
        for gone in ('#theme', '.pgrp', '[data-toggle=nogloss]', '#hovermode', '#cont', '#loop', '#gapwrap',
                     '#stopbnd', '#hoverpause', '#listen', '#dictmode', '#defmode', '#defmt', '#bars'):
            self.assertNotIn(gone, kept)
        # ▶ is not in the header at all any more: it plays from the dock at
        # the foot of the screen (lib/narrctl.js), and the reader's own
        # button stays on the page, unshown, as the one the dock presses
        self.assertNotIn('#play', kept)
        self.assertIn('html.m-reader[data-mode=mobile] header #play{display:none!important}', css)

    def test_the_narration_waits_for_a_touched_words_cloud_when_asked(self):
        # HOVER ⏸ IN A BOOK (a0.4.1; the owner, 2026-09-25 and 2026-09-28;
        # TO-DO §4.20 and §7.21): the video's switch in a reader, in BOTH
        # modes, kept on this device only.  What it DOES is driven, with the
        # audio's own events, by tests/phone_clouds.mjs section n; what is
        # pinned here is the text that drive rests on.
        js = (ROOT / 'lib' / 'mobilereader.js').read_text(encoding='utf-8')
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        start = js.index('/* ---- pause on touch: hover')
        end = js.index('/* ---- a book with few glosses')
        hp = js[start:end]
        # THIS DEVICE ONLY: a key of its own, never one the computer keeps (the
        # owner, 2026-09-28) -- neither the server's whitelist nor the page's
        self.assertIn("var HP_KEY = 'bk_hoverpause';", hp)
        import prefs
        self.assertNotIn('bk_hoverpause', prefs.KEYS)
        pjs = (ROOT / 'lib' / 'prefs.js').read_text(encoding='utf-8')
        self.assertNotIn('bk_hoverpause', pjs)
        # THE VIDEO'S OWN WORDS AND GLYPH (decision D15), and its grace: read
        # off the video's page, so the two cannot drift apart
        player = (ROOT / 'youtube' / 'lib' / 'player.html').read_text(encoding='utf-8')
        video = re.search(r'<button id="hoverpause"[^>]*>([^<]*)</button>', player).group(1)
        self.assertIn("var HP_LABEL = '%s';" % video.replace('&nbsp;', '\\u00a0'), hp)
        self.assertIn('var HP_GRACE = 350;', hp)
        pl = (ROOT / 'youtube' / 'lib' / 'player.js').read_text(encoding='utf-8')
        self.assertIn('}, 350);', pl[pl.index('function closeCloud()'):])
        # NOT ASKED OF THE MODE: the button and the wrapper are put up at the
        # start, mobile or not, and nothing between them asks mobile()
        self.assertNotIn('mobile()', hp)
        self.assertLess(js.index('    hpBuild();\n    hpInstall();\n'), js.index('if (p && p.mode && p.mode.onChange)'))
        # the button is drawn by both modes: beside the reader's own hover in
        # the header's first row, with no data-layout (which would hide it in
        # the browser mode) and the video's own id
        self.assertIn("hpBtn = el('button', 'm-hoverpause', HP_LABEL);", hp)
        self.assertIn("hpBtn.id = 'hoverpause';", hp)
        self.assertNotIn('data-layout', hp)
        self.assertIn("row.insertBefore(hpBtn, hm && hm.parentNode === row ? hm.nextSibling : null);", hp)
        # ... and hidden in a book with no narration -- every language's
        # book without a recording, right to left included -- which is what
        # keeps the row (and the Listening group) off such a book's gear
        self.assertIn("hpBtn.hidden = document.body.classList.contains('noaudio');", hp)
        # the reader's own open and close are wrapped by their bare names
        # (every caller in the reader resolves them so), and the wrapper of
        # the close is the only thing that ever lets go
        self.assertIn('window.openCloud = function () {', hp)
        self.assertIn('window.closeCloud = function () {', hp)
        self.assertIn('again = cloudC >= 0 && !cloudFor;', hp)
        # THE ▶ IS PRESSED WITHOUT THE CLICK BUBBLING: a bubbling one reaches
        # "a click outside the cloud shuts it" and shuts the cloud just opened
        self.assertIn("new MouseEvent('click', {bubbles: false, cancelable: true})", hp)
        self.assertIn("var b = document.getElementById('play');", hp)
        # what it owes is its own: the audio's play gives the debt up, and the
        # dictionary's sheet, when it closes, only asks for the grace again
        self.assertIn("a.addEventListener('play', function () {", hp)
        self.assertIn('hpHeld = false; hpGap = false;', hp)
        toSheet = js[js.index('function toSheet(box) {'):js.index('function openDict(b) {')]
        self.assertIn('if (held && how !== \'again\') narrGoOn();', toSheet)
        self.assertLess(toSheet.index('narrGoOn();'), toSheet.index('hpRelease();'))
        # the reader's own sheets are left in peace: every flag, each asked on
        # its own, for a reader built before a sheet existed lacks its binding
        for flag in ('ankiOpen', 'chOpen', 'fdShown', 'rgShown', 'narrOpen', 'secShown', 'dlOpen'):
            self.assertIn("(typeof %s !== 'undefined' && %s)" % (flag, flag), hp)
        # the loop's wait is the reader's `waiting`, taken and given back as
        # the reader's own play of that subparagraph
        self.assertIn('return loop === true && waiting != null && typeof playSub', hp)
        self.assertIn('playSub(cur, false)', hp)
        # the button is the layer's to make and the gear's to press: it is kept in the header, out of
        # sight in both layouts (html.pg-reader), and the gear's row "Pause while a gloss is open"
        # drives it (lib/gear-reader.js), under the hover cloud's switch
        self.assertRegex((ROOT / 'lib' / 'parseh.css').read_text(encoding='utf-8'), r'html\.pg-reader header :is\([^)]*#hoverpause[^)]*\)\{\s*display:none!important')
        keep = re.search(r"html\.m-reader\[data-mode=mobile\] header > \.hrow > :not\(([^)]*)\)", css)
        self.assertNotIn('#hoverpause', {s.strip() for s in keep.group(1).split(',')})
        gear = (ROOT / 'lib' / 'gear-reader.js').read_text(encoding='utf-8')
        self.assertIn("id: 'hoverpause', label: 'Pause while a gloss is open', indent: 1,", gear)
        self.assertIn("}, pressOf('hoverpause'))));", gear)
        # every language: the header is an island that reads left to right
        # whatever the book's language, so the button and its place are the
        # same in Persian, Arabic, Japanese, Hindi and Chinese as in English.
        # (Only the English fixture is narrated: no fixture has the switch
        # to press in another language; tests/mobile_pages.mjs asserts it is
        # not drawn for them, which is the rule a book with no recording gets.)
        tex = (ROOT / 'lib' / 'tex2html.py').read_text(encoding='utf-8')
        self.assertIn('<header lang="en" dir="ltr"><div class="hrow">', tex)
        self.assertIn('body.noaudio #play,body.noaudio #cont,body.noaudio #loop', tex)


# ------------------------------------------------------------ the decks
TEMPLATES = ('decks.html', 'deck.html', 'study.html', 'cram.html')


def rendered(name):
    import deckroutes
    import languages
    deck = {'folder': 'persian', 'slug': 'words', 'name': 'Words', 'lang': 'fa', 'path': 'persian/words',
            'counts': {'total': 0}, 'study': {}, 'settings': {}}
    mapping = deckroutes._deck_mapping('Words', deck)
    mapping['LANG_CHIPS'] = languages.chips_html({})
    return deckroutes.render_template(name, mapping)


class DeckTests(unittest.TestCase):
    def test_the_switch_is_the_hubs(self):
        import deckroutes
        import mobile
        self.assertEqual(deckroutes.MODE_SWITCH, mobile.mode_switch())

    def test_the_mode_is_read_as_parseh_js_reads_it(self):
        import deckroutes
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        s = deckroutes.MODE_SCRIPT
        self.assertIn("localStorage.getItem('parseh_mode')", s)
        # the same cookie pattern, character for character
        cookie = re.search(r"m = /(.+?)/\.exec\(document\.cookie", js).group(1)
        self.assertIn('/' + cookie.replace('\\s', '\\s') + '/.exec(document.cookie', s)
        self.assertIn("m=c?c[1]:'browser'", s)
        self.assertIn("setAttribute('data-mode',m)", s)

    def test_every_page_carries_both_layouts(self):
        import deckroutes
        for name in TEMPLATES:
            html = rendered(name)
            self.assertNotIn('{{', html, name)
            head = html[:html.index('</head>')]
            # the mode is on <html> before the first sheet is asked for
            self.assertLess(head.index(deckroutes.MODE_SCRIPT), head.index('<link rel="stylesheet"'), name)
            self.assertLess(head.index('/static/app.css'), head.index('/static/mobile.css'), name)
            p = parse(html)
            bars = [(w, a.get('class')) for w, t, a in p.els if t == 'header']
            modes = [a['data-parseh-mode'] for t, a in p.of('mobile') if 'data-parseh-mode' in a]
            if name in ('study.html', 'cram.html'):
                # a0.5.0: no bar over the exercise on a phone, so nothing of the bar's is
                # in the page -- the gear (static/gear.js) stands in the row of its title
                self.assertEqual(bars, [('browser', 'topbar')], name)
                self.assertEqual(modes, [], name)
                self.assertFalse(any('data-parseh-theme' in a for t, a in p.of('mobile')), name)
                continue
            self.assertEqual(bars, [('browser', 'topbar'), ('mobile', 'm-topbar')], name)
            # a0.5.0: a deck has a gear after the theme, and the Browser | Mobile switch is in
            # the gear's Interface group; the list of decks has no gear and keeps its switch
            self.assertEqual(modes, ['browser', 'mobile'] if name == 'decks.html' else [], name)
            self.assertTrue(any('data-parseh-theme' in a for t, a in p.of('mobile')), name)
            self.assertTrue(any(t == 'a' and a.get('href') == '/' for t, a in p.of('mobile')), name)

    def test_the_mobile_layouts_have_nothing_that_edits(self):
        for name in TEMPLATES:
            p = parse(rendered(name))
            for t, a in p.of('mobile'):
                self.assertNotIn(a.get('id'), ('btn-stop', 'btn-import', 'btn-restore', 'btn-new-deck',
                                               'btn-rename', 'btn-add-exercise', 'btn-options',
                                               'btn-delete-deck', 'btn-edit-card'), name)
                self.assertNotIn(t, ('input', 'textarea', 'select', 'form'), name)
        # and the sheet takes the browser layout's editing controls away:
        # the deck's own, and the list's -- which the mobile layout shows,
        # to pick exercises to cram, with nothing in it that changes one
        css = (ROOT / 'markdown' / 'app' / 'static' / 'mobile.css').read_text(encoding='utf-8')
        hidden = set()
        for m in re.finditer(r'html\[data-mode=mobile\] body\[data-page=(?:deck|study)\] :is\(([^{]*)\)'
                             r'\{display:none!important\}', css):
            hidden |= {s.strip() for s in m.group(1).split(',')}
        for sel in ('#btn-rename', '#btn-add-exercise', '#btn-options', '#btn-delete-deck', '#btn-edit-card',
                    '#btn-bulk-copy', '#btn-bulk-move', '#btn-bulk-add-tag', '#btn-bulk-remove-tag',
                    '#btn-bulk-new', '#btn-bulk-delete', '.dk-row-actions', '.dk-selection-hint'):
            self.assertIn(sel, hidden)
        for kept in ('.dk-browse', '#btn-select-all', '#btn-select-shown', '#btn-deselect-shown',
                     '#btn-select-tag', '#btn-deselect-all', '#browse-list'):
            self.assertNotIn(kept, hidden)
        self.assertIn('html[data-mode=mobile] .card.dk-card .dropdown{display:none!important}', css)

    def test_studying_answers_in_one_place(self):
        p = parse(rendered('study.html'))
        ids = [a.get('id') for w, t, a in p.els if a.get('id')]
        box = rendered('study.html')
        box = box[box.index('<div class="dk-answerbar">'):box.index('<div id="study-done"')]
        for inside in ('id="study-actions"', 'id="rating-bar"', 'id="btn-next"'):
            self.assertIn(inside, box)
        self.assertIn('btn-next', ids)
        nxt = [a for w, t, a in p.els if a.get('id') == 'btn-next'][0]
        self.assertEqual(nxt.get('data-layout'), 'mobile')
        # no bar over the exercise in the mobile layout: the way back is by the
        # deck's name, on both pages
        for name in ('study.html', 'cram.html'):
            back = [a for w, t, a in parse(rendered(name)).els if 'm-back' in (a.get('class') or '').split()]
            self.assertEqual(len(back), 1, name)
            self.assertEqual(back[0].get('data-layout'), 'mobile', name)
            self.assertIn('dk-back', back[0]['class'].split(), name)
        # and no bar in the templates either (it was a hidden copy, with the switch in it, once)
        for name in ('study.html', 'cram.html'):
            self.assertNotIn('m-topbar', rendered(name), name)
        # Next rates as the answer says: the rating the bar was shown for
        js = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('btnNext.dataset.rating = focus;', js)
        self.assertIn('if (btnNext.dataset.rating) rate(btnNext.dataset.rating);', js)
        self.assertIn('showBar(good ? "good" : "again");', js)
        self.assertIn('showBar("good");', js)

    def test_a_deck_crams_what_is_picked(self):
        p = parse(rendered('deck.html'))
        go = [a for w, t, a in p.els if a.get('id') == 'm-cram'][0]
        self.assertEqual(go.get('data-layout'), 'mobile')
        js = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('$("#btn-cram").addEventListener("click", cramSelected);', js)
        self.assertIn('$("#m-cram").addEventListener("click", cramSelected);', js)
        self.assertIn('go.hidden = n === 0;', js)

    def test_the_sheet_reaches_nothing_of_the_browser_layout(self):
        css = (ROOT / 'markdown' / 'app' / 'static' / 'mobile.css').read_text(encoding='utf-8')
        self.assertIn('html[data-mode=mobile] [data-layout=browser],\n'
                      'html:not([data-mode=mobile]) [data-layout=mobile]{display:none!important}', css)
        for part in top_level(css):
            self.assertTrue(re.search(r'html\[data-mode=mobile\]|\.m-|\[data-layout=', part), part)

    def test_the_pages_are_wired(self):
        js = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        boot = js[js.index('/* ---------------- boot ---------------- */'):]
        self.assertIn('bindMode();', boot)
        self.assertIn('$("#btn-practise").addEventListener("click"', js)
        self.assertIn('sessionStorage.setItem(`parseh-cram:${deck.path}`', js)


# ------------------------------- what a phone is told a thing is made of
# The record (lib/offline.py) is the whole of what a kept book, video or deck
# IS on a phone: an address that is not in it is an address that answers
# nothing in airplane mode, and a promise in it that the phone cannot test is
# a box that ticks itself for ever.  Both halves went wrong at once on the
# owner's phone (2026-09-23): "all books do not open while offline, loading
# stops at ~half", and boxes ticked for things that were not there.
#
# DRIVEN OVER THE FIXTURE EDITIONS, whose readers are built and committed, and
# over the bytes on the disk: where a digest is claimed it is hashed again
# here rather than worked out the way lib/offline.py works it out.  What a
# phone then DOES with all this -- opens the book, crams the deck, unticks a
# copy that is no longer whole -- is driven in a browser by
# tests/mobile_pages.mjs, with the computer stopped.
def parser_wants(reader):
    """Every address a built reader's PARSER fetches while it builds the page.

    Not what the loaded DOM holds: a page that loaded perfectly well with the
    computer there says nothing about which of its addresses a phone holds.
    <script src> and a stylesheet <link> are the two that STOP the parser, and
    stopping the parser is what left the owner with half a page.
    """
    html = Path(reader).read_text(encoding='utf-8')
    out = []
    for tag, rest in re.findall(r'<(script|link|img)\b([^>]*)>', html, re.I):
        if tag.lower() == 'link' and 'stylesheet' not in rest:
            continue
        m = re.search(r'\b(?:src|href)="([^"]+)"', rest, re.I)
        if not m or '://' in m.group(1):
            continue
        # the reader links the toolbox by climbing out of its own folder; what
        # matters here is which file of lib/ it lands on
        climbed = re.sub(r'^(?:\.\./)+', '/', m.group(1))
        if climbed.startswith('/lib/') and climbed not in out:
            out.append(climbed)
    return out


class WhatAReaderAsksForTests(unittest.TestCase):
    """THE ONE ADDRESS THAT WAS MISSING (the owner's 7, 2026-09-23).

    Every reader lib/tex2html.py builds loads /lib/mt.js as a parser-blocking
    script in its head, and that address was in no list at all: offline the
    request missed every cache, the parser stopped where it stood, and the
    page never reached its body.  Five of his books, half-drawn.
    """

    def test_every_reader_asks_only_for_files_the_record_names(self):
        import offline
        readers = sorted(FIXTURES.glob('*/*/reader/index.html'))
        self.assertGreaterEqual(len(readers), 5, 'the fixture editions with their readers built')
        for reader in readers:
            wants = parser_wants(reader)
            self.assertTrue(wants, reader)
            missing = [u for u in wants if u not in offline.SHARED]
            self.assertEqual(missing, [], '%s: not in what every kept page gets' % reader)

    def test_the_translation_helper_is_the_one_that_was_missing(self):
        import offline
        readers = sorted(FIXTURES.glob('*/*/reader/index.html'))
        self.assertTrue(all('/lib/mt.js' in parser_wants(r) for r in readers),
                        'every reader asks for it, in its head, before its body')
        self.assertIn('/lib/mt.js', offline.SHARED)
        # and the test above really would have caught it: take it out of the
        # list and the reader asks for something nobody kept
        without = tuple(u for u in offline.SHARED if u != '/lib/mt.js')
        with patch.object(offline, 'SHARED', without):
            missed = [u for u in parser_wants(readers[0]) if u not in offline.SHARED]
        self.assertEqual(missed, ['/lib/mt.js'])


class WhatTheRecordPromisesTests(unittest.TestCase):
    """A TICK MUST BE TESTABLE (the owner's 3, 2026-09-23: "there should be a
    check of this, it should actually look for the file and check that the
    download was complete and correct").

    So every entry says what the phone may test about it: the SHA-256 of the
    bytes the server will send where the computer could afford to hash them, a
    length alone where it could not, and `check: "here"` where the answer is
    composed as it goes out and has neither.  The third is as load-bearing as
    the other two: an entry with a size that is an estimate and no `check`
    would be measured against that estimate and called broken for ever.
    """

    @classmethod
    def setUpClass(cls):
        import offline
        cls.offline = offline
        cls.book_dir = FIXTURES / 'english' / 'mini-en'
        cls.rec = offline.book(str(cls.book_dir), '/books/english/mini-en/')

    def entries(self, rec):
        return list(rec.get('small') or []) + list(rec.get('media') or [])

    def test_a_digest_is_the_sha256_of_the_bytes_on_the_disk(self):
        """Hashed again here, off the file the server streams, so that the
        record agreeing with itself is not what passes."""
        checked = 0
        for x in self.entries(self.rec):
            if not x.get('digest'):
                continue
            rel = x['url'][len('/books/english/mini-en/'):]
            path = self.book_dir / rel
            if not path.is_file():                  # the reader's own alias
                continue
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), x['digest'], x['url'])
            if x.get('bytes'):
                self.assertEqual(x['bytes'], path.stat().st_size, x['url'])
            checked += 1
        self.assertGreaterEqual(checked, 1, 'at least one file was really hashed')

    def test_the_digest_is_lowercase_hex_and_the_worker_will_take_it(self):
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn('/^[0-9a-f]{64}$/.test(digest)', sw, 'what the phone will accept')
        for x in self.entries(self.rec):
            if x.get('digest'):
                self.assertRegex(x['digest'], r'^[0-9a-f]{64}$', x['url'])

    def test_a_file_too_big_to_hash_on_a_phone_carries_none(self):
        """WebCrypto has no streaming digest: hashing a 228 MB narration would
        need the whole of it in memory at once.  Above DIGEST_MAX the length
        is the check, and the record must not claim more than that."""
        off = self.offline
        self.assertEqual(off.DIGEST_MAX, 8 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / 'narration.mp3'
            big.write_bytes(b'\0' * (off.DIGEST_MAX + 1))
            small = Path(tmp) / 'page.html'
            small.write_bytes(b'<p>a page</p>')
            heavy = off._entry('/x/narration.mp3', str(big), 'recording')
            light = off._entry('/x/page.html', str(small))
        self.assertNotIn('digest', heavy, 'nothing above the line is hashed')
        self.assertEqual(heavy['bytes'], off.DIGEST_MAX + 1, 'and its length is what is promised')
        self.assertEqual(light['digest'], hashlib.sha256(b'<p>a page</p>').hexdigest())

    def test_an_answer_the_computer_makes_up_says_it_can_promise_nothing(self):
        """A note's page, a deck's exercises with the scheduler's numbers
        riding in them, a stylesheet written out of the language registry:
        none of them has a length this file can predict, and a length nobody
        can predict must not be offered as one to check against."""
        import decks
        import offline
        with tempfile.TemporaryDirectory() as tmp:
            decks.set_dir(Path(tmp))
            made = decks.create_deck('Kept deck', 'en')
            decks.add_item(made['folder'], made['slug'],
                           ':::exercise flashcard\ncard-type: vocab\n'
                           'target: [cat]{tl}\nmeaning: a cat\n:::')
            rec = offline.deck(decks, made['folder'], made['slug'])
        urls = {x['url']: x for x in rec['small']}
        cram = '/exercises/api/decks/%s/%s/cram' % (made['folder'], made['slug'])
        # THE EXERCISES TRAVEL WITH THE DECK (his decision B): one tick,
        # nothing to choose, at an address a worker is allowed to keep
        self.assertIn(cram, urls, 'the rendered exercises are in the deck\'s record')
        self.assertEqual(rec['media'], [], 'and nothing heavy is left for him to pick')
        for url in (cram, '/exercises/deck/%s/%s/cram' % (made['folder'], made['slug'])):
            self.assertEqual(urls[url].get('check'), 'here', url)
            self.assertNotIn('digest', urls[url], url)
        # and where a real file is streamed verbatim, the promise is real
        sheet = urls['/studio/static/sheet.css']
        self.assertRegex(sheet['digest'], r'^[0-9a-f]{64}$')
        self.assertGreater(sheet['bytes'], 0)

    def test_the_worker_honours_the_three_promises(self):
        """The record is only half of it: lib/sw.js must read `check`, the
        digest and the length as three different things.  If `check` were
        ignored, every composed answer would be judged not-whole and its row
        would never tick -- which is worse than the fault being mended."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("if (want.check === 'here') return true;", sw)
        self.assertIn("self.crypto.subtle.digest('SHA-256', body)", sw)
        self.assertIn("res.headers.get('content-length')", sw)
        self.assertIn('reply({check: id, urls: urls});', sw)
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn("check: x.check || ''", keep, 'and lib/keep.js passes it through')

    def test_the_digest_cache_is_never_written_inside_the_owners_content(self):
        """It is machine-local derived data keyed by absolute path: it belongs
        in config/, beside prefs.json, and nowhere near a book.

        WHERE PARSEH PUTS IT, NOT WHERE THIS TEST DOES.  This module points
        both stores at a folder of its own while it runs (setUpModule), so the
        module in hand would only answer with that folder.  The shipped
        constants are read off lib/offline.py itself, loaded a second time,
        apart from the one the tests use."""
        spec = importlib.util.spec_from_file_location('offline_as_shipped',
                                                      ROOT / 'lib' / 'offline.py')
        shipped = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shipped)
        for store in (shipped.DIGESTS, shipped.WHERES):
            self.assertEqual(Path(store).resolve().parent, (ROOT / 'config').resolve(),
                             'one file for the whole machine, beside what else it knows '
                             'about itself: %s' % store)
        self.assertNotEqual(Path(self.offline.DIGESTS).resolve().parent, (ROOT / 'config').resolve(),
                            'and while this module runs, the one it writes is its own')
        before = {p: p.stat().st_mtime for p in self.book_dir.rglob('*') if p.is_file()}
        self.offline.book(str(self.book_dir), '/books/english/mini-en/')
        after = {p: p.stat().st_mtime for p in self.book_dir.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'asking what a book is made of writes nothing into it')
        ignored = (ROOT / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('config/digests.json', ignored, 'and it is not the owner\'s to commit')


# ------------------------------------------------------------ the app
def png_size(path):
    data = Path(path).read_bytes()[:24]
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


class AppTests(unittest.TestCase):
    """The mobile interface installed as an app: what the server says about
    it.  That Chromium finds the pages installable, that the worker takes
    them over and answers for a server that has gone, is driven by
    tests/mobile_pages.mjs (its part "app")."""

    def test_the_manifest_describes_the_mobile_interface(self):
        import mobile
        m = mobile.manifest()
        self.assertEqual((m['name'], m['short_name']), ('Parseh', 'Parseh'))
        # it opens on the mobile hub, in the mobile mode, and the whole toolbox is the app
        self.assertEqual((m['start_url'], m['scope'], m['id']), ('/?mode=mobile', '/', '/'))
        self.assertEqual(m['display'], 'fullscreen')
        self.assertIn('standalone', m['display_override'])
        self.assertEqual(m['orientation'], 'any')
        got = {(i['sizes'], i['purpose']) for i in m['icons']}
        self.assertEqual(got, {('192x192', 'any'), ('512x512', 'any'), ('512x512', 'maskable'),
                               # the size an iPhone asks for (mobile.manifest)
                               ('180x180', 'any')})

    def test_the_icons_are_there_at_the_sizes_named(self):
        import mobile
        import serve
        for i in mobile.manifest()['icons'] + [{'src': '/lib/icons/apple-touch-icon.png', 'sizes': '180x180'}]:
            # three of them are named on the public copy (PUBLIC_ICONS), so
            # that Chrome's builder out on the internet can fetch them; the
            # file is the same one, and it is here
            here = i['src']
            if mobile.PUBLIC_ICONS and here.startswith(mobile.PUBLIC_ICONS):
                here = mobile.ICONS + here[len(mobile.PUBLIC_ICONS):]
            self.assertIn(here, serve.STATIC_FILES)
            self.assertTrue(serve.static_ok(here))
            w, h = png_size(ROOT / here.lstrip('/'))
            self.assertEqual('%dx%d' % (w, h), i['sizes'], i['src'])
        # the script that drew them is not on the web
        self.assertFalse(serve.static_ok('/lib/icons/make.mjs'))

    def test_only_the_browser_that_builds_an_app_is_sent_outside(self):
        """Chrome on Android hands the description to a server of Google's,
        which fetches the icons itself from the internet: that one browser is
        told the public copies.  Everybody else fetches them itself, and an
        iPhone that cannot reach an icon draws its own letter on a tile and
        keeps it -- which is what he saw once the manifest pointed out."""
        import mobile
        ANDROID = ('Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Mobile Safari/537.36')
        IPAD = ('Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                'Version/17.5 Safari/605.1.15')
        FIREFOX = 'Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0'
        DESKTOP = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36')
        self.assertTrue(mobile.mints(ANDROID))
        for ua in (IPAD, FIREFOX, DESKTOP, '', None):
            self.assertFalse(mobile.mints(ua), ua)
        out = [i['src'] for i in mobile.manifest(ANDROID)['icons']]
        self.assertEqual(sum(1 for s in out if s.startswith(mobile.PUBLIC_ICONS)), 3, out)
        # and the one an iPhone takes is on this server even there, so the
        # install button still appears on a phone that cannot reach the public
        # copies at all (Chromium wants one fetchable icon of 144px or more)
        self.assertIn(mobile.ICONS + 'apple-touch-icon.png', out)
        for ua in (IPAD, FIREFOX, DESKTOP, None):
            got = [i['src'] for i in mobile.manifest(ua)['icons']]
            self.assertTrue(all(s.startswith(mobile.ICONS) for s in got), (ua, got))
        # everything else about the description is the same for everyone
        a, b = mobile.manifest(ANDROID), mobile.manifest(IPAD)
        del a['icons'], b['icons']
        self.assertEqual(a, b)

    def test_the_icons_named_outside_are_ones_the_project_publishes(self):
        """PUBLIC_ICONS is the project's address under the domain
        (lib/project.py ICONS_URL), and the guide's site serves what
        html-guide/build.py --pages puts in it: lib/icons/*.png.  An icon
        named there and not published is a 404 to the server that builds
        the phone's app, and the app is not built -- the fault this address
        was put here to mend.  (That the PUBLISHED site has them is
        tests/test_project.py's: it builds the site.  Here: every name is a
        PNG file of the tree, which is what that build copies.)  The one an
        iPhone takes is named on this server, so that a phone away from it
        still has it."""
        import mobile
        import project
        self.assertEqual(mobile.PUBLIC_ICONS, project.ICONS_URL)
        # asked as the one browser that is sent outside asks (mobile.mints)
        named = mobile.manifest('Mozilla/5.0 (Linux; Android 14) Chrome/126.0.0.0 Mobile')['icons']
        outside = [i for i in named if i['src'].startswith(mobile.PUBLIC_ICONS)]
        self.assertEqual(len(outside), 3)
        for i in outside:
            icon = ROOT / 'lib' / 'icons' / i['src'][len(mobile.PUBLIC_ICONS):]
            self.assertTrue(icon.is_file(), icon)
            self.assertEqual(icon.read_bytes()[:8], b'\x89PNG\r\n\x1a\n', icon)
        for i in named:
            if i not in outside:
                self.assertTrue(i['src'].startswith(mobile.ICONS), i['src'])

    def test_an_iphone_finds_the_icon_at_the_top_of_the_site_too(self):
        """Where a page carries no apple-touch-icon tag, Safari asks the top
        of the site for the name itself.  It used to be a 404, and an iPhone
        that can fetch no icon draws its own tile and keeps it."""
        import mobile
        src = (ROOT / 'serve.py').read_text(encoding='utf-8')
        self.assertIn('"/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"', src)
        self.assertIn('<link rel="apple-touch-icon" sizes="180x180"', mobile.app_head())

    def test_every_page_of_the_mobile_interface_carries_the_app_tags(self):
        import deckroutes
        import mobile
        head = mobile.app_head()
        self.assertIn('<link rel="manifest" href="/manifest.webmanifest">', head)
        self.assertEqual(deckroutes.APP_HEAD, head, 'the same tags, in the one place each side keeps them')
        self.assertIn(head, shelf())
        self.assertIn(head, mobile.install_page('authority'))
        for name in TEMPLATES:
            self.assertIn(head, rendered(name), name)
        import test_mobile_mode
        self.assertIn(head, test_mobile_mode.hub()[0])
        # and a page built without them -- a book's reader -- is given them
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        self.assertIn("if (location.protocol === 'file:' || document.querySelector('link[rel=manifest]')) return;", js)
        self.assertIn("['link', {rel: 'manifest', href: '/manifest.webmanifest'}]", js)

    def test_a_refresh_never_takes_up_what_the_page_before_found(self):
        """The owner's fall-back (TO-DO §2.24, 2026-09-24): "upon refreshing,
        do not assume still offline".  Every refresh -- F5, the browser's
        button, a finger pulling the page down, ↻ -- is reported as
        "reload", and on one the boot line sets no mark; the older
        performance.navigation decides where the newer entry is absent.  The
        mark it does set says `assumed`, and the line leaves no global for a
        page's own `let` to collide with.  The copy at the top of
        lib/parseh.js (a reader's, a player's) says the same."""
        import mobile
        boot = mobile.AWAY_BOOT
        self.assertIn('getEntriesByType("navigation")', boot)
        self.assertIn('type==="reload"', boot)
        self.assertIn('performance.navigation.type===1', boot)
        self.assertIn('if(!r&&a&&a.away===true', boot)
        self.assertIn('setAttribute("data-parseh-away","assumed")', boot)
        self.assertIn('\n(function(){try{', boot)
        self.assertTrue(boot.endswith('}catch(e){}})();</script>'), boot[-40:])
        top = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8').split('var KEY =', 1)[0]
        self.assertIn("getEntriesByType('navigation')", top)
        self.assertIn("nav.type === 'reload'", top)
        self.assertIn('performance.navigation.type === 1', top)
        self.assertIn('if (!afresh && seen && seen.away === true', top)
        self.assertIn("setAttribute('data-parseh-away', 'assumed')", top)

    def test_whether_the_computer_is_there_is_asked_in_one_place(self):
        """TO-DO §2.24: `/__activity` was asked by three things at once --
        the activity list, lib/keep.js's probe and every watched ask -- and
        none of them cancelled an ask it had given up on, which on a slow
        tunnel piled up until a computer that was there looked gone.  One
        poll now, in lib/activity.js, with a cancel; everything else
        listens.  And the worker leaves that one address to the browser, so
        a refusal and a silence reach the page as what they are.  (The stop
        buttons still read the LIST once, on the press, to name what a stop
        would cut off: a question about the work, never about whether the
        computer is there.)"""
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertNotIn('/__activity', keep.replace('lib/activity.js', ''))
        for name in ('lib/parseh.js', 'markdown/app/static/app.js', 'markdown/app/static/decks.js'):
            self.assertNotIn('nobodyThere', (ROOT / name).read_text(encoding='utf-8'), name)
        for name in ('lib/keep.js', 'lib/parseh.js', 'markdown/app/static/app.js'):
            self.assertIn("'parseh:reach'", (ROOT / name).read_text(encoding='utf-8').replace('"', "'"), name)
        act = (ROOT / 'lib' / 'activity.js').read_text(encoding='utf-8')
        self.assertEqual(act.count("fetch('/__activity'"), 1)
        self.assertIn('ctl.abort()', act)
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertRegex(sw, r"if \(url\.pathname === '/__activity'( \|\| [^)]*\))?\) return;")

    def test_a_download_made_on_demand_is_left_to_the_browser(self):
        """TO-DO §2.28: the worker gave a navigation to a document's HTML export
        2.5 s and then served the page that says Parseh cannot be reached.  An
        export is made while it is asked for, however long that takes: the
        worker leaves every such download to the browser."""
        import re
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("MADE_ON_DEMAND.test(url.pathname)) return;", sw)
        made = re.search(r"const MADE_ON_DEMAND = /(.+)/;", sw).group(1)
        for path in ("/studio/download/cats-1a2b3c/html", "/studio/download/cats-1a2b3c/pdf",
                     "/exercises/api/decks/italian/verbi/export"):
            self.assertTrue(re.search(made, path), path)
        self.assertFalse(re.search(made, "/studio/doc/cats-1a2b3c"), "a page is still the worker's")

    def test_the_hub_has_the_door_and_the_app_not(self):
        import test_mobile_mode
        html = test_mobile_mode.hub()[0]
        self.assertIn('<a class="m-door m-guide m-appdoor" href="/m/install/">', html)
        css = (ROOT / 'lib' / 'mobile.css').read_text(encoding='utf-8')
        self.assertIn('@media (display-mode:standalone),(display-mode:fullscreen),(display-mode:minimal-ui){\n'
                      '  .m-appdoor{display:none!important}', css)

    def test_the_worker_keeps_what_was_kept_and_answers_it_first(self):
        """§19 reversed the worker's old rule (it kept nothing but the offline
        page): what has been KEPT ON THIS PHONE is answered by the phone."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        # one cache per thing, and one for the shared files
        self.assertIn("const KEPT = 'parseh-kept-';", sw)
        self.assertIn("const SHARED = 'parseh-shared';", sw)
        self.assertIn("const OFFLINE = '/m/offline/';", sw)
        # the kept copy answers first, and the small parts are renewed behind it
        self.assertIn('let hit = await caches.match(r, {ignoreVary: true', sw)
        # AND A KEPT PAGE REACHED WITH A QUERY IS STILL THAT PAGE.  Cramming a
        # picked handful opens <deck>/cram?selected=<ids>, where the ids are
        # whatever was ticked -- an address no record can name, for a page
        # that was kept.  Matched strictly it missed and fell to the offline
        # page with the whole deck sitting on the phone.  Navigations only: a
        # query at a DOOR means a different answer.
        self.assertIn('if (!hit && nav && url.search)', sw)
        self.assertIn('ignoreSearch: true', sw)
        self.assertIn('renew(r);', sw)
        # a range is cut here: the Cache API answers none, and a kept
        # narration would otherwise play from 0:00 and refuse to be moved
        self.assertIn("status: 206", sw)
        self.assertIn("head.set('Content-Range'", sw)
        # what only the computer can answer is refused at once, not hung on
        self.assertIn('needsComputer(url.pathname)', sw)
        self.assertIn('status: 503', sw)
        # a navigation that fails still gets the offline page
        self.assertIn('const nav = r.mode === \'navigate\';', sw)
        # nothing that writes is touched at all
        self.assertIn("if (r.method !== 'GET') return;", sw)
        # served from the top of the site, so that its scope is all of it
        serve_py = (ROOT / 'serve.py').read_text(encoding='utf-8')
        self.assertIn('if path == "/sw.js":', serve_py)
        self.assertIn('"text/javascript; charset=utf-8"', serve_py)

    def test_every_navigation_has_a_deadline(self):
        """The app used to stall on its own splash: with a network up and the
        computer unreachable -- asleep, or a Tailscale peer down -- the socket
        never settled, respondWith never resolved, and nothing was ever drawn
        (the owner's 1 and 2, 2026-09-23).  A navigation waits about two and a
        half seconds and then does not hang.

        WHAT THE DEADLINE MEANS FOR A PAGE NOBODY KEPT CHANGED ON 2026-09-28
        (TO-DO §2.28), by the owner's own decision, which overturns the rule
        of 2026-09-23 in this one respect: the deadline used to be the point
        where the computer was called gone, and a computer that was alive and
        took longer than that to begin a page was answered with "Parseh
        cannot be reached" -- again on Try again, every time.  It is now the
        point where the PAGES ARE ASKED whether the computer is answering
        (`navigate`, `computerAnswers`): the worker waits for the fetch it
        made, up to PATIENT, while one of them says so, and falls where a
        refused socket falls when none does."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn('const DEADLINE = 2500;', sw)
        self.assertIn('function reach(request, ms)', sw)
        self.assertIn('Promise.race', sw)
        # AND SO DOES EVERYTHING ELSE.  A subresource used to be handed a
        # bare fetch with no ceiling, so one address a kept page asked for and
        # nobody kept -- /lib/mt.js, a parser-blocking script every reader
        # loads -- held every book open for ever in airplane mode, half drawn
        # (the owner, 2026-09-23).  A page with a broken picture is a page; a
        # page that never parses is nothing.
        self.assertIn('return await (nav ? navigate(r) : reach(r, PATIENT));', sw)
        self.assertNotIn('fetch(r))', sw.split('async function answer')[1].split('self.addEventListener')[0],
                         'nothing in answer() may fetch without a deadline')
        # A NAVIGATION IS GIVEN THE DEADLINE, AND THE PAGE IS ASKED AT IT.  One
        # fetch, waited for twice: a second one would be a second question put
        # to the computer, and a page that is slow to make would be made twice.
        nav = sw.split('async function navigate(request)')[1].split('async function computerAnswers')[0]
        self.assertEqual(nav.count('fetch('), 1, 'the worker asks the computer for a page once')
        self.assertIn('const coming = fetch(request);', nav)
        self.assertIn('return await within(coming, DEADLINE);', nav)
        self.assertIn('if (!err.late || !(await computerAnswers())) throw err;', nav)
        self.assertIn('return await within(coming, began + PATIENT - Date.now());', nav)
        self.assertIn('const PATIENT = 30000;', sw)

    def test_at_the_deadline_the_pages_are_asked_and_the_computer_is_not(self):
        """The owner's decision of 2026-09-28: "ask the page's own verdict".
        The page's poll (lib/activity.js) stays the ONE asker of the computer,
        so the worker asks it nothing -- it sends the open pages one message
        with a port, and a page answers that the computer answers when ITS
        OWN question, put after this one, has been answered by it, or that it
        is away at once when it has judged it gone.  What a page said earlier
        is never the answer (a computer suspended a moment ago is just what
        a page cannot tell from a slow one for forty-five seconds), so
        nothing is read from its memory; a page that cannot answer, and no
        page at all, is a silence, and a silence is the offline page at the
        deadline and one short wait more."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        ask = sw.split('async function computerAnswers()')[1].split('\n}\n')[0]
        self.assertNotIn('fetch(', ask, 'the worker asks the pages, and the computer nothing')
        self.assertNotRegex(sw, r"fetch\([^)]*__activity",
                            'the worker has no question of its own to put to the computer')
        self.assertIn("self.clients.matchAll({type: 'window', includeUncontrolled: true})", ask)
        self.assertIn('if (!pages.length) return false;', ask)
        self.assertIn('new MessageChannel()', ask)
        self.assertIn('page.postMessage({reachAsk: true}, [line.port2]);', ask)
        self.assertIn("said(!!e.data && e.data.state === 'there')", ask)
        self.assertIn('setTimeout(() => end(false), ASKED)', ask)
        self.assertIn('const ASKED = 1500;', sw)
        act = (ROOT / 'lib' / 'activity.js').read_text(encoding='utf-8')
        # the page: one poll, still -- nothing here asks the computer a second way
        self.assertEqual(act.count("fetch('/__activity'"), 1)
        heard = act.split('function questioned(e) {')[1].split('\n  }\n')[0]
        self.assertIn('var port = e.data && e.data.reachAsk && e.ports && e.ports[0];', heard)
        self.assertIn("if (reach.state === 'away') { port.postMessage({state: 'away'}); return; }", heard)
        self.assertIn('waiting.push(port);', heard)
        self.assertIn('poke(0);', heard)
        self.assertNotIn('postMessage({state: reach.state', heard, 'never the verdict it held')
        self.assertIn("waiting.splice(0).forEach(function (port) { port.postMessage({state: 'there'}); });", act)
        self.assertIn("navigator.serviceWorker.addEventListener('message', questioned);", act)
        # and an ask that ended just before the question came must not cost the answer
        # (the question comes first; after it, work counted in items is asked at its own faster pace, a0.5.6)
        self.assertIn('return waiting.length ? 0 : counting() ? COUNTED : busy() ? FAST : SLOW;', act)
        self.assertIn("return server.running.some(function (e) { return e.unit === 'items'; });", act)

    def test_the_app_shell_is_kept_with_the_worker(self):
        """The start address of the app -- /?mode=mobile, which the manifest
        names -- was in no cache at all, so there was nothing for a deadline
        to fall back to.  The way in is kept now, from one list the computer
        gives (lib/offline.py, shell())."""
        import mobile
        import offline
        rec = offline.shell()
        self.assertTrue(rec['ok'])
        # the hub at BOTH of its addresses: caches.match tells them apart, and
        # the app starts at the one with the query on it
        self.assertEqual(mobile.manifest()['start_url'], '/?mode=mobile')
        self.assertIn('/?mode=mobile', rec['pages'])
        self.assertIn('/', rec['pages'])
        for page in ('/m/books/', '/m/videos/', '/m/kept/', '/m/offline/',
                     '/exercises/', '/studio/'):
            self.assertIn(page, rec['pages'])
        # the two lists those library pages ask for rather than carry
        self.assertIn('/exercises/api/decks', rec['apis'])
        self.assertIn('/studio/api/docs', rec['apis'])
        # and everything those pages load: the toolbox's shared files and the
        # studio's own, or a page would open offline with no layout at all
        for url in offline.SHARED:
            if (ROOT / url.lstrip('/')).exists():
                self.assertIn(url, rec['files'], url)
        self.assertIn('/studio/static/decks.js', rec['files'])
        self.assertIn('/studio/static/app.css', rec['files'])
        self.assertIn('/manifest.webmanifest', rec['files'])
        # a studio mounted elsewhere is followed, not hard-coded
        other = offline.shell(studio_base='/s', decks_base='/x')
        self.assertIn('/x/api/decks', other['apis'])
        self.assertIn('/s/static/app.js', other['files'])
        # the worker asks for it at one door and puts the hub under both of
        # its addresses
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("const SHELL_DOOR = '/__shell';", sw)
        self.assertIn("const SHELL = 'parseh-shell-1';", sw)
        self.assertIn("const q = url.indexOf('?');", sw)
        self.assertIn('await cache.put(new Request(url.slice(0, q)), res.clone());', sw)

    def test_the_worker_installs_one_page_and_nothing_else(self):
        """And this is the whole of why the app stopped installing (TO-DO §0,
        the third block of 2026-09-23).  The install event used to fetch the
        way in -- fifty-nine addresses, three and a quarter megabytes, one
        after another inside waitUntil -- and a worker that grinds through
        three megabytes over a tunnel stays in the installing state, which is
        a state Chrome will not install a site from: the owner accepted the
        offer on his phone and got no icon.

        So install is back to what it was before §19 was written: the two
        small pages that must open with the computer away, and skipWaiting.
        Nothing in the suite would have noticed the shell creeping back into
        it, which is why this test is about what install does NOT do."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        install = sw.split("self.addEventListener('install'")[1].split('\n});')[0]
        activate = sw.split("self.addEventListener('activate'")[1].split('\n});')[0]
        # the two pages, named in one place, and nothing else fetched
        self.assertIn("const OWN = [OFFLINE, '/m/kept/'];", sw)
        self.assertIn('OWN.map(u =>', install)
        # AND THEY HAVE A DEADLINE TOO.  `cache.add` is a fetch, and a fetch
        # waits for a socket, not for a computer: on the very network this
        # worker exists for -- wifi up, computer asleep -- two small pages
        # could hold the install event open until Chrome's own watchdog, which
        # is the same fault in miniature.  Each page is raced, and so is the
        # event itself.
        self.assertIn('reach(new Request(u', install)
        self.assertIn('DEADLINE', install)
        self.assertIn('Promise.race', install)
        # first and not last, so that a disk which refuses those two pages
        # cannot stop the worker activating either
        self.assertLess(install.index('self.skipWaiting();'), install.index('e.waitUntil('))
        # neither event waits on the shell: the old shellIn is gone outright,
        # and neither of them may reach the computer for the list
        self.assertNotIn('shellIn', sw)
        for event, text in (('install', install), ('activate', activate)):
            for word in ('warm', 'SHELL_DOOR', 'shellNow'):
                self.assertNotIn(word, text, '%s must not touch the shell (%s)' % (event, word))
        # activate keeps what it always did: the old caches dropped, the open
        # pages claimed
        self.assertIn('caches.delete(k)', activate)
        self.assertIn('self.clients.claim()', activate)

    def test_the_warming_is_asked_for_by_message_and_says_how_far_it_is(self):
        """What install no longer does, a page asks for once it is open --
        and the owner asked that it not be silent (his words, 2026-09-23:
        "I want the warming not to be silent, the getting ready - 41 of 59 is
        a good approach").

        Two words and two messages, and no third one: `way-in` is the pages,
        the lists and the files, `studio` is the faces; `warming` while the
        list is being walked and `warmed` when this worker has stopped
        walking it.  `done` counts addresses SETTLED, fetched or skipped, so
        a warm phone runs to the end without a single fetch -- which is what
        makes asking cheap enough for a page to ask every time it opens, and
        what makes a warming cut off in the middle carry on where it
        stopped."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        # the door the page knocks on, and the two words it may say
        self.assertIn('if (msg.warm) e.waitUntil(warm(msg.warm));', sw)
        self.assertIn("if (what !== 'way-in' && what !== 'studio') return Promise.resolve();", sw)
        # one address at a time, and what the phone holds is passed over --
        # the same question keep() asks, asked by the same helper
        self.assertIn('async function warmList(what)', sw)
        self.assertIn('for (const url of urls) {', sw)
        # and it asks the app's own cache too, so the two pages the install
        # event has just fetched are not fetched a second time
        self.assertIn('if (!(await held(req, [cache, shared, app]))) {', sw)
        # THE FACES GO WHERE THEY WILL OUTLIVE A RELEASE.  The way in is the
        # app's and belongs in the shell; the studio's faces are what a kept
        # note, a kept document and a studio page all draw with, so they go to
        # the shared cache -- in the shell they were a trap, since `keep`
        # skips what the shell holds and the next version bump took them away
        # from the book that had leant on them.
        self.assertIn("caches.open(what === 'studio' ? SHARED : SHELL)", sw)
        self.assertIn('async function held(req, where)', sw)
        # the two messages, to every window and not only to the page that
        # asked: the line may be on a page that asked for nothing
        self.assertIn('await tellClients({warming: {what: what, done: done, of: of}});', sw)
        # A PASS THAT STOPPED IS NOT A PASS THAT FINISHED, and the message
        # says which: a warm given up on because the computer went away used
        # to be announced as done, and the install page then read "Ready: its
        # pages are on this phone now" over a list hardly fetched.
        self.assertIn('await tellClients({warmed: {what: what, of: of, done: done}});', sw)
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn('whole: whole', keep)
        self.assertIn('Stopped at ', keep)
        self.assertIn('warmAsked[p.what] = false', keep,
                      'and a list cut off may be asked for again when the '
                      'computer comes back, or the rest never arrives')
        self.assertIn("self.clients.matchAll({type: 'window'})", sw)
        # and the page's side: the ask, the two messages read, and the two
        # places a studio page is recognised -- its own address, and a note
        # opened by clicking its mark
        self.assertIn('w.postMessage({warm: what});', keep)
        self.assertIn('if (d.warming) warmSaw(d.warming, false);', keep)
        self.assertIn('if (d.warmed) warmSaw(d.warmed, true);', keep)
        self.assertIn("warm('way-in');", keep)
        self.assertIn("if (STUDIO_PAGE.test(location.pathname)) warm('studio');", keep)
        self.assertIn("e.target.closest('[data-note]')) warm('studio');", keep)
        # never in the browser mode and never while the computer is away:
        # this is the APP fetching its own pages, and a tab is not the app
        self.assertIn('if (!what || warmAsked[what] || !mobile()) return;', keep)
        self.assertIn('if (!probed || away || !warmWant.length) return;', keep)

    def test_the_studios_faces_are_warmed_later_and_are_not_the_way_in(self):
        """`later` is the owner's own split: everything in pages, apis and
        files is how a person GETS somewhere, and without it a tap opens
        nothing; the studio's thirteen faces are what a studio PAGE needs to
        look like itself, and they were 1.83 of the 3.26 megabytes the door
        named in one breath.  They are still kept, by the same worker into
        the same cache -- afterwards, and only when a page that needs them
        asks."""
        import offline
        rec = offline.shell()
        faces = [x['url'] for x in offline.studio_faces()]
        self.assertEqual(rec['later'], faces)
        # the thirteen the sheet is set in, and TeX Gyre Chorus (a0.5.0), which sets the name Parseh in the
        # studio's bar and is picked up with the rest because the directory is what is read: it is there once the
        # studio has started (server.py copies it with the others), so a tree that has not started it has thirteen
        chorus = '/studio/static/fonts/texgyrechorus-mediumitalic.otf'
        self.assertIn(len(faces), (13, 14), faces)
        self.assertEqual(chorus in faces, len(faces) == 14, faces)
        # OUT of the way in, and it is the studio's own folder that goes --
        # the toolbox's own faces (/lib/fonts/) are part of the way in, since
        # a shelf with no Persian face is not a shelf anybody can read
        for url in faces:
            self.assertNotIn(url, rec['files'], url)
        self.assertFalse([u for u in rec['files'] if '/static/fonts/' in u])
        self.assertTrue([u for u in rec['files'] if u.startswith('/lib/fonts/')])
        # what the studio's pages LOAD stays in the way in, so that the
        # worker still learns the studio's own prefix from `files` alone
        self.assertIn('/studio/static/decks.js', rec['files'])
        self.assertIn('/studio/static/app.css', rec['files'])
        # a studio mounted elsewhere is followed here too
        other = offline.shell(studio_base='/s')
        self.assertTrue(all(u.startswith('/s/static/fonts/') for u in other['later']), other['later'])
        # and the worker knows which list that word means
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("if (what === 'studio') return (list.later || []).filter(Boolean);", sw)
        # WHAT A PAGE IS MADE OF COMES BEFORE THE PAGE.  A warm stops wherever
        # the computer goes away, and what it reached by then is what the
        # phone opens with: cached pages-first, the commonest half-warm state
        # was the hub present with its sheet and its script missing -- an app
        # that opened on unstyled markup doing nothing, which reads as Parseh
        # broken rather than Parseh away.
        self.assertIn("return [].concat(list.files || [], list.apis || [], list.pages || [])", sw)

    def test_the_getting_ready_line_is_drawn_where_a_page_leaves_a_slot(self):
        """The owner's own decision: the warming is not silent.  Any page may
        carry `[data-parseh-warm]`; while a warming runs it reads "Getting
        ready — 41 of 59", and a page that asked for nothing shows nothing at
        all.  The two places he is certain to be standing while the app gets
        ready carry one: the hub the app opens on, and the install page that
        asks him to stay until it is ready."""
        import mobile
        import test_mobile_mode
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn("var slots = document.querySelectorAll('[data-parseh-warm]');", keep)
        self.assertIn("'Getting ready — ' + done + ' of ' + of", keep)
        # hidden until something is really warming, and the numbers are the
        # worker's own: two lists warming together are summed
        self.assertIn('s.hidden = !any || (!running && !stay);', keep)
        self.assertIn('done += warmRuns[k].done;', keep)
        self.assertIn('of += warmRuns[k].of;', keep)
        # the hub's line goes when there is nothing left to say -- it is
        # opened a dozen times a day on a phone that has been ready for a
        # week -- and the install page's stays, because it told somebody to
        # wait for it
        self.assertIn('<p data-parseh-warm role="status" hidden></p>', test_mobile_mode.hub()[0])
        self.assertIn('<p data-parseh-warm="stay" role="status" hidden></p>', mobile.install_page('authority'))
        self.assertIn("var stay = s.getAttribute('data-parseh-warm') === 'stay';", keep)
        css = (ROOT / 'lib' / 'parseh.css').read_text(encoding='utf-8')
        self.assertIn('[data-parseh-warm][hidden]{display:none}', css)

    def test_a_shell_page_is_not_the_cannot_be_reached_page(self):
        """The owner's choice, 2026-09-23: the usual page opens, with the
        offline chip; /m/offline/ is left for a navigation that is neither
        kept nor part of the way in.  And it must not go stale in silence --
        the worker reads it again and the page swaps its list in place."""
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("await tellClients({shellFresh: url});", sw)
        # only when what came back really differs
        self.assertIn('if (was !== now)', sw)
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn('if (d.shellFresh) fillIn(d.shellFresh);', keep)
        self.assertIn("var BLOCKS = '[data-shell-block], .m-doors, .m-more-doors';", keep)
        # the shelves say which block is the computer's; the phone's own list
        # of what is kept says nothing, and is never swapped
        import mobile
        self.assertIn('<div class="m-shelf" data-shell-block>', shelf())
        # the videos' frame is the same block, and /m/kept/ is the phone's own
        src = (ROOT / 'lib' / 'mobile.py').read_text(encoding='utf-8')
        self.assertEqual(src.count('<div class="m-shelf" data-shell-block>'), 2)
        self.assertNotIn('data-shell-block', mobile.kept_page())
        # and the reading place is drawn again on the block that arrives
        self.assertIn("document.addEventListener('parseh:shell-filled', mark);", mobile.READ_ON_JS)

    def test_what_is_not_on_this_phone_is_drawn_but_not_tappable(self):
        """As a book whose reader was never built already looks on the shelf
        (m-book m-off).  The phone knows what is kept from parseh_kept."""
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn("card.classList.add('m-off');", keep)
        self.assertIn("a.removeAttribute('href');", keep)
        self.assertIn("a.setAttribute('aria-disabled', 'true');", keep)
        self.assertIn('Not on this phone', keep)
        # and it is undone when the computer can be reached again
        self.assertIn('function onPhone(card)', keep)

    def test_counts_the_clock_makes_wrong_are_not_shown_while_away(self):
        """What is due was worked out on the computer when the page was last
        read from it; the list beside it is still true, so the lists stay and
        the numbers go (the owner's 1, 2026-09-23)."""
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn('function showClock(hide)', keep)
        self.assertIn("document.querySelectorAll('[data-clock-count]')", keep)
        # the hub's counts say WHAT they count, so the one the clock moves is
        # named rather than matched by the words in it (serve.py count_tag)
        self.assertIn('[data-count-kind="due"]', keep)
        serve_py = (ROOT / 'serve.py').read_text(encoding='utf-8')
        self.assertIn('data-count-kind="%s"', serve_py)
        decks = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('label.dataset.clockCount = counts.dataset.clockCount = "";', decks)
        self.assertIn('now.dataset.clockCount = "";', decks)

    def test_a_kept_thing_shows_two_buttons(self):
        """Change what is kept, and Remove from this phone: one control never
        carries two meanings (the owner's 4, 2026-09-23).  The list of
        recordings is the computer's, so offline the button says so."""
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn("(have ? 'Change what is kept' : 'Keep on this phone') +", keep)
        self.assertIn("(away ? ' — needs the computer' : '')", keep)
        self.assertIn("drop.textContent = 'Remove from this phone';", keep)
        # Save fetches what is ticked and frees what is not, saying both --
        # and, since the notes came (TO-DO §0, the second block), how many
        # files the computer no longer has are being given back with them
        self.assertIn("'Save fetches ' + big(s.fetches) + ', frees ' + big(s.frees) + '.'", keep)
        self.assertIn('the computer no longer has', keep)
        # and asks once before it frees anything already here
        self.assertIn('window.confirm(', keep)
        # Select all and Clear all are two controls, each saying which it is
        self.assertIn("el('button', 'kp-small', 'Select all')", keep)
        self.assertIn("el('button', 'kp-small', 'Clear all')", keep)
        # a finger drawn across the boxes takes the run it crosses instead of
        # scrolling the sheet
        self.assertIn('function dragging(list)', keep)
        self.assertIn("list.addEventListener('pointermove'", keep)
        self.assertIn('list.setPointerCapture(e.pointerId)', keep)
        css = (ROOT / 'lib' / 'parseh.css').read_text(encoding='utf-8')
        self.assertIn('touch-action:none', css.split('.kp-row{')[1].split('}')[0])
        # the worker can take named addresses out of one thing's cache
        sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn('async function free(job, reply)', sw)
        self.assertIn('async function inside(id, reply)', sw)

    def test_keep_has_a_slot_on_a_deck_and_on_a_document(self):
        """§19.8, §19.9: it was dead on both pages.  Each names the row the
        buttons go in, and the value is the class that page dresses its own
        buttons in."""
        tpl = ROOT / 'markdown' / 'app' / 'templates'
        deck = (tpl / 'deck.html').read_text(encoding='utf-8')
        doc = (tpl / 'doc.html').read_text(encoding='utf-8')
        self.assertIn('<div class="dk-deckactions" data-keep-slot="btn">', deck)
        self.assertIn('<div class="navstack" data-keep-slot="btn ghost">', doc)
        for page in (deck, doc):
            self.assertIn('<script src="/lib/keep.js" defer></script>', page)
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn("document.querySelector('[data-keep-slot]')", keep)
        self.assertIn("row.getAttribute('data-keep-slot')", keep)
        # and the doors those two pages ask are where keep.js looks for them
        deckroutes = (ROOT / 'markdown' / 'app' / 'deckroutes.py').read_text(encoding='utf-8')
        server = (ROOT / 'markdown' / 'app' / 'server.py').read_text(encoding='utf-8')
        self.assertIn('/__offline$" % (F, S),        api_deck_offline)', deckroutes)
        self.assertIn('/__offline$",         api_doc_offline)', server)

    def test_keeping_a_deck_and_taking_it_out_are_two_things(self):
        """Keeping is the copy; taking out is the right to study away, and it
        asks for the copy first.  Giving the deck back leaves the copy alone
        (the owner's 8 and 9, 2026-09-23)."""
        decks = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('if (!deckIsKept(deck)) {', decks)
        self.assertIn('await keepDeckNow(deck);', decks)
        # and it says which of the two it is doing while it does it
        self.assertIn('"Keeping it on this phone first…"', decks)
        # giving it back no longer throws the copy away
        back = decks.split('async function giveDeckBack')[1].split('\n}')[0]
        self.assertNotIn('drop:', back)
        self.assertNotIn('delete reg[', back)
        # and removing the copy while the deck is out is refused, with why
        keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.assertIn('function heldBack(at)', keep)
        self.assertIn("'parseh_deck_out:'", keep)
        import mobile
        self.assertIn('parseh_deck_out:', mobile.KEPT_JS)

    def test_the_offline_page_stands_alone(self):
        """It is kept by the worker and opens with nothing to ask anybody: no
        stylesheet, no script from anywhere.  Its one inline script is the
        list of what is kept, read from this phone's own registry (§19.5)."""
        import mobile
        html = mobile.offline_page()
        self.assertNotIn('<link', html)
        self.assertNotIn('<script src', html)
        self.assertIn('prefers-color-scheme:dark', html)
        self.assertIn('location.reload()', html)
        self.assertIn("localStorage.getItem('parseh_kept')", html)

    def test_the_offline_page_tries_again_and_says_that_it_tried(self):
        """TO-DO §2.28: "the try again button which doesn't do anything".  A
        reload of an address that fails again put this very page up again,
        word for word, and nobody could tell a press that was heard from one
        that was not.  Now the press is written down for the page that comes
        back, which says when it tried -- and GO BACK is a button of its own,
        for a page the person came from.  Driven end to end in
        tests/mobile_pages.mjs (partExport); this holds the parts that must
        not drift apart from it."""
        import mobile
        html = mobile.offline_page()
        # the press: written down, then the address is loaded again (which
        # CAN succeed), the button saying it is trying meanwhile
        self.assertIn('id="again"', html)
        self.assertIn('onclick="tryAgain()"', html)
        press = html.split('function tryAgain()')[1].split('\n  }\n')[0]
        self.assertIn("sessionStorage.setItem(TRIED", press)
        self.assertIn('b.disabled = true', press)
        self.assertIn("Trying\\u2026", press)
        self.assertIn('location.reload()', press)
        # the page that comes back says so, once, and only for a try as young
        # as one load and for this address -- and never on /m/offline/ itself
        self.assertIn("Still cannot reach it. Tried again at ", html)
        self.assertIn("sessionStorage.removeItem(TRIED)", html)
        self.assertIn("note.page === location.href", html)
        self.assertIn("&& reloaded() &&", html)
        self.assertIn("n.type === 'reload'", html)
        self.assertIn("location.pathname !== '/m/offline/'", html)
        self.assertIn('id="tried" role="status" aria-live="polite" hidden', html)
        # GO BACK: its own button, hidden until there is somewhere to go back
        # to, and never inside a frame (where it would take the whole page)
        self.assertIn('id="back" class="plain" onclick="history.back()" hidden>Go back</button>', html)
        self.assertIn("window.top === window && history.length > 1", html)
        # an address that answers with a FILE does not replace this page, and
        # the button must not stay "Trying…" over it for ever
        self.assertIn("}, TRIED_WAIT);", press)
        self.assertIn("b.disabled = false", press)
        # still one page that stands alone, whatever it now does
        self.assertNotIn('<link', html)
        self.assertNotIn('<script src', html)
        self.assertNotIn('%(', html)

    def test_what_a_thing_is_made_of_is_one_answer(self):
        """§19.3: one answer per thing, said as addresses, with the sizes and
        a version -- and the heavy parts apart from the small ones."""
        import offline
        self.assertIn('/lib/parseh.js', offline.SHARED)
        self.assertIn('/lib/keep.js', offline.SHARED)
        rec = offline.book(str(FIXTURES / 'english' / 'mini-en'), '/books/english/mini-en/')
        if rec is None:          # the fixture is not built on this machine
            return
        self.assertEqual(rec['kind'], 'book')
        self.assertTrue(rec['version'])
        self.assertTrue(all('url' in x and 'bytes' in x for x in rec['small']))
        # the reader is opened at its directory as well as at index.html
        urls = [x['url'] for x in rec['small']]
        if '/books/english/mini-en/reader/index.html' in urls:
            self.assertIn('/books/english/mini-en/reader/', urls)
        # THREE PARTS SINCE 2026-09-23, not two: the page and its text, the
        # groups that are one tick apiece (the notes written beside this book)
        # and the heavy things picked one by one.  Written as the sum of all
        # three whether or not this fixture has a note beside it, so that the
        # day somebody writes one here the arithmetic is still the code's and
        # not this line's (tests/test_offline_notes.py drives the group
        # itself).
        totals = offline.totals(rec)
        self.assertEqual(totals['bytes'], totals['small_bytes'] + totals['groups_bytes']
                         + totals['media_bytes'])

    def test_the_install_page_says_what_the_server_speaks(self):
        import mobile
        own = mobile.install_page('authority')
        self.assertIn('href="/m/install/parseh-ca.crt"', own)
        self.assertIn('data-parseh-install hidden', own)
        self.assertIn('data-browser-page="/"', own)
        for other in ('own', 'http'):
            self.assertNotIn('parseh-ca.crt', mobile.install_page(other), other)
        # nothing on it asks for a terminal
        for page in (own, mobile.install_page('own'), mobile.install_page('http')):
            for word in ('serve.sh', 'serve.bat', 'terminal', 'openssl', '--http'):
                self.assertNotIn(word, page)

    def test_the_mode_comes_from_the_apps_address(self):
        js = (ROOT / 'lib' / 'parseh.js').read_text(encoding='utf-8')
        at = js.index('var m = /(?:^\\?|&)mode=(browser|mobile)(?=&|$)/.exec(location.search);')
        # read before the mode is first put on the page
        self.assertLess(at, js.rindex('  apply();\n  modeApply();'))
        self.assertIn('history.replaceState(history.state', js)
        # the worker registered in the mobile mode, on every page and at the switch
        self.assertIn("if (isMobile()) appRegister();", js)
        self.assertIn("modeOnChange(function (m) { if (m === 'mobile') appRegister(); });", js)
        decks = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('if (m === "mobile") appRegister();', decks)


@unittest.skipUnless(shutil.which('openssl'), 'openssl makes the certificate')
class UpdateTests(unittest.TestCase):
    """The app's half of an update (TO-DO §13.16): every release a new worker,
    which says so in a line; nothing kept swept by it; and a keep check that
    tells a file Parseh changed from a file that is broken.  What a browser
    does with all of it is driven in tests/mobile_pages.mjs (`update`); what
    is held here is the shape that makes it possible."""

    def setUp(self):
        import mobile
        self.mobile = mobile
        self.sw = (ROOT / 'lib' / 'sw.js').read_text(encoding='utf-8')
        self.keep = (ROOT / 'lib' / 'keep.js').read_text(encoding='utf-8')
        self.fresh_build = patch.object(mobile, '_build', None)
        self.fresh_build.start()

    def tearDown(self):
        self.fresh_build.stop()

    def event(self, name):
        return self.sw.split("self.addEventListener('%s'" % name)[1].split('\n});')[0]

    def test_the_worker_is_served_with_this_release_written_in(self):
        """A browser installs a new worker only when /sw.js is new bytes, and
        a release that did not edit lib/sw.js changed none of them."""
        import version
        served = self.mobile.worker().decode('utf-8')
        self.assertIn('const RELEASE = %s;' % json_str(version.VERSION), served)
        self.assertNotIn('__PARSEH_', served, 'both placeholders are written over')
        self.assertEqual(served, self.sw.replace("'__PARSEH_RELEASE__'", json_str(version.VERSION))
                                        .replace("'__PARSEH_BUILD__'", json_str(self.mobile.release_build())),
                         'and nothing else in the worker is touched')
        with patch.object(version, 'VERSION', 'a9.9.9'):
            other = self.mobile.worker().decode('utf-8')
        self.assertNotEqual(served, other, 'another release is another worker')
        self.assertIn('const RELEASE = "a9.9.9";', other)
        # read unstamped -- off the disk, by a server that does not know to
        # write it -- the worker knows no release and announces nothing
        self.assertIn("const STAMPED = RELEASE.indexOf('__') !== 0;", self.sw)

    def test_the_build_is_the_commit_of_the_release_manifest(self):
        """The same version installed twice -- how an unpublished release is
        iterated on -- is two workers when the commit differs."""
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / 'lib'
            lib.mkdir()
            with patch.object(self.mobile, 'LIB', str(lib)):
                self.assertEqual(self.mobile.release_build(), '', 'no manifest, no build')
                self.mobile._build = None
                (Path(tmp) / '.parseh-release.json').write_text(
                    '{"format": "parseh-release/1", "commit": "33e05192fed8aa0011223344556677889900aabb"}',
                    encoding='utf-8')
                self.assertEqual(self.mobile.release_build(), '33e05192fed8')
                self.assertIn('const BUILD = "33e05192fed8";', self.mobile.worker().decode('utf-8'))
                self.mobile._build = None
                (Path(tmp) / '.parseh-release.json').write_text('{"commit": "</script>"}', encoding='utf-8')
                self.assertEqual(self.mobile.release_build(), '', 'what is not a commit is not written in')
        import release
        self.assertEqual(self.mobile.RELEASE_MANIFEST, release.MANIFEST,
                         'the manifest is looked for under the name the release builder writes')

    def test_the_server_answers_sw_js_stamped(self):
        import http.client
        import threading
        import serve
        with patch.object(serve.Handler, 'log_request', lambda *a, **k: None):
            srv = serve.Server(('127.0.0.1', 0), serve.Handler, None)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                c = http.client.HTTPConnection('127.0.0.1', srv.server_address[1], timeout=60)
                c.request('GET', '/sw.js')
                r = c.getresponse()
                body = r.read()
                c.close()
            finally:
                srv.shutdown()
                srv.server_close()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader('Cache-Control'), 'no-cache')
        self.assertEqual(body, self.mobile.worker())

    def test_activate_sweeps_nothing_that_was_kept(self):
        """The owner's promise: an update keeps what the phone kept.  Only the
        app's own pages and its way in are dropped, and only by prefix."""
        activate = self.event('activate')
        swept = activate.split('keys.filter(')[1].split('.map(k => caches.delete(k))')[0]
        self.assertEqual(re.findall(r"startsWith\('([^']+)'\)", swept), ['parseh-app-', 'parseh-shell-'])
        for kept in ('KEPT', 'SHARED', 'JOBS', 'parseh-kept', 'parseh-shared', 'parseh-jobs'):
            self.assertNotIn(kept, swept, kept)
        self.assertIn("const KEPT = 'parseh-kept-';", self.sw)
        self.assertIn("const SHARED = 'parseh-shared';", self.sw)

    def test_a_new_worker_says_so_and_a_page_says_it_once(self):
        install, activate = self.event('install'), self.event('activate')
        # the one moment "an update, or a first install?" can be asked
        self.assertIn('const replacing = !!self.registration.active;', install)
        self.assertLess(install.index('const replacing'), install.index('e.waitUntil('))
        self.assertIn('noteRelease(replacing)', install)
        # told to the pages it has just claimed, after claiming them
        self.assertLess(activate.index('self.clients.claim()'), activate.index('announce()'))
        self.assertIn("if (said.version && said.replaced) await tellClients({updated: said});", self.sw)
        # and asked by a page opened later
        self.assertIn('if (msg.release) e.waitUntil(releaseSays().then(r => reply({release: r})));', self.sw)
        keep = self.keep
        self.assertIn("var RELEASE_SEEN = 'parseh_release';", keep)
        self.assertIn("if (d.updated) released(d.updated, true);", keep)
        self.assertIn("if (d.release) released(d.release, false);", keep)
        self.assertIn("navigator.serviceWorker.addEventListener('controllerchange', askRelease);", keep)
        self.assertIn("'Parseh was updated to ' + r.version", keep)
        # a downgrade is not passed off as an update
        self.assertIn("'Parseh went back to ' + r.version", keep)
        # and a first install is not an update
        self.assertIn('if (!seen && !r.replaced) return;', keep)
        # THE PAGE ASKS FOR THE NEW WORKER ITSELF -- the browser's own check
        # never came in the driving -- once the computer is found, on the
        # first page of each opening of the app and then at most once in ten
        # minutes, never on every page
        self.assertIn('if (!away) releaseCheck();', keep)
        self.assertIn("var releaseAsked = false, RELEASE_ASKED = 'parseh_release_asked', "
                      "RELEASE_EVERY = 10 * 60;", keep)
        self.assertIn('opened = !sessionStorage.getItem(RELEASE_ASKED);', keep)
        self.assertIn("return r && r.update ? r.update() : null;", keep)
        # NEVER A SILENT RELOAD: the worker never sends a page anywhere, and
        # what the page does on hearing of a release is a line and nothing
        # else (the ↻ a person presses is the one reload keep.js has)
        self.assertNotIn('location.reload', self.sw)
        self.assertNotIn('.navigate(', self.sw)
        told = keep.split('/* ---- Parseh was updated')[1].split('  function start_() {')[0]
        self.assertNotIn('reload', told)
        self.assertNotIn('location', told)

    def test_the_keep_check_tells_an_update_from_damage(self):
        # the digest a file was kept with is written on the kept copy, by each
        # of the three ways a copy is put: keep, a background keep, and renew
        self.assertIn("const KEPT_DIGEST = 'X-Parseh-Kept-Digest';", self.sw)
        self.assertIn('await to.put(req, stamped(res, digests[url]));', self.sw)
        self.assertIn(".put(new Request(url), stamped(res, ((head.want || {})[url] || {}).digest));", self.sw)
        self.assertIn('await c.put(new Request(url), fresh(res, body, sum));', self.sw)
        # the page hands the worker what the computer said, with every keep
        self.assertEqual(self.keep.count('digests: digestsOf(rec)'), 2)
        decks = (ROOT / 'markdown' / 'app' / 'static' / 'decks.js').read_text(encoding='utf-8')
        self.assertIn('digests: digests || {}', decks)
        # the three verdicts
        check = self.sw.split('async function check(job, reply)')[1].split('\n}\n')[0]
        self.assertIn('if (sound && seen.sum && kept !== seen.sum) {', check)
        self.assertIn('await from.put(req, stamped(res, seen.sum, seen.body));', check)
        self.assertIn('} else if (!sound && seen.sum && kept && seen.sum === kept && kept !== now) {', check)
        self.assertIn('whole: here && sound, updated: here && updated', check)
        # updated is whole, is counted to be said, and is never fetched again
        self.assertIn('if (x.here && x.whole && x.updated) updated++;', self.keep)
        self.assertIn('if (x.here && !x.whole) { broken[x.url] = true; torn.push(x.url); }', self.keep)
        self.assertIn('were updated on the computer since they were kept', self.keep)

    def test_renew_mends_every_copy_not_the_first_found(self):
        """/lib/'s scripts are in the way in AND in the shared cache, and a
        renew that stopped at the first left the other the old release's."""
        renew = self.sw.split('function renew(request) {')[1].split('\n}\n')[0]
        self.assertIn("if (!k.startsWith(KEPT) && k !== SHARED && k !== SHELL && k !== APP) continue;", renew)
        self.assertNotIn('return;\n    }\n  }).catch', renew, 'no holder ends the walk')
        loop = renew.split('for (const k of keys) {')[1]
        self.assertNotIn('      return;', loop, 'every holder is written, none returns early')

    def test_the_page_compares_versions_by_lib_version_rules(self):
        """The line says which way it went, and it must agree with the one
        written rule (lib/version.py) about which way that is."""
        deno = shutil.which('deno')
        if not deno:
            self.skipTest('deno is not on the PATH')
        import version
        body = self.keep.split('function vkey(v) {')[1].split('  function released(')[0]
        pairs = [('a0.3.2', 'a0.3.10'), ('a0.3.10', 'a0.3.9'), ('a1.0', 'a1.0.0'), ('b0.1', 'a0.9'),
                 ('a0.9', 'b0.1'), ('1.0', 'b9.9'), ('a0.3.2', 'a0.3.2'), ('a0.2.0', 'a0.3.0')]
        js = ('function vkey(v) {' + body +
              'console.log(JSON.stringify(%s.map(([a, b]) => older(a, b))));' % json_str(pairs))
        out = subprocess.run([deno, 'eval', js], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        import json
        self.assertEqual(json.loads(out.stdout), [version.compare(a, b) < 0 for a, b in pairs])


def json_str(value):
    import json
    return json.dumps(value)


class CertificateTests(unittest.TestCase):
    """serve.py's certificate: an authority of the machine's own, which a
    phone is told to trust once, and the server's, signed by it."""

    def setUp(self):
        import serve
        self.serve = serve
        self.td = tempfile.TemporaryDirectory()
        self.dir = self.td.name
        self.patch = patch.object(serve, 'TLS_DIR', self.dir)
        self.patch.start()
        self.quiet = patch('builtins.print')
        self.quiet.start()

    def tearDown(self):
        self.quiet.stop()
        self.patch.stop()
        self.td.cleanup()

    def f(self, name):
        return os.path.join(self.dir, name)

    def text(self, name):
        return subprocess.run(['openssl', 'x509', '-in', self.f(name), '-noout', '-text'],
                              capture_output=True, text=True, check=True).stdout

    def test_an_authority_and_a_certificate_it_signed(self):
        cert, key = self.serve.make_cert()
        self.assertEqual((cert, key), (self.f('cert.pem'), self.f('key.pem')))
        for name in ('ca.pem', 'ca-key.pem', 'cert.pem', 'key.pem'):
            self.assertTrue(os.path.isfile(self.f(name)), name)
        for private in ('ca-key.pem', 'key.pem'):
            self.assertEqual(os.stat(self.f(private)).st_mode & 0o777, 0o600, private)
        # nothing of the making is left behind
        self.assertEqual(sorted(os.listdir(self.dir)), ['ca-key.pem', 'ca.pem', 'cert.pem', 'key.pem', 'names.txt'])
        # the chain the server sends: its own, then the authority
        pems = Path(cert).read_text().count('-----BEGIN CERTIFICATE-----')
        self.assertEqual(pems, 2)
        r = subprocess.run(['openssl', 'verify', '-CAfile', self.f('ca.pem'), cert],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        leaf = self.text('cert.pem')
        self.assertIn('CA:FALSE', leaf)
        self.assertIn('TLS Web Server Authentication', leaf)
        self.assertIn('DNS:localhost', leaf)
        self.assertIn('IP Address:127.0.0.1', leaf)
        # no longer than an iPhone accepts
        r = subprocess.run(['openssl', 'x509', '-in', cert, '-noout', '-checkend', str(826 * 86400)],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, 'it ends within 826 days')

    def test_the_authority_can_vouch_for_this_machine_only(self):
        self.serve.make_cert()
        ca = self.text('ca.pem')
        self.assertIn('CA:TRUE, pathlen:0', ca)
        self.assertIn('X509v3 Name Constraints: critical', ca)
        for permitted in ('DNS:localhost', 'DNS:local', 'DNS:ts.net', 'IP:192.168.0.0/255.255.0.0',
                          'IP:10.0.0.0/255.0.0.0', 'IP:172.16.0.0/255.240.0.0', 'IP:100.64.0.0/255.192.0.0',
                          'IP:127.0.0.0/255.0.0.0'):
            self.assertIn(permitted, ca)
        # and the server's certificate names nothing outside them
        self.assertFalse(self.serve._ip_permitted('8.8.8.8'))
        self.assertTrue(self.serve._ip_permitted('100.86.243.109'))
        self.assertTrue(self.serve._ip_permitted('192.168.1.20'))
        with patch.object(self.serve, 'cert_names', lambda: (['localhost', 'box', 'box.example.com'],
                                                             ['127.0.0.1', '192.168.1.20', '8.8.8.8'])):
            self.serve.make_cert(force=True)
        leaf = self.text('cert.pem')
        self.assertIn('IP Address:192.168.1.20', leaf)
        self.assertNotIn('8.8.8.8', leaf)
        self.assertNotIn('box.example.com', leaf)

    def test_kept_renewed_near_its_end_and_made_again_when_asked(self):
        self.serve.make_cert()
        ca, first = Path(self.f('ca.pem')).read_text(), Path(self.f('cert.pem')).read_text()
        self.serve.make_cert()
        self.assertEqual(Path(self.f('cert.pem')).read_text(), first, 'kept')
        with patch.object(self.serve, 'TLS_RENEW', 900 * 86400):
            self.serve.make_cert()
        second = Path(self.f('cert.pem')).read_text()
        self.assertNotEqual(second, first, 'near its end: made again')
        self.serve.make_cert(force=True)
        self.assertNotEqual(Path(self.f('cert.pem')).read_text(), second, 'asked: made again')
        self.assertEqual(Path(self.f('ca.pem')).read_text(), ca, 'the authority a phone trusts, never')

    def test_an_old_certificate_of_parsehs_own_is_replaced_once(self):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-days', '3650', '-nodes',
                        '-keyout', self.f('key.pem'), '-out', self.f('cert.pem'),
                        '-subj', '/CN=box/O=Parseh'], capture_output=True, check=True)
        self.assertTrue(self.serve._made_here(self.f('cert.pem')))
        self.serve.make_cert()
        self.assertTrue(os.path.isfile(self.f('ca.pem')))
        r = subprocess.run(['openssl', 'verify', '-CAfile', self.f('ca.pem'), self.f('cert.pem')],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_certificate_put_there_by_hand_is_left_alone(self):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-days', '90', '-nodes',
                        '-keyout', self.f('key.pem'), '-out', self.f('cert.pem'),
                        '-subj', '/CN=box.tail1234.ts.net'], capture_output=True, check=True)
        own = Path(self.f('cert.pem')).read_bytes()
        self.assertFalse(self.serve._made_here(self.f('cert.pem')))
        self.serve.make_cert()
        self.assertEqual(Path(self.f('cert.pem')).read_bytes(), own)
        self.assertEqual(sorted(os.listdir(self.dir)), ['cert.pem', 'key.pem'])
        self.assertIsNone(self.serve.authority_der())

    def test_the_server_speaks_it_and_hands_over_the_authority_alone(self):
        import http.client
        import ssl
        import threading
        serve = self.serve
        cert, key = serve.make_cert()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        with patch.object(serve.Handler, 'log_request', lambda *a, **k: None):
            srv = serve.Server(('127.0.0.1', 0), serve.Handler, ctx)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                # a client that trusts the authority and nothing else
                trust = ssl.create_default_context(cafile=self.f('ca.pem'))
                c = http.client.HTTPSConnection('localhost', srv.server_address[1], context=trust, timeout=30)
                c.request('GET', '/m/install/parseh-ca.crt')
                r = c.getresponse()
                body = r.read()
                self.assertEqual(r.status, 200)
                self.assertEqual(r.getheader('Content-Type'), 'application/x-x509-ca-cert')
                self.assertEqual(body, serve.authority_der())
                self.assertEqual(body, ssl.PEM_cert_to_DER_cert(Path(self.f('ca.pem')).read_text()))
                self.assertNotIn(b'PRIVATE KEY', body)
                c.request('GET', '/m/install/')
                r = c.getresponse()
                page = r.read().decode('utf-8')
                self.assertIn('href="/m/install/parseh-ca.crt"', page)
                c.close()
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == '__main__':
    unittest.main()
