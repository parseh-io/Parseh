// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — THE VOCABULARY of a chapter, a book or a video as a list (a0.6.3, TO-DO 11.14).

   Every word the vocabulary lines of what is open give, once: the word in its
   script (a verb with its stems, as the reader prints it), its romanisation,
   its meaning or meanings, and how many times it is there.  A click goes to
   the first place it is; another click to the next, and round again.  The list
   is ordered as the words come, A–Z in the language's own order, or by how
   often they come; it has a filter, Test myself (the meanings hidden), Copy
   (tab-separated: word, romanisation, meaning), Print, and the cards made one
   after another (lib/later-cards.js).

   NOTHING IS STORED: the list is read from what the page holds each time it is
   opened, and nothing is written into the book or the video.  The panel is the
   one Review later draws (lib/later.css: a right-hand panel on a computer, a
   sheet from the foot on a phone), so it looks and closes the same way.

   A LINE IS CUT INTO ENTRIES by lib/vocline.js (ParsehVocline.entries, held
   equal to lib/texparse.py's voc_entries): each \dw \vb \bw, and a \pw that
   opens a stretch of the line, is a word; what follows it up to the next `;`
   is its meaning.  TWO ENTRIES ARE ONE WORD when their written form is the
   same after ParsehVocline.key (NFC, the marks and the zero-width joiners off,
   Persian's ي ك as ی ک, Turkish's i's, lower case); a verb by its first form.
   A plain-text line (a video glossed before the macros) has no entries.

   WHAT A PAGE HANDS IN, ParsehVocab.panel(adapter):
     { kind: 'book' | 'video', lang: the registry record (LANG),
       title: () => the book's or video's name, for the print,
       scopes: [{id, label}], scope: () => the one to open on,
       chunks: scope => [{at, voc}] (or a promise of it), in reading order --
               `at` is the page's own address of the chunk, handed back below,
       goTo: at => promise (the page goes there and lights the chunk),
       card: {can: () => bool, open: (word, at) => a later-cards session} or null,
       mount: button => where the door goes }
   and gets back {button, open(), close(), toggle(), isOpen(), onToggle(fn)}.

   ParsehVocab.gather(chunks, lang) is the list itself, a pure function: the
   words in the order they come, each {key, word, rom, head, meanings, count,
   at: [addresses], first}. */
(function () {
  'use strict';
  if (window.ParsehVocab) return;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function button(cls, text, title, on) {
    var b = el('button', cls, text);
    b.type = 'button';
    if (title) b.title = title;
    if (on) b.addEventListener('click', on);
    return b;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function phone() {
    try { if (window.Parseh && Parseh.mode && Parseh.mode.isMobile()) return true; } catch (e) {}
    return !!(window.matchMedia && matchMedia('(max-width: 560px)').matches);
  }
  function copyText(text) {
    if (window.Parseh && Parseh.copy) return Promise.resolve(Parseh.copy(text, true));
    var p = (navigator.clipboard && navigator.clipboard.writeText)
      ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard API'));
    return p.then(function () { return true; }).catch(function () {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return !!ok;
      } catch (e) { return false; }
    });
  }
  function addrId(at) { return JSON.stringify(at); }
  function meaningKey(m) { return String(m).replace(/\s+/g, ' ').trim().toLowerCase(); }

  /* =========================================================== THE LIST */
  function gather(chunks, lang) {
    var V = window.ParsehVocline, words = [], byKey = {};
    if (!V || !V.entries) return words;
    (chunks || []).forEach(function (c) {
      var es;
      try { es = V.entries(c.voc || '', lang); } catch (e) { return; }
      es.forEach(function (e) {
        if (!e.key) return;
        var w = byKey[e.key];
        if (!w) {
          w = byKey[e.key] = {key: e.key, word: e.word, rom: e.rom, head: e.head, kind: e.kind,
                              meanings: [], seen: {}, count: 0, at: [], ats: {}, first: words.length};
          words.push(w);
        } else if ((e.kind === 'vb' && w.kind !== 'vb') || (!w.rom && e.rom && (w.kind !== 'vb' || e.kind === 'vb'))) {
          // the fuller form of the word where a later entry has it: a verb's stems, a romanisation
          w.word = e.word; w.rom = e.rom; w.head = e.head; w.kind = e.kind;
        }
        w.count++;
        var m = e.meaning, mk = meaningKey(m);
        if (mk && !w.seen[mk]) { w.seen[mk] = 1; w.meanings.push(m); }
        var id = addrId(c.at);
        if (!w.ats[id]) { w.ats[id] = 1; w.at.push(c.at); }
      });
    });
    words.forEach(function (w) { delete w.seen; delete w.ats; });
    return words;
  }
  function meaningOf(w) { return w.meanings.join(' · '); }
  // A–Z in the language's own order; Japanese by the reading the line gives
  // (kanji have no order of their own a learner would know), every other
  // language by the word as written -- Chinese is ordered by its pinyin by the
  // collator itself
  function sorter(lang, how) {
    var code = (lang && lang.code) || 'en', coll;
    try { coll = new Intl.Collator(code, {sensitivity: 'base', numeric: true}); }
    catch (e) { coll = new Intl.Collator(undefined, {sensitivity: 'base'}); }
    var byWord = function (w) { return lang && lang.reading && w.rom ? w.rom : w.word; };
    if (how === 'az') return function (a, b) { return coll.compare(byWord(a), byWord(b)) || a.first - b.first; };
    if (how === 'freq') return function (a, b) { return b.count - a.count || a.first - b.first; };
    return function (a, b) { return a.first - b.first; };
  }

  /* the word as the reader prints it: the language's runs isolated with its
     code and direction, the romanisation in italics, the labels as text --
     joined by lib/vocline.js's rule (no space before closing punctuation) */
  function headEl(w, lang) {
    var box = el('span', 'vr-head');
    box.setAttribute('lang', (lang && lang.code) || '');
    box.setAttribute('dir', (lang && lang.dir) || 'ltr');
    var prev = '', first = true;
    (w.head && w.head.length ? w.head : [['fa', w.word]]).forEach(function (r) {
      var t = r[1];
      if (!first && !/[ (‘\/]$/.test(prev) && !/^[ ,;).’:\/]/.test(t)) box.appendChild(document.createTextNode(' '));
      var n;
      if (r[0] === 'fa') { n = el('bdi', 'vr-w', t); n.setAttribute('lang', lang.code); n.setAttribute('dir', lang.dir); }
      else if (r[0] === 'em') { n = el('bdi', 'vr-rom', t); n.setAttribute('dir', 'ltr'); n.setAttribute('lang', 'und-Latn'); }
      else { n = el('bdi', 'vr-lab', t); n.setAttribute('dir', 'ltr'); n.setAttribute('lang', 'en'); }
      box.appendChild(n);
      prev = t;
      first = false;
    });
    return box;
  }

  /* ============================================================ THE PANEL */
  var ORDERS = [['seen', 'As they come', 'in the order they first come'],
                ['az', 'A–Z', 'in the order of the alphabet'],
                ['freq', 'Most frequent', 'the words that come most often first']];
  function panel(ad) {
    var open = false, wrap = null, box = null, toggles = [], sheet = false, entry = null, spent = 0, opener = null;
    var scope = null, order = get('parseh_vocab_order') || 'seen', filter = '', testing = false, shown = {};
    var words = [], next = {}, loading = 0, unreadable = false, nLines = 0;
    if (!ORDERS.some(function (o) { return o[0] === order; })) order = 'seen';
    var lang = ad.lang || {code: '', dir: 'ltr'};

    var btn = el('button', 'vocab-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('lang', 'en');
    btn.title = 'Vocabulary: every word of the vocabulary lines of this ' + (ad.kind === 'video' ? 'video' : 'chapter or book') + ' (V)';
    btn.appendChild(el('span', 'vb-word', 'vocabulary'));
    btn.addEventListener('click', function () { handle.toggle(); });

    var head, title, countEl, closer, tools, scopeBox, scopeBtns = {}, orderBtns = {}, find, status, body, list;
    var testBtn, copyBtn, printBtn, cardsBtn;
    function build() {
      if (wrap) return;
      wrap = el('div', 'lp-wrap vocab-wrap');
      wrap.hidden = true;
      var back = el('div', 'lp-back');
      back.addEventListener('click', function () { handle.close('backdrop'); });
      box = el('div', 'lp-panel vocab-panel');
      box.setAttribute('role', 'dialog');
      box.setAttribute('aria-label', 'Vocabulary');
      box.setAttribute('lang', 'en');
      box.setAttribute('dir', 'ltr');
      box.tabIndex = -1;
      head = el('div', 'lp-head');
      head.appendChild(el('span', 'lp-grip'));
      title = el('h2', 'lp-title', 'Vocabulary');
      head.appendChild(title);
      countEl = el('span', 'lp-count');
      countEl.setAttribute('aria-hidden', 'true');
      head.appendChild(countEl);
      closer = button('lp-x', '✕', 'close (Esc)', function () { handle.close('button'); });
      closer.setAttribute('aria-label', 'close the vocabulary');
      head.appendChild(closer);
      box.appendChild(head);

      var view = el('div', 'lp-view');
      tools = el('div', 'lp-tools');
      scopeBox = el('div', 'lp-scope vocab-scope');
      scopeBox.setAttribute('role', 'group');
      scopeBox.setAttribute('aria-label', 'which words');
      (ad.scopes || []).forEach(function (s) {
        var b = button('lp-sc', s.label, null, function () { setScope(s.id); });
        scopeBtns[s.id] = b;
        scopeBox.appendChild(b);
      });
      tools.appendChild(scopeBox);
      var orderBox = el('div', 'lp-scope vocab-order');
      orderBox.setAttribute('role', 'group');
      orderBox.setAttribute('aria-label', 'order');
      ORDERS.forEach(function (o) {
        var b = button('lp-sc', o[1], o[2], function () { order = o[0]; put('parseh_vocab_order', order); draw(); });
        orderBtns[o[0]] = b;
        orderBox.appendChild(b);
      });
      tools.appendChild(orderBox);
      find = el('input', 'vocab-find');
      find.type = 'search';
      find.placeholder = 'Filter: a word, a romanisation or a meaning';
      find.setAttribute('aria-label', 'filter the words');
      find.setAttribute('autocomplete', 'off');
      find.setAttribute('spellcheck', 'false');
      find.addEventListener('input', function () { filter = find.value; saying = ''; draw(); });
      tools.appendChild(find);
      var row = el('div', 'lp-row');
      testBtn = button('lp-b vocab-test', 'Test myself', 'hide the meanings, and tap a word to see its own', function () {
        testing = !testing; shown = {}; draw();
      });
      copyBtn = button('lp-b vocab-copy', 'Copy', 'copy these words as a table: word, romanisation, meaning, separated by tabs', copyList);
      printBtn = button('lp-b vocab-print-btn', 'Print', 'print these words as a table', printList);
      cardsBtn = button('lp-b vocab-cards', 'Make cards one after another', 'open the card sheet for each of these words in turn', makeCards);
      row.appendChild(testBtn); row.appendChild(copyBtn); row.appendChild(printBtn); row.appendChild(cardsBtn);
      tools.appendChild(row);
      status = el('p', 'lp-status');
      status.setAttribute('role', 'status');
      tools.appendChild(status);
      body = el('div', 'lp-body');
      list = el('ul', 'lp-items vocab-list');
      body.appendChild(list);
      view.appendChild(tools);
      view.appendChild(body);
      box.appendChild(view);
      wrap.appendChild(back);
      wrap.appendChild(box);
      (document.body || document.documentElement).appendChild(wrap);
      box.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab' || !sheet || e.altKey || e.ctrlKey || e.metaKey) return;
        var all = box.querySelectorAll('button, input, a[href], [tabindex]:not([tabindex="-1"])');
        var can = Array.prototype.filter.call(all, function (x) { return !x.disabled && x.getClientRects().length > 0; });
        if (!can.length) return;
        var i = can.indexOf(document.activeElement);
        e.preventDefault();
        var nx = e.shiftKey ? (i <= 0 ? can[can.length - 1] : can[i - 1]) : (i < 0 || i === can.length - 1 ? can[0] : can[i + 1]);
        nx.focus();
      });
    }

    /* ---- what is listed */
    var sayTimer = null, saying = '';
    function say(t) { saying = t; clearTimeout(sayTimer); sayTimer = setTimeout(function () { saying = ''; paintStatus(); }, 5000); paintStatus(); }
    function shownWords() {
      var f = filter.replace(/\s+/g, ' ').trim(), V = window.ParsehVocline, out = words;
      if (f) {
        var fk = V && V.key ? V.key(f, lang) : f.toLowerCase(), fl = f.toLowerCase();
        out = out.filter(function (w) {
          return w.key.indexOf(fk) >= 0 || (w.rom || '').toLowerCase().indexOf(fl) >= 0 ||
                 meaningOf(w).toLowerCase().indexOf(fl) >= 0;
        });
      }
      return out.slice().sort(sorter(lang, order));
    }
    function paintStatus() {
      if (!status) return;
      var n = shownWords().length, t;
      if (saying) t = saying;
      else if (loading) t = 'reading the vocabulary lines…';
      else if (!words.length) t = nLines && unreadable ? 'The vocabulary lines here are plain text, with no \\dw or \\vb to cut them into words.'
                                                       : 'There are no vocabulary lines here.';
      else if (n < words.length) t = plural(n, 'word') + ' of ' + words.length + ' match the filter';
      else {
        var times = 0;
        words.forEach(function (w) { times += w.count; });
        t = plural(words.length, 'word') + ', ' + plural(times, 'entry', 'entries') + ' in all';
      }
      status.textContent = t;
    }
    function rowEl(w) {
      var li = el('li', 'vr');
      li.setAttribute('data-key', w.key);
      var go = button('vr-go', null, w.at.length > 1 ? 'go to where it is; again for the next place (' + w.at.length + ' places)'
                                                    : 'go to where it is', function () { goTo(w); });
      go.appendChild(headEl(w, lang));
      var n = el('span', 'vr-n', '×' + w.count);
      n.setAttribute('aria-label', plural(w.count, 'time'));
      go.appendChild(n);
      li.appendChild(go);
      var m = meaningOf(w);
      if (testing && !shown[w.key]) {
        var reveal = button('vr-show', 'show the meaning', null, function () { shown[w.key] = true; draw(); });
        li.appendChild(reveal);
      } else {
        var mean = el('div', 'vr-mean', m || '—');
        if (!m) mean.classList.add('vr-none');
        li.appendChild(mean);
      }
      return li;
    }
    function draw() {
      if (!wrap) return;
      Object.keys(scopeBtns).forEach(function (k) { scopeBtns[k].setAttribute('aria-pressed', scope === k ? 'true' : 'false'); });
      Object.keys(orderBtns).forEach(function (k) { orderBtns[k].setAttribute('aria-pressed', order === k ? 'true' : 'false'); });
      testBtn.setAttribute('aria-pressed', testing ? 'true' : 'false');
      cardsBtn.hidden = !(ad.card && ad.card.can() && window.ParsehLaterCards && words.length);
      var ws = shownWords();
      countEl.textContent = words.length ? String(ws.length) : '';
      while (list.firstChild) list.removeChild(list.firstChild);
      var frag = document.createDocumentFragment();
      ws.forEach(function (w) { frag.appendChild(rowEl(w)); });
      list.appendChild(frag);
      copyBtn.disabled = printBtn.disabled = testBtn.disabled = !ws.length;
      paintStatus();
    }
    function load() {
      var my = ++loading;
      paintStatus();
      return Promise.resolve().then(function () { return ad.chunks(scope); }).then(function (chunks) {
        if (my !== loading) return;
        loading = 0;
        nLines = 0;
        (chunks || []).forEach(function (c) { if (c.voc && String(c.voc).trim()) nLines++; });
        words = gather(chunks, lang);
        unreadable = !words.length && nLines > 0;
        next = {};
        draw();
      }, function () {
        if (my !== loading) return;
        loading = 0;
        words = [];
        draw();
        say('the vocabulary could not be read');
      });
    }
    function setScope(id) {
      scope = id;
      testing = false; shown = {};
      put('parseh_vocab_scope_' + ad.kind, id);
      load();
    }

    /* ---- going there: the first place, then the next, and round again */
    function goTo(w) {
      var k = next[w.key] || 0;
      if (k >= w.at.length) k = 0;
      next[w.key] = k + 1;
      var at = w.at[k];
      return Promise.resolve().then(function () { return ad.goTo(at); }).then(function () {
        say('‘' + w.word + '’' + (w.at.length > 1 ? ': place ' + (k + 1) + ' of ' + w.at.length : ''));
        if (sheet) handle.close('go');
      }, function () { say('could not go there'); });
    }

    /* ---- the tools */
    function tsv(ws) {
      var one = function (s) { return String(s == null ? '' : s).replace(/[\t\r\n]+/g, ' ').trim(); };
      return ws.map(function (w) { return [one(w.word), one(w.rom), one(meaningOf(w))].join('\t'); }).join('\n') + '\n';
    }
    function copyList() {
      var ws = shownWords();
      copyText(tsv(ws)).then(function (ok) {
        say(ok ? 'copied ' + plural(ws.length, 'word') + ' as a table' : 'the clipboard is not available here');
      });
    }
    function scopeLabel() {
      var s = (ad.scopes || []).filter(function (x) { return x.id === scope; })[0];
      return s ? s.label : '';
    }
    function printList() {
      var ws = shownWords(), sheetEl = el('div', 'vocab-print');
      sheetEl.setAttribute('lang', 'en');
      var name = '';
      try { name = ad.title ? ad.title() : ''; } catch (e) {}
      sheetEl.appendChild(el('h1', null, 'Vocabulary' + (name ? ' — ' + name : '')));
      sheetEl.appendChild(el('p', null, scopeLabel() + ' · ' + plural(ws.length, 'word') + (filter.trim() ? ' · filter: ' + filter.trim() : '')));
      var table = el('table'), tb = el('tbody');
      ws.forEach(function (w) {
        var tr = el('tr'), a = el('td', 'vp-w'), b = el('td', 'vp-m', testing ? '' : meaningOf(w)), c = el('td', 'vp-n', '×' + w.count);
        a.appendChild(headEl(w, lang));
        tr.appendChild(a); tr.appendChild(b); tr.appendChild(c);
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      sheetEl.appendChild(table);
      document.body.appendChild(sheetEl);
      var root = document.documentElement;
      root.classList.add('vocab-printing');
      var done = function () {
        root.classList.remove('vocab-printing');
        if (sheetEl.parentNode) sheetEl.parentNode.removeChild(sheetEl);
        window.removeEventListener('afterprint', done);
      };
      window.addEventListener('afterprint', done);
      try { window.print(); } catch (e) {}
      // a browser that prints without blocking and never says afterprint
      setTimeout(function () { if (!window.matchMedia || !matchMedia('print').matches) done(); }, 1500);
    }
    function makeCards() {
      var ws = shownWords();
      if (!ws.length || !ad.card || !window.ParsehLaterCards) return;
      ParsehLaterCards.queue({
        records: ws, open: function (w) { return ad.card.open(w, w.at[0]); },
        listed: function () { return true; }, saved: function () {},
        skipTitle: 'make no card of this word and go to the next', say: function (t) { say(t); }
      });
    }

    /* ---- open and shut, as Review later's panel */
    function pushEntry() {
      try { entry = 'vocab:' + Date.now(); history.pushState({parsehVocab: entry}, ''); } catch (e) { entry = null; }
    }
    function spendEntry() {
      var mine = entry && history.state && history.state.parsehVocab === entry;
      entry = null;
      if (!mine) return;
      spent++;
      try { history.back(); } catch (e) { spent--; }
    }
    function layout() {
      if (!wrap) return;
      sheet = phone();
      wrap.className = 'lp-wrap vocab-wrap ' + (sheet ? 'lp-sheet' : 'lp-side');
      box.setAttribute('aria-modal', sheet ? 'true' : 'false');
      if (open && sheet && !entry) pushEntry();
      if (open && !sheet && entry) spendEntry();
      if (open) draw();
    }
    window.addEventListener('popstate', function () {
      if (spent) { spent--; return; }
      if (open && entry && !(history.state && history.state.parsehVocab === entry)) { entry = null; handle.close('back'); }
    });
    window.addEventListener('resize', function () { if (open) layout(); });
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && open && !e.defaultPrevented) { e.preventDefault(); handle.close('key'); }
    });
    try { if (window.Parseh && Parseh.mode && Parseh.mode.onChange) Parseh.mode.onChange(function () { if (open) layout(); }); } catch (e) {}

    var handle = {button: btn};
    handle.isOpen = function () { return open; };
    handle.onToggle = function (fn) { toggles.push(fn); };
    handle.open = function () {
      if (open) return;
      build();
      opener = document.activeElement;
      open = true;
      wrap.hidden = false;
      var want = get('parseh_vocab_scope_' + ad.kind);
      scope = (ad.scopes || []).some(function (s) { return s.id === want; }) ? want
            : (ad.scope ? ad.scope() : (ad.scopes && ad.scopes[0] ? ad.scopes[0].id : null));
      testing = false; shown = {};
      layout();
      btn.setAttribute('aria-expanded', 'true');
      load();
      try { box.focus({preventScroll: true}); } catch (e) {}
      toggles.slice().forEach(function (fn) { try { fn(true); } catch (e) {} });
    };
    handle.close = function (how) {
      if (!open) return;
      open = false;
      wrap.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      if (entry && how !== 'back') spendEntry(); else entry = null;
      var back = opener && opener.isConnected && opener.getClientRects().length ? opener : btn;
      if (how !== 'go' && how !== 'other') { try { back.focus({preventScroll: true}); } catch (e) {} }
      toggles.slice().forEach(function (fn) { try { fn(false); } catch (e) {} });
    };
    handle.toggle = function () { if (open) handle.close('button'); else handle.open(); };
    handle.refresh = function () { if (open) load(); };
    handle.words = function () { return shownWords(); };
    return handle;
  }

  /* THE SHEET COMES WITH THE SCRIPT, as lib/later.js's does */
  function dress() {
    if (location.protocol === 'file:' || document.querySelector('link[href*="vocab.css"]')) return;
    var me = document.currentScript, src = me && me.src ? me.src : '';
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = (src ? src.replace(/vocab\.js(?=[?#]|$).*$/, '') : '/lib/') + 'vocab.css';
    (document.head || document.documentElement).appendChild(link);
  }
  dress();

  /* THE V KEY, for a page that hands in its panel: not in a field, not with a
     modifier, not while a sheet of the page's own is up (the page says, in
     `busy`) */
  function key(handle, busy) {
    window.addEventListener('keydown', function (e) {
      if ((e.key !== 'v' && e.key !== 'V') || e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
      var t = e.target;
      if (t && t.closest && t.closest('input, textarea, select, [contenteditable]')) return;
      try { if (busy && busy()) return; } catch (x) {}
      e.preventDefault();
      handle.toggle();
    }, true);
  }

  /* OPENED FROM ANOTHER SHEET (the gear's row on a phone): that sheet is put
     away first, and its history entry with it -- which arrives as a popstate a
     moment later and would take this sheet's own entry, and the sheet, with it
     -- so the list opens once that has happened (or after a short wait, where
     the other sheet had no entry to spend). */
  function openAfter(handle, closeOther) {
    var done = false;
    var go = function () {
      if (done) return;
      done = true;
      window.removeEventListener('popstate', go);
      setTimeout(function () { handle.open(); }, 0);
    };
    window.addEventListener('popstate', go);
    try { closeOther(); } catch (e) {}
    setTimeout(go, 400);
  }

  window.ParsehVocab = {gather: gather, panel: panel, key: key, sorter: sorter, openAfter: openAfter};
})();
