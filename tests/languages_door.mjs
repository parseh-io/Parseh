// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Languages (a0.6.1), against Parseh's REAL handler, page and routes on a temporary
// tree (tests/languages_harness.py: the language table, the language files and the content folders it may write
// are copies or temporary, never the checkout's):
//   a) every language of the registry has a card, its features opened on a click, Catalan's among them
//   b) adding a language from the form: a refusal is said in newlang.py's words; a good one is written, is in the
//      list at once, marked "added here", its chunking rules copied from the related language
//   c) its conventions, written with a chatbot: the prompt carries the related language's file; an answer
//      without the seven sections is refused in a sentence; one with them is written, and the card says so
//   d) a device let in sees every card and no button that could only be refused (the server refuses as well)
//   e) the Settings hub has the door; 1280 and 390, light and dark: no sideways scroll
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/languages_door.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
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
  const proc = new Deno.Command(python, {args: [root + '/tests/languages_harness.py', ...args], cwd: root,
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

const REG = JSON.parse(await Deno.readTextFile(root + '/lib/languages.json'));
const SHIPPED = REG._shipped;
// conventions a chatbot might answer with: the seven sections, an inner fence, no TODO
const CONVENTIONS = ['# Basque — the annotation conventions', '', 'Written for the test.', '',
  ...['The text field', 'Reading', 'Transliteration', 'Vocabulary', 'Never gloss', 'Chunking'].flatMap(s =>
    ['## ' + s, '', 'What holds for Basque here.', '']),
  '## Example', '', '```json', '{"fa": "kaixo", "en": "hello"}', '```', ''].join('\n');

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), args: ['--no-sandbox']});

async function run(phone) {
  console.log(phone ? '# as another device let in' : '# from the computer');
  const h = await startHarness(phone ? ['--as-phone'] : []);
  const url = `http://127.0.0.1:${h.info.port}`;
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  try {
    await page.goto(url + '/settings/languages/');
    await page.waitForSelector('details.lang');
    // a
    const codes = await page.$$eval('details.lang', ds => ds.map(d => d.getAttribute('data-code')));
    eq(codes.join(' '), SHIPPED.join(' '), 'a card for every language of the registry, in its order');
    await page.click('details.lang[data-code="ca"] > summary');
    const ca = await page.$eval('details.lang[data-code="ca"]', d => d.innerText);
    has(ca, 'Annotation conventions', 'Catalan\'s card opens on its features');
    has(ca, 'UDPipe', 'and says which analyzer reads it');
    assert(!(await page.$('details.lang[data-code="ca"] button[data-write]')),
           'Parseh\'s own language offers no prose to write: an update would replace it');
    if (phone) {
      // d
      eq(await page.$eval('[data-add] button[type=submit]', b => b.disabled), true, 'a device let in cannot add a language');
      has(await page.$eval('#lg-add', e => e.innerText), 'on the computer Parseh runs on only', 'and is told why');
      const r = await page.evaluate(() => fetch('/settings/api/languages/add', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code: 'eu', name: 'Basque', native: 'euskara'})})
        .then(r => r.status));
      eq(r, 403, 'and the server refuses it as well');
      eq((await h.send({what: 'files', code: 'eu'})).row, false, 'nothing was written');
    } else {
      // b
      const fill = async (code, name, native) => {
        await page.fill('[data-add] input[name=code]', code);
        await page.fill('[data-add] input[name=name]', name);
        await page.fill('[data-add] input[name=native]', native);
      };
      await fill('it', 'Basque', 'euskara');
      await page.click('[data-add] button[type=submit]');
      const refused = await until(() => page.$eval('[data-addout] .say', e => e.innerText.trim()), 'a refusal');
      has(refused, 'already', 'a code that is taken is refused in newlang.py\'s own words');
      await fill('eu', 'Basque', 'euskara');
      await page.selectOption('[data-add] select[name=like]', 'es');
      await page.fill('[data-add] input[name=iso3]', 'eus');
      await page.click('[data-add] button[type=submit]');
      await until(() => page.$('details.lang[data-code="eu"]'), 'the new card');
      const files = await h.send({what: 'files', code: 'eu'});
      assert(files.row && files.tex && files.md, 'its row, its .tex and its conventions\' template are written');
      assert(files.chunk, 'its chunking rules are copied from the related language');
      eq(files.checkout, false, 'and nothing of it reached the checkout');
      has(await page.$eval('[data-addout]', e => e.innerText), 'Still yours to write', 'newlang.py\'s list of what is left is shown');
      const eu = await page.$eval('details.lang[data-code="eu"]', d => d.innerText);
      has(eu, 'added here', 'the card says the language is this computer\'s');
      has(eu, 'still needed: Annotation conventions', 'and that its conventions are still the template');
      // c
      await page.click('details.lang[data-code="eu"] li[data-feature="conventions"] button[data-write]');
      const pane = 'details.lang[data-code="eu"] li[data-feature="conventions"] [data-pane]';
      await until(() => page.$eval(pane + ' select[data-like]', s => s.value === 'es'), 'the related language chosen');
      const prompt = await page.evaluate(() => fetch('/settings/api/languages/prompt', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code: 'eu', piece: 'conventions', like: 'es'})})
        .then(r => r.json()));
      has(prompt.prompt, 'Spanish\'s, as the model', 'the prompt carries the related language\'s conventions');
      has(prompt.prompt, 'Basque', 'and names the new one');
      await page.click(pane + ' [data-copy]');
      await until(() => page.$eval(pane + ' [data-cmsg]', e => /copied|copy it/.test(e.textContent)), 'the copy is said');
      await page.fill(pane + ' textarea[data-answer]', '````\n# Basque\n\n## The text field\nonly this\n````');
      await page.click(pane + ' [data-take]');
      const no = await until(() => page.$eval(pane + ' [data-tmsg]', e => e.classList.contains('bad') && e.textContent), 'a refusal');
      has(no, 'lack these sections', 'an answer without the seven sections is refused in a sentence');
      await page.fill(pane + ' textarea[data-answer]', 'Here they are:\n````markdown\n' + CONVENTIONS + '````\nHope it helps!');
      await page.click(pane + ' [data-take]');
      await until(() => page.$eval('#lg-say', e => e.innerText.includes('Written')), 'written');
      const feats = await h.send({what: 'features', code: 'eu'});
      eq(feats.find(f => f.key === 'conventions').state, 'have', 'the conventions are now the language\'s own');
      const eu2 = await page.$eval('details.lang[data-code="eu"]', d => d.innerText);
      assert(!eu2.includes('still needed: Annotation conventions'), 'and the card no longer asks for them');
    }
    // e
    await page.goto(url + '/settings/');
    has(await page.$eval('a[href="/settings/languages/"]', e => e.innerText), 'Languages', 'the hub has the door');
    for (const [w, scheme] of [[1280, 'light'], [390, 'dark']]) {
      await page.setViewportSize({width: w, height: 800});
      await page.emulateMedia({colorScheme: scheme});
      await page.goto(url + '/settings/languages/');
      await page.waitForSelector('details.lang');
      await page.click('details.lang[data-code="ar"] > summary');
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert(over <= 0, `${w} px, ${scheme}: no sideways scroll (${over})`);
    }
    eq(errors.join(' | '), '', 'no error on the page');
  } finally {
    await context.close();
    await h.stop();
  }
}

try {
  await run(false);
  await run(true);
} finally {
  await browser.close();
}
console.log(`\n${passed} passed`);
