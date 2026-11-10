// SPDX-License-Identifier: GPL-3.0-or-later
/* THE CHUNKS SIDE BY SIDE (a0.6.2): a further layout of a book's Chunks level.

   The Chunks level of a reader (lib/tex2html.py, `.pass.p2`) is one row for
   each chunk: the chunk's text, its gloss beside it.  This is the other way to
   lay the same rows out -- the chunks of a sentence following one another
   along the line and wrapping, from the side the language reads from, each a
   small column: the text, and under it the reading (where the language has
   one), the transliteration and the meaning; and UNDER the whole flow, the
   vocabulary, one line for each chunk that has one.

   It is a choice of the device: localStorage `bk_flow` ('1' = side by side;
   absent or '0' = the rows), worn by the page as body.chunkflow.  What is
   shown stays with the device that shows it (lib/prefs.py), so the key is in
   no list that follows the person.

   NOTHING IS BUILT INTO A READER FOR IT.  The columns are the rows the build
   has always written, laid out by rules in lib/parseh.css that hang off
   body.chunkflow; this file is loaded by lib/parseh.js into every reader,
   however old, beside the gear (lib/gear-reader.js), whose row "Chunks laid
   out" is the control.  So:
     - a chunk is the element it always was: `.row[data-c]`, its `.fa`, its
       `.gl` with `.kana`, `.tr`, `.voc`, `.en` -- every lookup, the cloud, the
       pencil, a card, a copy, a flag, the readings and the diacritics find it
       where they did;
     - the vocabulary line of a chunk STAYS in its row (`.gl .voc`, which the
       page reads: the cloud, the editor, "is this chunk written?") and is not
       drawn there; what is drawn is a COPY of it, in a block this file keeps
       as the last child of the level: `div.fvoc > div.fv[data-for="<n>"]`.
       The copy is not a row and carries no data-c, so nothing that looks for
       a chunk finds it;
     - the copies are kept current: a chapter that arrives later, and a chunk
       written again with the pencil (the page repaints the row's innerHTML),
       are seen by an observer on <main>, and the block of the level they are
       in is drawn again;
     - with the layout off the blocks are taken out and the page is the page
       it was, node for node.

   window.ParsehFlow = { get(): bool, set(on), on(cb) -> unsubscribe } */
(function (root) {
  'use strict';
  if (root.ParsehFlow) return;
  var KEY = 'bk_flow', CLS = 'chunkflow';
  var fns = [], active = false, watcher = null, dirty = [], timer = 0, penWatch = null;

  function stored() {
    try { return root.localStorage.getItem(KEY) === '1'; } catch (e) { return false; }
  }
  function tell() { fns.slice().forEach(function (f) { try { f(active); } catch (e) {} }); }
  function main() { return document.querySelector('main') || document.body; }

  /* ---------------------------------------------------- the vocabulary block */
  // the rows of a level, its own and no deeper
  function rowsOf(p2) {
    return Array.prototype.filter.call(p2.children, function (c) { return c.classList && c.classList.contains('row'); });
  }
  function blockOf(p2) {
    for (var c = p2.lastElementChild; c; c = c.previousElementSibling)
      if (c.classList.contains('fvoc')) return c;
    return null;
  }
  // what the block of this level should be, or null where no chunk has a vocabulary line
  function drawn(p2) {
    var box = null;
    rowsOf(p2).forEach(function (row) {
      var gl = row.querySelector('.gl'), v = gl && gl.querySelector('.voc');
      if (!v || !/\S/.test(v.textContent)) return;
      if (!box) { box = document.createElement('div'); box.className = 'fvoc'; }
      var line = document.createElement('div');
      line.className = 'fv';
      line.setAttribute('data-for', row.getAttribute('data-c') || '');
      // the gloss is in its own language and direction, which its cell says
      ['lang', 'dir'].forEach(function (a) { if (gl.hasAttribute(a)) line.setAttribute(a, gl.getAttribute(a)); });
      Array.prototype.forEach.call(v.childNodes, function (n) { line.appendChild(n.cloneNode(true)); });
      box.appendChild(line);
    });
    return box;
  }
  function build(p2) {
    if (!p2 || !p2.isConnected) return;
    var was = blockOf(p2), now = active ? drawn(p2) : null;
    if (was && now && was.innerHTML === now.innerHTML) {
      if (p2.lastElementChild !== was) p2.appendChild(was);
      return;
    }
    if (was) was.remove();
    if (now) p2.appendChild(now);
  }
  function buildAll() {
    Array.prototype.forEach.call(document.querySelectorAll('.pass.p2'), build);
  }
  function clearAll() {
    Array.prototype.forEach.call(document.querySelectorAll('.pass.p2 > .fvoc'), function (b) { b.remove(); });
  }

  /* -------------------------------------------- keeping the blocks current */
  function mine(n) { return n.nodeType === 1 && n.classList.contains('fvoc'); }
  function mark(p2) { if (p2 && dirty.indexOf(p2) < 0) dirty.push(p2); }
  function flush() {
    timer = 0;
    var todo = dirty;
    dirty = [];
    if (active) todo.forEach(build);
  }
  function seen(ms) {
    if (!active) return;
    ms.forEach(function (m) {
      var t = m.target.nodeType === 1 ? m.target : m.target.parentNode;
      if (!t || !t.closest) return;
      if (t.closest('.fvoc')) return;                       // this file's own drawing
      if (m.type === 'childList') {
        var nodes = Array.prototype.slice.call(m.addedNodes).concat(Array.prototype.slice.call(m.removedNodes));
        if (nodes.length && nodes.every(mine)) return;      // the block put in or taken out
        // a chapter, a paragraph, a level that has just arrived
        Array.prototype.forEach.call(m.addedNodes, function (n) {
          if (n.nodeType !== 1) return;
          if (n.matches('.pass.p2')) mark(n);
          Array.prototype.forEach.call(n.querySelectorAll('.pass.p2'), mark);
        });
      }
      mark(t.closest('.pass.p2'));                          // a row painted again
    });
    if (dirty.length && !timer) timer = setTimeout(flush, 40);
  }
  function watch(on) {
    if (!root.MutationObserver) return;
    if (on && !watcher) {
      watcher = new MutationObserver(seen);
      watcher.observe(main(), {childList: true, subtree: true, characterData: true});
    } else if (!on && watcher) {
      watcher.disconnect();
      watcher = null;
      dirty = [];
    }
  }

  /* ------------------------------------------------------------ the pencil
     The reader's pencil (#chpen, placed by the page's penPlace) stands INSIDE
     the top right corner of the row it is for, and the ⚑ of lib/later-reader.js
     to its left.  A row as wide as the page had room there; a column as wide as
     its words has not -- in a language read from the right that corner is the
     chunk's first word -- and the lines of a flow are close: over a column of
     the second line is the meaning of the one above.  So while the layout is
     on, each time the page has placed the pencil of a column, the pair (flag,
     pencil) is put again, WHERE NO TEXT IS DRAWN, the first of these that is
     free of every letter around (the text, a reading over it, a gloss line, a
     line of the vocabulary):
       1. on the column's corner, over the room between the lines (where the
          page's own corner is; a column narrower than the pair has it start on
          the column's start edge);
       2. over the column still, further along it;
       3. on the column's first line, past the end of its text;
       4. on that line, before its start (the margin, for a line's first chunk);
       5. under the column, as over it;
     then, where the lines are too close for any of these, the same five with
     the two buttons made lower, down to the height of their signs (.flowtight,
     lib/parseh.css);
     and, where the page is so full that none is free, the one that covers the
     least.  The pair never leaves the window, and its two buttons never share
     room: the pencil is put a flag's width in, so the flag has its place. */
  function penHolder() {
    try { return typeof penFor !== 'undefined' ? penFor : null; } catch (e) { return null; }  // the page's own
  }
  /* WHERE THE INK OF A PIECE OF TEXT IS.  The box of a run of text is as tall
     as its FONT (its highest accent to its lowest tail, whatever is written):
     a third taller than the letters in a Persian face, so that the boxes of
     two lines one under the other meet though nothing drawn does.  A canvas
     says how far the ink of these very letters goes above and below their
     baseline, and how far the font does; the box is cut down to the ink. */
  var inkCtx = null, inkSeen = {};
  function inkOf(node, b) {
    try {
      var cs = root.getComputedStyle(node.parentNode);
      var font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily, key = font + '\n' + node.nodeValue;
      var m = inkSeen[key];
      if (!m) {
        if (!inkCtx) inkCtx = document.createElement('canvas').getContext('2d');
        inkCtx.font = font;
        var t = inkCtx.measureText(node.nodeValue);
        m = inkSeen[key] = [t.fontBoundingBoxAscent, t.fontBoundingBoxDescent, t.actualBoundingBoxAscent, t.actualBoundingBoxDescent];
      }
      var tall = m[0] + m[1], k = b.height / tall;
      if (!(tall > 0) || !(k > 0.8 && k < 1.25) || !(m[2] + m[3] > 0)) return b;       // another face drew it: the whole box
      var line = b.top + m[0] * k;
      return {left: b.left, right: b.right, top: Math.max(b.top, line - m[2] * k), bottom: Math.min(b.bottom, line + m[3] * k)};
    } catch (e) { return b; }
  }
  // every piece of text drawn in an element, as the boxes its ink takes
  function lettersOf(scope, from, to, out) {
    var w = document.createTreeWalker(scope, 4 /* SHOW_TEXT */, null), g = document.createRange(), n;
    while ((n = w.nextNode())) {
      if (!/\S/.test(n.nodeValue)) continue;
      g.selectNodeContents(n);
      var rs = g.getClientRects();
      for (var i = 0; i < rs.length; i++)
        if (rs[i].width > 0 && rs[i].height > 0 && rs[i].bottom > from && rs[i].top < to) out.push(inkOf(n, rs[i]));
    }
    return out;
  }
  // what is written around a column: its own sentence, the one before and the one after
  function around(row, from, to) {
    var sub = row.closest('.sub') || row.parentNode, out = [];
    var near = function (step) {
      for (var e = sub; e && e !== main() && e !== document.body; e = e.parentNode)
        if (e[step]) return e[step];
      return null;
    };
    [near('previousElementSibling'), sub, near('nextElementSibling')].forEach(function (scope) {
      if (!scope || (scope !== sub && scope.contains(sub))) return;
      var b = scope.getBoundingClientRect();
      if (b.bottom <= from || b.top >= to) return;
      lettersOf(scope, from, to, out);
    });
    return out;
  }
  function covered(x, y, w, h, letters) {
    var sum = 0;
    for (var i = 0; i < letters.length; i++) {
      var b = letters[i];
      var dx = Math.min(x + w + 1, b.right) - Math.max(x - 1, b.left), dy = Math.min(y + h + 0.5, b.bottom) - Math.max(y - 0.5, b.top);
      if (dx > 0 && dy > 0) sum += dx * dy;
    }
    return sum;
  }
  function liftPen() {
    var pen = document.getElementById('chpen'), el = penHolder(), flag = flagEl();
    var fa = el && el.isConnected && el.classList.contains('row') && el.closest('.pass.p2') ? el.querySelector('.fa') : null;
    var r = fa ? el.getBoundingClientRect() : null;
    if (!active || !pen || pen.hidden || !fa || !r.width) {
      // the pencil of anything else is the page's, as the page draws it
      [pen, flag].forEach(function (b) {
        if (!b || !b.classList.contains('flowtight')) return;
        b.classList.remove('flowtight');
        b.style.removeProperty('--flowpad');
      });
      return;
    }
    watchFlag();
    var rtl = root.getComputedStyle(el.parentNode).direction === 'rtl';
    var pw = pen.offsetWidth, h = pen.offsetHeight + (pen.classList.contains('flowtight') ? 2 * (PAD - (parseFloat(pen.style.getPropertyValue('--flowpad')) || 0)) : 0);
    // the flag stands 4px to the pencil's left (lib/later-reader.js); it is not drawn in the mobile mode
    var fw = 0;
    if (flag && root.getComputedStyle(flag).display !== 'none') fw = flag.offsetWidth + 4;
    else if (flag && flag.hidden && document.documentElement.getAttribute('data-mode') !== 'mobile') fw = flagWide + 4;
    if (flag && flag.offsetWidth) flagWide = flag.offsetWidth;
    var W = fw + pw, maxX = Math.max(0, root.innerWidth - W - 4);
    // the letters of the text itself on its first line (a reading over them is not what the line is measured by)
    var base = [], wk = document.createTreeWalker(fa, 4, null), g = document.createRange(), n;
    while ((n = wk.nextNode())) {
      if (!/\S/.test(n.nodeValue) || (n.parentNode.closest && n.parentNode.closest('rt, rp'))) continue;
      g.selectNodeContents(n);
      Array.prototype.push.apply(base, Array.prototype.slice.call(g.getClientRects()));
    }
    base = base.filter(function (b) { return b.width > 0; });
    var line = base.length ? base.filter(function (b) { return b.top < base[0].bottom - 1 && b.bottom > base[0].top + 1; }) : [];
    var lineBox = null;
    if (line.length) lineBox = {l: Math.min.apply(null, line.map(function (b) { return b.left; })), r: Math.max.apply(null, line.map(function (b) { return b.right; })),
                                mid: (line[0].top + line[0].bottom) / 2};
    var corner = r.width >= W + 4 ? r.right - 4 - W : (rtl ? r.right - W : r.left);
    var letters = around(el, r.top - h - 8, r.bottom + h + 8);
    // the places, for a pair this tall, in the order they are liked
    var spotsFor = function (h) {
      var spots = [];
      var put = function (x, y) { spots.push([Math.round(Math.max(0, Math.min(maxX, x))), Math.round(Math.max(0, y))]); };
      // over the column at x: down to the ink of the line it is over (its accents, a reading), and no further
      // into the line than the room a first line keeps over its letters
      var over = function (x) {
        x = Math.max(0, Math.min(maxX, x));
        var foot = r.top + 12;
        for (var i = 0; i < letters.length; i++) {
          var b = letters[i];
          if (b.bottom > r.top && b.right > x - 1 && b.left < x + W + 1) foot = Math.min(foot, b.top - 0.5);
        }
        put(x, Math.floor(foot) - h);
      };
      over(corner);                                                   // 1. the corner
      var lo = Math.min(corner, r.left - 6), hi = Math.max(corner, r.right + 6 - W), along = [];
      for (var x = lo; x <= hi; x += 5) along.push(x);
      along.sort(function (a, b) { return Math.abs(a - corner) - Math.abs(b - corner); });
      along.forEach(over);                                            // 2. along the column, the nearest to the corner first
      if (lineBox) {                                                  // 3. and 4. beside the first line
        put(rtl ? lineBox.l - 5 - W : lineBox.r + 5, lineBox.mid - h / 2);
        put(rtl ? Math.max(lineBox.r, r.right) + 5 : Math.min(lineBox.l, r.left) - 5 - W, lineBox.mid - h / 2);
      }
      // 5. under the column, as over it: up to the ink of its last line
      var under = function (x) {
        x = Math.max(0, Math.min(maxX, x));
        var head = r.bottom - 12;
        for (var i = 0; i < letters.length; i++) {
          var b = letters[i];
          if (b.top < r.bottom && b.right > x - 1 && b.left < x + W + 1) head = Math.max(head, b.bottom + 0.5);
        }
        put(x, Math.ceil(head));
      };
      under(corner);
      along.forEach(under);
      return spots;
    };
    var best = null, least = Infinity, pad = PAD;
    var look = function (h, p) {
      var spots = spotsFor(h);
      for (var i = 0; i < spots.length; i++) {
        var c = covered(spots[i][0], spots[i][1], W, h, letters);
        if (c < least) { least = c; best = spots[i]; pad = p; }
        if (!c) return true;
      }
      return false;
    };
    // as they are; and where the lines are too close for that, the two made lower, a pixel
    // off the top and one off the bottom at a time (lib/parseh.css, .flowtight)
    for (var p = PAD; p >= 0 && !look(h - 2 * (PAD - p), p); p--);
    [pen, flag].forEach(function (b) {
      if (!b) return;
      b.classList.toggle('flowtight', pad < PAD);
      if (pad < PAD) { if (b.style.getPropertyValue('--flowpad') !== pad + 'px') b.style.setProperty('--flowpad', pad + 'px'); }
      else if (b.style.getPropertyValue('--flowpad')) b.style.removeProperty('--flowpad');
    });
    var top = best[1] + 'px', left = (best[0] + fw) + 'px';
    if (pen.style.top !== top) pen.style.top = top;
    if (pen.style.left !== left) pen.style.left = left;
  }
  var flagWide = 25, flagWatch = null, PAD = 3;     // the room the page gives each button over and under its sign (#chpen, .later-flag: 3px)
  function flagEl() { return document.querySelector('.later-flag'); }
  function watchPen() {
    var pen = document.getElementById('chpen');
    if (penWatch || !pen || !root.MutationObserver) return;
    penWatch = new MutationObserver(liftPen);
    penWatch.observe(pen, {attributes: true, attributeFilter: ['style', 'hidden']});
  }
  // the flag is as wide as what it says (⚑, ✓⚑): once it is drawn, the pair is measured again
  function watchFlag() {
    var flag = flagEl();
    if (flagWatch || !flag || !root.MutationObserver) return;
    flagWatch = new MutationObserver(liftPen);
    flagWatch.observe(flag, {attributes: true, attributeFilter: ['style', 'hidden'], childList: true, characterData: true, subtree: true});
    // Beside a column the flag may be the nearer of the two; the page gives the
    // pointer a moment to get from a chunk onto the PENCIL and knows nothing of
    // the flag, so a pointer that has reached the flag is told as one on the
    // pencil: the pencil stays for it to go on to.
    flag.addEventListener('mouseenter', function () {
      var pen = document.getElementById('chpen');
      if (active && pen && !pen.hidden) pen.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
    });
  }

  /* A SHIFT-CLICK COPIES THE CHUNK (the page's own handler: the chunk, a row's
     text, or the whole level where the click lands beside one).  Two things
     differ in this layout, and both are answered here -- the window hears a
     click before the document does, so the page's handler never has to tell:
       - a line of the vocabulary block copies the text of the chunk the line
         is for, as a click on that chunk's gloss in its row does;
       - BESIDE the columns (the space between two of them, the rest of a line
         after its last one, the block's own margin) the click is on the level
         itself, which the rows never left bare.  The page would copy all that
         is written in the level -- every gloss, and each vocabulary line
         twice, the row's and its copy.  What is copied is THE SENTENCE: the
         chunks' own texts, in order.  (The held finger's "Copy the sentence",
         lib/wordtouch.js, comes through here as well.) */
  function sentenceOf(p2) {
    var say = function (e) { return (typeof root.textOf === 'function' ? root.textOf(e) : e.textContent).trim(); };
    var parts = rowsOf(p2).map(function (row) { var fa = row.querySelector('.fa'); return fa ? say(fa) : ''; })
                          .filter(function (t) { return t; });
    // joined as the language writes: with spaces, unless its sentences have none
    var sub = p2.closest('.sub'), p1 = sub && sub.querySelector('.pass.p1');
    var spaced = !p1 || parts.length < 2 || /\S\s+\S/.test(say(p1));
    return parts.join(spaced ? ' ' : '');
  }
  root.addEventListener('click', function (e) {
    if (!active || !e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target && e.target.closest ? e.target : null;
    if (!t) return;
    var P = root.Parseh, text = null;
    if (!P || typeof P.copy !== 'function') return;
    var line = t.closest('.fvoc .fv[data-for]');
    if (line) {
      var p2 = line.closest('.pass.p2');
      var row = p2 && p2.querySelector('.row[data-c="' + line.getAttribute('data-for') + '"]');
      var fa = row && row.querySelector('.fa');
      if (fa) text = typeof root.textOf === 'function' ? root.textOf(fa) : fa.textContent;
    } else if (t.matches('.pass.p2') || t.matches('.pass.p2 > .fvoc')) {
      text = sentenceOf(t.closest('.pass.p2'));
    }
    if (text == null) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    P.copy(text);
  }, true);

  /* ------------------------------------------------------------- the state */
  function apply(on) {
    on = !!on;
    if (!document.body) return;
    document.body.classList.toggle(CLS, on);
    if (on === active) return;
    active = on;
    if (on) { buildAll(); watch(true); watchPen(); }
    else { watch(false); clearAll(); }
    tell();
  }
  function start() {
    apply(stored());
    // the same choice made in another tab of this browser
    root.addEventListener('storage', function (e) {
      if (e.key === KEY || e.key === null) apply(stored());
    });
  }

  root.ParsehFlow = {
    get: function () { return active; },
    set: function (on) {
      try { root.localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
      apply(on);
    },
    on: function (fn) {
      fns.push(fn);
      return function () { var i = fns.indexOf(fn); if (i >= 0) fns.splice(i, 1); };
    }
  };

  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})(window);
