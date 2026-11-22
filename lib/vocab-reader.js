// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — THE VOCABULARY LIST in a book's reader (a0.6.3, TO-DO 11.14).

   Loaded into every book's reader by lib/parseh.js, after lib/vocab.js (the
   list and its panel) and lib/later-reader.js (whose card sheet it borrows),
   so that every edition, however old, has it without a rebuild.  It asks for
   what it needs among the bindings the built page leaves in the global scope,
   each with `typeof`, as lib/later-reader.js does.

   WHERE THE WORDS COME FROM: SRC, the book's own copy of every chunk as the
   .tex writes it -- every chapter's, even one the page has not fetched yet
   (chapters arrive on demand, SRC is there from the start) -- with TIMES[n][3]
   saying which chapter chunk n is in.  So This chapter and Whole book are both
   read in the page, offline and in a kept copy alike, and no question goes to
   the computer.  (The computer can read the same thing: GET <book>/__vocab,
   lib/vocab.py, for what reads many books at once.)  "This chapter" is the
   chapter of the reading place.

   GOING TO A WORD: its chapter brought if it has not come yet, the chunk shown
   and lit as Review later's ▶ shows a chunk, and the reading place set there.
   On a computer the panel stays open beside the text, so the next click goes
   to the next place; on a phone the sheet goes down to show it.

   THE DOOR: «vocabulary» beside «⚑ later» in the header; on a phone, a row of
   the gear's sheet (lib/gear-reader.js borrows the same button).  The V key. */
(function () {
  'use strict';
  if (window.ParsehVocabReader) return;
  window.ParsehVocabReader = {};

  function langRec() { try { return typeof LANG === 'object' && LANG ? LANG : null; } catch (e) { return null; } }
  function srcAll() { try { return typeof SRC === 'object' && SRC && SRC.length ? SRC : null; } catch (e) { return null; } }
  function timesAll() { try { return typeof TIMES === 'object' && TIMES ? TIMES : null; } catch (e) { return null; } }
  function subsAll() { try { return typeof SUBS === 'object' && SUBS ? SUBS : null; } catch (e) { return null; } }
  function metaRec() { try { return typeof META === 'object' && META ? META : null; } catch (e) { return null; } }
  function chapterOfChunk(n) { var t = timesAll(); return (t && t[n] && +t[n][3]) || 0; }
  function hereChapter() {
    var i = -1, subs = subsAll();
    try { if (typeof cur === 'number') i = cur; } catch (e) {}
    if (i >= 0 && subs && subs[i]) return +subs[i][2] || 0;
    return 0;
  }
  function sheetOpen() {
    try {
      return !!((typeof ankiOpen !== 'undefined' && ankiOpen) || (typeof narrOpen !== 'undefined' && narrOpen) ||
                (typeof chOpen !== 'undefined' && chOpen) || (typeof fdShown !== 'undefined' && fdShown) ||
                (typeof secShown !== 'undefined' && secShown) || (typeof rgShown !== 'undefined' && rgShown) ||
                (typeof dlOpen !== 'undefined' && dlOpen) || (typeof bmOpen !== 'undefined' && bmOpen) ||
                document.querySelector('.m-dback'));
    } catch (e) { return false; }
  }
  function multiChapter() {
    var t = timesAll();
    if (!t) return false;
    for (var n = 0; n < t.length; n++) if (t[n] && +t[n][3]) return true;
    return false;
  }

  function chunks(scope) {
    var src = srcAll(), out = [], ci = scope === 'chapter' ? hereChapter() : -1;
    if (!src) return out;
    for (var n = 0; n < src.length; n++) {
      var voc = src[n] && src[n][4];
      if (!voc || (ci >= 0 && chapterOfChunk(n) !== ci)) continue;
      out.push({at: n, voc: String(voc), text: String(src[n][1] || ''), tr: String(src[n][3] || '')});
    }
    return out;
  }

  /* ---- going there */
  function find(n) {
    var e = document.querySelector('.sub [data-c="' + n + '"]');
    return e ? e.closest('.sub') : null;
  }
  function brought(n) {
    var sub = find(n);
    if (sub) return Promise.resolve(sub);
    var need = null;
    try { need = typeof needChapters === 'function' ? needChapters : null; } catch (e) {}
    if (!need) return Promise.resolve(null);
    return Promise.resolve(need(chapterOfChunk(n))).then(function () { return find(n); });
  }
  var flashTimer = null, flashed = [];
  function flash(els) {
    clearTimeout(flashTimer);
    flashed.forEach(function (e) { e.classList.remove('later-flash'); });
    flashed = Array.prototype.slice.call(els);
    flashed.forEach(function (e) { e.classList.add('later-flash'); });
    flashTimer = setTimeout(function () {
      flashed.forEach(function (e) { e.classList.remove('later-flash'); });
      flashed = [];
    }, 1600);
  }
  function setPlace(i) {
    try {
      var audio = document.getElementById('audio');
      if (audio && !audio.paused && typeof playSub === 'function') { playSub(i, true); return; }
      if (typeof cur === 'number' && typeof hl === 'function') {
        cur = i;
        hl(i, false);
        if (typeof save === 'function') save();
      }
    } catch (e) {}
  }
  function goTo(n) {
    return brought(n).then(function (sub) {
      if (!sub) throw new Error('this chunk is not in the book any more');
      var els = sub.querySelectorAll('.w[data-c="' + n + '"], .row[data-c="' + n + '"] .fa'), target = null;
      for (var i = 0; i < els.length; i++) if (els[i].getClientRects().length > 0) { target = els[i]; break; }
      target = target || sub;
      try {
        if (typeof reveal === 'function') reveal(target, 'center', 'auto');
        else target.scrollIntoView({block: 'center'});
      } catch (e) { target.scrollIntoView({block: 'center'}); }
      setPlace(+sub.getAttribute('data-s'));
      flash(els);
    });
  }

  /* ---- a word's card: the reader's own sheet, opened on the word, with the
     word's romanisation and meaning in place of the chunk's */
  function cards() {
    var R = window.ParsehLaterReader;
    return {
      can: function () {
        var p = window.Parseh, mobile = !!(p && p.mode && p.mode.isMobile && p.mode.isMobile());
        return !mobile && !!(R && R.sheetAt && R.cardsReady && R.cardsReady());
      },
      open: function (w, n) {
        return R.sheetAt(n, w.word, function () {
          if (typeof AN !== 'object' || !AN) return;
          if (AN.kana) AN.kana.value = '';
          if (AN.tr) AN.tr.value = w.rom || '';
          if (AN.en) AN.en.value = w.meanings.join(' · ');
        });
      }
    };
  }

  function placeButton(btn) {
    var after = document.querySelector('header .later-btn') || document.getElementById('toc');
    if (after && after.parentNode) after.parentNode.insertBefore(btn, after.nextSibling);
    else {
      var h = document.querySelector('header');
      if (h) h.appendChild(btn);
    }
  }
  // one panel on the right at a time: the contents, Review later, this
  function oneAtATime(handle) {
    var later = window.ParsehLaterReader && ParsehLaterReader.panel;
    handle.onToggle(function (open) {
      if (!open) return;
      try { if (later && later.isOpen()) later.close('other'); } catch (e) {}
      try {
        var tw = document.getElementById('tocwrap');
        if (tw && !tw.hidden && typeof tocOpen === 'function') tocOpen(false, true);
      } catch (e) {}
    });
    if (later && later.onToggle) later.onToggle(function (open) { if (open && handle.isOpen()) handle.close('other'); });
    var wrap = document.getElementById('tocwrap');
    if (wrap && window.MutationObserver)
      new MutationObserver(function () { if (!wrap.hidden && handle.isOpen()) handle.close('other'); })
        .observe(wrap, {attributes: true, attributeFilter: ['hidden']});
  }

  function start() {
    var L = langRec();
    if (!window.ParsehVocab || !L || !srcAll()) return;
    var many = multiChapter();
    var handle = ParsehVocab.panel({
      kind: 'book', lang: L,
      title: function () { var m = metaRec() || {}; return m.title_latin || m.title || m.book || ''; },
      // a book of one chapter has nothing to choose between
      scopes: many ? [{id: 'chapter', label: 'This chapter'}, {id: 'book', label: 'Whole book'}]
                   : [{id: 'book', label: 'Whole book'}],
      scope: function () { return many ? 'chapter' : 'book'; },
      chunks: chunks,
      goTo: goTo,
      card: cards()
    });
    placeButton(handle.button);
    oneAtATime(handle);
    ParsehVocab.key(handle, sheetOpen);
    window.ParsehVocabReader.panel = handle;
    window.ParsehVocabReader.goTo = goTo;
    window.ParsehVocabReader.chunks = chunks;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
