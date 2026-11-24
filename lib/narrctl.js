// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the narration's controls: play, the recording moved back and on,
   and how fast it plays (TO-DO §4.15, §4.17; docs/mobile.md).

   WHY IT LIVES IN lib/.  A reader is a page built for its book
   (lib/tex2html.py), and a book built before today carries nothing of what
   was added today -- which is most books on any shelf.  lib/parseh.js loads
   this file into every reader, in BOTH modes, so every edition, however old,
   gains these controls and the cure below without being built again.

   WHAT IT PUTS ON THE PAGE
     - the mobile mode: a dock of floating buttons at the foot of the screen,
       ↺ in the left corner, ⏯ and ↻ in the right with the speed above them,
       where a thumb reaches them without shifting the grip.  They fade when
       nothing has been touched for a while and come back at full strength at
       a touch, so they never sit brightly over the text being read;
     - the browser mode: ↺ and ↻ either side of ▶ in the header, and
       Shift+← / Shift+→ for them (← and → keep walking subparagraphs);
     - both modes: the speed is a chip saying 1.5×, and a tap on it opens the
       row of speeds; holding ↺ or ↻ opens the row of seconds, which the
       gear's Listening group also shows (Skip distance), since a hold cannot be seen.

   THE SPEED IS THE READER'S OWN <select id="speed">, always.  The chip sets
   that menu's value and lets the reader's own handler run, so nothing here
   needs to know what a reader does with the number (it sets the audio's rate
   and keeps it as bk_rate).  An old reader whose menu stops at 1.5 is handed
   the options it lacks.

   A VIDEO HAS NO SUCH MENU, AND ANSWERS A MOMENT LATER.  A book's <audio>
   takes a rate between two statements, so asking it back is asking the truth;
   YouTube's frame is a message away, and asking it back in the same breath
   still gets the rate from before the change -- which is how the chip came to
   paint one change behind on a video and nowhere else (the owner, on a real
   phone, 2026-09-23).  So a video's chosen speed is HELD here and painted at
   once, and put down again when the player itself says it is playing at it.
   A video also keeps a speed OF ITS OWN, vd_rate, and never the book's
   bk_rate: watching and listening are different habits, and the speed a book
   is read aloud at has nothing to say about the speed a video is watched at
   (the owner's choice, 2026-09-23).  It goes back the moment the player is
   there to take it, which is not when the page is drawn.

   AND THE SPEED NEVER CHANGES BY ITSELF.  Loading a recording -- which the
   reader does whenever the narration moves into a part kept in another file,
   and at the first play of a book whose recording is not the page's own src
   -- runs the media load algorithm, and that puts playbackRate back to
   defaultPlaybackRate, which is 1.  The sound went back to 1× while the
   control still said 1.5×, and the only way out was to move the control to
   1× and back again (the owner's report, 2026-09-22).  The cure is in two
   parts: defaultPlaybackRate is set with every rate, so the load has nothing
   to put back; and the rate is set again after every load, for a browser
   that reaches the same end by another road.  A rate that changes at any
   OTHER time is somebody meaning it -- the audio element has a speed in its
   own menu -- and then the chip follows the sound instead of fighting it. */
(function () {
  'use strict';
  if (window.ParsehNarr) return;

  /* today's menu, plus the two the owner asked for (2026-09-22) and the
     slowest, which he asked for on 2026-09-23 after meeting it on a video.

     THIS IS THE TOOLBOX'S OWN LIST, and it is what a book's narration and a
     film on this machine both offer -- one list, as he asked, for everything
     Parseh itself plays.  A VIDEO STILL HOSTED BY YOUTUBE CANNOT HAVE IT,
     and that is YouTube's rule and not a choice here: its player accepts
     only the rates its own getAvailablePlaybackRates reports -- 0.25, 0.5,
     0.75, 1, 1.25, 1.5, 1.75, 2 -- and ignores anything else it is handed,
     so a chip offering 0.6× would say one thing while the sound did another.
     `speeds()` below therefore asks the player for its list and falls back
     to this one, which is how a downloaded film already gets these and a
     YouTube-hosted video gets YouTube's eight. */
  var SPEEDS = [0.25, 0.5, 0.6, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
  /* AND THE TWO SHORT ONES (the owner, 2026-09-23).  A second and two
     seconds are what a phrase is worth: they are for going back over the
     word just missed, where five already overshoots into the line before.
     They lead the row because that is the order the numbers have. */
  var SECS = [1, 2, 5, 10, 15, 30, 60];
  var RATE_KEY = 'bk_rate', SKIP_KEY = 'bk_skip', HINT_KEY = 'bk_skiphint';
  /* a video's own, kept apart from the book's on purpose (see the head of
     this file); the seconds ↺ and ↻ carry stay one number for everything */
  var VRATE_KEY = 'vd_rate';
  var SKIP_DEF = 10, SKIP_MAX = 600, IDLE = 4000;

  function $(id) { return document.getElementById(id); }
  function audio() { return $('audio'); }
  function playBtn() { return $('play'); }
  function speedSel() { return $('speed'); }
  /* THE THING THAT PLAYS.  A book's reader has an <audio> element and a ▶ of
     its own, and everything below drives those.  A video has neither: it is
     YouTube's frame, or a film of this machine, behind the handle the player
     page hands out (window.ParsehPlayer, youtube/lib/player.js).  So the few
     things these controls do -- is it playing, play, pause, where is it, go
     there, how fast, how fast can it -- are asked of whichever is here, and
     nothing else in this file knows which it is.  A video keeps no reading
     place and no subparagraphs: there a skip is simply a seek. */
  function video() { return window.ParsehPlayer || null; }
  function vid() { return !audio() && !!video(); }
  function P() { return window.Parseh; }
  function mobile() { var p = P(); return !!(p && p.mode && p.mode.isMobile()); }
  function say(m, bad) { var p = P(); if (p && p.toast) p.toast(m, bad); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* ---------------- the speed ----------------
     The menu is the book of record; where a reader has none (a book with no
     narration at all) there is nothing to say and nothing is drawn.
     A video keeps three things instead of a menu: what it was asked to play
     at (`wanted`, until the player confirms it), what it last said it really
     plays at (`said`), and whether its remembered speed has been put back. */
  var wanted = 0, wantT = null, said = 0, restored = false;
  function rate() {
    if (vid()) {
      // the choice just made, before the frame has had time to agree
      if (wanted > 0) return wanted;
      var p = video(), kept = parseFloat(get(VRATE_KEY));
      // before there is a player its answer is a guess, and 1× is the guess
      // it always makes: the chip says the speed this video is about to be
      // put back to instead, and never flickers through 1× on the way
      if (!p.ready() && kept > 0) return kept;
      var r = p.rate();
      if (r > 0) return r;
      return kept > 0 ? kept : 1;
    }
    var s = speedSel(), v = s ? parseFloat(s.value) : parseFloat(get(RATE_KEY));
    return v > 0 ? v : 1;
  }
  // what this player will play at: YouTube offers the speeds it offers, and
  // a chip must not say 1.1× while the sound is at 1×
  function speeds() {
    if (vid()) {
      var own = video().rates && video().rates();
      if (own && own.length) return own;
    }
    return SPEEDS;
  }
  function saying(v) {
    // 1.5× and 1×, never 1.50× or 1.0×
    return String(+(+v).toFixed(2)).replace(/\.0+$/, '') + '×';
  }
  // the menu can only hold what it was built with: a value it lacks (the two
  // new speeds, or one chosen in the audio element's own menu) is added in
  // its place in the order, so setting it means something
  function option(v) {
    var s = speedSel();
    if (!s) return null;
    var want = String(v), i;
    for (i = 0; i < s.options.length; i++)
      if (parseFloat(s.options[i].value) === +v) return s.options[i];
    var o = document.createElement('option');
    o.value = want;
    o.textContent = want;
    for (i = 0; i < s.options.length; i++)
      if (parseFloat(s.options[i].value) > +v) { s.insertBefore(o, s.options[i]); return o; }
    s.appendChild(o);
    return o;
  }
  function setRate(v, quietly) {
    if (vid()) {
      // painted from the CHOICE, not from the player: the player is still
      // being told.  It is held until the player says the same number back,
      // and let go after four seconds whatever happens -- a rate a player
      // will not take must stop being claimed rather than be lied about.
      wanted = v;
      clearTimeout(wantT);
      wantT = setTimeout(function () { wanted = 0; paintSpeed(); }, 4000);
      video().setRate(v);
      if (!quietly) put(VRATE_KEY, String(v));
      paintSpeed();
      return;
    }
    var s = speedSel(), a = audio();
    if (s) {
      option(v);
      s.value = String(v);
      // the reader's own handler saves it and sets the audio's rate
      if (!quietly) s.dispatchEvent(new Event('change', {bubbles: true}));
    }
    if (!quietly) put(RATE_KEY, String(v));
    // the sound itself, always: a control saying one thing while the sound
    // does another is the whole complaint
    if (a) { try { a.defaultPlaybackRate = v; a.playbackRate = v; } catch (e) {} }
    paintSpeed();
  }
  // the sound's rate put back to what the control says
  function hold() {
    var a = audio();
    if (!a) return;
    var want = rate();
    try { a.defaultPlaybackRate = want; } catch (e) {}
    if (Math.abs((a.playbackRate || 1) - want) > 0.001) {
      try { a.playbackRate = want; } catch (e) {}
    }
  }
  // somebody moved the sound's own speed: the control follows it
  function adopt(v) {
    if (!(v > 0)) return;
    setRate(v, true);
    put(RATE_KEY, String(v));
    paintSpeed();
  }
  var loading = 0;
  function watchRate() {
    var a = audio();
    if (!a || a.dataset.ncRate) return;
    a.dataset.ncRate = '1';
    ['loadstart', 'emptied'].forEach(function (n) {
      a.addEventListener(n, function () { loading = Date.now(); hold(); });
    });
    ['loadedmetadata', 'loadeddata', 'canplay', 'play', 'playing', 'durationchange']
      .forEach(function (n) { a.addEventListener(n, hold); });
    a.addEventListener('ratechange', function () {
      var want = rate();
      if (Math.abs((a.playbackRate || 1) - want) < 0.001) return;
      // a reload is the browser undoing the choice: put it back
      if (Date.now() - loading < 3000 || a.readyState < 1) { hold(); return; }
      adopt(a.playbackRate);
    });
    hold();
  }

  /* ---------------- the video, which answers in its own time ----------------
     The player says when it starts, when it stops and when its rate really
     changed (youtube/lib/player.js passes YouTube's own onPlaybackRateChange
     on, and the film's ratechange), and a quiet look besides, since nothing
     announces a player becoming ready a second time.  Three things settle
     here, all of them out of a book's reach:
       - the held choice is put down as soon as the player plays at it;
       - a speed chosen in the player's OWN menu is adopted, as a book adopts
         one chosen in the audio element's;
       - the speed this video was last watched at goes back the moment there
         is a player to take it.
     Nothing here waits for the dock: a video keeps its speed in either mode. */
  var watching = false;
  function watchVideo() {
    if (watching || !vid()) return;
    watching = true;
    video().onChange(heard);
    setInterval(heard, 500);
    heard();
  }
  function heard() {
    if (vid()) { restoreRate(); heardRate(); }
    paintPlay();
  }
  function restoreRate() {
    // a frame that has not loaded refuses a rate and says nothing about it,
    // so this waits for the player rather than for the page
    if (restored || !video().ready()) return;
    restored = true;
    var v = parseFloat(get(VRATE_KEY));
    if (v > 0 && Math.abs(v - video().rate()) > 0.001) setRate(v, true);
  }
  function heardRate() {
    // before the player is there its rate is a guess, and a guess must not be
    // written over the speed this video was last watched at
    if (!video().ready()) return;
    var r = video().rate();
    if (!(r > 0) || Math.abs(r - said) < 0.001) return;
    said = r;
    if (wanted > 0) {
      if (Math.abs(r - wanted) > 0.001) return;   // the frame has not caught up
      clearTimeout(wantT);
      wanted = 0;
    } else {
      // nobody here asked for this: the player has a speed in its own menu,
      // and the chip follows it instead of fighting it
      put(VRATE_KEY, String(r));
    }
    paintSpeed();
  }

  /* ---------------- how far ↺ and ↻ carry ---------------- */
  function secs() {
    var v = parseInt(get(SKIP_KEY), 10);
    return v >= 1 && v <= SKIP_MAX ? v : SKIP_DEF;
  }
  function setSecs(n) {
    n = Math.min(SKIP_MAX, Math.max(1, Math.round(n)));
    put(SKIP_KEY, String(n));
    paintSecs();
  }

  /* ---------------- the row that opens under a button ----------------
     One device for both rows (the speeds, the seconds): a menu of choices
     anchored to the button that opened it, with the one in force marked.
     It goes into the full-screen element when there is one, since nothing
     outside it is drawn (the video, sideways). */
  var pop = null, popFor = null;
  function popClose(back) {
    if (!pop) return;
    var was = popFor;
    pop.remove();
    pop = null; popFor = null;
    if (was) was.setAttribute('aria-expanded', 'false');
    if (back && was) { try { was.focus(); } catch (e) {} }
    wake();
  }
  function popOpen(anchor, items, now, pick, label) {
    if (pop && popFor === anchor) { popClose(true); return; }
    popClose();
    pop = el('div', 'nc-pop');
    pop.setAttribute('role', 'menu');
    pop.setAttribute('aria-label', label);
    // a left-to-right island, as the dock below is: it is put on <body>, and
    // a Persian book's body runs right to left, which laid "1.5×" and "10s"
    // out backwards and put the slowest speed where the fastest belongs
    pop.setAttribute('dir', 'ltr');
    pop.setAttribute('lang', 'en');
    items.forEach(function (it) {
      var b = el('button', 'nc-popb', it.words);
      b.type = 'button';
      b.setAttribute('role', 'menuitemradio');
      b.setAttribute('aria-checked', String(it.value === now));
      if (it.value === now) b.classList.add('on');
      b.addEventListener('click', function () { pick(it.value); popClose(true); });
      pop.appendChild(b);
    });
    (document.fullscreenElement || document.body).appendChild(pop);
    popFor = anchor;
    anchor.setAttribute('aria-expanded', 'true');
    popPlace();
    var on = pop.querySelector('.on') || pop.firstChild;
    if (on) { try { on.focus(); } catch (e) {} }
  }
  function popPlace() {
    if (!pop || !popFor) return;
    var r = popFor.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    var pad = 8;
    var left = Math.round(r.left + r.width / 2 - w / 2);
    left = Math.max(pad, Math.min(left, window.innerWidth - w - pad));
    var top = r.top - h - pad;
    if (top < pad) top = Math.min(r.bottom + pad, window.innerHeight - h - pad);
    pop.style.left = left + 'px';
    pop.style.top = Math.max(pad, top) + 'px';
  }
  document.addEventListener('pointerdown', function (e) {
    if (!pop) return;
    if (pop.contains(e.target) || (popFor && popFor.contains(e.target))) return;
    popClose();
  }, true);
  window.addEventListener('keydown', function (e) {
    if (!pop) return;
    if (e.key === 'Escape') { e.preventDefault(); popClose(true); return; }
    var bs = Array.prototype.slice.call(pop.children), i = bs.indexOf(document.activeElement);
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault(); e.stopPropagation();
      bs[i < 0 ? 0 : Math.min(i + 1, bs.length - 1)].focus();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault(); e.stopPropagation();
      bs[i <= 0 ? 0 : i - 1].focus();
    }
  }, true);
  window.addEventListener('resize', popPlace);
  window.addEventListener('scroll', function () { if (pop) popPlace(); }, true);

  function openSpeeds(anchor) {
    popOpen(anchor, speeds().map(function (v) { return {value: v, words: saying(v)}; }),
            rate(), function (v) { setRate(v); }, 'how fast the recording plays');
  }
  function openSecs(anchor) {
    popOpen(anchor, SECS.map(function (v) { return {value: v, words: v + 's'}; }),
            secs(), setSecs, 'how many seconds ↺ and ↻ move the recording');
  }

  /* ---------------- the move itself ----------------
     The reader plays by SUBPARAGRAPH (lib/tex2html.py): the mark is on the
     one playing, and it stops at that one's end, where "continuous" takes it
     on.  So a jump into another subparagraph takes the reading place with it
     -- the mark, the place kept for next time, and where the playing stops --
     or the next stop would fall at the end of the one it left.  Listening on
     its own has no reading place: there only the fold ahead is worked out
     again from where the recording now is.  All of that is the reader's own
     state, the top-level bindings of its script, which every classic script
     of the page shares; a reader built before one of them existed has the
     recording moved and follows as it can.  Within the recording that is
     loaded, a book read from several files being one file at a time: from
     its start to its end. */
  function skipBy(by) {
    if (vid()) {
      var p = video();
      p.seek(Math.max(0, p.time() + by));
      return;
    }
    var a = audio();
    if (!a) return;
    var d = a.duration, to = Math.max(0, (a.currentTime || 0) + by);
    if (d > 0 && isFinite(d)) to = Math.min(to, d - 0.05);
    try {
      // every name below but a, to and i is the reader's; each is read
      // before anything is written, so a reader that lacks one throws
      // before it is half moved
      if (listening) {
        void armListen;
        seekTo(to, function () {});
        if (!a.paused) armListen();
        return;
      }
      var i = subAtTime(to);
      void [waiting, atBound, previewing, cur, stopAt, hl, save, SUBS, seekTo];
      clearTimeout(waiting); waiting = null;
      // a wait at a change of chapter, or a preview's window: this is
      // where the playing is now
      atBound = null; previewing = false;
      if (i >= 0 && i !== cur) { cur = i; hl(i, true); save(); }
      if (!a.paused && i >= 0) stopAt = SUBS[i][1];
      seekTo(to, function () {});
      return;
    } catch (e) { /* a reader older than one of the above */ }
    a.currentTime = to;
  }

  /* ---------------- the buttons ----------------
     A tap moves the recording; a press held open the row of seconds.  The
     hold cannot be seen, so the first tap says it once, and the gear's Listening
     group shows the same choice (mobile) or the title says it (a
     mouse, which has a tooltip to rest on). */
  var skips = [];
  function hinted() {
    if (get(HINT_KEY) === '1') return;
    put(HINT_KEY, '1');
    say('hold ↺ or ↻ to choose the seconds');
  }
  function mkSkip(dir, cls) {
    var b = el('button', 'nc-skip' + (cls ? ' ' + cls : ''));
    b.type = 'button';
    b.setAttribute('data-skip', String(dir));
    var held = false, timer = null;
    function start() {
      clearTimeout(timer);
      timer = setTimeout(function () { held = true; openSecs(b); }, 500);
    }
    function stop() { clearTimeout(timer); timer = null; }
    b.addEventListener('pointerdown', start);
    b.addEventListener('pointerup', stop);
    b.addEventListener('pointercancel', function () { stop(); held = false; });
    b.addEventListener('pointerleave', stop);
    b.addEventListener('contextmenu', function (e) { if (held) e.preventDefault(); });
    b.addEventListener('click', function (e) {
      stop();
      if (held) { held = false; e.preventDefault(); return; }
      hinted();
      skipBy(dir * secs());
    });
    skips.push(b);
    return b;
  }
  function mkChip(cls) {
    var b = el('button', 'nc-chip' + (cls ? ' ' + cls : ''));
    b.type = 'button';
    b.setAttribute('aria-haspopup', 'menu');
    b.setAttribute('aria-expanded', 'false');
    b.addEventListener('click', function () { openSpeeds(b); });
    // a wheel over it steps the speed, as it does over a menu
    b.addEventListener('wheel', function (e) {
      e.preventDefault();
      step(e.deltaY < 0 ? 1 : -1);
    }, {passive: false});
    return b;
  }
  function step(dir) {
    var list = speeds(), now = rate(), i = list.indexOf(now);
    if (i < 0) {  // a speed of somebody's own: step to the nearest above or below
      i = 0;
      for (var k = 0; k < list.length; k++) if (list[k] <= now) i = k;
      if (dir > 0 && list[i] <= now) i = Math.min(i + 1, list.length - 1);
    } else i = Math.max(0, Math.min(list.length - 1, i + dir));
    setRate(list[i]);
    say('speed ' + saying(list[i]));
  }

  var chip = null, dock = null, play = null, row = null, secsRow = null;
  function paintSpeed() {
    var v = rate();
    if (chip) {
      chip.textContent = saying(v);
      chip.setAttribute('aria-label', 'how fast the recording plays: ' + saying(v));
      chip.title = 'how fast the recording plays — click for the others' +
                   (mobile() ? '' : ', or the wheel, or [ and ]');
    }
    if (pop && popFor === chip)
      Array.prototype.forEach.call(pop.children, function (b) {
        var on = Math.abs(parseFloat(b.textContent) - v) < 0.001;
        b.setAttribute('aria-checked', String(on));
        b.classList.toggle('on', on);
      });
  }
  function paintSecs() {
    var n = secs();
    skips.forEach(function (b) {
      var dir = +b.getAttribute('data-skip');
      b.textContent = dir < 0 ? '↺ ' + n : n + ' ↻';
      b.setAttribute('aria-label', (dir < 0 ? 'back ' : 'on ') + n + ' seconds');
      b.title = 'the recording ' + (dir < 0 ? 'back ' : 'on ') + n +
                ' seconds — hold to choose how many';
    });
    if (secsRow)
      Array.prototype.forEach.call(secsRow.querySelectorAll('button'), function (b) {
        var on = +b.dataset.secs === n;
        b.setAttribute('aria-checked', String(on));
        b.classList.toggle('on', on);
      });
    if (pop && popFor && popFor.classList.contains('nc-skip'))
      Array.prototype.forEach.call(pop.children, function (b) {
        var on = parseInt(b.textContent, 10) === n;
        b.setAttribute('aria-checked', String(on));
        b.classList.toggle('on', on);
      });
  }
  function paintPlay() {
    if (!play) return;
    var a = audio();
    if (!a && !vid()) return;
    var going = a ? !a.paused : !video().paused();
    // ‖ AND ▶, THE MARKS THE REST OF PARSEH USES -- the reader's own header
    // button (lib/tex2html.py), the card kit's clip player, the studio.  ⏸ is
    // an emoji, and Android draws it in the colour font, orange and twice the
    // weight of everything around it (the owner, on a real phone, 2026-09-23);
    // no colour font can claim ‖ and ▶.
    play.textContent = going ? '‖' : '▶';
    play.setAttribute('aria-label', going ? 'pause the recording' : 'play the recording');
    play.title = going ? 'pause (space)' : 'play (space)';
  }

  /* ---------------- the dock, on a phone ----------------
     Fixed at the foot, in the two corners a thumb owns; faint after a few
     seconds in which nothing was touched, whole again at the first touch. */
  var idleT = null;
  /* WHAT ELSE FADES WITH THE DOCK.  A video on the whole screen has a way out
     in the corner (lib/mobileplayer.js), and it must behave as the dock does
     -- faint when nothing is touched, whole at the first touch -- or it sits
     brightly over the picture.  There is one idle clock on the page, this
     one, so it is told about that button rather than keeping a clock of its
     own and drifting out of step with the dock beside it. */
  var fades = [];
  function fade(b) {
    if (!b || fades.indexOf(b) >= 0) return;
    fades.push(b);
    b.classList.toggle('nc-idle', !!(dock && dock.classList.contains('nc-idle')));
  }
  function faint(yes) {
    if (dock) dock.classList.toggle('nc-idle', yes);
    fades.forEach(function (b) { b.classList.toggle('nc-idle', yes); });
  }
  function wake() {
    faint(false);
    clearTimeout(idleT);
    idleT = setTimeout(function () {
      if (!pop) faint(true);
    }, IDLE);
  }
  function buildDock() {
    if (dock || (!(audio() && playBtn()) && !vid())) return;
    dock = el('div', 'nc-dock');
    dock.setAttribute('data-layout', 'mobile');
    dock.setAttribute('role', 'group');
    dock.setAttribute('aria-label', 'the recording');
    /* A LEFT-TO-RIGHT ISLAND, WHATEVER THE BOOK READS LIKE.  The dock hangs
       off <body>, and a Persian, Arabic or Hebrew book's <body> runs right to
       left: the whole dock came out mirrored -- ↺ in the right corner, ⏯ and
       ↻ in the left -- and "↺ 10" and "10 ↻" were reordered on top of that,
       so back pointed forward (the owner, on a real phone, 2026-09-23).  The
       reader's own header is already an island of this kind (lang="en"
       dir="ltr", lib/tex2html.py); these are the toolbox's controls, not the
       book's text, and they read the same way in every book. */
    dock.setAttribute('dir', 'ltr');
    dock.setAttribute('lang', 'en');
    var left = el('div', 'nc-side nc-l'), right = el('div', 'nc-side nc-r');
    left.appendChild(mkSkip(-1, 'nc-big'));
    var top = el('div', 'nc-top');
    right.appendChild(top);
    var pair = el('div', 'nc-pair');
    play = el('button', 'nc-play');
    play.type = 'button';
    // the reader's own ▶ does the work: continuous, the loop, the fold
    // ahead and the reading place are all its business.  A video has no
    // such button: it is played and paused through the player's handle.
    play.addEventListener('click', function () {
      if (vid()) {
        var p = video();
        if (p.paused()) p.play(); else p.pause();
        setTimeout(paintPlay, 60);
        return;
      }
      var b = playBtn();
      if (b) b.click();
    });
    pair.appendChild(play);
    pair.appendChild(mkSkip(1, 'nc-big'));
    right.appendChild(pair);
    dock.appendChild(left);
    dock.appendChild(right);
    document.body.appendChild(dock);
    // A TOUCH, not a scroll: a page that scrolls ITSELF -- which this one
    // does all the while a narration plays, to keep the reading place in
    // view -- must not keep the dock bright over the text.  A finger that
    // scrolls has touched the screen first, so a real scroll wakes it
    // anyway; a wheel is here for a mouse on a touch screen.
    ['touchstart', 'pointerdown', 'keydown', 'wheel'].forEach(function (n) {
      window.addEventListener(n, wake, {passive: true});
    });
    var a = audio();
    if (a) {
      ['play', 'pause', 'ended', 'emptied'].forEach(function (n) {
        a.addEventListener(n, paintPlay);
      });
    }
    // a video is watched from start() instead: whether it is playing, and the
    // speed it was last watched at, are its business in either mode, and
    // neither of them waits for a dock to be built
    paintPlay();
    wake();
  }

  /* ---------------- the header, on a computer ----------------
     ↺ and ↻ either side of ▶, and the chip where the menu was.  The mobile
     sheet hides whatever the header holds that it has not named, so these
     are the browser mode's without being told. */
  function buildHeader() {
    var p = playBtn();
    if (row || !p || !audio()) return;     // a video's own controls are its frame's
    row = true;
    p.parentNode.insertBefore(mkSkip(-1), p);
    if (p.nextSibling) p.parentNode.insertBefore(mkSkip(1), p.nextSibling);
    else p.parentNode.appendChild(mkSkip(1));
  }

  /* the chip stands where the menu is on a computer, and in the dock on a
     phone: one chip, moved, so there is one truth on the page */
  function placeChip() {
    var s = speedSel();
    if (!s && !vid()) return;
    if (!chip) {
      chip = mkChip();
      if (s) s.classList.add('nc-was');
    }
    if (mobile() || !s) {
      var top = dock && dock.querySelector('.nc-top');
      if (top && chip.parentNode !== top) top.appendChild(chip);
    } else if (chip.parentNode !== s.parentNode || chip.nextSibling !== s) {
      s.parentNode.insertBefore(chip, s);
    }
    paintSpeed();
  }

  /* ---------------- the seconds, in the header's own row (mobile) ----------------
     A hold is invisible, so a row of the header says the same thing in the
     open: the row of seconds, in place of the field of figures that was
     there before. */
  function buildSecsRow() {
    var h = document.querySelector('header .hrow');
    if (secsRow || !h || (!audio() && !vid())) return;
    secsRow = el('span', 'm-rskip');
    secsRow.setAttribute('data-layout', 'mobile');
    secsRow.setAttribute('role', 'group');
    var lab = el('span', 'm-rskiplab', 'skip by');
    secsRow.appendChild(lab);
    SECS.forEach(function (n) {
      var b = el('button', '', n + 's');
      b.type = 'button';
      b.dataset.secs = String(n);
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', 'false');
      b.title = '↺ and ↻ move the recording ' + n + ' seconds';
      b.addEventListener('click', function () { setSecs(n); });
      secsRow.appendChild(b);
    });
    h.appendChild(secsRow);
  }

  /* ---------------- the keyboard (a computer) ----------------
     Shift+← and Shift+→ move the recording; ← and → keep walking
     subparagraphs, which is the reader's own binding -- so this listens in
     the capture phase and stops the event before the reader's hears it.
     [ and ] step the speed. */
  function isField(t) {
    return !!(t && t.closest && t.closest('input, textarea, select, [contenteditable]'));
  }
  function sheetOpen() {
    // the reader's own sheets, read defensively: an older reader may have
    // fewer of them
    try { if (ankiOpen || narrOpen || chOpen) return true; } catch (e) {}
    try { if (fdShown || secShown) return true; } catch (e) {}
    // the sheet that glosses a stretch with an LLM (#rgbox), on a line of its
    // own so a reader built before it keeps every check above: it focuses its
    // outline tree, which is no field, and Shift+←/→ there moved the paused
    // recording -- and the reading place with it -- and [ ] the speed, all
    // silently under the sheet, the tree never hearing its keys
    try { if (rgShown) return true; } catch (e) {}
    // AND THE SHEETS THE TOOLBOX OPENS OVER A READER, which are not the
    // reader's own variables to read: the card kit's cut editor (.pc-root,
    // lib/cardkit.js) and the timings editor (.tl-root, lib/timeline.js).
    // Each gives its edges Shift+← and Shift+→ of their own -- a half second
    // at a time -- and while one is open those keys are ITS keys; taken here
    // first, an edge nudged by half a second moved the recording instead,
    // silently, under a sheet that looked as if it had not heard.
    if (document.querySelector('.pc-root, .tl-root')) return true;
    return false;
  }
  window.addEventListener('keydown', function (e) {
    if ((!audio() && !vid()) || isField(e.target) || sheetOpen()) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    // In mobile mode the dock's ↺ / ↻ are the reader's primary navigation.
    // Take the plain arrows here, in capture phase, before a book's own
    // subparagraph walker sees them.  Shift keeps that walker on a book;
    // a video has no such walker, so shifted arrows remain a harmless skip.
    if (!e.shiftKey && mobile() && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault(); e.stopImmediatePropagation();
      skipBy((e.key === 'ArrowRight' ? 1 : -1) * secs());
      return;
    }
    if (e.shiftKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      if (mobile() && !vid()) return;
      e.preventDefault(); e.stopImmediatePropagation();
      skipBy((e.key === 'ArrowRight' ? 1 : -1) * secs());
      return;
    }
    if (!e.shiftKey && (e.key === '[' || e.key === ']')) {
      e.preventDefault(); e.stopImmediatePropagation();
      step(e.key === ']' ? 1 : -1);
    }
  }, true);

  /* ---------------- the mode ---------------- */
  function onMode(m) {
    if (m === 'mobile') {
      buildDock();
      buildSecsRow();
      if (dock) dock.hidden = false;
    } else if (dock) {
      dock.hidden = true;
      popClose();
    }
    placeChip();
    paintSecs();
    paintPlay();
  }
  function start() {
    if (!speedSel() && !audio() && !vid()) return;   // nothing here plays
    watchRate();
    watchVideo();
    buildHeader();
    var p = P();
    if (p && p.mode && p.mode.onChange) p.mode.onChange(onMode);
    onMode(mobile() ? 'mobile' : 'browser');
    paintSecs();
    // the person's speed may have come from the toolbox (lib/prefs.js) BEFORE
    // this script loaded: it was stored, but nobody was here to wear it, and
    // the reader's menu still says what it read at load.  Worn now.
    if (!vid()) {
      var kept = parseFloat(get(RATE_KEY));
      if (kept > 0 && Math.abs(kept - rate()) > 0.001) setRate(kept, true);
    }
    // another tab chose other seconds, or another speed -- and the speed a
    // page follows is the one that page plays: a video reads vd_rate, a book
    // bk_rate, and neither is ever handed the other's
    window.addEventListener('storage', function (e) {
      if (!e.key || e.key === SKIP_KEY) paintSecs();
      var key = vid() ? VRATE_KEY : RATE_KEY;
      if (!e.key || e.key === key) {
        var v = parseFloat(get(key));
        if (v > 0 && Math.abs(v - rate()) > 0.001) setRate(v, true);
        paintSpeed();
      }
    });
  }

  window.ParsehNarr = {
    speeds: speeds, seconds: SECS, all: SPEEDS,
    rate: rate, setRate: setRate, step: step,
    secs: secs, setSecs: setSecs, skipBy: skipBy,
    say: saying, hold: hold, fade: fade
  };
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', start);
  else start();
})();
