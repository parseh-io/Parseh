// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Linguistic analysis (a0.6.0), against Parseh's REAL handler, page and routes on a
// temporary tree (tests/analysis_harness.py):
//   a) not installed: every choice off, the models' licence said before any button, one Get per item
//   b) Get shows that it is fetching, Stop is there, the row then says it is here, and no choice changed
//   c) a failure is said in a sentence, and asking again works
//   d) a choice is saved, read back after a reload, and refused for nobody let in
//   e) Try it reads a sentence: the table, the phrases, and it keeps no state
//   f) Remove takes one thing away; Remove all of it takes the folder
//   g) 1280 and 390, light and dark: no sideways scroll, nothing wider than the screen
//   h) the Settings hub's card and the licences page
// Run from the computer and as a device let in.  REAL=<folder> instead drives the REAL download and the real
// analyzers into that folder, with sections r only, and leaves them there.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/analysis_door.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const REAL = Deno.env.get('REAL') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(a === b, `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const has = (t, p, m) => assert(t.includes(p), `${m} (wanted ${JSON.stringify(p)})`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}

async function startHarness(args) {
  const proc = new Deno.Command(python, {args: [root + '/tests/analysis_harness.py', ...args], cwd: root,
    stdin: 'piped', stdout: 'piped', stderr: 'piped'}).spawn();
  const log = [];
  (async () => {
    const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); }
  })();
  const lines = [], waiting = [];
  let buf = '';
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  (async () => {
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += value;
      let at;
      while ((at = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, at); buf = buf.slice(at + 1);
        if (waiting.length) waiting.shift()(line); else lines.push(line);
      }
    }
  })();
  const next = () => new Promise(res => { if (lines.length) res(lines.shift()); else waiting.push(res); });
  const ready = await Promise.race([next(), sleep(60000).then(() => 'TIMEOUT')]);
  if (!ready.startsWith('READY ')) throw Error('harness did not start: ' + ready + '\n' + log.join(''));
  const writer = proc.stdin.getWriter();
  const enc = new TextEncoder();
  const send = async cmd => {
    await writer.write(enc.encode(JSON.stringify(cmd) + '\n'));
    const got = await next();
    if (!got.startsWith('OK')) throw Error('harness: ' + got);
    return got.length > 3 ? JSON.parse(got.slice(3)) : null;
  };
  return {proc, info: JSON.parse(ready.slice(6)), send, log,
          stop: async () => { try { proc.kill('SIGTERM'); } catch (_) {} await proc.status; }};
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), args: ['--no-sandbox']});

async function fake(phone) {
  console.log(phone ? '# as another device let in' : '# from the computer');
  const h = await startHarness(phone ? ['--as-phone'] : []);
  const url = `http://127.0.0.1:${h.info.port}`;
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const open = () => page.goto(url + '/settings/analysis/');
  try {
    await open();
    await page.waitForSelector('#an select[data-use="lookup"]');
    const text = () => page.evaluate(() => document.querySelector('main').innerText);
    const get = async (...items) => {
      for (const i of items) await page.check(`[data-tick="${i}"]`);
      await page.click('#an-get');
    };
    const removeIt = async item => { await page.click(`[data-ask="${item}"]`); await page.click(`[data-remove="${item}"]`); };
    // a
    for (const k of ['lookup', 'chunking', 'evidence'])
      eq(await page.$eval(`select[data-use="${k}"]`, e => e.value), 'off', `${k} is off at first`);
    has(await text(), 'CC BY-NC-SA 4.0', 'the models\' licence is on the page');
    has(await text(), 'Straka', 'whose work they are is on the page');
    has(await text(), 'not part of Parseh', 'and that they can be left out');
    eq(await page.$$eval('[data-tick]', b => b.length), 11, 'a tick for Farahidi, Starlang and nine models');
    eq(await page.$eval('#an-get', b => b.disabled), true, 'nothing ticked, nothing to get');
    has(await text(), 'Get a language above', 'Try it says what it waits for');
    assert(!(await page.$('#an-try')), 'and has no button that could only fail');
    await page.check('[data-tick="udpipe:de"]');
    await page.check('[data-tick="farahidi"]');
    has(await page.$eval('#an-get', b => b.textContent), '2 items, about 35 MB', 'the button says what it will fetch, the program with it');
    await page.uncheck('[data-tick="farahidi"]');
    await page.uncheck('[data-tick="udpipe:de"]');
    // b
    await h.send({cmd: 'hold'});
    await get('udpipe:de', 'udpipe:fr');
    await page.waitForSelector('#an-stop');
    assert(await page.$eval('[data-tick="farahidi"]', b => b.disabled), 'the other ticks rest while it fetches');
    assert(await page.$('[role="progressbar"]'), 'a bar says it is going');
    await h.send({cmd: 'release'});
    await page.waitForSelector('[data-ask="udpipe:de"]');
    await page.waitForSelector('[data-ask="udpipe:fr"]');
    await until(async () => !(await page.$('#an-stop')), 'the fetch ends');
    eq(await page.$eval('select[data-use="lookup"]', e => e.value), 'off', 'getting an analyzer turned nothing on');
    has(await text(), 'Can work in German and French', 'each use says where it could work');
    has(await text(), 'also needs its dictionary', 'and what the dictionary panel also needs');
    // c
    await get('udpipe:hi');
    await until(async () => (await text()).includes('a fake failure'), 'the failure is said');
    assert(await page.$('[data-tick="udpipe:hi"]'), 'and it can be asked again');
    // d
    await page.selectOption('select[data-use="lookup"]', 'assist');
    await until(async () => (await h.send({cmd: 'choices'})).lookup === 'assist', 'the choice is written');
    eq((await h.send({cmd: 'choices'})).evidence, 'off', 'another choice did not move with it');
    await until(async () => /also need|Working in/.test(await text()), 'and the page says where it works');
    await page.selectOption('select[data-use="evidence"]', 'on');
    await until(async () => (await text()).includes('Skills for your chatbot') && await page.$('#an a[href="/settings/skills/"]'), 'turning the prompts on points at the skill');
    await page.selectOption('select[data-use="evidence"]', 'off');
    await until(async () => (await h.send({cmd: 'choices'})).evidence === 'off', 'and off again');
    await page.reload();
    await page.waitForSelector('select[data-use="lookup"]');
    eq(await page.$eval('select[data-use="lookup"]', e => e.value), 'assist', 'a reload reads it back');
    // e
    await page.selectOption('#an-lang', 'de');
    await page.fill('#an-text', 'Der alte Mann');
    await page.click('#an-try');
    await page.waitForSelector('#an-out h4');
    const said = await page.$eval('#an-out', e => e.innerText);
    has(said, 'Each word, in this sentence', 'Try it leads with each word');
    assert(await page.$('#an-out .tok .dposhere'), 'and its part of speech, as the chip the panels draw');
    has(said, 'The dictionary, with what fits', 'then the dictionary');
    has(said, 'Phrases', 'and the phrases');
    has(said, 'mann', 'and what was read');
    has(said, 'What a gloss prompt would carry', 'and what a prompt would carry, as it promises');
    eq(await page.$eval('#an-text', e => e.value), 'Der alte Mann', 'the sentence stays in its box');
    // the real lookup call: what `Find` adds, on a word only the analyzer's lemma finds
    const ask = (text, sentence) => h.send({cmd: 'lookup', text, sentence});
    let row = (await ask('Männer', 'Die Männer gehen'))[0];
    eq(row.hits[0].headword, 'mann', 'the call finds the word under its lemma, with Find chosen');
    eq(row.kind, 'analyzer', 'and the row says how');
    await page.selectOption('select[data-use="lookup"]', 'off');
    await until(async () => (await h.send({cmd: 'choices'})).lookup === 'off', 'the choice is written');
    row = (await ask('Männer', 'Die Männer gehen'))[0];
    eq(row.hits.length, 0, 'off: the answer is what it was');
    assert(!row.machine, 'and says nothing of any analyzer');
    // the choice shows what it does
    await page.selectOption('select[data-use="lookup"]', 'show');
    await page.waitForSelector('.preview .dfits');
    has(await page.$eval('.preview', e => e.innerText), 'fits this sentence', 'the panel as the choice makes it is on the page');
    const order = () => page.$$eval('.preview .dhit b', b => b.map(x => x.textContent));
    await until(async () => (await order())[0] === 'ran', 'Show leaves the order');
    await page.selectOption('select[data-use="lookup"]', 'assist');
    await until(async () => (await order())[0] === 'run', 'and the fuller choice puts it first');
    await page.selectOption('select[data-use="lookup"]', 'off');
    await until(async () => !(await page.$('.preview')), 'off shows none');
    // the keyboard stays where it was through a redraw, and a sentence half typed stays
    await page.focus('#an-text');
    await page.keyboard.type('xy');
    await h.send({cmd: 'hold'});
    await page.check('[data-tick="udpipe:es"]');
    await page.click('#an-get');
    await page.waitForSelector('#an-stop');
    await page.focus('#an-text');
    await sleep(1800);
    eq(await page.evaluate(() => document.activeElement.id), 'an-text', 'a poll leaves the keyboard in the box');
    has(await page.$eval('#an-text', e => e.value), 'xy', 'and what was typed');
    await h.send({cmd: 'release'});
    await page.waitForSelector('[data-ask="udpipe:es"]');
    // f
    await page.click('[data-ask="udpipe:de"]');
    has(await text(), 'Remove it?', 'Remove asks first');
    await page.click('[data-cancel]');
    assert(await page.$('[data-ask="udpipe:de"]'), 'Keep it keeps it');
    await removeIt('udpipe:de');
    await page.waitForSelector('[data-tick="udpipe:de"]');
    await page.click('#an > details summary');
    await page.click('[data-ask="all"]');
    await page.click('[data-remove="all"]');
    await page.waitForSelector('[data-tick="udpipe:es"]');
    assert(!(await Deno.stat(h.info.folder).catch(() => null)), 'Remove all of it takes the folder');
    // a choice left on with nothing to work with is said so
    await page.selectOption('select[data-use="chunking"]', 'assist');
    await until(async () => (await text()).includes('Nothing here can do this yet'), 'a choice with nothing behind it says so');
    await page.selectOption('select[data-use="chunking"]', 'off');
    await until(async () => (await h.send({cmd: 'choices'})).chunking === 'off', 'and off');
    // g
    for (const w of [1280, 390]) for (const scheme of ['light', 'dark']) {
      await page.emulateMedia({colorScheme: scheme});
      await page.setViewportSize({width: w, height: 800});
      await page.reload();
      await page.waitForSelector('#an select');
      const wide = await page.evaluate(() => ({doc: document.documentElement.scrollWidth, win: innerWidth,
        over: [...document.querySelectorAll('main *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.scroll')).length}));
      assert(wide.doc <= wide.win, `${w} ${scheme}: no sideways scroll`);
      eq(wide.over, 0, `${w} ${scheme}: nothing wider than the screen`);
    }
    await page.setViewportSize({width: 1280, height: 900});
    // h
    await page.goto(url + '/settings/');
    has(await page.$eval('a[href="/settings/analysis/"]', e => e.innerText), 'Linguistic analysis', 'the hub has the door');
    await page.goto(url + '/licences/');
    has(await page.evaluate(() => document.body.innerText), 'linguistic analyzers', 'the licences page names them');
    eq(errors.join(' | '), '', 'no script error');
  } finally {
    await context.close();
    await h.stop();
  }
}

async function real(folder) {
  console.log('# the real download, into', folder);
  const h = await startHarness(['--real', folder]);
  const url = `http://127.0.0.1:${h.info.port}`;
  const context = await browser.newContext({viewport: {width: 390, height: 800}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  try {
    await page.goto(url + '/settings/analysis/');
    await page.waitForSelector('#an select[data-use="lookup"]');
    const take = async (item, ms) => {
      if (await page.$(`[data-ask="${item}"]`)) { console.log('  already here', item); return; }
      const t0 = Date.now();
      await page.check(`[data-tick="${item}"]`);
      await page.click('#an-get');
      await page.waitForSelector(`[data-ask="${item}"]`, {timeout: ms});
      console.log(`  ok ${item} in ${Math.round((Date.now() - t0) / 1000)}s`);
    };
    await take("farahidi", 300000);
    await take('udpipe:de', 300000);
    await take('udpipe:ar', 300000);
    await take('udpipe:tr', 300000);
    await take('starlang', 590000);
    for (const [code, sentence, want] of [['de', 'Der alte Mann steht langsam von seinem Stuhl auf.', 'verb'],
                                          ['ar', 'ذهب الولد إلى المدرسة', 'Farahidi'],
                                          ['tr', 'Evlerimizden geldim.', 'Starlang']]) {
      await page.waitForSelector('#an-try:not([disabled])');
      await page.selectOption('#an-lang', code);
      await page.fill('#an-text', sentence);
      await page.click('#an-try');
      await page.waitForFunction(w => document.querySelector('#an-out').innerText.includes(w), want, {timeout: 120000});
      passed++;
      console.log('  ok Try it', code, 'said', want);
    }
    const left = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    assert(left, 'phone width: no sideways scroll with the results on the page');
    eq(errors.join(' | '), '', 'no script error');
  } finally {
    await context.close();
    await h.stop();
  }
}

try {
  if (REAL) await real(REAL);
  else { await fake(false); await fake(true); }
  console.log(`analysis_door: ${passed} checks passed`);
} catch (e) {
  console.error(e);
  Deno.exitCode = 1;
} finally {
  await browser.close();
}
