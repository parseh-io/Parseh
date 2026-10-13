// SPDX-License-Identifier: GPL-3.0-or-later
/* The Frank-method video player.
 *
 * Renders videos/<folder>/<id>/annotations.json under the embedded YouTube
 * video, one block per caption.  Each block is split into the annotator's
 * phrases; hovering a phrase opens the gloss cloud — the reading (kana)
 * where the language has one, transliteration, vocabulary, meaning — set
 * exactly like a gloss block in the reading editions.  The caption whose
 * time the video is inside is highlighted and followed.
 *
 * A phrase is also WRITTEN from that cloud: four colours to mark it with,
 * the same four the reading editions use, and a ✎ that opens the chunk's
 * own fields.  Both POST to /youtube/api/edit, which puts the edit through
 * check_annotations before anything is written and refuses it in the
 * checker's own words -- and those words are what the cloud shows.
 *
 * Everything the script knows about the LANGUAGE comes from CFG.lang, the
 * registry record (lib/languages.json) the server embedded in the page:
 * its direction, its character class (for isolating runs of the script
 * inside a gloss, and for telling target text from a bare run of
 * something else), its word separator (a Japanese chunk is one word), its
 * name for the labels, its Anki tag.  No script, digit or font is named
 * in this file.
 *
 * A video declares a second language, CFG.gloss: the one its meanings are
 * WRITTEN in (video.json's "gloss"; absent means English, which is what
 * every video written before the field existed means).  It is a prose
 * language and need not be one the toolbox teaches -- Persian glossed in
 * Spanish -- so its record carries only what a page asks of it: a name, a
 * direction, and whether the registry knows it too.  Everything on the
 * page that is PROSE rather than target text takes it: the meaning, the
 * vocabulary line, the note, and the labels over them.
 */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var CFG = window.YTFRANK || {};
  // The language record.  The server always embeds one; the fallback is
  // only so a page served without it does not throw.  It stands for the
  // toolbox's default language (content from before languages was Persian)
  // as far as that can be said without a regex or a font: no character
  // class, so nothing is isolated or told apart -- the record proper comes
  // from lib/languages.json, never from here.
  var L = CFG.lang || { code: 'fa', name: 'Persian', native: '', dir: 'rtl',
                        chars: null, word_sep: ' ', reading: false,
                        require_tr: true, tag: 'farsi', fonts: {} };
  var RTL = L.dir === 'rtl';
  // The gloss language.  The same fallback reasoning as L's: the server
  // always embeds one, and English is what a page served without it means,
  // since that is what every video that says nothing is glossed in.
  var G = CFG.gloss || { code: 'en', name: 'English', native: 'English',
                         dir: 'ltr', taught: true };
  var GRTL = G.dir === 'rtl';
  // one character of the target script; null for a Latin-script language,
  // which cannot be told from English by its letters
  var scriptRe = L.chars ? new RegExp('[' + L.chars + ']') : null;
  function hasScript(s) { return !!(scriptRe && s && scriptRe.test(s)); }
  /* ONE WORD HOWEVER IT IS WRITTEN, for telling whether two are the same
     word -- the book reader's wordKey (lib/tex2html.py), fold for fold:
     composed alike (NFC), the language's marks off (its registry `strip`,
     the range frank_strip drops in LaTeX) and its case folded the way
     languages.FOLD_JS folds it, which the two have to agree with character
     for character (a plain toLowerCase spells Turkish İ as i + U+0307).
     Compared as written, every Arabic verb row drew an arrow to itself: the
     hit is headed by its bare page title وصل and its \vb by the vowelled
     وَصَلَ -- "وصل → وَصَلَ", one verb, on all three verb rows the lookup
     gives وصل (a scratch ar.db, 2026-09-10).  Never for anything shown. */
  var marksRe = L.strip ? new RegExp('[' + L.strip + ']', 'g') : null;
  function foldCase(s) {
    return (s || '').normalize('NFC').replace(/[\u0130\u0131]/g, 'i')
                    .replace(/\u0307/g, '').toLowerCase();
  }
  function wordKey(s) {
    var k = foldCase(String(s || '').normalize('NFC').replace(/\s+/g, ' ').trim());
    return marksRe ? k.replace(marksRe, '') : k;
  }
  document.documentElement.setAttribute('data-lang', L.code);
  document.documentElement.setAttribute('data-dir', L.dir);
  // an element that holds target text: its language, and its direction
  // only when the language reads right-to-left (a dir="ltr" on a Persian
  // field would be a lie; no dir on a Japanese one lets the page's own win)
  function targetAttrs(el) {
    el.setAttribute('lang', L.code);
    if (RTL) el.setAttribute('dir', 'rtl'); else el.removeAttribute('dir');
  }
  // an element that holds gloss prose -- a meaning, a vocabulary line, a
  // note.  Same rule, the other language: the page and every box on it is
  // left-to-right chrome, so only a right-to-left gloss has anything to
  // say about its direction, and saying it is what stops the browser
  // laying an Arabic meaning out as if it began on the left.
  //
  // The alignment has to be said as well, and the dir attribute does not
  // say it: the cloud is chrome and its sheet aligns everything in it
  // LEFT, which a dir of rtl does not undo -- a wrapped Arabic meaning
  // would read right to left and still hang its second line off the left
  // edge.  `start` is the same rule written once for both: left in a
  // left-to-right gloss, so nothing that reads English moves.
  var GALIGN = 'start';
  function glossAttrs(el) {
    el.setAttribute('lang', G.code);
    if (GRTL) el.setAttribute('dir', 'rtl'); else el.removeAttribute('dir');
    el.style.textAlign = GALIGN;
  }
  // the gloss language's own name for a field of prose, and "meaning"
  // when it is the language being taught as well: a video that teaches
  // English and glosses in English would otherwise label the text field
  // and the meaning field alike, and neither label would say which was
  // which (player.html says the same beside the dashboard's row).
  var GLOSS_LABEL = G.code === L.code ? 'meaning' : G.name.toLowerCase();
  // a mouse gets glosses on hover, so a click is free to mean "replay";
  // a touch screen has no hover, so the tap must open the gloss instead
  var HOVER_OK = window.matchMedia &&
                 window.matchMedia('(hover: hover)').matches;
  // ...but `hover: hover` is a claim about the device, and a phone may make
  // it too -- and there the tap path was switched off while no hover ever
  // came: the tap's own synthetic mouseover opened the gloss and the click
  // behind it closed the same gloss again.  So every pointer event says what
  // it was, and the hover paths stand down while the last one was a finger.
  // A mouse never sets this, so a desktop is untouched.
  var touchNow = false;
  document.addEventListener('pointerdown', function (e) {
    touchNow = e.pointerType === 'touch' || e.pointerType === 'pen';
  }, true);
  function hoverPointer() { return HOVER_OK && !touchNow; }
  var segs = [];          // [{start, text, chunks:[{fa,tr,voc,en,note}]}]
  var els = [];           // the .seg elements, same order
  // video.json's "reorders": a text read out of its written order (kanbun),
  // whose words the word strip does not compare with the chunk's reading
  var reorders = false;
  var player = null, ready = false, active = -1;
  var lastUserScroll = 0;

  /* ---------------- settings, remembered like the reader's ---------------- */
  var store = function (k, d) {
    var v = localStorage.getItem(k);
    return v === null ? d : v === '1';
  };
  var opts = {
    follow: store('yt_follow', true),
    hoverpause: store('yt_hoverpause', false),
    pin: store('yt_pin', true),
    // a SOUND has no picture to put beside the text: the bar stays above it
    sbs: store('yt_sbs', false) && CFG.kind !== 'audio',
    // Defaults OFF, and stays hidden until the server says there is
    // something behind it.  A reader who does not want it never sees it
    // and the page never asks anything of the server.
    dict: store('yt_dict', false),
    // English's definitions, and the same translated: switches of their own,
    // offered only where the dictionary defines its words (DICT.defines)
    defs: store('yt_defs', false),
    defsMt: store('yt_defs_mt', false),
    // the reading alone in place of the text (#aloud), for a language
    // divided into words; remembered for every such video
    aloud: store('yt_aloud', false),
    // THE SMALL MARKS A LINE IS DRAWN WITH (the gear's «Diacritics», yt_marks):
    // shown unless the person put them away, on this device, for every video
    // of a language whose record has marks to put away (its `strip`)
    marks: store('yt_marks', true)
  };
  // what the switch has behind it, filled by the question asked once at the
  // foot of this file
  var DICT = { ready: false, src: null, words: false, pairs: false,
               corpus: null, cache: {}, defines: false };
  // how far ahead the preparing loop looks, in captions
  var AHEAD = 10;
  // and a translation model, if one has been fetched for this pair: a
  // separate thing from the dictionary, asked for separately, and loaded
  // only when the reader presses the button, because it is 20 MB.
  // WHAT IS KEPT, AND WHY TWO.  A caption's translation is shared by every
  // phrase in it and is what the panel shows; a phrase's own translation is
  // a probe, used only to guess which words of the caption are its.
  var MT = { ready: false, about: null, sent: {}, probe: {} };
  var MT_KEEP = 400;
  // Pasted external-chatbot translations use the complete caption as their
  // key.  Every phrase in it therefore reuses the same answer, while the
  // dictionary marks are recalculated for the phrase currently being edited.
  var LLM = { sent: {} };
  // Side by side only makes sense with room for two columns; below that the
  // page stays stacked whatever the setting says, and the CSS agrees (the
  // layout lives inside the same media query).
  var WIDE = '(min-width: 860px)';
  // A PHONE HELD SIDEWAYS is the other case, and there it is not a setting:
  // the owner asked for the video at the left and the transcript at the right
  // whenever the phone is turned, with the divider between them draggable
  // (TO-DO §4.2, 2026-09-22).  844px is a phone's long side, under the 860
  // a window needs, so the mobile mode has a threshold of its own, and
  // lib/mobile.css carries the layout for it.
  var WIDE_M = '(orientation: landscape) and (min-width: 600px)';
  function mobileMode() {
    return document.documentElement.getAttribute('data-mode') === 'mobile';
  }
  function sideOn() {
    if (!window.matchMedia || CFG.kind === 'audio') return false;
    if (mobileMode()) return window.matchMedia(WIDE_M).matches;
    return opts.sbs && window.matchMedia(WIDE).matches;
  }
  // the theme (light / dark / sepia) is the toolbox's own, one preference
  // for every page: /lib/parseh.js keeps it and wires the ◐ button
  function paintButtons() {
    $('#follow').classList.toggle('on', opts.follow);
    $('#hoverpause').classList.toggle('on', opts.hoverpause);
    $('#pin').classList.toggle('on', opts.pin);
    $('#sbs').classList.toggle('on', opts.sbs);
    $('#dictmode').classList.toggle('on', opts.dict);
    // hidden where they mean nothing, greyed while what each hangs from is off
    $('#defmode').classList.toggle('on', opts.defs);
    $('#defmode').hidden = !DICT.defines;
    $('#defmode').disabled = !opts.dict;
    $('#defmt').classList.toggle('on', opts.defsMt);
    $('#defmt').hidden = !(DICT.defines && MT.ready);
    $('#defmt').disabled = !(opts.dict && opts.defs);
    $('#aloud').classList.toggle('on', opts.aloud);
    document.body.classList.toggle('aloud', aloudOn());
    document.body.classList.toggle('nopin', !opts.pin);
    // in the mobile mode the phone's own orientation decides it
    document.body.classList.toggle('sbs', mobileMode() ? sideOn() : opts.sbs);
    // beside the text the video is always in view, so pinning has nothing
    // left to decide -- say so rather than leaving a dead button
    $('#pin').disabled = sideOn();
    $('#grip').title = sideOn()
      ? 'drag to make the video column wider or narrower — double-click for its usual width'
      : 'drag to make the video bigger or smaller — double-click for its usual size';
  }
  $('#follow').onclick = function () {
    opts.follow = !opts.follow; localStorage.setItem('yt_follow', opts.follow ? '1' : '0');
    paintButtons(); if (opts.follow && active >= 0) show(active);
  };
  $('#hoverpause').onclick = function () {
    opts.hoverpause = !opts.hoverpause;
    localStorage.setItem('yt_hoverpause', opts.hoverpause ? '1' : '0'); paintButtons();
  };
  $('#pin').onclick = function () {
    opts.pin = !opts.pin; localStorage.setItem('yt_pin', opts.pin ? '1' : '0');
    paintButtons(); measure();
  };
  $('#sbs').onclick = function () {
    opts.sbs = !opts.sbs; localStorage.setItem('yt_sbs', opts.sbs ? '1' : '0');
    paintButtons(); applySize();
    // the caption in play was positioned for the old layout
    if (active >= 0) show(active);
  };
  $('#dictmode').onclick = function () {
    opts.dict = !opts.dict; localStorage.setItem('yt_dict', opts.dict ? '1' : '0');
    paintButtons(); refillCloud();
  };
  /* ENGLISH, EXPLAINED IN ENGLISH -- the book reader's two switches
     (lib/tex2html.py), for its reason: every dictionary here is the English
     Wiktionary's, and English's own senses are definitions written in the
     language being learned.  So they wait behind a switch of their own, off
     until it is turned on, and a second puts each into the gloss language
     under it with the model on this machine.                              */
  var DEFS_SHOWN = 3;             // what an entry opens with: lookup's MAX_SENSES
  var DEFT = Object.create(null), DEFT_KEEP = 2000, DEFT_FAILED = false;
  function defsOn() { return DICT.defines && opts.defs; }
  function defsTranslated() {
    return defsOn() && opts.defsMt && MT.ready && typeof ParsehMT !== 'undefined';
  }
  $('#defmode').title = "the dictionary's own definitions, in " + (L.name || L.code) +
                        ', under each word it finds';
  $('#defmt').textContent = 'in ' + G.name.toLowerCase();
  $('#defmt').title = 'each definition put into ' + G.name + ' under it, by the translation ' +
                      "model on this machine: a machine's reading, not a gloss";
  $('#defmode').onclick = function () {
    opts.defs = !opts.defs; localStorage.setItem('yt_defs', opts.defs ? '1' : '0');
    PRE.queue = [];               // lined up for the switch as it was
    paintButtons(); refillCloud();
  };
  $('#defmt').onclick = function () { setDefsMt(!opts.defsMt); };
  // the one way the translation switch moves -- from the header, or from the
  // editor's own over its dictionary rows -- so the header, the cloud and an
  // open editor all follow it
  function setDefsMt(on) {
    opts.defsMt = on; localStorage.setItem('yt_defs_mt', on ? '1' : '0');
    paintButtons(); srcDefs(); refillCloud();
  }
  /* THE READING ALONE: every phrase of the transcript drawn as it is said --
     its kana, or its pinyin -- where its text was, the gloss still one hover
     away.  Only a language divided into words has the button, and a
     preference left on by one of those does nothing to a video of any other. */
  function aloudOn() { return !!(L.words && opts.aloud); }
  /* ITS NAME SAYS WHAT IT SHOWS: «kana only», «pinyin only», and «reading only»
     for a language that has neither (the page's button and the gear's row both
     say what is left of the line, and the reading is what the registry calls
     it -- kana for Japanese, pinyin for Chinese) */
  var READING_ONLY = (function () {
    var rd = ((L.reading ? L.reading_label : L.translit_label) || '').toLowerCase();
    return (rd === 'kana' || rd === 'pinyin' ? rd : 'reading') + ' only';
  })();
  $('#aloud').hidden = !L.words;
  if (L.words) $('#aloud').textContent = READING_ONLY;
  $('#aloud').onclick = function () {
    opts.aloud = !opts.aloud; localStorage.setItem('yt_aloud', opts.aloud ? '1' : '0');
    paintButtons();
    Array.prototype.forEach.call($('#segs').querySelectorAll('.seg .fa .w'), function (w) {
      var sg = segs[+w.parentNode.parentNode.dataset.i];
      var ch = sg && sg.chunks && sg.chunks[+w.dataset.j];
      if (ch) paintWords(w, ch);
    });
    refillCloud();
  };
  // EVERY LOOKUP GOES THROUGH THE ONE ASK THAT CANNOT HANG (lib/parseh.js,
  // `ask`).  A bare fetch towards a computer on the far side of a tunnel
  // that has gone is not refused, it is swallowed: the cloud said "looking
  // it up\u2026" for ever, and a video opened away never grew its dictionary
  // button at all.  Watched beside the one cheap question "is anybody
  // there?" rather than timed, so an honestly slow answer is still waited
  // for.  Without lib/parseh.js on the page it is a plain fetch, as before.
  function pAsk(u, i) {
    return (window.Parseh && Parseh.ask) ? Parseh.ask(u, i) : fetch(u, i);
  }
  // Ask once whether it has anything behind it.  A button nobody can use is
  // a button that should not be there, so it stays hidden until the server
  // says otherwise -- which for a toolbox with no dictionary is never, and
  // the player is then exactly the player it was.
  pAsk('/youtube/api/lookup', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video: CFG.id, about: 1 })
  }).then(function (r) { return r.json(); }).then(function (j) {
    // THE SWITCH IS FOR ALL OF THEM.  The dictionary and the corpus are
    // separate downloads and either can be here without the other; gating on
    // the dictionary alone left a reader with a corpus and no dictionary no
    // way to reach what they had downloaded.
    if (!j || !j.help) return;
    DICT.ready = true; DICT.src = j.source || {};
    DICT.words = !!j.available; DICT.pairs = !!j.corpus_available;
    DICT.corpus = j.corpus || {};
    DICT.defines = !!j.definitions;
    showHelp();
    // one local SQLite read per phrase, so preparing ahead is free
    preStart();
  }).catch(function () {});

  /* The header button, and what it says it is for -- which depends on which
     of the three this reader has actually got. */
  function showHelp() {
    if (!(DICT.ready || MT.ready)) return;
    var has = [];
    if (DICT.words) has.push('look the words up');
    if (DICT.pairs) has.push('show a sentence somebody translated');
    if (MT.ready) has.push('translate the line');
    $('#dictmode').hidden = false;
    $('#dictmode').title = has.length
      ? has.join(', ') + ' — where nothing is glossed'
      : 'reading help where nothing is glossed';
    paintButtons();
  }
  if (typeof ParsehMT !== 'undefined')
    ParsehMT.has(L.code, G.code).then(function (m) {
      if (!m) return;
      MT.ready = true; MT.about = m;
      // a model alone is enough to want the switch
      showHelp();
      preStart();
      refillCloud();
    }).catch(function () {});
  paintButtons();

  Parseh.CharacterDecomposition.mount({lang: L.code, toolbar: $('#typo').parentNode,
    scope: '#segs .seg .fa', observe: $('#segs'),
    onModeChange: function (on) { if (on) closeCloud(); },
    onOpen: function () {
      clearTimeout(resumeTimer); wasPlaying = false;
      if (player && ready) player.pauseVideo();
    }
  });

  /* ---------------- text size and margins ----------------
     The Aa button opens the toolbox's panel (Parseh.typo): sliders setting
     the --yt-* tokens the stylesheet is written against, remembered per
     browser under yt_typo like the other settings.  `sub` is the size of the
     subtitles over a video on a phone's whole screen (lib/mobileplayer.js,
     which opens this same panel from a button of its own there); the
     transcript keeps the size `fa` gives it. */
  var typoApi = null, typoFields = [], typoTold = [];
  if (window.Parseh && Parseh.typo) {
    typoFields = [
      {name: 'fa',    label: L.name,    min: 7,    max: 43,   step: 0.5,  unit: 'px', def: 20,   prop: '--yt-fa'},
      {name: 'sub',   label: 'subtitles', min: 6,  max: 48,   step: 0.5,  unit: 'px', def: 20,   prop: '--yt-sub'},
      {name: 'gl',    label: 'glosses', min: 7,    max: 23,   step: 0.5,  unit: 'px', def: 12.5, prop: '--yt-gl'},
      {name: 'width', label: 'width',   min: 200,  max: 1680, step: 10,   unit: 'px', def: 760,  prop: '--yt-width'},
      {name: 'lead',  label: 'leading', min: 0.5,  max: 1.9,  step: 0.05, unit: '×',  def: 1,    prop: '--yt-lead'}
    ].concat(Parseh.readingFields(L.code));
    // THESE SAME FIELDS ARE THE GEAR'S SLIDERS (the Text group, below): the
    // panel's range, step and default are the ones the Aa panel on the whole
    // screen has, and a value moved there moves the slider here
    typoApi = Parseh.typo({key: 'yt_typo', button: $('#typo'), fields: typoFields,
                           onChange: function () { typoTold.forEach(function (fn) { try { fn(); } catch (e) {} }); }});
  }
  // The reading over the transcript.  Japanese has always had its chunk's
  // kana split over a chunk as far as the kana allows (GUESS); a language
  // divided into words -- Japanese, Chinese -- draws a chunk that carries
  // its word line a word at a time instead, each word's own reading over it.
  var READINGS = (L.code === 'ja' || L.words) ? Parseh.readings({
    scope: 'video:' + L.code + ':' + CFG.id, kind: 'video', selector: '.seg .fa'
  }) : null;
  var GUESS = L.code === 'ja';

  /* the header wraps on a phone; measure it, and the pinned video, so the
     followed caption can stop short of both (same trick as the reader) */
  function measure() {
    document.documentElement.style.setProperty('--headh',
      document.querySelector('header').offsetHeight + 'px');
    document.documentElement.style.setProperty('--vidh',
      (opts.pin && !sideOn() ? $('#playerwrap').offsetHeight : 0) + 'px');
  }
  /* ---------------- the video's own size ---------------- */
  /* The grip resizes whichever thing is resizable in the layout in force.
     Stacked, it sits under the video and drags VERTICALLY: down for
     bigger, up for smaller, the width stored and the height following
     from 16:9.  Side by side, it is the divider between the columns and
     drags HORIZONTALLY, storing the column's width instead.  Either way a
     double-click forgets that layout's choice. */
  var vid = $('#vid'), wrap = $('#playerwrap'), grip = $('#grip');
  var VID_MIN = 280, COL_MIN = 320;         // the least a video, and a column beside the text, can be
  function maxVidW() { return Math.max(VID_MIN, wrap.clientWidth - 28); }
  // side by side, what is resized is the COLUMN, so the two layouts keep
  // their own remembered size: a width that suited a video stacked above
  // the text is not the width that suits a column beside it
  function maxColW() { return Math.max(COL_MIN, Math.round(window.innerWidth * 0.72)); }
  /* THE SIZE, FOR THE GEAR (its «Video size» slider drives the same stored
     size the bar under the video does, and follows the bar as it is dragged):
     what the layout in force sizes, the least and the most it can be, and the
     size as it is now.  Told to whoever asked (sizeTold, once a frame). */
  var sizeFns = [], sizeQueued = false;
  function sizeTold() {
    if (sizeQueued) return;
    sizeQueued = true;
    requestAnimationFrame(function () {
      sizeQueued = false;
      sizeFns.forEach(function (fn) { try { fn(); } catch (e) {} });
    });
  }
  var videoSize = {
    // stacked above the text the video is never wider than the stylesheet lets it be (#vid's max-width): the bar
    // stores the width the video really has, so the most it can be is that, and a slider that offered more would
    // jump back as soon as it was moved
    range: function () {
      if (sideOn()) return {min: COL_MIN, max: maxColW(), side: true};
      var cap = parseFloat(getComputedStyle(vid).maxWidth), max = maxVidW();
      if (cap > 0 && cap < max) max = Math.max(VID_MIN, Math.round(cap));
      return {min: VID_MIN, max: max, side: false};
    },
    get: function () { return Math.round(sideOn() ? wrap.offsetWidth : vid.offsetWidth); },
    set: function (px) {
      var r = videoSize.range();
      localStorage.setItem(r.side ? 'yt_sidew' : 'yt_vidw',
                           String(Math.round(Math.min(Math.max(r.min, px), Math.max(r.min, r.max)))));
      applySize();
    },
    // the double-click on the bar: forget this layout's choice
    reset: function () {
      localStorage.removeItem(sideOn() ? 'yt_sidew' : 'yt_vidw');
      applySize();
    },
    chosen: function () {
      return localStorage.getItem(sideOn() ? 'yt_sidew' : 'yt_vidw') !== null;
    },
    onChange: function (fn) {
      sizeFns.push(fn);
      return function () { var k = sizeFns.indexOf(fn); if (k >= 0) sizeFns.splice(k, 1); };
    }
  };
  function applySize() {
    if (sideOn()) {
      vid.style.width = '';                 // the video fills its column
      var c = parseInt(localStorage.getItem('yt_sidew') || '', 10);
      if (c > 0) {
        document.documentElement.style.setProperty('--sidew',
          Math.min(Math.max(COL_MIN, c), maxColW()) + 'px');
      } else {                              // no choice made: the CSS default
        document.documentElement.style.removeProperty('--sidew');
      }
      document.body.classList.remove('sized');
    } else {
      document.documentElement.style.removeProperty('--sidew');
      var w = parseInt(localStorage.getItem('yt_vidw') || '', 10);
      if (w > 0) {
        vid.style.width = Math.min(w, maxVidW()) + 'px';
        document.body.classList.add('sized');
      } else {
        vid.style.width = '';
        document.body.classList.remove('sized');
      }
    }
    measure();
    sizeTold();
  }
  (function () {
    var dragging = false, side = false, startX = 0, startY = 0, startW = 0;
    grip.addEventListener('pointerdown', function (e) {
      dragging = true;
      side = sideOn();                      // fixed for the whole drag
      startX = e.clientX; startY = e.clientY;
      startW = side ? wrap.offsetWidth : vid.offsetWidth;
      grip.setPointerCapture(e.pointerId);
      document.body.classList.add('resizing');
      e.preventDefault();
    });
    grip.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      if (side) {
        // the divider follows the pointer: one pixel right, one pixel wider
        var c = Math.round(startW + (e.clientX - startX));
        document.documentElement.style.setProperty('--sidew',
          Math.min(Math.max(COL_MIN, c), maxColW()) + 'px');
      } else {
        var w = Math.round(startW + (e.clientY - startY) * 16 / 9);
        vid.style.width = Math.min(Math.max(VID_MIN, w), maxVidW()) + 'px';
        document.body.classList.add('sized');
      }
      measure();
      sizeTold();
    });
    function done() {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove('resizing');
      localStorage.setItem(side ? 'yt_sidew' : 'yt_vidw',
                           String(side ? wrap.offsetWidth : vid.offsetWidth));
      measure();
      sizeTold();
    }
    grip.addEventListener('pointerup', done);
    grip.addEventListener('pointercancel', done);
    grip.addEventListener('dblclick', videoSize.reset);
  })();
  // crossing the two-column breakpoint changes which layout is in force,
  // so the buttons and the sizes both want redoing
  window.addEventListener('resize', function () { paintButtons(); applySize(); });
  applySize();

  /* the ⏻ button is wired by /lib/parseh.js (data-parseh-stop) */

  /* ---------------- helpers ---------------- */
  function fmt(t) {
    t = Math.max(0, Math.floor(t));
    var m = Math.floor(t / 60), s = t % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }
  /* Words of the target script inside a gloss line must sit in their own
     isolate or the bidi algorithm scrambles them (Persian), and want the
     language's face (every script) -- the reader wraps them in
     <bdi class=v>, and so does this.  The run regex is built from the
     record's character class: a run is a maximal stretch of the script,
     with inner separators when the language has one (a compound like
     فکر کردن stays one isolate, in reading order; Japanese, with no
     separator, is contiguous characters).  A Latin-script language has no
     class, so nothing is isolated: Italian inside an English gloss needs
     no help.

     The gloss language changes nothing here, and the case that looks as
     though it should is the one to see: gloss Persian in Arabic and the
     regex matches the whole line, which is a single maximal run and comes
     out as one isolate wearing one face -- the face it is written in.  So
     the rule holds for a gloss in the target's own script without being
     told about it. */
  var runRe = null;
  if (L.chars) {
    var cls = '[' + L.chars + ']';
    runRe = new RegExp(cls + '+' + (L.word_sep
      ? '(?:' + L.word_sep.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + cls + '+)*' : ''), 'g');
  }
  // what glossAttrs sets, written out: the cloud is assembled as a string
  // of HTML, and the elements holding gloss prose are made there
  var GATTRS = ' lang="' + esc(G.code) + '"' + (GRTL ? ' dir="rtl"' : '') +
               ' style="text-align:' + GALIGN + '"';
  function glossHTML(s) {
    if (!runRe) return esc(s);
    var out = '', last = 0, m;
    runRe.lastIndex = 0;
    while ((m = runRe.exec(s)) !== null) {
      out += esc(s.slice(last, m.index)) + '<bdi class="v" lang="' + L.code + '">' +
             esc(m[0]) + '</bdi>';
      last = m.index + m[0].length;
    }
    return out + esc(s.slice(last));
  }
  /* A VOCABULARY LINE THAT HOLDS THE BOOKS' MACROS is drawn as the reader draws
     it (lib/vocline.js, held to the reader's own renderer by one fixture); any
     other line is drawn exactly as it always was, so that every video glossed
     before macros existed looks the same to the pixel.  A line nobody can read
     -- a brace left open in a file edited by hand -- is shown as it stands:
     a cloud that will not open is worse than its source. */
  function vocHTML(s) {
    if (window.ParsehVocline && ParsehVocline.isMacro(s)) {
      try { return ParsehVocline.render(s, L); } catch (e) { /* drawn as it stands, below */ }
    }
    return glossHTML(s);
  }
  // THE SAME LINE AS PLAIN TEXT, for a card's notes: a card is read in Anki
  // and in a studio document, which know no macro, so what it carries is the
  // line as a person reads it (ParsehVocline.flatten) and never its source.  A
  // plain line goes as it is.
  function vocText(s) {
    if (window.ParsehVocline && ParsehVocline.isMacro(s)) {
      try { return ParsehVocline.flatten(s, L); } catch (e) { /* its source, below */ }
    }
    return s || '';
  }
  // the words of a chunk, for the per-word spans: split at the language's
  // separator; a language without one (Japanese) makes the chunk one word
  function wordsOf(s) { return L.word_sep ? s.split(L.word_sep) : [s]; }
  // a chunk's word line, where its language is divided into words and the
  // chunk has one; '' for every other chunk, which is drawn, looked up and
  // carded exactly as it always was
  function lineOf(ch) {
    return (READINGS && L.words && typeof ch.words === 'string' && ch.words.trim())
      ? ch.words : '';
  }
  // a lookup's body, with the chunk's word line where it has one: the
  // dictionary then looks up the words a person divided, one row each
  function withLine(body, ch) {
    var line = lineOf(ch);
    if (line) body.words = line;
    // a video's captions are speech: the dictionary reads a word that way where it can (lib/spoken.py), and says so
    body.register = 'spoken';
    return body;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ---------------- the reader's own mark ----------------
     Four colours, the same four as the reading editions: a chunk carries
     one in its "col" key, and the phrase wears it as hl-red and friends --
     the very class names lib/tex2html.py gives a coloured chunk, set to
     the very same values (style.css says where they come from).  A colour
     means nothing to any tool; it is the reader's mark on the text, and
     the two doors must not show it in two different reds.
     The names are check_annotations.COLOURS.  Nothing serves that tuple to
     a browser -- the page's config carries the language record and not the
     checker -- so they are written here once and nowhere else in this
     file, and the server refuses any fifth name in the checker's words. */
  var COLOURS = ['red', 'blue', 'orange', 'green'];
  function paintCol(el, ch) {
    COLOURS.forEach(function (c) { el.classList.remove('hl-' + c); });
    if (ch.col && COLOURS.indexOf(ch.col) >= 0) el.classList.add('hl-' + ch.col);
  }

  /* ---------------- ✱ notes: the phrases that carry a note ----------------
     A phrase's `note` is the aside under its meaning -- what the automatic
     transcript really heard, a cultural point -- and an LLM leaves one when
     something needs saying.  The button lights every phrase that has one, to
     see where a model may have flagged a problem, and walks from one to the
     next (‹ ›): a highlight over a long transcript is not a list.  It is a
     reviewing tool and nothing else -- it writes nothing, asks nothing, hides
     nothing, and no click means something else while it is on -- and it is OFF
     on every visit: a remembered highlight would leave a transcript looking
     marked for ever by something nobody recalls turning on.  Not in the mobile
     mode, which writes nothing and has no button for it.

     THE PHRASE'S OWN CLASS, has-note, and not an hl- colour: the four colours
     are the person's marks and go on showing beside it.  A class and nothing
     more -- the dashed underline and the ✱ are drawn by the stylesheet, so no
     text is added to the line, and selection, copy, the dictionary's sentence
     and the timings read what they always read -- and it is on the page only
     while the switch is, so that with it off a transcript is exactly what it
     was before there was a switch.  What counts is a note that is not blank
     once trimmed, on any chunk the line draws: a chunk drawn bare (one marked
     plain) has no cloud and its note is shown nowhere else.  The count and the
     walk read the page, which is the one thing that is always as drawn: a save,
     a cut and a redraw all end in pnPaint(). */
  // the switch, the phrase last walked to, whether any phrase wears the class, whether the bar is held
  var pn = { on: false, cur: null, swept: false, held: false };
  function hasNote(ch) {
    return !!ch && typeof ch.note === 'string' && ch.note.trim() !== '';
  }
  // every phrase the lines draw, with its chunk: the n-th phrase of a line is the
  // n-th chunk, and what lies between two is text
  function pnEach(fn) {
    Array.prototype.forEach.call($('#segs').querySelectorAll('.seg'), function (d) {
      var sg = segs[+d.dataset.i], fa = d.querySelector('.fa');
      if (!sg || !sg.chunks || !fa) return;
      var kids = Array.prototype.filter.call(fa.children, function (e) {
        return e.classList.contains('w') || e.classList.contains('bare');
      });
      sg.chunks.forEach(function (ch, j) { if (kids[j]) fn(kids[j], ch); });
    });
  }
  function paintNote(el, ch) {
    var lit = pn.on && hasNote(ch);
    el.classList.toggle('has-note', lit);
    if (!lit) el.classList.remove('note-here');
  }
  function pnList() {
    return Array.prototype.slice.call($('#segs').querySelectorAll('.has-note'));
  }
  function pnPaint() {
    if (mobileNow()) pn.on = false;       // the mobile mode has no button, so it is left off there
    var on = pn.on;
    if (on || pn.swept) { pnEach(paintNote); pn.swept = on; }
    var list = on ? pnList() : [];
    if (!on && pn.cur) { pn.cur.classList.remove('note-here'); pn.cur = null; }
    // the arrows are in the bar, which a narrow screen puts away as the page moves
    // down (lib/parseh.js, "the bar, on a phone"): while the walk is on it stays, or
    // the second press would have to wait for a scroll up
    if (on !== pn.held) { pn.held = on; document.body.toggleAttribute('data-bars-held', on); }
    var b = $('#notesbtn');
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.textContent = '✱ notes' + (on ? ' ' + list.length : '');
    ['#notesprev', '#notesnext'].forEach(function (s) {
      $(s).hidden = !on; $(s).disabled = !list.length;
    });
  }
  // the line the transcript is read below: the bar, and the video where it is
  // pinned over the text (what measure() hands the stylesheet as --headh and --vidh)
  function pnReadFrom() {
    return $('header').offsetHeight + (opts.pin && !sideOn() ? $('#playerwrap').offsetHeight : 0);
  }
  // one phrase on, in document order, wrapping at the ends.  From the phrase
  // last walked to; and where there is none (not walked yet, or its note has
  // gone) from where the page is being read, so that the first press goes to
  // the next note on the way and not back to the top of a long transcript
  function pnStep(dir) {
    var list = pnList();
    if (!list.length) return;
    var at = list.indexOf(pn.cur), to;
    if (at >= 0) to = (at + dir + list.length) % list.length;
    else {
      var edge = pnReadFrom(), below = list.filter(function (el) {
        return el.getBoundingClientRect().top > edge;
      }).length;
      to = dir > 0 ? (below ? list.length - below : 0)
                   : (list.length - below ? list.length - below - 1 : list.length - 1);
    }
    if (pn.cur) pn.cur.classList.remove('note-here');
    pn.cur = list[to];
    pn.cur.classList.add('note-here');
    // follow stands down for a moment, as it does for a hand on the wheel
    lastUserScroll = Date.now();
    pn.cur.closest('.seg').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  $('#notesbtn').onclick = function () { pn.on = !pn.on; pnPaint(); };
  $('#notesprev').onclick = function () { pnStep(-1); };
  $('#notesnext').onclick = function () { pnStep(1); };
  // the mode switched under the page: the highlight goes with the button
  if (window.Parseh && Parseh.mode && Parseh.mode.onChange) Parseh.mode.onChange(pnPaint);

  /* ---------------- diacritics: what a line is drawn with ----------------
     The gear's «Diacritics» (yt_marks) puts away the small marks that write the
     vowels, the doubling and the silent stop on a Persian or an Arabic line --
     the very marks the language's record calls its `strip`, which the books'
     third level leaves off and the lookups fold away (marksRe, above).  ONE
     RULE, AND DISPLAY ONLY: the lines are drawn from `asDrawn()`, and nothing
     else reads it -- ch.fa itself, the copy, the cards, the editor, the colour
     marks and every lookup (which fold the marks away their own way) go on
     with the chunk as it was written.  A phrase is still a phrase: its cloud
     opens with its own gloss, and shows the text it was written with when it
     is asked to. */
  function marksOff() { return !!marksRe && !opts.marks; }
  function asDrawn(s) {
    s = s === undefined || s === null ? '' : String(s);
    return marksOff() ? s.replace(marksRe, '') : s;
  }
  // whether any line of this video holds a mark to put away: the gear has no
  // switch to offer a video that has none (a Persian one written without)
  var hasMarkRe = L.strip ? new RegExp('[' + L.strip + ']') : null;
  function videoHasMarks() {
    if (!hasMarkRe) return false;
    return segs.some(function (sg) {
      return !sg.plain && (sg.chunks || []).some(function (ch) { return hasMarkRe.test(ch.fa || ''); });
    });
  }
  /* EVERY LINE DRAWN AGAIN WHERE IT STANDS: the elements stay -- their listeners,
     the colour of a marked phrase, the caption on air, the note seams, the
     lines being picked for a model -- and only the words written in them are
     written again.  The page is scrolled to where it was (a line without its
     marks is a little shorter, and the caption being read would move). */
  function redrawText() {
    var box = $('#segs');
    var held = null, was = 0;
    // the caption at the top of what is being read, and where it stood
    var from = pnReadFrom();
    Array.prototype.some.call(box.querySelectorAll('.seg'), function (d) {
      var r = d.getBoundingClientRect();
      if (r.bottom > from) { held = d; was = r.top; return true; }
      return false;
    });
    Array.prototype.forEach.call(box.querySelectorAll('.seg'), function (d) {
      var sg = segs[+d.dataset.i], fa = d.querySelector('.fa');
      if (!sg || !sg.chunks || !fa) return;                // the video's own framing is never touched
      var kids = Array.prototype.filter.call(fa.children, function (e) {
        return e.classList.contains('w') || e.classList.contains('bare');
      });
      sg.chunks.forEach(function (ch, j) {
        var e = kids[j];
        if (!e) return;
        if (e.classList.contains('bare')) e.textContent = asDrawn(ch.fa);
        else paintWords(e, ch);
      });
    });
    if (held) {
      var d = held.getBoundingClientRect().top - was;
      if (Math.abs(d) > 0.5) window.scrollBy(0, d);
    }
    refillCloud();
  }

  // the words of a chunk as spans of their own, so a modifier-click can
  // name the WORD even though the hover gloss belongs to the whole phrase
  // (a Japanese chunk is one word: its card is the phrase).  A function
  // and not code inside render(), because a saved edit draws the phrase
  // again: an fa edit may vocalise it or move a stop.
  //
  // A CHUNK DIVIDED INTO WORDS carries the division in "words" beside its
  // text (lib/wordline.js): it is drawn from that line, one .wd per word with
  // its own reading, each .wd still a child of the phrase -- and a line that
  // does not give the text back draws the chunk as a chunk without one.
  // With the reading alone switched on (#aloud) the phrase is its reading.
  function paintWords(w, ch) {
    w.classList.remove('words-bad');
    if (aloudOn()) {
      w.textContent = '';
      var said = document.createElement('span');
      said.className = 'wd';
      said.textContent = ParsehWordline.aloud((L.reading ? ch.kana : ch.tr) || '', asDrawn(ch.fa));
      w.appendChild(said);
      return;
    }
    var line = lineOf(ch);
    if (line && READINGS.renderWords(w, ch.fa, line)) return;
    w.textContent = '';
    wordsOf(asDrawn(ch.fa)).forEach(function (wordTxt, k) {
      if (k) w.appendChild(document.createTextNode(L.word_sep));
      var wd = document.createElement('span');
      wd.className = 'wd'; wd.textContent = wordTxt;
      // Japanese's guess only: READINGS is there for Chinese too now, and a
      // stray kana on a Chinese chunk was never hung over its text
      if (GUESS && ch.kana) READINGS.render(wd, wordTxt, ch.kana);
      w.appendChild(wd);
    });
  }

  /* ---------------- the cloud ---------------- */
  var cloud = $('#cloud'), cloudFor = null, hideTimer = null, resumeTimer = null;
  var wasPlaying = false, cloudCtx = null, ankiOpen = false;
  // While a phrase is being written the cloud stops being a hover: it has
  // to survive the pointer leaving it, and the next phrase hovered must not
  // wipe a half-typed form.  `editing` is that latch, and every way the
  // cloud closes itself asks it first.
  var editing = false, editWasPlaying = false;

  /* The colour row, at the foot of the cloud in BOTH its states: marking a
     phrase is a reading gesture and not an edit, so it is one click and it
     never sits behind the ✎. */
  function colourRow(ch) {
    var h = '<div class="colrow"><span class="clab">mark</span>' +
            '<button type="button" class="sw no' + (ch.col ? '' : ' on') +
            '" data-col="" title="no colour">&#10005;</button>';
    COLOURS.forEach(function (c) {
      h += '<button type="button" class="sw hl-' + c +
           (ch.col === c ? ' on' : '') + '" data-col="' + c +
           '" title="mark this phrase ' + c + '"></button>';
    });
    return h + '</div><div class="cstat"></div>';
  }
  function fillCloud(ch) {
    var h = '<div class="arrow"></div>';
    // with the transcript showing the reading alone, the text is here
    if (aloudOn()) h += '<div class="ctext" lang="' + L.code + '">' + esc(asDrawn(ch.fa)) + '</div>';
    // the reading (kana) sits above the transliteration, in the target face;
    // a language without a reading ignores the field (a stray key copied
    // from another language's template must not become a line)
    if (L.reading && ch.kana) h += '<div class="kana" lang="' + L.code + '">' + esc(ch.kana) + '</div>';
    // the transliteration is a romanisation of the TARGET and belongs to
    // no gloss language, so it takes no lang of its own -- the three lines
    // under it are prose the reader reads, and take the gloss's
    if (ch.tr) h += '<div class="tr">' + esc(ch.tr) + '</div>';
    if (ch.voc) h += '<div class="voc"' + GATTRS + '>' + vocHTML(ch.voc) + '</div>';
    if (ch.en) h += '<div class="en"' + GATTRS + '>' + glossHTML(ch.en) + '</div>';
    if (ch.note) h += '<div class="note"' + GATTRS + '>' + glossHTML(ch.note) + '</div>';
    // a chunk nobody has glossed yet -- a phrase all the same, hoverable and
    // writable (segEl() says why): say so, rather than opening a cloud that
    // looks broken.  THE GLOSS ALONE decides, as it does for the checker
    // (check_annotations.unwritten) and for "delete gloss" (hasGloss, below):
    // a note is the author's aside and no gloss, and a phrase whose gloss has
    // just been deleted keeps its note -- whose cloud showed that note alone,
    // reading as if it were the meaning, with nothing to say the gloss was gone
    if (!hasGloss(ch)) {
      h += '<div class="unwritten">nothing glossed yet</div>';
      // NOTHING SET UP AT ALL, and the reader is looking at an empty phrase:
      // this is the moment they want to know the feature exists, so say so
      // here rather than only in a header they have not read
      if (!DICT.ready && !MT.ready)
        h += '<div class="dict"><div class="dnone">A dictionary can look ' +
             'these words up, a corpus can show a sentence somebody ' +
             'translated, and a model can read the line. ' +
             '<a href="/settings/reading-help/">Set any of them up</a> — it takes a couple ' +
             'of minutes.</div></div>';
    }
    // The dictionary goes BELOW that line and never in place of it: it is
    // not a gloss, and the reader is told so twice -- once by the line
    // saying nothing is written, once by the panel's own label.  It is empty
    // here and filled when the answer comes back, because the cloud must
    // open at once and a lookup is a round trip.  Only where no vocabulary
    // line exists: a written phrase looks exactly as it did before this was
    // built.  AND ON A PHONE, only where nothing at all is written (the
    // owner, 2026-09-25: a gloss is ANY line of one -- a meaning, a
    // transliteration, a vocabulary line; hasGloss): there the panel goes
    // straight into the dictionary's sheet (openCloud), and a phrase with a
    // meaning written under it would have gone there too, its meaning lost
    // at the top of a long entry.  Such a phrase opens its cloud, as any
    // glossed phrase does, with the dictionary a press away (dictAsk).
    var dictShown = (mobileNow() ? !hasGloss(ch) : !ch.voc) && (DICT.ready || MT.ready) && opts.dict;
    var setupShown = !hasGloss(ch) && !DICT.ready && !MT.ready;
    if (dictShown)
      h += '<div class="dict" data-fill="1"></div>';
    // THE DICTIONARY UNDER ANY GLOSS, on a phone (the owner, 2026-09-24).
    // The panel above opens by itself only where nobody has written a
    // vocabulary line, and only with the header's switch on; a reader on a
    // phone may want the dictionary's senses of a phrase that has a gloss
    // too, and the switch is in the gear's sheet (it was under ⋯).  So beside "copy", the mobile
    // interface has a button that opens the dictionary's sheet, on demand --
    // wherever the panel is not there already (dictOnDemand): under every
    // gloss, and under "nothing glossed yet" with the dictionary switched off.
    var dictAsk = !dictShown && !setupShown && mobileNow()
      ? '<button type="button" class="mkdict" data-layout="mobile" aria-expanded="false" ' +
        'title="what the dictionary says of these words, in a sheet over the foot of the screen">' +
        'dictionary</button>'
      : '';
    h += '<div class="mkrow"><button type="button" class="mkcard">' +
         '+ card</button><button type="button" class="mkcopy" ' +
         'title="copy this phrase">&#10697; copy</button>' + dictAsk +
         '<button type="button" class="mkedit" ' +
         'title="write this phrase: its text and its gloss">&#9998; edit</button>' +
         laterButton(ch) + '</div>';
    cloud.innerHTML = h + colourRow(ch);
    // "I know this" a word at a time for a chunk its line draws -- asked of
    // renderWords, into a span nobody sees, so a line gone stale is offered
    // the controls of the chunk the transcript drew instead
    var line = lineOf(ch);
    if (line && READINGS.renderWords(document.createElement('span'), ch.fa, line))
      READINGS.wordControls(cloud, line);
    else if (GUESS && ch.kana) READINGS.controls(cloud, ch.fa);
    var dbox = cloud.querySelector('.dict[data-fill]');
    // the entry of a phrase nobody has glossed, which openCloud hands to the
    // dictionary's sheet on a phone
    autoBox = dictShown ? dbox : null;
    if (dbox) dictInto(dbox, ch);
  }

  // the mobile interface is in force (lib/parseh.js says, as every page asks it)
  function mobileNow() {
    var p = window.Parseh;
    return !!(p && p.mode && p.mode.isMobile && p.mode.isMobile());
  }
  /* The dictionary's entry for a phrase, asked for with the cloud's own
     button (fillCloud, the mobile interface): the same entry an unglossed
     phrase shows, filled the same way, in the dictionary's sheet.  Where
     nothing is set up for the language, the sheet says so and where to set
     one up, as an unglossed phrase's cloud does. */
  function dictOnDemand(btn) {
    if (!cloudCtx) return;
    var box = document.createElement('div');
    box.className = 'dict m-dict';
    btn.setAttribute('aria-expanded', 'true');
    openSheet(box);
    if (DICT.ready || MT.ready) dictInto(box, cloudCtx.ch);
    else box.innerHTML = '<div class="dnone">Nothing is set up to look ' + esc(L.name) +
      ' words up: a dictionary, a corpus of translated sentences or a model. ' +
      '<a href="/settings/reading-help/">Set any of them up</a> — it takes a couple of minutes.</div>';
  }
  /* THE DICTIONARY'S SHEET (TO-DO §4.18; Parseh.dictSheet, lib/parseh.js).
     On a phone an entry is read in a sheet from the foot of the screen, not
     in the cloud: the cloud is a card a few centimetres wide over the very
     phrase it is about, and an entry scrolling inside it was, the owner
     said, "basically unusable".  THE CLOUD STAYS FOR THE GLOSSES -- a
     glossed phrase nobody asks the dictionary about opens its cloud as it
     always did; what opens the sheet is the cloud's "dictionary", and a tap
     on a phrase with nothing glossed while the dictionary is on.

     While the sheet is up the cloud is hidden but not closed, and nothing
     but the sheet may close it (`dsheet`, which closeCloud and scheduleClose
     ask as they ask `editing`): the pointer "leaving" the cloud for the
     sheet, or a subtitle changing on the whole screen, would otherwise close
     it underneath -- and closing the cloud is what starts a paused video
     again.  The video is paused while the sheet is up, whether or not the
     cloud had paused it (on the whole screen the sheet covers the
     subtitles); when the sheet goes, the cloud goes with it, nothing is left
     open, and a video paused for either goes on as it does when a cloud
     closes (the owner's 4). */
  var dsheet = null, sheetPaused = false, autoBox = null;
  function openSheet(box) {
    if (!cloudCtx || !window.Parseh || !Parseh.dictSheet) return;
    var ch = cloudCtx.ch;
    // the gloss the cloud was showing, over the entry
    var carry = Array.prototype.filter.call(cloud.children, function (c) {
      return c.matches('.ctext, .kana, .tr, .voc, .en, .note, .unwritten');
    });
    if (player && ready) {
      clearTimeout(resumeTimer);
      var st = null;
      try { st = player.getPlayerState && player.getPlayerState(); } catch (e) {}
      // playing, or about to (3: YouTube buffering, as it does on a phone
      // over a slow link) -- left alone, a buffering video started under the
      // sheet as soon as it had enough, and on the whole screen took the
      // subtitles and their marked phrase away from under it
      if (st === 1 || st === 3) { wasPlaying = true; sheetPaused = true; player.pauseVideo(); }
    }
    cloud.hidden = true;
    dsheet = Parseh.dictSheet({
      box: box, lang: { code: L.code, dir: L.dir }, title: dictText(ch), anchor: cloudFor,
      // the room a phrase can be read in, above the sheet: under the header,
      // and under the video where it is pinned over the transcript (upright;
      // held sideways it is pinned BESIDE it, and the sheet knows the
      // difference)
      carry: carry, pinned: ['header', '#playerwrap'],
      onClose: function () { dsheet = null; closeCloud(); }
    });
  }

  /* ---- a video with few glosses (the owner, 2026-09-24) ----
     Fewer than half of its phrases with a gloss, and a press on a
     phrase does one of two different things on a phone -- the gloss beside
     it, or the dictionary's sheet -- with nothing to say which.  Every phrase
     already wears a faint dotted underline (style.css); in such a video, in
     the mobile mode, the ones with a gloss -- any line of one, hasGloss (the
     owner, 2026-09-25) -- are marked (m-gl) and the page says the video is
     sparse (m-sparse), and lib/mobile.css draws their line darker, the
     others keeping theirs as it was -- in the transcript and in the
     subtitles over the whole screen, which are copies of it.  A video
     glossed half or more, and the browser mode, are left exactly as they
     were: not a class is written. */
  function markGlossed() {
    var root = document.documentElement, on = mobileNow();
    var ws = on ? document.querySelectorAll('#segs .seg .w') : [], gl = [];
    Array.prototype.forEach.call(ws, function (w) {
      var line = w.closest('.seg'), sg = line && segs[+line.dataset.i];
      var ch = sg && sg.chunks && sg.chunks[+w.dataset.j];
      if (ch && hasGloss(ch)) gl.push(w);
    });
    var sparse = on && ws.length > 0 && gl.length * 2 < ws.length;
    if (root.classList.contains('m-sparse') !== sparse) root.classList.toggle('m-sparse', sparse);
    Array.prototype.forEach.call(document.querySelectorAll('.m-gl'), function (w) {
      w.classList.remove('m-gl');
    });
    if (sparse) gl.forEach(function (w) { w.classList.add('m-gl'); });
  }
  if (window.Parseh && Parseh.mode && Parseh.mode.onChange) Parseh.mode.onChange(markGlossed);

  /* ---------------- the dictionary behind an unglossed phrase ------------
     The same panel the book reader draws (lib/tex2html.py), for the same
     reason and under the same rule: this is a dictionary and not a gloss.
     It lists every sense a word can carry and cannot say which is meant,
     which is exactly the judgement a written vocabulary line is.  So it is
     ruled off, tinted, labelled, and the source and its licence are printed
     under it -- an entry with no provenance is a rumour.                  */
  function dictText(ch) { return (ch && ch.fa) || ''; }

  // `at` is the word of the chunk's word line the row was asked for,
  // [surface, reading], headed as the line writes it
  function dictLine(w, at) {
    var h = '<div class="dw"><div class="dwd" lang="' + esc(L.code) + '">' +
            esc(at ? at[0] : w.word) +
            (at && at[1] ? ' <span class="dread">' + esc(at[1]) + '</span>' : '') + '</div>';
    if (!w.hits.length) {
      // what it looked for, not merely that it failed: a reader can then
      // tell "not in the dictionary" from "the dictionary was never asked"
      return h + '<div class="dnone">not found (tried ' +
             esc(w.tried.join(', ')) + ')</div></div>';
    }
    // WHAT THE SPOKEN PASS READ (lib/spoken.py): drawn by lib/parseh.js, as the book's panel draws it -- a pill, the word it
    // was read as, why, its pieces, its sound -- and a word with several readings numbers them
    var SP = Parseh.spoken, many = SP.many(w);
    if (many) h += SP.header(w).outerHTML;
    w.hits.forEach(function (x, k) {
      // as the caption spells it, like the editor's row (srcHit) and the
      // book's panel: 睡觉 in a Simplified video, not the 睡覺 Wiktionary
      // files it under -- which the title still names
      var head = x.spelled || x.headword;
      var said = SP.note(x);
      var block = x.spoken ? SP.block(x, { written: w.word, lang: L.code, dir: L.dir }) : null;
      h += '<div class="dhit' + SP.row(x) + '">' + (many ? SP.lead(w, k) : '') + '<span class="dhead2"' +
           (x.spelled && x.spelled !== x.headword
             ? ' title="the dictionary files it under ' + esc(x.headword) + '"' : '') +
           '>' + esc(head) + (x.translit ? ' ' + esc(x.translit) : '') + '</span>' +
           (x.pos ? '<span class="dpos"> ' + esc(x.pos) + '</span>' : '') +
           (said ? '<span class="dnote"> — ' + esc(said) + '</span>' : '') +
           (block ? block.outerHTML : '');
      // A VERB'S OTHER FORMS, under its headword and before its senses.  The
      // dictionary answers می‌سازم with ساختن "to make, to build", and the
      // reader is left to get from the infinitive to the stem the form in
      // front of him is built on -- which is the whole difficulty of a
      // Persian verb, and the part a translation of the infinitive does not
      // say.  hit.vb is the language's own recipe (lib/verbs/) reading the
      // dictionary's conjugation table, present only on a hit it recognises
      // as a verb; its line is "pres. ساز sāz · past ساخت sāxt" in Persian,
      // "pres. vado · p.p. andato · aux. essere" in Italian.  Set like the
      // rest of the panel's prose, its target words isolated.  Headed by the
      // verb it belongs to when that is not the headword, as the editor's
      // row is (srcHit): German's "stand … auf" reaches stehen and carries
      // aufstehen's forms, "→ aufstehen · pret. stand auf · p.p. …".  The
      // same word is not another verb: folded (wordKey), so Arabic's وصل and
      // its vowelled وَصَلَ, or 睡觉 and the lemma 睡觉 the recipe writes in
      // the video's Simplified, get no arrow pointing at themselves.
      var lem = x.vb && x.vb.lemma && wordKey(x.vb.lemma) !== wordKey(head)
                ? x.vb.lemma : '';
      if (x.vb && (x.vb.line || lem))
        h += '<div class="dvb">' + (lem ? '\u2192 ' + glossHTML(lem) +
                                           (x.vb.line ? ' · ' : '') : '') +
             glossHTML(x.vb.line || '') + '</div>';
      // a dictionary that defines its words in their own language shows its
      // senses only with that switch on, and then as definitions
      if (!DICT.defines)
        x.senses.forEach(function (s) {
          h += '<div class="dsense">' + esc(s) + '</div>';
        });
      else if (opts.defs)
        h += defsHTML(x);
      h += '</div>';
    });
    // (a word the spoken pass read says how in each of its cards: the line that says it again is left out)
    if (w.via && w.via !== 'as written' && w.kind !== 'spoken')
      h += '<div class="dnone">found ' + esc(w.via) + '</div>';
    return h + '</div>';
  }

  // a hit's definitions: the first DEFS_SHOWN, and the rest behind a button
  function defsHTML(x) {
    var all = (x.senses || []).map(function (s, i) { return [s, (x.marks || [])[i] || '']; })
      .concat((x.more || []).map(function (s, i) { return [s, (x.more_marks || [])[i] || '']; }));
    var h = '<div class="ddefs">';
    all.forEach(function (d, i) {
      // what Wiktionary labels the sense with (lib/parseh.js, the book's too)
      var label = Parseh.senseLabels(d[1], x.pos).join(', ');
      h += '<div class="dsense ddef" lang="' + esc(L.code) + '" data-def="' + esc(d[0]) + '"' +
           (i >= DEFS_SHOWN ? ' hidden' : '') + '>' +
           (label ? '<span class="dlabel">(' + esc(label) + ') </span>' : '') + esc(d[0]) + '</div>';
    });
    var more = all.length - DEFS_SHOWN;
    if (more > 0)
      h += '<button type="button" class="ddefmore">' + more + ' more definition' +
           (more === 1 ? '' : 's') + '</button>';
    return h + '</div>';
  }
  // what a string of HTML cannot carry: the buttons' handlers
  function wireDefs(box) {
    box.querySelectorAll('.ddefmore').forEach(function (b) {
      b.onclick = function () {
        var defs = b.parentNode;
        defs.querySelectorAll('.ddef[hidden]').forEach(function (d) { d.hidden = false; });
        // hidden and not removed: the page asks next whether the click was
        // inside the cloud, and a removed button is inside nothing
        b.hidden = true;
        defsInto(defs);
        settleCloud();
      };
    });
  }
  // The definitions in `box` read in the gloss language: each element `sel`
  // names that shows holds its definition in data-def and is given the
  // translation as a .dtr of its own -- the ones already read at once, the
  // rest in one call.  `after` runs when a late answer lands; `onRead(el,
  // text)` once for an element, when its translation is in.
  function defsRead(box, sel, after, onRead) {
    // what shows inside `box`: neither the element nor anything between it
    // and the box hidden -- the cloud around a box may well be, for it is
    // filled before it is placed and shown
    function shows(d) {
      for (var e = d; e && e !== box; e = e.parentElement) if (e.hidden) return false;
      return true;
    }
    function shown() {
      return Array.prototype.filter.call(box.querySelectorAll(sel), shows);
    }
    function draw() {
      shown().forEach(function (d) {
        var t = d.querySelector(':scope > .dtr');
        if (!t) {
          t = document.createElement('div');
          t.className = 'dtr';
          t.setAttribute('lang', G.code);
          if (GRTL) t.setAttribute('dir', 'rtl');
          d.appendChild(t);
        }
        var got = DEFT[d.dataset.def];
        t.textContent = got === undefined ? '…' : got;
        t.classList.toggle('dwaiting', got === undefined);
        if (got !== undefined && onRead && !d.dataset.read) { d.dataset.read = '1'; onRead(d, got); }
      });
    }
    var want = [];
    shown().forEach(function (d) {
      if (DEFT[d.dataset.def] === undefined && want.indexOf(d.dataset.def) < 0)
        want.push(d.dataset.def);
    });
    draw();
    if (!want.length) return;
    ParsehMT.translate(L.code, G.code, want).then(function (got) {
      want.forEach(function (s, k) { mtKeep(DEFT, s, got[k] || '', DEFT_KEEP); });
      if (!box.isConnected) return;
      draw();
      if (after) after();
    }).catch(function (err) {
      if (!box.isConnected) return;
      box.querySelectorAll('.dtr.dwaiting').forEach(function (t) {
        t.textContent = (err && err.message) || 'the model could not be run';
      });
      if (after) after();
    });
  }
  // the panel's definitions, while their switch is on
  function defsInto(box) {
    if (defsTranslated()) defsRead(box, '.ddef', settleCloud);
  }

  function dictFill(box, j, ch, sg) {
    // Each of the three draws only if it has something to draw: a reader with
    // a corpus and no dictionary gets the sentences and no empty heading.
    var h = '', words = j.words || [];
    if (words.length) {
      // A BLOCK OF ITS OWN, like the two after it.  The dictionary used to go
      // straight into the panel, so the only thing between it and the model's
      // reading was the same dotted line that sits over each block's source
      // -- --rule on the panel's tint, 1.08:1 in every theme, which is to say
      // nothing -- and the three read as one list.  Wrapped, the stylesheet
      // can rule the three apart (.ddict | .dmt | .dpairs) and leave the
      // source line inside its block, where it belongs.
      h += '<div class="ddict"><div class="dhead">dictionary — not a gloss</div>';
      // asked with the chunk's word line, each row names its word's place in
      // the line (`i`): it goes under that word, and nothing is filtered here
      var line = lineOf(ch), pairs = null;
      if (line) { try { pairs = ParsehWordline.parse(line); } catch (_) {} }
      words.forEach(function (w) {
        h += dictLine(w, pairs && typeof w.i === 'number' ? pairs[w.i] || null : null);
      });
      // the definitions off, their switch never touched: the one moment to
      // say there are any, since without them the entry looks as if not
      if (DICT.defines && !opts.defs && localStorage.getItem('yt_defs') === null)
        h += '<div class="dnone">the dictionary explains these words in ' +
             esc(L.name || L.code) + ': “Show the dictionary\'s definitions”, in the ⚙ panel, shows what it says</div>';
      var src = (j.source && j.source.source) || 'a dictionary';
      if (j.source && j.source.licence) src += ' · ' + j.source.licence;
      if (defsTranslated())
        src += ' · the definitions put into ' + G.name + ' by ' +
               ((MT.about && MT.about.source) || 'a model');
      h += '<div class="dsrc">' + esc(src) + '</div></div>';
    }
    box.innerHTML = h;
    box.removeAttribute('data-fill');
    wireDefs(box);
    defsInto(box);
    mtInto(box, ch, sg, words);
    pairsInto(box, j, ch, sg);
    if (!box.childNodes.length)
      box.innerHTML = '<div class="dnone">' + (DICT.words
        ? 'the dictionary has nothing for these words'
        : 'nothing here has anything to say about this phrase') + '</div>';
  }

  /* ---------- a machine's reading, of the CAPTION ------------------------
     NOT OF THE PHRASE.  A phrase is a fragment by construction, and a
     fragment translated alone comes back as one; the caption holding it
     comes back as sense.  So the caption is translated, the whole of it is
     shown, and the words of it that seem to be THIS phrase's are marked
     inside it -- a guess, drawn as one, because the engine offers no word
     alignment: made from what the dictionary says the phrase's words mean
     (the lookup this panel has just drawn), never from where the phrase
     sits in its caption.  The book reader's block (lib/tex2html.py), same
     rule.

     NO BUTTON: the captions around the playing head have already been
     translated (preSentences), so there is nothing to wait for.          */
  function mtInto(box, ch, sg, words) {
    if (!MT.ready || typeof ParsehMT === 'undefined') return;
    var text = dictText(ch);
    var sentence = (sg && sg.text) || text;
    if (!sentence) return;
    var wrap = document.createElement('div');
    wrap.className = 'dmt';
    box.appendChild(wrap);
    if (MT.sent[sentence] !== undefined && MT.probe[text] !== undefined) {
      wrap.innerHTML = mtHTML(MT.sent[sentence], MT.probe[text], words,
                              sentence === text);
      return;
    }
    wrap.innerHTML = '<div class="dwait">reading the caption…</div>';
    var want = [sentence];
    if (text && text !== sentence) want.push(text);
    ParsehMT.translate(L.code, G.code, want).then(function (got) {
      mtKeep(MT.sent, sentence, got[0] || '');
      if (want.length > 1) mtKeep(MT.probe, text, got[1] || '');
      if (!wrap.isConnected) return;
      wrap.innerHTML = mtHTML(MT.sent[sentence], MT.probe[text] || '', words,
                              sentence === text);
      settleCloud();
    }).catch(function (err) {
      if (!wrap.isConnected) return;
      wrap.innerHTML = '<div class="dwait">' +
        esc((err && err.message) || 'the model could not be run') + '</div>';
      settleCloud();
    });
  }

  /* Each map bounded on its own, as the book reader bounds its two Maps --
     one shared list let a run of caption translations push every chunk probe
     out, and the two are used for different things. */
  function mtKeep(map, key, val, keep) {
    var fresh = map[key] === undefined;
    map[key] = val;
    if (!fresh) return;
    var keys = Object.keys(map);
    while (keys.length > (keep || MT_KEEP)) delete map[keys.shift()];
  }

  function mtHTML(out, probe, words, whole) {
    var src = (MT.about && MT.about.source) || 'a model';
    if (MT.about && MT.about.engine) src += ' · ' + MT.about.engine;
    var span = whole || !out ? null : ParsehMT.align(out, probe, words, G.code);
    var body;
    if (span) {
      // in as many places as the phrase's meaning landed in
      body = ParsehMT.marked(out, span).map(function (seg) {
        return seg.here ? '<b class="mthere' + (span.sure ? '' : ' mtmaybe') + '">' +
                          esc(seg.text) + '</b>'
                        : esc(seg.text);
      }).join('');
    } else {
      body = esc(out || '(it produced nothing)');
    }
    return '<div class="dhead">' +
           (whole ? 'a machine\'s reading — not a gloss'
                  : 'a machine\'s reading of the caption — not a gloss') +
           '</div><div class="mtout">' + body + '</div>' +
           (!whole && out ? '<div class="dnone">' + esc(mtWhy(span, 'phrase')) + '</div>' : '') +
           '<div class="dsrc">' + esc(src) + '</div>';
  }

  /* The line under the machine's reading: what the mark stands on -- which
     of the phrase's words the dictionary found there -- or, where nothing
     matched, that nothing is marked.  The book's mtWhy, same words. */
  function mtWhy(span, what) {
    if (!span)
      return 'no word of this reading matches what the dictionary says of the ' +
             what + ', so none is marked';
    var why = ParsehMT.why(span);
    return (span.sure ? 'this ' + what + ' is likely: ' : 'part of this ' + what + ' is likely: ') +
           '\u201c' + span.text + '\u201d' +
           (why ? ' \u2014 ' + why
                : span.by === 'translation' ? ' \u2014 by the ' + what + ' translated on its own' : '');
  }

  /* ---------- sentences somebody has already translated -------------------
     The book reader's block (lib/tex2html.py), for the same reason and under
     the same rule: this is NOT the caption in front of the reader and not a
     gloss of it, but a sentence a person translated that happens to share
     its rare words -- which is what lets somebody choose between the senses
     the dictionary lists without anybody guessing.                        */
  function pairHTML(p, j) {
      var marked = Parseh.pairMarkup(p, j, L, G);
      return '<div class="dpair"><div class="psrc" lang="' + esc(L.code) + '"' +
           (L.dir === 'rtl' ? ' dir="rtl"' : '') + '>' + marked.src + '</div>' +
           '<div class="pdst"' + GATTRS + '>' + marked.dst + '</div>' +
           ((p.matched && p.matched.length)
             ? '<div class="pwhy">shares ' + esc(p.matched.join(', ')) + '</div>'
             : '') + '</div>';
  }

  function pairsInto(box, j, ch, sg) {
    var pairs = (j.pairs || []).slice();
    if (!pairs.length) return;
    var wrap = document.createElement('div');
    wrap.className = 'dpairs';
    wrap.innerHTML = '<div class="dhead">a sentence somebody translated — not this one</div>' +
                     '<div class="dpair-list"></div>';
    var list = wrap.querySelector('.dpair-list');
    function addPair(p) {
      var holder = document.createElement('div');
      holder.innerHTML = pairHTML(p, j);
      if (holder.firstChild) list.appendChild(holder.firstChild);
    }
    pairs.forEach(addPair);
    var c = (j.corpus && j.corpus.source) ? j.corpus : (DICT.corpus || {});
    var src = c.source || 'a corpus';
    if (c.licence) src += ' · ' + c.licence;
    var source = document.createElement('div');
    source.className = 'dsrc'; source.textContent = src; wrap.appendChild(source);
    if (j.pairs_more) {
      var more = document.createElement('button');
      more.type = 'button'; more.className = 'dmore'; more.textContent = 'Load more';
      more.onclick = function () {
        more.disabled = true; more.textContent = 'Loading…';
        pAsk('/youtube/api/lookup', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(withLine({video: CFG.id, text: (ch && ch.fa) || '',
            sentence: (sg && sg.text) || '', corpus_only: true,
            corpus_offset: pairs.length, corpus_limit: 5}, ch || {}))
        }).then(function (r) { return r.json(); }).then(function (next) {
          if (!next || !next.ok) throw new Error('refused');
          var added = next.pairs || [];
          added.forEach(function (p) { pairs.push(p); addPair(p); });
          if (next.pairs_more) {
            more.disabled = false; more.textContent = 'Load more';
          } else more.remove();
          if (wrap.isConnected) settleCloud();
        }).catch(function () {
          more.disabled = false; more.textContent = 'Load more';
        });
      };
      wrap.appendChild(more);
    }
    box.appendChild(wrap);
  }

  /* WHAT AN ANSWER IS FOR: the phrase AND the caption it was asked in.  The
     server reads the sentence (a verb's recipe does: German leaves a
     separable verb's prefix at the clause's end), so one phrase is two
     answers in two captions -- `stand langsam` is aufstehen in "Er stand
     langsam von seinem Stuhl auf." and stehen in "Er stand langsam am
     Fenster.", each with its own "pret. stand auf" or "pret. stand"
     (dict/de.db, 2026-09-10).  Keyed by the phrase alone, one answer served
     both: with one phrase put in two captions, the second caption hovered
     showed the first's answer, and once the look-ahead had asked for both,
     the first showed the second's.  The book keys by chunk, which is both
     at once.  And the chunk's word line with them: the same text divided
     otherwise is other words, and another answer. */
  function dictKey(text, sentence, line) {
    // and the whole entry, asked for with the definitions on, kept apart
    var k = [text || '', sentence || '', line || ''];
    if (defsOn()) k.push('all');
    return JSON.stringify(k);
  }
  // the whole entry is asked for with the definitions on, and only then
  function withSenses(body) { if (defsOn()) body.senses = 'all'; return body; }

  function dictInto(box, ch) {
    var text = dictText(ch);
    if (!text) { box.remove(); return; }
    var sg = cloudCtx && cloudCtx.sg;
    var sentence = (sg && sg.text) || '', key = dictKey(text, sentence, lineOf(ch));
    if (DICT.cache[key]) { dictFill(box, DICT.cache[key], ch, sg); return; }
    box.innerHTML = '<div class="dwait">looking it up…</div>';
    pAsk('/youtube/api/lookup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(withSenses(withLine({ video: CFG.id, text: text, sentence: sentence }, ch)))
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) throw new Error('refused');
      DICT.cache[key] = j;
      // the cloud may have moved on while the server was answering
      if (box.isConnected) { dictFill(box, j, ch, sg); settleCloud(); }
    }).catch(function () {
      box.innerHTML = '<div class="dwait">the dictionary could not be reached</div>';
      if (box.isConnected) settleCloud();
    });
  }

  /* ---------------- preparing what you are about to hear -----------------
     The reader's own loop (lib/tex2html.py), with a caption where that has a
     subparagraph.  One request at a time; anything asked for by hand stops
     it; and a moment's quiet before it starts again.  Every request is one
     local SQLite read, so this costs nothing but a little idle time.     */
  var PRE = { busy: false, queue: [], timer: null, touched: Date.now() };
  ['pointerdown', 'keydown', 'wheel', 'scroll', 'touchstart'].forEach(function (e) {
    addEventListener(e, function () { PRE.touched = Date.now(); }, { passive: true });
  });

  function preTargets() {
    var from = active >= 0 ? active : 0, out = [];
    for (var i = from; i < Math.min(segs.length, from + AHEAD); i++) {
      var sg = segs[i];
      if (!sg || sg.plain) continue;
      (sg.chunks || []).forEach(function (ch) {
        if (!ch.fa || ch.voc) return;          // somebody wrote this one
        if (DICT.ready && opts.dict && !DICT.cache[dictKey(ch.fa, sg.text, lineOf(ch))])
          out.push({ ch: ch, sg: sg, dict: true });
      });
    }
    return out;
  }

  function preOne(t) {
    var post = function (where, body) {
      return fetch(where, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) }).then(function (r) { return r.json(); });
    };
    var chain = Promise.resolve(), line = lineOf(t.ch);
    if (t.dict)
      chain = chain.then(function () {
        return post('/youtube/api/lookup', withSenses(withLine({ video: CFG.id, text: t.ch.fa,
                 sentence: t.sg.text || '' }, t.ch)));
      }).then(function (j) {
        if (j && j.ok) { DICT.cache[dictKey(t.ch.fa, t.sg.text, line)] = j; }
      });
    return chain.catch(function () {});
  }

  /* THE CAPTIONS AHEAD, ALL IN ONE CALL: the engine's cost is almost all
     fixed, so ten cost about what one costs, and the panel opens filled. */
  function preSentences() {
    // ONLY WHILE THE SWITCH IS ON: the reading ahead is for somebody who has
    // asked to be helped.
    if (!MT.ready || !opts.dict || typeof ParsehMT === 'undefined') return null;
    var from = active >= 0 ? active : 0, want = [];
    for (var i = from; i < Math.min(segs.length, from + AHEAD); i++) {
      var sg = segs[i];
      if (!sg || sg.plain || !sg.text) continue;
      if (!(sg.chunks || []).some(function (c) { return c.fa && !c.voc; })) continue;
      if (MT.sent[sg.text] === undefined && want.indexOf(sg.text) < 0)
        want.push(sg.text);
    }
    if (!want.length) return null;
    return ParsehMT.translate(L.code, G.code, want).then(function (got) {
      want.forEach(function (t, k) { mtKeep(MT.sent, t, got[k] || ''); });
    }).catch(function () {});
  }

  /* THE DEFINITIONS AHEAD, where they are read in the gloss language: the
     ones the phrases ahead open with, all in one call once their lookups are
     in.  A failure stops it; the panel still asks, and says why.          */
  function preDefinitions() {
    if (!defsTranslated() || DEFT_FAILED) return null;
    var from = active >= 0 ? active : 0, want = [];
    for (var i = from; i < Math.min(segs.length, from + AHEAD) && want.length < 60; i++) {
      var sg = segs[i];
      if (!sg || sg.plain) continue;
      (sg.chunks || []).forEach(function (ch) {
        if (!ch.fa || ch.voc) return;
        var j = DICT.cache[dictKey(ch.fa, sg.text, lineOf(ch))];
        ((j && j.words) || []).forEach(function (w) {
          (w.hits || []).forEach(function (x) {
            (x.senses || []).slice(0, DEFS_SHOWN).forEach(function (s) {
              if (DEFT[s] === undefined && want.indexOf(s) < 0) want.push(s);
            });
          });
        });
      });
    }
    if (!want.length) return null;
    return ParsehMT.translate(L.code, G.code, want).then(function (got) {
      want.forEach(function (s, k) { mtKeep(DEFT, s, got[k] || '', DEFT_KEEP); });
    }).catch(function () { DEFT_FAILED = true; });
  }

  function prePump() {
    if (PRE.busy || cloudFor || editing) return;
    if (Date.now() - PRE.touched < 1500) return;
    var batch = preSentences();
    if (batch) { PRE.busy = true; batch.then(function () { PRE.busy = false; },
                                             function () { PRE.busy = false; }); return; }
    if (!PRE.queue.length) PRE.queue = preTargets();
    var t = PRE.queue.shift();
    if (!t) {
      // every lookup ahead is in: what their definitions say, in one call
      var defs = preDefinitions();
      if (defs) { PRE.busy = true; defs.then(function () { PRE.busy = false; },
                                             function () { PRE.busy = false; }); }
      return;
    }
    PRE.busy = true;
    preOne(t).then(function () { PRE.busy = false; }, function () { PRE.busy = false; });
  }
  function preStart() { if (!PRE.timer) PRE.timer = setInterval(prePump, 900); }

  /* ---------------- writing a phrase ----------------
     The three numbers the edit endpoint wants are already in the page: the
     video is CFG.id, the caption's element carries the index segEl() gave
     it (data-i) and the phrase carries its own within the caption (data-j,
     which is the chunk's number in annotations.json).  So nothing new is
     remembered anywhere -- the coordinates are read back off the DOM at the
     moment of the click, from the phrase the cloud is open on. */
  function coords() {
    var w = cloudFor;
    if (!w || !w.parentNode || !w.parentNode.parentNode) return null;
    var si = +w.parentNode.parentNode.dataset.i;   // .w -> .fa -> .seg
    var ci = +w.dataset.j;
    if (isNaN(si) || isNaN(ci)) return null;
    var sg = segs[si];
    var ch = sg && sg.chunks && sg.chunks[ci];
    // the caption goes with it: the sources sidebar reads `at.sg` to give
    // the model the whole caption, and without it every sidebar translated
    // the phrase alone -- the fragment the panel was built never to translate
    return ch ? { w: w, si: si, ci: ci, ch: ch, sg: sg } : null;
  }
  function stat(msg, bad) {
    var el = cloud.querySelector('.cstat');
    if (!el) return;
    el.textContent = msg || '';
    el.classList.toggle('bad', !!bad);
  }
  /* One edit, saved.  The server puts it through the checker first and
     refuses in the CHECKER'S OWN WORDS -- an fa that no longer reproduces
     its caption, a colour that is not one of the four, a chunk left
     half-written -- and that sentence is what the reader has to see: it
     names the rule that stopped him, where "failed" would name nothing.
     A refusal writes nothing at all, so the page and the file still agree
     and the form can simply stay open with the text in it.
     `said` is what the cloud says once it is written -- "saved ✓" unless the
     caller names it (a deleted gloss says so).  `done` runs on EVERY success,
     before `after` and whether or not the cloud is still on this phrase: what
     the page must remember about a write it made (a deleted gloss) cannot
     depend on where the pointer went while it was on its way. */
  function post(fields, after, said, done) {
    var at = coords();
    if (!at) return;
    stat('saving…');
    fetch('/youtube/api/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video: CFG.id, segment: at.si, chunk: at.ci,
                             fields: fields })
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'the edit was refused');
      // the answer replaces the chunk IN PLACE: every hover, card button
      // and copy in the transcript closes over this very object, and
      // swapping it for a new one would leave all of them on the old text
      var ch = at.ch, now = res.chunk_now || {};
      Object.keys(ch).forEach(function (k) { delete ch[k]; });
      Object.keys(now).forEach(function (k) { ch[k] = now[k]; });
      // AND THE CAPTION'S TEXT, which the page keeps apart from its chunks:
      // a phrase marked free takes its caption's text with it, the server
      // rewrites that text, and the shift-click copy of the caption, the
      // dictionary's sentence, "ask an LLM" and the timings all read it
      // from here -- they went on reading the old text until a reload
      if (typeof res.text === 'string' && at.sg === segs[at.si]) at.sg.text = res.text;
      // the file has just changed under any prompt the LLM panel is holding
      // for a copy by hand -- a gloss deleted here would go out in it again,
      // old words and all, and come back filled (rgForget, below)
      rgForget();
      if (done) done(ch);
      paintWords(at.w, ch);
      paintCol(at.w, ch);
      // a note written, changed or taken off lights or dims its phrase now (with
      // ✱ notes on), and the count follows
      pnPaint();
      // the answer may arrive after the pointer has moved to the next
      // phrase, whose cloud must not be told about this one
      if (cloudFor !== at.w) return;
      if (after) after(ch);
      stat(said || 'saved ✓');
    }).catch(function (e) {
      // a refusal is never dropped, though: it names the rule the edit
      // broke, so a cloud that has moved on comes back to the phrase the
      // message is about and says it there
      if (cloudFor !== at.w && !editing) openCloud(at.w, at.ch, segs[at.si]);
      var msg = (e && e.message) || String(e);
      // the one refusal that has a box to answer it: the phrase does not
      // reproduce the transcript, and the transcript is exactly what the
      // box at the foot of the form says need not be reproduced.  It is
      // below the fold of a scrolling column, so the message would
      // otherwise be a dead end -- bring it into view
      if (/reproduce the text|transcript\.txt/.test(msg)) {
        var row = cloud.querySelector('.efreerow');
        if (row) row.scrollIntoView({block: 'nearest'});
      }
      stat(msg, true);
    });
  }
  function setColour(col) {
    var at = coords();
    if (!at || (at.ch.col || '') === col) return;   // already that mark
    post({ col: col }, function (ch) {
      Array.prototype.forEach.call(cloud.querySelectorAll('.sw'), function (b) {
        b.classList.toggle('on', (b.dataset.col || '') === (ch.col || ''));
      });
    });
  }
  /* The fields annwrite lets a page set, each named the way THIS video
     names them: the first is the language taught, the reading row exists
     only where the language has a reading, the transliteration is called
     what the registry calls it (Italian gives a pronunciation, Japanese
     rōmaji), and the meaning is called after the language it is written
     in.  The third column is what the field holds: 'tl' target text, so
     it takes the language's face and direction, 'gl' gloss prose, so it
     takes the gloss language's -- and the vocabulary is 'gl' too, being a
     line of that prose with target words quoted inside it.  The note, last, is
     prose in the gloss language as well, and is called what it is. */
  function editRows() {
    var rows = [['fa', L.name.toLowerCase(), 'tl']];
    if (L.reading) rows.push(['kana', L.reading_label || 'reading', 'tl']);
    rows.push(['tr', L.translit_label || 'transliteration', ''],
              ['voc', 'vocabulary', 'gl'],
              ['en', GLOSS_LABEL, 'gl'],
              ['note', 'note', 'gl']);
    return rows;
  }
  // Each box the size of what is in it before the cloud is placed: a phrase,
  // a vocabulary line and a meaning are all different lengths, and a field
  // showing half of its own text cannot be read back.  MEASURED AGAIN
  // whenever the cloud changes width, not once at open.  A wide window keeps
  // the field column's width when the sources open (style.css), but a
  // narrow one stacks them and widens the whole cloud -- 434px of fields
  // become 646 in a 700px window -- and any window can be resized with the
  // editor open; a vocabulary line sized for three lines at the old width
  // keeps an empty third one, or loses one, at the new.  The height is let
  // go first, or a box could only ever grow.
  function fitFields() {
    Array.prototype.forEach.call(cloud.querySelectorAll('.ef'), function (el) {
      el.style.height = '';
      el.style.height = (el.scrollHeight + 2) + 'px';
    });
  }
  /* THE WORD LINE, in the editor of a language divided into words: the
     shared strip (Parseh.wordstrip) under the text box, its check run against
     what that box holds -- so it is made again, keeping its line, whenever
     the text or the reading is changed.  Propose is offered once the server
     has said, a single time for the page, that it can propose at all. */
  var strip = null, proposing = null, canPropose = false;
  function askPropose() {
    if (!proposing)
      proposing = fetch('/youtube/api/words', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video: CFG.id, text: '' })
      }).then(function (r) { return r.json(); }).then(function (j) {
        return (canPropose = !!(j && j.ok && j.available));
      }).catch(function () { return false; });
    return proposing;
  }
  function mountStrip(at, value) {
    var box = cloud.querySelector('.ewords');
    if (!box) return;
    var fa = cloud.querySelector('.ef[data-f="fa"]');
    var said = cloud.querySelector('.ef[data-f="' + (L.reading ? 'kana' : 'tr') + '"]');
    var o = { lang: L, fa: fa ? fa.value : at.ch.fa, value: value,
              reading: said ? said.value : '', reorders: !!(CFG.reorders || reorders),
              door: 'video',
              // what the line said is the server's answer no longer
              onchange: function () { stat(''); } };
    if (canPropose)
      o.propose = function () {
        return fetch('/youtube/api/words', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          // the reading box as it stands reads the proposed words
          body: JSON.stringify({ video: CFG.id, text: fa ? fa.value : at.ch.fa,
                                 reading: said ? said.value : (at.ch[L.reading ? 'kana' : 'tr'] || '') })
        }).then(function (r) { return r.json(); }).then(function (j) {
          if (!j || !j.ok) throw new Error((j && j.error) || 'nothing could be proposed');
          return j.available ? (j.words || '') : '';
        });
      };
    if (strip) strip.destroy();
    strip = Parseh.wordstrip(o);
    box.appendChild(strip.el);
  }
  function wordsInto(at) {
    if (!L.words) return;
    mountStrip(at, at.ch.words || '');
    [cloud.querySelector('.ef[data-f="fa"]'),
     cloud.querySelector('.ef[data-f="' + (L.reading ? 'kana' : 'tr') + '"]')].forEach(function (el) {
      if (el) el.addEventListener('input', function () { mountStrip(at, strip.value()); });
    });
    if (!proposing) askPropose().then(function (yes) {
      // not under somebody typing into the strip: the next editor has it
      if (yes && editing && cloudFor === at.w && strip && !strip.el.contains(document.activeElement))
        mountStrip(at, strip.value());
    });
  }
  /* THE VOCABULARY ROW, as the book's chunk sheet has it (lib/tex2html.py):
     what the line reads as, drawn by lib/vocline.js the way the reader and
     the cloud draw it; the box; the four buttons that write a book's entries,
     each saying what it is for (lib/vocbuttons.js); and a note.  It is a div
     with a label for the box, not a label round everything: buttons inside a
     label would be a second thing the label labels. */
  function vocRow(at, f) {
    return '<div class="erow evrow"><label class="elab" for="evoc">' + esc(f[1]) + '</label>' +
           '<div class="evcap">reads as</div><div class="evnow"></div>' +
           '<textarea id="evoc" class="ef gl" data-f="voc" rows="2">' + esc(at.ch.voc || '') + '</textarea>' +
           '<div class="evbtns" role="group" aria-label="write an entry">' +
           ['dw', 'vb', 'bw', 'pw'].map(function (k) {
             return '<button type="button" data-ins="' + k + '"></button>';
           }).join('') + '</div>' +
           '<div class="efnote">Entries are parted by <code>;</code>. The buttons write the books&#8217; ' +
           'entries, and <b>reads as</b> above shows the line the way the cloud will set it; a plain line ' +
           'is fine too. Only <code>\\dw</code> <code>\\vb</code> <code>\\bw</code> <code>\\pw</code>, ' +
           '<code>\\textit</code>, <code>\\emph</code> and <code>\\nobreak</code> may be written; ' +
           '<code>% &amp; # _ $</code> are ordinary characters in a video.</div></div>';
  }
  /* THE NOTE ROW: the aside under the meaning, offered on every phrase -- a note
     is as much written here as changed.  One row that grows with what is in it,
     and under it the line that says how a note is taken off: there is no button
     for that, an emptied box is how every field of this form is cleared. */
  function noteRow(at, f) {
    return '<div class="erow"><label class="elab" for="enote">' + esc(f[1]) + '</label>' +
           '<textarea id="enote" class="ef gl" data-f="note" rows="1">' + esc(at.ch.note || '') +
           '</textarea><div class="efnote">Shown under the meaning in the cloud. ' +
           'Empty it to take the note off.</div></div>';
  }
  // what the box holds, drawn: a macro line as the reader draws it, any other
  // as the cloud draws a plain one; a line not finished says what is short
  function vocNow(ta, el) {
    var v = ta.value;
    if (!v.trim()) { el.innerHTML = '<span class="none">no vocabulary line yet</span>'; return; }
    if (window.ParsehVocline && ParsehVocline.isMacro(v)) {
      try {
        // the four skeletons as they are written say nothing yet
        el.innerHTML = ParsehVocline.render(v, L) || '<span class="none">an entry with nothing in it yet</span>';
      } catch (e) { el.innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; }
    } else el.innerHTML = glossHTML(v);
    // a line that grew the form past the foot of the window is placed again
    var r = cloud.getBoundingClientRect();
    if (cloudFor && r.bottom > (document.documentElement.clientHeight || window.innerHeight) - 4)
      placeCloud(cloudFor);
  }
  function openEditor() {
    var at = coords();
    if (!at) return;
    editing = true;
    clearTimeout(hideTimer);
    // the page follows the playing video, and the cloud is fixed to the
    // viewport: left running, the video would scroll the phrase out from
    // under the form being typed into
    if (player && ready && player.getPlayerState &&
        player.getPlayerState() === 1) {
      editWasPlaying = true; player.pauseVideo();
    } else editWasPlaying = false;
    // the coordinates are shown as the checker writes them, so a refusal
    // about "segment 4 chunk 1" is recognisably about this phrase
    //
    // THE SOURCES OPEN TO THE LEFT OF THE FIELDS, AND THE WINDOW GROWS.  They
    // used to be a block over the fields in the same 460px column: up to 40vh
    // of dictionary rows, a model's reading and somebody's sentences pushed
    // the text, the vocabulary and the meaning down under the fold, so the
    // line being copied and the box it was being copied into were never on
    // screen together -- and the column was too narrow for a verb's forms.
    // So the body is two columns, .eside | .emain, each scrolling on its own,
    // with the head above them and the save row and the colours below them
    // (outside both, so neither column can scroll them away).  Everything
    // stays inside #cloud: the click dispatch and the hover-close below both
    // assume the form lives there, and tests/mtcheck.py looks for
    // `#cloud .eside` and `#cloud .esrcbody`.
    var h = '<div class="ehead">editing<span class="ewhere">segment ' + at.si +
            ' chunk ' + at.ci + '</span><span class="sp"></span>' +
            '<button type="button" class="esrc" title="what the dictionary, ' +
            'the model, the corpus and an external chatbot can offer for this ' +
            'phrase">\u2295 sources</button>' +
            '<button type="button" class="ecancel" title="close (Esc)">&#10005;</button></div>' +
            '<div class="ebody">' +
            '<div class="eside"' + (srcOpen ? '' : ' hidden') + '>' +
            '<div class="enote">Everything the toolbox already knows about ' +
            'this phrase. Nothing here is a gloss and nothing writes itself: ' +
            'each line has the buttons that put it into a field.</div>' +
            '<div class="esrcbody">looking\u2026</div></div>' +
            '<div class="emain">';
    editRows().forEach(function (f) {
      if (f[0] === 'voc' && window.ParsehVocButtons) { h += vocRow(at, f); return; }
      if (f[0] === 'note') { h += noteRow(at, f); return; }
      h += '<label class="erow"><span class="elab">' + esc(f[1]) + '</span>' +
           '<textarea class="ef' + (f[2] ? ' ' + f[2] : '') + '" data-f="' + f[0] +
           '" rows="' + (f[0] === 'voc' || f[0] === 'en' ? 2 : 1) + '">' +
           esc(at.ch[f[0]] || '') + '</textarea></label>';
      // the word line, under the text it divides (a div, not a label: the
      // strip is buttons and boxes of its own)
      if (f[0] === 'fa' && L.words)
        h += '<div class="erow"><span class="elab">words</span><div class="ewords"></div></div>';
    });
    // WHAT YOUTUBE HEARD IS SOMETIMES WRONG.  transcript.txt is what the
    // caption's text is held against, so an edit that changes a word is
    // refused -- unless this box says the phrase is the annotator's.  The
    // reading editions offer the same, per paragraph (lib/tex2html.py).
    h += '<div class="erow efreerow"><span class="elab">the transcript</span>' +
         '<label class="echk"><input type="checkbox" class="efree"' +
         (at.ch.free ? ' checked' : '') + '> this phrase need not reproduce ' +
         '<code>transcript.txt</code></label>' +
         '<div class="efnote">The pasted transcript is what YouTube heard, and it is ' +
         'sometimes wrong. The check that a caption still reproduces it is what stops ' +
         'a model, or a careless edit, quietly rewriting the video &mdash; and it stays ' +
         'on for every other caption. Ticked, <b>this phrase is yours</b>: an edit that ' +
         'departs from the transcript is written instead of refused, the ' +
         'caption&#8217;s text follows its phrases, and the checker reports the caption ' +
         'as not checked rather than as a fault. The whole CAPTION, because that is what ' +
         'is compared: one phrase departing takes its caption with it.</div></div>';
    h += '</div></div>';                  // .emain, .ebody
    h += '<div class="mkrow"><button type="button" class="esave">save' +
         ' <span class="kbd">Ctrl+↵</span></button>' +
         // its own button, beside save and never in the hover cloud: taking a
         // gloss off is a distinct thing from saving one (paintDel below
         // hides, greys and offers the undo)
         '<button type="button" class="edel" title="' + esc(DEL_TITLE) +
         '">delete gloss</button>' +
         '<button type="button" class="eundo" hidden title="write the deleted ' +
         'gloss back">undo delete</button>' +
         '<button type="button" class="edv" data-dv="split" title="cut this ' +
         'phrase in two">✂ cut in two</button>' +
         '<button type="button" class="edv" data-dv="next" title="join this ' +
         'phrase to the one after it">join next</button>' +
         (at.ci > 0 ? '<button type="button" class="edv" data-dv="prev" ' +
          'title="join the phrase before this one to it">join previous</button>'
          : '') + '</div>';
    cloud.classList.add('editing');
    // the wide window from the first frame when the sources were left open:
    // the fields are measured below at the width they will actually have
    cloud.classList.toggle('sideon', srcOpen);
    cloud.innerHTML = h + colourRow(at.ch);
    Array.prototype.forEach.call(cloud.querySelectorAll('.ef.tl'), targetAttrs);
    Array.prototype.forEach.call(cloud.querySelectorAll('.ef.gl'), glossAttrs);
    var vbox = cloud.querySelector('.ef[data-f="voc"]'), vnow = cloud.querySelector('.evnow'),
        vbtns = cloud.querySelector('.evbtns');
    if (vnow) {
      glossAttrs(vnow);
      vocNow(vbox, vnow);
      vbox.addEventListener('input', function () { vocNow(vbox, vnow); });
    }
    if (vbtns) {
      ParsehVocButtons.mount(vbtns, { lang: L, gloss: G });
      vbtns.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('[data-ins]') : null;
        if (b) ParsehVocButtons.insert(vbox, b.getAttribute('data-ins'));
      });
    }
    paintDel(at);
    fitFields();
    // the note's row grows as it is typed into, and the form is placed again
    // when that takes it past the foot of the window (as the vocabulary's does)
    var nbox = cloud.querySelector('.ef[data-f="note"]');
    if (nbox) nbox.addEventListener('input', function () {
      nbox.style.height = ''; nbox.style.height = (nbox.scrollHeight + 2) + 'px';
      var r = cloud.getBoundingClientRect();
      if (cloudFor && r.bottom > (document.documentElement.clientHeight || window.innerHeight) - 4)
        placeCloud(cloudFor);
    });
    wordsInto(at);
    var srcBtn = cloud.querySelector('.esrc');
    if (srcBtn) {
      srcBtn.classList.toggle('on', srcOpen);
      srcBtn.onclick = function (e) {
        e.preventDefault(); e.stopPropagation();
        srcShow(!srcOpen, at);
      };
    }
    if (srcOpen) srcFill(at);
    placeCloud(at.w);
    var first = cloud.querySelector('.ef');
    if (first) first.focus();
  }

  /* ---------- the sources sidebar ----------------------------------------
     THE SAME THREE THINGS THE READER'S PANEL SHOWS, where the gloss is
     actually written -- reading them in the cloud and retyping them into the
     editor was the whole of the work, and retyping is where a romanisation
     loses a macron.  It writes into a BOX and never into the video: what
     lands here is unsaved, for somebody to correct before they press save.
     Closed by default, and the choice is remembered.  The book reader's
     sidebar (lib/tex2html.py), same rule.                                 */
  var SRC_KEY = 'yt_side';
  var srcOpen = localStorage.getItem(SRC_KEY) === '1';

  function srcShow(on, at) {
    srcOpen = on;
    localStorage.setItem(SRC_KEY, on ? '1' : '0');
    var box = cloud.querySelector('.eside');
    var btn = cloud.querySelector('.esrc');
    if (box) box.hidden = !on;
    if (btn) btn.classList.toggle('on', on);
    // the window widens with the sources in it (style.css, .sideon), which
    // changes the width every field wraps at -- so they are measured again
    // before the cloud is placed at its new size
    cloud.classList.toggle('sideon', on && editing);
    fitFields();
    if (on && at) srcFill(at);
    else srcGen++;          // closed: whatever is still on its way is for nobody
    if (at) placeCloud(at.w);
  }

  /* THE ENTRIES THE SIDEBAR PUTS ARE THE BOOKS' when lib/vocline.js is on the
     page (it is, wherever the player is served): the \vb the language's recipe
     built -- `tex_video`, the book's own with what only a video says inside
     its parenthesis and the chunk's own form named after it -- or a \dw for a
     word, parted from what is there by "; " as a book's are.  A page without
     it puts the plain line it always did. */
  var MACRO_ENTRIES = typeof ParsehVocline !== 'undefined';
  var VOC_JOIN = MACRO_ENTRIES ? '; ' : ' · ';
  function vbEntry(vb) { return MACRO_ENTRIES && vb.tex_video ? vb.tex_video : vb.here; }
  function cpEntry(cp) { return MACRO_ENTRIES && cp.tex_video ? cp.tex_video : cp.plain; }
  function dwEntry(word, sound, sense) {
    if (!MACRO_ENTRIES) return word + (sound ? ' ' + sound : '') + (sense ? ' ' + sense : '');
    return '\\dw{' + word + '}{' + (sound || '') + '}' + (sense ? ' ' + sense : '');
  }

  // append rather than replace: a vocabulary line is built entry by entry
  function srcPut(field, text, sep) {
    if (!text) return;
    var el = cloud.querySelector('.ef[data-f="' + field + '"]');
    if (!el) return;
    var had = (el.value || '').trim();
    el.value = had ? had + (sep === undefined ? ' ' : sep) + text : text;
    el.style.height = (el.scrollHeight + 2) + 'px';
    // what the vocabulary reads as follows the box (the form's own listener)
    if (field === 'voc') el.dispatchEvent(new Event('input', { bubbles: true }));
    el.focus();
    // at the end, so the next thing typed carries the line on rather than
    // landing in front of what was just put there
    try { el.setSelectionRange(el.value.length, el.value.length); }
    catch (e) { /* a field that cannot be indexed is a field left alone */ }
  }

  // a button is [label, title, what it does] and, fourth, a class of its own
  // (`sgap`: it puts a line somebody still has to finish)
  function srcRow(into, mainHTML, sub, buttons) {
    var d = document.createElement('div');
    d.className = 'srow';
    d.innerHTML = '<div class="stxt">' + mainHTML + '</div>' +
                  (sub ? '<div class="ssub">' + esc(sub) + '</div>' : '') +
                  '<div class="sput"></div>';
    var put_ = d.querySelector('.sput');
    buttons.forEach(function (b) {
      var el = document.createElement('button');
      el.type = 'button'; el.textContent = b[0]; el.title = b[1];
      if (b[3]) el.className = b[3];
      el.onclick = function (e) { e.preventDefault(); e.stopPropagation(); b[2](); };
      put_.appendChild(el);
    });
    into.appendChild(d);
    return d;
  }

  function srcHead(into, text) {
    var h = document.createElement('h4');
    h.textContent = text;
    into.appendChild(h);
  }

  // a heading and the block under it, holding its place with a waiting line
  // until its answer comes back (the book's sideSection)
  function srcSection(into, head, waiting) {
    srcHead(into, head);
    var box = document.createElement('div');
    box.innerHTML = '<div class="snone"></div>';
    box.firstChild.textContent = waiting;
    into.appendChild(box);
    return box;
  }

  /* THE LEMMA'S OWN SOUND, for an entry that names the lemma.  hit.translit
     is the sound of the form the reader is looking at wherever the source
     romanises its forms -- mi-sāzam for می‌سازم -- which is right for the
     transliteration box and wrong beside the headword: the vocabulary line
     came out "ساختن mi-sāzam", an infinitive wearing a first person's
     sound.  The server says the lemma's own as head_sound (the pronunciation
     it derived, or the entry's romanisation); a server from before that
     field did not, and then the pronunciation is still the lemma's, and
     translit is too wherever the form had no romanisation of its own. */
  function headSound(h) {
    if (typeof h.head_sound === 'string') return h.head_sound;
    return h.said || (h.of_form ? '' : (h.translit || ''));
  }

  /* A word of the language inside the row's chrome, isolated.  The row is
     left-to-right and an arrow between two words is a neutral: "فکر کردن →
     کردن" left bare resolves the arrow to the Persian on both sides of it
     and prints the three right to left -- the lemma first, the arrow
     pointing from it to the headword, the relation read backwards.  An
     isolate is one neutral to the paragraph around it, so the pair reads
     left to right like the rest of the row, each word keeping its own order
     inside.  The lang is the language's: a Han character is drawn one way
     for Chinese and another for Japanese. */
  function tlWord(s, title) {
    return '<bdi lang="' + esc(L.code) + '"' +
           (title ? ' title="' + esc(title) + '"' : '') + '>' + esc(s) + '</bdi>';
  }

  /* What the recipe says is left to fill, whole, and one item to a line
     where it says several.  The items are sentences somebody reads and they
     carry their own punctuation -- Persian's compound puts "bw for فکر fekr
     after it: to think" there, English "the sound of go (the dictionary's
     /ɡəʊ/ is ...)" -- so the ", " they used to be joined with made two items
     and one indistinguishable, and any other separator a meaning can hold
     would too (";" is in Wiktionary's senses: "to research and develop; to
     do R&D").  A line each cannot be misread.  The row draws its lines
     (srcHit); a title has only "\n" to give, so it gets that and a dot. */
  function missTitle(items) {
    return items.length === 1 ? ' ' + items[0]
                              : '\n\u00b7 ' + items.join('\n\u00b7 ');
  }
  // a list the server sent, as strings; anything else as no list at all
  function strs(x) {
    return Array.isArray(x) ? x.filter(Boolean).map(String) : [];
  }

  /* One dictionary hit, as a row with the buttons that put it somewhere.
     A VERB IS OFFERED AS A VERB.  Where the language's recipe recognised the
     hit (hit.vb, lib/verbs/), the vocabulary entry is the one a person
     writes for a verb -- the form in the phrase, then the lemma with its
     other forms: "آمده āmade come (آمدن āmadan · pres. آ ā · past آمد āmad
     · to come)", as this video's own annotations write آمده -- and the row
     shows those forms under the headword, so what the button will put is
     read before it is pressed.  The recipe says when it could not fill
     something the language needs (a stem nobody romanised); the button then
     says what, and so does the row, rather than the line going in looking
     finished.  Anything else is the plain headword, its sound, a sense.

     WHAT GOES IN IS NAMED WHEN IT IS NOT THE HEADWORD.  German puts a
     separated verb back together: "stand … auf" is looked up as stand,
     reaches stehen, and the recipe hands back aufstehen's \vb -- whose line,
     "pret. stand auf · p.p. aufgestanden", sat under "stehen" unexplained.
     A reflexive does the same (freuen gives sich freuen), and a Persian
     compound (فکر کردن gives its light verb کردن, the noun left to a \bw).
     So the row says "stehen → aufstehen": the arrow is "what the vocabulary
     gets" when that is ANOTHER word than the one heading the row.

     THE ROW IS HEADED AS THE CAPTION SPELLS IT, as the book's is (sideHit):
     h.spelled, 睡觉 where Wiktionary files the entry under 睡覺, with the
     dictionary's headword in the title.  It used to be headed by the
     headword and point at the spelling -- and a verb's lemma is written the
     way the video writes it, so the real 睡觉 hit (dict/zh.db) read
     "睡覺 → 睡觉", one word pointing at itself.  Compared folded
     (wordKey), as the book compares, because Arabic did the same with its
     marks: "وصل → وَصَلَ", the bare page title and the vowelled \vb of one
     verb. */
  function srcHit(into, h) {
    var sense = (h.senses || [])[0] || '';
    var vb = (h.vb && h.vb.here) ? h.vb : null;
    var head = h.spelled || h.headword;
    var word = (vb && vb.lemma) || head;
    var btns = [], main = tlWord(head, h.spelled && h.spelled !== h.headword
                                         ? 'the dictionary files it under ' + h.headword
                                         : '') +
                          (wordKey(word) !== wordKey(head) ? ' \u2192 ' + tlWord(word) : '') +
                          (h.translit ? ' \u00b7 ' + esc(h.translit) : '');
    if (h.translit)
      btns.push(['romanisation \u2192', 'put it in the transliteration',
                 function () { srcPut('tr', h.translit); }]);
    if (vb) {
      var missing = strs(vb.missing);
      // hints the recipe could give and not decide -- Arabic's other masdars,
      // the right one depending on the sense -- are a choice and not a gap:
      // under the forms, quieter than they are, never in `missing`'s colour
      // and never in the button's list of what to fill
      var notes = strs(vb.notes);
      // INCOMPLETE IS WHAT THE RECIPE SAYS, whether or not it could name the
      // gap -- and then the row still says so, in the book's words.  The
      // title used to send the reader to "the line above" and the row drew
      // no such line, since there was no item to put on it.
      var partial = vb.complete === false;
      if (partial && !missing.length)
        missing = ['part of it (the dictionary did not say which)'];
      // AND THE BUTTON LOOKS UNFINISHED, dashed (style.css .sgap), as the
      // book's \vb button does.  The row says what is left, but the button
      // is the thing pressed, and the book's says so on its border: the same
      // half-made verb was drawn dashed in the book's editor and solid in
      // this one, as if the video's line went in finished.
      // A VERB THAT IS MORE THAN ONE WORD GETS ITS OWN BUTTON.  لبخند زدن is
      // ONE verb, and what the row says under "to fill in" -- a word to put
      // after the light verb -- is the other half of one entry, not a second
      // entry beside it.  A video's line has no macro to say which word
      // belongs to which, so the compound goes in as a whole and is glossed
      // as a whole (docs/lang/fa.md: `compounds as فکر کردن fekr kardan to
      // think`), with the verb that does the conjugating after it.  That is
      // another line than "\u2192 vocabulary" puts, not that line with something
      // added to it, so it is its own button -- and it stands first, because
      // for a compound it is the one to press.
      var cp = (vb.compound && vb.compound.plain) ? vb.compound : null;
      if (cp)
        btns.push(['\u2192 ' + cp.name,
                   cp.whole + (cp.sound ? ' ' + cp.sound : '') +
                   ' is ONE verb written in two words, not two entries: ' +
                   word + ' carries the forms, ' + cp.word +
                   ' never changes, and the pair means ' +
                   (cp.mean || 'what neither word means alone') +
                   '. This puts the whole compound in as one entry:\n' + cpEntry(cp) +
                   (cp.complete ? ''
                    : '\n\nthen fill in by hand what the dictionary did not give:' +
                      missTitle(cp.missing || [])),
                   function () { srcPut('voc', cpEntry(cp), VOC_JOIN); },
                   cp.complete ? '' : 'sgap']);
      btns.push(['\u2192 vocabulary', partial
                   ? 'add this verb and its forms to the vocabulary line \u2014 ' +
                     'then fill in by hand what the dictionary did not give:' +
                     missTitle(missing)
                   : 'add this verb and its forms to the vocabulary line' +
                     (MACRO_ENTRIES ? ':\n' + vbEntry(vb) : ''),
                 function () { srcPut('voc', vbEntry(vb), VOC_JOIN); },
                 partial ? 'sgap' : '']);
      if (vb.line || notes.length || partial) {
        main += '<div class="svb">' + (vb.line ? glossHTML(vb.line) : '');
        notes.forEach(function (n) {
          main += '<div class="svbnote">' + glossHTML(n) + '</div>';
        });
        if (partial)
          main += '<div class="svbmiss"><span>to fill in: </span><span>' +
                  missing.map(glossHTML).join('<br>') + '</span></div>';
        main += '</div>';
      }
    } else {
      var hs = headSound(h);
      btns.push(['\u2192 vocabulary', 'add this word to the vocabulary line',
                 function () { srcPut('voc', dwEntry(word, hs, sense), VOC_JOIN); }]);
    }
    if (sense)
      btns.push(['meaning \u2192', 'put this sense in the meaning',
                 function () { srcPut('en', sense); }]);
    // A WORD THE SPOKEN PASS READ says so under its row, as the reading panel's card does (lib/parseh.js)
    if (h.spoken && Parseh.spoken) {
      var sb = Parseh.spoken.block(h, { lang: L.code, dir: L.dir });
      if (sb) main += '<div class="svb">' + sb.outerHTML + '</div>';
    }
    var row = srcRow(into, main, sense, btns);
    // ENGLISH, EXPLAINED IN ENGLISH, read in the gloss language here too --
    // the book's sideHit: the sense as the model puts it, under the row, with
    // the buttons that put that, while the switch over the dictionary's rows
    // (or the header's) is on
    if (sense && DICT.defines && MT.ready) {
      var t = document.createElement('div');
      t.className = 'sdef'; t.dataset.def = sense;
      if (!vb) {
        var hsd = headSound(h);
        t.dataset.voc = dwEntry(word, hsd, '') + ' ';
      }
      t.hidden = !opts.defsMt;
      row.appendChild(t);
    }
  }
  // the buttons under a sense read in the gloss language, once it is in
  function srcDefPut(el, text) {
    if (!text) return;
    var put_ = document.createElement('div');
    put_.className = 'sput';
    var btns = [];
    if (el.dataset.voc !== undefined)
      btns.push(['\u2192 vocabulary', 'add this word to the vocabulary line, its sense in ' + G.name,
                 function () { srcPut('voc', el.dataset.voc + text, VOC_JOIN); }]);
    btns.push(['meaning \u2192', 'put this sense, in ' + G.name + ', in the meaning',
               function () { srcPut('en', text); }]);
    btns.forEach(function (b) {
      var x = document.createElement('button');
      x.type = 'button'; x.textContent = b[0]; x.title = b[1];
      x.onclick = function (e) { e.preventDefault(); e.stopPropagation(); b[2](); };
      put_.appendChild(x);
    });
    el.appendChild(put_);
  }
  // the switch inside the editor, just over the dictionary's rows
  function srcDefsSwitch(dict) {
    if (!dict || !(DICT.defines && MT.ready)) return;
    var bar = document.createElement('div');
    bar.className = 'sdefbar';
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'sdefmt';
    b.textContent = 'in ' + G.name.toLowerCase();
    b.title = 'each sense put into ' + G.name + ' under it, by the translation model ' +
              "on this machine: a machine's reading, not a gloss";
    b.classList.toggle('on', opts.defsMt);
    b.onclick = function (e) { e.preventDefault(); e.stopPropagation(); setDefsMt(!opts.defsMt); };
    bar.appendChild(b);
    dict.parentNode.insertBefore(bar, dict);
  }
  // an open editor's sources after the switch moved: the senses in the gloss
  // language shown or hidden, and read where they are wanted
  function srcDefs() {
    var body = editing ? cloud.querySelector('.esrcbody') : null;
    if (!body) return;
    body.querySelectorAll('.sdefmt').forEach(function (b) { b.classList.toggle('on', opts.defsMt); });
    body.querySelectorAll('.sdef').forEach(function (t) { t.hidden = !opts.defsMt; });
    if (opts.defsMt && DICT.defines && MT.ready) defsRead(body, '.sdef', null, srcDefPut);
  }

  // One rendering path for both the browser model and a pasted external
  // answer.  That keeps the dictionary-derived marks and insertion buttons
  // identical.  The external chatbot has no phrase-only probe, so its marks
  // are derived from `words` alone.
  function srcTranslation(box, whole, probe, words, text, sentence) {
    box.textContent = '';
    var split = !!(text && sentence && text !== sentence);
    var span = split && whole
      ? ParsehMT.align(whole, probe || '', words || [], G.code) : null;
    if (span) {
      var why = ParsehMT.why(span);
      srcRow(box, ParsehMT.marked(whole, span).map(function (seg) {
                return seg.here ? '<span class="shere">' + esc(seg.text) + '</span>'
                                : esc(seg.text);
              }).join(''),
              (span.sure ? 'the marked words are this phrase\u2019s'
                         : 'the marked words are part of this phrase\u2019s') +
              (why ? ': ' + why
                   : span.by === 'translation' ? ', by the phrase translated on its own' : ''),
              [['the marked words \u2192 meaning', 'put the guess in the meaning',
                function () { srcPut('en', span.text); }],
               ['the whole caption \u2192 meaning', 'put the whole translation in',
                function () { srcPut('en', whole); }]]);
    } else {
      srcRow(box, esc(whole || '(it produced nothing)'),
              whole && split
                ? 'no word of it matches what the dictionary says of this phrase' : '',
              whole ? [['meaning \u2192', 'put it in the meaning',
                        function () { srcPut('en', whole); }]] : []);
    }
  }

  function srcContext(si) {
    var out = { before: [], after: [] };
    for (var d = 1; d <= 3; d++) {
      var prev = segs[si - d], next = segs[si + d];
      var p = prev && String(prev.text || '').trim();
      var q = next && String(next.text || '').trim();
      if (p) out.before.unshift(p);
      if (q) out.after.push(q);
    }
    return out;
  }

  function srcLLM(box, at, text, evidence, gen) {
    box.textContent = '';
    if (typeof ParsehLLM === 'undefined' || !window.ParsehLLMRow) {
      box.innerHTML = '<div class="snone">the prompt helper could not be loaded</div>';
      return;
    }
    var sentence = (at.sg && at.sg.text) || text;
    var around = srcContext(at.si);
    var controls = document.createElement('div'); controls.className = 'sllmctl';
    // THE ROW (lib/llmrow.js) draws the button, the size and the reminder.  A
    // click in it goes no further: the cloud has handlers of its own above it.
    var askBox = document.createElement('div');
    askBox.addEventListener('click', function (e) { e.stopPropagation(); });
    var actions = document.createElement('div'); actions.className = 'sllmactions';
    var use = document.createElement('button');
    use.type = 'button'; use.textContent = 'Use translation';
    use.title = 'use the translation pasted below';
    actions.appendChild(use);
    var paste = document.createElement('textarea');
    paste.rows = 3; paste.placeholder = 'Paste the chatbot\u2019s translation here';
    paste.setAttribute('aria-label', 'Chatbot translation');
    glossAttrs(paste);
    var status = document.createElement('div');
    status.className = 'sllmstat'; status.setAttribute('aria-live', 'polite');
    var result = document.createElement('div'); result.className = 'sllmout';
    controls.appendChild(askBox); controls.appendChild(paste); controls.appendChild(actions);
    controls.appendChild(status); controls.appendChild(result); box.appendChild(controls);

    var cached = LLM.sent[sentence];
    if (cached !== undefined) {
      paste.value = cached;
      status.textContent = 'Reusing the translation pasted for this caption.';
      srcTranslation(result, cached, '', evidence.words || [], text, sentence);
    }

    var allPairs = null, ver = '';
    function corpusPage(offset) {
      return pAsk('/youtube/api/lookup', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(withLine({ video: CFG.id, text: text, sentence: sentence,
                               corpus_only: true, corpus_offset: offset,
                               corpus_limit: 50 }, at.ch))
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j || !j.ok) throw new Error('the corpus request was refused');
        return j;
      });
    }
    // THE PROMPT, made when it is asked for: Parseh's words, or -- where the menu in the row chose one of the
    // person's own -- theirs, read from the computer each time (ParsehLLM.own), so a prompt written again a
    // moment ago is the one used
    function build() {
      return ParsehLLM.own(row.promptId()).then(function (mine) {
        return ParsehLLM.prompt({
          sourceName: L.name, targetName: G.name, sourceCode: L.code, targetCode: G.code,
          sourceNative: L.native, trLabel: L.translit_label,
          version: ver, sentence: sentence, before: around.before, after: around.after,
          words: evidence.words || [], pairs: allPairs,
          instructions: mine && mine.text, instructionsKind: mine && mine.kind, custom: mine && mine.name
        });
      });
    }
    var row = ParsehLLMRow.mount(askBox, {
      surface: 'ask', label: 'Ask LLM', title: 'copy a prompt for an external chatbot',
      lang: L.code, options: false,
      remind: 'paste it into a chatbot, then paste its translation below.',
      // a failed preparing has said why in the line below, and gives no prompt
      getText: function () {
        if (allPairs) return build();
        return preparePairs().then(function () { return allPairs ? build() : ''; });
      },
      onCopied: function () { status.textContent = ''; status.classList.remove('bad'); }
    });
    // Fetch the remaining local corpus rows while the sidebar is being read.
    // The prompt is then held by the row, and the clipboard write occurs
    // directly in the click handler, which browsers with strict transient
    // clipboard permission require -- and the size is said before the copy.
    function preparePairs() {
      row.disable('preparing the prompt\u2026'); status.classList.remove('bad');
      status.textContent = evidence.pairs_more
        ? 'Preparing Ask LLM with all Tatoeba examples\u2026' : 'Preparing Ask LLM\u2026';
      return Promise.all([ParsehLLM.collectPairs(evidence, corpusPage), ParsehLLM.version()])
        .then(function (got) {
          allPairs = got[0]; ver = got[1];
          if (gen !== srcGen || !box.isConnected) return;
          row.enable();
          status.textContent = LLM.sent[sentence] !== undefined
            ? 'Reusing the translation pasted for this caption.' : '';
          return build().then(function (text) {
            if (gen === srcGen && box.isConnected) row.update(text);
          }, function (err) {
            // the person's own prompt could not be made: its words, not the corpus, are what failed
            if (gen !== srcGen || !box.isConnected) return;
            status.textContent = err.message; status.classList.add('bad');
          });
        }).catch(function () {
          if (gen !== srcGen || !box.isConnected) return;
          allPairs = null; row.enable();
          status.textContent = 'Could not collect all Tatoeba examples. Press Ask LLM to retry.';
          status.classList.add('bad');
        });
    }
    preparePairs();
    function accept() {
      var out = paste.value.trim();
      if (!out) {
        status.textContent = 'Paste the chatbot\u2019s translation first.';
        status.classList.add('bad'); paste.focus(); return;
      }
      mtKeep(LLM.sent, sentence, out);
      status.textContent = 'Translation ready for this whole caption.';
      status.classList.remove('bad');
      srcTranslation(result, out, '', evidence.words || [], text, sentence);
      fitFields();
    }
    use.onclick = function (e) { e.preventDefault(); e.stopPropagation(); accept(); };
    paste.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault(); accept();
      }
    });
  }

  /* WHICH FILLING IS CURRENT.  The dictionary's answer and the model's come
     back when they come back, and they wrote into the body they were asked
     for -- which is the SAME element after the sources are closed and opened
     again, or refilled for a phrase edited since.  So a late answer appended
     a second "sentences somebody translated", with the old phrase's
     sentences in it, under the new ones: duplicate headings. Every filling
     takes a number; an answer whose number is no
     longer the current one is dropped. */
  var srcGen = 0;

  function srcFill(at) {
    var body = cloud.querySelector('.esrcbody');
    if (!body) return;
    var gen = ++srcGen;
    body.textContent = '';
    var text = dictText(at.ch), sg = at.sg;
    if (!text) { body.innerHTML = '<div class="snone">no text yet</div>'; return; }

    /* THE SOURCE TOOLS, DRAWN AT ONCE AND IN THEIR ORDER -- dictionary,
       model, corpus, then the external-chatbot handoff -- each holding its
       book's sidebar draws them (sideFill).  The corpus's heading used to be
       drawn only when the lookup came back, so a lookup that failed (the
       server stopped, a refusal that is not JSON) left two headings where
       the book always has three, and no word on whether there had been any
       sentences to show. */
    var dict = srcSection(body, 'dictionary', 'looking the words up\u2026');
    srcDefsSwitch(dict);
    var mt = srcSection(body, 'a machine\u2019s reading',
                        MT.ready ? 'reading the caption\u2026'
                                 : 'no translation model for this pair');
    var pairs = srcSection(body, 'sentences somebody translated', 'looking\u2026');
    var llm = srcSection(body, 'external chatbot', 'waiting for the sources\u2026');
    // ONE lookup, read twice: by the dictionary block, and by the model's,
    // which marks the phrase's share of the caption by what it says the
    // phrase's words mean
    var look = pAsk('/youtube/api/lookup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(withLine({ video: CFG.id, text: text,
                             sentence: (sg && sg.text) || '' }, at.ch))
    }).then(function (r) { return r.json(); });
    look.then(function (j) {
      if (gen !== srcGen) return;
      dict.textContent = '';
      var found = (j && j.words) || [];
      if (!found.length)
        dict.innerHTML = '<div class="snone">the dictionary has nothing for ' +
                         'these words</div>';
      found.forEach(function (w) {
        (w.hits || []).forEach(function (h) { srcHit(dict, h); });
      });
      if (opts.defsMt && DICT.defines && MT.ready) defsRead(dict, '.sdef', null, srcDefPut);
      srcPairs(pairs, j);
      srcLLM(llm, at, text, j || {}, gen);
    }).catch(function () {
      if (gen !== srcGen) return;
      // the corpus rides on the same request, so it failed with it
      dict.innerHTML = '<div class="snone">the dictionary could not be ' +
                       'reached</div>';
      pairs.innerHTML = '<div class="snone">the corpus could not be ' +
                        'reached</div>';
      llm.innerHTML = '<div class="snone">the prompt needs the dictionary ' +
                      'and corpus results</div>';
    });

    if (!MT.ready) return;
    var sentence = (sg && sg.text) || text;
    var want = [sentence];
    if (text !== sentence) want.push(text);
    Promise.all([ParsehMT.translate(L.code, G.code, want),
                 look.catch(function () { return null; })]).then(function (both) {
      var got = both[0], j = both[1];
      mtKeep(MT.sent, sentence, got[0] || '');
      if (want.length > 1) mtKeep(MT.probe, text, got[1] || '');
      if (gen !== srcGen) return;      // kept for the panel; not drawn here
      var whole = got[0] || '', probe = want.length > 1 ? (got[1] || '') : '';
      srcTranslation(mt, whole, probe, (j && j.words) || [], text, sentence);
    }).catch(function () {
      if (gen !== srcGen) return;
      mt.innerHTML = '<div class="snone">the model could not be run</div>';
    });
  }

  // the sentences somebody translated, which come back with the lookup,
  // into the block srcFill has already put under its heading
  function srcPairs(box, j) {
    box.textContent = '';
    var pairs = (j && j.pairs) || [];
    if (!pairs.length) {
      box.innerHTML = '<div class="snone">nothing in the corpus is about ' +
                      'this phrase</div>';
      return;
    }
    pairs.forEach(function (p) {
      var marked = Parseh.pairMarkup(p, j, L, G);
      var row = srcRow(box, marked.src, p.dst,
              [['its meaning \u2192', 'put the translation in the meaning',
                function () { srcPut('en', p.dst); }]]);
      if (row.querySelector('.ssub')) row.querySelector('.ssub').innerHTML = marked.dst;
    });
  }
  function closeEditor() {
    if (!editing) return;
    editing = false;
    srcGen++;              // a lookup still on its way has nobody to tell
    if (strip) { strip.destroy(); strip = null; }   // and a proposal neither
    cloud.classList.remove('editing', 'sideon');
    cloud.style.maxHeight = '';
    // the LLM panel still open holds the video too (the transcript must keep
    // still under its picking hand): the video it would play on is handed to
    // the panel, and plays when that closes -- rgShut does the same the
    // other way round
    if (editWasPlaying && player && ready) {
      if (rgOn) rgWasPlaying = true; else player.playVideo();
    }
    editWasPlaying = false;
    closeCloud();          // the gloss it now has is one hover away again
  }
  function saveEdit() {
    var at = coords();
    if (!at) return;
    var fields = {}, n = 0;
    Array.prototype.forEach.call(cloud.querySelectorAll('.ef'), function (el) {
      var was = at.ch[el.dataset.f];
      was = (was === undefined || was === null) ? '' : String(was);
      if (el.value.trim() !== was.trim()) { fields[el.dataset.f] = el.value; n++; }
    });
    // The word line when it was changed -- and with any changed text of a
    // chunk that has a line or is being given one, changed or not: the
    // server holds the two together and refuses a text its words no longer
    // give back.  A chunk that had none and was given none sends nothing.
    if (strip) {
      var line = strip.value(), had = String(at.ch.words || '');
      if (line.trim() !== had.trim() ||
          (fields.fa !== undefined && (had.trim() || line.trim()))) {
        fields.words = line; n++;
      }
    }
    // the mark goes with the edit it permits, and on its own when it is the
    // only thing that moved
    var freeBox = cloud.querySelector('.efree');
    if (freeBox && freeBox.checked !== !!at.ch.free) { fields.free = freeBox.checked; n++; }
    // only what the hand actually touched is sent, so a refusal names that
    // field and not every field the chunk happens to have
    if (!n) { stat('nothing changed'); return; }
    post(fields, function (ch) {
      // the server trims, and drops a field emptied altogether: show the
      // boxes what is now on disk rather than what was typed at them
      Array.prototype.forEach.call(cloud.querySelectorAll('.ef'), function (el) {
        el.value = ch[el.dataset.f] || '';
      });
      if (freeBox) freeBox.checked = !!ch.free;
      if (strip) mountStrip(at, ch.words || '');
      paintDel(at);
    });
  }
  /* ---------- deleting a gloss, and taking the delete back ----------------
     DELETE GLOSS empties the gloss's own boxes -- the reading where the
     language has one, the transliteration, the vocabulary, the meaning --
     through the very door a save goes through (/youtube/api/edit), and
     nothing else: the text, the colour, the word line, the note and the
     transcript mark stay, and the chunk is one nobody has glossed yet, which
     is legal in every video.  One click and no question, because the undo is
     right there: the old gloss is kept IN THE PAGE (never in storage) until
     the page is reloaded, and UNDO DELETE writes it back through the same
     door -- filling boxes is always allowed.  Reopening the form on the chunk
     later offers the undo again.

     The memory is keyed by the chunk's place AND its text: a cut or a join
     renumbers the phrases of a caption, and a gloss must never be written
     back onto whichever phrase has moved into the deleted one's place.  An
     emptied chunk is also what an LLM is asked to fill (the region panel
     below), so delete, copy the prompt, paste the answer is a way to have a
     gloss written afresh. */
  var DEL_TITLE = "empty this chunk's transliteration, vocabulary and meaning " +
                  '(and its reading) — the text, the colour and the word line ' +
                  'stay; undo delete puts the gloss back';
  // the gloss's own boxes, the ones the form shows and whose being written
  // makes a chunk glossed: the reading only where the language has one (a
  // stray kana key elsewhere is nobody's gloss -- check_annotations.unwritten
  // ignores it there too, so the page and the checker agree which chunk has
  // a gloss).  What delete SENDS is a little more (delSlots, below).
  var GLOSS_SLOTS = (L.reading ? ['kana'] : []).concat(['tr', 'voc', 'en']);
  // THE BOXES DELETE EMPTIES, AND UNDO WRITES BACK: the gloss's own, and a
  // stray kana too, whatever L.reading says.  A language with no reading
  // shows no kana box, but an answer pasted when the video was added can
  // leave a "kana" key on a phrase all the same (the chat prompt's example
  // carries one for every language).  Left out of the delete, it stood as
  // the one written box of the phrase: the server's blank test counted it
  // then, so "delete gloss" was refused with a sentence telling the person
  // to press "delete gloss" -- and nothing in the form could clear it.  Sent
  // empty with the rest, the phrase is left blank whichever way the checker
  // counts it, and undo puts it back exactly as it was.
  function delSlots(ch) {
    return !L.reading && ch && ch.kana != null ? GLOSS_SLOTS.concat(['kana'])
                                               : GLOSS_SLOTS;
  }
  var UNDO = new Map();          // "<segment>:<chunk>\n<fa>" -> {kana?, tr, voc, en}
  function delKey(at) { return at.si + ':' + at.ci + '\n' + (at.ch.fa || ''); }
  // A reading that still says exactly what the chunk's word line proposes
  // (lib/wordline.js seed, lib/wordline.py's own rule) is nobody's writing:
  // it is what a draft starts a Japanese or Chinese chunk with, and the
  // checker calls such a chunk unglossed (check_annotations.unwritten), so
  // here it is no gloss either -- no "delete gloss" to offer on it, and
  // "nothing glossed yet" in its cloud.
  function hasGloss(ch) {
    var W = window.ParsehWordline;
    var sd = W && W.seed ? W.seed(ch, L) : [null, ''];
    return GLOSS_SLOTS.some(function (f) {
      var v = typeof ch[f] === 'string' ? ch[f].trim() : '';
      return !!v && !(f === sd[0] && sd[1] && v === sd[1]);
    });
  }
  // the two buttons as the chunk AS SAVED stands: no delete for a plain
  // chunk, a greyed one where there is nothing to take off, and the undo
  // wherever the page still holds a deleted gloss for this chunk
  function paintDel(at) {
    var del = cloud.querySelector('.edel'), undo = cloud.querySelector('.eundo');
    if (!del || !undo || !at) return;
    del.hidden = !!at.ch.plain;
    del.disabled = !hasGloss(at.ch);
    undo.hidden = !!at.ch.plain || !UNDO.has(delKey(at));
  }
  // after a delete or an undo, the boxes that hold the gloss show what is
  // now on disk; the text box and the transcript mark keep whatever is being
  // typed there, which neither button touched
  function repaintGloss(at, ch) {
    GLOSS_SLOTS.forEach(function (f) {
      var el = cloud.querySelector('.ef[data-f="' + f + '"]');
      if (el) el.value = ch[f] || '';
    });
    // what the vocabulary reads as follows the box
    var vn = cloud.querySelector('.evnow'), vx = cloud.querySelector('.ef[data-f="voc"]');
    if (vn && vx) vocNow(vx, vn);
    // the word line is checked against the reading box, which has just changed
    if (strip) mountStrip(at, strip.value());
    paintDel(at);
    fitFields();
  }
  function deleteGloss() {
    var at = coords();
    if (!at || at.ch.plain || !hasGloss(at.ch)) return;
    var old = {}, fields = {}, key = delKey(at);
    delSlots(at.ch).forEach(function (f) {
      old[f] = typeof at.ch[f] === 'string' ? at.ch[f] : '';
      fields[f] = '';
    });
    post(fields, function (ch) { repaintGloss(at, ch); }, 'gloss deleted',
         // remembered on every success, even one that lands after the form
         // has been closed: the gloss is gone from the file either way
         function () { UNDO.set(key, old); });
  }
  function undoDelete() {
    var at = coords();
    if (!at) return;
    var key = delKey(at), old = UNDO.get(key);
    if (!old) { paintDel(at); return; }
    // every box the delete emptied -- a stray kana among them -- and no other
    var fields = {};
    Object.keys(old).forEach(function (f) { fields[f] = old[f] || ''; });
    post(fields, function (ch) { repaintGloss(at, ch); }, 'gloss written back ✓',
         function () { UNDO.delete(key); });
  }
  document.addEventListener('keydown', function (e) {
    if (!editing || dvOn) return;      // the divide sheet is over the editor
    // a key pressed in the LLM panel is the panel's: Esc there closes it, and
    // Ctrl+Enter in its answer box is no save of this form
    if (e.target && e.target.closest && e.target.closest('#rgpanel')) return;
    if (e.key === 'Escape') { e.preventDefault(); closeEditor(); }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); saveEdit();
    }
  });
  /* THE SIZE THE HOVER CLOUD WAS PLACED AT, and what an answer arriving
     later compares with.  The panel under an unglossed phrase opens saying
     "looking it up…" -- a round trip is not something the cloud waits for
     -- and it was placed at that size and never again: at 1280x800 the
     first hover on a phrase at y 660 sat at 485..650, 165px tall, and the
     dictionary's answer, then the model's, grew it DOWNWARD to 488px, over
     the phrase it was pointing at and down to y 973 of an 800px window, the
     buttons at its foot out of reach.  Hovered again, the answer cached, the
     same phrase got a cloud placed at its full size, 162..650, above it --
     so that fault was only ever the placing having come too early (the
     cloud that fits neither side is the other fault, below).  Whatever
     fills the cloud after it is placed asks for it to be placed again
     (settleCloud), and gets it only if the cloud really changed size: an
     answer that changes nothing visible moves nothing, and the model's
     reading landing in a panel already at its full height does not shake
     the cloud under the pointer.  Placed again, a cloud above the phrase
     keeps its foot where it was and grows upward -- the row of buttons
     stays under the pointer that was travelling to it. */
  var placedW = -1, placedH = -1;
  function settleCloud() {
    if (editing || cloud.hidden || !cloudFor || !cloudFor.isConnected) return;
    if (cloud.offsetWidth === placedW && cloud.offsetHeight === placedH) return;
    placeCloud(cloudFor);
  }
  // The least of the panel worth drawing when it has to be cut to the room
  // there is: about five of its lines, a word and two of its senses.
  var PANEL_MIN = 96;
  function placeCloud(target) {
    if (editing) { placeEditor(target); return; }
    var r = target.getBoundingClientRect();
    cloud.hidden = false;
    cloud.classList.remove('below');
    // measure from a neutral position: the previous placement's inline left
    // still constrains the shrink-to-fit width and squeezes the cloud
    cloud.style.left = '8px'; cloud.style.top = '-9999px';
    // and the panel at its own height, not at the cut the last placing made
    var panel = cloud.querySelector('.dict');
    if (panel) panel.style.maxHeight = '';
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = document.documentElement.clientHeight || window.innerHeight;
    var cw = cloud.offsetWidth, chh = cloud.offsetHeight;
    // open towards the TOP of the page: sit above the phrase, and when
    // the room up there is short, ride up over the pinned video and the
    // header rather than flipping below (below runs off the page's
    // bottom edge).  Flip below only when the phrase itself is hugging
    // the top of the viewport, so the cloud would otherwise bury it.
    var top = r.top - chh - 10;
    var below = r.top < chh + 18;
    if (below) top = r.bottom + 10;
    else if (top < 8) top = 8;
    // A CLOUD WITH THE PANEL IN IT CAN FIT NEITHER SIDE.  At 1280x800 the
    // panel (44vh of it, style.css) makes the cloud 488px, and the phrase
    // just under the pinned video, at y 430, has 412px above it: the rule
    // above sent it below, where 320px were left, and it ran 160px off the
    // window.  The panel scrolls and the cloud must not (style.css: its arrow
    // is set against it), so the panel is what gives way -- cut to the room
    // on whichever side has more of it, above when that is the larger, the
    // cloud kept whole inside the window and off the phrase.  A gloss with
    // no panel is small and always fits; this never touches it.
    if (panel && top + chh > vh - 8) {
      var up = r.top - 18, down = vh - r.bottom - 18;
      below = down > up;
      panel.style.maxHeight = Math.max(PANEL_MIN,
        panel.offsetHeight - (chh - (below ? down : up))) + 'px';
      chh = cloud.offsetHeight;
      top = below ? r.bottom + 10 : Math.max(8, r.top - chh - 10);
    }
    if (below) cloud.classList.add('below');
    var left = Math.min(Math.max(8, r.left + r.width / 2 - cw / 2),
                        vw - cw - 8);
    cloud.style.top = top + 'px';
    cloud.style.left = left + 'px';
    var ar = cloud.querySelector('.arrow');
    if (ar) ar.style.left = Math.min(Math.max(10, r.left + r.width / 2 - left - 5),
                                     cw - 20) + 'px';
    placedW = cloud.offsetWidth; placedH = cloud.offsetHeight;
  }
  /* THE EDITING CLOUD IS PLACED BY RULES OF ITS OWN; the hover cloud above
     keeps every one of its.  The hover rule -- sit above the phrase, go below
     only when the phrase hugs the top -- looks at the bottom edge only to
     cut its panel, and for a small gloss it need not look.  The editor is
     not small: with its sources it was often most of the window's height,
     so it nearly always flipped below and ran off the page, the save button
     reachable only by scrolling inside it.  Here:
       . it goes on whichever side of the phrase has more room, above when
         it fits there, and is kept wholly inside the window;
       . when neither side holds it but the larger one still holds a usable
         editor (EDIT_ROOM), it is cut to that side's height -- the two
         columns scroll -- rather than laid over the phrase being written;
       . with the sources open it grows TO THE LEFT: the right edge stays
         where the fields-only editor's would be, so pressing ⊕ opens the
         sources beside the fields and leaves the fields where they were.
     Stacked (a narrow window, where the sources go under the fields) there is
     no left to grow into, and it is simply centred on the phrase. */
  // style.css says the same two things: the width below which the sources
  // stack under the fields, and the fields-only editor's width
  var STACK = '(max-width: 720px)';
  function editW() { return Math.min(460, window.innerWidth * 0.94); }
  // The fields-only editor of a Persian phrase measures 402px tall at
  // 1280x800 (head, four fields, the save row, the colours), so a side of the
  // phrase with 400px holds the fields whole, and the sources, cut to that,
  // scroll beside them.  Below that the columns would scroll for their first
  // lines, and covering the phrase is the lesser loss: its text is in the
  // first field anyway.
  var EDIT_ROOM = 400;
  function placeEditor(target) {
    var r = target.getBoundingClientRect();
    cloud.hidden = false;
    cloud.classList.remove('below');
    cloud.style.maxHeight = '';
    cloud.style.left = '8px'; cloud.style.top = '-9999px';
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = document.documentElement.clientHeight || window.innerHeight;
    var stacked = !!(window.matchMedia && window.matchMedia(STACK).matches);
    // STACKED, THE FIELDS COME FIRST IN HEIGHT AS WELL AS IN ORDER.  The
    // sources' strip is 36vh (style.css), and in a 390x844 window that left
    // the fields 258px of the 300 they need -- the meaning box scrolled out
    // of its own column.  So the strip gives back whatever the fields would
    // have to scroll for, down to a strip still worth reading.  Measured
    // here, once, rather than left to flex-shrink: the fields' height is
    // known when the cloud is placed, and the strip must not change size
    // again when the dictionary's answer lands in it.
    var side = cloud.querySelector('.eside'), main = cloud.querySelector('.emain');
    if (side) side.style.flexBasis = '';
    if (stacked && side && main && !side.hidden) {
      var over = main.scrollHeight - main.clientHeight;
      if (over > 0)
        side.style.flexBasis = Math.max(Math.min(140, vh * 0.2),
                                        side.offsetHeight - over) + 'px';
    }
    var cw = cloud.offsetWidth, chh = cloud.offsetHeight;
    var up = r.top - 18, down = vh - r.bottom - 18;
    var below = chh > up && down > up;
    var room = below ? down : up;
    if (chh > room && room >= EDIT_ROOM && !stacked) {
      cloud.style.maxHeight = room + 'px';
      chh = cloud.offsetHeight;
    }
    var top = below ? r.bottom + 10 : r.top - chh - 10;
    top = Math.max(8, Math.min(top, vh - chh - 8));
    var mid = r.left + r.width / 2, left;
    if (cloud.classList.contains('sideon') && !stacked) {
      var fw = editW();
      var right = Math.min(Math.max(mid + fw / 2, fw + 8), vw - 8);
      left = Math.max(8, right - cw);
    } else {
      left = Math.max(8, Math.min(mid - cw / 2, vw - cw - 8));
    }
    if (below) cloud.classList.add('below');
    cloud.style.top = top + 'px';
    cloud.style.left = left + 'px';
  }
  // a window resized with the editor open: across the stacking width the
  // columns change places, and at any width the fields wrap differently
  window.addEventListener('resize', function () {
    if (editing && cloudFor) { fitFields(); placeCloud(cloudFor); }
  });
  function openCloud(span, ch, sg) {
    if (editing) return;      // a form is open in there, half typed into
    clearTimeout(hideTimer);
    if (cloudFor && cloudFor !== span) cloudFor.classList.remove('hot');
    cloudFor = span; span.classList.add('hot');
    cloudCtx = { ch: ch, sg: sg };
    fillCloud(ch); placeCloud(span);
    if (opts.hoverpause && player && ready) {
      clearTimeout(resumeTimer);
      var st = player.getPlayerState && player.getPlayerState();
      if (st === 1) { wasPlaying = true; player.pauseVideo(); }
    }
    // A PHRASE NOBODY HAS GLOSSED, TAPPED ON A PHONE: its entry, already
    // being fetched into the cloud, goes into the dictionary's sheet, the
    // cloud never shown.  Not for a mouse at rest on it: a sheet that covers
    // the page must never spring up at a hover.
    if (autoBox && mobileNow() && !hoverPointer()) openSheet(autoBox);
  }
  /* The hover cloud drawn again for what the reader has just switched on,
     or what has just arrived (a model), and placed again at its new size.
     NEVER THE EDITOR: it is a form half typed into, and pressing the
     reading-help switch with it open redrew it as a gloss -- the typing
     gone, and the page still latched in `editing`, so no phrase would open
     a cloud until Esc. */
  function refillCloud() {
    // and never under the dictionary's sheet: placing the cloud shows it, and
    // a translation model found after the sheet opened drew the cloud again
    // behind the dimmed page, with a second lookup in it -- the sheet is
    // what the reader is looking at, and closing it closes the cloud anyway
    if (!cloudFor || !cloudCtx || editing || dsheet) return;
    fillCloud(cloudCtx.ch); placeCloud(cloudFor);
  }
  function closeCloud() {
    // while a phrase is being written only ✕ and Esc close the cloud: a
    // pointer wandering off the form, or a click on the video, must not
    // throw the typing away -- and while the dictionary's sheet is up, only
    // the sheet closes it (openSheet)
    if (editing || dsheet) return;
    if (cloudFor) cloudFor.classList.remove('hot');
    cloudFor = null; cloud.hidden = true;
    var held = sheetPaused;
    sheetPaused = false;
    if ((opts.hoverpause || held) && wasPlaying && player && ready) {
      // a small grace: darting to the neighbouring phrase must not stutter
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(function () {
        // never resume underneath the card dashboard
        if (!cloudFor && wasPlaying && !ankiOpen) {
          wasPlaying = false; player.playVideo();
        }
      }, 350);
    }
  }
  function scheduleClose() {
    if (editing || dsheet) return;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(closeCloud, 120);
  }
  cloud.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
  cloud.addEventListener('mouseleave', scheduleClose);
  cloud.addEventListener('click', function (e) {
    if (!cloudCtx || !e.target.classList) return;
    // the button, not whatever inside it was hit: the save button carries
    // its shortcut in a span of its own
    var t = e.target.closest ? (e.target.closest('button') || e.target) : e.target;
    if (t.classList.contains('mkcopy')) {
      if (window.Parseh) Parseh.copy(cloudCtx.ch.fa);
      return;
    }
    // REVIEW LATER: the cloud stays as it is, its button saying the new state
    if (t.classList.contains('mklater')) { laterToggle(cloudCtx.sg, cloudCtx.ch); return; }
    if (t.classList.contains('mkdict')) { dictOnDemand(t); return; }
    if (t.classList.contains('mkcard')) {
      var c = cloudCtx;                 // closeCloud() clears cloudCtx
      // the whole phrase: its caption and its chunk, no word of it
      openAnki(c.ch.fa, c.ch, c.sg, undefined,
               { i: segs.indexOf(c.sg), j: (c.sg.chunks || []).indexOf(c.ch), k: null, line: '' });
      return;
    }
    if (t.classList.contains('sw')) { setColour(t.dataset.col || ''); return; }
    if (t.classList.contains('mkedit')) { openEditor(); return; }
    if (t.classList.contains('ecancel')) { closeEditor(); return; }
    if (t.classList.contains('edv')) { dvStart(t.dataset.dv); return; }
    if (t.classList.contains('edel')) { if (!t.disabled) deleteGloss(); return; }
    if (t.classList.contains('eundo')) { undoDelete(); return; }
    if (t.classList.contains('esave')) { saveEdit(); }
  });
  document.addEventListener('click', function (e) {
    if (!cloud.hidden && !cloud.contains(e.target) &&
        !(e.target.classList && e.target.classList.contains('w'))) closeCloud();
  });

  /* ---------------- notes: what the transcript has no room for ----------
     The same thing the book reader has, in the same shape and against the
     same server: a markdown file in the seam between two captions, kept in
     the video's own folder under markdown/, written with the studio's
     editor and read in a frame over the page.  Never inline -- the
     transcript is the point -- and never in a prompt: a note is somebody's
     own reading, and a model has nothing to put in one.

     A note is anchored to a caption's START, which is what transcript.txt
     is keyed by and what survives a re-merge and a re-chunk.  One that
     names a start no longer in the video is shown at the end, marked
     adrift, rather than dropped. */
  var NOTES = CFG.notes || '';
  var NT = { back: $('#ntback'), box: $('#ntbox'), title: $('#nttitle'),
             frame: $('#ntframe'), edit: $('#ntedit'), read: $('#ntread'),
             close: $('#ntclose') };
  var ntOn = false, ntId = '', noteList = [];

  /* ---------- the bare note page, and the notes read ahead --------------
     What a mark opens is the studio's BARE note page (its templates/
     note.html): the rendered note on the studio's own sheet, with no editor
     and none of its scripts.  The document page it used to open is about
     1.3 MB fetched afresh every time, for something read a dozen times in a
     session and written on almost never; "open in the studio", in the bare
     page's own header, is one click from the whole of it.

     And a note whose mark comes near the window is read BEFORE it is asked
     for, so that the click costs nothing -- the same bargain the reader
     makes.  It is held as text and put into the frame with srcdoc, not left
     to the browser's cache, because the studio answers `no-cache` for
     everything it renders (a page somebody may be editing must never come
     back stale) and a revalidation over a tunnel is the very wait this is
     here to remove.  Capped, because a long video has a great many notes
     and a viewer walking it would otherwise carry all of them; never while
     a note is open, because the note being read is what the connection is
     for; and never for one that holds an exercise, which the server answers
     with a redirect to the studio's full page (an exercise with no script
     is a box that cannot be answered), remembered here so the next click
     goes straight there.

     AWAY FROM THE COMPUTER THERE IS NO REDIRECT TO SEE.  A kept video keeps
     its notes, and for a note that holds an exercise what was kept IS the
     studio's full page, so it can be answered on a train exactly as it is at
     the desk (TO-DO §0, "the notes, kept with their book or video").  The
     worker hands that page back at the bare address without a hop, and
     `redirected` is false: a test that believed it would put a document
     page, scripts and all, into the frame through srcdoc.  So the page is
     asked what it is as well.  The studio writes that on its own <body> --
     `data-page="doc"` on the document page, `data-page="note"` on the bare
     one -- which is honest whoever gave the answer, and which a note's own
     text cannot forge: everything it contributes went through the
     renderer's escaping. */
  var NOTE_HOLD = 12;
  // the studio's document page saying so itself (its templates/doc.html)
  var NOTE_FULL_MARK = '<body data-page="doc"';
  var noteHeld = {};        // id -> the bare page's html
  var noteOrder = [];       // those ids, the one held longest first
  var noteFull = {};        // ids the server sends to the studio instead
  var noteWaiting = [];     // came near while a note was open
  var noteBusy = {};

  function holdNote(id) {
    if (!id || noteHeld[id] || noteFull[id] || noteBusy[id]) return;
    if (ntOn) {
      if (noteWaiting.indexOf(id) < 0) noteWaiting.push(id);
      return;
    }
    noteBusy[id] = true;
    fetch(NOTES + '/note/' + encodeURIComponent(id)).then(function (r) {
      if (!r.ok) return null;
      if (r.redirected) { noteFull[id] = true; return null; }
      return r.text();
    }).then(function (html) {
      if (html == null) return;
      // the kept page saying what it is, where there was no redirect to see:
      // this note is answered by the studio's whole document page, so the
      // frame is sent to that address rather than fed these bytes
      if (html.indexOf(NOTE_FULL_MARK) >= 0) { noteFull[id] = true; return; }
      noteHeld[id] = html; noteOrder.push(id);
      while (noteOrder.length > NOTE_HOLD) delete noteHeld[noteOrder.shift()];
    }).catch(function () {
      // a server that does not know the bare address, or none at all: the
      // mark still opens the note, it simply opens it when it is clicked
    }).then(function () { delete noteBusy[id]; });
  }
  function forgetNote(id) {
    if (!id) return;
    delete noteHeld[id]; delete noteFull[id];
    var i = noteOrder.indexOf(id);
    if (i >= 0) noteOrder.splice(i, 1);
  }
  var nearNote = window.IntersectionObserver
    ? new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (!e.isIntersecting) return;
          nearNote.unobserve(e.target);
          holdNote(e.target.dataset.note);
        });
      }, { rootMargin: '600px 0px' })
    : null;

  function ntFrame(url, html) {
    // a fresh element, not a new src: an iframe's navigations land on the
    // joint session history, so three notes read would be three presses of
    // Back before the page moved
    var old = NT.frame;
    var f = document.createElement('iframe');
    f.id = 'ntframe'; f.title = old.title;
    // srcdoc for one already in hand: the same bytes the address would have
    // answered, drawn without going back for them.  Every address the note
    // page writes is absolute (the studio's own prefix), so nothing in it
    // depends on where the frame thinks it is.
    if (html != null) f.srcdoc = html; else f.src = url;
    old.parentNode.replaceChild(f, old);
    NT.frame = f;
  }
  // '' the bare page, 'edit' the studio's editor, 'full' its document page
  function noteUrl(id, how) {
    var at = NOTES + '/' + (how ? 'doc' : 'note') + '/' + encodeURIComponent(id);
    return how === 'edit' ? at + '/edit' : at;
  }
  function ntShow(id, title, how) {
    peekHide();             // the note itself is coming; its preview goes
    // one already known to need the studio's page goes straight there,
    // rather than to a bare address that would only redirect
    if (!how && noteFull[id]) how = 'full';
    ntId = id; ntOn = true;
    NT.title.textContent = title || 'note';
    var held = how ? null : noteHeld[id];
    if (held) ntFrame(null, held); else ntFrame(noteUrl(id, how));
    NT.edit.hidden = how === 'edit'; NT.read.hidden = how !== 'edit';
    NTOLD.hidden = !notesAway;  // what is in the frame is as of when it was kept
    NT.back.hidden = false; NT.box.hidden = false;
    if (player && ready && player.pauseVideo) player.pauseVideo();
  }
  function ntShut() {
    if (!ntOn) return;
    ntOn = false; NT.box.hidden = true; NT.back.hidden = true;
    ntFrame('about:blank');
    // the one that was open is the one that may have just been written --
    // the editor is reached through this very frame -- so the copy in hand
    // is dropped rather than shown again
    forgetNote(ntId);
    var waited = noteWaiting.slice();
    noteWaiting.length = 0;
    waited.forEach(holdNote);     // what came near while it was open
    loadNotes();            // the title may have changed, or the note be gone
  }
  // A key pressed inside the frame belongs to the frame's document; the note
  // posts up when it is framed, so "close (Esc)" is true in there too.
  //
  // `open-note-full` is the bare page's own header asking for the whole of
  // the studio.  It is done from out here, and not by the link navigating
  // itself, because a navigation inside the frame lands on the joint session
  // history: a note opened in full would cost a press of Back before the
  // video moved.
  window.addEventListener('message', function (e) {
    if (e.origin !== location.origin) return;
    var d = e.data;
    if (!d || !d.parseh) return;
    if (d.parseh === 'close-note') ntShut();
    else if (d.parseh === 'open-note-full' && ntOn)
      ntShow(ntId, NT.title.textContent, 'full');
  });
  NT.close.onclick = ntShut;
  NT.back.addEventListener('click', ntShut);
  NT.edit.onclick = function () { ntShow(ntId, NT.title.textContent, 'edit'); };
  NT.read.onclick = function () { ntShow(ntId, NT.title.textContent, ''); };
  document.addEventListener('keydown', function (e) {
    if (ntOn && e.key === 'Escape') {
      // stopImmediatePropagation, not stopPropagation: the divide sheet's own
      // Escape is registered on this very node in this very phase, and only
      // the immediate form stops a listener that is already a sibling
      e.preventDefault(); e.stopImmediatePropagation(); ntShut();
    }
  }, true);

  /* ---------- a note, before it is opened ---------------------------------
     A mark is a title in a pill, cut at 52 characters, and the only way to
     know what a note says was to open it: a frame over the whole page, the
     video paused, Esc to come back.  So a pointer resting on a mark shows a
     small card of what is in it -- the title whole, the opening of the text,
     and what a click will do -- and leaves the moment the pointer does.
     The text is notes.index()'s `excerpt`, which rides on the /api/marks
     answer loadNotes already fetches (front matter, anchor and markup taken
     out, about 280 characters), so a preview costs no request; a server
     from before that field gives the title and the invitation alone.

     TEXT, NEVER MARKUP.  A note can be somebody else's -- they travel inside
     video bundles -- and a preview is involuntary: it happens to whoever's
     pointer crosses the seam.  Clicking a note has always meant choosing to
     run it in the frame; resting on one must not.  So every word of it goes
     in by textContent and nothing here is ever innerHTML.

     Only where there is a hover (HOVER_OK): a touch screen's tap already
     opens the note, and a preview flashed on the way would be noise.  It is
     never in the way: pointer-events none, below the sheets and the note's
     own frame, and gone on leave, blur, Escape, a click, and any scroll --
     the follow mode scrolls the transcript on every caption, and a fixed
     card left behind would point at a different seam. */
  var PEEK_WAIT = 350;
  var peekEl = null, peekTimer = null, peekOn = null;
  function peekHide() {
    clearTimeout(peekTimer); peekTimer = null;
    if (peekOn) peekOn.removeAttribute('aria-describedby');
    peekOn = null;
    if (peekEl) peekEl.hidden = true;
  }
  function peekLine(cls, text) {
    var d = document.createElement('div');
    d.className = cls; d.textContent = text;
    peekEl.appendChild(d);
    return d;
  }
  function peekShow(b, n, adrift) {
    if (!b.isConnected || ntOn || dvOn || ankiOpen) return;
    if (!peekEl) {
      peekEl = document.createElement('div');
      peekEl.id = 'ntpeek';
      peekEl.setAttribute('role', 'tooltip');
      peekEl.hidden = true;
      document.body.appendChild(peekEl);
    }
    peekEl.textContent = '';
    peekLine('pkt', n.title || 'note');
    if (n.excerpt) peekLine('pkx', String(n.excerpt));
    peekLine('pkf', adrift
      ? 'this note names a caption that is no longer in the video — open it ' +
        'and change its anchor line'
      : (notesAway ? NT_KEPT : 'click to open'));
    // placed the way the cloud is: above the mark, below it only when the
    // mark is too near the top to leave room, and always inside the window
    peekEl.style.left = '8px'; peekEl.style.top = '-9999px';
    peekEl.hidden = false;
    var r = b.getBoundingClientRect();
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = document.documentElement.clientHeight || window.innerHeight;
    var pw = peekEl.offsetWidth, ph = peekEl.offsetHeight;
    var top = r.top - ph - 8;
    if (top < 8) top = r.bottom + 8;
    top = Math.max(8, Math.min(top, vh - ph - 8));
    // its start edge on the mark's: a mark is a pill at the seam's start,
    // and a card centred on a short one would hang off to the left of it
    var left = Math.max(8, Math.min(r.left, vw - pw - 8));
    peekEl.style.top = top + 'px'; peekEl.style.left = left + 'px';
    b.setAttribute('aria-describedby', 'ntpeek');
    peekOn = b;
  }
  if (HOVER_OK) {
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') peekHide();
    });
    // capture: a scroll does not bubble, and the transcript's is the window's
    window.addEventListener('scroll', peekHide, { capture: true, passive: true });
    window.addEventListener('resize', peekHide);
  }

  function noteMark(n, adrift) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'mark' + (adrift ? ' adrift' : '');
    b.textContent = n.title || 'note';
    if (HOVER_OK) {
      // the card says it -- and more -- so the browser's own tooltip, which
      // would land on top of the card a second later, is not asked for
      var arm = function () {
        clearTimeout(peekTimer);
        peekTimer = setTimeout(function () {
          peekTimer = null; peekShow(b, n, adrift);
        }, PEEK_WAIT);
      };
      b.addEventListener('mouseenter', arm);
      b.addEventListener('focus', arm);
      b.addEventListener('mouseleave', peekHide);
      b.addEventListener('blur', peekHide);
    } else {
      // without a hover the title is all there is, and lib/explain.js puts
      // it under "?" on a touch screen: what the mark DOES comes first and
      // the kept copy is said after it, rather than in place of it
      b.title = (adrift
        ? 'this note names a caption that is no longer in the video — open it ' +
          'and change its anchor line'
        : 'read this note') + (notesAway ? ' — ' + NT_KEPT : '');
    }
    b.onclick = function (e) {
      e.stopPropagation(); peekHide(); ntShow(n.id, n.title, '');
    };
    // read ahead when it comes near the window, so the click costs nothing
    b.dataset.note = n.id;
    if (nearNote) nearNote.observe(b);
    return b;
  }
  function newNote(gap) {
    if (!NOTES) return;
    fetch(NOTES + '/api/marks', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(gap.dataset.at
        ? { side: 'before', kind: 'cap', at: gap.dataset.at, target: L.code }
        : { side: 'after', kind: 'cap', at: gap.dataset.after, target: L.code })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok || !j.note) return;
      return loadNotes().then(function () {
        ntShow(j.note.id, j.note.title, 'edit');   // straight into the editor
      });
    }).catch(function () {});
  }
  function paintNotes() {
    peekHide();             // every mark is about to be drawn again
    // and thrown away with it: an observer still watching the old marks
    // would keep them, and the notes behind them, alive for the session
    if (nearNote) nearNote.disconnect();
    var gaps = document.querySelectorAll('#segs .gap');
    Array.prototype.forEach.call(gaps, function (g) {
      g.textContent = '';
      var plus = document.createElement('button');
      plus.type = 'button'; plus.className = 'plus'; plus.textContent = '+';
      plus.title = 'write a note here';
      plus.onclick = function (e) { e.stopPropagation(); newNote(g); };
      g.appendChild(plus);
    });
    var last = document.querySelector('#segs .gap.last');
    noteList.forEach(function (n) {
      var a = n.anchor, g = null;
      if (a && a.kind === 'cap') {
        // compared, not put into a selector: the anchor is a line somebody
        // typed into a file, and a quote in it would throw out of
        // querySelector and take every mark on the page with it
        var want = a.side === 'after' ? 'after' : 'at', at = String(a.at);
        g = Array.prototype.filter.call(gaps, function (x) {
          return x.dataset[want] === at;
        })[0] || null;
      }
      if (g) g.appendChild(noteMark(n, false));
      else if (last) last.appendChild(noteMark(n, true));
    });
  }
  function loadNotes() {
    if (!NOTES) { noteList = []; paintNotes(); return Promise.resolve(); }
    return fetch(NOTES + '/api/marks').then(function (r) { return r.json(); })
      // ONLY AN ANSWER THE COMPUTER REALLY GAVE MAY REPLACE THE MARKS.  The
      // seams' list is a door (lib/sw.js, isDoor): the computer is asked
      // first and the copy kept with the video answers when it does not, so
      // a kept note stays reachable -- there would be no mark to click on
      // otherwise.  What tells the two apart is `ok`: the studio answers this
      // address with {ok:true, notes:[...]} and nothing else, whether that
      // answer comes down the wire now or out of the cache where the wire
      // last put it, so an `ok` answer is the computer's own and an empty
      // `notes` in it is the truth -- the seams empty.
      .then(function (j) { if (j && j.ok && j.notes) noteList = j.notes; })
      // A REFUSAL IS NOT AN ANSWER ABOUT THE MARKS, and neither is a request
      // that never arrived.  Away from the computer the worker writes
      // {ok:false, offline:true} with a 503 of its own for a video kept
      // without its notes, and in the moment before the kept copy lands: it
      // is well-formed JSON and it knows nothing.  Either way the marks
      // already in hand stay -- they were true when they were read, and a
      // video whose notes vanish as the train enters a tunnel is the failure
      // this is here to prevent.  With none in hand the seams stay empty.
      .catch(function () {})
      .then(function () { paintNotes(); });
  }

  /* ---------- the marks, and the computer being away --------------------
     What is kept was kept at a moment, and the marks are as of that moment:
     a note written at the desk this morning is not in a list read last
     night.  Said quietly, and only while the computer cannot be reached --
     lib/keep.js asks that question for the whole toolbox and puts the
     answer on <html>, so nothing here pings anything -- and said in the two
     places it is wanted: on the frame the note is read in, and in the card
     a mark shows before it is opened.  The book reader carries the same
     lines (lib/tex2html.py); the two are a mirror and are meant to stay one.

     The "as kept" line is made here rather than written into player.html
     for the same reason the peek card is: it belongs to the notes and to
     nothing else on the page. */
  var notesAway = document.documentElement.hasAttribute('data-parseh-away');
  var NT_KEPT = 'the computer cannot be reached — the notes and their marks '
              + 'are as they were when this video was kept on this phone';
  var NTOLD = document.createElement('span');
  NTOLD.id = 'ntold';
  NTOLD.hidden = true;
  NTOLD.textContent = 'as kept';
  NTOLD.title = NT_KEPT;
  NTOLD.style.cssText = 'color:var(--faint);letter-spacing:0;text-transform:none;'
                      + 'font-size:11.5px;font-style:italic;white-space:nowrap';
  if (NT.title && NT.title.parentNode)
    NT.title.parentNode.insertBefore(NTOLD, NT.title.nextSibling);
  // The attribute is put on by another script, twenty seconds after the page
  // opened at the earliest, and taken off again when the computer comes
  // back; watching it is how this page hears both without asking anybody.
  if (window.MutationObserver)
    new MutationObserver(function () {
      var away = document.documentElement.hasAttribute('data-parseh-away');
      if (away === notesAway) return;
      notesAway = away;
      NTOLD.hidden = !away;
      paintNotes();             // the marks' explanations have just changed
    }).observe(document.documentElement,
               { attributes: true, attributeFilter: ['data-parseh-away'] });

  /* ---------------- where a chunk ends ----------------
     A chunk is a sense group, and the groups an LLM cut on its first pass
     are the first thing somebody who knows the language wants to move.
     Two operations, in a sheet of its own above the cloud:

       JOIN this phrase to the one after it (or, from the second phrase on,
       the one before it to this one -- so a run left unglossed, which has
       no cloud of its own, is still reachable from either side).  The texts
       go end to end with the language's word separator, so the caption is
       reproduced character for character and the fidelity check cannot
       fail; the romanisation and the meaning are joined with a space and
       the vocabulary with its own middle dot, and the server names in a
       note whatever could not simply be run together.

       CUT it in two, at one of the places the text divides: a space for a
       language written with spaces, and any two characters for Japanese,
       which writes none.  What goes to which half is a judgement, and this
       is where it is made -- the vocabulary entries arrive on the side
       whose text holds their headword and cross over with an arrow, every
       box is typed over freely, and nothing is written until the button.

     The proposals come from the server (lib/chunkdiv.py), which is also
     what the book reader's sheet draws: one set of rules, shown twice.

     AFTERWARDS the caption's chunks have been renumbered, and the page is
     redrawn from the list the server sends back -- not patched, because
     every phrase after the change has moved and every closure in the
     caption would be one out.  A page left open is safe too: each divide
     sends the text it is looking at, and the server refuses when the file
     no longer says that. */
  var dvBack = $('#dvback'), dvBox = $('#dvbox'), dvOn = false;
  var dvMode = '', dvAt = null, dvData = null, dvEntries = null, dvSides = [];

  function dvSay(m, bad) {
    var el = $('#dvstat');
    el.textContent = m || ''; el.classList.toggle('bad', !!bad);
  }
  function dvShut() {
    if (!dvOn) return;
    dvOn = false; dvBox.hidden = true; dvBack.hidden = true;
  }
  function dvAsk(body) {
    body.video = CFG.id;
    return fetch('/youtube/api/divide', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }
  function dvNotes(list) {
    var box = $('#dvnotes');
    box.textContent = '';
    (list || []).forEach(function (t) {
      var p = document.createElement('p'); p.textContent = t; box.appendChild(p);
    });
  }
  // one column of boxes: the half's text above, unchangeable -- a split
  // divides and does not rewrite, and changing a letter is the editor's job
  function dvCol(head, ch) {
    var c = document.createElement('div');
    c.className = 'dvcol';
    c.dataset.fa = ch.fa || '';
    var h = document.createElement('h4'); h.textContent = head; c.appendChild(h);
    var fa = document.createElement('div');
    fa.className = 'dvfa'; fa.setAttribute('dir', L.dir); fa.lang = L.code;
    fa.textContent = ch.fa || ''; c.appendChild(fa);
    // the colour is the one field the sheet draws no box for and still sends:
    // it is a field a page may set (annwrite.EDITABLE), and a page that left
    // it out would be saying "no colour".  The note is a field a page may set
    // too and the sheet has no box for it, so a page that leaves it out is not
    // saying "no note": the server carries it across itself (a cut leaves it on
    // the first half, a join joins both).  The plain mark is not a page's to set
    // at all -- the server refuses a divide that names it -- and is carried
    // the same way, so it stays here.
    if (ch.col) c.dataset.xcol = String(ch.col);
    var add = function (key, label, rows, kind) {
      var l = document.createElement('label'); l.textContent = label;
      var t = document.createElement('textarea');
      t.rows = rows; t.value = ch[key] || ''; t.dataset.k = key;
      if (kind === 'voc') t.className = 'dvvoc';
      if (kind === 'tl') targetAttrs(t);
      if (kind === 'gl' || kind === 'voc') glossAttrs(t);
      c.appendChild(l); c.appendChild(t);
    };
    if (L.reading) add('kana', L.reading_label || 'reading', 1, 'tl');
    add('tr', L.translit_label || 'transliteration', 1);
    var chips = document.createElement('div');
    chips.className = 'dvchips'; c.appendChild(chips); c._chips = chips;
    add('voc', 'vocabulary', 3, 'voc');
    add('en', GLOSS_LABEL, 2, 'gl');
    return c;
  }
  function dvRead(col) {
    var out = { fa: col.dataset.fa };
    Array.prototype.forEach.call(col.querySelectorAll('textarea'), function (t) {
      out[t.dataset.k] = t.value.trim();
    });
    // only the boxes the sheet draws and the colour: the plain mark sent back
    // here would be refused, and the note is the server's to carry across
    if (col.dataset.xcol) out.col = col.dataset.xcol;
    return out;
  }
  function dvPaintChips() {
    var cols = $('#dvpair').querySelectorAll('.dvcol');
    if (cols.length !== 2 || !dvEntries) return;
    Array.prototype.forEach.call(cols, function (c) {
      if (c._chips) c._chips.textContent = '';
    });
    ['a', 'b'].forEach(function (side, k) {
      var box = cols[k].querySelector('textarea[data-k="voc"]');
      if (box) box.value = dvEntries.filter(function (_e, i) {
        return dvSides[i] === side;
      }).map(function (e) { return e.text; }).join(dvData.voc_sep);
    });
    dvEntries.forEach(function (e, i) {
      var host = cols[dvSides[i] === 'a' ? 0 : 1]._chips;
      if (!host) return;
      var row = document.createElement('div'); row.className = 'dvchip';
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = dvSides[i] === 'a' ? '→' : '←';
      b.title = 'send this entry to the other phrase';
      b.onclick = function () {
        dvSides[i] = dvSides[i] === 'a' ? 'b' : 'a'; dvPaintChips();
      };
      var t = document.createElement('span');
      t.className = 'dvtxt'; t.textContent = e.text;
      row.appendChild(b); row.appendChild(t); host.appendChild(row);
    });
  }
  function dvPick(i) {
    var c = dvData.cuts[i], pair = $('#dvpair');
    Array.prototype.forEach.call($('#dvwhere').querySelectorAll('.dvcut'),
      function (b, k) { b.classList.toggle('on', k === i); });
    dvEntries = c.entries || [];
    dvSides = dvEntries.map(function (e) { return e.side; });
    pair.textContent = '';
    pair.appendChild(dvCol('first phrase', c.first));
    pair.appendChild(dvCol('second phrase', c.second));
    dvPaintChips();
    dvNotes(c.notes);
    $('#dvdo').disabled = false;
  }
  function dvSplitUI() {
    var where = $('#dvwhere'), cuts = dvData.cuts || [];
    $('#dvdo').textContent = 'divide'; $('#dvdo').disabled = true;
    where.textContent = ''; $('#dvpair').textContent = ''; dvNotes([]);
    var hint = document.createElement('div'); hint.className = 'anote';
    if (!cuts.length) {
      hint.textContent = L.word_sep
        ? 'This phrase is one word, and a phrase of a language written with ' +
          'spaces divides at a space. Join it to a neighbour instead.'
        : 'This phrase is a single character, so there is nothing to divide.';
      where.appendChild(hint); return;
    }
    var box = document.createElement('div');
    box.className = 'dvtext'; box.setAttribute('dir', L.dir); box.lang = L.code;
    // the pieces, not a slice by offset: the offsets are Python's code points
    // and this counts UTF-16 units, so one character outside the basic plane
    // would slide every mark a place along
    (dvData.pieces || []).forEach(function (pc, i) {
      box.appendChild(document.createTextNode(pc.text));
      if (i >= cuts.length) return;
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'dvcut'; b.textContent = '✂';
      b.title = 'divide here';
      b.onclick = function () { dvPick(i); };
      box.appendChild(b);
    });
    where.appendChild(box);
    hint.textContent = L.word_sep
      ? 'Pick where it divides. Joined back with the space, the two halves ' +
        'have to be this caption again — which is why a word is never cut through.'
      : 'Pick where it divides. This language writes no spaces, so it divides ' +
        'between any two characters.';
    where.appendChild(hint);
    if (cuts.length === 1) dvPick(0);
  }
  function dvMergeUI() {
    var where = $('#dvwhere'), pair = $('#dvpair');
    $('#dvdo').textContent = 'join';
    where.textContent = ''; pair.textContent = '';
    dvEntries = null; dvSides = [];
    if (!dvData.merge) {
      var n = document.createElement('div'); n.className = 'anote';
      n.textContent = dvData.merge_error || 'these two cannot be joined';
      where.appendChild(n); $('#dvdo').disabled = true; dvNotes([]); return;
    }
    $('#dvdo').disabled = false;
    var two = document.createElement('div');
    two.className = 'dvtext'; two.setAttribute('dir', L.dir); two.lang = L.code;
    two.textContent = (dvData.chunk.fa || '') + '  ·  ' +
                      ((dvData.next || {}).fa || '');
    where.appendChild(two);
    pair.appendChild(dvCol('the one phrase they become', dvData.merge.fields));
    var notes = (dvData.merge.notes || []).slice();
    if (dvData.merge.words > 7)
      notes.push('That is ' + dvData.merge.words + ' words in one phrase; the ' +
                 'conventions ask for two to six, and the checker warns above seven.');
    dvNotes(notes);
  }
  function dvStart(which) {
    var at = coords();
    if (!at) return;
    var si = at.si, ci = which === 'prev' ? at.ci - 1 : at.ci;
    if (ci < 0) return;
    dvMode = which === 'split' ? 'split' : 'merge';
    dvAt = { si: si, ci: ci };
    dvData = null; dvEntries = null;
    $('#dvtitle').textContent = (dvMode === 'split'
      ? 'cut segment ' + si + ' chunk ' + ci + ' in two'
      : 'join segment ' + si + ' chunk ' + ci + ' to the next');
    $('#dvwhere').textContent = ''; $('#dvpair').textContent = ''; dvNotes([]);
    $('#dvdo').disabled = true; $('#dvcancel').hidden = false;
    $('#dvdo').onclick = dvCommit;
    dvSay('reading the annotations…');
    dvBox.hidden = false; dvBack.hidden = false; dvOn = true;
    dvAsk({ action: 'preview', segment: si, chunk: ci }).then(function (j) {
      if (!j.ok) { dvSay(j.error || 'could not read the chunk', true); return; }
      dvData = j; dvSay('');
      if (dvMode === 'split') dvSplitUI(); else dvMergeUI();
    }).catch(function (e) {
      dvSay('the server did not answer (' + ((e && e.message) || e) +
            ') — nothing was written', true);
    });
  }
  function dvDone(j) {
    // the caption's whole new chunk list, and the transcript drawn again
    // from it: every phrase after the change has a new number, and a patch
    // would leave the hover closures one out
    segs[dvAt.si].chunks = j.chunks;
    // a prompt the LLM panel holds for a copy by hand was made from the
    // phrases as they were before this cut or join (rgForget)
    rgForget();
    closeEditor();
    render();
    // render() has replaced every .seg, and the on-air highlight was a class
    // on the old ones.  `active` still names the caption, so forgetting it is
    // what makes the next tick put the highlight back rather than skip it.
    active = -1;
    $('#dvwhere').textContent = ''; $('#dvpair').textContent = '';
    $('#dvcancel').hidden = false;
    dvNotes([(dvMode === 'split'
      ? 'The phrase is two phrases now.'
      : 'The two phrases are one now.') +
      ' Segment ' + dvAt.si + ' has ' + j.count + ' of them, and the ' +
      'transcript has been drawn again from the file.',
      // parts/ is retired (youtube/lib/merge_parts.py): the batches a video
      // is added from are dropped once it is on the shelf, and merge_parts
      // refuses to rebuild over an annotations.json newer than the batches
      // an older video still has -- so no division comes back over this one
      'annotations.json is what was written, and it is the video’s one ' +
      'copy of its phrases: nothing rebuilds it from anything else, so the ' +
      'old division cannot come back.']);
    dvSay('done ✓');
    $('#dvdo').textContent = 'close';
    $('#dvdo').disabled = false;
    $('#dvdo').onclick = dvShut;
    $('#dvdo').focus();
  }
  function dvCommit() {
    if (!dvData || !dvAt) return;
    var cols = $('#dvpair').querySelectorAll('.dvcol'), body;
    if (dvMode === 'split') {
      if (cols.length !== 2) return;
      body = { action: 'split', segment: dvAt.si, chunk: dvAt.ci,
               expect: dvData.chunk.fa,
               first: dvRead(cols[0]), second: dvRead(cols[1]) };
    } else {
      if (!cols.length) return;
      body = { action: 'merge', segment: dvAt.si, chunk: dvAt.ci,
               expect: dvData.chunk.fa,
               expect_next: (dvData.next || {}).fa, fields: dvRead(cols[0]) };
    }
    $('#dvdo').disabled = true; dvSay('writing…');
    dvAsk(body).then(function (j) {
      if (!j.ok) {
        dvSay(j.error || 'refused', true); $('#dvdo').disabled = false; return;
      }
      dvDone(j);
    }).catch(function (e) {
      dvSay('the server did not answer (' + ((e && e.message) || e) +
            ') — nothing was written', true);
      $('#dvdo').disabled = false;
    });
  }
  $('#dvcancel').onclick = dvShut;
  dvBack.addEventListener('click', dvShut);
  dvBox.addEventListener('submit', function (e) { e.preventDefault(); });
  document.addEventListener('keydown', function (e) {
    if (dvOn && e.key === 'Escape' && !$('#dvcancel').hidden) {
      e.preventDefault(); e.stopPropagation(); dvShut();
    }
  }, true);

  /* ---------------- render the transcript ---------------- */
  function render() {
    var box = $('#segs');
    box.textContent = '';
    els = [];
    segs.forEach(function (sg, i) {
      // The seam a note sits in: one before every caption and, after the
      // loop, one after the last -- so every gap between two lines is a
      // place, named by the caption's start, which is what transcript.txt
      // is keyed by and what survives a re-merge and a re-chunk.  Empty
      // here; what is in it is drawn from the notes beside the video, which
      // are written without the page being rebuilt.
      var gap = document.createElement('div');
      gap.className = 'gap';
      // the seam knows the caption above it and the caption below it, so
      // `after 12` and `before 18` are two spellings of the one place
      gap.dataset.at = String(sg.start);
      gap.dataset.after = i ? String(segs[i - 1].start) : '';
      box.appendChild(gap);
      // a chapter heading belongs to the caption it was pasted above
      if (sg.chapter) {
        var h = document.createElement('div');
        h.className = 'chap'; h.setAttribute('dir', 'auto');
        h.textContent = sg.chapter;
        box.appendChild(h);
      }
      var d = segEl(sg, i);
      box.appendChild(d);
      els.push(d);
      if (i === segs.length - 1) {
        var end = document.createElement('div');
        end.className = 'gap last';
        end.dataset.at = ''; end.dataset.after = String(sg.start);
        box.appendChild(end);
      }
      if (i === segs.length - 1) paintNotes();   // the seams exist now
    });
    // a stretch being picked for an LLM stays lit across a redraw (a divide,
    // a timing moved): the lines are new, the pick is not
    rgPaint();
    measure();
    markGlossed();
    pnPaint();
    laterPaint();
  }
  /* ONE CAPTION'S LINE, whole: its time, its phrases, and every listener the
     line and its phrases carry.  A function of its own because two things
     draw it -- render(), for the whole transcript, and redrawSeg(), for the
     few captions an LLM's answer has just written to, which are swapped in
     where they stand so nothing else on the page moves. */
  function segEl(sg, i) {
    var d = document.createElement('div');
    d.className = 'seg' + (sg.plain ? ' plain' : '');
    d.dataset.i = i;
    var lab = document.createElement('button');
    lab.className = 'lab'; lab.textContent = fmt(sg.start);
    lab.title = 'play from ' + fmt(sg.start);
    lab.onclick = function (e) {
      e.stopPropagation();
      // picking a stretch for an LLM: the time is part of the line it heads
      if (rgPickAt(+d.dataset.i)) return;
      seek(sg.start);
    };
    d.appendChild(lab);
    var fa = document.createElement('div');
    if (sg.plain) {
      // the video's own framing, not the language it teaches and not the
      // language it is glossed in: shown as it stands, never glossed.
      // English in every video the toolbox holds, which is what the class
      // and these attributes are named after and say.
      fa.className = 'en-line';
      fa.setAttribute('dir', 'ltr'); fa.lang = 'en';
      fa.textContent = sg.text || '';
    } else {
      // the line reads in the language's direction and face: the dir
      // attribute sets the direction, data-lang on <html> the font token
      fa.className = 'fa'; fa.setAttribute('dir', L.dir); fa.lang = L.code;
      (sg.chunks || []).forEach(function (ch, j) {
        // chunks are joined with the caption's own separator: a space for
        // most languages, nothing for Japanese, which the annotator split
        // at nothing (the fidelity check joins them the same way)
        if (j && L.word_sep) fa.appendChild(document.createTextNode(L.word_sep));
        // WHAT IS DRAWN BARE -- text, not a target: no hover, no card, no
        // dots, no ✎ -- is two things and only two.  A chunk marked plain
        // (an import's, or an aside marked so, which for a Latin-script
        // target is the only way one is told).  And a run of the video's own
        // framing inside a caption of the target script: a chunk with nothing
        // written on it, of a language with a script of its own, holding none
        // of that script -- the English a teacher says between two Persian
        // sentences.  Where the language has a reading, the kana alone is
        // something written.
        // EVERY OTHER CHUNK IS A PHRASE, glossed or not.  A chunk of the
        // target's text nobody has glossed yet is precisely what somebody
        // opens the page to write, and a span with no hover is a chunk the
        // player could never be used to fill in -- nor delete a gloss from
        // and fill again, nor ask a dictionary about.  An unglossed chunk is
        // legal in every video (check_annotations), so nothing about the
        // video decides this: its cloud says "nothing glossed yet" and offers
        // the ✎, whatever is or is not installed.
        var written = !!(ch.tr || ch.en || ch.voc || ch.note || (L.reading && ch.kana));
        if (ch.plain || (!written && L.chars && !hasScript(ch.fa))) {
          var bare = document.createElement('span');
          // target text left unglossed (ch.plain, from an import) reads
          // as the text around it, in the language's face (.tl); a run
          // of another script keeps its own quieter dress.  For a
          // Latin-script language nothing can be told apart, so a bare
          // run is always the quiet aside it was marked as.
          bare.className = 'bare' + (hasScript(ch.fa) ? ' tl' : '');
          bare.setAttribute('dir', 'auto');
          bare.textContent = asDrawn(ch.fa);
          // a mark set by hand in the file still shows on a chunk the
          // player itself would not offer to colour
          paintCol(bare, ch);
          fa.appendChild(bare);
          return;
        }
        var w = document.createElement('span');
        w.className = 'w'; w.dataset.j = j;
        paintWords(w, ch);
        paintCol(w, ch);
        w.addEventListener('mouseenter', function () {
          if (!hoverPointer()) return;    // a tap's synthetic hover: not one
          openCloud(w, ch, sg);
        });
        w.addEventListener('mouseleave', scheduleClose);
        // wired always, and deciding per event rather than per device: a
        // screen that claims a hover it never delivers still glosses a tap
        w.addEventListener('click', function (e) {     // touch: tap = gloss
          if (hoverPointer()) return;                  // a mouse: replay
          // picking a stretch: the tap is the line's, and picks it below
          if (rgPicking()) return;
          e.stopPropagation();
          if (cloudFor === w) closeCloud(); else openCloud(w, ch, sg);
        });
        fa.appendChild(w);
      });
    }
    d.appendChild(fa);
    // clicking a sentence replays it from its own beginning -- including
    // a click on a phrase (the gloss is already open from the hover) --
    // unless a stretch is being picked for an LLM, when it picks the line
    d.addEventListener('click', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;   // that's a card
      if (e.shiftKey) return;                           // that's a copy
      if (String(window.getSelection ? window.getSelection() : '')) return;
      if (rgPickAt(+d.dataset.i)) return;
      seek(sg.start);
    });
    return d;
  }
  /* One caption drawn again where it stands, from segs[i] as it now is: the
     line the answer wrote to, and nothing around it -- the seams, the notes,
     the on-air highlight, the scroll and the video all stay where they were.
     A cloud open on one of its old phrases has nothing left to point at. */
  function redrawSeg(i) {
    var old = els[i];
    if (!old || !old.parentNode || !segs[i]) return;
    var d = segEl(segs[i], i);
    ['on-air', 'near'].forEach(function (c) {
      if (old.classList.contains(c)) d.classList.add(c);
    });
    if (cloudFor && old.contains(cloudFor) && !editing) closeCloud();
    old.parentNode.replaceChild(d, old);
    els[i] = d;
    markGlossed();
    pnPaint();
    laterPaint();
  }

  // shift-click copies: the phrase under the cursor (the hoverable unit),
  // or the whole caption when the click lands beside one.  A plain click
  // still replays, and the modifier-click below still makes a card.
  // Capture phase, so the sentence's replay-click never fires for it.
  $('#segs').addEventListener('click', function (e) {
    if (!e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
    var segEl = e.target.closest ? e.target.closest('.seg') : null;
    if (!segEl) return;
    e.preventDefault(); e.stopPropagation();
    var w = e.target.closest('.w');
    var sg = segs[+segEl.dataset.i];
    var line = segEl.querySelector('.fa, .en-line');
    // WHAT IS COPIED IS THE PHRASE AS IT WAS WRITTEN: with the diacritics put
    // away the page draws it without its marks, and the copy still has them
    // (the caption's own text, below, never lost them)
    var own = w && sg && sg.chunks ? sg.chunks[+w.dataset.j] : null;
    var text = w ? (marksOff() && own ? own.fa : Parseh.baseText(w))
             : (sg && sg.text) ? sg.text
             : (line ? line.textContent : '');
    if (window.Parseh) Parseh.copy(text);
  }, true);
  // ... and the shift-click must not start a text selection of its own
  $('#segs').addEventListener('mousedown', function (e) {
    if (e.shiftKey && !(e.altKey || e.ctrlKey || e.metaKey)) e.preventDefault();
  });

  // alt/ctrl-click on a word -> the card dashboard, with that very word.
  // Capture phase, so the sentence's replay-click never fires for it.
  $('#segs').addEventListener('click', function (e) {
    if (!(e.altKey || e.ctrlKey || e.metaKey)) return;
    var t = e.target.closest ? e.target.closest('.wd') : null;
    if (!t) return;
    e.preventDefault(); e.stopPropagation();
    var wEl = t.parentNode, segEl = wEl.parentNode.parentNode;
    var sg = segs[+segEl.dataset.i];
    var ch = sg && sg.chunks[+wEl.dataset.j];
    if (!ch) return;
    // where the card's text is, for the cut editor: this caption, this
    // chunk, and (below) the word of it
    var at = { i: +segEl.dataset.i, j: +wEl.dataset.j, k: null, line: '' };
    // A WORD THE CHUNK'S LINE DREW (its data-k, the word's place in the
    // line): the card is that word, with the reading the line gives it
    var line = t.dataset.k !== undefined ? lineOf(ch) : '';
    var said = line ? ParsehWordline.parse(line)[+t.dataset.k] : null;
    if (said) {
      at.k = +t.dataset.k; at.line = line;
      openAnki(said[0], ch, sg, said[1], at);
      return;
    }
    // a language without a word separator (Japanese) makes the chunk its
    // one word, so the card is the phrase exactly as the cloud's button
    // gives it: the chunk untouched, so its reading (the kana of the whole
    // chunk) and its caption still fit -- stripping a closing 。、 would
    // make the word differ from the chunk and lose both
    if (!L.word_sep) { openAnki(ch.fa, ch, sg, undefined, at); return; }
    // the word's place among the chunk's words, where they are drawn one
    // span each (not while the chunk shows its reading alone)
    var wds = Array.prototype.slice.call(wEl.querySelectorAll('.wd'));
    if (wds.length === wordsOf(ch.fa).length) at.k = wds.indexOf(t);
    // the quotation marks and stops a word may be glued to, of every script
    // the toolbox meets -- punctuation, not a language table.  The same
    // class the reader trims off a card's front (lib/tex2html.py): the
    // ASCII , ; ? belong to the Latin-script captions, which write them
    // where Persian and Arabic write ، ؛ ؟, so a word cut from "Merhaba,
    // İngilizce" or "Nasılsın?" comes away clean.  “ is in both halves
    // (it opens in English, closes in German), and the apostrophe in
    // neither: "po'" and "İstanbul'da" wear it as part of the word.
    // THE WORD AS WRITTEN, not as drawn: with the diacritics put away the span
    // holds the word without its marks, and the card carries the marks (the
    // chunk's words are drawn one span each, so its k-th is the k-th written)
    var drawn = Parseh.baseText(t);
    var written = marksOff() && at.k !== null && at.k >= 0 && wordsOf(ch.fa)[at.k] !== undefined
                  ? wordsOf(ch.fa)[at.k] : drawn;
    var word = written.replace(/^[«"(「『（„“‹]+|[»".,;:?!،؛؟)」』、。！？）”“›…]+$/g, '');
    openAnki(word || written, ch, sg, undefined, at);
  }, true);

  // while a modifier is down, the word under the cursor lights up
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey)
      document.body.classList.add('altdown');
  });
  document.addEventListener('keyup', function (e) {
    if (!e.altKey && !e.ctrlKey && !e.metaKey)
      document.body.classList.remove('altdown');
  });
  window.addEventListener('blur', function () {
    document.body.classList.remove('altdown');
  });

  /* ---------------- sync with the video ---------------- */
  function findSeg(t) {
    var lo = 0, hi = segs.length - 1, ans = -1;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (segs[mid].start <= t + 0.15) { ans = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    return ans;
  }
  function show(i) {
    if (i < 0 || i >= els.length) return;
    els[i].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  function tick() {
    if (!ready || !player || !player.getCurrentTime) return;
    var t = player.getCurrentTime();
    var dur = player.getDuration ? player.getDuration() : 0;
    $('#pos').textContent = fmt(t) + (dur ? ' / ' + fmt(dur) : '');
    var i = findSeg(t);
    if (i !== active) {
      [active - 1, active, active + 1].forEach(function (k) {
        if (k >= 0 && k < els.length)
          els[k].classList.remove('on-air', 'near');
      });
      active = i;
      document.body.classList.toggle('synced', active >= 0);
      if (active >= 0) {
        els[active].classList.add('on-air');
        // the neighbours stay readable: a sentence often carries over
        if (active > 0) els[active - 1].classList.add('near');
        if (active + 1 < els.length) els[active + 1].classList.add('near');
        if (opts.follow && Date.now() - lastUserScroll > 2500) show(active);
      }
    }
  }
  function seek(t) {
    if (player && ready && player.seekTo) { player.seekTo(t, true); player.playVideo(); }
  }
  ['wheel', 'touchmove'].forEach(function (ev) {
    window.addEventListener(ev, function () { lastUserScroll = Date.now(); },
                            { passive: true });
  });

  /* ---------------- the card dashboard ---------------- */
  // Alt-click a word (or "+ card" in a cloud) and this modal opens,
  // prefilled from the phrase.  Saving POSTs to /anki/cards, which stores
  // the card as JSON under anki/<deck>/ -- the ground truth the .apkg is
  // built from.  GUIDs are minted once at save, so a rebuilt deck can be
  // re-imported into Anki forever: old notes update in place and keep
  // their scheduling, new cards arrive as new.
  //
  // THE SAME SHEET MAKES TWO OTHER CARDS (the switch at its top): an
  // exercise in one of the toolbox's exercise decks, and the card as studio
  // markdown on the clipboard.  Both are one `:::exercise flashcard` block
  // written by the card kit (lib/cardkit.js, ParsehCards), which the book
  // reader shares; they take a fourth type, jolly, that Anki has no note
  // type for.  Whichever it goes to, a card can carry the word's own sound:
  // a clip cut out of the film into the clip tray (/clips), which Anki copies
  // into its deck and a deck or a pasted document brings in from there.
  var A = {
    back: $('#ankiback'), box: $('#anki'), time: $('#atime'),
    deck: $('#adeck'), deckNew: $('#adecknew'), deckRow: $('#adeckrow'),
    fa: $('#afa'), kana: $('#akana'), tr: $('#atr'), en: $('#aen'), ctx: $('#actx'),
    notes: $('#anotes'), tags: $('#atags'), src: $('#asrc'),
    opp: $('#aopp'), oppKana: $('#aoppkana'), oppTr: $('#aopptr'),
    stat: $('#astat'), saveLab: $('#asavelab'), note: $('#atnote'),
    prev: $('#ashotprev'), img: $('#ashotimg'), hint: $('#ashothint'),
    shot: $('#ashot'), shotWhy: $('#ashotwhy'),
    snd: $('#asnd'), sndPrev: $('#asndprev'), sndAudio: $('#asndaudio'),
    sndName: $('#asndname'), sndWhy: $('#asndwhy'),
    mdRow: $('#amdrow'), mdOut: $('#amdout'),
    pvRow: $('#apvrow'), pvFrame: $('#apvframe'), pvNote: $('#apvnote'),
    // the jolly card's fields, by the names the markdown gives them
    jolly: { 'front-primary': $('#ajfp'), 'front-secondary': $('#ajfs'),
             'back-primary': $('#ajbp'), 'back-secondary': $('#ajbs') }
  };
  var JOLLY_KEYS = ['front-primary', 'front-secondary', 'back-primary', 'back-secondary'];
  // the dashboard follows the language: the first field is labelled with
  // its name and reads in its direction (as do the context and the
  // opposite), the reading row exists only when the language has one,
  // and the deck-name hint suggests a name nested under the language.
  // The meaning and the notes follow the GLOSS language the same way --
  // they are the two boxes the card's prose is typed into, and an Arabic
  // meaning has to run right to left inside this left-to-right form.
  $('#afalab').textContent = L.name.toLowerCase();
  $('#aenlab').textContent = GLOSS_LABEL;
  [A.fa, A.ctx, A.opp].forEach(targetAttrs);
  [A.en, A.notes].forEach(glossAttrs);
  $('#akanarow').hidden = !L.reading;
  A.oppKana.hidden = !L.reading;
  A.deckNew.placeholder = 'name the new deck (use :: to nest, e.g. ' + L.name + '::YouTube)';
  var ankiWasPlaying = false, ankiShot = null, ankiTime = 0;
  // EVERY OPENING OF THE SHEET IS ITS OWN.  sheetSeq counts them, and whatever
  // answers later -- a save, an add, a copy, the cut editor -- asks whether the
  // sheet that asked is still the one open before it touches it.  closeTimer
  // is the sheet closing itself after a save; cutting, how many cut editors
  // are open over it; busyFor, the sheet whose press is out (one at a time).
  var sheetSeq = 0, closeTimer = 0, cutting = 0, busyFor = 0;
  // which note type the card will use: "vocab" (the default) or
  // "opposites" -- the second asks "what is the opposite of X?", and its
  // answer side is written by hand in the dashboard -- or, for an exercise
  // deck and for markdown, "jolly"
  var ankiKind = 'vocab';
  // which cards the note makes: 'both', 'forward' (fa->en only) or
  // 'reverse' (en->fa only; vocab only -- the opposites note type has no
  // ReverseOnly field, so the option is hidden there)
  var ankiDir = 'both';
  function setDir(d) {
    ankiDir = d;
    var btns = document.querySelectorAll('#adir .dbtn');
    Array.prototype.forEach.call(btns, function (b) {
      b.classList.toggle('on', b.dataset.dir === d);
    });
  }
  Array.prototype.forEach.call(
    document.querySelectorAll('#adir .dbtn'), function (b) {
      b.onclick = function () { setDir(b.dataset.dir); };
    });
  // the rows the type shows: a jolly card is its four fields, and the
  // frame and the recording go into one of them rather than on a side
  function paintKind() {
    var k = ankiKind, opp = k === 'opposites', jolly = k === 'jolly';
    $('#akvocab').classList.toggle('on', k === 'vocab');
    $('#akopp').classList.toggle('on', opp);
    $('#akjolly').classList.toggle('on', jolly);
    ['#afarow', '#atrrow', '#anotesrow', '#asrcrow', '#adirrow'].forEach(function (s) {
      $(s).hidden = jolly;
    });
    $('#akanarow').hidden = jolly || !L.reading;
    $('#aenrow').hidden = opp || jolly;
    $('#actxrow').hidden = opp || jolly;
    $('#aopprow').hidden = !opp;
    $('#ajollyrow').hidden = !jolly;
    $('#adirrev').hidden = opp;
    $('#adirfwd').textContent = opp
      ? '→ word → opposite' : '→ ' + L.name + ' → ' + G.name;
    Array.prototype.forEach.call(document.querySelectorAll('#anki .ashotpick'),
      function (l) { l.hidden = jolly; });
    $('#asndsides').hidden = jolly;
    Array.prototype.forEach.call(document.querySelectorAll('#anki .ajollyinto'),
      function (l) { l.hidden = !jolly; });
  }
  function setKind(k) {
    // Anki has no note type for a jolly card
    if (k === 'jolly' && ankiTarget === 'anki') k = 'vocab';
    var was = ankiKind;
    ankiKind = k;
    if (k === 'opposites' && ankiDir === 'reverse') setDir('both');
    paintKind();
    if (k === 'opposites' && !A.opp.value) A.opp.focus();
    if (k === 'jolly' && was !== 'jolly') jollyOn();
  }
  $('#akvocab').onclick = function () { setKind('vocab'); };
  $('#akopp').onclick = function () { setKind('opposites'); };
  $('#akjolly').onclick = function () { setKind('jolly'); };
  var decksCache = [];
  var capFor = null, capVideo = null, capCropped = false, capSurface = '';

  function vidTitle() {
    return document.title.replace(/ — Parseh videos$/, '');
  }
  // A deck belongs to a language and a card goes to the deck of its own
  // language (the store refiles it if not), so this video's language comes
  // first, under its own heading; the other languages' decks are still
  // listed, each under its own, so an existing deck is never invisible --
  // picking one just means the card lands in the deck of THIS language
  // with that name, and the save says so.  The option value is
  // "<folder>/<slug>": a slug alone no longer names one deck.
  function deckOptions(list) {
    decksCache = list;
    var last = deckChoice('anki', list.map(function (d) { return d.folder + '/' + d.slug; }),
                          localStorage.getItem('yt_deck') || '');
    A.deck.innerHTML = '';
    A.deck.dataset.of = 'anki';
    var groups = {}, order = [];
    list.forEach(function (d) {
      if (!groups[d.lang]) { groups[d.lang] = []; order.push(d.lang); }
      groups[d.lang].push(d);
    });
    order.sort(function (a, b) {
      return (a === L.code ? 0 : 1) - (b === L.code ? 0 : 1);
    });
    order.forEach(function (code) {
      var g = document.createElement('optgroup');
      g.label = groups[code][0].language +
                (code === L.code ? '' : ' (another language)');
      groups[code].forEach(function (d) {
        var o = document.createElement('option');
        o.value = d.folder + '/' + d.slug;
        o.dataset.lang = d.lang;
        o.dataset.name = d.name;
        o.textContent = d.name + ' (' + d.cards + ' card' +
                        (d.cards === 1 ? '' : 's') + ')';
        if (o.value === last) o.selected = true;
        g.appendChild(o);
      });
      A.deck.appendChild(g);
    });
    var o = document.createElement('option');
    o.value = ''; o.textContent = '+ new deck…';
    if (!list.length || last === '') o.selected = true;
    A.deck.appendChild(o);
    deckPick();
  }
  /* THE CHOICE ON THE SCREEN OUTLIVES A NEW LIST.  The options are drawn
     again whenever the decks are listed anew (loadDecks(again): a count
     changed), and the answer can come after the owner has already picked --
     "+ new deck…" with its name being typed, or another deck.  Drawn from the
     deck used last, that pick would be undone and the card go where it was
     not sent.  So once the owner has picked (the select's own change), a list
     for the same destination keeps the pick while it is still one of the
     options; a card gone somewhere (the deck used last is written) hands the
     choice back to the deck used last.  '' is "+ new deck…"; null selects
     no option, which leaves the browser's first. */
  var deckPicked = false;
  function deckChoice(kind, values, last) {
    if (deckPicked && A.deck.dataset.of === kind && A.deck.options.length) {
      var shown = A.deck.value;
      if (shown === '' || values.indexOf(shown) >= 0) return shown;
    }
    return last && values.indexOf(last) >= 0 ? last : (values.length ? null : '');
  }
  function deckPick() {
    A.deckNew.hidden = A.deck.value !== '';
    if (!A.deckNew.hidden && !A.deckNew.value) A.deckNew.focus();
  }
  A.deck.addEventListener('change', function () { deckPicked = true; deckPick(); });

  /* -- where the card goes.  One <select> lists the decks of whichever
     destination is picked: Anki's (every language, as above) or the
     exercise decks of this video's language, which is the only language an
     exercise deck of this card could be in.  A list that arrives after the
     switch has moved on is dropped. -- */
  var CARD_TARGETS = ['anki', 'deck', 'md'];
  var ankiTarget = 'anki', exDecks = [], deckAsk = 0;
  var KIT = window.ParsehCards || null;
  // said wherever the kit is needed and is not there (the book reader's
  // sheet says the same)
  var KIT_GONE = 'the card kit (lib/cardkit.js) did not load: reload the page';
  // the tab's share and the recording of its sound (youtube/lib/tabcapture.js),
  // which the add page uses too
  var TC = window.ParsehTabCapture || null;
  var TC_GONE = 'the tab capture (youtube/lib/tabcapture.js) did not load: reload the page';
  // the sheet's head and its button, per destination
  var TARGET_TITLE = { anki: 'anki card', deck: 'exercise card', md: 'card markdown' };
  var SAVE_LABEL = { anki: 'save card', deck: 'add to deck', md: 'copy markdown' };
  function exDeckOptions(list) {
    exDecks = list;
    var last = deckChoice('deck', list.map(function (d) { return d.path; }),
                          localStorage.getItem('yt_exdeck') || '');
    A.deck.innerHTML = '';
    A.deck.dataset.of = 'deck';
    list.forEach(function (d) {
      var o = document.createElement('option');
      o.value = d.path;
      o.dataset.name = d.name;
      var n = (d.counts && d.counts.total) || 0;
      o.textContent = d.name + ' (' + n + ' exercise' + (n === 1 ? '' : 's') + ')';
      if (o.value === last) o.selected = true;
      A.deck.appendChild(o);
    });
    var o = document.createElement('option');
    o.value = ''; o.textContent = '+ new deck…';
    if (!list.length || last === '') o.selected = true;
    A.deck.appendChild(o);
    deckPick();
  }
  // `again`: the same destination's list asked for anew (a count changed),
  // which keeps showing the old one until it comes
  function loadDecks(again) {
    var n = ++deckAsk, t = ankiTarget;
    if (t === 'md') return;
    if (!again) A.deck.innerHTML = '';
    A.deckNew.placeholder = t === 'anki'
      ? 'name the new deck (use :: to nest, e.g. ' + L.name + '::YouTube)'
      : 'name the new exercise deck';
    if (t === 'anki') {
      fetch('/anki/decks', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (list) { if (n === deckAsk) deckOptions(list); })
        .catch(function () { if (n === deckAsk) deckOptions(decksCache); });
      return;
    }
    if (!KIT) { exDeckOptions([]); return; }
    KIT.decks(L.code).then(function (list) {
      if (n === deckAsk) exDeckOptions(list);
    }, function (e) {
      if (n !== deckAsk) return;
      exDeckOptions(exDecks);
      A.stat.textContent = 'the exercise decks did not list: ' + e.message;
    });
  }
  var TARGET_NOTE = {
    anki: '',
    deck: 'an exercise in the deck, studied on its page; ' +
          (CFG.kind === 'audio' ? 'the recording goes' : 'the recording and the frame go') + ' in with it',
    md: 'one :::exercise block on the clipboard, for a studio document or a deck’s “Add exercise”'
  };
  // the name typed for a new deck, per destination: an Anki name nests with
  // ::, an exercise deck's does not, and neither is the other's deck
  var newDeckNames = { anki: '', deck: '' };
  function setTarget(t) {
    if (CARD_TARGETS.indexOf(t) < 0) t = 'anki';
    if (ankiTarget !== 'md') newDeckNames[ankiTarget] = A.deckNew.value;
    if (t !== 'md') A.deckNew.value = newDeckNames[t];
    ankiTarget = t;
    localStorage.setItem('yt_card_target', t);
    [['anki', '#atanki'], ['deck', '#atdeck'], ['md', '#atmd']].forEach(function (p) {
      $(p[1]).classList.toggle('on', p[0] === t);
      $(p[1]).setAttribute('aria-pressed', p[0] === t ? 'true' : 'false');
    });
    var anki = t === 'anki';
    $('#akjolly').hidden = anki;
    // the direction, per destination: Anki's "both" is two cards; an
    // exercise asks both sides once (repeat) or draws one each time it is
    // shown (random)
    var both = $('#adirboth');
    $('#adirrnd').hidden = anki;
    if (anki && ankiDir === 'both-random') setDir('both');
    both.textContent = both.textContent.replace(/ both.*/, anki ? ' both' : ' both (repeat)');
    both.title = anki
      ? 'two cards: ' + L.name + ' \u2192 ' + G.name + ' and ' + G.name + ' \u2192 ' + L.name
      : 'both (repeat): shown ' + L.name + ' first, and in a deck two linked cards, one asked from each side';
    if (anki && ankiKind === 'jolly') setKind('vocab');
    A.deckRow.hidden = t === 'md';
    $('#atagsrow').hidden = !anki;
    $('#abuild').hidden = !anki;
    $('#async').hidden = !anki;
    $('#ahtitle').textContent = TARGET_TITLE[t];
    dupArmed = false;
    A.saveLab.textContent = SAVE_LABEL[t];
    $('#apreview').title = anki ? 'how the finished card will look in Anki, both directions'
                                : 'how the card will look in a deck: click it to turn it';
    A.note.textContent = TARGET_NOTE[t];
    A.note.hidden = !TARGET_NOTE[t];
    A.pvRow.hidden = true; A.pvFrame.srcdoc = '';
    A.mdRow.hidden = true;
    A.stat.textContent = '';
    if (!anki && !KIT) A.stat.textContent = KIT_GONE;
    loadDecks();
  }
  $('#atanki').onclick = function () { setTarget('anki'); };
  $('#atdeck').onclick = function () { setTarget('deck'); };
  $('#atmd').onclick = function () { setTarget('md'); };

  /* -- the jolly fields.  Prefilled from the word when jolly is picked, and
     left alone once written in; a picture or a recording goes in as a line
     of its own after the line the cursor was on, in the box the cursor was
     last in, typed in or not (jollyFocus; the back's main text until one
     has been). -- */
  var jollyTouched = false, jollyFocus = null;
  JOLLY_KEYS.forEach(function (k) {
    var ta = A.jolly[k];
    ta.addEventListener('focus', function () { jollyFocus = ta; });
    ta.addEventListener('input', function () { jollyTouched = true; });
  });
  function jollyValues() {
    var out = {};
    JOLLY_KEYS.forEach(function (k) { out[k] = A.jolly[k].value; });
    return out;
  }
  function fillJolly() {
    var word = A.fa.value.trim();
    // a Latin-script target cannot be told from English by its letters, so
    // its word is marked as the target's, as the kit marks a vocab card's
    A.jolly['front-primary'].value = (L.script === 'latin' && word)
      ? '[' + word.replace(/[\[\]]/g, '').replace(/\s+/g, ' ') + ']{tl}' : word;
    A.jolly['front-secondary'].value = [L.reading ? A.kana.value.trim() : '', A.tr.value.trim()]
      .filter(Boolean).join(' · ');
    A.jolly['back-primary'].value = A.en.value.trim();
    A.jolly['back-secondary'].value = A.ctx.value.trim();
    // written anew, so the recording and the frame are offered anew
    if (ankiClip) ankiClip.offered = false;
    if (ankiFrame) ankiFrame.offered = false;
  }
  function mediaLineOf(line) {
    var m = /^\s*!\[[^\]]*\]\(\s*([^()\s]+)\s*\)\s*$/.exec(line);
    return m ? m[1] : null;
  }
  function jollyNames(path) {
    return JOLLY_KEYS.some(function (k) { return A.jolly[k].value.indexOf(path) >= 0; });
  }
  function jollyInsert(path) {
    if (jollyNames(path)) return;
    var ta = jollyFocus || A.jolly['back-primary'];
    var v = ta.value, line = '![](' + path + ')';
    var at = (ta === jollyFocus && ta.selectionEnd != null) ? ta.selectionEnd : v.length;
    var end = v.indexOf('\n', at);
    if (end < 0) end = v.length;
    var head = v.slice(0, end), lead = head && head.slice(-1) !== '\n' ? '\n' : '';
    ta.value = head + lead + line + v.slice(end);
    var caret = (head + lead + line).length;
    try { ta.setSelectionRange(caret, caret); } catch (e) {}
    // tall enough to show the line it was given
    ta.rows = Math.min(8, Math.max(ta.rows, ta.value.split('\n').length));
  }
  function jollyRemove(path) {
    JOLLY_KEYS.forEach(function (k) {
      var ta = A.jolly[k], lines = ta.value.split('\n');
      var kept = lines.filter(function (l) { return mediaLineOf(l) !== path; });
      if (kept.length !== lines.length) ta.value = kept.join('\n');
    });
  }
  // the recording's line and the frame's go into the fields ONCE each: a
  // line the person then deletes stays deleted (the save does not bring it
  // back), and the save says the card goes without it
  function offerClip() {
    if (!ankiClip || ankiClip.offered) return;
    ankiClip.offered = true;
    jollyInsert('audio/' + ankiClip.clip.name);
  }
  function offerFrame(rec) {
    var f = ankiFrame;
    if (!rec || !f || f.clip !== rec || f.offered) return;
    f.offered = true;
    jollyInsert('images/' + rec.name);
  }
  function jollyOn() {
    if (!jollyTouched) fillJolly();
    offerClip();
    if (ankiShot && KIT) {
      ensureFrame().then(function (rec) {
        if (ankiKind === 'jolly') offerFrame(rec);
      }, function (e) { A.stat.textContent = e.message; });
    }
  }
  // what a press's markdown was to carry and does not name: the lines taken
  // out of a jolly card's fields.  '' when it names everything.  `clip` and
  // `frame` are the tray's records the press was made with
  function leftOut(md, clip, frame) {
    var gone = [];
    if (clip && md.indexOf('audio/' + clip.name) < 0) gone.push('the recording');
    if (frame && md.indexOf('images/' + frame.name) < 0) gone.push('the frame');
    return gone.length ? gone.join(' and ') + (gone.length > 1 ? ' are' : ' is') +
      ' not on the card: ' + (gone.length > 1 ? 'their lines were' : 'its line was') +
      ' taken out of the fields' : '';
  }
  // what the markdown does name, of the recording and the frame
  function carried(md, its, clip, frame) {
    return [clip && md.indexOf('audio/' + clip.name) >= 0 ? its + ' recording' : '',
            frame && md.indexOf('images/' + frame.name) >= 0 ? its + ' frame' : '']
      .filter(Boolean);
  }

  /* -- the tray's copies.  A recording is a clip in the tray from the moment
     it is cut; the captured frame goes there only when a deck or markdown
     needs a file to name.  One nobody used -- removed, replaced, or left on a
     sheet that was closed -- goes out of the tray again, as the cut editor's
     own cancel does, and as the book reader's sheet does.  Two kinds stay
     whatever happens to the sheet: a file that went onto a card (saved,
     added, or copied as markdown: trayUsed), and one a press has carried out
     and not yet had its answer for (trayOut, a count per name; a frame still
     on its way to the tray counts its presses itself, `held`) -- closing the
     sheet the moment after "add to deck" must not take out of the tray the
     recording the deck is about to fetch from it. -- */
  // `offered`: its line was put in the jolly fields once, and is not put
  // back if the person takes it out again
  var ankiClip = null;     // {clip: the tray's record, offered}
  var ankiFrame = null;    // {data: the shot it is, clip, ready, held, offered}
  var trayUsed = {}, trayOut = {};
  function forgetTray(name) {
    if (!name || trayUsed[name] || trayOut[name]) return;
    fetch('/clips/api/' + encodeURIComponent(name), { method: 'DELETE' })
      .catch(function () {});
  }
  // the frame `data` on its way to the tray, begun once
  function frameFor(data) {
    if (!data || !KIT) return null;
    if (ankiFrame && ankiFrame.data === data) return ankiFrame;
    dropFrame();
    var f = { data: data, clip: null, held: 0 };
    f.ready = KIT.uploadFrame(data, (A.fa.value.trim() || 'frame') + ' frame', L.code)
      .then(function (rec) {
        f.clip = rec;
        // dropped while it went, and no press waits for it
        if (ankiFrame !== f && !f.held) forgetTray(rec.name);
        return rec;
      }, function (e) {
        if (ankiFrame === f) ankiFrame = null;
        throw e;
      });
    ankiFrame = f;
    return f;
  }
  function ensureFrame() {
    var f = frameFor(ankiShot);
    return f ? f.ready : Promise.resolve(null);
  }
  function dropFrame() {
    var f = ankiFrame;
    ankiFrame = null;
    if (!f || !f.clip) return;
    if (!f.held) forgetTray(f.clip.name);
    jollyRemove('images/' + f.clip.name);
  }
  function setClip(clip) {
    unarm();
    dropClip();
    ankiClip = { clip: clip, offered: false };
    A.sndAudio.src = clip.url;
    A.sndName.textContent = clip.name +
      (typeof clip.duration === 'number' ? ' · ' + clip.duration.toFixed(2) + ' s' : '');
    A.sndPrev.hidden = false;
    if (ankiKind === 'jolly') offerClip();
  }
  // `closing`: the sheet goes, and its fields with it
  function dropClip(closing) {
    var c = ankiClip;
    ankiClip = null;
    try { A.sndAudio.pause(); } catch (e) {}
    A.sndAudio.removeAttribute('src');
    A.sndPrev.hidden = true;
    A.sndName.textContent = '';
    if (!c) return;
    forgetTray(c.clip.name);
    if (!closing) jollyRemove('audio/' + c.clip.name);
  }
  $('#asnddel').onclick = function () { dropClip(false); };
  function pickedSide(name, fallback) {
    var r = document.querySelector('#anki input[name=' + name + ']:checked');
    return r ? (r.value === 'back' ? 'back' : 'front') : fallback;
  }

  function clearShot() {
    ankiShot = null; A.prev.hidden = true; A.img.src = '';
    dropFrame();
  }
  $('#ashotdel').onclick = clearShot;

  /* -- WHERE IN THE FILM THE CARD'S WORD IS SAID.  A caption carries its
     start and nothing else: it lasts until the next one starts (the last,
     until the film ends), and nothing records where a chunk or a word falls
     inside it.  So the cut editor opens on the word's share of the caption's
     text -- the chunks before it, each with the separator the caption joins
     them with, then the words of its chunk before it -- which a person then
     moves by ear.  Code points, as the word line counts them. -- */
  var ankiAt = null;       // {i: caption, j: chunk, k: word or null, line}
  function cpLen(s) { return Array.from(String(s || '')).length; }
  function wordSpan(ch, at) {
    if (at.k == null || at.k < 0) return null;
    var fa = ch.fa || '';
    if (at.line) {
      // the word line's own division, spaces and all, as it draws the words
      var spans;
      try { spans = ParsehWordline.align(fa, ParsehWordline.parse(at.line)); }
      catch (e) { return null; }
      var pos = 0;
      for (var n = 0; n < spans.length; n++) {
        var len = cpLen(spans[n][0]);
        if (spans[n][2] === at.k) return [pos, pos + len];
        pos += len;
      }
      return null;
    }
    if (!L.word_sep) return null;
    var words = wordsOf(fa), from = 0;
    if (at.k >= words.length) return null;
    for (var q = 0; q < at.k; q++) from += cpLen(words[q]) + cpLen(L.word_sep);
    return [from, from + cpLen(words[at.k])];
  }
  function cutPlan() {
    var at = ankiAt, sg = at && segs[at.i];
    if (!sg || !KIT) return null;
    var next = segs[at.i + 1];
    var dur = (player && player.getDuration) ? player.getDuration() : 0;
    var t0 = +sg.start || 0;
    var t1 = next ? +next.start : (dur > t0 ? dur : t0 + 4);
    // the caption's text is its chunks joined -- and where a caption was
    // written otherwise (a Japanese one with spaces its chunks do not have)
    // the chunks are what the stretch is counted in, so they are the whole
    var sep = L.word_sep || '', chunks = sg.chunks || [];
    var joined = chunks.map(function (c) { return c.fa || ''; }).join(sep);
    var units = chunks.length ? cpLen(joined) : cpLen(sg.text), from = 0, to = units;
    var ch = at.j >= 0 ? chunks[at.j] : null;
    if (ch) {
      var pre = 0;
      for (var m = 0; m < at.j; m++) pre += cpLen(chunks[m].fa) + cpLen(sep);
      var w = wordSpan(ch, at);
      from = pre + (w ? w[0] : 0);
      to = pre + (w ? w[1] : cpLen(ch.fa));
    }
    return { context: [t0, t1], guess: KIT.guess([t0, t1], units, from, to) };
  }
  // THE CARD'S MOMENT -- its time, its source's link, a deck's link back,
  // the frame a capture takes: where the film is when that is inside the
  // caption the card was opened on (the word was just heard), and that
  // caption's start otherwise, so a word picked out of another caption
  // goes back to where it is said and not to wherever the film stands
  function cardMoment(sg) {
    var t0 = sg ? (+sg.start || 0) : 0;
    if (!(player && ready && player.getCurrentTime)) return t0;
    var now = player.getCurrentTime();
    if (!sg) return now;
    var next = segs[segs.indexOf(sg) + 1];
    return (now >= t0 && (!next || now < +next.start)) ? now : t0;
  }
  // Why there is nothing to cut here, or '' when there is.  A film on this
  // machine is cut by the server; a YouTube video's sound reaches nobody's
  // script, and is cut from a recording of this tab as it plays the stretch
  // (the kit records it; the share is the frame capture's, shareTab above),
  // which Chrome and Edge allow
  function noCut() {
    if (!KIT) return KIT_GONE;
    if (CFG.media) return '';
    if (CFG.local) return 'the film of this video is not on this machine any more, so there is no sound to cut';
    var why = KIT.tabProblem ? KIT.tabProblem() : 'the card kit cannot record a tab';
    if (why) return 'a YouTube video’s sound is cut from a recording of this tab, and ' + why;
    if (!(player && ready)) return 'the YouTube player has not loaded, so there is no sound to record';
    return '';
  }
  function paintCut() {
    var why = noCut();
    A.snd.disabled = !!why;
    A.snd.title = why || (CFG.media
      ? 'cut the stretch of the film this card is about into a clip, and put it on the card'
      : 'record this tab while the video plays the stretch this card is about, cut the clip out of it by ear, ' +
        'and put it on the card');
    // said under the button too: a phone shows no title
    A.sndWhy.textContent = why;
    A.sndWhy.hidden = !why;
  }
  A.snd.onclick = function () {
    var plan = cutPlan();
    if (!plan || noCut()) return;
    var word = A.fa.value.trim(), seq = sheetSeq;
    try { A.sndAudio.pause(); } catch (e) {}
    // somebody at work in the cut editor is still making this card: the
    // sheet does not close itself under it (closeSoon)
    cutting++;
    clearTimeout(closeTimer);
    KIT.cut({
      source: CFG.media
        ? { kind: 'film', src: CFG.media, cutUrl: '/youtube/api/clip',
            peaksUrl: '/youtube/api/peaks', video: CFG.id }
        : { kind: 'tab', video: CFG.id, player: player, stream: shareTab },
      context: plan.context, guess: plan.guess,
      lang: L.code, hint: word, label: fmt(plan.context[0]), text: word
    }).then(function (clip) {
      cutting--;
      if (!clip) return;
      // a clip used for a sheet no longer open is on nobody's card
      if (ankiOpen && seq === sheetSeq) setClip(clip); else forgetTray(clip.name);
    }, function () { cutting--; });
  };

  // `reading`, for a word of the chunk's word line: the line's own reading
  // of that word.  `at` says where the card's text is: the caption i, its
  // chunk j and, for one word of the chunk, the word k (`line` when k counts
  // the words of the chunk's word line) -- what the cut editor starts from
  function openAnki(word, ch, sg, reading, at) {
    // a sheet of its own: an answer still out for the last one is not this
    // one's, and neither is the last one's pending close
    sheetSeq++;
    clearTimeout(closeTimer);
    ankiTime = cardMoment(sg);
    A.time.textContent = fmt(ankiTime);
    if (player && ready && player.getPlayerState &&
        player.getPlayerState() === 1) {
      ankiWasPlaying = true; player.pauseVideo();
    } else ankiWasPlaying = false;
    closeCloud();
    ankiAt = at || { i: segs.indexOf(sg), j: sg ? (sg.chunks || []).indexOf(ch) : -1, k: null, line: '' };
    A.fa.value = word;
    var ofLine = typeof reading === 'string';
    // the reading is the whole chunk's (group ruby), so it fits the card
    // only when the card is the whole chunk; for one word of it the field
    // is left for the hand -- unless the word line gave the word its own,
    // which is the kana where the language has one and the romanisation
    // (pinyin) where it has not
    A.kana.value = ofLine ? (L.reading ? reading : '')
                          : (L.reading && word === ch.fa && ch.kana) ? ch.kana : '';
    A.tr.value = ofLine && !L.reading ? reading : (ch.tr || '');
    A.en.value = ch.en || '';
    // a single word gets the whole phrase as context; a whole phrase
    // gets its caption -- the sentence it lives in -- and so does a word
    // of the line, which the whole phrase would only repeat
    A.ctx.value = ((ofLine || word === ch.fa) && sg && sg.text) ? sg.text : ch.fa;
    A.notes.value = vocText(ch.voc) +
      (ch.note ? (ch.voc ? '\n' : '') + ch.note : '');
    // the registry's tag: farsi-youtube for Persian, exactly as before
    A.tags.value = L.tag + '-youtube ' + CFG.id;
    A.src.value = vidTitle() + ' — ' + fmt(ankiTime);
    A.opp.value = ''; A.oppKana.value = ''; A.oppTr.value = '';
    JOLLY_KEYS.forEach(function (k) { A.jolly[k].value = ''; A.jolly[k].rows = 2; });
    jollyTouched = false; jollyFocus = null;
    ankiKind = 'vocab';
    // the recording and the frame of the last card are not this one's; one
    // the last card went with stays in the tray (forgetTray)
    dropClip(true);
    setDir('both');
    clearShot();
    deckPicked = false;         // a new card starts from the deck used last
    setTarget(localStorage.getItem('yt_card_target') || 'anki');
    setKind('vocab');
    paintCut();
    paintShot();
    A.box.querySelector('input[name=asndside][value=front]').checked = true;
    A.back.hidden = false; A.box.hidden = false; ankiOpen = true;
    A.fa.focus();
  }
  function closeAnki() {
    ankiOpen = false; A.back.hidden = true; A.box.hidden = true;
    clearTimeout(closeTimer);
    laterSheetShut();
    // a clip nobody used, and a frame sent to the tray for a preview and
    // never saved with a card, go out of the tray
    dropClip(true);
    dropFrame();
    if (ankiWasPlaying && player && ready) player.playVideo();
    ankiWasPlaying = false;
  }
  $('#acancel').onclick = closeAnki;
  A.back.addEventListener('click', closeAnki);
  document.addEventListener('keydown', function (e) {
    if (!ankiOpen) return;
    if (e.key === 'Escape') { e.preventDefault(); closeAnki(); }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); saveCard();
    }
  });

  /* -- capturing a frame.  THERE ARE TWO WAYS, and which one is used depends
     on where the picture is, not on the browser (the owner's choice,
     2026-09-23).

     A FILM ON THIS MACHINE is a <video> of this very page, served from this
     very origin: a canvas reads its pixels outright.  No sharing question, no
     calibration dots, no rolling in muted past an overlay that is not there,
     and -- the point -- it works on a phone, where no browser shares a tab at
     all.  Until today every capture went the long way round, so the button on
     a phone answered "capture needs a secure page", which was never the
     reason (TO-DO §2.18).

     A YOUTUBE VIDEO is behind a cross-origin iframe and its pixels can only
     come from a display capture, which is a computer's affair.  On a phone
     the button says so plainly instead of blaming the address.

     Everything below is that second way, and all of it exists to hand back
     the VIDEO'S OWN frame, never a page screenshot:
       . Chrome, "This Tab": Region Capture crops the stream to the video
         element itself; older Chromium falls back to viewport arithmetic.
       . Firefox -- and any window or screen share: the page flashes two
         coloured dots on the video's corners, finds them in the captured
         frame, and derives the exact pixel mapping.  Toolbars, zoom, DPR
         and window position all cancel out of that equation.
     Standards only; nothing depends on YouTube's internals staying still.
     A PAUSED embed shows YouTube's controls, and they linger for a full
     FIVE seconds once playback starts -- so the capture seeks ~5s before
     the moment and rolls in muted: the overlay has just faded when the
     wanted frame goes by, and the player freezes back on it. -- */
  /* -- SHARING THIS TAB.  One share, asked for once, serves the frame
     capture (its pictures), the cut editor on a YouTube video (its sound,
     which lib/cardkit.js records while the stretch plays) and the waveform
     (below): one question from Chrome for all of them, however many frames
     and clips follow.  It is youtube/lib/tabcapture.js that holds it -- the
     add page records this tab too, and one share serves whoever asks.
     `want.audio`: the share must carry live sound. -- */
  var shareTab = TC ? TC.share : function () { return Promise.reject(new Error(TC_GONE)); };
  if (!TC) shareTab.live = function () { return null; };

  function ensureCapture() {
    if (capVideo && capFor && capFor === shareTab.live()) return Promise.resolve();
    if (!shareTab.live()) A.hint.hidden = false;
    return shareTab().then(function (s) {
      var track = s.getVideoTracks()[0];
      var st = track.getSettings ? track.getSettings() : {};
      capFor = s;
      capSurface = st.displaySurface || '';
      capCropped = false;
      // Region Capture (Chrome, own-tab shares): the track becomes the
      // video element itself -- pixel-perfect, immune to everything
      var crop = (capSurface === 'browser' && window.CropTarget &&
                  CropTarget.fromElement && track.cropTo)
        ? CropTarget.fromElement(vid).then(function (t) {
            return track.cropTo(t).then(function () { capCropped = true; });
          }).catch(function () {})
        : Promise.resolve();
      return crop.then(function () {
        capVideo = document.createElement('video');
        capVideo.muted = true; capVideo.playsInline = true;
        // its pictures only: the share's sound is never played on this page.
        // Not waited for: a share taken a while ago (for a recording) sends
        // no picture of a page that has not changed since, and play() would
        // wait for one -- the capture below changes the page (the sheet
        // goes), and waits for the picture that brings (framed)
        capVideo.srcObject = new MediaStream(s.getVideoTracks());
        capVideo.play().catch(function () {});
      });
    });
  }
  function sleep(ms) {
    return new Promise(function (r) { setTimeout(r, ms); });
  }
  // after rolling, hold until YouTube's overlay has faded -- that takes a
  // full five seconds of playback -- AND the video has reached the wanted
  // moment again (hard stop at ten)
  function waitFrame(t0, rolled) {
    if (!rolled) return sleep(300);
    var begun = Date.now();
    return new Promise(function (res) {
      (function poll() {
        var el = Date.now() - begun, cur = t0;
        try { cur = player.getCurrentTime(); } catch (err) {}
        if ((el >= 5000 && cur >= t0) || el >= 10000) return res();
        setTimeout(poll, 120);
      })();
    }).then(function () {
      var cur = t0;
      try { cur = player.getCurrentTime(); } catch (err) {}
      if (cur <= t0 + 0.6) return;
      // the moment sits inside the video's first five seconds, so the
      // fade-out wait overshot it.  Glide back while still playing -- a
      // pause would resurface the controls; the region is buffered, so
      // no spinner appears either
      player.seekTo(Math.max(0, t0 - 0.2), true);
      return sleep(450);
    });
  }
  // Once the capture has a picture of the page as it is now (four seconds at
  // most).  A share sends pictures when the page changes -- but one kept a
  // while and given a new element can go on sending none however much the
  // video plays (Chrome, driven: a share first used for a recording), until
  // something asks it for a frame outright: a track processor reading one
  // does (Chromium; elsewhere the page's changes are all there is)
  function framed() {
    var begun = Date.now();
    askFrame();
    return new Promise(function (res) {
      (function look() {
        var el = Date.now() - begun;
        if ((capVideo && capVideo.videoWidth && el > 150) || el > 4000) return res();
        setTimeout(look, 40);
      })();
    });
  }
  function askFrame() {
    if (!window.MediaStreamTrackProcessor || !capFor) return;
    var track = capFor.getVideoTracks()[0];
    if (!track || track.readyState !== 'live') return;
    var copy = track.clone(), done = false;
    var stop = function () {
      if (done) return;
      done = true;
      try { reader.cancel().catch(function () {}); } catch (e) {}
      copy.stop();
    };
    try {
      var reader = new MediaStreamTrackProcessor({ track: copy }).readable.getReader();
      reader.read().then(function (r) { if (r.value) r.value.close(); stop(); }, stop);
      setTimeout(stop, 3000);
    } catch (e) { copy.stop(); }
  }
  function grabRaw() {
    var vw = capVideo.videoWidth, vh = capVideo.videoHeight;
    if (!vw) throw new Error('no frame arrived — try once more');
    var c = document.createElement('canvas');
    c.width = vw; c.height = vh;
    c.getContext('2d').drawImage(capVideo, 0, 0);
    return c;
  }
  function toJpeg(c) { return c.toDataURL('image/jpeg', 0.87); }
  function cropJpeg(c, x, y, w, h) {
    x = Math.max(0, Math.round(x)); y = Math.max(0, Math.round(y));
    w = Math.round(Math.min(w, c.width - x));
    h = Math.round(Math.min(h, c.height - y));
    if (w < 8 || h < 8)
      throw new Error('the video area fell outside the capture — retry');
    var o = document.createElement('canvas');
    o.width = w; o.height = h;
    o.getContext('2d').drawImage(c, x, y, w, h, 0, 0, w, h);
    return toJpeg(o);
  }
  /* the calibration dots: magenta on the video's top-left corner, cyan on
     its bottom-right; their centres sit at known viewport coordinates */
  var mkEls = null;
  function showMarkers(r) {
    hideMarkers();
    function dot(color, x, y) {
      var d = document.createElement('div');
      d.style.cssText = 'position:fixed;width:26px;height:26px;z-index:200;' +
        'pointer-events:none;background:' + color +
        ';left:' + (x - 13) + 'px;top:' + (y - 13) + 'px';
      document.body.appendChild(d);
      return d;
    }
    var p = { x1: r.left + 13, y1: r.top + 13,
              x2: r.right - 13, y2: r.bottom - 13 };
    mkEls = [dot('#f0f', p.x1, p.y1), dot('#0ff', p.x2, p.y2)];
    return p;
  }
  function hideMarkers() {
    (mkEls || []).forEach(function (d) {
      if (d.parentNode) d.parentNode.removeChild(d);
    });
    mkEls = null;
  }
  function locateMarkers(c, p) {
    var d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    var m = { x: 0, y: 0, n: 0 }, k = { x: 0, y: 0, n: 0 };
    for (var y = 0; y < c.height; y += 2) {
      for (var x = 0; x < c.width; x += 2) {
        var i = (y * c.width + x) * 4;
        var R = d[i], G = d[i + 1], B = d[i + 2];
        if (R > 180 && B > 180 && G < 100) { m.x += x; m.y += y; m.n++; }
        else if (G > 180 && B > 180 && R < 100) { k.x += x; k.y += y; k.n++; }
      }
    }
    if (m.n < 12 || k.n < 12)
      throw new Error('could not see the player in the shared ' +
        (capSurface || 'window') +
        ' — keep this window visible on top, then try again');
    var ax = m.x / m.n, ay = m.y / m.n, bx = k.x / k.n, by = k.y / k.n;
    var sx = (bx - ax) / (p.x2 - p.x1), sy = (by - ay) / (p.y2 - p.y1);
    if (!(sx > 0.05 && sy > 0.05))
      throw new Error('calibration failed — try again');
    return { sx: sx, sy: sy, ox: ax - p.x1 * sx, oy: ay - p.y1 * sy };
  }

  /* -- THE FILM'S OWN FRAME.  The <video> and the film are of this origin, so
     the canvas is not tainted and toDataURL answers.  The film is put at the
     card's moment first -- a card can be about a caption the film is nowhere
     near -- and put back where it stood afterwards, because taking a picture
     must not move the film under the person watching it. -- */
  function filmAt(t) {
    var f = $('#film');
    return new Promise(function (res, rej) {
      if (!f) return rej(new Error('the film is not on this page'));
      if (Math.abs((f.currentTime || 0) - t) < 0.08) return res(f);
      var done = false;
      var there = function () {
        if (done) return;
        done = true;
        clearTimeout(bell);
        res(f);
      };
      // a seek that never answers -- a file still arriving over the network --
      // still gets a frame drawn rather than a button that hangs
      var bell = setTimeout(there, 2500);
      f.addEventListener('seeked', there, { once: true });
      try { f.currentTime = Math.max(0, t); }
      catch (e) { clearTimeout(bell); rej(e); }
    });
  }
  function drawFilm(f) {
    if (!f.videoWidth)
      throw new Error('the film has not loaded far enough yet — try once more');
    var c = document.createElement('canvas');
    c.width = f.videoWidth; c.height = f.videoHeight;
    c.getContext('2d').drawImage(f, 0, 0, c.width, c.height);
    return toJpeg(c);
  }

  /* Why there is no frame to take, or '' when there is -- said under the
     button, as the recording's reason is, because a phone shows no title. */
  function noShot() {
    // A SOUND HAS NO FRAME, and the sheet steps aside (the row is not drawn:
    // style.css) -- this is for anything that asks all the same
    if (CFG.kind === 'audio') return 'this is a sound: there is no picture';
    if (CFG.media) return '';        // the film is here: the canvas reads it
    if (CFG.local)
      return 'the film of this video is not on this machine any more, so there is no frame to take';
    if (!window.isSecureContext)
      return 'capture needs a secure page — open the toolbox over its https address';
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia)
      return 'a YouTube video’s frame is taken from a share of this tab, and this browser ' +
             'shares no tab — no phone browser does. Capture this video’s frame on the computer.';
    return '';
  }
  function paintShot() {
    var why = noShot();
    A.shot.disabled = !!why;
    A.shot.title = why || (CFG.media
      ? 'take the frame the film is showing at this card’s moment, straight from the film'
      : 'share this tab and take the frame the video is showing at this card’s moment');
    A.shotWhy.textContent = why;
    A.shotWhy.hidden = !why;
    // the long explanation of sharing is the tab share's, and belongs to
    // nobody else: a film needs no share and no explaining
    if (CFG.media || why) A.hint.hidden = true;
  }

  // what a capture does with the picture it got, and with the failure it got
  // instead: one pair for both ways of taking one
  function gotShot(data) {
    ankiShot = data; A.img.src = data; A.prev.hidden = false;
    A.hint.hidden = true; A.stat.textContent = '';
    unarm();
    // a jolly card names its picture in a field: the frame goes to the
    // tray now, to have a name to write there
    if (ankiKind === 'jolly') {
      ensureFrame().then(function (rec) {
        if (ankiKind === 'jolly') offerFrame(rec);
      }, function (e) { A.stat.textContent = e.message; });
    }
  }
  function shotFailed(e) {
    if (window.console && console.warn) console.warn('capture:', e);
    A.stat.textContent = 'capture failed — ' + ((e && (e.message || e.name)) || e);
    // the hint tells somebody how to answer the sharing question, which a
    // film never asks
    A.hint.hidden = !!CFG.media;
  }

  $('#ashot').onclick = function () {
    var why = noShot();
    if (why) { A.stat.textContent = why; paintShot(); return; }
    A.stat.textContent = 'capturing…';
    // A FILM ON THIS MACHINE: the short way, on a phone as on the computer
    if (CFG.media) {
      var f = $('#film');
      var stood = f ? (f.currentTime || 0) : 0, wasGoing = !!(f && !f.paused);
      if (wasGoing) f.pause();
      Promise.resolve().then(function () { return filmAt(ankiTime); })
        .then(drawFilm).then(gotShot).catch(shotFailed)
        .then(function () {
          // the film back where it stood, and playing again if it was: a
          // picture taken of a film must not move the film under the person
          if (!f) return;
          if (Math.abs((f.currentTime || 0) - stood) > 0.08) {
            try { f.currentTime = stood; } catch (e) {}
          }
          if (wasGoing) { var again = f.play(); if (again) again.catch(function () {}); }
        });
      return;
    }
    var t0 = ankiTime, rolled = false, wasMuted = true;
    // Promise.resolve() first: ensureCapture must not be able to fail
    // synchronously past the chain (that is how the button once managed
    // to "do nothing" on an insecure origin)
    Promise.resolve().then(ensureCapture).then(function () {
      if (player && ready && player.getPlayerState() !== 1) {
        rolled = true;
        wasMuted = player.isMuted();
        player.mute();
        // roll INTO the moment from ~5s before it: YouTube keeps its
        // overlay up for a full five seconds after playback starts, so
        // it has just faded when the wanted frame goes by
        player.seekTo(Math.max(0, t0 - 5.2), true);
        player.playVideo();
      }
      // hide the dialog so it is not in its own screenshot
      A.box.style.visibility = 'hidden';
      A.back.style.visibility = 'hidden';
      var r = vid.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight)
        throw new Error('scroll the video into view first');
      if (capCropped)                       // the track IS the video
        return waitFrame(t0, rolled).then(framed).then(function () {
          return toJpeg(grabRaw());
        });
      if (capSurface === 'browser')         // own tab, older Chromium
        return waitFrame(t0, rolled).then(framed).then(function () {
          var c = grabRaw();
          var sx = c.width / window.innerWidth,
              sy = c.height / window.innerHeight;
          return cropJpeg(c, r.left * sx, r.top * sy,
                          r.width * sx, r.height * sy);
        });
      // a window or a whole screen -- Firefox always lands here:
      // calibrate off the corner dots, drop them, then shoot
      var p = showMarkers(r);
      return sleep(rolled ? 800 : 400).then(framed).then(function () {
        var map = locateMarkers(grabRaw(), p);
        hideMarkers();
        return waitFrame(t0, rolled).then(function () {
          return cropJpeg(grabRaw(),
            r.left * map.sx + map.ox, r.top * map.sy + map.oy,
            r.width * map.sx, r.height * map.sy);
        });
      });
    }).then(gotShot).catch(shotFailed).then(function () {
      hideMarkers();
      A.box.style.visibility = ''; A.back.style.visibility = '';
      if (rolled) {
        player.pauseVideo(); player.seekTo(t0, true);
        if (!wasMuted) player.unMute();
      }
    });
  };

  // one gatherer for saving AND previewing, so they can never disagree
  function collectCard() {
    return {
      card: {
        video: CFG.id,
        lang: L.code,
        // the language the meaning and the notes are written in, which
        // decides the lang and dir of the gloss side of the built card
        // (youtube/lib/anki_export.py); absent means English there too
        gloss: G.code,
        time: Math.round(ankiTime * 10) / 10,
        fa: A.fa.value.trim(), tr: A.tr.value.trim(),
        kana: L.reading ? A.kana.value.trim() : '',
        en: A.en.value.trim(), context: A.ctx.value.trim(),
        opp: A.opp.value.trim(), opp_tr: A.oppTr.value.trim(),
        opp_kana: L.reading ? A.oppKana.value.trim() : '',
        notes: A.notes.value.trim(),
        kind: ankiKind,
        bidirectional: ankiDir !== 'forward',
        reverse_only: ankiDir === 'reverse',
        tags: A.tags.value.trim().split(/\s+/).filter(Boolean),
        source: {
          label: A.src.value.trim(),
          // A LOCAL VIDEO'S ADDRESS IS THIS PLAYER'S, ALWAYS.  A film on this
          // machine has no address anybody else could open, so the card
          // carries the player's own, which this toolbox can.  CFG.media
          // alone was the wrong question (TO-DO §2.16): a local video whose
          // film has been moved away has no CFG.media either, and every card
          // made from it went to youtube.com/watch?v=<the folder's name> --
          // an address YouTube has never heard of.  What decides is whether
          // the video IS a YouTube video, and CFG.local says so.
          url: (CFG.media || CFG.local)
            ? (location.origin + location.pathname + '#t=' + Math.floor(ankiTime))
            : ('https://www.youtube.com/watch?v=' + CFG.id +
               '&t=' + Math.floor(ankiTime) + 's')
        }
      },
      shot: ankiShot ? {
        side: (document.querySelector('input[name=aside]:checked') || {})
                .value === 'front' ? 'front' : 'back',
        data: ankiShot
      } : null,
      // the recording, by its name in the clip tray: the store copies it
      // into the deck's media/ as it saves the card
      clip: ankiClip ? { side: pickedSide('asndside', 'front'), name: ankiClip.clip.name } : null
    };
  }

  /* -- an exercise deck's card and markdown's: one `:::exercise flashcard`
     block, as the card kit writes it, from the same fields.  The frame is
     sent to the tray first, to be named there; a deck adopts both files from
     the tray as it takes the exercise, and so does a studio document the
     markdown is pasted into. -- */
  // the field a card cannot be without, or null: [element, what to say]
  function cardGap() {
    if (ankiKind === 'jolly') {
      var j = jollyValues();
      if (!j['front-primary'].trim() && !j['front-secondary'].trim())
        return [A.jolly['front-primary'], 'the front is empty: write in one of its two fields'];
      if (!j['back-primary'].trim() && !j['back-secondary'].trim())
        return [A.jolly['back-primary'], 'the back is empty: write in one of its two fields'];
      return null;
    }
    if (!A.fa.value.trim()) return [A.fa, 'the ' + L.name + ' side is empty'];
    if (ankiKind === 'opposites' && !A.opp.value.trim())
      return [A.opp, 'write the opposite in first — that is the answer side'];
    return null;
  }
  // THE CARD AS IT STANDS AT THE PRESS.  Everything a deck's card or
  // markdown is written from is read here, before anything is awaited, so
  // closing the sheet -- or opening it again on another word -- while the
  // frame goes to the tray or the deck is made changes nothing of what was
  // pressed.  Throws what is missing.
  function snapCard() {
    if (!KIT) throw new Error(KIT_GONE);
    if (ankiKind === 'jolly') {
      // a picture and a recording are lines in its fields, where the person
      // can see them, move them and take them out: one not put in yet goes
      // in now (a frame still on its way to the tray, when it comes)
      offerClip();
      if (ankiFrame && ankiFrame.clip && ankiFrame.data === ankiShot) offerFrame(ankiFrame.clip);
    }
    var gap = cardGap();
    if (gap) { gap[0].focus(); throw new Error(gap[1]); }
    return {
      kind: ankiKind, dir: ankiDir, card: collectCard().card, jolly: jollyValues(),
      origin: cardOrigin(),
      clip: ankiClip ? ankiClip.clip : null, clipSide: pickedSide('asndside', 'front'),
      frame: frameFor(ankiShot), frameSide: pickedSide('aside', 'back')
    };
  }
  // Promise of {md, frame: the frame's tray record or null}.  `here()`:
  // whether the sheet the snapshot was taken on is still the one open
  function snapMarkdown(snap, here) {
    var f = snap.frame;
    return (f ? f.ready : Promise.resolve(null)).then(function (frame) {
      var c = snap.card, jolly = snap.kind === 'jolly';
      var card = {
        fa: c.fa, kana: c.kana, tr: c.tr, en: c.en, context: c.context,
        opp: c.opp, opp_kana: c.opp_kana, opp_tr: c.opp_tr, notes: c.notes,
        source: c.source, dir: snap.dir, latin: L.script === 'latin',
        // the fields are a jolly card's whole: the kit would put a picture or
        // a recording it is handed back on a side, line taken out or not
        image: frame && !jolly ? { side: snap.frameSide, path: 'images/' + frame.name } : null,
        audio: snap.clip && !jolly ? { side: snap.clipSide, path: 'audio/' + snap.clip.name } : null
      };
      if (jolly) {
        if (frame && here() && ankiFrame === f && !f.offered) {
          offerFrame(frame);
          snap.jolly = jollyValues();
        }
        card.jolly = snap.jolly;
      }
      return { md: KIT.markdown(card, snap.kind), frame: frame };
    });
  }
  // where a deck's exercise was made: this video, the moment and a link
  // back to it in this player (decks._clean_origin)
  function cardOrigin() {
    return { video: CFG.id, time: Math.round(ankiTime * 10) / 10, label: fmt(ankiTime),
             url: location.pathname + '#t=' + Math.floor(ankiTime), title: vidTitle() };
  }
  // A PRESS IS KEPT, WHATEVER HAPPENS TO THE SHEET WHILE ITS ANSWER IS OUT
  // (the book reader's sheet does the same).  It carries its clip and its
  // frame out of reach of the sheet's cleaning (trayOut, `held`), and what
  // comes back is said on the sheet that asked -- or, when that sheet has
  // been closed since or opened again for another word, in a toast over the
  // page, the only place left to say it.
  function press(clip, frame) {
    var seq = sheetSeq, over = false, target = ankiTarget;
    var here = function () { return ankiOpen && seq === sheetSeq; };
    if (clip) trayOut[clip.name] = (trayOut[clip.name] || 0) + 1;
    if (frame) frame.held++;
    busyFor = seq;
    laterCopied = false;
    return {
      here: here,
      // progress, for the sheet that asked only
      note: function (text) { if (here()) A.stat.textContent = text; },
      // `link`: [its text, its href, what follows it] -- the link is said on
      // the sheet only, after a dash
      say: function (text, bad, link) {
        if (!here()) {
          if (window.Parseh && Parseh.toast)
            Parseh.toast((text + (link && link[2] ? link[2] : '')).replace(/\n+/g, ' — '), !!bad);
          return;
        }
        A.stat.textContent = text + (link ? ' — ' : '');
        if (link) {
          var a = document.createElement('a');
          a.href = link[1]; a.target = '_blank'; a.textContent = link[0];
          A.stat.appendChild(a);
          if (link[2]) A.stat.appendChild(document.createTextNode(link[2]));
        }
      },
      // The answer is in.  A file that went onto a card stays in the tray
      // for good -- for markdown and a deck's card, the files it names (a
      // jolly card's line may have been taken out); `md` null: the clip went
      // as it is (Anki) -- and one that did not leaves it, unless an open
      // sheet still holds it.
      done: function (ok, md) {
        if (over) return;
        over = true;
        if (busyFor === seq) busyFor = 0;
        if (clip) {
          var n = (trayOut[clip.name] || 1) - 1;
          if (n > 0) trayOut[clip.name] = n; else delete trayOut[clip.name];
          if (ok && (md == null || md.indexOf('audio/' + clip.name) >= 0)) trayUsed[clip.name] = true;
          else if (!(here() && ankiClip && ankiClip.clip === clip)) forgetTray(clip.name);
        }
        if (frame) {
          frame.held--;
          var name = frame.clip && frame.clip.name;
          if (name && ok && md != null && md.indexOf('images/' + name) >= 0) trayUsed[name] = true;
          else if (name && ankiFrame !== frame && !frame.held) forgetTray(name);
        }
        // REVIEW LATER hears how it ended: a card saved on any of the three targets
        laterPressDone(seq, target, ok);
      },
      // the sheet closes itself a moment after a save, so the answer can be
      // read -- unless it is another sheet by then, or somebody is still at
      // work on this one (the cut editor is open, or they have typed or
      // clicked in it since)
      closeSoon: function (ms) {
        clearTimeout(closeTimer);
        closeTimer = setTimeout(function () {
          closeTimer = 0;
          if (here() && !cutting) closeAnki();
        }, ms);
      }
    };
  }
  function pressBusy() { return busyFor !== 0 && busyFor === sheetSeq; }
  ['input', 'pointerdown'].forEach(function (t) {
    A.box.addEventListener(t, function () { clearTimeout(closeTimer); });
  });
  // the card, said back: "a vocabulary card for “chilo”"
  function cardSaid(snap) {
    var kind = { vocab: 'a vocabulary card', opposites: 'an opposites card', jolly: 'a jolly card' }[snap.kind];
    var word = snap.kind === 'jolly' ? '' : snap.card.fa;
    return kind + (word ? ' for “' + word + '”' : '');
  }
  // A DUPLICATE IS ASKED ABOUT, NOT REFUSED (as the book reader's sheet asks
  // it).  The deck says it has the card already; the button then reads "add
  // it again", and pressing it adds a second one.  Any change to the card --
  // a field, the deck, the type, the recording or the frame -- first asks
  // again.
  var dupArmed = false;
  function unarm() {
    if (!dupArmed) return;
    dupArmed = false;
    A.saveLab.textContent = SAVE_LABEL[ankiTarget];
  }
  A.box.addEventListener('input', unarm);
  A.box.addEventListener('change', unarm);
  ['#akvocab', '#akopp', '#akjolly', '#asnddel', '#ashotdel'].forEach(function (s) {
    $(s).addEventListener('click', unarm);
  });
  function addToDeck() {
    if (pressBusy()) return;
    if (!KIT) { A.stat.textContent = KIT_GONE; return; }
    var snap;
    try { snap = snapCard(); } catch (e) { A.stat.textContent = e.message; return; }
    var pick = A.deck.value, name = A.deckNew.value.trim();
    if (!pick && !name) {
      A.stat.textContent = 'name the new deck first';
      A.deckNew.focus(); return;
    }
    var picked = pick ? (exDecks.filter(function (d) { return d.path === pick; })[0] || { path: pick, name: pick }) : null;
    var force = dupArmed, card = cardSaid(snap);
    var p = press(snap.clip, snap.frame);
    p.note('adding…');
    var md, frame, deck;
    snapMarkdown(snap, p.here).then(function (r) {
      md = r.md; frame = r.frame;
      if (picked) return picked;
      // "+ new deck…": made now, and picked, so a second try adds to it
      // rather than making another
      p.note('making the deck…');
      return KIT.newDeck(name, L.code).then(function (d) {
        localStorage.setItem('yt_exdeck', d.path);
        deckPicked = false;
        if (A.deckNew.value.trim() === name) A.deckNew.value = '';
        if (newDeckNames.deck === name) newDeckNames.deck = '';
        exDecks = exDecks.concat([d]);
        if (p.here() && ankiTarget === 'deck') exDeckOptions(exDecks);
        return d;
      });
    }).then(function (d) {
      deck = d;
      p.note('adding…');
      return KIT.add(d.path, md, snap.origin, force);
    }).then(function (res) {
      if (!res.ok) {
        p.done(false);
        if (!p.here()) p.say(res.error + (res.conflict === 'duplicate' ? ' — nothing was added' : ''), true);
        else if (res.conflict === 'duplicate' && !force) {
          dupArmed = true;
          A.saveLab.textContent = 'add it again';
          A.stat.textContent = res.error + ' — press “add it again” to add a second one';
        } else {
          unarm();
          A.stat.textContent = res.error;
        }
        return;
      }
      p.done(true, md);
      localStorage.setItem('yt_exdeck', deck.path);
      deckPicked = false;
      // what went in: the card, and the files the deck took with it.  The
      // sheet stays, with a link to the deck and the deck's warnings
      var media = carried(md, 'its', snap.clip, frame), gone = leftOut(md, snap.clip, frame);
      var warnings = res.warnings || [];
      p.say('added ✓ — ' + card + (media.length ? ', with ' + media.join(' and ') : '') +
            (res.items && res.items.length > 1 ? ' (two linked cards, one each way)' : '') +
            ', to “' + deck.name + '”' + (gone ? ' — ' + gone : ''), warnings.length > 0,
            ['open the deck', '/exercises/deck/' + deck.path + '/', warnings.length ? '\n' + warnings.join('\n') : '']);
      if (p.here()) {
        unarm();
        if (ankiTarget === 'deck') loadDecks(true);   // its count
      }
    }).catch(function (e) {
      p.done(false);
      p.say(e.message, true);
    });
  }
  function copyMarkdown() {
    if (pressBusy()) return;
    if (!KIT) { A.stat.textContent = KIT_GONE; return; }
    var snap;
    try { snap = snapCard(); } catch (e) { A.stat.textContent = e.message; return; }
    var card = cardSaid(snap);
    var p = press(snap.clip, snap.frame);
    p.note('writing…');
    A.mdRow.hidden = true;
    var md, frame;
    snapMarkdown(snap, p.here).then(function (r) {
      md = r.md; frame = r.frame;
      return KIT.copy(md);
    }).then(function (ok) {
      // (review later: a card copied is a card saved, one left to copy by hand is not)
      laterCopied = ok === true;
      // what the markdown names in the tray, which comes along when pasted
      var media = carried(md, 'the', snap.clip, frame), gone = leftOut(md, snap.clip, frame);
      if (ok) {
        p.done(true, md);
        p.say('copied ✓ — ' + card + '. Paste it into a studio document or a deck’s “Add exercise”' +
          (media.length ? ': ' + media.join(' and ') + (media.length > 1 ? ' come' : ' comes') +
                          ' along from the clip tray when it is pasted there' : '') + (gone ? ' — ' + gone : ''));
        return;
      }
      if (!p.here()) {
        p.done(false);
        p.say('not copied — the browser would not put the card on the clipboard', true);
        return;
      }
      // there to copy by hand, so its files are kept for it
      p.done(true, md);
      A.mdOut.value = md;
      A.mdRow.hidden = false;
      A.mdOut.focus(); A.mdOut.select();
      A.stat.textContent = 'not copied — the browser would not put it on the clipboard: the markdown is below, to copy by hand' +
                           (gone ? ' — ' + gone : '');
    }).catch(function (e) {
      p.done(false);
      p.say(e.message, true);
    });
  }

  function saveCard() {
    if (ankiTarget === 'deck') return addToDeck();
    if (ankiTarget === 'md') return copyMarkdown();
    // deckLang is the language of the deck the user is LOOKING at; the card
    // goes to the deck of its own language whatever that is, and the answer
    // says so when the two differ
    var deckName, deckLang = L.code;
    if (A.deck.value === '') {
      deckName = A.deckNew.value.trim();
      if (!deckName) {
        A.stat.textContent = 'name the new deck first';
        A.deckNew.focus(); return;
      }
    } else {
      var key = A.deck.value;
      deckName = key;
      decksCache.forEach(function (d) {
        if (d.folder + '/' + d.slug === key) {
          deckName = d.name; deckLang = d.lang;
        }
      });
    }
    if (!A.fa.value.trim()) {
      A.stat.textContent = 'the ' + L.name + ' side is empty';
      A.fa.focus(); return;
    }
    if (ankiKind === 'opposites' && !A.opp.value.trim()) {
      A.stat.textContent = 'write the opposite in first — that is the answer side';
      A.opp.focus(); return;
    }
    if (pressBusy()) return;
    var c = collectCard();
    var body = { deck: deckName, deck_lang: deckLang, card: c.card };
    if (c.shot) body.shot = c.shot;
    if (c.clip) body.clip = c.clip;
    var p = press(c.clip ? ankiClip.clip : null, null);
    p.note('saving…');
    fetch('/anki/cards', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'save failed');
      p.done(true, null);
      localStorage.setItem('yt_deck', res.deck.folder + '/' + res.deck.slug);
      deckPicked = false;
      p.say('saved ✓ — “' + res.deck.name + '” (' +
        res.deck.language + ') now has ' + res.deck.cards + ' card' +
        (res.deck.cards === 1 ? '' : 's') +
        (res.refiled ? ' — ' + res.refiled.note : ''));
      p.closeSoon(res.refiled ? 2200 : 900);
    }).catch(function (e) {
      p.done(false);
      p.say(e.message, true);
    });
  }
  $('#asave').onclick = saveCard;

  /* ---------- the video-info sheet ------------------------------------
     Title, title_native, channel, level, blurb: video.json's own fields,
     not a chunk's -- fixed here rather than by hand-editing the file when
     api_add's YouTube lookup (oembed, or the LLM's answer) got the title
     or the channel wrong, which is the concrete case this exists for.
     Opened and saved the way the anki dashboard is (Esc and the backdrop
     close it, Ctrl+Enter saves), against /youtube/api/editmeta.  A save
     reloads the page rather than patching the DOM in place: the title and
     the channel are shown in three places here (the tab title, the header,
     the channel link's own href and label) and CFG.editable besides, and a
     reload is one line that can never leave one of them behind. */
  var VM = {
    back: $('#vmback'), box: $('#vmbox'),
    title: $('#vmtitle'), titleNative: $('#vmtitlenative'),
    channel: $('#vmchannel'), level: $('#vmlevel'), blurb: $('#vmblurb'),
    reorders: $('#vmreorders'), stat: $('#vmstat')
  };
  // "reorders" (kanbun) only means something where chunks have words
  $('#vmreordersrow').hidden = !L.words;
  var vmOpen = false, vmWasPlaying = false, vmWas = {};
  function openVidMeta() {
    var m = CFG.editable || {};
    vmWas = { title: m.title || '', title_native: m.title_native || '',
              channel: m.channel || '', level: m.level || '', blurb: m.blurb || '',
              reorders: !!m.reorders };
    VM.title.value = vmWas.title; VM.titleNative.value = vmWas.title_native;
    VM.channel.value = vmWas.channel; VM.level.value = vmWas.level;
    VM.blurb.value = vmWas.blurb; VM.reorders.checked = vmWas.reorders;
    VM.stat.textContent = ''; VM.stat.classList.remove('bad');
    if (player && ready && player.getPlayerState &&
        player.getPlayerState() === 1) {
      vmWasPlaying = true; player.pauseVideo();
    } else vmWasPlaying = false;
    VM.back.hidden = false; VM.box.hidden = false; vmOpen = true;
    VM.title.focus();
  }
  function closeVidMeta() {
    vmOpen = false; VM.back.hidden = true; VM.box.hidden = true;
    if (vmWasPlaying && player && ready) player.playVideo();
    vmWasPlaying = false;
  }
  /* THE TIMINGS: where each caption starts, moved over a picture of the
     sound.  The add page's transcript editor does this BEFORE a video is
     added and writes nothing to disk; this is the one door that does it
     afterwards, and youtube/lib/captimes.py says at length why moving a
     start is allowed where moving a caption's words is not.

     A caption has a start and nothing else -- the one before it runs until
     that start -- so there is one number per boundary and nothing to split,
     which is what `kind: point` means to the timeline.

     THE PICTURE OF THE SOUND, three ways.  A film on this machine has one
     for nothing: the server reads it with ffmpeg, window by window, as it
     does for a book (/youtube/api/peaks).  A YouTube video has no file
     anybody here can read, so it has no waveform unless somebody asks for
     one, and asking means recording the whole video as this tab plays it --
     which is why it is offered and never assumed.  What is kept from that
     recording is the SHAPE and not the sound: peaks every 50 ms, a few
     hundred kilobytes for an hour, written beside the video as
     waveform.json and read back by every later visit.  Nothing needs the
     audio itself, because the player can play any second of the video on
     its own. */
  var capWave = null;          // {rate, peaks} for a YouTube video, if any
  var capPlayTimer = 0, capPlayTo = null;
  function capSay(text, bad) {
    if (window.Parseh && Parseh.toast) Parseh.toast(text, !!bad);
  }

  function capStop() {
    clearInterval(capPlayTimer);
    capPlayTimer = 0; capPlayTo = null;
    try { if (player && player.pauseVideo) player.pauseVideo(); } catch (e) {}
  }
  function capPlay(a, b) {
    if (!player || !ready) return;
    clearInterval(capPlayTimer);
    capPlayTo = b;
    try { player.seekTo(Math.max(0, a), true); player.playVideo(); } catch (e) { return; }
    // the six methods are all there is: no event says "you have reached b",
    // so the clock is read often enough that the overshoot is not heard
    capPlayTimer = setInterval(function () {
      if (capPlayTo == null) return;
      var t = player.getCurrentTime ? player.getCurrentTime() : 0;
      if (t >= capPlayTo - 0.02) capStop();
    }, 25);
  }
  function capNow() {
    if (!player || !ready || !player.getCurrentTime) return null;
    var t = player.getCurrentTime();
    return isFinite(t) ? t : null;
  }
  // a window of the waveform recorded from the tab, cut and thinned to the
  // buckets the strip asked for -- the same answer shape the server gives
  function capWaveWindow(a, b, buckets) {
    if (!capWave || !capWave.peaks || !capWave.peaks.length) return null;
    var rate = capWave.rate || 20, src = capWave.peaks;
    var out = [], top = 0;
    for (var i = 0; i < buckets; i++) {
      var t0 = a + (b - a) * i / buckets, t1 = a + (b - a) * (i + 1) / buckets;
      var k0 = Math.floor(t0 * rate), k1 = Math.max(k0 + 1, Math.ceil(t1 * rate));
      var v = 0;
      for (var k = k0; k < k1 && k < src.length; k++) if (src[k] > v) v = src[k];
      out.push(v);
      if (v > top) top = v;
    }
    // the server normalises each window to its own loudest; so does this
    if (top > 0) for (var j = 0; j < out.length; j++) out[j] = Math.round(out[j] / top * 1000) / 1000;
    return {ok: true, peaks: out, start: a, end: b};
  }
  function capPeaks(a, b, buckets) {
    if (CFG.media)
      return fetch('/youtube/api/peaks', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({video: CFG.id, start: a, end: b, buckets: buckets})})
        .then(function (r) { return r.json(); })
        .then(function (j) { return j && j.ok ? j : null; })
        .catch(function () { return null; });
    return Promise.resolve(capWaveWindow(a, b, buckets));
  }
  /* "ESTIMATE THE REST" BY THE SOUND (lib/timeline.js): the captions after
     the line in hand, laid through a picture of the sound by the server
     (lib/wavealign.py).  A film on this machine is read there with ffmpeg,
     as its strip is.  A YouTube video's only picture is the one recorded
     from this tab, which the page already holds: the numbers for the
     stretch asked about are sent as they are -- raw, at their own rate, with
     the time of the first -- so the server needs nothing it does not have.
     With no picture there is nothing to send, and the sheet has already
     greyed the choice out; the refusal here is for the hand that got past.
     A picture that ends before the stretch begins (captions after the
     length the recording saw) is said the same way as the server says it,
     without asking.  And the request has a deadline, as the reader's has
     (tex2html.py): two minutes and a second for every minute of sound. */
  function capEstimate(req) {
    var body = {video: CFG.id, start: req.start, end: req.end, texts: req.texts,
                kind: req.kind || 'point'};
    if (!CFG.media) {
      if (!capWave || !capWave.peaks || !capWave.peaks.length)
        return Promise.reject(new Error('draw the sound first: there is no picture of ' +
                                        'this video’s sound yet to estimate by'));
      var rate = capWave.rate || 20;
      var k0 = Math.max(0, Math.floor(req.start * rate));
      if (k0 >= capWave.peaks.length)
        return Promise.reject(new Error('the picture of this video’s sound ends before ' +
                                        'this stretch begins, so it cannot be estimated by ' +
                                        'the sound: estimate it by the text'));
      var k1 = Math.min(capWave.peaks.length, Math.ceil(req.end * rate) + 1);
      body.wave = {rate: rate, start: k0 / rate, peaks: capWave.peaks.slice(k0, k1)};
    }
    var wait = 120000 + Math.max(0, req.end - req.start) * 1000 / 60;
    var ctl = new AbortController(), timer = setTimeout(function () { ctl.abort(); }, wait);
    function failed(e) {
      throw new Error(ctl.signal.aborted
        ? 'the server gave no answer in ' + Math.round(wait / 60000) +
          ' minutes, so the estimate was given up — nothing was estimated'
        : 'the server did not answer (' + ((e && e.message) || e) +
          ') — nothing was estimated');
    }
    return fetch('/youtube/api/estimate', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body), signal: ctl.signal
    }).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (j) {
        if (ctl.signal.aborted) failed();
        if (!r.ok || !j || !j.ok)
          throw new Error((j && j.error) || 'the sound could not be read to estimate from');
        return j;
      });
    }, failed).finally(function () { clearTimeout(timer); });
  }

  /* RECORDING THE SHAPE OF A YOUTUBE VIDEO'S SOUND.

     What is kept is peaks and not audio: one number every 50 ms, which is
     finer than the smallest step the editor takes (0.1 s) and is a few
     hundred kilobytes for an hour where the sound itself would be hundreds
     of megabytes -- too big for the upload ceiling, too big to hold in the
     page, and a copy of somebody else's recording besides.  Nothing here
     needs the audio: the player can play any second of the video itself.

     The recording itself -- the share, the Analyser, the clock loop that files
     each number under the VIDEO'S OWN clock and not under how long the
     recording has been running -- is youtube/lib/tabcapture.js, which the add
     page records from as well.  What stays here is what only this page does
     with it: the words the sheet shows, and keeping the shape beside the video. */
  function capRecordWave(onTick) {
    if (!player || !ready) return Promise.reject(new Error('the player has not loaded'));
    var why = KIT && KIT.tabProblem ? KIT.tabProblem() : '';
    if (why) return Promise.reject(new Error(why));
    if (!TC) return Promise.reject(new Error(TC_GONE));
    return TC.record({
      player: player, wave: true, keepShare: true,
      onStart: function () {
        if (onTick) onTick(0, 'listening… the video plays once, the whole way through');
      },
      onProgress: function (t, dur) { if (onTick) onTick(t / dur); }
    }).promise.then(function (w) {
      if (!w || !w.peaks) return w;
      if (onTick) onTick(1, 'keeping it…');
      return fetch('/youtube/api/waveform', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({video: CFG.id, rate: w.rate, peaks: w.peaks})
      }).then(function (r) {
        return r.json().catch(function () { return null; }).then(function (j) {
          // kept or not, the page has the shape and can draw it now
          capWave = {rate: w.rate, peaks: w.peaks};
          if (!r.ok || !j || !j.ok)
            capSay((j && j.error) || 'the waveform was drawn but could not be kept', true);
          return w;
        });
      }).catch(function () {
        capWave = {rate: w.rate, peaks: w.peaks};
        return w;
      });
    });
  }

  function capWhyNoWave() {
    if (CFG.media) return '';
    if (capWave) return '';
    if (!KIT) return KIT_GONE;
    var why = KIT.tabProblem ? KIT.tabProblem() : 'the card kit cannot record a tab';
    if (why) return 'a YouTube video’s sound reaches no script here, so its waveform is '
      + 'a recording of this tab — and ' + why;
    return '';
  }

  function openCapTimes() {
    if (!window.ParsehTimeline) {
      capSay('the timeline (lib/timeline.js) did not load: reload the page', true);
      return;
    }
    if (!segs.length) { capSay('this video has no captions to time', true); return; }
    if (!player || !ready) { capSay('the player has not loaded yet', true); return; }
    // WAIT FOR WHAT IS ALREADY ON THE SHELF.  waveform.json is fetched when
    // the page loads, and a hand quicker than that fetch would be offered
    // "draw the sound" for a video that has been drawn already -- and an
    // hour of recording is not a thing to offer twice by accident.
    Promise.resolve(capWaveReady).catch(function () {}).then(reallyOpenCapTimes);
  }
  function reallyOpenCapTimes() {
    if (!segs.length || !player || !ready) return;
    var was = segs.map(function (sg) { return +sg.start || 0; });
    var marks = segs.map(function (sg, i) {
      return {key: String(i), label: fmt(sg.start),
              text: sg.text || (sg.chunks || []).map(function (c) { return c.fa || ''; }).join(' '),
              t0: +sg.start || 0};
    });
    var dur = 0;
    try { dur = player.getDuration ? player.getDuration() : 0; } catch (e) {}
    // OPENS AT THE CAPTION THE VIEWER IS AT: the one under the playhead,
    // playing or paused -- which is what is heard when the alignment is
    // noticed to be lost, and the first caption for a video not yet begun.
    // Read before capStop, though a pause moves nothing.
    var now = capNow(), at = now == null ? 0 : Math.max(0, findSeg(now));
    capStop();
    ParsehTimeline.open({
      title: 'the timings — ' + (CFG.title || CFG.id),
      kind: 'point',
      marks: marks,
      at: at,
      duration: isFinite(dur) ? dur : 0,
      dir: L.dir, lang: L.code,
      peaks: capPeaks,
      estimate: capEstimate,
      play: capPlay, stop: capStop, now: capNow,
      // a film on this machine has its waveform for nothing, and one already
      // recorded is on disk: the offer is for the case that has neither
      wave: (CFG.media || capWave) ? null
            : {why: capWhyNoWave(), run: capRecordWave},
      save: function (changed) {
        var moves = changed.map(function (c) {
          var i = +c.key;
          return {i: i, from: was[i], to: c.t0};
        });
        return fetch('/youtube/api/times', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({video: CFG.id, moves: moves})
        }).then(function (r) {
          return r.json().catch(function () { return null; }).then(function (j) {
            if (!r.ok || !j || !j.ok)
              throw new Error((j && j.error) || 'the timings could not be saved');
            return j;
          });
        });
      }
    }).then(function (saved) {
      capStop();
      if (!saved || !saved.length) return;
      // the file on disk has moved; so must the page, without a reload
      saved.forEach(function (c) {
        var i = +c.key;
        if (segs[i]) segs[i].start = c.t0;
      });
      render(); loadNotes();
      capSay(saved.length + (saved.length === 1 ? ' caption' : ' captions') + ' moved');
    });
  }

  // a waveform recorded on an earlier visit, beside the video.  A film on
  // this machine never needs one: the server reads the film itself.
  var capWaveReady = null;
  function loadCapWave() {
    if (CFG.media || !CFG.ann) { capWaveReady = Promise.resolve(); paintCapTimes(); return; }
    capWaveReady = fetch(String(CFG.ann).replace(/annotations\.json$/, 'waveform.json'),
          {cache: 'no-store'})
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.peaks && j.peaks.length) capWave = {rate: +j.rate || 20, peaks: j.peaks};
        paintCapTimes();
      })
      .catch(function () { paintCapTimes(); });
  }

  function paintCapTimes() {
    var b = $('#captimes');
    if (!b) return;
    var why = !segs.length ? 'this video has no captions to time'
            : !window.ParsehTimeline ? 'the timeline (lib/timeline.js) did not load: reload the page'
            : '';
    b.disabled = !!why;
    b.title = why || ('move where each caption starts, by ear, over a picture of the sound: '
      + 'it opens at the caption you are on'
      + (capWhyNoWave() ? ' (no waveform here: ' + capWhyNoWave() + ')' : ''));
  }
  $('#captimes').onclick = openCapTimes;

  $('#vidinfo').onclick = openVidMeta;
  $('#vmcancel').onclick = closeVidMeta;
  VM.back.addEventListener('click', closeVidMeta);
  document.addEventListener('keydown', function (e) {
    if (!vmOpen) return;
    if (e.key === 'Escape') { e.preventDefault(); closeVidMeta(); }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); saveVidMeta();
    }
  });
  function saveVidMeta() {
    var fields = {};
    if (VM.title.value !== vmWas.title) fields.title = VM.title.value;
    if (VM.titleNative.value !== vmWas.title_native) fields.title_native = VM.titleNative.value;
    if (VM.channel.value !== vmWas.channel) fields.channel = VM.channel.value;
    if (VM.level.value !== vmWas.level) fields.level = VM.level.value;
    if (VM.blurb.value !== vmWas.blurb) fields.blurb = VM.blurb.value;
    if (VM.reorders.checked !== vmWas.reorders) fields.reorders = VM.reorders.checked;
    if (!Object.keys(fields).length) {
      VM.stat.textContent = 'nothing to change'; VM.stat.classList.remove('bad');
      return;
    }
    VM.stat.textContent = 'saving…'; VM.stat.classList.remove('bad');
    fetch('/youtube/api/editmeta', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video: CFG.id, fields: fields }) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.ok) { VM.stat.textContent = j.error || 'the edit was refused';
          VM.stat.classList.add('bad'); return; }
        VM.stat.textContent = 'saved ✓';
        setTimeout(function () { location.reload(); }, 500);
      }).catch(function (e) {
        VM.stat.textContent = 'the server did not answer (' + (e.message || e) +
          ') — nothing was written';
        VM.stat.classList.add('bad');
      });
  }
  $('#vmsave').onclick = saveVidMeta;

  /* ---------------- glossing a stretch with an LLM ----------------
     A run of captions, picked on the transcript, sent to an LLM as a prompt
     and filled from its answer -- the book reader's region sheet, for a
     video.  Everything that matters is decided by the server
     (lib/glossregion.py): which chunks the prompt asks to be glossed, and,
     when the answer comes back, which of them it may write.  The page only
     says which captions and how, and shows what the server did.

     PICKED ON THE TRANSCRIPT ITSELF.  While the panel is open a click on a
     caption -- its time, its text, any phrase of it -- picks it instead of
     playing it: the first sets "from", the second "to" (the two swapped if
     the second is the earlier), and a third starts again.  The run is lit on
     the transcript and each end is named in its slot by its number and its
     time.  The number is the caption's place among ALL the captions, plain
     ones included -- the numbering /youtube/api/edit and the editor's
     "segment N" use, and the one the server's own region words print -- so
     a plain caption can be an end, and inside the run it is sent as context
     and never glossed.  With "to" not picked the stretch is the one caption.

     THE TWO BOXES ARE READ WHEN THEY ARE USED: copying sends their state to
     make the prompt, and filling sends their state AT THAT MOMENT -- the
     state when you paste decides what may be replaced, whatever it was when
     the prompt was made (the owner's rule, D12).  A re-gloss that would
     replace a gloss writes nothing the first time: the button asks again,
     armed, and a second press within four seconds (the reader's two-press
     arm) says yes.

     WHAT THE ANSWER WROTE IS DRAWN AGAIN IN PLACE.  The server hands back
     every caption it wrote to, whole; each replaces its entry in `segs` and
     its line is swapped for a new one where it stands (redrawSeg) -- the
     video, the scroll, the on-air line, the other captions, the answer box
     and the undo memory all stay as they were, which a reload would lose. */
  var RG = {
    panel: $('#rgpanel'), btn: $('#rgn'), close: $('#rgclose'),
    from: $('#rgfrom'), to: $('#rgto'),
    regloss: $('#rgregloss'), perfield: $('#rgperfield'),
    sum: $('#rgsum'),
    ans: $('#rgans'), fill: $('#rgfill'), report: $('#rgreport')
  };
  var FILL_LABEL = 'fill from the answer', RG_ARM_MS = 4000;
  var rgOn = false, rgFrom = null, rgTo = null, rgWasPlaying = false;
  var rgBusy = false, rgArmed = false, rgArmTimer = 0;
  RG.panel.setAttribute('tabindex', '-1');     // focusable as a whole, on opening

  /* THE ROW OF CONTROLS AROUND THE PROMPT (lib/llmrow.js): copy the prompt, its
     size said before the copy, and what to do next.  It is asked for the
     prompt as soon as a stretch is picked and holds it, so the press copies
     inside the click; every road that changes what the prompt would say (a
     pick, a box, a write to the video, the panel opening or closing) drops it
     -- see rgForget.  Without the row's script there is no copy button, and
     the panel says so; the rest of the player goes on. */
  var rgMade = [];             // the server's account of each prompt made lately: {j, text}
  var rgByHand = false;        // the summary points at the box under the row
  var rgRow = window.ParsehLLMRow ? ParsehLLMRow.mount($('#rgrow'), {
    surface: 'video-region',
    // THE OPTIONS OF THE PROMPT (the scheme of the transliteration, the short vowels) are asked of the
    // server for this video's language, and start from what the video's own record says of them; a
    // choice made against that record may be made the video's (through the door the video's info sheet uses)
    lang: L.code, video: CFG.id,
    // (THE PROMPT MENU -- the person's own prompts for a stretch of a video, in this video's language -- is the
    // row's too, and what it chooses goes into the request as `prompt`: rgText)
    setFact: function (name, value) {
      var fields = {}; fields[name] = value;
      return fetch('/youtube/api/editmeta', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video: CFG.id, fields: fields }) })
        .then(function (r) { return r.json(); })
        .then(function (j) { if (!j.ok) throw new Error(j.error || 'the edit was refused'); });
    },
    ids: {copy: 'rgcopy', size: 'rgsize', say: 'rgcopysay', hand: 'rgprompt', handRow: 'rgpromptrow'},
    remind: 'paste it into the LLM, then paste its answer into the box below.',
    getText: rgText, onCopied: rgCopied,
    // a press: what was said of the last one is not about this one, and a
    // confirmation to replace glosses was about what was counted
    onPress: function () { rgDisarm(); rgSay(RG.sum, ''); },
    onError: function (e, which, press) { if (press) rgSay(RG.sum, e.message, true); },
    measure: function () { return rgOn && rgFrom !== null && !mobileMode(); }
  }) : (function () {
    $('#rgrow').textContent = 'the prompt helper could not be loaded';
    var no = function () {};
    return {update: no, forget: no, invalidate: no, disable: no, enable: no};
  }());

  // picking happens only with the panel open, and never in the phone's
  // mode, whose page writes nothing (lib/mobile.css hides the panel there)
  function rgPicking() { return rgOn && !mobileMode(); }
  // the stretch as [first, last], or null before a caption is picked
  function rgRange() {
    if (rgFrom === null) return null;
    var b = rgTo === null ? rgFrom : rgTo;
    return rgFrom <= b ? [rgFrom, b] : [b, rgFrom];
  }
  // a caption as a slot names it: "caption 12, 1:02", as the server does
  function rgName(i) {
    var sg = segs[i];
    return 'caption ' + i + ', ' + fmt(sg ? +sg.start || 0 : 0);
  }
  // the run on the transcript, the two slots, and the two buttons
  function rgPaint() {
    var r = rgPicking() ? rgRange() : null;
    els.forEach(function (el, k) {
      el.classList.toggle('rgpick', !!r && k >= r[0] && k <= r[1]);
    });
    document.body.classList.toggle('rgpicking', rgPicking());
    [[RG.from, rgFrom], [RG.to, rgTo]].forEach(function (p) {
      var set = p[1] !== null && p[1] < segs.length;
      p[0].textContent = set ? rgName(p[1]) : 'click a caption';
      p[0].classList.toggle('set', set);
    });
    var none = rgFrom === null;
    RG.fill.disabled = none || rgBusy;
    RG.fill.title = none ? 'click a caption first: the stretch starts there' : '';
    if (none || rgBusy)
      rgRow.disable(none ? 'click a caption first: the stretch starts there' : 'working on it');
    else rgRow.enable('copy the prompt for ' + rgWords() + ', to paste into an LLM');
    if (!none) {
      RG.fill.title = rgArmed ? 'press again to replace them'
        : "write the LLM's answer into " + rgWords() + ': only what the server lets through ' +
          'is written, and the report says what was kept and dropped';
    }
  }
  function rgWords() {
    var r = rgRange();
    return r[0] === r[1] ? 'caption ' + r[0] : 'captions ' + r[0] + '–' + r[1];
  }
  // A CLICK ON A CAPTION, while picking: true when it was taken as a pick
  // (and so must not seek), false when the page is not picking
  function rgPickAt(i) {
    if (!rgPicking() || isNaN(i) || i < 0 || i >= segs.length) return false;
    if (rgFrom === null || rgTo !== null) { rgFrom = i; rgTo = null; }
    else if (i < rgFrom) { rgTo = rgFrom; rgFrom = i; }
    else rgTo = i;
    // what was said about the last stretch is not about this one
    rgDisarm();
    rgSay(RG.sum, '');
    rgRow.invalidate();
    rgPaint();
    return true;
  }
  function rgSay(el, text, bad) {
    el.textContent = '';
    if (!text) return;
    var s = document.createElement('span');
    s.textContent = text;
    if (bad) s.className = 'bad';
    el.appendChild(s);
  }
  /* A PROMPT THE ROW HOLDS -- and one the clipboard refused, shown in the box
     under "copy the prompt" to be copied by hand -- is a picture of the files
     AT THE MOMENT IT WAS MADE: every gloss the stretch had then goes out in it
     as context the LLM is told to leave alone, and an LLM echoes such context
     back.  So it must never outlive those files: kept past a ✎ delete, it sent
     the deleted gloss out again, the answer echoed it, the server found the
     chunk blank at paste time and filled it with the very gloss just taken
     off -- the delete undone without a word, the report saying only "filled
     1".  On an iPad (Safari refuses a copy made after the round trip) the box
     is how a prompt arrived, so the fault was the ordinary road there.  The
     reader lets its own go the same way (rgDrop, lib/tex2html.py); here it
     goes when the panel opens or closes, when either box changes what the
     prompt would say, after a fill that wrote, and after every write through
     post() -- the ✎ form's save, delete and undo, a colour -- or the divide
     sheet (dvDone).  The row then asks for the prompt again, if a stretch is
     picked and the panel is open.  The summary goes with it only when it was
     the line pointing at the box -- a prompt that did reach the clipboard is
     out of this page's hands, and its summary stays. */
  function rgForget() {
    // called from inside the writes' success paths, where a throw would be
    // caught and shown as a refusal of an edit that was in fact written
    if (!RG || !rgRow) return;
    rgMade = [];
    rgRow.invalidate();
    if (!rgByHand) return;
    rgByHand = false;
    rgSay(RG.sum, '');
  }
  function rgOpen() {
    if (rgOn) return;
    rgForget();
    rgOn = true;
    RG.panel.hidden = false;
    RG.btn.classList.add('on'); RG.btn.setAttribute('aria-expanded', 'true');
    // the transcript must hold still under the picking hand: a playing video
    // scrolls it to the line being spoken (the editor pauses for the same
    // reason), and it plays on when the panel is closed
    if (player && ready && player.getPlayerState &&
        player.getPlayerState() === 1) {
      rgWasPlaying = true; player.pauseVideo();
    } else rgWasPlaying = false;
    // A VIDEO ONLY HELD BY A HOVER is a playing video all the same: the
    // hover-pause resumes it a moment after the cloud closes, which would be
    // under the open panel (a click on this button is a pointer that has
    // just left a phrase, or a finger whose cloud is still open).  The panel
    // takes the resume over and plays it when it closes.
    if (wasPlaying) {
      clearTimeout(resumeTimer); wasPlaying = false; rgWasPlaying = true;
    }
    rgPaint();
    rgRow.invalidate();
    try { RG.panel.focus({ preventScroll: true }); } catch (e) { RG.panel.focus(); }
  }
  function rgShut() {
    if (!rgOn) return;
    rgOn = false;
    RG.panel.hidden = true;
    RG.btn.classList.remove('on'); RG.btn.setAttribute('aria-expanded', 'false');
    rgDisarm();
    // with the panel shut, a phrase may be saved, deleted, cut or joined
    // unseen by it: a prompt kept for the copy by hand goes (rgForget)
    rgForget();
    // the picks are kept, unlit, for the next time the panel is opened
    rgPaint();
    if (RG.panel.contains(document.activeElement) || document.activeElement === RG.panel)
      RG.btn.focus();
    // NEVER UNDER THE ✎ FORM.  The panel has no backdrop, so the form can be
    // opened while it is open and closed after it, or before: whichever
    // closes first hands the video it paused to the one still open, and the
    // last to close plays it.  Played here, it would scroll the phrase being
    // typed into out from under the form (closeEditor does the same the
    // other way round)
    if (rgWasPlaying && player && ready) {
      if (editing) editWasPlaying = true; else player.playVideo();
    }
    rgWasPlaying = false;
  }
  function rgArm() {
    rgArmed = true;
    clearTimeout(rgArmTimer);
    rgArmTimer = setTimeout(rgDisarm, RG_ARM_MS);
    RG.fill.classList.add('armed');
  }
  function rgDisarm() {
    rgArmed = false;
    clearTimeout(rgArmTimer); rgArmTimer = 0;
    RG.fill.classList.remove('armed');
    RG.fill.textContent = FILL_LABEL;
    if (rgFrom !== null) rgPaint();
  }
  function rgBody(extra) {
    var r = rgRange(), b = {
      video: CFG.id, from: r[0], to: r[1],
      regloss: !!RG.regloss.checked, perfield: !!RG.perfield.checked
    };
    Object.keys(extra || {}).forEach(function (k) { b[k] = extra[k]; });
    return b;
  }
  // THE SHORT VOWELS the row shows now go with the answer as they went with the prompt: whether the
  // answer's `fa` may be written is the server's to decide, from this word and the language's record
  function rgMarks(body) {
    var o = rgRow.options ? rgRow.options() : {};
    if (o.marks) body.marks = o.marks;
    return body;
  }
  // through the ask that cannot hang (lib/parseh.js): a computer gone quiet
  // is said at once rather than waited on for ever, and a write is not even
  // tried while the page knows it is away
  function rgAsk(what, body) {
    return pAsk('/youtube/api/region/' + what, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () {
        return { ok: false, error: 'the server answered ' + r.status + ' with no sentence' };
      });
    });
  }
  function rgWhy(e, writing) {
    if (e && e.away)
      return 'the computer does not answer — ' + (writing ? 'nothing was written' : 'no prompt was made');
    return (e && e.message) || String(e);
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
  // a note of the server's, which is a sentence, or a {where, note} about a chunk
  function rgNote(n) {
    if (!n) return '';
    if (typeof n === 'string') return n;
    return (n.where ? n.where + ': ' : '') + (n.note || n.why || '');
  }

  /* COPY THE PROMPT: the server makes it, for the stretch and the two boxes
     as they are now, and the row puts it on the clipboard exactly as written
     (raw: its line breaks are its fences) -- having said its size first.
     Under the button, what was made: the stretch in the server's words, how
     many chunks it holds, how many the LLM is asked to gloss and how many go
     along glossed as context, and the server's notes.  A stretch with
     nothing to gloss is said so, and nothing goes on the clipboard: an LLM
     given nothing to do answers nothing (the row is given an empty text). */
  function rgText() {
    if (rgFrom === null) return '';
    // the prompt of the person's own that the menu chose goes with the prompt's request, and only with it: the
    // answer is read the same way whoever wrote the prompt
    var extra = rgRow.options ? rgRow.options() : {};
    if (rgRow.promptId && rgRow.promptId()) extra.prompt = rgRow.promptId();
    return rgAsk('prompt', rgBody(extra)).then(function (j) {
      if (!j || !j.ok) throw new Error((j && j.error) || 'the prompt could not be made');
      var text = j.fill ? j.prompt : '';
      // THE SHORT REQUEST for a chat that has the skill is made with the prompt: the row holds it beside it
      if (rgRow.skillOf) rgRow.skillOf(j.fill ? j.skill : null);
      // by its text, since two askings can overlap and be answered out of order
      rgMade.push({j: j, text: text});
      if (rgMade.length > 4) rgMade.shift();
      return text;
    }, function (e) { throw new Error(rgWhy(e, false)); });
  }
  // after a press: what was made of the text that was copied, and whether it reached the clipboard
  function rgCopied(ok, text) {
    var made = rgMade.filter(function (m) { return m.text === text; }).pop();
    if (!made) return;
    rgByHand = ok === false;
    rgSummary(made.j);
  }
  function rgSummary(j) {
    RG.sum.textContent = '';
    var head = document.createElement('b');
    head.textContent = j.region || rgWords();
    RG.sum.appendChild(head);
    var lines = [plural(+j.chunks || 0, 'chunk') + ', ' + (+j.fill || 0) + ' to gloss, ' +
                 (+j.glossed || 0) + ' glossed sent as context'];
    if (+j.folded) lines.push(plural(+j.folded, 'folded paragraph') + ' left out');
    // the server's own note says why, and what to tick instead; that it
    // reached the clipboard, or is below to copy by hand, is the row's to say
    if (!j.fill) lines.push('nothing was copied');
    (j.notes || []).forEach(function (n) { if (rgNote(n)) lines.push(rgNote(n)); });
    lines.forEach(function (t) {
      RG.sum.appendChild(document.createTextNode('\n' + t));
    });
  }

  /* FILL FROM THE ANSWER: the answer as pasted, the stretch, and the two
     boxes as they are at this press.  What comes back is a count of what was
     written and three lists -- what the answer tried to change and was kept,
     what was dropped and why, what the answer said nothing about -- and the
     captions written to, which are drawn again where they stand. */
  function rgFill() {
    if (rgFrom === null || rgBusy) return;
    var answer = RG.ans.value;
    if (!answer.trim()) {
      rgSay(RG.report, "paste the LLM's answer into the box first", true);
      RG.ans.focus();
      return;
    }
    var confirm = rgArmed;
    rgDisarm();
    rgBusy = true; rgPaint();
    rgSay(RG.report, confirm ? 'replacing…' : 'reading the answer…');
    rgAsk('apply', rgBody(rgMarks({ answer: answer, confirm: confirm }))).then(function (j) {
      if (!j || !j.ok) throw new Error((j && j.error) || 'the answer was refused');
      rgBusy = false;
      rgApplied(j);
    }).catch(function (e) {
      rgBusy = false;
      rgSay(RG.report, rgWhy(e, true), true);
    }).then(function () { rgPaint(); });
  }
  function rgApplied(j) {
    if (j.confirm_needed) {
      var n = +j.replace || 0;
      rgArm();
      RG.fill.textContent = 'replace ' + plural(n, 'gloss', 'glosses') + ' — press again';
      rgReport(j, 'armed');
      return;
    }
    // a prompt still in the box was made before these phrases were written
    if (j.wrote) rgForget();
    var closed = rgRedraw(j.segments || {});
    rgReport(j, closed);
  }
  // the captions the answer wrote to, drawn again from what the server read
  // back off the file.  A ✎ form open on one of them is closed first: the
  // chunk it was showing has just been written under it, and a save from it
  // would put the old boxes back (or be refused) -> the caption closed, if any
  function rgRedraw(segments) {
    var closed = null;
    Object.keys(segments).forEach(function (k) {
      var i = +k, sg = segments[k];
      if (isNaN(i) || i < 0 || i >= segs.length || !sg || typeof sg !== 'object') return;
      if (editing && cloudFor && els[i] && els[i].contains(cloudFor)) {
        closeEditor(); closed = i;
      }
      segs[i] = sg;
      redrawSeg(i);
    });
    rgPaint();
    return closed;
  }
  function rgReport(j, how) {
    var box = RG.report;
    box.textContent = '';
    var tally = document.createElement('div');
    tally.className = 'rgtally';
    if (how === 'armed') {
      var n = +j.replace || 0;
      var b = document.createElement('b');
      b.textContent = plural(n, 'existing gloss', 'existing glosses') + ' will be replaced';
      tally.appendChild(b);
      tally.appendChild(document.createTextNode(
        (+j.fill ? ', and ' + plural(+j.fill, 'chunk') + ' with no gloss filled' : '') +
        '. Nothing is written yet: press the button again within four seconds to go ahead.'));
    } else {
      tally.textContent = 'filled ' + (+j.filled || 0) + ' · completed ' + (+j.completed || 0) +
                          ' · replaced ' + (+j.replaced || 0) +
                          (j.marks ? ' · vowelled ' + (+j.vowelled || 0) : '');
      if (!j.wrote) tally.appendChild(document.createTextNode('\nnothing was written'));
    }
    box.appendChild(tally);
    if (typeof how === 'number')
      box.appendChild(document.createTextNode('the ✎ form open on caption ' + how +
        ' was closed: the answer wrote to that caption'));
    // not "protected" chunks alone: a phrase the answer has just FILLED is
    // listed here too when it also tried its word line, colour or note
    // (glossregion._decided), so the heading names every case -- as the
    // reader's does -- and each row's why says which
    rgList(box, 'kept — what the answer tried to change and may not (a gloss already there, ' +
                'a word line, a colour, a note, the free mark, a plain phrase), left as it is', j.kept);
    rgList(box, 'dropped', j.dropped);
    rgList(box, 'not answered', j.unanswered);
    rgList(box, 'notes', (j.notes || []).map(function (n) {
      return typeof n === 'string' ? { why: n } : { where: n.where, why: n.note || n.why, i: n.i };
    }));
  }
  // one list of the report, each entry "where — why"; an entry that names a
  // caption brings it into view when clicked (and plays nothing)
  function rgList(box, head, list) {
    if (!list || !list.length) return;
    var h = document.createElement('h5');
    h.textContent = head + ' (' + list.length + ')';
    box.appendChild(h);
    var ul = document.createElement('ul');
    list.forEach(function (e) {
      var li = document.createElement('li');
      if (e.where) {
        var w = document.createElement('span');
        w.className = 'rgwhere'; w.textContent = e.where;
        li.appendChild(w);
      }
      if (e.why) {
        var y = document.createElement('span');
        y.className = 'rgwhy';
        y.textContent = (e.where ? ' — ' : '') + e.why;
        li.appendChild(y);
      }
      var i = e.i;
      if (typeof i === 'number' && els[i]) {
        li.className = 'to';
        li.title = 'show this caption';
        li.onclick = function () {
          lastUserScroll = Date.now();
          els[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
        };
      }
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }
  RG.btn.onclick = function () { if (rgOn) rgShut(); else rgOpen(); };
  RG.close.onclick = rgShut;
  RG.fill.onclick = rgFill;
  // a box changed or the answer edited after the server asked for a yes: the
  // yes was about something else now.  And a box changed makes another
  // prompt -- re-gloss leaves the glosses out of it, per field marks the
  // half-glossed chunks to fill -- so one kept for the copy by hand is no
  // longer the prompt these boxes ask for (rgForget)
  [RG.regloss, RG.perfield].forEach(function (b) {
    b.addEventListener('change', function () { if (rgArmed) rgDisarm(); rgForget(); });
  });
  RG.ans.addEventListener('input', function () { if (rgArmed) rgDisarm(); });
  // Esc closes the panel and ends the picking -- not while a sheet is over
  // the page, nor while the ✎ form is open, which each close first on their
  // own Esc; the ✎ form gives way when the key was pressed in the panel
  document.addEventListener('keydown', function (e) {
    if (!rgOn || e.key !== 'Escape' || e.defaultPrevented) return;
    if (dvOn || ankiOpen || vmOpen || ntOn) return;
    if (editing && !RG.panel.contains(e.target)) return;
    e.preventDefault(); rgShut();
  });
  rgPaint();

  function isNight() {
    return window.Parseh ? Parseh.theme.isDark()
      : document.documentElement.getAttribute('data-theme') === 'dark';
  }
  function showPreview(note) {
    A.pvNote.textContent = note;
    A.pvRow.hidden = false;
    A.stat.textContent = '';
    setTimeout(function () {
      A.pvRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 60);
  }
  $('#apreview').onclick = function () {
    if (ankiTarget !== 'anki') {
      // the card as a deck draws it: the studio's renderer and its script,
      // which the kit puts in the frame (and lets it run)
      var t = ankiTarget, seq = sheetSeq, snap;
      try { snap = snapCard(); } catch (e) { A.stat.textContent = e.message; return; }
      A.stat.textContent = 'rendering…';
      snapMarkdown(snap, function () { return ankiOpen && seq === sheetSeq; }).then(function (r) {
        return KIT.preview(r.md, L.code, A.pvFrame, t === 'deck');
      }).then(function () {
        if (ankiOpen && seq === sheetSeq && ankiTarget === t)
          showPreview('drawn as a deck and a studio document draw it — click the card to turn it');
      }).catch(function (e) { if (ankiOpen && seq === sheetSeq) A.stat.textContent = e.message; });
      return;
    }
    var c = collectCard();
    A.stat.textContent = 'rendering…';
    fetch('/anki/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card: c.card, shot: c.shot, clip: c.clip, night: isNight() })
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'preview failed');
      // an Anki card runs no script of the page's: the frame's sandbox as it
      // was before a deck's preview widened it
      A.pvFrame.setAttribute('sandbox', 'allow-same-origin');
      A.pvFrame.srcdoc = res.html;
      showPreview('rendered with the very templates and styles the .apkg carries — ' +
                  'the line is where Anki flips to the answer');
    }).catch(function (e) { A.stat.textContent = e.message; });
  };
  $('#apvhide').onclick = function () { $('#apvrow').hidden = true; };

  $('#abuild').onclick = function () {
    // the value is "<folder>/<slug>", which is what the build URL names:
    // two languages may hold a deck of the same name, and the one-level
    // URL cannot tell them apart
    var key = A.deck.value;
    if (!key) {
      A.stat.textContent = 'save a card first — the deck does not exist yet';
      return;
    }
    // on the activity list while the deck is built and sent (lib/activity.js)
    if (window.ParsehActivity) ParsehActivity.download('/anki/build/' + key + '.apkg',
                                                       'Building the Anki deck…');
    else location.href = '/anki/build/' + key + '.apkg';
    A.stat.textContent = 'building — import the downloaded .apkg into Anki';
  };

  /* ---------------- boot ----------------
     video.json first, for its "reorders" (a text read out of its written
     order, whose word strip the editor draws without comparing the words
     with the reading): it sits beside the annotations, so the page already
     knows where it is.  A video.json that will not load is no error worth
     a message -- the transcript is what the page is for -- so that fetch
     answers with an empty record and the video reads in its written order,
     which is what every video that says nothing means.  Nothing else in the
     file changes how the transcript is drawn. */
  fetch(String(CFG.ann).replace(/annotations\.json$/, 'video.json'),
        { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : {}; })
    .catch(function () { return {}; })
    .then(function (meta) {
      reorders = !!(meta && meta.reorders);
      return fetch(CFG.ann, { cache: 'no-store' });
    })
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function (data) { segs = data.segments || []; render(); loadNotes();
                            paintCapTimes(); loadCapWave(); })
    .catch(function (e) {
      $('#segs').innerHTML = '<p class="hint">could not load ' + esc(CFG.ann) +
        ' (' + esc(e.message) + ') — has the annotation step run yet?</p>';
    });

  /* ---------------- the film, wherever it is -------------------------
     Everything above asks the player six things and no more:
     getPlayerState, playVideo, pauseVideo, getCurrentTime, getDuration and
     seekTo.  That is the whole of what the transcript needs to follow a
     video, and it is small enough that a file on this machine can answer it
     as well as YouTube can -- so a local film is not a second player but a
     second thing behind the same six.

     CFG.media is the film's own address under /youtube/videos/, served by
     the static route with Range, which is what lets a <video> seek at all.
     A video with no CFG.media is on YouTube and reaches it the way it always
     did. */
  /* A card made from a phrase carries the moment it was made at, as
     `#t=<seconds>` on this page's own address -- so opening the card's
     source lands where the phrase is spoken and not at the beginning.  It
     is read once, when whichever player is behind the six says it is ready;
     a YouTube video answers it too, and its cards always could have. */
  function jumpToHash() {
    var m = /^#t=(\d+(?:\.\d+)?)$/.exec(location.hash || '');
    if (!m || !player || !ready) return;
    var t = parseFloat(m[1]);
    if (t > 0 && player.seekTo) player.seekTo(t, true);
  }

  /* A SOUND, IN A VIDEO'S PLACE.  A video whose media is a sound alone (video.json
     says "kind": "audio", written when it was attached) has no frame to show.
     What fills the video's place is a bar: the shape of the sound, whole, with
     the playhead on it -- a press anywhere on it goes there, a drag scrubs -- and
     the element's own controls under it, the caption starts as hairlines at its
     foot.  The shape is read by the server with ffmpeg (/youtube/api/film/wave);
     without ffmpeg, or away from the computer, the bar is a plain track and says
     why.  Nothing here writes. */
  function soundBar(film) {
    var box = document.createElement('div');
    box.id = 'sndbar';
    var cv = document.createElement('canvas');
    cv.id = 'sndwave';
    cv.setAttribute('aria-label', 'the sound: press anywhere on it to go there');
    var say = document.createElement('div');
    say.className = 'sndsay';
    box.appendChild(cv);
    box.appendChild(say);
    film.parentNode.insertBefore(box, film);
    var wave = null, shown = '', pressed = false;
    function ink(name, fall) {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      return (v && v.trim()) || fall;
    }
    function span() {
      return film.duration && isFinite(film.duration) ? film.duration : (wave ? wave.seconds : 0);
    }
    function draw(force) {
      var w = cv.clientWidth, h = cv.clientHeight;
      if (!w || !h) return;
      var on = ink('--accent', '#be3455'), off = ink('--faint', '#a2949a');
      var dur = span(), now = film.currentTime || 0;
      // drawn again only when something it shows has changed
      var sig = [w, h, Math.round(now * 10), Math.round(dur), wave ? wave.peaks.length : 0,
                 segs.length, on, off].join('|');
      if (!force && sig === shown) return;
      shown = sig;
      var dpr = window.devicePixelRatio || 1;
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
        cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      }
      var g = cv.getContext('2d');
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, w, h);
      var at = dur ? Math.min(1, now / dur) * w : 0, mid = (h - 6) / 2;
      // what is drawn, for whoever looks: the shape of the sound, or a plain track
      cv.setAttribute('data-shape', wave && wave.peaks.length ? 'wave' : 'plain');
      if (wave && wave.peaks.length) {
        var n = wave.peaks.length, bw = w / n;
        for (var i = 0; i < n; i++) {
          var x = i * bw, v = Math.max(0.05, wave.peaks[i]) * (h - 12) / 2;
          g.fillStyle = x + bw / 2 <= at ? on : off;
          g.fillRect(x, mid - v, Math.max(1, bw - 0.6), v * 2);
        }
      } else {
        g.fillStyle = off; g.fillRect(0, mid - 1, w, 2);
        g.fillStyle = on; g.fillRect(0, mid - 1.5, at, 3);
      }
      if (dur) {
        g.fillStyle = off;
        for (var k = 0; k < segs.length; k++) {
          var sx = Math.round((+segs[k].start || 0) / dur * w);
          if (sx >= 0 && sx <= w) g.fillRect(sx, h - 5, 1, 5);
        }
      }
      g.fillStyle = on;
      g.fillRect(Math.min(w - 2, Math.max(0, at - 1)), 0, 2, h - 6);
    }
    function go(e) {
      var r = cv.getBoundingClientRect(), d = span();
      if (!d || !r.width) return;
      try { film.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * d; }
      catch (err) {}
      draw(true);
    }
    cv.addEventListener('pointerdown', function (e) {
      pressed = true;
      try { cv.setPointerCapture(e.pointerId); } catch (err) {}
      go(e);
      e.preventDefault();
    });
    cv.addEventListener('pointermove', function (e) { if (pressed) go(e); });
    ['pointerup', 'pointercancel'].forEach(function (name) {
      cv.addEventListener(name, function () { pressed = false; });
    });
    ['timeupdate', 'seeked', 'durationchange', 'loadedmetadata'].forEach(function (name) {
      film.addEventListener(name, function () { draw(); });
    });
    window.addEventListener('resize', function () { draw(true); });
    // the transcript arrives after the page, the theme can change under it, and a
    // paused sound has no event to say so: a look every so often costs nothing
    setInterval(draw, 400);
    fetch('/youtube/api/film/wave', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                     body: JSON.stringify({video: CFG.id, buckets: 900})})
      .then(function (r) { return r.json().catch(function () { return null; }); })
      .then(function (j) {
        if (j && j.ok && j.peaks && j.peaks.length) wave = j;
        else say.textContent = ((j && j.error) || 'the shape of the sound could not be drawn') +
                               ' — the bar is a plain track';
        draw(true);
      }, function () {
        say.textContent = 'the shape of the sound could not be drawn here — the bar is a plain track';
        draw(true);
      });
    draw(true);
  }

  /* THE FILM OR THE SOUND OF A VIDEO THAT IS NOT THERE ANY MORE: sent again, from
     the box that says so, to the same door the add page sends by (its own script,
     youtube/lib/addfilm.js, is not on this page: the player is kept on a phone and
     what it loads is a list).  Whole or not at all, and the page is opened again
     on it.  Browser mode only: a phone's page writes nothing (lib/mobile.css). */
  function sendAgain(box) {
    var pick = document.createElement('input');
    pick.type = 'file';
    pick.hidden = true;
    pick.accept = CFG.accept || 'audio/*,video/*';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'novid-again';
    btn.textContent = 'send the film or sound again…';
    var said = document.createElement('div');
    said.className = 'novid-said';
    said.setAttribute('aria-live', 'polite');
    var row = document.createElement('div');
    row.className = 'novid-send';
    row.appendChild(btn);
    row.appendChild(pick);
    row.appendChild(said);
    box.appendChild(row);
    btn.addEventListener('click', function () { pick.click(); });
    pick.addEventListener('change', function () {
      var f = pick.files && pick.files[0];
      if (!f) return;
      btn.disabled = true;
      var label = f.name + ' (' + (f.size >= 1e6 ? Math.round(f.size / 1e6) + ' MB'
                                                 : Math.max(1, Math.round(f.size / 1e3)) + ' kB') + ')';
      said.textContent = 'sending ' + label + '…';
      var act = window.Parseh && Parseh.working ? Parseh.working('Sending ' + f.name) : null;
      var x = new XMLHttpRequest();
      var url = '/youtube/api/film?video=' + encodeURIComponent(CFG.id) + '&name=' + encodeURIComponent(f.name);
      x.open('POST', act ? act.url(url) : url);
      x.setRequestHeader('Content-Type', 'application/octet-stream');
      x.upload.onprogress = function (e) {
        if (!e.lengthComputable) return;
        said.textContent = 'sending ' + label + ' — ' + Math.floor(100 * e.loaded / e.total) + ' %';
        if (act) act.progress(e.loaded, e.total);
      };
      x.onload = function () {
        var j = null;
        try { j = JSON.parse(x.responseText); } catch (err) {}
        if (act) act.end(!!(j && j.ok));
        if (j && j.ok) { said.textContent = 'sent — opening it…'; location.reload(); return; }
        btn.disabled = false;
        said.textContent = (j && j.error) || ('the server refused it (' + x.status + ')');
      };
      x.onerror = function () {
        if (act) act.end(false);
        btn.disabled = false;
        said.textContent = 'the server did not answer — nothing was sent';
      };
      x.send(f);
    });
  }

  if (CFG.media) {
    // A SOUND is an <audio> and is still `#film`: everything that asks the film
    // for its time, its rate or its sound asks it as before.  What fills the
    // video's place is a bar (soundBar), and the word for it on the page is
    // "sound" where the video's own would say "film".
    var SOUND = CFG.kind === 'audio';
    var film = document.createElement(SOUND ? 'audio' : 'video');
    film.id = 'film';
    film.controls = true;
    film.preload = 'metadata';
    if (!SOUND) film.playsInline = true;
    film.src = CFG.media;
    var slot = $('#yt');
    slot.parentNode.insertBefore(film, slot);
    slot.remove();
    if (SOUND) soundBar(film);
    player = {
      // YT's states, of which the six callers read only 1 = playing
      getPlayerState: function () { return (film.paused || film.ended) ? 2 : 1; },
      playVideo: function () { var p = film.play(); if (p) p.catch(function () {}); },
      pauseVideo: function () { film.pause(); },
      getCurrentTime: function () { return film.currentTime || 0; },
      getDuration: function () { return film.duration || 0; },
      seekTo: function (t) { try { film.currentTime = Math.max(0, t); } catch (e) {} },
      // THE OTHER THREE.  The transcript needs six; the Anki panel's frame
      // capture needs these as well, and answering only six meant that
      // button threw on every local film -- the count was made by reading
      // the transcript's callers and not every caller there is.
      isMuted: function () { return !!film.muted; },
      mute: function () { film.muted = true; },
      unMute: function () { film.muted = false; },
      // the rate is the timings editor's: it puts the video back to 1 while
      // it draws the sound.  A film here never asks it to -- the server
      // reads the film with ffmpeg instead -- but the shim answers
      // everything the page asks of a player, or it is not a player
      getPlaybackRate: function () { return film.playbackRate || 1; },
      setPlaybackRate: function (r) { try { film.playbackRate = r || 1; } catch (e) {} },
      // YouTube offers the speeds IT will play at, and the controls ask for
      // that list (lib/narrctl.js, the speed chip): a <video> of this machine
      // plays at whatever rate it is given, so it says it has no list of its
      // own and the chip offers the toolbox's own speeds
      getAvailablePlaybackRates: function () { return null; }
    };
    film.addEventListener('loadedmetadata', function () {
      ready = true; $('#novid').hidden = true; measure(); jumpToHash();
      // as the YouTube player does on its own ready: the controls outside this
      // script learn there is something to drive (lib/narrctl.js)
      saidState();
    });
    // the download carries the film, so the button says so -- and how big
    // it is, as the server sums what the bundle will carry (bundle.payload),
    // and where the smaller one is, because a two-hour film is not a small zip
    var dl = $('#dl');
    if (dl) {
      var n = CFG.bundle_bytes;
      var big = !n ? '' : ' (about ' + (n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB'
        : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + ' MB'
        : Math.max(1, Math.round(n / 1e3)) + ' kB') + ')';
      dl.title = 'download this video as a bundle: the ' + (SOUND ? 'sound' : 'film') +
                 ' itself and its glosses in one zip' + big + ', which another Parseh installs whole. ' +
                 'Add ?media=text to the address for the words alone.';
    }
    // the same meaning as YT's state 1: the person pressed play, so the
    // hover-pause has nothing of its own to resume -- and nor has the LLM
    // panel (rgWasPlaying, onStateChange below says why)
    film.addEventListener('play', function () { wasPlaying = false; rgWasPlaying = false; });
    film.addEventListener('error', function () {
      // SAY WHICH THING WENT WRONG.  A file that is gone and a file the
      // browser cannot decode are different problems with different
      // answers, and one message for both sends somebody looking for a
      // file that is sitting exactly where they put it.
      var code = (film.error && film.error.code) || 0;
      var n = $('#novid');
      var what = SOUND ? 'sound' : 'film';
      n.innerHTML = (code === 4
        ? 'this browser cannot play that ' + (SOUND ? 'sound' : 'file') + ' —<br>' +
          (SOUND ? 'a playable copy is made where ffmpeg is installed: add it again once it is<br>'
                 : '') +
          'the transcript below still works'
        : code === 3
          ? 'the ' + what + ' is there but will not decode —<br>' +
            'the transcript below still works'
          : 'the ' + what + ' is not where this video says it is —<br>' +
            'the transcript below still works');
      n.hidden = false;
    });
  } else if (CFG.local) {
    // A VIDEO THAT IS A FILE, WHOSE FILE IS NOT THERE.  Reaching for YouTube
    // here would ask it for a video at an id it has never heard of, and the
    // reader would be told, wrongly, that they need an internet connection.
    $('#novid').innerHTML = 'the film (or sound) that belongs to this video is not ' +
      'here any more —<br>send it again, put it back beside the transcript, or add the ' +
      'video again<br>— the transcript below still works';
    $('#novid').hidden = false;
    sendAgain($('#novid'));
  } else {
    // The IFrame API calls a global when it is ready.  If it never loads
    // (offline), say so in the frame; the transcript works regardless.
    window.onYouTubeIframeAPIReady = function () {
      player = new YT.Player('yt', {
        videoId: CFG.id,
        // YOUTUBE'S OWN ⛶ IS NOT ON A PHONE (the owner's choice, 2026-09-23).
        // The mobile interface has a whole screen of its own -- the page, laid
        // out by Parseh, with the line being said over the picture
        // (lib/mobileplayer.js) -- and a second ⛶ inside the frame puts the
        // iframe on top, which takes those subtitles away and leaves a way out
        // nobody here can offer.  One full screen, and it is the one with the
        // words in it.  On a computer the frame keeps its own button.
        playerVars: { rel: 0, playsinline: 1, fs: mobileMode() ? 0 : 1 },
        events: {
          // the offline note may have been shown by the slow-API timeout;
          // a player that reaches ready proves it wrong
          onReady: function () {
            ready = true; $('#novid').hidden = true; measure(); jumpToHash();
            // a sheet opened before the player came can cut from it now
            if (ankiOpen) paintCut();
            paintShot();
            // and the controls outside this script learn there is a player to
            // drive: the speed a video was last watched at is put back the
            // moment one exists (lib/narrctl.js)
            saidState();
          },
          onStateChange: function (e) {
            // the user pressed play himself: the hover-pause has nothing of
            // its own to resume, AND NEITHER HAS THE LLM PANEL.  It paused the
            // video when it opened and plays it when it closes; but it has no
            // backdrop, the video's own controls stay in reach -- and, a click
            // on a caption being a pick, they are how a line is heard while
            // picking.  Played and paused again by hand, the video is where the
            // person left it, and closing the panel started it by itself.
            // rgShut's own play comes after it has let the flag go, and the ✎
            // form's handover sets it with no play at all, so neither is lost
            if (e.data === 1) { wasPlaying = false; rgWasPlaying = false; }
            saidState();
          },
          // THE RATE, WHEN YOUTUBE HAS REALLY TAKEN IT.  setPlaybackRate is a
          // message to the frame and getPlaybackRate answers with the rate
          // from before it lands, so the speed chip painted one change behind
          // until it was given something to wait for (TO-DO §0, 2026-09-23).
          onPlaybackRateChange: saidState,
          /* A VIDEO YOUTUBE WILL NOT PLAY used to fail without a word: the
             frame sat empty and nothing said why (TO-DO §2.17).  The reasons
             are few and each has a different answer, so each is said in the
             same place that says why a player never started at all. */
          onError: function (e) {
            var code = e && e.data;
            var why = code === 2
              ? 'YouTube does not know this address —<br>' +
                'the id this video is filed under is not one of its own'
              : code === 5
                ? 'YouTube will not play this video in this browser —<br>' +
                  'it can still be watched on youtube.com'
                : code === 100
                  ? 'this video is gone from YouTube —<br>' +
                    'it was taken down, or it was made private'
                  : (code === 101 || code === 150)
                    ? 'the owner of this video does not allow it to be played ' +
                      'outside YouTube —<br>it can still be watched on youtube.com'
                    : 'YouTube would not play this video (error ' + esc(String(code)) + ')';
            $('#novid').innerHTML = why + '<br>— the transcript below still works';
            $('#novid').hidden = false;
          }
        }
      });
    };
    /* WAITING IS NOT FAILING.  This used to hang a blind six-second timer on
       the page: whatever had happened, if no player existed by then the box
       came up saying the video needed an internet connection -- which the
       page had never tested, and which was false every time the phone was
       merely slow.  On a tunnel, with the app fetching its own pages in the
       background, six seconds is an ordinary time for YouTube's script to
       arrive (that is exactly how this came to be seen: the owner, online,
       2026-09-23).  So the script's own load and error are listened to, the
       waiting says it is waiting, and only a real failure says so -- with
       what failed, a way to try again, and a way to watch it where it is. */
    var apiSaid = false;
    function giveUp(why) {
      if (apiSaid) return;
      apiSaid = true;
      var box = $('#novid');
      box.innerHTML = '';
      box.appendChild(document.createTextNode(why));
      box.appendChild(document.createElement('br'));
      var again = document.createElement('button');
      again.type = 'button';
      again.className = 'novid-again';
      again.textContent = 'Try again';
      again.addEventListener('click', function () {
        box.hidden = true;
        apiSaid = false;
        loadApi();
      });
      box.appendChild(again);
      if (CFG.id && !CFG.media) {
        var out = document.createElement('a');
        out.className = 'novid-out';
        out.href = 'https://www.youtube.com/watch?v=' + encodeURIComponent(CFG.id);
        out.rel = 'noreferrer';
        out.target = '_blank';
        out.textContent = 'Watch it on YouTube';
        box.appendChild(document.createTextNode(' · '));
        box.appendChild(out);
      }
      /* AND WHERE TO LOOK WHEN IT IS THE TUNNEL.  A phone on Tailscale can
         reach Parseh perfectly and not the open internet at all -- MagicDNS
         answers the tailnet's names and the phone cannot reach the resolver
         that would answer the rest -- and then every video fails here while
         everything else about Parseh works.  It is not something this page
         can mend, and it is not something anybody would guess, so the page
         says where it is written down. */
      var help = document.createElement('a');
      help.className = 'novid-out';
      help.href = '/guide/site/getting-started/other-devices.html' +
                  '#a-phone-on-tailscale-that-cannot-reach-the-internet';
      help.textContent = 'On a phone over Tailscale, this is usually DNS — what to change';
      box.appendChild(document.createElement('br'));
      box.appendChild(help);
      box.appendChild(document.createElement('br'));
      box.appendChild(document.createTextNode('— the transcript below still works'));
      box.hidden = false;
    }
    function loadApi() {
      if (window.YT && window.YT.Player) { window.onYouTubeIframeAPIReady(); return; }
      var tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      // the script itself failing is the one thing that IS a network answer
      tag.onerror = function () {
        giveUp('YouTube’s player could not be fetched — Parseh itself is answering, ' +
               'so it is YouTube this phone cannot reach.');
      };
      // it arrived: from here on the wait is YouTube's own, and a wait is not
      // a failure -- the player is given a long, honest grace
      tag.onload = function () {
        setTimeout(function () {
          if (!player) giveUp('YouTube’s player was fetched but never started.');
        }, 20000);
      };
      document.head.appendChild(tag);
      // and if the script neither loads nor errors -- a request left hanging,
      // which is what a phone with a network and no route does -- say so
      // rather than sitting silent for ever
      setTimeout(function () {
        if (!player && !window.YT) giveUp('YouTube’s player has not arrived yet.');
      }, 25000);
    }
    loadApi();
  }
  setInterval(tick, 250);
  measure();
  // a phone turned, or the mode switched in another tab: the layout follows
  if (window.matchMedia) {
    try {
      window.matchMedia(WIDE_M).addEventListener('change', function () {
        paintButtons();
        applySize();
        if (active >= 0) show(active);
      });
    } catch (e) {}
  }
  // The mode switched, here or in another tab: the layout follows -- AND SO
  // DOES THE LLM PANEL'S PICKING, which the phone's mode has none of
  // (rgPicking).  The panel is hidden there, not closed, and the run lit on
  // the transcript and body.rgpicking -- the column pushed 458px aside for a
  // panel no longer shown, the crosshair -- were left standing until
  // something else repainted, taps seeking under a tint that said they
  // picked.  Painted again on the switch, the run goes out in the phone's
  // mode and comes back lit in the computer's, the panel still open
  // (style.css also scopes those rules to a page not in the phone's mode)
  if (window.MutationObserver) {
    new MutationObserver(function () { paintButtons(); applySize(); rgPaint(); })
      .observe(document.documentElement, {attributes: true, attributeFilter: ['data-mode']});
  }

  /* ---------------- THE GEAR, ⚙ page (a0.5.0) ----------------
     Everything this page lets a person set, in the one panel -- lib/pagesettings.js
     draws it and this says what is in it: how the transcript follows the video, how
     a word is looked up, how the video plays, how the text looks, the zoom, the
     colours, the interface.  Groups, rows, names and sentences are the owner's
     (TO-DO §5.25).

     THE PAGE'S OWN CONTROLS STAY WHERE THEY ARE AND DO THE WORK.  A switch of the
     panel is read from the setting its button keeps and is moved by PRESSING that
     button, so the button, its handler, the key it is stored under and the gear can
     never disagree; the buttons that live only in the gear (hover ⏸, definitions,
     translated, the reading-help link) are put away by the stylesheet
     (html.pg-player) and are still in the page, for this to press.  What is not a
     button of the page's is what the page already knew how to do: the size of the
     video (the bar under it), the Aa panel's own sliders (typoFields), and the
     lines drawn without their marks (redrawText).  A page the toolkit did not come
     to (its script is missing) is the page it was.

     AND Aa OPENS THIS: the header's Aa stays where it is and opens the gear at its
     Text group -- one set of sliders -- so Parseh.typo's own panel is kept for the
     one place that still has it, the Aa on a phone's whole screen (lib/mobileplayer.js),
     which has no gear and sizes only the subtitles and the glosses. */
  (function () {
    var Gear = window.ParsehGear;
    if (!Gear || !Gear.mount) { document.documentElement.classList.remove('pg-player'); return; }
    var gear = null;
    var DEVICE = 'Saved on this device.';

    /* A switch that is one of the page's own buttons: pressed only if it is not already as asked, and pressed by
       RUNNING THE BUTTON'S OWN HANDLER, not by clicking it.  The toolkit hears every click on the page, whoever sent
       it, and one that lands outside the panel is what shuts a popover: a switch that pressed the page's button by
       a click shut its own panel, to be opened again for every switch.  (Where the handler is not a property -- a
       later script hung it with addEventListener -- the click is all there is.) */
    function press(sel, want, now) {
      if (!!now() === !!want) return;
      var b = $(sel);
      if (b.disabled) return;
      if (typeof b.onclick === 'function') b.onclick.call(b); else b.click();
    }
    // what the page says changed under the panel (a header button pressed, the window turned or
    // resized, a reading-help answer come): ONE row carries it, since every row is asked again
    function watchPage(cb) {
      var mo = null, head = document.querySelector('header');
      if (window.MutationObserver && head) {
        mo = new MutationObserver(function () { cb(); });
        mo.observe(head, {attributes: true, subtree: true, attributeFilter: ['class', 'hidden', 'disabled']});
        mo.observe(document.body, {attributes: true, attributeFilter: ['class']});
      }
      window.addEventListener('resize', cb);
      return function () { if (mo) mo.disconnect(); window.removeEventListener('resize', cb); };
    }
    // a setting another tab, or the toolbox, changed
    function watchKeys(keys) {
      return function (cb) {
        var h = function (e) { if (!e || !e.key || keys.indexOf(e.key) >= 0) cb(); };
        var p = function (e) { var d = e && e.detail; if (!d || keys.indexOf(d.key) >= 0) cb(); };
        window.addEventListener('storage', h);
        document.addEventListener('parseh:pref', p);
        return function () {
          window.removeEventListener('storage', h);
          document.removeEventListener('parseh:pref', p);
        };
      };
    }
    function narr() { return window.ParsehNarr || null; }

    /* ---- Watching & reading ---- */
    function setMarks(on) {
      opts.marks = !!on;
      localStorage.setItem('yt_marks', on ? '1' : '0');
      redrawText();
    }
    // the video's size as a share of what this layout can be, which is what a slider with
    // fixed ends can say; the number beside it is the width in pixels, which is what is kept
    function sizeShare() {
      var r = videoSize.range(), v = videoSize.get();
      return r.max > r.min ? Math.max(0, Math.min(100, (v - r.min) / (r.max - r.min) * 100)) : 100;
    }
    var watching = {
      id: 'watching', title: 'Watching & reading', caption: DEVICE,
      rows: [
        {id: 'follow', kind: 'switch', label: 'Keep the playing caption in view',
         help: 'Scrolls the transcript so the caption being said stays on screen; it waits a moment after you scroll yourself.',
         get: function () { return opts.follow; },
         set: function (v) { press('#follow', v, function () { return opts.follow; }); },
         watch: watchPage},
        {id: 'hoverpause', kind: 'switch', label: 'Pause while a gloss is open',
         help: 'While a gloss is open the video waits, and goes on a moment after it closes, so you can read at your own pace. With a mouse or a finger.',
         get: function () { return opts.hoverpause; },
         set: function (v) { press('#hoverpause', v, function () { return opts.hoverpause; }); }},
        {id: 'aloud', kind: 'switch', label: 'Show only the reading',
         help: 'Draws each phrase as its reading alone (kana, or pinyin) and keeps the text in the hover cloud.',
         when: function () { return !!L.words; },
         get: function () { return opts.aloud; },
         set: function (v) { press('#aloud', v, function () { return opts.aloud; }); }},
        {id: 'marks', kind: 'switch', label: 'Diacritics',
         help: 'Shows the small marks that write the vowels, the doubling and the silent stop (fatha, damma, kasra, ' +
               'tanwin, shadda, sukun) on the transcript. Off, the text reads as it is ordinarily printed and you can ' +
               'still point at a phrase for its gloss.',
         when: function () { return videoHasMarks(); },
         get: function () { return opts.marks; },
         set: setMarks},
        {id: 'sbs', kind: 'switch', label: 'Video beside the text',
         help: 'Puts the video in a column beside the transcript instead of above it. Only on wide screens ' +
               '(860 px and up); on a phone, turning it sideways does it.',
         when: function () { return CFG.kind !== 'audio'; },
         // on a phone's layout it is the phone's own turning that decides, so the switch says what the page is
         // doing and rests, with the reason, instead of promising what it cannot do
         disabled: function () { return mobileNow() ? 'On a phone, turning it sideways does it.' : false; },
         get: function () { return mobileNow() ? sideOn() : opts.sbs; },
         set: function (v) { press('#sbs', v, function () { return opts.sbs; }); }},
        {id: 'pin', kind: 'switch', label: 'Keep the video in view',
         help: 'The video stays at the top while the transcript scrolls under it. Not needed when the video is beside the text.',
         disabled: function () { return sideOn() ? 'The video is beside the text, so it is always in view.' : false; },
         get: function () { return opts.pin; },
         set: function (v) { press('#pin', v, function () { return opts.pin; }); }},
        {id: 'size', kind: 'slider', label: 'Video size',
         help: 'How big the video is. You can also drag the bar under it; double-click it to reset.',
         min: 0, max: 100, step: 1,
         when: function () { return CFG.kind !== 'audio'; },
         disabled: function () {
           var r = videoSize.range();
           return r.max > r.min ? false : 'This window has no room to make the video bigger or smaller.';
         },
         get: sizeShare,
         set: function (p) { var r = videoSize.range(); videoSize.set(r.min + p / 100 * (r.max - r.min)); },
         format: function (p) {
           var r = videoSize.range();
           // as kept where the slider is where the video is, and as the slider says elsewhere
           return (Math.round(p) === Math.round(sizeShare()) ? videoSize.get()
                                                              : Math.round(r.min + p / 100 * (r.max - r.min))) + ' px';
         },
         watch: function (cb) { return videoSize.onChange(cb); }},
        {id: 'lines', kind: 'switch', layouts: 'mobile', label: 'Show the lines around',
         help: 'On the whole-screen video, shows the caption before above and the caption after below the one being said.',
         when: function () { return !!(window.ParsehMobilePlayer && ParsehMobilePlayer.lines); },
         get: function () { return ParsehMobilePlayer.lines.get(); },
         set: function (v) { ParsehMobilePlayer.lines.set(v); },
         watch: function (cb) { return ParsehMobilePlayer.lines.onChange(cb); }}
      ]
    };

    /* ---- Looking a word up: the switches only where the page's own dictionary button is there ---- */
    var looking = {
      id: 'looking', title: 'Looking a word up', caption: DEVICE,
      rows: [
        {id: 'dict', kind: 'switch', label: 'Look words up in a dictionary',
         help: 'Where a phrase has not been glossed, its cloud looks its words up in the dictionary installed for this ' +
               'language. Remembered on this device.',
         when: function () { return !$('#dictmode').hidden; },
         get: function () { return opts.dict; },
         set: function (v) { press('#dictmode', v, function () { return opts.dict; }); }},
        {id: 'defs', kind: 'switch', indent: 1, label: 'Show the dictionary’s definitions',
         help: function () { return 'Under each word it finds, the dictionary’s own definition in ' + (L.name || L.code) + '.'; },
         when: function () { return !$('#dictmode').hidden && !$('#defmode').hidden; },
         disabled: function () { return $('#defmode').disabled ? 'Turn on the dictionary above first.' : false; },
         get: function () { return opts.defs; },
         set: function (v) { press('#defmode', v, function () { return opts.defs; }); }},
        {id: 'defsmt', kind: 'switch', indent: 2,
         label: function () { return 'Translate the definitions into ' + G.name; },
         help: function () {
           return 'Each definition is put into ' + G.name + ' by the translation model on this computer: ' +
                  'a machine’s reading, not a gloss.';
         },
         when: function () { return !$('#dictmode').hidden && !$('#defmt').hidden; },
         disabled: function () {
           return $('#defmt').disabled ? (opts.dict ? 'Turn on the definitions above first.' : 'Turn on the dictionary first.') : false;
         },
         get: function () { return opts.defsMt; },
         set: function (v) { press('#defmt', v, function () { return opts.defsMt; }); }},
        // drawn even where nothing is installed: it is how something gets installed
        {id: 'help', kind: 'link', href: '/settings/reading-help/', label: 'Get a dictionary for this language →',
         help: 'A dictionary, a corpus of translated sentences or a translation model can read a phrase nobody has ' +
               'glossed. Setting one up takes a couple of minutes.'}
      ]
    };

    /* ---- Playback: the skip is the person's (bk_skip, which ↺ ↻ and Shift+← → use); the speed is the dock's ---- */
    var playback = {
      id: 'playback', title: 'Playback', caption: 'Saved on this device, except the skip distance, which follows you.',
      rows: [
        {id: 'skip', kind: 'choice', kept: 'you', label: 'Skip distance',
         help: function () {
           return mobileNow() ? 'How many seconds ↺ and ↻ move the video. Shift+← and Shift+→ do the same.'
                              : 'How many seconds Shift+← and Shift+→ move the video.';
         },
         options: ((narr() && narr().seconds) || [1, 2, 5, 10, 15, 30, 60]).map(function (n) {
           return {value: n, label: n + ' s'};
         }),
         get: function () {
           if (narr() && narr().secs) return narr().secs();
           var v = parseInt(localStorage.getItem('bk_skip'), 10);
           return v >= 1 && v <= 600 ? v : 10;
         },
         set: function (v) {
           v = parseInt(v, 10);
           if (narr() && narr().setSecs) narr().setSecs(v); else localStorage.setItem('bk_skip', String(v));
         },
         watch: watchKeys(['bk_skip'])},
        // only where the page has a control of its own for it: the dock of the phone's layout (lib/narrctl.js);
        // a stepper, because the speeds a video plays at are the player's to say (YouTube offers eight)
        {id: 'speed', kind: 'stepper', layouts: 'mobile', kept: 'device', label: 'Playback speed',
         help: 'How fast the video plays. The speed chip in the dock at the foot of the screen sets the same speed.',
         when: function () { return !!(narr() && narr().rate); },
         values: function () { return (narr() && narr().speeds && narr().speeds()) || [1]; },
         get: function () { return narr().rate(); },
         set: function (v) { narr().setRate(v); },
         format: function (v) { return narr() && narr().say ? narr().say(v) : v + '×'; },
         def: 1, reset: function () { narr().setRate(1); }, resetLabel: 'Back to 1×',
         watch: function (cb) { return window.ParsehPlayer && ParsehPlayer.onChange ? ParsehPlayer.onChange(cb) : function () {}; }}
      ]
    };

    /* ---- Text: the Aa panel's own fields, each a slider with the words the owner chose ---- */
    var TEXT = {
      fa:           {label: function () { return (L.name || L.code) + ' text size'; },
                     help: 'How big the transcript’s own words are, the ones you are learning.',
                     show: function (v) { return Math.round(v * 10) / 10 + ' px'; }},
      sub:          {label: 'Subtitle size', layouts: 'mobile',
                     help: 'How big the subtitles are over the video when it fills the screen (a phone held sideways).',
                     show: function (v) { return Math.round(v * 10) / 10 + ' px'; }},
      gl:           {label: 'Gloss size',
                     help: 'How big the meanings and notes in the hover cloud are.',
                     show: function (v) { return Math.round(v * 10) / 10 + ' px'; }},
      width:        {label: 'Text width',
                     help: 'How wide the column of transcript may grow on a wide screen; on a narrow screen it always fits.',
                     show: function (v) { return Math.round(v) + ' px'; }},
      lead:         {label: 'Line spacing',
                     help: 'The space between lines: 1 is the usual, more is airier.',
                     show: function (v) { return Math.round(v * 100) / 100 + '×'; }},
      cjkSpace:     {label: 'Space between characters',
                     help: 'Extra room between characters; 0 is the normal spacing.',
                     show: function (v) { return Math.round(v * 1000) / 1000 + ' em'; }},
      kanaContrast: {label: 'Furigana contrast',
                     help: 'How strongly the small kana over the kanji are drawn: lower fades them so the kanji stand out, higher makes them darker.',
                     show: function (v) { return Math.round(v) + ' %'; }},
      kanaSize:     {label: 'Furigana size',
                     help: 'How big the kana over the kanji are, as a percentage of the kanji’s own size.',
                     show: function (v) { return Math.round(v) + ' %'; }}
    };
    var text = {id: 'text', title: 'Text', caption: DEVICE, rows: []};
    typoFields.forEach(function (f) {
      var t = TEXT[f.name];
      if (!t || !typoApi) return;
      var row = {id: f.name, kind: 'slider', label: t.label, help: t.help,
                 min: f.min, max: f.max, step: f.step, format: t.show,
                 get: function () { return typoApi.get()[f.name]; },
                 set: function (v) { typoApi.set(f.name, v); },
                 // the whole screen's panel moves the same values
                 watch: function (cb) {
                   typoTold.push(cb);
                   return function () { var k = typoTold.indexOf(cb); if (k >= 0) typoTold.splice(k, 1); };
                 }};
      if (t.layouts) row.layouts = t.layouts;
      text.rows.push(row);
    });
    if (typoApi) text.rows.push({id: 'reset', kind: 'action', label: 'Put the text back to normal',
      help: 'Sets every size, the width and the spacing above back to the usual.',
      onClick: function () { typoApi.reset(); }});

    /* ---- the last group of the phone's sheet holds the Keep buttons (lib/keep.js), brought in as they are ---- */
    var iface = Gear.std['interface']();
    iface.rows.push({id: 'keep', kind: 'node', layouts: 'mobile', label: 'Use it without the computer',
      help: 'Keep this video on this phone, so it still works when the computer cannot be reached.',
      el: function () { return document.querySelector('.kp-btn'); }});

    var header = document.querySelector('header');
    try {
      gear = Gear.mount({page: 'video', host: {browser: header, mobile: header},
                         groups: [watching, looking, playback, text, Gear.std.zoom(), Gear.std.colours(), iface]});
    } catch (e) {
      try { console.error('[gear]', e); } catch (x) {}
      document.documentElement.classList.remove('pg-player');
      return;
    }
    document.documentElement.classList.add('pg-player');

    /* ---- Aa: the gear at its Text group, and again to put it away ----
       In the capture phase at the window, so that it is heard before the toolkit's own click-outside (which
       would shut an open panel and have it opened again) and before Parseh.typo's button (which would open
       its own panel).  Where the panel already stands at Text the next press shuts it; where it stands
       elsewhere -- or has been scrolled away from Text -- the press brings Text to the top. */
    var aaAt = null;
    function bodyScroll() {
      var b = document.querySelector('.pg-panel[data-pg-page="video"] .pg-body');
      return b ? b.scrollTop : 0;
    }
    function paintAa() {
      var on = gear.isOpen() && aaAt !== null;
      $('#typo').classList.toggle('on', on);
      $('#typo').setAttribute('aria-expanded', on ? 'true' : 'false');
    }
    window.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('#typo') : null;
      if (!a || !gear || Gear.mounted() !== gear) return;
      e.preventDefault(); e.stopImmediatePropagation();
      if (gear.isOpen() && aaAt !== null && Math.abs(bodyScroll() - aaAt) < 3) { gear.close(); return; }
      if (gear.open('text')) aaAt = bodyScroll();
      paintAa();
    }, true);
    gear.onToggle(function (up) {
      if (!up) aaAt = null;
      paintAa();
    });
  })();

  /* ---- THE VIDEO, FOR THE LAYERS OUTSIDE THIS SCRIPT (TO-DO §4.2) ----
     On a phone the narration's controls float at the foot of the screen --
     ↺, ⏯, ↻ and the speed -- and they are the book reader's (lib/narrctl.js),
     which drives a book's <audio> straight.  A video has no such element: it
     is YouTube's own frame, or a film of this machine behind the same six
     calls (the shim above).  So the page hands out exactly what a control
     needs and nothing it could break with.  The speeds are the player's own,
     since YouTube offers the ones it offers and nothing else.  */
  var stateFns = [];
  function saidState() {
    stateFns.forEach(function (fn) { try { fn(); } catch (e) {} });
  }
  var filmEl = null;
  function watchFilm() {
    var f = $('#film');
    if (!f || f === filmEl) return;
    filmEl = f;
    ['play', 'pause', 'ended', 'ratechange'].forEach(function (n) {
      f.addEventListener(n, saidState);
    });
  }

  /* ---- REVIEW LATER (a0.5.0) ----
     Flag a phrase while watching and go on; come back to the list later, to go to
     a phrase, make its card, test oneself or copy the list.  The flags are the
     PERSON's, kept by the toolbox (lib/later.js, lib/later.py) -- never written
     into the video -- and this is the video's side of them, which lives HERE, in
     the script, because the phrases (segs), the card sheet (openAnki, press) and
     the player's seek are private to it, and because the page is written by the
     server with this very script, so there is no older page to reach:
       - THE FOUR WAYS TO FLAG: the cloud's button «review later» (it reads «✓ marked»
         once set, and a second press takes the flag off); the L key, on the phrase the
         open cloud is for, else the phrase under the pointer, else a word saying to
         point at one first; and a held finger (lib/wordtouch.js asks
         window.ParsehLaterMark).  There is no pencil here to put a ⚑ beside.
       - THE LOOK: a dotted line in the accent under a flagged phrase (.later-mark,
         lib/later.css), in the transcript and in the subtitles copied over the picture.
       - THE DOOR, «⚑ later 3», in the header after the title; on a phone on the first
         line once something is flagged (lib/mobile.css).
       - A PHRASE IS FOUND BY WHAT IT IS: the caption by its start, the phrase in it by
         its place and its text; a caption whose start was moved (the timings sheet) by
         its own text.  The rest is adrift: listed, with ▶ and + card shut.
       - ▶ takes the video to the caption's start and plays it, with the caption in view
         and the phrase lit.  + card opens this sheet for the phrase; the flag leaves the
         list when the card is SAVED, on any of the three targets (press() says so).
     The video's record keeps what lib/later.js's flag has room for: the phrase, its
     reading, its transliteration, its meaning, its vocabulary line as plain text
     (vocText), the caption it is in, the caption's start and the phrase's place. */
  var LT = window.ParsehLater || null;
  var LATER_REF = LT ? (LT.refOf(location.pathname) || CFG.id || null) : null;
  var laterPanel = null, laterBtn = null, laterSession = null, laterCopied = false;
  var lpx = null, lpy = null, lmouse = false;
  function laterOn() { return !!(LT && LATER_REF); }
  function lnorm(s) {
    s = String(s == null ? '' : s);
    try { s = s.normalize('NFC'); } catch (e) {}
    return s.replace(/\s+/g, ' ').trim();
  }
  function laterSay(text, bad) { if (window.Parseh && Parseh.toast) Parseh.toast(text, !!bad); }
  // a phrase: the span of a caption's line, in the transcript or in a copy of it over the picture
  function laterPhrase(node) {
    var w = node && node.closest ? node.closest('.w') : null, line = w && w.closest('.seg');
    var sg = line && segs[+line.dataset.i], ch = sg && sg.chunks && sg.chunks[+w.dataset.j];
    return ch ? { sg: sg, ch: ch, w: w, i: +line.dataset.i, j: +w.dataset.j } : null;
  }
  function laterParts(sg, ch) {
    return { kind: 'video', ref: LATER_REF, lang: L.code, glossLang: G.code, title: vidTitle(),
             start: sg.start, j: (sg.chunks || []).indexOf(ch), cap: sg.text || '',
             text: ch.fa, kana: ch.kana || '', tr: ch.tr || '', en: ch.en || '',
             voc: vocText(ch.voc), sentence: sg.text || '' };
  }
  function laterId(sg, ch) {
    return LT.idFor({ kind: 'video', ref: LATER_REF, start: sg.start, j: (sg.chunks || []).indexOf(ch), text: ch.fa });
  }
  function laterMarked(sg, ch) { return !!(laterOn() && sg && ch && LT.has(laterId(sg, ch))); }
  /* FLAG IT, OR TAKE THE FLAG OFF -- what every way to flag does.  The flag taken off
     carries the list's «removed · Undo»; one made says so, since a phrase is flagged
     without breaking the pace of watching. */
  function laterToggle(sg, ch) {
    if (!laterOn() || !sg || !ch) return Promise.resolve(false);
    var rec;
    try { rec = LT.record(laterParts(sg, ch)); }
    catch (e) { laterSay('this phrase cannot be marked: ' + e.message, true); return Promise.resolve(false); }
    return LT.toggle(rec).then(function (on) {
      if (on) laterSay('marked to review later');
      return on;
    }, function (e) { laterSay('could not mark it: ' + (e && e.message), true); return false; });
  }
  // the cloud's button, drawn with the rest of the row (fillCloud)
  function laterButton(ch) {
    if (!laterOn() || !cloudCtx) return '';
    var on = laterMarked(cloudCtx.sg, ch);
    return '<button type="button" class="mklater' + (on ? ' on' : '') + '" aria-pressed="' + (on ? 'true' : 'false') +
           '" title="' + (on ? 'this phrase is on your review later list: press to take it off'
                             : 'flag this phrase to come back to it later (L)') + '">' +
           (on ? '✓ marked' : 'review later') + '</button>';
  }

  /* WHERE A FLAGGED PHRASE IS: the caption that starts when it did, the phrase of its
     place if its text is still the flag's, else the phrase of the same text nearest to
     that place; else, for a caption whose start has moved, the caption of the same text. */
  function laterPick(sg, j, want) {
    var cs = sg.chunks || [];
    if (cs[j] && lnorm(cs[j].fa) === want) return j;
    var best = -1, gap = 1e9;
    cs.forEach(function (c, k) {
      if (lnorm(c.fa) !== want) return;
      var d = Math.abs(k - j);
      if (d < gap) { best = k; gap = d; }
    });
    return best;
  }
  function laterFind(rec, byStart) {
    var w = rec.where || {}, want = lnorm(rec.text), at = w.start || 0, j, i, hit = null;
    var near = byStart ? (byStart[Math.round(at * 1000)] || []) : null;
    for (var n = 0; n < (near ? near.length : segs.length); n++) {
      i = near ? near[n] : n;
      if (!near && Math.abs(segs[i].start - at) > 0.01) continue;
      j = laterPick(segs[i], w.j || 0, want);
      if (j >= 0) return { i: i, j: j, sg: segs[i], ch: segs[i].chunks[j] };
    }
    var cap = lnorm(w.text), gap = 1e9;
    if (cap) segs.forEach(function (sg, k) {
      if (lnorm(sg.text) !== cap) return;
      var jj = laterPick(sg, w.j || 0, want), d = Math.abs(sg.start - at);
      if (jj >= 0 && d < gap) { gap = d; hit = { i: k, j: jj, sg: sg, ch: sg.chunks[jj] }; }
    });
    return hit;
  }
  // the transcript has been read (a flag is asked about before the captions arrive, and waits for them)
  function laterLoaded() {
    if (segs.length) return Promise.resolve();
    return new Promise(function (done) {
      var tries = 0;
      (function look() { if (segs.length || tries++ > 100) done(); else setTimeout(look, 100); })();
    });
  }

  /* THE MARKS, kept in step with the store, with the transcript as it is drawn and with
     the subtitles copied over the picture */
  function laterPaint() {
    if (!laterOn()) return;
    var recs = LT.list({ ref: LATER_REF }), want = [], byStart = {};
    if (recs.length) segs.forEach(function (sg, i) { (byStart[Math.round(sg.start * 1000)] = byStart[Math.round(sg.start * 1000)] || []).push(i); });
    recs.forEach(function (rec) {
      var hit = laterFind(rec, byStart);
      if (!hit) return;
      Array.prototype.forEach.call(document.querySelectorAll('.seg[data-i="' + hit.i + '"] .w[data-j="' + hit.j + '"]'),
                                   function (e) { want.push(e); });
    });
    var keep = new Set(want);
    Array.prototype.forEach.call(document.querySelectorAll('.later-mark'), function (e) {
      if (!keep.has(e)) e.classList.remove('later-mark');
    });
    want.forEach(function (e) { e.classList.add('later-mark'); });
    // and the cloud, if it is open, says where its phrase stands
    var b = cloud.querySelector('.mklater');
    if (b && cloudCtx) {
      var on = laterMarked(cloudCtx.sg, cloudCtx.ch);
      b.textContent = on ? '✓ marked' : 'review later';
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.title = on ? 'this phrase is on your review later list: press to take it off'
                   : 'flag this phrase to come back to it later (L)';
    }
  }
  var laterFlashTimer = 0, laterFlashed = [];
  function laterFlash(hit) {
    clearTimeout(laterFlashTimer);
    laterFlashed.forEach(function (e) { e.classList.remove('later-flash'); });
    laterFlashed = Array.prototype.slice.call(document.querySelectorAll('.seg[data-i="' + hit.i + '"] .w[data-j="' + hit.j + '"]'));
    laterFlashed.forEach(function (e) { e.classList.add('later-flash'); });
    laterFlashTimer = setTimeout(function () {
      laterFlashed.forEach(function (e) { e.classList.remove('later-flash'); });
      laterFlashed = [];
    }, 1600);
  }
  function laterGo(rec) {
    return laterLoaded().then(function () {
      var hit = laterFind(rec);
      if (!hit) {
        if (laterPanel) laterPanel.refresh();
        throw new Error('this phrase is no longer where it was');
      }
      // the caption in view and the phrase lit, and the video at its start, playing
      if (els[hit.i]) els[hit.i].scrollIntoView({ behavior: 'auto', block: 'center' });
      laterFlash(hit);
      seek(hit.sg.start);
    });
  }
  function laterLabel(rec) {
    var w = rec.where || {}, at = w.start || 0, name = '';
    for (var i = 0; i < segs.length && segs[i].start <= at + 0.01; i++) if (segs[i].chapter) name = segs[i].chapter;
    return fmt(at) + (name ? ' · ' + name : '');
  }

  /* THE CARD SHEET for a flag, and how it ended (lib/later-cards.js asks): saved on any of its
     three targets (press() tells laterPressDone), or shut without a card (closeAnki tells
     laterSheetShut) -- except that a sheet shut while its answer is still out ends when the
     answer comes. */
  function laterNewSession(seq) {
    var s = { seq: seq, over: false, late: false, box: A.box };
    s.done = new Promise(function (resolve) {
      s.finish = function (how) {
        if (s.over) return;
        s.over = true;
        if (laterSession === s) laterSession = null;
        resolve(how);
      };
    });
    s.close = function () { if (ankiOpen && sheetSeq === seq) closeAnki(); };
    return s;
  }
  function laterPressDone(seq, target, ok) {
    var s = laterSession;
    if (!s || s.seq !== seq) return;
    var saved = ok === true && (target !== 'md' || laterCopied);
    if (saved) s.finish('saved');
    else if (s.late) s.finish('closed');
  }
  function laterSheetShut() {
    var s = laterSession;
    if (!s) return;
    if (busyFor === s.seq) s.late = true; else s.finish('closed');
  }
  function laterOpenSheet(rec) {
    return laterLoaded().then(function () {
      var hit = laterFind(rec);
      if (!hit) { if (laterPanel) laterPanel.refresh(); return null; }
      if (laterSession) laterSession.finish('closed');
      openAnki(hit.ch.fa, hit.ch, hit.sg, undefined, { i: hit.i, j: hit.j, k: null, line: '' });
      laterSession = laterNewSession(sheetSeq);
      return laterSession;
    });
  }

  /* THE L KEY, heard first of all, on the window: the phrase the open cloud is for, else
     the phrase under the pointer, else a word saying what to do.  Not while a field has the
     keys, a sheet is over the page, or a modifier is down -- and it is the one single-letter
     key this page has. */
  window.addEventListener('pointermove', function (e) {
    if (e.pointerType && e.pointerType !== 'mouse') return;
    lmouse = true; lpx = e.clientX; lpy = e.clientY;
  }, { passive: true, capture: true });
  window.addEventListener('keydown', function (e) {
    if ((e.key !== 'l' && e.key !== 'L') || e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
    if (!laterOn()) return;
    var t = e.target;
    if (t && t.closest && t.closest('input, textarea, select, [contenteditable], .lp-wrap')) return;
    if (ankiOpen || editing || dvOn || vmOpen || ntOn || dsheet) return;
    var at = null;
    if (cloudFor && cloudCtx && !cloud.hidden) at = { sg: cloudCtx.sg, ch: cloudCtx.ch };
    else if (lmouse && lpx !== null) at = laterPhrase(document.elementFromPoint(lpx, lpy));
    e.preventDefault();
    if (!at) { laterSay('point at a phrase first, then press L'); return; }
    laterToggle(at.sg, at.ch);
  }, true);
  // a held finger: lib/wordtouch.js adds «Review later: “…”» to its menu if this says it can
  window.ParsehLaterMark = {
    can: function (unit) { return laterOn() && !!laterPhrase(unit); },
    marked: function (unit) { var p = laterPhrase(unit); return !!(p && laterMarked(p.sg, p.ch)); },
    toggle: function (unit) { var p = laterPhrase(unit); return p ? laterToggle(p.sg, p.ch) : Promise.resolve(false); }
  };

  /* THE LIST: the panel lib/later.js draws for this video, and its door in the header */
  function laterAdapter() {
    return {
      kind: 'video', ref: LATER_REF, title: vidTitle(), lang: L.code, glossLang: G.code,
      // never on a phone
      canCard: function () { return !mobileNow(); },
      locate: function (rec) { return laterLoaded().then(function () { return { found: !!laterFind(rec) }; }); },
      goTo: laterGo,
      label: laterLabel,
      makeCard: function (rec) {
        return window.ParsehLaterCards ? ParsehLaterCards.one(laterOpenSheet, rec)
                                       : Promise.reject(new Error('cards are not available here'));
      },
      queue: function (recs) {
        return window.ParsehLaterCards ? ParsehLaterCards.queue({ records: recs, open: laterOpenSheet })
                                       : Promise.reject(new Error('cards are not available here'));
      }
    };
  }
  // «⚑ later 3»: always in the browser layout; on a phone once there is something flagged, since the
  // first line of a phone's header holds targets of a finger's size and counts them
  function laterDoor() { if (laterBtn) laterBtn.hidden = mobileNow() && LT.count({ ref: LATER_REF }) === 0; }
  /* ONE LINK OPENS THE VIDEO AT A PHRASE: <player>#later=<id>, from the page that lists every
     flag.  The list opens on that flag and the video goes to its caption -- once the transcript
     is drawn and the player is ready (or has been waited for long enough). */
  function laterFromLink() {
    var id = LT.fromHash();
    if (!id) return;
    LT.ready().then(function () {
      var rec = LT.get(id);
      if (!rec || rec.ref !== LATER_REF) { laterSay('that phrase is no longer on your review later list', true); return; }
      var tries = 0;
      (function go() {
        if (!(segs.length && (ready || tries > 80)) && tries++ < 200) { setTimeout(go, 100); return; }
        laterPanel.open({ id: id });
        laterGo(rec).catch(function () {});
      })();
    });
  }
  (function laterStart() {
    if (!laterOn()) return;
    laterPanel = LT.panel(laterAdapter());
    laterBtn = laterPanel.button;
    var ttl = document.querySelector('header .ttl'), hd = document.querySelector('header');
    if (ttl && ttl.parentNode) ttl.parentNode.insertBefore(laterBtn, ttl.nextSibling);
    else if (hd) hd.appendChild(laterBtn);
    laterDoor();
    LT.on('change', function (d) {
      if (d && d.ref && d.ref !== LATER_REF) return;
      laterDoor();
      laterPaint();
    });
    LT.ready().then(function () { laterDoor(); laterPaint(); });
    if (window.Parseh && Parseh.mode && Parseh.mode.onChange) Parseh.mode.onChange(laterDoor);
    laterFromLink();
  })();

  window.ParsehPlayer = {
    later: { panel: function () { return laterPanel; }, find: laterFind, toggle: laterToggle, paint: laterPaint,
             go: laterGo, record: function (node) { var p = laterPhrase(node); return p ? laterParts(p.sg, p.ch) : null; } },
    kind: function () { return CFG.media ? 'film' : 'youtube'; },
    typo: typoApi,
    ready: function () { return !!(player && ready); },
    paused: function () {
      try { return !player || !ready || player.getPlayerState() !== 1; } catch (e) { return true; }
    },
    play: function () { watchFilm(); if (player && ready) { player.playVideo(); saidState(); } },
    pause: function () { if (player && ready) { player.pauseVideo(); saidState(); } },
    time: function () { try { return player.getCurrentTime() || 0; } catch (e) { return 0; } },
    duration: function () { try { return player.getDuration() || 0; } catch (e) { return 0; } },
    seek: function (t) {
      if (!(player && ready)) return;
      var end = 0;
      try { end = player.getDuration() || 0; } catch (e) {}
      try { player.seekTo(Math.max(0, end ? Math.min(t, end - 0.1) : t), true); } catch (e) {}
    },
    rate: function () { try { return player.getPlaybackRate() || 1; } catch (e) { return 1; } },
    setRate: function (r) {
      try { player.setPlaybackRate(r); } catch (e) {}
      saidState();
    },
    // what this player will actually play at: YouTube's own list where it
    // says one, and a film's anything
    rates: function () {
      try {
        var list = player.getAvailablePlaybackRates && player.getAvailablePlaybackRates();
        if (list && list.length) return list.slice();
      } catch (e) {}
      return null;
    },
    onChange: function (fn) {
      stateFns.push(fn); watchFilm();
      // and a way to stop listening, for the gear's rows, which come and go
      return function () { var k = stateFns.indexOf(fn); if (k >= 0) stateFns.splice(k, 1); };
    },
    // the video's own size (the bar under it, and the gear's «Video size»)
    size: videoSize,
    /* THE SUBTITLE OVER A VIDEO ON THE WHOLE SCREEN (lib/mobileplayer.js).
       The line laid over the picture is a COPY of the caption being said, and
       a copy carries none of the listeners this page hung on each phrase as it
       drew it -- so a tap on a copied phrase glossed nothing, and the one
       thing the whole screen was for had never worked.  Here the layer says
       which caption and which phrase its copy is, and hands the copy itself as
       the thing to hang the cloud on: the gloss opens against the subtitle,
       under the finger, and not against a transcript the video is covering. */
    /* `hover`: a mouse come to rest on the phrase, as the transcript's own
       phrases answer one -- it opens the cloud and leaves it open, where a
       tap on the phrase whose cloud is open closes it again. */
    gloss: function (i, j, at, hover) {
      var sg = segs[i], ch = sg && sg.chunks && sg.chunks[j];
      if (!ch || !at) return false;
      if (cloudFor === at) {
        if (hover) clearTimeout(hideTimer); else closeCloud();
        return true;
      }
      openCloud(at, ch, sg);
      return true;
    },
    ungloss: function () { closeCloud(); },
    // the mouse gone off a phrase: the cloud goes after the transcript's own
    // grace, which the pointer travelling into the cloud cancels
    unglossSoon: function () { scheduleClose(); }
  };
  watchFilm();
})();
