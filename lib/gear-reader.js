// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the gear of a book's reader (a0.5.0, plan §2, §3, §4 and §6 "Book").

   Loaded into EVERY book's reader by lib/parseh.js, from beside it, right after
   the toolkit (lib/pagesettings.js): a reader is a page BUILT for its book
   (lib/tex2html.py), and one built before the gear existed has nothing of it in
   its own markup -- which is most books on any shelf.  So what a book's gear
   is lives here, in lib/, and reaches every edition, however old, with no
   rebuild.  The build writes the same words into a new reader (pass_buttons,
   the header's labels) so that it is right from its first paint; this layer
   says them again on the live page and leaves a page that has them alone.

   WHAT IT DOES
     - mounts the ⚙ with the book's groups, in plan §2's order: Levels &
       reading, Listening, Looking a word up, Text, Zoom, Colours, Interface;
     - drives the reader's OWN controls from the rows -- a row's switch presses
       the page's button, its choice sets the page's menu and lets the page's
       handler run -- so every control stays in the DOM and every handler,
       every key, every remembered value goes on working exactly as it did;
     - gives the levels their NAMES: the person's (bk_lvl:<language>:<pass key>,
       which follows them, lib/prefs.js), else the registry's, else -- for a
       reader built before the names were in the registry -- this file's table
       and, for a language somebody added since, the rule that names one
       (defaultName, the twin of languages.default_level_name);
     - takes the short vowel marks off levels 1 and 2 of a language that has
       some (the record's `strip`) on request: DIACRITICS, display only;
     - remembers "keep going" (bk_cont) and gives the page its new words;
     - makes Aa open the gear at Text, with the very sliders of Parseh.typo.

   NOTHING OF THE READER'S IS REWRITTEN BUT TEXT AND TITLES.  The layer sets a
   button's words (a level's name, "keep going", "highlight"), never its
   handler, and the only elements it takes out of the page's way are taken out
   by lib/mobile.css (html.pg-reader), not here. */
(function () {
  'use strict';
  var root = typeof window !== 'undefined' ? window : globalThis;
  if (root.ParsehGearReader) return;

  /* ====================================================== the levels' names */
  var NAME_MAX = 12;           // what a button holds (languages.LEVEL_NAME_MAX, prefs.MAX_LEVEL_NAME)
  // a pass key, and the number its class and its toggle wear: vocal is p1 / no1, as lib/tex2html.py's pass_class
  var NUMBER = {vocal: 1, chunks: 2, bare: 3, alt: 4, aloud: 5};

  /* THE REGISTRY'S OWN NAMES AND SENTENCES for the eleven languages Parseh ships
     -- [name, title] per pass key, exactly lib/languages.json (tests/test_gear_reader.py
     holds the two together).  A reader built before the names existed embeds its
     language WITHOUT them and with the old sentences, so a page of that age asks
     here first.  One line each so the diff of a reworded sentence is one line. */
  // LEVELS-BEGIN
  var LEVELS = {
    "fa": {"vocal": ["With vowels", "the sentence with its vowels, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"],
        "bare": ["Plain", "the sentence as Persian is ordinarily printed, with no marks"],
        "alt": ["Nastaliq", "the same sentence in nastaliq script"]},
    "ar": {"vocal": ["With vowels", "the sentence with its vowels, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"],
        "bare": ["Plain", "the sentence as Arabic is ordinarily printed, with no marks"]},
    "it": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "ja": {"vocal": ["Furigana", "with furigana over each word"],
        "aloud": ["Kana only", "the reading alone, in kana"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"],
        "bare": ["Plain", "plain, as Japanese is written"],
        "alt": ["Vertical", "the sentence in vertical columns (tategaki)"]},
    "fr": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "de": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "tr": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "en": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "hi": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "es": {"vocal": ["Sentence", "the sentence, to read on its own"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"]},
    "zh": {"vocal": ["Pinyin", "with pinyin over each word"],
        "aloud": ["Pinyin only", "the reading alone, in pinyin"],
        "chunks": ["Chunks", "the sentence cut into chunks, each with its gloss beside it"],
        "bare": ["Plain", "plain, as Chinese is written"],
        "alt": ["Vertical", "the sentence in vertical columns (tategaki)"]}
  };
  // LEVELS-END

  // characters as people count them, and as Python does: a letter outside the
  // basic plane is one, not two UTF-16 units
  function chars(s) { return Array.from(String(s)).length; }
  function capital(s) {
    var a = Array.from(String(s));
    return a.length ? a[0].toUpperCase() + a.slice(1).join('') : '';
  }
  function reading(L) {
    var sound = String(L.reading ? (L.reading_label || 'reading') : (L.translit_label || 'reading')).trim() || 'reading';
    var word = capital(sound);
    return chars(word) <= NAME_MAX ? word : 'Reading';
  }
  /* THE TWIN OF languages.default_level_name, for a language the table does not
     hold -- one a person added -- in a reader that embeds it without names.  The
     same rule, fed the record the page embeds (LANG, languages.Lang.as_json):
     where that carries a field the registry's row had not (translit_label,
     vocal_label) it has the value the rule would have read from nothing, so the
     two answer alike for every language (tests/test_gear_reader.py drives both
     over all eleven and over one lib/newlang.py wrote). */
  function defaultName(L, p) {
    var key = p && p.key, word = reading(L);
    if (key === 'vocal') {
      if (L.words || L.reading) {
        var said = String(L.vocal_label || '').trim();
        if (said.toLowerCase().indexOf('with ') === 0) {
          var own = capital(said.slice(5).trim());
          if (chars(own) > 0 && chars(own) <= NAME_MAX) return own;
        }
        return word;
      }
      if (L.strip) return L.script === 'arabic' ? 'With vowels' : 'With marks';
      return 'Sentence';
    }
    if (key === 'aloud') {
      var only = word + ' only';
      return chars(only) <= NAME_MAX ? only : 'Reading only';
    }
    if (key === 'chunks') return 'Chunks';
    if (key === 'bare') return 'Plain';
    if (key === 'alt') {
      if (p && p.kind === 'vertical') return 'Vertical';
      var face = String(((L.fonts || {}).alt_key) || '').trim();
      if (/^\p{L}+$/u.test(face) && face.toLowerCase() !== 'alt' && chars(face) <= NAME_MAX)
        return capital(face.slice(0, 1)) + Array.from(face).slice(1).join('').toLowerCase();
      return 'Other font';
    }
    var k = String(key || '').trim().toLowerCase();
    return Array.from(capital(k) || 'Level').slice(0, NAME_MAX).join('');
  }
  /* WHAT A PASS IS CALLED BY DEFAULT, and the sentence that says what it shows:
     what the embedded record carries when it carries a name (a reader built
     now), else the table (a reader of one of the eleven, built before), else
     the rule (any other), and for the sentence the record's own where the
     table has none. */
  function levelDefault(L, p) {
    var row = LEVELS[L.code] && LEVELS[L.code][p.key];
    if (p.name) return {name: String(p.name), title: String(p.title || (row && row[1]) || '')};
    if (row) return {name: row[0], title: row[1]};
    return {name: defaultName(L, p), title: String(p.title || '')};
  }

  var api = {LEVELS: LEVELS, defaultName: defaultName, levelDefault: levelDefault, NAME_MAX: NAME_MAX};
  root.ParsehGearReader = api;
  if (typeof document === 'undefined' || !document.addEventListener) return;

  /* ====================================================== the page's own state */
  function $(id) { return document.getElementById(id); }
  function qa(sel, from) { return Array.prototype.slice.call((from || document).querySelectorAll(sel)); }
  function getKey(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function putKey(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  // the reader's own top-level bindings, read where they are and nowhere else
  function lang() { try { return typeof LANG === 'object' && LANG ? LANG : null; } catch (e) { return null; } }
  function gloss() { try { return typeof GLOSS === 'object' && GLOSS ? GLOSS : null; } catch (e) { return null; } }
  function P() { return root.Parseh || null; }
  // a button of the page that says it is on (every switch of the reader wears `on`)
  function on(b) { return !!b && b.classList.contains('on'); }
  function press(b) { if (b && !b.disabled) b.click(); }
  function turn(b, want) { if (b && on(b) !== !!want) press(b); }
  function drawn(b) { return !!b && !b.hidden; }
  function hasRecording() { return !!document.body && !document.body.classList.contains('noaudio') && !!$('play'); }

  /* ------------------------------------------------------------- the levels */
  function nameKey(code, key) { return 'bk_lvl:' + code + ':' + key; }
  function chosenName(L, key) {
    var v = getKey(nameKey(L.code, key));
    return String(v === null ? '' : v).replace(/^\s+|\s+$/g, '');
  }
  /* The levels of this book, in the order of the buttons: pass key, the class
     number it wears, the page's button for it (found by the toggle it carries
     -- which is how tex2html.pass_buttons names it -- not by its place), the
     default name and sentence, and the name in force. */
  function levelItems() {
    var L = lang();
    if (!L || !L.passes) return [];
    return L.passes.map(function (p) {
      var n = NUMBER[p.key], d = levelDefault(L, p), mine = chosenName(L, p.key);
      return {key: p.key, n: n, btn: n ? document.querySelector('[data-toggle=no' + n + ']') : null,
              def: d.name, title: d.title, name: mine || d.name};
    }).filter(function (it) { return !!it.n; });
  }
  function levelShown(it) { return !document.body.classList.contains('no' + it.n); }
  var LOCKED = 'Hover mode shows the glosses in the cloud instead.';

  /* The text a button wears for a level, and the sentence under its name -- on
     the live page, and where the page was built with them, unchanged. */
  function setText(b, text) { if (b && text && b.textContent !== text) b.textContent = text; }
  function setTitle(b, title) {
    if (!b || !title) return;
    // a level the hover mode has put to rest wears the reason in its title and
    // keeps its own in t0, which the page puts back when the rest is over
    if (b.disabled && b.dataset.t0 !== undefined) b.dataset.t0 = title;
    else if (b.title !== title) b.title = title;
  }
  function hoverTitle(items) {
    var names = items.filter(function (it) { return it.key === 'vocal' || it.key === 'aloud' || it.key === 'bare'; })
                     .map(function (it) { return it.name; });
    if (!names.length) return '';
    var said = names.length < 3 ? names.join(' and ') : names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
    return 'the text alone (the level' + (names.length > 1 ? 's ' : ' ') + said +
           '), the glosses in a hover cloud over it (H)';
  }
  function paintLevels() {
    var items = levelItems();
    items.forEach(function (it) { setText(it.btn, it.name); setTitle(it.btn, it.title); });
    var cap = document.querySelector('.pgrp .pgrpc');
    setText(cap, 'levels');
    var h = $('hovermode'), t = hoverTitle(items);
    if (h && t && h.title !== t) h.title = t;
  }

  /* --------------------------------------------- the words the page now says */
  function paintWords() {
    var c = $('cont');
    if (c) { setText(c, 'keep going'); setTitle(c, 'keep playing into the next line instead of stopping at the end of each one'); }
    var gw = $('gapwrap');
    if (gw) {
      // the label is the text node in front of the menu: "gap" -> "between repeats"
      for (var n = gw.firstChild; n; n = n.nextSibling) {
        if (n.nodeType === 3 && /\S/.test(n.nodeValue)) {
          if (/^\s*gap\s*$/.test(n.nodeValue)) n.nodeValue = 'between repeats ';
          break;
        }
      }
      var g = $('gap');
      if (g) setTitle(g, 'pause between repeats');
    }
    setText($('bars'), '⌃ hide bars');
    setText($('barsback'), '⌄ show bars');
    var f = $('listenfollow'), s = $('listenscroll');
    if (f) {
      setText(f, 'highlight');
      setTitle(f, 'highlight the sentence being said while the recording plays on its own, the way a video’s ' +
                  'captions follow the video — it moves with the sound but no longer stops it at a ' +
                  'sentence’s end. Not needed: everything above works the same without it');
    }
    if (s) {
      setText(s, 'keep in view');
      setTitle(s, 'and scroll to keep it in view. Off, the highlight still moves — follow it by scrolling yourself');
    }
  }

  /* ---------------------------------------------------------- "keep going" */
  /* Remembered now, and following the person (bk_cont, lib/prefs.js): read at
     load and written at every press, the page's own press or the gear's.  A
     page built now does both itself; this makes an old one do the same, and
     writing the value a press has just left is harmless twice. */
  function keepGoing() {
    var c = $('cont');
    if (!c || c.getAttribute('data-gear-kept')) return;
    c.setAttribute('data-gear-kept', '1');
    var v = getKey('bk_cont');
    if (v === '0' || v === '1') turn(c, v === '1');
    c.addEventListener('click', function () { putKey('bk_cont', on(c) ? '1' : '0'); });
  }

  /* ================================================================ DIACRITICS
     A device switch, bk_marks ('0' = the marks are hidden; absent = shown), for
     a language whose record has a `strip` (Persian, Arabic): the very marks the
     bare level drops are taken off levels 1 and 2 -- the text nodes of `.p1 .w`
     (the .wd words inside it too) and of the chunk column `.row .fa` -- and off
     nothing else.  DISPLAY ONLY, and so:
       - the original of every changed text node is kept (a WeakMap), and putting
         the marks back restores the page node for node;
       - the page's own readers of text see the ORIGINAL: textOf (the cloud's
         copy, a card's chunk and sentence, a shift-click) and Parseh.baseText
         (the held finger's menu) are given a copy of the element with its text
         as the book wrote it, so a card or a copy carries the vowelled text;
       - nothing else moves: a node's value changes, no element is added, taken
         out or reordered, so the cloud, the gloss, the highlight and every
         lookup (.wd, data-c, data-w) are the page's own;
       - a chapter that arrives later (fillChapter, repaintChunks) is bare when
         it arrives: the observer on <main> sees it come. */
  var MARKS_KEY = 'bk_marks';
  var SCOPE = '.p1 .w, .row .fa';
  var originals = new WeakMap();
  var marksOff = false, marksRe = null, watcher = null;

  function marksFor(L) {
    if (!L || !L.strip) return null;
    try { return {any: new RegExp('[' + L.strip + ']'), all: new RegExp('[' + L.strip + ']', 'g')}; }
    catch (e) { return null; }
  }
  // a text node is the book's own text, not a reading drawn over it
  function plain(n) {
    var p = n.parentNode;
    return !(p && p.closest && p.closest('rt, rp'));
  }
  function eachText(el, fn) {
    var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), n, hit = [];
    while ((n = w.nextNode())) if (plain(n)) hit.push(n);
    hit.forEach(fn);
  }
  function bare(n) {
    var t = n.nodeValue;
    if (!marksRe.any.test(t)) return;
    // a value with marks in it is the book's own, whatever was kept of this node before (the page may have written it again)
    originals.set(n, t);
    n.nodeValue = t.replace(marksRe.all, '');
  }
  function restoreNode(n) {
    if (!originals.has(n)) return;
    n.nodeValue = originals.get(n);
    originals.delete(n);
  }
  // what comes under `node` (a chapter's markup, a repainted chunk, one text node)
  function visit(node, fn) {
    if (node.nodeType === 3) {
      var p = node.parentNode;
      if (p && p.closest && p.closest(SCOPE) && plain(node)) fn(node);
      return;
    }
    if (node.nodeType !== 1) return;
    if (node.closest && node.closest(SCOPE)) { eachText(node, fn); return; }
    qa(SCOPE, node).forEach(function (el) { eachText(el, fn); });
  }
  function textList(el) {
    var out = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), n;
    while ((n = w.nextNode())) out.push(n);
    return out;
  }
  /* A COPY OF `el` WITH ITS TEXT AS THE BOOK WROTE IT, for the page's readers
     of text to read -- the same markup in the same order, so the nodes pair up
     one for one with the copy's. */
  function original(el) {
    var copy = el.cloneNode(true), a = textList(el), b = textList(copy);
    for (var i = 0; i < a.length && i < b.length; i++) {
      var t = originals.get(a[i]);
      if (t !== undefined) b[i].nodeValue = t;
    }
    return copy;
  }
  var wrapped = false;
  function wrapReaders() {
    if (wrapped) return;
    wrapped = true;
    if (typeof root.textOf === 'function') {
      var was = root.textOf;
      root.textOf = function (el) { return was.call(this, marksOff && el && el.cloneNode ? original(el) : el); };
    }
    var p = P();
    if (p && typeof p.baseText === 'function') {
      var base = p.baseText;
      p.baseText = function (el) { return base.call(this, marksOff && el && el.cloneNode ? original(el) : el); };
    }
  }
  function setMarks(show, remember) {
    if (!marksRe) return;
    if (remember) putKey(MARKS_KEY, show ? '1' : '0');
    if (marksOff === !show) return;
    marksOff = !show;
    var main = document.querySelector('main') || document.body;
    if (marksOff) {
      visit(main, bare);
      if (!watcher && root.MutationObserver) {
        watcher = new MutationObserver(function (ms) {
          if (!marksOff) return;
          ms.forEach(function (m) {
            Array.prototype.forEach.call(m.addedNodes, function (n) { visit(n, bare); });
          });
        });
        watcher.observe(main, {childList: true, subtree: true});
      }
    } else {
      visit(main, restoreNode);
    }
  }
  function marksShown() { return !marksOff; }
  function diacritics() {
    var L = lang();
    marksRe = marksFor(L);
    if (!marksRe) return;
    wrapReaders();
    if (getKey(MARKS_KEY) === '0') setMarks(false, false);
    // the same switch changed in another tab of this browser
    root.addEventListener('storage', function (e) {
      if (e.key === MARKS_KEY || e.key === null) setMarks(getKey(MARKS_KEY) !== '0', false);
    });
  }

  /* ====================================================== telling the gear */
  /* ONE LISTENER FOR EVERY ROW'S `watch`.  What changes under the panel -- a key
     pressed on the page, the hover mode putting a level to rest, a dictionary
     found a moment after the page loaded, a name brought from another device --
     shows in the page's own controls (their class, hidden, disabled, title), in
     what is stored (storage, parseh:pref) or in a menu (change); the gear's
     rows are asked again when any of it moves, once for a burst. */
  var bus = (function () {
    var fns = [], timer = 0, started = false;
    function fire() {
      timer = 0;
      fns.slice().forEach(function (f) { try { f(); } catch (e) {} });
    }
    function poke() { if (!timer) timer = setTimeout(fire, 30); }
    function start() {
      if (started) return;
      started = true;
      if (root.MutationObserver) {
        var mo = new MutationObserver(poke), seen = [];
        var opts = {attributes: true, attributeFilter: ['class', 'hidden', 'disabled', 'style', 'title']};
        var add = function (e) { if (e && seen.indexOf(e) < 0) { seen.push(e); mo.observe(e, opts); } };
        ['hovermode', 'hoverpause', 'cont', 'loop', 'stopbnd', 'listen', 'dictmode', 'defmode', 'defmt',
         'bars', 'barsback', 'gapwrap'].forEach(function (id) { add($(id)); });
        qa('[data-toggle]').forEach(add);
        mo.observe(document.body, {attributes: true, attributeFilter: ['class']});
      }
      root.addEventListener('storage', poke);
      document.addEventListener('parseh:pref', poke);
      ['speed', 'gap'].forEach(function (id) { var e = $(id); if (e) e.addEventListener('change', poke); });
    }
    return {
      on: function (fn) {
        fns.push(fn);
        start();
        return function () { var i = fns.indexOf(fn); if (i >= 0) fns.splice(i, 1); };
      },
      poke: poke
    };
  })();

  /* ================================================================ the rows */
  function sw(o) {
    o.kind = 'switch';
    if (!o.watch) o.watch = bus.on;
    return o;
  }
  function pressOf(id) {
    return {
      get: function () { return on($(id)); },
      set: function (v) { turn($(id), v); }
    };
  }
  function merge(a, b) { for (var k in b) if (Object.prototype.hasOwnProperty.call(b, k)) a[k] = b[k]; return a; }
  function seconds(v) { return +v === 0 ? 'none' : String(+v) + ' s'; }

  /* WHAT A SWITCH IS CALLED IN A SUMMARY (a0.5.4): on a phone the sheet opens on an index of the themes, each with
     one line that says what it is set to -- "one to three words naming the row", said where it is ON. */
  var SHORT = {gloss: 'glosses', hover: 'cloud', hoverpause: 'pauses', bars: 'bars hidden', cont: 'keeps going',
               loop: 'repeat', stopbnd: 'waits at chapters', listen: 'on its own', dictmode: 'dictionary',
               defmode: 'definitions', defmt: 'translated'};
  // the short names of the page's own toggles that are drawn and ON, in the order given
  function flags(ids) {
    var out = [];
    ids.forEach(function (id) { if (drawn($(id)) && on($(id)) && SHORT[id]) out.push(SHORT[id]); });
    return out;
  }
  // parts for a group's summary: the pieces joined with " · "; a piece may itself be a list of parts
  function joined(pieces) {
    var out = [];
    pieces.forEach(function (p) {
      if (p === '' || p === null || p === undefined || (Array.isArray(p) && !p.length)) return;
      if (out.length) out.push(' \u00b7 ');
      if (Array.isArray(p)) out = out.concat(p); else out.push(p);
    });
    return out;
  }

  /* ---- Levels & reading ---- */
  function levelsGroup() {
    var rows = [];
    rows.push({
      id: 'levels', kind: 'levels', label: 'Levels',
      help: 'Which levels of the text this page shows, and what you call each one. The ticks stay on this device; the names follow you.',
      items: function () {
        return levelItems().map(function (it) {
          var locked = !!(it.btn && it.btn.disabled);
          return {key: it.key, name: it.name, def: it.def, help: it.title, shown: levelShown(it),
                  disabled: locked ? LOCKED : undefined};
        });
      },
      setShown: function (key, shown) {
        levelItems().forEach(function (it) {
          if (it.key === key && it.btn && !it.btn.disabled && levelShown(it) !== !!shown) it.btn.click();
        });
      },
      setName: function (key, v) {
        var L = lang();
        if (!L) return;
        putKey(nameKey(L.code, key), String(v || '').slice(0, 64));
        paintLevels();
      },
      watch: bus.on,
      when: function () { return levelItems().length > 0; }
    });
    rows.push(sw(merge({
      id: 'marks', label: 'Diacritics',
      help: function () {
        var L = lang() || {}, it = levelItems().filter(function (x) { return x.key === 'bare'; })[0];
        var marks = L.script === 'arabic'
          ? 'the small marks that write the vowels, the doubling and the silent stop (fatha, damma, kasra, tanwin, shadda, sukun)'
          : 'the small marks above and below the letters that write the vowels';
        return 'Shows ' + marks + ' on ' + (L.name || 'the book\'s') + ' text. Off, the text reads as it is ordinarily ' +
               'printed and you can still point at a chunk for its gloss' +
               (it ? '; the level “' + it.name + '” is the same text without the hover.' : '.');
      },
      when: function () { return !!marksRe; }
    }, {get: marksShown, set: function (v) { setMarks(!!v, true); }})));
    rows.push(sw(merge({
      id: 'gloss', label: 'Glosses', short: SHORT.gloss,
      help: 'Show the meaning beside each chunk. Turn it off to test yourself against the chunks alone. Key G.',
      when: function () { return !!document.querySelector('[data-toggle=nogloss]'); },
      disabled: function () { var b = document.querySelector('[data-toggle=nogloss]'); return b && b.disabled ? LOCKED : false; }
    }, {
      get: function () { return on(document.querySelector('[data-toggle=nogloss]')); },
      set: function (v) { turn(document.querySelector('[data-toggle=nogloss]'), v); }
    })));
    rows.push(sw(merge({
      id: 'hover', label: 'Glosses in a cloud', short: SHORT.hover,
      help: 'Read the text clean: a chunk\'s gloss opens in a cloud when you point at it (a tap on a touch screen). Key H. ' +
            'While it is on, the Chunks level and the glosses switch rest, because the cloud shows the glosses instead.',
      when: function () { return !!$('hovermode'); }
    }, pressOf('hovermode'))));
    rows.push(sw(merge({
      id: 'hoverpause', label: 'Pause while a gloss is open', indent: 1, short: SHORT.hoverpause,
      help: 'While a gloss is open the recording waits, and goes on a moment after it closes, so you can read at your own pace. ' +
            'With a mouse or a finger.',
      when: function () { return drawn($('hoverpause')) && hasRecording(); }
    }, pressOf('hoverpause'))));
    rows.push(sw(merge({
      id: 'bars', label: 'Hide the bars', short: SHORT.bars,
      help: 'Puts the header away so the text has the whole window; a small ⌄ at the top corner brings it back.',
      when: function () { return !!$('bars'); }
    }, {
      get: function () { return document.body.classList.contains('chrome-off'); },
      set: function (v) { press(v ? $('bars') : $('barsback')); }
    })));
    return {
      id: 'levels', title: 'Levels & reading', caption: 'Saved on this device, apart from the names of the levels, which follow you.',
      /* the ticked levels' names (the person's, so any script: each is told apart for a right-to-left reading), then
         what is off or unusual: no glosses (unless the cloud has taken them), the cloud, no diacritics */
      summary: function () {
        var names = [];
        levelItems().forEach(function (it) {
          if (!levelShown(it)) return;
          if (names.length) names.push(', ');
          names.push({bdi: it.name});
        });
        var extra = [], g = document.querySelector('[data-toggle=nogloss]');
        if (g && !g.disabled && !on(g)) extra.push('no glosses');
        if (drawn($('hovermode')) && on($('hovermode'))) extra.push('cloud');
        if (marksRe && !marksShown()) extra.push('no diacritics');
        return joined([names].concat(extra));
      },
      rows: rows
    };
  }

  /* ---- Listening ---- */
  function listeningGroup() {
    var N = function () { return root.ParsehNarr || null; };
    var speeds = (N() && N().speeds ? N().speeds() : [0.25, 0.5, 0.6, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2]);
    var secs = (N() && N().seconds) || [1, 2, 5, 10, 15, 30, 60];
    var gapOpts = $('gap') ? qa('option', $('gap')).map(function (o) { return o.value; }) : ['0', '0.5', '1', '1.5', '2', '3', '5'];
    var rows = [];
    rows.push({
      id: 'speed', kind: 'choice', label: 'Playback speed', kept: 'you', watch: bus.on,
      help: 'How fast the recording plays, from 0.25× to 2×. The [ and ] keys step it.',
      options: speeds.map(function (v) { return {value: v, label: N() && N().say ? N().say(v) : v + '×'}; }),
      get: function () { return N() ? N().rate() : 1; },
      set: function (v) { if (N()) N().setRate(+v); },
      when: function () { return !!N() && !!$('speed'); }
    });
    rows.push({
      id: 'skip', kind: 'choice', label: 'Skip distance', kept: 'you', watch: bus.on,
      help: 'How many seconds ↺ and ↻ move the recording. Shift+← and Shift+→ do the same.',
      options: secs.map(function (v) { return {value: v, label: v + ' s'}; }),
      get: function () { return N() ? N().secs() : 10; },
      set: function (v) { if (N()) N().setSecs(+v); },
      when: function () { return !!N(); }
    });
    rows.push(sw(merge({
      id: 'cont', label: 'Keep playing into the next line', kept: 'you', short: SHORT.cont,
      help: 'When a line of the recording ends, go straight on to the next one instead of stopping. Turn it off to practise one line at a time.',
      when: function () { return !!$('cont'); }
    }, pressOf('cont'))));
    rows.push(sw(merge({
      id: 'loop', label: 'Repeat this line', short: SHORT.loop,
      help: 'Plays the line again and again, with the pause below between repeats, until you turn it off. Key R. Not remembered: it is off each time you open the book.',
      when: function () { return !!$('loop'); }
    }, pressOf('loop'))));
    rows.push({
      id: 'gap', kind: 'choice', label: 'Pause between repeats', kept: 'you', indent: 1, watch: bus.on,
      help: 'The silence between one repeat of a line and the next while loop is on, from none to 5 seconds.',
      options: gapOpts.map(function (v) { return {value: v, label: seconds(v)}; }),
      get: function () { var g = $('gap'); return g ? g.value : '0'; },
      set: function (v) {
        var g = $('gap');
        if (!g) return;
        g.value = String(v);
        g.dispatchEvent(new Event('change', {bubbles: true}));
      },
      disabled: function (above) { return above === false ? 'Turn on “Repeat this line” first.' : false; },
      when: function () { return !!$('gap'); }
    });
    rows.push(sw(merge({
      id: 'stopbnd', label: 'Wait at each new chapter', kept: 'you', short: SHORT.stopbnd,
      help: 'When the recording reaches the start of a new chapter or section it stops and waits for you to press ▶, so you can take in the heading and get ready.',
      when: function () { return !!$('stopbnd'); }
    }, pressOf('stopbnd'))));
    rows.push(sw(merge({
      id: 'listen', label: 'Listen on its own', short: SHORT.listen,
      help: 'Plays the recording by itself: nothing is highlighted or scrolled and your reading place stays put. A seek bar appears so you can start anywhere. Not remembered.',
      when: function () { return !!$('listen'); }
    }, pressOf('listen'))));
    return {
      id: 'listening', title: 'Listening',
      caption: 'Follows you to your other devices; repeating and listening on its own are not remembered.',
      // "1×, skip 10 s" and the switches that are on
      summary: function () {
        var n = N(), lead = [];
        if (n && n.rate) lead.push(n.say ? n.say(n.rate()) : n.rate() + '×');
        if (n && n.secs) lead.push('skip ' + n.secs() + ' s');
        return joined([lead.join(', ')].concat(flags(['cont', 'loop', 'stopbnd', 'listen'])));
      },
      when: hasRecording, rows: rows
    };
  }

  /* ---- Looking a word up ---- */
  function lookingGroup() {
    var L = function () { return lang() || {}; }, G = function () { return gloss() || {}; };
    var rows = [];
    rows.push(sw(merge({
      id: 'dictmode', label: 'Look words up in a dictionary', short: SHORT.dictmode,
      help: 'Where a chunk has not been glossed, click or tap it to look its words up in the dictionary installed for this language. Remembered for this book.',
      when: function () { return drawn($('dictmode')); }
    }, pressOf('dictmode'))));
    rows.push(sw(merge({
      id: 'defmode', label: 'Show the dictionary\'s definitions', indent: 1, short: SHORT.defmode,
      help: function () { return 'Under each word it finds, the dictionary\'s own definition in ' + (L().name || 'the book\'s language') + '.'; },
      when: function () { return drawn($('defmode')); },
      disabled: function () { var b = $('defmode'); return b && b.disabled ? 'Turn the dictionary on first.' : false; }
    }, pressOf('defmode'))));
    rows.push(sw(merge({
      id: 'defmt', indent: 2, short: SHORT.defmt,
      label: function () { return 'Translate the definitions into ' + (G().name || 'the language of the glosses'); },
      help: function () {
        var g = G().name || 'the language of the glosses';
        return 'Each definition is put into ' + g + ' by the translation model on this computer: a machine\'s reading, not a gloss.';
      },
      when: function () { return drawn($('defmt')); },
      disabled: function () { var b = $('defmt'); return b && b.disabled ? 'Turn the definitions on first.' : false; }
    }, pressOf('defmt'))));
    var look = $('lookupset');
    rows.push({
      id: 'lookupset', kind: 'link', label: 'Get a dictionary for this language →',
      href: (look && look.getAttribute('href')) || '/settings/reading-help/',
      help: 'A dictionary, a corpus of translated sentences or a model to look words up with: set up in Parseh\'s own settings.'
    });
    return {
      id: 'looking', title: 'Looking a word up', caption: 'Saved on this device, for this book.',
      // nothing installed ("get one"), installed and not used, or what it is used for
      summary: function () {
        if (!drawn($('dictmode'))) return 'get one \u2192';
        if (!on($('dictmode'))) return 'no dictionary';
        return joined(['dictionary'].concat(flags(['defmode', 'defmt'])));
      },
      rows: rows
    };
  }

  /* ---- Text: the sliders of Parseh.typo, the very same fields ---- */
  var TEXT = {
    fa: ['text size', 'How big the book\'s own words are, the ones you are learning.'],
    gl: ['Gloss size', 'How big the meanings and notes beside each chunk are, and inside the hover cloud.'],
    width: ['Text width', 'How wide the column of text may grow on a wide screen; on a narrow screen it always fits.'],
    lead: ['Line spacing', 'The space between lines: 1 is the usual, more is airier.'],
    vh: ['Height of vertical columns', 'How tall each column of vertical text is, counted in character heights.'],
    cjkSpace: ['Space between characters', 'Extra room between characters; 0 is the normal spacing.'],
    kanaContrast: ['Furigana contrast', 'How strongly the small kana over the kanji are drawn: lower fades them so the kanji stand out, higher makes them darker.'],
    kanaSize: ['Furigana size', 'How big the kana over the kanji are, as a percentage of the kanji\'s own size.']
  };
  function typo() { var p = P(); return p && p.typo && p.typo.last ? p.typo.last : null; }
  function amount(f, v) {
    if (f.unit === 'px') return (Math.round(v * 10) / 10) + ' px';
    return (Math.round(v * 100) / 100) + (f.unit === '×' ? '×' : f.unit ? ' ' + f.unit : '');
  }
  function textGroup() {
    var t = typo(), rows = [];
    ((t && t.fields) || []).forEach(function (f) {
      var words = TEXT[f.name];
      if (!words) return;
      rows.push({
        id: 'typo-' + f.name, kind: 'slider', watch: bus.on,
        label: f.name === 'fa' ? function () { return ((lang() || {}).name || 'Book') + ' ' + words[0]; } : words[0],
        help: words[1], min: f.min, max: f.max, step: f.step,
        format: function (v) { return amount(f, v); },
        get: function () { var x = typo(); return x ? x.get()[f.name] : f.def; },
        set: function (v) { var x = typo(); if (x) x.set(f.name, v); }
      });
    });
    rows.push({
      id: 'typo-reset', kind: 'action', label: 'Put the text back to normal',
      help: 'Sets every slider above back to its usual value.',
      onClick: function () { var x = typo(); if (x) x.reset(); }
    });
    return {
      id: 'text', title: 'Text', caption: 'Saved on this device.',
      // the book's own words, as the first slider says them: "Persian text 28 px"
      summary: function () {
        var x = typo(), f = x && x.fields ? x.fields.filter(function (q) { return q.name === 'fa'; })[0] : null;
        return f ? ((lang() || {}).name || 'Book') + ' text ' + amount(f, x.get()[f.name]) : '';
      },
      rows: rows
    };
  }

  /* ======================================================= Aa opens the gear */
  /* The Aa button of the page stays where it is and opens the gear at Text; the
     panel Parseh.typo draws for it never opens, for the click is spent here, in
     the capture phase, before the toolbox's own listener on the button hears
     it.  Pressed while the gear is up with Text in view it closes it again, as
     it closed its old panel.  (It is also what a click outside would do to the
     cloud the page has open, so that is done.) */
  function textInView(gear) {
    // on the phone's sheet Text is in view when it is the theme on stage
    var st = typeof gear.stage === 'function' ? gear.stage() : null;
    if (st !== null && st !== undefined) return st === 'text';
    var g = document.querySelector('.pg-panel [data-pg-group=text]'), b = document.querySelector('.pg-panel .pg-body');
    if (!g || !b || g.hidden) return false;
    var gr = g.getBoundingClientRect(), br = b.getBoundingClientRect();
    return gr.top >= br.top - 4 && gr.top < br.bottom - 40;
  }
  function wireAa(gear) {
    root.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest || !t.closest('#typo')) return;
      e.stopImmediatePropagation();
      e.preventDefault();
      try { if (typeof closeCloud === 'function' && typeof cloudC === 'number' && cloudC >= 0) closeCloud(); } catch (x) {}
      if (gear.isOpen() && textInView(gear)) gear.close();
      else gear.open('text');
    }, true);
  }

  /* ================================================================= the mount */
  function header() { return document.querySelector('header .hrow'); }
  function mount() {
    var G = root.ParsehGear;
    if (!G || !document.body || !header()) { document.documentElement.classList.remove('pg-reader'); return null; }
    document.documentElement.classList.add('pg-reader');
    var colours = G.std.colours();
    // a theme the computer brought (lib/prefs.js says so) repaints the row at once
    var theme = colours.rows[0], was = theme.watch;
    theme.watch = function (cb) {
      var off = typeof was === 'function' ? was(cb) : null;
      var h = function (e) { if (e && e.detail && e.detail.key === 'parseh_theme') cb(); };
      document.addEventListener('parseh:pref', h);
      return function () { if (typeof off === 'function') off(); document.removeEventListener('parseh:pref', h); };
    };
    var iface = G.std.interface();
    // keep.js's buttons ("Keep on this phone"), borrowed into the sheet's last group while it is up
    iface.rows.push({
      id: 'keep', kind: 'node', layouts: 'mobile', label: 'Away from the computer',
      help: 'Keeps this book on this phone, so that it opens when the computer cannot be reached.',
      el: function () { return document.querySelector('.kp-btn'); }
    });
    var gear = G.mount({
      page: 'book',
      host: {browser: header, mobile: header},
      groups: [levelsGroup(), listeningGroup(), lookingGroup(), textGroup(), G.std.zoom(), colours, iface]
    });
    api.gear = gear;
    wireAa(gear);
    return gear;
  }

  function start() {
    if (!lang() && !$('typo')) return;       // not a book's reader
    paintWords();
    paintLevels();
    keepGoing();
    diacritics();
    mount();
    // a name brought from another device, or changed in another tab, is worn live
    document.addEventListener('parseh:pref', function (e) {
      var k = e && e.detail && e.detail.key;
      if (typeof k === 'string' && k.indexOf('bk_lvl:') === 0) { paintLevels(); bus.poke(); }
    });
    root.addEventListener('storage', function (e) {
      if (!e.key || e.key.indexOf('bk_lvl:') === 0) paintLevels();
    });
  }
  api.paintLevels = paintLevels;
  api.levelItems = levelItems;
  api.marks = {shown: marksShown, set: function (v) { setMarks(!!v, true); }};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
