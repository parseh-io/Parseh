// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the little shared script: the theme, the language preference,
   the browser or mobile mode, a toast, the clipboard, the stop button.
   Served at /lib/parseh.js; loaded early in <head> so the theme (and the
   mode) is on the page before it paints.

   Theme: ONE preference for the whole toolbox, `parseh_theme` in
   localStorage, applied as data-theme on <html>.  The button cycles the
   three palettes -- light, dark, and the sepia paper the studio's reading
   sheet has always had.  'auto' is a fourth value, but not a step in the
   cycle: it is the state before anything has been picked, when no
   attribute is set and the stylesheet follows the system.  The button then
   shows whichever palette the system resolved to, so the first click always
   changes something.  The older per-tool keys (bk_theme, yt_theme) are read
   once as a migration and never written again. */

/* THE PAGE ZOOM COMES FIRST OF ALL (lib/pagezoom.js, a0.5.0).  A zoom
   replaces what the page's own scripts ask the window about -- a rect, its
   size, where a click was -- so it has to be in place BEFORE the first of
   them runs, and a reader is a page built before zoom existed, with its
   scripts written into it: they cannot be told to wait.  This file is the one
   thing every page of the toolbox loads ahead of its own scripts, so the zoom
   is loaded from here; and the way to have a script run before the next one
   in the parser's hands is to write its tag where the parser is: the parser
   stops at it, fetches it, runs it, and goes on.  (A script put on the page
   with createElement, the way the layers below are, runs when it arrives,
   after the page's own.)  The address is taken from this script's own, as
   theirs are.
   document.write is right only while the parser is on this very script -- in
   a script that is run later it would wipe the page -- so it is used only
   where this one was put by the parser, in the head of a page still being
   read, and anywhere else the file is added as the layers below are, and the
   zoom is applied when it arrives.  Off the disk nothing is loaded: there the
   browser's own zoom is. */
(function () {
  if (window.ParsehZoom || location.protocol === 'file:') return;
  var me = document.currentScript;
  var src = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, 'pagezoom.js') : '/lib/pagezoom.js';
  if (me && src === me.src) return;
  function add() {
    if (window.ParsehZoom) return;
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
  }
  if (me && me.async === false && !me.defer && document.readyState === 'loading') {
    document.write('<script src="' + src.replace(/&/g, '&amp;').replace(/"/g, '&quot;') + '"><\/script>');
    // a browser that would not take the written tag still gets the file, late
    document.addEventListener('DOMContentLoaded', add);
  } else add();
})();

(function () {
  'use strict';

  /* THE PAGE ARRIVES ALREADY KNOWING THE COMPUTER IS AWAY (the owner's rule
     of 2026-09-23): "if the page knows the machine is offline when you click
     a thing, the page you arrive at should already know it is offline and
     act accordingly.  A book, a notebook, a deck of exercises does not
     change from offline to online mid-use."

     lib/mobile.py writes the same few lines (AWAY_BOOT) into the head of
     every page the server composes, before any script of that page's own.
     The two pages it does NOT compose are the two he named first: a BOOK'S
     READER, built by lib/tex2html.py, and a VIDEO'S PAGE -- and both of them
     load this file, in the head, ahead of everything else they run.  So it
     is set here too, for them.  Doing it twice costs one attribute write.

     It must be here at the very top and not in `appHead` below: appHead runs
     after the document is parsed, by which time a reader has already fired
     the lookup it makes on sight, and the whole point is to be earlier than
     that.  lib/keep.js reads this mark when it starts rather than assuming
     the computer is there, and may turn it ON later; it may not turn it off
     while the page is open once its own question has confirmed it.

     NOT ON A REFRESH (the owner's fall-back, 2026-09-24): "if we refresh the
     page, then it is forced to check again if the computer is online -- so
     upon refreshing, do not assume still offline."  A reload of any kind --
     F5, the browser's button, a finger pulling the page down, ↻ -- is
     reported as "reload", already here in the head; the older
     performance.navigation says the same where the newer entry is not there
     yet.  The memory is left as it is, and the mark says `assumed`: what the
     page before found, not what this one has. */
  try {
    var seen = JSON.parse(localStorage.getItem('parseh_away') || 'null');
    var nav = performance.getEntriesByType ? performance.getEntriesByType('navigation')[0] : null;
    var afresh = nav ? nav.type === 'reload' : !!(performance.navigation && performance.navigation.type === 1);
    if (!afresh && seen && seen.away === true && typeof seen.at === 'number' &&
        Date.now() / 1000 - seen.at <= (typeof seen.trusted === 'number' ? seen.trusted : 180))
      document.documentElement.setAttribute('data-parseh-away', 'assumed');
  } catch (e) {}

  /* AND AN ASK THAT CANNOT HANG, for the pages this file is the only shared
     script on -- a book's reader and a video's page.  Both of them ask the
     computer the moment they open (is there a dictionary?) and again at every
     tap on a word, with a bare `fetch`; and a bare fetch towards a computer
     on the far side of a tunnel that has gone never settles, because that
     socket is not refused, it is swallowed.  lib/sw.js cannot help: it
     answers GETs alone.  So a reader carried into a tunnel showed "looking
     it up…" in the cloud for ever, and one opened there never grew its
     dictionary button at all.

     NOT A TIMEOUT, A WATCH.  A dictionary on a big book can honestly take a
     while, and cutting it off after three seconds would break the feature to
     fix the phone.  So the ask is left alone and waits for the page's one
     question -- is the computer there? -- which lib/activity.js asks for the
     whole page.  A computer that is slow goes on being waited for, however
     long it takes: slow is online (TO-DO §2.24).  A computer the question
     finds GONE ends the ask at once with `away` set, which is what the
     callers show a sentence about instead of a spinner.  It used to ask that
     question itself, beside every ask, and read three seconds without an
     answer as "gone" -- which on a slow tunnel made the asks, and the
     probes beside them, pile up until a healthy computer looked absent. */
  // on a page already offline an ask is given as long as the worker takes to
  // answer from a kept copy (lib/sw.js, DEADLINE), and no longer
  var KEPT_ONLY = 3000;
  function awayNow() { return document.documentElement.hasAttribute('data-parseh-away'); }
  // an away this page has CONFIRMED -- the one that refuses a write -- as
  // against one it only assumed from the page before
  function awaySure() {
    if (document.documentElement.getAttribute('data-parseh-away') === 'confirmed') return true;
    var A = window.ParsehActivity;
    return !!(A && A.reach && A.reach().state === 'away');
  }
  function ask(url, init) {
    init = init || {};
    var writes = (init.method || 'GET').toUpperCase() !== 'GET';
    if (writes && awaySure() && !init.evenAway) {
      var shut = new Error('Parseh’s computer cannot be reached, and this needs it');
      shut.away = true;
      return Promise.reject(shut);
    }
    return new Promise(function (yes, no) {
      var settled = false, short = null;
      function end() {
        settled = true;
        clearTimeout(short);
        document.removeEventListener('parseh:reach', heard);
      }
      function gone() {
        if (settled) return;
        end();
        var out = new Error('the computer does not answer');
        out.away = true;
        no(out);
      }
      function heard(e) { if (e.detail && e.detail.state === 'away') gone(); }
      fetch(url, init).then(function (r) { if (!settled) { end(); yes(r); } },
                            function (e) { if (!settled) { end(); e.away = true; no(e); } });
      document.addEventListener('parseh:reach', heard);
      if (awaySure()) short = setTimeout(gone, KEPT_ONLY);
    });
  }

  var KEY = 'parseh_theme';
  var ORDER = ['light', 'dark', 'sepia'];
  var GLYPH = { light: '○', dark: '●', sepia: '◐' };

  function get() {
    var t = null;
    try { t = localStorage.getItem(KEY); } catch (e) {}
    if (t !== 'auto' && ORDER.indexOf(t) < 0) {
      t = 'auto';
      try {
        var old = localStorage.getItem('yt_theme') || localStorage.getItem('bk_theme');
        if (old === 'light' || old === 'dark') t = old;
      } catch (e) {}
    }
    return t;
  }
  function systemDark() {
    return !!(window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);
  }
  /* the palette actually on screen: 'auto' resolves to whichever of light
     and dark the stylesheet's media query picked */
  function resolved() {
    var t = get();
    return t === 'auto' ? (systemDark() ? 'dark' : 'light') : t;
  }
  function apply() {
    var t = get(), now = resolved();
    if (t === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', t);
    var next = ORDER[(ORDER.indexOf(now) + 1) % ORDER.length];
    var btns = document.querySelectorAll('[data-parseh-theme]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].textContent = GLYPH[now];
      btns[i].title = 'theme: ' + now +
        (t === 'auto' ? ' (following the system)' : '') + ' — click for ' + next;
    }
  }
  function set(t) {
    try { localStorage.setItem(KEY, t); } catch (e) {}
    apply();
  }
  function cycle() { set(ORDER[(ORDER.indexOf(resolved()) + 1) % ORDER.length]); }
  /* sepia is a light paper: only 'dark' is night */
  function isDark() { return resolved() === 'dark'; }

  /* ---- the mode: browser or mobile ----
     ONE switch for the whole toolbox, set from the hub's top bar.  In the
     browser mode every page is what it has always been, editing and all.
     The mobile mode is a second set of pages made to be READ on a phone --
     streamlined, and without a single editing control on them.  It is NOT
     the phone adjustments the pages already make (the bar that hides on a
     scroll, the layouts under 560px): those follow the width of the screen
     and go on doing so in either mode.  This follows a choice.

     Stored as `parseh_mode` in localStorage, 'browser' or 'mobile', where
     nothing stored means browser; and mirrored in a cookie of the same name,
     because the server and the studio's and the exercises' pages (which do
     not load this script) have to be able to read it too.  When storage
     holds nothing -- blocked, or never written on this origin -- the cookie
     answers.  It is put on <html> as data-mode as soon as this script is
     parsed, as the theme is, so a page's stylesheet has switched layouts
     before the first paint.

     A page that HAS a mobile version is listed in MOBILE_PAGES, and
     route(url) says where a link to url leads in the mode the toolbox is
     in: to the mobile version when there is one and the mode is mobile,
     and to url itself otherwise.  The browser page is always the fallback,
     so a page nobody has written a mobile version of yet simply opens as it
     is.  On a page that is itself a mobile page (<body data-mobile-page>)
     every link is routed that way.  Nothing is refused, in either mode: a
     browser page reached by its address works as it always has.  The design
     and the way to add a mobile page are in docs/mobile.md. */
  var MODE_KEY = 'parseh_mode';
  var MODES = ['browser', 'mobile'];
  /* {match: a RegExp over the whole path, to: its mobile path}; `to` is
     handed to String.replace, so it may say $1 for a part of the match (or
     be a function), and the query and the fragment are carried over */
  var MOBILE_PAGES = [
    // the hub is its own mobile version: the one page carries both layouts
    { match: /^\/(index\.html)?$/, to: '/' },
    // the book library is a static page (make_index.py): its mobile version is
    // a page of its own, written by the server on every request (lib/mobile.py)
    { match: /^\/books\/(index\.html)?$/, to: '/m/books/' },
    // a book's reader is its own mobile version: every reader, however old,
    // gets the mobile layer from this script (the loader at the end of this
    // file), so nothing has to be built again
    { match: /^(\/books\/(?:[^\/]+\/){1,2}reader\/)(index\.html)?$/, to: '$1' },
    // the exercise decks, a deck, studying it and cramming it: each page
    // carries both layouts (markdown/app/templates, static/mobile.css)
    { match: /^\/exercises\/(.*)$/, to: '/exercises/$1' },
    // the videos: the index and a channel are pages of their own on a phone
    // (lib/mobile.py), since the browser's carry what adds and deletes one;
    // a video's own page is the same page, with the layer this script loads
    { match: /^\/youtube\/(index\.html)?$/, to: '/m/videos/' },
    { match: /^\/youtube\/c\/([^\/]+)\/?$/, to: '/m/videos/$1/' },
    { match: /^(\/youtube\/v\/[^\/]+\/)(index\.html)?$/, to: '$1' },
    // the studio's library and its documents carry both layouts too
    // (markdown/app/templates, static/mobile.css); what writes one is not
    // drawn in the mobile layout
    { match: /^\/studio\/(doc\/[^\/]+\/?)?$/, to: '/studio/$1' },
    // the licences, which carry both layouts in one column (lib/notices.py)
    { match: /^\/licences\/$/, to: '/licences/' },
    // the chunks flagged to review later, both layouts in one column
    // (lib/laterpage.py)
    { match: /^\/later\/$/, to: '/later/' },
    // what is kept on this phone: a page of the app's own (§19.2)
    { match: /^\/m\/kept\/$/, to: '/m/kept/' }
  ];
  function modeCookie() {
    var m = null;
    try { m = /(?:^|;\s*)parseh_mode=(browser|mobile)(?:;|$)/.exec(document.cookie || ''); }
    catch (e) {}
    return m ? m[1] : null;
  }
  function modeGet() {
    var m = null;
    try { m = localStorage.getItem(MODE_KEY); } catch (e) {}
    if (MODES.indexOf(m) < 0) m = modeCookie();
    return m === 'mobile' ? 'mobile' : 'browser';
  }
  function isMobile() { return modeGet() === 'mobile'; }
  function modeCookieSet(m) {
    // a year, for the whole site; Lax, because it only ever travels with
    // the toolbox's own pages; not Secure, since serve.py can speak plain
    // http (--http, or a Windows machine without OpenSSL)
    try { document.cookie = MODE_KEY + '=' + m + '; Path=/; SameSite=Lax; Max-Age=31536000'; }
    catch (e) {}
  }
  var modeFns = [], modeShown = null;
  function modeApply() {
    var m = modeGet();
    document.documentElement.setAttribute('data-mode', m);
    // the server's copy follows whatever this page found, so the two never
    // disagree for longer than one page load
    if (modeCookie() !== m) modeCookieSet(m);
    var btns = document.querySelectorAll('[data-parseh-mode]');
    for (var i = 0; i < btns.length; i++)
      btns[i].setAttribute('aria-pressed',
                           btns[i].getAttribute('data-parseh-mode') === m ? 'true' : 'false');
    if (m !== 'mobile') unrouteLinks();
    // the switch may just have put a sideways chip row on the screen
    langReveal(false);
    var was = modeShown;
    modeShown = m;
    if (was !== null && was !== m) {
      for (var j = 0; j < modeFns.length; j++) { try { modeFns[j](m); } catch (e) {} }
      // A PAGE THAT IS ONLY A MOBILE VERSION (/m/books/) has nothing of its
      // own to show in the browser mode: switched there, here or in another
      // tab, it goes to the page it is the mobile version of, which its body
      // names in data-browser-page.  Only on a switch and never at load --
      // an address opened in the browser mode opens as it is -- and never the
      // other way round: a browser page may hold somebody's unsaved work.
      var back = m === 'browser' && document.body &&
                 document.body.getAttribute('data-browser-page');
      if (back) location.replace(back);
    }
  }
  function modeSet(m) {
    if (MODES.indexOf(m) < 0) return;
    try { localStorage.setItem(MODE_KEY, m); } catch (e) {}
    modeCookieSet(m);
    modeApply();
  }
  /* fn(mode) after every change of the mode on this page: a click here, or
     a switch made in another tab (the storage event); gives back a function
     that takes fn off again */
  function modeOnChange(fn) {
    modeFns.push(fn);
    return function () { var k = modeFns.indexOf(fn); if (k >= 0) modeFns.splice(k, 1); };
  }
  function modeRoute(url) {
    if (modeGet() !== 'mobile' || !/^https?:$/.test(location.protocol)) return url;
    var u;
    try { u = new URL(url, location.href); } catch (e) { return url; }
    if (u.origin !== location.origin) return url;
    for (var i = 0; i < MOBILE_PAGES.length; i++) {
      var p = MOBILE_PAGES[i];
      if (!p.match.test(u.pathname)) continue;
      return u.pathname.replace(p.match, p.to) + u.search + u.hash;
    }
    return url;
  }
  /* A link on a mobile page, followed in the mobile mode, goes where
     route() says.  The href itself is rewritten, in the capture phase and
     before the browser acts on the click, instead of the click being
     cancelled and the page moved by hand: that way everything a browser
     does with a link -- ctrl- or cmd-click into a new tab, shift-click into
     a window, a middle click, a long press's "open in new tab", a
     target=_blank -- it does with the mobile address, and none of it has to
     be imitated here.  The address the page was written with is kept in
     data-parseh-href and put back when the mode goes back to browser.  A
     link that must open the browser page whatever the mode says so with
     data-no-route; a download is never routed. */
  function routeLink(e) {
    if (!document.body || !document.body.hasAttribute('data-mobile-page')) return;
    if (modeGet() !== 'mobile') return;
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a || a.hasAttribute('download') || a.hasAttribute('data-no-route')) return;
    var own = a.getAttribute('data-parseh-href') || a.getAttribute('href');
    if (!own || own.charAt(0) === '#') return;
    var to = modeRoute(own);
    if (to === own) return;
    a.setAttribute('data-parseh-href', own);
    a.setAttribute('href', to);
  }
  function unrouteLinks() {
    var as = document.querySelectorAll('a[data-parseh-href]');
    for (var i = 0; i < as.length; i++) {
      as[i].setAttribute('href', as[i].getAttribute('data-parseh-href'));
      as[i].removeAttribute('data-parseh-href');
    }
  }
  document.addEventListener('click', routeLink, true);
  document.addEventListener('auxclick', routeLink, true);
  document.addEventListener('contextmenu', routeLink, true);
  // a switch made in another tab, and a page brought back from the
  // back-forward cache, which ran none of its script on the way back
  window.addEventListener('storage', function (e) {
    if (e.key === MODE_KEY || e.key === null) modeApply();
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) modeApply(); });
  /* The toggle: any button with data-parseh-mode="browser|mobile".  The
     pressed look comes from <html data-mode> in the stylesheet, so it is
     right from the first paint; aria-pressed is kept for the screen reader.
     The button clicked may belong to the layout the switch just hid: the
     focus then goes to its twin in the layout now on the screen. */
  function modeClick(e) {
    var b = e.target && e.target.closest && e.target.closest('[data-parseh-mode]');
    if (!b) return;
    var m = b.getAttribute('data-parseh-mode'), had = document.activeElement === b;
    modeSet(m);
    if (!had || b.offsetParent) return;
    var twins = document.querySelectorAll('[data-parseh-mode="' + m + '"]');
    for (var i = 0; i < twins.length; i++)
      if (twins[i].offsetParent) { twins[i].focus(); break; }
  }

  /* ---- a toast ---- */
  var toastTimer = null;
  // `ms`, where given, is how long it stays: news nobody asked for -- that
  // Parseh was updated (lib/keep.js) -- is given longer than the answer to a
  // press the person is watching for
  function toast(msg, isErr, ms) {
    var t = document.getElementById('parseh-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'parseh-toast';
      (document.body || document.documentElement).appendChild(t);
    }
    t.textContent = msg;
    t.classList.toggle('err', !!isErr);
    // force a reflow so a toast right after the last one animates again
    void t.offsetWidth;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); },
                            ms || (isErr ? 4200 : 2000));
  }

  /* ---- taking something off the shelf ----
     The studio has had this since it had a library: an x on the card, a
     question, and the document is gone.  A book and a video get the same
     gesture from the same place, because the card is where a person looks
     to manage a library and the reading page is where they look to read --
     a red button in the reader would be a red button under the pointer of
     somebody turning a page.

     One difference, and it is the content's: a note is a page somebody can
     write again, and a reading edition is weeks of glossing with a
     recording beside it that may exist nowhere else.  So this does not
     remove anything.  The server moves the directory to books/.trash/ or
     videos/.trash/ -- a dot directory, so every walker here already skips
     it and the thing is off the shelf the moment it lands -- and says where
     it went.  The question below says so too, because a person about to
     press a red button should be told what it does, not reassured.

     The card carries the address: data-del is what to POST to, data-what is
     what to call it in the question.  Delegated and in the capture phase,
     because the x lives inside the card's own <a> and a click that reached
     it would follow the link instead. */
  function cardDelete(e) {
    var b = e.target && e.target.closest && e.target.closest('[data-del]');
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    var url = b.getAttribute('data-del');
    var what = b.getAttribute('data-what') || 'this';
    var body = b.getAttribute('data-body') || '';
    if (!window.confirm('Take \u201c' + what + '\u201d off the shelf?\n\n'
                        + 'It is moved to the trash beside the others, not '
                        + 'deleted: nothing is lost, and it stops being part '
                        + 'of the library.')) return;
    b.disabled = true;
    fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: body || '{}'
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) throw new Error((j && j.error) || 'it was refused');
      /* j.warn means it was moved but something after it did not run --
         the library page, which is about to reload, is the stale one.  Say
         that instead of the cheerful line, and leave it up longer. */
      if (j.warn) { toast(j.warn, true); return; }
      toast(what + ' \u2192 ' + (j.trash || 'the trash'));
      setTimeout(function () { location.reload(); }, 900);
    }).catch(function (err) {
      b.disabled = false;
      toast((err && err.message) || String(err), true);
    });
  }

  /* ---- building a book from its card ----
     The card's build button -- and a card whose book has no reader yet, which
     is all button -- POSTs data-build, the book's own __build, and the server
     runs ./build.sh as a job (lib/bookbuild.py).  buildBook polls the job,
     says the build's last line as it goes, and calls back when it ends: the
     library page reloads, so the card shows what the reader now says; the
     reader page marks its PDF current.  A book already building answers 409
     with that build, which is polled the same.

       buildBook(url, what, opts)   what: the subject of the page's own
                                    messages ("<what> — building…"): the
                                    card's title, the reader's "the PDF"
         opts.book     the book's name, for the activity list's label
         opts.what     'html' for the reader alone, 'draft' for the PDF of
                       the chapters a book being made has so far, else the PDF
         opts.button, opts.say, opts.done, opts.failed */
  function cardBuild(e) {
    if (e.target && e.target.closest && e.target.closest('[data-del]')) return;
    var b = e.target && e.target.closest && e.target.closest('[data-build]');
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    var name = b.getAttribute('data-what') || '';
    buildBook(b.getAttribute('data-build'), name || 'the book', {
      book: name,
      button: b.tagName === 'BUTTON' ? b : null,
      done: function () { setTimeout(function () { location.reload(); }, 900); }
    });
  }
  /* WHY A BUILD FAILED, in its own words.  The last lines of a failed build
     are whatever TeX printed last -- "Type X to quit or <RETURN> to proceed"
     -- and the line that says what went wrong is higher up: build.sh prints
     TeX's first error under "PDF FAILED", and the Python build does the
     same.  So: that error, after the line naming what failed; the line naming
     it alone where there is no TeX error; and only then the last two. */
  function buildWhy(log) {
    log = (log || []).map(function (l) { return String(l).trim(); }).filter(Boolean);
    var err = log.filter(function (l) { return l.charAt(0) === '!'; })[0];
    var failed = log.filter(function (l) { return /FAILED|could not run|no lualatex/i.test(l); })[0];
    if (err) return (failed ? failed.replace(/\s*--.*$/, '') + ': ' : '') + err;
    return failed || log.slice(-2).join(' / ') || 'the server log says why';
  }
  function buildBook(url, what, opts) {
    opts = opts || {};
    var button = opts.button || null;
    var say = opts.say || toast;
    if (button) button.disabled = true;
    // on the activity list at once (lib/activity.js), before the server's
    // own entry for the build has been asked for; the answer names that
    // entry, and this page's is then the same one, shown once.  Its label
    // names the book as that entry will (serve.py named(): quoted, and
    // isolated for a title in another direction), so nothing moves when the
    // entry takes over.  `what` is no name for it: the reader and the
    // new-book page say "the PDF" and "the reader" in their own messages,
    // and the label was "Building the PDF of the PDF".  A caller that does
    // not pass the book's name -- a reader built before opts.book -- gets
    // the label without one, until the server's entry names it.
    var verb = opts.what === 'html' ? 'Rebuilding the reader'
             : opts.what === 'draft' ? 'Making the PDF of the chapters so far' : 'Building the PDF';
    var act = working(opts.book ? verb + ' of \u201c\u2068' + opts.book + '\u2069\u201d' : verb + '\u2026');
    function fail(err) {
      act.end(false);
      if (button) button.disabled = false;
      say((err && err.message) || String(err), true);
    }
    function poll() {
      fetch(url + '/status', {cache: 'no-store'}).then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.state === 'running') {
            var last = (j.log || []).slice(-1)[0];
            say(what + ' — ' + (last || 'building…'));
            setTimeout(poll, 1500);
            return;
          }
          act.end(j.state === 'done');
          if (button) button.disabled = false;
          if (j.state === 'done') {
            say(what + ': built');
            if (opts.done) opts.done(j);
          } else {
            say(what + ': the build failed — ' + buildWhy(j.log), true);
            if (opts.failed) opts.failed(j);
          }
        }).catch(fail);
    }
    fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({what: opts.what || 'pdf'})})
      .then(function (r) { return r.json().then(function (j) { return {status: r.status, j: j}; }); })
      .then(function (res) {
        if (!res.j.ok && res.status !== 409) throw new Error(res.j.error || 'it was refused');
        act.adopt(res.j.activity);
        say(what + ' — ' + (res.status === 409 ? 'already building…' : 'building…'));
        setTimeout(poll, 1200);
      }).catch(fail);
  }

  /* THIS PAGE'S OWN ENTRY on the activity list (lib/activity.js, loaded
     below), for work started here: shown at once, ended by the caller.
     Where the list is not there -- a page opened off the disk, or before
     the script has arrived -- the work goes on without it, and the handle
     answers every call with nothing. */
  function working(label, opts) {
    var A = window.ParsehActivity;
    if (A) return A.local(label, opts);
    return {job: '', url: function (u) { return u; }, end: function () {},
            progress: function () {}, set: function () {}, adopt: function () {}};
  }

  /* ---- the clipboard ----
     navigator.clipboard needs a secure context, which every page of the
     toolbox now has (https); the execCommand path is only a fallback for
     an old browser. */
  function shorten(s) { return s.length > 48 ? s.slice(0, 48) + '…' : s; }
  function copy(text, raw) {
    text = String(text == null ? '' : text);
    /* A word, a slug, an id -- what this was written for -- are better for
       having their whitespace squeezed.  A shell script and a ~15,000
       character PROMPT.md are destroyed by it: both add pages hand over
       heredoc-bearing sh and fenced Markdown, and every one of them arrived
       as a single unrunnable line.  `raw` asks for the text exactly as it
       stands; every caller that passes nothing keeps the old behaviour, and
       BOTH paths keep the toast and the execCommand fallback below (which
       preserves whitespace natively, and which a private clipboard call in
       the pages would have thrown away). */
    if (!raw) text = text.replace(/\s+/g, ' ').trim();
    if (!text) return Promise.resolve(false);
    var p = (navigator.clipboard && navigator.clipboard.writeText)
      ? navigator.clipboard.writeText(text)
      : Promise.reject(new Error('no clipboard API'));
    return p.then(function () {
      toast('copied: ' + shorten(text));
      return true;
    }).catch(function () {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) { toast('copied: ' + shorten(text)); return true; }
      } catch (e) {}
      toast('clipboard unavailable', true);
      return false;
    });
  }

  /* ---- shift held: the readers show their copy affordance ---- */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Shift') document.body.classList.add('shiftdown');
  });
  document.addEventListener('keyup', function (e) {
    if (!e.shiftKey) document.body.classList.remove('shiftdown');
  });
  window.addEventListener('blur', function () {
    document.body.classList.remove('shiftdown');
  });

  /* ---- stopping the server, from any page ----
     NOT WHILE IT IS WORKING, unless that is what is meant: a build, a
     restore or an upload still running is cut off by the stop, so the
     question names them first -- even where the page has already asked
     its own question (the reader's "really stop?", which passes `silent`),
     because that one was about stopping and this one is about the work.
     Asked of the activity list (/__activity); a server that does not
     answer it gets the plain question. */
  function stillRunning() {
    return fetch('/__activity', {cache: 'no-store'})
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) { return (j && j.running) || []; })
      .catch(function () { return []; });
  }
  function stopQuestion(list) {
    if (!list.length) return 'Stop the Parseh server?';
    var names = list.slice(0, 5).map(function (e) { return '  \u2022 ' + e.label; });
    if (list.length > 5) names.push('  \u2026 and ' + (list.length - 5) + ' more');
    return (list.length === 1 ? '1 task is' : list.length + ' tasks are') +
      ' still running:\n\n' + names.join('\n') + '\n\nStopping the server now cuts ' +
      (list.length === 1 ? 'it' : 'them') + ' off. Stop the Parseh server anyway?';
  }
  function stopServer(opts) {
    opts = opts || {};
    stillRunning().then(function (list) {
      if ((list.length || !opts.silent) && !confirm(stopQuestion(list))) return;
      stopNow(opts);
    });
  }
  function stopNow(opts) {
    if (opts.before) { try { opts.before(); } catch (e) {} }
    fetch('/__shutdown', { method: 'POST' }).catch(function () {}).then(function () {
      document.body.className = '';
      document.body.style.cssText = '';
      document.body.innerHTML =
        '<div style="max-width:640px;margin:22vh auto;text-align:center;' +
        'font:16px/1.6 -apple-system,sans-serif;color:var(--dim)">' +
        '<p style="font-size:19px;color:var(--ink)">Parseh stopped.</p>' +
        '<p>Start it again on the computer it runs on, the way you started it ' +
        'before (<b>Parseh.command</b> on a Mac, <b>serve.bat</b> on Windows), ' +
        'and reload this page.</p></div>';
    });
  }

  /* ---- text size and margins ----
     The studio has sliders for its sheet; this is the same idea for the
     readers, as one panel both can open: each caller names its fields
     (label, range, default, the CSS custom property it drives) and the
     localStorage key its values live under.  Applying a value is setting
     the property on <html>, so the stylesheet does the rest. */
  function typo(opts) {
    var key = opts.key, fields = opts.fields || [], btn = opts.button;
    var root = document.documentElement;
    function defaults() {
      var d = {};
      fields.forEach(function (f) { d[f.name] = f.def; });
      return d;
    }
    function load() {
      var d = defaults();
      try {
        var s = JSON.parse(localStorage.getItem(key) || '{}');
        fields.forEach(function (f) {
          var v = s[f.name];
          if (typeof v === 'number' && isFinite(v))
            d[f.name] = Math.min(f.max, Math.max(f.min, v));
        });
      } catch (e) {}
      return d;
    }
    var vals = load();
    function save() {
      // Preserve language-specific fields when another language saves its panel.
      var saved = {};
      try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) {}
      try { localStorage.setItem(key, JSON.stringify(Object.assign({}, saved, vals))); }
      catch (e) {}
    }
    function fmt(f, v) {
      if (f.unit === 'px') return (Math.round(v * 10) / 10) + 'px';
      return (Math.round(v * 100) / 100) + (f.unit || '');
    }
    function apply() {
      fields.forEach(function (f) {
        if (!f.prop) return;
        var v = vals[f.name];
        root.style.setProperty(f.prop, f.cssUnit ? v + f.cssUnit : (f.unit === 'px' ? v + 'px' : String(v)));
      });
      if (opts.onChange) { try { opts.onChange(vals); } catch (e) {} }
    }
    apply();
    var api = {
      get: function () { return vals; },
      set: function (name, v) {
        var field = fields.find(function (f) { return f.name === name; });
        if (!field || typeof v !== 'number' || !isFinite(v)) return;
        vals[name] = Math.min(field.max, Math.max(field.min, v));
        save(); apply(); if (btn) refresh();
      },
      reset: function () { vals = defaults(); save(); apply(); if (btn) refresh(); }
    };
    // THE GEAR (lib/pagesettings.js) draws these same sliders in its own panel
    // under "Text": it builds them from the very field list this panel was
    // made from, and writes through set(), so the values and the key they
    // live under (bk_typo, yt_typo) stay exactly as they were.  `typo.last` is
    // the instance of the page -- a page makes one.
    api.fields = fields;
    typo.last = api;
    if (!btn) return api;

    var panel = document.createElement('div');
    panel.className = 'parseh-typo';
    panel.hidden = true;
    panel.setAttribute('dir', 'ltr');
    var h = '<div class="thead">text &amp; margins<span class="sp"></span>' +
            '<button type="button" class="tclose" title="close (Esc)">\u2715</button></div>';
    fields.forEach(function (f) {
      h += '<div class="trow"><label for="st-' + f.name + '">' + f.label + '</label>' +
           '<input type="range" id="st-' + f.name + '" data-f="' + f.name + '" min="' + f.min +
           '" max="' + f.max + '" step="' + f.step + '"><output data-o="' + f.name + '"></output></div>';
    });
    h += '<div class="tfoot"><span class="hint">remembered in this browser</span>' +
         '<span class="sp"></span><button type="button" class="treset">reset</button></div>';
    panel.innerHTML = h;
    document.body.appendChild(panel);
    function refresh() {
      fields.forEach(function (f) {
        panel.querySelector('[data-f="' + f.name + '"]').value = vals[f.name];
        panel.querySelector('[data-o="' + f.name + '"]').textContent = fmt(f, vals[f.name]);
      });
    }
    panel.addEventListener('input', function (e) {
      var name = e.target.getAttribute('data-f');
      if (!name) return;
      vals[name] = parseFloat(e.target.value);
      save(); apply(); refresh();
    });
    panel.querySelector('.treset').addEventListener('click', api.reset);
    // opens under the button that asked (the header's Aa, or another a page
    // gives it: open(anchor)), and stays on the screen -- a panel opened low in
    // a phone held sideways ran off its foot
    var at = null;
    function place() {
      var r = (at || btn).getBoundingClientRect();
      var vw = document.documentElement.clientWidth || window.innerWidth;
      var vh = document.documentElement.clientHeight || window.innerHeight;
      panel.style.top = Math.max(8, Math.min(r.bottom + 6, vh - panel.offsetHeight - 8)) + 'px';
      panel.style.left = Math.max(8, Math.min(r.left, vw - panel.offsetWidth - 8)) + 'px';
    }
    var told = [];
    function said() {
      var up = !panel.hidden;
      told.forEach(function (fn) { try { fn(up, at); } catch (e) {} });
    }
    function open(anchor) {
      if (at && at !== btn) at.classList.remove('on');
      at = anchor || btn;
      refresh(); panel.hidden = false; place();
      at.classList.add('on');
      btn.classList.toggle('on', at === btn);
      said();
    }
    function close() {
      if (panel.hidden) return;
      panel.hidden = true;
      if (at) at.classList.remove('on');
      btn.classList.remove('on');
      said();
      at = null;
    }
    function toggle(anchor) {
      if (!panel.hidden && (!anchor || anchor === at)) close(); else open(anchor);
    }
    api.open = open; api.close = close; api.toggle = toggle;
    api.isOpen = function () { return !panel.hidden; };
    api.onToggle = function (fn) { told.push(fn); };
    panel.querySelector('.tclose').addEventListener('click', close);
    btn.addEventListener('click', function () { toggle(); });
    document.addEventListener('click', function (e) {
      if (panel.hidden || panel.contains(e.target) || btn.contains(e.target) ||
          (at && at.contains(e.target))) return;
      close();
    });
    // ONE ESCAPE, ONE LAYER.  The key that closes this panel is spent on it:
    // marked used, so a panel or sheet under it that honours defaultPrevented
    // -- the player's LLM panel, which has no backdrop to keep the Aa button
    // out of reach, and the reader's contents -- stays open instead of
    // closing in the same keypress (and the LLM panel playing the video it
    // had paused)
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) { e.preventDefault(); close(); }
    });
    window.addEventListener('resize', function () { if (!panel.hidden) place(); });
    refresh();
    return api;
  }

  // CJK controls share defaults and units between the two readers.
  function readingFields(lang) {
    var fields = [];
    if (lang === 'ja' || lang === 'zh') fields.push({name: 'cjkSpace',
      label: 'character spacing', min: -0.1, max: 1.5, step: 0.025, unit: 'em',
      cssUnit: 'em', def: 0, prop: '--cjk-space'});
    if (lang === 'ja') fields.push(
      {name: 'kanaContrast', label: 'reading contrast', min: -60, max: 100,
       step: 1, unit: '%', cssUnit: '%', def: 0, prop: '--kana-contrast'},
      {name: 'kanaSize', label: 'reading / kanji size', min: 10, max: 310,
       step: 5, unit: '%', cssUnit: '%', def: 50, prop: '--kana-size'});
    return fields;
  }
  function baseText(el) {
    var copy = el.cloneNode(true);
    copy.querySelectorAll('rt, rp').forEach(function (rt) { rt.remove(); });
    return copy.textContent;
  }
  function kanjiOf(text) {
    return Array.from(new Set(Array.from(text).filter(function (c) {
      return /\p{Script=Han}/u.test(c);
    })));
  }
  function kanaFold(s) {
    return s.normalize('NFC').replace(/[\u30a1-\u30f6]/g, function (c) {
      return String.fromCharCode(c.charCodeAt(0) - 0x60);
    });
  }
  // Kana in the spelling anchors the reading. Only accept a unique split;
  // compounds and irregular readings remain a single ruby, never guessed.
  function readingParts(text, kana) {
    var tokens = text.match(/\p{Script=Han}+[々〆ヶ]?|[\p{Script=Hiragana}\p{Script=Katakana}ー]+|[^\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}ー]+/gu) || [];
    var folded = kanaFold(kana), answers = [], visits = 0;
    function walk(i, at, parts) {
      if (++visits > 4000 || answers.length > 1) return;
      if (i === tokens.length) {
        if (at === kana.length) answers.push(parts);
        return;
      }
      var token = tokens[i];
      if (!kanjiOf(token).length) {
        var fixed = kanaFold(token);
        if (folded.slice(at, at + fixed.length) === fixed)
          walk(i + 1, at + fixed.length, parts.concat({text: token, kana: ''}));
        else if (/^[\p{P}\p{Z}\s]+$/u.test(token))
          walk(i + 1, at, parts.concat({text: token, kana: ''}));
      } else {
        for (var end = at + 1; end <= kana.length; end++)
          walk(i + 1, end, parts.concat({text: token, kana: kana.slice(at, end)}));
      }
    }
    walk(0, 0, []);
    if (!kanjiOf(text).length) return [{text: text, kana: ''}];
    return visits <= 4000 && answers.length === 1 ? answers[0] : [{text: text, kana: kana}];
  }
  /* A chunk with a word line (lib/wordline.js) is known a WORD at a time:
     its token is its identity, so 山(やま) and 山(さん) are two words and a
     word said twice is one.  Those go in a second store beside the kanji
     one, parseh_known_word:<scope>.  A word also counts as known when every
     kanji of it is already marked, so nothing a person marked a kanji at a
     time is lost -- and nothing is migrated: the kanji store goes on
     working exactly as it did for every chunk that has no words. */
  function wordline() { return window.ParsehWordline; }
  function readings(opts) {
    var key = 'parseh_known_kanji:' + opts.scope, known = new Set();
    var wordKey = 'parseh_known_word:' + opts.scope, knownWords = null, rows = [];
    function load() {
      try {
        var saved = JSON.parse(localStorage.getItem(key) || '[]');
        known = new Set(Array.isArray(saved) ? saved.filter(function (s) {
          return typeof s === 'string' && kanjiOf(s).length === 1 && Array.from(s).length === 1;
        }) : []);
      } catch (_) { known = new Set(); }
      knownWords = null;
    }
    load();
    // read on first use, not at load: parseh.js is in <head> and
    // wordline.js may not be on the page yet
    function words() {
      if (knownWords) return knownWords;
      var W = wordline(), saved;
      if (!W) return new Set();
      try { saved = JSON.parse(localStorage.getItem(wordKey) || '[]'); } catch (_) { saved = []; }
      knownWords = new Set();
      (Array.isArray(saved) ? saved : []).forEach(function (s) {
        if (typeof s !== 'string') return;
        try {
          var p = W.parse(s);
          if (p.length === 1) knownWords.add(W.key(p[0][0], p[0][1]));
        } catch (_) {}
      });
      return knownWords;
    }
    function byKanji(surface) {
      var chars = kanjiOf(surface);
      return chars.length > 0 && chars.every(function (c) { return known.has(c); });
    }
    function wordKnown(token, surface) { return words().has(token) || byKanji(surface); }
    var surfaces = Object.create(null);
    function surfaceOf(token) {
      if (!(token in surfaces)) {
        try { surfaces[token] = wordline().parse(token)[0][0]; } catch (_) { surfaces[token] = ''; }
      }
      return surfaces[token];
    }
    function apply() {
      document.querySelectorAll(opts.selector + ' ruby').forEach(function (ruby) {
        if (ruby.closest('.wd[data-w]')) return;
        var chars = kanjiOf(baseText(ruby));
        ruby.classList.toggle('reading-known', chars.length > 0 && chars.every(function (c) {
          return known.has(c);
        }));
      });
      document.querySelectorAll(opts.selector + ' .wd[data-w]').forEach(function (wd) {
        var on = wordKnown(wd.dataset.w, surfaceOf(wd.dataset.w));
        wd.querySelectorAll('ruby').forEach(function (ruby) {
          ruby.classList.toggle('reading-known', on);
        });
      });
      document.querySelectorAll('[data-known-kanji]').forEach(function (button) {
        var c = button.dataset.knownKanji, on = known.has(c);
        button.textContent = c + (on ? ': show reading' : ': I know this');
        button.setAttribute('aria-pressed', String(on));
      });
      // a row leaves the list once it has been on the page and is gone from
      // it (a cloud redrawn); one built before it is placed stays, labelled
      rows = rows.filter(function (r) {
        r.seen = r.seen || r.row.isConnected;
        return !r.seen || r.row.isConnected;
      });
      rows.forEach(function (r) {
        r.row.querySelectorAll('[data-known-word]').forEach(function (button) {
          var t = button.dataset.knownWord, s = surfaceOf(t);
          var on = wordKnown(t, s), kanjiOnly = on && !words().has(t);
          button.textContent = s + (on ? ': show reading' : ': I know this');
          button.setAttribute('aria-pressed', String(on));
          button.title = kanjiOnly
            ? 'Hidden because every kanji of it is marked known in this ' + opts.kind
            : 'Remember for every appearance in this ' + opts.kind;
        });
      });
    }
    function render(into, text, kana) {
      into.textContent = '';
      readingParts(text, kana).forEach(function (p) {
        if (!p.kana) { into.appendChild(document.createTextNode(p.text)); return; }
        var ruby = document.createElement('ruby');
        ruby.textContent = p.text;
        var rt = document.createElement('rt'); rt.textContent = p.kana;
        ruby.appendChild(rt); into.appendChild(ruby);
        var chars = kanjiOf(p.text);
        ruby.classList.toggle('reading-known', chars.length > 0 && chars.every(function (c) {
          return known.has(c);
        }));
      });
    }
    function controls(into, text) {
      var chars = kanjiOf(text);
      if (!chars.length) return;
      var row = document.createElement('div'); row.className = 'reading-controls';
      chars.forEach(function (c) {
        var b = document.createElement('button'); b.type = 'button';
        b.dataset.knownKanji = c;
        b.title = 'Remember for every appearance in this ' + opts.kind;
        b.onclick = function (e) {
          e.preventDefault(); e.stopPropagation();
          if (known.has(c)) known.delete(c); else known.add(c);
          try { localStorage.setItem(key, JSON.stringify(Array.from(known))); }
          catch (_) { toast('This browser could not save the reading preference.', true); }
          apply();
        };
        row.appendChild(b);
      });
      var hint = document.createElement('small');
      hint.textContent = 'For this ' + opts.kind + '. Shared compound readings hide when all their kanji are known.';
      row.appendChild(hint); into.insertBefore(row, into.querySelector('.mkrow')); apply();
    }
    /* A chunk drawn from its word line: one .wd per word, its reading over
       it, the whitespace of the text kept between.  A line that does not
       parse, or does not rejoin into the text, draws the text plain and says
       so with .words-bad -- a reader never loses the sentence to bad data. */
    function renderWords(into, fa, line) {
      into.textContent = '';
      into.classList.remove('words-bad');
      var W = wordline(), pairs, spans, keys;
      // 山(( parses, as 山( with no reading, and has no token: a word with
      // no identity to be known by falls back with the rest
      try {
        pairs = W.parse(line); spans = W.align(fa, pairs);
        keys = pairs.map(function (p) { return W.key(p[0], p[1]); });
      } catch (_) {
        into.textContent = fa;
        into.classList.add('words-bad');
        return false;
      }
      spans.forEach(function (sp) {
        if (sp[2] === null) { into.appendChild(document.createTextNode(sp[0])); return; }
        var p = pairs[sp[2]], wd = document.createElement('span');
        wd.className = 'wd';
        wd.dataset.w = keys[sp[2]];
        wd.dataset.k = String(sp[2]);
        if (sp[1]) {
          var ruby = document.createElement('ruby');
          ruby.textContent = sp[0];
          var rt = document.createElement('rt'); rt.textContent = sp[1];
          ruby.appendChild(rt); wd.appendChild(ruby);
          ruby.classList.toggle('reading-known', wordKnown(wd.dataset.w, p[0]));
        } else wd.textContent = sp[0];
        into.appendChild(wd);
      });
      return true;
    }
    function wordControls(into, line) {
      var W = wordline(), pairs, keys, seen = Object.create(null);
      try {
        pairs = W.parse(line);
        keys = pairs.map(function (p) { return W.key(p[0], p[1]); });
      } catch (_) { return null; }
      var row = document.createElement('div'); row.className = 'reading-controls word-controls';
      pairs.forEach(function (p, k) {
        if (!p[1]) return;
        var t = keys[k];
        if (seen[t]) return;
        seen[t] = true;
        var b = document.createElement('button'); b.type = 'button';
        b.dataset.knownWord = t;
        b.onclick = function (e) {
          e.preventDefault(); e.stopPropagation();
          var store = words(), hidden = byKanji(p[0]), had = store.has(t);
          if (had) store.delete(t); else if (!hidden) store.add(t);
          if (had || !hidden) {
            try { localStorage.setItem(wordKey, JSON.stringify(Array.from(store))); }
            catch (_) { toast('This browser could not save the reading preference.', true); }
          }
          // a word hidden by its kanji is not shown from here: that would
          // unmark a kanji every other word written with it shares
          if (hidden) toast('Every kanji of ' + p[0] + ' is marked known in this ' + opts.kind +
                            ': unmark one of them to show its reading.', true);
          apply();
        };
        row.appendChild(b);
      });
      if (!row.children.length) return null;
      var hint = document.createElement('small');
      hint.textContent = 'For this ' + opts.kind + '. A word marked here hides its reading wherever it appears.';
      row.appendChild(hint); into.insertBefore(row, into.querySelector('.mkrow'));
      rows.push({row: row, seen: false}); apply();
      return row;
    }
    window.addEventListener('storage', function (e) {
      if (e.key === key || e.key === wordKey || e.key === null) { load(); apply(); }
    });
    return {render: render, controls: controls, apply: apply,
            renderWords: renderWords, wordControls: wordControls};
  }

  /* ---- the word strip ----
     The editor of a chunk's word line, for both readers' sheets: one chip
     per word, its text on top and its reading in a box underneath.  ⊕
     joins two words, ✂ cuts one where it is pointed at, and ← → on a word's
     text move where that word begins.  Under the chips is a textarea that
     always holds the line: the chips rewrite it, typing in it redraws the
     chips whenever it parses, and it is what the page sends -- as in the
     divide sheets, no offset crosses the wire.  Everything here counts code
     points, never UTF-16 units.

       Parseh.wordstrip({lang, fa, value, reading, reorders, door, propose, onchange})
         -> {el, value(), set(line), destroy()}

     `lang` is the registry record the page embeds; `reading` the chunk's own
     kana or tr, which check() only compares with the words; `propose` an
     async () => line or ''.  onchange(line, result) runs on every change a
     person makes, with check()'s {errors, warnings}; set() is the caller's
     own and runs none.  The caller places `el`. */
  // Python's str.isspace, the set lib/wordline.js splits words on
  var SPACES = /[\t-\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/g;
  function wordstrip(opts) {
    var lang = opts.lang || {}, fa = String(opts.fa || ''), dir = lang.dir || 'ltr';
    var chips = [], proposed = null, stale = false, tokenErr = null, gone = false;
    var el = document.createElement('div');
    el.className = 'wordstrip';
    if (lang.code) el.setAttribute('data-lang', lang.code);
    el.innerHTML = '<div class="ws-chips"></div>' +
      '<div class="ws-bar"><button type="button" class="ws-propose">propose</button>' +
      '<button type="button" class="ws-hand">divide by hand</button>' +
      '<span class="ws-say"></span><span class="ws-sp"></span>' +
      '<button type="button" class="ws-astext" aria-expanded="false">edit as text</button></div>' +
      '<textarea class="ws-text" rows="2" spellcheck="false" hidden></textarea>' +
      '<div class="ws-note" aria-live="polite" hidden></div>';
    function $(sel) { return el.querySelector(sel); }
    var row = $('.ws-chips'), box = $('.ws-text'), note = $('.ws-note'), say = $('.ws-say');
    row.setAttribute('dir', dir); box.setAttribute('dir', dir);
    if (lang.code) box.lang = lang.code;
    $('.ws-propose').hidden = !opts.propose;

    function tell(msg, isErr) { say.textContent = msg; say.classList.toggle('err', !!isErr); }
    function fit(input) {
      var n = Array.from(input.value || input.placeholder).length;
      input.size = Math.max(4, n * (lang.reading ? 2 : 1) + 1);
    }
    function draw(focus) {
      row.textContent = '';
      chips.forEach(function (c, i) {
        if (i) {
          var j = document.createElement('button');
          j.type = 'button'; j.className = 'ws-join'; j.textContent = '⊕';
          j.title = 'join ' + chips[i - 1].s + ' and ' + c.s + ' into one word';
          j.onclick = function () { join(i - 1); };
          row.appendChild(j);
        }
        var chip = document.createElement('span'); chip.className = 'ws-chip';
        var surf = document.createElement('span'); surf.className = 'ws-surf';
        surf.tabIndex = 0;
        if (lang.code) surf.lang = lang.code;
        surf.title = '← → move where this word begins';
        // the ✂ is drawn by the stylesheet, so the chip's text is the word
        Array.from(c.s).forEach(function (ch, k) {
          if (k) {
            var cut = document.createElement('button');
            cut.type = 'button'; cut.className = 'ws-cut'; cut.tabIndex = -1;
            cut.title = 'cut the word here';
            cut.onclick = function () { cutAt(i, k); };
            surf.appendChild(cut);
          }
          surf.appendChild(document.createTextNode(ch));
        });
        surf.onkeydown = function (e) { nudge(e, i); };
        var input = document.createElement('input');
        input.className = 'ws-read'; input.value = c.r;
        input.placeholder = lang.reading_label || lang.translit_label || '';
        input.setAttribute('aria-label', 'the reading of ' + c.s);
        if (lang.reading && lang.code) input.lang = lang.code;
        fit(input);
        input.oninput = function () { chips[i].r = input.value; fit(input); fromChips(); };
        chip.appendChild(surf); chip.appendChild(input);
        row.appendChild(chip);
      });
      if (!focus) return;
      var at = row.querySelectorAll('.ws-chip')[focus[0]];
      var f = at && at.querySelector(focus[1]);
      if (f) {
        f.focus();
        if (f.setSelectionRange) f.setSelectionRange(f.value.length, f.value.length);
      }
    }
    // the chips rewrite the line; a word that cannot be written (a reading
    // that begins with '(') goes in as typed, and its refusal leads the note
    function fromChips() {
      var bad = null, W = wordline();
      box.value = chips.map(function (c) {
        try { return W.token(c.s, c.r); }
        catch (e) { bad = bad || e; return c.s + (c.r ? '(' + c.r + ')' : ''); }
      }).join(' ');
      tokenErr = bad; stale = false;
      changed();
    }
    function parsed(line) {
      try {
        chips = wordline().parse(line).map(function (p) { return {s: p[0], r: p[1]}; });
        stale = false;
      } catch (_) { stale = true; }
      tokenErr = null;
      if (!stale) draw();
    }
    function fromText() { parsed(box.value); changed(); }
    function paint() {
      var W = wordline(), line = box.value, empty = !!W && !line.trim();
      // no checker on the page is not a clean line
      var res = W ? W.check(fa, line, lang, opts.reading || '', !!opts.reorders, opts.door || 'book')
                  : {errors: [{code: 'no_wordline', message: 'lib/wordline.js is not on this page, so these words can be neither read nor checked'}], warnings: []};
      if (tokenErr) res.errors.unshift({code: tokenErr.code || 'token', message: tokenErr.message});
      row.classList.toggle('ws-stale', stale);
      $('.ws-hand').hidden = !empty || !fa.replace(SPACES, '');
      note.textContent = '';
      function add(cls, text) {
        var d = document.createElement('div'); d.className = cls; d.textContent = text;
        note.appendChild(d);
      }
      if (empty) add('ws-empty', 'This chunk has no words yet.');
      else {
        res.errors.forEach(function (e) { add('ws-err', e.message); });
        res.warnings.forEach(function (w) { add('ws-warn', w.message); });
      }
      note.hidden = !note.childNodes.length;
      return res;
    }
    function changed() {
      var res = paint();
      if (opts.onchange) opts.onchange(box.value, res);
    }

    function cutAt(i, k) {
      var chars = Array.from(chips[i].s);
      if (k < 1 || k >= chars.length) return;
      chips.splice(i, 1, {s: chars.slice(0, k).join(''), r: chips[i].r},
                         {s: chars.slice(k).join(''), r: ''});
      draw([i + 1, '.ws-read']); fromChips();
    }
    function join(i) {
      var a = chips[i], b = chips[i + 1];
      chips.splice(i, 2, {s: a.s + b.s, r: a.r + b.r});
      draw([i, '.ws-read']); fromChips();
    }
    // the word's first boundary, a character at a time: ← takes one from the
    // word before, → gives one back, and neither ever leaves a word empty
    function nudge(e, i) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault(); e.stopPropagation();
      if (i === 0) return;
      var take = (e.key === 'ArrowLeft') === (dir !== 'rtl');
      var before = Array.from(chips[i - 1].s), mine = Array.from(chips[i].s);
      if (take) { if (before.length < 2) return; mine.unshift(before.pop()); }
      else { if (mine.length < 2) return; before.push(mine.shift()); }
      chips[i - 1].s = before.join(''); chips[i].s = mine.join('');
      draw([i, '.ws-surf']); fromChips();
    }

    $('.ws-propose').onclick = function () {
      var b = this, line = box.value;
      // what is written and was not the last proposal is somebody's work
      if (line.trim() && line !== proposed &&
          !window.confirm('Replace these words with a proposal? What is written here now is lost.')) return;
      b.disabled = true; tell('proposing…');
      Promise.resolve().then(function () { return opts.propose(); }).then(function (got) {
        b.disabled = false;
        if (gone) return;
        if (!got) { tell('nothing was proposed for this chunk: divide it by hand'); return; }
        tell('');
        proposed = box.value = String(got);
        fromText();
      }, function (err) {
        b.disabled = false;
        if (!gone) tell((err && err.message) || String(err), true);
      });
    };
    $('.ws-hand').onclick = function () {
      var whole = fa.replace(SPACES, '');
      if (!whole) return;
      chips = [{s: whole, r: ''}];
      draw([0, '.ws-surf']); fromChips();
    };
    $('.ws-astext').onclick = function () {
      box.hidden = !box.hidden;
      this.setAttribute('aria-expanded', String(!box.hidden));
      this.classList.toggle('on', !box.hidden);
      if (!box.hidden) box.focus();
    };
    box.addEventListener('input', fromText);

    function set(line) {
      box.value = line == null ? '' : String(line);
      chips = [];
      parsed(box.value);
      if (stale) draw();
      paint();
    }
    set(opts.value);
    return {
      el: el,
      value: function () { return box.value; },
      set: set,
      destroy: function () { gone = true; el.remove(); }
    };
  }

  function escapeHTML(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
    });
  }
  // Keep offsets into the original spelling while matching folded words,
  // including vocalised Arabic/Persian and case-folded Latin text.
  function pairMarkup(pair, result, lang, gloss) {
    var marks = lang.strip ? new RegExp('[' + lang.strip + ']', 'g') : null;
    function fold(s) {
      s = String(s || '').normalize('NFC').replace(/[\u0130\u0131]/g, 'i').toLowerCase();
      return marks ? s.replace(marks, '') : s;
    }
    var text = pair.src || '', flat = '', offsets = [], endOffsets = [];
    var at = 0;
    Array.from(text).forEach(function (c) {
      var f = fold(c);
      for (var n = 0; n < f.length; n++) { offsets.push(at); endOffsets.push(at + c.length); }
      if (!f && endOffsets.length) endOffsets[endOffsets.length - 1] = at + c.length;
      flat += f; at += c.length;
    });
    var matched = (pair.matched || []).map(fold).filter(Boolean), ranges = [];
    matched.forEach(function (word) {
      var pos = 0, hit;
      while ((hit = flat.indexOf(word, pos)) !== -1) {
        var end = hit + word.length;
        var left = Array.from(flat.slice(0, hit)).pop() || '';
        var right = Array.from(flat.slice(end))[0] || '';
        if (lang.word_sep === '' || (!/[\p{L}\p{N}]/u.test(left) && !/[\p{L}\p{N}]/u.test(right)))
          ranges.push([offsets[hit], endOffsets[end - 1]]);
        pos = end;
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    ranges.forEach(function (r) {
      var last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push(r);
    });
    var source = '', cursor = 0;
    merged.forEach(function (r) {
      source += escapeHTML(text.slice(cursor, r[0])) + '<mark class="pair-match">' +
        escapeHTML(text.slice(r[0], r[1])) + '</mark>'; cursor = r[1];
    });
    source += escapeHTML(text.slice(cursor));
    var target = escapeHTML(pair.dst);
    if (window.ParsehMT) {
      var words = (result.words || []).filter(function (w) {
        return matched.indexOf(fold(w.word)) >= 0 || (w.hits || []).some(function (h) {
          return matched.indexOf(fold(h.headword)) >= 0;
        });
      });
      // Align each matched word independently so separate equivalents can
      // both be coloured. No model call and no change to the human translation.
      var spans = words.map(function (w) {
        return ParsehMT.align(pair.dst, '', [w], gloss.code);
      }).filter(Boolean);
      if (spans.length) {
        var hot = new Set();
        spans.forEach(function (span) {
          var index = 0;
          ParsehMT.marked(pair.dst, span).forEach(function (p) {
            if (p.here) {
              var first = p.text.search(/[\p{L}\p{N}]/u);
              var last = p.text.replace(/[^\p{L}\p{N}\p{M}]+$/u, '').length;
              if (first >= 0) for (var i = index + first; i < index + last; i++) hot.add(i);
            }
            index += p.text.length;
          });
        });
        target = ''; var start = 0, active = hot.has(0);
        for (var i = 1; i <= pair.dst.length; i++) {
          if (i === pair.dst.length || hot.has(i) !== active) {
            var chunk = escapeHTML(pair.dst.slice(start, i));
            target += active ? '<mark class="pair-match">' + chunk + '</mark>' : chunk;
            start = i; active = hot.has(i);
          }
        }
      }
    }
    return {src: source, dst: target};
  }

  /* ---- the language ----
     ONE preference for the whole toolbox, `parseh_lang` in localStorage:
     'all', or a registry code ('fa', 'ja', ...).  The index pages (the
     hub, /books/, /youtube/, the studio's library) render a chip row --
     languages.chips_html, class .parseh-langs, one .chip per language with
     data-pick -- and this marks the picked chip .on.  A row that carries
     data-lang-filter="<selector>" also filters: every element matching the
     selector inside <main> (or <body> when the page has no <main>) whose
     data-lang is not the picked language is hidden, and a heading (h1-h6
     or .lang-head) with data-lang whose group has nothing left visible is
     hidden with it.  The hub's row has no filter: there the chips only
     record the preference the other pages then open with -- and rewrite the
     counts on its doors, each of which carries its per-language numbers in
     data-counts.  <html> gets data-parseh-lang so a page's own stylesheet
     can react. */
  var LANG_KEY = 'parseh_lang';
  function langGet() {
    var v = null;
    try { v = localStorage.getItem(LANG_KEY); } catch (e) {}
    if (!v || !/^[a-z][a-z0-9_-]{0,15}$/i.test(v)) v = 'all';
    return v;
  }
  function isHeading(el) {
    return /^H[1-6]$/.test(el.tagName) || el.classList.contains('lang-head');
  }
  function langApply(smooth) {
    var pick = langGet();
    var rows = document.querySelectorAll('.parseh-langs');
    // A stored code no chip on this page offers -- a language since taken
    // out of the registry, or a value another tool wrote -- would hide every
    // card and heading and mark no chip, an empty page with nothing to
    // click.  Such a preference is stale: read it as 'all', and write that
    // back so the pages that wire the row themselves (the studio's library)
    // open on the same footing.
    if (rows.length && pick !== 'all' &&
        !document.querySelector('.parseh-langs .chip[data-pick="' + pick + '"]')) {
      pick = 'all';
      try { localStorage.setItem(LANG_KEY, pick); } catch (e) {}
    }
    document.documentElement.dataset.parsehLang = pick;
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r];
      var chips = row.querySelectorAll('.chip');
      for (var c = 0; c < chips.length; c++)
        chips[c].classList.toggle('on', chips[c].getAttribute('data-pick') === pick);
      var sel = row.getAttribute('data-lang-filter');
      if (!sel) continue;
      var scope = document.querySelector('main') || document.body;
      var els;
      try { els = scope.querySelectorAll(sel); } catch (e) { continue; }
      var heads = [];
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        // the row and its chips carry lang/data-lang of their own: never those
        if (el === row || row.contains(el) || el.closest('.parseh-langs')) continue;
        if (isHeading(el)) { heads.push(el); continue; }
        var lang = el.getAttribute('data-lang');
        el.hidden = pick !== 'all' && lang !== pick;
      }
      // a heading stands for the cards after it, up to the next heading:
      // with none of them visible it goes too
      for (var h = 0; h < heads.length; h++) {
        var head = heads[h], any = false, sib = head.nextElementSibling;
        while (sib && !isHeading(sib)) {
          if (!sib.hidden && sib.hasAttribute('data-lang')) { any = true; break; }
          sib = sib.nextElementSibling;
        }
        head.hidden = !any;
      }
    }
    // A count that knows its languages -- the hub's door tags -- carries
    // data-counts, {"all": "12 videos", "fa": "3 videos", ...}: it says the
    // picked language's number, so the one count answers for whichever
    // language is chosen instead of a row of per-language tags beside it.
    var tags = document.querySelectorAll('[data-counts]');
    for (var t = 0; t < tags.length; t++) {
      var tag = tags[t], map = tag.parsehCounts;
      if (map === undefined) {
        try { map = JSON.parse(tag.getAttribute('data-counts')); } catch (e) { map = null; }
        if (!map || typeof map !== 'object') map = null;
        tag.parsehCounts = map;
      }
      if (!map) continue;
      var say = map[pick] !== undefined ? map[pick] : map.all;
      if (say !== undefined) tag.textContent = say;
    }
    langReveal(smooth);
  }
  function langSet(v) {
    try { localStorage.setItem(LANG_KEY, v || 'all'); } catch (e) {}
    langApply(true);
  }
  /* A chip row that scrolls sideways instead of wrapping -- the mobile
     hub's -- always opens at its start, and the picked chip may be well past
     the edge of the screen: the doors' counts would then answer for a
     language nothing in view says is picked.  So such a row is scrolled to
     bring the picked chip to its middle whenever that chip is not wholly in
     view: when the page opens, when a chip is picked, and when the mode
     puts the row on the screen.  The row's own scrollLeft is moved, never
     scrollIntoView, which would scroll the page as well.  A row that wraps,
     or is not drawn, does not scroll, and is left alone.  The row's padding
     is where its edges fade out, so a chip there does not count as in view.
     The arithmetic is on the drawn boxes, so it holds for a right-to-left
     row as well. */
  function langReveal(smooth) {
    var rows = document.querySelectorAll('.parseh-langs');
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i], on = row.querySelector('.chip.on');
      if (!on || row.scrollWidth <= row.clientWidth) continue;
      var r = row.getBoundingClientRect(), c = on.getBoundingClientRect();
      var cs = getComputedStyle(row);
      if (c.left >= r.left + (parseFloat(cs.paddingLeft) || 0) - 0.5 &&
          c.right <= r.right - (parseFloat(cs.paddingRight) || 0) + 0.5) continue;
      var by = (c.left + c.width / 2) - (r.left + r.width / 2);
      // a pick glides there, unless motion is better left out
      if (smooth && row.scrollBy && !(window.matchMedia &&
          matchMedia('(prefers-reduced-motion: reduce)').matches))
        row.scrollBy({ left: by, behavior: 'smooth' });
      else row.scrollLeft += by;
    }
  }

  /* ---- the bar, on a phone ----
     A phone screen is mostly bar: the reader's header wraps into three rows
     and what is left over is too little to read in.  So on a narrow screen
     the bar goes away as soon as the page moves down, and comes back on the
     smallest move up -- not only at the top of the page, which would mean
     scrolling a chapter back to reach one button.

     NOTHING CHANGES ON A WIDE SCREEN.  The listener is wired only while the
     media query matches, and the class it toggles is defined only inside
     the same query in every stylesheet that answers it.

     The class goes on <body> and each page's own sheet says what to do with
     it, because the bars differ: the hub-level `.parseh-bar` is in the flow
     (it is made sticky there first), while the reader's and the player's
     headers are fixed.  Both move by a transform and nothing else -- the
     reader writes its header's height into body's inline padding from a
     ResizeObserver, and the player hangs its video off --headh, so a bar
     that changed height instead would drag the page or the video with it.

     A STRONGER HAND CAN STAND THIS DOWN.  The book reader also lets the bar
     be put away by hand (chrome-off, the same class and the same idea as
     the studio's own bars button); while that holds, the header is already
     away, and this has nothing to add -- worse, if it went on toggling
     `barhidden` regardless, that could come back true however the reader
     last scrolled, and bringing the header back by hand would hand it
     straight off-screen again.  So it simply does not touch `barhidden`
     while chrome-off is set, and the page that sets it clears `barhidden`
     itself when the bar comes back, so that pressing the button is what
     decides, not the scroll.  A page can hold the bar where it is for a
     while the same way, with <body data-bars-held>: the reader's mobile
     layer does while its extra controls are open -- and the dictionary's sheet
     holds it while it is up, with a class of its own (html.m-dsup, below).

     IN THE MOBILE MODE IT FOLLOWS THE SCROLL AT EVERY WIDTH.  A phone held
     sideways is wider than 560px and has the least height of all, and the
     mobile pages' sheet (lib/mobile.css) answers `barhidden` at any width in
     that mode; the browser pages' sheets still answer it only under 560px,
     so a browser page opened in the mobile mode is as it was. */
  var PHONE = '(max-width: 560px)';
  function bars() {
    if (!window.matchMedia || !document.body) return;
    var mq = window.matchMedia(PHONE);
    var lastY = 0, ticking = false, off = false, on = false;
    function set(v) {
      if (v === off) return;
      off = v;
      document.body.classList.toggle('barhidden', v);
    }
    function read() {
      ticking = false;
      var y = window.pageYOffset || document.documentElement.scrollTop || 0;
      if (y < 0) y = 0;                     // the rubber band at either end
      var d = y - lastY;
      if (Math.abs(d) < 4) return;          // a finger resting is not a move
      // where the page is, kept even while the bar is not to move: the
      // first move after is then measured from here, not from before
      lastY = y;
      // (and while the dictionary's sheet is up, html.m-dsup: the page is
      // scrolled to put the word in the room under the header, and a header
      // that came or went with that scroll would change the room)
      if (document.body.classList.contains('chrome-off') ||
          document.body.hasAttribute('data-bars-held') ||
          document.documentElement.classList.contains('m-dsup')) return;
      // near the top the bar always stands; below that, down takes it away
      // and any move up at all brings it back
      set(y > 56 && d > 0);
    }
    function onScroll() {
      if (ticking) return;
      ticking = true;
      if (window.requestAnimationFrame) requestAnimationFrame(read);
      else setTimeout(read, 16);
    }
    function follow() {
      var want = mq.matches || isMobile();
      if (want === on) return;
      on = want;
      if (want) {
        lastY = window.pageYOffset || 0;
        addEventListener('scroll', onScroll, {passive: true});
      } else {
        removeEventListener('scroll', onScroll);
        set(false);                          // back to a desktop: bar stays
      }
    }
    follow();
    if (mq.addEventListener) mq.addEventListener('change', follow);
    else if (mq.addListener) mq.addListener(follow);
    modeOnChange(follow);
  }

  function wire() {
    apply();
    modeApply();
    langApply();
    bars();
    appWire();
    // while nothing has been picked the page follows the system, so a system
    // that flips has to move the button's glyph with it
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var onFlip = function () { if (get() === 'auto') apply(); };
      if (mq.addEventListener) mq.addEventListener('change', onFlip);
      else if (mq.addListener) mq.addListener(onFlip);
    }
    var tb = document.querySelectorAll('[data-parseh-theme]');
    for (var i = 0; i < tb.length; i++) tb[i].addEventListener('click', cycle);
    var sb = document.querySelectorAll('[data-parseh-stop]');
    for (var j = 0; j < sb.length; j++)
      sb[j].addEventListener('click', function () { stopServer(); });
    // delegated, so a row a page renders later (the studio's library draws
    // its cards from JSON) is wired the moment it exists
    document.addEventListener('click', function (e) {
      var chip = e.target && e.target.closest && e.target.closest('.parseh-langs .chip');
      if (!chip) return;
      var pick = chip.getAttribute('data-pick');
      if (pick) langSet(pick);
    });
    document.addEventListener('click', modeClick);
    document.addEventListener('click', cardDelete, true);
    document.addEventListener('click', cardBuild, true);
  }

  /* A SENSE'S LABELS, as the reader of an entry wants them: the book
     reader's definitions and the player's both draw them from here.  The
     dictionary keeps a sense's tags beside it (lookup.py's `marks`,
     wiktextract's own, comma-joined), and most of them are Wiktionary's
     labels -- (transitive), (countable), (slang), (UK).  Three kinds are
     not, and go: the notation lookup writes for what a sense governs
     (`obj:acc`, with its colon); the part of speech the entry already names
     (`pronoun` on a pronoun); and what the FORM is, which a pronoun's or a
     noun's table lends every sense under it -- person, number, case, the
     kind of pronoun -- so that `thee` came out "(archaic, literary,
     objective, second person, singular)" where Wiktionary prints "(archaic,
     literary)".  Hyphens are spaces, as Wiktionary prints them.
     -> an array of labels, [] for none. */
  var FORM_TAGS = Object.create(null);
  ('first-person second-person third-person singular plural dual nominative ' +
   'objective subjective accusative dative genitive personal demonstrative ' +
   'interrogative indefinite definite invariable no-gloss form-of alt-of')
    .split(' ').forEach(function (t) { FORM_TAGS[t] = 1; });
  var POS_TAG = { adj: 'adjective', adv: 'adverb', conj: 'conjunction', det: 'determiner',
                  intj: 'interjection', num: 'numeral', prep: 'preposition',
                  postp: 'postposition', pron: 'pronoun', name: 'proper-noun' };
  function senseLabels(mark, pos) {
    var own = Object.prototype.hasOwnProperty.call(POS_TAG, pos) ? POS_TAG[pos] : (pos || '');
    var seen = Object.create(null);
    return String(mark || '').split(',').map(function (t) { return t.trim(); })
      .filter(function (t) {
        if (!t || t.indexOf(':') >= 0 || FORM_TAGS[t] || t === own || t === pos || seen[t]) return false;
        seen[t] = 1;
        return true;
      })
      .map(function (t) { return t.replace(/-/g, ' '); });
  }

  /* ---- SPOKEN READINGS, as the dictionary panels draw them (lib/spoken.py) ----
     A hit the spoken pass made carries `spoken` {kind, as, why, sound,
     sound_kind, parts, pieces, readings, same}: the word was read as another,
     and says what as and why.  The book's panel, the player's, the phone's
     sheet over either, and the review of a transcript draw it with THIS, so
     that a guess looks the same everywhere and cannot be taken for an entry:
     a tinted row with a dotted edge and a pill, the word as written and the
     word it was read as, the reason in words, the pieces of a composed word,
     any piece that has no formal word named as what it is, and the sound --
     the spoken one where a rule gives it, the formal one labelled as such
     where none does.  A hit with no `spoken` is drawn as it always was, and
     where a word holds more than one reading they are numbered under a
     header that says how many.  The reader draws elements, the player writes
     strings (outerHTML); the styles are put on the page once, from here, in
     the tokens every panel has. */
  var SPOKEN_COUNT = ['', '', 'two', 'three', 'four', 'five', 'six'];
  var SPOKEN_NO_FORMAL = ['emphatic', 'vocative', 'affection', 'affective', 'manner', 'redundant', 'echo', 'repeat',
                          'progressive', 'definite'];
  var spokenStyled = false;
  function spokenStyle() {
    if (spokenStyled || !document.head) return;
    spokenStyled = true;
    var st = document.createElement('style');
    st.setAttribute('data-parseh', 'spoken');
    st.textContent =
      '.dhit.dspk{border-inline-start:2px dotted var(--accent,#8a6d3b);' +
        'background:color-mix(in srgb,var(--accent,#8a6d3b) 8%,transparent);' +
        'padding:2px 6px;border-radius:3px;margin-top:3px}' +
      '.dspill{display:inline-block;font:600 10.5px/1.5 system-ui,sans-serif;letter-spacing:.05em;' +
        'text-transform:uppercase;color:var(--accent,#8a6d3b);border:1px solid currentColor;' +
        'border-radius:9px;padding:0 6px;margin-inline-end:6px;white-space:nowrap}' +
      '.dspoken{margin:2px 0 3px;font-size:.92em;color:var(--dim,#666)}' +
      '.dspoken>div{margin:1px 0}' +
      '.dspoken .dwas,.dspoken .das,.dspoken .dptext,.dspoken .dalt .dasr{color:var(--ink,#222);unicode-bidi:isolate}' +
      '.dspoken .darrow{margin:0 4px}' +
      '.dspoken .drole{font-style:italic}' +
      '.dspoken .dsnd{unicode-bidi:isolate;color:var(--ink,#222)}' +
      '.dsreadings{margin:4px 0 2px;font-size:11px;font-weight:600;letter-spacing:.07em;' +
        'text-transform:uppercase;color:var(--dim,#666)}' +
      '.dsnum{display:inline-block;min-width:1.4em;font-weight:600;color:var(--accent,#8a6d3b)}';
    document.head.appendChild(st);
  }
  function sEl(tag, cls, text, lang, dir) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (lang) e.setAttribute('lang', lang);
    if (dir) e.setAttribute('dir', dir);
    return e;
  }
  // does the word hold more than one reading, one of them spoken?  Then the
  // readings are numbered; a second LINE on one hit (spoken.same) is not one
  function spokenMany(w) {
    var hits = (w && w.hits) || [];
    return hits.length > 1 && hits.some(function (h) { return h.spoken && !h.spoken.same; });
  }
  function spokenHeader(w) {
    if (!spokenMany(w)) return null;
    spokenStyle();
    var n = w.hits.length;
    return sEl('div', 'dsreadings', (SPOKEN_COUNT[n] || n) + ' readings of this word, the likelier first');
  }
  // the number before a row's headword, as HTML, where the word has several readings
  function spokenLead(w, k) {
    return spokenMany(w) ? '<span class="dsnum">' + (k + 1) + '.</span>' : '';
  }
  function spokenRow(h) { return h && h.spoken && !h.spoken.same ? ' dspk' : ''; }
  // the hit's note, without the reason the spoken pass put in front of it (the block says that)
  function spokenNote(h) {
    var n = (h && h.note) || '', s = h && h.spoken;
    if (!s || s.same || !s.why || n.indexOf(s.why) !== 0) return n;
    return n.slice(s.why.length).replace(/^;\s*/, '');
  }
  /* The block: o = {written, lang, dir}, the word as the page writes it and
     the language it is in. */
  function spokenBlock(h, o) {
    var s = h && h.spoken;
    if (!s) return null;
    spokenStyle();
    o = o || {};
    var lang = o.lang || '', dir = o.dir || 'auto';
    var box = sEl('div', 'dspoken' + (s.same ? ' dsame' : ''));
    var top = sEl('div', 'dsline');
    top.appendChild(sEl('span', 'dspill', s.same ? 'also read as'
                                                  : s.kind === 'entry' ? 'spoken · the dictionary’s own page' : 'spoken'));
    if (s.same) {
      top.appendChild(sEl('span', 'das', s.as, lang, dir));
    } else {
      if (o.written) {
        top.appendChild(sEl('span', 'dwas', o.written, lang, dir));
        top.appendChild(sEl('span', 'darrow', '→'));
      }
      top.appendChild(sEl('span', 'das', s.as, lang, dir));
    }
    box.appendChild(top);
    if (s.why) box.appendChild(sEl('div', 'dwhy', s.why));
    if (s.parts && s.parts.length > 1) {
      var pc = sEl('div', 'dparts', 'pieces: ');
      pc.appendChild(sEl('span', 'dptext', s.parts.join(' + '), lang, dir));
      box.appendChild(pc);
    }
    // a piece is told on a line of its own where it has NO formal word (an emphatic -ā, a redundant -sh, the helper of the
    // progressive): the clitics, the copula and the endings of a composed word are in the reason and the pieces line already
    (s.pieces || []).forEach(function (p) {
      if (!p || !p.role || SPOKEN_NO_FORMAL.indexOf(p.role) < 0) return;
      var row = sEl('div', 'dpiece');
      row.appendChild(sEl('span', 'dptext', p.text || '', lang, dir));
      row.appendChild(document.createTextNode(' '));
      row.appendChild(sEl('span', 'drole', p.role));
      // (a note that only says the reason again is not said twice)
      if (p.note && p.note !== s.why) row.appendChild(document.createTextNode(' — ' + p.note));
      box.appendChild(row);
    });
    (s.readings || []).forEach(function (r, k) {
      if (!r || !r.as || (k === 0 && r.as === s.as)) return;
      var alt = sEl('div', 'dalt', 'or ');
      alt.appendChild(sEl('span', 'dasr', r.as, lang, dir));
      if (r.why) alt.appendChild(document.createTextNode(' — ' + r.why));
      box.appendChild(alt);
    });
    // the sound: the spoken one where a rule gives it; where none does, the formal word's, labelled, and never one made up.
    // (A second line on a card says only what else the letters read as: its card has the sound.)
    if (s.sound && !s.same) {
      var snd = sEl('div', 'dsound');
      if (s.sound_kind === 'spoken') {
        snd.appendChild(document.createTextNode('said '));
      } else {
        snd.appendChild(document.createTextNode('formal sound '));
        snd.title = 'no spoken sound is known for this word: this is the formal word\u2019s';
      }
      snd.appendChild(sEl('span', 'dsnd', s.sound, null, 'ltr'));
      box.appendChild(snd);
    }
    return box;
  }
  var spoken = { header: spokenHeader, lead: spokenLead, row: spokenRow, note: spokenNote, block: spokenBlock, many: spokenMany };

  /* ---- the mobile interface as an app (docs/mobile.md) ----
     Installed from a phone's browser, the mobile interface opens from an
     icon, on the whole screen: /manifest.webmanifest describes it, and
     /sw.js (lib/sw.js) is the service worker a browser asks for before it
     offers to install anything.  Here:
       - the app opens at /?mode=mobile: the mode is set from the address and
         the address given back without it, before anything is painted;
       - in the mobile mode the service worker is registered (again, which
         costs nothing) on every page, so whichever page a phone is on, it
         can be installed from there;
       - the browser's offer to install (beforeinstallprompt, Chrome's) is
         kept, in the mobile mode, for the page's own Install buttons --
         [data-parseh-install], drawn only while there is an offer -- rather
         than a bar of the browser's over whatever is being read;
       - a page built without the app's tags (a book's reader) gets them. */
  (function () {
    var m = /(?:^\?|&)mode=(browser|mobile)(?=&|$)/.exec(location.search);
    if (!m) return;
    try { localStorage.setItem(MODE_KEY, m[1]); } catch (e) {}
    modeCookieSet(m[1]);
    if (!window.history || !history.replaceState) return;
    var rest = location.search.replace(/(?:^\?|&)mode=(?:browser|mobile)(?=&|$)/, '').replace(/^&/, '');
    try { history.replaceState(history.state, '', location.pathname + (rest ? '?' + rest : '') + location.hash); }
    catch (e) {}
  })();
  var installOffer = null, appFns = [];
  function appStandalone() {
    return !!((window.matchMedia && window.matchMedia(
      '(display-mode: standalone), (display-mode: fullscreen), (display-mode: minimal-ui)').matches) ||
      window.navigator.standalone === true);
  }
  function appPaint() {
    var bs = document.querySelectorAll('[data-parseh-install]');
    for (var i = 0; i < bs.length; i++) bs[i].hidden = !installOffer;
    for (var j = 0; j < appFns.length; j++) { try { appFns[j](); } catch (e) {} }
  }
  function appInstall() {
    if (!installOffer) return Promise.resolve(false);
    var offer = installOffer;
    installOffer = null;                   // an offer is good for one prompt
    appPaint();
    offer.prompt();
    return offer.userChoice.then(function (c) { return !!c && c.outcome === 'accepted'; },
                                 function () { return false; });
  }
  function appRegister() {
    if (!('serviceWorker' in navigator) || !window.isSecureContext ||
        !/^https?:$/.test(location.protocol)) return Promise.resolve(null);
    // refused where the phone does not trust the certificate: the install
    // page says so, and nothing else here needs to
    return navigator.serviceWorker.register('/sw.js').catch(function () { return null; });
  }
  window.addEventListener('beforeinstallprompt', function (e) {
    if (!isMobile()) return;               // the browser mode: the browser's own way
    e.preventDefault();
    installOffer = e;
    appPaint();
  });
  window.addEventListener('appinstalled', function () { installOffer = null; appPaint(); });
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest && e.target.closest('[data-parseh-install]');
    if (b) appInstall();
  });
  function appHead() {
    if (location.protocol === 'file:' || document.querySelector('link[rel=manifest]')) return;
    var head = document.head;
    if (!head) return;
    // the same tags lib/mobile.py (app_head) writes into the pages it makes
    [['link', {rel: 'manifest', href: '/manifest.webmanifest'}],
     ['link', {rel: 'apple-touch-icon', sizes: '180x180', href: '/lib/icons/apple-touch-icon.png'}],
     ['meta', {name: 'mobile-web-app-capable', content: 'yes'}],
     ['meta', {name: 'apple-mobile-web-app-capable', content: 'yes'}],
     ['meta', {name: 'apple-mobile-web-app-title', content: 'Parseh'}]].forEach(function (t) {
      var el = document.createElement(t[0]);
      for (var k in t[1]) el.setAttribute(k, t[1][k]);
      head.appendChild(el);
    });
  }
  function appWire() {
    appHead();
    appPaint();
    if (isMobile()) appRegister();
    modeOnChange(function (m) { if (m === 'mobile') appRegister(); });
  }

  /* ---- the dictionary's sheet, on a phone (TO-DO §4.18) ----
     The owner, 2026-09-24: an entry read inside the gloss cloud "requires
     scrolling inside the cloud and from mobile is basically unusable".  It
     was a scrolling box inside a scrolling page, in a floating card a few
     centimetres wide, over the very word it was about.  So on a phone the
     dictionary opens as a SHEET from the foot of the screen -- the look of
     "Keep on this phone" (.kp-back / .kp-sheet, lib/parseh.css), under
     names of its own (lib/mobile.css draws it) -- and the cloud keeps what
     it was always good at: the reading, the transliteration, the vocabulary
     and the meaning, beside the word.

     ONE SHEET FOR BOTH PAGES.  A book's reader (lib/mobilereader.js) and a
     video's page (youtube/lib/player.js) each draw the entry with their own
     `dictInto`, into a box they hand in here; this is only the sheet around
     it, and it lives in this file because this file is the one both pages
     -- and every reader however old -- already load, as they load the other
     pieces the two panels share (senseLabels, pairMarkup, above).

     What the sheet does, all of it asked for:
       - AS TALL AS THE ENTRY, up to 86% of the screen, and scrolled inside
         beyond that (the owner's 1: no peek) -- ALWAYS, whatever the page
         pins at its top (dsClear says why).  It grows as the lookup lands,
         which it does after the sheet is open.
       - ONE SCROLLER, its body, with overscroll-behavior:contain: a finger
         can tell it from the page, and it cannot pull the page to refresh.
       - THE WORD MARKED (m-dword) for as long as the sheet is up, and
         scrolled into the room between the header and the sheet wherever
         the page can put it there; where it cannot, the sheet covers it, and
         closing the sheet shows it again where it was.
       - SENSES NUMBERED, one to a line, each hit's part of speech a label
         (the owner's 2: the three senses the server sends, nothing folded).
       - THE LANGUAGE'S DIRECTION AND FACE on every run of it: the entry's
         rules in every reader are written `#cloud .dict ...` and mean
         nothing out here, so the sheet restates them (lib/mobile.css) --
         and the hit's headword, which never said its language, is given it.
       - DISMISSED AS A PHONE DISMISSES THINGS: a swipe down, a tap beside
         it, the back gesture, and ✕ and Escape for a keyboard.  Closing it
         leaves nothing open (the owner's 4): `onClose` closes the page's
         cloud too, and a video the cloud had paused goes on.
     Where it stands: over the page, its dialogs and the gloss cloud, and
     UNDER the toast, the ? bubble and the keep sheet, so "?" still says what
     a thing in it is (lib/explain.js, 430). */
  var dsCur = null, dsSeq = 0, dsSpent = 0, dsWired = false, dsHead = null, dsOther = null;
  function dsEl(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  /* A HIT'S HEAD LINE IS ITS HEADWORD AND ITS TRANSLITERATION, run together
     by both panels as one string ("دنیا donyā").  Left so, a Persian or an
     Arabic headword is set in the page's own face, and a direction given to
     the whole would carry the Latin to the wrong side.  So the headword is
     cut off the Latin words that follow it, where there are any, and put in
     a span of its own with the language's lang, direction and face.  The
     patterns are built here, in a try: a browser too old for Unicode
     property escapes would refuse the whole of this file over a literal. */
  try {
    dsHead = new RegExp('^[\\p{Script=Latin}\\p{Script=Common}\\p{Script=Inherited}]+$', 'u');
    dsOther = new RegExp('[^\\p{Script=Latin}\\p{Script=Common}\\p{Script=Inherited}]', 'u');
  } catch (e) {}
  function dsSplitHead(hd, lang) {
    var text = hd.textContent, head = text, tail = '';
    if (dsHead && dsOther) {
      var words = text.split(' '), k = words.length;
      while (k > 1 && words[k - 1] && dsHead.test(words[k - 1])) k--;
      var front = words.slice(0, k).join(' ');
      if (k < words.length && dsOther.test(front)) { head = front; tail = ' ' + words.slice(k).join(' '); }
    }
    var w = dsEl('span', 'm-dhw', head);
    if (lang && lang.code) w.setAttribute('lang', lang.code);
    w.setAttribute('dir', lang && lang.dir === 'rtl' ? 'rtl' : 'auto');
    hd.textContent = '';
    hd.appendChild(w);
    if (tail) hd.appendChild(dsEl('span', 'm-dtl', tail));
    hd.setAttribute('data-m-split', '');
  }
  /* What the sheet adds to an entry as it lands, whichever page drew it: the
     headword's language, and a number before each sense of a hit -- as text
     of the page, so it is read out and can be asked of the page, and put
     again wherever a hit has gained a sense since (the definitions' "more"). */
  function dsTidy(s) {
    var heads = s.body.querySelectorAll('.dhead2:not([data-m-split])');
    for (var i = 0; i < heads.length; i++) dsSplitHead(heads[i], s.o.lang);
    var hits = s.body.querySelectorAll('.dhit');
    for (var h = 0; h < hits.length; h++) {
      var senses = hits[h].querySelectorAll('.dsense');
      for (var k = 0; k < senses.length; k++) {
        var first = senses[k].firstChild, want = (k + 1) + '.';
        if (first && first.nodeType === 1 && first.classList.contains('m-dsn')) {
          if (first.textContent !== want) first.textContent = want;
        } else senses[k].insertBefore(dsEl('span', 'm-dsn', want), first);
      }
    }
  }
  // the page's scroller around the word: the nearest box that scrolls, or
  // the page itself (null)
  function dsScroller(a) {
    for (var p = a.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
      var oy = getComputedStyle(p).overflowY;
      if ((oy === 'auto' || oy === 'scroll') && p.scrollHeight > p.clientHeight + 1) return p;
    }
    return null;
  }
  /* THE TOP OF THE ROOM A WORD CAN BE READ IN: under whatever the page pins
     at the top of the screen OVER THE WORD'S COLUMN -- its header, and a
     video's page its video (`pinned`, the selectors a page names).  Over the
     word's column, because a thing pinned beside the word hides nothing of
     it: a video's page held sideways pins its video down the whole left of
     the screen, from under the header to the foot, and counted as a ceiling
     that put the ceiling at the foot of the screen, and left the phrase, on
     the right, no room anywhere. */
  function dsCeiling(a, pinned) {
    var r = a.getBoundingClientRect(), H = window.innerHeight, top = 0;
    (pinned || ['header']).forEach(function (sel) {
      var e = document.querySelector(sel);
      if (!e) return;
      var pos = getComputedStyle(e).position;
      if (pos !== 'fixed' && pos !== 'sticky') return;
      var er = e.getBoundingClientRect();
      if (er.right <= r.left || er.left >= r.right || er.top >= H / 2) return;
      top = Math.max(top, er.bottom);
    });
    return Math.max(0, top);
  }
  /* THE WORD, CLEAR OF THE SHEET, WHERE THE PAGE CAN PUT IT THERE.  Asked
     again whenever the sheet changes height -- it opens on "looking it up…"
     and grows when the answer lands.  A word inside something fixed (the
     subtitles over a video on the whole screen) cannot be scrolled anywhere,
     and is left where it is: the sheet covers the subtitles, and the video
     waits paused while it is up.

     THE ENTRY COMES FIRST (the owner, 2026-09-25).  The sheet once stopped
     short of the word where the page pins something at its top -- a video's
     page held upright keeps its video under the header, a third of the
     screen -- cut down as far as 45% of the screen to leave the word a room
     above it.  The owner chose the entry: the sheet is ALWAYS as tall as
     what it holds, up to 86% of the screen, and where that covers the word,
     it covers it.  Nothing is lost by it: the word stays marked under the
     sheet, and the sheet closing -- which spends its own history entry --
     takes the page back to where it stood, with the word where it was
     tapped.  Where there IS a room between what is pinned and the sheet,
     the word is still scrolled into it; where there is none, the page is
     not moved at all, for a scroll that cannot uncover the word only takes
     the reader's place away. */
  function dsClear(s) {
    var a = s.anchor;
    if (s.closed || !a || !a.isConnected) return;
    for (var p = a; p && p !== document.body; p = p.parentElement)
      if (getComputedStyle(p).position === 'fixed') return;
    var r = a.getBoundingClientRect(), H = s.back.clientHeight;
    var ceil = 0;
    try { ceil = dsCeiling(a, s.o.pinned); } catch (e) {}
    // the sheet's top as laid out, not as a swipe in progress has it now
    var top = H - s.sheet.offsetHeight;
    if (r.top >= ceil + 6 && r.bottom <= top - 6) return;
    if (top - ceil < r.height + 12) return;
    // the middle of the room there is
    var want = ceil + (top - ceil - r.height) / 2;
    var d = r.top - want;
    if (Math.abs(d) < 2) return;
    var sc = dsScroller(a);
    if (sc) { sc.scrollTop += d; return; }
    /* THE LAST LINES OF A PAGE cannot be scrolled up past its end, and the
       last caption of a transcript, or of a book, is as likely to be looked
       up as any: while the sheet is up the page is lent the room it lacks,
       at its foot, under the sheet, where nobody sees it -- and it is given
       back when the sheet goes.  Measured from where the loan starts, the
       page's own foot: a page shorter than the screen grows by nothing until
       it passes the screen's height. */
    if (d > document.documentElement.scrollHeight - window.innerHeight - window.scrollY) {
      if (!s.space) {
        s.space = dsEl('div', 'm-dspace');
        s.space.setAttribute('aria-hidden', 'true');
        document.body.appendChild(s.space);
      }
      s.space.style.height = Math.max(0, Math.ceil(window.innerHeight + d - s.space.getBoundingClientRect().top)) + 'px';
    }
    window.scrollBy(0, d);
  }
  function dsClose(s, how) {
    if (s.closed) return;
    s.closed = true;
    if (dsCur === s) dsCur = null;
    if (s.back.parentNode) s.back.parentNode.removeChild(s.back);
    if (s.space && s.space.parentNode) s.space.parentNode.removeChild(s.space);
    if (s.anchor) s.anchor.classList.remove('m-dword');
    document.documentElement.classList.remove('m-dsup');
    if (s.watch) s.watch.disconnect();
    if (s.sized) s.sized.disconnect();
    // the history entry the sheet pushed, spent -- unless the back gesture
    // is what closed it, which has spent it already, or a sheet opened over
    // it takes the entry over (dictSheet).  The popstate this causes is the
    // sheet's own, and is not heard as a back gesture (below).
    if (how !== 'back' && how !== 'again' && history.state && history.state.parsehDictSheet === s.id) {
      dsSpent++;
      try { history.back(); } catch (e) { dsSpent--; }
    }
    if (s.o.onClose) { try { s.o.onClose(how); } catch (e) {} }
    // the keyboard's place given back to what opened the sheet, where it is
    // still on the page (the cloud's button goes with the cloud)
    var o = s.opener;
    if (how !== 'again' && o && o.isConnected && o.getClientRects().length && o.focus) {
      try { o.focus({preventScroll: true}); } catch (e) {}
    }
  }
  /* THE KEYBOARD STAYS IN THE SHEET.  It says it is a dialog that holds the
     page (aria-modal), and a Tab walked out of it into the header under the
     dimmed page, where nothing can be pressed; so Tab and Shift+Tab go round
     the sheet's own buttons and links, first to last and back. */
  function dsTab(s, e) {
    var all = s.sheet.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    var can = Array.prototype.filter.call(all, function (x) {
      return !x.disabled && x.getClientRects().length > 0;
    });
    var at = document.activeElement, i = can.indexOf(at);
    e.preventDefault();
    if (!can.length) { try { s.sheet.focus({preventScroll: true}); } catch (err) {} return; }
    var next = e.shiftKey ? (i <= 0 ? can[can.length - 1] : can[i - 1])
                          : (i < 0 || i === can.length - 1 ? can[0] : can[i + 1]);
    try { next.focus(); } catch (err) {}
  }
  function dsWire() {
    if (dsWired) return;
    dsWired = true;
    // THE BACK GESTURE: a popstate that leaves the sheet's own entry
    window.addEventListener('popstate', function () {
      if (dsSpent) { dsSpent--; return; }
      if (dsCur && !(history.state && history.state.parsehDictSheet === dsCur.id)) dsClose(dsCur, 'back');
    });
    document.addEventListener('keydown', function (e) {
      if (!dsCur) return;
      if (e.key === 'Tab' && !(e.altKey || e.ctrlKey || e.metaKey)) { dsTab(dsCur, e); return; }
      if (e.key !== 'Escape') return;
      e.preventDefault();
      e.stopImmediatePropagation();
      dsClose(dsCur, 'key');
    }, true);
    /* THE POINTER LEAVING THE PAGE UNDER THE SHEET IS NOT A POINTER LEAVING
       THE CLOUD.  A tap is followed by the mouse events a phone makes up for
       it, so the first tap on the sheet "leaves" the cloud's button that
       opened it -- and both pages close the cloud a moment after the mouse
       leaves it: the book's lookup would be thrown away before its answer
       landed (it fills only while its cloud is open), and the video would
       start again under the sheet.  While the sheet is up nothing under it
       is hovered, so what the page would hear of it is stopped here. */
    ['mouseout', 'mouseleave', 'pointerout', 'pointerleave'].forEach(function (t) {
      window.addEventListener(t, function (e) {
        var n = e.target;
        if (dsCur && n && n.nodeType === 1 && !dsCur.back.contains(n)) e.stopImmediatePropagation();
      }, true);
    });
    // the browser mode has no sheet: switched to it, the sheet goes
    modeOnChange(function (m) { if (m !== 'mobile' && dsCur) dsClose(dsCur, 'mode'); });
    window.addEventListener('resize', function () { if (dsCur) dsClear(dsCur); });
  }
  /* A swipe down closes it: from its head at any time (pointer events: the
     head takes no scrolling), and from its body when the body is scrolled
     to its top and the finger pulls further (touch events: the body's own
     scrolling is the browser's, and would cancel a pointer).  Let go short
     of a third of its height, slowly, and it springs back. */
  function dsDrag(s) {
    var y0 = 0, dy = 0, t0 = 0, on = false, tall = 0;
    function start(y) {
      on = true; y0 = y; dy = 0; t0 = Date.now(); tall = s.sheet.offsetHeight;
      s.sheet.classList.add('m-dsdrag');
    }
    function move(y) {
      dy = Math.max(0, y - y0);
      s.sheet.style.transform = dy ? 'translateY(' + dy + 'px)' : '';
    }
    function end() {
      if (!on) return;
      on = false;
      s.sheet.classList.remove('m-dsdrag');
      var flick = dy > 24 && dy / Math.max(1, Date.now() - t0) > 0.6;
      if (dy > Math.min(140, tall * 0.3) || flick) dsClose(s, 'swipe');
      else s.sheet.style.transform = '';
    }
    s.head.addEventListener('pointerdown', function (e) {
      if (e.button > 0 || (e.target.closest && e.target.closest('button'))) return;
      try { s.head.setPointerCapture(e.pointerId); } catch (err) {}
      start(e.clientY);
    });
    s.head.addEventListener('pointermove', function (e) { if (on) move(e.clientY); });
    s.head.addEventListener('pointerup', end);
    s.head.addEventListener('pointercancel', end);
    var ty0 = 0, atTop = false, pulling = false;
    s.body.addEventListener('touchstart', function (e) {
      pulling = false;
      if (e.touches.length !== 1) return;
      ty0 = e.touches[0].clientY;
      atTop = s.body.scrollTop <= 0;
    }, {passive: true});
    s.body.addEventListener('touchmove', function (e) {
      if (e.touches.length !== 1) return;
      var y = e.touches[0].clientY;
      if (!pulling) {
        if (!(atTop && s.body.scrollTop <= 0 && y - ty0 > 6)) return;
        pulling = true;
        start(ty0);
      }
      e.preventDefault();
      move(y);
    }, {passive: false});
    s.body.addEventListener('touchend', function () { if (pulling) { pulling = false; end(); } });
    s.body.addEventListener('touchcancel', function () { if (pulling) { pulling = false; end(); } });
  }
  /* o: {box, lang: {code, dir}, title, anchor, carry: [nodes], pinned:
         [selectors], onClose(how)} -- the box is the page's own, filled by
     its own dictInto, before or after this is called; `carry` are the
     cloud's gloss lines, copied in over it; `pinned`, what the page pins at
     the top of the screen (dsCeiling; the header when not said).  Returns
     {close(how), sheet, body, open()}. */
  function dictSheet(o) {
    // A SHEET OPENED OVER A SHEET takes over its history entry rather than
    // spending it and pushing another: the spending is a history.back() that
    // lands after the push, and it took the new sheet's entry with it --
    // leaving the page one back gesture from being left, with a sheet up
    var prev = dsCur;
    if (prev) dsClose(prev, 'again');
    dsWire();
    var s = {o: o, id: (++dsSeq) + ':' + Date.now(), anchor: o.anchor || null, closed: false};
    // what had the keyboard's place, to have it back when the sheet goes
    var had = document.activeElement;
    s.opener = had && had !== document.body && !(prev && prev.back.contains(had)) ? had : (prev && prev.opener) || null;
    s.back = dsEl('div', 'm-dback');
    s.back.setAttribute('data-layout', 'mobile');
    /* ITS OWN LANGUAGE.  The sheet's words are the toolbox's -- its head
       line, the senses, "looking it up…", ✕ -- in English, as the cloud they
       came out of says of itself (the reader's #cloud is lang="en"); hung off
       <body>, they would be taken for the book's language, read out in a
       Persian or a Japanese voice and broken by that language's rules.  The
       runs in the book's language say theirs (the head, the words, the
       headwords, the sentences), and the gloss lines carry the cloud's. */
    s.back.setAttribute('lang', 'en');
    s.back.setAttribute('dir', 'ltr');
    s.sheet = dsEl('div', 'm-dsheet');
    s.sheet.setAttribute('role', 'dialog');
    s.sheet.setAttribute('aria-modal', 'true');
    s.sheet.setAttribute('aria-label', 'the dictionary' + (o.title ? ': ' + o.title : ''));
    s.sheet.tabIndex = -1;
    s.head = dsEl('div', 'm-dshead');
    var grip = dsEl('span', 'm-dgrip');
    grip.setAttribute('aria-hidden', 'true');
    s.head.appendChild(grip);
    var title = dsEl('div', 'm-dstitle', o.title || '');
    if (o.lang && o.lang.code) title.setAttribute('lang', o.lang.code);
    title.setAttribute('dir', o.lang && o.lang.dir === 'rtl' ? 'rtl' : 'auto');
    s.head.appendChild(title);
    var x = dsEl('button', 'm-dsx', '✕');
    x.type = 'button';
    x.setAttribute('aria-label', 'close the dictionary');
    x.title = 'close the dictionary — a swipe down, a tap above it or the back gesture closes it too';
    x.addEventListener('click', function () { dsClose(s, 'button'); });
    s.head.appendChild(x);
    s.body = dsEl('div', 'm-dsbody');
    if (o.carry && o.carry.length) {
      var gl = dsEl('div', 'm-dsgl');
      o.carry.forEach(function (n) { gl.appendChild(n.cloneNode(true)); });
      s.body.appendChild(gl);
    }
    if (o.box) {
      // AN ENTRY TAKEN OUT OF THE CLOUD LEAVES THE CLOUD'S CUT BEHIND: a
      // cloud cuts its panel to the room beside the word (placeCloud, in
      // both pages, an inline max-height), and kept, that cut made the sheet
      // a peek of the entry with the rest spilling out of its box
      o.box.style.maxHeight = '';
      s.body.appendChild(o.box);
    }
    s.sheet.appendChild(s.head);
    s.sheet.appendChild(s.body);
    s.back.appendChild(s.sheet);
    // a tap beside the sheet, on the dimmed page, closes it
    s.back.addEventListener('click', function (e) { if (e.target === s.back) dsClose(s, 'backdrop'); });
    // and a wheel over the dimmed page does not scroll the page under it
    s.back.addEventListener('wheel', function (e) { if (!s.body.contains(e.target)) e.preventDefault(); },
                            {passive: false});
    document.body.appendChild(s.back);
    // up: the page's header held where it is (bars(), above), so the room
    // the word is given under it stays that room
    document.documentElement.classList.add('m-dsup');
    if (s.anchor) s.anchor.classList.add('m-dword');
    dsCur = s;
    try {
      if (prev && history.state && history.state.parsehDictSheet === prev.id)
        history.replaceState({parsehDictSheet: s.id}, '');
      else history.pushState({parsehDictSheet: s.id}, '');
    } catch (e) {}
    dsDrag(s);
    dsTidy(s);
    if (window.MutationObserver) {
      s.watch = new MutationObserver(function () { dsTidy(s); });
      s.watch.observe(s.body, {childList: true, subtree: true});
    }
    if (window.ResizeObserver) {
      s.sized = new ResizeObserver(function () { dsClear(s); });
      s.sized.observe(s.sheet);
    }
    dsClear(s);
    try { s.sheet.focus({preventScroll: true}); } catch (e) {}
    return {close: function (how) { dsClose(s, how || 'page'); }, sheet: s.sheet, body: s.body,
            open: function () { return !s.closed; }};
  }
  // whether a sheet is up, and closing whichever is: for a page that did
  // not open it (lib/mobileplayer.js, the browser leaving its full screen)
  dictSheet.up = function () { return !!dsCur; };
  dictSheet.close = function (how) {
    if (!dsCur) return false;
    dsClose(dsCur, how || 'page');
    return true;
  };

  window.Parseh = { KEY: KEY, theme: { get: get, set: set, apply: apply,
                    cycle: cycle, isDark: isDark, resolved: resolved },
                    lang: { KEY: LANG_KEY, get: langGet, set: langSet, apply: langApply },
                    mode: { KEY: MODE_KEY, get: modeGet, set: modeSet, isMobile: isMobile,
                            route: modeRoute, onChange: modeOnChange, apply: modeApply,
                            pages: MOBILE_PAGES },
                    app: { standalone: appStandalone, canPrompt: function () { return !!installOffer; },
                           prompt: appInstall, register: appRegister,
                           onChange: function (fn) { appFns.push(fn); } },
                    // an ask that cannot hang, and the one question every
                    // page of the app already keys off (see `ask`, `awayNow`)
                    ask: ask, away: awayNow,
                    toast: toast, copy: copy, stopServer: stopServer, buildBook: buildBook, typo: typo, readingFields: readingFields,
                    working: working, stopQuestion: stopQuestion,
                    readings: readings, wordstrip: wordstrip, baseText: baseText, pairMarkup: pairMarkup,
                    senseLabels: senseLabels, spoken: spoken, dictSheet: dictSheet };
  apply();
  modeApply();
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', wire);
  else wire();

  /* ---- what the server is working on: lib/activity.js ----
     Loaded from BESIDE THIS SCRIPT, by whatever address this one was
     loaded by: the book reader links lib/ relatively (it also opens off the
     disk), so a built reader gets the list without being built again, and
     every other page gets it without a tag of its own.  Off the disk there
     is no server to ask, and nothing is loaded. */
  (function () {
    if (window.ParsehActivity || location.protocol === 'file:') return;
    var me = document.currentScript;
    var src = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, 'activity.js')
                           : '/lib/activity.js';
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
  })();

  /* ---- the reading place and the settings the toolbox keeps: lib/prefs.js ----
     Loaded on every page, from beside this script: the theme follows a person
     from one device to another, and a reader hands its place to the toolbox
     so that the phone goes on where the computer stopped (TO-DO §4.9). */
  (function () {
    if (window.ParsehPrefs || location.protocol === 'file:') return;
    var me = document.currentScript;
    var src = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, 'prefs.js')
                           : '/lib/prefs.js';
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
  })();

  /* ---- keeping a thing on this phone, and the offline chip: lib/keep.js ----
     What has been kept works with the computer away (lib/sw.js holds it);
     this is the side a person sees -- the button in the gear's sheet on a thing that can
     be kept, and the chip that says the computer cannot be reached (§19). */
  (function () {
    if (window.ParsehKeep || location.protocol === 'file:') return;
    var me = document.currentScript;
    var src = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, 'keep.js')
                           : '/lib/keep.js';
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
  })();

  /* ---- "?": every title one tap away on a touch screen: lib/explain.js ----
     Loaded on every page the toolbox serves, from beside this script, as
     activity.js is above; it does nothing at all where a mouse can hover. */
  (function () {
    if (window.ParsehExplain || location.protocol === 'file:') return;
    var me = document.currentScript;
    var src = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, 'explain.js')
                           : '/lib/explain.js';
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    (document.head || document.documentElement).appendChild(s);
  })();

  /* ---- a video's page, in the mobile interface: lib/mobileplayer.js ----
     The player is written for its video by the server (youtube/lib/ytpages.py)
     and loads this script; the layer and the sheet are loaded from beside it,
     as the reader's are, and neither does anything until the mode is mobile.
     The narration's controls (lib/narrctl.js) come too: on a phone the dock
     at the foot plays the video, moves it back and on, and sets its speed. */
  (function () {
    if (location.protocol === 'file:' ||
        !/^\/youtube\/v\/[^\/]+\/(index\.html)?$/.test(location.pathname)) return;
    var me = document.currentScript;
    var base = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, '') : '/lib/';
    document.documentElement.classList.add('m-player');
    if (!document.querySelector('link[href$="/mobile.css"]')) {
      var l = document.createElement('link');
      l.rel = 'stylesheet';
      l.href = base + 'mobile.css';
      l.setAttribute('blocking', 'render');
      (document.head || document.documentElement).appendChild(l);
    }
    [['ParsehNarr', 'narrctl.js'], ['ParsehWordTouch', 'wordtouch.js'],
     ['ParsehMobilePlayer', 'mobileplayer.js']].forEach(function (w) {
      if (window[w[0]]) return;
      var s = document.createElement('script');
      s.src = base + w[1];
      s.async = true;
      (document.head || document.documentElement).appendChild(s);
    });
  })();

  /* ---- a book's reader, in the mobile interface: lib/mobilereader.js ----
     A reader is a page BUILT for its book (lib/tex2html.py), and a book built
     before the mobile interface existed has no mobile layout written into it
     -- which is most books, on any shelf, for any feature.  But every reader,
     however old, loads this script from lib/, so the mobile layer is loaded
     from here, beside it, as activity.js is above: the sheet (lib/mobile.css,
     whose reader rules all hang off html.m-reader) and the script that fits
     the header to a phone and keeps every writing door of the page shut
     (lib/mobilereader.js).  Both are loaded in either mode, because the mode
     can change while the page is open -- a switch made in another tab -- and
     neither does anything until the mode is mobile.
     A reader is known by its address, /books/<language>/<slug>/reader/ (or,
     for a book from before languages, /books/<slug>/reader/).  Opened off the
     disk it has no mobile interface, as it has no server. */
  (function () {
    if (location.protocol === 'file:' ||
        !/^\/books\/(?:[^\/]+\/){1,2}reader\/(?:index\.html)?$/.test(location.pathname)) return;
    var me = document.currentScript;
    var base = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, '') : '/lib/';
    document.documentElement.classList.add('m-reader');
    if (!document.querySelector('link[href$="/mobile.css"]')) {
      var l = document.createElement('link');
      l.rel = 'stylesheet';
      l.href = base + 'mobile.css';
      // held until it is in, where the browser knows how: without it the
      // header can be drawn once as the browser's before it is the phone's
      l.setAttribute('blocking', 'render');
      (document.head || document.documentElement).appendChild(l);
    }
    /* THE GEAR OF THE READER (a0.5.0): the one panel the page's settings live
       in -- the passes' names, the glosses, the listening, looking a word up,
       the text, the zoom, the colours -- drawn by the toolkit (lib/pagesettings.js)
       and fitted to this page by lib/gear-reader.js, which also puts the
       names on the level buttons and takes the vowel marks off on request.
       Both come from here, for every reader however old, and in ORDER (the
       toolkit, the reader's use of it, then the mobile layer below, which
       draws no menu of its own any more -- the gear is the phone's menu too):
       scripts put in by hand run in the order they were put in once they are
       told not to be async.
       html.pg-reader is what mobile.css keys the controls that moved into the
       panel on, set here so the first paint is already right -- and taken off
       again if either script cannot be had, so that a page without its gear
       is the page it was. */
    var rootEl = document.documentElement;
    rootEl.classList.add('pg-reader');
    [['ParsehGear', 'pagesettings.js'], ['ParsehGearReader', 'gear-reader.js']].forEach(function (w) {
      if (window[w[0]]) return;
      var g = document.createElement('script');
      g.src = base + w[1];
      g.async = false;
      g.onerror = function () { rootEl.classList.remove('pg-reader'); };
      (document.head || document.documentElement).appendChild(g);
    });
    // the narration's controls -- ▶ ↺ ↻, the speed, and the cure for a speed
    // that went back to 1× whenever a recording was loaded -- belong to both
    // modes, so they are loaded whatever the mode is (lib/narrctl.js)
    if (!window.ParsehNarr) {
      var n = document.createElement('script');
      n.src = base + 'narrctl.js';
      n.async = true;
      (document.head || document.documentElement).appendChild(n);
    }
    // and a held finger's menu, which stands in for the modifier-clicks a
    // tablet cannot make (lib/wordtouch.js)
    if (!window.ParsehWordTouch) {
      var w = document.createElement('script');
      w.src = base + 'wordtouch.js';
      w.async = true;
      (document.head || document.documentElement).appendChild(w);
    }
    // and what a book an agent is still making adds to its reader -- the
    // making panel, the lock on editing, "ask about this chunk" (lib/making.js).
    // It asks the server one question and does nothing for a book nobody is
    // making, in either mode, so it is loaded whatever the mode is
    if (!window.ParsehMaking) {
      var mk = document.createElement('script');
      mk.src = base + 'making.js';
      mk.async = true;
      (document.head || document.documentElement).appendChild(mk);
    }
    /* REVIEW LATER (a0.5.0): the chunks a person flags while reading, to come back to.
       The store and the list (lib/later.js), the cards made from it (lib/later-cards.js)
       and what a book gives it -- the four ways to flag, the dotted line under a flagged
       chunk, going to a chunk and making its card (lib/later-reader.js) -- come from here,
       for every reader however old, in that order: scripts put in by hand run in the
       order they were put in once they are told not to be async.  A page that cannot
       have them is the page it was. */
    [['ParsehLater', 'later.js'], ['ParsehLaterCards', 'later-cards.js'],
     ['ParsehLaterReader', 'later-reader.js']].forEach(function (w) {
      if (window[w[0]]) return;
      var lt = document.createElement('script');
      lt.src = base + w[1];
      lt.async = false;
      (document.head || document.documentElement).appendChild(lt);
    });
    if (window.ParsehMobileReader) return;
    var s = document.createElement('script');
    s.src = base + 'mobilereader.js';
    // after the gear's scripts above, so that the header is drawn once, with the gear in it
    s.async = false;
    (document.head || document.documentElement).appendChild(s);
  })();

  /* ---- the macro buttons of a book's chunk sheet: lib/vocbuttons.js ----
     The sheet is built into every reader, and its four buttons (\dw \vb \bw \pw)
     used to say what they write in a title nobody understood.  What says it
     now lives here, loaded from beside this script into every reader however
     old -- as the mobile layer is above -- so that no book has to be built
     again: the script dresses the buttons the sheet already has, and draws
     the examples with lib/vocline.js, the renderer the player draws a
     vocabulary line with.  A reader is known by its address, as above. */
  (function () {
    if (location.protocol === 'file:' ||
        !/^\/books\/(?:[^\/]+\/){1,2}reader\/(?:index\.html)?$/.test(location.pathname)) return;
    var me = document.currentScript;
    var base = me && me.src ? me.src.replace(/parseh\.js(?=[?#]|$).*$/, '') : '/lib/';
    [['ParsehVocline', 'vocline.js'], ['ParsehVocButtons', 'vocbuttons.js']].forEach(function (w) {
      if (window[w[0]]) return;
      var s = document.createElement('script');
      s.src = base + w[1];
      s.async = true;
      (document.head || document.documentElement).appendChild(s);
    });
  })();
})();
