// SPDX-License-Identifier: GPL-3.0-or-later
/* Parseh — REVIEW LATER: the chunks a person flagged while reading or
   watching, kept by the toolbox, listed in a sidebar and on a page (a0.5.0).

   Reading a book or watching a video, a person flags a chunk and goes on --
   the pace is not broken -- and comes back to the list later: to go to a
   chunk, to make its card, to test themselves on it, to copy the list.

   THE FLAGS ARE THE PERSON'S, not a book's (lib/later.py, config/prefs.json):
   they follow the person from the phone to the computer, are never written
   into a book, and are not in a book's bundle.  This file is the whole of the
   browser's side of them, in four parts:

     1. THE STORE.  A copy in localStorage (`parseh_later`: every flag AND
        every removal, which a device needs to know what it must not bring
        back) and an OUTBOX of changes not yet told to the computer
        (`parseh_later_out`), replayed at load, when the browser comes back
        online, when the page is shown again, and after every change; a
        failure is swallowed and the change waits (the precedent is the deck
        answers' outbox in markdown/app/static/decks.js).  Then the computer's
        list is asked for and merged: PER FLAG THE NEWEST CHANGE WINS, a
        removal is not undone by a device that still holds the flag, and what
        this device changed away from the computer is laid on top -- so
        nothing is lost, and nothing comes back.
     2. IDENTITY.  A flag's id is made from what the chunk IS (idFor), so one
        chunk flagged on two devices is one flag.
     3. THE SIDEBAR, ParsehLater.panel(adapter): a button «⚑ later 3» and the
        list -- a right-hand panel on a wide screen, a bottom sheet on a phone.
     4. THE PAGE, /later/ (lib/laterpage.py): the same list across every book
        and video, drawn into any element marked `data-later-page`.

   THE API, for the reader's and the player's adapters (the pages call it; none
   of it edits a book or a video):

     ParsehLater.ready()            -> Promise<{synced}>: the first look at the
                                       computer's list is over (or gave up after
                                       4 s).  The copy is usable at once, without it.
     ParsehLater.has(id)            -> bool: is this chunk flagged now?
     ParsehLater.get(id)            -> the flag, or null
     ParsehLater.list({ref})        -> the live flags of one book or video in
                                       reading order; list() all of them, newest first
     ParsehLater.count({ref})       -> how many (of one book or video, or all)
     ParsehLater.add(record)        -> Promise<record>: flagged at once in the copy,
                                       queued for the computer; events fire.  Flagging
                                       a chunk already flagged changes nothing.
     ParsehLater.remove(id, opts)   -> Promise<bool>: the same, for a removal; opts.toast is
                                       the words of the «… · Undo» line (default 'removed'),
                                       or false for none
     ParsehLater.toggle(record, opts) -> Promise<bool>: flagged if it was not (and true), taken off
                                       if it was (with its Undo; false) -- the cloud's button and
                                       the L key
     ParsehLater.undo()             -> Promise<record|false>: the last removal, taken back
     ParsehLater.on('change', fn)   -> a function that stops it; fn({ref}) after every change
                                       to the flags of that book or video, made here or
                                       learned from the computer or another tab (and the
                                       document hears `parseh:later` with {detail: {ref}})
     ParsehLater.sync()             -> Promise<bool>: send what waits and ask again, now
     ParsehLater.pending()          -> how many changes have not reached the computer
     ParsehLater.idFor(parts)       -> the id of a chunk: {kind, ref, sub|start, k|j, text}
     ParsehLater.record(parts)      -> a whole flag from what a page knows (below)
     ParsehLater.href(record)       -> the address that opens the book or the video AT the
                                       chunk: <reader or player path>#later=<id, encoded>
     ParsehLater.fromHash(hash)     -> the id in `#later=<id>` (this page's, if none is given); the
                                       flag itself is ParsehLater.get(id) once ready() has resolved
                                       (a device that never had it learns of it from the computer)
     ParsehLater.refOf(path)        -> what this page's flags are kept under: a reader's path without
                                       its index.html, a video page's id; null for any other page
     ParsehLater.panel(adapter)     -> {open({id}?), close(), toggle(), isOpen(), button, onToggle(fn),
                                        refresh(), destroy()} -- open({id}) opens it ON that flag
     ParsehLater.page(element)      -> draws the list across every book and video

   A FLAG'S SHAPE (lib/later.py checks and clamps it):
     {id, kind: 'book'|'video', ref, lang, glossLang, title, at, by,
      where: book {sub, k, para, label, chapter, t} | video {start, j, text},
      text, kana, tr, en, voc, sentence}
   -- `ref` is the reader's path (/books/<folder>/<slug>/reader/) or the
   video's id; `at` is when it was flagged, in seconds, by the computer's
   clock as near as this device can tell; the texts are PLAIN text: the chunk,
   its reading, its transliteration, its gloss, its vocabulary line and its
   sentence.  ParsehLater.record() takes the same names flat, with the parts
   of `where` beside them ({kind, ref, lang, glossLang, title, sub, k, para,
   label, chapter, t, text, ...} or {..., start, j, cap, text, ...}), and
   fills id, at and by.

   THE ADAPTER a page hands to panel() says what a book or a video can do,
   and the panel asks it for everything that touches the page:

     { kind: 'book' | 'video',
       ref, title, lang, glossLang,                 // this book's or video's
       canCard()      -> bool,                      // may a card be made here now?  (never on a phone)
       locate(record) -> Promise<{found: bool}>,    // is the chunk still where it was saved?
       goTo(record)   -> Promise,                   // take the reader or the player there
       makeCard?(record) -> Promise<{saved: bool}>, // open the card sheet; saved -> the flag leaves
       queue?(records)   -> Promise,                // «make cards one after another»
       label?(record)    -> string }                // the place, in the page's own words

   A chunk `locate` cannot find is ADRIFT: listed with the text and the gloss it
   was saved with, ▶ and + card shut with the reason, still removable and copyable.
   ▶ closes the panel after goTo; + card leaves the panel where it is, and the
   flag goes when the card is saved.  `queue` is for the page to run the sheet one
   chunk after another; it takes a flag off with ParsehLater.remove(id, {toast}) as
   each card is saved.

   NO HTML IS EVER MADE FROM A STRING IN THIS FILE (tests pin it): everything is
   built with createElement and textContent, so that nothing a book says can be
   taken for markup.  Sizes of fixed boxes are written with percentages and a
   CSS variable, never the viewport's units, so that the page's zoom
   (lib/pagezoom.js) cannot make them wrong. */
(function () {
  'use strict';
  if (window.ParsehLater) return;

  // where this script came from: the sheet beside it is fetched from there, as parseh.js loads its own helpers
  var SELF = document.currentScript && document.currentScript.src;
  var KEY = 'parseh_later';               // the copy: every flag and every removal this device knows
  var OUTBOX = 'parseh_later_out';        // the changes the computer has not been told
  var SKEW = 'parseh_later_skew';         // how far this device's clock is from the computer's
  var SCOPE = 'parseh_later_scope';       // «this book only» or «everything», for the sidebar
  var DOOR = '/__later';
  var TOMB_KEEP = 90 * 86400;             // a removal is remembered this long (lib/later.py)
  var SIX = 6000;                         // how long «removed · Undo» stays
  var LIMIT = {id: 300, text: 600, other: 600, voc: 1200, sentence: 800, by: 60, label: 80,
               chapter: 300, sub: 200, para: 40};
  // the shapes lib/later.py holds a place and an id to: a reader's path as the
  // toolbox serves it, and a video's id
  var SEG = '[A-Za-z0-9][A-Za-z0-9._-]{0,80}';
  var BOOK_REF = new RegExp('^/books/(?:' + SEG + '/){1,2}reader/$');
  var VIDEO_REF = /^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/;
  var ID_SHAPE = new RegExp('^later:(?:(book):(/books/(?:' + SEG + '/){1,2}reader/)|' +
                            '(video):([A-Za-z0-9][A-Za-z0-9._-]{0,120})):[A-Za-z0-9_.:/@%+=~-]*$');
  var KEYPART = /^[A-Za-z0-9._:@%+=~-]*$/;
  var LANG_SHAPE = /^[A-Za-z][A-Za-z0-9_-]{0,15}$/;

  /* ------------------------------------------------------------ small helpers */
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
  function parse(raw, fallback) {
    if (!raw) return fallback;
    try { var v = JSON.parse(raw); return v && typeof v === 'object' ? v : fallback; }
    catch (e) { return fallback; }
  }
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
    if (on) b.addEventListener('click', on);
    return b;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
  function isNum(x) { return typeof x === 'number' && isFinite(x); }

  /* THE CLOCK.  A flag carries the moment it was made, and the newest change
     wins -- so the clocks of two devices have to agree.  The computer says
     what time it is with every answer; this device keeps how far its own is
     from that, and stamps by it.  A device never asked has no correction. */
  var skew = +get(SKEW) || 0;
  function nowS() { return Date.now() / 1000 + skew; }
  function learnClock(serverNow) {
    if (!isNum(serverNow)) return;
    var d = serverNow - Date.now() / 1000;
    skew = Math.abs(d) < 86400 ? Math.round(d * 10) / 10 : 0;
    put(SKEW, String(skew));
  }

  /* The device, named by itself as lib/prefs.js does -- prefs.js may not have
     loaded yet, so it is told again here. */
  function device() {
    try { if (window.ParsehPrefs && ParsehPrefs.device) return ParsehPrefs.device(); } catch (e) {}
    var ua = navigator.userAgent || '';
    var what = /Android/i.test(ua) ? (/Mobile/.test(ua) ? 'Android phone' : 'Android tablet')
             : /iPhone/i.test(ua) ? 'iPhone' : /iPad/i.test(ua) ? 'iPad'
             : /Windows/i.test(ua) ? 'Windows computer'
             : /Macintosh|Mac OS/i.test(ua) ? 'Mac' : /CrOS/i.test(ua) ? 'Chromebook'
             : /Linux/i.test(ua) ? 'Linux computer' : 'this device';
    var who = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Firefox\//.test(ua) ? 'Firefox'
            : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : '';
    return who ? what + ' · ' + who : what;
  }

  /* HOW LONG AGO, in the words lib/prefs.js uses for the reading place. */
  function when(at) {
    var s = Math.max(0, nowS() - (at || 0));
    if (s < 90) return 'a moment ago';
    if (s < 3600) return Math.round(s / 60) + ' minutes ago';
    if (s < 7200) return 'an hour ago';
    if (s < 86400) return Math.round(s / 3600) + ' hours ago';
    if (s < 172800) return 'yesterday';
    return Math.round(s / 86400) + ' days ago';
  }
  function clock(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = sec % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  /* ------------------------------------------------------------- languages */
  /* The names and directions a language has.  /later/ is handed the whole
     registry (data-langs); on a page that was not, /lib/langs.css says it
     for every language of the registry (--tl-name, --tl-dir on anything
     that names a language), and a code it does not know is shown as itself.
     No list of the languages here: one added to the registry is named at once. */
  var LANGS = {};
  var RTL = {fa: 1, ar: 1, he: 1, ur: 1, ps: 1, sd: 1, ug: 1, yi: 1, dv: 1, ckb: 1};
  var dirs = {}, names = {};
  /* what /lib/langs.css puts on an element that names this language */
  function token(code, prop) {
    if (!document.body) return '';
    try {
      var probe = el('span');
      probe.setAttribute('data-lang', code);
      document.body.appendChild(probe);
      var v = (getComputedStyle(probe).getPropertyValue(prop) || '').trim();
      document.body.removeChild(probe);
      return v;
    } catch (e) { return ''; }
  }
  function langName(code) {
    if (!code) return '';
    if (typeof LANGS[code] === 'string') return LANGS[code];
    if (LANGS[code] && LANGS[code].name) return LANGS[code].name;
    if (!(code in names)) {
      var v = token(code, '--tl-name'), m = /^"(.*)"$/.exec(v) || /^'(.*)'$/.exec(v);
      names[code] = m ? m[1].replace(/\\(.)/g, '$1') : '';
    }
    return names[code] || code;
  }
  /* The direction of a language: the registry's own word where the page was
     given it, else what /lib/langs.css puts on anything that names a language
     (--tl-dir), else the right-to-left scripts there are. */
  function dirOf(code) {
    if (!code) return 'auto';
    if (dirs[code]) return dirs[code];
    var d = '';
    if (LANGS[code] && LANGS[code].dir) d = LANGS[code].dir;
    if (!d) d = token(code, '--tl-dir');
    if (d !== 'rtl' && d !== 'ltr') d = RTL[code] ? 'rtl' : 'ltr';
    return (dirs[code] = d);
  }
  function tag(node, code) {
    if (code) {
      node.setAttribute('lang', code);
      node.setAttribute('data-lang', code);
      node.setAttribute('dir', dirOf(code));
    } else node.setAttribute('dir', 'auto');
    return node;
  }

  /* --------------------------------------------------------------- identity */
  /* cyrb53: a small synchronous string hash, the same on every device. */
  function hash(str) {
    var h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (var i = 0; i < str.length; i++) {
      var ch = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761);
      h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return 4294967296 * (2097151 & h2) + (h1 >>> 0);
  }
  /* A chunk's text as the id sees it: composed, with every run of spaces one. */
  function normal(text) {
    var s = String(text == null ? '' : text);
    try { s = s.normalize('NFC'); } catch (e) {}
    return s.replace(/\s+/g, ' ').trim();
  }
  function num(v, fallback) { v = +v; return isNum(v) ? v : fallback; }
  function startText(start) { return String(Math.round(Math.max(0, num(start, 0)) * 1000) / 1000); }
  /* THE ID OF A CHUNK: later:<kind>:<ref>:<its place>:<its number>:<a hash of its
     text>.  A book's place is the subparagraph's key and its number the chunk's
     index inside it; a video's place is the caption's start and its number the
     phrase's index.  Nothing in it depends on which device made it, or on the
     numbers a page gives its chunks while it draws them (they move). */
  function idFor(p) {
    p = p || {};
    var w = p.where || {};
    var kind = p.kind === 'video' ? 'video' : 'book';
    var at = kind === 'book' ? String(p.sub != null ? p.sub : (w.sub != null ? w.sub : ''))
                             : startText(p.start != null ? p.start : w.start);
    var n = kind === 'book' ? (p.k != null ? p.k : w.k) : (p.j != null ? p.j : w.j);
    return 'later:' + kind + ':' + p.ref + ':' + at + ':' + Math.max(0, Math.floor(num(n, 0))) + ':' +
           hash(normal(p.text)).toString(36);
  }

  /* ------------------------------------------------------ checking a record */
  function clip(v, limit, lines) {
    if (typeof v === 'number' && isFinite(v)) v = String(v);
    if (typeof v !== 'string') return '';
    var s = v.replace(/\r\n?/g, '\n').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '');
    if (lines) s = s.split('\n').map(function (l) { return l.split(/\s+/).filter(Boolean).join(' '); })
                    .filter(Boolean).join('\n');
    else s = s.split(/\s+/).filter(Boolean).join(' ');
    return s.slice(0, limit);
  }
  function keyPart(v, limit) {
    var s = typeof v === 'string' ? v.trim().slice(0, limit) : '';
    return KEYPART.test(s) ? s : '';
  }
  function whole(v, hi) { return Math.floor(Math.min(Math.max(num(v, 0), 0), hi)); }
  /* A flag as it is kept, or an Error that says why it cannot be one: the
     checks lib/later.py makes, made here first so that the page learns of a
     bad one at once instead of the computer refusing it later. */
  function cleanRecord(r) {
    if (!r || typeof r !== 'object') throw new Error('a flag is an object');
    var kind = r.kind;
    if (kind !== 'book' && kind !== 'video') throw new Error("a flag's kind is 'book' or 'video'");
    var ref = typeof r.ref === 'string' ? r.ref : '';
    if (!(kind === 'book' ? BOOK_REF : VIDEO_REF).test(ref))
      throw new Error("a place is a book's reader path or a video's id");
    var text = clip(r.text, LIMIT.text);
    if (!text) throw new Error("a flag has the chunk's text");
    var w = r.where && typeof r.where === 'object' ? r.where : {};
    var id = r.id || idFor({kind: kind, ref: ref, where: w, text: text});
    if (typeof id !== 'string' || id.length > LIMIT.id || !ID_SHAPE.test(id) ||
        id.indexOf('later:' + kind + ':' + ref + ':') !== 0)
      throw new Error("the flag's id is not this chunk's");
    var where = kind === 'book'
      ? {sub: keyPart(w.sub, LIMIT.sub), k: whole(w.k, 100000), para: keyPart(w.para, LIMIT.para),
         label: clip(w.label, LIMIT.label), chapter: clip(w.chapter, LIMIT.chapter),
         t: w.t == null || !isNum(+w.t) ? null : Math.min(Math.max(+w.t, 0), 1e7)}
      : {start: Math.min(Math.max(num(w.start, 0), 0), 1e7), j: whole(w.j, 100000),
         text: clip(w.text, LIMIT.text)};
    var at = isNum(r.at) ? r.at : nowS();
    return {id: id, kind: kind, ref: ref,
            lang: LANG_SHAPE.test(r.lang || '') ? r.lang : '',
            glossLang: LANG_SHAPE.test(r.glossLang || '') ? r.glossLang : '',
            title: clip(r.title, LIMIT.other), at: at, by: clip(r.by || device(), LIMIT.by),
            where: where, text: text, kana: clip(r.kana, LIMIT.other), tr: clip(r.tr, LIMIT.other),
            en: clip(r.en, LIMIT.other), voc: clip(r.voc, LIMIT.voc, true),
            sentence: clip(r.sentence, LIMIT.sentence, true)};
  }
  /* A flag from what a page knows: the parts of `where` may stand beside the
     rest, flat.  Fills id, at and by. */
  function record(p) {
    p = p || {};
    var kind = p.kind === 'video' ? 'video' : 'book';
    var w = p.where || {};
    var where = kind === 'book'
      ? {sub: p.sub != null ? p.sub : w.sub, k: p.k != null ? p.k : w.k, para: p.para != null ? p.para : w.para,
         label: p.label != null ? p.label : w.label, chapter: p.chapter != null ? p.chapter : w.chapter,
         t: p.t != null ? p.t : w.t}
      : {start: p.start != null ? p.start : w.start, j: p.j != null ? p.j : w.j,
         text: p.cap != null ? p.cap : w.text};
    var r = {kind: kind, ref: p.ref, lang: p.lang, glossLang: p.glossLang, title: p.title, where: where,
             text: p.text, kana: p.kana, tr: p.tr, en: p.en, voc: p.voc, sentence: p.sentence,
             at: isNum(p.at) ? p.at : nowS(), by: p.by || device()};
    r.id = p.id || idFor({kind: kind, ref: p.ref, where: where, text: p.text});
    return cleanRecord(r);
  }

  /* ----------------------------------------------------------------- the store */
  var cache = {};          // id -> a flag, or {id, gone, kind, ref} where it was removed
  var out = [];            // [{op: 'add', record} | {op: 'remove', id, at}], the last change of each id
  var rawCache = null, rawOut = null;
  var undoStack = [];
  var listeners = {change: [], sync: []};

  function stamp(e) { return e.gone !== undefined ? e.gone : e.at; }
  /* A copy worth keeping: a removal with its moment, or a flag with a place of
     the shape the computer holds and the text of a chunk.  What is anything else
     -- a copy a browser extension or a hand has changed -- is dropped on reading,
     so that nothing in it ever reaches a link or the page. */
  function sound(e) {
    return !!(e && typeof e === 'object' && typeof e.id === 'string' &&
      (e.gone !== undefined ? isNum(e.gone)
        : (isNum(e.at) && (e.kind === 'book' || e.kind === 'video') && typeof e.ref === 'string' &&
           (e.kind === 'book' ? BOOK_REF : VIDEO_REF).test(e.ref) && typeof e.text === 'string')));
  }
  // false once the browser has refused to keep anything (a private window, a
  // full disk): the page then goes on from memory for as long as it is open,
  // and what it holds must not be replaced by an empty storage
  var keeping = true;
  function readStore() {
    rawCache = get(KEY);
    rawOut = get(OUTBOX);
    var c = parse(rawCache, {}), o = parse(rawOut, []);
    cache = {};
    Object.keys(c).forEach(function (id) { if (sound(c[id]) && c[id].id === id) cache[id] = c[id]; });
    out = Array.isArray(o) ? o.filter(function (op) {
      return op && (op.op === 'add' ? sound(op.record) : op.op === 'remove' && typeof op.id === 'string' && isNum(op.at));
    }) : [];
  }
  /* The outbox goes first: it is what must not be lost. */
  function writeStore() {
    gcTombs();
    rawOut = JSON.stringify(out);
    var ok = put(OUTBOX, rawOut);
    rawCache = JSON.stringify(cache);
    if (!put(KEY, rawCache)) {
      // no room: the removals are what can go (they are only a courtesy to
      // another device), the flags stay
      Object.keys(cache).forEach(function (id) { if (cache[id].gone !== undefined) delete cache[id]; });
      rawCache = JSON.stringify(cache);
      ok = put(KEY, rawCache) && ok;
    }
    keeping = ok;
  }
  function gcTombs() {
    var old = nowS() - TOMB_KEEP;
    Object.keys(cache).forEach(function (id) { if (cache[id].gone !== undefined && cache[id].gone < old) delete cache[id]; });
  }
  /* Another tab may have written since this one last read: before changing
     anything, take its copy if it is not ours. */
  function freshen() {
    if (keeping && (get(KEY) !== rawCache || get(OUTBOX) !== rawOut)) readStore();
  }

  function idParts(id) {
    var m = ID_SHAPE.exec(id);
    return m ? {kind: m[1] || m[3], ref: m[2] || m[4]} : null;
  }
  /* ONE CHANGE onto a set of flags, by the one rule lib/later.py keeps: an add
     replaces a flag that is not newer and revives a removal it is newer than;
     a remove takes a flag that is not newer and leaves a tombstone.  -> true
     when `items` changed. */
  function applyOp(items, op) {
    var was, at;
    if (op.op === 'add') {
      var r = op.record;
      was = items[r.id];
      if (was && sound(was)) {
        if (was.gone !== undefined) { if (!(r.at > was.gone)) return false; }
        else if (r.at < was.at) return false;
      }
      items[r.id] = r;
      return true;
    }
    at = op.at;
    was = items[op.id];
    if (was && sound(was)) {
      if (was.gone !== undefined) {
        if (at > was.gone) { items[op.id] = {id: op.id, gone: at, kind: was.kind, ref: was.ref}; return true; }
        return false;
      }
      if (at < was.at) return false;
      items[op.id] = {id: op.id, gone: at, kind: was.kind, ref: was.ref};
      return true;
    }
    var p = idParts(op.id);
    items[op.id] = {id: op.id, gone: at, kind: p ? p.kind : '', ref: p ? p.ref : ''};
    return true;
  }
  function opId(op) { return op.op === 'add' ? op.record.id : op.id; }
  function opKey(op) { return op.op + '|' + opId(op) + '|' + (op.op === 'add' ? op.record.at : op.at); }
  /* A change is made: laid on the copy at once, queued for the computer. */
  function commit(op) {
    applyOp(cache, op);
    out = out.filter(function (o) { return opId(o) !== opId(op); });
    out.push(op);
    writeStore();
  }

  function fire(name, detail) {
    (listeners[name] || []).slice().forEach(function (fn) { try { fn(detail); } catch (e) {} });
  }
  function emit(refs) {
    var seen = {};
    refs.forEach(function (ref) {
      if (seen[ref]) return;
      seen[ref] = 1;
      fire('change', {ref: ref});
      try { document.dispatchEvent(new CustomEvent('parseh:later', {detail: {ref: ref}})); } catch (e) {}
    });
  }
  /* The refs whose flags differ between two sets. */
  function differ(a, b) {
    var refs = [], seen = {};
    function note(e) { if (e && e.ref !== undefined && !seen[e.ref]) { seen[e.ref] = 1; refs.push(e.ref); } }
    Object.keys(a).forEach(function (id) {
      var x = a[id], y = b[id];
      if (!y || (x.gone !== undefined) !== (y.gone !== undefined) || stamp(x) !== stamp(y)) { note(x); note(y); }
    });
    Object.keys(b).forEach(function (id) { if (!a[id]) note(b[id]); });
    return refs;
  }

  /* ---- the API over the copy */
  function live() {
    return Object.keys(cache).map(function (id) { return cache[id]; }).filter(function (e) { return e.gone === undefined; });
  }
  function has(id) { var e = cache[id]; return !!(e && e.gone === undefined); }
  function getOne(id) { return has(id) ? cache[id] : null; }

  /* READING ORDER.  A book: by the paragraph (chapter:paragraph), then the
     subparagraph's own number, then the chunk's place in it.  A video: by the
     caption's start, then the phrase.  Where two are alike, the older first. */
  function digits(s) { return (String(s || '').match(/\d+/g) || []).map(Number); }
  function cmpDigits(a, b) {
    for (var i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] === undefined) return -1;
      if (b[i] === undefined) return 1;
      if (a[i] !== b[i]) return a[i] - b[i];
    }
    return 0;
  }
  function reading(a, b) {
    var x = a.where || {}, y = b.where || {};
    if (a.kind === 'video' || b.kind === 'video')
      return (num(x.start, 0) - num(y.start, 0)) || (num(x.j, 0) - num(y.j, 0)) || (a.at - b.at);
    return cmpDigits(digits(x.para), digits(y.para)) || cmpDigits(digits(x.label || x.sub), digits(y.label || y.sub)) ||
           (num(x.k, 0) - num(y.k, 0)) || (a.at - b.at);
  }
  function list(o) {
    var ref = o && o.ref, all = live();
    if (ref === undefined || ref === null) return all.sort(function (a, b) { return b.at - a.at; });
    return all.filter(function (e) { return e.ref === ref; }).sort(reading);
  }
  function count(o) {
    var ref = o && o.ref;
    return live().filter(function (e) { return ref === undefined || ref === null || e.ref === ref; }).length;
  }

  function add(r) {
    var rec;
    try { rec = cleanRecord(r); } catch (e) { return Promise.reject(e); }
    freshen();
    var was = cache[rec.id];
    // already flagged: nothing to say again
    if (was && was.gone === undefined) return Promise.resolve(was);
    // and never older than what removed it here, however the clocks stand
    if (was && was.gone !== undefined && !(rec.at > was.gone)) rec.at = was.gone + 0.001;
    commit({op: 'add', record: rec});
    emit([rec.ref]);
    kick();
    return Promise.resolve(rec);
  }
  function remove(id, opts) {
    freshen();
    var was = cache[id];
    if (!was || was.gone !== undefined) return Promise.resolve(false);
    commit({op: 'remove', id: id, at: Math.max(nowS(), was.at + 0.001)});
    undoStack.push(was);
    if (undoStack.length > 10) undoStack.shift();
    emit([was.ref]);
    kick();
    if (!opts || opts.toast !== false) snack(opts && typeof opts.toast === 'string' ? opts.toast : 'removed', true);
    return Promise.resolve(true);
  }
  function undo() {
    var was = undoStack.pop();
    hideSnack();
    if (!was) return Promise.resolve(false);
    return add(Object.assign({}, was, {at: nowS()}));
  }
  /* The «review later» button of a cloud and the L key: flag the chunk if it is
     not flagged, take it off if it is (with its Undo).  -> Promise<bool>, whether
     it is flagged now. */
  function toggle(r, opts) {
    var rec;
    try { rec = cleanRecord(r); } catch (e) { return Promise.reject(e); }
    freshen();
    if (has(rec.id)) return remove(rec.id, opts).then(function () { return false; });
    return add(rec).then(function () { return true; });
  }
  /* A page's address -> what its flags are kept under: a reader's path with its
     index.html taken off, or a video page's id; null for any other page. */
  function refOf(path) {
    path = String(path == null ? location.pathname : path).split(/[?#]/)[0];
    var b = /^(\/books\/(?:[^\/]+\/){1,2}reader\/)(?:index\.html)?$/.exec(path);
    if (b) return b[1];
    var v = /^\/youtube\/v\/([^\/]+)\/(?:index\.html)?$/.exec(path);
    return v ? v[1] : null;
  }
  function on(name, fn) {
    if (!listeners[name]) listeners[name] = [];
    listeners[name].push(fn);
    return function () {
      var k = listeners[name].indexOf(fn);
      if (k >= 0) listeners[name].splice(k, 1);
    };
  }

  /* ------------------------------------------------- telling the computer */
  function ask(url, init) {
    return (window.Parseh && Parseh.ask) ? Parseh.ask(url, init) : fetch(url, init);
  }
  var inflight = null, queued = null, retry = null, wait = 15000, lastSync = null;
  function acknowledge(batch) {
    freshen();
    var sent = {};
    batch.forEach(function (op) { sent[opKey(op)] = 1; });
    out = out.filter(function (op) { return !sent[opKey(op)]; });
    writeStore();
  }
  function post(ops) {
    return ask(DOOR, {method: 'POST', evenAway: true, headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({by: device(), ops: ops})});
  }
  /* A request the computer refused in words (400) holds a change it can never
     take; one such must not stop the rest for ever.  So they are sent one at a
     time, and those refused are dropped. */
  function isolate(batch) {
    var chain = Promise.resolve(true);
    batch.forEach(function (op) {
      chain = chain.then(function (okSoFar) {
        if (!okSoFar) return false;
        return post([op]).then(function (r) {
          if (r.ok) { acknowledge([op]); return true; }
          if (r.status === 400) { acknowledge([op]); return true; }
          return false;
        }, function () { return false; });
      });
    });
    return chain;
  }
  function send() {
    freshen();
    if (!out.length) return Promise.resolve(true);
    var batch = out.slice();
    return post(batch).then(function (r) {
      if (r.ok) { acknowledge(batch); return true; }
      if (r.status === 400) return isolate(batch);
      return false;                      // not let in, a worker's «needs the computer», a fault: they wait
    }, function () { return false; });
  }
  /* What the computer holds, with what this device changed since laid over it:
     the computer's list is the ground, the changes still in the outbox are
     replayed onto it by the same rule it applies them with.  A flag this
     device holds that the computer does not, and is not in the outbox, is one
     the computer has dropped -- not this device's to bring back. */
  function merge(items) {
    freshen();
    var next = {};
    items.forEach(function (e) { if (sound(e)) next[e.id] = e; });
    out.forEach(function (op) { applyOp(next, op); });
    var refs = differ(cache, next);
    cache = next;
    writeStore();
    emit(refs);
  }
  function pull() {
    return ask(DOOR + '?all=1&tomb=1').then(function (r) {
      if (!r.ok) throw new Error('the computer answered ' + r.status);
      return r.json();
    }).then(function (j) {
      if (!j || j.ok !== true || !Array.isArray(j.items)) throw new Error('not the flags');
      learnClock(j.now);
      merge(j.items);
      return true;
    });
  }
  function run() {
    inflight = send().then(function (sent) { return sent ? pull() : false; })
      .catch(function () { return false; })
      .then(function (ok) {
        inflight = null;
        lastSync = ok;
        clearTimeout(retry);
        retry = null;
        if (ok) wait = 15000;
        else if (!document.hidden) {
          // the computer may be a tunnel away: ask again, a little less often each time
          retry = setTimeout(sync, wait);
          wait = Math.min(wait * 2, 120000);
        }
        fire('sync', {ok: ok});
        return ok;
      });
    return inflight;
  }
  /* ONE LOOK AT A TIME, and a call is answered by one that BEGAN AFTER IT: a
     look already under way may have missed what was changed since it set out,
     so a call made meanwhile waits for it and then makes its own -- and every
     call made in that wait shares that one. */
  function sync() {
    if (location.protocol === 'file:') return Promise.resolve(false);
    if (!inflight) return run();
    if (!queued) queued = inflight.then(function () { queued = null; return run(); });
    return queued;
  }
  var kicked = null;
  function kick() {
    clearTimeout(kicked);
    kicked = setTimeout(sync, 350);
  }
  /* The first look at the computer's list, begun when this script runs; ready()
     is its end, or four seconds, whichever comes first. */
  var first = null, readyP = null;
  function ready() {
    if (!readyP) readyP = Promise.race([first || sync(), new Promise(function (done) { setTimeout(function () { done(false); }, 4000); })])
      .then(function (ok) { return {synced: !!ok}; });
    return readyP;
  }

  /* -------------------------------------------------------------- the toast */
  var snackEl = null, snackTimer = null;
  function hideSnack() {
    clearTimeout(snackTimer);
    if (snackEl) snackEl.classList.remove('ls-show');
  }
  /* «removed · Undo», six seconds; held while a pointer is over it or the
     keyboard is on its button, so that nobody loses the moment to reach it. */
  function snack(text, undoable) {
    if (!snackEl) {
      snackEl = el('div', 'ls');
      snackEl.id = 'later-snack';
      snackEl.setAttribute('role', 'status');
      snackEl.setAttribute('aria-live', 'polite');
      snackEl.setAttribute('lang', 'en');
      snackEl.setAttribute('dir', 'ltr');
      snackEl.appendChild(el('span', 'ls-text'));
      var u = button('ls-undo', 'Undo', 'put it back on the list', function () { undo(); });
      snackEl.appendChild(u);
      var hold = function () { clearTimeout(snackTimer); };
      var free = function () { snackTimer = setTimeout(hideSnack, SIX); };
      snackEl.addEventListener('mouseenter', hold);
      snackEl.addEventListener('mouseleave', free);
      snackEl.addEventListener('focusin', hold);
      snackEl.addEventListener('focusout', free);
      (document.body || document.documentElement).appendChild(snackEl);
    }
    snackEl.querySelector('.ls-text').textContent = text + (undoable ? ' · ' : '');
    snackEl.querySelector('.ls-undo').hidden = !undoable;
    void snackEl.offsetWidth;
    snackEl.classList.add('ls-show');
    clearTimeout(snackTimer);
    snackTimer = setTimeout(hideSnack, SIX);
  }

  /* ------------------------------------------------------- what a flag says */
  /* Where it is: «3.1 · Chapter 3» for a book, «12:41» for a video -- or the
     page's own words, where the adapter has them. */
  function placeText(rec, adapter) {
    if (adapter && rec.ref === adapter.ref && typeof adapter.label === 'function') {
      try { var said = adapter.label(rec); if (said) return String(said); } catch (e) {}
    }
    var w = rec.where || {};
    if (rec.kind === 'video') return clock(w.start);
    return [w.label, w.chapter].filter(Boolean).join(' · ');
  }
  function glossBits(rec) { return [rec.kana, rec.tr, rec.en, rec.voc && rec.voc.replace(/\n/g, '; ')].filter(Boolean); }
  function titleOf(rec) { return rec.title || (rec.kind === 'video' ? rec.ref : rec.ref.split('/').slice(-3, -2)[0]); }
  function refHref(rec) { return rec.kind === 'video' ? '/youtube/v/' + rec.ref + '/' : rec.ref; }
  function href(rec) { return refHref(rec) + '#later=' + encodeURIComponent(rec.id); }
  function fromHash(h) {
    var m = /(?:^|[#&])later=([^&]*)/.exec(h === undefined ? location.hash : String(h));
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return null; }
  }

  /* THE LIST AS TEXT: a markdown list under a heading for each book or video,
     and a table of tabs for a spreadsheet. */
  function oneLine(s) { return String(s == null ? '' : s).replace(/[\t\r\n]+/g, ' ').trim(); }
  function asMarkdown(groups, adapter) {
    var lines = [];
    groups.forEach(function (g) {
      if (lines.length) lines.push('');
      lines.push('## ' + oneLine(g.title) + (g.lang ? ' (' + langName(g.lang) + ')' : ''));
      lines.push('');
      g.items.forEach(function (rec) {
        var gloss = glossBits(rec).map(oneLine).join(' · '), place = oneLine(placeText(rec, adapter));
        lines.push('- **' + oneLine(rec.text) + '**' + (gloss ? ' — ' + gloss : '') + (place ? ' (' + place + ')' : ''));
      });
    });
    return lines.join('\n') + '\n';
  }
  function asTable(groups, adapter) {
    var rows = [['chunk', 'reading', 'transliteration', 'meaning', 'vocabulary', 'sentence', 'place', 'title', 'language', 'flagged'].join('\t')];
    groups.forEach(function (g) {
      g.items.forEach(function (rec) {
        var d = new Date(rec.at * 1000);
        var day = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
        rows.push([rec.text, rec.kana, rec.tr, rec.en, rec.voc, rec.sentence, placeText(rec, adapter), g.title,
                   langName(rec.lang), day].map(oneLine).join('\t'));
      });
    });
    return rows.join('\n') + '\n';
  }
  /* The clipboard: the toolbox's own copy where the page has it, else the
     browser's, else a textarea and execCommand, as lib/parseh.js does. */
  function copyText(text) {
    if (window.Parseh && Parseh.copy) return Parseh.copy(text, true);
    var p = (navigator.clipboard && navigator.clipboard.writeText)
      ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard API'));
    return p.then(function () { return true; }).catch(function () {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return !!ok;
      } catch (e) { return false; }
    });
  }

  /* ----------------------------------------------------- phone or wide screen */
  /* A PHONE is the mobile layout, or any screen 560 px wide or less (the
     toolbox's own threshold). */
  function phone() {
    try { if (window.Parseh && Parseh.mode && Parseh.mode.isMobile()) return true; } catch (e) {}
    return !!(window.matchMedia && matchMedia('(max-width: 560px)').matches);
  }

  /* ============================================================ THE LIST
     One list, drawn into the sidebar and into /later/: the flags in reading
     order under a heading for each book or video, each with the chunk, its
     gloss, where it is and how long ago, and what can be done with it.  Test
     myself and Copy the list are its tools. */
  var viewSeq = 0;
  function makeView(o) {
    var adapter = o.adapter || null, id = ++viewSeq;
    var scope = adapter && o.mode === 'panel' ? (get(SCOPE) === 'all' ? 'all' : 'this') : 'all';
    var testing = false, shown = {}, opened = {}, adrift = {}, locating = 0, drawing = 0, pending = null;
    var v = {el: el('div', 'lp-view')};

    /* ---- the tools above the list */
    var tools = el('div', 'lp-tools');
    var scopeBtns = {};
    if (adapter && o.mode === 'panel') {
      var sw = el('div', 'lp-scope');
      sw.setAttribute('role', 'group');
      sw.setAttribute('aria-label', 'which flags');
      [['this', 'this ' + (adapter.kind === 'video' ? 'video' : 'book') + ' only'], ['all', 'everything']].forEach(function (s) {
        var b = button('lp-sc', s[1], null, function () {
          scope = s[0];
          put(SCOPE, scope);
          testing = false;
          shown = {};
          draw();
        });
        scopeBtns[s[0]] = b;
        sw.appendChild(b);
      });
      tools.appendChild(sw);
    }
    var row = el('div', 'lp-row');
    var testBtn = button('lp-b lp-test', 'Test myself', 'hide the meanings, and tap a chunk to see its own', function () {
      testing = !testing;
      shown = {};
      draw();
    });
    var copyBtn = button('lp-b lp-copy', 'Copy the list', 'copy these chunks as a list or a table', function () {
      chooser.hidden = !chooser.hidden;
      copyBtn.setAttribute('aria-expanded', chooser.hidden ? 'false' : 'true');
    });
    copyBtn.setAttribute('aria-expanded', 'false');
    var cardsBtn = button('lp-b lp-cards', 'Make cards one after another', 'open the card sheet for each of these chunks in turn', function () {
      var items = visible().filter(function (r) { return r.ref === adapter.ref && adrift[r.id] !== true; }).sort(reading);
      if (items.length) Promise.resolve(adapter.queue(items)).catch(function () {});
    });
    row.appendChild(testBtn);
    row.appendChild(copyBtn);
    row.appendChild(cardsBtn);
    tools.appendChild(row);
    var chooser = el('div', 'lp-chooser');
    chooser.hidden = true;
    [['markdown', 'as a list (markdown)'], ['table', 'as a table (tab-separated)']].forEach(function (f) {
      chooser.appendChild(button('lp-b lp-fmt', f[1], null, function () {
        var groups = groupsOf(visible());
        var total = visible().length;
        var text = f[0] === 'table' ? asTable(groups, adapter) : asMarkdown(groups, adapter);
        chooser.hidden = true;
        copyBtn.setAttribute('aria-expanded', 'false');
        copyText(text).then(function (ok) {
          say(ok ? 'copied ' + plural(total, 'chunk') + ' ' + (f[0] === 'table' ? 'as a table' : 'as a list')
                 : 'the clipboard is not available here');
        });
      }));
    });
    tools.appendChild(chooser);
    var status = el('p', 'lp-status');
    status.setAttribute('role', 'status');
    tools.appendChild(status);
    var body = el('div', 'lp-body');
    v.el.appendChild(tools);
    v.el.appendChild(body);
    v.body = body;

    var saying = '', sayTimer = null;
    function say(text) {
      saying = text;
      clearTimeout(sayTimer);
      sayTimer = setTimeout(function () { saying = ''; paintStatus(); }, 4000);
      paintStatus();
    }

    /* ---- what is listed */
    function visible() {
      var all = list();
      if (scope === 'this' && adapter) all = all.filter(function (r) { return r.ref === adapter.ref; });
      return all;
    }
    /* by book or video: this page's own first, the rest the one flagged last first;
       inside each, reading order */
    function groupsOf(recs) {
      var by = {}, order = [];
      recs.forEach(function (r) {
        if (!by[r.ref]) {
          by[r.ref] = {ref: r.ref, kind: r.kind, title: titleOf(r), lang: r.lang, newest: 0, items: []};
          order.push(by[r.ref]);
        }
        var g = by[r.ref];
        g.items.push(r);
        if (r.at >= g.newest) { g.newest = r.at; g.title = titleOf(r); g.lang = r.lang; }
      });
      order.forEach(function (g) { g.items.sort(reading); });
      order.sort(function (a, b) {
        var ah = adapter && a.ref === adapter.ref ? 1 : 0, bh = adapter && b.ref === adapter.ref ? 1 : 0;
        return (bh - ah) || (b.newest - a.newest);
      });
      return order;
    }
    function cardable() {
      try { return !!(adapter && typeof adapter.makeCard === 'function' && adapter.canCard() && !phone()); }
      catch (e) { return false; }
    }

    /* ---- one row */
    function rowEl(rec) {
      var here = !!(adapter && rec.ref === adapter.ref), lost = here && adrift[rec.id] === true;
      var li = el('li', 'lr' + (lost ? ' lr-adrift' : '') + (testing ? ' lr-test' : '') + (testing && shown[rec.id] ? ' lr-shown' : '') +
                        (opened[rec.id] ? ' lr-open' : ''));
      li.setAttribute('data-id', rec.id);
      li.setAttribute('data-state', lost ? 'adrift' : 'found');
      var main = el('div', 'lr-body');
      var chunk = tag(el('span', 'lr-text', rec.text), rec.lang);
      var bits = glossBits(rec);
      if (testing) {
        // the meaning waits for a tap on the chunk
        var reveal = el('div', 'lr-hit');
        reveal.setAttribute('role', 'button');
        reveal.tabIndex = 0;
        reveal.setAttribute('aria-expanded', shown[rec.id] ? 'true' : 'false');
        var uncover = function () { shown[rec.id] = true; drawRow(rec.id, '.lr-know'); };
        reveal.addEventListener('click', function () { if (!shown[rec.id]) uncover(); });
        reveal.addEventListener('keydown', function (e) {
          if ((e.key === 'Enter' || e.key === ' ') && !shown[rec.id]) { e.preventDefault(); uncover(); }
        });
        reveal.appendChild(chunk);
        if (!shown[rec.id]) reveal.appendChild(el('span', 'lr-tap', 'tap to see the meaning'));
        main.appendChild(reveal);
      } else main.appendChild(chunk);
      if (!testing || shown[rec.id]) main.appendChild(glossEl(rec, bits));
      var meta = el('div', 'lr-meta');
      var place = placeText(rec, adapter);
      if (place) meta.appendChild(el('span', 'lr-place', place));
      var age = el('span', 'lr-age', when(rec.at));
      age.setAttribute('data-at', String(rec.at));
      meta.appendChild(age);
      main.appendChild(meta);
      if (lost) {
        var why = el('p', 'lr-why', 'this chunk is no longer where it was');
        main.appendChild(why);
      }
      li.appendChild(main);
      var acts = el('div', 'lr-acts');
      if (testing) {
        if (shown[rec.id]) {
          acts.appendChild(button('lr-b lr-know', 'I know it', 'take it off the list', function () {
            nextFocus(li);
            remove(rec.id, {toast: 'known · removed from the list'});
          }));
          acts.appendChild(button('lr-b lr-again', 'again', 'keep it, and hide the meaning', function () {
            delete shown[rec.id];
            drawRow(rec.id, '.lr-hit');
          }));
        }
      } else {
        if (here) {
          var go = button('lr-b lr-go', '▶', lost ? 'this chunk is no longer where it was' : 'go to this chunk', function () {
            Promise.resolve().then(function () { return adapter.goTo(rec); }).then(function () {
              if (o.onGo) o.onGo(rec);
            }, function () { say('could not go there'); });
          });
          go.setAttribute('aria-label', 'go to this chunk');
          if (lost) go.disabled = true;
          acts.appendChild(go);
        } else {
          var link = el('a', 'lr-b lr-go', '▶');
          link.href = href(rec);
          link.title = rec.kind === 'video' ? 'open the video at this caption' : 'open the book at this chunk';
          link.setAttribute('aria-label', link.title);
          acts.appendChild(link);
        }
        if (here && cardable()) {
          var card = button('lr-b lr-card', '+ card', lost ? 'this chunk is no longer where it was' : 'make a card from this chunk', function () {
            card.disabled = true;
            Promise.resolve().then(function () { return adapter.makeCard(rec); }).then(function (res) {
              if (res && res.saved) remove(rec.id, {toast: 'card saved · removed from the list'});
            }, function () { say('the card could not be made'); }).then(function () { card.disabled = lost; });
          });
          if (lost) card.disabled = true;
          acts.appendChild(card);
        }
        var x = button('lr-b lr-x', '✕', 'remove from the list', function () { nextFocus(li); remove(rec.id); });
        x.setAttribute('aria-label', 'remove from the list: ' + rec.text);
        acts.appendChild(x);
      }
      li.appendChild(acts);
      return li;
    }
    /* the gloss: one line, and a tap opens each of its parts on a line of its own */
    function glossEl(rec, bits) {
      var wrap = el('div', 'lr-gloss');
      if (!bits.length && !rec.sentence) {
        wrap.appendChild(el('p', 'lr-none', 'no gloss was written for this chunk'));
        return wrap;
      }
      var line;
      var fold = function () {
        opened[rec.id] = !opened[rec.id];
        var li = line.closest('.lr');
        if (li) li.classList.toggle('lr-open', !!opened[rec.id]);
        line.setAttribute('aria-expanded', opened[rec.id] ? 'true' : 'false');
        // the keyboard stays on what it pressed: the line gives way to its parts, and they to the line
        var next = li && li.querySelector(opened[rec.id] ? '.lr-fold' : '.lr-gl');
        if (next) { try { next.focus({preventScroll: true}); } catch (e) {} }
      };
      line = button('lr-gl', bits.join(' · ') || rec.sentence, 'show every part of the gloss', fold);
      line.setAttribute('aria-expanded', opened[rec.id] ? 'true' : 'false');
      line.setAttribute('dir', 'auto');
      wrap.appendChild(line);
      var more = el('div', 'lr-more');
      if (rec.kana) more.appendChild(tag(el('p', 'lr-g lr-kana', rec.kana), rec.lang));
      if (rec.tr) more.appendChild(el('p', 'lr-g lr-tr', rec.tr));
      if (rec.en) more.appendChild(tag(el('p', 'lr-g lr-en', rec.en), rec.glossLang || ''));
      if (rec.voc) more.appendChild(el('p', 'lr-g lr-voc', rec.voc));
      if (rec.sentence) more.appendChild(tag(el('p', 'lr-g lr-sentence', rec.sentence), rec.lang));
      more.appendChild(button('lr-fold', '▴ less', 'show the gloss on one line', fold));
      wrap.appendChild(more);
      return wrap;
    }
    /* After a removal the keyboard goes to the next row rather than to nowhere */
    function nextFocus(li) {
      var n = li.nextElementSibling || li.previousElementSibling;
      pending = n ? n.getAttribute('data-id') : null;
    }
    /* One row again, in place -- and the keyboard where `focus` says, when the
       row is one the person is working in (a locate, in the background, says nothing) */
    function drawRow(rid, focus) {
      var old = body.querySelector('li.lr[data-id="' + cssEscape(rid) + '"]');
      var rec = getOne(rid);
      if (!old || !rec) return;
      var fresh = rowEl(rec);
      old.parentNode.replaceChild(fresh, old);
      var f = focus && fresh.querySelector(focus);
      if (f) { try { f.focus({preventScroll: true}); } catch (e) {} }
    }
    function cssEscape(s) { return (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/["\\]/g, '\\$&'); }

    /* ---- the whole list */
    function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
    function paintStatus() {
      var recs = visible(), n = recs.length;
      if (o.onCount) o.onCount(n);
      var g = groupsOf(recs).length;
      var text;
      if (saying) text = saying;
      else if (!n) text = '';
      else if (testing) text = 'Test myself: ' + plural(n, 'chunk') + ' to go. Tap a chunk to see its meaning.';
      else text = plural(n, 'chunk') + (g > 1 ? ' in ' + g + ' books and videos' : '');
      // what waits to be told to the computer is said only once the computer has
      // failed to be reached -- not for the moment between a change and its sending
      var waiting = lastSync === false ? out.length : 0;
      if (waiting && !saying) text += (text ? ' · ' : '') + plural(waiting, 'change') + ' will be sent when the computer can be reached';
      status.textContent = text;
      status.hidden = !text;
    }
    function draw() {
      var recs = visible(), token = ++drawing;
      var keep = body.scrollTop;
      clear(body);
      testBtn.setAttribute('aria-pressed', testing ? 'true' : 'false');
      testBtn.textContent = testing ? 'Stop testing' : 'Test myself';
      testBtn.hidden = !recs.length;
      copyBtn.hidden = !recs.length;
      if (!recs.length) { chooser.hidden = true; copyBtn.setAttribute('aria-expanded', 'false'); }
      var queue = !!(adapter && typeof adapter.queue === 'function' && cardable());
      cardsBtn.hidden = !(queue && recs.some(function (r) { return r.ref === adapter.ref; }));
      Object.keys(scopeBtns).forEach(function (k) { scopeBtns[k].setAttribute('aria-pressed', scope === k ? 'true' : 'false'); });
      paintStatus();
      if (!recs.length) { body.appendChild(emptyEl()); locate(); return; }
      var groups = groupsOf(recs), heads = groups.length > 1 || scope === 'all';
      // a long list is drawn a screenful at a time, so that opening it never
      // holds the page: the first rows at once, the rest on the next frames
      var rows = [];
      groups.forEach(function (g) {
        var sec = el('section', 'lp-group');
        if (heads) sec.appendChild(groupHead(g));
        var ul = el('ul', 'lp-items');
        sec.appendChild(ul);
        body.appendChild(sec);
        g.items.forEach(function (r) { rows.push([ul, r]); });
      });
      var at = 0, firstBatch = true;
      (function more() {
        if (token !== drawing) return;
        var stop = Math.min(rows.length, at + (at ? 120 : 80));
        for (; at < stop; at++) rows[at][0].appendChild(rowEl(rows[at][1]));
        if (firstBatch) { firstBatch = false; body.scrollTop = keep; }
        if (wanted && showWanted()) { /* the row asked for is on the screen, and the list stays where it put it */ }
        else if (at >= rows.length) body.scrollTop = keep;
        if (at < rows.length) requestAnimationFrame(more);
        else { restoreFocus(); locate(); }
      })();
    }
    /* THE ROW A LINK POINTED AT (#later=<id>): drawn, scrolled to the middle of the
       list, lit for a moment and given the keyboard.  Asked for before it is drawn,
       it is shown as soon as it is. */
    var wanted = null;
    function showWanted() {
      var li = body.querySelector('li.lr[data-id="' + cssEscape(wanted) + '"]');
      if (!li) return false;
      wanted = null;
      li.scrollIntoView({block: 'center'});
      li.classList.add('lr-flash');
      setTimeout(function () { li.classList.remove('lr-flash'); }, 1600);
      var f = li.querySelector('.lr-go:not(:disabled), .lr-x');
      if (f) { try { f.focus({preventScroll: true}); } catch (e) {} }
      return true;
    }
    v.reveal = function (rid) {
      var rec = getOne(rid);
      if (!rec) return false;
      // a flag of another book is only in the list that holds everything
      if (scope === 'this' && adapter && rec.ref !== adapter.ref) scope = 'all';
      testing = false;
      shown = {};
      wanted = rid;
      draw();
      return true;
    };
    function restoreFocus() {
      if (!pending) return;
      var li = body.querySelector('li.lr[data-id="' + cssEscape(pending) + '"]');
      pending = null;
      var f = li && li.querySelector(testing ? '.lr-hit' : '.lr-x');
      if (f) { try { f.focus({preventScroll: true}); } catch (e) {} }
    }
    function groupHead(g) {
      var h = el('div', 'lp-gh');
      var t = el('h3', 'lp-gt');
      var name = tag(el(o.mode === 'page' || !(adapter && g.ref === adapter.ref) ? 'a' : 'span', 'lp-gname', g.title), g.lang);
      if (name.tagName === 'A') { name.href = refHref({kind: g.kind, ref: g.ref}); name.title = g.kind === 'video' ? 'open the video' : 'open the book'; }
      t.appendChild(name);
      h.appendChild(t);
      var meta = el('span', 'lp-gm', [langName(g.lang), plural(g.items.length, 'chunk')].filter(Boolean).join(' · '));
      h.appendChild(meta);
      return h;
    }
    function emptyEl() {
      var e = el('div', 'lp-empty');
      var here = scope === 'this' && adapter, elsewhere = here ? count() - count({ref: adapter.ref}) : 0;
      e.appendChild(el('p', 'lp-empty-h', here ? 'Nothing flagged in this ' + (adapter.kind === 'video' ? 'video' : 'book') + ' yet.' : 'Nothing flagged yet.'));
      e.appendChild(el('p', 'lp-empty-how', 'Point at a chunk and press L, or use «review later» in its cloud — on a phone, hold your finger on a word.'));
      if (elsewhere > 0) {
        var sw = button('lp-b', plural(elsewhere, 'chunk') + ' flagged elsewhere: show everything', null, function () {
          scope = 'all'; put(SCOPE, scope); draw();
        });
        e.appendChild(sw);
      }
      return e;
    }

    /* ---- asking the page where each chunk is, a few at a time */
    function locate() {
      if (!adapter || typeof adapter.locate !== 'function') return;
      var token = ++locating;
      var todo = visible().filter(function (r) { return r.ref === adapter.ref && adrift[r.id] === undefined; });
      (function step() {
        if (token !== locating || !todo.length) return;
        var r = todo.shift();
        Promise.resolve().then(function () { return adapter.locate(r); }).then(function (res) {
          adrift[r.id] = !(res && res.found);
        }, function () { adrift[r.id] = false; }).then(function () {
          if (token !== locating) return;
          if (adrift[r.id] === true) drawRow(r.id);
          setTimeout(step, 0);
        });
      })();
    }

    /* ---- staying right */
    var off = on('change', function () {
      if (v.dead) return;
      cancelAnimationFrame(v.frame);
      v.frame = requestAnimationFrame(function () { if (!v.dead) draw(); });
    });
    var offSync = on('sync', function () { if (!v.dead) paintStatus(); });
    var tick = setInterval(function () {
      var ages = body.querySelectorAll('.lr-age');
      for (var i = 0; i < ages.length; i++) ages[i].textContent = when(+ages[i].getAttribute('data-at'));
    }, 60000);
    v.draw = draw;
    v.refresh = function () { adrift = {}; draw(); };
    v.scopeIs = function () { return scope; };
    v.say = say;
    v.destroy = function () { v.dead = true; off(); offSync(); clearInterval(tick); };
    draw();
    return v;
  }

  /* ======================================================== THE SIDEBAR */
  function panel(adapter) {
    var open = false, wrap = null, box = null, view = null, closer = null, opener = null;
    var entry = null, spent = 0, toggles = [], sheet = false, handle = {};
    var btn = el('button', 'later-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('lang', 'en');
    // one inline run inside the button, so that what is read off it is «⚑ later 3»
    var inner = el('span', 'lb-in');
    inner.appendChild(el('span', 'lb-glyph', '⚑'));
    inner.appendChild(document.createTextNode(' '));
    inner.appendChild(el('span', 'lb-word', 'later'));
    var counter = el('span', 'lb-n');
    inner.appendChild(counter);
    btn.appendChild(inner);
    btn.addEventListener('click', function () { handle.toggle(); });
    function paintButton() {
      var n = count({ref: adapter.ref});
      counter.textContent = n ? ' ' + n : '';
      btn.setAttribute('data-count', String(n));
      btn.title = 'Review later: the chunks you flagged in this ' + (adapter.kind === 'video' ? 'video' : 'book') +
                  (n ? ' (' + plural(n, 'chunk') + ')' : '');
      btn.setAttribute('aria-label', 'review later' + (n ? ', ' + plural(n, 'chunk') + ' flagged' : ''));
    }
    var offButton = on('change', function (d) { if (!d || d.ref === adapter.ref) paintButton(); });
    paintButton();

    function build() {
      if (wrap) return;
      wrap = el('div', 'lp-wrap');
      wrap.hidden = true;
      var back = el('div', 'lp-back');
      back.addEventListener('click', function () { handle.close('backdrop'); });
      box = el('div', 'lp-panel');
      box.setAttribute('role', 'dialog');
      box.setAttribute('aria-label', 'Review later');
      box.setAttribute('lang', 'en');
      box.setAttribute('dir', 'ltr');
      box.tabIndex = -1;
      var head = el('div', 'lp-head');
      head.appendChild(el('span', 'lp-grip'));
      head.appendChild(el('h2', 'lp-title', 'Review later'));
      // how many are listed, beside the title -- the list's own count, whichever list is shown
      var shownN = el('span', 'lp-count');
      shownN.setAttribute('aria-hidden', 'true');
      head.appendChild(shownN);
      closer = button('lp-x', '✕', 'close (Esc)', function () { handle.close('button'); });
      closer.setAttribute('aria-label', 'close the list');
      head.appendChild(closer);
      box.appendChild(head);
      view = makeView({mode: 'panel', adapter: adapter, onGo: function () { handle.close('go'); },
                       onCount: function (n) { shownN.textContent = n ? String(n) : ''; }});
      box.appendChild(view.el);
      wrap.appendChild(back);
      wrap.appendChild(box);
      (document.body || document.documentElement).appendChild(wrap);
      box.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab' || !sheet || e.altKey || e.ctrlKey || e.metaKey) return;
        var all = box.querySelectorAll('button, a[href], [tabindex]:not([tabindex="-1"])');
        var can = Array.prototype.filter.call(all, function (x) { return !x.disabled && x.getClientRects().length > 0; });
        if (!can.length) return;
        var i = can.indexOf(document.activeElement);
        e.preventDefault();
        var next = e.shiftKey ? (i <= 0 ? can[can.length - 1] : can[i - 1]) : (i < 0 || i === can.length - 1 ? can[0] : can[i + 1]);
        next.focus();
      });
    }
    /* A phone's list is a sheet with a history entry of its own, so that the
       back gesture closes it instead of leaving the page. */
    function pushEntry() {
      try { entry = 'later:' + Date.now(); history.pushState({parsehLater: entry}, ''); } catch (e) { entry = null; }
    }
    function spendEntry() {
      var mine = entry && history.state && history.state.parsehLater === entry;
      entry = null;
      if (!mine) return;
      spent++;
      try { history.back(); } catch (e) { spent--; }
    }
    function layout() {
      if (!wrap) return;
      var was = sheet;
      sheet = phone();
      wrap.className = 'lp-wrap ' + (sheet ? 'lp-sheet' : 'lp-side');
      box.setAttribute('aria-modal', sheet ? 'true' : 'false');
      if (open && sheet && !entry) pushEntry();
      if (open && !sheet && entry) spendEntry();
      // a phone makes no cards: turned from a computer's window to a phone's, or back, the rows say so
      if (view && open && was !== sheet) view.draw();
    }
    var onPop = function () {
      if (spent) { spent--; return; }
      if (open && entry && !(history.state && history.state.parsehLater === entry)) { entry = null; handle.close('back'); }
    };
    var onSize = function () { if (open) layout(); };
    // Esc closes it, and stands down where something else has just used the
    // key (a cloud, a card sheet): that one is closed first
    var onKey = function (e) {
      if (e.key === 'Escape' && open && !e.defaultPrevented) { e.preventDefault(); handle.close('key'); }
    };
    window.addEventListener('popstate', onPop);
    window.addEventListener('resize', onSize);
    window.addEventListener('keydown', onKey);
    var offMode = null;
    try { if (window.Parseh && Parseh.mode && Parseh.mode.onChange) offMode = Parseh.mode.onChange(function () { if (open) layout(); }); } catch (e) {}

    handle.button = btn;
    handle.isOpen = function () { return open; };
    handle.onToggle = function (fn) { toggles.push(fn); };
    /* open({id}) opens it ON one flag: lit, in view, the keyboard on its ▶ -- what a
       link from /later/ (#later=<id>) asks for */
    handle.open = function (o) {
      if (open) { if (o && o.id && view) view.reveal(o.id); return; }
      build();
      opener = document.activeElement;
      open = true;
      wrap.hidden = false;
      layout();
      btn.setAttribute('aria-expanded', 'true');
      view.refresh();
      if (o && o.id) view.reveal(o.id);
      sync();
      if (!(o && o.id)) { try { box.focus({preventScroll: true}); } catch (e) {} }
      toggles.slice().forEach(function (fn) { try { fn(true); } catch (e) {} });
    };
    handle.close = function (how) {
      if (!open) return;
      open = false;
      wrap.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      if (entry && how !== 'back') spendEntry(); else entry = null;
      var back = opener && opener.isConnected && opener.getClientRects().length ? opener : btn;
      if (how !== 'go') { try { back.focus({preventScroll: true}); } catch (e) {} }
      toggles.slice().forEach(function (fn) { try { fn(false); } catch (e) {} });
    };
    handle.toggle = function () { if (open) handle.close('button'); else handle.open(); };
    handle.refresh = function () { paintButton(); if (view) view.refresh(); };
    handle.destroy = function () {
      if (open) handle.close('page');
      offButton();
      if (offMode) offMode();
      window.removeEventListener('popstate', onPop);
      window.removeEventListener('resize', onSize);
      window.removeEventListener('keydown', onKey);
      if (view) view.destroy();
      if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
      if (btn.parentNode) btn.parentNode.removeChild(btn);
    };
    return handle;
  }

  /* ========================================================= THE PAGE */
  /* /later/ : the list across every book and video, in an element the page
     marked.  It is drawn from the copy at once and again when the computer's
     answer arrives. */
  function page(root, langs) {
    if (langs && typeof langs === 'object') Object.keys(langs).forEach(function (c) { LANGS[c] = langs[c]; });
    var view = makeView({mode: 'page', adapter: null});
    root.appendChild(view.el);
    ready().then(function () { view.draw(); });
    return view;
  }

  /* --------------------------------------------------------------- starting */
  /* THE SHEET COMES WITH THE SCRIPT: a reader or a player that loads this file
     (lib/parseh.js does, from beside itself) needs no tag for lib/later.css, and
     a built reader, however old, gets it without being built again.  A page that
     links it itself -- /later/ -- is left alone. */
  function dress() {
    if (location.protocol === 'file:' || document.querySelector('link[href*="later.css"]')) return;
    var head = document.head || document.documentElement;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = (SELF ? SELF.replace(/later\.js(?=[?#]|$).*$/, '') : '/lib/') + 'later.css';
    head.appendChild(link);
  }
  function start() {
    dress();
    readStore();
    window.addEventListener('storage', function (e) {
      if (e.key !== KEY && e.key !== OUTBOX && e.key !== null) return;
      var before = cache;
      readStore();
      emit(differ(before, cache));
    });
    window.addEventListener('online', function () { sync(); });
    window.addEventListener('pageshow', function (e) { if (e.persisted) sync(); });
    document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') sync(); });
    first = sync();
    var go = function () {
      var root = document.querySelector('[data-later-page]');
      if (root) {
        var langs = null;
        try { langs = JSON.parse(root.getAttribute('data-langs') || 'null'); } catch (e) {}
        page(root.querySelector('#lp-root') || root, langs);
      }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go);
    else go();
  }

  window.ParsehLater = {
    ready: ready, sync: sync, has: has, get: getOne, list: list, count: count, add: add, remove: remove,
    toggle: toggle, undo: undo, on: on, pending: function () { freshen(); return out.length; },
    idFor: idFor, record: record, href: href, fromHash: fromHash, refOf: refOf, panel: panel, page: page,
    device: device
  };
  start();
})();
