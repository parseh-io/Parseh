// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/vocab_list.mjs
//      VOCAB_SHOTS=<dir> saves the screenshots; VOCAB_ONLY=a,c runs those scenes alone
//
// THE VOCABULARY LIST (a0.6.3, TO-DO 11.14): lib/vocab.js, lib/vocab-reader.js, the
// player's side in youtube/lib/player.js -- DRIVEN in a browser on the REAL hub
// (serve.main on a temporary toolbox, tests/vocab_harness.py), asserting what is
// DRAWN (where it is on the screen, what is under a point of it), not only what is
// in the DOM.
//
//  a) A BOOK ON A COMPUTER (the Persian book of three chapters, the second and third
//     fetched when wanted): the door, the panel at the right with the page live
//     beside it, This chapter / Whole book, one row per word with its count, right to
//     left; a click goes to the word's first place and the next click to the next, into
//     a chapter not yet fetched; the three orders; the filter; Copy (the clipboard's
//     own text); Test myself; Print; the V key and Esc; one panel on the right at a time;
//     the cards one after another, with the word's own romanisation and meaning.
//  b) EVERY MINI BOOK (twelve languages): the list drawn, the words in their
//     language's code and direction, a verb with the language's own two labels, and the
//     same words and counts as the computer's own reading of the sources (GET __vocab).
//  c) A VIDEO: a Persian one in the books' macros (one word written two ways, a verb
//     with two meanings), Whole video / Up to here, a click to a caption and the next;
//     an Arabic one; and a video whose lines are plain text, which says so.
//  d) A PHONE at 390x844 with a finger: no door in the header, the gear's row, the
//     sheet from the foot, a tap on a word takes the sheet down and shows the place,
//     the back gesture closes it; and nothing sideways at 320.
//  e) NOTHING WENT WRONG: no page error, no server traceback, config/ as it was.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('VOCAB_SHOTS') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-vocab-'});
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
const OWN = 'import sys,hashlib;sys.path.insert(0,"tests");import configguard;s=configguard.snapshot();print(hashlib.sha1(repr(sorted(s.items())).encode()).hexdigest())';
const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36';

const configBefore = (await run(PY, ['-c', OWN])).out;
const built = await run(PY, ['tests/vocab_harness.py', 'build', TMP]);
if (built.code) throw Error('the toolbox could not be built:\n' + built.err + built.out);
const MADE = JSON.parse(built.out.trim().split('\n').pop());
const FA = MADE.multi_fa;

const log = [];
const PORT = freePort();
const hub = new Deno.Command(PY, {args: ['tests/vocab_harness.py', 'serve', TMP, String(PORT)], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
drain(hub.stdout, log); drain(hub.stderr, log);
const B = `http://127.0.0.1:${PORT}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/__activity'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 90000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}
const LANGS = JSON.parse((await run(PY, ['-c', 'import sys,json;sys.path.insert(0,"lib");import languages;print(json.dumps({c: languages.get(c).as_json() for c in languages.CODES}))'])).out);

// what the pages log that is not a fault of this: the translation model's meta files and the fonts this tree has none of
const KNOWN = [/\/mt\/(en-en|engine)\/meta\.json/, /Failed to load resource: the server responded with a status of 404/];
const errors = [];
function watch(page, label) {
  page.on('pageerror', e => errors.push(`${label}: pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error' && !KNOWN.some(k => k.test(m.text()))) errors.push(`${label}: console: ${m.text()}`); });
}
async function shot(page, name) {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`});
  console.log('  shot', `${SHOTS}/${name}.png`);
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
const failures = [];
const ONLY = (Deno.env.get('VOCAB_ONLY') || '').split(',').filter(Boolean);
async function scene(name, fn) {
  if (ONLY.length && !ONLY.some(o => name.startsWith(o + ')'))) return;
  console.log(name);
  try { await fn(); }
  catch (e) { const said = String(e && e.stack || e).split('\n').slice(0, 4).join(' | '); failures.push(name + ' -- ' + said); console.log('  !! ' + said); }
}

let browser, failure;
async function ctxOf(kind) {
  const phone = kind === 'phone';
  const opts = phone ? {viewport: {width: 390, height: 844}, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: ANDROID}
    : {viewport: {width: 1280, height: 800}};
  const ctx = await browser.newContext({...opts, serviceWorkers: 'block', permissions: ['clipboard-read', 'clipboard-write']});
  await ctx.addCookies([{name: 'parseh_mode', value: phone ? 'mobile' : 'browser', url: B}]);
  return ctx;
}
async function openReader(ctx, path, label = 'reader') {
  const page = await ctx.newPage();
  watch(page, label);
  await page.goto(B + path);
  await page.waitForFunction(() => window.ParsehVocabReader && ParsehVocabReader.panel && window.ParsehVocline && ParsehVocline.entries,
                             null, {timeout: 25000});
  await sleep(350);                      // the reader puts the reading place back a moment after it loads
  if (await page.$('.pf-bar')) await page.click('.pf-stay');
  return page;
}
async function openVideo(ctx, id, label = 'video') {
  const page = await ctx.newPage();
  watch(page, label);
  await page.goto(B + `/youtube/v/${id}/`);
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.vocab && ParsehPlayer.vocab.panel() &&
                             document.querySelectorAll('#segs .seg .w').length > 0, null, {timeout: 30000});
  await page.waitForFunction(() => ParsehPlayer.ready(), null, {timeout: 25000});
  await sleep(300);
  return page;
}
const isOpen = page => page.evaluate(() => !!document.querySelector('.vocab-wrap:not([hidden]) .vocab-panel'));
async function openList(page) {
  if (!(await isOpen(page))) await page.click('.vocab-btn');
  await page.waitForSelector('.vocab-wrap:not([hidden]) .vocab-panel');
  await page.waitForFunction(() => !/reading/.test(document.querySelector('.vocab-wrap .lp-status').textContent));
}
// the rows as they are DRAWN: the word's text, the count, the meaning
const rows = page => page.evaluate(() => [...document.querySelectorAll('.vocab-wrap .vr')].map(li => ({
  word: li.querySelector('.vr-w').textContent, n: li.querySelector('.vr-n').textContent,
  mean: (li.querySelector('.vr-mean') || {}).textContent ?? null})));
const words = async page => (await rows(page)).map(r => r.word + ' ' + r.n);
// a button by its own words, inside the panel
const tool = (page, text) => page.locator('.vocab-wrap .lp-tools button', {hasText: text}).first();
// what was lit by the last jump: the chunk numbers of the elements wearing the flash, and whether one of them is on the screen
const lit = page => page.evaluate(() => {
  const els = [...document.querySelectorAll('.later-flash')];
  const shown = els.filter(e => e.getClientRects().length).map(e => e.getBoundingClientRect());
  const head = document.querySelector('header'), top = head ? head.getBoundingClientRect().bottom : 0;
  return {c: [...new Set(els.map(e => +(e.closest('[data-c]') || e).getAttribute('data-c')))],
          seen: shown.some(r => r.top >= top - 2 && r.bottom <= innerHeight + 2 && r.height > 0)};
});
// the panel where a person sees it: inside the window, and what is at the middle of a row is that row
const drawn = page => page.evaluate(() => {
  const box = document.querySelector('.vocab-wrap:not([hidden]) .vocab-panel');
  if (!box) return null;
  const r = box.getBoundingClientRect(), row = document.querySelector('.vocab-wrap .vr-go');
  const rr = row ? row.getBoundingClientRect() : null;
  const hit = rr ? document.elementFromPoint(rr.left + rr.width / 2, rr.top + rr.height / 2) : null;
  return {left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top), bottom: Math.round(r.bottom),
          w: innerWidth, h: innerHeight, rowHit: !!(hit && row.contains(hit)),
          sideways: box.scrollWidth - box.clientWidth, page: document.documentElement.scrollWidth - innerWidth};
});

try {
browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});

/* ====== a) a book on a computer ====== */
await scene('a) a book of three chapters, on a computer', async () => {
  const ctx = await ctxOf('desk'), page = await openReader(ctx, FA, 'multi-fa');
  const door = await page.locator('.vocab-btn').boundingBox();
  assert(door && door.y >= 0 && door.y + door.height <= 120, 'the door «vocabulary» is drawn in the header');
  eq(await page.evaluate(() => document.querySelector('.later-btn').nextElementSibling.classList.contains('vocab-btn')), true,
     'it stands beside «⚑ later»');
  await openList(page);
  const d = await drawn(page);
  assert(d.right === d.w && d.left >= d.w - 421 && d.top >= 60 && d.bottom <= d.h && d.rowHit,
         `the panel is drawn at the right of the window and its first row is what is under its middle (${JSON.stringify(d)})`);
  // the page beside it is live: what is at a point of the text is the text, not a backdrop
  const textHit = await page.evaluate(() => { const e = document.elementFromPoint(300, 400); return !!(e && e.closest('main')); });
  eq(textHit, true, 'the page beside the panel is not covered: a point of the text is the text');
  eq(await page.evaluate(() => [...document.querySelectorAll('.vocab-scope .lp-sc')].map(b => b.textContent + (b.getAttribute('aria-pressed') === 'true' ? '*' : ''))),
     ['This chapter*', 'Whole book'], 'it opens on This chapter, beside Whole book');
  eq(await words(page), ['جا ×10', 'تر ×1', 'مثل ×1', 'سال ×1'], 'chapter 1: four words, as they come, each with its count');
  eq((await rows(page)).map(r => r.mean), ['place', 'wet', 'like', 'year'], 'each with its meaning');
  const rtl = await page.evaluate(() => {
    const h = document.querySelector('.vocab-wrap .vr-head'), w = h.querySelector('.vr-w').getBoundingClientRect(),
          r = h.querySelector('.vr-rom').getBoundingClientRect();
    return {dir: h.getAttribute('dir'), lang: h.querySelector('.vr-w').getAttribute('lang'), wordRight: w.right > r.right};
  });
  eq(rtl, {dir: 'rtl', lang: 'fa', wordRight: true}, 'the word runs right to left, in its own language, at the right with its romanisation after it');
  await shot(page, 'a-panel');

  // a click goes to the first place; the next click to the next
  await page.locator('.vocab-wrap .vr-go').first().click();
  let l = await until(async () => { const x = await lit(page); return x.c.length && x; }, 6000, 'the first place lit');
  eq(l, {c: [0], seen: true}, 'جا: the first click lights chunk 0, on the screen');
  await page.locator('.vocab-wrap .vr-go').first().click();
  l = await until(async () => { const x = await lit(page); return x.c[0] === 4 && x; }, 6000, 'the next place lit');
  eq(l, {c: [4], seen: true}, 'the second click lights the next place, chunk 4');
  assert(await isOpen(page), 'and the panel stays open beside the text on a computer');
  assert(/place 2 of 10/.test(await page.locator('.vocab-wrap .lp-status').textContent()), 'the status says which place of how many');

  // the whole book, and a word's third place in a chapter the page has not fetched yet
  eq(await page.evaluate(() => !!document.querySelector('section.chapter[data-ch="2"][data-part]')), true, 'chapter 3 has not been fetched');
  await tool(page, 'Whole book').click();
  await page.waitForFunction(() => /×30/.test(document.querySelector('.vocab-wrap .vr-n').textContent));
  eq(await words(page), ['جا ×30', 'تر ×3', 'مثل ×3', 'سال ×3'], 'the whole book: the same words, three chapters\' counts');
  const tar = page.locator('.vocab-wrap .vr-go').nth(1);
  for (const want of [1, 41, 81]) {
    await tar.click();
    l = await until(async () => { const x = await lit(page); return x.c[0] === want && x; }, 8000, 'chunk ' + want);
    eq(l, {c: [want], seen: true}, `تر: a click lights chunk ${want}, on the screen`);
  }
  eq(await page.evaluate(() => !document.querySelector('section.chapter[data-ch="2"][data-part]')), true, 'chapter 3 was fetched to show it');
  await tar.click();
  l = await until(async () => { const x = await lit(page); return x.c[0] === 1 && x; }, 6000, 'round again');
  eq(l.c, [1], 'and the fourth click goes round to the first place again');

  // This chapter follows the reading place, which the jump to chapter 3 moved
  await tar.click(); await tar.click();
  await until(async () => (await lit(page)).c[0] === 81, 6000, 'back in chapter 3');
  await tool(page, 'This chapter').click();
  await page.waitForFunction(() => /×10/.test(document.querySelector('.vocab-wrap .vr-n').textContent));
  await page.locator('.vocab-wrap .vr-go').first().click();
  l = await until(async () => { const x = await lit(page); return x.c[0] === 80 && x; }, 6000, 'chapter 3\'s first');
  eq(l.c, [80], 'This chapter is now chapter 3, where the reading place went: جا\'s first place there is chunk 80');

  // the three orders
  await tool(page, 'A–Z').click();
  eq(await words(page), ['تر ×1', 'جا ×10', 'سال ×1', 'مثل ×1'], 'A–Z in the Persian alphabet (ت ج س م)');
  await tool(page, 'Most frequent').click();
  eq((await words(page))[0], 'جا ×10', 'Most frequent: جا first');
  await tool(page, 'As they come').click();

  // the filter: a word, a romanisation, a meaning
  const filter = async (text, want, what) => {
    await page.fill('.vocab-find', text);
    eq((await rows(page)).map(r => r.word), want, what);
  };
  await filter('sāl', ['سال'], 'the filter finds a romanisation');
  await filter('wet', ['تر'], 'and a meaning');
  await filter('جا', ['جا'], 'and a word');
  await filter('nothing like it', [], 'and nothing where nothing matches');
  assert(/0 words of 4 match/.test(await page.locator('.vocab-wrap .lp-status').textContent()), 'which the status says');
  await filter('', ['جا', 'تر', 'مثل', 'سال'], 'emptied, everything again');

  // Copy: the clipboard's own text
  await page.evaluate(() => navigator.clipboard.writeText('before'));
  await tool(page, 'Copy').click();
  await until(async () => (await page.evaluate(() => navigator.clipboard.readText())) !== 'before', 4000, 'the clipboard');
  eq(await page.evaluate(() => navigator.clipboard.readText()), 'جا\tjā\tplace\nتر\ttar\twet\nمثل\tmesl\tlike\nسال\tsāl\tyear\n',
     'Copy puts the words on the clipboard as a table: word, romanisation, meaning');

  // Test myself
  await tool(page, 'Test myself').click();
  eq(await page.evaluate(() => [document.querySelectorAll('.vocab-wrap .vr-mean').length, document.querySelectorAll('.vocab-wrap .vr-show').length]),
     [0, 4], 'Test myself hides every meaning behind a button');
  await page.locator('.vocab-wrap .vr-show').nth(1).click();
  eq((await rows(page)).map(r => r.mean), [null, 'wet', null, null], 'and a tap shows that word\'s meaning alone');
  await tool(page, 'Test myself').click();

  // Print: the list alone, as a table
  await page.evaluate(() => { window.__printed = null; window.print = () => {
    const t = document.querySelector('.vocab-print');
    window.__printed = {rows: t ? t.querySelectorAll('tr').length : 0, on: document.documentElement.classList.contains('vocab-printing'),
                        first: t ? t.querySelector('tr').innerText.replace(/\s+/g, ' ') : ''};
  }; });
  await tool(page, 'Print').click();
  const printed = await until(() => page.evaluate(() => window.__printed), 3000, 'the print');
  eq([printed.rows, printed.on, /جا/.test(printed.first) && /place/.test(printed.first)], [4, true, true],
     'Print prints a table of the four words, the page itself put away for it');

  // the V key and Esc, and one panel on the right at a time
  await page.keyboard.press('Escape');
  eq(await isOpen(page), false, 'Esc closes it');
  await page.mouse.move(300, 400);
  await page.keyboard.press('v');
  await page.waitForSelector('.vocab-wrap:not([hidden]) .vocab-panel');
  assert(true, 'V opens it');
  await page.click('.later-btn');
  await page.waitForSelector('.lp-wrap:not(.vocab-wrap):not([hidden])');
  eq(await isOpen(page), false, 'opening Review later closes it: one panel on the right at a time');
  await page.click('.vocab-btn');
  await page.waitForSelector('.vocab-wrap:not([hidden]) .vocab-panel');
  eq(await page.evaluate(() => !!document.querySelector('.lp-wrap:not(.vocab-wrap):not([hidden])')), false, 'and the other way round');

  // the cards, one after another, from the reader's own sheet
  await tool(page, 'Make cards one after another').click();
  await page.waitForSelector('#anki:not([hidden]) .lq-strip');
  const sheet = await page.evaluate(() => ({fa: AN.fa.value, tr: AN.tr.value, en: AN.en.value,
                                             strip: document.querySelector('#anki .lq-n').textContent}));
  eq(sheet, {fa: 'جا', tr: 'jā', en: 'place', strip: 'item 1 of 4'},
     'the card sheet opens on the first word, with its own romanisation and meaning, «item 1 of 4»');
  await page.click('#anki .lq-skip');
  await page.waitForFunction(() => /item 2 of 4/.test((document.querySelector('#anki .lq-n') || {}).textContent || ''));
  eq(await page.evaluate(() => AN.fa.value), 'تر', 'Skip opens the next word');
  await page.click('#anki .lq-stop');
  await page.waitForFunction(() => document.getElementById('anki').hidden);
  assert(true, 'Stop ends it');
  await ctx.close();
});

/* ====== b) every mini book ====== */
await scene('b) every mini book, in every language', async () => {
  const ctx = await ctxOf('desk');
  for (const [code, path] of Object.entries(MADE.readers)) {
    const page = await openReader(ctx, path, 'mini-' + code);
    await openList(page);
    const L = LANGS[code];
    const got = await page.evaluate(() => [...document.querySelectorAll('.vocab-wrap .vr')].map(li => ({
      key: li.getAttribute('data-key'), n: +li.querySelector('.vr-n').textContent.slice(1),
      lang: li.querySelector('.vr-w').getAttribute('lang'), dir: li.querySelector('.vr-head').getAttribute('dir'),
      head: li.querySelector('.vr-head').textContent})));
    // the computer's own reading of the same sources, cut by texparse.voc_entries
    const r = await fetch(B + path.replace(/reader\/$/, '__vocab'));
    const j = await r.json();
    const want = new Map();
    for (const c of j.chunks) for (const e of c.entries) want.set(e.key, (want.get(e.key) || 0) + 1);
    eq(got.map(g => [g.key, g.n]), [...want.entries()], `${code}: the list holds the words and counts the computer reads from the sources (${got.length} words)`);
    assert(got.every(g => g.lang === code && g.dir === L.dir), `${code}: every word in its language (${code}) and direction (${L.dir})`);
    if (j.chunks.some(c => c.entries.some(e => e.kind === 'vb' && e.head.length > 2))) {
      const labels = L.vb_labels;
      assert(got.some(g => labels.some(lab => g.head.includes(lab))), `${code}: a verb is drawn with its stems and the language's own labels (${labels.join(', ')})`);
    }
    const d = await drawn(page);
    assert(d.rowHit && d.sideways <= 1, `${code}: the panel is drawn, and nothing in it runs sideways`);
    await page.close();
  }
  await ctx.close();
});

/* ====== c) videos ====== */
await scene('c) a video', async () => {
  const ctx = await ctxOf('desk'), page = await openVideo(ctx, MADE.fa_macro, 'fa-video');
  // at 1280px the player's header is full: the door is the gear's row (and V), and the header stays one row
  // (what the header is without the door at all is the measure: the door must add nothing to it)
  const head = await page.evaluate(() => {
    const b = document.querySelector('.vocab-btn'), hd = document.querySelector('header');
    const h = Math.round(hd.getBoundingClientRect().height), next = b.nextSibling, parent = b.parentNode;
    parent.removeChild(b);
    const without = Math.round(hd.getBoundingClientRect().height);
    parent.insertBefore(b, next);
    return {door: b.getClientRects().length, h, without};
  });
  assert(head.door === 0 && head.h === head.without, `at 1280px the header has no room for the door, and is no taller for it (${head.h}px, ${head.without}px without it)`);
  await page.locator('[data-parseh-gear]').first().click();
  await page.evaluate(() => ParsehGear.mounted().open('interface'));
  const gearRow = page.locator('button.pg-action', {hasText: 'Vocabulary'}).first();
  await gearRow.waitFor({state: 'visible', timeout: 6000});
  await gearRow.click();
  await page.waitForSelector('.vocab-wrap:not([hidden]) .vocab-panel');
  await page.waitForFunction(() => !/reading/.test(document.querySelector('.vocab-wrap .lp-status').textContent));
  assert(true, 'the gear\'s «Vocabulary» opens the list');
  eq(await page.evaluate(() => [...document.querySelectorAll('.vocab-scope .lp-sc')].map(b => b.textContent + (b.getAttribute('aria-pressed') === 'true' ? '*' : ''))),
     ['Whole video*', 'Up to here'], 'it opens on Whole video, beside Up to here');
  eq(await rows(page), [
    {word: 'کتاب', n: '×2', mean: 'book'}, {word: 'دیدن', n: '×3', mean: 'to see · to meet'},
    {word: 'دوست', n: '×1', mean: 'friend'}, {word: 'خوب', n: '×1', mean: 'good'}, {word: 'باز', n: '×1', mean: 'again'}],
     'one row per word: کتاب and كتاب (an Arabic keyboard\'s) are one word, and a verb glossed two ways shows both meanings once');
  const verb = await page.evaluate(() => document.querySelectorAll('.vocab-wrap .vr-head')[1].textContent);
  assert(/pres\./.test(verb) && /بین/.test(verb) && /past/.test(verb), 'the verb is drawn with its stems, as the reader prints it: ' + verb);
  const d = await drawn(page);
  assert(d.right === d.w && d.rowHit, 'the panel is drawn at the right, its first row under its middle');
  const verbRow = page.locator('.vocab-wrap .vr-go').nth(1);
  const at = () => page.evaluate(() => [...document.querySelectorAll('.later-flash')].map(e => [+e.closest('.seg').dataset.i, +e.dataset.j]));
  for (const want of [[0, 1], [1, 1], [3, 1], [0, 1]]) {
    await verbRow.click();
    const got = await until(async () => { const a = await at(); return a.length && a[0][0] === want[0] && a; }, 6000, 'caption ' + want[0]);
    eq(got[0], want, `دیدن: a click lights phrase ${want[1]} of caption ${want[0]}`);
    const t = await until(async () => { const x = await page.evaluate(() => ParsehPlayer.time()); return Math.abs(x - [0, 2, 6, 0][[0, 1, 3, 0].indexOf(want[0])]) < 0.6 ? x + 0.0001 : 0; }, 6000, 'the seek');
    assert(t > 0, 'and the video is at that caption\'s start');
  }
  await shot(page, 'c-video');
  // the cards, from the player's own sheet
  await tool(page, 'Make cards one after another').click();
  await page.waitForSelector('#anki:not([hidden]) .lq-strip');
  eq(await page.evaluate(() => ({fa: document.getElementById('afa').value, tr: document.getElementById('atr').value,
                                 en: document.getElementById('aen').value, strip: document.querySelector('#anki .lq-n').textContent})),
     {fa: 'کتاب', tr: 'ketāb', en: 'book', strip: 'item 1 of 5'}, 'the player\'s card sheet opens on the first word, with its own romanisation and meaning');
  await page.click('#anki .lq-stop');
  await page.waitForFunction(() => document.getElementById('anki').hidden);
  // up to here: the video at 2.5 s holds the first two captions
  await page.evaluate(() => { ParsehPlayer.pause(); ParsehPlayer.seek(2.5); });
  await until(async () => Math.abs(await page.evaluate(() => ParsehPlayer.time()) - 2.5) < 0.3, 6000, 'the video at 2.5 s');
  await tool(page, 'Up to here').click();
  await page.waitForFunction(() => document.querySelectorAll('.vocab-wrap .vr').length === 3);
  eq(await words(page), ['کتاب ×1', 'دیدن ×2', 'دوست ×1'], 'Up to here, at 2.5 s: the words of the first two captions');
  // a window wide enough has the door beside «⚑ later», and the header is still one row
  await page.setViewportSize({width: 1600, height: 800});
  await sleep(200);
  const wide = await page.evaluate(() => {
    const b = document.querySelector('.vocab-btn'), r = b.getBoundingClientRect(), hd = document.querySelector('header');
    const h = Math.round(hd.getBoundingClientRect().height), next = b.nextSibling, parent = b.parentNode;
    parent.removeChild(b);
    const without = Math.round(hd.getBoundingClientRect().height);
    parent.insertBefore(b, next);
    return {beside: document.querySelector('.later-btn').nextElementSibling === b, shown: r.width > 0 && r.top >= 0, h, without};
  });
  assert(wide.beside && wide.shown && wide.h === wide.without,
         `at 1600px the door is drawn beside «⚑ later», and the header is no taller for it (${wide.h}px, ${wide.without}px)`);
  await page.close();

  const ar = await openVideo(ctx, MADE.ar_macro, 'ar-video');
  await ar.mouse.move(300, 500);
  await ar.keyboard.press('v');
  await ar.waitForSelector('.vocab-wrap:not([hidden]) .vocab-panel');
  await tool(ar, 'Whole video').click();
  await ar.waitForFunction(() => document.querySelectorAll('.vocab-wrap .vr').length === 3);
  eq(await rows(ar), [{word: 'خَرَجَ', n: '×1', mean: 'to go out'}, {word: 'ثَعْلَب', n: '×2', mean: 'fox, pl. ثَعَالِب · fox'},
                      {word: 'رَأَى', n: '×1', mean: 'to see'}],
     'Arabic: the fox written with and without its vowels is one word, its two meanings once each');
  const arv = await ar.evaluate(() => document.querySelector('.vocab-wrap .vr-head').textContent);
  assert(/impf\./.test(arv) && /masdar/.test(arv), 'an Arabic verb wears Arabic\'s own labels: ' + arv);
  await ar.close();

  const plain = await openVideo(ctx, MADE.fa_video, 'plain-video');
  await plain.evaluate(() => ParsehPlayer.vocab.panel().open());
  await plain.waitForFunction(() => !/reading/.test((document.querySelector('.vocab-wrap .lp-status') || {}).textContent || 'reading'));
  eq([await plain.evaluate(() => document.querySelectorAll('.vocab-wrap .vr').length),
      /plain text/.test(await plain.locator('.vocab-wrap .lp-status').textContent())], [0, true],
     'a video whose lines are plain text lists nothing, and says why');
  await ctx.close();
});

/* ====== d) a phone ====== */
await scene('d) a phone', async () => {
  const ctx = await ctxOf('phone'), page = await openReader(ctx, FA, 'phone');
  eq(await page.evaluate(() => document.querySelector('.vocab-btn').getClientRects().length), 0, 'the header has no door on a phone');
  await page.locator('[data-parseh-gear]').first().tap();
  await page.evaluate(() => ParsehGear.mounted().open('interface'));
  const row = page.locator('button.pg-action', {hasText: 'Vocabulary'}).first();
  await row.waitFor({state: 'visible', timeout: 6000});
  await row.tap();
  await page.waitForSelector('.vocab-wrap.lp-sheet:not([hidden]) .vocab-panel');
  await page.waitForFunction(() => !/reading/.test(document.querySelector('.vocab-wrap .lp-status').textContent));
  const d = await drawn(page);
  assert(d.bottom === d.h && d.top > 0 && d.left >= 0 && d.right <= d.w && d.rowHit,
         `the gear's «Vocabulary» opens a sheet from the foot of the screen, its first row under its middle (${JSON.stringify(d)})`);
  eq(await page.evaluate(() => !!document.querySelector('.pg-sheet:not([hidden]), .pg-panel:not([hidden])') &&
                               getComputedStyle(document.querySelector('.pg-sheet, .pg-panel')).display !== 'none' &&
                               document.querySelector('.pg-sheet, .pg-panel').getClientRects().length > 0), false, 'the gear\'s sheet went down for it');
  const h = await page.locator('.vocab-wrap .vr-go').first().boundingBox();
  assert(h.height >= 44, 'a word is a finger\'s height (' + Math.round(h.height) + 'px)');
  await shot(page, 'd-sheet');
  await page.locator('.vocab-wrap .vr-go').nth(3).tap();
  const l = await until(async () => { const x = await lit(page); return x.c.length && x; }, 6000, 'the place lit');
  eq([l.c, l.seen, await isOpen(page)], [[3], true, false], 'a tap on سال takes the sheet down and shows its place, lit');
  // the back gesture closes the sheet and leaves the page where it is
  await page.evaluate(() => ParsehVocabReader.panel.open());
  await page.waitForSelector('.vocab-wrap:not([hidden])');
  const url = page.url();
  await page.goBack();
  await until(async () => !(await isOpen(page)), 4000, 'the sheet closed by back');
  eq(page.url(), url, 'the back gesture closes the sheet and stays on the page');
  await page.setViewportSize({width: 320, height: 640});
  await page.evaluate(() => ParsehVocabReader.panel.open());
  await page.waitForSelector('.vocab-wrap:not([hidden])');
  const n = await drawn(page);
  assert(n.sideways <= 1 && n.right <= 320 && n.rowHit, `at 320px nothing in the sheet runs sideways (${n.sideways})`);
  await ctx.close();
});
} catch (e) { failure = e; }

/* ====== e) nothing went wrong ====== */
console.log('e) nothing went wrong');
if (browser) await browser.close();
try { hub.kill('SIGTERM'); } catch (_) {}
await sleep(300);
try {
  eq(errors, [], 'no page threw or logged an error');
  const said = log.join('');
  assert(!/Traceback|Exception/.test(said), 'the server did not print a traceback' + (/Traceback/.test(said) ? ': ' + said.slice(said.indexOf('Traceback'), said.indexOf('Traceback') + 400) : ''));
  eq((await run(PY, ['-c', OWN])).out, configBefore, 'the checkout\'s config/ is as it was');
} catch (e) { failures.push('e) ' + String(e.message || e).split('\n').slice(0, 3).join(' | ')); }
console.log('\n' + passed + ' checks passed');
if (failure) { console.log(failure.stack || failure); }
if (failures.length) { console.log('\nFAILED SCENES:\n  ' + failures.join('\n  ')); }
await Deno.remove(TMP, {recursive: true}).catch(() => {});
Deno.exit(failure || failures.length ? 1 : 0);
