// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/review_later_core.mjs
//      LATER_SHOTS=<dir> saves the screenshots (and prints where)
//
// REVIEW LATER, the core (a0.5.0): lib/later.js and lib/later.css, the door
// /__later, the hub's door and the page /later/ -- DRIVEN, in a browser, on the
// REAL hub (serve.main on a temporary toolbox, tests/cardkit_harness.py).  The
// sidebar is driven on a stand-in for a reader (tests/fixtures/later_panel.html:
// a fixed header, a fake adapter) over the real script and sheet, served from
// the hub's own origin; the page and the hub's door are the real ones.
//
//  a) THE SIDEBAR at 1280x800 with a mouse: the button «⚑ later N», the panel
//     under the header with the header's own controls still live, the flags in
//     reading order, the chunk with its lang and dir, the gloss on one line and
//     its parts on a tap, the place and the age; Esc closes and stands down for
//     a sheet that used it first; ✕ remove and Undo (and the line going after
//     six seconds); this book only / everything; Test myself (the meanings
//     hidden, I know it, again); Copy the list as markdown and as a table,
//     through the clipboard and through the textarea fallback; the empty state;
//     an adrift flag; ▶ go to; + card (and a card not saved); one after another;
//     no + card where canCard is false; a Persian chunk right to left; four
//     hundred flags without a long frame.
//  b) THE PHONE at 390x844 on a touch screen: the same list as a sheet from the
//     foot, rows and buttons a finger's height, no + card, closed by ✕, Esc, the
//     backdrop and the back gesture -- which spends its history entry -- and
//     nothing sideways at 320.
//  c) THE THREE THEMES: the text of the list, the buttons, the test mode and the
//     line that says «removed · Undo» are 4.5:1 or better in light, dark, sepia.
//  d) THE PAGE /later/ and THE HUB'S DOOR, on the real hub: the door's count in
//     both layouts and under a language chip, the groups by book and video with
//     their counts, each flag's link (<reader>#later=<id>, <player>#later=<id>),
//     Test myself and Copy the list, the empty state, the phone layout.
//  e) TWO DEVICES, one server: a flag made in one browser shows in the other; one
//     chunk flagged on both is one flag; a removal in one is not undone by the
//     other, which still held the flag -- not even by a flag it made while it was
//     away, before the removal.
//  f) THE PHONE WITH THE COMPUTER AWAY: the door's requests aborted; flags made
//     there survive a reload and arrive when the computer is back; a change the
//     computer refuses in words is dropped and does not stop the rest.
//  g) NOTHING WENT WRONG: no page threw or logged an error but the ones provoked,
//     no server traceback, the checkout's config/ as it was.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('LATER_SHOTS') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-later-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
// what was got and what was wanted are said only where they differ
const eq = (a, b, m) => {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(`FAIL: ${m}\n     got  ${JSON.stringify(a)}\n     want ${JSON.stringify(b)}`);
  passed++;
  console.log('  ok', m);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const FIXTURE = await Deno.readTextFile(root + '/tests/fixtures/later_panel.html');

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
async function hub() {
  const port = freePort(), log = [];
  const proc = new Deno.Command(PY, {args: ['tests/cardkit_harness.py', 'serve', TMP, String(port)],
                                     cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  drain(proc.stdout, log); drain(proc.stderr, log);
  const base = `http://127.0.0.1:${port}`;
  const until = Date.now() + 60000;
  for (;;) {
    try { const r = await fetch(base + '/__activity'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() > until) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
  return {proc, base, log};
}
// what config/ holds, as one number, to say it was not touched
const OWN = 'import sys,hashlib;sys.path.insert(0,"tests");import configguard;s=configguard.snapshot();print(hashlib.sha1(repr(sorted(s.items())).encode()).hexdigest())';

const BOOK = '/books/english/mini-en/reader/', FA = '/books/persian/mini-fa/reader/', VIDEO = 'street-market-a1b2c3';
const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36';
// the flags the scenes use, as a page hands them to ParsehLater.record(); reading order is 1.1, 1.2, 2.1
const SECOND = {kind: 'book', ref: BOOK, lang: 'en', glossLang: 'fa', title: 'Mini', sub: '1.2-aaaaaaaaaaaa', k: 1, para: '1:2',
                label: '1.2', chapter: 'Chapter 1', text: 'the second chunk', en: 'second', sentence: 'The second chunk of the sentence.'};
const FIRST = {kind: 'book', ref: BOOK, lang: 'en', glossLang: 'fa', title: 'Mini', sub: '1.1-bbbbbbbbbbbb', k: 0, para: '1:1',
               label: '1.1', chapter: 'Chapter 1', text: 'wound the clock', en: 'bound the watch', tr: 'wownd'};
const THIRD = {kind: 'book', ref: BOOK, lang: 'en', glossLang: 'fa', title: 'Mini', sub: '2.1-cccccccccccc', k: 0, para: '2:1',
               label: '2.1', chapter: 'Chapter 2', text: 'opens early', en: 'starts soon', voc: 'open — start\nearly — soon'};
const PERSIAN = {kind: 'book', ref: FA, lang: 'fa', glossLang: 'en', title: 'Persian one', sub: '1.1-dddddddddddd', k: 0, para: '1:1',
                 label: '1.1', chapter: 'فصل ۱', text: 'کتاب‌ها را خواندم', tr: 'ketâb-hâ râ khândam', en: 'I read the books',
                 sentence: 'من کتاب‌ها را خواندم.'};
const CLIP = {kind: 'video', ref: VIDEO, lang: 'en', glossLang: 'fa', title: 'Street market', start: 2, j: 1, cap: 'The market opens early.',
              text: 'opens early', en: 'starts soon'};

// what the pages log that was PROVOKED here: a refusal in words (400), a door
// that was cut off on purpose
const errors = [];
function watch(page, label) {
  page.on('pageerror', e => errors.push(`${label}: pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`${label}: console: ${m.text()}`); });
}
async function shot(page, name, opts) {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`, ...(opts || {})});
  console.log('  shot', `${SHOTS}/${name}.png`);
}
// the flags as a page flags them: the id back
const flag = (page, p) => page.evaluate(p => ParsehLater.add(ParsehLater.record(p)).then(r => r.id), p);
const ids = page => page.evaluate(() => ParsehLater.list().map(r => r.id).sort());
const texts = page => page.$$eval('.lp-body li.lr .lr-text', ls => ls.map(l => l.textContent));
const nrows = page => page.evaluate(() => document.querySelectorAll('.lp-body li.lr').length);
const rowsAre = (page, n) => page.waitForFunction(n => document.querySelectorAll('.lp-body li.lr').length === n, n);
const btnText = page => page.locator('.later-btn').innerText();
const shut = page => page.waitForFunction(() => !document.querySelector('.lp-wrap:not([hidden])'));
async function openPanel(page, tap) {
  if (await page.locator('.lp-wrap:not([hidden])').count()) return;
  await (tap ? page.tap('.later-btn') : page.click('.later-btn'));
  await page.waitForSelector('.lp-wrap:not([hidden]) .lp-panel');
  await sleep(150);                      // the page is asked where each chunk is, a few at a time
}
async function fixture(ctx, base, query = '') {
  const page = await ctx.newPage();
  watch(page, 'fixture' + query);
  await page.goto(base + '/later-fixture/' + query);
  await page.waitForFunction(() => window.ParsehLater && window.__panel);
  return page;
}
async function newContext(browser, kind) {
  const opts = kind === 'phone'
    ? {viewport: {width: 390, height: 844}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID}
    : {viewport: {width: 1280, height: 800}};
  const ctx = await browser.newContext({...opts, permissions: ['clipboard-read', 'clipboard-write']});
  // the stand-in reader, served from the hub's own origin
  await ctx.route(/\/later-fixture\//, route => route.fulfill({status: 200, contentType: 'text/html', body: FIXTURE}));
  return ctx;
}
async function api(base, path, body) {
  const r = await fetch(base + path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  return {status: r.status, json: await r.json().catch(() => null)};
}
const askDoor = async (base, q) => (await api(base, '/__later?' + q)).json;
// every flag the computer holds, removed: each scene begins with an empty list, as a person's first day does
async function wipe() {
  const items = (await askDoor(base, 'all=1')).items;
  if (items.length) await api(base, '/__later', {by: 'test', ops: items.map(r => ({op: 'remove', id: r.id, at: Date.now() / 1000}))});
  await sleep(30);
}
// waits for something the server does (a page's own waitForFunction must not be given an async function: it passes at once)
async function until(f, ms = 10000) {
  const t = Date.now();
  for (;;) {
    const v = await f();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('FAIL: timed out waiting for ' + f);
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
const LISTED = ['.later-btn', '.lp-title', '.lp-status', '.lp-b', '.lp-sc', '.lr-text', '.lr-gl', '.lr-meta', '.lp-gt', '.lp-gm', '.lr-b:not(:disabled)',
                '.lr-know', '.lp-empty-h', '.lp-empty-how', '.lr-why', '.lr-fold', '.lr-tap', '.ls-text', '.ls-undo', '.lr-g'];
const PAGE_LISTED = ['.lp-gt', '.lp-gm', '.lr-text', '.lr-gl', '.lr-meta', '.lp-status', '.lp-b', '.lr-b:not(:disabled)', 'p.sub', 'h1.idx', '.parseh-bar .where', '.ls-text'];

// ONE SCENE AFTER ANOTHER, each against an empty list on the computer; a scene that fails is
// told and the next goes on, so that one run says everything that is wrong
const failures = [];
const ONLY = (Deno.env.get('LATER_ONLY') || '').split(',').filter(Boolean);
async function scene(name, fn) {
  if (ONLY.length && !ONLY.some(o => name.startsWith(o + ')'))) return;
  console.log(name);
  try { await wipe(); await fn(); }
  catch (e) { const said = String(e && e.message || e).split('\n').slice(0, 3).join(' | '); failures.push(name + ' -- ' + said); console.log('  !! ' + said); }
}

const bin = Deno.env.get('CHROME_BIN');
const configBefore = (await run(PY, ['-c', OWN])).out;
const built = await run(PY, ['tests/cardkit_harness.py', 'build', TMP]);
if (built.code) throw Error('the toolbox could not be built:\n' + built.err);
const H = await hub();
const base = H.base;
let browser, failure;
try {
browser = await chromium.launch({executablePath: bin, headless: true});

/* ================= a) the sidebar, 1280 x 800, a mouse ================= */
await scene('a) the sidebar on a wide screen', async () => {
  const ctx = await newContext(browser);
  const page = await fixture(ctx, base);
  eq(await page.evaluate(() => ParsehLater.ready().then(r => r.synced)), true, 'ready() says the first look at the computer\'s list is done');
  eq(await btnText(page), '⚑ later', 'the button says «⚑ later», and no count while nothing is flagged');
  await flag(page, SECOND); await flag(page, FIRST); await flag(page, THIRD);
  eq(await btnText(page), '⚑ later 3', 'the button says «⚑ later 3» once three are flagged');
  eq(await page.locator('.later-btn').getAttribute('aria-expanded'), 'false', 'the button says the list is shut');
  eq(await page.locator('.later-btn').getAttribute('aria-haspopup'), 'dialog', 'and that it opens a dialog');
  assert(/3 chunks/.test(await page.locator('.later-btn').getAttribute('aria-label')), 'its name for a screen reader says how many');

  await openPanel(page);
  eq(await page.locator('.lp-panel').getAttribute('role'), 'dialog', 'the panel is a dialog');
  eq(await page.locator('.later-btn').getAttribute('aria-expanded'), 'true', 'the button says it is open');
  const g = await page.evaluate(() => {
    const p = document.querySelector('.lp-panel').getBoundingClientRect(), b = document.querySelector('.lp-back').getBoundingClientRect(), h = document.getElementById('hd').getBoundingClientRect();
    return {pl: p.left, pr: p.right, pt: p.top, pb: p.bottom, bt: b.top, hb: h.bottom, W: innerWidth, H: innerHeight, z: getComputedStyle(document.querySelector('.lp-wrap')).zIndex,
            sheet: document.querySelector('.lp-wrap').classList.contains('lp-sheet')};
  });
  assert(!g.sheet, 'a wide screen gets the side panel, not the sheet');
  assert(Math.abs(g.pr - g.W) < 1 && g.pr - g.pl <= 420.5 && g.pr - g.pl > 400, `it is at the right edge, 420 wide at most (${g.pr - g.pl})`);
  assert(Math.abs(g.pt - g.hb) < 1.5 && Math.abs(g.bt - g.hb) < 1.5, `it hangs from the foot of the header, as does its backdrop (${g.pt}, ${g.bt} vs ${g.hb})`);
  assert(Math.abs(g.pb - g.H) < 1, 'and goes down to the foot of the window');
  eq(g.z, '60', 'at the contents panel\'s z-index');
  await page.click('#hb');
  eq(await page.locator('#hb').innerText(), 'pass 2', 'the header\'s own button still works with the panel open');
  eq(await texts(page), ['wound the clock', 'the second chunk', 'opens early'], 'the flags are in reading order, not the order they were made in');
  eq(await page.locator('.lp-title').innerText(), 'Review later', 'the head says what it is');
  eq(await page.locator('.lp-count').textContent(), '3', 'and, beside the title, how many are listed');
  eq(await page.locator('.lp-status').innerText(), '3 chunks', 'and again in words under the tools');
  const row = await page.evaluate(() => {
    const li = document.querySelector('.lp-body li.lr'), t = li.querySelector('.lr-text');
    return {lang: t.getAttribute('lang'), dir: t.getAttribute('dir'), cdir: getComputedStyle(t).direction, place: li.querySelector('.lr-place').textContent,
            age: li.querySelector('.lr-age').textContent, gloss: li.querySelector('.lr-gl').textContent, btns: [...li.querySelectorAll('.lr-acts .lr-b')].map(b => b.className.replace('lr-b ', ''))};
  });
  eq([row.lang, row.dir, row.cdir], ['en', 'ltr', 'ltr'], 'the chunk carries its language and direction');
  eq(row.place, '1.1 · Chapter 1', 'the place is «1.1 · Chapter 1»');
  eq(row.age, 'a moment ago', 'the age is in the words the reading place uses');
  eq(row.gloss, 'wownd · bound the watch', 'the gloss is one compact line: transliteration · meaning');
  eq(row.btns, ['lr-go', 'lr-card', 'lr-x'], 'each row offers ▶, + card and ✕');
  await page.click('.lp-body li.lr:nth-child(2) .lr-gl');
  const more = await page.evaluate(() => { const li = document.querySelectorAll('.lp-body li.lr')[1]; return {open: li.classList.contains('lr-open'), vis: li.querySelector('.lr-more').getClientRects().length > 0, text: li.querySelector('.lr-more').textContent}; });
  assert(more.open && more.vis && /The second chunk of the sentence/.test(more.text) && /second/.test(more.text), 'a tap on the gloss opens its parts, the sentence among them');
  await shot(page, 'a1-sidebar-light');
  await page.click('.lp-body li.lr:nth-child(2) .lr-fold');
  assert(!(await page.evaluate(() => document.querySelectorAll('.lp-body li.lr')[1].classList.contains('lr-open'))), 'and «less» folds them again');

  // Esc closes, and stands down for a sheet that used the key first
  await page.evaluate(() => { window.__sheetOpen = true; });
  await page.keyboard.press('Escape');
  assert(await page.locator('.lp-wrap:not([hidden])').count() === 1, 'Escape does not close the list while another layer has used it (defaultPrevented)');
  await page.evaluate(() => { window.__sheetOpen = false; });
  await page.keyboard.press('Escape');
  await shut(page);
  assert(await page.evaluate(() => document.activeElement === document.querySelector('.later-btn')), 'Escape closes it when nothing else wanted it, and the keyboard is back on the button');
  eq(await page.evaluate(() => window.__toggles), [true, false], 'the page is told when it opens and when it shuts (onToggle)');
  await openPanel(page);
  await page.mouse.click(100, 300);
  await shut(page);
  assert(true, 'a click on the dimmed page closes it');
  await openPanel(page);
  await page.click('.lp-x');
  await shut(page);
  assert(true, '✕ closes it');

  // remove, and Undo
  await openPanel(page);
  await page.click('.lp-body li.lr:nth-child(1) .lr-x');
  await rowsAre(page, 2);
  eq(await texts(page), ['the second chunk', 'opens early'], '✕ takes the flag off the list');
  eq(await btnText(page), '⚑ later 2', 'and off the count on the button');
  const snack = await page.evaluate(() => { const s = document.getElementById('later-snack'); return {show: s.classList.contains('ls-show'), text: s.textContent}; });
  assert(snack.show && snack.text === 'removed · Undo', `«removed · Undo» is said (${snack.text})`);
  await shot(page, 'a2-removed-undo');
  await page.click('.ls-undo');
  await rowsAre(page, 3);
  eq(await texts(page), ['wound the clock', 'the second chunk', 'opens early'], 'Undo puts it back where it was in the order');
  eq(await btnText(page), '⚑ later 3', 'and in the count');
  assert(!(await page.evaluate(() => document.getElementById('later-snack').classList.contains('ls-show'))), 'and the line goes');
  await page.click('.lp-body li.lr:nth-child(3) .lr-x');
  await page.waitForFunction(() => document.getElementById('later-snack').classList.contains('ls-show'));
  const t0 = Date.now();
  await page.waitForFunction(() => !document.getElementById('later-snack').classList.contains('ls-show'), null, {timeout: 9000});
  const took = Date.now() - t0;
  assert(took > 5000 && took < 7500, `«removed · Undo» stays six seconds (${took} ms)`);
  eq(await page.evaluate(() => ParsehLater.undo().then(r => !!r)), true, 'ParsehLater.undo() takes the last removal back, whenever it is called');
  await rowsAre(page, 3);

  // this book only / everything
  await flag(page, PERSIAN);
  eq(await btnText(page), '⚑ later 3', 'a flag in another book is not in this one\'s count');
  eq(await texts(page), ['wound the clock', 'the second chunk', 'opens early'], 'nor in this book\'s list');
  assert((await page.locator('.lp-sc').first().innerText()) === 'this book only', 'the switch says «this book only»');
  await page.click('.lp-sc:nth-child(2)');
  await rowsAre(page, 4);
  eq(await page.$$eval('.lp-gh', hs => hs.map(h => h.textContent)), ['MiniEnglish · 3 chunks', 'Persian onePersian · 1 chunk'], 'everything is under a heading for each book: this one first');
  const other = await page.evaluate(() => { const li = [...document.querySelectorAll('.lp-body li.lr')].find(l => /کتاب/.test(l.textContent)); const go = li.querySelector('.lr-go'), t = li.querySelector('.lr-text');
    return {tag: go.tagName, href: go.getAttribute('href'), card: !!li.querySelector('.lr-card'), id: li.getAttribute('data-id'), dir: t.getAttribute('dir'), lang: t.getAttribute('lang'), cdir: getComputedStyle(t).direction}; });
  eq([other.tag, other.card], ['A', false], 'a flag in another book opens that book (a link), and has no + card here');
  eq(other.href, FA + '#later=' + encodeURIComponent(other.id), 'at its chunk: <reader>#later=<the id, encoded>');
  eq(await page.evaluate(h => ParsehLater.fromHash(new URL(h, location.href).hash), other.href), other.id, 'and ParsehLater.fromHash reads the id back');
  eq([other.lang, other.dir, other.cdir], ['fa', 'rtl', 'rtl'], 'a Persian chunk is set right to left, in its own language');
  eq(await page.evaluate(() => localStorage.getItem('parseh_later_scope')), 'all', 'the switch is remembered');
  await shot(page, 'a3-everything');
  await page.click('.lp-sc:nth-child(1)');
  await rowsAre(page, 3);
  eq(await page.evaluate(() => document.querySelectorAll('.lp-gh').length), 0, 'this book only draws no headings');
  await page.click('.lp-x');

  // Test myself
  await openPanel(page);
  await page.click('.lp-test');
  const test = await page.evaluate(() => ({pressed: document.querySelector('.lp-test').getAttribute('aria-pressed'), label: document.querySelector('.lp-test').textContent,
    glosses: document.querySelectorAll('.lp-body .lr-gloss').length, taps: document.querySelectorAll('.lp-body .lr-tap').length, know: document.querySelectorAll('.lp-body .lr-know').length,
    status: document.querySelector('.lp-status').textContent}));
  eq([test.pressed, test.label, test.glosses, test.taps, test.know], ['true', 'Stop testing', 0, 3, 0], 'Test myself hides every meaning, and says to tap');
  assert(/3 chunks to go/.test(test.status), 'and how many are left');
  await shot(page, 'a4-test-hidden');
  await page.click('.lp-body li.lr:nth-child(1) .lr-hit');
  const shown = await page.evaluate(() => { const li = document.querySelector('.lp-body li.lr'); return {gloss: li.querySelector('.lr-gloss')?.textContent, know: !!li.querySelector('.lr-know'), again: !!li.querySelector('.lr-again'), others: document.querySelectorAll('.lp-body .lr-gloss').length}; });
  assert(/bound the watch/.test(shown.gloss) && shown.know && shown.again && shown.others === 1, 'a tap on a chunk shows its own meaning and the two buttons «I know it» and «again»');
  await shot(page, 'a5-test-shown');
  await page.click('.lp-body li.lr:nth-child(1) .lr-again');
  eq(await page.evaluate(() => [document.querySelectorAll('.lp-body .lr-gloss').length, document.querySelectorAll('.lp-body li.lr').length]), [0, 3], '«again» keeps the flag and hides the meaning again');
  await page.click('.lp-body li.lr:nth-child(1) .lr-hit');
  await page.click('.lp-body li.lr:nth-child(1) .lr-know');
  await rowsAre(page, 2);
  eq(await btnText(page), '⚑ later 2', '«I know it» takes the flag off the list');
  eq(await page.evaluate(() => document.getElementById('later-snack').textContent), 'known · removed from the list · Undo', 'with an Undo');
  await page.click('.ls-undo');
  await rowsAre(page, 3);
  await page.click('.lp-test');
  eq(await page.evaluate(() => document.querySelectorAll('.lp-body .lr-gloss').length), 3, '«Stop testing» brings every meaning back');

  // Copy the list
  await page.click('.lp-copy');
  assert(await page.locator('.lp-chooser').isVisible(), '«Copy the list» offers the two forms');
  await page.click('.lp-fmt:nth-child(1)');
  eq(await page.evaluate(() => navigator.clipboard.readText()),
     '## Mini (English)\n\n- **wound the clock** — wownd · bound the watch (1.1 · Chapter 1)\n- **the second chunk** — second (1.2 · Chapter 1)\n' +
     '- **opens early** — starts soon · open — start; early — soon (2.1 · Chapter 2)\n', 'the markdown list, under a heading, in reading order, with each place');
  assert(/copied 3 chunks as a list/.test(await page.locator('.lp-status').innerText()), 'and it says what it copied');
  await page.click('.lp-copy');
  await page.click('.lp-fmt:nth-child(2)');
  const table = (await page.evaluate(() => navigator.clipboard.readText())).split('\n');
  const r1 = table[1].split('\t');
  eq(table[0].split('\t'), ['chunk', 'reading', 'transliteration', 'meaning', 'vocabulary', 'sentence', 'place', 'title', 'language', 'flagged'], 'the table has its header');
  eq([r1[0], r1[2], r1[3], r1[6], r1[7], r1[8]], ['wound the clock', 'wownd', 'bound the watch', '1.1 · Chapter 1', 'Mini', 'English'], 'and a row a flag, tab-separated');
  assert(table.slice(1, 4).every(l => l.split('\t').length === 10) && /^\d{4}-\d\d-\d\d$/.test(r1[9]) && table[4] === '', 'every row has the ten columns and a date, and the table ends in a newline');
  eq(table[3].split('\t')[4], 'open — start early — soon', 'a vocabulary of two lines is one cell');
  await page.click('.lp-x');

  // the empty state
  await openPanel(page);
  for (let i = 0; i < 3; i++) { await page.click('.lp-body li.lr:nth-child(1) .lr-x'); await rowsAre(page, 2 - i); }
  const empty = await page.evaluate(() => ({text: document.querySelector('.lp-empty').textContent, test: document.querySelector('.lp-test').hidden, copy: document.querySelector('.lp-copy').hidden}));
  assert(empty.text.includes('Point at a chunk and press L, or use «review later» in its cloud — on a phone, hold your finger on a word.'), 'the empty state says how to flag one');
  assert(empty.test && empty.copy, 'and offers neither Test myself nor Copy the list');
  assert(/1 chunk flagged elsewhere/.test(empty.text), 'it says that there is one in another book, and offers it');
  eq(await btnText(page), '⚑ later', 'the count is gone from the button');
  await shot(page, 'a6-empty');
  for (let i = 0; i < 3; i++) await page.evaluate(() => ParsehLater.undo());
  await rowsAre(page, 3);
  await page.click('.lp-x');
  await ctx.close();
});

/* ====== a2) adrift, go to, cards, one after another, the clipboard's other way ====== */
await scene('a2) an adrift flag, go to, + card, one after another', async () => {
  const ctx = await newContext(browser);
  const page = await fixture(ctx, base);
  const a = await flag(page, FIRST), b = await flag(page, SECOND), c = await flag(page, THIRD);
  await page.evaluate(id => { window.__adrift[id] = true; }, b);
  await openPanel(page);
  await page.waitForSelector(`li.lr[data-id="${b}"][data-state="adrift"]`);
  const lost = await page.evaluate(id => { const li = document.querySelector(`li.lr[data-id="${CSS.escape(id)}"]`); return {why: li.querySelector('.lr-why').textContent, go: li.querySelector('.lr-go').disabled, card: li.querySelector('.lr-card').disabled,
    x: li.querySelector('.lr-x').disabled, text: li.querySelector('.lr-text').textContent, gloss: li.querySelector('.lr-gl').textContent, vis: li.querySelector('.lr-why').getClientRects().length > 0}; }, b);
  eq([lost.why, lost.go, lost.card, lost.x, lost.vis], ['this chunk is no longer where it was', true, true, false, true], 'an adrift flag says why ▶ and + card are shut, and can still be removed');
  eq([lost.text, lost.gloss], ['the second chunk', 'second'], 'it is listed with the text and the gloss it was saved with');
  await shot(page, 'a7-adrift');
  await page.click('.lp-copy'); await page.click('.lp-fmt:nth-child(1)');
  assert((await page.evaluate(() => navigator.clipboard.readText())).includes('the second chunk'), 'and it is still copied');
  await page.click(`li.lr[data-id="${a}"] .lr-go`);
  await page.waitForFunction(() => window.__log.some(x => x.startsWith('goTo:')));
  eq(await page.evaluate(() => window.__log.filter(x => x.startsWith('goTo:'))), ['goTo:' + a], '▶ asks the page to go to that chunk');
  await shut(page);
  assert(true, 'and the list closes, so that the chunk can be seen');
  await openPanel(page);
  assert(await page.locator('.lp-cards').isVisible(), '«Make cards one after another» is there beside + card');
  await page.click('.lp-cards');
  await page.waitForFunction(() => window.__log.some(x => x.startsWith('queue:')));
  eq(await page.evaluate(() => window.__log.find(x => x.startsWith('queue:'))), `queue:${a},${c}`, 'it hands the page the flags in reading order, the adrift one left out');
  await page.evaluate(() => { window.__saveCard = false; });
  await page.click(`li.lr[data-id="${a}"] .lr-card`);
  await page.waitForFunction(() => window.__log.some(x => x.startsWith('card:')));
  await sleep(150);
  assert(await page.locator(`li.lr[data-id="${a}"]`).count() === 1 && !(await page.locator(`li.lr[data-id="${a}"] .lr-card`).isDisabled()), 'a card that was not saved leaves the flag, and the button free');
  await page.evaluate(() => { window.__saveCard = true; });
  await page.click(`li.lr[data-id="${a}"] .lr-card`);
  await page.waitForFunction(id => !document.querySelector(`li.lr[data-id="${CSS.escape(id)}"]`), a);
  assert(!(await ids(page)).includes(a), 'the flag leaves when the card is saved: off the list and out of the store');
  eq(await page.evaluate(() => document.getElementById('later-snack').textContent), 'card saved · removed from the list · Undo', 'with an Undo');
  await page.click('.ls-undo');
  await page.waitForFunction(id => document.querySelector(`li.lr[data-id="${CSS.escape(id)}"]`), a);
  // opened ON one flag, as a link from /later/ asks: lit, in view, the keyboard on its ▶
  await page.click('.lp-x');
  await shut(page);
  await page.evaluate(id => window.__panel.open({id}), c);
  await page.waitForSelector(`li.lr[data-id="${c}"].lr-flash`);
  const lit = await page.evaluate(id => { const li = document.querySelector(`li.lr[data-id="${CSS.escape(id)}"]`), r = li.getBoundingClientRect(), b = document.querySelector('.lp-body').getBoundingClientRect();
    return {inView: r.top >= b.top - 1 && r.bottom <= b.bottom + 1, focus: document.activeElement === li.querySelector('.lr-go')}; }, c);
  assert(lit.inView && lit.focus, 'open({id}) opens the list on that flag: lit, in view, the keyboard on its ▶');
  await page.waitForFunction(id => !document.querySelector(`li.lr[data-id="${CSS.escape(id)}"].lr-flash`), c, {timeout: 4000});
  assert(true, 'and the light goes out by itself');
  await page.evaluate(() => { window.__cardOK = false; });
  await page.click('.lp-x'); await openPanel(page);
  eq(await page.evaluate(() => [document.querySelectorAll('.lr-card').length, document.querySelectorAll('.lp-cards:not([hidden])').length]), [0, 0], 'where canCard() says no there is no + card and no «one after another»');
  await page.click('.lp-x');
  // what the cloud's button and the L key call: flag if not, take off if it is
  const FOURTH = {...THIRD, sub: '3.1-eeeeeeeeeeee', k: 2, para: '3:1', label: '3.1', text: 'a fourth chunk'};
  const t1 = await page.evaluate(p => ParsehLater.toggle(ParsehLater.record(p)), FOURTH);
  const id4 = await page.evaluate(p => ParsehLater.record(p).id, FOURTH);
  eq([t1, await page.evaluate(id => ParsehLater.has(id), id4)], [true, true], 'toggle() flags a chunk that is not flagged');
  const t2 = await page.evaluate(p => ParsehLater.toggle(ParsehLater.record(p)), FOURTH);
  eq([t2, await page.evaluate(id => ParsehLater.has(id), id4), await page.evaluate(() => document.getElementById('later-snack').textContent)], [false, false, 'removed · Undo'], 'and takes it off when it is, with the Undo');
  eq(await page.evaluate(p => ParsehLater.toggle(ParsehLater.record(p)), FOURTH), true, 'and flags it again after');
  eq(await page.evaluate(() => ['/books/english/mini-en/reader/index.html', '/books/mini-en/reader/', '/youtube/v/street-market-a1b2c3/', '/youtube/v/abc/index.html', '/books/', '/'].map(p => ParsehLater.refOf(p))),
     [BOOK, '/books/mini-en/reader/', VIDEO, 'abc', null, null], 'refOf() says what a page\'s flags are kept under: the reader\'s path without index.html, the video\'s id, nothing for any other page');
  await ctx.close();

  // the clipboard where the browser has none: a textarea and execCommand (on a computer that holds none of the above)
  await wipe();
  const bare = await browser.newContext({viewport: {width: 1280, height: 800}});
  await bare.route(/\/later-fixture\//, route => route.fulfill({status: 200, contentType: 'text/html', body: FIXTURE}));
  await bare.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true});
    window.__copied = null;
    document.execCommand = c => { const ta = document.querySelector('textarea'); if (c === 'copy' && ta) window.__copied = ta.value.slice(ta.selectionStart, ta.selectionEnd); return true; };
  });
  const bp = await fixture(bare, base, '?bare=1');
  assert(await bp.evaluate(() => typeof window.Parseh === 'undefined'), 'a page with no parseh.js at all');
  await flag(bp, FIRST); await flag(bp, THIRD);
  await openPanel(bp);
  await bp.click('.lp-copy'); await bp.click('.lp-fmt:nth-child(1)');
  await bp.waitForFunction(() => window.__copied !== null);
  eq(await bp.evaluate(() => window.__copied), '## Mini (English)\n\n- **wound the clock** — wownd · bound the watch (1.1 · Chapter 1)\n- **opens early** — starts soon · open — start; early — soon (2.1 · Chapter 2)\n',
     'with no clipboard API the list is copied through a textarea');
  assert(/copied 2 chunks/.test(await bp.locator('.lp-status').innerText()), 'and says so');
  await bare.close();
});

/* ================= a3) a Persian book, right to left ================= */
await scene('a3) a right-to-left chunk', async () => {
  const ctx = await newContext(browser);
  const page = await fixture(ctx, base, '?ref=fa');
  await flag(page, PERSIAN);
  await openPanel(page);
  const fa = await page.evaluate(() => {
    const t = document.querySelector('.lp-body .lr-text'), li = t.closest('.lr'), r = document.createRange();
    r.selectNodeContents(t);
    const box = r.getBoundingClientRect(), body = li.querySelector('.lr-body').getBoundingClientRect();
    return {dir: t.getAttribute('dir'), cdir: getComputedStyle(t).direction, lang: t.lang, font: getComputedStyle(t).fontFamily, chunkRight: Math.round(body.right - box.right), chunkLeft: Math.round(box.left - body.left),
            place: li.querySelector('.lr-place').textContent, chrome: document.querySelector('.lp-panel').getAttribute('dir')};
  });
  eq([fa.dir, fa.cdir, fa.lang], ['rtl', 'rtl', 'fa'], 'a Persian chunk is dir=rtl, lang=fa');
  assert(fa.chunkRight < fa.chunkLeft, `it reads from the right edge of its row (${fa.chunkRight} from the right, ${fa.chunkLeft} from the left)`);
  assert(/Vazirmatn|Naskh|Nastaliq/i.test(fa.font), `in the language's own face (${fa.font.slice(0, 60)})`);
  eq(fa.chrome, 'ltr', 'the panel\'s own words stay left to right');
  eq(fa.place, '1.1 · فصل ۱', 'the place carries the chapter\'s name as it is written');
  await shot(page, 'a8-persian');
  await ctx.close();
});

/* ========== a4) four hundred flags: the list opens without a long frame ========== */
await scene('a4) a long list', async () => {
  const ctx = await newContext(browser);
  const page = await fixture(ctx, base);
  await page.evaluate(() => {
    for (let i = 0; i < 400; i++)
      ParsehLater.add(ParsehLater.record({kind: 'book', ref: '/books/english/mini-en/reader/', lang: 'en', glossLang: 'fa', title: 'Mini', sub: `${1 + (i >> 5)}.${i & 31}-${String(i).padStart(12, '0')}`,
        k: i % 3, para: `${1 + (i >> 5)}:${1 + (i & 31)}`, label: `${1 + (i >> 5)}.${i & 31}`, chapter: 'Chapter ' + (1 + (i >> 5)), text: `chunk number ${i}`, en: `meaning ${i}`}));
  });
  await page.waitForFunction(() => ParsehLater.count({ref: '/books/english/mini-en/reader/'}) === 400);
  eq(await btnText(page), '⚑ later 400', 'four hundred are flagged');
  const gaps = await page.evaluate(() => new Promise(done => {
    let last = performance.now(), worst = 0, frames = 0;
    const t0 = performance.now();
    const tick = () => { const n = performance.now(); worst = Math.max(worst, n - last); last = n; frames++;
      if (document.querySelectorAll('.lp-body li.lr').length >= 400 && n - t0 > 200) done({worst: Math.round(worst), frames, rows: document.querySelectorAll('.lp-body li.lr').length, ms: Math.round(n - t0)});
      else requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    document.querySelector('.later-btn').click();
  }));
  eq(gaps.rows, 400, 'all four hundred rows are drawn');
  assert(gaps.worst < 250, `and the page was never held for more than a quarter of a second (worst frame ${gaps.worst} ms, ${gaps.frames} frames, ${gaps.ms} ms in all)`);
  eq((await texts(page)).slice(0, 3), ['chunk number 0', 'chunk number 1', 'chunk number 2'], 'in reading order');
  await page.evaluate(() => { document.querySelector('.lp-body').scrollTop = 3000; });
  assert(await page.evaluate(() => document.querySelector('.lp-body').scrollTop > 2000 && window.scrollY === 0), 'the list scrolls by itself, not the page');
  await ctx.close();
});

/* ===== a5) a page that loads the script and nothing else is dressed by it ===== */
await scene('a5) the sheet comes with the script', async () => {
  const ctx = await newContext(browser);
  // a page with nothing on it, of the hub's own origin
  await ctx.route(/\/plain-page\//, route => route.fulfill({status: 200, contentType: 'text/html',
    body: '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>plain</title></head><body><p>a page with nothing</p></body></html>'}));
  const page = await ctx.newPage();
  watch(page, 'undressed');
  await page.goto(base + '/plain-page/');
  assert(await page.evaluate(() => !document.querySelector('link[href*="later.css"]') && typeof window.ParsehLater === 'undefined'), 'a page with neither the script nor the sheet');
  await page.addScriptTag({url: base + '/lib/later.js'});         // as lib/parseh.js loads a helper, from beside itself
  await page.waitForFunction(() => [...document.styleSheets].some(s => /\/lib\/later\.css$/.test(s.href || '')));
  assert(true, 'the script put its own sheet on the page, from beside itself');
  eq(await page.evaluate(() => document.querySelectorAll('link[href*="later.css"]').length), 1, 'once');
  const look = await page.evaluate(() => {
    const h = ParsehLater.panel({kind: 'book', ref: '/books/english/mini-en/reader/', title: 'Mini', lang: 'en', glossLang: 'fa', canCard: () => false,
                                 locate: () => Promise.resolve({found: true}), goTo: () => Promise.resolve()});
    document.body.appendChild(h.button);
    const s = getComputedStyle(h.button);
    return {radius: s.borderRadius, text: h.button.textContent};
  });
  eq([look.radius, look.text], ['6px', '⚑ later'], 'and the button is styled by it');
  await page.addScriptTag({url: base + '/lib/later.js'});
  eq(await page.evaluate(() => document.querySelectorAll('link[href*="later.css"]').length), 1, 'a script loaded twice does not make a second sheet');
  await ctx.close();
});

/* ============== b) a phone, 390 x 844, a touch screen ============== */
await scene('b) the phone\'s sheet', async () => {
  const ctx = await newContext(browser, 'phone');
  const page = await fixture(ctx, base);
  await flag(page, FIRST); await flag(page, SECOND); await flag(page, THIRD);
  const urlBefore = page.url();
  const hist = await page.evaluate(() => history.length);
  await openPanel(page, true);
  assert(await page.locator('.lp-wrap.lp-sheet:not([hidden])').count() === 1, 'a phone gets the sheet');
  const s = await page.evaluate(() => {
    const p = document.querySelector('.lp-panel').getBoundingClientRect(), W = innerWidth, H = innerHeight;
    const rows = [...document.querySelectorAll('.lp-body li.lr')].map(l => Math.round(l.getBoundingClientRect().height));
    const btns = [...document.querySelectorAll('.lp-wrap button, .lp-wrap a.lr-go')].filter(b => b.getClientRects().length && !b.closest('.lr-more') && !/lr-gl|lr-fold/.test(b.className)).map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), b.className]; });
    return {bottom: Math.round(p.bottom), H, top: Math.round(p.top), w: Math.round(p.width), W, rows, btns, card: document.querySelectorAll('.lr-card').length, queue: document.querySelectorAll('.lp-cards:not([hidden])').length,
            modal: document.querySelector('.lp-panel').getAttribute('aria-modal'), hist: history.length, state: history.state && history.state.parsehLater ? 'ours' : null, grip: getComputedStyle(document.querySelector('.lp-grip')).display};
  });
  assert(s.bottom === s.H && s.top >= s.H * 0.14 - 1, `the sheet stands on the foot of the screen and is at most 86% of it (${s.top}..${s.bottom} of ${s.H})`);
  assert(s.w <= s.W, 'and is no wider than the screen');
  assert(s.rows.every(h => h >= 48), `every row is a finger's height or more (${s.rows})`);
  const small = s.btns.filter(b => b[0] < 48 || b[1] < 48);
  assert(small.length === 0, `every button is at least 48 x 48 (${JSON.stringify(small)})`);
  eq([s.card, s.queue], [0, 0], 'a phone never makes cards: no + card, no «one after another», though the adapter says canCard');
  eq([s.modal, s.state, s.grip], ['true', 'ours', 'block'], 'the sheet is modal, has its own history entry and its grip');
  assert(s.hist === hist + 1, 'one history entry was pushed');
  await shot(page, 'b1-sheet-light');
  await page.tap('.lp-x');
  await shut(page);
  await sleep(300);
  eq(await page.evaluate(() => [history.state === null || !history.state.parsehLater, location.href]), [true, urlBefore], '✕ closes it and gives the history entry back; the page is where it was');
  await openPanel(page, true);
  await page.keyboard.press('Escape');
  await shut(page);
  assert(true, 'Escape closes it');
  await sleep(300);
  await openPanel(page, true);
  await page.touchscreen.tap(195, 40);
  await shut(page);
  assert(true, 'a tap on the dimmed page above it closes it');
  await sleep(300);
  await openPanel(page, true);
  await page.goBack();
  await shut(page);
  eq(page.url(), urlBefore, 'the back gesture closes the sheet and leaves the page where it is');
  eq(await page.evaluate(() => window.__toggles), [true, false, true, false, true, false, true, false], 'the page heard every opening and closing');
  await openPanel(page, true);
  await page.tap('.lp-body li.lr:nth-child(1) .lr-x');
  await rowsAre(page, 2);
  const undo = await page.evaluate(() => { const r = document.querySelector('.ls-undo').getBoundingClientRect(), s = document.getElementById('later-snack').getBoundingClientRect(); return [Math.round(r.height), Math.round(r.width), s.right <= innerWidth && s.left >= 0 && s.bottom <= innerHeight]; });
  assert(undo[0] >= 44 && undo[1] >= 48 && undo[2], `«Undo» is a finger's reach (${undo[0]} x ${undo[1]}) and on the screen`);
  await shot(page, 'b2-sheet-removed');
  await page.tap('.ls-undo');
  await rowsAre(page, 3);
  await page.tap('.lp-test');
  await page.tap('.lp-body li.lr:nth-child(1) .lr-hit');
  const tb = await page.evaluate(() => [...document.querySelectorAll('.lp-body li.lr:nth-child(1) .lr-acts .lr-b')].map(b => { const r = b.getBoundingClientRect(); return [b.textContent, Math.round(r.width), Math.round(r.height)]; }));
  assert(tb.length === 2 && tb.every(b => b[1] >= 48 && b[2] >= 48), `«I know it» and «again» are each 48 x 48 or more (${JSON.stringify(tb)})`);
  await shot(page, 'b3-sheet-test');
  await page.tap('.lp-test');
  await page.tap('.lp-x');
  await shut(page);
  await sleep(300);
  await page.setViewportSize({width: 320, height: 640});
  await sleep(200);
  await flag(page, PERSIAN);
  await openPanel(page, true);
  await page.tap('.lp-sc:nth-child(2)');
  await rowsAre(page, 4);
  const w = await page.evaluate(() => { const p = document.querySelector('.lp-panel'), b = document.querySelector('.lp-body');
    const over = [...document.querySelectorAll('.lp-wrap *')].filter(e => e.getClientRects().length && e.getBoundingClientRect().right > innerWidth + 0.5).map(e => e.className);
    return {doc: document.documentElement.scrollWidth, inner: innerWidth, panel: [p.scrollWidth, p.clientWidth], body: [b.scrollWidth, b.clientWidth], over}; });
  assert(w.doc <= w.inner && w.panel[0] <= w.panel[1] && w.body[0] <= w.body[1] && w.over.length === 0, `at 320 px nothing goes sideways (${JSON.stringify(w)})`);
  await shot(page, 'b4-sheet-320');
  await ctx.close();
});

/* ============== c) the three themes: 4.5:1 ============== */
await scene('c) the three themes', async () => {
  const ctx = await newContext(browser);
  const page = await fixture(ctx, base);
  await flag(page, FIRST); await flag(page, SECOND); await flag(page, THIRD); await flag(page, PERSIAN);
  const lone = await flag(page, {...FIRST, sub: '3.1-eeeeeeeeeeee', k: 2, para: '3:1', label: '3.1', text: 'a lost one'});
  await page.evaluate(id => { window.__adrift[id] = true; }, lone);
  await openPanel(page);
  await page.click('.lp-sc:nth-child(2)');
  await rowsAre(page, 5);
  await page.click('.lp-body li.lr:nth-child(2) .lr-gl');
  await page.waitForSelector(`li.lr[data-id="${lone}"][data-state="adrift"]`);
  for (const theme of ['light', 'dark', 'sepia']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    // the line «removed · Undo» is up, and one flag's parts are open
    await page.evaluate(() => ParsehLater.remove(ParsehLater.list()[0].id));
    await sleep(150);
    await shot(page, 'c1-list-' + theme);
    let list = await page.evaluate(contrastOf, LISTED);
    // and in Test myself, with one meaning shown
    await page.evaluate(() => ParsehLater.undo());
    await rowsAre(page, 5);
    await page.click('.lp-test');
    await page.click('.lp-body li.lr:nth-child(2) .lr-hit');
    await shot(page, 'c2-test-' + theme);
    list = list.concat(await page.evaluate(contrastOf, LISTED));
    await page.click('.lp-test');
    const bad = list.filter(r => r.ratio < 4.5);
    assert(list.length > 40 && bad.length === 0, `${theme}: ${list.length} texts, the worst ${Math.min(...list.map(r => r.ratio))}:1${bad.length ? ' -- BELOW 4.5: ' + JSON.stringify(bad.slice(0, 8)) : ' -- all 4.5:1 or better'}`);
  }
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  await ctx.close();
});

/* ============ d) the page /later/ and the hub's door ============ */
await scene('d) the page and the hub\'s door', async () => {
  const ctx = await newContext(browser);
  const page = await ctx.newPage();
  watch(page, 'hub');
  await page.goto(base + '/');
  eq(await page.locator('.hub-browser a.door[href="/later/"] .tag').innerText(), 'nothing marked yet', 'the hub\'s door says «nothing marked yet» while nothing is flagged');
  await page.goto(base + '/later/');
  await page.waitForSelector('.lp-empty');
  assert(/Point at a chunk and press L/.test(await page.locator('.lp-empty').innerText()), 'the page\'s empty state says how to flag a chunk');
  assert((await page.locator('.lp-test').isHidden()) && (await page.locator('.lp-copy').isHidden()), 'with no Test myself and no Copy the list');
  await shot(page, 'd1-page-empty');
  const refused = await api(base, '/__later', {by: 'x', ops: [{op: 'add'}]});
  assert(refused.status === 400 && /flag is an object/.test(refused.json.error), 'a change with no record is refused in words, over the wire: ' + (refused.json && refused.json.error));
  // flag them as the pages do, so that the ids are the ones the reader and the player make
  const mk = await ctx.newPage();
  await mk.goto(base + '/later/');
  // EACH FLAG GETS ITS OWN MOMENT, two seconds after the one before, named here and not read off the clock: made in a loop the five were
  // stamped within a millisecond or two of each other, a flag's `at` has the clock's millisecond for its grain, and "the one flagged
  // last first" below is an order by `at` -- two flags stamped in the same millisecond keep the order they were made in, so the heading of
  // 'Mini' (its newest flag made third) came before 'Persian one' (made fourth) in about one run in a few (measured: 43 of 200 loops of
  // five had two neighbours with the same stamp)
  await mk.evaluate(async ps => {
    const t0 = Date.now() / 1000 - 20;
    let i = 0;
    for (const p of ps) await ParsehLater.add(ParsehLater.record(Object.assign({}, p, {at: t0 + 2 * i++})));
    await ParsehLater.sync();
  }, [FIRST, SECOND, THIRD, PERSIAN, CLIP]);
  await mk.close();
  eq((await askDoor(base, 'counts=1')).total, 5, 'the five flags are on the computer');
  await page.goto(base + '/');
  eq(await page.locator('.hub-browser a.door[href="/later/"] .tag').innerText(), '5 chunks', 'the hub\'s door counts them');
  eq(await page.locator('.hub-mobile a.m-door[href="/later/"] .tag').evaluate(t => t.textContent), '5 chunks', 'in the phone layout too');
  const per = JSON.parse(await page.locator('.hub-browser a.door[href="/later/"] .tag').getAttribute('data-counts'));
  eq([per.all, per.en, per.fa, per.it], ['5 chunks', '4 chunks', '1 chunk', 'nothing marked yet'], 'the count carries each language\'s own, for the chips to say');
  await page.click('.hub-browser .parseh-langs .chip[data-pick="en"]');
  eq(await page.locator('.hub-browser a.door[href="/later/"] .tag').innerText(), '4 chunks', 'and the English chip says how many are English');
  await shot(page, 'd2-hub-door');
  await page.click('.hub-browser .parseh-langs .chip[data-pick="all"]');
  eq(await page.locator('.hub-browser a.door[href="/later/"] .tag').innerText(), '5 chunks', 'all of them again with the first chip');

  await page.goto(base + '/later/');
  await page.waitForSelector('.lp-body li.lr');
  const heads = await page.$$eval('.lp-gh', hs => hs.map(h => [h.querySelector('.lp-gname').textContent, h.querySelector('.lp-gm').textContent, h.querySelector('.lp-gname').getAttribute('href')]));
  eq(heads.map(h => h.slice(0, 2)), [['Street market', 'English · 1 chunk'], ['Persian one', 'Persian · 1 chunk'], ['Mini', 'English · 3 chunks']], 'the list is under a heading for each book and video -- the one flagged last first -- with its language and its count');
  eq(heads.map(h => h[2]), ['/youtube/v/' + VIDEO + '/', FA, BOOK], 'a heading\'s name opens the book or the video itself');
  const links = await page.$$eval('.lp-body li.lr', ls => ls.map(l => ({id: l.getAttribute('data-id'), href: l.querySelector('.lr-go').getAttribute('href'), tag: l.querySelector('.lr-go').tagName, text: l.querySelector('.lr-text').textContent, place: l.querySelector('.lr-place').textContent})));
  const vid = links.find(l => l.id.startsWith('later:video'));
  eq(vid.href, `/youtube/v/${VIDEO}/#later=${encodeURIComponent(vid.id)}`, 'a video\'s flag opens the player at the caption: <player>#later=<id>');
  eq(vid.place, '0:02', 'the place of a video\'s flag is its time');
  const bk = links.find(l => l.text === 'wound the clock');
  eq(bk.href, `${BOOK}#later=${encodeURIComponent(bk.id)}`, 'a book\'s flag opens the reader at the chunk: <reader>#later=<id>');
  eq(links.map(l => l.tag), links.map(() => 'A'), 'each is a link');
  eq(await page.$$eval('.lp-main .lr-text[lang=fa]', ts => ts.map(t => [t.dir, getComputedStyle(t).direction])), [['rtl', 'rtl']], 'the Persian chunk is right to left on the page');
  eq(await page.evaluate(() => [document.querySelectorAll('.lr-card').length, document.querySelectorAll('.lp-cards:not([hidden])').length, document.querySelectorAll('.lp-scope').length]), [0, 0, 0], 'the page makes no cards and has no «this book only»');
  await shot(page, 'd3-page-browser');
  await page.click('.lp-test');
  eq(await page.evaluate(() => [document.querySelectorAll('.lp-body .lr-gloss').length, document.querySelectorAll('.lr-tap').length]), [0, 5], 'Test myself hides the meanings on the page');
  await page.click('.lp-body li.lr:nth-child(1) .lr-hit');
  await page.click('.lp-body li.lr:nth-child(1) .lr-know');
  await rowsAre(page, 4);
  await until(async () => (await askDoor(base, 'counts=1')).total === 4);
  assert(true, '«I know it» takes it off the computer\'s list too');
  await page.click('.ls-undo');
  await rowsAre(page, 5);
  await until(async () => (await askDoor(base, 'counts=1')).total === 5);
  assert(true, 'and the Undo is on the computer too');
  await page.click('.lp-test');
  await page.click('.lp-copy'); await page.click('.lp-fmt:nth-child(1)');
  const md = await page.evaluate(() => navigator.clipboard.readText());
  assert(/^## Street market \(English\)\n\n- \*\*opens early\*\* — starts soon \(0:02\)\n\n## Persian one \(Persian\)\n\n- \*\*کتاب‌ها را خواندم\*\* — ketâb-hâ râ khândam · I read the books \(1\.1 · فصل ۱\)\n\n## Mini \(English\)\n\n- \*\*wound the clock\*\*/.test(md),
         'the page copies every book and video, each under its own heading: ' + JSON.stringify(md.slice(0, 160)));
  await ctx.close();

  // the phone's layout of the same page
  const pctx = await newContext(browser, 'phone');
  await pctx.addCookies([{name: 'parseh_mode', value: 'mobile', url: base}]);
  await pctx.addInitScript(() => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (e) {} });
  const ph = await pctx.newPage();
  watch(ph, 'phone page');
  await ph.goto(base + '/');
  const dr = await ph.evaluate(() => { const a = document.querySelector('.hub-mobile a.m-door[href="/later/"]'), r = a.getBoundingClientRect(); a.scrollIntoView({block: 'center'}); return {h: Math.round(r.height), vis: r.width > 0, tag: a.querySelector('.tag').textContent}; });
  assert(dr.vis && dr.h >= 72 && dr.tag === '5 chunks', `the phone hub has the door, ${dr.h} px high, saying ${dr.tag}`);
  await shot(ph, 'd4-hub-phone');
  await Promise.all([ph.waitForURL(base + '/later/'), ph.tap('.hub-mobile a.m-door[href="/later/"]')]);
  await ph.waitForSelector('.lp-body li.lr');
  const m = await ph.evaluate(() => ({browserBar: getComputedStyle(document.querySelector('.parseh-bar[data-layout=browser]')).display, mobileBar: getComputedStyle(document.querySelector('.parseh-bar[data-layout=mobile]')).display,
    rows: [...document.querySelectorAll('.lp-body li.lr')].map(l => Math.round(l.getBoundingClientRect().height)),
    btns: [...document.querySelectorAll('.lp-main button, .lp-main a.lr-go')].filter(b => b.getClientRects().length && !/lr-gl|lr-fold/.test(b.className)).map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), b.className]; }),
    sideways: document.documentElement.scrollWidth - innerWidth, switchBtns: document.querySelectorAll('.parseh-bar[data-layout=mobile] [data-parseh-mode]').length}));
  eq([m.browserBar, m.mobileBar, m.switchBtns], ['none', 'flex', 2], 'the phone layout shows its own bar, with the Browser | Mobile switch');
  assert(m.rows.every(h => h >= 48), `every row is a finger's height (${m.rows})`);
  const tiny = m.btns.filter(b => b[0] < 48 || b[1] < 48);
  assert(tiny.length === 0, `every button is 48 x 48 or more (${JSON.stringify(tiny)})`);
  assert(m.sideways <= 0, 'nothing goes sideways');
  await shot(ph, 'd5-page-phone');
  await ph.tap('.lp-body li.lr:nth-child(1) .lr-x');
  await rowsAre(ph, 4);
  await ph.tap('.ls-undo');
  await rowsAre(ph, 5);
  assert(true, 'a phone can remove a flag from the page, and take it back');
  await ph.setViewportSize({width: 320, height: 640});
  await sleep(200);
  eq(await ph.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 0), true, 'and at 320 px the page does not go sideways');
  await ph.setViewportSize({width: 390, height: 844});
  for (const theme of ['light', 'dark', 'sepia']) {
    await ph.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    await ph.evaluate(() => ParsehLater.remove(ParsehLater.list()[0].id));
    await sleep(150);
    const list = await ph.evaluate(contrastOf, PAGE_LISTED);
    const bad = list.filter(r => r.ratio < 4.5);
    assert(list.length > 15 && bad.length === 0, `the page in ${theme}: the worst of ${list.length} texts is ${Math.min(...list.map(r => r.ratio))}:1${bad.length ? ' ' + JSON.stringify(bad) : ''}`);
    await shot(ph, 'd6-page-phone-' + theme);
    await ph.evaluate(() => ParsehLater.undo());
    await rowsAre(ph, 5);
  }
  await pctx.close();
});

/* ============ e) two devices, one server ============ */
await scene('e) two devices', async () => {
  const A = await newContext(browser), B = await newContext(browser);
  const pa = await fixture(A, base), pb = await fixture(B, base);
  const x = await flag(pa, FIRST), y = await flag(pa, SECOND);
  await pa.evaluate(() => ParsehLater.sync());
  await pb.evaluate(() => ParsehLater.sync());
  eq(await btnText(pb), '⚑ later 2', 'a flag made in one browser is on the other\'s button after it syncs');
  eq(await ids(pb), await ids(pa), 'the same two flags, with the same ids');
  eq(await pb.evaluate(id => ParsehLater.get(id).by, x), 'Linux computer · Chrome', 'saying which device made it');
  await flag(pb, FIRST);
  await pb.evaluate(() => ParsehLater.sync());
  await pa.evaluate(() => ParsehLater.sync());
  eq((await askDoor(base, 'counts=1')).total, 2, 'a chunk flagged on both is ONE flag');
  // a removal in A is not undone by B, which still holds the flag
  await pa.evaluate(id => ParsehLater.remove(id, {toast: false}), x);
  await pa.evaluate(() => ParsehLater.sync());
  eq(await pb.evaluate(id => ParsehLater.has(id), x), true, 'B still holds the flag A removed');
  await pb.evaluate(() => ParsehLater.sync());
  eq(await pb.evaluate(id => ParsehLater.has(id), x), false, 'and drops it when it syncs');
  eq((await askDoor(base, 'all=1')).items.map(r => r.id), [y], 'the computer does not bring it back');
  // and not even by a flag B made while it was away, before A's removal
  await B.route(/\/__later(\?|$)/, route => route.abort());
  await flag(pb, THIRD);
  const z = await pb.evaluate(() => ParsehLater.list().find(r => r.text === 'opens early').id);
  await pb.evaluate(id => ParsehLater.remove(id, {toast: false}), z);
  const z2 = await flag(pb, THIRD);                  // flagged again while away: an add, as old as this moment
  eq([z2, await pb.evaluate(() => ParsehLater.pending())], [z, 1], 'B, away, has one change waiting: the chunk flagged again');
  await sleep(60);
  await pa.evaluate(() => ParsehLater.sync());
  await flag(pa, THIRD);
  await pa.evaluate(() => ParsehLater.sync());
  await sleep(60);
  await pa.evaluate(id => ParsehLater.remove(id, {toast: false}), z);        // A removes it, AFTER B flagged it
  await pa.evaluate(() => ParsehLater.sync());
  await B.unroute(/\/__later(\?|$)/);
  await pb.evaluate(() => ParsehLater.sync());
  eq(await pb.evaluate(id => [ParsehLater.has(id), ParsehLater.pending()], z), [false, 0], 'B comes back and sends its flag, which is older than A\'s removal: the removal stands, on B too');
  assert(!(await askDoor(base, 'all=1')).items.some(r => r.id === z), 'and on the computer');
  await A.close(); await B.close();
});

/* ============ f) a phone with the computer away ============ */
await scene('f) the computer away', async () => {
  const P = await newContext(browser, 'phone');
  await P.route(/\/__later(\?|$)/, route => route.abort());
  const pp = await fixture(P, base);
  eq(await pp.evaluate(() => ParsehLater.ready().then(r => r.synced)), false, 'ready() says the computer could not be reached, and does not hang');
  const x = await flag(pp, FIRST), y = await flag(pp, THIRD);
  eq(await btnText(pp), '⚑ later 2', 'flags can be made with the computer away');
  eq(await pp.evaluate(() => ParsehLater.pending()), 2, 'two changes wait to be sent');
  await pp.reload();
  await pp.waitForFunction(() => window.ParsehLater && window.__panel);
  eq(await btnText(pp), '⚑ later 2', 'a reload with the computer still away keeps them');
  eq(await pp.evaluate(() => ParsehLater.pending()), 2, 'and what waits');
  await openPanel(pp, true);
  assert(/2 changes will be sent when the computer can be reached/.test(await pp.locator('.lp-status').innerText()), 'the list says so: ' + (await pp.locator('.lp-status').innerText()));
  await shot(pp, 'f1-away');
  await pp.tap('.lp-body li.lr:nth-child(1) .lr-x');
  await rowsAre(pp, 1);
  eq(await pp.evaluate(() => ParsehLater.pending()), 2, 'a removal made away waits too (the second flag stays; the first\'s change is one: removed)');
  await pp.tap('.ls-undo');
  await rowsAre(pp, 2);
  assert((await askDoor(base, 'all=1')).items.length === 0, 'nothing of it is on the computer yet');
  // the computer is back: the browser says it is online
  await P.unroute(/\/__later(\?|$)/);
  await pp.evaluate(() => window.dispatchEvent(new Event('online')));
  await pp.waitForFunction(() => ParsehLater.pending() === 0, null, {timeout: 15000});
  eq((await askDoor(base, 'all=1')).items.map(r => r.id).sort(), [x, y].sort(), 'what was flagged away arrives when the computer is back');
  await pp.waitForFunction(() => !/will be sent/.test(document.querySelector('.lp-status').textContent));
  assert(true, 'and the list stops saying it waits');
  // a second browser sees them
  const D = await newContext(browser);
  const pd = await fixture(D, base);
  await pd.evaluate(() => ParsehLater.ready());
  eq(await btnText(pd), '⚑ later 2', 'another browser has them');
  await D.close();

  // a change the computer refuses in words does not stop the others: staged in the outbox of a phone that is away
  const Q = await newContext(browser, 'phone');
  await Q.route(/\/__later(\?|$)/, route => route.abort());
  const pq = await fixture(Q, base);
  const bad = {op: 'add', record: {id: 'later:book:/books/english/mini-en/reader/:9.9-ffffffffffff:0:zz', kind: 'book', ref: '/books/english/mini-en/reader/', at: Date.now() / 1000, text: '', where: {}}};
  await pq.evaluate(b => localStorage.setItem('parseh_later_out', JSON.stringify([b])), bad);
  await pq.reload();
  await pq.waitForFunction(() => window.ParsehLater && window.__panel);
  eq(await pq.evaluate(() => ParsehLater.pending()), 1, 'a change the computer will refuse waits in the outbox like any other');
  const said = await api(base, '/__later', {by: 'x', ops: [bad]});
  assert(said.status === 400 && /chunk's text/.test(said.json.error), 'and the computer does refuse it, in words: ' + said.json.error);
  await flag(pq, SECOND);
  eq(await pq.evaluate(() => ParsehLater.pending()), 2, 'a good one is queued behind it');
  await Q.unroute(/\/__later(\?|$)/);
  await pq.evaluate(() => window.dispatchEvent(new Event('online')));
  await pq.waitForFunction(() => ParsehLater.pending() === 0, null, {timeout: 15000});
  assert((await askDoor(base, 'all=1')).items.some(r => r.text === 'the second chunk'), 'the good change arrived: the refusal did not stop it');
  eq(await pq.evaluate(() => ParsehLater.pending()), 0, 'and the refused one was dropped, not kept for ever');
  await Q.close();
  await P.close();
});

/* ============ g) nothing went wrong ============ */
await scene('g) nothing went wrong', async () => {
  // what was PROVOKED: the door cut off on purpose (net::ERR_FAILED, in the page of `fixture` that is away or the one beside it)
  // and the one refusal in words that a page logs as a failed load
  const rest = errors.filter(e => !(/ERR_FAILED|Failed to fetch|Failed to load resource/.test(e)));
  eq(rest, [], 'no page threw, and none logged an error but the requests cut off or refused on purpose');
  const provoked = errors.length - rest.length;
  console.log(`  note: ${provoked} logged request(s) were the ones cut off or refused on purpose`);
  assert(!/Traceback/.test(H.log.join('')), 'the server printed no traceback: ' + (H.log.join('').match(/Traceback[\s\S]{0,600}/) || [''])[0]);
  eq((await run(PY, ['-c', OWN])).out, configBefore, 'the checkout\'s config/ is exactly as it was');
});
console.log('\n%d checks passed', passed);
if (failures.length) throw Error(failures.length + ' scene(s) failed:\n  ' + failures.join('\n  '));
} catch (e) {
  failure = e;
} finally {
  try { await browser.close(); } catch { /* gone */ }
  try { H.proc.kill(); } catch { /* gone */ }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true});
}
if (failure) { console.error(failure); Deno.exit(1); }
Deno.exit(0);
