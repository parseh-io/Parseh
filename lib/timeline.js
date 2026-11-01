// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the timeline: where one piece of text stops being said and the
   next starts, moved by hand over a picture of the sound.  Served at
   /lib/timeline.js (with /lib/timeline.css); the book reader and the video
   player both link it, so a change here needs no reader rebuilt.  Plain
   ES2017, no build step.

     ParsehTimeline.open(opts)   the boundary editor, resolving to the marks
                                 that moved, or null when nothing was saved

   WHAT THIS IS, BESIDE THE TWO EDITORS THAT WERE ALREADY HERE.  The reader's
   own `edit times` moves ONE subparagraph at a time, by its six steps, with
   the text on the page beside it; the card kit's cut editor moves the two
   edges of ONE clip over a waveform.  Neither shows the boundary itself --
   the moment the reader stops hearing 2.3 and starts hearing 2.4 -- which is
   the thing somebody timing a book is actually looking for, and which is
   always a boundary BETWEEN TWO: moving it is one act, not two edits that
   have to be made to agree.  So the strip here carries the whole stretch
   with every boundary on it, the text of the three that matter is above it,
   and a drag moves the end of one and the start of the next together.

   JOINED, AND SPLIT.  A boundary is joined by default -- one line, one
   number, `prev.t1 === next.t0` -- because a recording has no gap in it and
   two numbers that should be one are two chances to be wrong.  Split, the
   end of one and the start of the next are two lines with the silence
   between them shaded as belonging to neither, for a recording that really
   does pause (a chapter heading read, then a breath, then the text).  A
   video has no split: a caption has a start and nothing else, and the one
   before it runs until that start, so the two numbers ARE one number.

   WHAT IT DOES NOT KNOW.  Not where the times live, not how to play them,
   not how to draw the sound: the caller passes those in, because a book's
   are a narration's own clock read by an <audio> and a video's are the
   player's, and this file would be wrong about one of them.  See `open`. */
(function () {
  'use strict';
  if (window.ParsehTimeline) return;

  var PREVIEW = 1.5;          // seconds a move replays, as in the book
  var LEAST = 0.05;           // the shortest a piece may be made by dragging
  var PAD = 0.75;             // what a fitted view leaves either side
  var LEAD = 0.15;            // a mark is "reached" this early, as the player
  var STEP = {'-1': -1, '-5': -0.5, '-': -0.1, '+': 0.1, '+5': 0.5, '+1': 1};
  var KNOB = 14, REACH = 11;  // the finger targets of a line on the strip

  // WHICH WAY "ESTIMATE THE REST" GOES -- 'text' or 'sound' -- is a habit of
  // the hand and not a property of one book, so it is kept on this device
  // and is the same for a book and a video.  Every touch of the storage is
  // in a try: a private window, or a page opened off the disk, may refuse
  // it, and then the choice simply lasts as long as the sheet.
  var BY_KEY = 'tl_estimate_by';
  function readBy() {
    try { return window.localStorage.getItem(BY_KEY) === 'sound' ? 'sound' : 'text'; }
    catch (e) { return 'text'; }
  }
  function keepBy(v) {
    try { window.localStorage.setItem(BY_KEY, v); } catch (e) {}
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function button(text, attrs) {
    var b = el('button', null, text);
    b.type = 'button';
    for (var k in attrs) if (attrs.hasOwnProperty(k)) b.setAttribute(k, attrs[k]);
    return b;
  }
  function r2(n) { return Math.round(n * 100) / 100; }
  function r1(n) { return Math.round(n * 10) / 10; }
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function str(v) { return typeof v === 'string' ? v : ''; }

  /* THE MIDDLE OF THE QUIET NEAREST A TIME, in a window of the sound's peaks -- the finder `into the quiet` uses
     (below), at the top of the file because the video player settles a line's new start with it too
     (ParsehTimeline.quiet): a boundary belongs in the silence between two words. */
  var SNAP_QUIET = 0.12;      // of the window's own loudest
  var SNAP_LEAST = 0.06;      // a gap shorter than this is inside a word
  function middleOfQuiet(res, t) {
    if (!res || !res.peaks || !res.peaks.length) return null;
    var p = res.peaks, n = p.length, a = +res.start, b = +res.end;
    if (!(b > a)) return null;
    var step = (b - a) / n, top = 0, i;
    for (i = 0; i < n; i++) if (p[i] > top) top = p[i];
    if (!(top > 0)) return null;          // all of it is silence: nothing to aim at
    var mark = top * SNAP_QUIET, best = null, bestD = Infinity, from = -1;
    for (i = 0; i <= n; i++) {
      var quiet = i < n && p[i] <= mark;
      if (quiet && from < 0) from = i;
      if (!quiet && from >= 0) {
        var t0 = a + from * step, t1 = a + i * step;
        if (t1 - t0 >= SNAP_LEAST) {
          var mid = (t0 + t1) / 2;
          // a gap the edge already stands in is the one that was meant,
          // however far its middle happens to be
          var d = (t >= t0 && t <= t1) ? -1 : Math.abs(mid - t);
          if (d < bestD) { bestD = d; best = mid; }
        }
        from = -1;
      }
    }
    return best;
  }
  // 0:08.40 -- the clock the reader's own boxes carry, to a hundredth
  function fmt(t) {
    t = Math.max(0, +t || 0);
    var m = Math.floor(t / 60), s = t - m * 60;
    return m + ':' + (s < 10 ? '0' : '') + s.toFixed(2);
  }
  // STRICTLY, because parseFloat is not strict: it reads "03s.40" as 3 and
  // says nothing, so a stray keystroke in a time box would have retimed a
  // subparagraph to a number nobody typed.  A part is digits, with at most
  // one point in it, and anything else is not a time at all -- refused, and
  // the box goes back to what the boundary actually is.
  var PART = /^(?:\d+(?:\.\d*)?|\.\d+)$/;
  function parse(v) {
    v = String(v == null ? '' : v).trim().replace(',', '.');
    if (!v) return null;
    var p = v.split(':'), n = 0;
    if (p.length > 3) return null;
    for (var i = 0; i < p.length; i++) {
      if (!PART.test(p[i])) return null;
      n = n * 60 + parseFloat(p[i]);
    }
    return isFinite(n) ? Math.max(0, n) : null;
  }

  var current = null;

  /* opts:
       title      what the sheet is called
       marks      [{key, label, text, t0, t1}] in order; for `point` only t0
                  is read and t1 is whatever the next one starts at
       kind       'span' (a book: two numbers, splittable) or
                  'point' (a video: one number, and no split)
       duration   the whole recording's length, when it is known
       dir, lang  how the text of a mark is written
       at         the mark to open on (an index), else the first
       peaks(a,b,n)  -> Promise<{peaks:[0..1], start, end}> or null for none
       play(a,b)     play that stretch; stop() stops it
       now()         where the sound stands, for the ◉ stamp, or null
       estimate(req) -> Promise of the server's answer to "estimate the rest
                     by the sound" (serve.py, lib/wavealign.py), or a
                     rejection carrying its words; req is {start, end, texts,
                     kind} -- the stretch to lay, which is the whole rest or
                     only the next N seconds of it (see `stretch`), and the
                     texts of the pieces inside it and no others.  Absent,
                     "by the sound" is offered but grey.
       save(changed) -> Promise; `changed` is [{key, t0, t1}] of what moved */
  function open(opts) {
    if (current) current.cancel();
    return new Promise(function (resolve) { current = build(opts || {}, resolve); });
  }

  function build(opts, resolve) {
    var kind = opts.kind === 'point' ? 'point' : 'span';
    var point = kind === 'point';
    var dur = +opts.duration > 0 ? +opts.duration : 0;
    var closed = false, dragging = null, busy = false;
    // `estimating` is the one busy spell that holds the marks still as well:
    // the answer is laid over the numbers the question was asked about.
    // `asking` numbers the questions, so an answer to one given up (stopped,
    // see stopSound) is known for a stale one when it comes
    var by = readBy(), estimating = false, asking = 0;

    // THE WORKING COPY.  Nothing the caller handed in is written to: what
    // comes back out of `save` is the list of what moved, and a cancel
    // leaves the caller's own array exactly as it was.
    var marks = (opts.marks || []).map(function (m, i) {
      return {key: str(m.key) || String(i), label: str(m.label), text: str(m.text),
              t0: +m.t0 || 0, t1: m.t1 == null ? null : +m.t1, i: i};
    });
    var N = marks.length;
    // a video's ends are never stored: one caption runs until the next
    function endOf(i) {
      if (point) return i + 1 < N ? marks[i + 1].t0 : (dur || marks[i].t0 + 4);
      return marks[i].t1 == null ? marks[i].t0 : marks[i].t1;
    }
    // which boundaries have been pulled apart; a video's never can be
    var split = {};
    if (!point)
      for (var k = 0; k + 1 < N; k++)
        if (Math.abs(endOf(k) - marks[k + 1].t0) > 0.005) split[k] = true;

    var start0 = marks.map(function (m) { return m.t0; });
    var end0 = marks.map(function (m, i) { return endOf(i); });

    var sel = clamp(+opts.at || 0, 0, Math.max(0, N - 1));
    var edge = 's';                     // which line of `sel` the steps move
    var view = [0, 1], peaks = null, peaksView = null, plain = false;
    var peaksAsk = 0, peaksTimer = 0, playing = false;

    var before = document.activeElement;
    var root = el('div', 'tl-root');
    root.setAttribute('dir', 'ltr');
    root.setAttribute('lang', 'en');
    var box = el('div', 'tl-box');
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', str(opts.title) || 'edit the timings');
    box.tabIndex = -1;
    root.appendChild(box);

    /* ---- the head ---- */
    var head = el('div', 'tl-head');
    head.appendChild(el('span', 'tl-title', str(opts.title) || 'edit the timings'));
    var shut = button('✕', {'class': 'tl-x', 'data-x': 'cancel',
                                 'title': 'leave without saving (Escape)',
                                 'aria-label': 'close'});
    head.appendChild(shut);
    box.appendChild(head);

    /* ---- the three that matter, above the sound ---- */
    var texts = el('div', 'tl-texts');
    function line(cls, what) {
      var d = el('div', 'tl-line ' + cls);
      d.appendChild(el('span', 'tl-who', what));
      var t = el('bdi', 'tl-say');
      if (opts.dir) t.setAttribute('dir', opts.dir);
      if (opts.lang) t.setAttribute('lang', opts.lang);
      d.appendChild(t);
      texts.appendChild(d);
      return {row: d, say: t};
    }
    var prevLine = line('tl-prev', 'before');
    var nowLine = line('tl-now', 'here');
    var nextLine = line('tl-next', 'after');
    box.appendChild(texts);

    /* ---- the boundary itself: its number, and the six steps ---- */
    var edit = el('div', 'tl-edit');
    var what = el('div', 'tl-what');
    edit.appendChild(what);

    function stepRow(name, which) {
      var r = el('div', 'tl-row');
      r.dataset.edge = which;
      r.appendChild(el('span', 'tl-lbl', name));
      ['-1', '-5', '-'].forEach(function (s) {
        r.appendChild(button(s === '-' ? '−.1' : s === '-5' ? '−.5' : '−1',
                             {'data-e': which + s, 'class': 'tl-step'}));
      });
      var inp = el('input', 'tl-at');
      inp.type = 'text';
      inp.inputMode = 'decimal';
      inp.setAttribute('aria-label', name + ' of this piece, in the recording');
      r.appendChild(inp);
      ['+', '+5', '+1'].forEach(function (s) {
        r.appendChild(button(s === '+' ? '+.1' : s === '+5' ? '+.5' : '+1',
                             {'data-e': which + s, 'class': 'tl-step'}));
      });
      r.appendChild(button('◉', {'data-e': which + 'h', 'class': 'tl-step tl-stamp',
                                      'title': 'put it where the sound stands now'}));
      edit.appendChild(r);
      return {row: r, at: inp};
    }
    var rowS = stepRow('starts', 's');
    var rowE = stepRow('ends', 'e');

    var acts = el('div', 'tl-acts');
    var playBtn = button('▶ hear it', {'data-x': 'play', 'class': 'tl-btn',
      'title': 'play this piece from its start to where the next one begins'});
    var crossBtn = button('▶ across the join', {'data-x': 'cross', 'class': 'tl-btn',
      'title': 'play the second before the boundary and the second after it, to hear whether it falls in the right place'});
    var splitBtn = button('split', {'data-x': 'split', 'class': 'tl-btn',
      'title': 'let this piece end before the next one starts, leaving the silence between them to neither'});
    var REST_BY = {
      text: 'lay a first guess over everything AFTER this line -- each piece given '
          + 'a slice of what is left in proportion to how much text it has, the way '
          + '\u201cestimate times\u201d does over a whole recording. Nothing to the '
          + 'left of this line is touched (E)',
      sound: 'lay a first guess over everything AFTER this line from the picture of '
           + 'the sound \u2014 each boundary put in a pause it shows where the length '
           + 'of the text allows, and the rest shared out by the pace of the speech '
           + 'around it. Nothing to the left of this line is touched (E)'};
    var restBtn = button('estimate the rest', {'data-x': 'rest', 'class': 'tl-btn',
                                               'title': REST_BY.text});
    var STOP_WHY = 'stop waiting for the estimate from the sound: nothing is laid, and '
      + 'nothing that was moved by hand is lost (Escape)';
    // THE TWO WAYS OF ESTIMATING IT, side by side with the button they steer
    // and pressed like a switch: which one E runs is always on the screen.
    // By the sound needs a picture of the sound, and says so while there is
    // none; the one chosen is remembered all the same, and is back in force
    // the moment a picture comes (see soundWhy).
    var byText = button('by the text', {'data-x': 'by-text', 'class': 'tl-by-b',
      'aria-pressed': 'true',
      'title': 'estimate in proportion to how much text each piece has '
             + '\u2014 it needs no picture of the sound, and hears nothing'});
    var bySound = button('by the sound', {'data-x': 'by-sound', 'class': 'tl-by-b',
      'aria-pressed': 'false'});
    var SOUND_WHY = 'estimate from the picture of the sound: the pieces are '
      + 'laid through it in order, their boundaries in the pauses it shows where the '
      + 'text allows \u2014 it hears where the speech stops and starts, never which '
      + 'words are said';
    var byGroup = el('span', 'tl-by');
    byGroup.setAttribute('role', 'group');
    byGroup.setAttribute('aria-label', 'how the rest is estimated');
    byGroup.appendChild(byText);
    byGroup.appendChild(bySound);
    // THE NEXT N SECONDS, between what is estimated and how: read from left
    // to right the row says "estimate [the rest | the next 30 s] [by the
    // text | by the sound]".  Empty is the rest, as it always was; a number
    // makes the same act a shorter one (see `stretch`).  It is NOT kept: a
    // habit of the hand is the switch, but how far to estimate is a decision
    // about this stretch of this recording, made afresh every time, so
    // every sheet opens on "estimate the rest".
    var NEXT_WHAT = 'estimate only as far as this many seconds after the line in hand \u2014 the '
      + 'pieces in that stretch, up to the boundary closest to it. 90, or 1:30; empty, it is '
      + 'everything after the line. Enter takes the number and gives the keys back to the sheet';
    // refused in words, and never guessed at (the same as every time box):
    // the status says what happened, the button's title what to do about it
    var NEXT_BAD = 'the box must hold seconds (90 or 1:30) or be empty; nothing was estimated';
    var NEXT_ZERO = 'the seconds in the box must be above zero, or the box empty; nothing was estimated';
    var NEXT_BAD_TITLE = 'the box beside this button does not hold a number of seconds (90 or 1:30): '
      + 'until it does, or is emptied, this button and E estimate nothing';
    var nextIn = el('input', 'tl-nx-in');
    nextIn.type = 'text';
    nextIn.inputMode = 'decimal';
    nextIn.maxLength = 9;
    nextIn.autocomplete = 'off';
    nextIn.spellcheck = false;
    nextIn.setAttribute('aria-label', 'seconds after this line to estimate; empty for the whole rest');
    nextIn.title = NEXT_WHAT;
    var nextBox = el('label', 'tl-nx');
    nextBox.appendChild(document.createTextNode('the next'));
    nextBox.appendChild(nextIn);
    nextBox.appendChild(document.createTextNode('s'));
    var restGroup = el('span', 'tl-est');
    restGroup.appendChild(restBtn);
    restGroup.appendChild(nextBox);
    restGroup.appendChild(byGroup);
    var quietBtn = button('into the quiet', {'data-x': 'quiet', 'class': 'tl-btn',
      'title': 'move it to the middle of the nearest stretch where the sound drops '
             + 'away \u2014 the gap between two words, which is where a boundary '
             + 'belongs (S)'});
    var quietWhy = quietBtn.title;
    acts.appendChild(playBtn);
    acts.appendChild(crossBtn);
    acts.appendChild(quietBtn);
    acts.appendChild(restGroup);
    if (!point) acts.appendChild(splitBtn);
    edit.appendChild(acts);
    box.appendChild(edit);

    /* ---- the sound, at the bottom ---- */
    var wrap = el('div', 'tl-wrap');
    var zoom = el('div', 'tl-zoom');
    var outBtn = button('−', {'data-x': 'out', 'class': 'tl-zb',
                                   'title': 'see more of the recording at once'});
    var inBtn = button('+', {'data-x': 'in', 'class': 'tl-zb',
                             'title': 'see less of it, in more detail'});
    var fitBtn = button('fit', {'data-x': 'fit', 'class': 'tl-zb',
                                'title': 'back to the piece being timed and its neighbours (F)'});
    var allBtn = button('all', {'data-x': 'all', 'class': 'tl-zb',
                                'title': 'the whole recording at once'});
    var v0Lab = el('span', 'tl-t'), spanLab = el('span', 'tl-span'), v1Lab = el('span', 'tl-t');
    zoom.appendChild(outBtn); zoom.appendChild(inBtn);
    zoom.appendChild(fitBtn); zoom.appendChild(allBtn);
    // MAKING A PICTURE OF THE SOUND WHERE THERE IS NONE.  Only a caller with
    // no other way to one offers this, and only ever as something asked for:
    // it costs the whole length of the recording, in real time, and Chrome
    // asks to share the tab before it can start.
    var waveBtn = null;
    if (opts.wave) {
      waveBtn = button('\u25cf draw the sound', {'data-x': 'wave', 'class': 'tl-zb tl-wavebtn'});
      zoom.appendChild(waveBtn);
    }
    zoom.appendChild(v0Lab); zoom.appendChild(spanLab); zoom.appendChild(v1Lab);
    wrap.appendChild(zoom);

    var strip = el('div', 'tl-strip');
    var canvas = el('canvas', 'tl-wave');
    strip.appendChild(canvas);
    var bands = el('div', 'tl-bands');       // one tinted block per piece
    strip.appendChild(bands);
    var lines = el('div', 'tl-lines');       // the boundaries themselves
    strip.appendChild(lines);
    var playhead = el('div', 'tl-playhead');
    strip.appendChild(playhead);
    wrap.appendChild(strip);
    box.appendChild(wrap);

    // The hint is one sentence longer than it looks: what E does with the
    // box beside it, which depends on what the box holds (see paintHint).
    var HINT_HEAD = 'Drag a boundary, or click a piece to take it up. The arrows move it by 0.1 s ' +
      '(Shift: 0.5 s), ◉ puts it where the sound stands, and Space plays it. ' +
      '“,” and “.” take up the piece before and after, '  +
      'F brings the view back to it, S drops the line being moved into the '  +
      'nearest quiet, and E lays a fresh guess over everything after it — '  +
      'by the text or by the sound, whichever of the two is pressed beside '  +
      'the estimate button.';
    var HINT_TAIL = ' Escape leaves it (while the sound is being read, Escape stops that instead).';
    var hint = el('div', 'tl-hint', HINT_HEAD + HINT_TAIL);
    box.appendChild(hint);

    /* ---- the foot ---- */
    var foot = el('div', 'tl-foot');
    var stat = el('span', 'tl-stat');
    stat.setAttribute('role', 'status');
    var saveBtn = button('save the timings', {'data-x': 'save', 'class': 'tl-btn tl-save'});
    var cancelBtn = button('cancel', {'data-x': 'cancel', 'class': 'tl-btn'});
    foot.appendChild(stat);
    foot.appendChild(saveBtn);
    foot.appendChild(cancelBtn);
    box.appendChild(foot);

    /* ================= what is where ================= */
    function xOf(t) { return (t - view[0]) / (view[1] - view[0]) * 100; }
    function tAt(clientX) {
      var r = strip.getBoundingClientRect();
      var f = clamp((clientX - r.left - strip.clientLeft) / (strip.clientWidth || 1), 0, 1);
      return view[0] + f * (view[1] - view[0]);
    }
    // WHAT MOVED, and no more than that.  A point mark owns its start and
    // nothing else -- its end is the next one's start, and that next one
    // reports it -- so counting a changed end here would send the piece
    // before every moved caption as well, as a move from a number to
    // itself, and say "2 captions moved" where one did.
    function moved() {
      var out = [];
      for (var i = 0; i < N; i++) {
        var e = endOf(i);
        var shifted = Math.abs(marks[i].t0 - start0[i]) > 0.005
          || (!point && Math.abs(e - end0[i]) > 0.005);
        if (shifted)
          out.push(point ? {key: marks[i].key, t0: r2(marks[i].t0)}
                         : {key: marks[i].key, t0: r2(marks[i].t0), t1: r2(e)});
      }
      return out;
    }

    /* ================= moving things ================= */
    // THE ONE ACT.  Moving a boundary is moving the end of one piece and the
    // start of the next to the same number; only a split boundary is two.
    function setBoundary(i, t, who) {
      // the boundary after piece i.  `who` is 'e' (the end of i) or 's' (the
      // start of i+1), which only tells the two apart when they are split.
      var lo = marks[i].t0 + LEAST;
      var hi = i + 1 < N ? (split[i] && who === 's' ? endOf(i + 1) : endOf(i + 1)) - LEAST
                         : (dur || t + LEAST);
      if (i + 1 >= N) hi = dur ? dur : Math.max(t, marks[i].t0 + LEAST);
      t = clamp(t, lo, Math.max(lo, hi));
      if (point) {
        if (i + 1 < N) marks[i + 1].t0 = t;
        else marks[i].t1 = t;
        return;
      }
      if (i + 1 >= N) { marks[i].t1 = t; return; }
      if (split[i]) {
        if (who === 's') marks[i + 1].t0 = Math.max(t, marks[i].t1 == null ? t : marks[i].t1);
        else marks[i].t1 = Math.min(t, marks[i + 1].t0);
      } else {
        marks[i].t1 = t;
        marks[i + 1].t0 = t;
      }
    }
    function setStart(t) {                       // the very first start
      var hi = endOf(0) - LEAST;
      marks[0].t0 = clamp(t, 0, Math.max(0, hi));
    }

    function nudge(which, d) {
      if (estimating) return activeTime();
      edge = which;
      var t;
      if (which === 's') {
        if (sel === 0) { setStart(marks[0].t0 + d); t = marks[0].t0; }
        else { setBoundary(sel - 1, marks[sel].t0 + d, 's'); t = marks[sel].t0; }
        paint();
        preview('head');
      } else {
        setBoundary(sel, endOf(sel) + d, 'e');
        t = endOf(sel);
        paint();
        preview('tail');
      }
      return t;
    }
    // where the active edge stands, and the one way of putting it somewhere:
    // the steps, the typed time, the playhead stamp and the snap to the
    // quiet all mean the same act on the same number
    function activeTime() { return edge === 's' ? marks[sel].t0 : endOf(sel); }
    function placeEdge(which, t) {
      if (estimating) { paint(); return; }
      edge = which;
      if (which === 's') {
        if (sel === 0) setStart(t); else setBoundary(sel - 1, t, 's');
      } else setBoundary(sel, t, 'e');
      paint();
      preview(which === 's' ? 'head' : 'tail');
    }
    function stamp(which) {
      var t = opts.now ? opts.now() : null;
      if (t == null) { say('there is nothing playing to take a time from', true); return; }
      placeEdge(which, t);
    }
    function commit(inp, which) {
      var t = parse(inp.value);
      if (t == null) { paint(); return; }
      placeEdge(which, t);
    }

    /* ================= playing ================= */
    function stop() { playing = false; if (opts.stop) try { opts.stop(); } catch (e) {} }
    function play(a, b) {
      if (!opts.play) return;
      playing = true;
      try { opts.play(Math.max(0, a), b); } catch (e) {}
    }
    function preview(side) {
      var a = marks[sel].t0, b = endOf(sel);
      if (side === 'head') play(a, Math.min(b, a + PREVIEW));
      else play(Math.max(a, b - PREVIEW), b);
    }
    function hear() { play(marks[sel].t0, endOf(sel)); }
    function cross() {
      // the second before the boundary and the second after it: the one
      // listen that says whether a boundary falls in the right place
      var t = edge === 's' ? marks[sel].t0 : endOf(sel);
      play(Math.max(0, t - 1), t + 1);
    }

    /* ============ the rest of it, estimated afresh ============
       A HAND WORKS LEFT TO RIGHT.  By the time the tenth boundary is right
       the fortieth is still where a first guess put it, and that guess was
       made over the WHOLE stretch -- so every error the hand has just taken
       out of the left is still spread through the right, pushing all of it
       the same way.  This lays the guess again over what is left: from the
       line in hand to the last end, in proportion to how much text each
       piece has, and it does not touch one number to the left of it.

       It is the same measure as `estimate times` on a narration row
       (lib/timestamp.py, spread): the text with its marks stripped and its
       spaces taken out, so a long sentence gets a long slice, and a floor
       under every piece so that none is too short to play.  Stripping is
       done here with NFD and the combining marks dropped, which is what
       LANG.strip does for the scripts that have them -- a vowelled Persian
       sentence is not longer than the same sentence bare, and counting the
       harakat would make it look it.

       It happens in the working copy, like everything else here: the strip
       shows it at once and nothing is written until it is saved.

       AND ONLY AS FAR AS THE HAND WANTS.  The whole rest is often more than
       the next stretch of work: fifty pieces of a long narration, where the
       hand has just fixed ten and means to hear the next ten before it
       trusts any of the forty after them -- and every number a guess moves
       is one to hear again.  With a number of seconds in the box beside the
       button the same act is done over a shorter stretch, and `stretch`
       says which. */
    var SPREAD_FLOOR = 0.4;
    function sizeOf(text) {
      var bare = String(text || "").normalize
        ? String(text || "").normalize("NFD").replace(/[̀-ًͯ-ْؐ-ؚۖ-ۭ]/g, "")
        : String(text || "");
      return Math.max(1, bare.replace(/\s+/g, "").length);
    }
    // the first piece whose start this would move, and the number it keeps
    function restFrom() { return edge === "s" ? sel : sel + 1; }

    // WHAT THE BOX HOLDS: nothing, a number of seconds above zero, or
    // something that is not one -- which is refused in words and never
    // guessed at, as every time box here is (see `parse`).  The number is
    // taken to the hundredth like every other number on the sheet, so one
    // that rounds to nothing is nothing.
    function nextRead() {
      var raw = nextIn.value.trim();
      if (!raw) return {state: 'none'};
      var n = parse(raw);
      if (n == null) return {state: 'bad', why: NEXT_BAD};
      if (!(r2(n) > 0)) return {state: 'bad', why: NEXT_ZERO};
      return {state: 'ok', n: n, text: String(r2(n)), one: r2(n) === 1};
    }

    /* THE STRETCH: WHICH PIECES THE ESTIMATE LAYS, AND WHERE IT STOPS.  From
       the line in hand, `a`, to a CUT -- a boundary that is there already:
       the start of some piece after the first one it would move, or the end
       of the last piece.  Whole, the cut is the end of the last piece and it
       is "estimate the rest", as it always was.  With a number of seconds it
       is the cut CLOSEST to a + that number, on either side of it -- the
       last cut short of it is not "closest" when the next is a hair beyond
       -- and a tie goes to the earlier, the smaller stretch.  The cut is
       where the hand said a piece begins, so it is kept: the piece at it and
       everything after it are never written, and the stretch's last piece
       runs up to it, never past.  Every stretch holds at least one piece,
       because the cuts are taken from the second piece on.

       A tie is a tie in decimals and not in doubles, so distances are
       compared in millionths of a second: 3.9 + 3.25 is halfway between 6.5
       and 7.8, and in doubles it is a hair nearer 7.8, which is here the
       end -- the whole rest, from a hand that asked for less.  A cut so
       close to the line that no piece fits before it (SPREAD_FLOOR) is not
       one to choose: the next is taken instead, or there is none and the
       stretch is the rest, which then says "there is no room". */
    // ROOM FOR A PIECE BETWEEN THE LINE AND A CUT, decided in millionths of a
    // second like the distances: a cut exactly SPREAD_FLOOR after the line
    // is 0.4 s away in decimals, and in doubles it is sometimes a hair more
    // and sometimes a hair less -- so which stretch a number made would
    // depend on where the line happened to stand.  Strictly more than the
    // floor, as it always was.
    function room(cut, line) {
      return Math.round((cut - line) * 1e6) > Math.round(SPREAD_FLOOR * 1e6);
    }
    function stretch(num) {
      var from = restFrom(), a = N ? activeTime() : 0, end = N ? endOf(N - 1) : 0;
      var sc = {from: from, to: N - 1, a: a, cut: end, whole: true,
                boxed: !!num, text: num ? num.text : '', one: !!(num && num.one)};
      if (!num || from >= N) return sc;
      var want = a + num.n, best = Infinity;
      for (var j = from + 1; j <= N; j++) {
        var t = j < N ? marks[j].t0 : end;
        if (!room(t, a)) continue;
        var d = Math.round(Math.abs(t - want) * 1e6);
        if (d < best) { best = d; sc.to = j - 1; sc.cut = t; sc.whole = j === N; }
      }
      return sc;
    }
    // WHAT WAS LAID, in words: which stretch, which way, what it heard, and
    // what stayed still.  A number whose closest boundary is the end says so,
    // since it was asked for less than the whole rest and got it -- the
    // number may fall short of the end, or run past it, and be nearer to it
    // than to the last piece's start all the same.
    function laid(sc, how, heardNote) {
      var n = sc.to - sc.from + 1;
      var count = n === 1 ? 'the one piece' : n + ' pieces';
      if (sc.boxed && !sc.whole)
        return count + ' in the next ' + r1(sc.cut - sc.a) + ' s (to ' + fmt(sc.cut) + ') estimated '
          + how + heardNote + '; nothing outside that stretch moved';
      return count + ' after this estimated ' + how + heardNote + '; nothing to the left of it moved'
        + (sc.boxed ? ' (the closest boundary to the next ' + sc.text + (sc.one ? ' second' : ' seconds')
                      + ' is the end, so this is the whole rest)' : '');
    }

    function spreadRest() {
      if (busy) return;
      var num = nextRead();
      if (num.state === 'bad') { say(num.why, true); return; }
      var sc = stretch(num.state === 'ok' ? num : null);
      if (byNow() === 'sound') { soundRest(sc); return; }
      if (sc.from >= N) {
        say("there is nothing after this one to estimate", true);
        return;
      }
      if (!room(sc.cut, sc.a)) {
        say("there is no room between this line and the end", true);
        return;
      }
      var sizes = [], total = 0, i;
      for (i = sc.from; i <= sc.to; i++) { var z = sizeOf(marks[i].text); sizes.push(z); total += z; }
      total = total || 1;
      var span = sc.cut - sc.a, t = sc.a;
      for (i = sc.from; i <= sc.to; i++) {
        var k = i - sc.from;
        // the last one ends at the cut: a rounding error must not leave a
        // sliver of silence nobody can play
        var end = (i === sc.to) ? sc.cut : t + span * sizes[k] / total;
        if (end < t + SPREAD_FLOOR) end = Math.min(sc.cut, t + SPREAD_FLOOR);
        marks[i].t0 = r2(t);
        if (!point) {
          // at a cut short of the end, the piece after it starts where it
          // did, so this one ends exactly there and not at a rounding of it
          marks[i].t1 = (i === sc.to && !sc.whole) ? sc.cut : r2(end);
          // a spread is contiguous by what it means, so a boundary pulled
          // apart to the right of here is put back together
          if (i < N - 1) delete split[i];
        }
        t = end;
      }
      paint();
      say(laid(sc, 'afresh by the text', ''));
    }

    /* ============ the rest of it, estimated from the sound ============
       THE SAME ACT, WITH EARS.  By the text puts every boundary where the
       length of the text says it falls, which is right on average and wrong
       in every pause the reader took and every sentence said faster than
       the last.  By the sound hands the same pieces, with the same stretch,
       to the server (lib/wavealign.py through `opts.estimate`), which lays
       them through the picture of the sound: a boundary goes into a pause
       the picture shows where the length of the text allows one, and the
       pace of the speech is followed as it changes.  It hears WHERE the
       speech stops and starts, never WHAT is said -- so it is a better
       first guess, and still a guess to be fixed by ear.

       What it may change is exactly what by the text may: nothing to the
       left of the line in hand, and nothing of what lies after it but the
       pieces' own numbers.  The stretch starts AT THE LINE, whichever edge
       it is: a start in hand keeps its piece's start, and the leading
       silence stays with that piece; an end in hand becomes the next
       piece's start too, as by the text makes it -- a split boundary's old
       start, somewhere after the line, would leave the sound between them
       to nobody.  A book's boundaries come back joined or split as the
       sound has them (a pause a breath long is left to neither piece); a
       video's are one number each, as ever.  While the answer is awaited
       the marks are held still, because it is laid over the numbers the
       question was asked about; a sheet shut in the meantime drops it; and
       the wait can be given up (stopSound), since an hour of sound may
       take a minute or two to read. */
    // WHY BY THE SOUND IS GREY, or '' when it is not.  Only a reader can
    // lack `estimate`: the page is written when the book is built while this
    // file is served fresh to every page, so a reader built before by the
    // sound came opens this sheet without the door -- and the one button
    // that writes a new reader without touching the timings is in that
    // reader's own top bar.
    function soundWhy() {
      if (!opts.estimate)
        return 'this reader was built before estimating by the sound existed: press '
          + '“rebuild the reader” in the bar at the top of the page, then reload '
          + 'the page';
      if (peaks || drawable) return '';
      if (opts.wave)
        return str(opts.wave.why)
          ? 'there is no picture of the sound here to estimate by, and it cannot be '
            + 'drawn in this browser: ' + str(opts.wave.why)
          : 'draw the sound first (“● draw the sound”, above the picture): '
            + 'there is no picture of it here yet to estimate by';
      if (!opts.peaks || (plain && !probing))
        return 'there is no picture of the sound here to estimate by — it is drawn by '
          + 'ffmpeg, on the computer Parseh runs on';
      return 'waiting for the picture of the sound…';
    }
    // WHETHER THE SOUND CAN BE DRAWN HERE AT ALL, which is not the same
    // question as whether THIS VIEW has a picture.  The server draws at most
    // five minutes at a time (clips.MAX_SECONDS), so "all" over a longer
    // narration comes back empty on a computer that has ffmpeg -- and read
    // as "no picture", that greyed by the sound and blamed ffmpeg for it.
    // So a picture ever drawn in this sheet settles it for good, and a view
    // that comes back empty before one has is followed by ONE question for a
    // short stretch at its start: only if that fails too is there no picture
    // to be had.  TWO SECONDS OF IT, because any picture at all answers the
    // question: so short a one is cheap to draw, and under any limit a
    // server may put on one window, not only today's five minutes (the
    // tests hold their eight-second recording to seven, and a longer
    // question would be refused there for the very reason the view was).
    var PROBE = 2;
    var drawable = false, probing = false, probed = false;
    function probeSound() {
      if (drawable || probed || !opts.peaks) return;
      probed = true; probing = true;
      var a = r2(view[0]), b = r2(Math.min(view[1], view[0] + PROBE));
      if (!(b > a)) b = r2(a + 1);
      Promise.resolve(opts.peaks(a, b, 50)).then(function (res) {
        probing = false;
        if (closed) return;
        if (res && res.peaks && res.peaks.length) drawable = true;
        paintEdit();
      }).catch(function () {
        probing = false;
        if (!closed) paintEdit();
      });
    }
    // the way E goes now: the one chosen, unless it cannot go that way here
    function byNow() { return by === 'sound' && !soundWhy() ? 'sound' : 'text'; }
    function choose(v) {
      if (busy) return;
      by = v;
      keepBy(v);
      paintEdit();
      say('\u201c' + restBtn.textContent + '\u201d now goes by the ' + (v === 'sound' ? 'sound' : 'text'));
    }
    function heard(anchored, boundaries) {
      var a = Math.max(0, Math.round(+anchored || 0)), b = Math.max(0, Math.round(+boundaries || 0));
      if (!b) return '';
      if (b === 1) return ' — the boundary between them sits in '
        + (a ? 'a pause it heard' : 'no pause it heard');
      if (!a) return ' — none of the ' + b + ' boundaries sits in a pause it heard';
      if (a >= b) return ' — all ' + b + ' boundaries sit in a pause it heard';
      return ' — ' + a + ' of the ' + b + ' boundaries ' + (a === 1 ? 'sits' : 'sit')
        + ' in a pause it heard';
    }
    // every number the marks hold, to tell whether any moved while waiting
    function held() {
      return JSON.stringify([marks.map(function (m) { return [m.t0, m.t1]; }),
                             Object.keys(split).sort()]);
    }
    function soundRest(sc) {
      if (sc.from >= N) {
        say('there is nothing after this one to estimate', true);
        return;
      }
      if (!room(sc.cut, sc.a)) {
        say('there is no room between this line and the end', true);
        return;
      }
      // ONLY THE PIECES INSIDE THE STRETCH are asked about, from the line to
      // the cut: the server lays what it is given through the sound of that
      // stretch, and knows nothing of what lies beyond it
      var texts = [];
      for (var i = sc.from; i <= sc.to; i++) texts.push(marks[i].text);
      var was = held();
      var me = ++asking;
      busy = true; estimating = true;
      paintEdit(); paintWave();
      say(sc.boxed && !sc.whole ? 'estimating the next ' + r1(sc.cut - sc.a) + ' s from the sound…'
                                : 'estimating from the sound…');
      var asked;
      try { asked = opts.estimate({start: sc.a, end: sc.cut, texts: texts, kind: kind}); }
      catch (e) { asked = Promise.reject(e); }
      Promise.resolve(asked).then(function (res) {
        if (closed || me !== asking) return;
        busy = false; estimating = false;
        var why = held() !== was
          ? 'the timings moved while the sound was being read, so nothing was laid'
          : laySound(res, sc);
        if (why) { say(why, true); paintEdit(); paintWave(); return; }
        paint();
        say(laid(sc, 'from the sound', heard(res.anchored, res.boundaries)));
      }, function (err) {
        if (closed || me !== asking) return;
        busy = false; estimating = false;
        say((err && err.message) || 'the sound could not be read to estimate from', true);
        paintEdit(); paintWave();
      });
    }
    // GIVING UP THE WAIT.  A long stretch is read for a minute or two, a
    // server gone quiet may never answer, and until then the sheet holds
    // still -- save included, so that no save can race the answer.  The one
    // way out used to be leaving, which threw away every unsaved change
    // made in the sheet.  So while it waits, "estimate the rest" is a stop,
    // and so is Escape: the question is forgotten (its answer, when it
    // comes, is a stale one and is dropped), nothing has moved, and the
    // sheet is the hand's again.  True when there was a wait to give up.
    function stopSound() {
      if (!estimating) return false;
      asking++;
      busy = false; estimating = false;
      paintEdit(); paintWave();
      say('stopped: nothing was estimated, and nothing moved');
      return true;
    }
    // THE ANSWER, CHECKED WHOLE BEFORE ONE NUMBER OF IT IS LAID: a piece for
    // each piece asked about, in order, inside the stretch.  Anything else
    // is refused as a whole, and the working copy is as it was.
    //
    // AT THE CUT, of a stretch that stops short of the end, a book's last
    // piece ends where the answer says -- never past the cut -- and the piece
    // after the cut keeps the start it had: joined to it when the answer
    // ends exactly there, split from it where the sound left a pause before
    // it, by the same rule as every boundary inside the stretch.  A video's
    // last caption has no end to write: it runs until the next one starts,
    // which is the cut, untouched.
    function laySound(res, sc) {
      var from = sc.from, a = sc.a, last = sc.cut;
      var p = res && res.pieces, n = sc.to - from + 1, k;
      var bad = 'the answer did not fit these pieces, so nothing was laid';
      if (!p || p.length !== n) return bad;
      var t0 = [], t1 = [];
      for (k = 0; k < n; k++) {
        t0.push(k === 0 ? a : r2(+p[k].t0));
        t1.push(point ? (k + 1 < n ? r2(+p[k + 1].t0) : last) : Math.min(last, r2(+p[k].t1)));
      }
      for (k = 0; k < n; k++) {
        if (!isFinite(t0[k]) || !isFinite(t1[k]) || !(t1[k] > t0[k])
            || t0[k] < a - 0.005 || (k + 1 < n && t1[k] > t0[k + 1] + 0.005))
          return bad;
      }
      for (k = 0; k < n; k++) {
        var i = from + k;
        marks[i].t0 = t0[k];
        if (point) continue;
        marks[i].t1 = t1[k];
        if (i + 1 >= N) continue;
        // a boundary the sound left a pause in is split, the pause said by
        // neither; any other is one number, exactly.  The one at the cut
        // is against the next piece's own start, which the answer never
        // had a say in
        var next = k + 1 < n ? t0[k + 1] : marks[i + 1].t0;
        if (next - t1[k] > 0.005) split[i] = true;
        else { delete split[i]; marks[i].t1 = next; }
      }
      return '';
    }

    /* ================= into the quiet ================= */
    /* A BOUNDARY BELONGS IN THE SILENCE BETWEEN TWO WORDS, not in the
       middle of one, and the eye finds that gap on the strip long before
       the hand can drag onto the middle of it.  This is the hand doing what
       the eye has already done.

       It reads the same peaks the strip draws, so it works wherever the
       strip does -- a book's narration and a film through the server's
       ffmpeg, a YouTube video through the recording of the tab -- and it
       asks for its own window, finer than the strip's, because what is one
       pixel on screen may be a tenth of a second of sound.

       QUIET IS RELATIVE, because the peaks are: audiofile.peaks scales a
       window to its own loudest, so a stretch is quiet here when it is far
       below whatever the loudest thing nearby is, and a gap shorter than a
       breath is not a gap at all but the pause inside one word. */
    function toSilence() {
      if (busy) return;
      if (!opts.peaks || !peaks) {
        say('there is no picture of the sound here to find the quiet in', true);
        return;
      }
      var which = edge, t = activeTime();
      // as far either side as the eye can see, within reason: zoomed in it
      // looks close, zoomed out it looks wide, and both are what was meant
      var w = clamp((view[1] - view[0]) / 4, 1.5, 8);
      var a = Math.max(0, t - w), b = t + w;
      if (dur) b = Math.min(b, dur);
      if (!(b > a)) return;
      busy = true; paintEdit(); paintWave();
      say('looking for the quiet\u2026');
      Promise.resolve(opts.peaks(r2(a), r2(b), 600)).then(function (res) {
        if (closed) return;
        busy = false;
        var at = middleOfQuiet(res, t);
        if (at == null) {
          say('no quiet stretch near it to move to', true);
          paintEdit(); paintWave();
          return;
        }
        placeEdge(which, at);
        say('moved into the quiet, at ' + fmt(activeTime()));
      }).catch(function () {
        if (closed) return;
        busy = false;
        say('the sound could not be read just there', true);
        paintEdit(); paintWave();
      });
    }

    /* ================= the picture ================= */
    // WHERE THE LAST PIECE ENDS, for the eye rather than for the ear.  A
    // video's last caption runs to the end of the file, which is the right
    // answer when playing it and a useless one when fitting the view: on an
    // hour of video whose last caption is at ten seconds, fitting near the
    // end would show fifty-nine minutes of nothing.  For the view it ends a
    // couple of typical captions after it starts instead.
    function fitEnd(i) {
      if (!point || i + 1 < N) return endOf(i);
      var typical = N > 1 ? (marks[N - 1].t0 - marks[0].t0) / (N - 1) : 4;
      return Math.min(endOf(i), marks[i].t0 + Math.max(4, typical * 2));
    }
    function fitted() {
      var a = marks[Math.max(0, sel - 1)].t0, b = fitEnd(Math.min(N - 1, sel + 1));
      var v = [Math.max(0, a - PAD), b + PAD];
      if (dur) v[1] = Math.min(v[1], Math.max(dur, b));
      if (!(v[1] > v[0])) v[1] = v[0] + 1;
      return v;
    }
    function setView(v, why) {
      var lo = Math.max(0, v[0]), hi = v[1];
      if (dur) hi = Math.min(hi, dur);
      if (!(hi - lo > 0.25)) hi = lo + 0.25;
      if (lo === view[0] && hi === view[1]) return;
      view = [lo, hi];
      askPeaks();
      paint();
      if (why) say(why);
    }
    function zoomBy(f) {
      var mid = (view[0] + view[1]) / 2, half = (view[1] - view[0]) * f / 2;
      setView([mid - half, mid + half]);
    }
    function showAll() { setView([0, dur || (endOf(N - 1) + PAD)]); }

    function askPeaks() {
      if (!opts.peaks) { plain = true; draw(); return; }
      clearTimeout(peaksTimer);
      peaksTimer = setTimeout(function () {
        var n = ++peaksAsk;
        var buckets = clamp(Math.round(strip.clientWidth || 600), 50, 4000);
        var a = r2(view[0]), b = r2(view[1]);
        Promise.resolve(opts.peaks(a, b, buckets)).then(function (res) {
          if (closed || n !== peaksAsk) return;
          if (res && res.peaks && res.peaks.length) {
            peaks = res.peaks;
            peaksView = [+res.start, +res.end];
            plain = false;
            drawable = true;
          } else { plain = true; probeSound(); }
          // a picture that has just come (or has just been found missing)
          // is what decides whether E may go by the sound
          draw(); paintEdit();
        }).catch(function () {
          if (closed || n !== peaksAsk) return;
          plain = true; probeSound(); draw(); paintEdit();
        });
      }, peaks ? 200 : 0);
    }

    function draw() {
      var w = strip.clientWidth, h = strip.clientHeight;
      var dpr = window.devicePixelRatio || 1;
      if (!w || !h) return;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      var c = canvas.getContext('2d');
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, w, h);
      strip.classList.toggle('tl-plain', plain && !peaks);
      strip.classList.toggle('tl-drawn', !!peaks);
      if (!peaks || !peaksView) return;
      var cs = getComputedStyle(strip);
      var off = cs.getPropertyValue('--tl-wave').trim() || '#a2949a';
      var on = cs.getPropertyValue('--tl-wave-on').trim() || '#be3455';
      var n = peaks.length, span = peaksView[1] - peaksView[0], mid = h / 2;
      var a = marks[sel].t0, b = endOf(sel);
      for (var i = 0; i < n; i++) {
        var t0 = peaksView[0] + span * i / n, t1 = peaksView[0] + span * (i + 1) / n;
        if (t1 < view[0] || t0 > view[1]) continue;
        var x0 = xOf(t0) * w / 100, x1 = xOf(t1) * w / 100;
        var amp = Math.max(1, peaks[i] * (h / 2 - 3));
        var tm = (t0 + t1) / 2;
        c.fillStyle = (tm >= a && tm <= b) ? on : off;
        c.fillRect(x0, mid - amp, Math.max(1, x1 - x0 - (x1 - x0 > 2 ? 0.5 : 0)), amp * 2);
      }
    }

    function paintBands() {
      bands.textContent = '';
      for (var i = 0; i < N; i++) {
        var a = marks[i].t0, b = endOf(i);
        if (b < view[0] || a > view[1]) continue;
        var d = el('div', 'tl-band' + (i === sel ? ' tl-band-on' : ''));
        d.style.left = clamp(xOf(a), -5, 105) + '%';
        d.style.width = Math.max(0, clamp(xOf(b), -5, 105) - clamp(xOf(a), -5, 105)) + '%';
        d.dataset.i = String(i);
        d.title = marks[i].label ? marks[i].label + ' — click to take it up' : 'click to take it up';
        var lab = el('span', 'tl-blab', marks[i].label || '');
        d.appendChild(lab);
        bands.appendChild(d);
        // the silence a split boundary leaves to neither piece
        if (!point && split[i] && i + 1 < N) {
          var g = el('div', 'tl-gap');
          g.style.left = clamp(xOf(b), -5, 105) + '%';
          g.style.width = Math.max(0, clamp(xOf(marks[i + 1].t0), -5, 105)
                                     - clamp(xOf(b), -5, 105)) + '%';
          g.title = 'said by neither: this piece has ended and the next has not begun';
          bands.appendChild(g);
        }
      }
    }
    function paintLines() {
      lines.textContent = '';
      function one(t, role, i, who) {
        if (t < view[0] - 0.01 || t > view[1] + 0.01) return;
        var d = el('div', 'tl-edge' + (role === 'on' ? ' tl-edge-on' : ''));
        d.style.left = xOf(t) + '%';
        d.dataset.i = String(i);
        d.dataset.who = who;
        d.tabIndex = 0;
        d.setAttribute('role', 'slider');
        d.setAttribute('aria-valuenow', String(r2(t)));
        d.setAttribute('aria-valuetext', fmt(t));
        d.setAttribute('aria-label', who === 's' ? 'where this piece starts' : 'where it ends');
        lines.appendChild(d);
      }
      one(marks[0].t0, sel === 0 && edge === 's' ? 'on' : '', 0, 's');
      for (var i = 0; i < N; i++) {
        var b = endOf(i);
        var isOn = (i === sel && edge === 'e') || (i === sel - 1 && edge === 's');
        one(b, isOn ? 'on' : '', i, 'e');
        if (!point && split[i] && i + 1 < N)
          one(marks[i + 1].t0, (i + 1 === sel && edge === 's') ? 'on' : '', i, 's');
      }
    }
    function paintTexts() {
      function put(o, i, blank) {
        if (i < 0 || i >= N) { o.row.classList.add('tl-none'); o.say.textContent = blank; return; }
        o.row.classList.remove('tl-none');
        o.say.textContent = (marks[i].label ? marks[i].label + '  ' : '') + marks[i].text;
      }
      put(prevLine, sel - 1, 'nothing before this one');
      put(nowLine, sel, '');
      put(nextLine, sel + 1, 'nothing after this one');
    }
    function paintEdit() {
      var a = marks[sel].t0, b = endOf(sel);
      what.textContent = (marks[sel].label ? marks[sel].label + ' — ' : '')
        + fmt(a) + ' to ' + fmt(b) + '  (' + (b - a).toFixed(2) + ' s)'
        + (!point && sel < N - 1 && split[sel] ? '  · split from the next' : '');
      if (document.activeElement !== rowS.at) rowS.at.value = fmt(a);
      if (document.activeElement !== rowE.at) rowE.at.value = fmt(b);
      rowS.row.classList.toggle('tl-on', edge === 's');
      rowE.row.classList.toggle('tl-on', edge === 'e');
      if (!point) {
        var isSplit = sel < N - 1 && !!split[sel];
        splitBtn.textContent = isSplit ? 'join to the next' : 'split from the next';
        splitBtn.disabled = sel >= N - 1 || estimating;
        splitBtn.title = sel >= N - 1
          ? 'there is nothing after this piece to split from'
          : isSplit ? 'let the next piece start exactly where this one ends'
                    : 'let this piece end before the next one starts, leaving the silence between them to neither';
      }
      // held still while the sound is being read: see soundRest
      Array.prototype.forEach.call(edit.querySelectorAll('.tl-step'),
                                   function (b) { b.disabled = estimating; });
      rowS.at.readOnly = rowE.at.readOnly = estimating;
      // while the sound is being read the button is the way to stop it, and
      // the box is held still with the marks: it is what the question was
      // asked about
      var next = nextRead();
      restBtn.disabled = estimating ? false : busy || restFrom() >= N;
      restBtn.textContent = estimating ? 'stop estimating'
        : next.state === 'ok' ? 'estimate the next ' + next.text + (next.one ? ' second' : ' seconds')
        : 'estimate the rest';
      nextIn.readOnly = estimating;
      if (next.state === 'bad') nextIn.setAttribute('aria-invalid', 'true');
      else nextIn.removeAttribute('aria-invalid');
      paintChoice(next);
      paintHint(next);
      quietBtn.disabled = busy || !peaks;
      quietBtn.title = peaks ? quietWhy
        : 'there is no picture of the sound here to find the quiet in';
      var n = moved().length;
      saveBtn.textContent = n ? 'save the timings (' + n + ')' : 'save the timings';
      saveBtn.disabled = !n || busy;
    }
    // WHICH WAY E GOES, shown as the one pressed.  A choice that cannot be
    // had here is kept (by) but not shown pressed, and its button says why
    // it is grey; the remembered one is back the moment a picture comes.
    function paintChoice(next) {
      var why = soundWhy(), now = byNow();
      byText.setAttribute('aria-pressed', now === 'text' ? 'true' : 'false');
      bySound.setAttribute('aria-pressed', now === 'sound' ? 'true' : 'false');
      byText.disabled = busy;
      bySound.disabled = busy || !!why;
      bySound.title = why || SOUND_WHY;
      restBtn.title = estimating ? STOP_WHY
        : next.state === 'bad' ? NEXT_BAD_TITLE
        : next.state === 'ok' ? nextBy(now, next) : REST_BY[now];
    }
    // WHAT THE BUTTON DOES WITH A NUMBER IN THE BOX, said with the stretch
    // it makes of it today: the rounding can land a good way from the number
    // where the pieces are long, and there is no other place that says where
    function nextBy(now, next) {
      var sc = stretch(next), n = sc.to - sc.from + 1;
      var where = sc.whole ? 'the end is the closest, so it is the whole rest'
        : (n === 1 ? 'the one piece' : n + ' pieces') + ', ' + r1(sc.cut - sc.a) + ' s, up to ' + fmt(sc.cut);
      return 'lay a first guess over the pieces in the next ' + next.text + (next.one ? ' second' : ' seconds')
        + ' after this line, up to the boundary closest to them (' + where + ') \u2014 '
        + (now === 'sound'
          ? 'each boundary put in a pause the picture of the sound shows where the length of the text '
            + 'allows, and the rest shared out by the pace of the speech around it'
          : 'each piece given a slice of that stretch in proportion to how much text it has')
        + '. Nothing outside that stretch is touched (E)';
    }
    // WHAT E DOES, by what the box holds.  Empty, the box is offered; a
    // number says what it will do; anything else says E will not run.
    function paintHint(next) {
      hint.textContent = HINT_HEAD + (next.state === 'ok'
        ? ' With a number in the box, E \u2014 once Enter has taken the number \u2014 estimates the pieces in the next '
          + next.text + (next.one ? ' second' : ' seconds') + ', up to the boundary closest to them; nothing outside that stretch moves.'
        : next.state === 'bad'
          ? ' The box beside it wants seconds (90 or 1:30) or nothing; E estimates nothing until it does.'
          : ' Seconds in the box beside it estimate only the next stretch of that length.')
        + HINT_TAIL;
    }
    function paintHead() {
      var t = opts.now ? opts.now() : null;
      if (t == null || t < view[0] || t > view[1]) { playhead.hidden = true; return; }
      playhead.hidden = false;
      playhead.style.left = xOf(t) + '%';
    }
    function paint() {
      v0Lab.textContent = fmt(view[0]);
      v1Lab.textContent = fmt(view[1]);
      spanLab.textContent = (view[1] - view[0]).toFixed(1) + ' s across';
      paintBands(); paintLines(); paintTexts(); paintEdit(); paintHead(); paintWave(); draw();
    }

    function say(text, bad) {
      stat.textContent = text || '';
      stat.classList.toggle('tl-bad', !!bad);
    }

    /* ================= taking one up ================= */
    function take(i, which) {
      sel = clamp(i, 0, N - 1);
      if (which) edge = which;
      if (!inView()) setView(fitted());
      paint();
    }
    function inView() {
      var a = marks[sel].t0, b = endOf(sel);
      return a >= view[0] - 0.01 && b <= view[1] + 0.01;
    }

    /* ================= dragging ================= */
    function edgeAt(x) {
      // the nearest line within reach, and which of the two it is
      var best = null, bestD = REACH + 1;
      var all = lines.querySelectorAll('.tl-edge');
      for (var i = 0; i < all.length; i++) {
        var r = all[i].getBoundingClientRect();
        var d = Math.abs((r.left + r.right) / 2 - x);
        if (d < bestD) { bestD = d; best = all[i]; }
      }
      return best;
    }
    function onPointerDown(e) {
      if (e.button != null && e.button !== 0) return;
      if (busy) return;
      var line = e.target.closest ? e.target.closest('.tl-edge') : null;
      if (!line && strip.contains(e.target)) line = edgeAt(e.clientX);
      if (line) {
        var i = +line.dataset.i, who = line.dataset.who;
        var at = who === 's' && i === 0 ? marks[0].t0
               : who === 's' ? marks[i + 1].t0 : endOf(i);
        dragging = {i: i, who: who, grip: at - tAt(e.clientX)};
        if (who === 's' && i === 0) take(0, 's');
        else if (who === 's') take(i + 1, 's');
        else take(i, 'e');
        try { strip.setPointerCapture(e.pointerId); } catch (x) {}
        e.preventDefault();
        return;
      }
      var band = e.target.closest ? e.target.closest('.tl-band') : null;
      if (band) { take(+band.dataset.i); return; }
    }
    function onDrag(e) {
      if (!dragging) return;
      var t = clamp(tAt(e.clientX) + dragging.grip, view[0], view[1]);
      if (dragging.who === 's' && dragging.i === 0) setStart(t);
      else if (dragging.who === 's') setBoundary(dragging.i, t, 's');
      else setBoundary(dragging.i, t, 'e');
      paint();
    }
    function onDrop(e) {
      if (!dragging) return;
      var who = dragging.who;
      dragging = null;
      try { strip.releasePointerCapture(e.pointerId); } catch (x) {}
      preview(who === 's' ? 'head' : 'tail');
    }
    strip.addEventListener('pointermove', onDrag);
    strip.addEventListener('pointerup', onDrop);
    strip.addEventListener('pointercancel', onDrop);
    strip.addEventListener('wheel', function (e) {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey || e.shiftKey) { zoomBy(e.deltaY > 0 ? 1.25 : 0.8); return; }
      var by = (view[1] - view[0]) * (e.deltaY > 0 ? 0.12 : -0.12);
      setView([view[0] + by, view[1] + by]);
    }, {passive: false});

    /* ================= splitting ================= */
    function toggleSplit() {
      if (point || sel >= N - 1 || estimating) return;
      if (split[sel]) {
        // joined again: the next starts exactly where this one ends
        var t = Math.min(endOf(sel), marks[sel + 1].t0);
        delete split[sel];
        marks[sel].t1 = t;
        marks[sel + 1].t0 = t;
        say('joined: the next piece starts where this one ends');
      } else {
        split[sel] = true;
        say('split: drag either line on its own, and the silence between them is said by neither');
      }
      paint();
    }

    /* ================= drawing the sound, when asked ================= */
    function paintWave() {
      if (!waveBtn) return;
      var why = str(opts.wave.why);
      waveBtn.disabled = !!why || busy;
      waveBtn.hidden = !!peaks;          // there is already a picture
      waveBtn.title = why || 'play the whole recording once, listening to this tab, and '
        + 'keep the shape of what it hears \u2014 it takes as long as the recording does, '
        + 'and is kept, so it is done once';
    }
    function drawSound() {
      if (!opts.wave || !opts.wave.run || busy) return;
      var why = str(opts.wave.why);
      if (why) { say(why, true); return; }
      busy = true; paintEdit(); paintWave();
      say('sharing this tab\u2026');
      Promise.resolve(opts.wave.run(function (done, note) {
        if (closed) return;
        if (note) say(note);
        else say('listening\u2026 ' + Math.round(Math.max(0, Math.min(1, done)) * 100) + '%');
      })).then(function (w) {
        if (closed) return;
        busy = false;
        if (w && w.peaks && w.peaks.length) {
          say('the sound is drawn');
          peaks = null; peaksView = null; plain = false;
          askPeaks();
        } else say('nothing was recorded', true);
        paintEdit(); paintWave();
      }).catch(function (err) {
        if (closed) return;
        busy = false;
        say((err && err.message) || 'the sound could not be recorded', true);
        paintEdit(); paintWave();
      });
    }

    /* ================= saving ================= */
    function doSave() {
      var changed = moved();
      if (!changed.length || busy) return;
      if (!opts.save) { finish(changed); return; }
      busy = true; paintEdit(); say('saving…');
      Promise.resolve(opts.save(changed)).then(function () {
        if (closed) return;
        busy = false;
        say('saved ' + changed.length + (changed.length === 1 ? ' timing' : ' timings'));
        finish(changed);
      }).catch(function (err) {
        if (closed) return;
        busy = false; paintEdit();
        say((err && err.message) || 'that could not be saved', true);
      });
    }

    /* ================= the page under it hears nothing ================= */
    var EVENTS = ['click', 'dblclick', 'pointerdown', 'mousedown', 'touchstart',
                  'keydown', 'keyup', 'keypress', 'input', 'change', 'contextmenu'];
    function onEvent(e) {
      var t = e.target;
      var inside = t && t.nodeType === 1 && root.contains(t);
      if (e.type.indexOf('key') === 0) {
        e.stopPropagation();
        if (e.type === 'keydown') onKey(e, inside ? t : box);
        return;
      }
      if (!inside) return;
      e.stopPropagation();
      if (e.type === 'click') onClick(e);
      else if (e.type === 'pointerdown') onPointerDown(e);
      else if (e.type === 'input') { if (t === nextIn) paintEdit(); }
      else if (e.type === 'change') {
        if (t === rowS.at) commit(rowS.at, 's');
        else if (t === rowE.at) commit(rowE.at, 'e');
      }
    }
    function onClick(e) {
      var b = e.target.closest('button');
      if (b && !b.disabled && b.getAttribute('aria-disabled') !== 'true') {
        var code = b.dataset.e;
        if (code) {
          var which = code.charAt(0), rest = code.slice(1);
          if (rest === 'h') stamp(which);
          else if (STEP.hasOwnProperty(rest)) nudge(which, STEP[rest]);
          return;
        }
        var x = b.dataset.x;
        if (x === 'cancel') cancel();
        else if (x === 'save') doSave();
        else if (x === 'play') hear();
        else if (x === 'cross') cross();
        else if (x === 'quiet') toSilence();
        else if (x === 'rest') { if (!stopSound()) spreadRest(); }
        else if (x === 'by-text') choose('text');
        else if (x === 'by-sound') choose('sound');
        else if (x === 'split') toggleSplit();
        else if (x === 'in') zoomBy(0.6);
        else if (x === 'out') zoomBy(1.7);
        else if (x === 'fit') setView(fitted());
        else if (x === 'all') showAll();
        else if (x === 'wave') drawSound();
        return;
      }
      var band = e.target.closest('.tl-band');
      if (band) take(+band.dataset.i);
    }
    function focusables() {
      return Array.prototype.filter.call(
        box.querySelectorAll('button, input, [tabindex="0"]'),
        function (n) { return !n.disabled && n.getClientRects().length; });
    }
    function onKey(e, t) {
      var k = e.key;
      if (k === 'Escape') { e.preventDefault(); if (!stopSound()) cancel(); return; }
      if (k === 'Tab') {
        var f = focusables(), i = f.indexOf(document.activeElement);
        if (!f.length) return;
        if (i < 0 || (e.shiftKey && i === 0) || (!e.shiftKey && i === f.length - 1)) {
          e.preventDefault();
          f[e.shiftKey ? f.length - 1 : 0].focus();
        }
        return;
      }
      if (t === rowS.at || t === rowE.at) {
        if (k === 'Enter') { e.preventDefault(); commit(t, t === rowS.at ? 's' : 'e'); }
        return;
      }
      // THE BOX FOR SECONDS IS TYPED IN, so the keys the sheet keeps for
      // itself -- the full stop and the comma that step between pieces, E,
      // S, F, Enter that saves -- are its own while it has the focus.  Enter
      // only takes the number: the estimate moves numbers, and is pressed
      // on purpose, with E or the button.
      if (t === nextIn) {
        if (k === 'Enter') { e.preventDefault(); nextIn.blur(); box.focus({preventScroll: true}); }
        return;
      }
      if (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === 'ArrowDown') {
        e.preventDefault();
        var d = (k === 'ArrowLeft' || k === 'ArrowDown') ? -1 : 1;
        nudge(edge, d * (e.shiftKey ? 0.5 : 0.1));
        return;
      }
      // (not a held one: Enter in the seconds box hands the focus to the sheet, and a
      // key held down on from there must not save it)
      if (k === 'Enter') { e.preventDefault(); if (!e.repeat) doSave(); return; }
      if (k === ' ') { e.preventDefault(); if (playing) stop(); else hear(); return; }
      // THE KEYS PRESSED OVER AND OVER, and so reachable on any keyboard.
      // Stepping to the next piece and bringing the view back onto it are
      // what a hand doing this does all day, between one nudge and the
      // next.  [ and ] say "previous" and "next" to an English keyboard and
      // almost nothing to an Italian or a French one, where both sit behind
      // AltGr; so the comma and the full stop lead -- unshifted everywhere,
      // and already "step back, step on" to anyone who has used a video
      // editor -- with the page keys and the brackets kept beside them for
      // the hands that know those.  Never with a modifier down: Ctrl+F is
      // the browser's own.
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (k === ',' || k === '<' || k === 'PageUp' || k === '[') {
        e.preventDefault(); take(sel - 1); return;
      }
      if (k === '.' || k === '>' || k === 'PageDown' || k === ']') {
        e.preventDefault(); take(sel + 1); return;
      }
      if (k === 'f' || k === 'F') { e.preventDefault(); setView(fitted()); return; }
      if (k === 's' || k === 'S') { e.preventDefault(); toSilence(); return; }
      if (k === 'e' || k === 'E') { e.preventDefault(); spreadRest(); return; }
    }
    function onFocus(e) {
      if (closed || root.contains(e.target)) return;
      box.focus({preventScroll: true});
    }
    function onResize() { paint(); askPeaks(); }

    /* ================= living and dying ================= */
    var ticker = 0;
    function close() {
      if (closed) return;
      closed = true;
      current = null;
      clearTimeout(peaksTimer);
      clearInterval(ticker);
      EVENTS.forEach(function (n) { window.removeEventListener(n, onEvent, true); });
      window.removeEventListener('focus', onFocus, true);
      window.removeEventListener('resize', onResize);
      stop();
      if (root.parentNode) root.parentNode.removeChild(root);
      if (before && before.focus) try { before.focus({preventScroll: true}); } catch (e) {}
    }
    function cancel() { close(); resolve(null); }
    function finish(changed) { close(); resolve(changed); }

    EVENTS.forEach(function (n) { window.addEventListener(n, onEvent, true); });
    window.addEventListener('focus', onFocus, true);
    window.addEventListener('resize', onResize);
    document.body.appendChild(root);
    box.focus({preventScroll: true});

    if (!N) {
      texts.textContent = '';
      texts.appendChild(el('div', 'tl-line tl-none', 'this recording covers no text with times on it yet'));
      edit.hidden = true; wrap.hidden = true; saveBtn.hidden = true;
    } else {
      view = fitted();
      askPeaks();
      paint();
      ticker = setInterval(paintHead, 120);
    }

    return {cancel: cancel};
  }

  /* A RECORDING OF ITS OWN, stopping where it was told to.  `timeupdate`
     fires four times a second at best, which would overrun a 1.5 s preview
     by a sixth of it; so the clock is watched on a frame loop, with an
     interval behind it for a tab nobody is looking at and a one-shot timer
     for the last sixtieth.  The same watch the cut editor keeps.
     Not the page's own player: the reader's <audio> is the reading place,
     and a preview is not reading.  `src` may be changed later. */
  function media(src) {
    var a = new Audio();
    a.preload = 'auto';
    if (src) a.src = src;
    var stopAt = null, raf = 0, tick = 0, fine = 0, dead = false;
    function at() { return a.currentTime || 0; }
    function halt() {
      stopAt = null;
      cancelAnimationFrame(raf); clearInterval(tick); clearTimeout(fine);
      raf = tick = fine = 0;
      try { a.pause(); } catch (e) {}
    }
    function check() {
      if (stopAt == null || a.paused || a.seeking) return;
      var rem = stopAt - at();
      if (rem <= 0.004) { halt(); return; }
      if (rem < 0.06 && !fine) fine = setTimeout(function () { fine = 0; check(); }, rem * 1000);
    }
    function watch() {
      cancelAnimationFrame(raf); clearInterval(tick);
      var frame = function () {
        if (dead) return;
        check();
        if (!a.paused || a.seeking) raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
      tick = setInterval(function () {
        if (dead || (a.paused && !a.seeking)) { clearInterval(tick); tick = 0; return; }
        check();
      }, 25);
    }
    return {
      el: a,
      src: function (u) { if (u && u !== a.getAttribute('src')) { halt(); a.src = u; a.load(); } },
      play: function (from, to) {
        if (dead) return;
        halt();
        stopAt = to;
        var go = function () {
          try { a.currentTime = Math.max(0, from); } catch (e) {}
          var p = a.play();
          if (p && p.catch) p.catch(function () {});
          watch();
        };
        if (a.readyState < 1) a.addEventListener('loadedmetadata', go, {once: true});
        else go();
      },
      stop: halt,
      now: function () { return a.paused && !stopAt ? null : at(); },
      free: function () { dead = true; halt(); try { a.removeAttribute('src'); a.load(); } catch (e) {} }
    };
  }

  window.ParsehTimeline = {open: open, media: media, fmt: fmt, seconds: parse, quiet: middleOfQuiet};
})();
