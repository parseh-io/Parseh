// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — THE GEAR, ⚙ page: the one panel every page opens for the settings
   of the page it is on (a0.5.0, plan §2 and §9).

   Until now each page kept its settings wherever they were first put: the Aa
   panel in the readers, a toolbar of sliders in a document, the pass buttons
   in a reader's header, a ⋯ menu on a phone.  A person looking for "how big is
   the text" or "how fast does it play" had to know which of them held it.
   This is the one place: a button in the page's bar, a panel under it (on a
   phone, a sheet from the foot of the screen), and in the panel every control
   of the page as a ROW -- a name, ONE sentence that says what it does, and
   the control -- under a group that says where its settings are kept.

   IT IS A TOOLKIT, NOT A PAGE.  A page (its ADAPTER, written beside the page's
   own code) hands in a declarative `spec` of groups and rows and the toolkit
   draws the button and the panel, keeps every row in step with the page, and
   never hides or replaces a control of the page's own: the page keeps its
   originals in the DOM, so every handler it has goes on working.  The one
   thing it moves is what a `node` row names (below), and only while the panel
   is up.

   THE API, all of it (the contract of plan §9, and the four additions the
   integrator made to it on 2026-10-06: node, indent, mounted(), unmount()):

     var gear = ParsehGear.mount(spec)       once per page; a second mount replaces the first
     spec = { page:   'book' | 'video' | 'doc' | 'edit' | 'deck' | 'study' | 'cram',
              host:   { browser: Element | () => Element|null,       where the BUTTON is appended,
                        mobile:  Element | () => Element|null },     one host for each layout
              mobileMode: () => bool        default: Parseh.mode.isMobile(), else parseh_mode
              onMode:     fn => unsubscribe default: Parseh.mode.onChange, else the storage event,
                                            the parseh:mode event and <html data-mode>
              titles: { title: 'This page', first: 'Only for this page.',
                        foot: { text, href } | false },             the three defaults are these
              groups: [Group] }
     Group = { id, title, caption, when?, layouts?: 'both'|'browser'|'mobile', summary?, rows: [Row] }
     Row   = { id, kind, label, help, when?, layouts?, kept?: 'device'|'you', indent?: 1, short?,
               disabled?: (above) => false | 'the reason, printed under the row', ...by kind }

       switch   { get(): bool, set(bool), watch?(cb) -> unwatch }         <button role=switch>
       choice   { options: [{value, label, help?}], get(), set(v), watch? }
                                       a radiogroup of chips when there are four short options or fewer,
                                       otherwise a <select>
       slider   { min, max, step, unit?, format?(v), get(), set(v), watch? }
       stepper  { values: [..], get(), set(v), can(dir) -> true|'reason', format?(v),
                  reset?(), resetLabel? }                                 the zoom: [−] 100 % [+]
       levels   { items: () => [{key, name, def, help, shown}], setShown(key, bool),
                  setName(key, str|''), watch? }                          checkbox + name field + help
       link     { href, label, newTab? } | { onClick, label }
       buttons  { items: [{label, title?, onClick, pressed?(): bool}], watch? }
       action   { label, onClick }
       note     { text }
       node     { el: Element | () => Element|null }     label and help are optional for this kind

     gear = { open(groupId?), close(), toggle(), isOpen(), refresh(), onToggle(fn), button, unmount(),
              stage(), back() }
     ParsehGear.mounted()    the gear in force, or null

   THE PHONE'S SHEET HAS TWO STAGES (a0.5.4).  It opens on an INDEX: one row per
   group (a "theme"), the theme's name and, under it, one line that says what it
   is set to now -- its SUMMARY.  A tap on a row slides the sheet to that theme
   alone (‹ and the back gesture return).  The popover on a wide window is one
   list and has no index.  The API above reads on a sheet as:
     open(groupId)   the index underneath, the theme on stage, its first control focused;
                     open() with no group opens the index, or leaves the stage as it is
                     where the sheet is already up.  On the popover: scrolled to the group.
     stage()         'index' | <groupId> while the sheet is up; null on the popover or shut
     back()          the ‹: from a theme to the index (true), from the index nothing (false)
   SUMMARY: `Group.summary` is a string or a function read at every refresh, or
   an array of parts (a string, or { bdi: 'a name that may read right to left' });
   where it is given it is the summary.  Otherwise the toolkit joins with " · ", in
   row order and over the rows that are drawn: a choice's chosen label; a slider's
   and a stepper's value (format(v) where given); the ticked names of a levels row,
   joined with ", " (each in a <bdi>); the pressed buttons' labels; and a switch's
   `short` -- "one to three words naming the row in a summary" -- where the switch
   is ON.  A row without `short`, and a link, an action, a note and a node, say
   nothing.  The line is chrome (English, left to right); a name inside it is not.

   NODE: a control that another layer owns -- lib/keep.js's "Keep on this
   phone" buttons (`.kp-btn`) on the phone's sheet -- is MOVED into the row
   while the panel is up (when it is opened, and on every refresh while it
   stays open) and put back where it was, the same parent and the same next
   sibling, when the panel closes, when the row stops being drawn (its layout is
   gone, its when() is false) and when the gear is unmounted.  It is the same
   element all the while, so its own handlers go on working; where el() answers
   null the row is not drawn.  Give the row `layouts` where the element is only
   there in one of them.

   INDENT: `indent: 1` draws the row hanging under the row drawn above it (the
   dictionary, its definitions, their translation: `indent: 2` for the third),
   and calls its disabled(above) with whether the row above is ON when that row
   is a switch (true or false), else with undefined -- so a row under a switch
   that is off can say why it rests without reading the page's state itself.

   MOUNTED, UNMOUNTED: ParsehGear.mounted() answers the handle in force or
   null, and `document` gets a CustomEvent `parseh:gear` whose detail is
   'mounted' or 'unmounted' -- the layers that drew their own ⋯ menu and Aa
   panel (lib/mobilereader.js, lib/mobileplayer.js, Parseh.typo) ask when they
   start and listen after, and stand down while there is a gear.  A second
   mount replaces the first with no 'unmounted' between: there is a gear all
   the while.  gear.unmount() closes the panel, sends every borrowed node home,
   takes the button and the panel out of the page and lets every watch go.

   AND THREE STANDARD GROUPS, so every page has the same three whatever it is
   built on: ParsehGear.std.zoom(), .colours({apply}) and .interface().

   WHAT THE LAYER ADDS BESIDES (all of it optional, none of it needed to use
   it): `label`, `help`, `caption` and `title` may be functions, read at every
   refresh (a row named after the book's language); a stepper's `values` may be
   a function, and it may carry `def` (the value its reset goes back to: the
   reset button rests while it is already there) and `info()` (a sentence
   printed under it); a levels item may carry `lang` and `disabled` (a reason,
   printed under the row); a note's `text` may be a function; gear.destroy() is
   gear.unmount(); gear.onToggle(fn) gives back a function that takes fn off;
   <html> wears the class pg-open while the panel is up (and pg-sheet while it
   is the phone's sheet); a Row of any kind named in `kept` wears a small tag
   where the group's caption is mixed.

   IT LOADS IN BOTH WORLDS, as lib/explain.js does: the toolbox's pages (the
   readers, the player, the hub) have lib/parseh.js, and the studio's pages (a
   document, the editor, the decks) do not.  So nothing here needs `Parseh`:
   where it is there the toolkit uses it (the theme, the mode), and where it is
   not it does the same work itself.  The panel is built with createElement and
   textContent and nothing else (a row's words may come from a book).  Its
   rules are lib/pagesettings.css, which this file links itself, from beside
   itself, whichever address it was loaded by -- so a page needs the one tag.
   (Both files are on the web because serve.py's STATIC_FILES names them, and
   on a phone because lib/offline.py's SHARED does; tests/test_page_gear.py
   holds both lists to it.)

   THE LOOK, and what the owner asked of it: every row says WHAT it is in a name
   and WHAT IT DOES in a sentence, both visible (never a tooltip alone); every
   group says where its settings are kept; nothing a newcomer could not follow.
   Wide screens get a popover under the button; a phone (the mobile layout, or a
   window of 560px or less) gets ONE sheet, half the screen high, with the page
   visible and usable above it, so a change shows at once -- or, if the person
   wants it, TALL (the window less 48px): a drag up on the head, or a tap on the
   grab line, and the choice is remembered on this device (parseh_gear_tall).
   Rows are 48px high on a phone.  The chrome is always English and left to right (like the
   readers' header and the dictionary's sheet); only a level's name field takes
   the direction of what is typed in it.

   HISTORY: the sheet pushes one entry on opening (so the back gesture closes it)
   and a second on entering a theme (so the gesture leaves the theme first); an
   entry the sheet spent itself -- ‹, ✕, Esc, a swipe -- is never heard as a gesture.

   KEYS: a key typed in the panel goes no further than the panel -- a reader
   plays on Space and moves on the arrows on any element but a text box, and
   must not do either for a switch -- and Escape closes the panel (the whole
   sheet, whichever stage it is on) and is not heard by the page at all; Space and Enter on the button are the button's
   own.  A key typed anywhere else on the page while the popover is up is the
   page's, except Escape, which closes the popover and is spent on it. */
(function () {
  'use strict';
  if (window.ParsehGear) return;

  /* WHERE THE STYLES ARE, found NOW: document.currentScript is this script
     while it runs and nothing a moment later. */
  var me = document.currentScript;
  var HERE = me && me.src ? me.src : '';
  var CSS_HREF = /pagesettings\.js(?=[?#]|$)/.test(HERE)
    ? HERE.replace(/pagesettings\.js(?=[?#]|$)/, 'pagesettings.css') : '/lib/pagesettings.css';

  var DEFAULT_TITLES = {
    title: 'This page',
    first: 'Only for this page.',
    foot: { text: "Parseh's own settings (network, updating, dictionaries)", href: '/settings/' }
  };
  var BUTTON_TITLE = 'Settings of this page: how it looks, how it reads, how it zooms';
  var BUTTON_LABEL = 'Settings of this page';
  var SHEET_MAX = 560;       // a window this narrow or narrower gets the sheet
  var POP_W = 380;           // the popover's width, where the window has the room
  var KEPT = { device: 'on this device', you: 'follows you' };
  var HIST = 'parsehGear';   // the history entry the sheet pushes (as Parseh.dictSheet's own)
  var NAME_MAX = 12;         // characters in a level's name
  var TALL_KEY = 'parseh_gear_tall';  // "1" where the sheet is to rest tall, absent where half
  var HALF_PCT = 55;         // the sheet's resting height, in percent of the window's
  var SHEET_GAP = 48;        // what the tall sheet leaves of the page above it
  var SHEET_FLOOR = 240;     // the half sheet's floor, for a phone held sideways
  var ROW_H = 56, ROW_TIGHT = 50, HEAD_H = 50;  // an index row; one that must be squeezed; the head, border and all

  var current = null;        // the one mount
  var counter = 0;           // ids stay unique across a replaced mount

  /* ---------------------------------------------------------------- helpers */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function attrs(e, a) {
    for (var k in a) if (Object.prototype.hasOwnProperty.call(a, k)) e.setAttribute(k, a[k]);
    return e;
  }
  function warn(e) { try { console.error('[ParsehGear]', e); } catch (x) {} }
  /* A page's own function is called inside a try: a handler that throws must
     not take the whole panel with it, and the next row is still drawn */
  function safe(fn, a, b) {
    if (typeof fn !== 'function') return undefined;
    try { return fn(a, b); } catch (e) { warn(e); return undefined; }
  }
  // a string given as itself or as a function that makes it
  function words(v) {
    var s = typeof v === 'function' ? safe(v) : v;
    return s === undefined || s === null || s === false ? '' : String(s);
  }
  function truthy(fn) { return typeof fn !== 'function' ? true : !!safe(fn); }
  function same(a, b) {
    if (a === b) return true;
    if (a === undefined || a === null || b === undefined || b === null) return false;
    return String(a) === String(b);
  }
  function list(v) {
    var l = typeof v === 'function' ? safe(v) : v;
    return Object.prototype.toString.call(l) === '[object Array]' ? l : [];
  }
  function round(v) { return Math.round(v * 100) / 100; }
  function pathOf(ev) {
    try { if (ev.composedPath) return ev.composedPath(); } catch (e) {}
    var p = [], n = ev.target;
    while (n) { p.push(n); n = n.parentNode; }
    return p;
  }
  // a name cut to NAME_MAX characters, counted as people count them and not as UTF-16 does
  function cut(s) {
    var a = Array.prototype.slice.call(String(s));
    try { a = Array.from(String(s)); } catch (e) {}
    return a.length > NAME_MAX ? a.slice(0, NAME_MAX).join('') : String(s);
  }
  function vw() { return document.documentElement.clientWidth || window.innerWidth; }
  function vh() { return document.documentElement.clientHeight || window.innerHeight; }
  function drawn(e) { return !!(e && e.getClientRects && e.getClientRects().length); }

  /* ------------------------------------------------------- the stylesheet */
  /* Requested the moment this script runs, so it is on its way before a page
     mounts; the button is held back until it is in (see mount) rather than
     drawn bare for a moment. */
  var styleLink = null, styleDone = false, styleWait = [];
  function styleSettled() {
    if (styleDone) return;
    styleDone = true;
    var w = styleWait; styleWait = [];
    for (var i = 0; i < w.length; i++) { try { w[i](); } catch (e) {} }
  }
  function styleLoad() {
    if (styleLink) return;
    var have = document.querySelector('link[data-pg-style]');
    styleLink = have || el('link');
    if (!have) {
      styleLink.rel = 'stylesheet';
      styleLink.href = CSS_HREF;
      styleLink.setAttribute('data-pg-style', '');
      (document.head || document.documentElement).appendChild(styleLink);
    }
    if (styleLink.sheet) { styleSettled(); return; }
    styleLink.addEventListener('load', styleSettled);
    styleLink.addEventListener('error', styleSettled);
    // and never for ever: a stylesheet that never comes leaves the page as it was
    setTimeout(styleSettled, 4000);
  }
  styleLoad();

  /* ------------------------------------------------- the mode, and the theme */
  function storedMode() {
    var m = null;
    try { m = localStorage.getItem('parseh_mode'); } catch (e) {}
    if (m !== 'browser' && m !== 'mobile') {
      var c = null;
      try { c = /(?:^|;\s*)parseh_mode=(browser|mobile)(?:;|$)/.exec(document.cookie || ''); } catch (e) {}
      m = c ? c[1] : 'browser';
    }
    return m;
  }
  function defaultMobile() {
    var P = window.Parseh;
    if (P && P.mode && typeof P.mode.isMobile === 'function') {
      try { return !!P.mode.isMobile(); } catch (e) {}
    }
    return storedMode() === 'mobile';
  }
  /* fn() after the mode may have changed, wherever it was changed: by this
     toolkit, by the page's own switch, in another tab.  Several signals,
     because the studio's pages have no Parseh.mode to ask. */
  function defaultOnMode(fn) {
    var P = window.Parseh;
    if (P && P.mode && typeof P.mode.onChange === 'function') return P.mode.onChange(fn);
    var h = function (e) { if (!e || !e.key || e.key === 'parseh_mode') fn(); };
    window.addEventListener('storage', h);
    document.addEventListener('parseh:mode', fn);
    window.addEventListener('parseh:mode', fn);
    var mo = null;
    if (window.MutationObserver) {
      mo = new MutationObserver(fn);
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-mode'] });
    }
    return function () {
      window.removeEventListener('storage', h);
      document.removeEventListener('parseh:mode', fn);
      window.removeEventListener('parseh:mode', fn);
      if (mo) mo.disconnect();
    };
  }
  function setMode(m) {
    if (m !== 'browser' && m !== 'mobile') return;
    var P = window.Parseh, S = window.ParsehStudioMode;
    if (P && P.mode && typeof P.mode.set === 'function') { P.mode.set(m); return; }
    // the studio's own switch does more than write the value (it registers the
    // worker the installed app lives by), so it is asked first where it is there
    if (S && typeof S.set === 'function') safe(S.set, m);
    else {
      try { localStorage.setItem('parseh_mode', m); } catch (e) {}
      try { document.cookie = 'parseh_mode=' + m + '; Path=/; SameSite=Lax; Max-Age=31536000'; } catch (e) {}
      document.documentElement.setAttribute('data-mode', m);
    }
    try { document.dispatchEvent(new CustomEvent('parseh:mode', { detail: { mode: m } })); } catch (e) {}
  }
  var THEMES = ['auto', 'light', 'dark', 'sepia'];
  function getTheme() {
    var P = window.Parseh;
    if (P && P.theme && typeof P.theme.get === 'function') {
      var t = safe(P.theme.get);
      if (THEMES.indexOf(t) >= 0) return t;
    }
    var s = null;
    try { s = localStorage.getItem('parseh_theme'); } catch (e) {}
    return THEMES.indexOf(s) >= 0 ? s : 'auto';
  }
  function setTheme(t, apply) {
    if (THEMES.indexOf(t) < 0) return;
    var P = window.Parseh;
    if (P && P.theme && typeof P.theme.set === 'function') P.theme.set(t);
    else {
      try { localStorage.setItem('parseh_theme', t); } catch (e) {}
      if (t === 'auto') document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', t);
    }
    if (typeof apply === 'function') safe(apply, t);
  }
  function watchTheme(cb) {
    var h = function (e) { if (!e || !e.key || e.key === 'parseh_theme') cb(); };
    window.addEventListener('storage', h);
    var mos = [];
    if (window.MutationObserver) {
      [document.documentElement, document.body].forEach(function (n) {
        if (!n) return;
        var mo = new MutationObserver(cb);
        mo.observe(n, { attributes: true, attributeFilter: ['data-theme'] });
        mos.push(mo);
      });
    }
    return function () {
      window.removeEventListener('storage', h);
      mos.forEach(function (m) { m.disconnect(); });
    };
  }

  /* ================================================================ the kinds
     Each builds the CONTROL of one kind of row and answers
       { ctl, place, update(off) -> reason|undefined, state?(), has?(), away?() }
     `ctl` is the element; `place` says where it goes in the row ('side': at
     the right of the name; 'below': under the sentence; 'above': before it;
     'only': the row is nothing else); `update(off)` redraws it from the
     page's own answers, and the row hands it `off` -- false, or a reason, or
     true -- so a disabled row greys its control and a kind may add a reason
     of its own (a stepper that is at its end).  `state()` says whether the row
     is on, for the row under it to read (a switch); `has()` says there is
     anything to draw (a node whose element is not there yet is no row);
     `away()` is told the row is not drawn or the panel is shut. */
  var KINDS = {};

  KINDS['switch'] = function (row, x) {
    var b = attrs(el('button', 'pg-switch'), {
      type: 'button', role: 'switch', 'aria-checked': 'false',
      'aria-labelledby': x.nameId, 'aria-describedby': x.helpId + ' ' + x.whyId });
    var track = el('span', 'pg-track');
    track.appendChild(el('span', 'pg-knob'));
    b.appendChild(track);
    b.addEventListener('click', function () {
      if (b.disabled) return;
      safe(row.set, b.getAttribute('aria-checked') !== 'true');
      x.changed();
    });
    // the words beside it are part of the target: a click on the sentence does what a click on the switch does
    x.text.addEventListener('click', function () { if (!b.disabled) b.click(); });
    return {
      ctl: b, place: 'side',
      state: function () { return !!safe(row.get); },
      update: function (off) {
        b.setAttribute('aria-checked', safe(row.get) ? 'true' : 'false');
        b.disabled = !!off;
      }
    };
  };

  KINDS.choice = function (row, x) {
    var opts = list(row.options), uses = 0, short = opts.length <= 4;
    opts.forEach(function (o) {
      var n = String(o.label).length;
      uses += n;
      if (n > 18) short = false;
    });
    if (uses > 40) short = false;
    var box = el('div', 'pg-choice'), said = el('div', 'pg-opthelp');
    said.setAttribute('aria-live', 'polite');
    var ctl, controls = [];
    if (short) {
      ctl = attrs(el('div', 'pg-chips'), { role: 'radiogroup', 'aria-labelledby': x.nameId,
                                           'aria-describedby': x.helpId + ' ' + x.whyId });
      opts.forEach(function (o, i) {
        var c = attrs(el('button', 'pg-chip', o.label), { type: 'button', role: 'radio',
                                                            'aria-checked': 'false', tabindex: '-1' });
        c.addEventListener('click', function () { if (!c.disabled) choose(i, false); });
        ctl.appendChild(c);
        controls.push(c);
      });
      // ARROWS move and choose, as a radio group's do; Space and Enter are the button's own
      ctl.addEventListener('keydown', function (e) {
        var at = controls.indexOf(document.activeElement), n = controls.length, to = -1;
        if (at < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') to = (at + 1) % n;
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') to = (at + n - 1) % n;
        else if (e.key === 'Home') to = 0;
        else if (e.key === 'End') to = n - 1;
        if (to < 0) return;
        e.preventDefault();
        choose(to, true);
      });
    } else {
      ctl = attrs(el('select', 'pg-select'), { 'aria-labelledby': x.nameId,
                                               'aria-describedby': x.helpId + ' ' + x.whyId });
      opts.forEach(function (o, i) { ctl.appendChild(attrs(el('option', null, o.label), { value: String(i) })); });
      ctl.addEventListener('change', function () { choose(parseInt(ctl.value, 10), false); });
      controls.push(ctl);
    }
    function choose(i, focus) {
      var o = opts[i];
      if (!o) return;
      safe(row.set, o.value);
      x.changed();
      if (focus && controls[i]) { try { controls[i].focus(); } catch (e) {} }
    }
    box.appendChild(ctl);
    box.appendChild(said);
    return {
      ctl: box, place: 'below',
      update: function (off) {
        var cur = safe(row.get), at = -1;
        opts.forEach(function (o, i) { if (at < 0 && same(o.value, cur)) at = i; });
        if (short) {
          controls.forEach(function (c, i) {
            c.setAttribute('aria-checked', i === at ? 'true' : 'false');
            c.tabIndex = i === at || (at < 0 && i === 0) ? 0 : -1;
            c.disabled = !!off;
          });
        } else {
          // a value the list does not hold (a speed set by a key) is shown rather than hidden
          var stray = ctl.querySelector('option[data-pg-stray]');
          if (stray) ctl.removeChild(stray);
          if (at < 0 && cur !== undefined && cur !== null) {
            stray = attrs(el('option', null, String(cur)), { value: 'x', 'data-pg-stray': '' });
            ctl.appendChild(stray);
            ctl.value = 'x';
          } else ctl.value = at < 0 ? '' : String(at);
          ctl.disabled = !!off;
        }
        said.textContent = at >= 0 && opts[at].help ? opts[at].help : '';
      }
    };
  };

  KINDS.slider = function (row, x) {
    var box = el('div', 'pg-slide');
    var inp = attrs(el('input', 'pg-range'), {
      type: 'range', min: String(row.min), max: String(row.max), step: String(row.step || 1),
      id: x.id + '-i', 'aria-labelledby': x.nameId, 'aria-describedby': x.helpId + ' ' + x.whyId });
    var out = attrs(el('output', 'pg-out'), { 'for': x.id + '-i' });
    function show(v) {
      var t = typeof row.format === 'function' ? words(function () { return row.format(v); })
                                               : round(v) + (row.unit || '');
      out.textContent = t;
      inp.setAttribute('aria-valuetext', t);
    }
    inp.addEventListener('input', function () {
      var v = parseFloat(inp.value);
      if (!isFinite(v)) return;
      show(v);
      safe(row.set, v);
      x.changed();
    });
    box.appendChild(inp);
    box.appendChild(out);
    return {
      ctl: box, place: 'below',
      update: function (off) {
        var v = Number(safe(row.get));
        if (!isFinite(v)) v = Number(row.min);
        // not rewritten while it says the same: a thumb under a finger must not be moved from under it
        if (Math.abs(parseFloat(inp.value) - v) > 1e-9) inp.value = String(v);
        show(parseFloat(inp.value));
        inp.disabled = !!off;
      }
    };
  };

  KINDS.stepper = function (row, x) {
    var box = el('div', 'pg-step');
    var less = attrs(el('button', 'pg-btn pg-stepbtn', '\u2212'), { type: 'button', 'aria-label': 'Decrease',
                                                                    'aria-describedby': x.whyId });
    var more = attrs(el('button', 'pg-btn pg-stepbtn', '+'), { type: 'button', 'aria-label': 'Increase',
                                                               'aria-describedby': x.whyId });
    var val = attrs(el('output', 'pg-stepval'), { role: 'status', 'aria-live': 'polite' });
    var back = null;
    box.appendChild(less);
    box.appendChild(val);
    box.appendChild(more);
    if (typeof row.reset === 'function') {
      back = attrs(el('button', 'pg-btn pg-stepreset', row.resetLabel || 'Back to normal'), { type: 'button' });
      back.addEventListener('click', function () { if (!back.disabled) { safe(row.reset); x.changed(); } });
      box.appendChild(back);
    }
    function values() { return list(row.values); }
    function fmt(v) { return typeof row.format === 'function' ? words(function () { return row.format(v); }) : String(v); }
    // the value one step on: the next of the list, or the nearest on that side where the current one is not in it
    function target(dir) {
      var vs = values(), cur = safe(row.get), i = -1, k, best;
      for (k = 0; k < vs.length; k++) if (same(vs[k], cur)) i = k;
      if (i >= 0) return vs[i + dir];
      cur = Number(cur);
      for (k = 0; k < vs.length; k++) {
        if (dir > 0 && vs[k] > cur && (best === undefined || vs[k] < best)) best = vs[k];
        if (dir < 0 && vs[k] < cur && (best === undefined || vs[k] > best)) best = vs[k];
      }
      return best;
    }
    function go(dir) {
      var b = dir > 0 ? more : less;
      if (b.disabled) return;
      var to = target(dir);
      if (to === undefined) return;
      safe(row.set, to);
      x.changed();
    }
    less.addEventListener('click', function () { go(-1); });
    more.addEventListener('click', function () { go(1); });
    return {
      ctl: box, place: 'below',
      update: function (off) {
        val.textContent = fmt(safe(row.get));
        // what the row has to say about itself first (set to this, room for that), then why a step is refused
        var info = words(row.info), why = info && !off ? [info] : [];
        [[less, -1], [more, 1]].forEach(function (p) {
          var verdict = typeof row.can === 'function' ? safe(row.can, p[1]) : true;
          var none = target(p[1]) === undefined;
          p[0].disabled = !!off || none || (verdict !== true && verdict !== undefined);
          if (!off && typeof verdict === 'string' && verdict && why.indexOf(verdict) < 0) why.push(verdict);
        });
        if (back) back.disabled = !!off || (row.def !== undefined && same(safe(row.get), row.def));
        return why.length ? why.join(' ') : undefined;
      }
    };
  };

  KINDS.levels = function (row, x) {
    var box = el('div', 'pg-levels'), made = {}, order = [];
    box.setAttribute('role', 'group');
    box.setAttribute('aria-labelledby', x.nameId);
    function make(it) {
      var key = String(it.key), id = x.id + '-' + key.replace(/[^\w-]+/g, '_');
      var m = { key: key, last: null, timer: 0, item: it };
      m.li = el('div', 'pg-lv');
      m.pick = el('label', 'pg-lvcheck');
      m.box = attrs(el('input'), { type: 'checkbox', 'aria-describedby': id + '-h' });
      m.pick.appendChild(m.box);
      m.li.appendChild(m.pick);
      if (typeof row.setName === 'function') {
        m.name = attrs(el('input', 'pg-lvname'), { type: 'text', dir: 'auto', autocomplete: 'off',
          autocapitalize: 'off', spellcheck: 'false', maxlength: String(NAME_MAX), 'aria-describedby': id + '-h' });
        m.li.appendChild(m.name);
        m.name.addEventListener('input', function () {
          var c = cut(m.name.value);
          if (c !== m.name.value) m.name.value = c;
          clearTimeout(m.timer);
          m.timer = setTimeout(commit, 450);
        });
        m.name.addEventListener('change', commit);
        // LEFT, a box is drawn again from what the page says: an emptied one shows the usual name once more
        // (it cannot be at `change`, which comes while the keyboard is still in the box)
        m.name.addEventListener('blur', function () { commit(); x.changed(); });
        m.name.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); commit(); } });
      } else {
        m.name = el('span', 'pg-lvlabel');
        m.li.appendChild(m.name);
      }
      m.help = el('div', 'pg-lvhelp');
      m.help.id = id + '-h';
      m.li.appendChild(m.help);
      m.box.addEventListener('change', function () {
        safe(row.setShown, m.key, !!m.box.checked);
        x.changed();
      });
      // a name typed, as the page is to keep it: the default's own wording is no name at all
      function commit() {
        clearTimeout(m.timer);
        var v = cut(m.name.value).replace(/^\s+|\s+$/g, '');
        if (v === m.item.def) v = '';
        if (v === m.last) return;
        m.last = v;
        safe(row.setName, m.key, v);
        x.changed();
      }
      return m;
    }
    return {
      ctl: box, place: 'below',
      update: function (off) {
        var items = list(row.items), keep = {}, i, why = [];
        items.forEach(function (it) {
          var key = String(it.key), m = made[key];
          if (!off && typeof it.disabled === 'string' && it.disabled && why.indexOf(it.disabled) < 0) why.push(it.disabled);
          if (!m) { m = made[key] = make(it); }
          m.item = it;
          keep[key] = true;
          var label = words(it.name) || words(it.def) || key;
          var no = off || it.disabled;
          m.box.checked = !!it.shown;
          m.box.disabled = !!no;
          m.box.setAttribute('aria-label', 'Show the level ' + label);
          if (m.name.tagName === 'INPUT') {
            if (document.activeElement !== m.name) {
              m.name.value = words(it.name) || words(it.def);
              m.last = m.name.value === words(it.def) ? '' : m.name.value;
            }
            m.name.placeholder = words(it.def);
            m.name.disabled = !!no;
            m.name.setAttribute('aria-label', 'Name of the level ' + (words(it.def) || key));
            if (it.lang) m.name.setAttribute('lang', it.lang); else m.name.removeAttribute('lang');
          } else {
            m.name.textContent = label;
            if (it.lang) m.name.setAttribute('lang', it.lang); else m.name.removeAttribute('lang');
          }
          m.help.textContent = words(it.help);
          m.li.classList.toggle('pg-off', !!it.disabled);
          m.li.setAttribute('data-pg-level', key);
        });
        for (i = order.length - 1; i >= 0; i--) {
          if (!keep[order[i]]) {
            if (made[order[i]].li.parentNode) made[order[i]].li.parentNode.removeChild(made[order[i]].li);
            clearTimeout(made[order[i]].timer);
            delete made[order[i]];
            order.splice(i, 1);
          }
        }
        // in the page's order, and a line already in its place is not touched: a box with the keyboard in it
        // that was taken out and put back would lose the caret in the middle of a name
        order = items.map(function (it) { return String(it.key); });
        var at = box.firstChild;
        order.forEach(function (key) {
          var li = made[key].li;
          if (li === at) at = at.nextSibling;
          else box.insertBefore(li, at);
        });
        // a level at rest says why, under the row, as a row at rest does
        return why.length ? why.join(' ') : undefined;
      }
    };
  };

  KINDS.link = function (row, x) {
    var a;
    if (row.href) {
      a = attrs(el('a', 'pg-link'), { href: row.href, 'aria-describedby': x.helpId });
      if (row.newTab) { a.target = '_blank'; a.rel = 'noopener'; }
    } else {
      a = attrs(el('button', 'pg-link'), { type: 'button', 'aria-describedby': x.helpId });
      a.addEventListener('click', function () { safe(row.onClick); x.changed(); });
    }
    return {
      ctl: a, place: 'above',
      update: function () { a.textContent = words(row.label); }
    };
  };

  KINDS.buttons = function (row, x) {
    var ctl = attrs(el('div', 'pg-chips'), { role: 'group', 'aria-labelledby': x.nameId,
                                             'aria-describedby': x.helpId + ' ' + x.whyId });
    var bs = [];
    list(row.items).forEach(function (it) {
      var b = attrs(el('button', 'pg-chip', it.label), { type: 'button', 'aria-pressed': 'false' });
      if (it.title) b.title = it.title;
      b.addEventListener('click', function () { if (b.disabled) return; safe(it.onClick); x.changed(); });
      ctl.appendChild(b);
      bs.push([b, it]);
    });
    return {
      ctl: ctl, place: 'below',
      update: function (off) {
        bs.forEach(function (p) {
          p[0].setAttribute('aria-pressed', safe(p[1].pressed) ? 'true' : 'false');
          p[0].disabled = !!off;
        });
      }
    };
  };

  KINDS.action = function (row, x) {
    var b = attrs(el('button', 'pg-btn pg-action'), { type: 'button', 'aria-describedby': x.helpId + ' ' + x.whyId });
    b.addEventListener('click', function () { if (b.disabled) return; safe(row.onClick); x.changed(); });
    return {
      ctl: b, place: 'above',
      update: function (off) { b.textContent = words(row.label); b.disabled = !!off; }
    };
  };

  KINDS.note = function (row) {
    var p = el('p', 'pg-note');
    return { ctl: p, place: 'only', update: function () { p.textContent = words(row.text); } };
  };

  /* A NODE IS A CONTROL ANOTHER LAYER OWNS -- lib/keep.js's "Keep on this
     phone" buttons are the first -- BROUGHT INTO THE ROW while the panel is up
     and sent home when it is not (the panel shut, the row not drawn, the
     layout gone, the gear unmounted).  It is the same element all the while, so
     every handler it has goes on working, and the layer that owns it is not
     asked to draw anything twice.  A comment node stands in its place
     meanwhile, which is how it is put back exactly where it was -- the same
     parent, the same next sibling -- whatever else has been taken out of that
     parent in the meantime and in whatever order they come home. */
  KINDS.node = function (row, x) {
    var holder = attrs(el('div', 'pg-node'), { role: 'group' }), at = null;
    if (x.named) holder.setAttribute('aria-labelledby', x.nameId);
    function resolve() {
      var n = typeof row.el === 'function' ? safe(row.el) : row.el;
      return n && n.nodeType === 1 ? n : null;
    }
    function home() {
      if (!at) return;
      var n = at.node, mark = at.mark;
      at = null;
      if (n.parentNode === holder) {
        if (mark && mark.parentNode) mark.parentNode.insertBefore(n, mark);
        else holder.removeChild(n);
      }
      if (mark && mark.parentNode) mark.parentNode.removeChild(mark);
    }
    function bring(n) {
      if (at && at.node === n && n.parentNode === holder) return true;
      home();
      var mark = n.parentNode ? document.createComment('pg') : null;
      try {
        if (mark) n.parentNode.insertBefore(mark, n);
        holder.appendChild(n);
      } catch (e) {
        // an element that holds this very panel cannot be put in it
        if (mark && mark.parentNode) mark.parentNode.removeChild(mark);
        return false;
      }
      at = { node: n, mark: mark };
      return true;
    }
    return {
      ctl: holder, place: 'below',
      has: function () { return !!resolve(); },
      away: home,
      update: function (off) {
        var n = resolve();
        if (!n || !x.isUp() || !bring(n)) { home(); return; }
        if (off) holder.setAttribute('inert', ''); else holder.removeAttribute('inert');
      }
    };
  };

  /* ========================================================= the standard groups */
  var ZOOM_HELP = "Makes everything on the page bigger or smaller together \u2014 bars, buttons, clouds, sheets. " +
                  "A computer's own Ctrl + and Ctrl \u2212 do the same; the installed app cannot.";
  var COLOURS_HELP = "The colours of every Parseh page. 'Follow my device' uses your phone's or computer's own " +
                     "light or dark setting.";
  var INTERFACE_HELP = 'Browser: every page, with everything that edits. Mobile: pages made for a phone, ' +
                       'to read and to study, with nothing that edits.';

  function zoomOf() { return window.ParsehZoom || null; }
  var std = {
    /* ZOOM: a stepper over window.ParsehZoom (lib/pagezoom.js), one zoom for
       everything Parseh draws on this device.  Not drawn where the module is
       not there, and checked at every refresh, so a page that loads it late
       gains the group. */
    zoom: function () {
      return {
        id: 'zoom', title: 'Zoom', caption: 'Saved on this device, for all of Parseh.',
        when: function () { return !!zoomOf(); },
        rows: [{
          id: 'zoom', kind: 'stepper', label: 'Page zoom', help: ZOOM_HELP,
          values: function () { var z = zoomOf(); return z && z.STEPS ? z.STEPS : [100]; },
          // what the window really has in force, which is what a person sees (and counts steps from)
          get: function () {
            var z = zoomOf();
            if (!z) return 100;
            return typeof z.applied === 'function' ? z.applied() : z.get();
          },
          set: function (v) { var z = zoomOf(); if (z) z.set(v); },
          can: function (dir) { var z = zoomOf(); return z && typeof z.can === 'function' ? z.can(dir) : true; },
          format: function (v) { return v + ' %'; },
          reset: function () { var z = zoomOf(); if (z) z.reset(); },
          resetLabel: 'Back to 100 %', def: 100,
          info: function () {
            var z = zoomOf();
            if (!z || typeof z.applied !== 'function' || typeof z.get !== 'function') return '';
            return z.applied() !== z.get() ? 'Set to ' + z.get() + ' %, but this window has room for ' + z.applied() + ' %.' : '';
          },
          watch: function (cb) {
            var z = zoomOf(), off = null;
            if (z && typeof z.onChange === 'function') off = z.onChange(cb);
            window.addEventListener('parseh:zoom', cb);
            document.addEventListener('parseh:zoom', cb);
            window.addEventListener('resize', cb);
            return function () {
              if (typeof off === 'function') off();
              window.removeEventListener('parseh:zoom', cb);
              document.removeEventListener('parseh:zoom', cb);
              window.removeEventListener('resize', cb);
            };
          }
        }]
      };
    },
    /* COLOURS: the one theme of every Parseh page, `parseh_theme`; 'auto'
       is "follow my device".  Through Parseh.theme where there is one, else
       written here (localStorage and <html data-theme>) and handed to the
       page's own `apply(t)`, which a studio page uses to dress its <body>. */
    colours: function (o) {
      var apply = o && o.apply;
      return {
        id: 'colours', title: 'Colours', caption: 'Follows you to your other devices.',
        rows: [{
          id: 'theme', kind: 'choice', label: 'Colour scheme', help: COLOURS_HELP,
          options: [{ value: 'auto', label: 'Follow my device' }, { value: 'light', label: 'Light' },
                    { value: 'dark', label: 'Dark' }, { value: 'sepia', label: 'Sepia' }],
          get: getTheme,
          set: function (t) { setTheme(t, apply); },
          watch: watchTheme
        }]
      };
    },
    /* INTERFACE: the browser or the mobile pages, one choice for the whole
       toolbox (docs/mobile.md), made here as the hub's own switch makes it. */
    'interface': function () {
      function item(m, label, title) {
        return { label: label, title: title, onClick: function () { setMode(m); },
                 pressed: function () { return (defaultMobile() ? 'mobile' : 'browser') === m; } };
      }
      return {
        id: 'interface', title: 'Interface', caption: 'Saved on this device.',
        summary: function () { return defaultMobile() ? 'Mobile pages' : 'Browser pages'; },
        rows: [{
          id: 'mode', kind: 'buttons', label: 'Browser or mobile pages', help: INTERFACE_HELP,
          items: [item('browser', 'Browser', 'Every page, with everything that edits'),
                  item('mobile', 'Mobile', 'Pages made for a phone, to read and to study')],
          watch: function (cb) { return defaultOnMode(cb); }
        }]
      };
    }
  };

  /* ================================================================== mount */
  function make(spec) {
    spec = spec || {};
    var titles = {
      title: spec.titles && spec.titles.title ? spec.titles.title : DEFAULT_TITLES.title,
      first: spec.titles && spec.titles.first !== undefined ? spec.titles.first : DEFAULT_TITLES.first,
      foot: spec.titles && spec.titles.foot !== undefined ? spec.titles.foot : DEFAULT_TITLES.foot
    };
    var no = ++counter, seq = 0;
    function uid(part) { return 'pg' + no + '-' + String(part).replace(/[^\w-]+/g, '_') + '-' + (++seq); }
    var groups = list(spec.groups).filter(function (g) { return g && g.id; });
    var host = spec.host || {};
    var mobileFn = typeof spec.mobileMode === 'function' ? spec.mobileMode : defaultMobile;
    var onModeFn = typeof spec.onMode === 'function' ? spec.onMode : defaultOnMode;

    var btn = null, panel = null, headEl = null, bodyEl = null, built = [], told = [];
    var isUp = false, sheet = false, stack = [], spent = 0, dead = false, wired = false;
    var unwatchers = [], cleanups = [], placing = null;
    /* THE SHEET'S STAGE: 'index', or the id of the theme on stage.  `leaving` is the theme that is sliding out
       (kept drawn until it is gone); `tall` the detent in force. */
    var stage = 'index', leaving = '', leaveTimer = 0, tall = false;
    var byId = {}, indexEl = null, trackEl = null, indexPane = null, themePane = null, footEl = null;
    var titleEl = null, subEl = null, backEl = null, gripEl = null, xEl = null, firstEl = null;

    function mobile() { return !!safe(mobileFn); }
    function layoutOk(o) {
      var l = o.layouts;
      if (!l || l === 'both') return true;
      return l === 'mobile' ? mobile() : !mobile();
    }
    // the SHEET is for a phone: the mobile layout, or a window this narrow (in the page's own pixels,
    // which under the zoom's shim is what a person sees, not what the screen has)
    function sheetNow() { return mobile() || vw() <= SHEET_MAX; }

    /* ------------------------------------------------------------ the button */
    btn = attrs(el('button', 'pg-gear'), {
      type: 'button', 'data-parseh-gear': '', 'data-pg-page': spec.page || '',
      'aria-haspopup': 'dialog', 'aria-expanded': 'false',
      'aria-label': BUTTON_LABEL, title: BUTTON_TITLE });
    btn.appendChild(attrs(el('span', 'pg-gear-glyph', '\u2699'), { 'aria-hidden': 'true' }));
    btn.appendChild(el('span', 'pg-gear-word', 'page'));
    btn.addEventListener('click', function () { toggle(); });
    // the keys that press it are its own: a page that plays on Space must not play as the gear is opened
    btn.addEventListener('keydown', function (e) { if (e.key === ' ' || e.key === 'Enter') e.stopPropagation(); });
    btn.addEventListener('keyup', function (e) { if (e.key === ' ' || e.key === 'Enter') e.stopPropagation(); });
    // held back until the stylesheet is in, rather than drawn bare for a moment
    if (!styleDone) {
      btn.style.visibility = 'hidden';
      styleWait.push(function () { btn.style.visibility = ''; });
    }
    function hostOf(which) {
      var h = host[which];
      return typeof h === 'function' ? safe(h) : h;
    }
    function syncButton() {
      btn.classList.toggle('pg-mobile', mobile());
      btn.classList.toggle('pg-phone', sheetNow());
    }
    function placeButton() {
      if (dead) return;
      syncButton();
      var h = hostOf(mobile() ? 'mobile' : 'browser');
      if (h && h.nodeType === 1 && btn.parentNode !== h) h.appendChild(btn);
    }

    /* ------------------------------------------------------------- the rows */
    function buildRow(g, row) {
      var kind = KINDS[row.kind];
      if (!kind) { warn('unknown kind of row: ' + row.kind); return null; }
      var id = uid(g.id + '-' + row.id);
      var wrap = attrs(el('div', 'pg-row'), { 'data-pg-row': row.id, 'data-pg-kind': row.kind });
      var text = el('div', 'pg-text');
      /* WHO NAMES THE CONTROL.  A link and an action ARE their own name (the
         control says it, and the row adds the sentence); a note is only a
         sentence; a node has a name where it was given one; the rest always. */
      var given = row.label !== undefined && row.label !== null && row.label !== '';
      var named = row.kind === 'node' ? given : row.kind !== 'link' && row.kind !== 'action' && row.kind !== 'note';
      var x = { id: id, nameId: id + '-n', helpId: id + '-h', whyId: id + '-w', text: text, row: row, named: named,
                changed: changed,
                // a borrowed node stands in its row only while the row can be seen: the panel is up and,
                // on the sheet, the row's theme is on stage
                isUp: function () { return isUp && (!sheet || stage === g.id); } };
      if (!named) x.nameId = x.helpId;
      var k = kind(row, x);
      var nameEl = null, nameText = null, helpEl = el('div', 'pg-help');
      helpEl.id = x.helpId;
      if (named) {
        nameEl = el('div', 'pg-name');
        nameEl.id = x.nameId;
        nameText = el('span', 'pg-nametext');
        nameEl.appendChild(nameText);
        if (row.kept && KEPT[row.kept]) nameEl.appendChild(el('span', 'pg-kept', KEPT[row.kept]));
        text.appendChild(nameEl);
      }
      text.appendChild(helpEl);
      var why = attrs(el('div', 'pg-why'), { id: x.whyId, role: 'note' });
      why.hidden = true;
      if (k.place === 'only') wrap.appendChild(k.ctl);
      else if (k.place === 'above') { wrap.appendChild(k.ctl); wrap.appendChild(text); }
      else { wrap.appendChild(text); wrap.appendChild(k.ctl); }
      wrap.appendChild(why);
      if (k.place === 'only') wrap.classList.add('pg-noterow');
      // A ROW MAY HANG UNDER THE ONE ABOVE IT (the dictionary, its definitions, their translation)
      var indent = Math.max(0, Math.min(3, parseInt(row.indent, 10) || 0));
      if (indent) {
        wrap.setAttribute('data-pg-indent', String(indent));
        wrap.style.setProperty('--pg-in', String(indent));
      }
      function away() {
        wrap.hidden = true;
        if (k.away) k.away();
      }
      return {
        el: wrap, row: row, away: away,
        // a node sent home, the row left as it is (the panel is shut, not the row gone)
        home: function () { if (k.away) k.away(); },
        // what the row under it may read: a switch is on or it is off; anything else says nothing
        state: function () { return k.state ? k.state() : undefined; },
        /* `above` is the row drawn just over this one, so that a row under a switch can ask whether the
           switch is on: disabled(on) is called with true or false, and with undefined where the row
           above is not a switch (or there is none) */
        update: function (above) {
          var on = layoutOk(row) && truthy(row.when) && (!k.has || k.has());
          if (!on) { away(); return false; }
          wrap.hidden = false;
          var label = words(row.label), help = words(row.help);
          if (nameText) nameText.textContent = label || (row.kind === 'node' ? '' : row.id);
          helpEl.textContent = help;
          helpEl.hidden = !help;
          text.hidden = !(named || help);
          var off = typeof row.disabled === 'function' ? safe(row.disabled, above ? above.state() : undefined) : false;
          wrap.classList.toggle('pg-off', !!off);
          var own = k.update(off);
          var reason = typeof off === 'string' && off ? off : (typeof own === 'string' ? own : '');
          why.textContent = reason;
          why.hidden = !reason;
          return true;
        }
      };
    }
    function buildGroup(g) {
      var sec = attrs(el('section', 'pg-group'), { 'data-pg-group': g.id });
      var h = el('h3', 'pg-gtitle');
      h.id = uid(g.id + '-t');
      sec.setAttribute('aria-labelledby', h.id);
      var cap = el('p', 'pg-caption');
      sec.appendChild(h);
      sec.appendChild(cap);
      var rows = [];
      list(g.rows).forEach(function (r) {
        if (!r || !r.id) return;
        var b = buildRow(g, r);
        if (b) { rows.push(b); sec.appendChild(b.el); }
      });
      return {
        el: sec, g: g, rows: rows, irow: buildIndexRow(g),
        home: function () { rows.forEach(function (r) { r.home(); }); },
        update: function () {
          var on = layoutOk(g) && truthy(g.when), any = false, above = null;
          if (on) rows.forEach(function (r) { if (r.update(above)) { any = true; above = r; } });
          else rows.forEach(function (r) { r.away(); });
          sec.hidden = !(on && any);
          h.textContent = words(g.title) || g.id;
          var c = words(g.caption);
          cap.textContent = c;
          cap.hidden = !c;
        }
      };
    }

    /* ------------------------------------------------------------ the panel */
    function build() {
      if (panel || !document.body) return !!panel;
      panel = attrs(el('div', 'pg-panel'), {
        role: 'dialog', 'aria-label': BUTTON_LABEL, dir: 'ltr', lang: 'en', tabindex: '-1',
        'data-pg-page': spec.page || '' });
      panel.hidden = true;
      headEl = el('div', 'pg-head');
      /* THE GRAB LINE is a button of its own, 48px wide, so that a tap on it makes the sheet tall or half again
         while the rest of the head stays a title; it is not in the keyboard's way (the sheet's height is for a
         finger) */
      gripEl = attrs(el('button', 'pg-grip'), { type: 'button', tabindex: '-1', 'aria-hidden': 'true' });
      gripEl.appendChild(el('span', 'pg-gripline'));
      headEl.appendChild(gripEl);
      backEl = attrs(el('button', 'pg-back', '‹'), { type: 'button', 'aria-label': 'Back to the list',
                                                          title: 'back to the list' });
      backEl.hidden = true;
      backEl.addEventListener('click', function () { back(); });
      headEl.appendChild(backEl);
      var ht = el('div', 'pg-headtext');
      titleEl = attrs(el('h2', 'pg-title', titles.title), { 'aria-live': 'polite' });
      subEl = el('p', 'pg-sub');
      subEl.hidden = true;
      ht.appendChild(titleEl);
      ht.appendChild(subEl);
      headEl.appendChild(ht);
      xEl = attrs(el('button', 'pg-x', '✕'), { type: 'button', 'aria-label': 'Close', title: 'close (Esc)' });
      xEl.addEventListener('click', function () { close('button'); });
      headEl.appendChild(xEl);
      bodyEl = el('div', 'pg-body');
      /* TWO PANES side by side in a track that slides: the index, and the themes.  On a wide window the index
         is not drawn and the themes pane is the one long list it always was. */
      trackEl = el('div', 'pg-stages');
      indexPane = el('div', 'pg-pane pg-pane-index');
      indexEl = attrs(el('div', 'pg-index'), { role: 'group', 'aria-label': 'Settings, by theme' });
      indexPane.appendChild(indexEl);
      themePane = el('div', 'pg-pane pg-pane-theme');
      if (titles.first) { firstEl = el('p', 'pg-first', titles.first); themePane.appendChild(firstEl); }
      groups.forEach(function (g) {
        var b = buildGroup(g);
        built.push(b);
        byId[g.id] = b;
        themePane.appendChild(b.el);
        indexEl.appendChild(b.irow.el);
      });
      if (titles.foot && titles.foot.href) {
        footEl = el('div', 'pg-foot');
        footEl.appendChild(attrs(el('a', 'pg-footlink', titles.foot.text || DEFAULT_TITLES.foot.text),
                                 { href: titles.foot.href }));
        themePane.appendChild(footEl);
      }
      trackEl.appendChild(indexPane);
      trackEl.appendChild(themePane);
      bodyEl.appendChild(trackEl);
      panel.appendChild(headEl);
      panel.appendChild(bodyEl);
      document.body.appendChild(panel);
      btn.setAttribute('aria-controls', panel.id = uid('panel'));
      /* KEYS TYPED IN THE PANEL BELONG TO THE PANEL.  A reader answers Space, the arrows, R, G and H anywhere on
         the page but in a text box, a picker or a text area -- not on a button -- so a Space on a switch here
         would also play or stop the recording, and a G typed into a level's name would flip the glosses.  The
         keys go no further than the panel; Escape closes it and is not heard by the page at all (the one
         layer it is spent on), and the keys' own work -- an arrow on a slider, a Tab -- is the browser's and
         is left alone. */
      panel.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !e.defaultPrevented && !e.isComposing && e.keyCode !== 229) {
          e.preventDefault();
          close('key');
        }
        e.stopPropagation();
      });
      panel.addEventListener('keyup', function (e) { e.stopPropagation(); });
      panel.addEventListener('keypress', function (e) { e.stopPropagation(); });
      swipe();
      // what the page says changes, the row follows; every row that can say so is listened to
      groups.forEach(function (g) {
        list(g.rows).forEach(function (r) {
          if (r && typeof r.watch === 'function') {
            // a closed panel is not redrawn: it is asked afresh the moment it opens
            var un = safe(r.watch, function () { if (isUp && !dead) refreshAll(); });
            if (typeof un === 'function') unwatchers.push(un);
          }
        });
      });
      return true;
    }

    /* ------------------------------------------------------ the index, and its summaries */
    /* What one row has to say of itself in a summary: a list of parts, each a string or { bdi: name }. */
    function rowParts(row) {
      var cur, t, out = [];
      switch (row.kind) {
        case 'switch':
          t = safe(row.get) ? words(row.short) : '';
          return t ? [t] : [];
        case 'choice':
          cur = safe(row.get);
          list(row.options).forEach(function (o) { if (!out.length && same(o.value, cur)) out.push(words(o.label)); });
          // a value the list does not hold (a speed set by a key) is said as it is
          if (!out.length && cur !== undefined && cur !== null && cur !== '') out.push(String(cur));
          return out;
        case 'slider':
          cur = Number(safe(row.get));
          if (!isFinite(cur)) return [];
          return [typeof row.format === 'function' ? words(function () { return row.format(cur); })
                                                   : round(cur) + (row.unit || '')];
        case 'stepper':
          cur = safe(row.get);
          if (cur === undefined || cur === null) return [];
          return [typeof row.format === 'function' ? words(function () { return row.format(cur); }) : String(cur)];
        case 'levels':
          list(row.items).forEach(function (it) {
            if (!it || !it.shown) return;
            var name = words(it.name) || words(it.def) || String(it.key);
            if (out.length) out.push(', ');
            out.push({ bdi: name });
          });
          return out;
        case 'buttons':
          list(row.items).forEach(function (it) {
            if (!it || !safe(it.pressed)) return;
            if (out.length) out.push(', ');
            out.push(words(it.label));
          });
          return out;
      }
      return [];
    }
    function asParts(v) {
      if (v === undefined || v === null || v === false) return [];
      if (Object.prototype.toString.call(v) === '[object Array]') {
        return v.map(function (p) {
          return p && typeof p === 'object' ? { bdi: String(p.bdi === undefined ? '' : p.bdi) } : String(p === undefined || p === null ? '' : p);
        }).filter(function (p) { return p !== '' && !(typeof p === 'object' && p.bdi === ''); });
      }
      var one = String(v);
      return one === '' ? [] : [one];
    }
    // a group's summary: what the page's adapter said of it, else what its drawn rows say, joined
    function summaryOf(b) {
      var g = b.g, given = g.summary;
      if (given !== undefined && given !== null) {
        var v = typeof given === 'function' ? safe(given) : given;
        if (v !== undefined) return asParts(v);
      }
      var out = [];
      b.rows.forEach(function (r) {
        if (r.el.hidden) return;
        var p = rowParts(r.row);
        if (!p.length) return;
        if (out.length) out.push(' · ');
        out = out.concat(p);
      });
      return out;
    }
    function plain(parts) {
      return parts.map(function (p) { return typeof p === 'object' ? p.bdi : p; }).join('');
    }
    function paintSummary(span, parts) {
      while (span.firstChild) span.removeChild(span.firstChild);
      parts.forEach(function (p) {
        if (typeof p === 'object') span.appendChild(el('bdi', null, p.bdi));
        else span.appendChild(document.createTextNode(p));
      });
    }
    function buildIndexRow(g) {
      var r = attrs(el('button', 'pg-irow'), { type: 'button', 'data-pg-index': g.id });
      var t = el('span', 'pg-itext');
      var n = el('span', 'pg-iname'), sm = el('span', 'pg-isum');
      t.appendChild(n);
      t.appendChild(sm);
      r.appendChild(t);
      r.appendChild(attrs(el('span', 'pg-ichev', '›'), { 'aria-hidden': 'true' }));
      r.addEventListener('click', function () { enter(g.id); });
      return { el: r, name: n, sum: sm };
    }
    // the index drawn from the groups, as they are now
    function updateIndex() {
      var shown = 0;
      built.forEach(function (b) {
        var gone = b.el.hidden;
        b.irow.el.hidden = gone;
        if (gone) return;
        shown++;
        var name = words(b.g.title) || b.g.id, parts = summaryOf(b), said = plain(parts);
        b.irow.name.textContent = name;
        paintSummary(b.irow.sum, parts);
        b.irow.sum.hidden = !parts.length;
        b.irow.el.setAttribute('aria-label', said ? name + ', ' + said : name);
      });
      // seven themes in the half sheet of a small phone: the rows are squeezed to 50px, and no further
      var room = (tall ? tallH() : halfH()) - HEAD_H;
      panel.style.setProperty('--pg-row', (shown * ROW_H > room && shown * ROW_TIGHT <= room + 4 ? ROW_TIGHT : ROW_H) + 'px');
    }
    /* The head says where the sheet is: the page's title and its one-line subtitle on the index; the theme's
       name and its caption (where its settings are kept) on a theme, with the ‹ to go back. */
    function paintHead() {
      if (!panel) return;
      var inTheme = sheet && stage !== 'index' && byId[stage];
      backEl.hidden = !inTheme;
      panel.classList.toggle('pg-in-theme', !!inTheme);
      var title = inTheme ? (words(byId[stage].g.title) || stage) : titles.title;
      var sub = inTheme ? words(byId[stage].g.caption) : (titles.first || '');
      if (titleEl.textContent !== title) titleEl.textContent = title;
      subEl.textContent = sub;
      subEl.hidden = !sub;
      if (sheet) panel.setAttribute('data-pg-stage', stage); else panel.removeAttribute('data-pg-stage');
    }
    function paintStage() {
      Object.keys(byId).forEach(function (id) {
        byId[id].el.classList.toggle('pg-here', id === stage || id === leaving);
      });
      var inTheme = sheet && stage !== 'index';
      indexPane.classList.toggle('pg-pane-on', !inTheme);
      themePane.classList.toggle('pg-pane-on', inTheme);
      /* the pane that is not on stage is out of reach at once -- no key, no finger, no screen reader -- while its
         slide out is still being drawn (it is not `visibility: hidden` until the slide is done) */
      setInert(indexPane, inTheme);
      setInert(themePane, sheet && !inTheme);
      paintHead();
    }
    function setInert(e, on) {
      if (on) e.setAttribute('inert', ''); else e.removeAttribute('inert');
    }
    function finishLeave() {
      clearTimeout(leaveTimer);
      leaveTimer = 0;
      if (!leaving) return;
      leaving = '';
      if (panel) paintStage();
    }
    /* whether the stages slide: asked of the sheet's own transition, which the stylesheet takes away where the
       person has asked for no motion (and which a query of the window would only say a second time) */
    function slow() {
      try { return parseFloat(getComputedStyle(trackEl).transitionDuration) > 0; } catch (e) { return true; }
    }
    function refreshAll() {
      if (!panel) return;
      built.forEach(function (b) { b.update(); });
      // a theme on stage that stopped being drawn (its layout is gone, its when() is false) leaves the stage
      if (sheet && stage !== 'index' && (!byId[stage] || byId[stage].el.hidden)) leaveStage(true);
      updateIndex();
      paintHead();
      if (isUp && !sheet) popover();
    }
    function groupAt() { return sheet && stage !== 'index' ? stage : ''; }
    // every node of another layer's, which the panel has borrowed, sent home
    function homeAll() { built.forEach(function (b) { b.home(); }); }
    // after a control of the panel has done its work: every row asks the page again, for one may have
    // changed another (turning the hover cloud on rests the Chunks level)
    function changed() { refreshAll(); }

    /* ------------------------------------------------- where the panel stands */
    /* THE POPOVER stands under the button, its right edge on the button's, and
       stays inside the window.  Placed from getBoundingClientRect, the root's
       clientWidth/clientHeight and its own size, which are the numbers a page
       zoomed by lib/pagezoom.js still gets in its own pixels, and from nothing
       else -- no viewport units, which that module has to take apart. */
    function popover() {
      var W = vw(), H = vh(), pad = 8, w = Math.max(240, Math.min(POP_W, W - 2 * pad));
      var r = btn.getBoundingClientRect();
      var seen = drawn(btn) && (r.width || r.height);
      panel.style.width = w + 'px';
      // never above the window: a bar that has slid away with the scroll takes its button off the top
      var top = Math.max(pad, seen ? r.bottom + 6 : pad), room = H - top - pad;
      if (room >= 220) {
        panel.style.maxHeight = Math.floor(room) + 'px';
      } else {
        // low in the window (a bar held at the foot, a phone held sideways): up, as the Aa panel was
        panel.style.maxHeight = Math.max(160, H - 2 * pad) + 'px';
        top = Math.max(pad, Math.min(top, H - panel.offsetHeight - pad));
      }
      var left = seen ? r.right - w : W - w - pad;
      panel.style.top = Math.round(top) + 'px';
      panel.style.left = Math.round(Math.max(pad, Math.min(left, W - w - pad))) + 'px';
    }
    /* THE SHEET'S HEIGHTS, in the page's own pixels (the numbers lib/pagesettings.css makes its rules of, from
       --pg-vh): half the window with a floor, and tall, the window less the strip of page left above it. */
    function halfH() { return Math.max(SHEET_FLOOR, Math.round(vh() * HALF_PCT / 100)); }
    function tallH() { return Math.max(halfH(), vh() - SHEET_GAP); }
    function readTall() {
      try { return localStorage.getItem(TALL_KEY) === '1'; } catch (e) { return false; }
    }
    function setTall(v) {
      tall = !!v;
      try { if (tall) localStorage.setItem(TALL_KEY, '1'); else localStorage.removeItem(TALL_KEY); } catch (e) {}
      panel.classList.toggle('pg-tall', tall && sheet);
      updateIndex();
    }
    function present() {
      var s = sheetNow();
      sheet = s;
      panel.classList.toggle('pg-sheet', s);
      panel.classList.toggle('pg-popover', !s);
      panel.classList.toggle('pg-tall', s && tall);
      document.documentElement.classList.toggle('pg-sheet', isUp && s);
      // 1% of the window's height in the page's own pixels: the sheet's height is made of it
      panel.style.setProperty('--pg-vh', (vh() / 100) + 'px');
      /* ✕ is the last thing the keyboard reaches in the sheet (‹, the rows, ✕) and the first in the popover */
      if (s) { if (xEl.parentNode !== panel) panel.appendChild(xEl); }
      else if (xEl.parentNode !== headEl) headEl.appendChild(xEl);
      // the foot link closes the index on the sheet, and the one list on the popover
      if (footEl) {
        var home = s ? indexPane : themePane;
        if (footEl.parentNode !== home) home.appendChild(footEl);
      }
      if (s) panel.style.top = panel.style.left = panel.style.width = panel.style.maxHeight = '';
      else popover();
      paintStage();
    }
    /* THE BACK GESTURE closes the sheet, as it does the dictionary's: the sheet
       pushes an entry of its own on the way in, and the popstate that leaves
       that entry is the way out.  A theme entered pushes a second, so the same
       gesture leaves the theme first.  An entry the sheet spent itself is not
       heard as a gesture (`spent`). */
    function pushEntry() {
      var id = no + ':' + Date.now() + ':' + stack.length;
      try { history.pushState({ parsehGear: id }, ''); stack.push(id); } catch (e) {}
    }
    /* the entries above the first `keep` of them given back: one history.go(-n) -- one popstate to be spent --
       when the top one is still ours; none where the gesture has spent them already */
    function spendEntries(how, keep) {
      var n = stack.length - keep;
      if (n <= 0) return;
      var gone = stack.splice(keep, n), top = gone[gone.length - 1];
      var mine = history.state && history.state[HIST] === top;
      if (how === 'back' || !mine) return;
      spent++;
      try { if (n === 1) history.back(); else history.go(-n); } catch (e) { spent--; }
    }
    function onPop() {
      if (spent) { spent--; return; }
      if (!isUp || !stack.length) return;
      var now = history.state && history.state[HIST], at = now ? stack.indexOf(now) : -1;
      if (at === stack.length - 1) return;
      if (at < 0) { stack = []; close('back'); return; }
      // a gesture back out of a theme: the index again, the entry it spent forgotten
      stack.length = at + 1;
      if (stage !== 'index') leaveStage(false);
    }
    function onKey(e) {
      if (e.key !== 'Escape' || e.defaultPrevented || e.isComposing || e.keyCode === 229) return;
      // ONE ESCAPE, ONE LAYER: spent on this panel, so a layer under it that honours defaultPrevented stays
      e.preventDefault();
      close('key');
    }
    /* A click outside closes the popover; the sheet is not modal -- the page
       above it is for reading and for changing what the sheet shows -- so it
       does not.  In the capture phase and counted from the path the event had
       when it started, so a control that redraws itself under the click does
       not look like a click outside, and a click that opens the panel (the
       page's Aa) cannot also close it. */
    function onClick(e) {
      if (!isUp || sheet) return;
      /* A SCRIPT'S CLICK IS NOT A PERSON'S.  An adapter's row presses the page's
         own button (button.click()) to do what the row says, and a page presses
         its own buttons for its own reasons (the reader's hover pause presses
         its play button); such a click is outside the panel and must not shut
         it under the person's hand, as the first row of the book's gear did. */
      if (e.isTrusted === false) return;
      var path = pathOf(e);
      if (path.indexOf(panel) >= 0 || path.indexOf(btn) >= 0) return;
      close('outside');
    }
    function onResize() {
      syncButton();
      if (!isUp) return;
      var was = sheet, at = groupAt();
      present();
      if (sheet && !was) { stage = 'index'; pushEntry(); paintStage(); refreshAll(); }
      else if (!sheet && was) {
        // the popover is one list: the theme that was on stage is where it opens
        spendEntries('layout', 0);
        stage = 'index';
        finishLeave();
        refreshAll();
        if (at) scrollToGroup(at);
      } else { updateIndex(); }
    }
    var onZoom = function () { onResize(); refreshAll(); };

    /* The listeners that must outlive one opening are wired ONCE: the popstate
       that answers a history entry the sheet spent itself arrives after the
       sheet is gone, and a listener taken off with it would leave `spent`
       counted for the next back gesture to be swallowed by. */
    function wire() {
      if (wired) return;
      wired = true;
      window.addEventListener('resize', onResize);
      window.addEventListener('orientationchange', onResize);
      window.addEventListener('popstate', onPop);
      window.addEventListener('parseh:zoom', onZoom);
      document.addEventListener('parseh:zoom', onZoom);
      // a window whose visual viewport resizes (a phone's keyboard) stands the sheet again
      if (window.visualViewport) window.visualViewport.addEventListener('resize', onResize);
    }
    function unwire() {
      if (!wired) return;
      wired = false;
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
      window.removeEventListener('popstate', onPop);
      window.removeEventListener('parseh:zoom', onZoom);
      document.removeEventListener('parseh:zoom', onZoom);
      if (window.visualViewport) window.visualViewport.removeEventListener('resize', onResize);
    }
    function scrollToGroup(gid) {
      var g = byId[gid];
      if (!g || g.el.hidden) return false;
      // the group at the top of the panel, and the first control of it where a keyboard lands
      var top = g.el.getBoundingClientRect().top - bodyEl.getBoundingClientRect().top + bodyEl.scrollTop;
      bodyEl.scrollTop = Math.max(0, Math.floor(top) - 6);
      var f = firstControl(g.el);
      if (f) { try { f.focus({ preventScroll: true }); } catch (e) {} }
      return true;
    }
    /* ENTERING A THEME (the sheet): its group alone on the stage, the sheet slid to it, a second history entry
       pushed (the first theme only: from one theme to another there is still just the one), its first control
       focused.  Every row of the groups that went off stage is asked again, which sends a borrowed node home. */
    function enter(gid) {
      if (!sheet || !isUp) return false;
      var b = byId[gid];
      if (!b || b.el.hidden) return false;
      finishLeave();
      if (stage === gid) { var again = firstControl(b.el); if (again) { try { again.focus({ preventScroll: true }); } catch (e) {} } return true; }
      if (stage === 'index') pushEntry();
      stage = gid;
      themePane.scrollTop = 0;
      paintStage();
      refreshAll();
      var f = firstControl(b.el);
      if (f) { try { f.focus({ preventScroll: true }); } catch (e) {} }
      return true;
    }
    /* LEAVING IT: the index on stage again; `spend` says whether the entry the theme pushed is given back (the ‹)
       or was given back already (the gesture).  The theme slides out and is drawn until it is gone. */
    function leaveStage(spend) {
      if (stage === 'index') return false;
      var was = stage;
      stage = 'index';
      if (spend) spendEntries('back-button', 1);
      finishLeave();
      if (slow()) { leaving = was; leaveTimer = setTimeout(finishLeave, 220); }
      paintStage();
      refreshAll();
      return was;
    }
    function back() {
      if (!isUp || !sheet) return false;
      var was = leaveStage(true);
      if (!was) return false;
      // the keyboard's place goes to the row that was open, and the index is where it was left
      var r = byId[was] && byId[was].irow.el;
      if (r && !r.hidden) {
        try { r.focus({ preventScroll: true }); } catch (e) {}
        try { r.scrollIntoView({ block: 'nearest' }); } catch (e) {}
      }
      return true;
    }
    function open(gid) {
      if (dead || !build()) return false;
      placeButton();
      wire();
      if (!isUp) {
        isUp = true;
        tall = readTall();
        stage = 'index';
        finishLeave();
        panel.hidden = false;
        present();
        refreshAll();
        document.documentElement.classList.add('pg-open');
        btn.setAttribute('aria-expanded', 'true');
        if (sheet) { stack = []; pushEntry(); }
        document.addEventListener('keydown', onKey);
        document.addEventListener('click', onClick, true);
        told.forEach(function (fn) { safe(fn, true); });
        try { panel.focus({ preventScroll: true }); } catch (e) {}
        indexPane.scrollTop = 0;
        if (!sheet) bodyEl.scrollTop = 0;
      }
      if (gid) {
        var id = String(gid);
        if (sheet) enter(id);
        else scrollToGroup(id);
      }
      return true;
    }
    function firstControl(g) {
      var all = g.querySelectorAll('button, input, select, a[href]');
      for (var i = 0; i < all.length; i++) {
        if (!all[i].disabled && drawn(all[i]) && all[i].tabIndex >= -1) {
          // a radio group's chips are reached by the one that is checked
          if (all[i].getAttribute('role') === 'radio' && all[i].tabIndex < 0) continue;
          return all[i];
        }
      }
      return null;
    }
    function close(how) {
      if (!isUp) return;
      isUp = false;
      var inside = panel.contains(document.activeElement);
      panel.hidden = true;
      document.documentElement.classList.remove('pg-open', 'pg-sheet');
      btn.setAttribute('aria-expanded', 'false');
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onClick, true);
      panel.style.transform = '';
      panel.style.height = '';
      stage = 'index';
      finishLeave();
      paintStage();
      homeAll();
      // both entries at once where a theme was up, and none that a gesture has spent already
      spendEntries(how, 0);
      // the keyboard's place goes back to the button, where it was in the panel
      if (inside && how !== 'outside' && drawn(btn)) { try { btn.focus({ preventScroll: true }); } catch (e) {} }
      told.forEach(function (fn) { safe(fn, false); });
    }
    function toggle() { if (isUp) close('toggle'); else open(); }

    /* THE HEAD IS THE SHEET'S HANDLE.  A drag on it moves the sheet: DOWN from half closes it (let go short of
       a third of its height, slowly, and it springs back, as the dictionary's does); UP from half makes it
       tall, and DOWN from tall brings it to half, each once it has gone a third of the way between the two
       (a flick does the same from less).  A tap on the grab line toggles tall and half; the grab line is a
       button of its own so that the title stays a title, and a drag may start on it as well, so the press is
       judged here, by how far it went, rather than by a click that pointer capture would take away. */
    function swipe() {
      var y0 = 0, dy = 0, t0 = 0, h0 = 0, on = false, grip = false;
      headEl.addEventListener('pointerdown', function (e) {
        if (!sheet || e.button > 0) return;
        grip = !!(e.target.closest && e.target.closest('.pg-grip'));
        // ‹ is a button, not a handle (✕ is out of the head on the sheet)
        if (!grip && e.target.closest && e.target.closest('button')) return;
        try { headEl.setPointerCapture(e.pointerId); } catch (err) {}
        on = true; y0 = e.clientY; dy = 0; t0 = Date.now(); h0 = panel.offsetHeight;
        panel.classList.add('pg-drag');
      });
      headEl.addEventListener('pointermove', function (e) {
        if (!on) return;
        dy = e.clientY - y0;
        if (tall) {
          // from tall the sheet shortens under the finger, no further than half
          panel.style.height = dy > 0 ? Math.max(halfH(), h0 - dy) + 'px' : '';
          panel.style.transform = '';
        } else if (dy < 0) {
          // from half it grows, no further than tall
          panel.style.height = Math.min(tallH(), h0 - dy) + 'px';
          panel.style.transform = '';
        } else {
          panel.style.height = '';
          panel.style.transform = dy ? 'translateY(' + dy + 'px)' : '';
        }
      });
      function end(e) {
        if (!on) return;
        on = false;
        panel.classList.remove('pg-drag');
        var gone = Math.abs(dy), took = Math.max(1, Date.now() - t0);
        var flick = gone > 24 && gone / took > 0.6, span = tallH() - halfH(), third = Math.max(24, span / 3);
        var cancelled = e && e.type === 'pointercancel';
        panel.style.height = '';
        panel.style.transform = '';
        if (!cancelled && grip && gone < 8 && took < 600) { setTall(!tall); return; }
        if (cancelled) return;
        if (dy > 0) {
          if (tall) { if (span > 0 && (dy > third || flick)) setTall(false); }
          else if (dy > Math.min(120, panel.offsetHeight * 0.3) || flick) close('swipe');
        } else if (dy < 0 && !tall && span > 0 && (-dy > third || flick)) setTall(true);
      }
      headEl.addEventListener('pointerup', end);
      headEl.addEventListener('pointercancel', end);
    }

    /* ----------------------------------------------- following the page */
    var modeOff = safe(onModeFn, function () {
      placeButton();
      if (panel) { refreshAll(); if (isUp) onResize(); }
    });
    window.addEventListener('resize', syncButton);
    cleanups.push(function () { window.removeEventListener('resize', syncButton); });

    /* THE BUTTON'S PLACE MAY BE BUILT AFTER THE GEAR (a page that draws its
       bar once its data has come): looked for as the page grows, for a few
       seconds, as lib/explain.js looks for its bar. */
    function arrive() {
      placeButton();
      if (!document.body) return;
      if (window.MutationObserver) {
        placing = new MutationObserver(function () {
          var h = hostOf(mobile() ? 'mobile' : 'browser');
          if (h && btn.parentNode !== h) placeButton();
        });
        placing.observe(document.documentElement, { childList: true, subtree: true });
        setTimeout(function () { if (placing) { placing.disconnect(); placing = null; } }, 10000);
      }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrive);
    else arrive();
    placeButton();

    var handle = {
      open: open, close: function () { close('page'); }, toggle: toggle,
      isOpen: function () { return isUp; },
      // 'index' or the theme on stage while the sheet is up; null on the popover or shut
      stage: function () { return isUp && sheet ? stage : null; },
      back: back,
      // everything asked again; and the button looked for again, should its place have come late
      refresh: function () { placeButton(); refreshAll(); },
      onToggle: function (fn) {
        if (typeof fn !== 'function') return function () {};
        told.push(fn);
        return function () { var k = told.indexOf(fn); if (k >= 0) told.splice(k, 1); };
      },
      button: btn,
      unmount: unmount, destroy: unmount
    };
    /* UNMOUNTED: the panel shut, every node it borrowed sent home, the button
       and the panel taken out of the page, every listener and every watch let
       go.  Where this was the gear in force, the page is told (parseh:gear). */
    function unmount() {
      if (dead) return;
      if (isUp) close('unmount');
      homeAll();
      dead = true;
      unwire();
      unwatchers.forEach(function (u) { safe(u); });
      cleanups.forEach(function (c) { safe(c); });
      if (typeof modeOff === 'function') safe(modeOff);
      if (placing) { placing.disconnect(); placing = null; }
      document.removeEventListener('DOMContentLoaded', arrive);
      if (btn.parentNode) btn.parentNode.removeChild(btn);
      if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
      panel = null;
      told.length = 0;
      if (current === handle) { current = null; announce('unmounted'); }
    }
    return handle;
  }

  /* THE GEAR, FOUND BY THE LAYERS THAT USED TO DO ITS WORK: the readers' ⋯
     menu (lib/mobilereader.js, lib/mobileplayer.js) and the Aa panel
     (Parseh.typo) stop drawing their own where there is a gear.  They ask
     `ParsehGear.mounted()` -- the handle in force, or null -- when they start,
     and listen on `document` for `parseh:gear` (detail 'mounted' or
     'unmounted') afterwards.  A second mount REPLACES the first without a
     word of 'unmounted' between: the page has a gear all the while. */
  function announce(what) {
    try { document.dispatchEvent(new CustomEvent('parseh:gear', { detail: what })); } catch (e) {}
  }
  function mount(spec) {
    if (current) {
      var old = current;
      current = null;
      try { old.unmount(); } catch (e) { warn(e); }
    }
    current = make(spec);
    announce('mounted');
    return current;
  }

  window.ParsehGear = { mount: mount, mounted: function () { return current; }, std: std,
                        KINDS: Object.keys(KINDS), version: 1 };
})();
