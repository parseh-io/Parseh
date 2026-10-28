// SPDX-License-Identifier: GPL-3.0-or-later
import {chromium} from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=python3 deno run --allow-all tests/gear_studio.mjs
//      GEAR_STUDIO_SHOTS=<dir>   saves screenshots: every page, wide (1280x800) and on a phone (390x844), the panel
//                                open on each of its groups, in the light, dark and sepia themes
//      GEAR_STUDIO_ONLY=a,b      runs only those sections (a development aid): mount, text, exercises, page, editor,
//                                theme, interface, phone, widths, zoom, alone, shots
//
// THE GEAR OF A DOCUMENT, THE EDITOR AND THE EXERCISES (a0.5.0, plan §6; markdown/app/static/gear.js on the toolkit
// lib/pagesettings.js), driven where a person meets it -- the REAL pages, served by Parseh's own handler on a
// temporary library and a temporary exercises store (tests/decks_harness.py parseh: the studio at /studio, the decks
// at /exercises), in a real Chromium, with a mouse at 1280x800 and a finger at 390x844:
//
//  mount)     on a document, the editor, a deck, studying it and cramming it: the ⚙ is the last thing in the bar's row,
//             after ◐ (which the browser bars have now), and holds the groups the plan names, in its order, with the rows
//             of each: a document five type rows and a reset, the exercise pages four type rows and no more
//  text)      every row of Text changes the real page and back: the size of the script reaches the sheet AND the scale
//             Build PDF sends, the Latin size takes the column's width with it, the width, the leading, the headwords'
//             size, the justifying; "Put the text back to normal" is the PDF's own values; the two keys of
//             localStorage hold them and survive a reload; what is set on a document is read on a deck's pages (the
//             one shared key) and the other way about; the editor's preview follows live
//  exercises) «Hide transliterations» and «Drag to answer», from the gear and from the card, each the other's: one
//             state, the two buttons worded to match -- and on a page with no exercise on it yet, applied to the ones
//             drawn afterwards
//  page)      «Hide the bars» and the corner's «show bars»; Aa opens the gear at Text, a second press shuts it
//  editor)    «Write the source right to left» is the ⇤ RTL button's choice, both ways, and is kept for the document
//  theme)     ◐ on every browser bar; ONE function paints it: ◐, the gear's Colours, another tab, the computer's newer
//             value in another browser -- <html> and <body> and the sheet, the phone's ◐ page included
//  interface) the Browser | Mobile switch in the gear: the layout changes at once, the gear moves to the other bar
//  phone)     the phone's bar is ONE row at 320…430 with every target 48px, ◐ and ⚙ after the way up, no switch in it
//             (the library's and the decks' list's still have one); study and cram: the gear in the title row; the sheet
//             opens on the index of the page's themes with what each is set to (a0.5.4), a theme's rows 48px
//  widths)    nothing overflows sideways, 320 to 1280, on any of the five pages, in either layout
//  zoom)      with a ParsehZoom (lane Z's module is not in this tree: a stub) the Zoom group stands where the plan says
//  alone)     the studio run alone (no toolbox): the two files of the gear are answered for, the page works, and does
//             not say the theme follows a person
//  shots)     the screenshots
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('GEAR_STUDIO_SHOTS') || '';
const ONLY = (Deno.env.get('GEAR_STUDIO_ONLY') || '').split(',').filter(Boolean);
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
    await sleep(50);
  }
}

/* ------------------------------------------------------------ the server */
async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/decks_harness.py', mode], cwd: root,
                                         stdout: 'piped', stderr: 'inherit'}).spawn();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

/* ------------------------------------------------------------- the content */
const LESSON = `---
title: The gear lesson
target: fa
---

## کتاب | ketāb | = *book*

The word [کتاب]{tl} means *book*, as in [این کتاب است]{tl}.

:::exercise flashcard
card-type: vocab
target: [سلام]{tl}
transliteration: salām
meaning: hello
:::

:::exercise order-sentences
prompt: Put them in order
- [1] first
- [2] second
- [3] third
:::
`;
const OTHER = `---
title: A lesson nobody has set the type of
target: fa
---

Some text, with [کتاب]{tl} in it.
`;
const FLASH = ':::exercise flashcard\ncard-type: vocab\ntarget: [سلام]{tl}\ntransliteration: salām\nmeaning: hello\n:::';
const ORDER = ':::exercise order-sentences\nprompt: Put them in order\n- [1] first\n- [2] second\n- [3] third\n:::';

/* what the PDF's own values are, for a Persian document (app.js TYPO_DEFAULTS and defaultScale) */
const NORMAL = {fa: 1.52, base: 17, width: 720, lead: 1.45, voce: 3.4, justify: true};

const ZOOM_STUB = `window.ParsehZoom = (function () {
  var STEPS = [70, 80, 90, 100, 110, 125, 150, 175, 200], cur = 100, subs = [];
  function tell() { subs.slice().forEach(function (f) { f(); }); }
  return {STEPS: STEPS, get: function () { return cur; }, applied: function () { return cur; },
          set: function (v) { cur = v; tell(); }, can: function () { return true; }, reset: function () { cur = 100; tell(); },
          onChange: function (f) { subs.push(f); return function () { subs = subs.filter(function (x) { return x !== f; }); }; }};
})();`;

/* ----------------------------------------------------------- the browser */
const {proc, info} = await startHarness('parseh');
const B = `http://127.0.0.1:${info.port}`;
const S = info.studio;                       // "/studio"
const post = (path, data) => fetch(B + path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
const made = async md => (await (await post(`${S}/api/docs`, {markdown: md})).json()).meta.id;
const madeDeck = async (name, items) => {
  const deck = (await (await post('/exercises/api/decks', {name, lang: 'fa'})).json()).deck;
  for (const markdown of items) {
    const r = await post(`/exercises/api/decks/${deck.path}/items`, {markdown});
    if (!r.ok) throw Error('an exercise was refused: ' + await r.text());
  }
  return deck.path;
};
const lesson = await made(LESSON), other = await made(OTHER);
const flashDeck = await madeDeck('Gear flashcards', [FLASH]);
const orderDeck = await madeDeck('Gear sequences', [ORDER]);
const plainDeck = await madeDeck('Gear plain', [':::exercise single-choice\nprompt: Pick one\n- [x] first\n- [ ] second\n:::']);
const URLS = {
  doc: id => `${B}${S}/doc/${id || lesson}`,
  edit: id => `${B}${S}/doc/${id || lesson}/edit`,
  deck: d => `${B}/exercises/deck/${d || flashDeck}/`,
  study: d => `${B}/exercises/deck/${d || flashDeck}/study`,
  cram: d => `${B}/exercises/deck/${d || flashDeck}/cram#all`,
};
const KINDS = ['doc', 'edit', 'deck', 'study', 'cram'];
const READY = {   // what says a page of this kind has drawn what it draws
  doc: 'article.sheet .exercise', edit: '#sheet .exercise', deck: '.dk-row', study: '#study-stage .exercise, #study-stage .ex-flashcard',
  cram: '#cram-stage .exercise, #cram-stage .ex-flashcard'};

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN') || undefined, headless: true});
const errors = [];
const watch = (page, name) => {
  page.on('pageerror', e => errors.push(`${name}: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(`${name} console: ${m.text()}`); });
};

const DESK = {viewport: {width: 1280, height: 800}};
const PHONE = {viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true, deviceScaleFactor: 2};
/* a context whose device says the theme and the mode it is to start in, ONCE for the whole context (the first page of
   it): the device's own word, with the moment it was said beside it, so that what the computer holds of the theme (an
   earlier context's) does not outvote it -- and nothing is said again for the pages that follow, which find what the
   pages before them left */
async function context(opts, {theme, mode, zoom} = {}) {
  const ctx = await browser.newContext(opts);
  await ctx.addInitScript(([theme, mode, zoom, stub]) => {
    try {
      if (!localStorage.getItem('__gear_seed')) {
        localStorage.setItem('__gear_seed', '1');
        if (theme) { localStorage.setItem('parseh_theme', theme); localStorage.setItem('parseh_at', JSON.stringify({parseh_theme: Date.now() / 1000})); }
        if (mode) { localStorage.setItem('parseh_mode', mode); document.cookie = 'parseh_mode=' + mode + '; Path=/'; }
      }
    } catch (e) {}
    if (zoom) (0, eval)(stub);
  }, [theme || '', mode || '', !!zoom, ZOOM_STUB]);
  return ctx;
}
async function open(ctx, kind, arg, {ready} = {}) {
  const page = await ctx.newPage();
  watch(page, kind);
  await page.goto(URLS[kind](arg));
  await page.waitForSelector(ready || READY[kind], {state: 'attached', timeout: 20000});
  await page.waitForSelector('[data-parseh-gear]', {state: 'attached'});
  await page.evaluate(() => document.fonts.ready);
  return page;
}
const tapOrClick = (page, loc) => page.evaluate(() => matchMedia('(pointer: coarse)').matches).then(t => t ? loc.tap() : loc.click());
const gearButton = page => page.locator('[data-parseh-gear]:visible').first();
const panel = page => page.locator('.pg-panel');
async function openGear(page, group) {
  if (!(await page.evaluate(() => ParsehGear.mounted().isOpen()))) await tapOrClick(page, gearButton(page));
  await until(() => page.evaluate(() => ParsehGear.mounted().isOpen() && !document.querySelector('.pg-panel').hidden), 'the gear is up');
  if (group) await page.evaluate(g => ParsehGear.mounted().open(g), group);
  await sleep(120);
  // on a phone's sheet the theme slides in from the right (0.16 s): let it come to rest before anything is read or tapped
  if (group && await page.evaluate(() => document.querySelector('.pg-panel').classList.contains('pg-sheet'))) await sleep(200);
}
/* the element scrolled to the middle of the strip of the page a phone's sheet leaves (under its bars, above the sheet) */
const place = async (page, sel, y = 240) => {
  await page.evaluate(([sel, y]) => { const e = document.querySelector(sel); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - y); }, [sel, y]);
  await sleep(500);
};
const closeGear = async page => { await page.evaluate(() => ParsehGear.mounted().close()); await sleep(80); };
const groupsOf = page => page.evaluate(() => [...document.querySelectorAll('.pg-panel .pg-group')]
  .filter(g => !g.hidden).map(g => g.getAttribute('data-pg-group')));
const rowsOf = (page, group) => page.evaluate(g => [...document.querySelectorAll(`.pg-panel [data-pg-group="${g}"] .pg-row`)]
  .filter(r => !r.hidden).map(r => r.getAttribute('data-pg-row')), group);
const row = (page, group, id) => page.locator(`.pg-panel [data-pg-group="${group}"] [data-pg-row="${id}"]`);
const sheetVars = (page, sel = '.sheet') => page.evaluate(sel => {
  const s = document.querySelector(sel), st = s.style;
  return {fa: +st.getPropertyValue('--fa-scale'), base: parseFloat(st.getPropertyValue('--base-size')),
          width: parseFloat(st.getPropertyValue('--sheet-width')), lead: +st.getPropertyValue('--leading'),
          voce: +st.getPropertyValue('--voce-scale'), justify: s.classList.contains('justify')};
}, sel);
const stored = (page, key) => page.evaluate(k => { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }, key);
const setRange = async (page, group, id, value) => {
  const input = row(page, group, id).locator('input[type=range]');
  await input.fill(String(value));
  await sleep(60);
};
const out = (page, group, id) => row(page, group, id).locator('output').textContent();
const switchOn = async (page, group, id) => (await row(page, group, id).locator('[role=switch]').getAttribute('aria-checked')) === 'true';
const flipSwitch = (page, group, id) => tapOrClick(page, row(page, group, id).locator('[role=switch]'));
const theme = page => page.evaluate(() => ({body: document.body.dataset.theme || 'paper', html: document.documentElement.getAttribute('data-theme'),
                                            stored: localStorage.getItem('parseh_theme'),
                                            sheet: getComputedStyle(document.querySelector('.sheet') || document.body).backgroundColor,
                                            page: getComputedStyle(document.body).backgroundColor}));
const glyph = page => page.evaluate(() => [...document.querySelectorAll('[data-parseh-theme]')].filter(b => b.getClientRects().length)
  .map(b => b.textContent));
const bytes = (page, sel) => page.evaluate(sel => {
  const e = document.querySelector(sel); if (!e) return null;
  const r = e.getBoundingClientRect(); return {l: Math.round(r.left), t: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height)};
}, sel);
async function shot(page, name) {
  if (SHOTS) await page.screenshot({path: `${SHOTS}/${name}.png`});
}

/* A SECTION THAT FAILS DOES NOT STOP THE REST: each is run on its own, its first failure said and counted, and the run
   ends with all of them -- a turn of the suite lock is long to wait for */
const failures = [];
async function section(name, run, fn) {
  if (!run) return;
  try { await fn(); }
  catch (e) { failures.push(name); console.log(`  FAILED section "${name}": ${String(e && e.message || e).split('\n')[0]}`); }
}

try {
  /* ====================================================================================== mount */
  await section('mount', want('mount'), async () => {
    console.log('mount) the gear on the five pages, at 1280x800 with a mouse');
    const ctx = await context(DESK, {theme: 'light'});
    // (with lib/pagezoom.js on every studio page since a0.5.0 the Zoom group stands where the plan says)
    const GROUPS = {
      doc: ['text', 'exercises', 'page', 'zoom', 'colours', 'interface'], edit: ['text', 'zoom', 'colours', 'editor'],
      deck: ['text', 'exercises', 'zoom', 'colours', 'interface'], study: ['text', 'exercises', 'zoom', 'colours', 'interface'],
      cram: ['text', 'exercises', 'zoom', 'colours', 'interface']};
    const TEXT_DOC = ['fa', 'base', 'width', 'lead', 'voce', 'justify', 'reset'], TEXT_DECK = ['fa', 'base', 'lead', 'justify'];
    for (const kind of KINDS) {
      const page = await open(ctx, kind);
      // the button: one, in the bar's row, after ◐, its words and its name
      const where = await page.evaluate(() => {
        const g = [...document.querySelectorAll('[data-parseh-gear]')], b = g[0];
        const tail = b && b.parentElement, kids = tail ? [...tail.children].map(c => c.hasAttribute('data-parseh-theme') ? 'theme' : c.hasAttribute('data-parseh-gear') ? 'gear' : c.tagName) : [];
        const row = tail && tail.parentElement;
        return {n: g.length, tail: tail && tail.className, kids, row: row && row.className, header: row && row.parentElement.tagName + '.' + row.parentElement.className,
                last: row && row.lastElementChild === tail, word: b && b.querySelector('.pg-gear-word').textContent,
                label: b && b.getAttribute('aria-label'), title: b && b.title};
      });
      eq([where.n, where.tail, where.kids, where.last, where.header], [1, 'bar-tail', ['theme', 'gear'], true, 'HEADER.topbar'],
         `${kind}: one gear, after ◐, the last two of the browser bar's row (${JSON.stringify(where)})`);
      eq([where.word, where.label], ['page', 'Settings of this page'], `${kind}: it says "page" and is named "Settings of this page"`);
      const th = await page.locator('.topbar [data-parseh-theme]').count();
      assert(th === 1 && (await page.locator('.topbar [data-parseh-theme]').isVisible()), `${kind}: the browser bar has a ◐`);
      await openGear(page);
      eq(await groupsOf(page), GROUPS[kind], `${kind}: the groups, in the plan's order (Zoom included: the zoom module is on every studio page)`);
      if (kind === 'doc' || kind === 'edit') eq(await rowsOf(page, 'text'), TEXT_DOC, `${kind}: Text holds the five type rows, "justify" and the reset`);
      else eq(await rowsOf(page, 'text'), TEXT_DECK, `${kind}: Text holds four rows, no width and no headword size, and no reset`);
      if (kind === 'doc' || kind === 'deck' || kind === 'study' || kind === 'cram')
        eq(await rowsOf(page, 'exercises'), kind === 'doc' ? ['translit', 'drag', 'autocheck'] : ['translit', 'drag'],
           `${kind}: Exercises holds the transliterations and the dragging` + (kind === 'doc' ? ', and on a document alone, Check as I answer (a0.5.7)' : ''));
      if (kind === 'doc') eq(await rowsOf(page, 'page'), ['bars'], 'doc: Page holds the bars');
      if (kind === 'edit') eq(await rowsOf(page, 'editor'), ['dir', 'tab', 'opentab'], 'edit: the editor group holds the direction of the source and the preview\'s own tab (a switch and a button)');
      eq(await rowsOf(page, 'colours'), ['theme'], `${kind}: Colours`);
      if (kind !== 'edit') eq(await rowsOf(page, 'interface'), ['mode'], `${kind}: Interface`);
      eq(await page.locator('.pg-panel .pg-title').textContent(), 'This page', `${kind}: the panel is "This page"`);
      // the names the plan gives, and a sentence under each
      const names = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=text] .pg-row')]
        .map(r => [r.getAttribute('data-pg-row'), (r.querySelector('.pg-nametext') || r.querySelector('.pg-btn') || {}).textContent,
                   (r.querySelector('.pg-help') || {}).textContent]));
      if (kind === 'doc') {
        eq(names.map(n => n[1]), ['Persian text size', 'Latin text size', 'Text width', 'Line spacing', 'Headword size', 'Justify the text',
                                  'Put the text back to normal'], 'doc: the plan\'s names, the language\'s own in the first');
        eq(names[0][2], 'How big the Persian text is compared with the Latin text around it (1× = the same size). The PDF you build uses the same size.',
           'doc: the first row says it is also the PDF\'s scale');
        eq(names[1][2], 'How big the Latin-script text (the explanations around the Persian) is, from 13 to 23 pixels. The text width follows it unless you set the width yourself.',
           'doc: Latin text size, in the plan\'s words');
        eq(names[4][2], 'How big the word at the top of each dictionary-style entry is, as a multiple of the text size.', 'doc: Headword size');
        eq(names[5][2], 'Straight left and right edges, with words hyphenated at line ends, the way the PDF sets it.', 'doc: Justify the text');
      }
      if (kind === 'deck') eq(names.map(n => n[1]), ['Persian text size', 'Latin text size', 'Line spacing', 'Justify the text'],
                              'deck: four names');
      await closeGear(page);
      await page.close();
    }
    await ctx.close();
  });

  /* ======================================================================================= text */
  await section('text', want('text'), async () => {
    console.log('text) every row changes the real page, the PDF\'s scale, the stored keys -- and back');
    const ctx = await context(DESK, {theme: 'light'});
    const doc = await open(ctx, 'doc');
    await openGear(doc, 'text');
    eq(await sheetVars(doc), NORMAL, 'a document starts from the PDF\'s own values');
    // Build PDF is asked for at the scale of the first row: the request is read, not sent on
    let asked = null;
    await doc.route(/\/api\/docs\/[^/]+\/build(\?.*)?$/, r => { asked = JSON.parse(r.request().postData() || '{}'); r.fulfill({status: 500, contentType: 'application/json', body: '{"error":"not built here"}'}); });
    // the size of the script
    await setRange(doc, 'text', 'fa', 2.1);
    eq((await sheetVars(doc)).fa, 2.1, 'Persian text size: the sheet is set at 2.1');
    eq(await out(doc, 'text', 'fa'), '2.10×', 'and the row says 2.10×');
    await closeGear(doc);
    await doc.locator('#btn-build').click();
    await until(() => asked, 'the build was asked for');
    eq(asked.scale, 2.1, 'Build PDF sends the same scale: the one number is both the page\'s and the PDF\'s');
    await openGear(doc, 'text');
    // the Latin size takes the column's width with it, by the ratio they hold
    await setRange(doc, 'text', 'base', 20);
    let v = await sheetVars(doc);
    eq([v.base, Math.round(v.width)], [20, Math.round(720 * 20 / 17)], 'Latin text size: 20 px, and the column\'s width follows (720 x 20 / 17)');
    eq(await out(doc, 'text', 'base'), '20 px', 'the row says 20 px');
    // the width itself moves the ratio and nothing else
    await setRange(doc, 'text', 'width', 900);
    v = await sheetVars(doc);
    eq([v.base, v.width], [20, 900], 'Text width: 900, and the Latin size does not move with it');
    await setRange(doc, 'text', 'base', 16);
    v = await sheetVars(doc);
    eq([v.base, Math.round(v.width)], [16, Math.round(900 * 16 / 20)], 'then the Latin size scales from where the width IS now (900 x 16 / 20)');
    await setRange(doc, 'text', 'lead', 1.8);
    eq((await sheetVars(doc)).lead, 1.8, 'Line spacing: 1.8');
    await setRange(doc, 'text', 'voce', 4.2);
    eq((await sheetVars(doc)).voce, 4.2, 'Headword size: 4.2');
    await flipSwitch(doc, 'text', 'justify');
    eq((await sheetVars(doc)).justify, false, 'Justify the text: off, and the sheet is no longer justified');
    assert(!(await switchOn(doc, 'text', 'justify')), 'and the switch says off');
    // the keys: the shared one and the document's own, both
    const global = await stored(doc, 'exlex-typo:global'), own = await stored(doc, 'exlex-typo:' + lesson);
    eq([global.fa, global.base, global.lead, global.voce, global.justify, 'theme' in global], [2.1, 16, 1.8, 4.2, false, false],
       'the shared key holds the values, and no theme');
    eq(own, global, 'and the document\'s own key holds the same');
    // they survive a reload
    await doc.reload();
    await doc.waitForSelector('article.sheet .exercise');
    v = await sheetVars(doc);
    eq([v.fa, v.base, v.lead, v.voce, v.justify], [2.1, 16, 1.8, 4.2, false], 'a reload reads them back: the sheet wears them');
    await openGear(doc, 'text');
    eq([await out(doc, 'text', 'fa'), await out(doc, 'text', 'lead'), await switchOn(doc, 'text', 'justify')], ['2.10×', '1.80', false],
       'and the panel shows them');
    // back to normal: the PDF's own values
    await tapOrClick(doc, row(doc, 'text', 'reset').locator('button'));
    await sleep(100);
    eq(await sheetVars(doc), NORMAL, 'Put the text back to normal: the PDF\'s own values on the sheet');
    eq([await out(doc, 'text', 'fa'), await out(doc, 'text', 'base'), await out(doc, 'text', 'width'), await switchOn(doc, 'text', 'justify')],
       ['1.52×', '17 px', '720 px', true], 'and in the rows');
    const reset = await stored(doc, 'exlex-typo:' + lesson);
    eq([reset.fa, reset.base, reset.width, reset.lead, reset.voce, reset.justify], [1.52, 17, 720, 1.45, 3.4, true], 'and in the stored key');
    await closeGear(doc);

    // the exercise pages share the key: set on the document, read on the deck's pages
    await openGear(doc, 'text');
    await setRange(doc, 'text', 'fa', 1.9);
    await setRange(doc, 'text', 'lead', 1.7);
    await flipSwitch(doc, 'text', 'justify');
    await closeGear(doc);
    const deck = await open(ctx, 'deck');
    await openGear(deck, 'text');
    eq([await out(deck, 'text', 'fa'), await out(deck, 'text', 'lead'), await switchOn(deck, 'text', 'justify')], ['1.90×', '1.70', false],
       'what was set on a document is what the deck\'s Text says (one stored value, exlex-typo:global)');
    const study = await open(ctx, 'study');
    eq([(await sheetVars(study, '#study-stage')).fa, (await sheetVars(study, '#study-stage')).lead], [1.9, 1.7],
       'and what the study page\'s exercise is set in');
    // ... and the other way about: set on the study page, read on a document nobody has set
    await openGear(study, 'text');
    await setRange(study, 'text', 'fa', 1.3);
    await setRange(study, 'text', 'base', 19);
    eq((await sheetVars(study, '#study-stage')).fa, 1.3, 'on the study page the exercise follows the row at once');
    const fresh = await open(ctx, 'doc', other, {ready: 'article.sheet p'});
    v = await sheetVars(fresh);
    eq([v.fa, v.base], [1.3, 19], 'a document nobody has set the type of starts from what the exercises were set to');
    assert(!(await stored(fresh, 'exlex-typo:' + other)), 'and has no record of its own until it is set');
    await fresh.close(); await study.close(); await deck.close(); await doc.close();

    // the editor's preview follows live, on the same stored values
    const edit = await open(ctx, 'edit');
    await openGear(edit, 'text');
    await setRange(edit, 'text', 'fa', 2.2);
    await setRange(edit, 'text', 'lead', 1.95);
    v = await sheetVars(edit, '#sheet');
    eq([v.fa, v.lead], [2.2, 1.95], 'the editor: Text moves the live preview');
    await flipSwitch(edit, 'text', 'justify');
    eq((await sheetVars(edit, '#sheet')).justify, true, 'and the justifying of it');
    const editOwn = await stored(edit, 'exlex-typo:' + lesson);
    eq([editOwn.fa, editOwn.lead], [2.2, 1.95], 'the document\'s own key is written from the editor too');
    const back = await open(ctx, 'doc');
    eq([(await sheetVars(back)).fa, (await sheetVars(back)).lead], [2.2, 1.95], 'and the reading page shows what the editor set');
    await back.close(); await edit.close();
    await ctx.close();
  });

  /* ================================================================================= exercises */
  await section('exercises', want('exercises'), async () => {
    console.log('exercises) the two switches, from the gear and from the card: one state');
    const ctx = await context(DESK, {theme: 'light'});
    const doc = await open(ctx, 'doc');
    const state = () => doc.evaluate(() => ({hidden: document.body.classList.contains('ex-hide-transliteration'),
      tl: [...document.querySelectorAll('.ex-translit-switch')].map(b => b.textContent + '/' + b.getAttribute('aria-pressed')),
      drag: [...document.querySelectorAll('.ex-drag-switch')].map(b => b.textContent + '/' + b.getAttribute('aria-pressed')),
      draggable: [...document.querySelectorAll('.ex-sequence .ex-item')].map(i => i.draggable),
      keys: [localStorage.getItem('parseh_exercise_hide_transliteration'), localStorage.getItem('parseh_exercise_drag')],
      shown: (() => { const e = document.querySelector('.ex-card-transliteration'); return !!e && getComputedStyle(e).display !== 'none'; })()}));
    let s = await state();
    eq([s.hidden, s.tl, s.shown], [false, ['Hide transliterations/false'], true], 'at first the card shows its transliteration and offers to hide it');
    eq([s.drag, s.draggable], [['✥ dragging on/true'], [true, true, true]], 'and a sequence may be dragged, on a mouse');
    await openGear(doc, 'exercises');
    eq([await switchOn(doc, 'exercises', 'translit'), await switchOn(doc, 'exercises', 'drag')], [false, true], 'the gear says the same');
    // from the gear
    await flipSwitch(doc, 'exercises', 'translit');
    s = await state();
    eq([s.hidden, s.tl, s.shown, s.keys[0]], [true, ['Show transliterations/true'], false, '1'],
       'Hide transliterations, from the gear: the line is gone, the card\'s own button says "Show", the key is 1');
    await flipSwitch(doc, 'exercises', 'drag');
    s = await state();
    eq([s.drag, s.draggable, s.keys[1]], [['✥ dragging off/false'], [false, false, false], '0'],
       'Drag to answer, from the gear: the blocks cannot be dragged, the exercise\'s own button says "dragging off", the key is 0');
    // from the card (a click outside shuts the popover: what the card said is what the gear says when it is opened again)
    await doc.locator('.ex-translit-switch').click();
    s = await state();
    eq([s.hidden, s.shown, s.keys[0]], [false, true, '0'], 'the card\'s own button turns it back');
    await openGear(doc, 'exercises');
    assert(!(await switchOn(doc, 'exercises', 'translit')), 'and the gear says so when it is opened again: one state, two buttons');
    await closeGear(doc);
    await doc.locator('.ex-drag-switch').click();
    s = await state();
    eq([s.drag, s.draggable, s.keys[1]], [['✥ dragging on/true'], [true, true, true], '1'], 'the exercise\'s button turns dragging back on');
    await openGear(doc, 'exercises');
    assert(await switchOn(doc, 'exercises', 'drag'), 'and the gear\'s row says it too');
    // remembered: every page of this browser
    await flipSwitch(doc, 'exercises', 'translit');
    await flipSwitch(doc, 'exercises', 'drag');
    await closeGear(doc);
    await doc.reload();
    await doc.waitForSelector('article.sheet .exercise');
    s = await state();
    eq([s.hidden, s.tl, s.drag, s.draggable], [true, ['Show transliterations/true'], ['✥ dragging off/false'], [false, false, false]],
       'a reload keeps both');
    // a page with no exercise on it yet: the choice is set there, and applied to the exercise drawn afterwards
    await doc.close();
    const deck = await open(ctx, 'deck');
    assert(await deck.locator('.ex-flashcard').count() === 0, 'the deck page has no exercise drawn on it');
    await openGear(deck, 'exercises');
    eq([await switchOn(deck, 'exercises', 'translit'), await switchOn(deck, 'exercises', 'drag')], [true, false], 'but its gear says what the device chose');
    await flipSwitch(deck, 'exercises', 'translit');
    await flipSwitch(deck, 'exercises', 'drag');
    eq(await deck.evaluate(() => [localStorage.getItem('parseh_exercise_hide_transliteration'), localStorage.getItem('parseh_exercise_drag')]),
       ['0', '1'], 'turned there, the keys change');
    await flipSwitch(deck, 'exercises', 'translit');
    await flipSwitch(deck, 'exercises', 'drag');
    await deck.close();
    const study = await open(ctx, 'study');
    await study.waitForSelector('#study-stage .ex-translit-switch');
    eq(await study.evaluate(() => [document.body.classList.contains('ex-hide-transliteration'),
                                   document.querySelector('.ex-translit-switch').textContent]),
       [true, 'Show transliterations'], 'the exercise drawn on the study page afterwards wears it: transliteration hidden');
    await study.close();
    const order = await open(ctx, 'study', orderDeck);
    await order.waitForSelector('#study-stage .ex-drag-switch');
    eq(await order.evaluate(() => [document.querySelector('.ex-drag-switch').textContent, [...document.querySelectorAll('.ex-sequence .ex-item')].map(i => i.draggable)]),
       ['✥ dragging off', [false, false, false]], 'and the sequence drawn afterwards cannot be dragged');
    // the study page's own switch and its gear, together (the popover stands over the exercise's switch: it is shut to press it)
    await order.locator('.ex-drag-switch').click();
    await openGear(order, 'exercises');
    assert(await switchOn(order, 'exercises', 'drag'), 'on the study page, what the exercise\'s own switch did is what the gear\'s row says');
    await order.close();
    // a finger: dragging starts off where the pointer is coarse, and the row says so -- and the sheet stays up under a tap on
    // the page above it, so there the rows follow the page's own buttons LIVE
    const phone = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const pdoc = await open(phone, 'doc');
    await openGear(pdoc, 'exercises');
    assert(!(await switchOn(pdoc, 'exercises', 'drag')), 'on a touch screen "Drag to answer" is off until it is said');
    await place(pdoc, '.ex-translit-switch');
    await pdoc.locator('.ex-translit-switch').tap();
    await sleep(120);
    assert(await switchOn(pdoc, 'exercises', 'translit'), 'on the phone the sheet stays up under a tap on the card\'s own button, and its row follows it at once');
    await place(pdoc, '.ex-drag-switch');
    await pdoc.locator('.ex-drag-switch').tap();
    await sleep(120);
    assert(await switchOn(pdoc, 'exercises', 'drag'), 'and the dragging\'s row follows the exercise\'s button');
    await pdoc.close();
    await phone.close();
    await ctx.close();
  });

  /* ========================================================================================= page */
  await section('page', want('page'), async () => {
    console.log('page) the bars, and Aa');
    const ctx = await context(DESK, {theme: 'light'});
    const doc = await open(ctx, 'doc');
    const names = await doc.evaluate(() => [document.querySelector('#btn-bars').textContent, document.querySelector('#btn-bars-show').textContent]);
    eq(names, ['⌃ hide bars', '⌄ show bars'], 'the toolbar\'s button reads "⌃ hide bars" and the corner\'s "⌄ show bars"');
    const bars = () => doc.evaluate(() => ({off: document.body.classList.contains('chrome-off'), top: !!document.querySelector('.topbar').getClientRects().length,
      show: !!document.querySelector('#btn-bars-show').getClientRects().length, key: localStorage.getItem('parseh_bars_off')}));
    eq(await bars(), {off: false, top: true, show: false, key: '0'}, 'the bars stand to begin with');
    await openGear(doc, 'page');
    assert(!(await switchOn(doc, 'page', 'bars')), 'the gear says they are not away');
    await flipSwitch(doc, 'page', 'bars');
    eq(await bars(), {off: true, top: false, show: true, key: '1'}, 'Hide the bars, from the gear: the three bars are away, the way back is in the corner');
    assert(await panel(doc).isVisible(), 'and the gear\'s panel is still there to say so');
    await closeGear(doc);
    await doc.reload();
    await doc.waitForSelector('article.sheet');
    eq((await bars()).off, true, 'a reload keeps them away');
    await doc.locator('#btn-bars-show').click();
    eq(await bars(), {off: false, top: true, show: false, key: '0'}, 'the corner button brings them back');
    await doc.locator('#btn-bars').click();
    eq((await bars()).off, true, 'and the toolbar\'s own button puts them away');
    // the gear says what the page's own buttons did (no gear button is on the screen with the bars away: the API opens it)
    await doc.evaluate(() => ParsehGear.mounted().open('page'));
    assert(await switchOn(doc, 'page', 'bars'), 'the gear says they are away');
    await closeGear(doc);                                   // (with no bar for the popover to hang from it stands at the top corner, over the way back)
    await doc.locator('#btn-bars-show').click();
    await openGear(doc, 'page');
    assert(!(await switchOn(doc, 'page', 'bars')), 'and, opened again, that the corner brought them back');
    await closeGear(doc);

    // Aa: the gear at Text; a second press shuts it; the gear's own button leaves it where it was and Aa takes it to Text
    const at = () => doc.evaluate(() => {
      const p = document.querySelector('.pg-panel'), b = p && p.querySelector('.pg-body'), g = p && p.querySelector('[data-pg-group=text]');
      return {up: !!p && !p.hidden, atText: !!g && Math.abs(g.getBoundingClientRect().top - b.getBoundingClientRect().top) < 40, expanded: document.querySelector('#btn-typo').getAttribute('aria-expanded')};
    });
    await doc.locator('#btn-typo').click();
    await sleep(200);
    eq(await at(), {up: true, atText: true, expanded: 'true'}, 'Aa opens the gear at Text');
    eq(await doc.evaluate(() => document.activeElement.closest('[data-pg-row]') && document.activeElement.closest('[data-pg-row]').getAttribute('data-pg-row')),
       'fa', 'with the keyboard on its first control');
    await doc.locator('#btn-typo').click();
    await sleep(200);
    eq((await at()).up, false, 'a second press of Aa shuts it (and does not shut it only to open it again)');
    await gearButton(doc).click();
    await doc.evaluate(() => document.querySelector('.pg-body').scrollTo(0, 99999));
    await sleep(100);
    assert(!(await at()).atText, 'the gear\'s own button opens it where it is (here, scrolled away from Text)');
    await doc.locator('#btn-typo').click();
    await sleep(200);
    eq((await at()).atText && (await at()).up, true, 'and Aa then takes it to Text');
    await doc.keyboard.press('Escape');
    await sleep(100);
    eq((await at()).up, false, 'Esc shuts it');
    await doc.close();
    await ctx.close();
  });

  /* ======================================================================================= editor */
  await section('editor', want('editor'), async () => {
    console.log('editor) the direction of the source');
    const ctx = await context(DESK, {theme: 'light'});
    const edit = await open(ctx, 'edit');
    const dir = () => edit.evaluate(id => ({src: document.querySelector('#src').dir, button: document.querySelector('#btn-editor-dir').textContent,
                                            key: localStorage.getItem('parseh_editor_dir:' + id), focus: document.activeElement && document.activeElement.id}), lesson);
    eq((await dir()).src, 'ltr', 'the source is written left to right to begin with');
    await openGear(edit, 'editor');
    assert(!(await switchOn(edit, 'editor', 'dir')), 'the row says so');
    eq(await row(edit, 'editor', 'dir').locator('.pg-nametext').textContent(), 'Write the source right to left', 'it is "Write the source right to left"');
    eq(await row(edit, 'editor', 'dir').locator('.pg-help').textContent(), 'Which way the source text box runs, for a right-to-left language. Remembered for this document.',
       'and says what it does, in the plan\'s words');
    await flipSwitch(edit, 'editor', 'dir');
    let d = await dir();
    eq([d.src, d.button, d.key], ['rtl', '⇥ LTR editor', 'rtl'], 'turned on: the source runs right to left, the editor\'s own button says so, and it is kept for the document');
    assert(d.focus !== 'src', 'and the keyboard is still in the panel, not thrown into the text box');
    // the page's own button turns it back (a click outside shuts the popover: the gear says it when it is opened again)
    await edit.locator('#btn-editor-dir').click();
    d = await dir();
    eq([d.src, d.key], ['ltr', 'ltr'], 'the page\'s own button turns it back');
    await openGear(edit, 'editor');
    assert(!(await switchOn(edit, 'editor', 'dir')), 'and the gear, opened again, says so');
    await flipSwitch(edit, 'editor', 'dir');
    await edit.reload();
    await edit.waitForSelector('#src');
    eq((await dir()).src, 'rtl', 'remembered: a reload keeps the document\'s direction');
    await openGear(edit, 'editor');
    assert(await switchOn(edit, 'editor', 'dir'), 'and the row says it');
    // the editor has no phone layout: whatever the device's mode is, its gear is in the bar
    await closeGear(edit);
    await edit.close();
    const mobile = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const pe = await open(mobile, 'edit');
    eq(await pe.evaluate(() => [document.querySelector('[data-parseh-gear]').parentElement.className, ParsehGear.mounted().isOpen()]), ['bar-tail', false],
       'on a device set to the mobile mode the editor, which has no phone layout, still has its gear in its bar');
    await openGear(pe);
    eq(await groupsOf(pe), ['text', 'zoom', 'colours', 'editor'], 'with the same groups, and no Interface');
    // and there (a sheet: not shut by a tap on the page above it) the row follows the page's own button AT ONCE
    await pe.evaluate(() => ParsehGear.mounted().open('editor'));
    const before = await switchOn(pe, 'editor', 'dir');
    await pe.evaluate(() => document.querySelector('#btn-editor-dir').scrollIntoView({block: 'center'}));
    await pe.locator('#btn-editor-dir').tap();
    await sleep(150);
    assert(await switchOn(pe, 'editor', 'dir') === !before, 'on a phone the open sheet\'s row follows the editor\'s own ⇤ RTL button as it is pressed');
    await pe.close();
    await mobile.close();
    await ctx.close();
  });

  /* ======================================================================================= theme */
  await section('theme', want('theme'), async () => {
    console.log('theme) one function paints it, whatever changes it');
    const ctx = await context(DESK, {theme: 'light'});
    const looks = async page => { const t = await theme(page); return [t.body, t.html, t.stored]; };
    for (const kind of KINDS) {
      const page = await open(ctx, kind);
      const g0 = await glyph(page);
      eq(g0, ['○'], `${kind}: ◐ shows the palette on screen (light: ○)`);
      eq(await page.locator('.topbar [data-parseh-theme]').getAttribute('title'), 'theme: light — click for dark', `${kind}: and says what a click does, as the reader's does`);
      const before = await theme(page);
      await page.locator('.topbar [data-parseh-theme]').click();
      const t = await theme(page);
      eq([t.body, t.html, t.stored, await glyph(page)], ['dark', 'dark', 'dark', ['●']], `${kind}: ◐ makes the whole page dark: <body>, <html>, the key, the glyph`);
      assert(t.page !== before.page, `${kind}: and the page's colour really changed (${before.page} -> ${t.page})`);
      if (kind !== 'deck') assert(t.sheet !== before.sheet, `${kind}: and so did the sheet's (${before.sheet} -> ${t.sheet})`);
      await page.locator('.topbar [data-parseh-theme]').click();
      eq(await looks(page), ['sepia', 'sepia', 'sepia'], `${kind}: and again: sepia`);
      await page.locator('.topbar [data-parseh-theme]').click();
      eq(await looks(page), ['paper', 'light', 'light'], `${kind}: and again: light, which the sheet calls paper`);
      await page.close();
    }
    // the gear's Colours: the same function, at once, and ◐ follows
    const doc = await open(ctx, 'doc');
    await openGear(doc, 'colours');
    const chip = name => row(doc, 'colours', 'theme').locator('.pg-chip', {hasText: name}).first();
    const checked = () => row(doc, 'colours', 'theme').locator('[role=radio][aria-checked=true]').textContent();
    eq(await checked(), 'Light', 'Colours says which is on (Light, as the bar\'s ◐ left it)');
    await tapOrClick(doc, chip('Dark'));
    await sleep(100);
    let t = await theme(doc);
    eq([t.body, t.html, t.stored, await glyph(doc)], ['dark', 'dark', 'dark', ['●']], 'Colours: Dark repaints <body>, <html>, the key and ◐ at once');
    assert(t.sheet !== 'rgb(255, 255, 255)', 'and the sheet is no longer white');
    await tapOrClick(doc, chip('Sepia'));
    await sleep(100);
    eq((await looks(doc)), ['sepia', 'sepia', 'sepia'], 'Colours: Sepia');
    await tapOrClick(doc, chip('Follow my device'));
    await sleep(100);
    t = await theme(doc);
    eq([t.stored, t.html], ['auto', null], 'Colours: Follow my device is no attribute on <html>, as the readers have it');
    eq(t.body, 'paper', 'and (the system being light here) the page is paper');
    await tapOrClick(doc, chip('Light'));
    // ◐ pressed (a click outside shuts the popover): the gear, opened again, says what ◐ chose
    await doc.locator('.topbar [data-parseh-theme]').click();
    eq((await looks(doc))[2], 'dark', 'the bar\'s ◐ goes on to dark from Light');
    await openGear(doc, 'colours');
    eq(await checked(), 'Dark', 'and Colours, opened again, says Dark');
    // another tab of the same browser (the storage event)
    const second = await open(ctx, 'doc');
    await doc.locator('.topbar [data-parseh-theme]').click();
    await until(async () => (await theme(second)).body === 'sepia', 'the other tab follows');
    eq((await looks(second)), ['sepia', 'sepia', 'sepia'], 'another tab of the same browser follows (the storage event)');
    await second.close();
    await doc.close();
    // the system turning dark under "Follow my device"
    const auto = await context(DESK, {theme: 'auto'});
    const ap = await open(auto, 'doc');
    await ap.emulateMedia({colorScheme: 'light'});
    eq((await theme(ap)).body, 'paper', 'following the system: light is paper');
    await ap.emulateMedia({colorScheme: 'dark'});
    await until(async () => (await theme(ap)).body === 'dark', 'the page follows the system turning dark');
    eq([(await theme(ap)).body, await glyph(ap)], ['dark', ['●']], 'the system turns dark and the page, which follows it, turns with it');
    await ap.close();
    await auto.close();

    // THE COMPUTER BRINGS A NEWER VALUE: set in one browser, read by the next (lib/prefs.js says parseh:pref when it wears one)
    const toldBy = async want => until(async () => ((await (await fetch(B + '/__prefs')).json()).settings.parseh_theme || {}).v === want, 'the computer was told ' + want);
    const one = await context(DESK, {});
    const a = await open(one, 'doc');
    const was = (await theme(a)).stored;                                         // whatever the computer last held
    await a.locator('.topbar [data-parseh-theme]').click();
    const sys = (await theme(a)).stored;
    assert(sys !== was && ['light', 'dark', 'sepia'].includes(sys), `◐ moved the theme on (${was} -> ${sys})`);
    await toldBy(sys);
    assert(true, 'the computer was told what ◐ chose: the device sent it, by lib/prefs.js, which these pages load now');
    const two = await context(DESK, {});                                         // another browser: it knows nothing yet
    const b = await open(two, 'deck');
    await until(async () => (await theme(b)).stored === sys, 'the other browser was told');
    const paint = {light: ['paper', '○'], dark: ['dark', '●'], sepia: ['sepia', '◐']}[sys];
    await until(async () => (await theme(b)).body === paint[0], 'and painted');
    eq([(await theme(b)).body, await glyph(b)], [paint[0], [paint[1]]],
       'another browser, opened later, is painted in the colours the first one chose: the theme follows the person (' + sys + ')');
    // what lib/prefs.js does when it wears a value it brought, said to the page as the toolbox says it: the page reads the key and repaints
    await b.evaluate(() => { localStorage.setItem('parseh_theme', 'sepia'); document.dispatchEvent(new CustomEvent('parseh:pref', {detail: {key: 'parseh_theme', value: 'sepia'}})); });
    await sleep(100);
    eq([(await theme(b)).body, await glyph(b)], ['sepia', ['◐']], 'and a page that is open when parseh:pref is said is repainted at once');
    await b.close(); await a.close();
    await one.close(); await two.close();
    await ctx.close();

    // THE PHONE'S ◐ PAGE (the claim the plan checks): a document in the mobile layout, ◐ on its bar
    const pctx = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const pd = await open(pctx, 'doc');
    const before = await theme(pd);
    await pd.locator('.m-topbar [data-parseh-theme]').tap();
    await sleep(120);
    const after = await theme(pd);
    eq([after.body, after.html, after.stored, await glyph(pd)], ['dark', 'dark', 'dark', ['●']],
       'the phone document\'s ◐: <html> AND <body> (where the studio\'s sheet reads it) AND the glyph');
    assert(after.sheet !== before.sheet && after.page !== before.page, `and the sheet and the page are really repainted (${before.sheet} -> ${after.sheet})`);
    // with the sheet up (it stays up under a tap on the bar): Colours follows ◐ live, and ◐ follows Colours
    await tapOrClick(pd, gearButton(pd));
    await pd.evaluate(() => ParsehGear.mounted().open('colours'));
    const pchecked = () => row(pd, 'colours', 'theme').locator('[role=radio][aria-checked=true]').textContent();
    eq(await pchecked(), 'Dark', 'the phone\'s Colours says Dark');
    await pd.evaluate(() => { document.querySelector('.pg-panel').scrollTop = 0; });
    await pd.locator('.m-topbar [data-parseh-theme]').tap();
    await sleep(150);
    eq([await pchecked(), (await theme(pd)).body], ['Sepia', 'sepia'], 'a tap on the bar\'s ◐ with the sheet up: the sheet\'s Colours follows it at once');
    await tapOrClick(pd, row(pd, 'colours', 'theme').locator('.pg-chip', {hasText: 'Light'}));
    await sleep(100);
    eq([(await theme(pd)).body, await glyph(pd)], ['paper', ['○']], 'and Colours on the sheet repaints the sheet and the page above it, and ◐ shows it');
    await pd.close();
    await pctx.close();
  });

  /* ================================================================================== interface */
  await section('interface', want('interface'), async () => {
    console.log('interface) the switch is in the gear, and the layout changes at once');
    const ctx = await context(DESK, {theme: 'light', mode: 'browser'});
    for (const kind of ['doc', 'deck', 'study', 'cram']) {
      const page = await open(ctx, kind);
      await openGear(page, 'interface');
      const pressed = () => page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=interface] .pg-chip')].map(b => b.textContent + ':' + b.getAttribute('aria-pressed')));
      eq(await pressed(), ['Browser:true', 'Mobile:false'], `${kind}: Interface says Browser`);
      await tapOrClick(page, row(page, 'interface', 'mode').locator('.pg-chip', {hasText: 'Mobile'}));
      await sleep(300);
      eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'), localStorage.getItem('parseh_mode'), document.cookie.includes('parseh_mode=mobile')]),
         ['mobile', 'mobile', true], `${kind}: Mobile: the page changes layout at once, the choice is stored and mirrored in the cookie`);
      const host = await page.evaluate(() => document.querySelector('[data-parseh-gear]').parentElement.className || document.querySelector('[data-parseh-gear]').parentElement.tagName);
      eq(host, kind === 'study' || kind === 'cram' ? 'dk-studyhead' : 'm-topbar',
         `${kind}: and the gear is on the phone's bar now${kind === 'study' || kind === 'cram' ? ' (the title row)' : ''}: ${host}`);
      assert(await page.evaluate(() => document.querySelector('.topbar').getClientRects().length === 0), `${kind}: the browser bar is gone`);
      assert(await page.evaluate(() => ParsehGear.mounted().isOpen()), `${kind}: the panel stayed up through the change`);
      eq(await pressed(), ['Browser:false', 'Mobile:true'], `${kind}: and says Mobile`);
      await openGear(page, 'interface');                 // the popover became the phone's sheet, on its index
      await tapOrClick(page, row(page, 'interface', 'mode').locator('.pg-chip', {hasText: 'Browser'}));
      await sleep(300);
      eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'), localStorage.getItem('parseh_mode'), document.querySelector('[data-parseh-gear]').parentElement.className]),
         ['browser', 'browser', 'bar-tail'], `${kind}: Browser, from the gear on the phone layout: back to the browser's bar`);
      await page.close();
    }
    // the switch is gone from the phone bars of the pages with a gear, and the library's and the decks' list's stay
    const phone = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const sw = page => page.evaluate(() => [...document.querySelectorAll('[data-parseh-mode]')].filter(b => b.getClientRects().length).map(b => b.getAttribute('data-parseh-mode')));
    for (const kind of ['doc', 'deck', 'study', 'cram']) {
      const page = await open(phone, kind);
      eq(await sw(page), [], `${kind}: no Browser | Mobile switch on the phone`);
      await page.close();
    }
    const lib = await phone.newPage();
    await lib.goto(`${B}${S}/`);
    await lib.waitForSelector('.m-topbar');
    eq(await sw(lib), ['browser', 'mobile'], 'the library, which has no gear, keeps its switch');
    eq(await lib.locator('.m-topbar [data-parseh-gear]').count(), 0, 'and has no gear');
    await lib.locator('.m-topbar [data-parseh-theme]').tap();
    await sleep(100);
    eq((await theme(lib)).body, 'dark', 'its ◐ turns the page (one function, the library\'s too)');
    await lib.goto(`${B}/exercises/`);
    await lib.waitForSelector('.m-topbar');
    eq(await sw(lib), ['browser', 'mobile'], 'the decks\' list keeps its switch too');
    eq([await lib.locator('.m-topbar [data-parseh-gear]').count(), (await theme(lib)).body], [0, 'dark'], 'and no gear; and it wears the theme');
    await lib.close();
    await phone.close();
    await ctx.close();
  });

  /* ========================================================================================= phone */
  await section('phone', want('phone'), async () => {
    console.log('phone) the bar is one row, every target 48px; the sheet; the title row');
    for (const W of [320, 360, 390, 430]) {
      const ctx = await context({viewport: {width: W, height: 844}, hasTouch: true, isMobile: true, deviceScaleFactor: 2}, {theme: 'light', mode: 'mobile'});
      for (const kind of ['doc', 'deck']) {
        const page = await open(ctx, kind);
        const bar = await page.evaluate(() => {
          const b = document.querySelector('.m-topbar'), r = b.getBoundingClientRect();
          const items = [...b.querySelectorAll('a, button')].filter(e => e.getClientRects().length).map(e => {
            const q = e.getBoundingClientRect();
            return {id: e.getAttribute('data-parseh-gear') !== null ? 'gear' : e.getAttribute('data-parseh-theme') !== null ? 'theme' : e.className.split(' ')[0],
                    w: Math.round(q.width), h: Math.round(q.height), l: Math.round(q.left), r: Math.round(q.right), t: Math.round(q.top)};
          });
          return {h: Math.round(r.height), top: Math.round(r.top), items, sideways: document.documentElement.scrollWidth - innerWidth};
        });
        const tops = new Set(bar.items.map(i => i.t));
        assert(bar.items.length >= 4 && bar.items.some(i => i.id === 'gear') && bar.items.some(i => i.id === 'theme') && bar.items.some(i => i.id === 'px-ask'),
               `${W}px ${kind}: the bar has the way home, the way up, ◐, ⚙ and the ? (${bar.items.map(i => i.id)})`);
        assert(bar.items.every(i => i.w >= 48 && i.h >= 48), `${W}px ${kind}: every target is 48px or more (${bar.items.map(i => i.id + ' ' + i.w + 'x' + i.h)})`);
        assert(bar.h <= 64 && tops.size === 1, `${W}px ${kind}: the bar is ONE row (${bar.h}px high, items at ${[...tops]})`);
        assert(bar.items.every(i => i.l >= 0 && i.r <= W) && bar.sideways <= 0, `${W}px ${kind}: nothing leaves the screen (${bar.items.map(i => i.l + '-' + i.r)}, sideways ${bar.sideways})`);
        const order = bar.items.map(i => i.id);
        assert(order.indexOf('theme') < order.indexOf('gear'), `${W}px ${kind}: ⚙ comes after ◐ (${order})`);
        await page.close();
      }
      for (const kind of ['study', 'cram']) {
        const page = await open(ctx, kind);
        const head = await page.evaluate(() => {
          const g = document.querySelector('[data-parseh-gear]').getBoundingClientRect(), h = document.querySelector('.dk-studyhead').getBoundingClientRect(),
                t = document.querySelector('.dk-studyhead .dk-title').getBoundingClientRect(), back = document.querySelector('.dk-studyhead .m-back').getBoundingClientRect();
          return {gear: [Math.round(g.width), Math.round(g.height), Math.round(g.left), Math.round(g.right)], in: document.querySelector('[data-parseh-gear]').parentElement.className,
                  title: [Math.round(t.left), Math.round(t.right)], back: [Math.round(back.width), Math.round(back.height)], bar: !!document.querySelector('.m-topbar'),
                  sideways: document.documentElement.scrollWidth - innerWidth, row: Math.round(h.height), headTop: [Math.round(g.top), Math.round(t.top)]};
        });
        assert(head.in === 'dk-studyhead' && head.gear[0] >= 48 && head.gear[1] >= 48 && head.gear[3] <= W && head.title[1] <= head.gear[2] + 1 && !head.bar && head.sideways <= 0,
               `${W}px ${kind}: no bar over the exercise; the gear is in the title's row, 48px, clear of the title and on the screen (${JSON.stringify(head)})`);
        await page.close();
      }
      await ctx.close();
    }
    // THE INDEX of each page that has a phone layout: the themes it offers, each with what it is set to
    const ictx = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const THEMES = {doc: ['text', 'exercises', 'page', 'zoom', 'colours', 'interface'], deck: ['text', 'exercises', 'zoom', 'colours', 'interface'],
                    study: ['text', 'exercises', 'zoom', 'colours', 'interface'], cram: ['text', 'exercises', 'zoom', 'colours', 'interface']};
    for (const kind of ['doc', 'deck', 'study', 'cram']) {
      const page = await open(ictx, kind);
      await tapOrClick(page, gearButton(page));
      await until(() => page.evaluate(() => !document.querySelector('.pg-panel').hidden), `the sheet on ${kind}`);
      await sleep(400);
      const idx = await page.evaluate(() => [...document.querySelectorAll('.pg-panel .pg-irow')].filter(r => r.getClientRects().length).map(r =>
        [r.dataset.pgIndex, r.querySelector('.pg-iname').textContent, r.querySelector('.pg-isum').textContent, Math.round(r.getBoundingClientRect().height)]));
      console.log(`  ${kind} index:`, JSON.stringify(idx));
      eq(idx.map(r => r[0]), THEMES[kind], `${kind}: the index lists the page's themes, in order`);
      assert(idx.every(r => r[3] >= 48), `${kind}: each row a finger high`);
      const fits = await page.evaluate(() => { const b = document.querySelector('.pg-panel .pg-body').getBoundingClientRect();
        return [...document.querySelectorAll('.pg-panel .pg-irow')].filter(r => r.getClientRects().length).every(r => { const q = r.getBoundingClientRect(); return q.top >= b.top - 0.5 && q.bottom <= b.bottom + 0.5; }); });
      eq(fits, true, `${kind}: and all of them are in the half sheet with no scrolling`);
      const said = Object.fromEntries(idx.map(r => [r[0], r[2]]));
      assert(/^\S+( \S+)* text \d\.\d\d×$/.test(said.text), `${kind}: Text says the first slider's value: "${said.text}"`);
      eq([said.zoom, said.colours, said.interface], ['100 %', 'Light', 'Mobile pages'], `${kind}: Zoom, Colours and Interface`);
      await shot(page, `phone-index-${kind}`);
      await page.close();
    }
    await ictx.close();
    // the sheet, on the phone document page: half the screen, the text visible above it, and a tap on a row changes the page
    const ctx = await context(PHONE, {theme: 'light', mode: 'mobile'});
    const doc = await open(ctx, 'doc');
    await tapOrClick(doc, gearButton(doc));
    await until(() => doc.evaluate(() => !document.querySelector('.pg-panel').hidden), 'the sheet');
    await sleep(500);                                              // it rises over a sixth of a second: measured when it has risen
    const sh = await doc.evaluate(() => { const r = document.querySelector('.pg-panel').getBoundingClientRect(); return {top: Math.round(r.top), h: Math.round(r.height), bottom: Math.round(r.bottom), sheet: document.querySelector('.pg-panel').classList.contains('pg-sheet')}; });
    assert(sh.sheet && sh.bottom === 844 && sh.h >= 400 && sh.h <= 520, `the gear on a phone is one sheet from the foot, about half the screen (${JSON.stringify(sh)})`);
    await doc.evaluate(() => ParsehGear.mounted().open('text'));
    await sleep(200);
    const tall = await doc.evaluate(() => [...document.querySelectorAll('.pg-panel .pg-row')].filter(r => !r.hidden && r.getClientRects().length).map(r => Math.round(r.getBoundingClientRect().height)).every(h => h >= 48));
    assert(tall, 'every row of the theme on stage is 48px or taller');
    await setRange(doc, 'text', 'fa', 2.4);
    eq((await sheetVars(doc)).fa, 2.4, 'a slider moved on the sheet changes the text above it');
    const above = await doc.evaluate(() => { const e = document.elementFromPoint(195, 200); return !!e && !e.closest('.pg-panel'); });
    assert(above, 'and the page above the sheet is the page\'s own, still there to read');
    // the bars, on a phone: the phone's own bar goes with the toolbar, so the corner's way back is not over ◐ and ⚙
    await doc.evaluate(() => ParsehGear.mounted().open('page'));
    await sleep(150);
    await flipSwitch(doc, 'page', 'bars');
    await sleep(150);
    const away = await doc.evaluate(() => ({bar: !!document.querySelector('.m-topbar').getClientRects().length, tool: !!document.querySelector('#typobar').getClientRects().length,
                                            show: !!document.querySelector('#btn-bars-show').getClientRects().length}));
    eq(away, {bar: false, tool: false, show: true}, 'Hide the bars on a phone puts away the phone\'s bar and the toolbar, and leaves the way back in the corner (where nothing else is)');
    await doc.locator('.pg-panel .pg-x').tap();
    await doc.locator('#btn-bars-show').tap();
    await sleep(200);
    eq(await doc.evaluate(() => [!!document.querySelector('.m-topbar').getClientRects().length, !!document.querySelector('[data-parseh-gear]').getClientRects().length]),
       [true, true], 'and the corner button brings them back, the gear with them');
    await doc.close();
    await ctx.close();
  });

  /* ======================================================================================= widths */
  await section('widths', want('widths'), async () => {
    console.log('widths) the bars, the gear and the panel stay on the screen from 320 to 1280, on the five pages');
    // WHAT IS STRICT IS THE CHROME this lane put on the pages -- the bars, ◐, the gear, the panel: each of them inside
    // the window.  What the pages hold (a flashcard's head at 320px, a long word) is not this lane's, and is told as a note
    // when it makes the page wider than the window, with who stands past the edge, so that it is seen and not hidden.
    const ctx = await context(DESK, {theme: 'light'});
    const WHERE = [['doc', other, 'article.sheet p'], ['edit', other, '#sheet p'], ['deck', flashDeck, null], ['study', plainDeck, '.exercise'], ['cram', plainDeck, '.exercise']];
    const pages = {};
    for (const [kind, arg, ready] of WHERE) pages[kind] = await open(ctx, kind, arg, {ready});
    const MEASURE = () => {
      const label = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '');
      // the bars and what stands in them (the row of the document's bar, which scrolls inside itself, keeps what is in it:
      // but its last two, ◐ and ⚙, are pinned over its end and must be seen)
      const chrome = [...document.querySelectorAll('.topbar, .topbar > *, .m-topbar, .m-topbar > *, .toolbar, .toolbar > *, .metabar, .dk-studyhead, .dk-studyhead > *, .bar-tail, .bar-tail > *, [data-parseh-gear], [data-parseh-theme], .pg-panel')]
        .filter(e => e.getClientRects().length && (!e.closest('.topbar-actions') || e.closest('.bar-tail') || e.matches('.bar-tail')))
        .filter(e => { const r = e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; }).map(label);
      const over = document.documentElement.scrollWidth - innerWidth;
      const who = [...document.querySelectorAll('body *')].filter(e => e.getClientRects().length && !e.closest('.topbar-actions, .pg-panel'))
        .map(e => [e, e.getBoundingClientRect().right]).filter(([e, r]) => r > innerWidth + 1).sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([e, r]) => label(e) + ' ' + Math.round(r));
      const g = document.querySelector('[data-parseh-gear]'), r = g.getBoundingClientRect();
      return {chrome, over, who, gear: [Math.round(r.left), Math.round(r.right), r.width > 0]};
    };
    const notes = [];
    for (const W of [320, 360, 390, 430, 561, 800, 1280]) {
      const bad = [];
      for (const [kind] of WHERE) {
        const page = pages[kind];
        await page.setViewportSize({width: W, height: 800});
        await sleep(150);
        const o = await page.evaluate(MEASURE);
        if (o.chrome.length) bad.push(`${kind}: ${o.chrome.join(', ')}`);
        if (!(o.gear[2] && o.gear[0] >= 0 && o.gear[1] <= W)) bad.push(`${kind} gear ${o.gear}`);
        if (o.over > 0) notes.push(`${W}px ${kind} +${o.over} (${o.who.join(', ')})`);
      }
      assert(!bad.length, `${W}px, browser layout: every bar, ◐ and ⚙ is inside the window (${bad.join('; ') || 'all five'})`);
    }
    // with the gear open, the popover or the sheet is inside the window too, and does not widen the page
    for (const W of [320, 390, 800, 1280]) {
      const bad = [];
      for (const [kind] of WHERE) {
        const page = pages[kind];
        await page.setViewportSize({width: W, height: 800});
        await openGear(page);
        await sleep(300);
        const o = await page.evaluate(MEASURE);
        if (o.chrome.length) bad.push(`${kind}: ${o.chrome.join(', ')}`);
        await closeGear(page);
      }
      assert(!bad.length, `${W}px, browser layout: and with the gear open the panel is inside the window (${bad.join('; ') || 'all five'})`);
    }
    // and the lesson, with its flashcard and its headword, as a thing to know
    const lessonPage = await open(ctx, 'doc');
    await lessonPage.setViewportSize({width: 320, height: 800});
    await sleep(150);
    const lesson320 = await lessonPage.evaluate(MEASURE);
    if (lesson320.over > 0) notes.push(`320px the gear lesson (a flashcard, a headword) +${lesson320.over} (${lesson320.who.join(', ')})`);
    await lessonPage.close();
    for (const [kind] of WHERE) await pages[kind].close();
    await ctx.close();
    const phone = await context(DESK, {theme: 'light', mode: 'mobile'});
    const mp = {};
    for (const [kind, arg, ready] of WHERE.filter(w => w[0] !== 'edit')) mp[kind] = await open(phone, kind, arg, {ready});
    for (const W of [320, 360, 390, 430, 561, 800, 1280]) {
      const bad = [];
      for (const kind of Object.keys(mp)) {
        await mp[kind].setViewportSize({width: W, height: 800});
        await sleep(150);
        const o = await mp[kind].evaluate(MEASURE);
        if (o.chrome.length) bad.push(`${kind}: ${o.chrome.join(', ')}`);
        if (o.over > 0) notes.push(`${W}px mobile ${kind} +${o.over} (${o.who.join(', ')})`);
      }
      assert(!bad.length, `${W}px, mobile layout: every bar and the gear is inside the window (${bad.join('; ') || 'all four'})`);
    }
    for (const kind of Object.keys(mp)) await mp[kind].close();
    await phone.close();
    console.log(notes.length ? '  (notes: the page itself is wider than the window at: ' + notes.join(' | ') + ')'
                             : '  (and no page, in either layout, is wider than the window at any of these widths)');
  });

  /* ========================================================================================= zoom */
  await section('zoom', want('zoom'), async () => {
    console.log('zoom) with the zoom module in place, the Zoom group stands where the plan says');
    const ctx = await context(DESK, {theme: 'light', zoom: true});
    const GROUPS = {doc: ['text', 'exercises', 'page', 'zoom', 'colours', 'interface'], edit: ['text', 'zoom', 'colours', 'editor'],
                    deck: ['text', 'exercises', 'zoom', 'colours', 'interface'], study: ['text', 'exercises', 'zoom', 'colours', 'interface'],
                    cram: ['text', 'exercises', 'zoom', 'colours', 'interface']};
    for (const kind of KINDS) {
      const page = await open(ctx, kind);
      await openGear(page);
      eq(await groupsOf(page), GROUPS[kind], `${kind}: with a ParsehZoom the groups are the plan's, Zoom after Page and before Colours`);
      await page.close();
    }
    await ctx.close();
  });

  /* ========================================================================================= alone */
  await section('alone', want('alone'), async () => {
    console.log('alone) the studio run alone: the gear\'s two files are answered for, the page works, the theme is not said to follow a person');
    const alone = await startHarness('studio');
    const A = `http://127.0.0.1:${alone.info.port}`;
    try {
      const id = (await (await fetch(A + '/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({markdown: LESSON})})).json()).meta.id;
      for (const f of ['/lib/pagesettings.js', '/lib/pagesettings.css']) {
        const r = await fetch(A + f);
        assert(r.ok && (await r.text()).length > 1000, `the studio alone answers ${f}`);
      }
      const ctx = await context(DESK, {theme: 'light'});
      const page = await ctx.newPage();
      watch(page, 'alone');
      await page.goto(`${A}/doc/${id}`);
      await page.waitForSelector('article.sheet .exercise');
      await page.waitForSelector('[data-parseh-gear]', {state: 'attached'});
      await page.locator('#btn-typo').click();
      await sleep(200);
      // the studio alone answers the zoom module too (the pages carry its tag), so the Zoom group is there, and it is the
      // real one: a step taken in it zooms the page, and the step back puts the page as it was
      eq(await groupsOf(page), ['text', 'exercises', 'page', 'zoom', 'colours', 'interface'], 'the document has its gear without the toolbox');
      await page.locator('.pg-panel [data-pg-group=zoom] .pg-stepbtn[aria-label=Increase]').click();
      eq(await page.evaluate(() => ParsehZoom.applied()), 110, 'the Zoom group\'s + takes the whole page to 110 %');
      await page.locator('.pg-panel [data-pg-group=zoom] .pg-stepbtn[aria-label=Decrease]').click();
      eq(await page.evaluate(() => [ParsehZoom.applied(), ParsehZoom.factor()]), [100, 1], 'and its − takes it back to 100 %, with nothing replaced');
      await setRange(page, 'text', 'fa', 2);
      eq((await sheetVars(page)).fa, 2, 'and its sliders move the sheet');
      eq(await page.locator('.pg-panel [data-pg-group=colours] .pg-caption').textContent(), 'Saved on this device.',
         'the theme is said to stay on this device (nothing carries it to another here)');
      eq(await page.locator('.pg-panel .pg-footlink').count(), 0, 'and there is no link to the toolbox\'s own settings, which are not here');
      await page.locator('.topbar [data-parseh-theme]').click({force: true});
      eq((await theme(page)).body, 'dark', 'and ◐ turns it');
      await page.close();
      await ctx.close();
    } finally {
      try { alone.proc.kill('SIGTERM'); } catch (_) { /* gone */ }
      await alone.proc.status;
    }
  });

  /* ========================================================================================= shots */
  await section('shots', SHOTS && want('shots'), async () => {
    console.log('shots) the pages, the panel on each of its groups, wide and on a phone, in the three themes');
    for (const th of ['light', 'dark', 'sepia']) {
      const desk = await context(DESK, {theme: th});
      for (const kind of KINDS) {
        const page = await open(desk, kind);
        await shot(page, `${kind}-wide-${th}`);
        await openGear(page);
        const groups = await groupsOf(page);
        for (const g of groups) {
          await page.evaluate(g => ParsehGear.mounted().open(g), g);
          await sleep(150);
          if (th === 'light' || g === 'text') await shot(page, `${kind}-wide-${th}-gear-${g}`);
        }
        await page.close();
      }
      await desk.close();
      const phone = await context(PHONE, {theme: th, mode: 'mobile'});
      for (const kind of ['doc', 'deck', 'study', 'cram']) {
        const page = await open(phone, kind);
        await shot(page, `${kind}-phone-${th}`);
        await tapOrClick(page, gearButton(page));
        await sleep(300);
        for (const g of await groupsOf(page)) {
          await page.evaluate(g => ParsehGear.mounted().open(g), g);
          await sleep(150);
          if (th === 'light' || g === 'text') await shot(page, `${kind}-phone-${th}-gear-${g}`);
        }
        await page.close();
      }
      await phone.close();
    }
  });

  if (errors.length) { failures.push('errors'); console.log('  FAILED: page errors or console errors: ' + errors.slice(0, 3).join(' | ')); }
  else { passed++; console.log('  ok no page errors, no console errors on any page'); }
  if (failures.length) { console.log(`\ngear studio FAILED in ${failures.join(', ')} (${passed} checks passed)`); Deno.exitCode = 1; }
  else console.log(`\ngear studio passed (${passed} checks)`);
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) { /* gone */ }
  await proc.status;
}
