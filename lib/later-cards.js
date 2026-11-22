// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — REVIEW LATER: the cards made from the list, one by one and one
   after another (a0.5.0).

   The list of a book or a video (lib/later.js) has two doors to the page's
   own card sheet: «+ card» on a row, and «Make cards one after another» over
   the list.  What opens the sheet, and how the page knows that a card was
   SAVED, is each page's own (the reader's layer, lib/later-reader.js; the
   player, youtube/lib/player.js) -- the sheet is theirs, with its three
   targets and its cut editor.  What the two have in common is here: ask the
   page to open its sheet for a flag, wait for how it ended, and for the
   queue, a strip over the sheet that says which item it is and lets the
   person Skip or Stop.

   THE PAGE HANDS OVER ONE FUNCTION, open(flag), which answers (a promise of)
   a SESSION, or null when the chunk is not there any more:

       { box:   the card sheet's own element, which the strip is put into
         done:  a promise of how the sheet ended -- 'saved' once a card was
                saved on ANY of its three targets (Anki, an exercise deck, the
                markdown on the clipboard), 'closed' when it was shut without
                one (Esc, ✕, the backdrop)
         close: shut the sheet, saved or not }

   HOW IT ENDS, in the queue: a saved card takes its flag off the list (with
   no «removed · Undo» line, which would say it again and again) and the next
   sheet opens a moment later, so that the sheet's own answer can be read;
   Skip leaves the flag where it is and opens the next; Stop, and the sheet
   shut by hand, end the queue -- the way out of a sheet is Esc, and it must
   not need pressing once more for every item left.

   The sheet's remembered target, deck and type stay as the page keeps them:
   nothing here touches them.  No HTML is made from a string in this file. */
(function () {
  'use strict';
  if (window.ParsehLaterCards) return;

  var READ_MS = 800;           // how long a saved card's answer is left to be read before the next sheet
  var running = null;          // the queue that is going, if one is

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
    b.addEventListener('click', on);
    return b;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
  function say(o, text, bad) {
    try {
      if (o && typeof o.say === 'function') o.say(text, bad);
      else if (window.Parseh && Parseh.toast) Parseh.toast(text, !!bad);
    } catch (e) {}
  }
  function opened(open, rec) {
    return Promise.resolve().then(function () { return open(rec); });
  }

  /* ONE CARD, from «+ card»: resolves {saved} -- the flag leaves the list when
     the card was saved (the panel does that), and stays when the sheet was
     shut without one.  A chunk that is not there is an error, which the panel
     says in its own words. */
  function one(open, rec) {
    return opened(open, rec).then(function (s) {
      if (!s) throw new Error('this chunk is no longer where it was');
      return s.done.then(function (how) { return {saved: how === 'saved'}; });
    });
  }

  /* THE STRIP: «item 2 of 7 · Skip · Stop», the first thing in the card
     sheet, so that it is over the card's own fields and under nothing, in the
     sheet's own width, and the page's sheet is not covered by it anywhere. */
  function strip(skipTitle) {
    var bar = el('div', 'lq-strip');
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'cards one after another');
    bar.setAttribute('lang', 'en');
    bar.setAttribute('dir', 'ltr');
    var n = el('span', 'lq-n');
    n.setAttribute('aria-live', 'polite');
    bar.appendChild(n);
    var skip = button('lq-b lq-skip', 'Skip', skipTitle || 'leave this chunk on the list and go to the next', function () { bar.onSkip(); });
    var stop = button('lq-b lq-stop', 'Stop', 'make no more cards from the list', function () { bar.onStop(); });
    bar.appendChild(skip);
    bar.appendChild(stop);
    bar.onSkip = bar.onStop = function () {};
    bar.put = function (box, text) {
      n.textContent = text;
      if (box && bar.parentNode !== box) box.insertBefore(bar, box.firstChild);
    };
    bar.away = function () { if (bar.parentNode) bar.parentNode.removeChild(bar); };
    return bar;
  }

  /* ONE AFTER ANOTHER.  o = {records, open, say?} -> Promise<{saved, skipped,
     stopped}>.  `records` are in reading order, as the panel hands them.
     The vocabulary list (lib/vocab.js) makes its cards here too, from words
     that are not flags: it hands `listed(rec)` (is the item still to be made;
     a flag's answer is whether it is still flagged), `saved(rec)` (what a
     saved card does to the item; a flag's leaves the list) and `skipTitle`. */
  function queue(o) {
    if (running) return running;
    var recs = (o && o.records ? o.records : []).slice(), total = recs.length;
    var at = 0, saved = 0, skipped = 0, stopped = false, ended = false, bar = strip(o && o.skipTitle);
    var listed = (o && o.listed) || function (rec) { return !!(window.ParsehLater && ParsehLater.has(rec.id)); };
    var onSaved = (o && o.saved) || function (rec) { ParsehLater.remove(rec.id, {toast: false}); };
    var going = new Promise(function (finish) {
      function end() {
        bar.away();
        ended = true;
        running = null;
        var said = saved ? plural(saved, 'card') + ' saved' : 'no card saved';
        if (skipped) said += ' · ' + skipped + ' skipped';
        if (stopped && at < total) said += ' · stopped';
        say(o, said);
        finish({saved: saved, skipped: skipped, stopped: stopped});
      }
      function step() {
        if (stopped || at >= total) { end(); return; }
        var rec = recs[at++], place = at;
        // taken off the list since the queue was made: nothing to make
        if (!listed(rec)) { step(); return; }
        opened(o.open, rec).then(function (s) {
          if (!s) { skipped++; step(); return; }
          var cause = null;
          bar.onSkip = function () { cause = 'skip'; s.close(); };
          bar.onStop = function () { cause = 'stop'; s.close(); };
          bar.put(s.box, 'item ' + place + ' of ' + total);
          s.done.then(function (how) {
            if (how === 'saved') {
              saved++;
              onSaved(rec);
              setTimeout(function () { s.close(); step(); }, READ_MS);
              return;
            }
            if (cause === 'skip') { skipped++; step(); return; }
            // Stop, or the sheet shut by hand
            stopped = true;
            end();
          });
        }, function () { skipped++; step(); });
      }
      step();
    });
    // a queue with nothing to do has ended before it is returned
    if (!ended) running = going;
    return going;
  }

  window.ParsehLaterCards = {one: one, queue: queue, active: function () { return !!running; }};
})();
