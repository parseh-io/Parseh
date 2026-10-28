// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — what the server is working on, shown on every page.
   Served at /lib/activity.js.  lib/parseh.js loads it on every page that
   has parseh.js (the hub, the two libraries, the book reader, the player,
   the add pages, the Reading help page, the Anki wizard, the clip tray), and the
   studio's and the exercises' templates carry a tag of their own, because
   they do not load parseh.js.  A studio run on its own has no /lib/ at
   all: the tag 404s and every page there works exactly as before.

   WHY.  Building a book's PDF takes minutes; a backup of a shelf of narrated
   books, or a film brought back in a bundle, is gigabytes going through one
   request.  None of that used to say anything outside the page that started
   it, and often not there either: a restore still running looked exactly
   like one that had died, and the hub -- where a person goes to do the next
   thing -- never knew.  The server keeps the list (lib/activity.py, merged
   with the book builds and the dictionary downloads by serve.py) and this
   draws it:

     * a pill in the bottom corner of every page -- a spinner, "Working:"
       and what, "+N more" -- which opens into the whole list, each with its
       time and, where the bytes are counted, how far it has got;
     * on the hub, a panel under the brand as well, one row a task;
     * a short "Done" when something this page saw running has finished.
       Errors are not said here: the page that started the work says them,
       in its own toast, with the server's own sentence.

   POLLED, every 1.5 s while anything runs (or this page has just started
   something) and every 5 s otherwise, and not at all while the tab is
   hidden -- it asks again the moment it is shown.

   AND THE SAME POLL IS THE PAGE'S ONE QUESTION "IS THE COMPUTER THERE?"
   (TO-DO §2.24): every other script that wants to know listens to this one
   rather than asking the server itself -- see "asking the server", below.

   THE PAGE THAT STARTS THE WORK SHOWS IT AT ONCE, before any poll:

     ParsehActivity.local(label)        -> handle: .end(ok), .progress(done,
                                           total), .job, .url(u)
     ParsehActivity.track(fn, label)    -> fn(handle)'s promise, the entry
                                           ended when it settles
     ParsehActivity.expect(label)       -> a handle that ends itself when
                                           the server's entry for .job ends
     ParsehActivity.download(url, label)   a download by location.href

   A handle's .url(u) puts ?job=<its token> on the request, and the server
   records the token on its entry: that is how the page knows the entry is
   its own (shown once, not twice), and how a DOWNLOAD STARTED BY A PLAIN
   LINK is followed at all.  The browser's own download manager keeps the
   download -- a fetch and a blob would hold a whole shelf in the tab's
   memory and hide the browser's progress -- so a click on such a link is
   answered here with "Preparing the download…" at once, the link is given
   a token for that one click, and the entry lives until the server's entry
   with that token has come and gone (or never came, after a while). */
(function () {
  'use strict';
  if (window.ParsehActivity) return;          // two tags on one page: one list
  // A NOTE OPENED OVER A BOOK OR A VIDEO is a studio page in a frame: the
  // page around it already shows the list, and a second pill inside the
  // frame would be the same list twice.  Its work goes on that page's list
  // (framed(), below: its download links followed there too, and its own
  // entries let go when the frame is closed under them).
  if (window.parent !== window) {
    try {
      var up = window.parent.ParsehActivity;
      if (up) {
        window.ParsehActivity = up.framed ? up.framed(window) : up;
        return;
      }
    } catch (e) { /* another origin's frame: draw our own */ }
  }

  var FAST = 1500, SLOW = 5000;
  // while work counted in ITEMS runs (the LaTeX drawings of many documents: a share of what there is to do, each drawing
  // that is over moves the bar) the list is asked more often, so that the bar goes on in small steps and not in a few jumps
  var COUNTED = 600;
  var FLASH_MS = 3000;           // how long "Done" stays
  var EXPECT_MS = 20000;         // a download whose entry never shows is let go
  // THE ADDRESSES serve.py puts on the list as downloads (long_work there).
  // A link to one of these is followed by its token; any other link is not
  // touched.
  var DOWNLOAD = /(\/__download\/?|\/__backup|\/__narration\/export|\/api\/backup|\/api\/export|\/api\/decks\/[^\/]+\/[^\/]+\/export|\/download\/[a-z0-9-]+\/(zip|pdf|html)|\/anki\/build\/.+\.apkg)$/;

  var offDisk = location.protocol === 'file:';
  var server = {running: [], finished: []};
  var skew = 0;                  // the server's clock minus this one, in ms
  var since = null;              // the server's time at the first answer
  var locals = [];               // this page's own work, newest last
  var seen = {};                 // entry ids and tokens this page saw running
  var flashed = {};              // ... and those it has already said "Done" for
  var flash = null;              // {label, until, mine}: mine is this page's own work
  var timer = null, dead = false, hot = 0;
  var open = false;              // the pill's list is shown
  var mini = false;              // shrunk to its spinner, until the list empties
  var ui = null, hub = null;
  var hubSeen = false;           // the hub's panel is on the screen

  // THE OTHER TABS ARE TOLD when this one starts or ends something, and ask
  // the server at once instead of at their next slow poll: the hub open in
  // another tab shows an upload begun here within a moment, not five seconds
  var tabs = null;
  try { tabs = new BroadcastChannel('parseh-activity'); } catch (e) { tabs = null; }
  function tell() { try { if (tabs) tabs.postMessage('changed'); } catch (e) {} }
  if (tabs) tabs.onmessage = function () { hot = Date.now() + 10000; poke(250); };

  function token() {
    var s = '';
    for (var i = 0; i < 12; i++) s += 'abcdefghijkmnpqrstuvwxyz23456789'.charAt(Math.floor(Math.random() * 32));
    return s;
  }
  function withJob(u, job) {
    u = String(u);
    var hash = '', at = u.indexOf('#');
    if (at >= 0) { hash = u.slice(at); u = u.slice(0, at); }
    return u + (u.indexOf('?') >= 0 ? '&' : '?') + 'job=' + encodeURIComponent(job) + hash;
  }

  /* ---- this page's own work ---- */
  function local(label, opts) {
    opts = opts || {};
    var h = {job: token(), label: String(label || 'Working…'), started: Date.now(),
             done: null, total: null, follow: !!opts.follow, seen: false, ended: false,
             until: opts.follow ? Date.now() + EXPECT_MS : 0};
    h.url = function (u) { return withJob(u, h.job); };
    h.progress = function (done, total) {
      h.done = done; h.total = total == null ? h.total : total; draw();
    };
    h.set = function (text) { if (text) { h.label = String(text); draw(); } };
    // the server answered with the name of an entry that is not the
    // request's -- a book build is a job of its own, which outlives the
    // request that started it (or was already running): that one is this
    // page's now
    h.adopt = function (id) { if (id) { h.job = String(id); poke(); } };
    h.end = function (ok) {
      if (h.ended) return;
      h.ended = true;
      locals = locals.filter(function (x) { return x !== h; });
      // "Done" only for work that went through, and only once: the server's
      // entry for the same token will not say it a second time
      var entry = findFinished(h.job);
      if (ok !== false && (!entry || entry.ok))
        sayDone((entry && entry.label) || h.named || h.label, h.job, true);
      flashed[h.job] = 1;
      draw();
      poke(400);
      tell();
    };
    locals.push(h);
    hot = Date.now() + 10000;       // poll fast for a while: the entry is coming
    draw();
    poke(300);
    tell();
    return h;
  }
  function track(work, label) { return settle(local(label), work); }
  // the entry `h` ends when `work` (a promise, a function returning one, or
  // an XMLHttpRequest) is over
  function settle(h, work) {
    var p;
    try { p = typeof work === 'function' ? work(h) : work; }
    catch (e) { h.end(false); throw e; }
    if (p && typeof p.then === 'function') {
      p.then(function () { h.end(true); }, function () { h.end(false); });
    } else if (p && typeof p.addEventListener === 'function' && 'readyState' in p) {
      // an XMLHttpRequest, which knows how much of an upload has gone
      if (p.upload) p.upload.addEventListener('progress', function (e) {
        if (e.lengthComputable) h.progress(e.loaded, e.total);
      });
      p.addEventListener('loadend', function () { h.end(p.status > 0 && p.status < 400); });
    } else {
      h.end(true);
    }
    return p;
  }
  function expect(label) { return local(label, {follow: true}); }
  function download(url, label) {
    var h = expect(label || 'Preparing the download…');
    location.href = h.url(url);
    return h;
  }

  /* A CLICK ON A DOWNLOAD LINK: the token goes on the address for this one
     click and comes off again straight after, so the next click gets a
     fresh one and the page's own markup is left as it was.  Bubbling, and
     after the page's own handlers: a click one of them has taken over
     (preventDefault) is not a download. */
  function guess(path) {
    if (/\.apkg$/.test(path)) return 'Building the Anki deck…';
    if (/backup$|\/api\/export$/.test(path)) return 'Packing the backup…';
    if (/narration\/export$/.test(path)) return 'Packing the narration…';
    if (/\/export$/.test(path)) return 'Exporting the deck…';
    return 'Preparing the download…';
  }
  function hook(doc) { doc.addEventListener('click', onClick, false); }
  function onClick(e) {
    if (e.defaultPrevented || e.button !== 0) return;
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var u;
    try { u = new URL(a.href, location.href); } catch (err) { return; }
    if (u.origin !== location.origin || !DOWNLOAD.test(u.pathname)) return;
    var h = expect(guess(u.pathname));
    var was = a.getAttribute('href');
    a.setAttribute('href', h.url(a.href));
    setTimeout(function () { a.setAttribute('href', was); }, 0);
  }

  /* ---- asking the server, and whether it is there at all ---- */
  /* ONE QUESTION, ASKED HERE AND NOWHERE ELSE (TO-DO §2.24, decided with the
     owner 2026-09-24).  `/__activity` used to be asked by three things at
     once -- this list, lib/keep.js's probe every twenty seconds, and every
     watched ask of lib/parseh.js and static/app.js every three -- and none of
     them ever cancelled an ask it had given up on.  A browser opens six
     connections to an HTTP/1.1 server, and an ask abandoned but not cancelled
     keeps its own: driven, six of them made the next ask of a computer that
     answers in 2 ms wait five seconds.  On a slow tunnel that was a loop --
     a slow answer, a probe beside it, the probe late, "away" -- and it
     declared a computer gone that was right there.  So the list and the
     question share this one poll, one ask at a time, and an ask given up on
     is cancelled.

     WHAT "AWAY" MEANS.  The owner: "Offline will mean drastic things
     usually, it's not a status that should change fast ... We should not
     talk of offline for simply having a slow connection."  So:

       an answer, however late      -> THERE.  Slow is online.
       three asks in a row that fail at once, two seconds apart
                                    -> AWAY, in about four seconds.  A socket
                                       refused, a name not found, no route:
                                       the network itself saying no.  Once is
                                       not enough, because Chrome fails
                                       whatever is in flight the moment a
                                       phone changes network.
       the browser says there is no network, and an ask fails
                                    -> AWAY, at once.
       three asks across 45 s, and not one answered
                                    -> AWAY.  Over Tailscale a computer
                                       switched off or asleep is SILENT, not
                                       refused -- and silence is also what a
                                       slow link looks like at first.  Only
                                       time tells the two apart.
       no answer 5 s after the quiet began
                                    -> SLOW, which is still online:
                                       lib/keep.js says "checking…".

     A failed fetch never says why -- one TypeError, one message, whatever
     happened -- so how soon it failed is the only instrument there is.  Time
     the page spends hidden is not silence: the ask out is dropped uncounted
     and asked again when the page is seen.  lib/sw.js leaves this address to
     the browser, so what arrives here is the network's own answer and not a
     worker's guess at one.

     Whoever wants the answer listens for `parseh:reach` on the document, or
     asks `ParsehActivity.reach()`: {state: unknown | there | slow | away,
     why, since, asks}.  An AWAY is said again at every ask that goes
     unanswered after it, so what is written down for the next page stays
     as recent as the silence it describes. */
  var NO_SOONER = 3000;       // failing sooner than this is the network saying no
  var NO_AGAIN = 2000;        // ... which is asked again this soon
  var NOS = 3;                // ... and believed at the third in a row
  var LATE = 5000;            // no answer this long after the quiet began: slow
  var PATIENCE = 15000;       // one ask is given this long, then cancelled
  var WINDOW = 45000;         // silence across this long ...
  var ASKS = 3;               // ... and this many asks is away
  var reach = {state: 'unknown', why: '', quiet: 0, asks: 0, nos: 0};
  var asking = null;          // the ask out now: {began, ctl, cut, late, heard, done}
  var waiting = [];           // the worker's questions (below) not yet answered

  function busy() {
    return server.running.length > 0 || locals.length > 0 || !!flash || Date.now() < hot;
  }
  function schedule(ms) {
    clearTimeout(timer);
    timer = null;
    if (dead || offDisk || document.hidden) return;
    timer = setTimeout(poll, ms);
  }
  function poke(ms) { schedule(ms == null ? 0 : ms); }
  // when to ask next: soon after a refusal (a second is not a verdict), at
  // once after a silence (the window is three asks, not three waits), at
  // once too when the worker is waiting to hear that the computer answers (an
  // ask that ended a moment before its question came would otherwise take the
  // answer away, and the next ask is seconds off), and at the list's own pace
  // otherwise -- still asking once away, for the page that comes after this one
  function next() {
    if (reach.state === 'away') return PATIENCE;
    if (reach.asks) return reach.nos ? NO_AGAIN : 0;
    return waiting.length ? 0 : counting() ? COUNTED : busy() ? FAST : SLOW;
  }
  function counting() {
    return server.running.some(function (e) { return e.unit === 'items'; });
  }
  function poll() {
    timer = null;
    if (asking || dead || offDisk) return;
    var me = {began: Date.now(), heard: false, done: false,
              ctl: window.AbortController ? new AbortController() : null};
    asking = me;
    me.cut = setTimeout(function () {
      heard(me, 'silent');
      if (me.ctl) me.ctl.abort();
      over(me);
    }, PATIENCE);
    // "checking…" once the quiet has lasted LATE, counted from when it began
    me.late = setTimeout(function () { if (!me.heard) quiet(); },
                         Math.max(0, (reach.quiet || me.began) + LATE - Date.now()));
    var failed = function () { heard(me, Date.now() - me.began < NO_SOONER ? 'no' : 'failed'); };
    fetch('/__activity', {cache: 'no-store', credentials: 'same-origin',
                          signal: me.ctl ? me.ctl.signal : undefined})
      .then(function (r) {
        if (me.heard) return null;
        // no list on this server (a studio run on its own): it answered, and
        // there is nothing more to ask it
        if (r.status === 404) { heard(me, 'answer'); dead = true; return null; }
        // a worker from before this change still answers this address itself
        // when the computer does not, with a refusal of its own (lib/sw.js,
        // `refused`): that is the network failing, not the computer speaking
        if (r.status === 503)
          return r.json().then(function (j) {
            if (j && j.offline === true) failed(); else heard(me, 'answer');
          }, function () { heard(me, 'answer'); });
        heard(me, 'answer');
        return r.json().then(function (j) {
          // a fault in drawing is this script's, not the network's: said, and
          // never counted as the server going away
          if (j && j.running) { try { took(j); } catch (e) { console.error('[activity]', e); } }
        }, function () { /* an answer that is not the list: still an answer */ });
      })
      .catch(function () { if (!me.heard) failed(); })
      .then(function () { over(me); });
  }
  function over(me) {
    if (me.done) return;
    me.done = true;
    clearTimeout(me.cut);
    clearTimeout(me.late);
    if (asking === me) asking = null;
    schedule(next());
  }
  // an ask whose end this page will not see -- hidden, or the network just
  // changed under it -- is not silence: dropped, uncounted, and the quiet
  // that was building starts again
  function drop() {
    var me = asking;
    if (me) {
      me.heard = true;
      if (me.ctl) me.ctl.abort();
      over(me);
    }
    if (reach.state !== 'away') { reach.quiet = 0; reach.asks = 0; reach.nos = 0; }
  }
  function heard(me, kind) {
    if (me.heard) return;
    me.heard = true;
    var now = Date.now();
    if (kind === 'answer') {
      reach.quiet = 0; reach.asks = 0; reach.nos = 0;
      said('there', '');
      // whoever asked whether the computer answers has its answer: it did
      waiting.splice(0).forEach(function (port) { port.postMessage({state: 'there'}); });
      return;
    }
    if (!reach.quiet) reach.quiet = me.began;
    reach.asks++;
    reach.nos = kind === 'no' ? reach.nos + 1 : 0;
    if (kind !== 'silent' && navigator.onLine === false) said('away', 'no network');
    else if (reach.nos >= NOS) said('away', 'refused');
    else if (reach.asks >= ASKS && now - reach.quiet >= WINDOW) said('away', 'silent');
    else if (reach.state === 'away') said('away', reach.why);
    else if (now - reach.quiet >= LATE) said('slow', '');
  }
  function quiet() {
    if (reach.state !== 'away' && reach.state !== 'slow') said('slow', '');
  }
  function reachNow() {
    return {state: reach.state, why: reach.why, since: reach.quiet, asks: reach.asks};
  }
  /* THE WORKER'S ONE QUESTION (lib/sw.js, `computerAnswers`; the owner,
     2026-09-28).  A navigation to a page this device has not kept, still
     unanswered after the worker's two and a half seconds, is not called
     lost by the worker on its own: it asks the open pages, through a port,
     whether the computer is answering them.  THIS POLL STAYS THE ONE ASKER
     of the computer -- the worker asks nothing of it, and here nothing is
     asked twice at once (`poll` refuses while an ask is out): the question
     only brings the next ask forward.  The reply is `there` when the
     computer's answer to it arrives, and never from memory (what this page
     heard five seconds ago says nothing of a computer suspended since); or
     `away` at once, when the page has judged it gone; and no reply at all
     from a page that is hidden, since a hidden page does not ask, nor from a
     computer that is silent -- the worker treats no reply as no.  It is
     the top page's alone: a frame has no poll of its own (above). */
  function questioned(e) {
    var port = e.data && e.data.reachAsk && e.ports && e.ports[0];
    if (!port) return;
    if (reach.state === 'away') { port.postMessage({state: 'away'}); return; }
    waiting.push(port);
    if (waiting.length > 4) waiting.shift();       // a long silence must not pile them up
    poke(0);
  }
  if (navigator.serviceWorker && !offDisk) navigator.serviceWorker.addEventListener('message', questioned);
  function said(state, why) {
    reach.state = state;
    reach.why = why;
    try { document.dispatchEvent(new CustomEvent('parseh:reach', {detail: reachNow()})); }
    catch (e) { /* a browser with no CustomEvent: reach() still says it */ }
  }
  function findFinished(job) {
    for (var i = 0; i < server.finished.length; i++) {
      var f = server.finished[i];
      if (f.job === job || f.id === job) return f;
    }
    return null;
  }
  function matches(e, h) { return !!h.job && (e.job === h.job || e.id === h.job); }
  function took(j) {
    skew = j.now * 1000 - Date.now();
    if (since === null) since = j.now;
    server = {running: j.running || [], finished: j.finished || []};
    server.running.forEach(function (e) { seen[e.id] = 1; if (e.job) seen[e.job] = 1; });
    // a download followed by its token ends when its entry has gone
    locals.slice().forEach(function (h) {
      if (!h.follow) return;
      var on = server.running.some(function (e) { return matches(e, h); });
      if (on) { h.seen = true; return; }
      var f = findFinished(h.job);
      if (f) { h.end(f.ok); return; }
      if (h.seen || Date.now() > h.until) h.end(h.seen);
    });
    // "Done" for work this page saw running, or that finished while it was
    // open -- a short job would otherwise come and go between two polls
    server.finished.forEach(function (f) {
      if (flashed[f.id] || (f.job && flashed[f.job])) return;
      flashed[f.id] = 1;
      if (f.job) flashed[f.job] = 1;
      if (f.ok && (seen[f.id] || (f.job && seen[f.job]) || f.finished >= since))
        sayDone(f.label, f.id);
    });
    draw();
  }
  function sayDone(label, key, mine) {
    if (key) flashed[key] = 1;
    flash = {label: label, until: Date.now() + FLASH_MS, mine: !!mine};
    setTimeout(function () {
      if (flash && Date.now() >= flash.until) { flash = null; draw(); }
    }, FLASH_MS + 50);
  }

  /* ---- what is shown ---- */
  // the list: this page's own work first (a local entry, or the server's
  // entry carrying its token), then everything else, oldest first
  function items() {
    var out = [], mine = {};
    locals.forEach(function (h) {
      var e = null;
      for (var i = 0; i < server.running.length; i++)
        if (matches(server.running[i], h)) { e = server.running[i]; break; }
      if (e) {
        mine[e.id] = 1;
        h.named = e.label;          // what "Done" will say: the server's words
        // the server knows the name and the size; the page may know the
        // progress sooner (an upload's own counter)
        var useLocal = e.total == null && h.total != null;
        out.push({key: e.id, label: e.label, started: e.started * 1000 - skew, stage: e.stage,
                  done: useLocal ? h.done : e.done, total: useLocal ? h.total : e.total,
                  counted: useLocal, unit: e.unit, page: null, mine: true});
      } else if (!(h.follow && findFinished(h.job))) {
        // the server's words once it has said them, even after its own
        // entry is over and the page has not yet said so
        out.push({key: 'local:' + h.job, label: h.named || h.label, started: h.started, stage: null,
                  done: h.done, total: h.total, counted: true, page: null, mine: true});
      }
    });
    server.running.forEach(function (e) {
      if (mine[e.id]) return;
      out.push({key: e.id, label: e.label, started: e.started * 1000 - skew, stage: e.stage,
                done: e.done, total: e.total, unit: e.unit, page: e.page, mine: false});
    });
    return out;
  }
  function clock(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    if (s < 60) return s + ' s';
    var h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, r = s % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') : '') + m + ':' + (r < 10 ? '0' : '') + r;
  }
  function bytes(n) {
    return n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + ' MB'
      : Math.max(1, Math.round(n / 1e3)) + ' kB';
  }
  // how far the bytes have got -- WHILE THEY ARE MOVING, as the server says
  // ("receiving", "sending") or as this page counts them itself (an upload's
  // own progress): once an upload is in and being installed, "100%" would
  // say it is over when it is not
  function pct(it) {
    if (!(it.total > 0) || it.done == null) return null;
    // WORK COUNTED IN ITEMS (the LaTeX drawings being made, lib/latexbatch.py) is a share of what there is to do, at
    // every moment of it: the stage is a word of its own ("the document it is on"), never a reason to hide the bar
    if (it.unit === 'items') return Math.min(100, Math.floor(100 * it.done / it.total));
    if (it.stage ? !/^(receiving|sending)$/.test(it.stage) : !it.counted) return null;
    return Math.min(100, Math.floor(100 * it.done / it.total));
  }
  function meta(it) {
    var bits = [], p = pct(it);
    if (it.stage) bits.push(it.stage);
    if (it.unit === 'items') { if (p !== null) bits.push(Math.min(it.done, it.total) + ' of ' + it.total); }
    else if (p !== null) bits.push(p + '% of ' + bytes(it.total));
    bits.push(clock(Date.now() - it.started));
    return bits.join(' · ');
  }
  function here(page) {
    return !page || page.split('#')[0] === location.pathname + location.search;
  }
  // a page on THIS server, which is all "open the page" may ever lead to:
  // the server keeps only such a path (activity.py's clean_page), and this
  // is the same rule again at the only place it becomes a link -- "//x/y"
  // or "/\x/y" would be another site to the browser
  function ours(page) {
    return typeof page === 'string' && /^\/(?![\/\\])[^\s\\]*$/.test(page);
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  /* One row a task, KEYED and updated in place: the list is redrawn every
     second for the clock, and a row rebuilt each time would take the focus
     off the link somebody has just tabbed to. */
  function row(li, it) {
    if (!li) {
      li = el('li', 'pa-row');
      var head = el('div', 'pa-head');
      head.appendChild(el('span', 'pa-spin'));
      head.appendChild(el('span', 'pa-lbl'));
      li.appendChild(head);
      var line = el('div', 'pa-meta');
      line.appendChild(el('span', 'pa-when'));
      var a = el('a', 'pa-open', 'open the page');
      line.appendChild(a);
      li.appendChild(line);
      var bar = el('div', 'pa-bar');
      bar.appendChild(el('i'));
      li.appendChild(bar);
    }
    li.setAttribute('data-key', it.key);
    setText(li.querySelector('.pa-lbl'), it.label);
    setText(li.querySelector('.pa-when'), meta(it));
    // the page it was started from, where that is another page: the way
    // back to it, from the hub above all
    var link = li.querySelector('.pa-open');
    var away = ours(it.page) && !here(it.page);
    link.hidden = !away;
    if (away && link.getAttribute('href') !== it.page) link.setAttribute('href', it.page);
    var p = pct(it), bar2 = li.querySelector('.pa-bar');
    bar2.hidden = p === null;
    if (p !== null) bar2.firstChild.style.width = p + '%';
    return li;
  }
  function fill(ul, list) {
    var had = {};
    Array.prototype.forEach.call(ul.children, function (li) { had[li.getAttribute('data-key')] = li; });
    var at = 0;
    list.forEach(function (it) {
      var li = row(had[it.key], it);
      delete had[it.key];
      if (ul.children[at] !== li) ul.insertBefore(li, ul.children[at] || null);
      at++;
    });
    Object.keys(had).forEach(function (k) { ul.removeChild(had[k]); });
  }

  function build() {
    if (ui || !document.body) return;
    style();
    // The live region is the pill's summary alone -- what is running and how
    // many -- so a screen reader hears a task begin and end, and not a
    // percentage every second and a half.
    var wrap = el('div');
    wrap.id = 'parseh-activity';
    wrap.hidden = true;
    wrap.setAttribute('lang', 'en');
    wrap.setAttribute('dir', 'ltr');
    var list = el('div', 'pa-list');
    list.id = 'parseh-activity-list';
    list.hidden = true;
    // A CORNER IS STILL A PLACE ON THE PAGE, and on a phone the pill sits on
    // whatever is at the bottom of the screen.  "shrink" folds it to its
    // spinner, out of the way, until everything running now is over; the
    // spinner opens this list again, where "full size" undoes it.
    var head = el('div', 'pa-top');
    var ttl = el('span', 'pa-ttl', '');
    var shrink = el('button', 'pa-shrink', 'shrink');
    shrink.type = 'button';
    shrink.title = 'fold the indicator down to its spinner until this work is over';
    head.appendChild(ttl);
    head.appendChild(shrink);
    var ul = el('ul');
    list.appendChild(head);
    list.appendChild(ul);
    var pill = el('button', 'pa-pill');
    pill.type = 'button';
    pill.setAttribute('aria-expanded', 'false');
    pill.setAttribute('aria-controls', list.id);
    pill.title = 'what the server is working on — click for the list';
    var spin = el('span', 'pa-spin');
    spin.setAttribute('aria-hidden', 'true');
    var say = el('span', 'pa-say');
    say.setAttribute('role', 'status');
    say.setAttribute('aria-live', 'polite');
    say.setAttribute('aria-atomic', 'true');
    var num = el('span', 'pa-pct');
    num.setAttribute('aria-hidden', 'true');
    var more = el('span', 'pa-more');
    pill.appendChild(spin); pill.appendChild(say); pill.appendChild(num); pill.appendChild(more);
    wrap.appendChild(list);
    wrap.appendChild(pill);
    document.body.appendChild(wrap);
    pill.addEventListener('click', function () { setOpen(!open); });
    shrink.addEventListener('click', function () { mini = !mini; setOpen(false); });
    document.addEventListener('keydown', function (e) {
      if (open && e.key === 'Escape') setOpen(false);
    });
    document.addEventListener('click', function (e) {
      if (open && !wrap.contains(e.target)) setOpen(false);
    });
    ui = {wrap: wrap, list: list, ttl: ttl, ul: ul, pill: pill, say: say, num: num, more: more,
          shrink: shrink};
    // THE HUB SAYS IT IN THE PAGE TOO, under the brand: it is the page a
    // person comes back to between two things, and a corner is easy to miss
    var main = document.querySelector('main.hub');
    if (main) {
      var sec = el('section', 'pa-hub');
      sec.id = 'parseh-working';
      sec.hidden = true;
      sec.setAttribute('aria-label', 'what the server is working on');
      var h2 = el('h2');
      h2.appendChild(el('span', 'pa-spin'));
      h2.appendChild(el('span', 'pa-hubttl', 'Working…'));
      sec.appendChild(h2);
      sec.appendChild(el('ul'));
      // the hub keeps a place for it (#hub-activity) above both of its
      // layouts, the browser one and the mobile one, so it shows in either
      var slot = document.getElementById('hub-activity');
      var brand = main.querySelector('.brand');
      if (slot) slot.appendChild(sec);
      else if (brand && brand.parentNode === main) main.insertBefore(sec, brand.nextSibling);
      else main.insertBefore(sec, main.firstChild);
      hub = sec;
      // WHILE THE PANEL IS ON THE SCREEN the pill says nothing it does not,
      // and on a phone it would sit on a door: it steps aside, and comes back
      // as soon as the panel is scrolled away
      if (window.IntersectionObserver) {
        new IntersectionObserver(function (seen) {
          hubSeen = seen[seen.length - 1].isIntersecting;
          draw();
        }).observe(sec);
      }
    }
  }
  /* THE PAGE'S OWN WORK IS NOT LEFT UNDER A DIMMED PAGE.  z 55 keeps the
     pill under every sheet and dialog, which is right for work started
     anywhere else.  But work is started from inside some of those: a note
     opened over a book or a video is a studio page in a frame, whose
     uploads and builds are this page's list's (framed()), and the reader's
     narration panel runs its own; the studio's dialogs send a backup while
     they wait.  All of them dim the page under a backdrop, and a pill under
     it said "Working" to nobody.  So while this page's own work is on, and
     what covers the pill's spot is a BACKDROP -- a fixed layer over the
     whole screen, above the pill -- the pill is lifted over it (pa-over).
     Never over a sheet, a panel or a dialog itself: where one of those is
     on the spot, the pill stays under it, so it covers no control somebody
     has opened.  Asked of the stack at the spot, whichever side of it the
     pill is on at the moment, so lifting it does not change the answer. */
  function overlaid() {
    if (!document.elementsFromPoint) return false;
    var r = ui.pill.getBoundingClientRect();
    if (!(r.width > 1)) return false;
    var at = document.elementsFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    for (var i = 0; i < at.length; i++) {
      if (ui.wrap.contains(at[i])) continue;
      return backdrop(at[i]);
    }
    return false;
  }
  function backdrop(e) {
    var cs = getComputedStyle(e);
    if (cs.position !== 'fixed' || !(parseInt(cs.zIndex, 10) > 55)) return false;
    var b = e.getBoundingClientRect();
    return b.left <= 1 && b.top <= 1 && b.right >= innerWidth - 1 && b.bottom >= innerHeight - 1;
  }
  function setOpen(v) {
    open = !!v && !ui.wrap.hidden;
    ui.list.hidden = !open;
    ui.pill.setAttribute('aria-expanded', open ? 'true' : 'false');
    draw();
  }
  function setText(node, text) { if (node.textContent !== text) node.textContent = text; }

  function draw() {
    if (!document.body) return;
    build();
    if (!ui) return;
    var list = items();
    var fl = flash && Date.now() < flash.until ? flash : null;
    if (!list.length && !fl) {
      ui.wrap.hidden = true;
      ui.list.hidden = true;
      open = false;
      mini = false;
      ui.pill.setAttribute('aria-expanded', 'false');
      setText(ui.say, '');
      if (hub) hub.hidden = true;
      return;
    }
    ui.wrap.hidden = false;
    // the pill steps aside for the hub's panel -- out of sight, but still
    // read out, so a screen reader hears the same news either way
    var quiet = !!hub && hubSeen;
    ui.wrap.classList.toggle('pa-quiet', quiet);
    // ... and out of the keyboard's way too: a button shrunk to a pixel is a
    // stop on Tab with nothing to be seen, and the panel has it all
    if (quiet) ui.pill.tabIndex = -1;
    else ui.pill.removeAttribute('tabindex');
    ui.wrap.classList.toggle('pa-over', (locals.length > 0 || !!(fl && fl.mine)) && overlaid());
    ui.wrap.classList.toggle('pa-mini', mini);
    setText(ui.shrink, mini ? 'full size' : 'shrink');
    var first = list[0];
    ui.wrap.classList.toggle('pa-done', !first);
    if (first) {
      setText(ui.say, 'Working: ' + first.label);
      var p = pct(first);
      setText(ui.num, p === null ? '' : p + '%');
      setText(ui.more, list.length > 1 ? '+' + (list.length - 1) + ' more' : '');
    } else {
      setText(ui.say, 'Done: ' + fl.label);
      setText(ui.num, '');
      setText(ui.more, '');
    }
    if (open) {
      setText(ui.ttl, list.length ? (list.length === 1 ? 'Working on 1 thing' : 'Working on ' + list.length + ' things')
                                  : 'Done');
      fill(ui.ul, list);
    }
    if (hub) {
      hub.hidden = false;
      hub.classList.toggle('pa-done', !first);
      setText(hub.querySelector('.pa-hubttl'),
              first ? 'Working… ' + (list.length === 1 ? '1 task' : list.length + ' tasks') + ' running'
                    : 'Done: ' + fl.label);
      fill(hub.querySelector('ul'), list);
    }
  }

  /* THE LOOK, carried here and not in a stylesheet: the studio's pages load
     app.css and not parseh.css, and one file is all a page has to load.
     The colours are the page's own tokens, whichever of the two palettes
     it has -- parseh.css's --card/--rule/--dim, or the studio's --chrome-*
     under the same accent -- so the pill follows light, dark and sepia.
     z-index 55: over the reader's and the player's fixed bars (50), under
     every sheet, panel, cloud, dialog and toast (60 and up), so it never
     covers a control somebody opened; bottom right, clear of the toast
     (centred) and the studio's "back to the top" (bottom left).  Lifted to
     105 over a backdrop while this page's own work runs (overlaid(), above):
     over the note (94/95) and the studio's dialogs (100), still under every
     toast (120, 400) and the studio's "stopped" screen (200). */
  function style() {
    if (document.getElementById('parseh-activity-css')) return;
    var s = el('style');
    s.id = 'parseh-activity-css';
    s.textContent = [
      '#parseh-activity,.pa-hub{--pa-accent:var(--accent,#be3455);--pa-accent-fg:var(--accent-fg,#fff);',
      '--pa-card:var(--card,var(--chrome-panel,#fff));--pa-ink:var(--ink,var(--chrome-fg,#241e21));',
      '--pa-dim:var(--dim,var(--chrome-mut,#635358));--pa-rule:var(--rule,var(--chrome-line,#e3d9dd))}',
      '#parseh-activity{position:fixed;right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px));',
      'z-index:55;display:flex;flex-direction:column;align-items:flex-end;gap:8px;',
      'max-width:calc(100vw - 28px);pointer-events:none;',
      'font:13.5px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;text-align:left}',
      '#parseh-activity.pa-over{z-index:105}',
      '#parseh-activity[hidden],#parseh-activity [hidden],.pa-hub[hidden]{display:none!important}',
      '#parseh-activity>*{pointer-events:auto}',
      '#parseh-activity.pa-quiet .pa-pill,#parseh-activity.pa-mini .pa-say{position:absolute;',
      'width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap;box-shadow:none}',
      '#parseh-activity.pa-mini .pa-pct,#parseh-activity.pa-mini .pa-more{display:none}',
      '#parseh-activity.pa-mini .pa-pill{padding:10px;gap:0}',
      '.pa-top{display:flex;align-items:center;gap:10px;padding:4px 10px 4px 14px}',
      '.pa-shrink{margin-left:auto;font:inherit;font-size:12px;color:var(--pa-ink);background:none;',
      'border:1px solid var(--pa-rule);border-radius:6px;padding:3px 9px;cursor:pointer}',
      '.pa-shrink:hover{border-color:var(--pa-accent);color:var(--pa-accent)}',
      '.pa-pill{display:flex;align-items:center;gap:8px;max-width:min(460px,100%);margin:0;',
      'border:0;border-radius:99px;padding:8px 15px 8px 11px;background:var(--pa-accent);',
      'color:var(--pa-accent-fg);box-shadow:0 6px 22px rgba(0,0,0,.28);cursor:pointer;',
      'font:inherit;font-weight:600;text-align:left}',
      '.pa-pill:focus-visible{outline:3px solid var(--pa-ink);outline-offset:2px}',
      '.pa-say{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext}',
      '.pa-pct,.pa-more{flex:none;font-weight:400;opacity:.92;white-space:nowrap}',
      '.pa-spin{flex:none;display:inline-block;width:13px;height:13px;border-radius:50%;',
      'border:2px solid currentColor;border-right-color:transparent;animation:pa-spin .8s linear infinite}',
      '@keyframes pa-spin{to{transform:rotate(360deg)}}',
      '@media (prefers-reduced-motion:reduce){.pa-spin{animation-duration:2.4s}}',
      '.pa-done .pa-pill .pa-spin,.pa-hub.pa-done h2 .pa-spin{animation:none;border:0;width:auto;height:auto}',
      '.pa-done .pa-pill .pa-spin::before,.pa-hub.pa-done h2 .pa-spin::before{content:"\\2713"}',
      '.pa-list{width:min(460px,100%);max-height:min(55vh,380px);overflow:auto;box-sizing:border-box;',
      'background:var(--pa-card);color:var(--pa-ink);border:1px solid var(--pa-rule);',
      'border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.25);padding:6px 0}',
      '.pa-ttl{font-size:12px;color:var(--pa-dim);text-transform:uppercase;letter-spacing:.04em}',
      '#parseh-activity ul,.pa-hub ul{list-style:none;margin:0;padding:0}',
      '.pa-row{padding:7px 14px;border-top:1px solid var(--pa-rule)}',
      '.pa-row:first-child{border-top:0}',
      '.pa-head{display:flex;align-items:baseline;gap:8px}',
      '.pa-row .pa-spin{width:10px;height:10px;color:var(--pa-accent);position:relative;top:1px}',
      '.pa-lbl{min-width:0;overflow-wrap:anywhere;unicode-bidi:plaintext}',
      '.pa-meta{margin:2px 0 0 18px;font-size:12px;color:var(--pa-dim);overflow-wrap:anywhere}',
      '.pa-meta a{color:var(--pa-accent);margin-left:.6em}',
      '.pa-bar{margin:5px 0 0 18px;height:4px;border-radius:2px;background:var(--pa-rule);overflow:hidden}',
      '.pa-bar i{display:block;height:100%;background:var(--pa-accent)}',
      '.pa-hub{margin:0 auto 26px;max-width:720px;box-sizing:border-box;background:var(--pa-card);',
      'color:var(--pa-ink);border:1px solid var(--pa-rule);border-left:4px solid var(--pa-accent);',
      'border-radius:12px;padding:10px 4px 6px;text-align:left;',
      'font:14px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}',
      '.pa-hub h2{margin:0 12px 4px;font-size:15px;font-weight:600;color:var(--pa-accent);',
      'display:flex;align-items:center;gap:9px}',
      '.pa-hub .pa-row{padding:7px 12px}',
      '@media (max-width:560px){#parseh-activity{right:10px;max-width:calc(100vw - 20px)}',
      '.pa-pill{max-width:min(78vw,100%)}}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(s);
  }

  // the elapsed times move on between two polls
  setInterval(function () { if (ui && !ui.wrap.hidden) draw(); }, 1000);

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { clearTimeout(timer); timer = null; drop(); }
    else poke(0);
  });
  // the network changing under the page is a reason to ask, and never an
  // answer: a phone roaming between two Wi-Fis says "offline" for a moment
  window.addEventListener('online', function () { drop(); poke(0); });
  window.addEventListener('offline', function () { drop(); poke(0); });
  hook(document);

  /* THE LIST AS A FRAMED PAGE SEES IT -- a note's studio page, over a book
     or a video.  Everything it starts is on this page's list, as this
     page's own work (so it is lifted over the note's backdrop, above).  Its
     download links are hooked here as this page's are.  And its entries
     are let go when the frame goes: closing the note, or moving it to
     another page, takes the frame's requests with it, and what was waiting
     on them inside the frame is code of a page no longer shown, which a
     browser need not run again -- Chromium happens to end the entry
     anyway, but the pill must not depend on it to stop saying "Uploading".
     A download it started is not let go: the browser keeps that, and the
     server's entry says when it is over. */
  function framed(win) {
    var mine = [];
    function keep(h) { mine.push(h); return h; }
    hook(win.document);
    win.addEventListener('pagehide', function () {
      mine.forEach(function (h) { if (!h.follow) h.end(false); });
      mine = [];
    });
    return {
      local: function (label, opts) { return keep(local(label, opts)); },
      track: function (work, label) { return settle(keep(local(label)), work); },
      expect: function (label) { return keep(expect(label)); },
      download: function (url, label) {
        var h = keep(expect(label || 'Preparing the download…'));
        win.location.href = h.url(url);
        return h;
      },
      poke: poke, items: items, hook: hook, framed: framed
    };
  }

  window.ParsehActivity = {local: local, track: track, expect: expect, download: download,
                           poke: poke, items: items, hook: hook, framed: framed,
                           reach: reachNow};
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', function () { draw(); poke(0); });
  else { draw(); poke(0); }
})();
