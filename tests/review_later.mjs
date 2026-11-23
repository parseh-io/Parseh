// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
import { gearSwitch } from './gear_driver.mjs';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/review_later.mjs
//      LATER_SHOTS=<dir> saves the screenshots (and prints where);  LATER_ONLY=a,c runs those scenes alone
//
// REVIEW LATER IN THE BOOK READER AND THE VIDEO PLAYER (a0.5.0, lane G2): the layer that plugs the two pages
// into lib/later.js -- lib/later-reader.js, lib/later-cards.js, the player's own section, the held finger's
// line in lib/wordtouch.js, the door in both headers (lib/mobile.css) -- DRIVEN, in a browser, on the REAL
// hub (tests/later_harness.py: serve.main over a temporary toolbox) and its REAL readers and videos, in the
// browser layout (1280x800, a mouse) and on a phone (390x844, a finger).  The core (the store, the door, the
// sidebar's own rows, /later/) is tests/review_later_core.mjs's; this is what the PAGES do with it.
//
//  a) THE FOUR WAYS TO FLAG IN A BOOK, with a mouse: the door «⚑ later» after «contents»; the cloud's button
//     («review later» -> «✓ marked» -> taken off, with its Undo); the L key on the open cloud's chunk, on the chunk
//     under the pointer, on nothing (a word that says what to do), refused with a modifier, in a field and with a
//     sheet open; the ⚑ beside the pencil (and the pencil still the pencil); the contents panel and the list
//     closing each other; the dotted line (2px, dotted, in the accent) on every pass that has the chunk
//  b) A BOOK OF THREE CHAPTERS, RIGHT TO LEFT: flags in a chapter that has not come are listed and found without
//     fetching it; ▶ brings the chapter, scrolls to the chunk, lights it, sets the reading place and plays nothing;
//     the marks appear on a chapter fetched later; a flag whose subparagraph key changed is found by its
//     paragraph and text; one whose text is gone is adrift, ▶ and + card shut with the reason; Diacritics hidden:
//     the flag keeps the vowelled text, is found again after a reload, and the card carries the vowelled text
//  c) THE CARDS: + card opens today's sheet on that chunk; saved on Anki, on an exercise deck and as markdown the
//     flag leaves the list; cancelled it does not; one after another across three items with Skip, Stop and Esc
//  c2) GOING TO A CHUNK OF A NARRATED BOOK: with the narration stopped ▶ sets the reading place and plays nothing; with
//     it playing, the narration goes to the chunk's subparagraph and on from there
//  d) A PHONE: a held finger's «Review later» line, the door drawn once something is flagged and a finger high,
//     the list as a bottom sheet with no + card and no queue, the first line of the header at 390, 360 and 320
//  e) THE VIDEO, with a mouse and with a finger: the same four ways (no pencil), the dotted line, the door, the
//     list, ▶ seeking and playing, + card and the queue, the sheet after a link
//  e3) THE VIDEO ON THE WHOLE SCREEN (a phone held sideways): nothing new is drawn, and a held finger on a subtitle,
//     which is a copy of a caption, flags that caption's phrase -- the line is under it in the subtitles and the transcript
//  f) TWO DEVICES AND A LINK: a flag made in one browser shows in the other, a removal is not undone; a reload
//     keeps the flags; /later/ opens a book at the chunk (#later=<id>) with the list open
//  g) A READER BUILT BEFORE a0.5.0 gets all of it from lib/parseh.js with no rebuild
//  h) THE THREE THEMES: the new texts are 4.5:1 or better in light, dark and sepia; nothing sideways 320..1280
//  i) NOTHING WENT WRONG: no page threw or logged an error but the ones the machine always logs (the
//     translation model's meta.json is not there), no server traceback, the checkout's config/ as it was
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('LATER_SHOTS') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-later-pages-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(`FAIL: ${m}\n     got  ${JSON.stringify(a)}\n     want ${JSON.stringify(b)}`);
  passed++;
  console.log('  ok', m);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function run(cmd, args) {
  const o = await new Deno.Command(cmd, {args, cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  return {code: o.code, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
function drain(stream, sink) {
  (async () => {
    const r = stream.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; sink.push(value); }
  })();
}
// what config/ holds, as one number, to say it was not touched
const OWN = 'import sys,hashlib;sys.path.insert(0,"tests");import configguard;s=configguard.snapshot();print(hashlib.sha1(repr(sorted(s.items())).encode()).hexdigest())';
const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36';

const configBefore = (await run(PY, ['-c', OWN])).out;
const built = await run(PY, ['tests/later_harness.py', 'build', TMP]);
if (built.code) throw Error('the toolbox could not be built:\n' + built.err + built.out);
const MADE = JSON.parse(built.out.trim().split('\n').pop());
const EN = MADE.readers.en, FA = MADE.multi_fa, MEN = MADE.multi_en, FAB = MADE.readers.fa;
const VID = MADE.en_video, FAV = MADE.fa_video;

const log = [];
const PORT = freePort();
const hub = new Deno.Command(PY, {args: ['tests/later_harness.py', 'serve', TMP, String(PORT)], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
drain(hub.stdout, log); drain(hub.stderr, log);
const B = `http://127.0.0.1:${PORT}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/__activity'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 90000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}

// what the pages log that is NOT a fault: the translation model's two meta files, which this tree has none of
const KNOWN = [/\/mt\/(en-en|engine)\/meta\.json/, /Failed to load resource: the server responded with a status of 404/];
const errors = [];
function watch(page, label) {
  page.on('pageerror', e => errors.push(`${label}: pageerror: ${e.message}`));
  // and the one 409 the video's cards are meant to meet: a card its Anki deck has already is asked about (10.7, scene e)
  const asked = m => /status of 409/.test(m.text()) && /\/anki\/cards$/.test((m.location() || {}).url || '');
  page.on('console', m => { if (m.type() === 'error' && !KNOWN.some(k => k.test(m.text())) && !asked(m)) errors.push(`${label}: console: ${m.text()}`); });
}
async function shot(page, name, opts) {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`, ...(opts || {})});
  console.log('  shot', `${SHOTS}/${name}.png`);
}
async function api(path, body) {
  const r = await fetch(B + path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  return {status: r.status, json: await r.json().catch(() => null)};
}
// every flag the computer holds, removed: each scene begins with an empty list, as a person's first day does
async function wipe() {
  const items = (await api('/__later?all=1')).json.items;
  if (items.length) await api('/__later', {by: 'test', ops: items.map(r => ({op: 'remove', id: r.id, at: Math.max(Date.now() / 1000, r.at + 0.001)}))});
  await sleep(30);
}
async function until(f, ms = 10000, what = '') {
  const t = Date.now();
  for (;;) {
    const v = await f();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('FAIL: timed out waiting for ' + (what || f));
    await sleep(100);
  }
}
// the contrast of every drawn text matching a selector against what is behind it (self-contained: it runs in the page)
function contrastOf(sels) {
  const num = c => c.match(/[\d.]+/g).map(Number);
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const behind = el => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const c = num(getComputedStyle(n).backgroundColor), a = c.length > 3 ? c[3] : 1;
      if (a === 0) continue;
      layers.push([c[0], c[1], c[2], a]);
      if (a === 1) break;
    }
    let base = [255, 255, 255];
    if (layers.length && layers[layers.length - 1][3] === 1) base = layers.pop().slice(0, 3);
    for (let i = layers.length - 1; i >= 0; i--) { const [r, g, b, a] = layers[i]; base = [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)]; }
    return base;
  };
  return sels.flatMap(sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length && e.textContent.trim()).map(e => {
    const a = lum(num(getComputedStyle(e).color)), b = lum(behind(e));
    return {sel, text: e.textContent.trim().slice(0, 24), ratio: +((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toFixed(2)};
  }));
}

// ONE SCENE AFTER ANOTHER, each against an empty list on the computer; a scene that fails is told and the next
// goes on, so that one run says everything that is wrong
const failures = [];
const ONLY = (Deno.env.get('LATER_ONLY') || '').split(',').filter(Boolean);
async function scene(name, fn) {
  if (ONLY.length && !ONLY.some(o => name.startsWith(o + ')'))) return;
  console.log(name);
  try { await wipe(); await fn(); }
  catch (e) { const said = String(e && e.stack || e).split('\n').slice(0, 4).join(' | '); failures.push(name + ' -- ' + said); console.log('  !! ' + said); }
}

const bin = Deno.env.get('CHROME_BIN');
let browser, failure;
async function ctxOf(kind, extra) {
  const phone = kind === 'phone' || (kind && kind.isMobile);
  const opts = kind === 'phone' ? {viewport: {width: 390, height: 844}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID}
    : kind === 'desk' ? {viewport: {width: 1280, height: 800}} : kind;
  // a worker would answer the pages from its cache
  const ctx = await browser.newContext({...opts, serviceWorkers: 'block', permissions: ['clipboard-read', 'clipboard-write'], ...(extra || {})});
  await ctx.addCookies([{name: 'parseh_mode', value: phone ? 'mobile' : 'browser', url: B}]);
  return ctx;
}
async function pageOf(ctx, label) {
  const page = await ctx.newPage();
  watch(page, label);
  if (ctx._options && ctx._options.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  return page;
}
const press = async (page, sel) => { const l = typeof sel === 'string' ? page.locator(sel).first() : sel; if (page.touch) await l.tap(); else await l.click(); };
async function openReader(ctx, path, label = 'reader') {
  const page = await pageOf(ctx, label);
  await page.goto(B + path);
  await page.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel && document.querySelector('[data-parseh-gear]') !== null, null, {timeout: 25000});
  await sleep(350);                     // the reader puts the reading place back a moment after it loads
  if (await page.$('.pf-bar')) await press(page, '.pf-stay');
  return page;
}
async function openVideo(ctx, id = VID, label = 'video') {
  const page = await pageOf(ctx, label);
  await page.goto(B + `/youtube/v/${id}/`);
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.later && ParsehPlayer.later.panel() && document.querySelectorAll('#segs .seg .w').length > 0, null, {timeout: 30000});
  await page.waitForFunction(() => ParsehPlayer.ready(), null, {timeout: 25000});
  await sleep(300);
  return page;
}
// a held finger, as a person holds one: a touch start, 700 ms, a touch end
async function hold(page, sel, ms = 700) {
  await page.locator(sel).first().evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(200);
  const b = await page.locator(sel).first().boundingBox();
  const x = Math.round(b.x + b.width / 2), y = Math.round(b.y + b.height / 2);
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y, radiusX: 4, radiusY: 4, force: 1, id: 1}]});
  await sleep(ms);
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  await sleep(200);
}
const flags = (page, ref) => page.evaluate(ref => ParsehLater.list(ref ? {ref} : undefined), ref);
const count = (page, ref) => page.evaluate(ref => ParsehLater.count(ref ? {ref} : undefined), ref);
const marks = page => page.evaluate(() => [...document.querySelectorAll('.later-mark')].map(e => e.textContent.replace(/\s+/g, ' ').trim()));
// the page paints in a frame of its own after a change: wait for what it paints, as a person's eye does
const textIs = (page, sel, text) => page.waitForFunction(([s, x]) => { const e = document.querySelector(s); return !!e && e.textContent.trim() === x; }, [sel, text], {timeout: 6000});
const marksAre = (page, f) => until(async () => f((await marks(page)).length), 6000, 'the marks');
const doorText = page => page.locator('.later-btn').first().innerText();
// a flag, as the page itself would make it from a chunk's element, laid straight into the store
const flagOf = (page, sel) => page.evaluate(sel => {
  const n = document.querySelector(sel);
  const p = window.ParsehLaterReader ? ParsehLaterReader.record(n) : ParsehPlayer.later.record(n);
  return ParsehLater.add(ParsehLater.record(p)).then(r => r.id);
}, sel);
const toastText = page => page.evaluate(() => { const t = document.getElementById('parseh-toast'); return t && t.classList.contains('show') ? t.textContent : ''; });
const openList = async page => {
  if (!(await page.locator('.lp-wrap:not([hidden])').count())) await press(page, '.later-btn');
  await page.waitForSelector('.lp-wrap:not([hidden]) .lp-panel');
  await sleep(250);                     // each chunk is asked about, a few at a time
};
const rowsOf = page => page.evaluate(() => [...document.querySelectorAll('.lp-body li.lr')].map(li => ({
  id: li.getAttribute('data-id'), state: li.getAttribute('data-state'), text: li.querySelector('.lr-text').textContent,
  place: (li.querySelector('.lr-place') || {}).textContent || '', go: !!li.querySelector('.lr-go:not(:disabled)'), card: li.querySelector('.lr-card') ? !li.querySelector('.lr-card').disabled : null,
  cardWhy: li.querySelector('.lr-card') ? li.querySelector('.lr-card').title : '', goWhy: li.querySelector('.lr-go') ? li.querySelector('.lr-go').title : '',
  dir: li.querySelector('.lr-text').getAttribute('dir')})));
// where a point of an element is: its centre
const centre = (page, sel) => page.locator(sel).first().evaluate(e => { e.scrollIntoView({block: 'center'}); }).then(() => sleep(150))
  .then(() => page.locator(sel).first().boundingBox()).then(b => ({x: b.x + b.width / 2, y: b.y + b.height / 2}));

try {
browser = await chromium.launch({executablePath: bin, headless: true});

/* ====== a) the four ways to flag in a book's reader, a mouse at 1280x800 ====== */
await scene('a) the four ways to flag, in the book reader, with a mouse', async () => {
  const ctx = await ctxOf('desk');
  const page = await openReader(ctx, EN);
  eq(await page.evaluate(() => document.getElementById('toc').nextElementSibling === document.querySelector('.later-btn')
                              && document.querySelector('.later-btn').closest('header') !== null), true,
     'the door «⚑ later» stands right after «contents», in the header');
  eq(await doorText(page), '⚑ later', 'it says «⚑ later», and no count while nothing is flagged');
  await shot(page, 'a1-header');

  // ---- the cloud's button, in hover mode
  await page.click('#hovermode');
  await page.hover('main .p1 .w[data-c="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  eq(await page.evaluate(() => [...document.querySelectorAll('#cloud .mkrow button')].map(b => b.textContent)),
     ['+ card', '⨉ copy', '✎ edit', 'review later'], 'the cloud\'s row gains «review later», beside + card, copy and edit');
  await shot(page, 'a2-cloud');
  await page.click('#cloud .mklater');
  await until(async () => (await count(page, EN)) === 1, 5000, 'the flag');
  await textIs(page, '#cloud .mklater', '✓ marked');
  assert(true, 'the button reads «✓ marked» once set');
  eq(await doorText(page), '⚑ later 1', 'the door counts it');
  const rec = (await flags(page, EN))[0];
  eq([rec.kind, rec.ref, rec.text, rec.lang, rec.glossLang, rec.where.k, rec.where.label, rec.where.chapter, rec.where.para, !!rec.where.sub],
     ['book', EN, 'The old man', 'en', 'en', 0, '1.1', 'chapter 1', '1:1', true], 'the flag is the chunk\'s own: its text, place in the subparagraph, label, chapter and paragraph');
  assert(/old/.test(rec.voc) && rec.en === 'the old man' && rec.tr === 'ðə oʊld mæn' && /put it down/.test(rec.sentence),
         'and its snapshot: the vocabulary line and the meaning and the reading as plain text, and the sentence: ' + JSON.stringify([rec.voc, rec.en, rec.tr]));
  await marksAre(page, n => n >= 2);
  const style = await page.evaluate(() => {
    const e = document.querySelector('main .p1 .w[data-c="0"]'), s = getComputedStyle(e);
    const probe = document.createElement('i'); probe.style.color = 'var(--accent)'; document.body.appendChild(probe);
    const accent = getComputedStyle(probe).color; probe.remove();
    return {line: s.textDecorationLine, style: s.textDecorationStyle, width: s.textDecorationThickness, colour: s.textDecorationColor, accent,
            marked: [...document.querySelectorAll('.later-mark')].map(x => x.className.replace(/\s+/g, ' ')),
            levels: [...new Set([...document.querySelectorAll('.later-mark')].map(x => (x.closest('.pass') || {}).className))]};
  });
  eq([style.line, style.style, style.width, style.colour === style.accent], ['underline', 'dotted', '2px', true],
     'the flagged chunk wears a dotted underline, 2px, in the accent: ' + JSON.stringify(style));
  assert(style.levels.length >= 2, 'on every level that has the chunk -- the sentence and the chunks: ' + JSON.stringify(style.levels));
  await page.click('#cloud .mklater');
  await until(async () => (await count(page, EN)) === 0, 5000, 'the flag taken off');
  await textIs(page, '#cloud .mklater', 'review later');
  assert(true, 'pressed again, it takes the flag off');
  await marksAre(page, n => n === 0);
  assert(true, 'and the line goes');
  assert(await page.evaluate(() => document.getElementById('later-snack').classList.contains('ls-show') && /removed/.test(document.getElementById('later-snack').textContent)),
         'with the list\'s «removed · Undo» line');
  await page.click('#later-snack .ls-undo');
  await until(async () => (await count(page, EN)) === 1, 5000, 'Undo');
  await marksAre(page, n => n >= 2);
  assert(true, 'Undo puts the flag, and its line, back');
  await page.evaluate(() => ParsehLater.remove(ParsehLater.list()[0].id, {toast: false}));
  await until(async () => (await count(page, EN)) === 0, 5000);

  // ---- the L key: on the open cloud's chunk
  await page.hover('main .p1 .w[data-c="1"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden && /^review later|✓ marked/.test(document.querySelector('#cloud .mklater').textContent));
  await page.keyboard.press('l');
  await until(async () => (await count(page, EN)) === 1, 5000, 'L on the cloud');
  eq((await flags(page, EN))[0].text, 'wound the clock', 'L flags the chunk the open cloud is for');
  await textIs(page, '#cloud .mklater', '✓ marked');
  assert(true, 'and the cloud says so');
  await page.keyboard.press('L');
  await until(async () => (await count(page, EN)) === 0, 5000);
  assert(true, 'L (a capital too) takes it off again');

  // ---- on the chunk under the pointer, with no cloud (hover mode off, the sentence level)
  await page.click('#hovermode');
  const c2 = await centre(page, 'main .p1 .w[data-c="2"]');
  await page.mouse.move(c2.x, c2.y);
  await sleep(250);
  await page.keyboard.press('l');
  await until(async () => (await count(page, EN)) === 1, 5000, 'L on the pointer');
  eq((await flags(page, EN))[0].text, 'and put it down.', 'L flags the chunk under the pointer');
  assert((await toastText(page)).includes('marked to review later'), 'and says so');
  await page.keyboard.press('l');
  await until(async () => (await count(page, EN)) === 0, 5000);
  // ... and on a row of the chunks level
  const row = await centre(page, 'main .row[data-c="1"] .fa');
  await page.mouse.move(row.x, row.y);
  await sleep(250);
  await page.keyboard.press('l');
  await until(async () => (await count(page, EN)) === 1, 5000, 'L on a row');
  eq((await flags(page, EN))[0].text, 'wound the clock', 'L reaches the chunks level too');
  await page.keyboard.press('l');
  await until(async () => (await count(page, EN)) === 0, 5000);

  // ---- on nothing; with a modifier; in a field; with a sheet open
  await page.mouse.move(8, 500);
  await sleep(700);                                   // the pencil's own grace (300 ms) is over: no chunk is the pointer's
  await page.keyboard.press('l');
  await sleep(250);
  assert((await toastText(page)).includes('point at a chunk first, then press L'), 'on nothing, L says to point at a chunk first: ' + (await toastText(page)));
  eq(await count(page, EN), 0, 'and flags nothing');
  await page.mouse.move(c2.x, c2.y);
  await sleep(200);
  await page.keyboard.press('Control+l');
  await page.keyboard.press('Alt+l');
  await sleep(200);
  eq(await count(page, EN), 0, 'with a modifier L does nothing');
  await page.keyboard.press('c');                      // the contents' own key
  await page.waitForFunction(() => !document.getElementById('tocwrap').hidden);
  await page.click('#tocq');
  await page.keyboard.type('l');
  await sleep(200);
  eq([await count(page, EN), await page.inputValue('#tocq')], [0, 'l'], 'typing an l in a field flags nothing, and the field has it');
  await page.keyboard.press('Escape');
  await page.mouse.move(c2.x, c2.y);
  await page.click('main .p1 .wd[data-w], main .p1 .wd', {modifiers: ['Alt'], position: {x: 3, y: 3}}).catch(() => {});
  if (await page.evaluate(() => !document.getElementById('anki').hidden)) {
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    await page.mouse.move(c2.x, c2.y);
    await page.keyboard.press('l');
    await sleep(200);
    eq(await count(page, EN), 0, 'with a card sheet open L does nothing');
    await page.click('#acancel');
  } else assert(false, 'the card sheet did not open to be tried');

  // ---- the ⚑ beside the pencil, at the chunks level, with no hover mode
  const r1 = await centre(page, 'main .row[data-c="3"] .fa');
  await page.mouse.move(r1.x, r1.y);
  await page.waitForFunction(() => !document.getElementById('chpen').hidden);
  await sleep(200);
  const where = await page.evaluate(() => {
    const p = document.getElementById('chpen').getBoundingClientRect(), f = document.querySelector('.later-flag');
    if (!f || f.hidden) return null;
    const r = f.getBoundingClientRect();
    return {leftOfPencil: r.right <= p.left + 1, sameRow: Math.abs(r.top - p.top) < 3, h: Math.round(r.height), text: f.textContent};
  });
  eq([where && where.leftOfPencil, where && where.sameRow, where && where.text], [true, true, '⚑'], 'the ⚑ stands at the pencil\'s left, on its line: ' + JSON.stringify(where));
  await shot(page, 'a3-flag-by-pencil', {clip: {x: 200, y: 330, width: 800, height: 260}});
  const fb = await page.locator('.later-flag').boundingBox();
  await page.mouse.move(fb.x + fb.width / 2, fb.y + fb.height / 2);
  await sleep(500);                                   // the pencil's own grace is 300 ms: the pointer is on the ⚑ and it stays
  assert(await page.evaluate(() => !document.querySelector('.later-flag').hidden && !document.getElementById('chpen').hidden), 'the pointer on the ⚑ keeps it and the pencil there');
  await page.mouse.click(fb.x + fb.width / 2, fb.y + fb.height / 2);
  await until(async () => (await count(page, EN)) === 1, 5000, 'the ⚑');
  eq((await flags(page, EN))[0].text, 'He hadn\'t slept,', 'a click on the ⚑ flags the pencil\'s chunk');
  await textIs(page, '.later-flag', '✓⚑');
  assert(true, 'and the ⚑ says it is flagged');
  await page.mouse.click(fb.x + fb.width / 2, fb.y + fb.height / 2);
  await until(async () => (await count(page, EN)) === 0, 5000);
  assert(true, 'a second click takes it off');
  await page.mouse.move(r1.x, r1.y);
  await sleep(300);
  await page.click('#chpen');
  await page.waitForFunction(() => !document.getElementById('chbox').hidden);
  assert(true, 'the pencil is still the pencil: it opens the chunk\'s sheet');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.getElementById('chbox').hidden);

  // ---- the list and the contents close each other; the list keeps the page live
  await flagOf(page, 'main .p1 .w[data-c="0"]');
  await openList(page);
  assert(await page.evaluate(() => !document.querySelector('.lp-wrap').hidden), 'the list opens from the door');
  await page.click('#toc');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && !document.getElementById('tocwrap').hidden);
  assert(true, 'opening the contents shuts the list');
  await press(page, '.later-btn');
  await page.waitForFunction(() => !document.querySelector('.lp-wrap').hidden && document.getElementById('tocwrap').hidden);
  assert(true, 'and opening the list shuts the contents');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden);
  assert(true, 'Esc shuts the list');
  // reload: the flag and its line are there
  await page.reload();
  await page.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel);
  await until(async () => (await marks(page)).length >= 2, 8000, 'the marks after a reload');
  eq(await doorText(page), '⚑ later 1', 'a reload keeps the flag, its line and the count');
  await ctx.close();
});

/* ====== b) a book of three chapters, right to left ====== */
await scene('b) a book of three chapters, right to left: the chapter that has not come, adrift, the vowels', async () => {
  const ctx = await ctxOf('desk');
  let page = await openReader(ctx, FA);
  eq(await page.evaluate(() => document.querySelectorAll('section.chapter[data-part]').length), 2, 'the book comes with its first chapter only; the other two are files');
  // flag a chunk of chapter 3: bring it, point at it, press L
  await page.evaluate(() => needChapters(2));
  const sel3 = 'section.chapter[data-ch="2"] .p1 .w[data-c="85"]';
  const p3 = await centre(page, sel3);
  await page.mouse.move(p3.x, p3.y);
  await sleep(250);
  await page.keyboard.press('l');
  await until(async () => (await count(page, FA)) === 1, 5000, 'L in chapter 3');
  const f3 = (await flags(page, FA))[0];
  const para3 = await page.evaluate(s => document.querySelector(s).closest('.para').dataset.p, sel3);
  eq([f3.where.para, f3.where.k, f3.where.label.length > 0, f3.lang, f3.glossLang], [para3, 1, true, 'fa', 'en'], 'a chunk of chapter 3 is flagged by its paragraph and its place: ' + JSON.stringify(f3.where));
  assert(/[ً-ْ]/.test(f3.text), 'with the book\'s own vowelled text: ' + f3.text);
  // and one in chapter 1, by the cloud
  await page.click('#hovermode');
  await page.hover('main .p1 .w[data-c="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.click('#cloud .mklater');
  await until(async () => (await count(page, FA)) === 2, 5000, 'the cloud in chapter 1');
  await page.click('#hovermode');
  // reload: chapters 2 and 3 are files again
  await page.reload();
  await page.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel);
  await until(async () => (await marks(page)).length >= 2, 8000, 'chapter 1\'s marks');
  eq(await page.evaluate(() => document.querySelectorAll('section.chapter[data-part]').length), 2, 'a reload: the chapters are files again');
  eq(await page.evaluate(() => document.querySelector('section.chapter[data-ch="2"] .later-mark')), null, 'and nothing of chapter 3 is marked, it is not on the page');
  await openList(page);
  const rows = await rowsOf(page);
  eq(rows.map(r => r.state), ['found', 'found'], 'the list holds both, and neither is adrift');
  eq(rows.map(r => r.dir), ['rtl', 'rtl'], 'each chunk is set right to left');
  assert(await page.evaluate(() => { const t = document.querySelector('.lp-body .lr-text'); return getComputedStyle(t).direction === 'rtl' && getComputedStyle(t).fontFamily.length > 0; }), 'in the language\'s own direction and face');
  eq(rows.map(r => r.place.replace(/[^\d.:]/g, '').length > 0), [true, true], 'with their places: ' + JSON.stringify(rows.map(r => r.place)));
  await shot(page, 'b1-list-rtl');
  eq(await page.evaluate(() => document.querySelectorAll('section.chapter[data-part]').length), 2, 'asking where they are fetched no chapter');
  // ▶ on the chapter-3 one
  await page.evaluate(() => { window.__aud = document.getElementById('audio'); });
  await page.click('.lp-body li.lr:nth-child(2) .lr-go');
  await page.waitForFunction(() => !document.querySelector('section.chapter[data-ch="2"][data-part]'), null, {timeout: 10000});
  await page.waitForFunction(() => document.querySelector('.later-flash') !== null, null, {timeout: 5000});
  const landed = await page.evaluate(() => {
    const e = document.querySelector('.later-flash'), r = e.getBoundingClientRect(), sub = e.closest('.sub');
    return {mid: Math.round(r.top + r.height / 2), vh: innerHeight, cur: cur, sub: +sub.dataset.s, onAir: !!document.querySelector('.on-air'),
            pos: JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => /^bk_pos/.test(k))) || 'null'),
            paused: document.getElementById('audio').paused, panel: !document.querySelector('.lp-wrap').hidden, text: e.textContent.trim()};
  });
  assert(Math.abs(landed.mid - landed.vh / 2) < 140, 'a chunk of a chapter that had not come: its chapter fetched, the chunk scrolled to the middle: ' + JSON.stringify(landed));
  eq([landed.cur, landed.onAir, landed.paused, landed.panel], [landed.sub, true, true, false], 'it is lit, the reading place is its subparagraph, nothing plays, and the list stands aside');
  eq(landed.pos && landed.pos.i, landed.sub, 'and the place is saved');
  await page.waitForFunction(() => !!document.querySelector('section.chapter[data-ch="2"] .later-mark'), null, {timeout: 6000});
  assert(true, 'the marks are on the chapter that was fetched later');
  await shot(page, 'b2-went');

  // ---- a changed subparagraph key is found by the paragraph and the text; a chunk that is gone is adrift
  const keyless = await page.evaluate(() => {
    const p = ParsehLaterReader.record(document.querySelector('main section.chapter[data-ch="0"] .p1 .w[data-c="2"]'));
    return ParsehLater.add(ParsehLater.record({...p, sub: '9.9-deadbeefdead'})).then(r => r.id);
  });
  const gone = await page.evaluate(() => {
    const p = ParsehLaterReader.record(document.querySelector('main section.chapter[data-ch="0"] .p1 .w[data-c="3"]'));
    return ParsehLater.add(ParsehLater.record({...p, sub: '9.9-deadbeefdead', para: '9:9', text: 'یک چیزِ دیگر'})).then(r => r.id);
  });
  await page.waitForFunction(() => document.querySelectorAll('.lp-body li.lr').length === 4);
  await sleep(500);
  const r2 = Object.fromEntries((await rowsOf(page)).map(r => [r.id, r]));
  eq([r2[keyless].state, r2[keyless].go], ['found', true], 'a flag whose subparagraph key has changed is still found, by its paragraph and its text');
  eq([r2[gone].state, r2[gone].go, r2[gone].card], ['adrift', false, false], 'one whose paragraph and text are gone is ADRIFT: listed, ▶ and + card shut');
  assert(/no longer where it was/.test(r2[gone].goWhy) && /no longer where it was/.test(r2[gone].cardWhy), 'each saying why: ' + r2[gone].goWhy);
  assert(await page.evaluate(id => document.querySelector(`li.lr[data-id="${CSS.escape(id)}"] .lr-why`) !== null, gone), 'and the row says so in words');
  await shot(page, 'b3-adrift');
  await page.evaluate(id => ParsehLater.remove(id, {toast: false}), gone);

  // ---- Diacritics hidden: the flag keeps the book's own text
  await page.keyboard.press('Escape');
  await gearSwitch(page, 'marks', false);
  await sleep(200);
  const bare = await page.evaluate(() => document.querySelector('main .p1 .w[data-c="1"]').textContent);
  assert(!/[ً-ْ]/.test(bare), 'Diacritics hidden: the page draws the chunk with no marks: ' + bare);
  const c1 = await centre(page, 'main .p1 .w[data-c="1"]');
  await page.mouse.move(c1.x, c1.y);
  await sleep(250);
  await page.keyboard.press('l');
  await until(async () => (await flags(page, FA)).some(r => r.where.k === 1 && r.where.para === '1:1'), 5000, 'L with the marks hidden');
  const kept = (await flags(page, FA)).find(r => r.where.k === 1 && r.where.para === '1:1');
  assert(/[ً-ْ]/.test(kept.text), 'the flag keeps the vowelled text: ' + kept.text);
  assert((await marks(page)).some(t => !/[ً-ْ]/.test(t)), 'and the line is under the bare chunk');
  await page.reload();
  await page.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel);
  await until(async () => (await marks(page)).length > 0, 8000, 'marks with the marks hidden');
  eq(await page.evaluate(() => document.querySelectorAll('main .p1 .w[data-c="1"].later-mark').length), 1, 'a flagged chunk with its marks hidden is found again after a reload');
  await openList(page);
  const kr = (await rowsOf(page)).find(r => r.text === kept.text);
  eq(kr && kr.state, 'found', 'and the list finds it');
  await page.click(`li.lr[data-id="${await page.evaluate(id => CSS.escape(id), kept.id)}"] .lr-card`);
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  eq(await page.inputValue('#afa'), kept.text, '+ card carries the vowelled text, though the page draws none');
  await page.click('#acancel');
  await gearSwitch(page, 'marks', true);
  await ctx.close();
});

/* ====== c) the cards ====== */
await scene('c) the cards: saved on three targets, cancelled, one after another', async () => {
  const ctx = await ctxOf('desk');
  const page = await openReader(ctx, EN);
  const ids = [];
  for (const n of [0, 1, 2, 3]) ids.push(await flagOf(page, `main .p1 .w[data-c="${n}"]`));
  await openList(page);
  eq((await rowsOf(page)).map(r => r.text), ['The old man', 'wound the clock', 'and put it down.', 'He hadn\'t slept,'], 'four flags, in reading order');
  eq((await rowsOf(page)).map(r => r.card), [true, true, true, true], '+ card is offered on each');
  // ---- + card, Anki: the sheet is today's, on that chunk
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  const sheet = await page.evaluate(() => ({fa: afa.value, ctx: actx.value, notes: anotes.value, tr: atr.value, en: aen.value, src: asrc.value, list: !document.querySelector('.lp-wrap').hidden}));
  eq([sheet.fa, sheet.en, sheet.tr, /^The old man wound the clock/.test(sheet.ctx), /old/.test(sheet.notes), sheet.list],
     ['The old man', 'the old man', 'ðə oʊld mæn', true, true, true], 'the sheet opens as the cloud\'s + card opens it, on that chunk, the list staying behind it: ' + JSON.stringify(sheet));
  await shot(page, 'c1-sheet');
  // cancelled: the flag stays
  await page.click('#acancel');
  await sleep(300);
  eq(await count(page, EN), 4, 'a card not saved takes nothing off the list');
  assert((await rowsOf(page))[0].card === true, 'and the row\'s + card is there again');
  // saved
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.selectOption('#adeck', '').catch(() => {});
  await page.fill('#adecknew', 'Later::Cards');
  await page.click('#asave');
  await until(async () => (await count(page, EN)) === 3, 8000, 'the Anki save');
  assert((await page.evaluate(() => document.getElementById('astat').textContent)).includes('saved ✓') || (await toastText(page)).includes('saved'), 'saved on Anki, for real: the flag leaves');
  await page.waitForFunction(() => document.getElementById('anki').hidden, null, {timeout: 5000});
  assert((await page.evaluate(() => document.getElementById('later-snack').textContent)).includes('card saved · removed from the list'), 'with the list\'s own line about it');
  // ---- an exercise deck
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.click('#atdeck');
  await page.selectOption('#adeck', '').catch(() => {});
  await page.fill('#adecknew', 'Later deck');
  await page.click('#asave');
  await until(async () => (await count(page, EN)) === 2, 8000, 'the exercise deck save');
  assert((await page.evaluate(() => document.getElementById('astat').textContent)).includes('added ✓'), 'added to an exercise deck, for real: the flag leaves: ' + await page.evaluate(() => document.getElementById('astat').textContent));
  await page.click('#acancel');
  // ---- markdown on the clipboard
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.click('#atmd');
  await page.click('#asave');
  await until(async () => (await count(page, EN)) === 1, 8000, 'the markdown copy');
  assert((await page.evaluate(() => navigator.clipboard.readText())).includes(':::exercise flashcard'), 'copied as markdown, for real: the flag leaves, and the clipboard has the card');
  await page.click('#acancel');

  // ---- one after another, across three items: save, Skip, save
  for (const n of [1, 2]) ids.push(await flagOf(page, `main .p1 .w[data-c="${n}"]`));
  await sleep(300);
  eq(await count(page, EN), 3, 'three flags, for the queue');
  await page.waitForSelector('.lp-cards:not([hidden]), .lp-cards');
  await page.click('.lp-cards');
  await page.waitForFunction(() => !document.getElementById('anki').hidden && document.querySelector('#anki .lq-strip'));
  eq(await page.evaluate(() => [document.querySelector('.lq-n').textContent, document.querySelector('#anki .lq-strip').parentNode.id, afa.value]), ['item 1 of 3', 'anki', 'wound the clock'],
     'the strip «item 1 of 3» is the first thing in the card sheet, on the first chunk');
  await shot(page, 'c2-queue');
  await page.click('#atanki');
  await page.click('#asave');
  await until(async () => (await count(page, EN)) === 2, 8000, 'the first of the queue');
  await page.waitForFunction(() => document.querySelector('.lq-n') && document.querySelector('.lq-n').textContent === 'item 2 of 3' && afa.value === 'and put it down.', null, {timeout: 8000});
  assert(true, 'saved, the next sheet opens by itself: «item 2 of 3», on the next chunk');
  await page.click('.lq-skip');
  await page.waitForFunction(() => document.querySelector('.lq-n') && document.querySelector('.lq-n').textContent === 'item 3 of 3' && afa.value === 'He hadn\'t slept,', null, {timeout: 8000});
  eq(await count(page, EN), 2, 'Skip leaves the flag where it is and goes to the next');
  await page.click('#asave');
  await until(async () => (await count(page, EN)) === 1, 8000, 'the last of the queue');
  await page.waitForFunction(() => document.getElementById('anki').hidden && !document.querySelector('.lq-strip'), null, {timeout: 8000});
  assert((await toastText(page)).includes('2 cards saved · 1 skipped') || (await page.evaluate(() => document.getElementById('parseh-toast').textContent)).includes('2 cards saved'),
         'at the end the strip is gone and a line says what came of it: ' + (await page.evaluate(() => document.getElementById('parseh-toast').textContent)));
  eq((await flags(page, EN)).map(r => r.text), ['and put it down.'], 'only the skipped one is left');
  // ---- Stop, and Esc
  for (const n of [0, 1]) await flagOf(page, `main .p1 .w[data-c="${n}"]`);
  await sleep(300);
  await page.click('.lp-cards');
  await page.waitForFunction(() => !document.getElementById('anki').hidden && document.querySelector('.lq-strip'));
  await page.click('.lq-stop');
  await page.waitForFunction(() => document.getElementById('anki').hidden && !document.querySelector('.lq-strip'));
  eq(await count(page, EN), 3, 'Stop shuts the sheet and ends it, and no flag is taken off');
  await page.click('.lp-cards');
  await page.waitForFunction(() => !document.getElementById('anki').hidden && document.querySelector('.lq-strip'));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.getElementById('anki').hidden && !document.querySelector('.lq-strip'));
  await sleep(500);
  assert(!(await page.evaluate(() => document.getElementById('anki').hidden === false)), 'Esc on the sheet ends it too, and the next does not open');
  eq(await count(page, EN), 3, 'with every flag still there');
  await ctx.close();
});

/* ====== c2) going to a chunk of a narrated book ====== */
await scene('c2) going to a chunk of a narrated book: nothing plays; a narration that is playing follows', async () => {
  const ctx = await ctxOf('desk');
  const page = await openReader(ctx, EN);
  await flagOf(page, 'main .p1 .w[data-c="0"]');
  await flagOf(page, 'main .p1 .w[data-c="3"]');
  await openList(page);
  await page.click('li.lr:nth-child(2) .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && document.querySelector('.later-flash'));
  const still = await page.evaluate(() => ({paused: document.getElementById('audio').paused, cur: cur, sub: +document.querySelector('.later-flash').closest('.sub').dataset.s, t: document.getElementById('audio').currentTime}));
  eq([still.paused, still.cur === still.sub, still.sub], [true, true, 1], 'with the narration stopped ▶ sets the reading place on the chunk\'s subparagraph and plays nothing');
  await sleep(400);
  assert(await page.evaluate(() => document.getElementById('audio').paused), 'and nothing starts afterwards');
  await page.click('#play');
  await page.waitForFunction(() => !document.getElementById('audio').paused, null, {timeout: 8000});
  await openList(page);
  await page.click('li.lr:nth-child(1) .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && cur === 0, null, {timeout: 5000});
  const follow = await page.evaluate(() => ({cur: cur, t: document.getElementById('audio').currentTime, paused: document.getElementById('audio').paused}));
  assert(follow.cur === 0 && follow.t >= 0.7 && follow.t < 3.9, 'with the narration playing, ▶ takes it to the chunk\'s subparagraph and it goes on from there: ' + JSON.stringify(follow));
  await page.evaluate(() => document.getElementById('play').click());
  await ctx.close();
});

/* ====== d) a phone ====== */
await scene('d) a phone: the held finger, the door, the list as a sheet, the first line', async () => {
  const ctx = await ctxOf('phone');
  const page = await openReader(ctx, EN);
  assert(await page.evaluate(() => document.querySelector('.later-btn').hidden && document.querySelector('.later-btn').getClientRects().length === 0),
         'with nothing flagged the door is not on a phone\'s first line');
  await hold(page, 'main .p1 .wd');
  const rows = await page.evaluate(() => [...document.querySelectorAll('.wt-menu button')].map(b => b.textContent));
  eq(rows, ['Copy “The old man”', 'Copy the sentence', 'Review later: “The old man”'], 'a held finger opens «Review later: “…”» beside the copies');
  await page.click('.wt-menu button:last-child');
  await until(async () => (await count(page, EN)) === 1, 5000, 'the held finger');
  await marksAre(page, n => n >= 2);
  assert(true, 'the chunk wears its dotted line');
  assert((await toastText(page)).includes('marked to review later'), 'and a line says it was flagged');
  const door = await page.evaluate(() => { const b = document.querySelector('.later-btn'), r = b.getBoundingClientRect(); return {w: Math.round(r.width), h: Math.round(r.height), hidden: b.hidden, text: b.innerText.replace(/\s+/g, ' ')}; });
  assert(door.h >= 48 && door.w >= 48 && !door.hidden && door.text === '⚑ 1', 'the door is there now, a finger high, «⚑ 1»: ' + JSON.stringify(door));
  await shot(page, 'd1-header-390');
  await hold(page, 'main .p1 .wd');
  eq(await page.evaluate(() => document.querySelector('.wt-menu button:last-child').textContent), 'Take “The old man” off review later', 'held again, the line offers to take it off');
  await page.click('.wt-menu button:last-child');
  await until(async () => (await count(page, EN)) === 0, 5000);
  assert(await page.evaluate(() => document.querySelector('.later-btn').hidden), 'and with nothing flagged the door goes again');
  // the list as a sheet
  await flagOf(page, 'main .p1 .w[data-c="1"]');
  await flagOf(page, 'main .p1 .w[data-c="2"]');
  await press(page, '.later-btn');
  await page.waitForSelector('.lp-wrap.lp-sheet:not([hidden]) .lp-panel');
  await sleep(300);
  eq(await page.evaluate(() => [!!document.querySelector('.lr-card'), !!document.querySelector('.lp-cards:not([hidden])'), document.querySelectorAll('.lr-go').length]), [false, false, 2],
     'the list is a sheet from the foot of the screen: ▶ and ✕, no + card, no «one after another»');
  await shot(page, 'd2-sheet');
  const fits = await page.evaluate(() => [...document.querySelectorAll('.lp-panel .lr-b, .lp-panel .lp-b, .lp-panel .lp-sc, .lp-panel .lp-x')].filter(b => b.getClientRects().length).map(b => { const r = b.getBoundingClientRect(); return Math.min(r.width, r.height); }));
  assert(fits.every(v => v >= 47.5), 'every control in it is a finger high: ' + Math.min(...fits));
  await press(page, 'li.lr:nth-child(2) .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && document.querySelector('.later-flash'));
  assert(true, '▶ goes to the chunk and puts the sheet away');
  // the cloud's button, in hover mode, with a tap
  await page.evaluate(() => scrollTo(0, 0));
  await sleep(300);
  await press(page, '#hovermode').catch(() => {});
  if (!(await page.evaluate(() => document.body.classList.contains('hovermode')))) await gearSwitch(page, 'hover', true);
  await press(page, 'main .p1 .w[data-c="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  const mk = await page.evaluate(() => { const b = document.querySelector('#cloud .mklater'); const r = b.getBoundingClientRect(); return {h: Math.round(r.height), text: b.textContent}; });
  assert(mk.h >= 48 && mk.text === 'review later', 'on a phone the cloud\'s button is there, a finger high: ' + JSON.stringify(mk));
  await press(page, '#cloud .mklater');
  await until(async () => (await count(page, EN)) === 3, 5000, 'the cloud\'s button, tapped');
  await ctx.close();
  // the first line, at three widths: seven targets at 360 and above, and under 360 the door takes a line below the six
  for (const [w, line] of [[390, 1], [360, 1], [320, 2]]) {
    const c = await ctxOf({viewport: {width: w, height: 800}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID});
    const p = await openReader(c, EN);
    const t = await p.evaluate(() => [...document.querySelectorAll('header a[href], header button')].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect(); return {n: e.id || (e.hasAttribute('data-parseh-gear') ? 'gear' : e.classList.contains('later-btn') ? 'later' : e.className.split(' ')[0]), top: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right)}; }));
    const tops = [...new Set(t.map(x => x.top))];
    eq([t.map(x => x.n).includes('later'), tops.length, t.every(x => x.w >= 47.5 && x.h >= 47.5), t.every(x => x.right <= w)], [true, line, true, true],
       `${w}px: «⚑ 3» and the first line's other targets: ${line === 1 ? 'all on one line' : 'six on the line and the door on a line of its own'}, each 48px, on the screen: ${JSON.stringify(t.map(x => x.n + '@' + x.top))}`);
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${w}px: nothing sideways`);
    await shot(p, 'd3-header-' + w);
    await c.close();
  }
});

/* ====== e) the video, with a mouse and with a finger ====== */
const seg = (i, j = 0) => `#segs .seg[data-i="${i}"] .w[data-j="${j}"]`;
await scene('e) the video, with a mouse: the four ways, the dotted line, the list, going there, the cards', async () => {
  const ctx = await ctxOf('desk');
  const page = await openVideo(ctx);
  eq(await page.evaluate(() => document.querySelector('header .ttl').nextElementSibling === document.querySelector('.later-btn')), true, 'the door «⚑ later» stands right after the title, in the header');
  eq(await doorText(page), '⚑', 'in a window of 1280px it is the compact «⚑», the word «later» being for a window with room (below), and no count while nothing is flagged');
  assert(await page.evaluate(() => document.querySelector('header').getBoundingClientRect().height < 60), 'and the header is still one row: the door did not send the gear down a line');
  await shot(page, 'e1-header');
  await page.hover(seg(1, 0));
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  eq(await page.evaluate(() => { const b = [...document.querySelectorAll('#cloud .mkrow button')]; return [b.length, b[b.length - 1].textContent]; }), [4, 'review later'], 'the cloud\'s row ends with «review later»');
  await shot(page, 'e2-cloud');
  await page.click('#cloud .mklater');
  await until(async () => (await count(page, VID)) === 1, 5000, 'the flag');
  await textIs(page, '#cloud .mklater', '✓ marked');
  assert(true, 'pressed, it reads «✓ marked»');
  const rec = (await flags(page, VID))[0];
  eq([rec.kind, rec.ref, rec.text, rec.where.start, rec.where.j, rec.where.text, rec.lang, rec.glossLang, rec.title, rec.en, /market/.test(rec.voc)],
     ['video', VID, 'The market', 2, 0, 'The market opens early.', 'en', 'en', 'Four lines', 'the place of the stalls', true], 'the flag is the phrase: caption start, place, caption text, and its snapshot: ' + JSON.stringify(rec.where));
  await marksAre(page, n => n === 1);
  const st = await page.evaluate(seg => { const s = getComputedStyle(document.querySelector(seg)); return [s.textDecorationLine, s.textDecorationStyle, s.textDecorationThickness]; }, seg(1, 0));
  eq(st, ['underline', 'dotted', '2px'], 'the phrase wears the dotted line');
  await page.click('#cloud .mklater');
  await until(async () => (await count(page, VID)) === 0, 5000);
  await marksAre(page, n => n === 0);
  assert(true, 'pressed again, the flag goes and so does the line');
  // L on the cloud's phrase; L on the pointer's phrase with the cloud shut; L on nothing
  await page.hover(seg(2, 1));
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.keyboard.press('l');
  await until(async () => (await count(page, VID)) === 1, 5000, 'L');
  eq((await flags(page, VID))[0].text, 'today.', 'L flags the phrase the open cloud is for');
  await page.evaluate(() => document.dispatchEvent(new MouseEvent('click', {bubbles: true})));
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  await page.keyboard.press('l');
  await until(async () => (await count(page, VID)) === 0, 5000, 'L on the pointer');
  assert(true, 'with the cloud shut, L takes the flag off the phrase under the pointer');
  await page.mouse.move(40, 300);
  await sleep(300);
  await page.keyboard.press('l');
  await sleep(250);
  assert((await toastText(page)).includes('point at a phrase first, then press L'), 'on nothing L says to point at a phrase first: ' + await toastText(page));
  await page.hover(seg(1, 1));
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.keyboard.press('Control+l');
  await sleep(200);
  eq(await count(page, VID), 0, 'with a modifier L does nothing');
  await press(page, '#cloud .mkcard');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.focus('#afa');
  await page.keyboard.type('l');
  eq([await count(page, VID), (await page.inputValue('#afa')).endsWith('l')], [0, true], 'in the card sheet L is a letter, and flags nothing');
  await page.click('#acancel');

  // the list; going there
  for (const [i, j] of [[1, 0], [2, 0], [3, 1]]) await flagOf(page, seg(i, j));
  await openList(page);
  const rows = await rowsOf(page);
  eq(rows.map(r => [r.text, r.place, r.state]), [['The market', '0:02', 'found'], ['Bring a bag', '0:04', 'found'], ['fresh bread.', '0:06', 'found']], 'the list: the phrases in the order of the video, each with its clock time');
  await shot(page, 'e3-list');
  await page.click('li.lr:nth-child(3) .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && document.querySelector('.later-flash') !== null);
  await until(async () => await page.evaluate(() => !ParsehPlayer.paused() && ParsehPlayer.time() >= 6), 8000, 'the video at the caption');
  await page.waitForFunction(() => { const s = document.querySelector('#segs .seg.on-air'); return !!s && s.dataset.i === '3'; }, null, {timeout: 8000});
  const went = await page.evaluate(() => { const s = document.querySelector('#segs .seg.on-air'), r = (document.querySelector('.later-flash') || s).getBoundingClientRect(); return {on: s && s.dataset.i, mid: Math.round(r.top + r.height / 2), vh: innerHeight}; });
  eq(went.on, '3', '▶ takes the video to the caption and plays it: the caption is on air, the list stands aside, the phrase is lit');
  await page.evaluate(() => ParsehPlayer.pause());
  assert(went.mid > 60 && went.mid < went.vh, 'and the phrase is on the screen: ' + JSON.stringify(went));
  // remove + Undo
  await openList(page);
  await page.click('li.lr:nth-child(1) .lr-x');
  await until(async () => (await count(page, VID)) === 2, 5000);
  await page.click('#later-snack .ls-undo');
  await until(async () => (await count(page, VID)) === 3, 5000);
  assert(true, '✕ removes and Undo puts it back');
  // adrift; a caption whose start moved is still found
  const moved = await page.evaluate(() => { const p = ParsehPlayer.later.record(document.querySelector('#segs .seg[data-i="2"] .w[data-j="1"]')); return ParsehLater.add(ParsehLater.record({...p, start: 4.5})).then(r => r.id); });
  const lost = await page.evaluate(() => { const p = ParsehPlayer.later.record(document.querySelector('#segs .seg[data-i="2"] .w[data-j="1"]')); return ParsehLater.add(ParsehLater.record({...p, start: 99, cap: 'a caption that is not there', text: 'not a phrase of this video'})).then(r => r.id); });
  await page.waitForFunction(() => document.querySelectorAll('.lp-body li.lr').length === 5);
  await sleep(500);
  const r2 = Object.fromEntries((await rowsOf(page)).map(r => [r.id, r]));
  eq([r2[moved].state, r2[moved].go], ['found', true], 'a phrase whose caption has moved is found by the caption\'s text');
  eq([r2[lost].state, r2[lost].go, r2[lost].card], ['adrift', false, false], 'one that is gone is adrift: ▶ and + card shut');
  await page.evaluate(id => ParsehLater.remove(id, {toast: false}), lost);
  await page.evaluate(id => ParsehLater.remove(id, {toast: false}), moved);

  // the cards: Anki, an exercise deck, markdown, cancelled, one after another
  await page.waitForFunction(() => document.querySelectorAll('.lp-body li.lr').length === 3);
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  const sheet = await page.evaluate(() => ({fa: afa.value, en: aen.value, ctx: actx.value, notes: anotes.value}));
  eq([sheet.fa, sheet.en, sheet.ctx, /market/.test(sheet.notes)], ['The market', 'the place of the stalls', 'The market opens early.', true], 'the card sheet opens on that phrase: ' + JSON.stringify(sheet));
  await page.click('#acancel');
  await sleep(250);
  eq(await count(page, VID), 3, 'cancelled, nothing leaves the list');
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.click('#atanki');
  await page.selectOption('#adeck', '').catch(() => {});
  await page.fill('#adecknew', 'Later::Video');
  await page.click('#asave');
  await until(async () => (await count(page, VID)) === 2, 8000, 'the Anki save');
  assert(true, 'saved on Anki, the flag leaves');
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.click('#atdeck');
  await page.selectOption('#adeck', '').catch(() => {});
  await page.fill('#adecknew', 'Later video deck');
  await page.click('#asave');
  await until(async () => (await count(page, VID)) === 1, 8000, 'the deck save');
  await page.click('#acancel');
  assert(true, 'added to an exercise deck, the flag leaves');
  await page.click('li.lr:nth-child(1) .lr-card');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  await page.click('#atmd');
  await page.click('#asave');
  await until(async () => (await count(page, VID)) === 0, 8000, 'the markdown copy');
  assert((await page.evaluate(() => navigator.clipboard.readText())).includes(':::exercise'), 'copied as markdown, the flag leaves');
  await page.click('#acancel');
  for (const [i, j] of [[1, 0], [1, 1], [2, 0]]) await flagOf(page, seg(i, j));
  await sleep(300);
  await page.click('.lp-cards');
  await page.waitForFunction(() => !document.getElementById('anki').hidden && document.querySelector('#anki .lq-strip'));
  eq(await page.evaluate(() => [document.querySelector('.lq-n').textContent, afa.value]), ['item 1 of 3', 'The market'], 'one after another: «item 1 of 3»');
  await page.click('#atanki');
  await page.click('#asave');
  // "The market" went to Later::Video above: the deck has it, so the sheet asks first (10.7) and the queue waits
  await page.waitForFunction(() => /add it again/.test(document.getElementById('astat').textContent), null, {timeout: 8000});
  eq(await page.evaluate(() => [document.querySelector('.lq-n').textContent, afa.value]), ['item 1 of 3', 'The market'],
     'a card the deck has already: the sheet asks «add it again», and the queue stays on it');
  await page.click('#asave');
  await page.waitForFunction(() => document.querySelector('.lq-n') && document.querySelector('.lq-n').textContent === 'item 2 of 3' && afa.value === 'opens early.', null, {timeout: 8000});
  await page.click('.lq-skip');
  await page.waitForFunction(() => document.querySelector('.lq-n') && document.querySelector('.lq-n').textContent === 'item 3 of 3' && afa.value === 'Bring a bag', null, {timeout: 8000});
  await page.click('.lq-stop');
  await page.waitForFunction(() => document.getElementById('anki').hidden && !document.querySelector('.lq-strip'));
  eq((await flags(page, VID)).map(r => r.text), ['opens early.', 'Bring a bag'], 'saved, Skip, Stop: two flags left, the saved one gone');
  await ctx.close();
});
await scene('e2) the video on a phone: a tap, a held finger, the door, the sheet, the first line', async () => {
  const ctx = await ctxOf('phone');
  const page = await openVideo(ctx);
  assert(await page.evaluate(() => document.querySelector('.later-btn').hidden), 'with nothing flagged the door is not on the first line');
  await page.locator(seg(1, 0)).evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(300);
  await page.tap(seg(1, 0));
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  const b = await page.evaluate(() => { const e = document.querySelector('#cloud .mklater'); return {h: Math.round(e.getBoundingClientRect().height), text: e.textContent}; });
  assert(b.h >= 48 && b.text === 'review later', 'a tap opens the cloud, with «review later» a finger high: ' + JSON.stringify(b));
  await page.tap('#cloud .mklater');
  await until(async () => (await count(page, VID)) === 1, 5000, 'the cloud\'s button');
  await page.evaluate(() => document.dispatchEvent(new MouseEvent('click', {bubbles: true})));
  const door = await page.evaluate(() => { const e = document.querySelector('.later-btn'), r = e.getBoundingClientRect(); return {w: Math.round(r.width), h: Math.round(r.height), hidden: e.hidden, text: e.innerText.replace(/\s+/g, ' ')}; });
  assert(!door.hidden && door.w >= 48 && door.h >= 48 && door.text === '⚑ 1', 'the door is there, a finger high: ' + JSON.stringify(door));
  await hold(page, seg(2, 0));
  eq(await page.evaluate(() => [...document.querySelectorAll('.wt-menu button')].map(x => x.textContent)), ['Copy “Bring a bag”', 'Copy the caption', 'Review later: “Bring a bag”'], 'a held finger on a phrase: «Review later: “…”» beside the copies');
  await page.click('.wt-menu button:last-child');
  await until(async () => (await count(page, VID)) === 2, 5000, 'the held finger');
  await marksAre(page, n => n === 2);
  await shot(page, 'e4-phone');
  await press(page, '.later-btn');
  await page.waitForSelector('.lp-wrap.lp-sheet:not([hidden]) .lp-panel');
  await sleep(300);
  eq(await page.evaluate(() => [!!document.querySelector('.lr-card'), !!document.querySelector('.lp-cards:not([hidden])'), document.querySelectorAll('.lr-go').length]), [false, false, 2], 'the list is a sheet: ▶ and ✕, no + card, no «one after another»');
  await shot(page, 'e5-phone-sheet');
  await press(page, 'li.lr:nth-child(2) .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden);
  await until(async () => await page.evaluate(() => ParsehPlayer.time() >= 4), 8000, 'the video at the caption');
  assert(true, '▶ puts the sheet away and takes the video to the caption');
  await ctx.close();
  for (const w of [390, 360, 320]) {
    const c = await ctxOf({viewport: {width: w, height: 800}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID});
    const p = await openVideo(c);
    await flagOf(p, seg(1, 0));
    await sleep(300);
    const t = await p.evaluate(() => [...document.querySelectorAll('header a[href], header button')].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect(); return {n: e.id || (e.hasAttribute('data-parseh-gear') ? 'gear' : e.classList.contains('later-btn') ? 'later' : e.className.split(' ')[0]), top: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right)}; }));
    eq([t.some(x => x.n === 'later'), new Set(t.map(x => x.top)).size, t.every(x => x.w >= 47.5 && x.h >= 47.5), t.every(x => x.right <= w)], [true, 1, true, true], `${w}px: the first line holds «⚑ 1» with the rest, on one line, each 48px, on the screen: ${JSON.stringify(t.map(x => x.n))}`);
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${w}px: nothing sideways`);
    await shot(p, 'e6-header-' + w);
    await c.close();
  }
});

await scene('e3) the video on the whole screen: the subtitles are copies of a caption, and a held finger flags their phrase', async () => {
  const ctx = await ctxOf({viewport: {width: 844, height: 390}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID});
  const page = await openVideo(ctx);
  await page.waitForFunction(() => { const b = document.querySelector('.m-vfull'); return !!b && !b.hidden; }, null, {timeout: 8000});
  await press(page, '.m-vfull');
  await page.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'), null, {timeout: 8000});
  await page.evaluate(() => document.querySelectorAll('#segs .seg .lab')[2].click());
  await page.waitForFunction(() => { const s = document.querySelector('.m-subs .seg'); return !!s && !!s.querySelector('.w'); }, null, {timeout: 10000});
  // a caption of this film lasts two seconds and what follows takes longer on a busy machine: a copy of the next one
  // would have no dotted line under it, so the film stands still on the caption (a person holds a finger on a paused line)
  await page.evaluate(() => { ParsehPlayer.pause(); ParsehPlayer.seek(4.5); });
  await page.waitForFunction(() => /Bring a bag/.test((document.querySelector('.m-subs') || {}).textContent || ''), null, {timeout: 10000});
  await sleep(600);
  assert(await page.evaluate(() => document.querySelector('.later-btn').getClientRects().length === 0), 'the whole screen draws nothing new: the door is not on it');
  await hold(page, '.m-subs .w');
  const rows = await page.evaluate(() => [...document.querySelectorAll('.wt-menu button')].map(x => x.textContent));
  assert(rows.length === 3 && /^Review later: “/.test(rows[2]), 'a held finger on a subtitle: the same three lines, the last «Review later: “…”»: ' + JSON.stringify(rows));
  await page.click('.wt-menu button:last-child');
  await until(async () => (await count(page, VID)) === 1, 5000, 'the subtitle\'s phrase');
  const flagged = (await flags(page, VID))[0];
  eq([flagged.where.start, flagged.where.text], [4, 'Bring a bag today.'], 'the flag is the phrase of the caption the copy is of: ' + flagged.text);
  await marksAre(page, n => n >= 2);
  assert(await page.evaluate(() => document.querySelectorAll('.m-subs .w.later-mark').length >= 1 && document.querySelectorAll('#segs .w.later-mark').length >= 1), 'the dotted line is under the phrase in the subtitles and in the transcript');
  await shot(page, 'e7-whole-screen');
  await ctx.close();
});

/* ====== f) two devices, a reload, and a link ====== */
await scene('f) two devices, one computer; a link from /later/ opens the book and the video at the flag', async () => {
  const A = await ctxOf('desk'), Bc = await ctxOf('desk');
  const a = await openReader(A, EN, 'device A');
  const c0 = await centre(a, 'main .p1 .w[data-c="0"]');
  await a.mouse.move(c0.x, c0.y);
  await sleep(250);
  await a.keyboard.press('l');
  await until(async () => (await count(a, EN)) === 1, 5000);
  await a.evaluate(() => ParsehLater.sync());
  await sleep(300);
  const b = await openReader(Bc, EN, 'device B');
  await until(async () => (await count(b, EN)) === 1, 8000, 'the flag on the other device');
  await marksAre(b, n => n >= 2);
  eq(await doorText(b), '⚑ later 1', 'a flag made on one device shows on the other: its count and its line');
  // B takes it off, with its own L key
  const bc = await centre(b, 'main .p1 .w[data-c="0"]');
  await b.mouse.move(bc.x, bc.y);
  await sleep(250);
  await b.keyboard.press('l');
  await until(async () => (await count(b, EN)) === 0, 5000);
  await b.evaluate(() => ParsehLater.sync());
  await sleep(400);
  // A still holds it; its reload must not bring it back
  eq(await count(a, EN), 1, 'device A has not heard of the removal yet');
  await a.reload();
  await a.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel);
  await a.evaluate(() => ParsehLater.ready());
  await sleep(300);
  eq([await count(a, EN), (await marks(a)).length], [0, 0], 'a removal on one device is not undone by the other, which still held the flag');
  // a link from /later/
  const ids = [];
  const fa = await openReader(A, FA, 'link');
  await fa.evaluate(() => needChapters(2));
  ids.push(await flagOf(fa, 'section.chapter[data-ch="2"] .p1 .w[data-c="85"]'));
  const v = await openVideo(A, VID, 'video link');
  ids.push(await flagOf(v, seg(2, 0)));
  await fa.evaluate(() => ParsehLater.sync());
  await v.evaluate(() => ParsehLater.sync());
  // the links are opened on the OTHER device, which has never held these two flags: it learns of them from the computer
  const hubPage = await pageOf(Bc, 'later page');
  await hubPage.goto(B + '/later/');
  await hubPage.waitForSelector('li.lr .lr-go');
  await shot(hubPage, 'f1-later-page');
  const links = await hubPage.evaluate(() => [...document.querySelectorAll('li.lr a.lr-go')].map(x => x.getAttribute('href')));
  assert(links.length === 2 && links.every(h => h.includes('#later=')), 'the page lists both flags, each a link to <page>#later=<id>: ' + JSON.stringify(links.map(h => h.slice(0, 50))));
  const bookLink = links.find(h => h.startsWith(FA));
  await hubPage.goto(B + bookLink);
  await hubPage.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel);
  await hubPage.waitForFunction(() => { const w = document.querySelector('.lp-wrap'); return !!w && !w.hidden; }, null, {timeout: 12000});
  await hubPage.waitForFunction(() => document.querySelector('section.chapter[data-ch="2"]:not([data-part]) .later-mark'), null, {timeout: 12000});
  await sleep(500);
  const landed = await hubPage.evaluate(() => { const e = document.querySelector('section.chapter[data-ch="2"] .later-mark'); const r = e.getBoundingClientRect(); return {mid: Math.round(r.top + r.height / 2), vh: innerHeight, hash: location.hash.slice(0, 7), chapter: !document.querySelector('section.chapter[data-ch="2"][data-part]')}; });
  assert(landed.chapter && landed.hash === '#later=' && Math.abs(landed.mid - landed.vh / 2) < 160, 'a link from /later/ opens the book at the chunk, its chapter fetched, with the list open on it: ' + JSON.stringify(landed));
  await shot(hubPage, 'f2-opened-by-link');
  const vid = await pageOf(Bc, 'video by link');
  await vid.goto(B + `/youtube/v/${VID}/` + '#later=' + encodeURIComponent(ids[1]));
  await vid.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.later && ParsehPlayer.later.panel());
  await vid.waitForFunction(() => { const w = document.querySelector('.lp-wrap'); return !!w && !w.hidden; }, null, {timeout: 15000});
  await until(async () => await vid.evaluate(() => ParsehPlayer.time() >= 4), 12000, 'the video at the flag');
  assert(true, 'and the video: the list open on the flag, the video at its caption -- on a device that had never held either flag');
  await A.close(); await Bc.close();
});

/* ====== g) a reader built before a0.5.0 ====== */
await scene('g) a reader built before a0.5.0 gets it all with no rebuild', async () => {
  if (!MADE.old_fa) { console.log('  (no earlier build of the fixture reader on this checkout: skipped)'); return; }
  const html = await (await fetch(B + MADE.old_fa)).text();
  assert(!/later-btn|ParsehLater|later-reader/.test(html) && !/pg-reader|pagesettings/.test(html), 'the page is an old one: nothing of review later, nor of the gear, in its own markup');
  const ctx = await ctxOf('desk');
  const page = await pageOf(ctx, 'old reader');
  await page.goto(B + MADE.old_fa);
  await page.waitForFunction(() => window.ParsehLaterReader && ParsehLaterReader.panel, null, {timeout: 25000});
  await sleep(350);
  assert(await page.evaluate(() => !!document.querySelector('header .later-btn')), 'it has the door');
  const c1 = await centre(page, 'main .p1 .w[data-c="1"]');
  await page.mouse.move(c1.x, c1.y);
  await sleep(250);
  await page.keyboard.press('l');
  await until(async () => (await count(page)) === 1, 5000, 'L on the old reader');
  await marksAre(page, n => n >= 1);
  const old = (await flags(page))[0];
  eq([old.kind, old.ref, old.text.length > 0, old.where.para], ['book', MADE.old_fa, true, '1:1'], 'L flags a chunk of it: ' + JSON.stringify(old.where));
  await openList(page);
  eq((await rowsOf(page)).map(r => r.state), ['found'], 'the list holds it, found');
  await page.click('li.lr .lr-go');
  await page.waitForFunction(() => document.querySelector('.lp-wrap').hidden && document.querySelector('.later-flash'));
  assert(true, '▶ goes there');
  await ctx.close();
});

/* ====== h) the three themes; nothing sideways ====== */
await scene('h) the three themes, and nothing sideways from 320 to 1280', async () => {
  const ctx = await ctxOf('desk');
  const page = await openReader(ctx, EN);
  for (const n of [0, 1]) await flagOf(page, `main .p1 .w[data-c="${n}"]`);
  for (const theme of ['light', 'dark', 'sepia']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    await sleep(150);
    await page.click('#hovermode');
    await page.hover('main .p1 .w[data-c="2"]');
    await page.waitForFunction(() => !document.getElementById('cloud').hidden && document.querySelector('#cloud .mklater'));
    await sleep(200);
    await shot(page, 'h1-cloud-' + theme);
    let list = await page.evaluate(contrastOf, ['.later-btn', '#cloud .mklater']);
    await page.click('#hovermode');
    const r = await centre(page, 'main .row[data-c="3"] .fa');
    await page.mouse.move(r.x, r.y);
    await page.waitForFunction(() => !document.querySelector('.later-flag').hidden);
    await shot(page, 'h2-flag-' + theme, {clip: {x: 200, y: 330, width: 800, height: 200}});
    list = list.concat(await page.evaluate(contrastOf, ['.later-flag']));
    const bad = list.filter(x => x.ratio < 4.5);
    assert(list.length >= 3 && bad.length === 0, `${theme}: the new texts, the worst ${Math.min(...list.map(x => x.ratio))}:1 of ${list.length}${bad.length ? ' -- BELOW 4.5: ' + JSON.stringify(bad) : ''}`);
    await shot(page, 'h3-marks-' + theme);
  }
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  // the queue's strip, in the three themes
  await openList(page);
  await page.click('.lp-cards');
  await page.waitForFunction(() => !document.getElementById('anki').hidden && document.querySelector('.lq-strip'));
  for (const theme of ['light', 'dark', 'sepia']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    await sleep(150);
    const bad = (await page.evaluate(contrastOf, ['.lq-n', '.lq-b'])).filter(x => x.ratio < 4.5);
    assert(bad.length === 0, `${theme}: the queue's strip is 4.5:1 or better`);
    await shot(page, 'h4-queue-' + theme, {clip: {x: 320, y: 30, width: 640, height: 130}});
  }
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  await page.click('.lq-stop');
  await ctx.close();
  // nothing sideways, with a flag (so that the door is drawn), at every width
  for (const w of [320, 360, 390, 768, 1024, 1280, 1600]) {
    const touch = w < 600;
    const c = await ctxOf(touch ? {viewport: {width: w, height: 800}, deviceScaleFactor: 1, isMobile: true, hasTouch: true, userAgent: ANDROID} : {viewport: {width: w, height: 800}});
    const p = await openReader(c, EN, 'width ' + w);
    await flagOf(p, 'main .p1 .w[data-c="0"]');
    await sleep(300);
    const over = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    const v = await openVideo(c, VID, 'video width ' + w);
    await flagOf(v, seg(1, 0));
    await sleep(300);
    const overV = await v.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    assert(over <= 1 && overV <= 1, `${w}px: the book and the video draw nothing sideways with a flag and its door (${over}, ${overV})`);
    if (w >= 1280) {
      const door = (await doorText(v)).replace(/\s+/g, ' ');
      const rowHeight = await v.evaluate(() => Math.round(document.querySelector('header').getBoundingClientRect().height));
      eq([door, rowHeight < 60], [w >= 1480 ? '⚑ later 1' : '⚑ 1', true], `${w}px: the video's door reads «${door}», with a flag, and the header is one row (${rowHeight}px)`);
    }
    await c.close();
  }
});
} catch (e) { failure = e; }

/* ====== i) nothing went wrong ====== */
console.log('i) nothing went wrong');
if (browser) await browser.close();
try { hub.kill('SIGTERM'); } catch (_) {}
await sleep(300);
try {
  eq(errors, [], 'no page threw or logged an error but the ones the machine always logs');
  const said = log.join('');
  assert(!/Traceback|Exception/.test(said), 'the server did not print a traceback' + (/Traceback/.test(said) ? ': ' + said.slice(said.indexOf('Traceback'), said.indexOf('Traceback') + 400) : ''));
  eq((await run(PY, ['-c', OWN])).out, configBefore, 'the checkout\'s config/ is as it was');
} catch (e) { failures.push('i) ' + String(e.message || e).split('\n').slice(0, 3).join(' | ')); }
console.log('\n' + passed + ' checks passed');
if (failure) { console.log(failure.stack || failure); }
if (failures.length) { console.log('\nFAILED SCENES:\n  ' + failures.join('\n  ')); }
await Deno.remove(TMP, {recursive: true}).catch(() => {});
Deno.exit(failure || failures.length ? 1 : 0);
