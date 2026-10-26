// SPDX-License-Identifier: GPL-3.0-or-later
import {chromium} from 'npm:playwright-core@1.52.0';
import {gearOpen, gearClose, gearUp, gearRow, gearReach} from './gear_driver.mjs';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/gear_reader.mjs
//      GEAR_READER_SHOTS=<dir>   saves the screenshots this suite looks at (the header, the gear on every group,
//                                wide and on a phone, in the three themes, a right-to-left book, an old reader)
//      GEAR_READER_ONLY=a,b      runs only those sections (a development aid): built, wide, listening, marks,
//                                phone, keys, names, old, widths, look
//
// THE BOOK READER'S GEAR (a0.5.0, plan §2, §3, §4, §6 "Book"): lib/gear-reader.js on the toolkit
// (lib/pagesettings.js), driven where a person meets it -- built readers served by the REAL hub over a temporary
// toolbox (tests/mobile_harness.py's tree, plus a three-chapter Persian and Arabic book and readers made OLD),
// in a real Chromium, with a mouse at 1280x800 and with a finger at 390x844.  The reader's own controls stay in
// the DOM, so every row is shown to change the real control AND the real page, and to change back.
//
//  built)     what the BUILD writes for a new reader (lib/tex2html.py): the levels' names on the buttons and never
//             a digit, the caption "levels", the header's new words, the hover tooltip's names, "keep going" kept
//  wide)      the gear in the browser layout, on the Persian book: the button at the end of the first row, the
//             popover, the groups this book has; every row of Levels & reading (the ticks, the names -- their
//             limit, the page's buttons and the tooltip following, emptied = the registry's again --, glosses,
//             hover and what it rests, hide the bars), Looking a word up, Text (the very sliders of Aa, the same
//             bk_typo, reset; Aa opens the gear at Text and shuts it), Colours, Interface
//  listening) the narrated English book: speed, skip, keep going, repeat, the pause between repeats, wait at
//             each new chapter, listen on its own (and "highlight" / "keep in view" drawn only while it is on),
//             pause while a gloss is open: each changes the page's own control and the page, and back
//  marks)     Diacritics in Persian and Arabic: levels 1 and 2 bare, level 3 as it was, the cloud and its gloss
//             and the highlight where they were, a copy and a card carrying the vowelled text, a chapter fetched
//             afterwards bare too, a reload keeping it, and the page restored node for node
//  phone)     390x844 with a finger: the first line is the hub, the shelf, the contents, Aa and the gear (no ⋯),
//             the sheet is half the window with the text above it and opens on the INDEX of the themes with what
//             each is set to (all seven in view), Aa lands on Text and a second press shuts it, a theme's rows a
//             finger high, the Keep row only while its theme is on stage, closed by ✕, Esc and the back gesture
//             (which leaves a theme first), the listening line while listen is on, and the index on a Persian,
//             a Japanese and a Chinese book
//  keys)      a device's keys survive a reload and stay on the device; the person's (speed, skip, the pause between
//             repeats, wait at a change, keep going, the levels' names, the theme) cross to another browser
//             context through the one server; a rename shows in the other
//  names)     the levels' names on the buttons, in their tooltips, in the gear and in hover mode's tooltip, in
//             Persian and Arabic (right to left), Japanese, Chinese, English and Hindi
//  old)       a reader BUILT BEFORE a0.5.0 (digits on its buttons, the old words, a language record without
//             names, no bk_cont) gains the gear, the names, "keep going" kept and Diacritics with no rebuild
//  widths)    nothing scrolls sideways from 320 to 1280, the gear shut and open
//  look)      the screenshots, and the sheet over everything it must be over
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('GEAR_READER_SHOTS') || '';
const ONLY = (Deno.env.get('GEAR_READER_ONLY') || '').split(',').filter(Boolean);
const want = name => !ONLY.length || ONLY.includes(name);
if (SHOTS) await Deno.mkdir(SHOTS, {recursive: true});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, wanted, m) => assert(same(got, wanted),
  `${m} -- got ${JSON.stringify(got)}${same(got, wanted) ? '' : ', wanted ' + JSON.stringify(wanted)}`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(page, fn, arg, what, timeout = 8000) {
  for (const t = Date.now();;) {
    const v = await page.evaluate(fn, arg);
    if (v) return v;
    if (Date.now() - t > timeout) throw Error('FAIL: waited in vain for ' + what);
    await sleep(100);
  }
}
const run = async (args, opts = {}) => {
  const o = await new Deno.Command(args[0], {args: args.slice(1), stdout: 'piped', stderr: 'piped', ...opts}).output();
  if (!o.success) throw Error(td.decode(o.stderr) || td.decode(o.stdout));
  return td.decode(o.stdout);
};
const py = (code, ...args) => run([PY, '-c', code, ...args]);

/* ================================================================== the toolbox */
const WORK = await Deno.makeTempDir({prefix: 'parseh-gear-reader-'});
const MADE = JSON.parse((await run([PY, 'tests/mobile_harness.py', 'build', WORK])).trim().split('\n').pop());
const BOOKS = `${WORK}/root/books`;

// A THREE-CHAPTER BOOK in each right-to-left language (the same paragraphs renumbered into chapters 2 and 3), for
// the chapters that arrive when they are asked for (lib/tex2html.py, one_chapter_at_a_time); and the English and
// Persian readers made OLD: what a build of before a0.5.0 wrote, which the layer has to dress on its own.
await py(String.raw`
import io, os, shutil, sys
from pathlib import Path
sys.path.insert(0, 'tests')
import mobile_harness
books = sys.argv[1]
for folder, slug, src in (('persian', 'lazy-fa', 'persian/mini-fa'), ('arabic', 'lazy-ar', 'arabic/mini-ar')):
    d = os.path.join(books, folder, slug)
    shutil.copytree('tests/fixtures/books/' + src, d, ignore=shutil.ignore_patterns('reader', '.reader-key'))
    ch1 = io.open(os.path.join(d, 'ch1.tex'), encoding='utf-8').read()
    for n in (2, 3):
        part = (ch1.replace('\\chapopen{1}', '\\chapopen{%d}' % n).replace('\\parstart{1.', '\\parstart{%d.' % n)
                   .replace('\\parnum{1.', '\\parnum{%d.' % n))
        io.open(os.path.join(d, 'ch%d.tex' % n), 'w', encoding='utf-8').write(part)
    m = os.path.join(d, 'main.tex')
    s = io.open(m, encoding='utf-8').read()
    assert '\\input{ch1.tex}' in s
    io.open(m, 'w', encoding='utf-8').write(s.replace('\\input{ch1.tex}', '\\input{ch1.tex}\n\\input{ch2.tex}\n\\input{ch3.tex}'))
    mobile_harness.built_reader(Path(d))
# the two old ones start as copies of a built book (the recording of the English one comes along)
for folder, slug, src in (('persian', 'old-fa', 'persian/mini-fa'), ('english', 'old-en', 'english/mini-en')):
    shutil.copytree(os.path.join(books, src), os.path.join(books, folder, slug))
`, BOOKS);

/* WHAT A BUILD OF BEFORE a0.5.0 WROTE, made out of what this build writes: the language record embedded without the
   passes' names and with other sentences, the digits on the level buttons and the old caption, the old words of the
   header, and no bk_cont in the page's script.  Each change is asserted, so that a build that stops writing what
   this undoes cannot make the test pass for nothing. */
function downgrade(html) {
  let h = html, L = null;
  const swap = (a, b) => { if (!h.includes(a)) throw Error('downgrade: not in the page: ' + a.slice(0, 60)); h = h.replace(a, b); };
  h = h.replace(/const LANG=(\{.*?\});const GLOSS=/s, (m, j) => {
    L = JSON.parse(j);
    L.passes.forEach(p => { delete p.name; p.title = 'the old wording of ' + p.key; });
    return 'const LANG=' + JSON.stringify(L) + ';const GLOSS=';
  });
  if (!L) throw Error('downgrade: no language record');
  let i = 0;
  h = h.replace(/<button data-toggle="(no\d)" title="[^"]*">[^<]*<\/button>/g, (m, t) =>
    `<button data-toggle="${t}" title="${L.passes[i].title}">${L.passes[i++].label}</button>`);
  if (!i) throw Error('downgrade: no level buttons');
  swap('<span class="pgrpc">levels</span>', '<span class="pgrpc">which passes you see</span>');
  swap('>keep going</button>', '>continuous</button>');
  if (h.includes('>highlight</button>')) swap('>highlight</button>', '>follow</button>');
  if (h.includes('>keep in view</button>')) swap('>keep in view</button>', '>scroll to it</button>');
  swap('between repeats\n', 'gap\n');
  swap('&#8963; hide bars</button>', '&#8963; bars</button>');
  swap('&#8964; show bars</button>', '&#8964; bars</button>');
  swap("cont = localStorage.getItem('bk_cont') !== '0';\n", '');
  swap("\n  localStorage.setItem('bk_cont', cont ? '1' : '0'); };", ' };');
  swap('<b>the first level only</b>', '<b>pass 1 only</b>');
  h = h.replace(/title="the text alone \(the levels? [^)]*\), the glosses/, 'title="the text alone (passes 1 and 3), the glosses');
  return h;
}
for (const [slug, folder] of [['old-fa', 'persian'], ['old-en', 'english']]) {
  const p = `${BOOKS}/${folder}/${slug}/reader/index.html`;
  await Deno.writeTextFile(p, downgrade(await Deno.readTextFile(p)));
}

const port = await (async () => { const l = Deno.listen({hostname: '127.0.0.1', port: 0}); const p = l.addr.port; l.close(); return p; })();
const hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], stdout: 'null', stderr: 'null'}).spawn();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 60000) throw Error('the hub did not start');
  await sleep(250);
}
const READERS = {...MADE.readers, 'lazy-fa': '/books/persian/lazy-fa/reader/', 'lazy-ar': '/books/arabic/lazy-ar/reader/',
                 'old-fa': '/books/persian/old-fa/reader/', 'old-en': '/books/english/old-en/reader/'};
// what the toolbox keeps for the person, put back to the usual between sections (every page the suite opens
// asks for it at load, and a value one section left would be worn by the next)
async function resetPrefs() {
  const at = Date.now() / 1000;
  const keys = {bk_rate: '1', bk_gap: '0', bk_skip: '10', bk_stopbnd: '0', bk_cont: '1', parseh_theme: 'auto'};
  for (const c of ['fa', 'ar', 'it', 'ja', 'fr', 'de', 'tr', 'en', 'hi', 'es', 'zh'])
    for (const k of ['vocal', 'chunks', 'bare', 'alt', 'aloud']) keys[`bk_lvl:${c}:${k}`] = '';
  const settings = {};
  for (const [k, v] of Object.entries(keys)) settings[k] = {v, at};
  const r = await fetch(B + '/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                          body: JSON.stringify({by: 'the test', settings})});
  await r.body?.cancel();
  await sleep(60);
}
const serverPrefs = async () => (await (await fetch(B + '/__prefs')).json()).settings || {};

const DESK = {viewport: {width: 1280, height: 800}};
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, deviceScaleFactor: 2};
const errors = [];
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
async function newPage(opts, tag, init) {
  const ctx = await browser.newContext(opts);
  if (init) await ctx.addInitScript(init);
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push(tag + ': ' + e.message); console.log('PAGE ERROR', tag, e.message); });
  if (opts.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  return page;
}
const MOBILE_MODE = () => { localStorage.setItem('parseh_mode', 'mobile'); document.cookie = 'parseh_mode=mobile; Path=/; SameSite=Lax; Max-Age=31536000'; };
const tap = async (page, sel) => { const l = page.locator(sel).first(); if (page.touch) await l.tap(); else await l.click(); };
async function open(page, code, {skipAsk = true} = {}) {
  await page.goto(B + READERS[code], {waitUntil: 'load'});
  await page.waitForSelector('[data-parseh-gear]', {state: 'attached', timeout: 15000});
  await sleep(350);
  if (skipAsk && await page.$('.pf-bar')) await tap(page, '.pf-stay');
}
const shot = async (page, name) => { if (SHOTS) await page.screenshot({path: `${SHOTS}/${name}.png`}); };
const isDrawn = (page, sel) => page.evaluate(sel => [...document.querySelectorAll(sel)]
  .some(e => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden'), sel);
const ls = (page, k) => page.evaluate(k => localStorage.getItem(k), k);
const registry = JSON.parse(await Deno.readTextFile('lib/languages.json'));
const levelsOf = code => registry[code].passes;                 // [{key, name, label, title}]
const NUM = {vocal: 1, chunks: 2, bare: 3, alt: 4, aloud: 5};
const rowText = (page, id) => page.evaluate(id => {
  const r = document.querySelector(`.pg-panel [data-pg-row="${id}"]`);
  return r ? {name: (r.querySelector('.pg-nametext') || {}).textContent || '', help: (r.querySelector('.pg-help') || {}).textContent || '',
              why: (r.querySelector('.pg-why') || {}).hidden === false ? r.querySelector('.pg-why').textContent : '', hidden: r.hidden} : null;
}, id);
// the header's drawn controls in the order they are seen: line by line, then left to right
const firstLine = page => page.evaluate(() => [...document.querySelectorAll('header a[href], header button, header select, header input, header label[for]')].filter(e => e.getClientRects().length > 0)
  .map(e => ({n: e.id || (e.hasAttribute('data-parseh-gear') ? 'gear' : e.classList.contains('home') ? (e.classList.contains('glyph') ? 'hub' : 'shelf') : e.className),
              t: Math.round(e.getBoundingClientRect().top), l: e.getBoundingClientRect().left}))
  .sort((a, b) => a.t - b.t || a.l - b.l));
const switchOn = (page, id) => page.evaluate(id => document.querySelector(`.pg-panel [data-pg-row="${id}"] button.pg-switch`).getAttribute('aria-checked') === 'true', id);
const selectDisabled = (page, id) => page.evaluate(id => document.querySelector(`.pg-panel [data-pg-row="${id}"] select`).disabled, id);
const switchDisabled = (page, id) => page.evaluate(id => document.querySelector(`.pg-panel [data-pg-row="${id}"] button.pg-switch`).disabled, id);
async function flip(page, id) {
  await gearReach(page, id);                    // on the phone's sheet the row's theme is entered first
  const sw = gearRow(page, id).locator('button.pg-switch');
  await sw.scrollIntoViewIfNeeded();
  if (page.touch) await sw.tap(); else await sw.click();
  await sleep(120);
}
async function pick(page, id, label) {
  await gearReach(page, id);
  const s = gearRow(page, id).locator('select.pg-select');
  await s.scrollIntoViewIfNeeded();
  await s.selectOption({label});
  await sleep(120);
}

try {
  /* =================================================================== built */
  if (want('built')) {
    console.log('\nbuilt) what the build writes for a new reader');
    for (const code of ['en', 'fa', 'ar', 'ja', 'hi', 'zh']) {
      const html = await Deno.readTextFile(`${BOOKS}${READERS[code].replace('/books', '')}index.html`);
      for (const p of levelsOf(code)) {
        const t = `<button data-toggle="no${NUM[p.key]}" title="${p.title}">${p.name}</button>`;
        assert(html.includes(t), `${code}: the ${p.key} button wears its name, ${JSON.stringify(p.name)}, and says what it shows`);
      }
      assert(!/<button data-toggle="no\d"[^>]*>\d<\/button>/.test(html), `${code}: no level button says a digit`);
      assert(html.includes('<span class="pgrpc">levels</span>') && !html.includes('which passes you see'),
             `${code}: the caption under them is "levels"`);
      const keep = levelsOf(code).filter(p => ['vocal', 'aloud', 'bare'].includes(p.key)).map(p => p.name);
      const said = keep.length < 3 ? keep.join(' and ') : keep.slice(0, -1).join(', ') + ' and ' + keep.at(-1);
      assert(html.includes(`title="the text alone (the level${keep.length > 1 ? 's' : ''} ${said}), the glosses in a hover cloud over it (H)"`),
             `${code}: hover mode's tooltip names the text levels it keeps (${said})`);
      assert(!/passes? \d/.test(html.slice(html.indexOf('<header'), html.indexOf('</header>'))), `${code}: no pass number in the header`);
    }
    const en = await Deno.readTextFile(`${BOOKS}/english/mini-en/reader/index.html`);
    for (const w of ['>keep going</button>', '>highlight</button>', '>keep in view</button>', 'between repeats\n', '&#8963; hide bars</button>', '&#8964; show bars</button>'])
      assert(en.includes(w), `the header says ${JSON.stringify(w.replace(/\n/g, ' ').replace(/<\/button>/, ''))}`);
    for (const w of ['>continuous</button>', '>follow</button>', '>scroll to it</button>', '&#8963; bars</button>', '&#8964; bars</button>'])
      assert(!en.includes(w), `and no longer ${JSON.stringify(w)}`);
    assert(en.includes("cont = localStorage.getItem('bk_cont') !== '0';") && en.includes("localStorage.setItem('bk_cont', cont ? '1' : '0');"),
           '"keep going" is read at load and written at every press, under bk_cont');
    assert(en.includes('<b>the first level only</b>'), 'and the chunk editor\'s note names no pass number');
  }

  /* ===================================================================== wide */
  if (want('wide')) {
    console.log('\nwide) the gear in the browser layout, on the Persian book');
    await resetPrefs();
    const page = await newPage(DESK, 'wide');
    await open(page, 'fa');
    const g = await page.evaluate(() => {
      const b = document.querySelector('[data-parseh-gear]'), row = document.querySelector('header .hrow');
      const r = b.getBoundingClientRect();
      return {last: row.lastElementChild === b || [...row.children].filter(c => c.getClientRects().length).pop() === b,
              text: b.textContent, label: b.getAttribute('aria-label'), up: b.getAttribute('aria-expanded'),
              pgReader: document.documentElement.classList.contains('pg-reader'), w: r.width, h: r.height, top: r.top};
    });
    eq([g.last, g.text, g.label, g.up, g.pgReader], [true, '\u2699page', 'Settings of this page', 'false', true],
       'the button ends the first row of the header: a gear and the word "page"');
    await shot(page, 'wide-header');
    await gearOpen(page);
    const pop = await page.evaluate(() => {
      const p = document.querySelector('.pg-panel'), b = document.querySelector('[data-parseh-gear]');
      const r = p.getBoundingClientRect(), br = b.getBoundingClientRect();
      return {popover: p.classList.contains('pg-popover'), under: r.top >= br.bottom - 1, inside: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
              expanded: b.getAttribute('aria-expanded'), title: p.querySelector('.pg-title').textContent};
    });
    eq(pop, {popover: true, under: true, inside: true, expanded: 'true', title: 'This page'}, 'it opens a popover under the button, inside the window');
    eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group]')].filter(g => !g.hidden)
                             .map(g => g.dataset.pgGroup).filter(g => g !== 'zoom')),
       ['levels', 'looking', 'text', 'colours', 'interface'], 'the groups of this book: no Listening, there being no recording to listen to');

    // ---- the levels
    const items = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-row=levels] .pg-lv')].map(li => ({
      key: li.dataset.pgLevel, name: li.querySelector('.pg-lvname').value, help: li.querySelector('.pg-lvhelp').textContent,
      checked: li.querySelector('input[type=checkbox]').checked})));
    eq(items.map(i => [i.key, i.name, i.help, i.checked]), levelsOf('fa').map(p => [p.key, p.name, p.title, true]),
       'Levels: one row for each, with its registry name, the sentence that says what it shows, and its tick on');
    const tickBox = key => page.locator(`.pg-panel [data-pg-row=levels] .pg-lv[data-pg-level=${key}] .pg-lvcheck`);
    await tickBox('bare').click();
    eq(await page.evaluate(() => [document.body.classList.contains('no3'), document.querySelector('[data-toggle=no3]').classList.contains('on'),
                                  localStorage.getItem('bk_no3'), [...document.querySelectorAll('.p3')].some(e => e.getClientRects().length)]),
       [true, false, '1', false], 'unticking Plain presses the page\'s own button: its pass is hidden, kept on this device');
    await tickBox('bare').click();
    eq(await page.evaluate(() => [document.body.classList.contains('no3'), [...document.querySelectorAll('.p3')].some(e => e.getClientRects().length)]),
       [false, true], 'and ticking it brings the pass back');
    // a level pressed on the page: the gear follows
    await page.evaluate(() => document.querySelector('[data-toggle=no4]').click());
    await until(page, () => !document.querySelector('.pg-panel [data-pg-level=alt] input').checked, null, 'the row following the page');
    assert(true, 'a level turned off on the page is ticked off in the open gear');
    await page.evaluate(() => document.querySelector('[data-toggle=no4]').click());
    // ---- the names
    const nameBox = key => page.locator(`.pg-panel [data-pg-row=levels] .pg-lv[data-pg-level=${key}] .pg-lvname`);
    await nameBox('vocal').fill('Mine');
    await until(page, () => document.querySelector('[data-toggle=no1]').textContent === 'Mine', null, 'the button wearing the name');
    eq(await page.evaluate(() => [document.querySelector('[data-toggle=no1]').textContent, localStorage.getItem('bk_lvl:fa:vocal'),
                                  document.getElementById('hovermode').title]),
       ['Mine', 'Mine', 'the text alone (the levels Mine and Plain), the glosses in a hover cloud over it (H)'],
       'a name typed is the button\'s face, kept under bk_lvl:fa:vocal, and hover mode\'s tooltip says it');
    await until(page, async () => (((await (await fetch('/__prefs')).json()).settings || {})['bk_lvl:fa:vocal'] || {}).v === 'Mine', null, 'the toolbox hearing it', 8000);
    eq((await serverPrefs())['bk_lvl:fa:vocal'].v, 'Mine', 'and the toolbox keeps it for the person');
    await nameBox('chunks').fill('abcdefghijklmnop');
    await until(page, () => document.querySelector('[data-toggle=no2]').textContent.length > 0 && localStorage.getItem('bk_lvl:fa:chunks'), null, 'the long name kept');
    eq(await page.evaluate(() => [document.querySelector('[data-toggle=no2]').textContent, document.querySelector('.pg-panel [data-pg-level=chunks] .pg-lvname').value]),
       ['abcdefghijkl', 'abcdefghijkl'], 'a name is twelve characters at the most');
    await nameBox('chunks').fill('');
    await page.locator('.pg-panel .pg-title').click();
    await until(page, () => document.querySelector('[data-toggle=no2]').textContent === 'Chunks', null, 'the default back');
    eq(await page.evaluate(() => [document.querySelector('[data-toggle=no2]').textContent, localStorage.getItem('bk_lvl:fa:chunks'),
                                  document.querySelector('.pg-panel [data-pg-level=chunks] .pg-lvname').value]),
       ['Chunks', '', 'Chunks'], 'emptied, a name is the registry\'s again');
    await nameBox('vocal').fill('');
    await page.locator('.pg-panel .pg-title').click();
    await until(page, () => document.querySelector('[data-toggle=no1]').textContent === 'With vowels', null, 'the first default back');

    // ---- glosses, and the hover mode that rests them
    eq([await switchOn(page, 'gloss'), await switchOn(page, 'hover')], [true, false], 'Glosses on, the cloud off to begin with');
    await flip(page, 'gloss');
    eq(await page.evaluate(() => [document.body.classList.contains('nogloss'), [...document.querySelectorAll('.row .gl')].some(e => e.getClientRects().length),
                                  document.querySelector('[data-toggle=nogloss]').classList.contains('on')]),
       [true, false, false], 'the glosses switch hides the glosses beside the chunks, through the page\'s own button');
    await flip(page, 'gloss');
    await flip(page, 'hover');
    eq(await page.evaluate(() => [document.body.classList.contains('hovermode'), document.getElementById('hovermode').classList.contains('on'),
                                  document.querySelector('[data-toggle=no2]').disabled, document.querySelector('[data-toggle=nogloss]').disabled]),
       [true, true, true, true], 'the cloud on: the page rests the Chunks level and the glosses switch');
    const why = await rowText(page, 'gloss');
    eq([await switchDisabled(page, 'gloss'), why.why], [true, 'Hover mode shows the glosses in the cloud instead.'], 'and the gear rests them with the reason, printed under the row');
    eq(await page.evaluate(() => [document.querySelector('.pg-panel [data-pg-level=chunks] input').disabled, document.querySelector('.pg-panel [data-pg-row=levels] .pg-why').textContent]),
       [true, 'Hover mode shows the glosses in the cloud instead.'], 'the Chunks level\'s tick rests too, saying why');
    await gearClose(page);
    await page.hover('.p1 .w[data-c="1"]');
    await until(page, () => !document.getElementById('cloud').hidden, null, 'the cloud over a word');
    eq(await page.evaluate(() => [...document.getElementById('cloud').querySelectorAll('.tr, .en')].length > 0), true, 'a word pointed at opens the cloud with its gloss');
    await page.mouse.move(2, 2);
    await gearOpen(page);
    await flip(page, 'hover');
    eq(await page.evaluate(() => [document.body.classList.contains('hovermode'), document.querySelector('[data-toggle=no2]').disabled]), [false, false], 'the cloud off: nothing rests');

    // ---- hide the bars, and bring them back
    await flip(page, 'bars');
    eq(await page.evaluate(() => [document.body.classList.contains('chrome-off'), document.querySelector('header').getClientRects().length > 0,
                                  document.getElementById('barsback').hidden, document.getElementById('barsback').textContent]),
       [true, false, false, '\u2304 show bars'], 'Hide the bars: the header is away and the corner button says how to bring it back');
    assert(await gearUp(page), 'and the gear is still up to say it');
    await flip(page, 'bars');
    eq(await page.evaluate(() => [document.body.classList.contains('chrome-off'), document.querySelector('header').getClientRects().length > 0]), [false, true], 'turned off in the gear, the bars are back');
    // the page's own buttons, pressed while the gear is up (a script's click does not shut it): the row follows them
    await page.evaluate(() => document.getElementById('bars').click());
    await until(page, () => document.querySelector('.pg-panel [data-pg-row=bars] button.pg-switch').getAttribute('aria-checked') === 'true', null, 'the row following the page\'s "hide bars"');
    assert(await gearUp(page), 'the page\'s own "hide bars" button: the gear\'s row follows it, and the gear stays up');
    await page.evaluate(() => document.getElementById('barsback').click());
    await until(page, () => document.querySelector('.pg-panel [data-pg-row=bars] button.pg-switch').getAttribute('aria-checked') === 'false', null, 'the row following the corner button');
    assert(true, 'and the corner "show bars"');
    await gearClose(page);

    // ---- Looking a word up: the link is always there; the switches where the page draws them
    await gearOpen(page, 'looking');
    const look = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=looking] [data-pg-row]')].filter(r => !r.hidden).map(r => r.dataset.pgRow));
    eq(look, ['lookupset'], 'a book with no dictionary installed: just the way to get one');
    eq(await page.evaluate(() => document.querySelector('.pg-panel [data-pg-row=lookupset] a').getAttribute('href').replace(/^.*\/settings/, '/settings')),
       '/settings/reading-help/', 'which goes to Parseh\'s own reading-help settings');
    // a dictionary found: the switches appear with it, and press the page's buttons
    await page.evaluate(() => { DICT.ready = true; DICT.defines = true; MT.ready = true; document.getElementById('dictmode').hidden = false; showDefs(); });
    await until(page, () => !!document.querySelector('.pg-panel [data-pg-row=dictmode]:not([hidden])'), null, 'the dictionary row');
    eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=looking] [data-pg-row]')].filter(r => !r.hidden).map(r => r.dataset.pgRow)),
       ['dictmode', 'defmode', 'defmt', 'lookupset'], 'a dictionary there: look up, the definitions, their translation, and the link');
    eq([await switchDisabled(page, 'defmode'), (await rowText(page, 'defmode')).why, (await rowText(page, 'defmt')).name],
       [true, 'Turn the dictionary on first.', 'Translate the definitions into English'], 'the definitions rest while the dictionary is off, and say so; the translation is named for the glosses\' language');
    await flip(page, 'dictmode');
    eq(await page.evaluate(() => [document.getElementById('dictmode').classList.contains('on'), DICT.on]),
       [true, true], 'the dictionary switch presses the page\'s own');
    await flip(page, 'defmode');
    eq(await page.evaluate(() => [document.getElementById('defmode').classList.contains('on'), DICT.defs]), [true, true], 'and the definitions');
    await flip(page, 'defmode'); await flip(page, 'dictmode');
    await page.evaluate(() => { DICT.ready = false; DICT.defines = false; MT.ready = false; document.getElementById('dictmode').hidden = true; showDefs(); });
    eq(await page.evaluate(() => ['stopbnd', 'hoverpause', 'defmode', 'defmt', 'lookupset'].map(id => document.getElementById(id).getClientRects().length > 0)),
       [false, false, false, false, false], 'what the gear holds -- stop at a change, hover pause, the definitions, the link -- is in the DOM and not drawn on the page');
    await gearClose(page);

    // ---- Text: the very sliders of Aa
    await gearOpen(page, 'text');
    const text = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=text] [data-pg-row]')].map(r => [r.dataset.pgRow, r.querySelector('.pg-nametext') ? r.querySelector('.pg-nametext').textContent : '', (r.querySelector('.pg-help') || {}).textContent || '']));
    eq(text, [['typo-fa', 'Persian text size', 'How big the book\'s own words are, the ones you are learning.'],
              ['typo-gl', 'Gloss size', 'How big the meanings and notes beside each chunk are, and inside the hover cloud.'],
              ['typo-width', 'Text width', 'How wide the column of text may grow on a wide screen; on a narrow screen it always fits.'],
              ['typo-lead', 'Line spacing', 'The space between lines: 1 is the usual, more is airier.'],
              ['typo-reset', '', 'Sets every slider above back to its usual value.']],
       'Text: the sliders Parseh.typo has, named and worded as plan 6 says');
    const slide = async (id, v) => { const i = page.locator(`.pg-panel [data-pg-row=${id}] input[type=range]`); await i.evaluate((e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }, String(v)); await sleep(120); };
    await slide('typo-fa', 30);
    eq(await page.evaluate(() => [JSON.parse(localStorage.getItem('bk_typo')).fa, document.documentElement.style.getPropertyValue('--rd-fa'), Parseh.typo.last.get().fa,
                                  parseFloat(getComputedStyle(document.querySelector('.p1 .w')).fontSize),
                                  document.querySelector('.pg-panel [data-pg-row=typo-fa] output').textContent]),
       [30, '30px', 30, 30, '30 px'], 'a slider writes the same bk_typo Aa wrote, sets the page\'s own token, and the text grows');
    await slide('typo-lead', 1.4);
    eq(await page.evaluate(() => JSON.parse(localStorage.getItem('bk_typo')).lead), 1.4, 'the others too: line spacing');
    await page.locator('.pg-panel [data-pg-row=typo-reset] button').click();
    eq(await page.evaluate(() => [JSON.parse(localStorage.getItem('bk_typo')).fa, JSON.parse(localStorage.getItem('bk_typo')).lead, document.documentElement.style.getPropertyValue('--rd-fa'),
                                  document.querySelector('.pg-panel [data-pg-row=typo-fa] input').value]),
       [20, 1, '20px', '20'], '"Put the text back to normal" puts them back, in the page and in the panel');
    await gearClose(page);
    // Aa opens the gear at Text, once and not twice
    await page.click('#typo');
    await until(page, () => { const p = document.querySelector('.pg-panel'); return p && !p.hidden; }, null, 'the gear opening from Aa');
    const aa = await page.evaluate(() => {
      const g = document.querySelector('.pg-panel [data-pg-group=text]').getBoundingClientRect(), b = document.querySelector('.pg-panel .pg-body').getBoundingClientRect();
      return {atTop: Math.abs(g.top - b.top) < 40, typoPanel: !document.querySelector('.parseh-typo').hidden, focus: document.activeElement.closest('[data-pg-group]') ? document.activeElement.closest('[data-pg-group]').dataset.pgGroup : null};
    });
    eq(aa, {atTop: true, typoPanel: false, focus: 'text'}, 'Aa opens the gear at Text, with the first control focused, and the old panel stays shut');
    await page.click('#typo');
    await until(page, () => document.querySelector('.pg-panel').hidden, null, 'Aa shutting it again');
    assert(true, 'and pressed again, with Text in view, it shuts the gear');
    await page.click('#typo');
    await page.evaluate(() => { document.querySelector('.pg-panel .pg-body').scrollTop = 0; });
    await sleep(100);
    await page.click('#typo');
    assert(await gearUp(page), 'Aa with the gear open elsewhere takes it to Text instead of shutting it');
    await page.keyboard.press('Escape');
    assert(!(await gearUp(page)), 'Esc shuts it');

    // ---- Colours and Interface
    await gearOpen(page, 'colours');
    await page.locator('.pg-panel [data-pg-row=theme] .pg-chip:text-is("Dark")').click();
    eq(await page.evaluate(() => [document.documentElement.getAttribute('data-theme'), localStorage.getItem('parseh_theme')]), ['dark', 'dark'], 'Colours: Dark is parseh_theme and the page\'s own theme');
    await page.evaluate(() => Parseh.theme.set('sepia'));
    await until(page, () => document.querySelector('.pg-panel [data-pg-row=theme] .pg-chip[aria-checked=true]').textContent === 'Sepia', null, 'the row following ◐');
    assert(true, 'a theme set from the page (◐) shows in the open row');
    await page.locator('.pg-panel [data-pg-row=theme] .pg-chip:text-is("Follow my device")').click();
    eq(await page.evaluate(() => [document.documentElement.getAttribute('data-theme'), localStorage.getItem('parseh_theme')]), [null, 'auto'], 'and Follow my device lets go of it');
    // a theme the computer brought (lib/prefs.js stores it and says so on the document): the open row follows
    await page.evaluate(() => { localStorage.setItem('parseh_theme', 'dark'); document.dispatchEvent(new CustomEvent('parseh:pref', {detail: {key: 'parseh_theme', value: 'dark'}})); });
    await until(page, () => document.querySelector('.pg-panel [data-pg-row=theme] .pg-chip[aria-checked=true]').textContent === 'Dark', null, 'the row following the theme the computer brought');
    assert(true, 'a theme brought by the toolbox (parseh:pref) repaints the open Colours row');
    await page.evaluate(() => { localStorage.setItem('parseh_theme', 'auto'); document.dispatchEvent(new CustomEvent('parseh:pref', {detail: {key: 'parseh_theme', value: 'auto'}})); });
    await gearOpen(page, 'interface');
    await page.locator('.pg-panel [data-pg-row=mode] button:text-is("Mobile")').click();
    eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'), localStorage.getItem('parseh_mode'), document.querySelector('[data-parseh-gear]').classList.contains('pg-mobile')]),
       ['mobile', 'mobile', true], 'Interface: Mobile is the toolbox\'s own switch, and the gear takes its phone dress');
    // the open popover became the phone's sheet, on its index: the theme is entered again
    await gearOpen(page, 'interface');
    await page.locator('.pg-panel [data-pg-row=mode] button:text-is("Browser")').click();
    eq(await page.evaluate(() => document.documentElement.getAttribute('data-mode')), 'browser', 'and Browser brings the page back');
    await page.context().close();
  }

  /* ================================================================ listening */
  if (want('listening')) {
    console.log('\nlistening) the narrated English book');
    await resetPrefs();
    const page = await newPage(DESK, 'listening');
    await open(page, 'en');
    await gearOpen(page);
    eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group]')].filter(g => !g.hidden).map(g => g.dataset.pgGroup).filter(g => g !== 'zoom')),
       ['levels', 'listening', 'looking', 'text', 'colours', 'interface'], 'a book with a recording has the Listening group');
    eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=listening] [data-pg-row]')].filter(r => !r.hidden).map(r => r.dataset.pgRow)),
       ['speed', 'skip', 'cont', 'loop', 'gap', 'stopbnd', 'listen'], 'with the rows plan 6 names, in order');
    eq(await page.evaluate(() => [document.getElementById('cont').textContent, document.getElementById('gapwrap').firstChild.nodeValue.trim(),
                                  document.getElementById('bars').textContent, document.getElementById('barsback').textContent]),
       ['keep going', 'between repeats', '\u2303 hide bars', '\u2304 show bars'], 'the page says "keep going", "between repeats", "hide bars", "show bars"');
    const names = await Promise.all(['speed', 'skip', 'cont', 'loop', 'gap', 'stopbnd', 'listen'].map(id => rowText(page, id)));
    eq(names.map(n => n.name), ['Playback speed', 'Skip distance', 'Keep playing into the next line', 'Repeat this line', 'Pause between repeats', 'Wait at each new chapter', 'Listen on its own'], 'named as plan 6 names them');

    // speed
    await pick(page, 'speed', '1.5\u00d7');
    eq(await page.evaluate(() => [document.getElementById('speed').value, document.getElementById('audio').playbackRate, localStorage.getItem('bk_rate'), ParsehNarr.rate(),
                                  document.querySelector('header .nc-chip').textContent]),
       ['1.5', 1.5, '1.5', 1.5, '1.5\u00d7'], 'Playback speed: the page\'s own menu, the sound, bk_rate and the header\'s chip agree');
    await page.evaluate(() => ParsehNarr.setRate(1.25));
    await until(page, () => document.querySelector('.pg-panel [data-pg-row=speed] select').selectedOptions[0].textContent === '1.25\u00d7', null, 'the speed row following');
    assert(true, 'a speed set elsewhere (the chip, the [ and ] keys) shows in the open row');
    await pick(page, 'speed', '1\u00d7');
    // skip
    await pick(page, 'skip', '5 s');
    eq(await page.evaluate(() => [localStorage.getItem('bk_skip'), ParsehNarr.secs(), [...document.querySelectorAll('header .nc-skip')].map(b => b.textContent)]), ['5', 5, ['\u21ba 5', '5 \u21bb']],
       'Skip distance: bk_skip, and the header\'s \u21ba and \u21bb say it');
    await pick(page, 'skip', '10 s');
    // keep going
    eq([await switchOn(page, 'cont'), await ls(page, 'bk_cont')], [true, '1'], 'Keep playing into the next line: on to begin with (and as the toolbox has it)');
    await flip(page, 'cont');
    eq(await page.evaluate(() => [document.getElementById('cont').classList.contains('on'), cont, localStorage.getItem('bk_cont')]), [false, false, '0'], 'turned off: the page\'s own button, its state and bk_cont');
    await gearClose(page);
    await page.reload({waitUntil: 'load'});
    await page.waitForSelector('[data-parseh-gear]'); await sleep(300);
    eq(await page.evaluate(() => [document.getElementById('cont').classList.contains('on'), cont]), [false, false], 'a reload: still off, on the page');
    await gearOpen(page);
    eq(await switchOn(page, 'cont'), false, 'and in the gear');
    await flip(page, 'cont');
    eq(await page.evaluate(() => [cont, localStorage.getItem('bk_cont')]), [true, '1'], 'turned on again');
    // repeat and the pause between
    eq([await switchOn(page, 'loop'), await selectDisabled(page, 'gap'), (await rowText(page, 'gap')).why], [false, true, 'Turn on \u201cRepeat this line\u201d first.'],
       'Repeat: off, and the pause between repeats rests, saying why');
    await flip(page, 'loop');
    eq(await page.evaluate(() => [document.getElementById('loop').classList.contains('on'), loop, document.getElementById('gapwrap').style.display]), [true, true, 'inline'],
       'Repeat this line: the page\'s own loop, and its "between repeats" menu appears');
    eq(await selectDisabled(page, 'gap'), false, 'the pause between repeats wakes');
    await pick(page, 'gap', '2 s');
    eq(await page.evaluate(() => [localStorage.getItem('bk_gap'), document.getElementById('gap').value, gap]), ['2', '2', 2], 'and sets the page\'s own menu, its number and bk_gap');
    await pick(page, 'gap', 'none');
    await flip(page, 'loop');
    eq([await selectDisabled(page, 'gap'), await page.evaluate(() => document.getElementById('gapwrap').style.display)], [true, 'none'], 'Repeat off: its menu goes from the page and rests in the gear');
    // stop at a change
    await flip(page, 'stopbnd');
    eq(await page.evaluate(() => [document.getElementById('stopbnd').classList.contains('on'), stopBound, localStorage.getItem('bk_stopbnd')]), [true, true, '1'], 'Wait at each new chapter: the page\'s own button, bk_stopbnd');
    await flip(page, 'stopbnd');
    // listen, and what only it draws
    await until(page, () => document.getElementById('audio').readyState >= 1, null, 'the recording\'s length');
    eq(await page.evaluate(() => ['listenfollow', 'listenscroll', 'seekwrap'].map(id => document.getElementById(id).getClientRects().length > 0)), [false, false, false],
       'Listening off: "highlight", "keep in view" and the seek bar are not on the page');
    await flip(page, 'listen');
    eq(await page.evaluate(() => [document.getElementById('listen').classList.contains('on'), listening,
                                  ['listenfollow', 'listenscroll', 'seekwrap'].map(id => document.getElementById(id).getClientRects().length > 0),
                                  [document.getElementById('listenfollow').textContent, document.getElementById('listenscroll').textContent]]),
       [true, true, [true, true, true], ['highlight', 'keep in view']], 'Listen on its own: the page listens, and draws the seek bar, "highlight" and "keep in view"');
    await page.evaluate(() => document.getElementById('listenfollow').click());
    eq(await page.evaluate(() => document.getElementById('listenfollow').classList.contains('on')), true, 'which are the page\'s: pressed there, they are on');
    await flip(page, 'listen');
    eq(await page.evaluate(() => ['listenfollow', 'listenscroll', 'seekwrap'].map(id => document.getElementById(id).getClientRects().length > 0)), [false, false, false], 'turned off, they go');
    // hover pause, under the hover cloud's row
    const hp = await page.evaluate(() => { const r = document.querySelector('.pg-panel [data-pg-row=hoverpause]'); return [r.previousElementSibling.dataset.pgRow, r.dataset.pgIndent, r.querySelector('.pg-nametext').textContent]; });
    eq(hp, ['hover', '1', 'Pause while a gloss is open'], 'Pause while a gloss is open hangs under Glosses in a cloud');
    await flip(page, 'hoverpause');
    eq(await page.evaluate(() => [document.getElementById('hoverpause').classList.contains('on'), localStorage.getItem('bk_hoverpause')]), [true, '1'], 'and presses the layer\'s own button, kept on this device');
    eq(Object.keys(await serverPrefs()).includes('bk_hoverpause'), false, 'and it is never the toolbox\'s');
    await flip(page, 'hoverpause');
    await page.context().close();
  }

  /* ===================================================================== marks */
  if (want('marks')) {
    console.log('\nmarks) Diacritics: the vowel marks of Persian and Arabic, off and on');
    for (const [code, lang, marks] of [['lazy-fa', 'fa', '[\u064B-\u0652]'], ['lazy-ar', 'ar', '[\u064B-\u0652\u0670]']]) {
      await resetPrefs();
      const page = await newPage(DESK, 'marks ' + lang);
      await open(page, code);
      const snap = () => page.evaluate(m => {
        const re = new RegExp(m), txt = sel => [...document.querySelectorAll(sel)].map(e => e.textContent).join('|');
        const cls = [...document.querySelectorAll('.p1 .w, .row .fa')].map(e => e.className).join('|');
        return {p1: txt('.p1 .w'), p2: txt('.row .fa'), p3: txt('.p3'), p1m: re.test(txt('.p1 .w')), p2m: re.test(txt('.row .fa')), p3m: re.test(txt('.p3')),
                wds: document.querySelectorAll('.wd').length, cls, hot: document.querySelectorAll('[class*=hl-]').length,
                dataw: [...document.querySelectorAll('.wd[data-w]')].map(e => e.dataset.w).join('|'), lazy: document.querySelectorAll('section.chapter[data-part]').length};
      }, marks);
      const before = await snap();
      assert(before.p1m && before.p2m && !before.p3m && before.lazy > 0, `${lang}: the book has marks on levels 1 and 2, none on level 3, and chapters still to be fetched (${before.lazy})`);
      await gearOpen(page);
      eq(await switchOn(page, 'marks'), true, `${lang}: Diacritics is on to begin with`);
      const help = (await rowText(page, 'marks')).help;
      assert(help.startsWith('Shows ') && help.includes('Off, the text reads as it is ordinarily printed') && /\u201cPlain\u201d is the same text without the hover/.test(help) && !/level 3/.test(help),
             `${lang}: and says what it does, naming the Plain level and no number: ${help}`);
      await flip(page, 'marks');
      await sleep(200);
      const off = await snap();
      eq([off.p1m, off.p2m, off.p3 === before.p3, off.wds, off.dataw === before.dataw, off.cls === before.cls], [false, false, true, before.wds, true, true],
         `${lang}: off: levels 1 and 2 are bare, level 3 is as it was, and no word, attribute or class has moved`);
      eq(off.p1, before.p1.replace(new RegExp(marks, 'g'), ''), `${lang}: levels 1 is exactly the same text without the marks`);
      eq(await ls(page, 'bk_marks'), '0', `${lang}: kept on this device`);
      // the page's readers of text see the book's own
      const read = await page.evaluate(() => ({textOf: textOf(document.querySelector('.p1 .w[data-c="1"]')), base: Parseh.baseText(document.querySelector('.p1 .w[data-c="1"]')),
        chunk: chunkData(1).fa, drawn: document.querySelector('.p1 .w[data-c="1"]').textContent, sentence: textOf(document.querySelector('.sub .p1')).replace(/\s+/g, ' ').trim()}));
      assert(new RegExp(marks).test(read.textOf) && read.textOf === read.base && read.base === read.chunk && !new RegExp(marks).test(read.drawn) &&
             read.textOf.replace(new RegExp(marks, 'g'), '') === read.drawn && new RegExp(marks).test(read.sentence),
             `${lang}: textOf, Parseh.baseText and chunkData read the book's own vowelled text while the page draws it bare`);
      // the cloud, the gloss, the highlight
      await gearClose(page);
      await page.evaluate(() => document.getElementById('hovermode').click());
      await page.hover('.p1 .w[data-c="1"]');
      await until(page, () => !document.getElementById('cloud').hidden && !!document.querySelector('.p1 .w.hot'), null, 'the cloud');
      const cloud = await page.evaluate(() => ({hot: +document.querySelector('.p1 .w.hot').dataset.c, tr: (document.querySelector('#cloud .tr') || {}).textContent, en: (document.querySelector('#cloud .en') || {}).textContent,
                                              row: (document.querySelector('.row[data-c="1"] .gl .en') || {}).textContent}));
      eq([cloud.hot, !!cloud.tr, cloud.en === cloud.row], [1, true, true], `${lang}: hover mode: the cloud still opens on level 1 with the chunk's own gloss and the highlight`);
      await page.evaluate(() => { window.__said = []; Parseh.copy = t => { __said.push(t); return true; }; });
      await page.locator('#cloud .mkcopy').click();
      const copied = await page.evaluate(() => __said.pop());
      assert(new RegExp(marks).test(copied) && copied === read.textOf, `${lang}: the cloud's copy button copies the vowelled chunk: ${copied}`);
      await page.mouse.move(2, 2);
      await page.evaluate(() => document.getElementById('hovermode').click());
      await page.click('.p1 .w[data-c="1"]', {modifiers: ['Shift']});
      const shift = await page.evaluate(() => __said.pop());
      assert(shift === read.textOf, `${lang}: a shift-click copies the vowelled chunk too`);
      await page.locator('.p1 .wd').nth(1).click({modifiers: ['Alt']});
      await until(page, () => !document.getElementById('anki').hidden, null, 'the card sheet');
      const card = await page.evaluate(() => ({fa: document.getElementById('afa').value, ctx: document.getElementById('actx').value}));
      assert(new RegExp(marks).test(card.fa) && new RegExp(marks).test(card.ctx), `${lang}: a card carries the vowelled word and sentence: ${card.fa} / ${card.ctx.slice(0, 24)}`);
      await page.locator('#acancel').click();
      // a chapter fetched AFTER the switch is bare too
      await page.evaluate(() => needChapters(0));
      await until(page, () => !document.querySelector('section.chapter[data-part]'), null, 'the chapters fetched');
      const after = await snap();
      eq([after.lazy, after.p1m, after.p2m, after.p3m], [0, false, false, false], `${lang}: chapters fetched after the switch arrive bare, level 3 untouched`);
      // a reload keeps it
      await page.reload({waitUntil: 'load'});
      await page.waitForSelector('[data-parseh-gear]'); await sleep(400);
      const rel = await snap();
      eq([rel.p1m, rel.p2m, rel.p3m], [false, false, false], `${lang}: a reload keeps the marks off`);
      await gearOpen(page);
      eq(await switchOn(page, 'marks'), false, `${lang}: and the gear says so`);
      // and back: every node as it was
      await page.evaluate(() => needChapters(0));
      const bare = await snap();
      await flip(page, 'marks');
      await sleep(200);
      const on = await snap();
      assert(on.p1m && on.p2m && !on.p3m && on.p3 === bare.p3, `${lang}: on again: the marks are back on levels 1 and 2`);
      eq(await ls(page, 'bk_marks'), '1', `${lang}: kept as shown`);
      // restored exactly: the book's own text, node for node, against a copy read from the file
      const file = await Deno.readTextFile(`${BOOKS}/${code === 'lazy-fa' ? 'persian' : 'arabic'}/${code}/reader/index.html`);
      const fromFile = await page.evaluate(async src => {
        const doc = new DOMParser().parseFromString(src, 'text/html');
        return [...doc.querySelectorAll('.p1 .w')].map(e => e.textContent).join('|');
      }, file);
      eq(on.p1.split('|').slice(0, fromFile.split('|').length), fromFile.split('|'), `${lang}: the page is exactly the book's own text again (level 1 against the file)`);
      await page.context().close();
    }
  }

  /* ===================================================================== phone */
  if (want('phone')) {
    console.log('\nphone) 390x844 with a finger');
    await resetPrefs();
    const page = await newPage(PHONE, 'phone', MOBILE_MODE);
    await open(page, 'en');
    await page.waitForSelector('.px-ask', {state: 'visible', timeout: 8000});       // lib/explain.js comes a moment after the page
    const first = await firstLine(page);
    eq(first.map(x => x.n), ['hub', 'shelf', 'toc', 'typo', 'gear', 'px-ask'], 'the first line: the hub, the shelf, the contents, Aa, the gear and the ? -- no \u22ef');
    assert(new Set(first.map(x => x.t)).size === 1, 'all on one line');
    eq(await page.evaluate(() => [!!document.querySelector('.m-rmore'), !!document.querySelector('.m-rlab'), !!document.querySelector('header .parseh-mode')]), [false, false, false],
       'and nothing of the old menu is in the page: no \u22ef, no group lines, no Browser | Mobile switch');
    await shot(page, 'phone-closed');
    // Aa, on a phone, opens the sheet at Text -- and not the old panel
    await tap(page, '#typo');
    await until(page, () => !document.querySelector('.pg-panel').hidden, null, 'the sheet from Aa');
    await sleep(300);
    eq(await page.evaluate(() => ({stage: document.querySelector('.pg-panel').getAttribute('data-pg-stage'), title: document.querySelector('.pg-title').textContent,
      first: !!document.activeElement.closest('[data-pg-group=text]'), old: !document.querySelector('.parseh-typo').hidden})),
       {stage: 'text', title: 'Text', first: true, old: false}, 'Aa opens the sheet at Text (the index underneath, its first slider focused), and the old panel stays shut');
    // a second press shuts it while Text is on stage; pressed on the index (or another theme) it brings Text back instead
    await tap(page, '#typo');
    await until(page, () => document.querySelector('.pg-panel').hidden, null, 'Aa again shuts it');
    assert(true, 'a second press of Aa shuts the sheet while Text is on stage');
    await tap(page, '#typo');
    await until(page, () => !document.querySelector('.pg-panel').hidden, null, 'the sheet from Aa again');
    await sleep(300);
    await tap(page, '.pg-panel .pg-back');
    await sleep(300);
    eq(await page.evaluate(() => document.querySelector('.pg-panel').getAttribute('data-pg-stage')), 'index', '‹ goes back to the index');
    await tap(page, '#typo');
    await sleep(300);
    eq(await page.evaluate(() => [document.querySelector('.pg-panel').hidden, document.querySelector('.pg-panel').getAttribute('data-pg-stage')]), [false, 'text'], 'Aa pressed with the index showing takes the sheet to Text and does not shut it');
    await gearClose(page);
    await tap(page, '[data-parseh-gear]');
    await until(page, () => !document.querySelector('.pg-panel').hidden, null, 'the sheet');
    await sleep(300);
    const sheet = await page.evaluate(() => {
      const r = document.querySelector('.pg-panel').getBoundingClientRect();
      const probe = document.elementFromPoint(200, 160);
      return {sheet: document.querySelector('.pg-panel').classList.contains('pg-sheet'), share: r.height / innerHeight, bottom: Math.round(r.bottom - innerHeight), textAbove: !!probe && !probe.closest('.pg-panel'),
              stage: document.querySelector('.pg-panel').getAttribute('data-pg-stage'),
              dock: (() => { const d = document.querySelector('.nc-dock'); return d ? getComputedStyle(d).zIndex : null; })(), history: history.state && history.state.parsehGear ? 'pushed' : 'none'};
    });
    assert(sheet.sheet && sheet.share > 0.45 && sheet.share < 0.65 && sheet.bottom === 0 && sheet.textAbove, `the sheet is about half the screen, at the foot, the text visible above it: ${JSON.stringify(sheet)}`);
    eq(sheet.stage, 'index', 'it opens on the index of the themes');
    // THE INDEX: a row for each theme the book has, what each is set to said under its name, all in view with no scroll
    const idx = await page.evaluate(() => [...document.querySelectorAll('.pg-panel .pg-irow')].filter(r => r.getClientRects().length).map(r =>
      [r.dataset.pgIndex, r.querySelector('.pg-iname').textContent, r.querySelector('.pg-isum').textContent, Math.round(r.getBoundingClientRect().height)]));
    console.log('  index:', JSON.stringify(idx));
    eq(idx.map(r => r[0]), ['levels', 'listening', 'looking', 'text', 'zoom', 'colours', 'interface'], 'the themes, in the plan\'s order: levels, listening, looking, text, zoom, colours, interface');
    eq(idx.map(r => r[1]), ['Levels & reading', 'Listening', 'Looking a word up', 'Text', 'Zoom', 'Colours', 'Interface'], 'each says its name');
    assert(idx.every(r => r[3] >= 48), 'every row of the index is a finger high (' + idx.map(r => r[3]).join(',') + 'px)');
    const fit = await page.evaluate(() => { const b = document.querySelector('.pg-panel .pg-body').getBoundingClientRect(), rows = [...document.querySelectorAll('.pg-panel .pg-irow')].filter(r => r.getClientRects().length);
      return rows.every(r => { const q = r.getBoundingClientRect(); return q.top >= b.top - 0.5 && q.bottom <= b.bottom + 0.5; }); });
    eq(fit, true, 'and all seven are inside the half sheet at once, with no scrolling');
    const sum = Object.fromEntries(idx.map(r => [r[0], r[2]]));
    assert(/^Sentence, Chunks\b/.test(sum.levels), `Levels & reading says the ticked levels: "${sum.levels}"`);
    assert(/^1×, skip 10 s\b/.test(sum.listening), `Listening says the speed and the skip: "${sum.listening}"`);
    eq(sum.looking, 'get one →', 'Looking a word up says "get one" while nothing is installed');
    assert(/^English text \d+(\.\d+)? px$/.test(sum.text), `Text says the first slider's value: "${sum.text}"`);
    eq([sum.zoom, sum.colours, sum.interface], ['100 %', 'Follow my device', 'Mobile pages'], 'Zoom, Colours (the scheme chosen) and Interface (Mobile pages)');
    await shot(page, 'phone-index');
    // every row a finger high, in the theme on stage
    await gearOpen(page, 'levels');
    const rows = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=levels] [data-pg-row]')].filter(r => !r.hidden).map(r => [r.dataset.pgRow, Math.round(r.getBoundingClientRect().height)]));
    assert(rows.every(([, h]) => h >= 48), `every row of a theme is at least 48px high (${rows.length} rows)`);
    eq(await page.evaluate(() => document.querySelector('.pg-panel [data-pg-group]:not(.pg-here)') && 'x'), 'x', 'and the other themes are not drawn');
    const small = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group=levels] button, .pg-panel [data-pg-group=levels] select, .pg-panel [data-pg-group=levels] .pg-lvcheck, .pg-panel .pg-back, .pg-panel .pg-x')].filter(e => e.getClientRects().length > 0)
      .map(e => { e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(); return [e.className, Math.round(r.width), Math.round(r.height)]; }).filter(([, w, h]) => w < 44 || h < 44));
    eq(small, [], 'and every control in it a finger\'s size');
    await gearOpen(page, 'listening');
    // a tap changes the real control
    await tap(page, '.pg-panel [data-pg-row=cont] button.pg-switch');
    eq(await page.evaluate(() => [document.getElementById('cont').classList.contains('on'), localStorage.getItem('bk_cont')]), [false, '0'], 'a tap on a row presses the page\'s own control: keep going off, remembered');
    await tap(page, '.pg-panel [data-pg-row=cont] button.pg-switch');
    // the Keep row, in the last theme: the buttons stand in it only while it is on stage
    eq(await page.evaluate(() => !!document.querySelector('.pg-panel .kp-btn')), false, 'the Keep buttons are on the page, not in the sheet, while another theme is on stage');
    await gearOpen(page, 'interface');
    const keep = await page.evaluate(() => { const r = document.querySelector('.pg-panel [data-pg-row=keep]'); return r ? [r.hidden, !!r.querySelector('.kp-btn'), r.querySelector('.kp-keep') ? r.querySelector('.kp-keep').textContent : null] : null; });
    eq(keep, [false, true, 'Keep on this phone'], 'the Keep buttons stand in the last theme\'s row while it is on stage');
    await tap(page, '.pg-panel .pg-back');
    await sleep(300);
    eq(await page.evaluate(() => [!!document.querySelector('.pg-panel .kp-btn'), !!document.querySelector('header .hrow > .kp-btn')]), [false, true], 'and ‹ sends them home to the header');
    await gearOpen(page, 'interface');
    await gearClose(page);
    eq(await page.evaluate(() => [!!document.querySelector('header .hrow > .kp-btn'), document.querySelector('.kp-btn').getClientRects().length > 0]), [true, false], 'and they are back in the header, out of sight, when it is shut');
    // closes by ✕, Esc, back
    await gearOpen(page);
    await page.keyboard.press('Escape');
    assert(!(await gearUp(page)), 'Esc shuts the sheet');
    await gearOpen(page);
    await page.goBack().catch(() => {});
    await sleep(500);
    assert(!(await gearUp(page)), 'the back gesture shuts it (and stays on the book)');
    assert((await page.evaluate(() => location.pathname)) === READERS.en, 'on the same page');
    // from a theme the gesture goes back to the index first, and closes the sheet at the second
    await gearOpen(page, 'text');
    await page.goBack().catch(() => {});
    await sleep(500);
    eq(await page.evaluate(() => [document.querySelector('.pg-panel').hidden, document.querySelector('.pg-panel').getAttribute('data-pg-stage')]), [false, 'index'], 'the back gesture from a theme returns to the index');
    await page.goBack().catch(() => {});
    await sleep(500);
    assert(!(await gearUp(page)) && (await page.evaluate(() => location.pathname)) === READERS.en, 'and the next one closes the sheet, on the same page');
    await gearOpen(page, 'looking');
    await page.keyboard.press('Escape');
    assert(!(await gearUp(page)), 'Esc shuts the whole sheet from a theme');
    await sleep(300);
    // listen on its own: the listening line
    await until(page, () => document.getElementById('audio').readyState >= 1, null, 'the recording\'s length');
    await gearSwitchTouch(page, 'listen', true);
    const line = await page.evaluate(() => ['listenfollow', 'listenscroll', 'seekwrap', 'pos'].map(id => document.getElementById(id).getClientRects().length > 0));
    eq(line, [true, true, true, true], 'listening on its own draws a line under the first: the highlight, keeping it in view, the seek bar and where the recording is');
    await shot(page, 'phone-listening-line');
    await gearSwitchTouch(page, 'listen', false);
    eq(await page.evaluate(() => ['listenfollow', 'listenscroll', 'seekwrap', 'pos'].map(id => document.getElementById(id).getClientRects().length > 0)), [false, false, false, false], 'and nothing of it is on the phone\'s page otherwise');
    // the phone's skip row is the gear's now
    eq(await isDrawn(page, '.m-rskip'), false, 'the phone\'s "skip by" row is not drawn: Skip distance is the gear\'s');
    for (const g of ['levels', 'listening', 'looking', 'text', 'colours', 'interface']) {
      await gearOpen(page, g);
      await sleep(120);
      await shot(page, `phone-${g}`);
    }
    await gearClose(page);
    // THE INDEX IN OTHER LANGUAGES: the chrome stays English and left to right, a level's NAME may not (it is in a
    // <bdi>), and a book of five levels (Japanese, Chinese) is cut with an ellipsis, not wrapped
    for (const code of ['fa', 'ja', 'zh']) {
      await open(page, code);
      await tap(page, '[data-parseh-gear]');
      await until(page, () => !document.querySelector('.pg-panel').hidden, null, `the sheet on the ${code} book`);
      await sleep(300);
      const r = await page.evaluate(() => {
        const row = document.querySelector('.pg-panel .pg-irow[data-pg-index=levels]'), sum = row.querySelector('.pg-isum'), c = getComputedStyle(sum);
        const panel = document.querySelector('.pg-panel');
        return {text: sum.textContent, bdi: [...sum.querySelectorAll('bdi')].map(b => b.textContent), dir: [panel.getAttribute('dir'), c.direction, panel.getAttribute('lang')],
                oneLine: sum.getBoundingClientRect().height < 20, rowH: Math.round(row.getBoundingClientRect().height), cut: c.textOverflow + '/' + c.whiteSpace,
                inside: row.getBoundingClientRect().right <= innerWidth + 0.5, aria: row.getAttribute('aria-label'),
                rows: [...document.querySelectorAll('.pg-panel .pg-irow')].filter(x => x.getClientRects().length).length,
                all: (() => { const b = document.querySelector('.pg-panel .pg-body').getBoundingClientRect(); return [...document.querySelectorAll('.pg-panel .pg-irow')].filter(x => x.getClientRects().length).every(x => { const q = x.getBoundingClientRect(); return q.top >= b.top - 0.5 && q.bottom <= b.bottom + 0.5; }); })()};
      });
      console.log(`  ${code}:`, JSON.stringify([r.text, r.rowH]));
      assert(r.bdi.length >= 2 && r.bdi.join(', ') === r.text.split(' \u00b7 ')[0], `${code}: every ticked level's name is in a <bdi> and they read in the order of the levels (${JSON.stringify(r.bdi)})`);
      eq(r.dir, ['ltr', 'ltr', 'en'], `${code}: the sheet is English and left to right even on a ${code} book`);
      eq([r.oneLine, r.cut, r.inside], [true, 'ellipsis/nowrap', true], `${code}: the summary is one line, cut with an ellipsis, inside the row`);
      assert(r.rowH >= 48 && r.rows >= 6 && r.all, `${code}: ${r.rows} rows (Listening only where the book has a recording), a finger high (${r.rowH}px), all in view with no scrolling`);
      assert(r.aria.startsWith('Levels & reading, ') && r.aria.includes(r.bdi[0]), `${code}: and a screen reader hears the row as its name and its summary`);
      await shot(page, `phone-index-${code}`);
      await gearClose(page);
    }
    await page.context().close();
  }
  async function gearSwitchTouch(page, id, wantOn) {
    await gearReach(page, id);
    const sw = gearRow(page, id).locator('button.pg-switch');
    await sw.scrollIntoViewIfNeeded();
    if (((await sw.getAttribute('aria-checked')) === 'true') !== wantOn) await sw.tap();
    await sleep(150);
    await gearClose(page);
  }

  /* ====================================================================== keys */
  if (want('keys')) {
    console.log('\nkeys) what stays on a device and what follows the person');
    await resetPrefs();
    const A = await newPage(DESK, 'keys A');
    await open(A, 'en');
    await gearOpen(A);
    await pick(A, 'speed', '1.5\u00d7');
    await pick(A, 'skip', '15 s');
    await flip(A, 'loop'); await pick(A, 'gap', '2 s'); await flip(A, 'loop');
    await flip(A, 'stopbnd');
    await flip(A, 'cont');
    await gearOpen(A, 'colours');
    await A.locator('.pg-panel [data-pg-row=theme] .pg-chip:text-is("Sepia")').click();
    await gearOpen(A, 'levels');
    await gearRow(A, 'levels').locator('.pg-lv[data-pg-level=vocal] .pg-lvname').fill('Plainer');
    await A.locator('.pg-panel .pg-title').click();
    // device keys: a level hidden, glosses off, Diacritics' key, a hover pause, the text's size
    await A.locator('.pg-panel [data-pg-row=levels] .pg-lv[data-pg-level=chunks] .pg-lvcheck').click();
    await flip(A, 'hoverpause');
    await gearOpen(A, 'text');
    await A.locator('.pg-panel [data-pg-row=typo-fa] input[type=range]').evaluate(e => { e.value = '26'; e.dispatchEvent(new Event('input', {bubbles: true})); });
    await gearClose(A);
    await A.evaluate(() => localStorage.setItem('bk_marks', '0'));
    await sleep(2200);                            // prefs.js tells the toolbox after a short grace
    const kept = await serverPrefs();
    eq(['bk_rate', 'bk_skip', 'bk_gap', 'bk_stopbnd', 'bk_cont', 'parseh_theme', 'bk_lvl:en:vocal'].map(k => kept[k] && kept[k].v),
       ['1.5', '15', '2', '1', '0', 'sepia', 'Plainer'], 'the toolbox keeps the person\'s: speed, skip, the pause between repeats, wait at a change, keep going, the theme, a level\'s name');
    eq(['bk_no2', 'bk_marks', 'bk_hoverpause', 'bk_typo', 'bk_loop', 'bk_hover'].filter(k => kept[k]), [], 'and nothing of what stays on the device: the levels hidden, Diacritics, the text size, hover pause');
    // a reload of the same context: the device's own keys, and the person's, still there
    await A.reload({waitUntil: 'load'});
    await A.waitForSelector('[data-parseh-gear]'); await sleep(500);
    eq(await A.evaluate(() => [document.body.classList.contains('no2'), localStorage.getItem('bk_hoverpause'), JSON.parse(localStorage.getItem('bk_typo')).fa, document.getElementById('speed').value,
                               document.getElementById('cont').classList.contains('on'), document.querySelector('[data-toggle=no1]').textContent]),
       [true, '1', 26, '1.5', false, 'Plainer'], 'a reload: the device\'s keys and the person\'s are all still worn');
    // ANOTHER BROWSER CONTEXT, one server: the person's follow, the device's do not
    const Bp = await newPage(DESK, 'keys B');
    await open(Bp, 'en');
    await sleep(900);
    const b = await Bp.evaluate(() => ({speed: document.getElementById('speed').value, rate: document.getElementById('audio').playbackRate, skip: ParsehNarr.secs(), gap: document.getElementById('gap').value, stop: document.getElementById('stopbnd').classList.contains('on'),
                                       cont: document.getElementById('cont').classList.contains('on'), theme: document.documentElement.getAttribute('data-theme'), name: document.querySelector('[data-toggle=no1]').textContent,
                                       hidden: document.body.classList.contains('no2'), pause: localStorage.getItem('bk_hoverpause'), typo: localStorage.getItem('bk_typo'), marks: localStorage.getItem('bk_marks')}));
    eq([b.speed, b.rate, b.skip, b.gap, b.stop, b.cont, b.theme, b.name], ['1.5', 1.5, 15, '2', true, false, 'sepia', 'Plainer'], 'in another context: the speed, the skip, the pause, wait at a change, keep going, the theme and the level\'s name have followed the person');
    eq([b.hidden, b.pause, b.typo, b.marks], [false, null, null, null], 'and the levels hidden, hover pause, the text size and Diacritics have not');
    await gearOpen(Bp);
    eq([await switchOn(Bp, 'cont'), await switchOn(Bp, 'stopbnd'), (await Bp.evaluate(() => document.querySelector('.pg-panel [data-pg-row=skip] select').selectedOptions[0].textContent))], [false, true, '15 s'], 'and its gear shows them');
    await gearClose(Bp);
    // a rename in one shows in the other
    await gearOpen(A);
    await gearRow(A, 'levels').locator('.pg-lv[data-pg-level=vocal] .pg-lvname').fill('Again');
    await A.locator('.pg-panel .pg-title').click();
    await sleep(2200);
    await Bp.reload({waitUntil: 'load'});
    await Bp.waitForSelector('[data-parseh-gear]'); await sleep(900);
    eq(await Bp.evaluate(() => document.querySelector('[data-toggle=no1]').textContent), 'Again', 'a rename in one context shows in the other, on its next load');
    // and a value the toolbox brings to a page that is open is worn live (prefs.js announces it)
    await Bp.evaluate(() => document.dispatchEvent(new CustomEvent('parseh:pref', {detail: {key: 'bk_lvl:en:vocal', value: 'Live'}})));
    await Bp.evaluate(() => localStorage.setItem('bk_lvl:en:vocal', 'Live'));
    await Bp.evaluate(() => document.dispatchEvent(new CustomEvent('parseh:pref', {detail: {key: 'bk_lvl:en:vocal', value: 'Live'}})));
    await until(Bp, () => document.querySelector('[data-toggle=no1]').textContent === 'Live', null, 'the live name');
    assert(true, 'a name announced on a page that is open (parseh:pref) is worn at once');
    await A.context().close(); await Bp.context().close();
  }

  /* ===================================================================== names */
  if (want('names')) {
    console.log('\nnames) the levels\' names in every language');
    await resetPrefs();
    for (const code of ['fa', 'ar', 'ja', 'zh', 'en', 'hi']) {
      const page = await newPage(DESK, 'names ' + code);
      await open(page, code);
      const faces = await page.evaluate(() => [...document.querySelectorAll('.pgrp [data-toggle]')].map(b => [b.dataset.toggle, b.textContent, b.title]));
      eq(faces, levelsOf(code).map(p => ['no' + NUM[p.key], p.name, p.title]), `${code}: the buttons wear the registry's names and say what each shows`);
      assert(faces.every(([, t]) => !/\d/.test(t)), `${code}: and no digit`);
      await gearOpen(page);
      const rows = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-row=levels] .pg-lv')].map(li => [li.dataset.pgLevel, li.querySelector('.pg-lvname').value, li.querySelector('.pg-lvhelp').textContent]));
      eq(rows, levelsOf(code).map(p => [p.key, p.name, p.title]), `${code}: the gear's rows too`);
      const dir = await page.evaluate(() => [getComputedStyle(document.querySelector('main .p1')).direction, getComputedStyle(document.querySelector('header')).direction, getComputedStyle(document.querySelector('.pg-panel')).direction]);
      eq(dir, [code === 'fa' || code === 'ar' ? 'rtl' : 'ltr', 'ltr', 'ltr'], `${code}: the text reads its own way, the header and the gear left to right`);
      const keep = levelsOf(code).filter(p => ['vocal', 'aloud', 'bare'].includes(p.key)).map(p => p.name);
      const title = await page.evaluate(() => document.getElementById('hovermode').title);
      assert(keep.every(n => title.includes(n)) && !/\d/.test(title), `${code}: hover mode's tooltip names the levels it keeps: ${title}`);
      // a renamed level in this language, and back
      const k = levelsOf(code)[0];
      await gearRow(page, 'levels').locator(`.pg-lv[data-pg-level=${k.key}] .pg-lvname`).fill('\u0646\u0627\u0645');
      await page.locator('.pg-panel .pg-title').click();
      await until(page, k => document.querySelector(`[data-toggle=no${k}]`).textContent === '\u0646\u0627\u0645', NUM[k.key], 'a name in another script');
      eq(await ls(page, `bk_lvl:${code}:${k.key}`), '\u0646\u0627\u0645', `${code}: a name in any script is kept under bk_lvl:${code}:${k.key}`);
      await gearRow(page, 'levels').locator(`.pg-lv[data-pg-level=${k.key}] .pg-lvname`).fill('');
      await page.locator('.pg-panel .pg-title').click();
      await until(page, (n) => document.querySelector(`[data-toggle=no${n[0]}]`).textContent === n[1], [NUM[k.key], k.name], 'the default again');
      await page.context().close();
    }
    await resetPrefs();
  }

  /* ======================================================================= old */
  if (want('old')) {
    console.log('\nold) a reader built before a0.5.0, with no rebuild');
    await resetPrefs();
    // what the page itself says before the layer touches it is what an old build wrote: read the file
    const raw = await Deno.readTextFile(`${BOOKS}/persian/old-fa/reader/index.html`);
    assert(!/"name": ?"With vowels"/.test(raw.slice(raw.indexOf('const LANG='), raw.indexOf('const GLOSS='))) && raw.includes('which passes you see') &&
           !raw.includes("localStorage.getItem('bk_cont')"), 'the old Persian reader: a language record without names, digits on its buttons, no bk_cont');
    const page = await newPage(DESK, 'old fa');
    await open(page, 'old-fa');
    eq(await page.evaluate(() => [...document.querySelectorAll('.pgrp [data-toggle]')].map(b => [b.textContent, b.title])),
       levelsOf('fa').map(p => [p.name, p.title]), 'the names and the new sentences arrive from the layer\'s own table (the embedded record has neither)');
    eq(await page.evaluate(() => document.querySelector('.pgrpc').textContent), 'levels', 'the caption says "levels"');
    await gearOpen(page);
    eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group]')].filter(g => !g.hidden).map(g => g.dataset.pgGroup).filter(g => g !== 'zoom')),
       ['levels', 'looking', 'text', 'colours', 'interface'], 'the gear is there, with this book\'s groups');
    await gearRow(page, 'levels').locator('.pg-lv[data-pg-level=bare] .pg-lvname').fill('Bare');
    await page.locator('.pg-panel .pg-title').click();
    await until(page, () => document.querySelector('[data-toggle=no3]').textContent === 'Bare', null, 'a rename on an old reader');
    eq(await page.evaluate(() => document.getElementById('hovermode').title), 'the text alone (the levels With vowels and Bare), the glosses in a hover cloud over it (H)', 'and hover mode\'s tooltip says it');
    // Diacritics, with the page's own readers of text
    eq(await page.evaluate(() => [/[\u064B-\u0652]/.test([...document.querySelectorAll('.p1 .w')].map(e => e.textContent).join(''))]), [true], 'the old page has its marks');
    await flip(page, 'marks');
    eq(await page.evaluate(() => [/[\u064B-\u0652]/.test([...document.querySelectorAll('.p1 .w')].map(e => e.textContent).join('')), /[\u064B-\u0652]/.test(textOf(document.querySelector('.p1 .w'))), /[\u064B-\u0652]/.test(Parseh.baseText(document.querySelector('.p1 .w')))]),
       [false, true, true], 'Diacritics on an old reader: the page is bare and its own readers of text still see the vowelled text');
    await flip(page, 'marks');
    await gearClose(page);
    // the old English reader: the words, and "keep going" remembered
    const en = await newPage(DESK, 'old en');
    await open(en, 'old-en');
    eq(await en.evaluate(() => ['cont', 'listenfollow', 'listenscroll'].map(id => document.getElementById(id).textContent)), ['keep going', 'highlight', 'keep in view'], 'an old English reader is given the new words');
    eq(await en.evaluate(() => [document.getElementById('gapwrap').firstChild.nodeValue.trim(), document.getElementById('bars').textContent, document.getElementById('barsback').textContent]),
       ['between repeats', '\u2303 hide bars', '\u2304 show bars'], 'the new label of the gap and of the bars');
    await gearOpen(en);
    await flip(en, 'cont');
    eq(await en.evaluate(() => [cont, localStorage.getItem('bk_cont')]), [false, '0'], 'keep going off, written under bk_cont although this page\'s own script never wrote it');
    await en.reload({waitUntil: 'load'});
    await en.waitForSelector('[data-parseh-gear]'); await sleep(500);
    eq(await en.evaluate(() => [cont, document.getElementById('cont').classList.contains('on')]), [false, false], 'and it is read at load: still off');
    // the phone
    const ph = await newPage(PHONE, 'old phone', MOBILE_MODE);
    await open(ph, 'old-en');
    await ph.waitForSelector('.px-ask', {state: 'visible', timeout: 8000});
    eq((await firstLine(ph)).map(x => x.n), ['hub', 'shelf', 'toc', 'typo', 'gear', 'px-ask'], 'an old reader on a phone: the first line, the gear in it, no \u22ef');
    await shot(ph, 'old-phone');
    await shot(page, 'old-wide');
    await page.context().close(); await en.context().close(); await ph.context().close();
    await resetPrefs();
  }

  /* ===================================================================== widths */
  if (want('widths')) {
    console.log('\nwidths) nothing scrolls sideways');
    await resetPrefs();
    for (const [code, mode] of [['fa', 'browser'], ['en', 'mobile']]) {
      const page = await newPage({viewport: {width: 1280, height: 800}}, 'widths', mode === 'mobile' ? MOBILE_MODE : undefined);
      await open(page, code);
      for (const w of [320, 360, 390, 430, 600, 768, 1024, 1280]) {
        await page.setViewportSize({width: w, height: 800});
        await sleep(300);
        const shut = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        await gearOpen(page);
        await sleep(200);
        const up = await page.evaluate(() => [document.documentElement.scrollWidth - innerWidth, document.querySelector('.pg-panel').scrollWidth - document.querySelector('.pg-panel').clientWidth]);
        await gearClose(page);
        assert(shut <= 0 && up[0] <= 0 && up[1] <= 0, `${code}, ${mode}, ${w}px: no sideways scroll, the gear shut or open (${shut}, ${up})`);
      }
      await page.context().close();
    }
  }

  /* ======================================================================= look */
  if (want('look')) {
    console.log('\nlook) the sheet over what it must be over, in the three themes');
    await resetPrefs();
    for (const theme of ['light', 'dark', 'sepia']) {
      for (const [opts, tag, code, init] of [[DESK, 'wide', 'fa'], [PHONE, 'phone', 'en', MOBILE_MODE]]) {
        const page = await newPage(opts, `look ${tag} ${theme}`, init);
        await open(page, code);
        await page.evaluate(t => Parseh.theme.set(t), theme);
        await sleep(300);
        await shot(page, `look-${tag}-${theme}-header`);
        await gearOpen(page);
        for (const g of ['levels', 'listening', 'looking', 'text', 'colours', 'interface']) {
          if (!(await page.evaluate(g => { const e = document.querySelector(`.pg-panel [data-pg-group=${g}]`); return !!e && !e.hidden; }, g))) continue;
          await gearOpen(page, g);
          await sleep(120);
          await shot(page, `look-${tag}-${theme}-${g}`);
        }
        // the sheet over the reading-place question and the Keep bar, which would otherwise be drawn on its buttons
        if (tag === 'phone') {
          await page.evaluate(() => { const b = document.createElement('div'); b.className = 'pf-bar'; b.textContent = 'a question'; document.body.appendChild(b); });
          eq(await page.evaluate(() => getComputedStyle(document.querySelector('.pf-bar')).display), 'none', `${theme}: the sheet takes the reading-place question out of its way`);
        }
        await page.context().close();
      }
    }
    // a right-to-left book with its gear open, wide
    const rtl = await newPage(DESK, 'look rtl');
    await open(rtl, 'ar');
    await gearOpen(rtl);
    await shot(rtl, 'look-arabic-gear');
    await rtl.context().close();
  }

  assert(errors.length === 0, 'no page threw: ' + errors.join(' | '));
} finally {
  await browser.close();
  try { hub.kill('SIGTERM'); } catch (_) {}
  try { await hub.status; } catch (_) {}
  await Deno.remove(WORK, {recursive: true}).catch(() => {});
}
console.log(`\ngear_reader: ${passed} checks passed`);
