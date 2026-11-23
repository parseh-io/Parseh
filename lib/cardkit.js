// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the card kit: what the book reader and the video player share to
   make a card somewhere other than Anki, and to give a card its recording.
   Served at /lib/cardkit.js (with /lib/cardkit.css); both pages link it, so a
   change here needs no reader rebuilt.  Plain ES2017, no build step.

     ParsehCards.cut(opts)            the cut editor: a recording's [start, end]
                                      chosen by ear, saved into the clip tray
     ParsehCards.guess(...)           where a word or a chunk probably is inside
                                      its sentence, from its share of the text
     ParsehCards.markdown(card, kind) one `:::exercise flashcard` block
     ParsehCards.decks / newDeck / add     the exercise decks (/exercises/api)
     ParsehCards.preview(md, lang, iframe, deck) the card as a deck will draw it
     ParsehCards.copy / uploadFrame / canRecord
     ParsehCards.canCaptureTab / tabProblem   whether this browser can record
                                      its own tab's sound (a YouTube video's)

   THE CUT EDITOR IS THE BOOK'S TIMING EDITOR, over a picture of the sound.
   The rows are the reader's own (.edit .erow, the same data-e codes, the same
   steps, a nudge of the start playing the first 1.5 s and one of the end the
   last 1.5 s), so a hand that has timed a book already knows it -- except
   that ▶ is ‖ while the clip plays, as the saved clip's button is, and a
   press during a nudge's preview plays the whole clip; above them a
   strip shows the recording around the sentence, with the waveform when the
   server has ffmpeg, the two edges to drag and the playhead to stamp them
   with.  The server cuts the clip (POST cutUrl).  A server without ffmpeg
   answers 409 {record: true}, and the clip is then recorded HERE: the
   recording played silently through Web Audio, captured sample by sample
   with the element's own clock beside each block, trimmed by that clock and
   sent to the tray as a WAV.  A YouTube video (source kind "tab") has no
   file anybody can reach: the editor first records the stretch as this tab
   plays it, and cuts that recording, in the browser, into a WAV for the
   tray. */
(function () {
  'use strict';
  if (window.ParsehCards) return;

  var PREVIEW = 1.5;          // seconds a nudge replays, as in the book
  var LEAD = 0.25;            // what a browser recording plays either side
  var FADE = 0.008;           // the server's own fade (audiofile.extract): no
                              // clip clicks, and every clip fades alike
  var STEP = {'s-1': -1, 's-5': -0.5, 's-': -0.1, 's+': 0.1, 's+5': 0.5, 's+1': 1,
              'e-1': -1, 'e-5': -0.5, 'e-': -0.1, 'e+': 0.1, 'e+5': 0.5, 'e+1': 1};

  /* ---------------------------------------------------------------- helpers */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function button(text, attrs) {
    var b = el('button', null, text);
    b.type = 'button';
    Object.keys(attrs || {}).forEach(function (k) { b.setAttribute(k, attrs[k]); });
    return b;
  }
  // times are kept to the hundredth, as the book keeps SUBS
  function r2(x) { return Math.round(x * 100) / 100; }
  function secs(x) { return (+x).toFixed(2); }
  function str(v) { return v == null ? '' : String(v); }

  // A JSON request that never throws on an HTTP error: the caller reads
  // status and body.  A network failure still rejects.
  function call(url, body, method) {
    var o = {method: method || (body === undefined ? 'GET' : 'POST'), headers: {}};
    if (body !== undefined) {
      o.headers['Content-Type'] = 'application/json';
      o.body = JSON.stringify(body);
    }
    return fetch(url, o).then(function (r) {
      return r.text().then(function (t) {
        var j = null;
        try { j = JSON.parse(t); } catch (e) {}
        if (!j || typeof j !== 'object')
          j = {ok: false, error: (t || r.statusText || 'no answer').slice(0, 300)};
        return {status: r.status, j: j};
      });
    });
  }
  function failure(res, what) {
    return new Error((res.j && res.j.error) || (what + ' failed (' + res.status + ')'));
  }

  /* ---------------------------------------------------------------- guess */
  // [s, e] for the stretch `from..to` of a sentence `units` long that is
  // heard over `context` = [t0, t1]: its share of the text, widened by `pad`
  // either side, kept within 0.3 s of the sentence and at least 0.2 s long.
  function guess(context, units, from, to, pad) {
    if (pad == null) pad = 0.12;
    var t0 = +context[0], t1 = +context[1], span = t1 - t0, s, e;
    if (units > 0) {
      s = t0 + span * from / units - pad;
      e = t0 + span * to / units + pad;
    } else {
      s = t0 - pad;
      e = t1 + pad;
    }
    var lo = Math.max(0, t0 - 0.3), hi = t1 + 0.3;
    s = Math.min(Math.max(s, lo), hi);
    e = Math.min(Math.max(e, lo), hi);
    if (e < s + 0.2) {
      e = Math.min(hi, s + 0.2);
      s = Math.max(lo, Math.min(s, e - 0.2));
    }
    return [s, e];
  }

  /* ---------------------------------------------------------------- markdown */
  // One field line.  A value with a line break is a `key: |` block, every
  // line indented two spaces (mdparser keeps the lines as written); so is a
  // lone `|`, which on one line would open a block of nothing.
  function field(key, value) {
    var v = str(value).replace(/\r\n?/g, '\n');
    if (!v.trim()) return '';
    if (v.indexOf('\n') < 0 && v.trim() !== '|') return key + ': ' + v.trim();
    var lines = v.split('\n').map(function (l) { return l.replace(/\s+$/, ''); });
    while (lines.length && !lines[0].trim()) lines.shift();
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    return key + ': |\n' + lines.map(function (l) { return l ? '  ' + l : ''; }).join('\n');
  }
  // Target-language fields are opaque direction-aware blocks.  The renderer's
  // mark grammar deliberately forbids brackets inside a block, so a value
  // containing its own bracket/brace syntax is left byte-for-byte alone:
  // losing a person's syntax would be worse than declining this automation.
  function marked(v) {
    v = str(v).replace(/\r\n?/g, '\n');
    if (!v.trim() || /\[[^\[\]]*\]\{[^{}]*\}/.test(v) || /[\[\]{}]/.test(v)) return v;
    return v.split('\n').map(function (line) {
      return line.trim() ? '[' + line + ']{tl}' : line;
    }).join('\n');
  }
  // [label](url) when there is a web address to go to; the link syntax
  // allows no bracket in the label and no space or parenthesis in the url
  function sourceValue(src) {
    if (!src) return '';
    if (typeof src === 'string') return src;
    var label = str(src.label).replace(/\s+/g, ' ').trim(), url = str(src.url).trim();
    if (/^https?:\/\//i.test(url)) {
      url = url.replace(/\s/g, '%20').replace(/\(/g, '%28').replace(/\)/g, '%29');
      return '[' + (label || url).replace(/\[/g, '(').replace(/\]/g, ')') + '](' + url + ')';
    }
    return label;
  }
  function markdown(card, kind) {
    card = card || {};
    kind = kind === 'opposites' || kind === 'jolly' ? kind : 'vocab';
    var out = ['card-type: ' + kind];
    var push = function (key, value) { var f = field(key, value); if (f) out.push(f); };
    var target = marked;
    if (kind === 'jolly') {
      var j = {};
      ['front-primary', 'front-secondary', 'back-primary', 'back-secondary'].forEach(function (k) {
        j[k] = str((card.jolly || {})[k]).replace(/\r\n?/g, '\n');
      });
      // a jolly card has no picture or recording field: one given here goes
      // on its side as a line of its own, unless a field already names it
      [card.image, card.audio].forEach(function (m) {
        if (!m || !m.path) return;
        var all = j['front-primary'] + j['front-secondary'] + j['back-primary'] + j['back-secondary'];
        if (all.indexOf(m.path) >= 0) return;
        var k = (m.side === 'back' ? 'back' : 'front') + '-primary';
        j[k] = (j[k].trim() ? j[k].replace(/\s+$/, '') + '\n' : '') + '![](' + m.path + ')';
      });
      Object.keys(j).forEach(function (k) { push(k, j[k]); });
    } else {
      push('target', target(card.fa));
      push('reading', card.kana);
      push('transliteration', card.tr);
      if (kind === 'opposites') {
        push('opposite', target(card.opp));
        push('opposite-reading', card.opp_kana);
        push('opposite-transliteration', card.opp_tr);
      } else {
        push('meaning', card.en);
        push('context', target(card.context));
      }
      push('notes', card.notes);
      push('source', sourceValue(card.source));
      if (card.image && card.image.path)
        push((card.image.side === 'back' ? 'back' : 'front') + '-image', card.image.path);
      if (card.audio && card.audio.path)
        push((card.audio.side === 'back' ? 'back' : 'front') + '-audio', card.audio.path);
      // the sheet's "both" is a deck's both (repeat): two linked cards there
      if (card.dir === 'reverse') push('direction', 'reverse');
      else if (card.dir === 'both' || card.dir === 'both-repeat') push('direction', 'both-repeat');
      else if (card.dir === 'both-random') push('direction', 'both-random');
    }
    return ':::exercise flashcard\n' + out.join('\n') + '\n:::\n';
  }

  /* ---------------------------------------------------------------- decks */
  function decks(lang) {
    return call('/exercises/api/decks?lang=' + encodeURIComponent(lang || '')).then(function (res) {
      if (res.status !== 200 || !res.j.ok) throw failure(res, 'listing the decks');
      return res.j.decks || [];
    });
  }
  function newDeck(name, lang) {
    return call('/exercises/api/decks', {name: name, lang: lang}).then(function (res) {
      if (res.status !== 201 || !res.j.ok) throw failure(res, 'making the deck');
      return res.j.deck;
    });
  }
  // {ok, item, warnings}, or {ok: false, conflict, error}: a duplicate is an
  // answer to show and ask about, not an exception
  function add(deckPath, md, origin, force) {
    var body = {markdown: md};
    if (origin && typeof origin === 'object') body.origin = origin;
    if (force) body.force = true;
    var path = str(deckPath).split('/').map(encodeURIComponent).join('/');
    return call('/exercises/api/decks/' + path + '/items', body).then(function (res) {
      if (res.j.ok && res.status < 300)
        return {ok: true, item: res.j.item, items: res.j.items || (res.j.item ? [res.j.item] : []),
                warnings: res.j.warnings || []};
      return {ok: false, conflict: res.j.conflict || null,
              error: res.j.error || ('adding to the deck failed (' + res.status + ')')};
    }, function (err) {
      return {ok: false, conflict: null, error: 'the server did not answer: ' + err.message};
    });
  }

  /* ---------------------------------------------------------------- small ones */
  function copy(text) {
    if (window.Parseh && typeof Parseh.copy === 'function')
      return Promise.resolve(Parseh.copy(text, true)).then(function (ok) { return ok !== false; });
    if (navigator.clipboard && navigator.clipboard.writeText)
      return navigator.clipboard.writeText(str(text)).then(function () { return true; },
                                                            function () { return false; });
    return Promise.resolve(false);
  }

  // Web Audio, and a recording this page may read: a file of another
  // origin plays, but reaches the graph as silence
  function canRecord(src) {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !AC.prototype || !('createMediaElementSource' in AC.prototype)) return false;
    if (!(AC.prototype.createScriptProcessor || AC.prototype.createJavaScriptNode)) return false;
    if (src == null) return true;
    try { return new URL(src, location.href).origin === location.origin; }
    catch (e) { return false; }
  }

  function uploadFrame(dataUrl, hint, lang) {
    var m = /^data:(image\/[a-z]+);base64,(.*)$/i.exec(str(dataUrl));
    if (!m) return Promise.reject(new Error('a frame is a data: URL of a picture'));
    var bin = atob(m[2]), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var q = new URLSearchParams({kind: 'image', hint: str(hint), lang: str(lang)});
    return fetch('/clips/api/upload?' + q, {method: 'POST', headers: {'Content-Type': m[1]}, body: bytes})
      .then(function (r) { return r.json().then(function (j) { return {status: r.status, j: j}; }); })
      .then(function (res) {
        if (res.status !== 201 || !res.j.ok) throw failure(res, 'keeping the frame');
        return res.j.clip;
      });
  }

  /* ---------------------------------------------------------------- preview */
  // The card as a deck draws it: the studio's own renderer on the server,
  // and the studio's own script in the frame -- bindExercises from
  // /studio/static/app.js turns the card and plays its recordings exactly
  // as a deck's page does.  Should that script not load, a few lines turn
  // the card by themselves.
  function theme() {
    var t = document.documentElement.getAttribute('data-theme');
    if (t === 'dark' || t === 'sepia') return t;
    if (t === 'light') return '';
    return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : '';
  }
  function escAttr(s) { return str(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }
  // what a click on the card is not a turn of: studio app.js's CARD_CONTROLS
  var FLIP = '(function(){var s=document.getElementById("sheet");' +
    'if(typeof bindExercises==="function"){try{bindExercises(s);return;}catch(e){}}' +
    's.addEventListener("click",function(e){var c=e.target.closest(".ex-flashcard");' +
    'if(!c||e.target.closest("audio,video,iframe,a,button,input,select,textarea,label,summary,details,.fnref,.fncloud"))return;' +
    'var f=c.classList.toggle("flipped"),a=c.querySelector(".ex-card-front"),b=c.querySelector(".ex-card-back");' +
    'if(a)a.hidden=f;if(b)b.hidden=!f;c.setAttribute("aria-pressed",f?"true":"false");});})();';
  // `deck`: the card is going into a deck, which does not say that both
  // sides will be asked of a card it asks both sides of
  function preview(md, lang, iframe, deck) {
    return call('/clips/api/preview', {markdown: md, lang: lang, in_deck: !!deck}).then(function (res) {
      if (!res.j.ok) throw failure(res, 'the preview');
      var sb = (iframe.getAttribute('sandbox') || '').split(/\s+/);
      if (sb.indexOf('allow-scripts') < 0 || sb.indexOf('allow-same-origin') < 0)
        iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts');
      var th = theme();
      var doc = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">' +
        '<meta name="viewport" content="width=device-width, initial-scale=1">' +
        '<base target="_blank">' +
        '<link rel="stylesheet" href="/studio/static/app.css">' +
        '<link rel="stylesheet" href="/studio/static/langs.css">' +
        // a card may carry a formula, and this frame is its own document:
        // it links the maths the studio's pages link, and bindExercises
        // (below, in app.js) draws it here as it does everywhere else
        '<link rel="stylesheet" href="/studio/static/mathjax.css">' +
        '<style>body{padding:8px;min-height:0;background:var(--sheet-bg)}' +
        '.sheet{margin:0;max-width:none;padding:6px 8px;box-shadow:none;font-size:16px}</style>' +
        '</head><body data-page="card-preview"' + (th ? ' data-theme="' + th + '"' : '') + '>' +
        '<article id="sheet" class="sheet" data-lang="' + escAttr(lang) + '">' + res.j.html +
        '</article><div id="modal-root"></div>' +
        '<script src="/studio/static/mathjax.js"><\/script>' +
        '<script src="/studio/static/app.js"><\/script><script>' + FLIP + '<\/script></body></html>';
      return new Promise(function (resolve) {
        var done = function () { iframe.removeEventListener('load', done); resolve({ok: true, html: res.j.html}); };
        iframe.addEventListener('load', done);
        iframe.srcdoc = doc;
      });
    });
  }

  /* ---------------------------------------------------------------- recording in the browser */
  // [s, e] of `url`, recorded as it plays: silent, through Web Audio.  Each
  // block of samples is kept with the element's currentTime beside it, and
  // that clock less the samples heard so far -- the media time of the first
  // sample kept -- is one number while the recording plays on, so the clip is
  // cut out of the samples by it.  A reading can come late (the page was
  // busy when the block was handed over) but never early, so the number near
  // a block is the least of its reading and the next few.
  //
  // A RECORDING THAT STOPS TO LOAD breaks that: the graph goes on taking
  // silence while the element waits, and every block after the wait reads
  // another number.  So the stretch is loaded before it is played; a pass
  // that stops anyway (the element says `waiting`, the blocks of the clip do
  // not read one number, or the pass never gets to its end) is thrown away
  // and played again once more of it is here; and when three passes have
  // failed the recording fails, saying so.  A clip is never cut out of a
  // pass that was not played straight through.
  // Resolves with a 16-bit WAV; `onTick(phase, done, total, pass)` says how
  // far it is ('loading' or 'recording').
  var PASSES = 3;             // plays of the stretch before giving up
  var CLOCK = 0.03;           // how far the blocks of one clip may disagree
  var LOADWAIT = 8000;        // ms with nothing more loaded: play what there is
  function recordClip(url, s, e, host, onTick) {
    var abort = null;
    var p = new Promise(function (resolve, reject) {
      var AC = window.AudioContext || window.webkitAudioContext;
      var ac = new AC();
      var media = el('audio', 'pc-rec');
      media.preload = 'auto';
      media.hidden = true;
      media.src = url;
      host.appendChild(media);
      var from = Math.max(0, s - LEAD), until = e + LEAD, rate = ac.sampleRate;
      var graph = null, over = false, pass = null, passes = 0;
      var seekTimer = 0, loadTimer = 0, passTimer = 0;
      var STOPPED = {};
      function tick(phase, done, total) { if (onTick && !over) onTick(phase, done, total, passes); }
      function end(err, blob) {
        if (over) return;
        over = true;
        pass = null;
        clearTimeout(seekTimer); clearTimeout(loadTimer); clearTimeout(passTimer);
        try { media.pause(); } catch (x) {}
        if (graph) {
          graph.proc.onaudioprocess = null;
          try { graph.src.disconnect(); graph.proc.disconnect(); graph.gain.disconnect(); } catch (x) {}
        }
        media.removeAttribute('src');
        try { media.load(); } catch (x) {}
        media.remove();
        try { Promise.resolve(ac.close()).catch(function () {}); } catch (x) {}
        if (err) reject(err); else resolve(blob);
      }
      abort = function () { end(new Error('cancelled')); };

      // a pass: to the start of the stretch, loaded, played through it
      function again() {
        clearTimeout(passTimer);
        pass = null;
        try { media.pause(); } catch (x) {}
        if (over) return;
        if (++passes > PASSES) {
          end(new Error('the recording kept stopping to load, so no clip was made of it: try again'));
          return;
        }
        var ps = pass = {chunks: [], marks: [], frames: 0, lastT: -1, on: false, moved: false, tail: 0};
        seekTo(from, function () {
          if (pass === ps) loaded(ps, function () { if (pass === ps) play(ps); });
        });
      }
      function seekTo(t, then) {
        var done = false;
        var go = function () {
          if (done || over) return;
          done = true;
          clearTimeout(seekTimer);
          media.removeEventListener('seeked', go);
          then();
        };
        media.addEventListener('seeked', go);
        seekTimer = setTimeout(go, 4000);    // a seek to where it already is
        media.currentTime = t;
      }
      // how far the recording is loaded on from `t`
      function loadedTo(t) {
        var b = media.buffered;
        for (var i = 0; i < b.length; i++)
          if (b.start(i) <= t + 0.05 && b.end(i) >= t) return b.end(i);
        return t;
      }
      function loaded(ps, then) {
        var best = -1, since = Date.now();
        (function look() {
          if (pass !== ps || over) return;
          var need = isFinite(media.duration) ? Math.min(until, media.duration) : until;
          var have = loadedTo(from);
          if (have >= need - 0.01) { then(); return; }
          if (have > best + 0.001) { best = have; since = Date.now(); }
          else if (Date.now() - since >= LOADWAIT) { then(); return; }
          tick('loading', Math.max(0, have - from), until - from);
          loadTimer = setTimeout(look, 200);
        })();
      }
      function play(ps) {
        connect();
        ps.on = true;
        Promise.resolve(ac.resume()).then(function () {
          if (pass === ps) return media.play();
        }).catch(function (err) {
          if (pass === ps) end(new Error('the browser would not play the recording: ' + (err && err.message)));
        });
        passTimer = setTimeout(function () { if (pass === ps) again(); }, (until - from) * 1000 + 8000);
      }
      function connect() {
        if (graph) return;
        var srcNode = ac.createMediaElementSource(media);
        var proc = (ac.createScriptProcessor || ac.createJavaScriptNode).call(ac, 4096, 2, 1);
        var gain = ac.createGain();
        gain.gain.value = 0;                 // heard by nobody
        srcNode.connect(proc); proc.connect(gain); gain.connect(ac.destination);
        graph = {src: srcNode, proc: proc, gain: gain};
        proc.onaudioprocess = hear;
      }
      function hear(ev) {
        var ps = pass;
        if (over || !ps || !ps.on) return;
        var t = media.currentTime, ib = ev.inputBuffer, len = ib.length, ch = ib.numberOfChannels;
        var mono = new Float32Array(len);
        for (var c = 0; c < ch; c++) {
          var d = ib.getChannelData(c);
          for (var i = 0; i < len; i++) mono[i] += d[i] / ch;
        }
        ps.chunks.push(mono);
        ps.frames += len;
        // live: heard while the element played on; still: heard while it did
        // not, after it had begun (a wait, a pause) and before the file ended
        var live = !media.paused && !media.seeking && ps.lastT >= 0 && t > ps.lastT;
        if (live) ps.moved = true;
        ps.marks.push({off: t - ps.frames / rate, frames: ps.frames, len: len, live: live,
                       still: !live && ps.moved && !media.ended});
        ps.lastT = t;
        tick('recording', Math.max(0, Math.min(t, e) - s), e - s);
        // at the end of the file the last samples are still on their way
        if (t >= until || (media.ended && ++ps.tail > 2)) done(ps);
      }
      function done(ps) {
        if (pass !== ps) return;
        ps.on = false;
        clearTimeout(passTimer);
        try { media.pause(); } catch (x) {}
        var blob;
        try { blob = cutOut(ps); } catch (x) {
          if (x === STOPPED) again(); else end(x);
          return;
        }
        end(null, blob);
      }
      function cutOut(ps) {
        var marks = ps.marks;
        // the number near a live block: the least of its reading and the next
        // few, as far as the next block that is not live
        marks.forEach(function (m, i) {
          if (!m.live) return;
          m.lo = m.off;
          for (var j = i + 1; j < Math.min(marks.length, i + 6) && marks[j].live; j++)
            m.lo = Math.min(m.lo, marks[j].off);
        });
        var live = marks.filter(function (m) { return m.live; });
        if (!live.length) throw new Error('the browser heard nothing of the recording');
        var off = median(live.map(function (m) { return m.lo; }));
        var i0 = Math.round((s - off) * rate), i1 = Math.round((e - off) * rate);
        // Of the blocks holding the clip none is the silence of a wait, and
        // every other reads the same number; and all of the clip was heard.
        var clip = marks.filter(function (m) { return m.frames > i0 && m.frames - m.len < i1; });
        var los = clip.filter(function (m) { return m.live; }).map(function (m) { return m.lo; });
        if (!los.length || i0 < 0 || i1 > ps.frames + rate * 0.01 ||
            clip.some(function (m) { return m.still; }) ||
            Math.max.apply(null, los) - Math.min.apply(null, los) > CLOCK) throw STOPPED;
        off = median(los);
        i0 = Math.max(0, Math.round((s - off) * rate));
        i1 = Math.min(ps.frames, Math.round((e - off) * rate));
        if (i1 - i0 < rate * 0.05) throw new Error('the browser recorded too little of the clip');
        var out = new Float32Array(i1 - i0), at = 0, k = 0;
        ps.chunks.forEach(function (c) {
          var lo = Math.max(i0, at), hi = Math.min(i1, at + c.length);
          if (hi > lo) { out.set(c.subarray(lo - at, hi - at), k); k += hi - lo; }
          at += c.length;
        });
        return fadedWav(out, rate);
      }

      media.addEventListener('error', function () { end(new Error('the recording could not be loaded')); });
      // stopped to load in the middle of a pass: that pass is no good
      media.addEventListener('waiting', function () {
        var ps = pass;
        if (ps && ps.on && ps.moved) again();
      });
      if (media.readyState >= 1) again(); else media.addEventListener('loadedmetadata', again, {once: true});
    });
    p.abort = function () { if (abort) abort(); };
    return p;
  }
  function wav(samples, rate) {
    var n = samples.length, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    var put = function (o, s) { for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    put(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); put(8, 'WAVE');
    put(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); put(36, 'data'); v.setUint32(40, n * 2, true);
    for (var i = 0; i < n; i++) {
      var x = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    }
    return new Blob([buf], {type: 'audio/wav'});
  }
  // A clip the browser cut, as the WAV the tray is sent: FADE at each end,
  // the server's own, so no clip clicks and every one fades alike whoever
  // cut it.  The samples are the caller's own copy, faded in place.
  function fadedWav(samples, rate) {
    var n = Math.min(Math.round(FADE * rate), samples.length >> 2);
    for (var i = 0; i < n; i++) { samples[i] *= i / n; samples[samples.length - 1 - i] *= i / n; }
    return wav(samples, rate);
  }
  function median(xs) {
    xs = xs.slice().sort(function (a, b) { return a - b; });
    return xs[xs.length >> 1];
  }

  /* ---------------------------------------------------------------- recording this tab */
  // A YOUTUBE VIDEO'S SOUND is out of every script's reach: it plays in a
  // frame of YouTube's own, and no file of it is anywhere this page can read.
  // What Chrome and Edge do allow, once the person says so, is a recording of
  // the tab itself, sound and all.  The page owns that share (its frame
  // capture takes pictures off the same one) and hands the kit a way to it,
  // with the player; the kit plays the stretch through once, sound on, keeps
  // what the tab gave out meanwhile, and that is the recording the editor
  // cuts.  Nothing of it is ever played to the speakers.
  //
  // WHERE IN THE VIDEO EACH SAMPLE IS.  The samples carry the page's clock:
  // AudioData.timestamp is performance.now()'s (measured, not promised: it
  // comes 20 ms before the data, and where it does not the arrival less those
  // 20 ms is used); an AudioWorklet, where there is no track processor, gives
  // only its blocks' arrival, some 28 ms late.  The player says where the
  // video is whenever its frame reports -- read the moment a message comes,
  // and every 16 ms besides -- so while it plays, video time = clock + c, and
  // c is the middle of those readings, the first 150 ms of playing left out.
  // A pass during which the player stopped to load, or whose readings
  // disagree by more than 30 ms, is played again, once.
  var TAB_LEAD = 0.5;         // played before the stretch and after it
  var REACH_MAX = 60;         // how far "record again" may be sent either way
  var TAB_TAIL = 150;         // ms recorded on after the player stops
  var TAB_SKIP = 150;         // ms of playing whose readings are not trusted
  var TAB_SPREAD = 0.03;      // how far the readings may disagree
  var TAB_QUIET = 0.01;       // a stretch no louder than this was not heard
  var TAB_LAG = 20;           // ms from an AudioData's timestamp to its arrival
  var TAB_BLOCK_LAG = 28;     // ms from a worklet block's sound to its arrival

  // '' when this browser can record the sound of its own tab, else why not,
  // in words a person can act on
  function tabProblem() {
    if (!window.isSecureContext)
      return 'recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge';
    var ua = navigator.userAgentData, md = navigator.mediaDevices;
    var chromium = !!(ua && ua.brands && ua.brands.some(function (b) { return /chromium/i.test(b.brand); }));
    if (!chromium || ua.mobile || !md || !md.getDisplayMedia)
      return 'only Chrome and Edge, on a computer, can record the sound of a tab';
    if (!window.MediaStreamTrackProcessor && !(window.AudioContext && window.AudioWorkletNode))
      return 'this browser cannot read the sound of a shared tab';
    return '';
  }
  function canCaptureTab() { return !tabProblem(); }

  // what went wrong asking for the tab, said as what to do about it
  function tabError(err) {
    var name = err && err.name, msg = err && err.message;
    if (name === 'NotAllowedError')
      return new Error('the tab was not shared, so nothing was recorded: press “record” and, ' +
                       'when Chrome asks, press “Allow”');
    if (name === 'InvalidStateError')
      return new Error('Chrome shares a tab only straight after a click: press “record” again');
    if (name === 'NotFoundError' || name === 'NotReadableError' || name === 'AbortError')
      return new Error('Chrome could not share the tab (' + (msg || name) + '): press “record” again');
    return err instanceof Error ? err : new Error(String(err));
  }
  var NO_TAB_SOUND = 'the tab was shared without its sound: press “record” and, when Chrome asks, ' +
                     'leave “Also allow tab audio” turned on';
  var TAB_ENDED = 'the tab stopped being shared while it recorded: press “record” again, and Chrome asks once more';

  // The samples of an audio track, kept from begin() to end(): end() gives
  // {rate, clock: performance.now() of the first sample, data: mono}.
  function tapProcessor(track) {
    var clone = track.clone();
    var reader = new MediaStreamTrackProcessor({track: clone}).readable.getReader();
    var chunks = [], keep = false, shut = false;
    (function pump() {
      reader.read().then(function (r) {
        if (r.done) return;
        var ad = r.value, got = performance.now();
        try {
          if (keep) {
            var n = ad.numberOfFrames, nc = ad.numberOfChannels;
            var mono = new Float32Array(n), part = new Float32Array(n);
            for (var c = 0; c < nc; c++) {
              ad.copyTo(part, {planeIndex: c, format: 'f32-planar'});
              for (var i = 0; i < n; i++) mono[i] += part[i] / nc;
            }
            chunks.push({stamp: ad.timestamp / 1000, got: got, rate: ad.sampleRate, data: mono});
          }
        } catch (x) {
        } finally {
          ad.close();
        }
        if (!shut) pump();
      }, function () {});
    })();
    return {
      path: 'processor',
      begin: function () { chunks = []; keep = true; },
      end: function () {
        keep = false;
        if (!chunks.length) return null;
        var rate = chunks[0].rate, first = chunks[0].stamp;
        // the timestamps are the page's clock when they come that far ahead of
        // the data; one that strays from the samples before it is a gap
        var lag = median(chunks.map(function (c) { return c.got - c.stamp; }));
        var stamped = lag > -5 && lag < 250, slack = Math.round(rate * 0.002);
        var pos = [], at = 0, len = 0;
        chunks.forEach(function (c) {
          var p = at;
          if (stamped) {
            var q = Math.round((c.stamp - first) / 1000 * rate);
            if (Math.abs(q - at) > slack) p = Math.max(0, q);
          }
          pos.push(p);
          at = p + c.data.length;
          len = Math.max(len, at);
        });
        var data = new Float32Array(len);
        chunks.forEach(function (c, k) { data.set(c.data, pos[k]); });
        var clock = stamped ? first
          : median(chunks.map(function (c, k) { return c.got - pos[k] / rate * 1000; })) - TAB_LAG;
        return {rate: rate, clock: clock, data: data};
      },
      close: function () {
        shut = true;
        keep = false;
        try { reader.cancel().catch(function () {}); } catch (x) {}
        clone.stop();
      }
    };
  }
  // the same, where there is no track processor: an AudioWorklet with no
  // output at all (it is run all the same), so nothing reaches the speakers
  var WORKLET = 'registerProcessor("parseh-tab",class extends AudioWorkletProcessor{' +
    'constructor(){super();this.on=false;this.port.onmessage=e=>{this.on=!!e.data;};}' +
    'process(ins){var c=ins[0];if(this.on&&c&&c.length){var n=c[0].length,m=new Float32Array(n);' +
    'for(var k=0;k<c.length;k++)for(var j=0;j<n;j++)m[j]+=c[k][j]/c.length;' +
    'this.port.postMessage({f:currentFrame,d:m},[m.buffer]);}return true;}});';
  function tapWorklet(track) {
    var ac = new (window.AudioContext || window.webkitAudioContext)({latencyHint: 'interactive'});
    var url = URL.createObjectURL(new Blob([WORKLET], {type: 'text/javascript'}));
    var clone = track.clone(), node = null, blocks = [], keep = false;
    return ac.audioWorklet.addModule(url).then(function () {
      URL.revokeObjectURL(url);
      node = new AudioWorkletNode(ac, 'parseh-tab', {numberOfInputs: 1, numberOfOutputs: 0});
      node.port.onmessage = function (e) {
        if (keep) blocks.push({f: e.data.f, got: performance.now(), data: e.data.d});
      };
      ac.createMediaStreamSource(new MediaStream([clone])).connect(node);
      return ac.resume();
    }).then(function () {
      var rate = ac.sampleRate;
      return {
        path: 'worklet',
        begin: function () { blocks = []; keep = true; node.port.postMessage(1); },
        end: function () {
          keep = false;
          node.port.postMessage(0);
          if (!blocks.length) return null;
          var f0 = blocks[0].f, last = blocks[blocks.length - 1];
          var data = new Float32Array(last.f + last.data.length - f0);
          blocks.forEach(function (b) { data.set(b.data, b.f - f0); });
          var clock = median(blocks.map(function (b) { return b.got - (b.f - f0) / rate * 1000; })) - TAB_BLOCK_LAG;
          return {rate: rate, clock: clock, data: data};
        },
        close: function () {
          keep = false;
          clone.stop();
          try { Promise.resolve(ac.close()).catch(function () {}); } catch (x) {}
        }
      };
    }, function (err) {
      URL.revokeObjectURL(url);
      clone.stop();
      try { ac.close(); } catch (x) {}
      throw err;
    });
  }

  // [from, to] of the video, as this tab plays it: {rate, t0 (the video's time
  // at the first sample), data, from, to (what was heard playing), peak,
  // spread, passes, path}.  `onTick(done, total, pass, t)` while it plays.
  // The player is left as it was found: its place, sound, volume and speed.
  function recordTab(src, from, to, onTick) {
    var yt = src.player, cancelled = false;
    var STOP = new Error('cancelled');
    function wait(ms) {
      return new Promise(function (r) { setTimeout(r, ms); })
        .then(function () { if (cancelled) throw STOP; });
    }
    var p = (async function () {
      var stream;
      try { stream = await src.stream({audio: true}); } catch (err) { throw tabError(err); }
      if (cancelled) throw STOP;
      var track = stream && stream.getAudioTracks().filter(function (t) { return t.readyState === 'live'; })[0];
      if (!track) throw new Error(NO_TAB_SOUND);
      var ended = false, onEnded = function () { ended = true; };
      track.addEventListener('ended', onEnded);
      var was = {muted: yt.isMuted(), volume: yt.getVolume(), rate: yt.getPlaybackRate(),
                 t: yt.getCurrentTime(), playing: yt.getPlayerState() === 1};
      // the page's own sounds would be in the recording too
      var hushed = [];
      Array.prototype.forEach.call(document.querySelectorAll('audio, video'), function (m) {
        hushed.push([m, m.muted]);
        m.muted = true;
        if (!m.paused) m.pause();
      });
      var tap = null;
      try {
        tap = window.MediaStreamTrackProcessor ? tapProcessor(track) : await tapWorklet(track);
        if (cancelled) throw STOP;
        var best = null;
        for (var pass = 1; pass <= 2; pass++) {
          var r = await playThrough(pass);
          if (r.take) {
            if (best && best.spread <= r.take.spread) break;
            best = r.take;
            if (r.take.spread <= TAB_SPREAD) break;
          } else if (pass === 2 && !best) {
            throw new Error(r.why);
          }
        }
        best.passes = pass > 2 ? 2 : pass;
        best.path = tap.path;
        return best;
      } finally {
        track.removeEventListener('ended', onEnded);
        if (tap) tap.close();
        try {
          yt.pauseVideo();
          yt.setPlaybackRate(was.rate);
          yt.setVolume(was.volume);
          if (was.muted) yt.mute(); else yt.unMute();
          yt.seekTo(was.t, true);
          if (was.playing) yt.playVideo();
        } catch (x) {}
        hushed.forEach(function (h) { h[0].muted = h[1]; });
      }

      // one play of the stretch: {take} or {why} it is no good
      async function playThrough(pass) {
        var dur = +yt.getDuration() || 0;
        var a = Math.max(0, from - TAB_LEAD), b = dur > 0 ? Math.min(dur, to + TAB_LEAD) : to + TAB_LEAD;
        yt.pauseVideo();
        yt.unMute();
        yt.setVolume(100);
        yt.setPlaybackRate(1);
        yt.seekTo(a, true);
        var asked = performance.now();
        for (;;) {
          await wait(50);
          if (ended) throw new Error(TAB_ENDED);
          // a video not started yet plays when it is sent somewhere: it is
          // stopped there, and sent back to where the pass begins
          var st = yt.getPlayerState();
          if (st === 1) {
            yt.pauseVideo();
            yt.seekTo(a, true);
          } else if (Math.abs(yt.getCurrentTime() - a) < 0.25 && st !== 3) {
            break;
          }
          if (performance.now() - asked > 15000)
            throw new Error('the video would not go to ' + secs(a) + ' s: record again');
        }
        await wait(300);
        tap.begin();
        var marks = [], last = null, began = 0, stalled = false;
        var read = function () {
          var now = performance.now(), t = +yt.getCurrentTime(), st = yt.getPlayerState();
          if (last && last.t === t && last.st === st) return;
          last = {t: t, st: st};
          if (st === 1) {
            if (!began) began = now;
            marks.push([now, t]);
          } else if (began && st === 3) {
            stalled = true;
          }
        };
        window.addEventListener('message', read);
        // where the video stands as it is told to play, and when it is told
        var p0 = +yt.getCurrentTime(), sent = performance.now();
        try {
          yt.playVideo();
          var limit = performance.now() + (b - a) * 1000 + 15000;
          for (;;) {
            read();
            if (ended) throw new Error(TAB_ENDED);
            if (stalled || (began && (last.t >= b || last.st === 0))) break;
            if (performance.now() > limit) { stalled = true; break; }
            if (onTick) onTick(Math.max(0, Math.min(yt.getCurrentTime(), b) - a), b - a, pass, yt.getCurrentTime());
            await wait(16);
          }
        } finally {
          window.removeEventListener('message', read);
        }
        // a stretch reaching the end of the video ends with it
        var over = began && last.st === 0;
        yt.pauseVideo();
        await wait(TAB_TAIL);
        var got = tap.end();
        if (stalled) return {why: 'the video kept stopping to load while it was recorded: record again'};
        if (!got || !got.data.length) return {why: 'Chrome gave no sound for the tab: record again'};
        var trusted = marks.filter(function (m) { return m[0] - began >= TAB_SKIP && m[1] <= b; });
        if (trusted.length < 5) return {why: 'the video did not say where it was while it played: record again'};
        var offs = trusted.map(function (m) { return m[1] - m[0] / 1000; }).sort(function (x, y) { return x - y; });
        var c = offs[offs.length >> 1];
        // the readings' own disagreement, a late one or two left out
        var spread = offs[Math.floor(offs.length * 0.9)] - offs[Math.floor(offs.length * 0.1)];
        var t0 = got.clock / 1000 + c, rate = got.rate, data = got.data;
        // It played from p0.  YouTube says PLAYING late -- some 0.18 s into
        // the playing, driven, from the start of a video -- so its first
        // reading in that state is not where the sound began, unless it is
        // further on than the time since the video was told to play allows
        // (it skipped).  Nothing heard before that moment is the video's.
        var m0 = marks[0], from0 = m0[1] - p0 <= (m0[0] - sent) / 1000 + 0.05 ? Math.min(p0, m0[1]) : m0[1];
        var heard = [Math.max(from0, t0, sent / 1000 + c),
                     Math.min(over ? (dur || b) : marks[marks.length - 1][1], t0 + data.length / rate)];
        if (heard[0] > from + 0.01 || heard[1] < to - 0.01)
          return {why: 'the video did not play all of the stretch: record again'};
        var peak = 0;
        for (var i = Math.max(0, Math.floor((from - t0) * rate)),
                 n = Math.min(data.length, Math.ceil((to - t0) * rate)); i < n; i++) {
          var x = data[i] < 0 ? -data[i] : data[i];
          if (x > peak) peak = x;
        }
        if (peak < TAB_QUIET)
          throw new Error('no sound was captured — is the video muted? Turn its sound on and record again');
        return {take: {rate: rate, t0: t0, data: data, from: heard[0], to: heard[1], peak: peak, spread: spread}};
      }
    })();
    p.abort = function () { cancelled = true; };
    return p;
  }
  // the loudness of [a, b] of a recording in n slices, 0..1 of the loudest
  function takePeaks(take, a, b, n) {
    var out = [], top = 0, d = take.data, rate = take.rate;
    for (var i = 0; i < n; i++) {
      var lo = Math.max(0, Math.floor((a + (b - a) * i / n - take.t0) * rate));
      var hi = Math.min(d.length, Math.ceil((a + (b - a) * (i + 1) / n - take.t0) * rate));
      var m = 0;
      for (var j = lo; j < hi; j++) {
        var x = d[j] < 0 ? -d[j] : d[j];
        if (x > m) m = x;
      }
      out.push(m);
      if (m > top) top = m;
    }
    return out.map(function (v) { return top ? Math.round(v / top * 1000) / 1000 : 0; });
  }
  // [s, e] of a recording, as a WAV faded as the server fades
  function cutTake(take, s, e) {
    var i0 = Math.max(0, Math.round((s - take.t0) * take.rate));
    var i1 = Math.min(take.data.length, Math.round((e - take.t0) * take.rate));
    return fadedWav(take.data.slice(i0, Math.max(i0, i1)), take.rate);
  }

  /* ---------------------------------------------------------------- the cut editor */
  var current = null;

  function cut(opts) {
    if (current) current.cancel();
    return new Promise(function (resolve) { current = openCut(opts || {}, resolve); });
  }

  function openCut(opts, resolve) {
    var src = opts.source || {};
    // a YouTube video: no file to cut, but this tab's recording of it
    var tab = src.kind === 'tab' && !!src.player && typeof src.stream === 'function';
    var ctx = opts.context && opts.context.length === 2 ? [+opts.context[0], +opts.context[1]] : null;
    var g = opts.guess && opts.guess.length === 2 ? [+opts.guess[0], +opts.guess[1]] : ctx;
    if (!g || !(g[1] > g[0])) g = [0, 1];
    if (!ctx) ctx = g.slice();
    var g0 = [r2(Math.max(0, g[0])), r2(g[1])];
    if (!(g0[1] > g0[0])) g0[1] = r2(g0[0] + 0.2);
    var sel = {s: g0[0], e: g0[1]};
    var dur = NaN, active = 's', dragging = null, stopAt = null, raf = 0, tick = 0, fine = 0;
    // whole: what plays is the clip, from ▶ (not a preview, not Space's run
    // from the playhead); asked: which play() is the latest, a stop included
    var whole = false, asked = 0;
    // a tab's recording: `recording` the one made (its samples, the video's
    // time at the first, what of the video it heard), `taking` one under way;
    // the hidden player plays it, `base` seconds into the video
    var recording = null, taking = null, takeUrl = '', base = 0, recNow = null;
    // the stretch the recording in hand was asked for: the strip shows all
    // of it, even where that is more than the sentence and its second
    var reached = null;
    if (tab) {
      try { dur = +src.player.getDuration() || NaN; } catch (x) {}
    }
    var view = fitted();
    var peaks = null, peaksView = null, plain = false, peaksAsk = 0, peaksTimer = 0;
    // the clip saved last: the cursors it was cut for, and (a tab's) the
    // recording it was cut from
    var saved = null, savedSpan = null, savedTake = null, made = [], busy = false, closed = false, rec = null;
    var before = document.activeElement;

    /* ---- the markup ---- */
    var root = el('div', 'pc-root');
    var box = el('div', 'pc-cut');
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Cut the audio');
    box.setAttribute('dir', 'ltr');
    box.setAttribute('lang', 'en');
    box.tabIndex = -1;
    root.appendChild(box);

    var head = el('div', 'pc-head');
    head.appendChild(el('span', 'pc-title', 'cut the audio'));
    var what = el('span', 'pc-what');
    var said = str(opts.text).replace(/\s+/g, ' ').trim();
    if (said) {
      var q = el('bdi', null, said.length > 90 ? said.slice(0, 90) + '…' : said);
      q.setAttribute('dir', 'auto');
      what.appendChild(q);
    }
    head.appendChild(what);
    var xBtn = button('✕', {'data-x': 'cancel', 'class': 'pc-x', 'title': 'cancel (Esc)', 'aria-label': 'Cancel'});
    head.appendChild(xBtn);
    box.appendChild(head);

    // A TAB'S RECORDING FIRST: what is about to happen, said before Chrome
    // asks, and the button that starts it (a share is granted only straight
    // after a click).  The strip and the rows come once there is a recording.
    var takeBox = el('div', 'pc-take');
    var takeText = el('p', 'pc-take-text');
    var recBtn = button('● record', {'data-x': 'record', 'class': 'pc-btn pc-record'});
    var takeBar = el('span', 'pc-bar pc-take-bar'), takeFill = el('span', 'pc-fill');
    takeBar.appendChild(takeFill);
    takeBar.hidden = true;
    [takeText, recBtn, takeBar].forEach(function (n) { takeBox.appendChild(n); });
    takeBox.hidden = !tab;
    box.appendChild(takeBox);

    var strip = el('div', 'pc-strip');
    strip.title = 'click to move the playhead · drag an edge to move it';
    var canvas = el('canvas', 'pc-wave');
    var band = el('div', 'pc-ctx');
    var selBox = el('div', 'pc-sel');
    var ph = el('div', 'pc-playhead');
    var edge0 = el('div', 'pc-edge pc-edge0'), edge1 = el('div', 'pc-edge pc-edge1');
    [[edge0, 'start'], [edge1, 'end']].forEach(function (x) {
      x[0].tabIndex = 0;
      x[0].setAttribute('role', 'slider');
      x[0].setAttribute('aria-label', x[1] + ' of the clip');
    });
    [canvas, band, selBox, ph, edge0, edge1].forEach(function (n) { strip.appendChild(n); });
    box.appendChild(strip);
    var scale = el('div', 'pc-scale');
    var v0Lab = el('span'), phLab = el('span', 'pc-at'), v1Lab = el('span');
    scale.appendChild(v0Lab); scale.appendChild(phLab); scale.appendChild(v1Lab);
    box.appendChild(scale);

    // the book's .edit, as tex2html writes it for a subparagraph
    var edit = el('div', 'edit pc-rows');
    edit.setAttribute('dir', 'ltr');
    var r1 = el('div', 'erow');
    r1.appendChild(el('span', 'who', str(opts.label) || 'clip'));
    var playBtn = button('▶', {'data-e': 'p', 'title': 'play the clip', 'aria-label': 'Play the clip'});
    r1.appendChild(playBtn);
    var durEl = el('span', 'dur');
    r1.appendChild(durEl);
    edit.appendChild(r1);
    function row(p, name) {
      var r = el('div', 'erow pc-row-' + p);
      r.appendChild(el('span', 'lbl', name));
      r.appendChild(button('−1', {'data-e': p + '-1'}));
      r.appendChild(button('−.5', {'data-e': p + '-5'}));
      r.appendChild(button('−.1', {'data-e': p + '-'}));
      var inp = el('input', p === 's' ? 'e0' : 'e1');
      inp.type = 'number';
      inp.step = '0.05';
      inp.min = '0';
      inp.setAttribute('aria-label', name + ', seconds');
      r.appendChild(inp);
      r.appendChild(button('+.1', {'data-e': p + '+'}));
      r.appendChild(button('+.5', {'data-e': p + '+5'}));
      r.appendChild(button('+1', {'data-e': p + '+1'}));
      r.appendChild(button('◉', {'data-e': p + 'h', 'title': 'set to the playhead'}));
      edit.appendChild(r);
      return {row: r, input: inp};
    }
    var rs = row('s', 'start'), re = row('e', 'end');
    re.row.appendChild(button('undo', {'data-e': 'rv', 'title': 'undo'}));
    var e0 = rs.input, e1 = re.input;
    // How much further the next recording goes, for a caption that cuts the
    // sentence across: seconds moved from where the stretch would otherwise
    // start and end, negative earlier and positive later.  Only a tab's
    // editor records at all, so the row stands with "record again".
    var reachRow = el('div', 'erow pc-row-r');
    reachRow.appendChild(el('span', 'lbl', 'reach'));
    reachRow.title = 'How much further \u25cf record again goes: seconds moved from where ' +
                     'the stretch would otherwise start and end \u2014 negative earlier, ' +
                     'positive later. For a caption that cuts the sentence across.';
    function reachIn(name, n) {
      reachRow.appendChild(el('span', 'pc-rlab', name));
      var inp = el('input', 'pc-r pc-r' + n);
      inp.type = 'number';
      inp.step = '0.5';
      inp.min = String(-REACH_MAX);
      inp.max = String(REACH_MAX);
      inp.value = '0';
      inp.setAttribute('aria-label', 'record again: move the ' + name + ', seconds');
      reachRow.appendChild(inp);
      reachRow.appendChild(el('span', 'pc-rlab', 's'));
      return inp;
    }
    var reach0 = reachIn('start', 0), reach1 = reachIn('end', 1);
    edit.appendChild(reachRow);
    box.appendChild(edit);

    // The clip as the tray keeps it, played by a button of the editor's own
    // and not by the element's controls: a key pressed on those never reaches
    // the page, so Escape and Enter would do nothing there.
    var savedBox = el('div', 'pc-saved');
    savedBox.hidden = true;
    var hearBtn = button('▶', {'data-x': 'hear', 'class': 'pc-hear', 'title': 'play the saved clip',
                              'aria-label': 'Play the saved clip'});
    var bar = el('span', 'pc-bar'), fill = el('span', 'pc-fill');
    bar.appendChild(fill);
    var savedName = el('span', 'pc-name');
    var savedAudio = el('audio', 'pc-saved-audio');
    savedAudio.preload = 'auto';
    savedAudio.hidden = true;
    [hearBtn, bar, savedName, savedAudio].forEach(function (n) { savedBox.appendChild(n); });
    box.appendChild(savedBox);

    var foot = el('div', 'pc-foot');
    var againBtn = button('● record again', {'data-x': 'record', 'class': 'pc-btn pc-again',
                                            'title': 'play the stretch around the edges again and record it anew'});
    var saveBtn = button('save clip', {'data-x': 'save', 'class': 'pc-btn pc-save'});
    var useBtn = button('use this clip', {'data-x': 'use', 'class': 'pc-btn pc-use',
                                          'title': 'put this clip on the card (Enter); cut first when the cursors moved'});
    var cancelBtn = button('cancel', {'data-x': 'cancel', 'class': 'pc-btn pc-cancel'});
    var stat = el('span', 'pc-stat');
    stat.setAttribute('role', 'status');
    [againBtn, saveBtn, useBtn, cancelBtn, stat].forEach(function (n) { foot.appendChild(n); });
    box.appendChild(foot);
    var hint = el('div', 'pc-hint',
      'Drag an edge, or click the strip and stamp an edge with ◉. ' +
      'Arrow keys move the focused edge by 0.1 s (Shift: 0.5 s); Enter uses the clip, Esc cancels. ' +
      'reach sends \u25cf record again further back or further on, for a caption that cuts the ' +
      'sentence across.');
    box.appendChild(hint);
    // what a tab's editor shows before it has a recording, and after
    function paintTake() {
      if (!tab) { againBtn.hidden = reachRow.hidden = true; return; }
      var have = !!recording;
      takeBox.hidden = have;
      [strip, scale, edit, hint, saveBtn, useBtn, againBtn].forEach(function (n) { n.hidden = !have; });
      if (!have) savedBox.hidden = true;
    }

    // the recording, played by an element of our own, never the page's
    var player = el('audio', 'pc-play');
    player.preload = 'auto';
    player.hidden = true;
    root.appendChild(player);
    if (src.src && !tab) player.src = str(src.src);
    // the video's time, of the element's: a tab's recording starts `base` in
    function at() { return (player.currentTime || 0) + base; }
    function seekTo(t) {
      try { player.currentTime = Math.max(0, t - base); } catch (x) {}
    }

    /* ---- drawing ---- */
    function xOf(t) { return (t - view[0]) / (view[1] - view[0]) * 100; }
    // inside the border, where the edges and the waveform are placed
    function tAt(clientX) {
      var r = strip.getBoundingClientRect();
      var f = Math.min(1, Math.max(0, (clientX - r.left - strip.clientLeft) / (strip.clientWidth || 1)));
      return view[0] + f * (view[1] - view[0]);
    }
    function paintPlayhead() {
      // while a tab records, where the video is
      var t = recNow != null ? recNow : at();
      ph.style.left = xOf(t) + '%';
      ph.hidden = t < view[0] || t > view[1];
      phLab.textContent = '▸ ' + secs(t) + ' s';
    }
    function paint() {
      e0.value = secs(sel.s);
      e1.value = secs(sel.e);
      durEl.textContent = secs(sel.e - sel.s) + 's';
      selBox.style.left = xOf(sel.s) + '%';
      selBox.style.width = (xOf(sel.e) - xOf(sel.s)) + '%';
      band.style.left = xOf(ctx[0]) + '%';
      band.style.width = (xOf(ctx[1]) - xOf(ctx[0])) + '%';
      edge0.style.left = xOf(sel.s) + '%';
      edge1.style.left = xOf(sel.e) + '%';
      edge0.setAttribute('aria-valuenow', secs(sel.s));
      edge0.setAttribute('aria-valuetext', secs(sel.s) + ' seconds');
      edge1.setAttribute('aria-valuenow', secs(sel.e));
      edge1.setAttribute('aria-valuetext', secs(sel.e) + ' seconds');
      v0Lab.textContent = secs(view[0]) + ' s';
      v1Lab.textContent = secs(view[1]) + ' s';
      // a clip saved for other cursors than these, or from a recording made
      // before this one, is shown dimmed, and says so: "use" cuts again first
      if (saved) {
        var moved = !(savedSpan[0] === sel.s && savedSpan[1] === sel.e), older = savedTake !== recording;
        savedBox.classList.toggle('pc-stale', moved || older);
        if (!busy && !stat.classList.contains('pc-bad'))
          say(older ? 'the clip saved is of the recording before this one: “use this clip” cuts it again, from this one'
                    : moved ? 'the edges moved after saving: “use this clip” cuts the clip again'
                    : 'saved to the clip tray');
      }
      paintPlayhead();
      draw();
    }
    function draw() {
      var w = strip.clientWidth, h = strip.clientHeight, dpr = window.devicePixelRatio || 1;
      if (!w || !h) return;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      var c = canvas.getContext('2d');
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, w, h);
      // plain: no waveform will come; drawn: it is here
      strip.classList.toggle('pc-plain', plain);
      strip.classList.toggle('pc-drawn', !!peaks);
      if (!peaks) return;
      var cs = getComputedStyle(strip);
      var off = cs.getPropertyValue('--pc-wave').trim() || '#a2949a';
      var on = cs.getPropertyValue('--pc-wave-on').trim() || '#be3455';
      var n = peaks.length, span = peaksView[1] - peaksView[0], mid = h / 2;
      for (var i = 0; i < n; i++) {
        var t0 = peaksView[0] + span * i / n, t1 = peaksView[0] + span * (i + 1) / n;
        if (t1 < view[0] || t0 > view[1]) continue;
        var x0 = xOf(t0) * w / 100, x1 = xOf(t1) * w / 100;
        var a = Math.max(1, peaks[i] * (h / 2 - 4));
        var tm = (t0 + t1) / 2;
        c.fillStyle = tm >= sel.s && tm <= sel.e ? on : off;
        c.fillRect(x0, mid - a, Math.max(1, x1 - x0 - (x1 - x0 > 2 ? 0.5 : 0)), a * 2);
      }
    }
    function askPeaks() {
      if (tab) {
        // a tab's waveform is its recording's, worked out here, of what it heard
        clearTimeout(peaksTimer);
        peaks = null;
        if (recording) {
          var a = Math.max(view[0], recording.from), b = Math.min(view[1], recording.to);
          if (b > a) {
            peaksView = [a, b];
            peaks = takePeaks(recording, a, b,
              Math.max(50, Math.min(4000, Math.round((strip.clientWidth || 600) * (b - a) / (view[1] - view[0])))));
          }
        }
        plain = !peaks;
        draw();
        return;
      }
      if (plain || !src.peaksUrl) { plain = true; draw(); return; }
      clearTimeout(peaksTimer);
      peaksTimer = setTimeout(function () {
        var n = ++peaksAsk, want = [r2(view[0]), r2(view[1])];
        var body = {start: want[0], end: want[1],
                    buckets: Math.max(50, Math.min(4000, Math.round(strip.clientWidth || 600)))};
        who(body);
        call(src.peaksUrl, body).then(function (res) {
          if (closed || n !== peaksAsk) return;
          if (res.status === 200 && res.j.ok && res.j.peaks) {
            peaks = res.j.peaks;
            peaksView = [+res.j.start, +res.j.end];
          } else {
            plain = true;          // no ffmpeg (409), or no waveform to be had
          }
          draw();
        }, function () { if (!closed) { plain = true; draw(); } });
      }, peaks ? 250 : 0);
    }
    // The view is the sentence and a second either side, or a second past an
    // edge taken beyond that -- and back to the sentence when the edge comes
    // back, as undo brings it.  It holds still while an edge is dragged: the
    // pointer is read against the strip as it was when pressed, so a drag
    // goes at most to the end of the strip, and the strip is fitted again when
    // the edge is let go.  A new view asks for its waveform.
    function core() {
      var v = [Math.max(0, Math.min(ctx[0], sel.s) - 1), Math.max(ctx[1], sel.e) + 1];
      if (isFinite(dur)) v[1] = Math.min(v[1], Math.max(dur, sel.e));
      return v;
    }
    function fitted() {
      var v = core();
      // A recording asked to reach further holds more than the sentence and
      // its second, and the strip has to show all of it: the cursors are
      // dragged inside the strip, so audio the strip does not show is audio
      // that was recorded and cannot be used.
      if (reached) {
        v[0] = Math.min(v[0], reached[0]);
        v[1] = Math.max(v[1], reached[1]);
      }
      return v;
    }
    // WHAT "record again" GOES FOR.  A caption is not always where the
    // sentence is -- YouTube's transcript cuts one across, and the words
    // wanted start before the caption does or run on after it.  The reach
    // row moves each edge of the stretch by however many seconds is typed
    // there: negative earlier, positive later.  It is measured from the
    // stretch itself (core) and not from what the last recording reached,
    // so pressing record again twice with the same numbers goes to the same
    // place rather than creeping outward.
    function reachBy(inp) {
      var v = parseFloat(inp.value);
      if (!isFinite(v)) return 0;
      return Math.max(-REACH_MAX, Math.min(REACH_MAX, v));
    }
    function nextSpan() {
      var v = core(), a = Math.max(0, v[0] + reachBy(reach0)), b = v[1] + reachBy(reach1);
      if (isFinite(dur) && dur > 0) b = Math.min(b, dur);
      if (!(b > a + 0.2)) b = a + 0.2;         // never an empty stretch
      return [a, b];
    }
    function fitView() {
      if (dragging) return;
      var v = fitted();
      if (v[0] !== view[0] || v[1] !== view[1]) {
        view = v;
        if (!plain || tab) askPeaks();
      }
    }
    function who(body) {
      if (src.kind === 'film') body.video = src.video;
      else body.narration = src.narration || '';
      return body;
    }

    /* ---- playing ---- */
    // `clip`: this is the clip itself, played from ▶
    function play(from, to, clip) {
      if (!savedAudio.paused) savedAudio.pause();
      if (tab) {
        // a tab's recording holds what it heard, and no more
        if (!recording || taking) return;
        from = Math.max(from, recording.from);
        to = Math.min(to, recording.to);
        if (!(to > from)) { say('that is outside the recording: record again to hear it', true); return; }
      }
      stopAt = to;
      whole = !!clip;
      var n = ++asked;
      var go = function () {
        if (n !== asked || closed) return;     // stopped, or another play, while it loaded
        seekTo(from);
        var pr = player.play();
        if (pr && pr.catch) pr.catch(function () {});
        watch();
        paintPlay();
      };
      if (player.readyState >= 1) go();
      else player.addEventListener('loadedmetadata', go, {once: true});
    }
    function stop() {
      stopAt = null;
      whole = false;
      asked++;
      if (!player.paused) player.pause();
      paintPlay();
    }
    // ▶ plays the clip from its start and is ‖ while it does, as the saved
    // clip's button; what else plays (a nudge's preview, Space from the
    // playhead) leaves it ▶, and a press plays the clip instead
    function playingClip() { return whole && !player.paused; }
    function paintPlay() {
      var on = playingClip();
      // ‖ is narrower than ▶: held to ▶'s width, the readout beside it holds still
      if (on && playBtn.textContent !== '‖') playBtn.style.minWidth = playBtn.getBoundingClientRect().width + 'px';
      else if (!on) playBtn.style.minWidth = '';
      playBtn.textContent = on ? '‖' : '▶';
      playBtn.title = on ? 'stop the clip' : 'play the clip';
      playBtn.setAttribute('aria-label', on ? 'Stop the clip' : 'Play the clip');
    }
    // A preview ends where it was asked to, not up to a quarter of a second
    // later at the next timeupdate: a frame loop while it plays, and a timer
    // for the last stretch.
    function check() {
      if (stopAt == null || player.paused || player.seeking) return;
      var rem = stopAt - at();
      if (rem <= 0.004) { stop(); paintPlayhead(); return; }
      if (rem < 0.06 && !fine) fine = setTimeout(function () { fine = 0; check(); }, rem * 1000);
    }
    function watch() {
      cancelAnimationFrame(raf);
      clearInterval(tick);
      var frame = function () {
        if (closed) return;
        check();
        paintPlayhead();
        if (!player.paused || player.seeking) raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
      tick = setInterval(function () {                 // a frame loop sleeps in a hidden tab
        if (closed || (player.paused && !player.seeking)) { clearInterval(tick); return; }
        check();
      }, 25);
    }
    function playHead() { play(sel.s, Math.min(sel.e, sel.s + PREVIEW)); }
    function playTail() { play(Math.max(sel.s, sel.e - PREVIEW), sel.e); }
    // the saved clip: ▶ and ‖ as the reader's own, and how far it has played
    function hear() {
      if (!savedAudio.paused) { savedAudio.pause(); return; }
      stop();
      if (savedAudio.ended) savedAudio.currentTime = 0;
      var pr = savedAudio.play();
      if (pr && pr.catch) pr.catch(function () {});
    }
    var hearRaf = 0;
    function paintHear() {
      cancelAnimationFrame(hearRaf);
      var d = savedAudio.duration, on = !savedAudio.paused;
      fill.style.width = (isFinite(d) && d > 0 ? Math.min(100, savedAudio.currentTime / d * 100) : 0) + '%';
      hearBtn.textContent = on ? '‖' : '▶';
      hearBtn.title = on ? 'pause the saved clip' : 'play the saved clip';
      hearBtn.setAttribute('aria-label', on ? 'Pause the saved clip' : 'Play the saved clip');
      if (on && !closed) hearRaf = requestAnimationFrame(paintHear);
    }
    ['play', 'pause', 'ended', 'seeked', 'emptied'].forEach(function (t) {
      savedAudio.addEventListener(t, paintHear);
    });
    player.addEventListener('play', watch);
    player.addEventListener('seeked', paintPlayhead);
    player.addEventListener('pause', paintPlayhead);
    ['play', 'pause', 'emptied'].forEach(function (t) { player.addEventListener(t, paintPlay); });
    player.addEventListener('loadedmetadata', function () {
      // a tab's recording is not the video: its length is the player's
      if (!tab) dur = player.duration;
      if (isFinite(dur) && sel.e > dur) set(sel.s, dur);
      else fitView();
      if (stopAt == null && player.paused) seekTo(sel.s);
      paint();
    });
    player.addEventListener('error', function () {
      if (!closed && src.src && !tab) say('the recording could not be loaded', true);
    });

    /* ---- the cursors ---- */
    // false when the two would not make a clip (an end not after its start)
    function set(s, e, preview) {
      s = r2(Math.max(0, +s));
      e = r2(+e);
      if (isFinite(dur) && e > dur) e = r2(dur);
      if (!isFinite(s) || !isFinite(e) || !(e > s)) { paint(); return false; }
      sel.s = s;
      sel.e = e;
      if (!busy && stat.classList.contains('pc-bad')) say('');   // what went wrong was the last move
      fitView();
      paint();
      if (preview === 'head') playHead();
      else if (preview === 'tail') playTail();
      return true;
    }
    function nudge(which, d) {
      active = which;
      if (which === 's') set(sel.s + d, sel.e, 'head');
      else set(sel.s, sel.e + d, 'tail');
    }
    function act(a) {
      if (a === 'p') {
        if (playingClip()) stop(); else play(sel.s, sel.e, true);
        return;
      }
      if (STEP[a] !== undefined) { nudge(a[0], STEP[a]); return; }
      if (a === 'sh' || a === 'eh') {
        if (tab && !recording) return;
        var t = at();
        active = a[0];
        var ok = a === 'sh' ? set(t, sel.e, 'head') : set(sel.s, t, 'tail');
        if (!ok) say(a === 'sh' ? 'the playhead is not before the end' : 'the playhead is not after the start', true);
        return;
      }
      if (a === 'rv') { stop(); set(g0[0], g0[1]); }
    }
    function commit(inp) {
      var v = inp.value.trim();
      if (v === '' || !isFinite(+v)) { paint(); return; }
      var s = inp === e0 ? +v : sel.s, e = inp === e1 ? +v : sel.e;
      if (r2(s) === sel.s && r2(e) === sel.e) { paint(); return; }
      active = inp === e0 ? 's' : 'e';
      if (!set(s, e, inp === e1 ? 'tail' : 'head')) say('the end must come after the start', true);
    }

    /* ---- saving ---- */
    function say(text, bad) {
      stat.textContent = text || '';
      stat.classList.toggle('pc-bad', !!bad);
    }
    // Busy, the two buttons say so and do nothing -- but are not disabled: a
    // disabled button loses the focus, to the page's body, and the hand on
    // the keyboard its place.
    function setBusy(on) {
      busy = on;
      [saveBtn, useBtn, recBtn, againBtn].forEach(function (b) { b.setAttribute('aria-disabled', on ? 'true' : 'false'); });
      box.classList.toggle('pc-busy', on);
      if (!on && !closed && !box.contains(document.activeElement))
        (tab && !recording ? recBtn : saveBtn).focus({preventScroll: true});
    }
    function forget(name) {
      if (name) fetch('/clips/api/' + encodeURIComponent(name), {method: 'DELETE'}).catch(function () {});
    }
    function got(clip, span) {
      // a clip cut before this one, and never used, goes out of the tray
      if (saved && saved.name !== clip.name) {
        forget(saved.name);
        made = made.filter(function (n) { return n !== saved.name; });
      }
      if (made.indexOf(clip.name) < 0) made.push(clip.name);
      saved = clip;
      savedSpan = span;
      savedTake = recording;
      savedBox.hidden = false;
      savedAudio.src = clip.url;
      savedName.textContent = clip.name + (clip.duration != null ? ' · ' + secs(clip.duration) + ' s' : '');
      say('saved to the clip tray');
      paint();
      stop();
      var pr = savedAudio.play();
      if (pr && pr.catch) pr.catch(function () {});
      return clip;
    }
    function save() {
      if (busy) return Promise.resolve(null);
      var span = [sel.s, sel.e];
      if (saved && savedTake === recording && savedSpan[0] === span[0] && savedSpan[1] === span[1])
        return Promise.resolve(saved);
      if (tab) return saveTake(span);
      if (!src.cutUrl) { say('there is nothing here to cut from', true); return Promise.resolve(null); }
      stop();
      setBusy(true);
      say('cutting ' + secs(span[0]) + '–' + secs(span[1]) + ' s…');
      var meta = {start: span[0], end: span[1], lang: str(opts.lang), hint: str(opts.hint),
                  label: str(opts.label), text: str(opts.text)};
      who(meta);
      return call(src.cutUrl, meta).then(function (res) {
        if (closed) { if (res.j.clip) forget(res.j.clip.name); return null; }
        if (res.status === 201 && res.j.ok && res.j.clip) return got(res.j.clip, span);
        if (res.status === 409 && res.j.record) return recordHere(span);
        throw failure(res, 'cutting the clip');
      }).catch(function (err) {
        if (!closed) say(err.message, true);
        return null;
      }).then(function (clip) {
        if (!closed) setBusy(false);
        return clip;
      });
    }
    function recordHere(span) {
      if (!canRecord(src.src))
        throw new Error('this machine has no ffmpeg to cut with, and this browser cannot record the clip itself');
      say('recording in the browser (the server has no ffmpeg), silently…');
      rec = recordClip(src.src, span[0], span[1], root, function (phase, t, total, pass) {
        if (closed) return;
        var again = pass > 1 ? ' (it stopped to load: again, ' + pass + ' of ' + PASSES + ')' : '';
        say((phase === 'loading' ? 'loading the recording to record it: '
                                 : 'recording in the browser, silently: ') +
            secs(t) + ' of ' + secs(total) + ' s' + again);
      });
      return rec.then(function (blob) {
        rec = null;
        if (closed) return null;
        say('keeping the recording…');
        var source = {kind: src.kind === 'film' ? 'film' : 'book', start: span[0], end: span[1]};
        if (src.kind === 'film') source.video = str(src.video); else source.narration = str(src.narration);
        return upload(blob, source);
      }, function (err) {
        rec = null;
        throw err;
      }).then(function (res) {
        if (!res) return null;
        if (closed) { if (res.j.clip) forget(res.j.clip.name); return null; }
        if (res.status !== 201 || !res.j.ok) throw failure(res, 'keeping the recording');
        return got(res.j.clip, span);
      });
    }
    // a WAV made here, into the tray
    function upload(blob, source) {
      var q = new URLSearchParams({kind: 'audio', hint: str(opts.hint) || str(opts.label), lang: str(opts.lang),
                                   label: str(opts.label), text: str(opts.text), source: JSON.stringify(source)});
      return fetch('/clips/api/upload?' + q, {method: 'POST', headers: {'Content-Type': 'audio/wav'}, body: blob})
        .then(function (r) { return r.json().then(function (j) { return {status: r.status, j: j}; }); });
    }

    /* ---- a tab's recording ---- */
    // The stretch the strip shows -- the sentence and a second either side,
    // or a second past an edge beyond it -- played through and recorded
    // here; one made before stays until this one is made.
    function record() {
      if (!tab || busy || taking || closed) return;
      var span = nextSpan();
      stop();
      if (!savedAudio.paused) savedAudio.pause();
      setBusy(true);
      takeFill.style.width = '0%';
      takeBar.hidden = false;
      var what = secs(span[0]) + '–' + secs(span[1]) + ' s';
      say('recording ' + what + ' of the video…');
      var mine = taking = recordTab(src, span[0], span[1], function (done, total, pass, t) {
        if (closed || taking !== mine) return;
        takeFill.style.width = (total > 0 ? Math.min(100, done / total * 100) : 0) + '%';
        recNow = t;
        if (recording) paintPlayhead();
        say('recording ' + what + ' of the video: ' + secs(done) + ' of ' + secs(total) + ' s' +
            (pass > 1 ? ' (once more: the first time did not hold together)' : ''));
      });
      mine.then(function (tk) {
        if (closed || taking !== mine) return;
        taking = null;
        recNow = null;
        useTake(tk, span);
        say('recorded ' + secs(tk.from) + '–' + secs(tk.to) + ' s: move the edges by ear, then save the clip');
      }, function (err) {
        if (closed || taking !== mine) return;
        taking = null;
        recNow = null;
        say(err.message, true);
      }).then(function () {
        if (closed || taking) return;
        takeBar.hidden = true;
        setBusy(false);
        paint();
        if (!box.contains(document.activeElement) || document.activeElement === recBtn ||
            document.activeElement === againBtn)
          (recording ? againBtn : recBtn).focus({preventScroll: true});
      });
    }
    function useTake(tk, span) {
      stop();
      recording = tk;
      reached = span || null;
      base = tk.t0;
      if (takeUrl) URL.revokeObjectURL(takeUrl);
      takeUrl = URL.createObjectURL(wav(tk.data, tk.rate));
      player.src = takeUrl;
      paintTake();
      fitView();
      askPeaks();
      paint();
    }
    // [s, e] of the recording, as the tray keeps it
    function saveTake(span) {
      if (!recording) { say('record the stretch first', true); return Promise.resolve(null); }
      if (span[0] < recording.from - 0.005 || span[1] > recording.to + 0.005) {
        say('the recording holds ' + secs(recording.from) + '–' + secs(recording.to) +
            ' s: record again to take in the edges', true);
        return Promise.resolve(null);
      }
      stop();
      setBusy(true);
      say('keeping ' + secs(span[0]) + '–' + secs(span[1]) + ' s…');
      var source = {kind: 'youtube', video: str(src.video), start: span[0], end: span[1]};
      if (src.video)
        source.url = 'https://www.youtube.com/watch?v=' + encodeURIComponent(src.video) + '&t=' + Math.floor(span[0]) + 's';
      return upload(cutTake(recording, span[0], span[1]), source).then(function (res) {
        if (closed) { if (res.j.clip) forget(res.j.clip.name); return null; }
        if (res.status !== 201 || !res.j.ok) throw failure(res, 'keeping the clip');
        return got(res.j.clip, span);
      }).catch(function (err) {
        if (!closed) say(err.message, true);
        return null;
      }).then(function (clip) {
        if (!closed) setBusy(false);
        return clip;
      });
    }

    function use() {
      if (busy) return;
      if (tab && !recording) { record(); return; }
      save().then(function (clip) { if (clip && !closed) finish(clip); });
    }

    /* ---- opening and closing ---- */
    function finish(clip) {
      if (closed) return;
      if (clip) made = made.filter(function (n) { return n !== clip.name; });
      close();
      resolve(clip || null);
    }
    function cancel() {
      if (closed) return;
      if (rec) rec.abort();
      if (taking) taking.abort();
      // what was cut in here and not used is not a clip anybody wanted
      made.forEach(forget);
      made = [];
      finish(null);
    }
    function close() {
      closed = true;
      if (current === api) current = null;
      cancelAnimationFrame(raf);
      cancelAnimationFrame(hearRaf);
      clearInterval(tick);
      clearTimeout(fine);
      clearTimeout(peaksTimer);
      EVENTS.forEach(function (t) { window.removeEventListener(t, onEvent, true); });
      document.removeEventListener('play', onPagePlay, true);
      document.removeEventListener('focusin', onFocus, true);
      window.removeEventListener('resize', onResize);
      [player, savedAudio].forEach(function (a) {
        try { a.pause(); a.removeAttribute('src'); a.load(); } catch (x) {}
      });
      if (taking) taking.abort();
      taking = null;
      if (takeUrl) URL.revokeObjectURL(takeUrl);
      root.remove();
      if (before && before.focus && document.contains(before)) {
        try { before.focus({preventScroll: true}); } catch (x) {}
      }
    }

    // THE PAGE UNDER THE EDITOR HEARS NOTHING OF IT.  Every click, key and
    // press inside is taken in the capture phase at the window, before any
    // listener of the reader's or the player's -- the reader's own timing
    // editor answers every `.edit button` on the page from the document --
    // and handled here.  (Not pointermove or pointerup: the strip hears those
    // of a dragged edge itself.)  Nothing in the editor that takes the focus
    // swallows a key before it gets here: the saved clip has no controls.
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
      else if (e.type === 'change' && (t === e0 || t === e1)) commit(t);
    }
    function onClick(e) {
      var b = e.target.closest('button');
      if (!b || b.disabled) return;
      if (b.dataset.e) act(b.dataset.e);
      else if (b.dataset.x === 'save') save();
      else if (b.dataset.x === 'use') use();
      else if (b.dataset.x === 'hear') hear();
      else if (b.dataset.x === 'record') record();
      else if (b.dataset.x === 'cancel') cancel();
    }
    function edgeOf(t) {
      if (t === reach0 || t === reach1) return null;
      if (t === edge0 || rs.row.contains(t)) return 's';
      if (t === edge1 || re.row.contains(t)) return 'e';
      return null;
    }
    function focusables() {
      return Array.prototype.filter.call(
        box.querySelectorAll('button, input, [tabindex="0"]'),
        function (n) { return !n.disabled && n.getClientRects().length; });
    }
    function onKey(e, t) {
      var k = e.key, tag = t.tagName;
      if (k === 'Escape') { e.preventDefault(); cancel(); return; }
      // the reach boxes are not an edge: the arrows step the number the way
      // any number box steps, and Enter goes and records what they ask for
      if (t === reach0 || t === reach1) {
        if (k === 'Enter') { e.preventDefault(); record(); return; }
        if (/^Arrow(Left|Right|Up|Down)$/.test(k)) return;
      }
      if (k === 'Tab') {
        var f = focusables(), i = f.indexOf(document.activeElement);
        if (!f.length) return;
        if (i < 0 || (e.shiftKey && i === 0) || (!e.shiftKey && i === f.length - 1)) {
          e.preventDefault();
          f[e.shiftKey ? f.length - 1 : 0].focus();
        }
        return;
      }
      if (k === 'Enter') {
        if (tag === 'INPUT') { e.preventDefault(); commit(t); return; }
        if (tag === 'BUTTON') return;          // the button's own click
        e.preventDefault();
        use();                                 // a tab's first: record
        return;
      }
      if (/^Arrow(Left|Right|Up|Down)$/.test(k)) {
        if (tag === 'INPUT' && (k === 'ArrowLeft' || k === 'ArrowRight')) return;   // the caret
        e.preventDefault();
        if (tag === 'INPUT' && t.value.trim() !== secs(t === e0 ? sel.s : sel.e)) commit(t);
        var d = (k === 'ArrowRight' || k === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 0.5 : 0.1);
        nudge(edgeOf(t) || active, d);
        return;
      }
      if (k === ' ' && tag !== 'BUTTON' && tag !== 'INPUT' && !(tab && !recording)) {
        // from the playhead to the end of the strip
        e.preventDefault();
        if (!player.paused) stop(); else play(at(), view[1]);
      }
    }
    // Which edge a press on an edge takes hold of.  Close together the two
    // hit areas overlap, and the one drawn last would take every press: so a
    // press on a knob takes that knob's edge (the start's is at the top, the
    // end's at the bottom), and anywhere else the nearer line's.  With the
    // two lines on one another, the way the pointer then goes decides, knob
    // or not: left the start, right the end ('?' until it has gone) -- so the
    // clip always widens under the hand.
    var KNOB = 15, REACH = 12;
    function edgeAt(x, y, target) {
      var r = strip.getBoundingClientRect(), w = strip.clientWidth || 1;
      var x0 = r.left + strip.clientLeft + xOf(sel.s) * w / 100;
      var x1 = r.left + strip.clientLeft + xOf(sel.e) * w / 100;
      var by0 = Math.abs(x - x0) <= REACH, by1 = Math.abs(x - x1) <= REACH;
      if (by0 !== by1) return by0 ? 's' : 'e';
      if (!by0) return target === edge0 ? 's' : 'e';
      if (x1 - x0 < 4) return '?';
      var b = edge0.getBoundingClientRect();
      if (y < b.top + KNOB) return 's';
      if (y > b.bottom - KNOB) return 'e';
      return x - x0 <= x1 - x ? 's' : 'e';
    }
    function onPointerDown(e) {
      if (e.button || !strip.contains(e.target)) return;
      e.preventDefault();
      var edge = e.target.closest('.pc-edge');
      if (edge) {
        stop();
        // the time under the pointer less the edge's own, kept through the
        // drag: a press beside the line does not make the edge jump to it
        dragging = {which: edgeAt(e.clientX, e.clientY, edge), x: e.clientX, at: tAt(e.clientX)};
        take(dragging);
        try { strip.setPointerCapture(e.pointerId); } catch (x) {}
        return;
      }
      var t = r2(tAt(e.clientX)), wasPlaying = !player.paused;
      if (wasPlaying && stopAt != null && t >= stopAt) {
        // past where it was to stop: it plays on to the end of the strip,
        // and is no longer the clip
        stopAt = view[1];
        whole = false;
        paintPlay();
      }
      seekTo(t);
      paintPlayhead();
      box.focus({preventScroll: true});
    }
    function take(d) {
      if (d.which === '?') { edge0.focus({preventScroll: true}); return; }
      d.grip = d.at - (d.which === 's' ? sel.s : sel.e);
      active = d.which;
      (d.which === 's' ? edge0 : edge1).focus({preventScroll: true});
    }
    function onDrag(e) {
      var d = dragging;
      if (!d) return;
      if (d.which === '?') {
        if (Math.abs(e.clientX - d.x) < 3) return;
        d.which = e.clientX < d.x ? 's' : 'e';
        take(d);
      }
      var t = Math.min(view[1], Math.max(view[0], tAt(e.clientX) - d.grip));
      if (d.which === 's') set(Math.min(t, sel.e - 0.05), sel.e);
      else set(sel.s, Math.max(t, sel.s + 0.05));
    }
    function onDrop(e) {
      var d = dragging;
      if (!d) return;
      dragging = null;
      fitView();
      paint();
      if (e.type !== 'pointerup' || d.which === '?') return;
      if (d.which === 's') playHead(); else playTail();
    }
    strip.addEventListener('pointermove', onDrag);
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (t) {
      strip.addEventListener(t, onDrop);
    });
    // whatever on the page starts playing while the editor is open is
    // stopped: one recording at a time, and it is this one
    function onPagePlay(e) {
      var m = e.target;
      if (m && m.pause && !root.contains(m)) m.pause();
    }
    function onFocus(e) {
      if (!root.contains(e.target)) box.focus({preventScroll: true});
    }
    function onResize() { paint(); if (!plain) askPeaks(); }
    // the page under the veil does not scroll, and neither does a dialog
    // that fits
    function onWheel(e) {
      if (!box.contains(e.target) || box.scrollHeight <= box.clientHeight) e.preventDefault();
    }
    root.addEventListener('wheel', onWheel, {passive: false});
    root.addEventListener('touchmove', onWheel, {passive: false});

    EVENTS.forEach(function (t) { window.addEventListener(t, onEvent, true); });
    document.addEventListener('play', onPagePlay, true);
    document.addEventListener('focusin', onFocus, true);
    window.addEventListener('resize', onResize);
    savedAudio.addEventListener('play', function () { stop(); });
    Array.prototype.forEach.call(document.querySelectorAll('audio, video'), function (m) {
      if (!root.contains(m) && !m.paused) m.pause();
    });

    document.body.appendChild(root);
    if (tab) {
      // Before the tab is shared, what Chrome is about to ask, and a button
      // to start; once it is, the recording starts as the editor opens.
      var span = fitted(), live = null;
      try { live = typeof src.stream.live === 'function' && src.stream.live({audio: true}); } catch (x) {}
      var stretch = 'the stretch ' + secs(span[0]) + '–' + secs(span[1]) + ' s plays once, sound on, while ';
      takeText.textContent = live
        ? 'The sound is cut from a recording of this tab: ' + stretch + 'it is recorded.'
        : 'A YouTube video’s sound is cut from a recording of this tab: ' + stretch + 'it is recorded. ' +
          'Chrome asks first: press “Allow”, and leave “Also allow tab audio” turned on.';
      paintTake();
      paint();
      recBtn.focus({preventScroll: true});
      if (live) record();
    } else {
      againBtn.hidden = true;
      paint();
      askPeaks();
      edge0.focus({preventScroll: true});
    }

    var api = {cancel: cancel};
    return api;
  }

  window.ParsehCards = {
    cut: cut, guess: guess, markdown: markdown,
    decks: decks, newDeck: newDeck, add: add,
    copy: copy, preview: preview, uploadFrame: uploadFrame,
    canRecord: canRecord,
    canCaptureTab: canCaptureTab, tabProblem: tabProblem
  };
})();
