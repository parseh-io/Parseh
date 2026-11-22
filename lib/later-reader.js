// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — REVIEW LATER in a book's reader (a0.5.0).

   Loaded into EVERY book's reader by lib/parseh.js, from beside it, after
   lib/later.js (the store and the list) and lib/later-cards.js: a reader is a
   page built for its book (lib/tex2html.py), and one built before review
   later existed has nothing of it in its own markup -- so the layer lives
   here, in lib/, and reaches every edition, however old, without a rebuild.
   It finds what it needs among the classic-script bindings the built page
   leaves in the global scope (SUBS, SRC, openAnki, needChapters...), each
   asked for with `typeof` as lib/mobilereader.js asks, and does nothing for
   one that has not got them.

   WHAT A BOOK GIVES THE LIST (lib/later.js, panel(adapter)) is the adapter
   below: where a flagged chunk is now (locate), taking the reader there
   (goTo) and making its card (makeCard, queue) -- and the four ways to flag:
     - the gloss cloud's button «review later», which reads «✓ marked» once
       it is set and takes the flag off when pressed again;
     - the L key, on the chunk the open cloud is for, else the chunk under the
       pointer (else the one the pencil last stood at), else a word that says
       to point at a chunk first;
     - a ⚑ beside the pencil that goes with the chunk under the pointer, at
       any level and with no hover mode;
     - a held finger: lib/wordtouch.js asks window.ParsehLaterMark.
   A flagged chunk wears a quiet dotted underline (lib/later.css, .later-mark).

   A CHUNK IS FOUND BY WHAT IT IS, never by its number.  data-c numbers move
   whenever the book changes, so a flag keeps the subparagraph's key
   (.sub[data-key]), the chunk's place inside it (k = data-c - data-from), the
   paragraph (.para[data-p]) and the chunk's text; and it is looked for in that
   order -- the k-th chunk of that subparagraph if its text is still the
   flag's, else the chunk of the same text nearest to k, else the same text
   anywhere in the paragraph -- and is ADRIFT where it is not.  The text is
   always the book's own, with its vowel marks: lane C's Diacritics only
   changes what is DRAWN, and textOf (which it hands the original) is what is
   read here.

   A CHAPTER THAT HAS NOT COME YET is a file beside the reader.  Flags in it
   are listed from the copy the flag itself holds; asking where one is does not
   fetch the chapter if the book's own copy of every chunk (SRC, which every
   reader since a0.2.0 carries) still has its text -- going there, and making
   its card, do (needChapters, the reader's own); a flag whose chunk is not in
   the chapter once it is here is adrift from then on. */
(function () {
  'use strict';
  if (window.ParsehLaterReader) return;
  window.ParsehLaterReader = {};

  var LT = function () { return window.ParsehLater; };
  var P = function () { return window.Parseh; };
  function mobile() { var p = P(); return !!(p && p.mode && p.mode.isMobile && p.mode.isMobile()); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function toast(text, bad) {
    var p = P();
    try { if (p && p.toast) p.toast(text, !!bad); } catch (e) {}
  }
  function isField(t) {
    return !!(t && t.closest && t.closest('input, textarea, select, [contenteditable]'));
  }
  function norm(s) {
    s = String(s == null ? '' : s);
    try { s = s.normalize('NFC'); } catch (e) {}
    return s.replace(/\s+/g, ' ').trim();
  }

  /* ---- what the page holds, asked for as lib/mobilereader.js asks ---- */
  function langRec() { try { return typeof LANG === 'object' && LANG ? LANG : null; } catch (e) { return null; } }
  function glossRec() { try { return typeof GLOSS === 'object' && GLOSS ? GLOSS : null; } catch (e) { return null; } }
  function metaRec() { try { return typeof META === 'object' && META ? META : null; } catch (e) { return null; } }
  function subsAll() { try { return typeof SUBS === 'object' && SUBS ? SUBS : null; } catch (e) { return null; } }
  function srcAll() { try { return typeof SRC === 'object' && SRC && SRC.length ? SRC : null; } catch (e) { return null; } }
  function timesAll() { try { return typeof TIMES === 'object' && TIMES ? TIMES : null; } catch (e) { return null; } }
  function parasAll() { try { return typeof PARAS === 'object' && PARAS ? PARAS : null; } catch (e) { return null; } }
  function readerHas() {
    try { return typeof chunkData === 'function' && typeof textOf === 'function' && !!subsAll() && !!langRec(); }
    catch (e) { return false; }
  }
  // one of the reader's own sheets is over the page (lib/mobilereader.js asks the same, hpOwnSheet)
  function sheetOpen() {
    try {
      return !!((typeof ankiOpen !== 'undefined' && ankiOpen) || (typeof narrOpen !== 'undefined' && narrOpen) ||
                (typeof chOpen !== 'undefined' && chOpen) || (typeof fdShown !== 'undefined' && fdShown) ||
                (typeof secShown !== 'undefined' && secShown) || (typeof rgShown !== 'undefined' && rgShown) ||
                (typeof dlOpen !== 'undefined' && dlOpen) || (typeof bmOpen !== 'undefined' && bmOpen) ||
                document.querySelector('.m-dback'));
    } catch (e) { return false; }
  }

  var ref = null;                 // what this book's flags are kept under: its reader's path
  var panelHandle = null;         // the list's own handle (ParsehLater.panel)

  /* ================================================================ THE CHUNK
     A chunk element is a `.w[data-c]` of any pass or a `.row[data-c]` of the
     chunks pass; the subparagraph it is in carries the key and the first and
     last chunk numbers. */
  function holderOf(node) {
    var h = node && node.closest ? node.closest('.pass [data-c], [data-c]') : null;
    return h && h.closest && h.closest('.sub') ? h : null;
  }
  function subFrom(sub) {
    var f = +sub.getAttribute('data-from');
    if (f >= 0) return f;
    var first = sub.querySelector('[data-c]');
    return first ? +first.getAttribute('data-c') : 0;
  }
  function subTo(sub) {
    var t = +sub.getAttribute('data-to');
    if (t >= 0) return t;
    var all = sub.querySelectorAll('[data-c]');
    return all.length ? +all[all.length - 1].getAttribute('data-c') : subFrom(sub);
  }
  /* A chunk's text in its own subparagraph, the book's own -- the very text a
     card or a copy carries (textOf is lane C's, which gives back the marks
     Diacritics took off the page). */
  function textIn(sub, n) {
    var e = sub.querySelector('.row[data-c="' + n + '"] .fa') || sub.querySelector('.p1 .w[data-c="' + n + '"]') ||
            sub.querySelector('[data-c="' + n + '"]');
    if (!e) return null;
    var t;
    try { t = textOf(e); } catch (x) { t = e.textContent; }
    return norm(t);
  }
  function labelOf(sub) {
    var l = sub.querySelector('.lab');
    return l ? l.textContent.trim() : '';
  }
  // the chapter a subparagraph is in, named as its contents names it
  function chapterName(sub) {
    var sec = sub.closest('section.chapter');
    var ci = sec ? sec.getAttribute('data-ch') : null, para = sub.closest('.para[data-p]');
    var entry = null;
    if (para) entry = document.querySelector('#toclist a.toce[data-p="' + para.getAttribute('data-p') + '"]');
    if (!entry && ci !== null) entry = document.querySelector('#toclist a.toce[data-ci="' + ci + '"]');
    var printed = entry ? entry.getAttribute('data-ch') : null;
    if (printed === null) return '';
    var head = document.querySelector('#toclist .tocch[data-ch="' + printed + '"]');
    var name = head ? head.querySelector('.tocchn') : null, num = head ? head.querySelector('.tocchl bdi') : null;
    if (name && name.textContent.trim()) return name.textContent.trim();
    return 'chapter ' + (num ? num.textContent.trim() : printed);
  }
  function bookTitle() {
    var m = metaRec() || {};
    return m.title_latin || m.title || m.book || '';
  }

  /* WHAT A FLAG IS MADE OF, from a chunk element: the identity (subparagraph,
     place in it, text) and the snapshot the list stands on by itself.  The
     gloss is what the book's cloud and its card carry (chunkData), the
     plain text of the rendered line -- the vocabulary line as a person reads
     it, not as the .tex writes it. */
  function factsOf(holder) {
    if (!holder || !readerHas()) return null;
    var n = +holder.getAttribute('data-c'), sub = holder.closest('.sub');
    if (!(n >= 0) || !sub) return null;
    var d = null;
    try { d = chunkData(n); } catch (e) {}
    var s = srcAll() ? srcAll()[n] : null;
    var text = d && d.fa ? d.fa : (s && s[1] ? String(s[1]) : textIn(sub, n) || '');
    return {n: n, sub: sub, key: sub.getAttribute('data-key') || '', k: Math.max(0, n - subFrom(sub)),
            text: text, d: d, s: s};
  }
  function partsOf(f) {
    var L = langRec(), G = glossRec(), subs = subsAll(), i = +f.sub.getAttribute('data-s');
    var row = subs && subs[i] ? subs[i] : null, para = f.sub.closest('.para[data-p]'), p1 = f.sub.querySelector('.p1');
    var sentence = '';
    if (p1) { try { sentence = norm(textOf(p1)); } catch (e) { sentence = norm(p1.textContent); } }
    // what the page draws for the chunk, which is what its cloud and its card carry; the book's own
    // copy of it (SRC: [colour, text, kana, tr, voc, en, words]) only where the page has no row for it
    var d = f.d || {}, s = f.d ? [] : (f.s || []);
    return {kind: 'book', ref: ref, lang: L ? L.code : '', glossLang: G ? G.code : '', title: bookTitle(),
            sub: f.key, k: f.k, para: para ? para.getAttribute('data-p') : '',
            label: labelOf(f.sub) || (row ? String(row[5] || '') : ''), chapter: chapterName(f.sub),
            t: row && row[0] != null ? row[0] : null,
            text: f.text, kana: d.kana || (s[2] ? String(s[2]) : ''), tr: d.tr || (s[3] ? String(s[3]) : ''),
            en: d.en || (s[5] ? String(s[5]) : ''), voc: d.voc || flatVoc(s[4]), sentence: sentence};
  }
  // the vocabulary line as plain text, for a chunk the page has no row of
  function flatVoc(line) {
    if (!line) return '';
    try { if (window.ParsehVocline && ParsehVocline.flatten) return ParsehVocline.flatten(String(line), langRec()); } catch (e) {}
    return String(line);
  }
  function idOf(f) {
    return LT().idFor({kind: 'book', ref: ref, sub: f.key, k: f.k, text: f.text});
  }
  function isMarked(holder) {
    var f = factsOf(holder);
    return !!(f && LT().has(idOf(f)));
  }
  /* FLAG IT, OR TAKE THE FLAG OFF: the one thing every way to mark does.  A flag
     taken off carries the list's «removed · Undo» line; one made says so in a
     toast, since a chunk is marked without the pace of reading being broken. */
  function toggleHolder(holder) {
    var f = factsOf(holder);
    if (!f) { toast('this chunk cannot be marked here', true); return Promise.resolve(false); }
    var rec;
    try { rec = LT().record(partsOf(f)); }
    catch (e) { toast('this chunk cannot be marked: ' + e.message, true); return Promise.resolve(false); }
    return LT().toggle(rec).then(function (on) {
      if (on) toast('marked to review later');
      return on;
    }, function (e) { toast('could not mark it: ' + (e && e.message), true); return false; });
  }

  /* ================================================ WHERE A FLAGGED CHUNK IS */
  function subByKey(key, keyed) {
    if (!key) return null;
    if (keyed) return keyed.get(key) || null;
    return document.querySelector('.sub[data-key="' + key + '"]');
  }
  function inSub(sub, k, want) {
    var from = subFrom(sub), to = subTo(sub), first = from + k;
    if (first >= from && first <= to && textIn(sub, first) === want) return {n: first, sub: sub};
    var best = -1, gap = 1e9;
    for (var n = from; n <= to; n++) {
      if (textIn(sub, n) !== want) continue;
      var d = Math.abs(n - first);
      if (d < gap) { best = n; gap = d; }
    }
    return best >= 0 ? {n: best, sub: sub} : null;
  }
  function inPara(pkey, want, w) {
    var paras = document.querySelectorAll('.para[data-p="' + pkey + '"]'), any = null;
    for (var p = 0; p < paras.length; p++) {
      var subs = paras[p].querySelectorAll('.sub');
      for (var i = 0; i < subs.length; i++) {
        var hit = inSub(subs[i], w.k || 0, want);
        if (!hit) continue;
        if (labelOf(subs[i]) === (w.label || '')) return hit;
        if (!any) any = hit;
      }
    }
    return any;
  }
  /* The chunk of a flag in the page AS IT IS NOW -- chapters not yet fetched are
     not in it -- or null.  `keyed` is the page's subparagraphs by key, made once
     for a run of flags. */
  function resolveDom(rec, keyed) {
    var w = rec.where || {}, want = norm(rec.text), hit = null, sub = subByKey(w.sub, keyed);
    if (sub) hit = inSub(sub, w.k || 0, want);
    if (!hit && w.para) hit = inPara(w.para, want, w);
    return hit;
  }
  function chunkEls(hit) {
    return hit.sub.querySelectorAll('.w[data-c="' + hit.n + '"], .row[data-c="' + hit.n + '"] .fa');
  }
  // the chapter (the section's index) a flag's paragraph is in, from what the page knows of every chapter at once
  function chapterOf(rec) {
    var pkey = rec.where && rec.where.para;
    if (!pkey) return -1;
    var paras = parasAll(), subs = subsAll();
    if (paras && subs) {
      for (var i = 0; i < paras.length; i++)
        if (paras[i][0] === pkey && subs[paras[i][1]]) return +subs[paras[i][1]][2] || 0;
    }
    var a = document.querySelector('#toclist a.toce[data-p="' + pkey + '"]');
    return a ? (+a.getAttribute('data-ci') || 0) : -1;
  }
  function pendingChapters() {
    var out = [];
    Array.prototype.forEach.call(document.querySelectorAll('section.chapter[data-part]'), function (s) {
      var c = +s.getAttribute('data-ch') || 0;
      if (out.indexOf(c) < 0) out.push(c);
    });
    return out;
  }
  // the book's own copy of every chunk says whether this text is still in the chapter that has not come
  function srcHas(rec, ci) {
    var S = srcAll(), T = timesAll(), want = norm(rec.text);
    if (!S) return false;
    for (var n = 0; n < S.length; n++) {
      if (ci >= 0 && T && T[n] && (+T[n][3] || 0) !== ci) continue;
      if (S[n] && norm(S[n][1]) === want) return true;
    }
    return false;
  }
  /* Where a flag is, fetching its chapter if it must: Promise<{n, sub}|null>. */
  function findChunk(rec, fetchIt) {
    var hit = resolveDom(rec);
    if (hit || !fetchIt || typeof needChapters !== 'function') return Promise.resolve(hit);
    var ci = chapterOf(rec), pending = pendingChapters();
    var todo = ci >= 0 ? (pending.indexOf(ci) >= 0 ? [ci] : []) : pending;
    var chain = Promise.resolve(null);
    todo.forEach(function (c) {
      chain = chain.then(function (got) {
        if (got) return got;
        return Promise.resolve(needChapters(c)).then(function () { return resolveDom(rec); });
      });
    });
    return chain;
  }
  function locate(rec) {
    if (resolveDom(rec)) return Promise.resolve({found: true});
    var ci = chapterOf(rec), pending = pendingChapters();
    if (ci >= 0 ? pending.indexOf(ci) < 0 : !pending.length) return Promise.resolve({found: false});
    if (srcHas(rec, ci)) return Promise.resolve({found: true});
    return findChunk(rec, true).then(function (h) { return {found: !!h}; });
  }

  /* ============================================================== GOING THERE */
  function visibleOf(els) {
    for (var i = 0; i < els.length; i++) if (els[i].getClientRects().length > 0) return els[i];
    return null;
  }
  /* THE READING PLACE, as the book's own jumps leave it: the subparagraph marked
     and saved, nothing played -- the narration goes on only when it was already
     playing, and then from the chunk, since a recording playing on elsewhere
     would take the place straight back. */
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
  function land(hit) {
    var els = chunkEls(hit), target = visibleOf(els) || hit.sub;
    // a chunk in a run folded away is shown (not unfolded) as the contents' jump shows it
    try {
      if (typeof reveal === 'function') reveal(target, 'center', 'auto');
      else target.scrollIntoView({block: 'center'});
    } catch (e) { target.scrollIntoView({block: 'center'}); }
    setPlace(+hit.sub.getAttribute('data-s'));
    flash(els);
  }
  function lost() {
    // the page now holds the chapter, and the chunk is not in it: the list says so on its row
    if (panelHandle) panelHandle.refresh();
    return new Error('this chunk is no longer where it was');
  }
  function goTo(rec) {
    return findChunk(rec, true).then(function (hit) {
      if (!hit) throw lost();
      land(hit);
    });
  }

  /* ================================================================ THE MARKS
     A dotted line under every flagged chunk, kept in step with the store, with
     the chapters as they arrive and with a chunk drawn again.  The class is on
     the elements and the text is never touched, which is why Diacritics, the
     highlight and the colours do not know of it. */
  var paintFrame = 0;
  function paint() {
    paintFrame = 0;
    if (!readerHas()) return;
    var recs = LT().list({ref: ref}), keyed = null, want = [];
    if (recs.length) {
      keyed = new Map();
      Array.prototype.forEach.call(document.querySelectorAll('.sub[data-key]'), function (s) {
        keyed.set(s.getAttribute('data-key'), s);
      });
    }
    recs.forEach(function (rec) {
      var hit = resolveDom(rec, keyed);
      if (hit) Array.prototype.forEach.call(chunkEls(hit), function (e) { want.push(e); });
    });
    var keep = new Set(want);
    Array.prototype.forEach.call(document.querySelectorAll('.later-mark'), function (e) {
      if (!keep.has(e)) e.classList.remove('later-mark');
    });
    want.forEach(function (e) { if (!e.classList.contains('later-mark')) e.classList.add('later-mark'); });
    paintCloudButton();
    paintFlag();
  }
  function schedulePaint() {
    if (!paintFrame) paintFrame = requestAnimationFrame(paint);
  }
  // a chapter arrived, or a chunk was drawn again: the page's own markup changed under the marks
  function watchMarks() {
    var main = document.querySelector('main');
    if (!main || !window.MutationObserver) return;
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === 'attributes') { schedulePaint(); return; }
        for (var j = 0; j < m.addedNodes.length; j++) {
          var n = m.addedNodes[j];
          if (n.nodeType === 1 && (n.matches('.sub, .para, .pass, .row, .w, section.chapter') ||
                                   (n.querySelector && n.querySelector('.sub, .row, .w[data-c]')))) { schedulePaint(); return; }
        }
      }
    }).observe(main, {childList: true, subtree: true, attributes: true, attributeFilter: ['data-part']});
  }

  /* ========================================================= THE CLOUD'S BUTTON */
  function cloudHolder() {
    try {
      if (typeof cloudC !== 'number' || cloudC < 0) return null;
      if (typeof cloudFor !== 'undefined' && cloudFor && cloudFor.isConnected) return holderOf(cloudFor);
      return document.querySelector('.p1 .w[data-c="' + cloudC + '"]');
    } catch (e) { return null; }
  }
  function paintCloudButton() {
    var b = document.querySelector('#cloud .mklater');
    if (!b) return;
    var h = cloudHolder(), on = !!(h && isMarked(h));
    b.textContent = on ? '✓ marked' : 'review later';
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.title = on ? 'this chunk is on your review later list: press to take it off'
                 : 'flag this chunk to come back to it later (L)';
  }
  /* The cloud is the reader's, filled afresh every time it opens (fillCloud ends
     with its row of buttons), so the button is put into the row each time, as
     lib/mobilereader.js puts the dictionary's -- at the end, after whatever the
     page and the mobile layer have put there. */
  function addCloudButton() {
    var cloud = document.getElementById('cloud'), row = cloud && cloud.querySelector('.mkrow');
    if (!row || row.querySelector('.mklater')) return;
    var b = el('button', 'mklater');
    b.type = 'button';
    row.appendChild(b);
    paintCloudButton();
    if (typeof refitCloud === 'function') { try { refitCloud(b); } catch (e) {} }
  }
  function watchCloud() {
    var cloud = document.getElementById('cloud');
    if (!cloud || !window.MutationObserver) return;
    new MutationObserver(addCloudButton).observe(cloud, {childList: true});
    cloud.addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('.mklater') : null;
      if (!b || !cloud.contains(b)) return;
      var h = cloudHolder();
      if (h) toggleHolder(h);
    });
    addCloudButton();
  }

  /* ================================================================= THE L KEY
     The chunk the open cloud is for; else the chunk under the pointer; else the
     one the pencil last stood at (a touch screen has no pointer to follow);
     else a word saying what to do.  Heard first of all, on the window, as the
     mobile layer hears E -- and not while a field has the keys, a sheet is over
     the page, or a modifier is down. */
  var px = null, py = null, mouseSeen = false;
  window.addEventListener('pointermove', function (e) {
    if (e.pointerType && e.pointerType !== 'mouse') return;
    mouseSeen = true; px = e.clientX; py = e.clientY;
  }, {passive: true, capture: true});
  function chunkUnderPointer() {
    if (mouseSeen && px !== null) {
      var h = holderOf(document.elementFromPoint(px, py));
      if (h) return h;
    }
    try { if (typeof penFor !== 'undefined' && penFor && penFor.isConnected) return holderOf(penFor); } catch (e) {}
    return null;
  }
  function onKey(e) {
    if ((e.key !== 'l' && e.key !== 'L') || e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
    if (isField(e.target) || sheetOpen()) return;
    if (e.target && e.target.closest && e.target.closest('.lp-wrap')) return;
    var h = cloudHolder() || chunkUnderPointer();
    e.preventDefault();
    if (!h) { toast('point at a chunk first, then press L'); return; }
    toggleHolder(h);
  }

  /* ============================================= THE ⚑ BESIDE THE PENCIL (#chpen)
     The reader's pencil goes with the chunk under the pointer (penAt, penPlace), at
     any level but pass 1 in hover mode, whose cloud has the button instead.  This
     is a second small button that stands to the left of it, wherever it is, and
     is for the same chunk -- one click flags it or takes the flag off.  Browser
     layout only: a phone has no pencil (lib/mobile.css), and flags by a held finger. */
  var flag = null, flagFor = null, flagHeld = false, flagTimer = null;
  function paintFlag() {
    if (!flag) return;
    var on = !!(flagFor && flagFor.isConnected && isMarked(flagFor));
    flag.classList.toggle('on', on);
    flag.setAttribute('aria-pressed', on ? 'true' : 'false');
    flag.textContent = on ? '✓⚑' : '⚑';
    flag.title = on ? 'on your review later list: click to take it off' : 'review later: flag this chunk (L)';
    // the glyph says nothing to a screen reader
    flag.setAttribute('aria-label', on ? 'this chunk is on your review later list: take it off' : 'flag this chunk to review later');
  }
  function flagPlace() {
    var pen = document.getElementById('chpen');
    if (!flag || !pen) return;
    if (pen.hidden || mobile()) {
      // the pencil has gone; this stays only for a pointer that has reached it
      if (!flagHeld) flag.hidden = true;
      return;
    }
    var holder = null;
    try { holder = typeof penFor !== 'undefined' ? penFor : null; } catch (e) {}
    // a chunk with no box (its level put away since the pencil came to it) has no corner to stand at
    if (!holder || !holder.isConnected || !holder.getClientRects().length) { if (!flagHeld) flag.hidden = true; return; }
    flagFor = holder;
    flag.hidden = false;
    paintFlag();
    var r = pen.getBoundingClientRect();
    flag.style.top = r.top + 'px';
    flag.style.left = Math.max(0, r.left - flag.offsetWidth - 4) + 'px';
  }
  function buildFlag() {
    var pen = document.getElementById('chpen');
    if (!pen || flag) return;
    flag = el('button', 'later-flag', '⚑');
    flag.type = 'button';
    flag.hidden = true;
    flag.setAttribute('lang', 'en');
    document.body.appendChild(flag);
    // the pointer on this button is on the chunk's door, as on the pencil: the page's
    // own mouseover (which would start the pencil's grace) never hears of it
    flag.addEventListener('mouseover', function (e) { e.stopPropagation(); });
    flag.addEventListener('mouseenter', function () { flagHeld = true; clearTimeout(flagTimer); });
    flag.addEventListener('mouseleave', function () {
      flagHeld = false;
      clearTimeout(flagTimer);
      flagTimer = setTimeout(flagPlace, 350);
    });
    flag.addEventListener('click', function (e) {
      // as the pencil's own click: the page's "a tap elsewhere puts the pencil away" is not for this
      e.preventDefault(); e.stopPropagation();
      if (flagFor && flagFor.isConnected) toggleHolder(flagFor);
    });
    if (window.MutationObserver)
      new MutationObserver(flagPlace).observe(pen, {attributes: true, attributeFilter: ['hidden', 'style']});
  }

  /* ============================================================ THE HELD FINGER
     lib/wordtouch.js adds a line for what a hold on a chunk can do, if this says
     it can: the chunk is the `.w` or the row's `.fa` the menu is for. */
  window.ParsehLaterMark = {
    can: function (unit) { return !!(LT() && ref && readerHas() && holderOf(unit)); },
    marked: function (unit) { var h = holderOf(unit); return !!(h && isMarked(h)); },
    toggle: function (unit) { var h = holderOf(unit); return h ? toggleHolder(h) : Promise.resolve(false); }
  };

  /* ================================================================ THE CARDS
     The sheet is the reader's own (openAnki), opened as the cloud's «+ card» opens
     it, for a chunk whose chapter has been brought.  What the person did with it
     is told by the sheet's own doors, which are wrapped, not copied:
       - press(), which every one of the three saves goes through, hands back the
         object whose done(used) says the answer is in; `used` is true for a card
         that was saved -- and for a markdown card that could NOT be put on the
         clipboard and is left on the sheet to copy by hand, which is no save, so
         the clipboard's own answer (ParsehCards.copy) is asked as well;
       - the sheet being put away (its `hidden`) is how a sheet shut without a
         card ends, unless a press is still out, whose answer is then waited for. */
  var session = null, lastCopy = null;
  function cardSession(seq) {
    var s = {seq: seq, over: false, out: false, late: false};
    s.box = document.getElementById('anki');
    s.done = new Promise(function (resolve) {
      s.finish = function (how) {
        if (s.over) return;
        s.over = true;
        if (session === s) session = null;
        resolve(how);
      };
    });
    s.close = function () {
      try {
        if (typeof closeAnki === 'function' && typeof ankiOpen !== 'undefined' && ankiOpen &&
            (typeof sheetSeq !== 'number' || sheetSeq === seq)) closeAnki();
      } catch (e) {}
    };
    return s;
  }
  function pressStarted(seq, target) {
    lastCopy = null;
    if (session && session.seq === seq) session.out = true;
    return target;
  }
  function pressDone(seq, target, used) {
    var s = session;
    if (!s || s.seq !== seq) return;
    s.out = false;
    var saved = used === true && (target !== 'md' || lastCopy === true);
    if (saved) s.finish('saved');
    else if (s.late) s.finish('closed');
  }
  function hookCards() {
    if (typeof press === 'function' && !window.press.__laterHooked) {
      var was = window.press;
      var wrapped = function () {
        var p = was.apply(this, arguments), seq = -1, target = '';
        try {
          seq = typeof sheetSeq === 'number' ? sheetSeq : -1;
          target = pressStarted(seq, typeof cardTo === 'string' ? cardTo : '');
          var done = p && p.done;
          if (typeof done === 'function') {
            p.done = function (used) {
              var r = done.apply(this, arguments);
              try { pressDone(seq, target, used); } catch (e) {}
              return r;
            };
          }
        } catch (e) {}
        return p;
      };
      wrapped.__laterHooked = true;
      window.press = wrapped;
    }
    var K = window.ParsehCards;
    if (K && typeof K.copy === 'function' && !K.copy.__laterHooked) {
      var copy = K.copy;
      var copied = function () {
        var r = copy.apply(this, arguments);
        if (r && typeof r.then === 'function') return r.then(function (ok) { lastCopy = ok === true; return ok; });
        return r;
      };
      copied.__laterHooked = true;
      K.copy = copied;
    }
    var box = document.getElementById('anki');
    if (box && window.MutationObserver && !box.__laterWatched) {
      box.__laterWatched = true;
      new MutationObserver(function () {
        var s = session;
        if (!s || !box.hidden) return;
        // shut: ended now, unless a press is out -- its answer ends it
        if (s.out) s.late = true; else s.finish('closed');
      }).observe(box, {attributes: true, attributeFilter: ['hidden']});
    }
  }
  function cardsReady() {
    try {
      return !!(window.ParsehLaterCards && typeof openAnki === 'function' && typeof rowOf === 'function' &&
                document.getElementById('anki'));
    } catch (e) { return false; }
  }
  /* The page's session for a flag: its chunk brought, the sheet open on it, and how it ended. */
  function openSheetFor(rec) {
    return findChunk(rec, true).then(function (hit) {
      if (!hit) { lost(); return null; }
      hookCards();
      var d = null;
      try { d = chunkData(hit.n); } catch (e) {}
      var from = hit.sub.querySelector('.row[data-c="' + hit.n + '"]') || hit.sub;
      if (session) session.finish('closed');
      openAnki(d && d.fa ? d.fa : textIn(hit.sub, hit.n) || rec.text, hit.n, from);
      session = cardSession(typeof sheetSeq === 'number' ? sheetSeq : -1);
      // the sheet may have been opened and put away again before this ran
      return session;
    });
  }

  /* The same session for any chunk by its number, its chapter brought first --
     what the vocabulary list (lib/vocab-reader.js) makes a word's card with:
     the sheet opened on `word`, and `fill` then given the chance to put the
     word's own romanisation and meaning in its fields. */
  function sheetAt(n, word, fill) {
    var find = function () {
      var e = document.querySelector('.sub [data-c="' + n + '"]');
      return e ? {n: n, sub: e.closest('.sub')} : null;
    };
    var hit = find();
    var got = hit ? Promise.resolve(hit) : Promise.resolve().then(function () {
      var ci = 0;
      try { ci = (TIMES[n] && TIMES[n][3]) || 0; } catch (e) {}
      return needChapters(ci);
    }).then(find);
    return got.then(function (h) {
      if (!h) return null;
      hookCards();
      var from = h.sub.querySelector('.row[data-c="' + n + '"]') || h.sub;
      if (session) session.finish('closed');
      openAnki(word, n, from);
      try { if (fill) fill(); } catch (e) {}
      session = cardSession(typeof sheetSeq === 'number' ? sheetSeq : -1);
      return session;
    });
  }

  /* ================================================================= THE LIST */
  function adapterOf() {
    var L = langRec(), G = glossRec();
    return {
      kind: 'book', ref: ref, title: bookTitle(), lang: L ? L.code : '', glossLang: G ? G.code : '',
      // never on a phone, and only where the page has the card sheet
      canCard: function () { return !mobile() && cardsReady(); },
      locate: locate,
      goTo: goTo,
      makeCard: function (rec) {
        return window.ParsehLaterCards ? ParsehLaterCards.one(openSheetFor, rec)
                                       : Promise.reject(new Error('cards are not available here'));
      },
      queue: function (recs) {
        return window.ParsehLaterCards ? ParsehLaterCards.queue({records: recs, open: openSheetFor})
                                       : Promise.reject(new Error('cards are not available here'));
      }
    };
  }
  /* THE DOOR, «⚑ later 3»: in the header's second row after «contents» in the
     browser layout, and on a phone on the first line (lib/mobile.css) -- where it
     is drawn only once there is something flagged, since the first line has room
     for six targets of a finger's size and this makes seven. */
  function placeButton(btn) {
    var toc = document.getElementById('toc');
    if (toc && toc.parentNode) toc.parentNode.insertBefore(btn, toc.nextSibling);
    else {
      var h = document.querySelector('header');
      if (h) h.appendChild(btn);
    }
  }
  function paintDoor(btn) {
    btn.hidden = mobile() && LT().count({ref: ref}) === 0;
  }
  // the list and the contents are both panels on the right: one at a time
  function watchContents() {
    var wrap = document.getElementById('tocwrap');
    if (!wrap || !panelHandle) return;
    if (window.MutationObserver) {
      new MutationObserver(function () { if (!wrap.hidden && panelHandle.isOpen()) panelHandle.close('contents'); })
        .observe(wrap, {attributes: true, attributeFilter: ['hidden']});
    }
    panelHandle.onToggle(function (open) {
      try { if (open && !wrap.hidden && typeof tocOpen === 'function') tocOpen(false, true); } catch (e) {}
    });
  }

  /* ONE LINK OPENS THE BOOK AT A CHUNK: <reader>#later=<id>, from the page that lists
     every flag.  The list opens on that flag and the reader goes to its chunk -- after
     the reader has put its own reading place back (which it does a moment after load,
     and which would otherwise take the page away again). */
  function fromLink() {
    var id = LT().fromHash();
    if (!id) return;
    LT().ready().then(function () {
      var rec = LT().get(id);
      if (!rec || rec.ref !== ref) { toast('that chunk is no longer on your review later list', true); return; }
      var tries = 0;
      (function go() {
        var settled = true;
        try { settled = typeof autoscroll === 'undefined' || autoscroll === true; } catch (e) {}
        if (!settled && tries++ < 60) { setTimeout(go, 50); return; }
        panelHandle.open({id: id});
        goTo(rec).catch(function () {});
      })();
    });
  }

  /* ================================================================== STARTING */
  function start() {
    var lt = LT();
    ref = lt && lt.refOf ? lt.refOf(location.pathname) : null;
    if (!lt || !ref || !readerHas()) return;
    panelHandle = lt.panel(adapterOf());
    placeButton(panelHandle.button);
    paintDoor(panelHandle.button);
    watchContents();
    watchCloud();
    buildFlag();
    watchMarks();
    hookCards();
    window.addEventListener('keydown', onKey, true);
    lt.on('change', function (d) {
      if (d && d.ref && d.ref !== ref) return;
      paintDoor(panelHandle.button);
      schedulePaint();
    });
    var p = P();
    if (p && p.mode && p.mode.onChange) p.mode.onChange(function () { paintDoor(panelHandle.button); flagPlace(); });
    paint();
    // the computer's list may hold what this device has not seen
    lt.ready().then(function () { paintDoor(panelHandle.button); paint(); });
    fromLink();
    window.ParsehLaterReader.panel = panelHandle;
    window.ParsehLaterReader.paint = paint;
    window.ParsehLaterReader.locate = locate;
    window.ParsehLaterReader.goTo = goTo;
    window.ParsehLaterReader.sheetAt = sheetAt;
    window.ParsehLaterReader.cardsReady = cardsReady;
    window.ParsehLaterReader.record = function (node) { var f = factsOf(holderOf(node)); return f ? partsOf(f) : null; };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
