// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — a link to the guide from every door (TO-DO §15.10).

   The hub, the clip tray, Review later, /lookup/ and the Settings doors wrote a
   "guide" button into their bars by hand; the reader, the player, the shelves,
   the add pages, the studio, the decks and the Anki page had none.  This puts
   one there, on the page's OWN page of the guide (PAGES below), so that the
   question "how does this page work?" is one press away wherever it is asked.

   WHY A SCRIPT AND NOT A LINE IN EACH PAGE.  Two of those pages are written once
   and kept: a book's reader (lib/tex2html.py) and the book library
   (lib/make_index.py) are files on disk, and a line added to their templates
   would reach nobody's books until each was built again.  Every page of the
   toolbox loads lib/parseh.js, which loads this from beside it; the studio's
   templates, which do not load parseh.js, carry a tag of their own, as they do
   for lib/explain.js.

   WHERE IT GOES.  Into every bar the page wears that has no guide link yet --
   both layouts, the one not drawn included, so a switch of mode finds it there
   -- just before the theme button ◐ (before Stop in the studio's bars, which
   end on ◐ and ⚙ as a pair; at the end of a bar that has neither), and
   dressed as that bar's own buttons are.  A bar that already links the guide
   is left alone, and its address is the one the others get: the Settings
   pages' phone bars learn theirs from the browser bar.  The hub is left alone:
   it has the guide on both layouts already (a door of its own on the phone).
   A PHONE'S BAR HAS NO ROOM FOR IT.  The mobile layout's bar (.m-bar, the
   studio's .m-topbar) is one line of targets a finger finds -- home, Browser |
   Mobile, ◐, ? -- and a sixth wrapped it onto two.  So on the phone's layout
   the guide is a line at the foot of the page instead ("The guide to this
   page", drawn only in that layout where the page has the other one too) --
   and so it is on every layout of the studio library and the decks, whose
   browser bar is a row of menus laid out to fit 700 px with nothing to spare --, and
   in the gear's sheet, beside Parseh's settings, on every page that has a gear
   (lib/pagesettings.js asks ParsehGuide.href()): that is where a phone's
   reader and player, which keep one line of header for a thumb, have it.

   The guide is the one this Parseh serves, /guide/ (lib/guidebuild.py): it
   is the guide of the version running, and it opens with no network. */
(function () {
  'use strict';
  if (window.ParsehGuide) return;

  var SITE = '/guide/site/';
  // the page's address -> its page of the guide; the first that matches wins
  var PAGES = [
    [/^\/books\/add\/?/, 'books/adding.html'],
    [/^\/books\/[^/]+\/[^/]+\/reader\//, 'books/reader.html'],
    [/^\/books\/?(index\.html)?$/, 'books/library.html'],
    [/^\/youtube\/add\/?/, 'videos/adding-a-video.html'],
    [/^\/youtube\/v\//, 'videos/the-player.html'],
    [/^\/youtube\/?/, 'videos/finding-a-video.html'],
    [/^\/m\//, 'getting-started/mobile-mode.html'],
    [/^\/studio\/prompt/, 'studio/llm-prompt.html'],
    [/^\/studio\/(new|doc\/[^/]+\/edit)/, 'studio/editor.html'],
    [/^\/studio\/doc\//, 'studio/document-page.html'],
    [/^\/studio\/note\//, 'studio/notes.html'],
    [/^\/studio\/?/, 'studio/library.html'],
    [/^\/exercises\/deck\/[^/]+\/[^/]+\/study/, 'exercises/studying.html'],
    [/^\/exercises\/deck\/[^/]+\/[^/]+\/cram/, 'exercises/cram.html'],
    [/^\/exercises\/deck\//, 'exercises/deck-page.html'],
    [/^\/exercises\/?/, 'exercises/decks-page.html'],
    [/^\/anki\//, 'cards-and-anki/card-store.html'],
    [/^\/clips\//, 'cards-and-anki/clip-tray.html']
  ];
  var BARS = '.parseh-bar, header.topbar, header.m-topbar, body > header';
  var HAS = 'a[href^="/guide"]';
  var TITLE = 'the guide: how this page works';

  function off() {
    var p = location.pathname;
    return location.protocol === 'file:' || p === '/' || p === '/index.html' || /^\/guide(\/|\.pdf|$)/.test(p);
  }
  // a guide link a bar of this page already has: its address is the page's
  function written() {
    var bars = document.querySelectorAll(BARS);
    for (var i = 0; i < bars.length; i++) {
      var a = bars[i].querySelector(HAS);
      if (a) return a.getAttribute('href');
    }
    return null;
  }
  function href() {
    var w = written();
    if (w) return w;
    var p = location.pathname;
    for (var i = 0; i < PAGES.length; i++) if (PAGES[i][0].test(p)) return SITE + PAGES[i][1];
    return '/guide/';
  }

  var CSS = [
    'a.px-guide{text-decoration:none;white-space:nowrap}',
    'a.px-guide:not(.parseh-btn):not(.btn){font:inherit;font-size:13px;line-height:20px;padding:5px 9px;',
    '  border:1px solid var(--rule,var(--chrome-line,#ddd));border-radius:6px;',
    '  background:var(--bg,var(--chrome-panel,transparent));color:var(--ink,var(--chrome-fg,#222))}',
    'a.px-guide:not(.parseh-btn):not(.btn):hover{border-color:var(--accent,#be3455);color:var(--accent,#be3455)}',
    // the phone's line at the foot of the page: a target a finger finds
    '.px-guide-end{margin:28px 16px 20px;text-align:center;font-size:15px}',
    '.px-guide-end a{display:inline-flex;align-items:center;min-height:48px;padding:0 12px;',
    '  color:var(--accent,#be3455)}',
    '.pg-foot a.px-guide-foot{margin-inline-start:18px}'
  ].join('\n');
  function style() {
    if (document.getElementById('px-guide-style')) return;
    var s = document.createElement('style');
    s.id = 'px-guide-style';
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  function phone(bar) { return bar.classList.contains('m-bar') || bar.classList.contains('m-topbar'); }
  // the studio library's bar and the decks' (a0.6.2, tests/studio_home_bar.mjs): a row of menus and Stop laid out
  // to fit 700 px, with no ◐ -- a sixth thing pushes it past the window's side
  function full(bar) {
    return bar.classList.contains('topbar') && !!bar.querySelector('.topbar-actions') &&
           !bar.querySelector('[data-parseh-theme]');
  }
  function place(bar, to) {
    if (bar.querySelector(HAS)) return;
    // the bar's own header row, for the reader's and the player's header
    var theme = bar.querySelector('[data-parseh-theme], #theme, .m-theme');
    var stop = bar.querySelector('#btn-stop, [data-parseh-stop]');
    var a = document.createElement('a');
    a.href = to;
    a.textContent = 'guide';
    a.title = TITLE;
    a.className = 'px-guide';
    if (bar.classList.contains('parseh-bar')) a.className += ' parseh-btn';
    else if (bar.classList.contains('topbar')) a.className += ' btn ghost';
    // the studio's bars end on ◐ and ⚙ as a pair (static/gear.js): there it goes before Stop
    var at = bar.classList.contains('topbar') ? (stop || theme) : (theme || stop);
    if (at) at.parentNode.insertBefore(a, at);
    else (bar.querySelector('.topbar-actions') || bar).appendChild(a);
  }

  function run() {
    if (off()) return;
    style();
    var to = href();
    var bars = document.querySelectorAll(BARS), want = false, other = false, always = false;
    for (var i = 0; i < bars.length; i++) {
      var b = bars[i], has = !!b.querySelector(HAS);
      if (phone(b)) { if (!has) want = true; }
      else if (full(b)) { if (!has) want = always = true; }
      else { other = true; place(b, to); }
    }
    if (!want || document.querySelector('.px-guide-end')) return;
    var p = document.createElement('p');
    p.className = 'px-guide-end';
    if (other && !always) p.setAttribute('data-layout', 'mobile');
    var a = document.createElement('a');
    a.href = to;
    a.textContent = 'The guide to this page';
    a.title = TITLE;
    p.appendChild(a);
    (document.querySelector('main') || document.body).appendChild(p);
  }

  window.ParsehGuide = {href: function () { return off() ? null : href(); }, run: run};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
