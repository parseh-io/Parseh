// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — ONE capture of the sound of this tab, shared by everything that wants it.

   A YouTube video's sound reaches no script: its frame belongs to another
   site.  The only way to hear it is to record the TAB while the video plays,
   which Chrome and Edge allow (getDisplayMedia, asked for once, with the
   tab's sound).  This file is that recording and nothing else -- no page, no
   button, no fetch, no toast -- so the two pages that need it stand on the same
   code instead of each keeping a recorder of its own:

     . the video's player draws the SHAPE of the sound (the timings sheet's
       "draw the sound", youtube/lib/player.js), and
     . the add page turns the same recording into a transcript, by sending the
       sound to the computer Parseh runs on.

     ParsehTabCapture.capability(opts)  -> {ok, why}     why not, in words
     ParsehTabCapture.problem(opts)     -> '' | why      the same, as a string
     ParsehTabCapture.share(want)       -> Promise<MediaStream>   THE getDisplayMedia call
     ParsehTabCapture.share.live(want)  -> MediaStream | null     the share as it stands
     ParsehTabCapture.release()         let the share go (stop its tracks)
     ParsehTabCapture.busy()            -> bool: a recording is under way in this page
     ParsehTabCapture.record(opts)      -> {promise, cancel(), state}
     ParsehTabCapture.embed(el, id, on) -> Promise<YT.Player>  a YouTube player to record

   record(opts):
     player      a YT.Player: getDuration getCurrentTime seekTo playVideo pauseVideo
                 (and get/setPlaybackRate, isMuted/getVolume/mute/unMute/setVolume,
                 and getPlayerState, whose 0 -- YouTube's "ended" -- is how the end
                 of a video is told from a video that has stopped)
     wave        true (default): the SHAPE, 20 numbers a second (consumer 1, below)
     pcm         false (default) | true | {chunkSeconds: 5}: the SOUND, 16 kHz mono
                 16-bit, in chunks in order (consumer 2, below)
     keepShare   true (default): the share stays live for whatever asks next (the
                 frame capture, the cut editor: one question from Chrome for all);
                 false: its tracks are stopped at the end
     unmute      false (default) | true: play unmuted at full volume, put back after
                 (a muted video records silence)
     dropVideo   false (default) | true, with keepShare false: stop the share's
                 picture as soon as it is granted, so that the browser does not
                 compose the tab for an hour for nothing; the sound goes on (driven:
                 tests/youtube_capture.mjs, ten seconds of it -- an hour is not)
     wakeLock    keep the screen awake while it records (default: with pcm)
     guardUnload ask before the page is left while it records (default: with pcm)
     adGuard     stop when YouTube plays an ad (default: with pcm)
     onStart(duration)               playing has begun (once)
     onProgress(seconds, duration)   about once a second of the video
     onPeaks(peaks, rate)            once, at the end: the shape, normalised
     onChunk(pcm, offset, signal)    an Int16Array of samples and the sample number of
                                     its first, in order; a Promise it returns is
                                     waited for before the next chunk is handed on,
                                     and `signal` aborts when the recording is over
                                     without having completed (cancelled, failed)
     onMark(frame, videoSeconds)     where the video was, at sample `frame` of the
                                     sound -- see MARKS below
     onEnd(reason)                   once, when everything is cleaned up: 'ended'
                                     (the video reached its end: its clock did, or
                                     its player said "ended"), 'stalled' (its clock
                                     stopped for ten seconds, and not at its end),
                                     'share-ended' (the person stopped sharing),
                                     'cancelled', 'ad', 'error'
   The promise resolves for ended, stalled and cancelled with {reason, rate,
   peaks (with wave), samples (with pcm), reached, duration}, and rejects with an
   Error whose message says what to do for the rest (its .reason is the reason).

   embed(el, id, on): on = {onReady(player), onState(code), onError(code, words),
   lengthWait: 2500, timeout: 25000} -- a frame of YouTube's is put in `el` (it
   must be on screen, and not display:none), and the promise is kept when the
   player is ready and knows how long the video is (or, after lengthWait ms, when it
   is ready and does not: a record() of it then says so).

   TWO CONSUMERS, ONE SHARE, ONE CLOCK.  The share is asked for once.  Every 25 ms
   one loop reads the video's clock once and feeds both:
     1. THE SHAPE.  An Analyser in an AudioContext of the browser's own rate reads
        the tab's sound; the loudest sample of what it holds is filed under
        round(clock * 20) -- THE VIDEO'S CLOCK, not the recording's, so that a
        video that stops to buffer does not slide what follows -- and the whole is
        divided by its loudest and kept to three decimals.  Bit for bit what
        player.js did before this file existed (tests/youtube_capture.mjs section
        l plays the ticks itself and holds it to a checksum).
     2. THE SOUND.  An AudioWorklet in a SECOND AudioContext of 16 kHz, on a
        clone of the audio track, hands blocks of 16-bit samples to the page; they
        are cut into chunks of chunkSeconds and given to onChunk one at a time.  A
        second context on purpose: the Analyser at 16 kHz would look at 128 ms of
        sound instead of 43 and every number of the shape would change.

   MARKS.  The sound is in RECORDING time and a transcript has to be in the
   VIDEO's: they differ by the start (the clock waits for YouTube to say it is
   playing) and by every stop to buffer (the tab records silence while the clock
   stands still).  So the clock and the sound are paired: onMark(frame, seconds)
   says "at sample `frame` of the sound, the video's clock read `seconds`".  One
   mark when the sound begins; one whenever the clock has strayed 0.05 s from where
   the last mark says it should be (no oftener than every 0.2 s); one at least
   every 30 s.  Nothing is guessed here: the caller (the server's remap) lays its
   captions through them.  Measured (tests/youtube_capture.mjs, Chrome 151 on
   Linux, a video of tones): laid through the marks, a tone is where the video has it
   to within 0.04 s once the video is playing, and to within 0.1 s in the first
   moments, before the clock has told how late it started.

   WHAT IS ALWAYS TRUE (tests/youtube_capture.mjs holds each):
     . one getDisplayMedia call per share, none if a live share with sound is held
     . a share with no sound fails BEFORE the video plays, in a sentence
     . nothing is ever connected to the speakers, and the microphone is never asked
     . the 'ended' listener on the share is taken off again at the end
     . a video that has played to its end is 'ended', never 'stalled', whatever
       length its player gave: YouTube's is the true length rounded UP to a whole
       second (596.501 s is 597) and its clock stops where the video does, up to a
       second short of it (measured, 2026-09-29: 7 of 13 videos stopped more than
       0.3 s short, and every one said "ended" as its clock stopped).  So a video
       that has played to within END_NEAR of its length is over when its player
       says "ended" -- or, of a player that cannot say, when its clock stands still
       for ten seconds.  A player that says it is paused or loading, or a clock
       that stops far from the end, is still a stall, and says so
     . cancel() -- and every other end -- stops playback and puts the player back
       as it was, closes both contexts, stops the clone, aborts what onChunk
       started, and leaves no timer and no state: a second record() works

   Plain ES2017, no build step, a classic script (no modules) so that the phone's
   copy of the player and its service worker need nothing special: served at
   /youtube/lib/tabcapture.js and kept for offline in lib/offline.py PLAYER_FILES. */
(function () {
  'use strict';
  if (window.ParsehTabCapture) return;

  var WAVE_RATE = 20;              // numbers a second: one every 50 ms
  var TICK_MS = 25;                // the one clock loop
  var STALL_TICKS = 400;           // a clock unmoved for this many ticks (10 s) has stalled
  var END_MARGIN = 0.3;            // seconds from the end at which a video has ended
  var END_NEAR = 5;                // seconds from the length within which "ended" from the player (or a stopped clock, if it cannot say) is the end
  var END_TAIL_MS = 500;           // the sound goes on this long after the clock says the end
  var PCM_RATE = 16000;            // what a transcript is made from
  var BLOCK = 4000;                // samples the worklet posts at a time: a quarter second
  var CHUNK_SECONDS = 5;           // the default chunk handed to onChunk
  var MAX_BACKLOG = 300;           // seconds of sound held for a slow onChunk before giving up
  var MARK_DRIFT = 0.05;           // how far the clock may stray from the last mark
  var MARK_GAP = 0.2;              // seconds of sound between one mark and the next, at least
  var MARK_EVERY = 30;             // seconds of sound between marks, at most
  var AD_JUMP = 1;                 // seconds the clock or the length may jump before it is an ad
  var AD_START = 2;                // the ad guard wakes once the clock has read under this
  var START_WAIT = 3000;           // ms the worklet has to say it is listening

  /* -------------------------------------------------------------- words */
  // The first three are lib/cardkit.js tabProblem's, word for word: the player's
  // sheets read that one, this page cannot load the card kit (the add page never
  // does), and tests/youtube_capture.mjs holds the two to each other.
  var SAY_SECURE = 'recording this tab needs the page opened at this computer’s address, or at the https address from another device, in Chrome or Edge';
  var SAY_BROWSER = 'only Chrome and Edge, on a computer, can record the sound of a tab';
  var SAY_READER = 'this browser cannot read the sound of a shared tab';
  var SAY_NO_SHARE = 'capture needs a secure page — open the toolbox at this computer’s address, or at the https address from another device';
  var SAY_NO_SOUND = 'the share came without its sound — share this tab again and ' +
                     'leave “Also allow tab audio” turned on';
  var SAY_NO_SOUND_PCM = 'the share came without its sound — share this tab again and ' +
                         'turn on “Share tab audio”';
  var SAY_SURFACE = 'a window or the whole screen was shared, not this tab — share this tab ' +
                    'again, with “Share tab audio” turned on';
  var SAY_NOTHING = 'nothing was heard — the tab was shared without its sound, or the video is muted';
  var SAY_NOT_STARTED = 'the video did not start playing — its clock never moved. Check that it plays ' +
                        'in the player (it may be unavailable, or slow to start), then try again';
  var SAY_SHARE_ENDED = 'the tab stopped being shared while the sound was being drawn';
  var SAY_SHARE_ENDED_PCM = 'the tab stopped being shared while its sound was being recorded';
  var SAY_AD = 'YouTube played an ad, so the recording was stopped — an ad’s sound would end ' +
               'up in the transcript';
  var SAY_BACKLOG = 'the sound could not be sent as fast as it was recorded, so the recording was stopped';
  var SAY_16K = 'this browser cannot record at 16 kHz, which the transcript is made from';
  var SAY_DEAF = 'the browser did not start reading the sound of the tab — press the button again';
  var SAY_BUSY = 'a recording is already under way in this page';
  var SAY_NO_PLAYER = 'the player has not loaded';
  var SAY_NO_LENGTH = 'the video has not said how long it is yet';
  var SAY_NO_AUDIO = 'this browser has no Web Audio';

  /* ------------------------------------------------- what this browser can do */
  // cardkit.js tabProblem, unchanged: '' when this browser can record the sound
  // of its own tab, else why not, in words a person can act on
  function baseProblem() {
    if (!window.isSecureContext) return SAY_SECURE;
    var ua = navigator.userAgentData, md = navigator.mediaDevices;
    var chromium = !!(ua && ua.brands && ua.brands.some(function (b) { return /chromium/i.test(b.brand); }));
    if (!chromium || ua.mobile || !md || !md.getDisplayMedia) return SAY_BROWSER;
    if (!window.MediaStreamTrackProcessor && !(window.AudioContext && window.AudioWorkletNode))
      return SAY_READER;
    return '';
  }
  // What the SOUND consumer needs beyond that: an AudioWorklet (the track
  // processor cardkit can do without is not what reads this).  `pcm: false` asks
  // only what the shape needs, which is baseProblem's own answer.
  function problem(opts) {
    var why = baseProblem();
    if (why) return why;
    if (!(opts && opts.pcm === false) && !(window.AudioContext && window.AudioWorkletNode))
      return SAY_READER;
    return '';
  }
  function capability(opts) {
    var why = problem(opts);
    return {ok: !why, why: why};
  }

  /* ------------------------------------------------------------ the share */
  /* SHARING THIS TAB.  One share, asked for once, serves the frame capture (its
     pictures), the cut editor on a YouTube video (its sound, which lib/cardkit.js
     records while the stretch plays) and this file's recordings: one question
     from Chrome for all of them, however many frames and clips follow.  It is
     asked for with its sound wherever the browser can record that (Chrome, Edge);
     a share given without the sound still serves the pictures, and the sound
     asks again, for a share that takes its place.  A share the person stops
     (Chrome's "Stop sharing") is asked for anew next time.  `want.audio`: the
     share must carry live sound.  (Moved here from youtube/lib/player.js.) */
  var tabShare = null;
  function tabShared(sound) {
    var s = tabShare;
    var live = function (kind) {
      return s.getTracks().some(function (t) {
        return t.kind === kind && t.readyState === 'live';
      });
    };
    return s && live('video') && (!sound || live('audio')) ? s : null;
  }
  function share(want) {
    var sound = !!(want && want.audio), have = tabShared(sound);
    if (have) return Promise.resolve(have);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia)
      return Promise.reject(new Error(SAY_NO_SHARE));
    var withSound = !baseProblem();
    // A share still live but without its sound is let go before asking
    // again: Chrome does not share this tab a second time while the first
    // share's picture is cropped to the video, as the frame capture's is
    // ("Could not start video source", however often it is asked).  Refused,
    // the next frame asks too.
    if (tabShare) {
      tabShare.getTracks().forEach(function (t) { t.stop(); });
      tabShare = null;
    }
    // preferCurrentTab and the rest are Chrome's; Firefox ignores unknown members
    return navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: withSound ? { echoCancellation: false, noiseSuppression: false, autoGainControl: false } : false,
      preferCurrentTab: true, selfBrowserSurface: 'include', systemAudio: 'exclude'
    }).then(function (s) {
      var old = tabShare;
      tabShare = s;
      if (old && old !== s) old.getTracks().forEach(function (t) { t.stop(); });
      return s;
    });
  }
  // the share as it stands, without asking: what the cut editor reads to know
  // whether Chrome is about to ask
  share.live = function (want) { return tabShared(!!(want && want.audio)); };
  function release() {
    var s = tabShare;
    tabShare = null;
    if (s) s.getTracks().forEach(function (t) { try { t.stop(); } catch (e) {} });
  }

  /* -------------------------------------------------- the sound, in blocks */
  // A worklet with no output at all (it runs all the same, so nothing reaches
  // the speakers) that turns the tab's sound into 16-bit mono samples, in
  // blocks of BLOCK, in order, each starting where the last ended.  It starts on
  // a 1 and says at which frame of its context it did ({on: frame}); on a 0 it
  // hands over what it holds and says {end: 1}.  A block the browser skipped is
  // filled with silence, so the samples are the recording's, not the arrivals'.
  var WORKLET = 'registerProcessor("parseh-pcm16",class extends AudioWorkletProcessor{' +
    'constructor(){super();this.on=false;this.next=-1;this.n=0;this.buf=new Int16Array(' + BLOCK + ');' +
    'this.port.onmessage=e=>{if(e.data===1){this.on=true;this.next=-1;this.n=0;}' +
    'else if(this.on){this.on=false;if(this.n)this.port.postMessage({d:this.buf.slice(0,this.n)});' +
    'this.port.postMessage({end:1});this.n=0;}};}' +
    'put(v){this.buf[this.n++]=v;if(this.n===this.buf.length){' +
    'this.port.postMessage({d:this.buf},[this.buf.buffer]);this.buf=new Int16Array(' + BLOCK + ');this.n=0;}}' +
    'process(ins){if(!this.on)return true;var c=ins[0],cf=currentFrame,n=128,k,j;' +
    'if(this.next<0){this.next=cf;this.port.postMessage({on:cf});}' +
    'var gap=Math.min(cf-this.next,160000);while(gap-->0)this.put(0);' +
    'if(c&&c.length){n=c[0].length;for(j=0;j<n;j++){var s=0;for(k=0;k<c.length;k++)s+=c[k][j];s/=c.length;' +
    's=s<-1?-1:s>1?1:s;this.put(Math.round(s<0?s*32768:s*32767));}}' +
    'else for(j=0;j<n;j++)this.put(0);' +
    'this.next=cf+n;return true;}});';

  // Blocks in, chunks out, in order, each with the number of the sample it starts
  // at.  What it holds is what it costs, and held() counts it.
  function chunker(size, emit) {
    var parts = [], have = 0, at = 0;
    function take(n) {
      var out = new Int16Array(n), put = 0;
      while (put < n) {
        var b = parts[0], need = n - put;
        if (b.length <= need) { out.set(b, put); put += b.length; parts.shift(); }
        else { out.set(b.subarray(0, need), put); parts[0] = b.subarray(need); put += need; }
      }
      have -= n;
      return out;
    }
    return {
      push: function (block) {
        parts.push(block); have += block.length;
        while (have >= size) { var at0 = at; at += size; emit(take(size), at0); }
      },
      flush: function () {
        if (!have) return;
        var n = have, at0 = at;
        at += n;
        emit(take(n), at0);
      },
      // what is held is let go: the recording is over and the sound is not wanted
      drop: function () { parts = []; have = 0; },
      held: function () { return have; }
    };
  }
  // Chunks handed to `send` one at a time, the next only once the last one's
  // promise is kept.  Sound piling up behind a slow send is held for MAX_BACKLOG
  // seconds and no more; past that it gives up, in words, and holds nothing.
  function sender(send, signal, failed) {
    var queue = [], queued = 0, sending = false, over = false, idle = [];
    function pump() {
      if (sending || over) return;
      if (!queue.length) { idle.splice(0).forEach(function (f) { f(); }); return; }
      var c = queue.shift();
      queued -= c.pcm.length;
      sending = true;
      new Promise(function (ok) { ok(send(c.pcm, c.offset, signal)); }).then(function () {
        sending = false;
        pump();
      }, function (err) {
        sending = false;
        stop();
        failed(err instanceof Error ? err : new Error(String((err && err.message) || err || SAY_BACKLOG)));
      });
    }
    function stop() {
      over = true;
      queue = []; queued = 0;
      idle.splice(0).forEach(function (f) { f(); });
    }
    return {
      add: function (pcm, offset) {
        if (over) return;
        queue.push({pcm: pcm, offset: offset});
        queued += pcm.length;
        if (queued > MAX_BACKLOG * PCM_RATE) { stop(); failed(new Error(SAY_BACKLOG)); return; }
        pump();
      },
      // resolves once everything handed over has been sent (or given up)
      drained: function () {
        return new Promise(function (ok) {
          if (over || (!sending && !queue.length)) ok(); else idle.push(ok);
        });
      },
      stop: stop,
      queued: function () { return queued; }
    };
  }
  // the two together, for record() and for the test that feeds them an hour
  function pipeline(size, send, signal, failed) {
    var cut = null;
    var out = sender(send, signal, function (err) { cut.drop(); failed(err); });
    cut = chunker(size, out.add);
    return {
      push: cut.push,
      end: function () { cut.flush(); return out.drained(); },
      stop: function () { out.stop(); cut.drop(); },
      held: cut.held,
      queued: out.queued
    };
  }

  // The 16 kHz half: a context of its own, the worklet on a clone of the audio
  // track (so stopping it never touches the share), and the first block's frame
  // as the recording's origin.  Resolves with {begin(), end(), frame(), close()}.
  function openPcm(track, onBlock) {
    var AC = window.AudioContext || window.webkitAudioContext;
    var ac = null, clone = null, node = null, url = '', origin = null;
    var onOrigin = null, onEnd = null;
    function undo() {
      if (url) { URL.revokeObjectURL(url); url = ''; }
      if (clone) { try { clone.stop(); } catch (e) {} clone = null; }
      if (node) { try { node.port.onmessage = null; node.disconnect(); } catch (e) {} node = null; }
      var c = ac;
      ac = null;
      return c ? Promise.resolve().then(function () { return c.close(); }).catch(function () {}) : Promise.resolve();
    }
    try { ac = new AC({sampleRate: PCM_RATE}); } catch (e) { return Promise.reject(new Error(SAY_16K)); }
    if (ac.sampleRate !== PCM_RATE) return undo().then(function () { throw new Error(SAY_16K); });
    url = URL.createObjectURL(new Blob([WORKLET], {type: 'text/javascript'}));
    clone = track.clone();
    return ac.audioWorklet.addModule(url).then(function () {
      URL.revokeObjectURL(url); url = '';
      node = new AudioWorkletNode(ac, 'parseh-pcm16', {numberOfInputs: 1, numberOfOutputs: 0});
      node.port.onmessage = function (e) {
        var m = e.data;
        if (m.on != null) { origin = m.on; if (onOrigin) onOrigin(); }
        else if (m.d) onBlock(m.d);
        else if (m.end && onEnd) onEnd();
      };
      ac.createMediaStreamSource(new MediaStream([clone])).connect(node);
      return ac.resume();
    }).then(function () {
      return {
        // starts the samples; resolves once the worklet says it is listening
        begin: function () {
          return new Promise(function (ok, no) {
            var timer = setTimeout(function () { onOrigin = null; no(new Error(SAY_DEAF)); }, START_WAIT);
            onOrigin = function () { clearTimeout(timer); onOrigin = null; ok(); };
            node.port.postMessage(1);
          });
        },
        // hands over what the worklet holds; resolves when all of it has come
        end: function () {
          return new Promise(function (ok) {
            var timer = setTimeout(function () { onEnd = null; ok(); }, START_WAIT);
            onEnd = function () { clearTimeout(timer); onEnd = null; ok(); };
            try { node.port.postMessage(0); } catch (e) { clearTimeout(timer); ok(); }
          });
        },
        // the sample of the recording that the context is at
        frame: function () { return origin == null || !ac ? -1 : Math.round(ac.currentTime * PCM_RATE) - origin; },
        started: function () { return origin != null; },
        close: undo
      };
    }, function (err) {
      return undo().then(function () { throw err; });
    });
  }

  /* --------------------------------------------------------- the recording */
  var active = null;               // the recording under way: one at a time
  function busy() { return !!active; }
  function call(fn) {
    if (typeof fn !== 'function') return undefined;
    try { return fn.apply(null, Array.prototype.slice.call(arguments, 1)); } catch (e) { return undefined; }
  }
  function refused(opts, reason, message) {
    var err = new Error(message);
    err.reason = reason;
    call(opts.onEnd, reason);
    return {promise: Promise.reject(err), cancel: function () { return Promise.resolve(); }, state: 'done'};
  }

  function record(opts) {
    opts = opts || {};
    var player = opts.player;
    var pcm = !!opts.pcm, wave = opts.wave !== false;
    if (active) return refused(opts, 'error', SAY_BUSY);
    if (!player) return refused(opts, 'error', SAY_NO_PLAYER);
    var why = problem({pcm: pcm});
    if (why) return refused(opts, 'error', why);
    var dur = 0;
    try { dur = player.getDuration ? player.getDuration() : 0; } catch (e) {}
    if (!(dur > 0)) return refused(opts, 'error', SAY_NO_LENGTH);
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return refused(opts, 'error', SAY_NO_AUDIO);

    var size = Math.max(1, Math.round((opts.pcm && opts.pcm.chunkSeconds || CHUNK_SECONDS) * PCM_RATE));
    var keepShare = opts.keepShare !== false;
    var wantWake = opts.wakeLock != null ? !!opts.wakeLock : pcm;
    var wantGuard = opts.guardUnload != null ? !!opts.guardUnload : pcm;
    var wantAdGuard = opts.adGuard != null ? !!opts.adGuard : pcm;

    var rec = {state: 'sharing', promise: null, cancel: null};
    var settle = {};
    rec.promise = new Promise(function (ok, no) { settle.ok = ok; settle.no = no; });
    active = rec;

    var st = null, track = null, ac = null, an = null, buf = null, peaks = null;
    var pcmSide = null, line = null, ctl = new AbortController();
    var timer = 0, tailTimer = 0, wake = null, over = false, played = false;
    var was = 1, volume = null, muted = false;
    var stalled = 0, last = -1, reached = 0, ticks = 0, armed = false;
    var mark = null, samples = 0, heard = 0, sendFailure = null, lateCancel = false;

    // ---- the ways out of it -------------------------------------------------
    function fail(reason, message) {
      var err = new Error(message);
      err.reason = reason;
      finish(reason, err);
    }
    function onShareEnded() { fail('share-ended', pcm ? SAY_SHARE_ENDED_PCM : SAY_SHARE_ENDED); }
    function onLeave(e) { e.preventDefault(); e.returnValue = ''; return ''; }
    function finish(reason, err) {
      if (over) return;
      over = true;
      rec.state = 'ending';
      clearInterval(timer);
      clearTimeout(tailTimer);
      // the listener taken off, or a later "Stop sharing" would pause whatever plays then
      if (track) track.removeEventListener('ended', onShareEnded);
      if (wake) wake.release();
      if (wantGuard) window.removeEventListener('beforeunload', onLeave);
      if (played) {
        try { player.pauseVideo(); } catch (e) {}
        try { if (player.setPlaybackRate) player.setPlaybackRate(was); } catch (e) {}
        if (opts.unmute) {
          try {
            if (volume != null) player.setVolume(volume);
            if (muted) player.mute();
          } catch (e) {}
        }
      }
      var closing = null;
      if (ac) { try { closing = ac.close(); } catch (e) {} ac = null; }
      var complete = !err && reason !== 'cancelled';
      if (!complete) ctl.abort();
      // the recording of a video that ended: its last samples, and every chunk sent
      var tail = pcmSide && complete
        ? pcmSide.end().then(function () { return line.end(); })
        : Promise.resolve();
      tail.then(function () {
        if (line && !complete) line.stop();
        return pcmSide ? pcmSide.close() : null;
      }).then(function () {
        return Promise.resolve(closing).catch(function () {});
      }).then(function () {
        if (!keepShare) release();
        var result = null;
        // cancelled while the last chunks were still going out, or a chunk
        // that could not be sent: neither is a recording that completed
        if (complete && lateCancel) { complete = false; reason = 'cancelled'; }
        else if (complete && sendFailure) { complete = false; err = sendFailure; reason = 'error'; }
        if (complete && reason === 'stalled' && reached < 1) {
          // THE VIDEO NEVER STARTED (playVideo ignored: an age or consent screen, autoplay refused in
          // the frame, a start slower than ten seconds): nothing was heard because nothing played, and
          // a sound the tab made meanwhile is not the video's -- it is neither "the share has no sound"
          // nor a recording to hand on
          err = new Error(SAY_NOT_STARTED);
          err.reason = reason = 'error';
        } else if (complete) {
          var top = 0, k;
          if (wave) {
            for (k = 0; k < peaks.length; k++) if (peaks[k] > top) top = peaks[k];
          } else top = heard;
          if (!top) {
            err = new Error(SAY_NOTHING);
            err.reason = reason = 'error';
          } else {
            if (wave) for (k = 0; k < peaks.length; k++) peaks[k] = Math.round(peaks[k] / top * 1000) / 1000;
            result = {reason: reason, reached: reached, duration: dur};
            if (wave) { result.rate = WAVE_RATE; result.peaks = peaks; }
            if (pcm) result.samples = samples;
          }
        }
        if (reason === 'cancelled') result = {reason: 'cancelled', reached: reached, duration: dur};
        rec.state = 'done';
        active = null;
        if (result && result.peaks) call(opts.onPeaks, result.peaks, WAVE_RATE);
        call(opts.onEnd, reason);
        if (result) settle.ok(result); else settle.no(err);
      });
    }
    rec.cancel = function () {
      if (over) {
        // it is already ending, and may be waiting on the last chunks to be
        // sent: the wait is over, and what was not sent is dropped
        if (rec.state === 'ending' && !lateCancel) {
          lateCancel = true;
          ctl.abort();
          if (line) line.stop();
        }
      } else finish('cancelled');
      return rec.promise.then(function () {}, function () {});
    };

    // ---- the one clock loop --------------------------------------------------
    // what the player says it is doing (YouTube's 0 is "ended"); null when it cannot say
    function playerState() {
      try {
        var s = player.getPlayerState ? player.getPlayerState() : null;
        return typeof s === 'number' && isFinite(s) ? s : null;
      } catch (e) { return null; }
    }
    function tick() {
      var v = 0, j, t = 0;
      if (an) {
        an.getFloatTimeDomainData(buf);
        for (j = 0; j < buf.length; j++) {
          var a = buf[j] < 0 ? -buf[j] : buf[j];
          if (a > v) v = a;
        }
      }
      try { t = player.getCurrentTime(); } catch (e) {}
      if (!isFinite(t)) return;
      // 1. the shape: each number is filed under the VIDEO'S clock
      var slot = Math.round(t * WAVE_RATE);
      if (peaks && slot >= 0 && slot < peaks.length && v > peaks[slot]) peaks[slot] = v;
      // a video that has stopped moving for a good while has ended, or has stalled
      // past helping: either way there is no more to hear
      if (Math.abs(t - last) < 0.01) stalled++; else stalled = 0;
      var before = last;
      last = t;
      if (t > reached) reached = t;
      ticks++;
      if (slot % 20 === 0) call(opts.onProgress, t, dur);
      // an ad: the clock runs backwards, or the length changes under us
      if (wantAdGuard) {
        if (!armed && t < AD_START) armed = true;
        if (armed) {
          var ad = before >= 0 && t < before - AD_JUMP;
          if (!ad && ticks % 40 === 0) {
            try { var d = player.getDuration(); ad = isFinite(d) && Math.abs(d - dur) > AD_JUMP; } catch (e) {}
          }
          if (ad) { fail('ad', SAY_AD); return; }
        }
      }
      // 2. the sound: where the video is, at the sample the sound has reached
      if (pcmSide && opts.onMark) markTick(t);
      // THE END.  The clock reaching the length is one way, and not the usual one: the length a player
      // gives is the video's rounded UP to a whole second (YouTube's is), the clock stops where the
      // video does, up to a second short, and `t >= dur - END_MARGIN` never came -- the recording sat
      // ten seconds and called a video that had ended "stalled".  So a video that has played to
      // within END_NEAR of its length is over when its player says "ended", or, of a player that
      // cannot say, when its clock has stood still for ten seconds.  A player that says it is
      // paused or loading, and a clock that stops anywhere else, is a stall: no silent loss of the
      // last seconds.  (`reached >= 1`: an "ended" left over from an earlier play is not this one's.)
      var near = reached >= 1 && reached >= dur - END_NEAR;
      var state = near ? playerState() : null;
      var ended = t >= dur - END_MARGIN || (near && (state === 0 || (state === null && stalled > STALL_TICKS)));
      if (ended || stalled > STALL_TICKS) {
        var reason = ended ? 'ended' : 'stalled';
        if (pcm && reason === 'ended') {
          // the sound is still on its way: the last of it is worth a moment
          clearInterval(timer);
          rec.state = 'ending';
          tailTimer = setTimeout(function () { finish('ended'); }, END_TAIL_MS);
        } else finish(reason);
      }
    }
    function markTick(t) {
      var frame = pcmSide.frame();
      if (frame < 0) return;
      if (mark) {
        var since = (frame - mark.frame) / PCM_RATE;
        var strayed = Math.abs(t - (mark.video + since)) > MARK_DRIFT && since >= MARK_GAP;
        if (!strayed && since < MARK_EVERY) return;
      }
      mark = {frame: frame, video: t};
      call(opts.onMark, frame, t);
    }

    // ---- getting started -----------------------------------------------------
    function begin() {
      // the video plays once, from the start, at its own speed
      try { was = player.getPlaybackRate ? player.getPlaybackRate() : 1; } catch (e) {}
      try { if (player.setPlaybackRate) player.setPlaybackRate(1); } catch (e) {}
      if (opts.unmute) {
        try {
          muted = player.isMuted();
          volume = player.getVolume();
          if (muted) player.unMute();
          player.setVolume(100);
        } catch (e) {}
      }
      played = true;
      try { player.seekTo(0, true); player.playVideo(); } catch (e) {}
      rec.state = 'listening';
      call(opts.onStart, dur);
      track.addEventListener('ended', onShareEnded, {once: true});
      if (wantGuard) window.addEventListener('beforeunload', onLeave);
      if (wantWake) wake = keepAwake();
      timer = setInterval(tick, TICK_MS);
    }
    share({audio: true}).then(function (s) {
      if (over) { if (!keepShare) release(); return; }
      st = s;
      if (pcm) {
        var vt = st.getVideoTracks()[0], set = vt && vt.getSettings ? vt.getSettings() : {};
        if (set.displaySurface && set.displaySurface !== 'browser') {
          release();
          throw Object.assign(new Error(SAY_SURFACE), {reason: 'error'});
        }
      }
      // no sound: said now, before anything plays, and not after an hour of silence
      if (!st.getAudioTracks().length) {
        throw Object.assign(new Error(pcm ? SAY_NO_SOUND_PCM : SAY_NO_SOUND), {reason: 'error'});
      }
      track = st.getAudioTracks()[0];
      // the picture is of no use to a recording that is let go of afterwards
      if (opts.dropVideo && !keepShare) {
        st.getVideoTracks().forEach(function (t) { try { t.stop(); } catch (e) {} });
      }
      // the shape's half: the browser's own rate, nothing connected to the speakers
      if (wave) {
        ac = new AC();
        var src = ac.createMediaStreamSource(st);
        an = ac.createAnalyser();
        an.fftSize = 2048;
        an.smoothingTimeConstant = 0;
        src.connect(an);             // and to nothing else: it is not played again
        buf = new Float32Array(an.fftSize);
        peaks = [];
        for (var i = 0, n = Math.ceil(dur * WAVE_RATE) + 1; i < n; i++) peaks.push(0);
      }
      if (!pcm) return begin();
      // the sound's half opens first, so that the first sound of the video is caught
      line = pipeline(size, opts.onChunk || function () {}, ctl.signal, function (err) {
        err.reason = err.reason || 'error';
        sendFailure = err;
        finish('error', err);
      });
      return openPcm(track, function (block) {
        samples += block.length;
        for (var k = 0; k < block.length; k++) {
          var m = block[k] < 0 ? -block[k] : block[k];
          if (m > heard) heard = m;
        }
        line.push(block);
      }).then(function (side) {
        pcmSide = side;
        if (over) return side.close().then(function () { return null; });
        return side.begin();
      }).then(function () {
        if (!over) begin();
      });
    }).then(null, function (err) {
      if (over) return;
      if (!err.reason) err.reason = 'error';
      finish(err.reason, err);
    });
    return rec;
  }

  // keep the screen awake while a long recording runs; the browser lets go when
  // the tab is hidden, so it is asked again when the tab is seen
  function keepAwake() {
    var lock = null, gone = false;
    function ask() {
      if (gone || !navigator.wakeLock || document.visibilityState !== 'visible') return;
      try {
        navigator.wakeLock.request('screen').then(function (l) {
          if (gone) { try { l.release(); } catch (e) {} return; }
          lock = l;
        }, function () {});
      } catch (e) {}
    }
    document.addEventListener('visibilitychange', ask);
    ask();
    return {
      release: function () {
        gone = true;
        document.removeEventListener('visibilitychange', ask);
        if (lock) { try { lock.release(); } catch (e) {} lock = null; }
      }
    };
  }

  /* ----------------------------------------------------------- the player */
  // A YouTube player to record: the IFrame API loaded once (chained onto anything
  // else waiting for it, as the transcript editor does), a frame put in `el`, and
  // the promise kept when it says it is ready.  It is never the person's own
  // video, and it needs no Referer of its own: an embed without one is refused
  // ("Video player configuration error"), so none is taken away.
  var YT_API = 'https://www.youtube.com/iframe_api';
  var embeds = 0;
  function whyYouTube(code) {
    return code === 2 ? 'YouTube does not know this address'
      : code === 5 ? 'YouTube will not play this video in this browser'
      : code === 100 ? 'this video is gone from YouTube — it was taken down, or it was made private'
      : (code === 101 || code === 150)
        ? 'the owner of this video does not allow it to be played outside YouTube'
        : 'YouTube would not play this video (error ' + String(code) + ')';
  }
  function embed(el, videoId, on) {
    on = on || {};
    return new Promise(function (ok, no) {
      var slot = document.createElement('div');
      slot.id = 'parseh-tabcapture-yt-' + (++embeds);
      el.appendChild(slot);
      var made = false, settled = false, timer = 0;
      function refuse(err) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        no(err);
      }
      function make() {
        if (made || settled) return;
        made = true;
        var player = new window.YT.Player(slot.id, {
          videoId: videoId,
          playerVars: {rel: 0, playsinline: 1},
          events: {
            onReady: function () {
              if (settled) return;
              // ready is not the same as knowing how long the video is: YouTube
              // says 0 until it has read the video's details, which is nearly
              // always at once, and a recording needs the length.  Waited for a
              // moment, and no longer: a live video never says.
              var till = Date.now() + (on.lengthWait == null ? 2500 : on.lengthWait);
              (function ask() {
                if (settled) return;
                var d = 0;
                try { d = player.getDuration(); } catch (e) {}
                if (!(d > 0) && Date.now() < till) { setTimeout(ask, 100); return; }
                settled = true;
                clearTimeout(timer);
                call(on.onReady, player);
                ok(player);
              })();
            },
            onStateChange: function (e) { call(on.onState, e && e.data); },
            onError: function (e) {
              var code = e && e.data, words = whyYouTube(code);
              call(on.onError, code, words);
              refuse(Object.assign(new Error(words), {code: code}));
            }
          }
        });
      }
      if (window.YT && window.YT.Player) make();
      else {
        var was = window.onYouTubeIframeAPIReady;
        window.onYouTubeIframeAPIReady = function () {
          if (typeof was === 'function') { try { was(); } catch (x) {} }
          make();
        };
        if (!document.querySelector('script[data-tc-yt], script[data-se-yt]')) {
          var tag = document.createElement('script');
          tag.src = YT_API;
          tag.setAttribute('data-tc-yt', '1');
          // the script itself failing is the one thing that IS a network answer
          tag.onerror = function () {
            // a dead tag left in <head> would stop every later try adding a script of its own, and
            // each would wait its whole time and blame the wrong thing: gone first, so that it is
            // gone even when this try has already timed out
            try { tag.parentNode.removeChild(tag); } catch (x) {}
            refuse(new Error('YouTube’s player could not be fetched — Parseh itself is answering, ' +
                             'so it is YouTube this computer cannot reach'));
          };
          document.head.appendChild(tag);
        }
      }
      // a script that neither loads nor fails, or a player that never starts
      timer = setTimeout(function () {
        refuse(new Error('YouTube’s player did not start'));
      }, on.timeout || 25000);
    });
  }

  window.ParsehTabCapture = {
    capability: capability, problem: problem,
    share: share, release: release, busy: busy,
    record: record, embed: embed,
    // for the test that feeds the sound's pipeline an hour of it in a second
    _pipeline: pipeline
  };
})();
