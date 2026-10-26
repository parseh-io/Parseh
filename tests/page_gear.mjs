// SPDX-License-Identifier: GPL-3.0-or-later
import {chromium} from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/page_gear.mjs
//      PAGE_GEAR_SHOTS=<dir>   saves a screenshot of the panel open on every group, wide (1280x800) and on a
//                              phone (390x844), in the light, dark and sepia themes, and a strip of the three
//                              themes side by side for each group (the section `shots`)
//      PAGE_GEAR_ONLY=a,b      runs only those sections (a development aid): button, open, kinds, node, mount,
//                              keys, phone, widths, contrast, std, zoom, look, shots
//
// THE GEAR, lib/pagesettings.js + lib/pagesettings.css (a0.5.0, plan §2 and §9): the one panel every page opens for
// its own settings, driven where a person meets it.  Two fixture pages, loaded exactly as a page loads the toolkit
// (a script tag; the script links its own sheet), served by a tiny static server over the REAL lib/ and the studio's
// real sheets -- no Parseh server is needed for a panel that only draws what the page hands it:
//   BOOK  a reader's page: lib/parseh.css, lib/langs.css, lib/mobile.css and the REAL lib/parseh.js (so the
//         toolkit meets Parseh.theme and Parseh.mode as it will in a reader), a right-to-left page, two bars
//         (the reader's header and a phone's), and a spec of every kind of row: levels with names, a disabled
//         row with its reason, a note, a link, an action, switches, sliders, selects, and the three standard groups
//   DOC   a studio document: the studio's own sheets (sheet.css, app.css: its --chrome-* tokens, its theme on
//         <body>), NO parseh.js -- the world the toolkit also has to work in
//
//  button)  where the button stands and what it says: ⚙ and the word on a wide screen, ⚙ alone on a phone (48x48)
//           and under 600px, its name, its title, aria; held in the host of the layout in force, and moved with it
//  open)    opens by click, closes by click, Esc (spent: defaultPrevented), ✕, an outside click (the popover); the
//           popover under the button, inside the window; open('text') scrolls to the group and focuses its first
//           control; onToggle; a second mount replaces the first; a closed panel is not in the way
//  kinds)   every kind of row changes its state and the page's handler gets the right value; an external change
//           reaches the row through watch, and refresh() re-reads; when() and disabled() (with the reason printed);
//           a group with no drawn row is not drawn; the level names, their limit, the right-to-left one
//  node)    the two rows that hang under a switch (indent: 16px a step, and disabled(above) told whether the switch
//           above is on); a `node` row: another layer's own buttons brought into the sheet while it is up (the very
//           same elements, their handlers working, a mark standing where each was) and sent home to the same parent
//           and the same next sibling when the panel is shut, when the row stops being drawn, when the layout is
//           left and when the gear is unmounted; el() answering null is no row
//  mount)   ParsehGear.mounted() and the parseh:gear event ('mounted' by every mount, no 'unmounted' between a
//           mount and the mount that replaces it, 'unmounted' by unmount()); unmount() takes the button, the panel,
//           <html>'s class, the listeners and (on a phone) the history entry away, and says nothing twice
//  keys)    the keyboard: Tab order, Space and Enter on a switch, arrows in a radiogroup, Home and End
//  phone)   on a 390x844 touch screen (a0.5.4: two stages, two heights): the sheet opens on the INDEX of the themes, each
//           with a summary of what it is set to (the default rule kind by kind; a group's own summary wins; names
//           in <bdi>), seven rows of 56px (50px at 360x740, or where eight must fit) inside the half sheet with no
//           scrolling, each what a finger reaches at its centre; a tap enters a theme (its head, ‹ 48px, only its
//           group drawn), ‹, the back gesture, ✕, Esc and a swipe return or close from both stages, with a second
//           history entry that is spent exactly once (the next sheet's back gesture still works); open('text')
//           lands on the theme; stage() and back(); the two heights by drag, flick and a tap on the grab line,
//           remembered across a reload; a Keep-style node row only while its theme is on stage; the sheet
//           becoming the popover with a theme up and back; Tab order ‹ rows ✕; the landscape floor; the popover
//           untouched
//  widths)  nothing overflows sideways at 320, 360, 390 and 430px, with names that are far too long
//  contrast) the name, the sentence, the caption, the chips and the links keep 4.5:1 (3:1 for the large) in the
//           light, dark and sepia themes, in both fixtures
//  std)     the three standard groups: colours write parseh_theme and <html data-theme> (and the studio's own
//           apply), interface writes parseh_mode, the cookie and <html data-mode> and fires parseh:mode, and the
//           panel and the button follow the mode
//  zoom)    std.zoom() is not drawn without ParsehZoom and is driven against a stub with one; the popover and the
//           sheet stand right under a page zoomed the way lib/pagezoom.js zooms one (a CSS zoom and a geometry shim)
//  look)    the screenshots, and the panel on top of everything it must be on top of
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const SHOTS = Deno.env.get('PAGE_GEAR_SHOTS') || '';
const ONLY = (Deno.env.get('PAGE_GEAR_ONLY') || '').split(',').filter(Boolean);
const want = name => !ONLY.length || ONLY.includes(name);
if (SHOTS) await Deno.mkdir(SHOTS, {recursive: true});
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 8000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('FAIL: timed out: ' + what);
    await sleep(40);
  }
}

/* ---------------------------------------------------------------- the files, served */
const TYPES = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2',
               '.png': 'image/png', '.json': 'application/json', '.svg': 'image/svg+xml'};
async function file(path, base) {
  if (path.includes('..')) return new Response('no', {status: 400});
  const full = root + '/' + base + path;
  try {
    const data = await Deno.readFile(full);
    const ext = full.slice(full.lastIndexOf('.'));
    return new Response(data, {headers: {'content-type': (TYPES[ext] || 'application/octet-stream') + (ext === '.html' ? '; charset=utf-8' : ''),
                                         'cache-control': 'no-store'}});
  } catch { return new Response('not found', {status: 404}); }
}

const PERSIAN = ['کتابی که می‌خوانید با چند لایه نوشته شده است.', 'هر جمله را می‌توانید با واکه‌ها یا بدون آن‌ها بخوانید.',
  'برای دیدن معنی هر تکه، نشانگر را روی آن ببرید.', 'اندازهٔ نوشته را از همین‌جا می‌توانید تغییر دهید.',
  'اگر چیزی را نمی‌فهمید، فرهنگ لغت یک لمس از شما دور است.'];
const PARAS = Array.from({length: 14}, (_, i) => `<p class="para" dir="rtl" lang="fa"><span class="n">${i + 1}</span> ${PERSIAN[i % PERSIAN.length]} ${PERSIAN[(i + 2) % PERSIAN.length]}</p>`).join('\n');

/* The page's own bar: the reader's header look (lib/tex2html.py), two rows' worth of it in one: a browser bar and a
   mobile one, as a page that carries both layouts has them.  The gear's host in each is a span of its own. */
const READER_CSS = `
body{padding-top:92px}
header{position:fixed;top:0;left:0;right:0;z-index:50;background:var(--card);border-bottom:1px solid var(--rule);
  display:flex;flex-direction:column;gap:0;padding:4px 10px}
.hrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:3px 0}
header button{font:inherit;font-size:13px;padding:5px 9px;border:1px solid var(--rule);background:var(--bg);
  color:var(--ink);border-radius:6px;cursor:pointer;white-space:nowrap}
header button.on{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
header a.home{color:var(--dim);text-decoration:none;font-size:15px;padding:4px 8px;border:1px solid var(--rule);border-radius:6px}
header .sp{flex:1}
main{max-width:760px;margin:0 auto;padding:16px 14px 60vh;overflow-x:clip}
.para{font-family:var(--tl-font,serif);font-size:var(--rd-fa,26px);line-height:2;margin:0 0 14px}
.para .n{font:12px sans-serif;color:var(--faint);margin-inline-end:8px}
`;

function bookPage(q) {
  const long = q.get('long') === '1', stub = q.get('stubzoom') === '1', node = q.get('node') === '1', summed = q.get('sum') === '1';
  return `<!doctype html>
<html lang="fa" dir="rtl" data-parseh-lang="fa">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>fixture reader</title>
${zshim(q)}
<script>
/* the layers parseh.js loads from beside itself are not under test here */
window.ParsehActivity = {reach: function () { return {state: 'here'}; }};
window.ParsehPrefs = {}; window.ParsehKeep = {}; window.ParsehExplain = {};
</script>
<link rel="stylesheet" href="/lib/parseh.css"><link rel="stylesheet" href="/lib/langs.css">
<link rel="stylesheet" href="/lib/mobile.css">
<style>${READER_CSS}</style>
<script src="/lib/parseh.js"></script>
${stub ? `<script>${ZOOM_STUB}</script>` : ''}
<script src="/lib/pagesettings.js"></script>
</head>
<body data-lang="fa">
<header lang="en" dir="ltr">
  <div class="hrow" data-layout="browser" id="bbar"><a class="home" href="#">پ</a><span class="sp"></span>
    <button id="contents">contents</button><button id="aa">Aa</button><button id="theme" data-parseh-theme>◐</button><span id="bhost"></span></div>
  <div class="hrow parseh-bar m-bar" data-layout="mobile" id="mbar"><a class="home" href="#">پ</a><span class="sp"></span>
    <button id="mtheme" data-parseh-theme>◐</button><span id="mhost"></span></div>
</header>
<main>${PARAS}</main>
<div id="menu" hidden><button class="kp-btn" id="keep1">Keep on this phone</button><button class="kp-btn" id="keep2">Keep this chapter too</button><span id="after">the menu goes on</span></div>
<script>
(function () {
  // what a reader's own shortcuts would hear (it plays on Space, moves on the arrows, flips the glosses on G)
  window.__keys = [];
  window.addEventListener('keydown', function (e) { window.__keys.push(e.key); });
  // what the layers that used to draw their own ⋯ and Aa would hear: from the very first mount
  window.__gearEvents = [];
  document.addEventListener('parseh:gear', function (e) { window.__gearEvents.push(e.detail); });
  window.__args = [];
  document.getElementById('keep1').addEventListener('click', function () { window.__kept = (window.__kept || 0) + 1; });
  var st = window.__st = {
    lang: 'fa', audio: true, vowels: true, gloss: true, hover: false, pause: false, dict: false, defs: false, trans: false, cont: true, bnd: false,
    speed: 1, skip: 10, gap: 1.5, px: 28, gl: 14, width: 760, lead: 1.5,
    levels: {vocal: {shown: true, name: '', def: 'With vowels', help: 'the sentence with its vowels, to read on its own'},
             chunks: {shown: true, name: '', def: 'Chunks', help: 'the sentence cut into chunks, each with its gloss beside it'},
             bare: {shown: true, name: '', def: 'Plain', help: 'the sentence as Persian is ordinarily printed, with no marks'},
             alt: {shown: false, name: '', def: 'Nastaliq', help: 'the same sentence in nastaliq script'}}
  };
  var calls = window.__calls = [];
  function rec(id, v) { calls.push({id: id, v: v}); }
  var subs = {};
  window.__emit = function (id) { (subs[id] || []).slice().forEach(function (f) { f(); }); };
  window.__subs = function (id) { return (subs[id] || []).length; };
  function watch(id) {
    return function (cb) {
      (subs[id] = subs[id] || []).push(cb);
      return function () { subs[id] = subs[id].filter(function (f) { return f !== cb; }); };
    };
  }
  function sw(id, label, help, key, extra) {
    var r = {id: id, kind: 'switch', label: label, help: help,
             get: function () { return st[key]; }, set: function (v) { st[key] = v; rec(id, v); }, watch: watch(id)};
    for (var k in extra) r[k] = extra[k];
    return r;
  }
  function slider(id, label, help, key, min, max, step, unit, extra) {
    var r = {id: id, kind: 'slider', label: label, help: help, min: min, max: max, step: step, unit: unit,
             get: function () { return st[key]; },
             set: function (v) {
               st[key] = v; rec(id, v);
               // the text size is drawn at once, as a reader draws it: the page above the sheet shows it
               if (key === 'px') document.documentElement.style.setProperty('--rd-fa', v + 'px');
             }, watch: watch(id)};
    for (var k in extra) r[k] = extra[k];
    return r;
  }
  function levelItems() {
    return ['vocal', 'chunks', 'bare', 'alt'].map(function (k) {
      var l = st.levels[k];
      return {key: k, name: l.name || l.def, def: l.def, help: l.help, shown: l.shown,
              disabled: k === 'chunks' && st.hover ? 'The cloud shows the glosses, so this level rests.' : false};
    });
  }
  var SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map(function (v) { return {value: v, label: v + '×'}; });
  var SKIPS = [1, 2, 5, 10, 15, 30, 60].map(function (v) { return {value: v, label: v + ' s'}; });
  var groups = [
    {id: 'levels', title: 'Levels & reading', caption: 'Saved on this device.', rows: [
      {id: 'levels', kind: 'levels', label: 'Levels', kept: 'you',
       help: 'Tick the levels you want to see. Type in a box to rename a level; clear the box to go back to its usual name.',
       items: levelItems,
       setShown: function (k, v) { st.levels[k].shown = v; rec('level.shown.' + k, v); },
       setName: function (k, n) { st.levels[k].name = n; rec('level.name.' + k, n); }, watch: watch('levels')},
      sw('diacritics', 'Diacritics', 'Shows the small marks that write the vowels on Persian and Arabic text. Off, the text reads as it is ordinarily printed.', 'vowels',
         {short: 'diacritics', when: function () { return st.lang === 'fa'; }}),
      sw('gloss', 'Glosses', 'Show the meaning beside each chunk. Turn it off to test yourself against the chunks alone. Key G.', 'gloss',
         {short: 'glosses', disabled: function () { return st.hover ? 'The cloud is showing the glosses, so this rests while it is on.' : false; }}),
      sw('hover', 'Glosses in a cloud', "Read the text clean: a chunk's gloss opens in a cloud when you point at it. Key H.", 'hover', {short: 'cloud'}),
      sw('hoverpause', 'Pause while a gloss is open', 'While a gloss is open the recording waits, and goes on a moment after it closes.', 'pause',
         {when: function () { return st.audio; }}),
      {id: 'tip', kind: 'note', text: 'Only the levels you tick are drawn; the book itself is not changed.'}]},
    {id: 'listening', title: 'Listening', caption: 'Follows you to your other devices.', rows: [
      {id: 'speed', kind: 'choice', label: 'Playback speed', kept: 'you',
       help: 'How fast the recording plays, from 0.25× to 2×. The [ and ] keys step it.', options: SPEEDS,
       get: function () { return st.speed; }, set: function (v) { st.speed = v; rec('speed', v); }, watch: watch('speed')},
      {id: 'skip', kind: 'choice', label: 'Skip distance', help: 'How many seconds ↺ and ↻ move the recording.', options: SKIPS,
       get: function () { return st.skip; }, set: function (v) { st.skip = v; rec('skip', v); }},
      slider('gap', 'Pause between repeats', 'The silence between one repeat of a line and the next while loop is on.', 'gap', 0, 5, 0.5, ' s',
             {format: function (v) { return v === 0 ? 'none' : v + ' s'; }}),
      sw('cont', 'Keep playing into the next line', 'When a line of the recording ends, go straight on to the next one.', 'cont', {short: 'keeps going'}),
      sw('bnd', 'Wait at each new chapter', 'When the recording reaches a new chapter it stops and waits for you to press ▶.', 'bnd')]},
    {id: 'lookup', title: 'Looking a word up', caption: 'Saved on this device.', rows: [
      sw('dict', 'Look words up in a dictionary', 'Where a chunk has not been glossed, click or tap it to look its words up.', 'dict', {short: 'dictionary'}),
      // THE CHAIN: the dictionary, its definitions, their translation -- each hung under the one above it, and
      // each asking the switch above whether it is on (the row above a row says so as the argument of disabled)
      sw('defs', "Show the dictionary's definitions", "Under each word it finds, the dictionary's own definition.", 'defs',
         {indent: 1, disabled: function (on) { window.__args.push(['defs', on]); return on ? false : 'Turn on “Look words up in a dictionary” first.'; }}),
      sw('trans', 'Translate the definitions', 'Each definition is put into English by the translation model on this computer.', 'trans',
         {indent: 2, disabled: function (on) { window.__args.push(['trans', on]); return on ? false : 'Turn on the definitions first.'; }}),
      {id: 'help', kind: 'link', label: 'Get a dictionary for this language →', href: '/settings/reading-help/',
       help: 'Opens the page where dictionaries are chosen and installed.',
       disabled: function (on) { window.__args.push(['help', on]); return false; }}]},
    {id: 'text', title: 'Text', caption: 'Saved on this device.', rows: [
      slider('px', 'Persian text size', "How big the book's own words are, the ones you are learning.", 'px', 18, 56, 1, 'px',
             {disabled: function (on) { window.__args.push(['px', on]); return false; }}),
      slider('gl', 'Gloss size', 'How big the meanings and notes beside each chunk are.', 'gl', 10, 28, 1, 'px'),
      slider('width', 'Text width', 'How wide the column of text may grow on a wide screen.', 'width', 480, 1200, 10, 'px'),
      slider('lead', 'Line spacing', 'The space between lines: 1 is the usual, more is airier.', 'lead', 1, 2.4, 0.05, ''),
      {id: 'normal', kind: 'action', label: 'Put the text back to normal', help: 'Resets only the text sliders.',
       onClick: function () { st.px = 28; st.gl = 14; st.width = 760; st.lead = 1.5; rec('normal', true); }}]},
    ParsehGear.std.zoom(), ParsehGear.std.colours(), ParsehGear.std['interface']()${node ? `,
    // other layers' own buttons, brought in while the panel is up (lib/keep.js's .kp-btn are the first), for the phone only
    {id: 'keep', title: 'Keeping', caption: 'Saved on this device.', layouts: 'mobile', rows: [
      {id: 'keep1', kind: 'node', label: 'Keep on this phone', help: 'Keeps this book so it opens with the computer away.',
       el: function () { return window.__noKeep1 ? null : document.getElementById('keep1'); }},
      {id: 'keep2', kind: 'node', el: function () { return document.getElementById('keep2'); }},
      {id: 'late', kind: 'node', label: 'A button that is not there yet', el: function () { return window.__late || null; }}]}` : ''}${summed ? `,
    // an adapter that says its own summary: a function with a name that reads right to left, and a plain string
    {id: 'summed', title: 'Said by the page', caption: 'Saved on this device.',
     summary: function () { return [{bdi: 'فارسی ساده'}, ', ', {bdi: 'Chunks'}, ' · no glosses']; },
     rows: [sw('sumsw', 'A switch with a short name that is not used', 'The group says its own summary, so this one is ignored.', 'cont', {short: 'ignored'})]},
    {id: 'said', title: 'Said in words', caption: 'Saved on this device.', summary: 'In the page\\'s own words',
     rows: [{id: 'saidnote', kind: 'note', text: 'A note.'}]},
    {id: 'quiet', title: 'Says nothing', caption: 'Saved on this device.', summary: function () { return ''; },
     rows: [sw('quietsw', 'A switch', 'Its short name is not used either: an empty summary is a summary.', 'cont', {short: 'ignored'})]}` : ''}${long ? `,
    {id: 'long', title: 'Names far too long', caption: 'Saved on this device.', rows: [
      {id: 'longlevels', kind: 'levels', label: 'A level with a name nobody should have to read in one line',
       help: 'A long sentence about this row that goes on and on and on, to see where it wraps and that it never pushes the row wider than the sheet.',
       items: function () { return [
         {key: 'a', name: 'An extremely long name that cannot fit in any box', def: 'Chunks', shown: true, help: 'A very long description of what this level is: ' + 'word '.repeat(30)},
         {key: 'b', name: 'فارسی ساده', def: 'Plain', shown: true, help: 'a right-to-left name, typed by the person', lang: 'fa'},
         {key: 'c', name: 'Supercalifragilisticexpialidocious', def: 'Plain', shown: false, help: 'one word with no spaces to break at'}]; },
       setShown: function (k, v) { rec('long.shown.' + k, v); }, setName: function (k, n) { rec('long.name.' + k, n); }},
      {id: 'staticlevels', kind: 'levels', label: 'Levels that cannot be renamed',
       help: 'These have no name box: the name is a line of text.',
       items: function () { return [{key: 'a', name: 'An extremely long name that cannot fit in any box and goes on', def: 'x', shown: true, help: 'long: ' + 'word '.repeat(20)},
                                    {key: 'b', name: 'Supercalifragilisticexpialidocious-with-more-and-more', def: 'x', shown: true, help: ''}]; },
       setShown: function (k, v) { rec('static.shown.' + k, v); }}]}` : ''}
  ];
  window.__spec = {
    page: 'book',
    host: {browser: function () { return document.getElementById('bhost'); }, mobile: function () { return document.getElementById('mhost'); }},
    groups: groups
  };
  window.__gear = ParsehGear.mount(window.__spec);
  window.__ready = true;
})();
</script>
</body></html>`;
}

const ZOOM_STUB = `
window.ParsehZoom = (function () {
  var STEPS = [70, 80, 90, 100, 110, 125, 150, 175, 200], st = {stored: 100, max: 150}, subs = [];
  window.__zoom = st;
  function applied() { return Math.min(st.stored, st.max); }
  function tell() { subs.forEach(function (f) { f(applied()); }); try { document.dispatchEvent(new CustomEvent('parseh:zoom')); } catch (e) {} }
  return {STEPS: STEPS, get: function () { return st.stored; }, applied: applied,
    set: function (v) { (window.__calls = window.__calls || []).push({id: 'zoom.set', v: v}); st.stored = v; tell(); },
    can: function (dir) { return dir > 0 && applied() >= st.max ? 'This window is too narrow for more.' : true; },
    reset: function () { (window.__calls = window.__calls || []).push({id: 'zoom.reset'}); st.stored = 100; tell(); },
    onChange: function (fn) { subs.push(fn); return function () { subs = subs.filter(function (f) { return f !== fn; }); }; },
    allowedMax: function () { return st.max; }};
})();`;

/* A PAGE ZOOMED THE WAY lib/pagezoom.js ZOOMS ONE (plan §5): `html{zoom:Z}` and a geometry shim that makes every
   rectangle, the window's and the root's sizes, the pointer's coordinates and elementFromPoint speak the page's own
   (zoomed) pixels.  A trimmed copy of the plan's prototype; the toolkit has to place itself right under it from
   getBoundingClientRect, clientWidth/clientHeight and its own offsetWidth/offsetHeight and nothing else.
   `__native` keeps what the browser itself says, for the test to measure the real picture with. */
const ZOOM_SHIM = `(function (Z) {
  if (Z === 1) return;
  var de = document.documentElement;
  window.__native = {rect: Element.prototype.getBoundingClientRect, w: window.innerWidth, h: window.innerHeight};
  de.style.zoom = String(Z);
  de.style.setProperty('--z', String(Z));
  function R(r) { return new DOMRect(r.x / Z, r.y / Z, r.width / Z, r.height / Z); }
  var gb = Element.prototype.getBoundingClientRect, gc = Element.prototype.getClientRects;
  Element.prototype.getBoundingClientRect = function () { return R(gb.call(this)); };
  Element.prototype.getClientRects = function () { return Array.prototype.map.call(gc.call(this), R); };
  function div(obj, name) {
    var d = Object.getOwnPropertyDescriptor(obj, name);
    if (!d || !d.get) return;
    Object.defineProperty(obj, name, {configurable: true, enumerable: d.enumerable,
      get: function () { return d.get.call(this) / Z; }, set: d.set && function (v) { d.set.call(this, v * Z); }});
  }
  ['innerWidth', 'innerHeight', 'scrollX', 'scrollY', 'pageXOffset', 'pageYOffset'].forEach(function (n) { div(window, n); });
  ['clientWidth', 'clientHeight', 'scrollTop', 'scrollLeft', 'scrollWidth', 'scrollHeight'].forEach(function (n) {
    var d = Object.getOwnPropertyDescriptor(Element.prototype, n);
    Object.defineProperty(Element.prototype, n, {configurable: true, enumerable: d.enumerable,
      get: function () { var v = d.get.call(this); return this === de ? v / Z : v; },
      set: d.set && function (v) { d.set.call(this, this === de ? v * Z : v); }});
  });
  ['clientX', 'clientY', 'pageX', 'pageY'].forEach(function (n) { div(MouseEvent.prototype, n); });
  var efp = document.elementFromPoint; document.elementFromPoint = function (x, y) { return efp.call(document, x * Z, y * Z); };
  if (window.visualViewport) ['width', 'height', 'offsetLeft', 'offsetTop', 'pageLeft', 'pageTop'].forEach(function (n) { div(Object.getPrototypeOf(visualViewport), n); });
})(window.__Z || 1);`;
const zshim = q => q.get('z') ? `<script>window.__Z=${Number(q.get('z'))};${ZOOM_SHIM}</script>` : '';

function docPage(q) {
  const studiomode = q.get('studiomode') === '1', extra = q.get('extra') === '1';
  return `<!doctype html>
<html lang="en" data-mode="browser">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>fixture document</title>
${zshim(q)}
<link rel="stylesheet" href="/studio/static/sheet.css"><link rel="stylesheet" href="/studio/static/app.css">
<link rel="stylesheet" href="/studio/static/mobile.css">
<script>
/* the studio's head: the mode and the theme, before anything is painted */
(function () {
  var m = null, t = null;
  try { m = localStorage.getItem('parseh_mode'); t = localStorage.getItem('parseh_theme'); } catch (e) {}
  document.documentElement.setAttribute('data-mode', m === 'mobile' ? 'mobile' : 'browser');
  window.__bodyTheme = t === 'light' || t === 'dark' || t === 'sepia' ? t : '';
})();
</script>
${studiomode ? '<script src="/studio/static/mode.js"></script>' : ''}
${q.get('stubzoom') === '1' ? `<script>${ZOOM_STUB}</script>` : ''}
<script src="/lib/pagesettings.js"></script>
</head>
<body>
<header class="topbar" data-layout="browser" id="dbar"><a class="hublink" href="#"><span class="glyph">پ</span></a>
  <span class="doc-title">A studio document</span>
  <div class="topbar-actions"><button class="btn" id="daa">Aa</button><span id="dhost"></span></div></header>
<header class="topbar" data-layout="mobile" id="dmbar"><a class="hublink" href="#"><span class="glyph">پ</span></a>
  <span class="doc-title">A studio document</span>
  <div class="topbar-actions"><span id="dmhost"></span></div></header>
<main class="container"><article class="sheet" data-lang="fa">
<h1>How the sheet reads</h1>
${Array.from({length: 10}, () => '<p>The page above the panel is a sheet of the studio: its words, its tokens, its theme on the body. ' +
  'A change made in the panel shows here at once, because the sheet is the part the phone leaves visible.</p>').join('\n')}
</article></main>
<script>
(function () {
  if (window.__bodyTheme) document.body.setAttribute('data-theme', window.__bodyTheme);
  var st = window.__st = {fa: 1.52, lat: 17, width: 760, lead: 1.45, justify: false, translit: false, drag: false, bars: false};
  var calls = window.__calls = [];
  function rec(id, v) { calls.push({id: id, v: v}); }
  window.__applied = [];
  function slider(id, label, help, key, min, max, step, unit) {
    return {id: id, kind: 'slider', label: label, help: help, min: min, max: max, step: step, unit: unit,
            get: function () { return st[key]; }, set: function (v) { st[key] = v; rec(id, v); }};
  }
  function sw(id, label, help, key) {
    return {id: id, kind: 'switch', label: label, help: help,
            get: function () { return st[key]; }, set: function (v) { st[key] = v; rec(id, v); }};
  }
  window.__spec = {
    page: 'doc',
    host: {browser: function () { return document.getElementById('dhost'); }, mobile: function () { return document.getElementById('dmhost'); }},
    groups: [
      {id: 'text', title: 'Text', caption: 'Saved on this device.', rows: [
        slider('fa', 'Persian text size', 'How big the Persian text is compared with the Latin text around it (1× = the same size).', 'fa', 0.8, 2.6, 0.02, '×'),
        slider('lat', 'Latin text size', 'How big the Latin-script text is, from 13 to 23 pixels.', 'lat', 13, 23, 1, 'px'),
        slider('lead', 'Line spacing', 'The space between lines: 1 is the usual, more is airier.', 'lead', 1, 2.2, 0.05, ''),
        sw('justify', 'Justify the text', 'Straight left and right edges, with words hyphenated at line ends, the way the PDF sets it.', 'justify'),
        {id: 'normal', kind: 'action', label: 'Put the text back to normal', help: "Values go back to the PDF's own.",
         onClick: function () { st.fa = 1.52; st.lat = 17; st.lead = 1.45; rec('normal', true); }}]},
      {id: 'exercises', title: 'Exercises', caption: 'Saved on this device.', rows: [
        sw('translit', 'Hide transliterations', 'Hides the line that spells how a word sounds in Latin letters on every exercise flashcard.', 'translit'),
        sw('drag', 'Drag to answer', 'Lets you drag words into place in exercises that offer it. Off by default on a touch screen.', 'drag'),
        {id: 'sides', kind: 'choice', label: 'Flashcard sides', help: 'Which side of a card is shown first.',
         options: [{value: 'both', label: 'Both', help: 'Front and back side by side.'},
                   {value: 'front', label: 'Front', help: 'Only the front; press to turn the card over.'},
                   {value: 'back', label: 'Back', help: 'Only the back first.'}],
         get: function () { return st.sides || 'both'; }, set: function (v) { st.sides = v; rec('sides', v); }}]},
      {id: 'page', title: 'Page', caption: 'Saved on this device.', rows: [
        sw('bars', 'Hide the bars', 'Puts the header away so the text has the whole window.', 'bars'),
        {id: 'guide', kind: 'link', label: "Read the guide's page on exercises", href: 'https://parseh.io/guide', newTab: true,
         help: 'Opens the guide in a new tab.'},
        {id: 'say', kind: 'link', label: 'Show what changed', onClick: function () { rec('say', true); },
         help: 'A link that does something instead of going somewhere.'}]},
      ParsehGear.std.zoom(),
      ParsehGear.std.colours({apply: function (t) {
        window.__applied.push(t);
        if (t === 'auto') document.body.removeAttribute('data-theme'); else document.body.setAttribute('data-theme', t);
      }}),
      ParsehGear.std['interface']()${extra ? `,
      // a group whose every row is at rest is not drawn; one that says which layout it is for is drawn in that one only
      {id: 'empty', title: 'Nothing here yet', caption: 'Saved on this device.', rows: [
        {id: 'x', kind: 'note', text: 'Drawn only while the page says so.', when: function () { return !!window.__showEmpty; }}]},
      {id: 'onlymobile', title: 'Only on a phone', caption: 'Saved on this device.', layouts: 'mobile', rows: [
        {id: 'm', kind: 'note', text: 'A group for the mobile layout.'}]},
      {id: 'onlybrowser', title: 'Only in the browser', caption: 'Saved on this device.', layouts: 'browser', rows: [
        {id: 'b', kind: 'note', text: 'A group for the browser layout.'},
        {id: 'bm', kind: 'note', text: 'A row for the mobile layout inside it.', layouts: 'mobile'}]},
      {id: 'gated', title: 'Gated', caption: 'Saved on this device.', when: function () { return !!window.__open; }, rows: [
        {id: 'g', kind: 'note', text: 'Drawn while the group says so.'}]}` : ''}
    ]
  };
  window.__gear = ParsehGear.mount(window.__spec);
  window.__ready = true;
})();
</script>
</body></html>`;
}

function startServer() {
  const server = Deno.serve({hostname: '127.0.0.1', port: 0, onListen: () => {}}, async req => {
    const u = new URL(req.url), p = decodeURIComponent(u.pathname);
    if (p === '/fx/book.html') return new Response(bookPage(u.searchParams), {headers: {'content-type': 'text/html; charset=utf-8'}});
    if (p === '/fx/doc.html') return new Response(docPage(u.searchParams), {headers: {'content-type': 'text/html; charset=utf-8'}});
    if (p.startsWith('/lib/')) return file(p, '');
    if (SHOTS && p.startsWith('/shots/')) {
      try { return new Response(await Deno.readFile(SHOTS + p.slice('/shots'.length)), {headers: {'content-type': 'image/png'}}); }
      catch { return new Response('not found', {status: 404}); }
    }
    if (p.startsWith('/studio/static/')) return file(p.slice('/studio/static'.length), 'markdown/app/static');
    if (p === '/settings/' || p.startsWith('/settings/')) return new Response('<!doctype html><title>settings</title><h1>Parseh settings</h1>', {headers: {'content-type': 'text/html'}});
    if (p === '/sw.js') return new Response('', {headers: {'content-type': 'text/javascript'}});
    if (p === '/manifest.webmanifest') return new Response('{}', {headers: {'content-type': 'application/manifest+json'}});
    return new Response(null, {status: 204});
  });
  return {server, base: `http://127.0.0.1:${server.addr.port}`};
}

/* ---------------------------------------------------------------- the browser */
const {server, base} = startServer();
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
const errors = [];
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, deviceScaleFactor: 2};
const WIDE = {viewport: {width: 1280, height: 800}};
const THEMES = ['light', 'dark', 'sepia'];

/* A page of the fixture in a fresh context: `kind` 'wide' or 'phone' (the phone's mode is the mobile one, unless
   `mode` says otherwise), the stored theme, and whatever else the test wants in the query. */
async function open(kind, fixture, {theme = 'light', mode = null, query = '', width = null, height = null, init = null, reduced = false} = {}) {
  const base0 = kind === 'phone' ? PHONE : WIDE;
  const opts = {...base0, viewport: {width: width || base0.viewport.width, height: height || base0.viewport.height}};
  if (reduced) opts.reducedMotion = 'reduce';
  const context = await browser.newContext(opts);
  const m = mode || (kind === 'phone' ? 'mobile' : 'browser');
  await context.addInitScript(([t, mo]) => {
    try {
      if (localStorage.getItem('parseh_theme') === null) localStorage.setItem('parseh_theme', t);
      if (localStorage.getItem('parseh_mode') === null) localStorage.setItem('parseh_mode', mo);
      document.cookie = 'parseh_mode=' + localStorage.getItem('parseh_mode') + '; Path=/';
    } catch (e) {}
  }, [theme, m]);
  if (init) await context.addInitScript(init);
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  page.on('pageerror', e => errors.push(fixture + ' pageerror: ' + e.message));
  page.on('console', c => { if (c.type() === 'error') errors.push(fixture + ' console: ' + c.text()); });
  await page.goto(`${base}/fx/${fixture}.html${query ? '?' + query : ''}`);
  await page.waitForFunction(() => window.__ready === true);
  await page.waitForFunction(() => !document.querySelector('[data-parseh-gear]').style.visibility);
  return {page, context, close: () => context.close()};
}

const gearBtn = page => page.locator('[data-parseh-gear]');
const panelOf = page => page.locator('.pg-panel');
const rowOf = (page, id) => page.locator(`.pg-row[data-pg-row="${id}"]`);
const groupOf = (page, id) => page.locator(`.pg-group[data-pg-group="${id}"]`);
const calls = page => page.evaluate(() => window.__calls.slice());
const lastCall = async page => (await calls(page)).slice(-1)[0];
const isUp = page => page.evaluate(() => window.__gear.isOpen());
async function openGear(page, group) {
  await page.evaluate(g => window.__gear.open(g), group || undefined);
  await page.waitForSelector('.pg-panel:not([hidden])');
  // on the phone's sheet a theme slides in from the right (0.16 s): let it come to rest before anything is measured
  if (group && await page.evaluate(() => document.querySelector('.pg-panel').classList.contains('pg-sheet'))) {
    await page.waitForFunction(g => document.querySelector('.pg-panel').getAttribute('data-pg-stage') === g, group, {timeout: 2000}).catch(() => {});
    await sleep(240);
  }
}

const ids = {book: ['levels', 'listening', 'lookup', 'text', 'zoom', 'colours', 'interface'],
            doc: ['text', 'exercises', 'page', 'zoom', 'colours', 'interface']};
// what the keyboard is on, said short
const where = page => page.evaluate(() => {
  const a = document.activeElement;
  if (!a) return 'none';
  const row = a.closest('[data-pg-row]'), lv = a.closest('[data-pg-level]');
  return a.tagName.toLowerCase() + (a.type && a.tagName === 'INPUT' ? ':' + a.type : '') +
    (a.getAttribute('role') ? '[' + a.getAttribute('role') + ']' : '') + (row ? '@' + row.getAttribute('data-pg-row') : '') +
    (lv ? '/' + lv.getAttribute('data-pg-level') : '') + (a.classList.contains('pg-panel') ? '#panel' : '');
});
const swOf = (page, id) => rowOf(page, id).locator('button.pg-switch');
const rangeOf = (page, id) => rowOf(page, id).locator('input.pg-range');
const outOf = (page, id) => rowOf(page, id).locator('output.pg-out');
const chipsOf = (page, id) => rowOf(page, id).locator('.pg-chip');
const checked = async (page, id) => (await chipsOf(page, id).evaluateAll(cs => cs.map(c => c.getAttribute('aria-checked') === 'true' ? c.textContent : null))).filter(Boolean);
const pressed = async (page, id) => (await chipsOf(page, id).evaluateAll(cs => cs.map(c => c.getAttribute('aria-pressed') === 'true' ? c.textContent : null))).filter(Boolean);
const store = (page, k) => page.evaluate(k => localStorage.getItem(k), k);
const attrOf = (page, sel, a) => page.evaluate(([s, a]) => { const e = document.querySelector(s); return e ? e.getAttribute(a) : null; }, [sel, a]);
const rect = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }, sel);
const near = (a, b, tol) => Math.abs(a - b) <= tol;

/* A section that fails stops THAT section and no other, and every failure is listed at the end: a run is long, and
   the lock it waits for is longer. */
const failed = [];
async function sec(name, fn) {
  if (!want(name)) return;
  console.log(name + ')');
  try { await fn(); } catch (e) { failed.push(name + ': ' + e.message); console.log('  FAILED ' + e.message); }
}

await sec('button', async () => {
  const read = page => gearBtn(page).evaluate(e => {
    const r = e.getBoundingClientRect(), w = e.querySelector('.pg-gear-word'), g = e.querySelector('.pg-gear-glyph');
    return {tag: e.tagName, type: e.getAttribute('type'), label: e.getAttribute('aria-label'), title: e.getAttribute('title'),
      popup: e.getAttribute('aria-haspopup'), expanded: e.getAttribute('aria-expanded'), data: e.hasAttribute('data-parseh-gear'),
      glyph: g && g.textContent, glyphHidden: g && g.getAttribute('aria-hidden'), word: w && w.textContent,
      wordShown: !!(w && w.getClientRects().length), host: e.parentElement && e.parentElement.id,
      last: e.parentElement && e.parentElement.lastElementChild === e, w: r.width, h: r.height, right: r.right, vw: innerWidth};
  });
  let t = await open('wide', 'book');
  let b = await read(t.page);
  eq([b.tag, b.type], ['BUTTON', 'button'], 'wide: a <button type=button>');
  eq(b.label, 'Settings of this page', 'wide: aria-label');
  eq(b.title, 'Settings of this page: how it looks, how it reads, how it zooms', 'wide: the title says what it holds');
  eq([b.popup, b.expanded, b.data], ['dialog', 'false', true], 'wide: aria-haspopup=dialog, aria-expanded=false, data-parseh-gear');
  eq([b.glyph, b.glyphHidden, b.word], ['⚙', 'true', 'page'], 'wide: the glyph (hidden from a reader of the screen) and the word');
  assert(b.wordShown, 'wide: the word is drawn');
  eq([b.host, b.last], ['bhost', true], "wide: the browser layout's host, as its last item");
  assert(b.h < 40 && b.right <= b.vw, 'wide: the size of the bar\'s own buttons (' + Math.round(b.h) + 'px), inside the window');
  eq(await t.page.locator('[data-parseh-gear]').count(), 1, 'wide: one button in the whole page');
  eq(await t.page.locator('#mhost [data-parseh-gear]').count(), 0, "wide: none in the other layout's host");
  eq(await panelOf(t.page).count(), 0, 'wide: no panel is built before it is asked for');
  // the layout in force decides the host, and the button follows a change of it
  await t.page.evaluate(() => Parseh.mode.set('mobile'));
  await until(async () => (await read(t.page)).host === 'mhost', 'the button moves to the mobile bar');
  b = await read(t.page);
  assert(!b.wordShown && b.w >= 47.5 && b.h >= 47.5, 'the mobile layout on a wide screen: ⚙ alone, 48px (' + Math.round(b.w) + 'x' + Math.round(b.h) + ')');
  await t.page.evaluate(() => Parseh.mode.set('browser'));
  await until(async () => (await read(t.page)).host === 'bhost', 'and back to the browser bar');
  assert((await read(t.page)).wordShown, 'back in the browser layout the word returns');
  await t.close();

  t = await open('phone', 'book');
  b = await read(t.page);
  eq([b.host, b.glyph, b.wordShown], ['mhost', '⚙', false], 'phone: in the mobile bar, ⚙ alone');
  assert(b.w >= 47.5 && b.h >= 47.5, 'phone: a 48px target (' + Math.round(b.w) + 'x' + Math.round(b.h) + ')');
  eq([b.label, b.title], ['Settings of this page', 'Settings of this page: how it looks, how it reads, how it zooms'], 'phone: the same name and title');
  await t.close();

  t = await open('phone', 'book', {mode: 'browser'});
  b = await read(t.page);
  eq([b.host, b.wordShown], ['bhost', false], 'a phone in the browser layout: its bar, ⚙ alone (under 600px)');
  assert(b.h >= 47.5, 'a phone in the browser layout: 48px high too');
  await t.close();

  for (const [w, shown] of [[700, true], [599, false], [620, true]]) {
    t = await open('wide', 'book', {width: w, height: 800});
    eq((await read(t.page)).wordShown, shown, `at ${w}px the word is ${shown ? 'drawn' : 'hidden'} (600px is the line)`);
    await t.close();
  }

  // the document, which has no Parseh: the mode it reads is its own storage and the event it listens for
  t = await open('wide', 'doc');
  b = await read(t.page);
  eq([b.host, b.wordShown, b.last], ['dhost', true, true], 'doc: the studio\'s topbar, the word drawn');
  await t.page.evaluate(() => {
    localStorage.setItem('parseh_mode', 'mobile');
    document.documentElement.setAttribute('data-mode', 'mobile');
    document.dispatchEvent(new CustomEvent('parseh:mode'));
  });
  await until(async () => (await read(t.page)).host === 'dmhost', 'doc: the button moves to the mobile topbar');
  assert(!(await read(t.page)).wordShown, 'doc: ⚙ alone in the mobile layout');
  await t.close();
});

await sec('open', async () => {
  let t = await open('wide', 'book');
  let p = t.page;
  await p.evaluate(() => {
    window.__esc = [];
    window.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc.push(e.defaultPrevented); });
    window.__told = [];
    window.__untell = window.__gear.onToggle(v => window.__told.push(v));
    document.getElementById('aa').addEventListener('click', () => window.__gear.open('text'));
  });
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await attrOf(p, '[data-parseh-gear]', 'aria-expanded'), 'true', 'a click opens it: aria-expanded');
  eq(await isUp(p), true, 'isOpen()');
  const pa = await panelOf(p).evaluate(e => ({role: e.getAttribute('role'), label: e.getAttribute('aria-label'), dir: e.getAttribute('dir'),
    lang: e.getAttribute('lang'), cs: getComputedStyle(e).direction, focus: document.activeElement === e, ctl: document.querySelector('[data-parseh-gear]').getAttribute('aria-controls') === e.id,
    title: e.querySelector('.pg-title').textContent, first: e.querySelector('.pg-first').textContent,
    foot: e.querySelector('.pg-footlink').textContent, href: e.querySelector('.pg-footlink').getAttribute('href'),
    x: e.querySelector('.pg-x').getAttribute('title'), xl: e.querySelector('.pg-x').getAttribute('aria-label'),
    cls: e.className, html: document.documentElement.className}));
  eq([pa.role, pa.label, pa.dir, pa.lang, pa.cs], ['dialog', 'Settings of this page', 'ltr', 'en', 'ltr'], 'the panel: role=dialog, its name, left to right and English in a right-to-left page');
  eq([pa.title, pa.first], ['This page', 'Only for this page.'], 'the head says "This page" and the first line says it is only about this page');
  eq([pa.foot, pa.href], ["Parseh's own settings (network, updating, dictionaries)", '/settings/'], "the foot links to Parseh's own settings");
  eq([pa.x, pa.xl], ['close (Esc)', 'Close'], '✕: titled "close (Esc)" and named Close');
  assert(pa.focus && pa.ctl, 'the keyboard is in the panel and the button names it (aria-controls)');
  assert(/pg-popover/.test(pa.cls) && !/pg-sheet/.test(pa.cls) && /pg-open/.test(pa.html), 'a wide window gets the popover; <html> wears pg-open');
  // where it stands
  const rb = await rect(p, '[data-parseh-gear]'), rp = await rect(p, '.pg-panel');
  assert(rp.t >= rb.b + 3 && rp.t <= rb.b + 12, `under the button (${Math.round(rb.b)} -> ${Math.round(rp.t)})`);
  assert(near(rp.r, rb.r, 2), `its right edge on the button's (${Math.round(rp.r)} / ${Math.round(rb.r)})`);
  assert(rp.w >= 360 && rp.w <= 381 && rp.l >= 0 && rp.b <= 800, `about 380px wide and inside the window (${Math.round(rp.w)}px, bottom ${Math.round(rp.b)})`);
  eq(await panelOf(p).evaluate(e => e.querySelector('.pg-body').scrollHeight > e.querySelector('.pg-body').clientHeight || true), true, 'it scrolls inside (the body is the one scroller)');
  // the toggle
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  eq(await isUp(p), false, 'the button again closes it');
  eq(await attrOf(p, '[data-parseh-gear]', 'aria-expanded'), 'false', 'aria-expanded goes back to false');
  // Esc with the keyboard IN the panel: it closes it, and the page does not hear it at all
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  await p.keyboard.press('Escape');
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  eq(await p.evaluate(() => window.__esc), [], 'Esc typed in the panel closes it and is not heard by the page: one Esc, one layer');
  eq(await where(p), 'button', 'the keyboard goes back to the button');
  // Esc with the keyboard on the page while the popover is up: spent on the popover, so a layer under it stays
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  await p.evaluate(() => document.activeElement.blur());
  await p.keyboard.press('Escape');
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  eq(await p.evaluate(() => window.__esc), [true], 'Esc typed on the page while the popover is up closes it and is spent: defaultPrevented for a layer under it');
  await p.keyboard.press('Escape');
  eq((await p.evaluate(() => window.__esc)).slice(-1)[0], false, 'with the panel shut an Esc is nobody\'s: not spent');
  // ✕
  await gearBtn(p).click();
  await p.locator('.pg-x').click();
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  assert(true, '✕ closes it');
  // outside
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  await p.locator('.pg-title').click();
  eq(await isUp(p), true, 'a click on the panel itself leaves it open');
  await p.mouse.click(300, 400);
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  assert(true, 'a click outside closes the popover');
  // the page's own Aa opens it at the text, and cannot close it again with the same click
  await p.locator('#aa').click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await isUp(p), true, 'Aa opens the gear (and the click that opened it does not close it)');
  const at = await p.evaluate(() => { const g = document.querySelector('[data-pg-group=text]'), b = document.querySelector('.pg-body');
    return {top: g.getBoundingClientRect().top - b.getBoundingClientRect().top, focus: document.activeElement.closest('[data-pg-group]') && document.activeElement.closest('[data-pg-group]').getAttribute('data-pg-group'), cls: document.activeElement.className}; });
  assert(at.top < 24 && at.top > -4, `open('text') scrolls the Text group to the top of the panel (${Math.round(at.top)}px)`);
  eq([at.focus, at.cls], ['text', 'pg-range'], "and focuses the group's first control");
  await p.locator('#aa').click();
  eq(await isUp(p), true, 'Aa while it is open leaves it open');
  await openGear(p, 'listening');
  const at2 = await p.evaluate(() => document.activeElement.closest('[data-pg-group]').getAttribute('data-pg-group'));
  eq(at2, 'listening', 'open(group) on an open panel moves to that group');
  await openGear(p, 'no-such-group');
  eq(await isUp(p), true, 'an unknown group is not an error: the panel is simply open');
  const told = await p.evaluate(() => window.__told.slice());
  assert(told.length >= 8 && told.every((v, i) => v === (i % 2 === 0)), `onToggle: true, false, true, false... (${told.length} calls)`);
  await p.evaluate(() => { window.__untell(); });
  await p.keyboard.press('Escape');
  const n = (await p.evaluate(() => window.__told.length));
  await gearBtn(p).click();
  eq(await p.evaluate(() => window.__told.length), n, 'the function onToggle gave back takes the listener off');
  // watchers are alive while the panel stands, and gone when a second mount replaces it
  assert(await p.evaluate(() => window.__subs('gloss')) > 0, 'rows are watched once the panel is built');
  await p.evaluate(() => {
    window.__second = ParsehGear.mount({page: 'book', host: {browser: function () { return document.getElementById('bhost'); }},
      groups: [{id: 'one', title: 'One', caption: 'Only one.', rows: [{id: 'n', kind: 'note', text: 'hello'}]}]});
  });
  eq(await p.locator('[data-parseh-gear]').count(), 1, 'a second mount replaces the first: one button');
  eq(await p.evaluate(() => window.__subs('gloss')), 0, "the first mount's watchers were taken off");
  eq(await panelOf(p).count(), 0, "and its panel is gone");
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await p.locator('.pg-group').count(), 1, 'the second mount draws its own groups');
  eq(await p.locator('.pg-note').textContent(), 'hello', 'a note is a line of text');
  await t.close();

  // a host that is not there yet: the button waits for it
  t = await open('wide', 'book');
  p = t.page;
  await p.evaluate(() => {
    window.__late = null;
    window.__lateGear = ParsehGear.mount({page: 'book', host: {browser: function () { return window.__late; }}, groups: [{id: 'g', title: 'G', rows: [{id: 'n', kind: 'note', text: 'x'}]}]});
  });
  eq(await p.evaluate(() => window.__lateGear.button.isConnected), false, 'with no host the button is not in the page');
  await p.evaluate(() => { const s = document.createElement('span'); s.id = 'late'; document.querySelector('#bbar').appendChild(s); window.__late = s; });
  await until(() => p.evaluate(() => window.__lateGear.button.parentElement && window.__lateGear.button.parentElement.id === 'late'), 'the button finds its host once the page has drawn it');
  await t.close();
});

await sec('kinds', async () => {
  let t = await open('wide', 'book');
  let p = t.page;
  await openGear(p, 'levels');
  // a switch
  const dia = swOf(p, 'diacritics');
  eq(await dia.getAttribute('aria-checked'), 'true', 'switch: reads get()');
  eq(await dia.getAttribute('role'), 'switch', 'switch: role=switch on a <button>');
  await dia.click();
  eq([await dia.getAttribute('aria-checked'), await lastCall(p)], ['false', {id: 'diacritics', v: false}], 'switch: a click flips it and calls set(false)');
  await rowOf(p, 'diacritics').locator('.pg-help').click();
  eq([await dia.getAttribute('aria-checked'), await lastCall(p)], ['true', {id: 'diacritics', v: true}], 'switch: the sentence is part of the target');
  const names = await rowOf(p, 'diacritics').evaluate(e => ({name: e.querySelector('.pg-name').textContent, help: e.querySelector('.pg-help').textContent.length > 20,
    by: document.getElementById(e.querySelector('button').getAttribute('aria-labelledby')).textContent, desc: e.querySelector('button').getAttribute('aria-describedby').split(' ').some(i => document.getElementById(i) && document.getElementById(i).classList.contains('pg-help'))}));
  assert(names.name === 'Diacritics' && names.help && names.by === 'Diacritics' && names.desc, 'switch: a visible name and sentence, named and described (aria-labelledby, aria-describedby)');
  // external change through watch, and refresh()
  await p.evaluate(() => { window.__st.vowels = false; window.__emit('diacritics'); });
  eq(await dia.getAttribute('aria-checked'), 'false', 'switch: an external change reaches the row through watch');
  await p.evaluate(() => { window.__st.vowels = true; });
  eq(await dia.getAttribute('aria-checked'), 'false', 'switch: nothing is re-read by itself where there is no watch...');
  await p.evaluate(() => window.__gear.refresh());
  eq(await dia.getAttribute('aria-checked'), 'true', '...and refresh() re-reads every row');
  // when()
  await p.evaluate(() => { window.__st.lang = 'ar'; window.__gear.refresh(); });
  eq(await rowOf(p, 'diacritics').isVisible(), false, 'when() false: the row is not drawn');
  await p.evaluate(() => { window.__st.lang = 'fa'; window.__st.audio = false; window.__gear.refresh(); });
  eq([await rowOf(p, 'diacritics').isVisible(), await rowOf(p, 'hoverpause').isVisible()], [true, false], 'when() true again: drawn; another row\'s when() false: not drawn');
  await p.evaluate(() => { window.__st.audio = true; window.__gear.refresh(); });
  // disabled() with its reason, and a change in one row reaching another
  eq([await swOf(p, 'gloss').isDisabled(), await rowOf(p, 'gloss').locator('.pg-why').isVisible()], [false, false], 'disabled(): false means enabled and says nothing');
  await swOf(p, 'hover').click();
  eq(await swOf(p, 'gloss').isDisabled(), true, 'disabled(): the row is at rest while the hover cloud is on');
  eq(await rowOf(p, 'gloss').locator('.pg-why').textContent(), 'The cloud is showing the glosses, so this rests while it is on.', 'disabled(): the reason is printed under the row');
  eq(await rowOf(p, 'gloss').locator('.pg-why').isVisible(), true, 'disabled(): and it is visible');
  assert(await rowOf(p, 'gloss').evaluate(e => e.querySelector('button').getAttribute('aria-describedby').split(' ').some(i => document.getElementById(i) === e.querySelector('.pg-why'))), 'disabled(): the reason describes the control');
  const kept = await p.evaluate(() => window.__calls.length);
  await rowOf(p, 'gloss').locator('.pg-switch').click({force: true}).catch(() => {});
  eq(await p.evaluate(() => window.__calls.length), kept, 'a disabled switch does nothing when pressed');
  // levels: a level at rest, with the reason, in the row that holds it
  const chunks = p.locator('.pg-lv[data-pg-level=chunks]');
  eq([await chunks.locator('input[type=checkbox]').isDisabled(), await chunks.locator('.pg-lvname').isDisabled()], [true, true], 'levels: a level whose item says disabled is at rest');
  eq(await rowOf(p, 'levels').locator('.pg-why').textContent(), 'The cloud shows the glosses, so this level rests.', "levels: and its reason is printed under the row");
  await swOf(p, 'hover').click();
  eq([await swOf(p, 'gloss').isDisabled(), await rowOf(p, 'gloss').locator('.pg-why').isVisible(), await chunks.locator('.pg-lvname').isDisabled()], [false, false, false], 'turned off again, everything is enabled and the reasons are gone');

  // levels
  const lv = key => p.locator(`.pg-lv[data-pg-level=${key}]`);
  eq(await p.locator('.pg-lv').count(), 4, 'levels: one line for each level');
  eq(await p.locator('.pg-lv .pg-lvname').evaluateAll(a => a.map(i => i.value)), ['With vowels', 'Chunks', 'Plain', 'Nastaliq'], "levels: each name is in its box (the usual name where the person has given none)");
  eq(await p.locator('.pg-lv .pg-lvname').evaluateAll(a => a.map(i => i.placeholder)), ['With vowels', 'Chunks', 'Plain', 'Nastaliq'], 'levels: and an emptied box shows the usual name');
  eq(await p.locator('.pg-lv input[type=checkbox]').evaluateAll(a => a.map(i => i.checked)), [true, true, true, false], 'levels: ticked as the page says');
  eq(await lv('vocal').locator('.pg-lvhelp').textContent(), 'the sentence with its vowels, to read on its own', "levels: each level's own sentence under it");
  await lv('alt').locator('input[type=checkbox]').check();
  eq(await lastCall(p), {id: 'level.shown.alt', v: true}, 'levels: ticking calls setShown(key, true)');
  await lv('alt').locator('input[type=checkbox]').uncheck();
  eq(await lastCall(p), {id: 'level.shown.alt', v: false}, 'levels: and unticking, false');
  const name = lv('vocal').locator('.pg-lvname');
  eq(await name.getAttribute('dir'), 'auto', 'levels: the name box takes the direction of what is typed (dir=auto) in a page that is not');
  await name.fill('Vowels');
  await until(async () => (await calls(p)).some(c => c.id === 'level.name.vocal' && c.v === 'Vowels'), 'a typed name is handed to setName');
  await sleep(700);
  eq((await calls(p)).filter(c => c.id === 'level.name.vocal').length, 1, 'levels: once (the typing is waited out), not once a key');
  await name.fill('  Hi  ');
  await name.press('Enter');
  eq((await lastCall(p)), {id: 'level.name.vocal', v: 'Hi'}, 'levels: Enter hands it over at once, trimmed');
  await name.fill('ABCDEFGHIJKLMNOP');
  eq(await name.inputValue(), 'ABCDEFGHIJKL', 'levels: a name is at most 12 characters');
  await name.fill('');
  await name.pressSequentially('abcdefghijklmnop');
  eq((await name.inputValue()).length, 12, 'levels: and typed, the box stops at 12');
  await name.fill('With vowels');
  await name.press('Enter');
  eq(await lastCall(p), {id: 'level.name.vocal', v: ''}, "levels: a name that is the usual one is no name: setName(key, '')");
  await name.fill('');
  await name.blur();
  await until(async () => (await name.inputValue()) === 'With vowels', 'an emptied box goes back to the usual name when it is left');
  eq(await lastCall(p), {id: 'level.name.vocal', v: ''}, "levels: emptied and left, setName(key, '') -- back to the usual name");
  await name.fill('فارسی');
  eq(await name.evaluate(e => e.matches(':dir(rtl)')), true, 'levels: a right-to-left name is set right to left');
  await name.fill('Latin');
  eq(await name.evaluate(e => e.matches(':dir(ltr)')), true, 'levels: a Latin one left to right');
  await name.fill('');
  await name.blur();
  await p.evaluate(() => { window.__st.levels.bare.shown = false; window.__st.levels.bare.name = 'Raw'; window.__emit('levels'); });
  eq([await lv('bare').locator('input[type=checkbox]').isChecked(), await lv('bare').locator('.pg-lvname').inputValue()], [false, 'Raw'], 'levels: an external change (watch) redraws the list');
  eq(await rowOf(p, 'levels').locator('.pg-kept').textContent(), 'follows you', "a row whose caption is not its own says where IT is kept");
  eq(await rowOf(p, 'diacritics').locator('.pg-kept').count(), 0, 'and a row that has no kept says nothing');

  // sliders
  await openGear(p, 'text');
  const px = rangeOf(p, 'px');
  eq(await px.evaluate(e => [e.min, e.max, e.step, e.value, e.getAttribute('aria-valuetext')]), ['18', '56', '1', '28', '28px'], 'slider: min, max, step, the value, valuetext');
  eq(await outOf(p, 'px').textContent(), '28px', 'slider: the output says it with its unit');
  await px.focus();
  await p.keyboard.press('ArrowRight');
  await p.keyboard.press('ArrowRight');
  eq([await lastCall(p), await outOf(p, 'px').textContent()], [{id: 'px', v: 30}, '30px'], 'slider: the arrows step it and call set(30)');
  eq(await p.evaluate(() => document.documentElement.style.getPropertyValue('--rd-fa')), '30px', 'slider: and the page above shows it at once');
  await p.keyboard.press('Home');
  eq(await lastCall(p), {id: 'px', v: 18}, 'slider: Home is the least');
  const box = await px.boundingBox();
  await p.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
  const mid = (await lastCall(p)).v;
  assert(mid >= 35 && mid <= 39, `slider: a click in the middle of the track is about the middle (${mid})`);
  await p.evaluate(() => { window.__st.px = 44; window.__emit('px'); });
  eq([await px.inputValue(), await outOf(p, 'px').textContent()], ['44', '44px'], 'slider: an external change reaches it through watch');
  await openGear(p, 'listening');
  await rangeOf(p, 'gap').focus();
  await p.keyboard.press('Home');
  eq([await outOf(p, 'gap').textContent(), await lastCall(p)], ['none', {id: 'gap', v: 0}], "slider: a format() says what a value is (0 is 'none')");
  await p.keyboard.press('ArrowRight');
  eq(await outOf(p, 'gap').textContent(), '0.5 s', 'slider: and the next step');
  // an action puts values back and every row reads them again, with no watch to say so
  await openGear(p, 'text');
  await p.evaluate(() => { window.__st.px = 50; window.__gear.refresh(); });
  eq(await outOf(p, 'px').textContent(), '50px', 'action: (setup) the slider says 50px');
  await rowOf(p, 'normal').locator('button.pg-action').click();
  eq(await lastCall(p), {id: 'normal', v: true}, 'action: a press calls onClick');
  eq(await outOf(p, 'px').textContent(), '28px', "action: and the sliders it changed are read again at once");
  eq(await rowOf(p, 'normal').locator('.pg-name').count(), 0, 'action: its label is its own name, drawn once, on the button');
  eq(await rowOf(p, 'normal').locator('.pg-help').textContent(), 'Resets only the text sliders.', 'action: with its sentence under it');

  // choice: a picker for more than four
  await openGear(p, 'listening');
  const sp = rowOf(p, 'speed').locator('select.pg-select');
  eq(await sp.evaluate(e => [e.options.length, e.options[e.selectedIndex].text]), [8, '1×'], 'choice: more than four options is a <select>, on the current one');
  await sp.selectOption({label: '1.5×'});
  eq([await lastCall(p), await sp.evaluate(e => e.options[e.selectedIndex].text)], [{id: 'speed', v: 1.5}, '1.5×'], 'choice: choosing calls set(value) with the option\'s own value (a number stays a number)');
  await p.evaluate(() => { window.__st.speed = 1.3; window.__emit('speed'); });
  eq(await sp.evaluate(e => e.options[e.selectedIndex].text), '1.3', 'choice: a value the list does not hold (set by a key) is shown, not hidden');
  await p.evaluate(() => { window.__st.speed = 2; window.__emit('speed'); });
  eq(await sp.evaluate(e => [e.options.length, e.options[e.selectedIndex].text]), [8, '2×'], 'choice: and goes when the value is one of the list again');
  // link
  await openGear(p, 'lookup');
  const lk = rowOf(p, 'help').locator('a.pg-link');
  eq(await lk.evaluate(e => [e.textContent, e.getAttribute('href'), e.getAttribute('target')]), ['Get a dictionary for this language →', '/settings/reading-help/', null], 'link: the words, where it goes, in this tab');
  eq(await rowOf(p, 'help').locator('.pg-help').textContent(), 'Opens the page where dictionaries are chosen and installed.', 'link: with its sentence');
  // disabled by a reason that is another row's state
  eq(await swOf(p, 'defs').isDisabled(), true, 'disabled(): a row waiting for another');
  eq(await rowOf(p, 'defs').locator('.pg-why').textContent(), 'Turn on “Look words up in a dictionary” first.', 'disabled(): and says what to turn on');
  await swOf(p, 'dict').click();
  eq([await swOf(p, 'defs').isDisabled(), await rowOf(p, 'defs').locator('.pg-why').isVisible()], [false, false], 'disabled(): turned on, the other is free and the reason gone');
  await t.close();

  // the document: a choice of chips with a sentence for each option, the two kinds of link, the groups that are not drawn
  t = await open('wide', 'doc', {query: 'extra=1'});
  p = t.page;
  await openGear(p, 'exercises');
  const sides = rowOf(p, 'sides');
  eq(await sides.locator('[role=radiogroup]').count(), 1, 'choice: up to four short options is a radiogroup of chips');
  eq(await checked(p, 'sides'), ['Both'], 'choice: the current one is checked');
  eq(await sides.locator('.pg-opthelp').textContent(), 'Front and back side by side.', "choice: the checked option's own sentence is said under it");
  await chipsOf(p, 'sides').filter({hasText: 'Front'}).click();
  eq([await lastCall(p), await checked(p, 'sides'), await sides.locator('.pg-opthelp').textContent()], [{id: 'sides', v: 'front'}, ['Front'], 'Only the front; press to turn the card over.'], 'choice: choosing calls set(value) and the sentence follows');
  eq(await chipsOf(p, 'sides').evaluateAll(a => a.map(c => c.tabIndex)), [-1, 0, -1], 'choice: one stop in the tab order, the checked one');
  await openGear(p, 'page');
  const nt = rowOf(p, 'guide').locator('a.pg-link');
  eq(await nt.evaluate(e => [e.getAttribute('href'), e.getAttribute('target'), e.getAttribute('rel')]), ['https://parseh.io/guide', '_blank', 'noopener'], 'link: newTab opens another tab and keeps the page to itself (noopener)');
  const say = rowOf(p, 'say').locator('button.pg-link');
  eq(await say.count(), 1, 'link: with onClick it is a button that looks like a link');
  await say.click();
  eq(await lastCall(p), {id: 'say', v: true}, 'link: and calls onClick');
  eq(await groupOf(p, 'empty').isVisible(), false, 'a group with no drawn row is not drawn');
  await p.evaluate(() => { window.__showEmpty = true; window.__gear.refresh(); });
  eq(await groupOf(p, 'empty').isVisible(), true, '...and is drawn when a row is');
  eq(await groupOf(p, 'gated').isVisible(), false, 'a group whose when() is false is not drawn');
  await p.evaluate(() => { window.__open = true; window.__gear.refresh(); });
  eq(await groupOf(p, 'gated').isVisible(), true, '...and is when it is true');
  eq([await groupOf(p, 'onlymobile').isVisible(), await groupOf(p, 'onlybrowser').isVisible(), await rowOf(p, 'bm').isVisible()], [false, true, false], "layouts: in the browser layout the browser's group is drawn, the phone's is not, nor a mobile row in it");
  await t.close();
  t = await open('phone', 'doc', {query: 'extra=1'});
  p = t.page;
  await openGear(p);
  // the sheet draws a theme at a time: what it offers is its index
  eq([await p.locator('.pg-irow[data-pg-index=onlymobile]').isVisible(), await p.locator('.pg-irow[data-pg-index=onlybrowser]').isVisible()], [true, false], "layouts: in the mobile layout the phone's group is on the index and the browser's is not");
  await t.close();
});

await sec('node', async () => {
  // THE CHAIN: indent, and the state of the row above handed to disabled()
  let t = await open('wide', 'book');
  let p = t.page;
  await openGear(p, 'lookup');
  const left = id => p.evaluate(id => document.querySelector(`[data-pg-row=${id}]`).getBoundingClientRect().left, id);
  const lDict = await left('dict'), lDefs = await left('defs'), lTrans = await left('trans'), lHelp = await left('help');
  assert(near(lDefs - lDict, 16, 2) && near(lTrans - lDefs, 16, 2), `indent: 1 hangs a row 16px under the one above, 2 another step (${Math.round(lDefs - lDict)}, ${Math.round(lTrans - lDefs)})`);
  eq([await rowOf(p, 'dict').getAttribute('data-pg-indent'), await rowOf(p, 'defs').getAttribute('data-pg-indent'), await rowOf(p, 'trans').getAttribute('data-pg-indent')], [null, '1', '2'], 'indent: the row says how deep it hangs');
  assert(near(lHelp, lDict, 1), 'indent: a row without it is back at the margin');
  eq(await rowOf(p, 'defs').evaluate(e => getComputedStyle(e).borderLeftWidth), '2px', 'indent: with a rule down its left, to say what it hangs from');
  const argsOf = id => p.evaluate(id => window.__args.filter(a => a[0] === id).slice(-1)[0][1], id);
  eq([await argsOf('defs'), await argsOf('trans'), await argsOf('help')], [false, false, false], "disabled(above): a row under a switch that is off is told so (and a link under a switch too)");
  eq(await argsOf('px'), undefined, 'disabled(above): the first row of a group has none above it: undefined');
  eq([await swOf(p, 'defs').isDisabled(), await swOf(p, 'trans').isDisabled(), await rowOf(p, 'trans').locator('.pg-why').textContent()], [true, true, 'Turn on the definitions first.'], 'indent: the chain rests with the reason of the row that matters');
  await swOf(p, 'dict').click();
  eq([await argsOf('defs'), await argsOf('trans'), await swOf(p, 'defs').isDisabled(), await swOf(p, 'trans').isDisabled()], [true, false, false, true], 'indent: the dictionary on frees the definitions; the translation still waits for them');
  await swOf(p, 'defs').click();
  eq([await argsOf('trans'), await swOf(p, 'trans').isDisabled()], [true, false], 'indent: and the definitions on free the translation');
  await t.close();

  // NODE, on a phone: another layer's own buttons, brought in while the sheet is up and sent home when it is not
  t = await open('phone', 'book', {query: 'node=1'});
  p = t.page;
  const state = () => p.evaluate(() => {
    const m = document.getElementById('menu'), k1 = document.getElementById('keep1'), k2 = document.getElementById('keep2');
    return {kids: [...m.childNodes].filter(n => n.nodeType === 1).map(n => n.id),
            marks: [...m.childNodes].filter(n => n.nodeType === 8).length,
            in1: !!k1.closest('.pg-panel'), in2: !!k2.closest('.pg-panel'),
            parent1: k1.parentNode.id || k1.parentNode.className,
            next1: k1.nextSibling ? (k1.nextSibling.id || k1.nextSibling.nodeName) : null, mine: k1.__mine || null};
  });
  await p.evaluate(() => { document.getElementById('keep1').__mine = 'the very same element'; });
  eq(await state(), {kids: ['keep1', 'keep2', 'after'], marks: 0, in1: false, in2: false, parent1: 'menu', next1: 'keep2', mine: 'the very same element'},
     'node: before the panel is opened the buttons are where their layer put them');
  await gearBtn(p).tap();
  await p.waitForSelector('.pg-panel:not([hidden])');
  let s = await state();
  eq([s.in1, s.in2, s.kids], [false, false, ['keep1', 'keep2', 'after']], 'node: the sheet opens on the index, and the buttons are where they were until their theme is entered');
  await openGear(p, 'keep');
  s = await state();
  eq([s.in1, s.in2, s.kids, s.marks, s.parent1, s.mine], [true, true, ['after'], 2, 'pg-node', 'the very same element'],
     'node: with its theme on stage both buttons are in the panel (the same elements) and a mark stands in each place');
  eq(await rowOf(p, 'keep1').locator('#keep1').isVisible(), true, 'node: drawn in its row');
  eq([await rowOf(p, 'keep1').locator('.pg-name').textContent(), await rowOf(p, 'keep1').locator('.pg-help').textContent()],
     ['Keep on this phone', 'Keeps this book so it opens with the computer away.'], 'node: with its name and its sentence where it was given them');
  eq(await rowOf(p, 'keep2').locator('.pg-text').isVisible(), false, 'node: and with neither where it was given none: the button alone');
  eq(await rowOf(p, 'late').isVisible(), false, 'node: el() answering null is a row that is not drawn');
  await p.locator('#keep1').tap();
  eq(await p.evaluate(() => window.__kept), 1, "node: the layer's own handler goes on working from inside the panel");
  // a row that stops being drawn sends its element home at once, to the place its mark kept, and the other stays
  await p.evaluate(() => { window.__noKeep1 = true; window.__gear.refresh(); });
  s = await state();
  eq([s.in1, s.in2, s.kids, s.next1], [false, true, ['keep1', 'after'], '#comment'], "node: a row that stops being drawn sends its element home, to its own place, while the other stays");
  await p.evaluate(() => { window.__noKeep1 = false; window.__gear.refresh(); });
  s = await state();
  eq([s.in1, s.kids], [true, ['after']], 'node: and takes it back when it is drawn again');
  await p.evaluate(() => {
    const b = document.createElement('button');
    b.id = 'latebtn'; b.textContent = 'A late button';
    document.getElementById('menu').appendChild(b);
    window.__late = b; window.__gear.refresh();
  });
  eq([await rowOf(p, 'late').isVisible(), await p.evaluate(() => !!document.getElementById('latebtn').closest('.pg-panel'))], [true, true], 'node: an element that turns up later is drawn on the next refresh');
  await p.locator('.pg-x').tap();
  await p.waitForSelector('.pg-panel', {state: 'hidden'});
  s = await state();
  eq([s.in1, s.in2], [false, false], 'node: shut, nothing of theirs is left in the panel...');
  eq(s.kids, ['keep1', 'keep2', 'after', 'latebtn'], '...every element is in its parent again, in its old order...');
  eq([s.marks, s.parent1, s.next1, s.mine], [0, 'menu', 'keep2', 'the very same element'], '...the same parent, the same next sibling, the very same element, and no mark left behind');
  await gearBtn(p).tap();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq((await state()).in1, false, 'node: opened again, on the index, they are home');
  await openGear(p, 'keep');
  eq((await state()).in1, true, 'node: and come in again with their theme');
  await p.evaluate(() => Parseh.mode.set('browser'));
  await until(async () => (await state()).in1 === false, 'node: the layout is left');
  s = await state();
  eq([s.kids.slice(0, 3), s.marks, await isUp(p)], [['keep1', 'keep2', 'after'], 0, true], 'node: the group is for the mobile layout, so leaving it sends the elements home while the panel stays up');
  await p.evaluate(() => Parseh.mode.set('mobile'));
  await openGear(p, 'keep');
  await until(async () => (await state()).in1 === true, 'node: back in the layout, with the theme entered, they return');
  await p.evaluate(() => window.__gear.unmount());
  s = await state();
  eq([s.in1, s.in2, s.kids.slice(0, 3), s.marks], [false, false, ['keep1', 'keep2', 'after'], 0], 'node: unmount sends every borrowed element home');
  await t.close();
});

await sec('mount', async () => {
  let t = await open('wide', 'book');
  let p = t.page;
  eq(await p.evaluate(() => [window.__gearEvents.slice(), ParsehGear.mounted() === window.__gear]), [['mounted'], true], 'mounted(): the gear in force, and the page was told (parseh:gear, "mounted") by the very first mount');
  eq(await p.evaluate(() => [typeof window.__gear.unmount, typeof window.__gear.destroy, ParsehGear.KINDS.join()]),
     ['function', 'function', 'switch,choice,slider,stepper,levels,link,buttons,action,note,node'], 'the handle has unmount() (and destroy, the same); the kinds are the nine of the contract and node');
  await p.evaluate(() => {
    window.__first = window.__gear;
    window.__second = ParsehGear.mount({page: 'book', host: {browser: () => document.getElementById('bhost')},
      groups: [{id: 'g', title: 'G', rows: [{id: 'n', kind: 'note', text: 'x'}]}]});
  });
  eq(await p.evaluate(() => [window.__gearEvents.slice(), ParsehGear.mounted() === window.__second]), [['mounted', 'mounted'], true], 'a second mount replaces the first with no "unmounted" between: there is a gear all the while');
  await p.evaluate(() => window.__first.unmount());
  eq(await p.evaluate(() => [window.__gearEvents.length, ParsehGear.mounted() === window.__second, document.querySelectorAll('[data-parseh-gear]').length]), [2, true, 1], 'the first handle, replaced, unmounts quietly: no event, the second stays in force');
  await p.evaluate(() => {
    window.__esc = []; window.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc.push(e.defaultPrevented); });
    window.__told = []; window.__second.onToggle(v => window.__told.push(v));
  });
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  await p.evaluate(() => window.__second.unmount());
  eq(await p.evaluate(() => [window.__gearEvents.slice(), ParsehGear.mounted(), document.querySelectorAll('[data-parseh-gear]').length,
                             document.querySelectorAll('.pg-panel').length, document.documentElement.className.includes('pg-open'),
                             window.__second.isOpen(), window.__told.slice()]),
     [['mounted', 'mounted', 'unmounted'], null, 0, 0, false, false, [true, false]],
     'unmount(): the page is told ("unmounted"), mounted() is null, the button and the panel are gone, <html> is clear, and onToggle heard it shut');
  await p.keyboard.press('Escape');
  eq((await p.evaluate(() => window.__esc)).slice(-1)[0], false, "unmount(): no Esc of the page's is spent on a panel that is not there");
  await p.evaluate(() => window.__second.unmount());
  eq(await p.evaluate(() => window.__gearEvents.length), 3, 'unmount() twice says nothing the second time');
  await p.evaluate(() => { ParsehGear.mount({page: 'book', host: {browser: () => document.getElementById('bhost')}, groups: []}); });
  eq(await p.evaluate(() => [window.__gearEvents.slice(-1)[0], document.querySelectorAll('[data-parseh-gear]').length]), ['mounted', 1], 'and a mount after it is a mount again');
  await t.close();
  // on a phone the sheet's history entry goes with the sheet
  t = await open('phone', 'book');
  p = t.page;
  await gearBtn(p).tap();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(typeof await p.evaluate(() => history.state && history.state.parsehGear), 'string', '(setup) the open sheet has pushed its entry');
  await p.evaluate(() => window.__gear.unmount());
  await sleep(300);
  eq(await p.evaluate(() => [history.state, location.pathname]), [null, '/fx/book.html'], "unmount(): on a phone the sheet's history entry goes with it, and the page stays");
  await t.close();
});

await sec('keys', async () => {
  let t = await open('wide', 'book');
  let p = t.page;
  await gearBtn(p).focus();
  await p.keyboard.press('Enter');
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await where(p), 'div[dialog]#panel', 'Enter on the button opens it and puts the keyboard in the panel');
  const seq = [];
  for (let i = 0; i < 7; i++) { await p.keyboard.press('Tab'); seq.push(await where(p)); }
  eq(seq, ['button', 'input:checkbox@levels/vocal', 'input:text@levels/vocal', 'input:checkbox@levels/chunks', 'input:text@levels/chunks', 'input:checkbox@levels/bare', 'input:text@levels/bare'], 'Tab: ✕ first, then the rows in the order they are drawn');
  await p.keyboard.press('Shift+Tab');
  eq(await where(p), 'input:checkbox@levels/bare', 'Shift+Tab goes back');
  // a switch: Space and Enter
  await swOf(p, 'gloss').focus();
  await p.keyboard.press('Space');
  eq([await swOf(p, 'gloss').getAttribute('aria-checked'), await lastCall(p)], ['false', {id: 'gloss', v: false}], 'switch: Space flips it');
  await p.keyboard.press('Enter');
  eq([await swOf(p, 'gloss').getAttribute('aria-checked'), await lastCall(p)], ['true', {id: 'gloss', v: true}], 'switch: Enter flips it back');
  // a radiogroup: arrows move and choose, Home and End are the ends
  await openGear(p, 'colours');
  const th = () => checked(p, 'theme');
  eq(await th(), ['Light'], 'radiogroup: the stored theme is the checked one');
  const light = chipsOf(p, 'theme').filter({hasText: 'Light'});
  await light.focus();
  await p.keyboard.press('ArrowRight');
  eq([await th(), await where(p), await store(p, 'parseh_theme')], [['Dark'], 'button[radio]@theme', 'dark'], 'radiogroup: ArrowRight moves to the next, checks it and sets it');
  await p.keyboard.press('ArrowDown');
  eq(await th(), ['Sepia'], 'radiogroup: ArrowDown too');
  await p.keyboard.press('ArrowRight');
  eq(await th(), ['Follow my device'], 'radiogroup: and round the end');
  await p.keyboard.press('ArrowLeft');
  eq(await th(), ['Sepia'], 'radiogroup: ArrowLeft back');
  await p.keyboard.press('Home');
  eq([await th(), await store(p, 'parseh_theme')], [['Follow my device'], 'auto'], 'radiogroup: Home is the first');
  await p.keyboard.press('End');
  eq(await th(), ['Sepia'], 'radiogroup: End is the last');
  eq(await chipsOf(p, 'theme').evaluateAll(a => a.map(c => c.tabIndex)), [-1, -1, -1, 0], 'radiogroup: roving tabindex: the checked one is the only stop');
  // KEYS TYPED IN THE PANEL BELONG TO THE PANEL: a reader plays on Space and moves on the arrows, on any element
  // but a text box, and must not do either for a switch
  await p.evaluate(() => { window.__keys.length = 0; });
  await openGear(p, 'listening');
  await swOf(p, 'cont').focus();
  await p.keyboard.press('Space');
  await p.keyboard.press('g');
  await p.keyboard.press('ArrowRight');
  await p.keyboard.press('r');
  eq(await p.evaluate(() => window.__keys), [], 'keys: Space, G, R and an arrow typed on a switch of the panel are not heard by the page');
  eq(await swOf(p, 'cont').getAttribute('aria-checked'), 'false', 'keys: ...and Space did what it is for, it flipped the switch');
  await openGear(p, 'levels');
  await p.locator('.pg-lv[data-pg-level=chunks] .pg-lvname').focus();
  await p.keyboard.type('gh');
  eq(await p.evaluate(() => window.__keys), [], 'keys: letters typed in a level\'s name are not heard by the page either');
  await p.evaluate(() => document.activeElement.blur());
  await p.keyboard.press('g');
  eq(await p.evaluate(() => window.__keys), ['g'], "keys: a key typed on the page itself, outside the panel, is the page's");
  // Esc from a field
  await openGear(p, 'levels');
  await p.locator('.pg-lv[data-pg-level=chunks] .pg-lvname').focus();
  await p.keyboard.press('Escape');
  eq([await isUp(p), await where(p)], [false, 'button'], 'Esc from a text field closes the panel and the keyboard goes back to the button');
  // and the keys that press the button are the button's own
  await p.evaluate(() => { window.__keys.length = 0; });
  await gearBtn(p).focus();
  await p.keyboard.press('Space');
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await p.evaluate(() => window.__keys), [], 'keys: Space on the gear button opens the panel and the page does not hear it (a reader would play)');
  await t.close();
});

await sec('phone', async () => {
  const H = 844;
  // the sheet's own numbers, read from the page
  const stageOf = p => p.evaluate(() => window.__gear.stage());
  const entryOf = p => p.evaluate(() => history.state && history.state.parsehGear);
  const hitsIndexRow = (p, id) => p.evaluate(id => {
    const r = document.querySelector(`.pg-irow[data-pg-index="${id}"]`), b = r.getBoundingClientRect();
    const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    return !!e && !!e.closest(`.pg-irow[data-pg-index="${id}"]`);
  }, id);
  const tapIndex = (p, id) => p.locator(`.pg-irow[data-pg-index="${id}"]`).tap();
  const shut = p => p.waitForSelector('.pg-panel', {state: 'hidden'});
  const openSheet = async p => { await gearBtn(p).tap(); await p.waitForSelector('.pg-panel:not([hidden])'); await sleep(250); };

  let t = await open('phone', 'book');
  let p = t.page;
  await p.evaluate(() => { window.__esc = []; window.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc.push(e.defaultPrevented); }); });
  await openSheet(p);
  eq(await panelOf(p).evaluate(e => [e.classList.contains('pg-sheet'), e.classList.contains('pg-popover')]), [true, false], 'phone: the panel is the sheet');
  const rs = await rect(p, '.pg-panel');
  assert(near(rs.b, H, 1) && near(rs.w, 390, 1) && rs.l <= 1, `phone: the sheet stands on the foot of the window, the whole width (bottom ${Math.round(rs.b)}, ${Math.round(rs.w)}px)`);
  assert(rs.h >= H * 0.45 && rs.h <= H * 0.65, `phone: it rests about half the window high (${Math.round(rs.h)} of ${H}px)`);
  // a point on the second paragraph of the page, which the sheet leaves in view
  const aim = await p.evaluate(() => { const r = document.querySelectorAll('.para')[1].getBoundingClientRect(); return {x: 195, y: Math.round(r.top + 20), sheet: document.querySelector('.pg-panel').getBoundingClientRect().top}; });
  const above = await p.evaluate(a => { const e = document.elementFromPoint(a.x, a.y); return {in: !!e.closest('.pg-panel'), para: !!e.closest('.para')}; }, aim);
  assert(aim.y < aim.sheet && !above.in && above.para, `phone: the page is visible above it, and is what a finger there reaches (y=${aim.y}, the sheet starts at ${Math.round(aim.sheet)})`);
  await p.touchscreen.tap(aim.x, aim.y);
  eq(await isUp(p), true, 'phone: a tap on the page above leaves it open (not modal)');
  eq(await p.evaluate(() => [getComputedStyle(document.documentElement).overflow, getComputedStyle(document.body).overflow, document.querySelectorAll('[class*=backdrop], [class*=dim]').length]), ['visible', 'visible', 0], 'phone: nothing dims or locks the page');

  /* ---- THE INDEX: the themes, each with what it is set to, all seven in view without a scroll ---- */
  eq([await stageOf(p), await panelOf(p).getAttribute('data-pg-stage')], ['index', 'index'], 'index: the sheet opens on the index');
  eq(await p.evaluate(() => [document.querySelector('.pg-title').textContent, document.querySelector('.pg-sub').textContent,
      document.querySelector('.pg-sub').getClientRects().length > 0, document.querySelector('.pg-back').getClientRects().length]),
     ['This page', 'Only for this page.', true, 0], 'index: the head says This page, with "Only for this page." as its subtitle, and no ‹');
  eq(await p.evaluate(() => document.querySelector('.pg-first').getClientRects().length), 0, 'index: the paragraph is not a row of the body any more');
  const idx = await p.evaluate(() => [...document.querySelectorAll('.pg-irow')].filter(r => r.getClientRects().length).map(r =>
    [r.getAttribute('data-pg-index'), r.querySelector('.pg-iname').textContent, r.querySelector('.pg-isum').textContent, r.getAttribute('aria-label'), r.tagName]));
  eq(idx.map(r => r[0]), ids.book, 'index: one row for each theme the page draws, in the spec\'s order');
  eq(idx.map(r => r[1]), ['Levels & reading', 'Listening', 'Looking a word up', 'Text', 'Zoom', 'Colours', 'Interface'], 'index: each says the theme\'s name');
  eq(idx.map(r => r[4]), Array(7).fill('BUTTON'), 'index: each row is a button');
  // THE SUMMARIES, by the default rule, kind by kind
  eq(idx[0][2], 'With vowels, Chunks, Plain · diacritics · glosses', 'summary: levels (the ticked names, joined) then the switches that are ON and have a short name');
  eq(idx[1][2], '1× · 10 s · 1.5 s · keeps going', 'summary: a choice says its chosen label, a slider its formatted value, a switch its short name');
  eq(idx[2][2], '', 'summary: nothing on, nothing said (a line of no words is not drawn)');
  eq(idx[3][2], '28px · 14px · 760px · 1.5', 'summary: a slider without format says its value and its unit; the action says nothing');
  eq(idx[4][2], '100 %', 'summary: the zoom stepper');
  eq(idx[5][2], 'Light', 'summary: the colour scheme chosen');
  eq(idx[6][2], 'Mobile pages', 'summary: the interface (the standard group names it)');
  eq(idx[1][3], 'Listening, 1× · 10 s · 1.5 s · keeps going', 'summary: a screen reader hears the row as its name and its summary');
  eq(idx[2][3], 'Looking a word up', 'summary: and as its name alone where there is no summary');
  eq(await p.evaluate(() => document.querySelector('[data-pg-index=lookup] .pg-isum').getClientRects().length), 0, 'summary: an empty one takes no line');
  // a summary follows the page: a switch pressed from outside, a slider moved
  await p.evaluate(() => { window.__st.dict = true; window.__st.gloss = false; window.__st.speed = 1.5; window.__emit('dict'); window.__emit('gloss'); window.__emit('speed'); });
  await until(() => p.evaluate(() => document.querySelector('[data-pg-index=lookup] .pg-isum').textContent === 'dictionary'), 'the summary follows a switch of the page');
  eq(await p.evaluate(() => [document.querySelector('[data-pg-index=levels] .pg-isum').textContent, document.querySelector('[data-pg-index=listening] .pg-isum').textContent]),
     ['With vowels, Chunks, Plain · diacritics', '1.5× · 10 s · 1.5 s · keeps going'], 'summary: and the others follow it, a switch that went off no longer named');
  await p.evaluate(() => { window.__st.dict = false; window.__st.gloss = true; window.__st.speed = 1; window.__emit('dict'); window.__emit('gloss'); window.__emit('speed'); });
  await until(() => p.evaluate(() => document.querySelector('[data-pg-index=lookup] .pg-isum').getClientRects().length === 0), 'and back');
  // sizes: seven rows in the half sheet, each a finger's target, each what a finger reaches at its centre
  const body = await rect(p, '.pg-body');
  const rows = await p.evaluate(() => [...document.querySelectorAll('.pg-irow')].filter(r => r.getClientRects().length).map(r => { const b = r.getBoundingClientRect(); return {id: r.getAttribute('data-pg-index'), t: b.top, b: b.bottom, h: b.height, w: b.width}; }));
  assert(rows.every(r => r.t >= body.t - 0.5 && r.b <= body.b + 0.5), `index: the seven rows are inside the body with no scrolling (${Math.round(rows[0].t - body.t)}..${Math.round(rows[6].b - body.t)} of ${Math.round(body.h)}px)`);
  assert(rows.every(r => near(r.h, 56, 0.6) && r.w >= 387), 'index: each row is 56px high and the whole width (two lines: a finger\'s target)');
  const hits = [];
  for (const r of rows) hits.push(await hitsIndexRow(p, r.id));
  eq(hits, Array(7).fill(true), 'index: each row is what a finger reaches at its centre (elementFromPoint)');
  eq(await p.evaluate(() => { const b = document.querySelector('.pg-body'); return b.scrollHeight - b.clientHeight; }) <= 1, true, 'index: the body itself does not scroll');
  // the grab line is a target of 48px, over the head's middle
  const gr = await rect(p, '.pg-grip');
  assert(near(gr.w, 48, 0.6) && near(gr.h, 48, 0.6), `phone: the grab line is a 48px square (${Math.round(gr.w)}x${Math.round(gr.h)})`);
  eq(await p.evaluate(() => { const g = document.querySelector('.pg-grip').getBoundingClientRect(); const e = document.elementFromPoint(g.left + g.width / 2, g.top + g.height / 2); return !!e.closest('.pg-grip'); }), true, 'phone: and what a finger reaches at its centre');
  eq(await p.evaluate(() => { const g = document.querySelector('.pg-gripline'); return g.getClientRects().length > 0; }), true, 'phone: the grab line is drawn');
  // ✕ is 48px and in the corner; the head is under 52px, so the rows have the room
  const xr = await rect(p, '.pg-x');
  assert(near(xr.w, 48, 0.6) && near(xr.h, 48, 0.6) && near(xr.r, rs.r, 2), `phone: ✕ is 48x48 at the right end of the head (${Math.round(xr.w)}x${Math.round(xr.h)})`);

  /* ---- A THEME: its group alone, ‹ and the caption in the head ---- */
  const hist1 = await p.evaluate(() => history.length), id1 = await entryOf(p);
  assert(typeof id1 === 'string' && id1.length > 0, 'history: the sheet pushed an entry of its own on opening');
  await tapIndex(p, 'listening');
  await until(async () => (await stageOf(p)) === 'listening', 'a tap on a row enters the theme');
  await sleep(260);
  eq(await panelOf(p).getAttribute('data-pg-stage'), 'listening', 'theme: data-pg-stage says which');
  eq(await p.evaluate(() => [document.querySelector('.pg-title').textContent, document.querySelector('.pg-sub').textContent,
      document.querySelector('.pg-title').getAttribute('aria-live')]),
     ['Listening', 'Follows you to your other devices.', 'polite'], 'theme: the head becomes the theme\'s name with its caption, and the title is a polite live region');
  eq(await p.evaluate(() => [...document.querySelectorAll('.pg-group')].filter(g => g.getClientRects().length).map(g => g.getAttribute('data-pg-group'))), ['listening'], 'theme: only that group is drawn');
  eq(await p.evaluate(() => ['.pg-gtitle', '.pg-caption'].map(s => document.querySelector('[data-pg-group=listening] ' + s).getClientRects().length)), [0, 0], "theme: the group's own title and caption are not drawn twice (the head says them)");
  const br = await rect(p, '.pg-back');
  assert(near(br.w, 48, 0.6) && near(br.h, 48, 0.6) && br.l <= 2, `theme: ‹ is 48x48 at the left end of the head (${Math.round(br.w)}x${Math.round(br.h)})`);
  eq(await p.evaluate(() => { const b = document.querySelector('.pg-back'); const r = b.getBoundingClientRect(); return [b.getAttribute('aria-label'), !!document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2).closest('.pg-back')]; }), ['Back to the list', true], 'theme: ‹ says where it goes and is what a finger reaches');
  eq(await p.evaluate(() => { const a = document.activeElement; return !!a.closest('[data-pg-group=listening]'); }), true, "theme: the keyboard's place is on the theme's first control");
  assert((await p.evaluate(() => history.length)) === hist1 + 1, 'history: entering a theme pushed a second entry');
  const id2 = await entryOf(p);
  assert(typeof id2 === 'string' && id2 !== id1, 'history: and it is its own');
  // every control of the theme is a finger's size, and what a finger reaches at its centre
  const small = await panelOf(p).evaluate(panel => {
    const out = [];
    panel.querySelectorAll('[data-pg-group=listening] button, [data-pg-group=listening] a[href], [data-pg-group=listening] select, [data-pg-group=listening] input, .pg-back, .pg-x').forEach(c => {
      if (!c.getClientRects().length) return;
      const t = c.type === 'checkbox' ? c.closest('label') : c;
      t.scrollIntoView({block: 'center'});
      const r = t.getBoundingClientRect();
      if (r.height < 47.5 || (c.type === 'checkbox' && r.width < 47.5)) { out.push((c.className || c.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); return; }
      const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (!e || !(c === e || c.contains(e) || t.contains(e))) out.push('unreachable ' + (c.className || c.tagName));
    });
    return out;
  });
  eq(small, [], 'theme: every control in view is 48px or more and is what a finger reaches at its centre');
  // ‹ goes back to the index: the row that was open is where the keyboard is, and the entry is given back
  await p.locator('.pg-back').tap();
  await until(async () => (await stageOf(p)) === 'index', '‹ returns to the index');
  eq(await p.evaluate(() => [document.activeElement.getAttribute('data-pg-index'), document.querySelector('.pg-title').textContent, document.querySelector('.pg-back').getClientRects().length]),
     ['listening', 'This page', 0], 'theme: ‹ returns to the index, the row that was open has the keyboard, the head is the page\'s again');
  await sleep(250);
  eq(await entryOf(p), id1, 'history: ‹ spent its own entry (the sheet\'s is the one left)');
  eq(await isUp(p), true, 'history: and the sheet is still up');
  // the back gesture from a theme returns to the index; from the index it closes
  await tapIndex(p, 'text');
  await until(async () => (await stageOf(p)) === 'text', 'the text theme');
  await p.goBack();
  await until(async () => (await stageOf(p)) === 'index', 'the back gesture returns to the index');
  eq([await isUp(p), await entryOf(p)], [true, id1], 'history: the back gesture from a theme leaves the theme and not the sheet');
  await p.goBack();
  await shut(p);
  eq(await p.evaluate(() => location.pathname), '/fx/book.html', 'history: the second gesture closes the sheet, and stays on the page');
  eq(await stageOf(p), null, 'stage(): null when it is shut');
  // ✕ from a theme closes the whole sheet and spends BOTH entries; the next sheet's back gesture still works
  await sleep(200);
  await openSheet(p);
  await tapIndex(p, 'zoom');
  await until(async () => (await stageOf(p)) === 'zoom', 'the zoom theme');
  await p.locator('.pg-x').tap();
  await shut(p);
  await sleep(300);
  eq(await p.evaluate(() => [location.pathname, history.state]), ['/fx/book.html', null], 'close: ✕ from a theme closes the whole sheet and spends both its entries');
  await openSheet(p);
  eq(await stageOf(p), 'index', 'close: the sheet opens on the index again, not where it was left');
  await p.goBack();
  await shut(p);
  eq(await p.evaluate(() => location.pathname), '/fx/book.html', 'close: and the back gesture after it still closes the next sheet (a spent entry is not heard as a gesture)');
  // the same for ‹ then ✕, and for ✕ from the index
  await sleep(200);
  await openSheet(p);
  await tapIndex(p, 'colours');
  await until(async () => (await stageOf(p)) === 'colours', 'the colours theme');
  await p.locator('.pg-back').tap();
  await until(async () => (await stageOf(p)) === 'index', 'back to the index');
  await sleep(250);
  await p.locator('.pg-x').tap();
  await shut(p);
  await sleep(300);
  eq(await p.evaluate(() => history.state), null, 'close: ‹ and then ✕ leave no entry behind');
  await openSheet(p);
  await p.goBack();
  await shut(p);
  eq(await p.evaluate(() => location.pathname), '/fx/book.html', 'close: and the next back gesture still works');
  // Esc closes the whole sheet from a theme, once, and the page does not hear it
  await sleep(200);
  await openSheet(p);
  await tapIndex(p, 'interface');
  await until(async () => (await stageOf(p)) === 'interface', 'the interface theme');
  await p.keyboard.press('Escape');
  await shut(p);
  eq(await p.evaluate(() => window.__esc), [], 'close: Esc closes the whole sheet from a theme (one key, one layer), and the page does not hear it');
  await sleep(300);
  eq(await p.evaluate(() => history.state), null, 'close: and spends both entries');
  await openSheet(p);
  await p.goBack();
  await shut(p);
  eq(await p.evaluate(() => location.pathname), '/fx/book.html', 'close: the gesture after Esc still closes the next sheet');
  // a swipe down on the head, from the index and from a theme
  for (const where of ['index', 'text']) {
    await sleep(200);
    await openSheet(p);
    if (where !== 'index') { await tapIndex(p, where); await until(async () => (await stageOf(p)) === where, 'the ' + where + ' theme'); await sleep(260); }
    const rh = await rect(p, '.pg-head');
    await p.mouse.move(120, rh.t + 30);
    await p.mouse.down();
    await p.mouse.move(120, rh.t + 50, {steps: 3});
    await p.mouse.up();
    await sleep(160);
    eq([await isUp(p), await panelOf(p).evaluate(e => e.style.transform)], [true, ''], `swipe: a short pull on the head springs back (${where})`);
    await p.mouse.move(120, rh.t + 30);
    await p.mouse.down();
    await p.mouse.move(120, rh.t + 230, {steps: 8});
    await p.mouse.up();
    await shut(p);
    assert(true, `swipe: a swipe down on the head closes the whole sheet (${where})`);
    await sleep(300);
    eq(await p.evaluate(() => history.state), null, 'swipe: and spends its entries');
  }

  /* ---- gear.open(group), stage(), back() ---- */
  await sleep(200);
  eq(await p.evaluate(() => [window.__gear.back(), window.__gear.stage()]), [false, null], 'api: back() and stage() on a shut sheet say nothing');
  await p.evaluate(() => window.__gear.open('text'));
  await p.waitForSelector('.pg-panel:not([hidden])');
  await sleep(260);
  eq(await stageOf(p), 'text', 'api: open("text") lands on the theme (what Aa does)');
  eq(await p.evaluate(() => { const a = document.activeElement; return [!!a.closest('[data-pg-group=text]'), a.classList.contains('pg-range')]; }), [true, true], 'api: with its first control focused');
  eq(await p.evaluate(() => [window.__gear.back(), window.__gear.stage()]), [true, 'index'], 'api: back() goes to the index underneath');
  eq(await p.evaluate(() => [window.__gear.back(), window.__gear.stage()]), [false, 'index'], 'api: and does nothing on the index');
  await p.evaluate(() => window.__gear.open());
  eq(await stageOf(p), 'index', 'api: open() with no group leaves the stage as it is');
  await p.evaluate(() => window.__gear.open('zoom'));
  await p.evaluate(() => window.__gear.open());
  eq(await stageOf(p), 'zoom', 'api: open() on a sheet that is up leaves the theme on stage');
  await p.evaluate(() => window.__gear.open('colours'));
  eq([await stageOf(p), (await p.evaluate(() => history.length)) - hist1], ['colours', 1], 'api: from one theme to another there is still the one extra entry');
  await p.evaluate(() => window.__gear.open('nonesuch'));
  eq(await stageOf(p), 'colours', 'api: a group that is not there leaves it where it is');
  await p.keyboard.press('Escape');
  await shut(p);
  await sleep(300);

  /* ---- keys ---- */
  await openSheet(p);
  await p.keyboard.press('Tab');
  eq(await p.evaluate(() => document.activeElement.getAttribute('data-pg-index')), 'levels', 'keys: Tab from the sheet goes to the first row of the index');
  await p.keyboard.press('Tab');
  eq(await p.evaluate(() => document.activeElement.getAttribute('data-pg-index')), 'listening', 'keys: and through the rows');
  await p.keyboard.press('Enter');
  await until(async () => (await stageOf(p)) === 'listening', 'Enter opens the row');
  assert(true, 'keys: Enter on a row of the index opens the theme');
  await p.keyboard.press('Shift+Tab');
  eq(await p.evaluate(() => document.activeElement.className), 'pg-back', 'keys: in a theme, Shift+Tab from the first control reaches ‹');
  await p.keyboard.press('Enter');
  await until(async () => (await stageOf(p)) === 'index', 'Enter on ‹');
  eq(await p.evaluate(() => document.activeElement.getAttribute('data-pg-index')), 'listening', 'keys: Enter on ‹ goes back, to the row that was open');
  await p.keyboard.press('Space');
  await until(async () => (await stageOf(p)) === 'listening', 'Space opens a row');
  assert(true, 'keys: Space opens a row too');
  await p.keyboard.press('Escape');
  await shut(p);
  await sleep(300);
  await openSheet(p);
  await tapIndex(p, 'colours');
  await until(async () => (await stageOf(p)) === 'colours', 'colours');
  await p.keyboard.press('Tab');
  eq(await p.evaluate(() => document.activeElement.className), 'pg-x', 'keys: in a theme Tab goes ‹, the rows, ✕ (✕ is last)');
  await p.keyboard.press('Escape');
  await shut(p);
  await sleep(300);

  /* ---- THE TWO HEIGHTS ---- */
  eq(await p.evaluate(() => localStorage.getItem('parseh_gear_tall')), null, 'height: half is the resting height (nothing stored)');
  await openSheet(p);
  const half = await rect(p, '.pg-panel');
  // a drag on the head; `pause` (ms between the moves) makes it slow, which is not a flick
  const dragHead = async (dy, steps = 8, y = 30, pause = 0) => {
    const rh = await rect(p, '.pg-head');
    await p.mouse.move(100, rh.t + y);
    await p.mouse.down();
    for (let i = 1; i <= steps; i++) { await p.mouse.move(100, rh.t + y + dy * i / steps); if (pause) await sleep(pause); }
    await p.mouse.up();
    await sleep(320);
  };
  await dragHead(-40, 4, 30, 90);
  eq([await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), await p.evaluate(() => localStorage.getItem('parseh_gear_tall'))], [false, null], 'height: a drag up of less than a third of the way springs back to half');
  assert(near((await rect(p, '.pg-panel')).h, half.h, 2), 'height: and the sheet is as it was');
  await dragHead(-200);
  eq([await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), await p.evaluate(() => localStorage.getItem('parseh_gear_tall'))], [true, '1'], 'height: a drag up past a third of the way makes it tall, and the choice is remembered');
  const tallR = await rect(p, '.pg-panel');
  assert(near(tallR.h, H - 48, 2) && near(tallR.t, 48, 2) && near(tallR.b, H, 1), `height: tall is the window less 48px (${Math.round(tallR.h)} of ${H}px, top at ${Math.round(tallR.t)})`);
  assert(await p.evaluate(() => { const r = document.querySelector('.para').getBoundingClientRect(); return r.top < 48 + 1 || true; }), 'height: ...');
  await dragHead(60, 4, 30, 90);
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), true, 'height: a drag down from tall of less than a third stays tall');
  await dragHead(200);
  eq([await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), await p.evaluate(() => localStorage.getItem('parseh_gear_tall')), await isUp(p)], [false, null, true], 'height: a drag down from tall past a third brings it to half (it does not close), and that is remembered');
  assert(near((await rect(p, '.pg-panel')).h, half.h, 2), 'height: half again');
  // a flick does the same from less
  await dragHead(-90, 2);
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), true, 'height: a flick up makes it tall');
  await dragHead(90, 2);
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), false, 'height: a flick down from tall brings it to half');
  // a tap on the grab line toggles, from the index and from a theme (and is not a drag)
  await p.locator('.pg-grip').tap();
  await sleep(320);
  eq([await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), await p.evaluate(() => localStorage.getItem('parseh_gear_tall'))], [true, '1'], 'height: a tap on the grab line makes it tall');
  await tapIndex(p, 'text');
  await until(async () => (await stageOf(p)) === 'text', 'text');
  await sleep(260);
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), true, 'height: the detent is the same on a theme');
  // the index at tall simply has room
  await p.locator('.pg-back').tap();
  await until(async () => (await stageOf(p)) === 'index', 'index');
  await sleep(300);
  const bodyT = await rect(p, '.pg-body');
  const rowsT = await p.evaluate(() => [...document.querySelectorAll('.pg-irow')].filter(r => r.getClientRects().length).map(r => r.getBoundingClientRect().bottom));
  assert(rowsT.length === 7 && rowsT[6] < bodyT.b - 40, `height: the index at tall has room under the rows (${Math.round(bodyT.b - rowsT[6])}px)`);
  const footT = await p.evaluate(() => { const f = document.querySelector('.pg-footlink'), b = f.getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return [f.getAttribute('href'), !!e.closest('.pg-footlink')]; });
  eq(footT, ['/settings/', true], 'height: and the foot link to the settings of Parseh closes the list, where a finger reaches it');
  // remembered across a reload, for the next sheet, the next page
  await p.keyboard.press('Escape');
  await shut(p);
  await p.reload();
  await p.waitForFunction(() => window.__ready === true);
  await openSheet(p);
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), true, 'height: after a reload the sheet opens tall (parseh_gear_tall, on this device)');
  assert(near((await rect(p, '.pg-panel')).h, H - 48, 2), 'height: and is tall');
  await p.locator('.pg-grip').tap();
  await sleep(320);
  eq([await panelOf(p).evaluate(e => e.classList.contains('pg-tall')), await p.evaluate(() => localStorage.getItem('parseh_gear_tall'))], [false, null], 'height: a tap on the grab line again makes it half, and forgets it');
  // the window changing under a sheet that is tall: the detent stays
  await p.locator('.pg-grip').tap();
  await sleep(320);
  await p.setViewportSize({width: 390, height: 640});
  await sleep(300);
  assert(near((await rect(p, '.pg-panel')).h, 640 - 48, 3), 'height: a window that changes height (a phone\'s keyboard) stands the sheet again, in the detent in force');
  await p.setViewportSize({width: 390, height: 844});
  await p.locator('.pg-grip').tap();
  await sleep(320);
  await p.keyboard.press('Escape');
  await shut(p);
  await t.close();

  // the 360x740 phone: the same seven themes in the half sheet, squeezed to 50px so that they fit
  t = await open('phone', 'book', {width: 360, height: 740});
  p = t.page;
  await openSheet(p);
  const body2 = await rect(p, '.pg-body'), rs2 = await rect(p, '.pg-panel');
  const rows2 = await p.evaluate(() => [...document.querySelectorAll('.pg-irow')].filter(r => r.getClientRects().length).map(r => { const b = r.getBoundingClientRect(); return {id: r.getAttribute('data-pg-index'), t: b.top, b: b.bottom, h: b.height}; }));
  assert(rows2.length === 7 && rows2.every(r => r.t >= body2.t - 0.5 && r.b <= body2.b + 0.5), `index 360x740: the seven rows are inside the half sheet (${Math.round(rs2.h)}px) with no scrolling (${Math.round(rows2[6].b - body2.t)} of ${Math.round(body2.h)}px)`);
  assert(rows2.every(r => r.h >= 49.5), `index 360x740: none under 50px (${Math.round(rows2[0].h)}px)`);
  const hits2 = [];
  for (const r of rows2) hits2.push(await hitsIndexRow(p, r.id));
  eq(hits2, Array(7).fill(true), 'index 360x740: each row is what a finger reaches at its centre');
  await t.close();

  // a page with eight themes (the Keeping group of the phone): at 390x844 they are squeezed to 50px and still need no scroll
  t = await open('phone', 'book', {query: 'node=1'});
  p = t.page;
  await openSheet(p);
  const body3 = await rect(p, '.pg-body');
  const rows3 = await p.evaluate(() => [...document.querySelectorAll('.pg-irow')].filter(r => r.getClientRects().length).map(r => { const b = r.getBoundingClientRect(); return {t: b.top, b: b.bottom, h: b.height}; }));
  assert(rows3.length === 8 && rows3.every(r => r.t >= body3.t - 0.5 && r.b <= body3.b + 0.5 && r.h >= 49.5), `index: eight themes still fit at 390x844, squeezed to 50px (${Math.round(rows3[7].b - body3.t)} of ${Math.round(body3.h)}px)`);

  /* ---- A NODE (lib/keep.js's buttons) stands in its row only while its theme is on stage ---- */
  const nodeAt = p => p.evaluate(() => ['keep1', 'keep2'].map(id => { const e = document.getElementById(id); return e.parentElement.classList.contains('pg-node') ? 'row' : e.parentElement.id || e.parentElement.tagName; }));
  eq(await nodeAt(p), ['menu', 'menu'], 'node: on the index the buttons are on the page, where they were');
  await tapIndex(p, 'keep');
  await until(async () => (await stageOf(p)) === 'keep', 'the keeping theme');
  eq(await nodeAt(p), ['row', 'row'], 'node: with its theme on stage they stand in their row');
  await sleep(260);
  eq(await p.evaluate(() => { const b = document.getElementById('keep1').getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return e === document.getElementById('keep1'); }), true, 'node: and are what a finger reaches');
  await p.locator('.pg-back').tap();
  await until(async () => (await stageOf(p)) === 'index', 'index');
  eq(await nodeAt(p), ['menu', 'menu'], 'node: ‹ sends them home');
  eq(await p.evaluate(() => [...document.getElementById('menu').children].map(e => e.id)), ['keep1', 'keep2', 'after'], 'node: to the same place among their neighbours');
  await tapIndex(p, 'text');
  await until(async () => (await stageOf(p)) === 'text', 'text');
  eq(await nodeAt(p), ['menu', 'menu'], 'node: while another theme is on stage they are on the page');
  await p.evaluate(() => window.__gear.open('keep'));
  eq(await nodeAt(p), ['row', 'row'], 'node: from one theme to another they come in');
  await p.evaluate(() => window.__gear.back());
  eq(await nodeAt(p), ['menu', 'menu'], 'node: and go home again');
  await p.evaluate(() => window.__gear.open('keep'));
  await p.evaluate(() => window.__gear.back());
  await p.evaluate(() => window.__gear.open('keep'));
  eq(await nodeAt(p), ['row', 'row'], 'node: entered twice over they are in the row once');
  await p.evaluate(() => { window.__noKeep1 = true; window.__gear.refresh(); });
  eq(await nodeAt(p), ['menu', 'row'], 'node: a row that stops being drawn sends its own button home (the other row keeps its)');
  await p.evaluate(() => { window.__noKeep1 = false; window.__gear.refresh(); });
  eq(await nodeAt(p), ['row', 'row'], 'node: and takes it in again');
  await p.keyboard.press('Escape');
  await shut(p);
  eq(await nodeAt(p), ['menu', 'menu'], 'node: the sheet shut, they are home');
  await t.close();

  /* ---- a summary the page says itself wins; names that read right to left are wrapped ---- */
  t = await open('phone', 'book', {query: 'sum=1'});
  p = t.page;
  await openSheet(p);
  const said = await p.evaluate(() => ['summed', 'said', 'quiet'].map(id => { const s = document.querySelector(`[data-pg-index=${id}] .pg-isum`); return [s.textContent, s.getClientRects().length > 0, [...s.querySelectorAll('bdi')].map(b => b.textContent), document.querySelector(`[data-pg-index=${id}]`).getAttribute('aria-label')]; }));
  eq(said[0].slice(0, 3), ['فارسی ساده, Chunks · no glosses', true, ['فارسی ساده', 'Chunks']], 'summary: a group\'s own summary (a function of parts) is the summary, and its names are in <bdi>');
  eq(said[0][3], 'Said by the page, فارسی ساده, Chunks · no glosses', 'summary: and what a screen reader hears');
  eq(said[1].slice(0, 3), ["In the page's own words", true, []], 'summary: a string is the summary');
  eq(said[2].slice(0, 2), ['', false], 'summary: an empty summary draws nothing, whatever the rows would say');
  const lv = await p.evaluate(() => [...document.querySelectorAll('[data-pg-index=levels] .pg-isum bdi')].map(b => b.textContent));
  eq(lv, ['With vowels', 'Chunks', 'Plain'], 'summary: the levels row\'s names are each in a <bdi> (a level\'s name may be in any script)');
  eq(await p.evaluate(() => { const s = document.querySelector('.pg-isum'); const c = getComputedStyle(s); return [c.direction, document.querySelector('.pg-panel').getAttribute('dir'), c.whiteSpace, c.textOverflow]; }), ['ltr', 'ltr', 'nowrap', 'ellipsis'], 'summary: the line is chrome (left to right) cut with an ellipsis where it does not fit');
  await p.evaluate(() => { window.__st.levels.vocal.name = 'A name far too long for one line of the sheet'; window.__st.levels.alt.shown = true; window.__emit('levels'); });
  await until(() => p.evaluate(() => document.querySelector('[data-pg-index=levels] .pg-isum').textContent.includes('far too long')), 'the long name is in the summary');
  eq(await p.evaluate(() => { const r = document.querySelector('[data-pg-index=levels]'), s = r.querySelector('.pg-isum'); return [s.scrollWidth > s.clientWidth ? 'cut' : 'whole', Math.round(r.getBoundingClientRect().height)]; }), ['cut', 56], 'summary: a line too long for the row is cut, not wrapped (the row stays two lines, 56px)');
  await p.keyboard.press('Escape');
  await shut(p);
  await t.close();

  /* ---- the popover is not touched: no index, one list, the old head ---- */
  t = await open('wide', 'book');
  p = t.page;
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await p.evaluate(() => [window.__gear.stage(), document.querySelector('.pg-index').getClientRects().length, document.querySelector('.pg-back').getClientRects().length,
      document.querySelector('.pg-grip').getClientRects().length, document.querySelector('.pg-sub').getClientRects().length, document.querySelector('.pg-first').getClientRects().length > 0,
      [...document.querySelectorAll('.pg-group')].filter(g => g.getClientRects().length).length, document.querySelector('.pg-x').parentElement.className]),
     [null, 0, 0, 0, 0, true, 7, 'pg-head'], 'popover: no stage, no index, no ‹, no grab line; the one list of every group, "Only for this page." in the body, ✕ in the head');
  await p.evaluate(() => window.__gear.open('text'));
  eq(await p.evaluate(() => { const g = document.querySelector('[data-pg-group=text]').getBoundingClientRect(), b = document.querySelector('.pg-body').getBoundingClientRect(); return g.top - b.top < 20 && g.top >= b.top - 1; }), true, 'popover: open(group) scrolls to the group, as it did');
  await t.close();

  /* ---- the sheet follows the layout ---- */
  t = await open('phone', 'book');
  p = t.page;
  await openSheet(p);
  await tapIndex(p, 'interface');
  await until(async () => (await stageOf(p)) === 'interface', 'the interface theme');
  await chipsOf(p, 'mode').filter({hasText: 'Browser'}).tap();
  await until(async () => (await rect(p, '#bhost [data-parseh-gear]')) !== null, 'the button goes to the browser bar');
  eq(await panelOf(p).evaluate(e => [e.hidden, e.classList.contains('pg-sheet')]), [false, true], 'phone: switched to the browser layout the panel stays up, still the sheet, still on its theme (a window of 390px)');
  eq(await stageOf(p), 'interface', 'phone: and on the same stage');
  eq(await pressed(p, 'mode'), ['Browser'], 'phone: and says which is in force');
  await chipsOf(p, 'mode').filter({hasText: 'Mobile'}).tap();
  await until(async () => (await rect(p, '#mhost [data-parseh-gear]')) !== null, 'and back to the mobile bar');
  eq(await pressed(p, 'mode'), ['Mobile'], 'phone: and back in the mobile layout it says so');
  await p.locator('.pg-back').tap();
  await until(async () => (await stageOf(p)) === 'index', 'index');
  await sleep(200);
  eq(await p.evaluate(() => document.querySelector('[data-pg-index=interface] .pg-isum').textContent), 'Mobile pages', 'phone: and the index says it');
  await t.close();

  // a sheet becoming the popover with a theme up: both entries spent, the popover scrolled to the group; and back
  t = await open('wide', 'book', {width: 540, height: 800});
  p = t.page;
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-sheet')), true, 'resize: 540px is the sheet');
  await p.locator('.pg-irow[data-pg-index=text]').click();
  await until(async () => (await stageOf(p)) === 'text', 'text');
  await sleep(260);
  const histR = await p.evaluate(() => history.length);
  await p.setViewportSize({width: 700, height: 800});
  await until(() => panelOf(p).evaluate(e => e.classList.contains('pg-popover')), 'the window grows into a popover');
  await sleep(400);
  eq([await stageOf(p), await isUp(p), await p.evaluate(() => history.state)], [null, true, null], 'resize: the sheet became the popover with a theme up: no stage, still up, both entries given back');
  eq(await p.evaluate(() => { const g = document.querySelector('[data-pg-group=text]').getBoundingClientRect(), b = document.querySelector('.pg-body').getBoundingClientRect(); return g.top - b.top < 20 && g.top >= b.top - 1; }), true, 'resize: its one list is scrolled to the group that was on stage');
  assert(histR >= 1, 'resize: ...');
  await p.setViewportSize({width: 540, height: 800});
  await until(() => panelOf(p).evaluate(e => e.classList.contains('pg-sheet')), 'and back into a sheet');
  await sleep(300);
  eq([await stageOf(p), typeof (await entryOf(p))], ['index', 'string'], 'resize: and into a sheet again, on the index, with its entry');
  await p.goBack();
  await shut(p);
  eq(await p.evaluate(() => location.pathname), '/fx/book.html', 'resize: whose back gesture closes it');
  await t.close();

  // landscape: a short window keeps a floor under the sheet, and tall is the window less 48px
  t = await open('phone', 'book', {width: 844, height: 390});
  p = t.page;
  await openSheet(p);
  const rl = await rect(p, '.pg-panel');
  assert(rl.h >= 239 && rl.h <= 390 - 47 && near(rl.b, 390, 1), `landscape: the sheet is 240px or half, whichever is more, and leaves room above (${Math.round(rl.h)}px of 390)`);
  assert(rl.w <= 561 && rl.w >= 559 && near(rl.l + rl.w / 2, 422, 2), `landscape: 560px wide, in the middle (${Math.round(rl.w)}px)`);
  await p.locator('.pg-grip').tap();
  await sleep(320);
  const rlt = await rect(p, '.pg-panel');
  assert(near(rlt.h, 390 - 48, 2) && rlt.h > rl.h, `landscape: tall is the window less 48px (${Math.round(rlt.h)}px of 390)`);
  await p.locator('.pg-grip').tap();
  await sleep(320);
  await t.close();
  // the mobile layout on a wide screen is the sheet too
  t = await open('wide', 'book', {mode: 'mobile'});
  p = t.page;
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await panelOf(p).evaluate(e => e.classList.contains('pg-sheet')), true, 'the mobile layout at 1280px: the sheet');
  await t.close();
  // a browser layout under 560px is the sheet; over it, the popover
  for (const [w, sheet] of [[559, true], [561, false]]) {
    t = await open('wide', 'book', {width: w, height: 800});
    await gearBtn(t.page).click();
    await t.page.waitForSelector('.pg-panel:not([hidden])');
    eq(await panelOf(t.page).evaluate(e => e.classList.contains('pg-sheet')), sheet, `the browser layout at ${w}px: ${sheet ? 'the sheet' : 'the popover'} (560px is the line)`);
    if (!sheet) {
      const r = await rect(t.page, '.pg-panel');
      assert(r.l >= 0 && r.r <= w && r.w <= w - 15, `the popover at ${w}px fits (${Math.round(r.l)}..${Math.round(r.r)})`);
    }
    await t.close();
  }
});

await sec('widths', async () => {
  for (const w of [320, 360, 390, 430]) {
    const t = await open('phone', 'book', {width: w, height: 800, query: 'long=1&stubzoom=1'});
    const p = t.page;
    await gearBtn(p).tap();
    await p.waitForSelector('.pg-panel:not([hidden])');
    await p.evaluate(() => { window.__st.hover = true; window.__gear.refresh(); });
    const bad = [];
    for (const g of [...ids.book, 'long']) {
      await openGear(p, g);
      bad.push(...await panelOf(p).evaluate((panel, g) => {
        // on the sheet the pane on stage is what scrolls; on the popover the body
        const out = [], pr = panel.getBoundingClientRect(), body = panel.querySelector('.pg-pane-on') && panel.classList.contains('pg-sheet') ? panel.querySelector('.pg-pane-on') : panel.querySelector('.pg-body');
        if (pr.left < -0.5 || pr.right > innerWidth + 0.5) out.push(g + ': the panel is off the window ' + Math.round(pr.left) + '..' + Math.round(pr.right));
        if (body.scrollWidth > body.clientWidth + 0.5) out.push(g + ': the body scrolls sideways ' + body.scrollWidth + '>' + body.clientWidth);
        body.querySelectorAll('*').forEach(e => {
          if (!e.getClientRects().length) return;
          const r = e.getBoundingClientRect();
          if (r.width && (r.right > pr.right + 0.5 || r.left < pr.left - 0.5)) out.push(g + ': ' + (e.className || e.tagName) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
        });
        return out;
      }, g));
    }
    eq(bad.slice(0, 6), [], `${w}px: nothing of the panel goes past its sides, in any group, with names far too long`);
    const page = await p.evaluate(() => ({sw: document.documentElement.scrollWidth, iw: innerWidth, sx: scrollX, btn: document.querySelector('[data-parseh-gear]').getBoundingClientRect().right}));
    assert(page.sw <= page.iw && page.sx === 0 && page.btn <= page.iw, `${w}px: the page does not scroll sideways and the button is inside it (${page.sw} <= ${page.iw})`);
    // the long names wrap in their line; the boxes are as wide as the line
    await openGear(p, 'long');
    const ln = await p.evaluate(() => {
      const r = document.querySelector('[data-pg-row=staticlevels]'), l = r.querySelector('.pg-lvlabel');
      const f = document.querySelector('[data-pg-row=longlevels] .pg-lvname');
      return {wrapped: l.getBoundingClientRect().height > parseFloat(getComputedStyle(l).lineHeight) * 1.5, boxw: f.getBoundingClientRect().width,
              lineh: document.querySelector('[data-pg-row=longlevels] .pg-lv').getBoundingClientRect().height};
    });
    assert(ln.wrapped, `${w}px: a name too long for the line wraps onto the next, whole`);
    assert(ln.boxw > 100, `${w}px: a name box keeps a usable width (${Math.round(ln.boxw)}px)`);
    await t.close();
  }
  // the popover, with the same names, in a window of its own width
  const t = await open('wide', 'book', {query: 'long=1'});
  await openGear(t.page, 'long');
  const pr = await rect(t.page, '.pg-panel');
  assert(pr.l >= 0 && pr.r <= 1280 && pr.b <= 800, 'the popover with the long names stays in the window');
  const over = await panelOf(t.page).evaluate(panel => { const b = panel.querySelector('.pg-body'); return b.scrollWidth - b.clientWidth; });
  assert(over <= 0, 'and does not scroll sideways');
  await t.close();
});

/* The A, AA and large-text rules, from computed styles: the colour of the text, over the colours behind it, in the page's
   own palette.  A colour is read through a canvas, so that whatever the browser answers (rgb(), color(srgb ...)) is numbers. */
const CONTRAST = `(function () {
  var cv = document.createElement('canvas'); cv.width = cv.height = 1;
  var cx = cv.getContext('2d', {willReadFrequently: true});
  function rgba(c) { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); var d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; }
  function lum(c) { var a = c.slice(0, 3).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]; }
  function ratio(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function back(el) {
    var layers = [], n = el;
    while (n && n.nodeType === 1) { var c = rgba(getComputedStyle(n).backgroundColor); if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } n = n.parentElement; }
    var base = [255, 255, 255];
    for (var i = layers.length - 1; i >= 0; i--) { var l = layers[i]; base = [0, 1, 2].map(function (k) { return l[k] * l[3] + base[k] * (1 - l[3]); }); }
    return base;
  }
  window.__contrast = function (el) {
    var cs = getComputedStyle(el), fg = rgba(cs.color), bg = back(el);
    var f = [0, 1, 2].map(function (k) { return fg[k] * fg[3] + bg[k] * (1 - fg[3]); });
    return ratio(f, bg);
  };
  window.__edge = function (el, prop, over) { var cs = getComputedStyle(el), c = rgba(cs[prop]); return ratio(c, back(over || el)); };
})();`;

await sec('contrast', async () => {
  const TEXTS = ['.pg-title', '.pg-first', '.pg-gtitle', '.pg-caption', '.pg-name', '.pg-help', '.pg-kept', '.pg-lvhelp', '.pg-lvlabel',
                 '.pg-why', '.pg-note', '.pg-opthelp', '.pg-footlink', '.pg-link', '.pg-out', '.pg-stepval', '.pg-lvname', '.pg-select',
                 '.pg-chip', '.pg-btn', '.pg-x', '.pg-gear'];
  const worst = {};
  for (const fixture of ['book', 'doc']) {
    for (const kind of ['wide', 'phone']) {
      for (const theme of THEMES) {
        const {page: p, close} = await open(kind, fixture, {theme, query: (fixture === 'book' ? 'long=1&' : 'extra=1&') + 'stubzoom=1'});
        await p.evaluate(CONTRAST);
        await openGear(p);
        if (fixture === 'book') await p.evaluate(() => { window.__st.hover = true; window.__st.dict = false; window.__gear.refresh(); });
        // every group is looked at where it is visible, because a hidden element has no colours worth reading
        const bad = [];
        let min = 99;
        for (const g of await p.evaluate(() => [...document.querySelectorAll('.pg-group')].filter(e => !e.hidden).map(e => e.getAttribute('data-pg-group')))) {
          await openGear(p, g);
          const r = await p.evaluate(sels => {
            const out = [];
            sels.forEach(s => document.querySelectorAll(s).forEach(e => {
              const txt = (e.tagName === 'INPUT' ? e.value : e.textContent).trim();
              if (!e.getClientRects().length || !txt) return;
              const cs = getComputedStyle(e), px = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
              const need = px >= 24 || (px >= 18.66 && bold) ? 3 : 4.5;
              out.push({s, v: window.__contrast(e), need, t: txt.slice(0, 24), on: e.getAttribute('aria-checked') || e.getAttribute('aria-pressed') || (e.getAttribute('aria-expanded') === 'true' ? 'open' : '')});
            }));
            return out;
          }, TEXTS);
          for (const x of r) { min = Math.min(min, x.v); if (x.v < x.need) bad.push(`${x.s} "${x.t}" ${x.on} ${x.v.toFixed(2)}`); }
        }
        eq([...new Set(bad)].slice(0, 5), [], `${fixture}/${kind}/${theme}: every text of the panel keeps AA (lowest ${min.toFixed(2)}:1)`);
        worst[`${fixture}/${theme}`] = Math.min(worst[`${fixture}/${theme}`] || 99, min);
        // the edges of controls: 3:1 against what is behind them
        const edges = await p.evaluate(() => {
          const out = [], panel = document.querySelector('.pg-panel');
          const tr = document.querySelector('.pg-track');
          if (tr) out.push(['switch track', window.__edge(tr, 'borderTopColor', panel)]);
          const ch = document.querySelector('.pg-chip');
          if (ch) out.push(['chip edge', window.__edge(ch, 'borderTopColor', panel)]);
          return out;
        });
        for (const [what, v] of edges) assert(v >= 3, `${fixture}/${kind}/${theme}: the ${what} is ${v.toFixed(2)}:1 against the panel (3:1)`);
        await close();
      }
    }
  }
  console.log('  lowest text contrast by fixture and theme:', JSON.stringify(Object.fromEntries(Object.entries(worst).map(([k, v]) => [k, +v.toFixed(2)]))));
});

await sec('std', async () => {
  // COLOURS, with Parseh there (a reader)
  let t = await open('wide', 'book');
  let p = t.page;
  await openGear(p, 'colours');
  eq(await panelOf(p).evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(255, 255, 255)', 'colours: the panel is the light palette\'s card');
  eq(await rowOf(p, 'theme').locator('.pg-name').textContent(), 'Colour scheme', 'colours: a name');
  eq(await rowOf(p, 'theme').locator('.pg-help').textContent(), "The colours of every Parseh page. 'Follow my device' uses your phone's or computer's own light or dark setting.", 'colours: the sentence of the plan');
  eq(await groupOf(p, 'colours').locator('.pg-caption').textContent(), 'Follows you to your other devices.', 'colours: where it is kept');
  eq(await rowOf(p, 'theme').locator('.pg-chip').allTextContents(), ['Follow my device', 'Light', 'Dark', 'Sepia'], 'colours: Follow my device, Light, Dark, Sepia');
  eq(await rowOf(p, 'theme').locator('[role=radiogroup]').count(), 1, 'colours: a radiogroup');
  await chipsOf(p, 'theme').filter({hasText: 'Dark'}).click();
  eq([await store(p, 'parseh_theme'), await attrOf(p, 'html', 'data-theme'), await checked(p, 'theme')], ['dark', 'dark', ['Dark']], 'colours: Dark writes parseh_theme and <html data-theme> (through Parseh.theme)');
  eq(await panelOf(p).evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(33, 26, 29)', 'colours: and the panel is dressed in it at once');
  await chipsOf(p, 'theme').filter({hasText: 'Sepia'}).click();
  eq([await store(p, 'parseh_theme'), await attrOf(p, 'html', 'data-theme')], ['sepia', 'sepia'], 'colours: Sepia');
  eq(await panelOf(p).evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(248, 243, 230)', 'colours: the sepia paper');
  await chipsOf(p, 'theme').filter({hasText: 'Follow my device'}).click();
  eq([await store(p, 'parseh_theme'), await attrOf(p, 'html', 'data-theme')], ['auto', null], "colours: Follow my device is 'auto' and takes the attribute off");
  await p.evaluate(() => Parseh.theme.set('dark'));
  await until(async () => (await checked(p, 'theme')).join() === 'Dark', "colours: a change made elsewhere (the page's own ◐) reaches the row through watch");
  await p.evaluate(() => { localStorage.setItem('parseh_theme', 'light'); window.dispatchEvent(new StorageEvent('storage', {key: 'parseh_theme', newValue: 'light'})); Parseh.theme.apply(); });
  await until(async () => (await checked(p, 'theme')).join() === 'Light', 'colours: and one made in another tab');
  // INTERFACE, with Parseh
  await openGear(p, 'interface');
  eq(await groupOf(p, 'interface').locator('.pg-caption').textContent(), 'Saved on this device.', 'interface: where it is kept');
  eq(await rowOf(p, 'mode').locator('.pg-help').textContent(), 'Browser: every page, with everything that edits. Mobile: pages made for a phone, to read and to study, with nothing that edits.', 'interface: the sentence of the plan');
  eq(await rowOf(p, 'mode').locator('.pg-chip').allTextContents(), ['Browser', 'Mobile'], 'interface: Browser | Mobile');
  eq(await rowOf(p, 'mode').locator('.pg-chip').evaluateAll(a => a.map(c => c.getAttribute('aria-pressed'))), ['true', 'false'], 'interface: the layout in force is the pressed one');
  await chipsOf(p, 'mode').filter({hasText: 'Mobile'}).click();
  eq([await store(p, 'parseh_mode'), await attrOf(p, 'html', 'data-mode'), await p.evaluate(() => /parseh_mode=mobile/.test(document.cookie))], ['mobile', 'mobile', true], 'interface: Mobile writes parseh_mode, <html data-mode> and the cookie (through Parseh.mode)');
  await until(async () => (await rect(p, '#mhost [data-parseh-gear]')) !== null, 'interface: the button moves to the mobile bar');
  eq([await isUp(p), await panelOf(p).evaluate(e => e.classList.contains('pg-sheet'))], [true, true], 'interface: the open panel becomes the phone\'s sheet, still open');
  await openGear(p, 'interface');
  eq(await rowOf(p, 'mode').locator('.pg-chip').evaluateAll(a => a.map(c => c.getAttribute('aria-pressed'))), ['false', 'true'], 'interface: and says Mobile is in force');
  await chipsOf(p, 'mode').filter({hasText: 'Browser'}).click();
  eq([await store(p, 'parseh_mode'), await attrOf(p, 'html', 'data-mode')], ['browser', 'browser'], 'interface: Browser takes it back');
  await until(async () => (await rect(p, '#bhost [data-parseh-gear]')) !== null, 'interface: and the button returns to the browser bar');
  await until(() => p.evaluate(() => !document.querySelector('.pg-panel').classList.contains('pg-sheet')), 'interface: the sheet is a popover again');
  // the history entry the sheet pushed on the way is spent when it stops being a sheet
  eq(await p.evaluate(() => history.state), null, 'interface: the sheet\'s history entry is spent when the sheet stops being one');
  await t.close();

  // THE DOCUMENT: no Parseh at all
  t = await open('wide', 'doc');
  p = t.page;
  eq(await p.evaluate(() => typeof window.Parseh), 'undefined', 'doc: there is no Parseh here');
  await openGear(p, 'colours');
  eq(await checked(p, 'theme'), ['Light'], 'doc colours: reads the stored theme');
  await chipsOf(p, 'theme').filter({hasText: 'Dark'}).click();
  eq([await store(p, 'parseh_theme'), await attrOf(p, 'html', 'data-theme'), await p.evaluate(() => window.__applied.slice(-1)[0]), await attrOf(p, 'body', 'data-theme')], ['dark', 'dark', 'dark', 'dark'], "doc colours: writes parseh_theme and <html data-theme> itself and hands the page's own apply(t) the theme");
  eq(await panelOf(p).evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(33, 26, 29)', "doc colours: the studio's own dark card");
  await chipsOf(p, 'theme').filter({hasText: 'Sepia'}).click();
  eq(await panelOf(p).evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(248, 243, 230)', "doc colours: the studio's own sepia paper");
  await chipsOf(p, 'theme').filter({hasText: 'Follow my device'}).click();
  eq([await store(p, 'parseh_theme'), await attrOf(p, 'html', 'data-theme'), await p.evaluate(() => window.__applied.slice(-1)[0])], ['auto', null, 'auto'], "doc colours: 'auto' takes the attribute off and says auto");
  // interface with no Parseh and no studio switch
  await openGear(p, 'interface');
  await p.evaluate(() => { window.__heard = []; document.addEventListener('parseh:mode', e => window.__heard.push(e.detail && e.detail.mode)); });
  await chipsOf(p, 'mode').filter({hasText: 'Mobile'}).click();
  eq([await store(p, 'parseh_mode'), await attrOf(p, 'html', 'data-mode'), await p.evaluate(() => /(?:^|;\s*)parseh_mode=mobile(?:;|$)/.test(document.cookie)), await p.evaluate(() => window.__heard)], ['mobile', 'mobile', true, ['mobile']], 'doc interface: writes parseh_mode, <html data-mode>, the cookie and fires parseh:mode');
  await until(async () => (await rect(p, '#dmhost [data-parseh-gear]')) !== null, 'doc interface: the button is in the mobile topbar');
  await openGear(p, 'interface');
  eq(await rowOf(p, 'mode').locator('.pg-chip').evaluateAll(a => a.map(c => c.getAttribute('aria-pressed'))), ['false', 'true'], 'doc interface: Mobile is pressed');
  await chipsOf(p, 'mode').filter({hasText: 'Browser'}).click();
  eq([await store(p, 'parseh_mode'), await attrOf(p, 'html', 'data-mode'), await p.evaluate(() => /(?:^|;\s*)parseh_mode=browser(?:;|$)/.test(document.cookie))], ['browser', 'browser', true], 'doc interface: and Browser back');
  await t.close();
  // the studio's own switch, where it is there, does the work (it registers the worker an installed app lives by)
  t = await open('wide', 'doc', {query: 'studiomode=1'});
  p = t.page;
  await p.evaluate(() => { window.__studio = []; const o = ParsehStudioMode.set; ParsehStudioMode.set = function (m) { window.__studio.push(m); return o.apply(this, arguments); }; });
  await openGear(p, 'interface');
  await chipsOf(p, 'mode').filter({hasText: 'Mobile'}).click();
  eq([await p.evaluate(() => window.__studio), await store(p, 'parseh_mode'), await attrOf(p, 'html', 'data-mode')], [['mobile'], 'mobile', 'mobile'], "doc interface: the studio's own ParsehStudioMode.set is asked first where it exists");
  await t.close();
});

await sec('zoom', async () => {
  // no ParsehZoom: the group is not drawn (the fixture page loads the real parseh.js, which since a0.5.0 brings
  // lib/pagezoom.js with it: take the module away, as a page without it would be)
  let t = await open('wide', 'book');
  let p = t.page;
  await p.evaluate(() => { delete window.ParsehZoom; if (window.__gear) window.__gear.refresh(); });
  await openGear(p);
  eq(await groupOf(p, 'zoom').isVisible(), false, 'zoom: without ParsehZoom the group is not drawn');
  eq(await p.evaluate(() => [...document.querySelectorAll('.pg-gtitle')].filter(e => e.getClientRects().length).map(e => e.textContent)), ['Levels & reading', 'Listening', 'Looking a word up', 'Text', 'Colours', 'Interface'], 'zoom: and no other group is missing for it');
  await p.evaluate(() => { window.ParsehZoom = {STEPS: [90, 100, 110], get: () => 100, applied: () => 100, set() {}, can: () => true, reset() {}, onChange: () => () => {}}; window.__gear.refresh(); });
  eq(await groupOf(p, 'zoom').isVisible(), true, 'zoom: a module that arrives later gives the group, on the next refresh');
  await t.close();

  // against a stub
  t = await open('wide', 'book', {query: 'stubzoom=1'});
  p = t.page;
  await openGear(p, 'zoom');
  eq(await groupOf(p, 'zoom').locator('.pg-gtitle').textContent(), 'Zoom', 'zoom: the group is Zoom');
  eq(await groupOf(p, 'zoom').locator('.pg-caption').textContent(), 'Saved on this device, for all of Parseh.', 'zoom: where it is kept');
  eq(await rowOf(p, 'zoom').locator('.pg-help').textContent(), "Makes everything on the page bigger or smaller together — bars, buttons, clouds, sheets. A computer's own Ctrl + and Ctrl − do the same; the installed app cannot.", 'zoom: the sentence of the plan');
  const val = () => rowOf(p, 'zoom').locator('.pg-stepval').textContent();
  const less = rowOf(p, 'zoom').locator('button[aria-label=Decrease]'), more = rowOf(p, 'zoom').locator('button[aria-label=Increase]');
  const back = rowOf(p, 'zoom').locator('.pg-stepreset');
  eq([await val(), await less.textContent(), await more.textContent()], ['100 %', '−', '+'], 'zoom: [−] 100 % [+]');
  eq(await back.textContent(), 'Back to 100 %', 'zoom: and the way back');
  eq(await back.isDisabled(), true, 'zoom: at 100 % the way back rests');
  await more.click();
  eq([await lastCall(p), await val()], [{id: 'zoom.set', v: 110}, '110 %'], 'zoom: + takes the next step of ParsehZoom.STEPS');
  eq(await back.isDisabled(), false, 'zoom: away from 100 % the way back is there');
  await less.click();
  await less.click();
  eq([await lastCall(p), await val()], [{id: 'zoom.set', v: 90}, '90 %'], 'zoom: − takes the one before');
  await p.evaluate(() => ParsehZoom.set(150));
  eq(await val(), '150 %', 'zoom: a change from outside (onChange) reaches the stepper');
  eq(await more.isDisabled(), true, 'zoom: where ParsehZoom.can(+1) refuses, + is at rest');
  eq([await rowOf(p, 'zoom').locator('.pg-why').textContent(), await rowOf(p, 'zoom').locator('.pg-why').isVisible()], ['This window is too narrow for more.', true], "zoom: with the module's reason printed under it");
  await less.click();
  eq([await val(), (await lastCall(p)).v], ['125 %', 125], 'zoom: from 150 − is 125 (a step of the list)');
  eq(await rowOf(p, 'zoom').locator('.pg-why').isVisible(), false, 'zoom: the reason goes with the refusal');
  await p.evaluate(() => { window.__zoom.stored = 175; window.__zoom.max = 125; window.dispatchEvent(new Event('resize')); });
  eq(await val(), '125 %', 'zoom: what is shown is what is in force (applied), not what is stored');
  eq(await rowOf(p, 'zoom').locator('.pg-why').textContent(), 'Set to 175 %, but this window has room for 125 %. This window is too narrow for more.', 'zoom: and the difference is said');
  await back.click();
  eq([await lastCall(p), await val()], [{id: 'zoom.reset'}, '100 %'], 'zoom: the way back calls reset()');
  await t.close();

  // THE PAGE ZOOMED THE WAY lib/pagezoom.js ZOOMS ONE: it must land right under the button, in the window, at any zoom
  for (const z of [0.8, 1.25, 1.5, 2]) {
    t = await open('wide', 'book', {query: `z=${z}&stubzoom=1`});
    p = t.page;
    const loc = await p.evaluate(() => ({iw: innerWidth, ih: innerHeight, cw: document.documentElement.clientWidth, z: window.__Z}));
    assert(near(loc.iw * z, 1280, 1) && near(loc.cw * z, 1280, 2), `x${z}: (setup) the shim speaks the page's own pixels (${Math.round(loc.iw)} wide)`);
    await gearBtn(p).click();
    await p.waitForSelector('.pg-panel:not([hidden])');
    const real = await p.evaluate(() => {
      const f = window.__native.rect, b = f.call(document.querySelector('[data-parseh-gear]')), a = f.call(document.querySelector('.pg-panel'));
      return {bb: b.bottom, br: b.right, pt: a.top, pr: a.right, pl: a.left, pb: a.bottom, pw: a.width, W: window.__native.w, H: window.__native.h};
    });
    assert(near(real.pt, real.bb + 6 * z, 3), `x${z}: the popover is right under the button, in real pixels (${Math.round(real.bb)} -> ${Math.round(real.pt)})`);
    assert(near(real.pr, real.br, 3) || real.pl <= 8 * z + 2, `x${z}: its right edge is the button's (${Math.round(real.pr)} / ${Math.round(real.br)})`);
    assert(real.pl >= 0 && real.pr <= real.W + 0.5 && real.pb <= real.H + 0.5, `x${z}: and it is inside the window (${Math.round(real.pl)}..${Math.round(real.pr)}, bottom ${Math.round(real.pb)} of ${real.H})`);
    assert(near(real.pw, 380 * z, 3), `x${z}: 380 of the page's own pixels wide (${Math.round(real.pw)} real)`);
    // a click on the page's own text (a real pointer, in the shim's pixels) is outside and closes it
    await p.mouse.click(300, 500);
    await p.waitForSelector('.pg-panel', {state: 'hidden'});
    assert(true, `x${z}: an outside click closes it`);
    await t.close();
  }
  for (const z of [1.25, 1.5]) {
    t = await open('phone', 'book', {query: `z=${z}&stubzoom=1`});
    p = t.page;
    await gearBtn(p).tap();
    await p.waitForSelector('.pg-panel:not([hidden])');
    await sleep(250);
    const real = await p.evaluate(() => { const a = window.__native.rect.call(document.querySelector('.pg-panel')); return {t: a.top, b: a.bottom, w: a.width, l: a.left, W: window.__native.w, H: window.__native.h}; });
    assert(near(real.b, real.H, 1.5) && near(real.w, real.W, 1.5), `phone x${z}: the sheet stands on the foot and fills the width (bottom ${Math.round(real.b)} of ${real.H})`);
    assert(real.t >= real.H * 0.40 && real.t <= real.H * 0.55, `phone x${z}: and is about half the window (top at ${Math.round(real.t)} of ${real.H})`);
    await t.close();
  }
});

await sec('look', async () => {
  // reduced motion: no slide, no sweep
  let t = await open('phone', 'book', {reduced: true});
  let p = t.page;
  await gearBtn(p).tap();
  await p.waitForSelector('.pg-panel:not([hidden])');
  const rm = await p.evaluate(() => ({a: getComputedStyle(document.querySelector('.pg-panel')).animationName, t: getComputedStyle(document.querySelector('.pg-track')).transitionDuration}));
  eq(rm, {a: 'none', t: '0s'}, 'reduced motion: no animation on the sheet, no transition on a switch');
  await t.close();
  t = await open('phone', 'book');
  p = t.page;
  await gearBtn(p).tap();
  await p.waitForSelector('.pg-panel:not([hidden])');
  eq(await p.evaluate(() => getComputedStyle(document.querySelector('.pg-panel')).animationName), 'pg-rise', 'motion allowed: the sheet rises');
  await t.close();
  // on top of what it must be on top of, and out of the way when shut
  t = await open('wide', 'book');
  p = t.page;
  const underBefore = await p.evaluate(() => document.elementFromPoint(1000, 120).tagName);
  await gearBtn(p).click();
  await p.waitForSelector('.pg-panel:not([hidden])');
  const top = await p.evaluate(() => { const e = document.elementFromPoint(1100, 200); return !!e.closest('.pg-panel'); });
  assert(top, 'the popover is on top of the page and of its fixed header');
  await p.keyboard.press('Escape');
  eq(await p.evaluate(() => document.elementFromPoint(1000, 120).tagName), underBefore, 'shut, it is not in the way of anything');
  // an RTL page does not turn the panel around: the switch is at the right of its words
  await gearBtn(p).click();
  const sides = await p.evaluate(() => { const r = document.querySelector('[data-pg-row=gloss]'); return [r.querySelector('.pg-text').getBoundingClientRect().left < r.querySelector('.pg-switch').getBoundingClientRect().left, getComputedStyle(r.querySelector('.pg-name')).textAlign]; });
  eq(sides, [true, 'left'], 'a right-to-left page does not turn the panel around: the words left, the switch right');
  await t.close();
});

/* THE SCREENSHOTS, for whoever runs this with PAGE_GEAR_SHOTS to look at: the whole window with the panel open on each
   group, wide and on a phone, in the three themes, and for each group a strip of the panel alone in the three themes
   side by side (strip-<fixture>-<kind>-<group>.png), which is what is read for crowding, clipping and contrast. */
await sec('shots', async () => {
  if (!SHOTS) return;
  const made = [];
  for (const fixture of ['book', 'doc']) {
    for (const kind of ['wide', 'phone']) {
      const strips = {};
      for (const theme of THEMES) {
        const {page, close} = await open(kind, fixture, {theme, query: fixture === 'book' ? 'stubzoom=1&long=1&node=1' : 'stubzoom=1'});
        await openGear(page);
        // the phone's sheet opens on the index of the themes, which is shot as well
        if (kind === 'phone') {
          await sleep(220);
          await page.screenshot({path: `${SHOTS}/${fixture}-${kind}-${theme}-index.png`});
          await page.locator('.pg-panel').screenshot({path: `${SHOTS}/${fixture}-${kind}-${theme}-index-panel.png`});
          (strips.index = strips.index || []).push(`${fixture}-${kind}-${theme}-index-panel.png`);
        }
        for (const g of await page.evaluate(() => [...document.querySelectorAll('.pg-group')].filter(e => !e.hidden).map(e => e.getAttribute('data-pg-group')))) {
          await openGear(page, g);
          await sleep(220);
          const stem = `${fixture}-${kind}-${theme}-${g}`;
          await page.screenshot({path: `${SHOTS}/${stem}.png`});
          await page.locator('.pg-panel').screenshot({path: `${SHOTS}/${stem}-panel.png`});
          (strips[g] = strips[g] || []).push(`${stem}-panel.png`);
          made.push(stem);
        }
        await close();
      }
      for (const [g, files] of Object.entries(strips)) {
        const context = await browser.newContext({viewport: {width: 1200, height: 900}});
        const page = await context.newPage();
        await page.setContent('<body style="margin:0;padding:8px;display:flex;gap:8px;align-items:flex-start;background:#777">' +
          files.map(f => `<img src="${base}/shots/${f}" style="display:block">`).join('') + '</body>');
        await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth));
        await page.screenshot({path: `${SHOTS}/strip-${fixture}-${kind}-${g}.png`, fullPage: true});
        await context.close();
      }
    }
  }
  console.log('  screenshots:', made.length, 'in', SHOTS);
});

await browser.close();
server.shutdown();
console.log(passed + ' checks passed');
if (errors.length) { console.log('errors:\n' + [...new Set(errors)].join('\n')); failed.push('the pages logged ' + errors.length + ' errors'); }
if (failed.length) { console.log('FAILED:\n  ' + failed.join('\n  ')); Deno.exit(1); }
