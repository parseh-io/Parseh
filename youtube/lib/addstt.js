// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — the speech to text of the add-a-video page.

     ParsehAddStt.mount(opts) -> {sourceChanged, langChanged, modelChanged, redraw,
                                  busy, guardEdit, wave, words, videoAdded}

   ONE OPTIONAL BLOCK in the transcript's step, and nothing else of Parseh's
   knows it is there: it writes the transcript into the box the page already
   has, in the format the page already reads, and the video is added the way a
   pasted transcript adds one.  A person who never installs speech to text
   sees a link to where it is installed; nothing is fetched, downloaded or
   asked of anyone because this page was opened.

   WHAT IT READS.  POST /lookup/api/speech, the slim slice Settings -> Speech to
   text keeps (lib/getstt.py summary): is it installed, which models, how the
   processor may be chosen, which languages.  It is asked again whenever this
   page is looked at again (window focus), so an install made in another tab
   shows here with no reload.  Only the models that are ready are offered
   (never more than the two), and the NVIDIA GPU only when the computer says
   the card is ready; CPU always works.

   WHAT IT DOES, by the routes under <base>/api/transcribe/ (lib/sttjobs.py):

     a film on this computer:  start -> status ... -> result.  The computer
        reads the file itself: nothing is played and any browser will do.  The
        path is a path on THAT computer's disk, whoever is looking at this page.
     a YouTube video:  start (the computer says which video: its own id, never
        this page's guess) -> the video is put in a frame here -> the person
        presses "Start recording" (the browser only shares a tab for a click,
        and the frame has to be there first) -> youtube/lib/tabcapture.js
        plays it from its beginning while it records this tab's sound, and
        each chunk goes to audio; the marks and the shape of the sound go
        before the last piece; then status ... -> result.

   THE RESULT WAITS FOR EXPLICIT REVIEW AND USE.  Never over words the person wrote
   without asking (before it starts, and again when it arrives if the box
   changed meanwhile), never adds the video, and whatever LLM prompt was
   prepared is out of date (opts.invalidate).  The box is tied to the video, the
   language and the model that made it: change one of them and the tie is
   dropped, quietly.  Changing the processor alone changes nothing about the
   transcript, so it does not.

   WHAT IT NEVER DOES: put a control on a video already added (this page is
   the only one that has it), fail into a traceback (every refusal and every
   end of a capture is a sentence), overwrite the box on a failure, or start a
   second job while one runs.

   Plain ES2017, no build step, a classic script: served at
   /youtube/lib/addstt.js, after youtube/lib/tabcapture.js. */
(function () {
  'use strict';
  if (window.ParsehAddStt) return;

  var SLICE = '/lookup/api/speech';
  var SETTINGS = '/settings/speech/';
  var POLL_MS = 1200;              // how often a running job is asked how it is
  var DEADLINE_MS = 8000;          // one ask: a silent computer is not a refusal
  var PIECE_TRIES = 3;             // a piece of the recording is sent this often before giving up
  var PIECE_DEADLINE_MS = 40000;   // one piece is 5 s of sound, 160 KB
  var READY_MS = 8 * 60 * 1000;    // a loaded video nobody records: the computer would give up at 10 minutes
  var PREFS = 'yt_add_stt';        // the model and the processor last chosen, in this browser only
  var STATE = 'yt_add_stt_state';  // what a reload must find again: the tie, held derived data, a running job

  /* ---------------------------------------------------------------- words */
  var SAY_START_OVER = 'Replace the transcript in the box with a new one made by speech to text? ' +
                       'What is written there now is lost.';
  var SAY_RESULT_OVER = 'The transcript in the box changed while this was running. Replace it with ' +
                        'the one speech to text made? What is written there now is lost.';
  var SAY_LOCKED = 'a transcription is running — cancel it first';
  var SAY_ABSENT = 'Speech to text is not set up on this computer. It is optional: Parseh can write ' +
                   'a transcript for you, here on this computer and without sending anything anywhere, ' +
                   'but pasting one works exactly as it always did.';
  var SAY_FILM = 'The film named above is read from its file on the computer Parseh runs on, so ' +
                 'nothing is played and any browser will do. The path is a path on that computer’s ' +
                 'disk, even when this page is open on another device.';
  var SAY_YOUTUBE = 'The video plays here in real time, from its beginning, while this page records ' +
                    'its sound — an hour of video takes an hour. Your browser will ask which tab to ' +
                    'share: choose this tab, and turn on “Share tab audio”. Keep this tab in front ' +
                    'until it is done. The sound is processed on this computer and deleted once the ' +
                    'transcript is made.';
  var SAY_READY = 'The video is loaded. Press Start recording: it plays here in real time, from its ' +
                  'beginning, while this page records its sound. Your browser will ask which tab to ' +
                  'share — choose this tab, and turn on “Share tab audio”. Keep this tab in front ' +
                  'until it is done.';
  var SAY_KEEP = 'Keep this tab in front until it is done. Cancel stops the recording and writes nothing.';
  var SAY_NO_TAB = 'Automatic transcription of a YouTube video records this tab’s sound while the ' +
                   'video plays, and this browser cannot: ';
  var SAY_STALLED = 'The video stopped moving for ten seconds, so the recording was stopped and ' +
                    'nothing was written.';
  var SAY_HIDDEN = 'This tab is not in front. Bring it back, or the recording may fall behind.';
  var SAY_LEFT = 'The recording was stopped when the page was left, so nothing was written. Press ' +
                 'Transcribe to start again.';
  var SAY_GIVE_UP = 'The recording was not started, so the transcription was let go. Press ' +
                    'Transcribe to begin again.';
  var SAY_SILENT = 'Parseh has not answered for a moment — still waiting.';

  /* ---------------------------------------------------------------- small */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function button(text, id, cls) {
    var b = el('button', cls || 'wbtn', text);
    b.type = 'button';
    b.id = id;
    return b;
  }
  // A small string that says whether two texts are the same: enough to know
  // "the box still holds what was put in it", without keeping a second copy of
  // a 150 KB transcript in the browser's storage.
  function hash(s) {
    var h = 5381;
    s = String(s == null ? '' : s);
    for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36) + ':' + s.length;
  }
  function clock(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = sec % 60;
    var two = function (x) { return (x < 10 ? '0' : '') + x; };
    return h ? h + ':' + two(m) + ':' + two(s) : m + ':' + two(s);
  }
  // THE BROWSER'S STORAGE IS A CONVENIENCE, never something the page depends
  // on: it can be blocked, full or gone, and every read and write is guarded.
  function load(key) {
    try { var v = JSON.parse(localStorage.getItem(key) || 'null'); return v && typeof v === 'object' ? v : {}; }
    catch (e) { return {}; }
  }
  function store(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) {} }
  function forget(key) { try { localStorage.removeItem(key); } catch (e) {} }

  // One ask of the computer, with a deadline of its own: what comes back is
  // {status, j}; a server that answers nothing rejects, and that is not the
  // same as one that refuses.  `body` is JSON, or a typed array of sound.
  function ask(url, body, ms, outer) {
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, ms || DEADLINE_MS);
    function stop() { ctl.abort(); }
    if (outer) {
      if (outer.aborted) ctl.abort();
      else outer.addEventListener('abort', stop, {once: true});
    }
    var opts = {method: 'POST', signal: ctl.signal};
    if (body && ArrayBuffer.isView(body)) {
      opts.headers = {'Content-Type': 'application/octet-stream'};
      opts.body = body;
    } else {
      opts.headers = {'Content-Type': 'application/json'};
      opts.body = JSON.stringify(body || {});
    }
    return fetch(url, opts).then(function (r) {
      return r.text().then(function (t) {
        var j = null;
        try { j = JSON.parse(t); } catch (e) {}
        return {status: r.status, j: j && typeof j === 'object' ? j
                : {ok: false, error: 'Parseh answered with something that was not an answer.'}};
      });
    }).then(function (x) {
      clearTimeout(timer);
      if (outer) outer.removeEventListener('abort', stop);
      return x;
    }, function (e) {
      clearTimeout(timer);
      if (outer) outer.removeEventListener('abort', stop);
      throw e;
    });
  }

  // Why the browser cannot record a tab, in the words of the one module that
  // knows -- or that the module did not even load.
  function tabProblem() {
    var TC = window.ParsehTabCapture;
    if (!TC || !TC.capability) return 'the part of this page that records a tab did not load';
    var c = TC.capability();
    return c.ok ? '' : c.why;
  }
  // What a failed capture says.  tabcapture's own messages are sentences; the
  // browser's are "Permission denied".
  function whyCapture(err) {
    var name = err && err.name, msg = err && err.message;
    if (name === 'NotAllowedError' || name === 'SecurityError')
      return 'The browser was not allowed to record this tab. Press Start recording again, choose ' +
             'this tab, and press “Share”.';
    if (name === 'NotFoundError' || name === 'NotReadableError' || name === 'AbortError')
      return 'The browser could not record this tab (' + name + '). Press Start recording to try again.';
    // an Error of tabcapture's own is a sentence already (the browser's are
    // DOMExceptions with a name of their own, and say things like "TypeError")
    if (msg && (!name || name === 'Error')) {
      msg = msg.charAt(0).toUpperCase() + msg.slice(1);
      return /[.!?]$/.test(msg) ? msg : msg + '.';
    }
    return 'The recording could not be made' + (name ? ' (' + name + ')' : '') + '.';
  }

  /* ---------------------------------------------------------------- mount */
  function mount(o) {
    var root = o.root, base = o.base || '/youtube';
    var toast = o.toast || function () {};
    var confirmOver = o.confirm || function (m) { return window.confirm(m); };
    var route = function (name) { return base + '/api/transcribe/' + name; };

    // THE STATE.  `phase`: idle | starting | loading (the video is being put
    // in its frame) | ready (it is there, waiting for the click that shares the
    // tab) | recording | sending (the end of the recording) | working (the
    // computer is listening) | stopping.  `run` counts starts and ends, so that
    // an answer that arrives after a Cancel finds it is not wanted.
    var S = {slice: null, phase: 'idle', run: 0, job: '', kind: '', key: '', lang: '', model: '',
             startHash: '', video: '', player: null, rec: null, sent: 0, timer: 0, readyTimer: 0,
             abort: null, held: null, said: '', pct: null, responses: 0, secondPass: null};
    var AUTO = null;   // {source, lang, model, hash}: the box holds what THIS video, language and model made
    var WAVE = null;   // {job, source}: the shape of the sound, held by the computer for this video
    var WORDS = null;  // {job, source, lang}: the word tape, for a YouTube video or a local film
    var LOCKED = null; // while a job runs: [[element, value]] what the controls read when it began
    var lastToast = 0;

    /* ---------------------------------------------------------- the block */
    root.textContent = '';
    root.hidden = true;
    var title = el('p', 'stt-title');
    title.appendChild(el('b', null, 'Speech to text'));
    title.appendChild(el('span', 'stt-opt', 'optional'));
    var absent = el('div', 'stt-absent');
    absent.id = 'stt_absent';
    absent.appendChild(el('p', 'fieldnote', SAY_ABSENT));
    var setup = el('a', 'wbtn small quiet', 'Set up speech to text');
    setup.id = 'stt_setup';
    setup.href = SETTINGS;
    setup.target = '_blank';
    setup.rel = 'noopener';
    var why = el('p', 'fieldnote warn');
    why.id = 'stt_why';
    absent.appendChild(el('div', 'row')).appendChild(setup);

    var form = el('div', 'stt-form');
    form.id = 'stt_form';
    var intro = el('p', 'fieldnote', 'Have Whisper on this computer listen to the video and write a pending transcript. ' +
                   'Then edit it in Transcribe & review and try any correction tools you need. Connected LLM tools send text only when you run them. Audio stays on this computer.');
    var selModel = el('select'), selProc = el('select');
    selModel.id = 'stt_model';
    selProc.id = 'stt_proc';
    var rowModel = el('div', 'row'), rowProc = el('div', 'row');
    var lblModel = el('label', 'inline', 'Model '), lblProc = el('label', 'inline', 'Processing ');
    lblModel.appendChild(selModel);
    lblProc.appendChild(selProc);
    rowModel.appendChild(lblModel);
    var moreModels = el('a', 'fieldnote', 'Manage models'); moreModels.href = SETTINGS;
    moreModels.target = '_blank'; moreModels.rel = 'noopener'; rowModel.appendChild(moreModels);
    rowProc.appendChild(lblProc);
    var exact = el('input');
    exact.type = 'checkbox';
    exact.id = 'stt_exact';
    var rowExact = el('div', 'row'), lblExact = el('label', 'inline', 'Exact word times ');
    lblExact.appendChild(exact);
    rowExact.appendChild(lblExact);
    var modelNote = el('span', 'fieldnote'), now = el('span', 'fieldnote'), gpu = el('span', 'fieldnote warn');
    var langNote = el('span', 'fieldnote'), busyNote = el('span', 'fieldnote warn'), how = el('p', 'fieldnote');
    var exactNote = el('span', 'fieldnote');
    modelNote.id = 'stt_modelnote';
    now.id = 'stt_now';
    gpu.id = 'stt_gpu';
    langNote.id = 'stt_lang';
    busyNote.id = 'stt_busy';
    how.id = 'stt_how';
    exactNote.id = 'stt_exactnote';
    var go = button('Transcribe', 'stt_go'), rec = button('Start recording', 'stt_rec');
    var cancel = button('Cancel', 'stt_cancel', 'wbtn quiet');
    var reopen = button('Open transcription', 'stt_open', 'wbtn quiet');
    reopen.hidden = true; reopen.setAttribute('data-layout', 'browser');
    var reviewRoot = el('section', 'stt-review');
    reviewRoot.id = 'stt_review'; reviewRoot.hidden = true;
    reviewRoot.setAttribute('data-layout', 'browser');
    var actions = el('div', 'row');
    [go, rec, cancel, reopen].forEach(function (b) { actions.appendChild(b); });
    var frame = el('div', 'stt-frame');
    frame.id = 'stt_frame';
    var bar = el('div', 'stt-bar');
    bar.id = 'stt_bar';
    bar.setAttribute('role', 'progressbar');
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', '100');
    bar.appendChild(el('i'));
    var secondProgress = el('div', 'stt-second-pass'); secondProgress.hidden = true;
    secondProgress.id = 'stt_second_pass';
    var secondLabel = el('p', 'fieldnote'); secondLabel.id = 'stt_second_pass_label';
    secondLabel.setAttribute('role', 'status'); secondLabel.setAttribute('aria-live', 'polite');
    var secondBar = el('div', 'stt-bar'); secondBar.id = 'stt_second_pass_bar';
    secondBar.setAttribute('role', 'progressbar'); secondBar.setAttribute('aria-labelledby', secondLabel.id);
    secondBar.setAttribute('aria-valuemin', '0'); secondBar.appendChild(el('i'));
    secondProgress.appendChild(secondLabel); secondProgress.appendChild(secondBar);
    var sayEl = el('p', 'stt-say');
    sayEl.id = 'stt_say';
    sayEl.setAttribute('role', 'status');
    sayEl.setAttribute('aria-live', 'polite');
    [intro, rowModel, modelNote, rowProc, now, gpu, rowExact, exactNote, busyNote, langNote, how, actions, frame, bar, secondProgress, sayEl,
     el('div', 'row')].forEach(function (n) { form.appendChild(n); });
    form.lastChild.appendChild(reviewRoot);
    var reviewMobile = el('p', 'fieldnote', 'Switch to the Browser interface above to choose and use the pending transcript review.');
    reviewMobile.setAttribute('data-layout', 'mobile'); reviewMobile.hidden = true;
    form.lastChild.appendChild(reviewMobile);
    var REVIEW = window.ParsehAsrReview.mount(reviewRoot, {choose: function (mode, skill, task, ids, options) { chooseReview(mode, ids, skill, task, options); }, retry: retryReview, external: externalReview, current: pendingCurrent, job: function () { return S.job; }, use: useReview, cancel: cancelReview, save: saveReviewDraft, pause: pauseReview,
      select: selectReviewWord, seek: seekReview, dictionary: function (wordId) {
        if (!S.held || !pendingCurrent()) return Promise.reject(new Error('This review changed.'));
        return ask(route('dictionary'), {job: S.job, source_sha256: S.held.res.review.evidence.source_sha256, word_id: wordId}, 10000)
          .then(function (r) { if (!r.j.ok) throw new Error(r.j.error); return r.j; });
      }});
    var LLM = null;

    var tied = el('p', 'fieldnote');
    tied.id = 'stt_tied';
    var noteEl = el('div', 'note');
    noteEl.id = 'stt_note';
    noteEl.setAttribute('aria-live', 'polite');
    [title, absent, why, form, tied, noteEl].forEach(function (n) { root.appendChild(n); });

    /* The browser workspace owns playback; ASR, review and the box keep their
       existing lifecycle. Returning to Add Video preserves the pending draft. */
    var workspace = el('dialog', 'stt-workspace');
    workspace.id = 'stt_workspace'; workspace.setAttribute('data-layout', 'browser');
    workspace.setAttribute('aria-labelledby', 'stt_workspace_title');
    // a <div>, not a <header>: the page's stylesheet and scripts (youtube/lib/style.css, lib/*.js) know a bare <header> as
    // the player's fixed bar that slides away on scroll, and took this one out of the window, over its top, and off it
    var head = el('div', 'stt-workspace-head');
    var heading = el('h2', null, 'Transcribe & review'); heading.id = 'stt_workspace_title';
    var step = el('span', 'stt-workspace-step');
    var back = button('Return to Add Video', 'stt_back', 'wbtn small quiet');
    [heading, step, back].forEach(function (n) { head.appendChild(n); }); workspace.appendChild(head);
    var columns = el('div', 'stt-workspace-columns'), media = el('section', 'stt-workspace-media');
    media.setAttribute('aria-label', 'Video and playback controls');
    var playerNote = el('p', 'fieldnote', 'Loading the video…');
    var transport = el('div', 'stt-transport'); transport.setAttribute('dir', 'ltr');
    var playPause = button('Play', 'stt_play', 'wbtn small quiet');
    var playbackClock = el('output', 'stt-playback-clock', '0:00'); playbackClock.setAttribute('aria-label', 'Playback time');
    transport.appendChild(playPause); transport.appendChild(playbackClock);
    var nudges = el('div', 'stt-nudges'); transport.appendChild(nudges);
    [-5, -2, -1, 1, 2, 5].forEach(function (seconds) {
      var b = button((seconds > 0 ? '+' : '−') + Math.abs(seconds) + ' s', 'stt_seek_' + (seconds < 0 ? 'back_' : 'forward_') + Math.abs(seconds), 'wbtn small quiet');
      b.setAttribute('aria-label', (seconds < 0 ? 'Back ' : 'Forward ') + Math.abs(seconds) + ' seconds');
      b.addEventListener('click', function () { if (S.player) seekReview(currentTime() + seconds, false); });
      nudges.appendChild(b);
    });
    var context = el('div', 'stt-replay-context');
    var selectedLine = el('bdi', null, 'Select a transcript word to jump to its time.'); selectedLine.dir = 'auto';
    var selectedTime = el('p', 'fieldnote');
    var replayActions = el('div', 'row');
    var replayWord = button('Replay word', 'stt_replay_word', 'wbtn small quiet');
    var replaySentence = button('Replay caption', 'stt_replay_caption', 'wbtn small quiet');
    var leadLabel = el('label', 'inline', 'Context '), lead = el('select');
    [1, 2, 5].forEach(function (n) { var option = el('option', null, n + ' s'); option.value = String(n); lead.appendChild(option); });
    lead.value = '2'; lead.setAttribute('aria-label', 'Seconds of context before and after replay'); leadLabel.appendChild(lead);
    [replayWord, replaySentence, leadLabel].forEach(function (n) { replayActions.appendChild(n); });
    [selectedLine, selectedTime, replayActions].forEach(function (n) { context.appendChild(n); });
    var work = el('section', 'stt-workspace-review'); work.setAttribute('aria-label', 'Transcription and review');
    var pending = el('div', 'stt-workspace-pending');
    var pendingHeading = el('h3', null, 'Whisper is preparing your transcript');
    pending.appendChild(pendingHeading);
    pending.appendChild(el('p', null, 'When transcription finishes, edit the words or try any review tool. Your transcript box stays unchanged until you choose Use this transcript.'));
    var jobActions = el('div', 'row');
    var notice = el('p', 'stt-workspace-notice'); notice.setAttribute('role', 'status');
    [pending, jobActions, reviewRoot, notice].forEach(function (n) { work.appendChild(n); });
    // Moving reviewRoot alone is safe on mobile: it was browser-only already.
    [media, work].forEach(function (n) { columns.appendChild(n); }); workspace.appendChild(columns); root.appendChild(workspace);
    var beforeWorkspace = null, inWorkspace = false, playbackTimer = 0, replayStop = null, selectedWord = null, selectedCaption = null, mediaGeneration = 0;
    function browserLayout() { return document.documentElement.getAttribute('data-mode') !== 'mobile'; }
    function captureLive() { return ['starting', 'loading', 'ready', 'recording', 'sending', 'stopping'].indexOf(S.phase) >= 0; }
    function openWorkspace() {
      if (!browserLayout()) return;
      if (!inWorkspace) {
        beforeWorkspace = document.activeElement;
        [frame, playerNote, transport, context].forEach(function (n) { media.appendChild(n); });
        [how, bar, secondProgress, sayEl].forEach(function (n) { pending.appendChild(n); });
        [rec, cancel].forEach(function (n) { jobActions.appendChild(n); });
        // Progress stays above review, including during LLM requests.
        work.insertBefore(bar, reviewRoot); work.insertBefore(secondProgress, reviewRoot); work.insertBefore(sayEl, reviewRoot);
        inWorkspace = true;
      }
      if (!workspace.open) { workspace.showModal(); heading.tabIndex = -1; heading.focus(); }
      if (!playbackTimer) playbackTimer = setInterval(updatePlayback, 250);
      ensureReviewPlayer(); paint();
    }
    function closeWorkspace(force) {
      if (!force && captureLive()) return;
      replayStop = null; clearInterval(playbackTimer); playbackTimer = 0;
      if (S.player && !captureLive()) { try { S.player.pauseVideo(); } catch (e) {} }
      if (workspace.open) workspace.close();
      if (beforeWorkspace && beforeWorkspace.focus) beforeWorkspace.focus();
      beforeWorkspace = null;
      paint();
    }
    back.addEventListener('click', function () { closeWorkspace(false); });
    reopen.addEventListener('click', openWorkspace);
    workspace.addEventListener('cancel', function (e) { e.preventDefault(); closeWorkspace(false); });
    function currentTime() { try { return S.player.getCurrentTime() || 0; } catch (e) { return 0; } }
    function updatePlayback() {
      var p = S.player, enabled = !!p && !captureLive();
      Array.prototype.forEach.call(transport.querySelectorAll('button'), function (b) { b.disabled = !enabled; });
      replayWord.disabled = !enabled || !selectedWord;
      replaySentence.disabled = !enabled || !selectedCaption;
      if (!p) return;
      var t = currentTime(), duration = 0, playing = false;
      try { duration = p.getDuration(); playing = p.getPlayerState() === 1; } catch (e) {}
      playbackClock.textContent = clock(t) + (duration > 0 ? ' / ' + clock(duration) : '');
      playPause.textContent = playing ? 'Pause' : 'Play';
      // A seek is asynchronous, especially with YouTube. Arm the stop only
      // once playback reaches the requested region, not at its old position.
      if (replayStop != null) {
        if (t >= replayStop.from - .25 && t < replayStop.end) replayStop.armed = true;
        if (replayStop.armed && t >= replayStop.end) { try { p.pauseVideo(); } catch (e) {} replayStop = null; }
      }
      if (S.held && REVIEW.playhead) REVIEW.playhead(t);
    }
    function seekReview(at, play, end) {
      if (!S.player || captureLive() || typeof at !== 'number' || !isFinite(at)) return;
      var duration = 0; try { duration = S.player.getDuration(); } catch (e) {}
      at = Math.max(0, duration > 0 ? Math.min(at, duration) : at);
      replayStop = typeof end === 'number' && isFinite(end) ? {from: at, end: Math.max(at + .1, end), armed: false} : null;
      try { S.player.seekTo(at, true); if (play) S.player.playVideo(); } catch (e) {}
      updatePlayback();
    }
    function selectReviewWord(w, caption, jump) {
      selectedWord = w; selectedCaption = caption;
      selectedLine.textContent = caption.text;
      var hasWordTime = typeof w.start === 'number' && isFinite(w.start);
      selectedTime.textContent = 'Selected: ' + w.text + ' · ' + clock(hasWordTime ? w.start : caption.start) +
        (hasWordTime ? ' · Whisper word time' : ' · Caption time; word timing unavailable');
      if (jump) {
        var start = hasWordTime ? w.start : caption.start;
        var end = hasWordTime && typeof w.end === 'number' ? w.end : caption.end;
        seekReview(start, true, (typeof end === 'number' ? Math.max(start, end) : start + 1) + .6);
      }
      updatePlayback();
    }
    function replay(which) {
      var span = which === 'word' && selectedWord && typeof selectedWord.start === 'number' ? selectedWord : selectedCaption;
      if (!span) return;
      var padding = Number(lead.value);
      seekReview(Math.max(0, span.start - padding), true, typeof span.end === 'number' ? span.end + padding : null);
    }
    replayWord.addEventListener('click', function () { replay('word'); });
    replaySentence.addEventListener('click', function () { replay('caption'); });
    playPause.addEventListener('click', function () {
      replayStop = null;
      if (!S.player || captureLive()) return;
      try { if (S.player.getPlayerState() === 1) S.player.pauseVideo(); else S.player.playVideo(); } catch (e) {}
      updatePlayback();
    });
    function ensureReviewPlayer() {
      if (!inWorkspace || !S.job || S.player || S.mediaLoading) return;
      if (S.kind === 'film') {
        var film = el('video'); film.controls = true; film.preload = 'metadata'; film.playsInline = true;
        var filmSeek = null;
        film.src = route('media') + '?job=' + encodeURIComponent(S.job); frame.textContent = ''; frame.appendChild(film);
        S.player = {getCurrentTime: function () { return film.currentTime; }, getDuration: function () { return film.duration; },
          getPlayerState: function () { return film.paused || film.ended ? 2 : 1; },
          seekTo: function (t) { if (film.readyState < 1) filmSeek = t; else film.currentTime = t; }, pauseVideo: function () { film.pause(); },
          playVideo: function () { var promise = film.play(); if (promise) promise.catch(function () { playerNote.textContent = 'Press Play in the video to start playback.'; }); },
          destroy: function () { film.pause(); film.removeAttribute('src'); film.load(); film.remove(); }};
        film.addEventListener('loadedmetadata', function () {
          if (filmSeek != null) { film.currentTime = filmSeek; filmSeek = null; }
          playerNote.textContent = 'Click a word to listen; playback pauses just after it. Replay adds the context selected below.'; updatePlayback();
        });
        film.addEventListener('error', function () { playerNote.textContent = 'This browser could not play the local video. You can still review the transcript; try a browser-compatible video format for playback.'; });
      } else if (S.kind === 'yt' && S.held && workspace.open) {
        var generation = ++mediaGeneration; S.mediaLoading = true; frame.textContent = '';
        playerNote.textContent = 'Loading the video for review…';
        window.ParsehTabCapture.embed(frame, S.video, {}).then(function (p) {
          if (generation !== mediaGeneration) { try { p.destroy(); } catch (e) {} return; }
          S.mediaLoading = false; S.player = p;
          playerNote.textContent = 'Click a word to listen from its timestamp. Replay adds the context selected below.'; updatePlayback();
        }, function () {
          if (generation !== mediaGeneration) return;
          S.mediaLoading = false; playerNote.textContent = 'The video could not be loaded. You can still review or reopen this window to try playback again.';
        });
      }
      updatePlayback();
    }

    /* -------------------------------------------------- what is remembered */
    var prefs = load(PREFS), exactWanted = prefs.exact !== false, filledLanguage = '';
    function savePrefs() {
      prefs.models_by_language = prefs.models_by_language || {};
      if (selModel.value) prefs.models_by_language[o.lang().code] = selModel.value;
      prefs.model = selModel.value; prefs.processing = selProc.value; prefs.exact = exactWanted;
      store(PREFS, prefs);
    }
    function persist() {
      store(STATE, {auto: AUTO, wave: WAVE, words: WORDS,
                    job: S.job ? {id: S.job, kind: S.kind, key: S.key, lang: S.lang, model: S.model,
                                  hash: S.startHash} : null});
    }
    var was = load(STATE);

    /* ------------------------------------------------------- what is asked */
    function key(src) { return src.kind + ':' + src.value; }
    function models() {
      var language = o.lang().code;
      return ((S.slice && S.slice.models) || []).filter(function (m) {
        var supported = m.languages || (m.language ? [m.language] : []);
        return m.ready && (!supported.length || supported.indexOf(language) >= 0);
      });
    }
    function modelLabel(id) {
      var m = ((S.slice && S.slice.models) || []).filter(function (x) { return x.id === id; })[0];
      return m ? m.label : String(id || '');
    }
    function card() {
      return ((S.slice && S.slice.processing) || []).filter(function (p) { return p.id === 'cuda'; })[0] || null;
    }
    function autoNow() {
      return ((S.slice && S.slice.processing) || []).filter(function (p) { return p.id === 'auto'; })[0] || null;
    }
    function alignerFor(code) {
      return ((S.slice && S.slice.aligners) || []).filter(function (a) { return a.language === code; })[0] || null;
    }
    function fill() {
      var have = models().map(function (m) { return m.id; });
      var code = o.lang().code, saved = ((S.slice && S.slice.preferences || {}).models_by_language || {})[code];
      var browserSaved = (prefs.models_by_language || {})[code];
      var pick = saved || filledLanguage === code && selModel.value || browserSaved || prefs.model || (S.slice && S.slice.default_model);
      selModel.textContent = '';
      models().forEach(function (m) {
        var specific = m.languages && m.languages.length || m.language;
        var extra = specific ? '' : m.tag;
        var op = el('option', null, m.label + (extra && m.label.indexOf(extra) < 0 ? ' — ' + extra : ''));
        op.value = m.id;
        selModel.appendChild(op);
      });
      var dflt = S.slice && S.slice.default_model;
      selModel.value = have.indexOf(pick) >= 0 ? pick : (have.indexOf(dflt) >= 0 ? dflt : (have[0] || ''));
      filledLanguage = code;
      var c = card(), proc = selProc.value || prefs.processing || 'auto';
      selProc.textContent = '';
      [['auto', 'Automatic — recommended'], ['cpu', 'CPU']].concat(c && c.ready ? [['cuda', 'NVIDIA GPU']] : [])
        .forEach(function (p) {
          var op = el('option', null, p[1]);
          op.value = p[0];
          selProc.appendChild(op);
        });
      selProc.value = ['auto', 'cpu'].concat(c && c.ready ? ['cuda'] : []).indexOf(proc) >= 0 ? proc : 'auto';
    }

    /* ------------------------------------------------------------ painting */
    function say(text, pct) {
      S.said = text || '';
      S.pct = pct == null ? null : pct;
      paint();
    }
    function note(text, kind) {
      noteEl.className = 'note' + (kind ? ' ' + kind : '');
      noteEl.textContent = text || '';
      noteEl.hidden = !text;
      if (notice) notice.textContent = text || '';
    }
    function paint() {
      // Keep the existing inline mobile flow. Normal desktop close/reopen
      // leaves the iframe in place: moving it would reload YouTube's player.
      if (!browserLayout() && inWorkspace && !workspace.open) {
        mediaGeneration++; S.mediaLoading = false;
        if (S.player) { try { S.player.destroy(); } catch (e) {} S.player = null; }
        [how, frame, bar, sayEl].forEach(function (n) { form.appendChild(n); });
        [rec, cancel].forEach(function (n) { actions.appendChild(n); });
        inWorkspace = false;
      }
      var s = S.slice, idle = S.phase === 'idle';
      var src = o.source(), lang = o.lang();
      var ok = !!(s && s.installed && models().length);
      var yt = src.kind === 'yt';
      var noLang = ok && s.languages && s.languages[lang.code] === false;
      var noTab = ok && yt ? tabProblem() : '';
      var mode = !src.kind || !s ? 'off' : !ok ? 'absent'
        : (idle && noLang) ? 'nolang' : (idle && noTab) ? 'notab' : 'form';
      root.hidden = mode === 'off';
      root.setAttribute('data-state', mode === 'form' ? S.phase : mode);
      absent.hidden = mode !== 'absent';
      form.hidden = mode !== 'form';
      why.hidden = mode !== 'nolang' && mode !== 'notab';
      if (mode === 'nolang') {
        why.textContent = 'Speech to text cannot listen for ' + lang.name +
          '. Paste the transcript instead, as always.';
      } else if (mode === 'notab') {
        why.textContent = SAY_NO_TAB + noTab + '. Pasting the transcript works as it always did.';
      }
      if (mode === 'absent' && s) {
        var rt = s.runtime || {};
        setup.href = s.settings || SETTINGS;
        // an install that needs attention says what: "built by an older Parseh"
        var extra = s.installed && !models().length ? ' Install a model for ' + lang.name + ', or a standard multilingual model.' : rt.state === 'ready' ? ' The program is installed, but a model still has to be added.'
          : rt.state && rt.state !== 'absent' && rt.why ? ' ' + rt.why : '';
        absent.firstChild.textContent = SAY_ABSENT + extra;
      }
      if (mode === 'form') {
        var film = src.kind === 'film', c = card(), a = autoNow(), m = selModel.value;
        var info = models().filter(function (x) { return x.id === m; })[0];
        modelNote.textContent = info ? info.hint : '';
        if (info && info.fully_compatible === false) modelNote.textContent += ' Language-specific model; check word timings and the transcript before using it.';
        modelNote.hidden = !info || !info.hint;
        // "Processing: Automatic · currently CPU", said in the person's terms
        var proc = selProc.value, cname = (c && c.name) || 'the NVIDIA graphics card';
        now.textContent = 'Processing: ' + (proc === 'cpu' ? 'CPU'
          : proc === 'cuda' ? 'NVIDIA GPU · ' + cname
          : 'Automatic · currently ' + (a && a.now === 'cuda' ? cname : 'CPU'));
        // a card that is there but not ready is said, once, with what is missing
        gpu.hidden = !(c && !c.ready && c.name && c.why);
        gpu.textContent = gpu.hidden ? '' : c.why;
        busyNote.hidden = !(idle && s.busy);
        busyNote.textContent = busyNote.hidden ? '' : 'Speech to text is busy right now (a transcription or an ' +
          'install is running): starting one now may be refused.';
        langNote.textContent = '';
        // the language's own name is set apart (<bdi>), and the dash stays out of
        // it: inside, a right-to-left name would take the dash to its far side
        // (English is "English — English" in the selector; here it is said once)
        var own = lang.native && lang.native !== lang.name ? lang.native : '';
        langNote.appendChild(document.createTextNode('Listens for ' + lang.name + (own ? ' — ' : '')));
        if (own) langNote.appendChild(el('bdi', null, own));
        langNote.appendChild(document.createTextNode(', the language chosen above.'));
        var aligner = alignerFor(lang.code), exactReady = !!(aligner && aligner.files_ready);
        exact.disabled = !exactReady;
        exact.checked = !!(exactReady && exactWanted);
        exactNote.textContent = exactReady
          ? 'Optional alignment network installed — exact word times are ' + (exact.checked ? 'on.' : 'off.')
          : 'Optional — Whisper still gives approximate word times. Get exact word times for ' + lang.name + ' in Settings.';
        how.textContent = film ? SAY_FILM : S.phase === 'ready' ? SAY_READY
          : (S.phase === 'recording' || S.phase === 'sending') ? SAY_KEEP : SAY_YOUTUBE;
        go.hidden = !idle;
        rec.hidden = S.phase !== 'ready';
        cancel.hidden = !(S.phase === 'starting' || S.phase === 'loading' || S.phase === 'ready' || S.phase === 'recording'
                          || S.phase === 'sending' || S.phase === 'working');
        frame.hidden = inWorkspace ? false : !(S.phase === 'loading' || S.phase === 'ready' || S.phase === 'recording');
        reopen.hidden = idle || workspace.open;
        reopen.textContent = S.held ? 'Resume transcript review' : 'Open transcription';
        back.disabled = captureLive();
        back.title = back.disabled ? 'Finish or cancel the recording before returning to Add Video.' : 'Keep the pending draft and return to Add Video';
        step.textContent = S.secondPass ? 'Whisper second pass' : S.phase === 'correcting' ? 'Review tool running' : S.held ? 'Review transcript' : idle ? 'Speech to text' : 'Whisper transcription';
        pending.hidden = !!S.held;
        pendingHeading.textContent = S.secondPass ? 'Whisper second pass' : S.kind === 'yt' && captureLive() ? 'Record this YouTube video' : 'Whisper is transcribing';
        notice.textContent = noteEl.textContent;
        var live = S.phase !== 'idle' && S.said !== '';
        sayEl.hidden = !live || inWorkspace && !!S.held;
        sayEl.textContent = live ? S.said : '';
        bar.hidden = !!S.secondPass || !(S.phase === 'recording' || S.phase === 'sending' || S.phase === 'working' || S.phase === 'correcting');
        bar.classList.toggle('wait', S.pct == null);
        bar.firstChild.style.width = S.pct == null ? '' : Math.max(0, Math.min(100, S.pct)) + '%';
        if (S.pct == null) bar.removeAttribute('aria-valuenow');
        else bar.setAttribute('aria-valuenow', String(Math.round(S.pct)));
        secondProgress.hidden = !S.secondPass;
        if (S.secondPass) {
          var done = S.secondPass.done || 0, total = S.secondPass.total || 0;
          secondLabel.textContent = 'Whisper second pass · ' + done + ' / ' + total + ' suspect words processed';
          secondBar.setAttribute('aria-valuemax', String(total || 1));
          secondBar.setAttribute('aria-valuenow', String(done));
          secondBar.setAttribute('aria-valuetext', done + ' of ' + total + ' suspect words processed');
          secondBar.firstChild.style.width = (total ? 100 * done / total : 100) + '%';
        }
        reviewRoot.hidden = !S.held;
        reviewMobile.hidden = !S.held;
      }
      // what the box holds, and whose it is
      var box = o.transcript();
      tied.hidden = !AUTO || !box.trim();
      if (!tied.hidden) {
        tied.textContent = hash(box) === AUTO.hash
          ? 'The transcript in the box was made by speech to text (' + modelLabel(AUTO.model) +
            '). Read it through: it is yours to edit before the video is added.'
          : 'The transcript in the box began as speech to text (' + modelLabel(AUTO.model) +
            ') and has been edited since.';
      }
    }

    /* ------------------------------------------------- locking while a job runs */
    function targets() {
      var out = (o.lock || []).map(function (sel) { return document.querySelector(sel); }).filter(Boolean);
      return out.concat([selModel, selProc, exact]);
    }
    function lock(on) {
      var list = targets();
      if (on) LOCKED = list.map(function (e) { return [e, e.value, e.checked]; });
      else LOCKED = null;
      list.forEach(function (e) {
        e.classList.toggle('stt-locked', on);
        if (on) e.setAttribute('aria-disabled', 'true'); else e.removeAttribute('aria-disabled');
        if (e.tagName === 'INPUT') e.readOnly = on;
      });
    }
    // A control that is locked still looks like one, so it answers: the click
    // or the key is turned away, said once, and a value that was changed by
    // any other means is put back.  Not `disabled`: a disabled control answers
    // nothing at all, and says nothing about why.
    function turnedAway(e) {
      if (!LOCKED) return;
      var t = e.target;
      if (!t || !t.closest) return;
      var hit = targets().some(function (x) { return x === t || x.contains(t); });
      if (!hit) return;
      if (e.type === 'keydown' && (e.key === 'Tab' || e.key === 'Shift' || e.key === 'Escape')) return;
      // a text box that is read-only can still be clicked into, and its words
      // selected and copied; only a key that would change it, or a paste, is
      // an attempt
      if (t.tagName === 'INPUT' && t.type !== 'checkbox') {
        if (e.type === 'mousedown' || e.type === 'click') return;
        if (e.type === 'keydown' && !(e.key.length === 1 && !e.ctrlKey && !e.metaKey)
            && e.key !== 'Backspace' && e.key !== 'Delete') return;
      }
      if (e.type === 'change' || e.type === 'input') {
        LOCKED.forEach(function (p) { if (p[0] === t) { t.value = p[1]; t.checked = p[2]; } });
      }
      e.preventDefault();
      e.stopPropagation();
      if (Date.now() - lastToast > 1500) { lastToast = Date.now(); toast(SAY_LOCKED, true); }
    }
    ['mousedown', 'click', 'keydown', 'paste', 'change', 'input'].forEach(function (type) {
      document.addEventListener(type, turnedAway, true);
    });

    /* ------------------------------------------------------- ties and drops */
    function drop(what) {
      AUTO = null;
      persist();
      note('The transcript in the box is no longer tied to speech to text: the ' + what + ' changed. It ' +
           'stays as it is, and a new transcription asks before it replaces it.');
    }
    function sourceChanged() {
      invalidatePending('video');
      var k = key(o.source());
      if (AUTO && AUTO.source !== k) drop('video');
      if (WAVE && WAVE.source !== k) { WAVE = null; persist(); }
      if (WORDS && WORDS.source !== k) { WORDS = null; persist(); }
      paint();
    }
    function langChanged() {
      invalidatePending('language');
      if (AUTO && AUTO.lang !== o.lang().code) drop('language');
      if (WORDS && WORDS.lang !== o.lang().code) { WORDS = null; persist(); }
      fill(); paint();
    }
    function modelChanged() {
      invalidatePending('Whisper model');
      savePrefs();
      if (AUTO && AUTO.model !== selModel.value) drop('model');
      if (selModel.value && S.phase === 'idle') {
        var code = o.lang().code, model = selModel.value;
        if (S.slice) {
          S.slice.preferences = S.slice.preferences || {};
          S.slice.preferences.models_by_language = S.slice.preferences.models_by_language || {};
          S.slice.preferences.models_by_language[code] = model;
        }
        ask('/settings/api/speech/select-model', {language:code,model:model}, DEADLINE_MS).then(function (r) {
          if (!r.j.ok) throw new Error(r.j.error || 'The model preference could not be saved.');
          if (S.slice && prefs.models_by_language[code] === model) S.slice.preferences.models_by_language[code] = model;
        }).catch(function () { note('This model is selected for this transcription. Its preference could not be saved on the host.', 'warn'); });
      }
      paint();
    }
    selModel.addEventListener('change', modelChanged);
    selProc.addEventListener('change', function () { savePrefs(); paint(); });
    exact.addEventListener('change', function () { exactWanted = exact.checked; savePrefs(); paint(); });

    /* ------------------------------------------------------------ the job */
    function post(name, body, ms, outer) { return ask(route(name), body, ms, outer); }
    function stopTimers() {
      clearTimeout(S.timer);
      clearTimeout(S.readyTimer);
      S.timer = S.readyTimer = 0;
    }
    // Everything of a job that is over, put away: no timer, no frame, no
    // player, no tab left shared, nothing remembered, the controls free.
    function tidy() {
      stopTimers();
      S.run++;
      mediaGeneration++; S.mediaLoading = false;
      var p = S.player;
      S.player = null;
      S.rec = null;
      if (S.abort) { try { S.abort.abort(); } catch (e) {} S.abort = null; }
      if (p) {
        try { p.pauseVideo(); } catch (e) {}
        try { if (p.destroy) p.destroy(); } catch (e) {}
      }
      frame.textContent = '';
      S.job = S.kind = S.key = S.video = '';
      S.sent = 0;
      S.secondPass = null;
      S.phase = 'idle';
      selectedWord = selectedCaption = null;
      selectedLine.textContent = 'Select a transcript word to jump to its time.';
      selectedTime.textContent = '';
      closeWorkspace(true);
      updatePlayback();
      lock(false);
      persist();
    }
    function cancelServer(job) {
      if (!job) return Promise.resolve();
      return post('cancel', {job: job}, 6000).then(function () {}, function () {});
    }
    // A job that ended badly: the sentence, the box left exactly as it was.
    function fail(run, text, tell) {
      if (run !== S.run) return;
      var job = S.job;
      S.held = null; REVIEW.clear();
      tidy();
      if (tell !== false) cancelServer(job);
      note(text || 'Transcription failed.', 'bad');
      paint();
    }
    function begin() {
      if (S.phase !== 'idle') return;
      var src = o.source(), lang = o.lang(), film = src.kind === 'film';
      if (!src.value) {
        toast(film ? 'name the film on this machine' : 'paste the URL', true);
        if (o.focusSource) o.focusSource();
        return;
      }
      var model = selModel.value;
      if (!model) return;
      var box = o.transcript();
      // NEVER OVER A PERSON'S WORDS WITHOUT ASKING: before anything is
      // recorded or uploaded, not after an hour of it
      if (box.trim() && (!AUTO || hash(box) !== AUTO.hash) && !confirmOver(SAY_START_OVER)) return;
      note('');
      S.held = null; REVIEW.clear();
      var run = ++S.run;
      S.kind = src.kind;
      S.key = key(src);
      S.lang = lang.code;
      S.model = model;
      S.startHash = hash(o.transcript());
      S.phase = 'starting';
      playerNote.textContent = film ? 'Loading the local video…' : 'Start recording when the video is ready. Playback controls become available after recording.';
      lock(true);
      say('Starting…');
      openWorkspace();
      var body = {source: film ? 'film' : 'youtube', lang: lang.code, model: model,
                  processing: selProc.value, exact: !!exact.checked};
      if (film) body.path = src.value; else body.url = src.value;
      post('start', body).then(function (r) {
        if (run !== S.run) { if (r.j && r.j.job) cancelServer(r.j.job); return; }
        var j = r.j;
        if (!j.ok) {
          tidy();
          note(j.error + (j.code === 'busy' ? ' Wait for it to finish, or stop it from the page that started it.' : ''),
               'bad');
          if (j.code === 'not-installed' || j.code === 'no-model') refresh();
          paint();
          return;
        }
        S.job = j.job;
        S.video = j.video_id || '';
        persist();
        if (film) { S.phase = 'working'; ensureReviewPlayer(); say(j.say || 'Getting ready…'); poll(run); return; }
        S.phase = 'loading';
        say('Loading the video…');
        window.ParsehTabCapture.embed(frame, S.video, {}).then(function (player) {
          if (run !== S.run) { try { if (player.destroy) player.destroy(); } catch (e) {} return; }
          S.player = player;
          S.phase = 'ready';
          say('');
          // the computer gives up on a recording that never starts; so does this page, first
          S.readyTimer = setTimeout(function () { fail(run, SAY_GIVE_UP); }, READY_MS);
        }, function (err) {
          fail(run, (err && err.message ? err.message : 'The video could not be loaded') +
                    (/[.!?]$/.test((err && err.message) || '') ? '' : '.'));
        });
      }, function () {
        if (run !== S.run) return;
        tidy();
        note('Parseh did not answer, so nothing was started.', 'bad');
        paint();
      });
    }

    // THE RECORDING.  Called from the click itself: the browser shares a tab
    // only in answer to one, and the video was put in its frame before it.
    function record() {
      if (S.phase !== 'ready' || !S.player) return;
      var TC = window.ParsehTabCapture, run = S.run, job = S.job;
      clearTimeout(S.readyTimer);
      var marks = [], peaks = null, ctl = new AbortController(), started = false;
      S.abort = ctl;
      S.sent = 0;
      S.phase = 'recording';
      say('Waiting for you to share this tab…');
      var r = TC.record({
        player: S.player, wave: true, pcm: true, keepShare: false, unmute: true,
        onStart: function () { started = true; if (run === S.run) say('Recording 0:00…', 0); },
        onProgress: function (sec, total) {
          if (run !== S.run) return;
          say('Recording ' + clock(sec) + ' / ' + clock(total) + '…', total > 0 ? 100 * sec / total : null);
        },
        onChunk: function (pcm, offset, signal) { return sendPiece(run, pcm, offset, signal); },
        onMark: function (frameNo, sec) { marks.push([frameNo, sec]); },
        onPeaks: function (p, rate) { peaks = {rate: rate, peaks: p}; }
      });
      S.rec = r;
      r.promise.then(function (res) {
        if (run !== S.run) return;
        if (res.reason === 'stalled') { fail(run, SAY_STALLED); return; }
        if (res.reason !== 'ended') { fail(run, 'The recording ended early, so nothing was written.'); return; }
        finishRecording(run, job, marks, peaks, ctl);
      }, function (err) {
        if (run !== S.run) return;
        // A share that was refused, or came without its sound, or a browser that
        // could not open its 16 kHz half: nothing has played yet, so the video
        // and the job are still good, and the button can be pressed again.
        if (!started && S.player) {
          S.rec = null;
          S.abort = null;
          S.phase = 'ready';
          note(whyCapture(err), 'bad');
          say('');
          S.readyTimer = setTimeout(function () { fail(run, SAY_GIVE_UP); }, READY_MS);
          return;
        }
        fail(run, whyCapture(err));
      });
    }
    // One piece of the sound, sent and answered before the next is handed over.
    // A piece sent twice is written once by the computer, so one that timed out
    // is simply sent again.  A gap -- the computer holding LESS than this piece
    // starts at -- means an earlier piece is missing, and only the piece in hand
    // is kept here: it is said, and the recording stopped.
    function sendPiece(run, pcm, offset, signal) {
      var tries = 0;
      function once(data, at) {
        if (run !== S.run) return Promise.reject(new Error('The recording was stopped.'));
        var url = route('audio') + '?job=' + encodeURIComponent(S.job) + '&offset=' + at;
        return ask(url, data, PIECE_DEADLINE_MS, signal).then(function (r) {
          var j = r.j;
          if (j.ok) { S.sent = Math.max(S.sent, at + data.length); return; }
          if (j.code === 'gap' && typeof j.have === 'number') {
            var from = j.have - offset;
            if (from >= 0 && from < pcm.length && tries++ < PIECE_TRIES) return once(pcm.subarray(from), j.have);
            throw new Error('A piece of the recording went missing on its way, so it was stopped.');
          }
          throw new Error(j.error || 'The recording could not be sent.');
        }, function (e) {
          if (signal && signal.aborted) throw e;
          if (++tries < PIECE_TRIES) {
            return new Promise(function (ok) { setTimeout(ok, 600 * tries); }).then(function () { return once(data, at); });
          }
          throw new Error('Parseh did not answer while the recording was being sent, so it was stopped.');
        });
      }
      return once(pcm, offset);
    }
    function finishRecording(run, job, marks, peaks, ctl) {
      // The capture released its tab share. Keep its paused video for review.
      if (S.player) { try { S.player.pauseVideo(); } catch (e) {} }
      playerNote.textContent = 'The recording is complete. Playback is available while Whisper prepares the transcript.';
      S.phase = 'sending';
      say('Sending the end of the recording…', null);
      // what is asked again where the computer said nothing (each of these can be
      // said twice: the marks replace what was sent, and a last piece sent again
      // is taken), until it has been three times
      function again(fn) {
        var n = 0;
        return (function go() {
          return fn().then(null, function (e) {
            if (++n >= PIECE_TRIES || ctl.signal.aborted) throw e;
            return new Promise(function (ok) { setTimeout(ok, 600 * n); }).then(go);
          });
        })();
      }
      // a refusal is thrown as its sentence; a computer that says nothing, as
      // that; `needed: false` is for what nothing depends on
      function step(name, body, needed, ms) {
        return again(function () { return post(name, body, ms, ctl.signal); }).then(function (r) {
          if (r.j.ok || !needed) return r;
          throw new Error(r.j.error || 'The recording could not be sent.');
        }, function () {
          if (!needed) return {j: {ok: false}};
          throw new Error('Parseh did not answer while the recording was being sent.');
        });
      }
      // marks first (they put the sound on the video's own clock), then the shape
      // of the sound (nothing depends on it: a video with no waveform is still a
      // video), and the last piece -- empty, the recording is all there -- seals it
      step('marks', {job: job, marks: marks}, true, DEADLINE_MS).then(function () {
        return peaks ? step('wave', {job: job, rate: peaks.rate, peaks: peaks.peaks}, false, 4 * DEADLINE_MS) : null;
      }).then(function () {
        var url = route('audio') + '?job=' + encodeURIComponent(job) + '&offset=' + S.sent + '&last=1';
        return again(function () { return ask(url, new Uint8Array(0), DEADLINE_MS * 2, ctl.signal); });
      }).then(function (r) {
        if (run !== S.run) return;
        if (!r.j.ok) { fail(run, r.j.error || 'The recording could not be sealed.'); return; }
        S.phase = 'working';
        say('Audio captured.', null);
        poll(run);
      }, function (e) {
        if (run !== S.run) return;
        fail(run, (e && e.message) || 'The recording could not be sent.');
      });
    }

    // THE COMPUTER LISTENING: asked how it is, over and over, each ask with a
    // deadline of its own.  A computer that says nothing is waited for and said
    // so; only what it says ends a job.
    function poll(run) {
      var misses = 0;
      (function tick() {
        if (run !== S.run) return;
        post('status', {job: S.job}).then(function (r) {
          if (run !== S.run) return;
          var j = r.j;
          misses = 0;
          if (S.phase === 'working' && noteEl.textContent === SAY_SILENT) note('');
          if (!j.ok) { fail(run, j.error || 'That transcription is not here any more.', false); return; }
          S.secondPass = j.state === 'whisper-second-pass' || j.correction && j.correction.state === 'running' && j.correction.task === 'whisper-second' ? j.second_pass : null;
          if (j.state === 'done' || j.state === 'awaiting-review-choice') { finishJob(run); return; }
          if (j.state === 'failed') { fail(run, j.error, false); return; }
          if (j.state === 'cancelled') { fail(run, 'The transcription was cancelled.', false); return; }
          if (S.phase === 'correcting' && S.held) {
            if (!pendingCurrent()) { discardPending(); return; }
            var c = j.correction || {};
            var elapsed = c.started ? Math.floor(Date.now() / 1000 - c.started) : 0;
            REVIEW.progress(j.say + (j.pct == null ? ' Elapsed: ' + clock(elapsed) + '.' : ''));
            if (c.response_count && c.response_count !== S.responses) {
              S.responses = c.response_count;
              post('result', {job: S.job}).then(function (reply) {
                if (run !== S.run || !S.held || S.phase !== 'correcting' || !reply.j.ok) return;
                var review = reply.j.review || {};
                REVIEW.diagnostics(review.diagnostics, review.diagnostics_clipped);
              }, function () {});
            }
          }
          say(j.say, j.pct);
          S.timer = setTimeout(tick, POLL_MS);
        }, function () {
          if (run !== S.run) return;
          if (++misses >= 3) note(SAY_SILENT, 'warn');
          S.timer = setTimeout(tick, POLL_MS);
        });
      })();
    }
    // The words are asked for once the job says it is done.  A computer that says
    // nothing THEN is waited for, not given up on: the job is done, and pressing
    // Transcribe again would make a recording of an hour for nothing.
    function finishJob(run, misses) {
      post('result', {job: S.job}).then(function (r) {
        if (run !== S.run) return;
        if (!r.j.ok) { fail(run, r.j.error || 'The transcript could not be read.', false); return; }
        deliver(run, r.j);
      }, function () {
        if (run !== S.run) return;
        if ((misses || 0) + 1 >= 3) note(SAY_SILENT, 'warn');
        S.timer = setTimeout(function () { finishJob(run, (misses || 0) + 1); }, POLL_MS * 2);
      });
    }
    // Every ASR result is pending. No route inserts text without the Use click.
    function pendingCurrent() {
      return S.held && S.held.t.key === key(o.source()) && S.held.t.lang === o.lang().code &&
        S.held.t.model === selModel.value && S.held.t.startHash === hash(o.transcript());
    }
    function discardPending() {
      var job = S.job;
      S.held = null; REVIEW.clear(); tidy(); cancelServer(job);
      note('The source, language, Whisper model or transcript box changed. The stale review was discarded; the box was left untouched.', 'warn'); paint();
    }
    function invalidatePending() { if (S.held && !pendingCurrent()) discardPending(); }
    function deliver(run, res) {
      if (S.key !== key(o.source()) || S.lang !== o.lang().code || S.model !== selModel.value || S.startHash !== hash(o.transcript())) {
        discardPending(); return;
      }
      stopTimers(); lock(false);
      var t = {job: S.job, key: S.key, lang: S.lang, model: S.model, startHash: S.startHash};
      S.held = {res: res, t: t};
      var review = res.review || {};
      if (review.correction && review.correction.code === 'source-changed') { discardPending(); return; }
      S.secondPass = null;
      S.phase = 'review';
      say('Review and edit the transcript. Try any tool, then choose Use this transcript.');
      ask('/settings/api/llm/status', {}).then(function (r) {
        if (run !== S.run || !S.held) return;
        LLM = r.j && r.j.ok ? r.j : {configured: false};
        REVIEW.show(S.held.res, S.phase, res.review && res.review.evidence ? LLM : {configured: false});
      }, function () {
        if (run === S.run && S.held) REVIEW.show(S.held.res, S.phase, {configured: false});
      });
      REVIEW.show(res, S.phase, res.review && res.review.evidence ? LLM : {configured: false});
      ensureReviewPlayer();
      paint();
    }
    function retryReview(wordIds, skill, task, options) { if (wordIds.length) chooseReview(task === 'likelihood' ? 'likelihood' : 'llm', wordIds, skill, task, options); }
    function externalReview(action, values) {
      if (!S.held || (S.phase !== 'choice' && S.phase !== 'review') || !pendingCurrent()) {
        return Promise.reject(new Error('This review changed. Prepare a new Whisper result.'));
      }
      if (action === 'keep-alive') {
        return post('external-action', Object.assign({job: S.job, source_sha256: S.held.res.review.evidence.source_sha256, action: action}, values || {}))
          .then(function (r) { if (!r.j.ok) throw new Error(r.j.error); });
      }
      var run = S.run, held = S.held, attempt = S.reviewAttempt = (S.reviewAttempt || 0) + 1;
      var body = Object.assign({job: S.job, source_sha256: held.res.review.evidence.source_sha256}, values || {});
      var name = action === 'start' ? 'external-start' : 'external-action';
      if (action !== 'start') body.action = action;
      return post(name, body).then(function (r) {
        if (run !== S.run || attempt !== S.reviewAttempt || S.held !== held || !pendingCurrent()) {
          throw new Error('This review changed; the returned answer was discarded.');
        }
        if (!r.j.ok) {
          if (r.j.code === 'source-changed') discardPending();
          throw new Error(r.j.error);
        }
        S.held.res = r.j;
        var external = r.j.review && r.j.review.external;
        S.phase = 'review';
        say(external && !external.finished ? 'Copy the prompt to your chosen chatbot, then paste its answer here.' : 'Review the proposals, then choose Use this transcript.');
        paint();
        return {res: r.j, state: external && !external.finished ? 'external' : S.phase, connection: LLM};
      });
    }
    function chooseReview(mode, wordIds, skill, task, options) {
      if (!S.held || (S.phase !== 'choice' && S.phase !== 'review')) return;
      if (!pendingCurrent()) { discardPending(); return; }
      var evidence = S.held.res.review && S.held.res.review.evidence;
      if (!evidence) {
        if (mode !== 'whisper') return;
        S.phase = 'review'; REVIEW.show(S.held.res, 'review', {configured: false}); paint(); return;
      }
      var run = S.run, attempt = S.reviewAttempt = (S.reviewAttempt || 0) + 1;
      task = task || 'suspect';
      var numerical = mode === 'likelihood';
      var second = mode === 'whisper-second';
      if (!wordIds) REVIEW.resetProposals();
      S.responses = 0;
      S.phase = mode === 'llm' || numerical || second ? 'correcting' : 'choosing';
      S.pct = null;
      REVIEW.show(S.held.res, 'correcting', LLM);
      say(second ? 'Preparing Whisper second pass…' : numerical ? 'Loading the standalone likelihood model…' : 'Preparing the saved review model…');
      paint();
      var started = Date.now(), preparing = mode === 'llm';
      var prepareTimer = preparing ? setInterval(function () {
        if (attempt !== S.reviewAttempt || run !== S.run || !S.held) { clearInterval(prepareTimer); return; }
        REVIEW.progress('Preparing the saved model profile. Elapsed: ' + clock(Math.floor((Date.now() - started) / 1000)) + '.');
      }, 1000) : null;
      var body = {job: S.job, source_sha256: evidence.source_sha256,
        task: task,
        instruction_mode: skill ? 'skill' : 'prompt',
        connection_id: mode === 'llm' && LLM ? LLM.connection_id : null};
      // a reasoning workspace is handed to the model whole unless the person asked for small regions
      if (task === 'workspace' && options && options.divide === true) body.divide = true;
      if (wordIds) body.word_ids = wordIds; else body.mode = mode;
      if (numerical) {
        body = {job: S.job, source_sha256: evidence.source_sha256, revision: LLM && LLM.likelihood && LLM.likelihood.revision};
        if (wordIds) body.word_ids = wordIds;
        if (options && typeof options.phonetic_filter === 'boolean') body.phonetic_filter = options.phonetic_filter;
      }
      if (second) {
        body = {job:S.job, source_sha256:evidence.source_sha256};
        if (wordIds) body.word_ids = wordIds;
      }
      var prepared = second ? post('whisper-second-pass', body) : numerical ? post('review-likelihood', body) : mode === 'llm' ? ask('/settings/api/llm/review-prepare', {task: task, connection_id: body.connection_id}, 310000).then(function (r) {
        clearInterval(prepareTimer);
        if (attempt !== S.reviewAttempt || run !== S.run || !S.held || S.phase !== 'correcting' || !pendingCurrent()) return null;
        if (!r.j.ok) return r;
        LLM = r.j; body.connection_id = LLM.connection_id;
        return post(wordIds ? 'retry-review' : 'review', body);
      }) : post(wordIds ? 'retry-review' : 'review', body);
      prepared.then(function (r) {
        clearInterval(prepareTimer);
        if (run !== S.run || !S.held) return;
        if (attempt !== S.reviewAttempt) return;
        if (!r || S.phase !== 'correcting' && S.phase !== 'choosing') return;
        if (!r.j.ok) {
          if (r.j.code === 'source-changed') { discardPending(); return; }
          S.phase = 'review'; note(r.j.error, 'warn');
          if (r.j.code === 'settings-changed' || r.j.code === 'llm-unconfigured') {
            LLM = null;
            ask('/settings/api/llm/status', {}).then(function (fresh) {
              if (run !== S.run || !S.held || S.phase !== 'review') return;
              LLM = fresh.j && fresh.j.ok ? fresh.j : {configured: false};
              REVIEW.show(S.held.res, 'review', LLM);
            }, function () {});
          }
          REVIEW.show(S.held.res, 'review', LLM); paint(); return;
        }
        if (mode === 'llm' || numerical || second) { poll(run); } else finishJob(run);
      }, function () {
        clearInterval(prepareTimer);
        if (attempt !== S.reviewAttempt) return;
        if (run !== S.run || !S.held) return;
        // The start may have reached the host: recover through status, never
        // resend a generation request because its answer was lost.
        note(SAY_SILENT, 'warn'); poll(run);
      });
    }
    function saveReviewDraft(draft) {
      if (!S.held || !pendingCurrent()) return Promise.reject(new Error('The review source changed.'));
      draft.browser = {transcript: o.transcript(), hash: S.startHash};
      return post('save-draft', {job:S.job, source_sha256:S.held.res.review.evidence.source_sha256,
        generation:S.phase === 'correcting' ? undefined : S.held.res.review.generation || 0, draft:draft}).then(function (r) {
        if (!r.j.ok) throw new Error(r.j.error || 'The draft could not be saved.');
      });
    }
    function pauseReview() {
      var run = S.run;
      var stopped = S.phase === 'correcting' ? post('cancel-review',{job:S.job}).then(function (r) {
        if (!r.j.ok) throw new Error(r.j.error || 'The review could not be stopped. Keep this page open and try again.');
      }) : Promise.resolve();
      return stopped.then(function () {
        if(run!==S.run)return;
        S.held=null; REVIEW.clear();tidy();
        note('Review saved. Continue it from Videos or the pending transcription button.');refreshPending();paint();
      });
    }
    var pendingButton = button('Continue pending transcription', 'stt_continue_pending', 'wbtn small quiet');
    pendingButton.hidden=true;pendingButton.setAttribute('data-layout','browser');root.appendChild(pendingButton);
    var pendingList=el('div','stt-pending-list');pendingList.hidden=true;root.appendChild(pendingList);
    function refreshPending() {
      return post('pending',{}).then(function(r){
        if(!r.j.ok)return; pendingButton.hidden=!r.j.pending.length;pendingList.textContent='';
        r.j.pending.forEach(function(item){var row=el('div','stt-pending-item'),b=button(item.title+' · '+item.lang,'','wbtn small quiet');b.addEventListener('click',function(){resumeSaved(item.job);});row.appendChild(b);var discard=button('Discard saved review','','wbtn small quiet');discard.addEventListener('click',function(){if(confirmOver('Discard this saved transcription review?'))post('cancel',{job:item.job}).then(function(answer){if(answer.j.ok)refreshPending();else note(answer.j.error,'warn');});});row.appendChild(discard);pendingList.appendChild(row);});
      },function(){});
    }
    pendingButton.addEventListener('click',function(){pendingList.hidden=!pendingList.hidden;refreshPending();});
    function resumeSaved(token) {
      if(S.phase!=='idle'){note('Pause or finish this review before opening another.','warn');return;}
      post('resume',{job:token}).then(function(r){
        if(!r.j.ok){note(r.j.error,'warn');return;}
        var saved=r.j, browser=saved.draft.browser || {};
        if(o.transcript().trim() && o.transcript() !== (browser.transcript || '') && !confirmOver('Open this saved review and restore its Add Video draft?'))return;
        if(!o.restorePending){note('Open the matching source and language before resuming.','warn');return;}
        o.restorePending(saved.source,saved.lang,browser.transcript || '');
        var src=o.source();selModel.value=saved.model;
        S.job=saved.job;S.kind=src.kind;S.key=key(src);S.lang=saved.lang;S.model=saved.model;S.startHash=hash(o.transcript());
        S.video=saved.source.id || '';S.phase='working';var run=++S.run;persist();openWorkspace();
        pendingList.hidden=true;finishJob(run);
        try {var link=new URL(location.href);link.searchParams.delete('pending');history.replaceState(null,'',link);}catch(e){}
      },function(){note('Parseh did not answer. The saved review stays on disk.','warn');});
    }
    function cancelReview() {
      S.reviewAttempt = (S.reviewAttempt || 0) + 1;
      if (S.phase === 'correcting' || S.phase === 'choosing') {
        var run = S.run;
        post('cancel-review', {job: S.job}).then(function (r) {
          if (run !== S.run) return;
          if (r.j.ok) finishJob(run); else note(r.j.error, 'warn');
        }, function () { note(SAY_SILENT, 'warn'); });
        return;
      }
      var job = S.job; S.held = null; REVIEW.clear(); tidy(); cancelServer(job);
      note('Review cancelled. The transcript box was left untouched.'); paint();
    }
    function useReview(decisions, manualEdits) {
      manualEdits = manualEdits || {};
      if (!S.held || S.phase !== 'review') return;
      if (!pendingCurrent()) { discardPending(); return; }
      if (o.transcript().trim() && (o.transcript() !== S.held.res.text || Object.keys(decisions).length || Object.keys(manualEdits).length) && !confirmOver('Replace the transcript in the box with this reviewed transcript? What is written there now is lost.')) return;
      var held = S.held, run = S.run;
      var evidence = held.res.review && held.res.review.evidence;
      REVIEW.disableUse(true);
      var request = evidence ? post('use', {job: S.job, source_sha256: evidence.source_sha256, decisions: decisions, manual_edits: manualEdits})
        : Promise.resolve({j: held.res});
      request.then(function (r) {
        if (run !== S.run || S.held !== held) return;
        if (!pendingCurrent()) { discardPending(); return; }
        if (!r.j.ok) {
          if (r.j.code === 'source-changed') { discardPending(); return; }
          note(r.j.error, 'warn'); REVIEW.disableUse(false);
          if (r.j.code === 'stale-review') finishJob(run);
          return;
        }
        if (r.j.words && r.j.words.timings_stale) WORDS = null;
        S.held = null; REVIEW.clear(); tidy(); apply(r.j, held.t);
      }, function () {
        if (run !== S.run) return;
        note('Parseh did not answer. The review is still pending and the box has not changed.', 'warn'); REVIEW.disableUse(false);
      });
    }
    function apply(res, t) {
      S.held = null;
      o.setTranscript(res.text);
      AUTO = {source: t.key, lang: t.lang, model: t.model, hash: hash(o.transcript())};
      if (res.wave && res.wave.held) WAVE = {job: t.job, source: t.key};
      if (res.words && res.words.held) WORDS = {job: t.job, source: t.key, lang: t.lang};
      persist();
      o.invalidate();
      var n = res.captions;
      var out = 'The transcript is in the box' + (n ? ': ' + n + ' caption' + (n === 1 ? '' : 's') : '') +
                '. Read it through and edit it as you like — the video has not been added.';
      var extra = (res.notes || []).length ? ' ' + res.notes.join(' ') : '';
      note(out + extra + (res.warning ? ' ' + res.warning : ''), res.warning ? 'warn' : 'good');
      paint();
    }


    /* ----------------------------------------------- Cancel, and leaving */
    function stop(text) {
      if (S.phase === 'idle' || S.phase === 'stopping') return;
      var job = S.job, r = S.rec;
      S.phase = 'stopping';
      S.run++;
      stopTimers();
      if (S.abort) { try { S.abort.abort(); } catch (e) {} }
      say('Stopping…');
      (r ? r.cancel() : Promise.resolve()).then(function () {
        return cancelServer(job);
      }).then(function () {
        tidy();
        note(text || 'The transcription was cancelled. The transcript in the box was not touched.');
        paint();
      });
    }
    go.addEventListener('click', begin);
    rec.addEventListener('click', record);
    cancel.addEventListener('click', function () { stop(); });
    // a page left during a recording ends it: the sound would go on arriving from nowhere
    window.addEventListener('pagehide', function () {
      if(S.held && pendingCurrent() && navigator.sendBeacon){var draft=REVIEW.snapshot();draft.browser={transcript:o.transcript(),hash:S.startHash};try{navigator.sendBeacon(route('save-draft'),new Blob([JSON.stringify({job:S.job,source_sha256:S.held.res.review.evidence.source_sha256,generation:S.phase === 'correcting' ? undefined : S.held.res.review.generation || 0,draft:draft})],{type:'application/json'}));}catch(e){}}
      var live = S.phase === 'loading' || S.phase === 'ready' || S.phase === 'recording' || S.phase === 'sending';
      if (!live || S.kind !== 'yt' || !S.job || !navigator.sendBeacon) return;
      try { navigator.sendBeacon(route('cancel'), new Blob([JSON.stringify({job: S.job})], {type: 'application/json'})); }
      catch (e) {}
      forget(STATE);
    });
    document.addEventListener('visibilitychange', function () {
      if (S.phase !== 'recording') return;
      if (document.hidden) note(SAY_HIDDEN, 'warn'); else if (noteEl.textContent === SAY_HIDDEN) note('');
    });

    /* ------------------------------------------------- the computer's word */
    function refresh() {
      return ask(SLICE, {}, DEADLINE_MS).then(function (r) { return r.j && r.j.ok ? r.j : null; },
                                              function () { return null; }).then(function (s) {
        // asked again while it is being used, it would only change under a job's feet
        if (S.phase !== 'idle') return;
        if (s || !S.slice) S.slice = s;
        if (S.slice) fill();
        paint();
      });
    }
    function again() { if (document.visibilityState !== 'hidden' && S.phase === 'idle') refresh(); }
    window.addEventListener('focus', again);
    document.addEventListener('visibilitychange', again);

    /* ----------------------------------------- what a reload finds again */
    // A job the computer is still listening for is taken up again; a recording
    // cannot be (its tab share and its video are gone with the page), so it is
    // let go, and said.
    function resume() {
      var src = o.source(), lang = o.lang(), j = was.job;
      if (!j || !j.id) return;
      post('status', {job: j.id}).then(function (r) {
        var s = r.j;
        function over(text, kind) {
          if (text) note(text, kind);
          if (text && (s.state === 'awaiting-audio' || s.state === 'receiving')) cancelServer(j.id);
          S.job = '';
          persist();
          paint();
        }
        if (!s.ok || s.state === 'cancelled') { over(''); return; }
        if (s.state === 'failed') { over(s.error || 'The earlier transcription failed.', 'bad'); return; }
        var same = j.key === key(src) && j.lang === lang.code && S.phase === 'idle';
        if (!same) { over('A transcription that was running for another video or language was stopped.'); return; }
        if (s.state === 'awaiting-audio' || s.state === 'receiving') { over(SAY_LEFT); return; }
        var run = ++S.run;
        S.job = j.id; S.kind = src.kind; S.key = j.key; S.lang = j.lang; S.model = j.model;
        S.video = s.video_id || '';
        S.startHash = j.hash || '';
        S.phase = 'working';
        lock(true);
        say(s.say, s.pct);
        if (s.state === 'done' || s.state === 'awaiting-review-choice') finishJob(run); else poll(run);
      }, function () { S.job = ''; persist(); });
    }

    // What the page was a moment ago: the tie of the box to its video (only if
    // it is still that video's), and the waveform held for it.  A running job
    // is asked about once the computer has said what it has.
    (function restore() {
      var k = key(o.source());
      AUTO = was.auto && was.auto.source === k ? was.auto : null;
      WAVE = was.wave && was.wave.source === k ? was.wave : null;
      WORDS = was.words && was.words.source === k ? was.words : null;
    })();
    lock(false);
    refresh().then(function(){refreshPending();var saved=new URLSearchParams(location.search).get('pending');if(saved)resumeSaved(saved);else resume();});
    return {
      sourceChanged: sourceChanged,
      langChanged: langChanged,
      modelChanged: modelChanged,
      redraw: function () { invalidatePending(); paint(); },
      busy: function () { return S.phase !== 'idle'; },
      // "Edit the transcript…" opens a video of its own: two would both be heard
      guardEdit: function () {
        return o.source().kind === 'yt' && (S.phase === 'loading' || S.phase === 'ready' || S.phase === 'recording')
          ? 'the video in the frame above is being recorded — finish or cancel that first' : '';
      },
      // the token of the waveform held for THIS video, or '' (the doors that make a video take it)
      wave: function () {
        var src = o.source();
        return WAVE && src.kind === 'yt' && WAVE.source === key(src) ? WAVE.job : '';
      },
      // Word timing is useful for either source kind.  The final add door
      // adopts it only when its held panel hash still agrees with the box.
      words: function () {
        var src = o.source();
        return WORDS && WORDS.source === key(src) && WORDS.lang === o.lang().code ? WORDS.job : '';
      },
      videoAdded: function () { AUTO = WAVE = WORDS = null; S.held = null; REVIEW.clear(); forget(STATE); paint(); }
    };
  }

  window.ParsehAddStt = {mount: mount, hash: hash};
})();
