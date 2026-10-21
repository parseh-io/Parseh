// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Pictograms (ARASAAC) (TO-DO §8.40, W9, a0.4.2), against Parseh's REAL
// handler, page and routes on a temporary arasaac/ tree, with the two hosts the pictograms come from
// stood in for (tests/arasaac_harness.py, tests/arasaac_fake.py):
//   a) not installed: the licence said first (the credit in ARASAAC's words, not for sale, shared alike,
//      the terms and the licence linked), then the languages -- English ticked, what ARASAAC has in each,
//      Japanese and Hindi said not to be offered -- the size of the pictures, and what it all costs BEFORE
//      the button; no lock and no dead button; the hosts named
//   b) the size line follows a tick and a size, from the server's plan
//   c) fetching: Get it -> a bar that moves (the word list, then the pictures by number), Stop, the
//      controls shut while it runs, then Installed with its counts, Update and Remove…
//   d) Stop keeps the promise: stopped, not failed, kept, and Carry on fetches only the rest
//   e) a host that fails is said in a sentence and Try again works
//   f) installed: Remove… asks first; Keep it keeps; one language's words go and the pictures stay;
//      everything goes and the page is as it was
//   g) adding a language fetches its list and no picture; a change of size asks first and replaces them all
//   h) Update fetches only what ARASAAC changed, asking before it fetches
//   i) a folder made by another Parseh is said so, with one way out
//   j) 1280 and 390, light, dark and sepia: never a sideways scroll, targets big enough, nothing wider
//      than the screen
//   k) the Settings hub's card and the licences page's entry
//   l) one failed poll (a dropped connection, a 502) does not end the polling
//   m) the keyboard stays on the control it was on, through every redraw
//   n) a press whose request never arrives says so, and its button comes back
// Run once from the computer and once as a device that has been let in over the Wi-Fi: BOTH are fully
// working (no lock anywhere on this door, as on Speech to text's).
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/arasaac_door.mjs
//   ARASAAC_DOOR_WHO=computer (or phone) runs one; SECTIONS=jkl runs only those; SHOTS=<dir> saves screenshots.
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
const who = (Deno.env.get('ARASAAC_DOOR_WHO') || 'computer,phone').split(',');
const only = (Deno.env.get('SECTIONS') || '').toLowerCase();
let passed = 0;
const failures = [];
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(a === b, `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const has = (text, part, m) => assert(text.includes(part), `${m} (wanted ${JSON.stringify(part)} in ${JSON.stringify(text.slice(0, 400))})`);
const lacks = (text, part, m) => { if (text.includes(part)) throw Error(`FAIL: ${m} (found ${JSON.stringify(part)})`); passed++; console.log('  ok', m); };
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

async function startHarness(phone) {
  const args = [root + '/tests/arasaac_harness.py'];
  if (phone) args.push('--as-phone');
  const proc = new Deno.Command(python, {args, cwd: root, stdin: 'piped', stdout: 'piped', stderr: 'piped'}).spawn();
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
  const info = JSON.parse(ready.slice(6));
  const writer = proc.stdin.getWriter();
  const enc = new TextEncoder();
  const send = async cmd => {
    await writer.write(enc.encode(JSON.stringify(cmd) + '\n'));
    const got = await next();
    if (!got.startsWith('OK')) throw Error('harness: ' + got);
    return got.length > 3 ? JSON.parse(got.slice(3)) : null;
  };
  return {proc, info, send, log, stop: async () => { try { proc.kill('SIGTERM'); } catch (_) {} await proc.status; }};
}

const THEMES = ['light', 'dark', 'sepia'];

async function suite(phone) {
  const name = phone ? 'a device let in over the Wi-Fi' : 'the computer';
  console.log(`\n== ${name} ==`);
  const h = await startHarness(phone);
  const origin = `http://127.0.0.1:${h.info.port}`;
  const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
    // (a 502 is the one a test makes itself: section l answers a poll with one, as a proxy would)
    page.on('response', r => { if (r.status() >= 400 && r.status() !== 502 && !/favicon/.test(r.url())) errors.push(`http ${r.status()} ${r.url()}`); });
    const tag = phone ? 'phone' : 'computer';
    const section = async (title, fn) => {
      if (only && !only.includes(title[0])) return;
      console.log(title);
      try { await fn(); } catch (e) { failures.push(`${name}: ${title}: ${e.message}`); console.log('  ' + e.message); }
    };
    const shot = async n => { if (SHOTS) await page.screenshot({path: `${SHOTS}/arasaac-${tag}-${n}.png`, fullPage: true}); };
    const world = async (n, extra) => { await h.send(Object.assign({cmd: 'world', n: n || 40}, extra || {})); };
    const door = async () => {
      await page.goto(origin + '/settings/arasaac/');
      await page.waitForSelector('#ar .lang');
    };
    const text = async sel => (await page.locator(sel).first().innerText()).replace(/\s+/g, ' ');
    const main = async () => (await page.locator('#ar').innerText()).replace(/\s+/g, ' ');
    const state = () => page.evaluate(() => fetch('/settings/api/arasaac/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}).then(r => r.json()));
    const api = async (what, body) => page.evaluate(([w, b]) => fetch('/settings/api/arasaac/' + w, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b || {})}).then(async r => Object.assign(await r.json(), {status: r.status})), [what, body || {}]);
    const stats = () => h.send({cmd: 'stats'});
    const installed = async () => { await until(async () => (await text('[data-row="whole"]')).includes('Installed'), 'the pictograms are installed', 40000); };

    await section('a) not installed', async () => {
      await world(40);
      await door();
      eq(await page.locator('h1.idx').textContent(), 'pictograms (ARASAAC)', 'the page says what it is');
      const st = await state();
      eq(st.where, phone ? 'lan' : 'self', 'and knows where it is asked from');
      eq(JSON.stringify(st.may), JSON.stringify({'arasaac.get': true, 'arasaac.remove': true, 'arasaac.stop': true}),
         'every button is allowed, from here too');
      has(await text('.whomay'), 'any device let in', "the door's pill says who may");
      has(await text('.whomay'), 'only ARASAAC’s own word lists and pictures can be fetched', 'and why that is safe');
      eq(await page.locator('[data-lock]').count(), 0, 'no lock line');
      eq(await page.locator('#ar button:disabled').count(), 0, 'no dead button');
      // the licence comes first, in ARASAAC's own words, before any choice or button
      const body = await main();
      const at = s => body.toLowerCase().indexOf(s.toLowerCase());     // (a heading is drawn in capitals)
      assert(at('Whose pictures these are') >= 0 && at('Whose pictures these are') < at('What to fetch'), 'whose pictures these are comes before what to fetch');
      has(body, 'The pictographic symbols used are the property of the Government of Aragón and have been created by Sergio Palao for ARASAAC (http://www.arasaac.org), that distributes them under Creative Commons License BY-NC-SA.',
          'the credit is ARASAAC’s sentence, word for word');
      has(body, 'Not for sale.', 'non-commercial is said plainly');
      has(body, 'Shared on the same terms.', 'and share-alike');
      has(body, 'a document that holds them is for sharing as it is, credit and all, and never for selling', 'and what it means for a document');
      const links = await page.locator('#ar .about a').evaluateAll(els => els.map(e => [e.textContent, e.getAttribute('href'), e.getAttribute('rel')]));
      assert(links.some(l => l[1] === 'https://arasaac.org/terms-of-use' && l[2] === 'noopener'), 'the terms are linked, opened apart');
      assert(links.some(l => l[1] === 'https://creativecommons.org/licenses/by-nc-sa/4.0/'), 'and the licence');
      assert(links.some(l => /studio\/pictograms/.test(l[1])), 'and the guide');
      // the languages: English first and ticked, what ARASAAC has in each, two said not to be offered
      const langs = await page.locator('#ar .lang').evaluateAll(els => els.map(e => ({code: e.dataset.lang, no: e.classList.contains('no'),
        checked: !!(e.querySelector('input') || {}).checked, text: e.innerText.replace(/\s+/g, ' ')})));
      eq(langs[0].code, 'en', 'English is first');
      assert(langs[0].checked, 'and ticked');
      eq(langs.filter(l => l.checked).length, 1, 'and the only one ticked');
      for (const code of ['fa', 'ar', 'it', 'fr', 'de', 'tr', 'es', 'zh'])
        assert(langs.some(l => l.code === code && !l.no), `${code} is offered`);
      const ja = langs.find(l => l.code === 'ja'), hi = langs.find(l => l.code === 'hi');
      assert(ja.no && ja.text.includes('ARASAAC has no words in this language'), 'Japanese is said not to be offered, and why');
      assert(hi.no && hi.text.includes('ARASAAC has almost no words in this language yet (1)'), 'Hindi too: it has one word');
      has(langs[0].text, '26,578 words, naming every pictogram', 'English says how many words, and that they name every pictogram');
      has(langs[0].text, '7.6 MB to fetch', 'and what its list costs');
      has(langs.find(l => l.code === 'tr').text, '2,783 words, naming 2,656 of 13,829 pictograms', 'Turkish is honest about how few it has');
      // the size of the pictures, and the plan before the button
      eq(await page.locator('input[name=px]').count(), 2, 'two sizes');
      eq(await page.locator('input[name=px]:checked').getAttribute('value'), '300', '300 pixels is the one to start with');
      const plan = await text('.plan');
      has(plan, '166 MB', 'what it all costs is said before the button (7.6 MB of words and 159 MB of pictures)');
      has(plan, '13,829 pictures at 300 pixels', 'how many pictures');
      has(plan, 'takes about 12 minutes, one picture at a time', 'how long it takes');
      has(plan, 'kept as about 161 MB', 'and what it keeps');
      eq(await page.locator('#ar [data-get]').count(), 1, 'one Get it');
      eq((await page.locator('#ar [data-get]').getAttribute('aria-label')), 'Get it: the pictograms', 'named by the words it shows');
      eq(await page.locator('#ar [data-update], #ar [data-remove-all]').count(), 0, 'no Update and no Remove before there is anything');
      has(await text('main .foot'), 'api.arasaac.org', 'the hosts are named');
      has(await text('main .foot'), 'static.arasaac.org', 'both of them');
      eq(await text('.band .n'), '0 MB', 'nothing kept yet');
      await shot('a-absent');
    });

    await section('b) the plan follows a tick and a size', async () => {
      await door();
      await page.check('#lang-es');
      await until(async () => (await text('.plan')).includes('174 MB'), 'Spanish adds its 8.2 MB list');
      has(await text('.plan'), '16 MB of word lists', 'the lists, summed (7.6 and 8.2)');
      await page.uncheck('#lang-es');
      await page.check('input[name=px][value="500"]');
      await until(async () => (await text('.plan')).includes('321 MB') || (await text('.plan')).includes('329 MB'), '500 pixels costs about twice as much');
      has(await text('.plan'), '13,829 pictures at 500 pixels', 'and says it is 500');
      has(await text('.plan'), 'takes about 12 minutes', 'the same time: it is the number of pictures that counts');
      await page.check('input[name=px][value="300"]');
      await until(async () => (await text('.plan')).includes('166 MB'), 'back to 300');
      await page.uncheck('#lang-en');
      await until(async () => (await text('.plan')).includes('159 MB'), 'with no list ticked only the pictures remain');
      eq(await page.locator('#ar [data-get]').isDisabled(), true, 'and with nothing ticked there is nothing to get');
      await page.check('#lang-en');
    });

    await section('c) fetching', async () => {
      await world(60, {delay: 0.03});
      await door();
      await page.click('#ar [data-get]');
      await page.waitForSelector('[data-row="job"] [role=progressbar]');
      await until(async () => (await text('[data-row="job"]')).includes('pictures'), 'the list is in and the pictures begin');
      const bar = () => page.locator('[data-row="job"] [role=progressbar]').getAttribute('aria-valuenow');
      const first = Number(await bar());
      await until(async () => Number(await bar()) > first + 4, 'the bar moves');
      assert(true, `the bar moved from ${first}% on`);
      has(await text('[data-row="job"]'), 'Fetching the pictograms', 'the row says what it is doing');
      assert(/\d+ of 60 pictures/.test(await text('[data-row="job"]')), 'in pictures, out of the number there are');
      eq(await page.locator('[data-row="job"] [data-stop]').count(), 1, 'with a Stop');
      eq(await page.locator('#ar [data-get]').count(), 0, 'and no second Get it');
      eq(await page.locator('#ar input:disabled').count() > 0, true, 'the choices are shut while it runs');
      eq(await page.locator('#ar input:not(:disabled)').count(), 0, 'all of them');
      await shot('c-fetching');
      await installed();
      has(await text('[data-row="whole"]'), '60 of 60 pictures · 300 pixels', 'the counts, from what is on the disk');
      eq(await page.locator('#ar [data-update]').count(), 1, 'Update is offered');
      eq(await page.locator('#ar [data-remove-all]').count(), 1, 'and Remove…');
      eq(await page.locator('#ar [data-get]').count(), 0, 'and no Get it');
      has(await main(), 'Fetched ', 'it says when');
      eq(await page.locator('#ar .lang[data-lang=en] [data-remove-lang]').count(), 1, 'the English words have a Remove…');
      assert((await page.locator('#lang-fr').count()) === 1, 'a language not here can still be ticked');
      const st = await state();
      eq(st.arasaac.state, 'installed', 'the server agrees');
      eq(st.arasaac.files, 60, 'with the files');
      await shot('c-installed');
      const s = await stats();
      eq(s.lists, 1, 'one list was asked for');
      eq(s.pictures, 60, 'and each picture once');
      eq(s.connections, 2, 'on one connection for the pictures');
    });

    await section('d) stop', async () => {
      await world(80, {delay: 0.05});
      await door();
      await page.click('#ar [data-get]');
      await until(async () => /\b[1-9]\d* of 80 pictures/.test(await text('[data-row="job"]')), 'some pictures are in');
      await page.click('[data-row="job"] [data-stop]');
      await until(async () => (await main()).includes('You stopped it'), 'it says it was stopped');
      has(await main(), 'what came is kept, and pressing it again carries on from there', 'and what that means');
      lacks(await main(), 'The last try stopped', 'it is not called a failure');
      has(await text('[data-row="whole"]'), 'Part of it is here', 'the state says part of it is here');
      assert((await stats()).files > 0, 'files are on the disk');
      const kept = (await stats()).files;
      eq(await page.locator('#ar [data-get]').textContent(), 'Carry on', 'the button says Carry on');
      await h.send({cmd: 'slow', seconds: 0});
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('e) a host that fails', async () => {
      await world(30);
      await h.send({cmd: 'fail', pattern: '/pictograms/\\d+/', how: '500', times: 999});
      await door();
      await page.click('#ar [data-get]');
      await until(async () => (await main()).includes('The last try stopped'), 'the failure is said', 30000);
      has(await main(), 'after 4 tries', 'in a sentence that says what happened');
      has(await main(), 'press it again to carry on', 'and what to do');
      eq(await page.locator('#ar [data-get]').textContent(), 'Try again', 'the button says Try again');
      lacks(await main(), 'Traceback', 'never a traceback');
      await h.send({cmd: 'unfail'});
      await page.click('#ar [data-get]');
      await installed();
      eq((await state()).arasaac.pending, 0, 'and Try again finished it');
    });

    await section('f) removing', async () => {
      await world(20);
      await h.send({cmd: 'build', locales: ['en', 'fr'], resolution: 300});
      await door();
      await page.click('#ar .lang[data-lang=fr] [data-remove-lang]');
      has(await text('#ar .lang[data-lang=fr] .ask'), 'Remove the French words?', 'asks first');
      has(await text('#ar .lang[data-lang=fr] .ask'), 'the pictures stay', 'and says what stays');
      await page.click('#ar .ask [data-cancel]');
      eq(await page.locator('#ar .ask').count(), 0, 'Keep it keeps it');
      eq((await state()).arasaac.locales.fr !== undefined, true, 'the French words are still there');
      await page.click('#ar .lang[data-lang=fr] [data-remove-lang]');
      await page.click('#ar .ask [data-yes-lang]');
      await until(async () => (await state()).arasaac.locales.fr === undefined, 'the French words are gone');
      eq((await state()).arasaac.files, 20, 'the pictures are not');
      eq(await page.locator('#lang-fr').count(), 1, 'French can be ticked again');
      await page.click('#ar [data-remove-all]');
      has(await text('#ar .ask'), 'Remove all the pictograms?', 'removing everything asks first');
      await page.click('#ar .ask [data-cancel]');
      eq((await state()).arasaac.state, 'installed', 'Keep it keeps it');
      await page.click('#ar [data-remove-all]');
      await page.click('#ar .ask [data-yes-all]');
      await until(async () => (await state()).arasaac.state === 'absent', 'everything is gone');
      await until(async () => (await page.locator('#ar [data-get]').count()) === 1, 'and the page is as it was: Get it');
      eq(await text('.band .n'), '0 MB', 'nothing kept');
    });

    await section('g) adding a language, and changing the size', async () => {
      await world(20);
      await h.send({cmd: 'build', locales: ['en'], resolution: 300});
      await h.send({cmd: 'reset_stats'});
      await door();
      await page.check('#lang-fr');
      eq((await page.locator('#ar [data-get]').textContent()).trim(), 'Add the language ticked', 'the button says what it fetches');
      await until(async () => (await text('.plan')).includes('6.8 MB to fetch'), 'the plan follows the tick');
      has(await text('.plan'), '6.8 MB to fetch — 6.8 MB of word lists', 'and what that costs: the list, and no pictures');
      lacks(await text('.plan'), 'pictures at', 'no pictures');
      eq(await page.locator('#ar [data-update]').count(), 1, 'Update is still its own button');
      await page.click('#ar [data-get]');
      await until(async () => (await state()).arasaac.locales.fr !== undefined, 'the French words come');
      await until(async () => (await text('#ar .lang[data-lang=fr]')).includes('installed'), 'and the row says installed');
      const s1 = await stats();
      eq(s1.pictures, 0, 'and no picture was asked for again');
      eq(s1.lists, 1, 'one list');
      // THE ROW SAYS "installed" AS SOON AS THE WORDS ARE THERE, but the page draws Remove… only when the job is over, and it
      // learns that from its next poll (once a second): wait for the buttons, not for the row
      await until(async () => (await page.locator('#ar [data-remove-lang]').count()) === 2, 'the job ends and both languages can be removed');
      eq(await page.locator('#ar [data-remove-lang]').count(), 2, 'both languages can be removed now');
      // the size: a question of its own, because it replaces every picture
      await page.check('input[name=px][value="500"]');
      await until(async () => (await page.locator('#ar [data-resize]').count()) === 1, 'the size changes the button');
      eq((await page.locator('#ar [data-resize]').textContent()).trim(), 'Fetch again at 500 pixels…', 'it says what it does');
      eq(await page.locator('#ar [data-update]').count(), 0, 'and Update is not offered beside a change of size');
      await until(async () => (await text('.plan')).includes('The pictures that are here are replaced'), 'the plan says they are replaced');
      has(await text('.plan'), '20 pictures at 500 pixels', 'all of them, at the new size (the twenty there are)');
      await page.click('#ar [data-resize]');
      has(await text('#ar .ask'), 'Fetch every picture again at 500 pixels?', 'it asks first');
      await page.click('#ar .ask [data-cancel]');
      eq((await state()).arasaac.resolution, 300, 'Keep what is here keeps it');
      await page.click('#ar [data-resize]');
      await h.send({cmd: 'reset_stats'});
      await page.click('#ar .ask [data-yes-size]');
      await until(async () => (await state()).arasaac.resolution === 500 && !(await state()).arasaac.job.running, 'every picture is fetched again at 500', 40000);
      const s2 = await stats();
      eq(s2.pictures, 20, 'each picture was asked for again');
      eq(s2.lists, 0, 'and no list');
      eq(s2.files, 20, 'none of the 300 pixel ones is left beside them');
      has(await text('[data-row="whole"]'), '500 pixels', 'the page says what size they are');
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('h) update', async () => {
      await world(30);
      await h.send({cmd: 'build', locales: ['en'], resolution: 300});
      await h.send({cmd: 'change', ids: [1], picture: false});
      await h.send({cmd: 'change', ids: [2], picture: true});
      await h.send({cmd: 'change', add: [99999], drop: [3]});
      await h.send({cmd: 'reset_stats'});
      // THREE PICTURES ARE A FEW MILLISECONDS AT THE FAKE HOST'S SPEED, and the page asks how things stand once a second:
      // so they are held at the host until the count has been seen (slowed by the clock instead, 0.6 s each, the page's
      // look could fall before the pictures began or after they were over -- it did, on a loaded computer)
      await h.send({cmd: 'hold'});
      await door();
      eq(await page.locator('#ar [data-update]').count(), 1, 'Update is offered');
      await page.click('#ar [data-update]');
      await page.waitForSelector('[data-row="job"]');
      has(await text('[data-row="job"]'), 'Looking for what has changed', 'the row says what it is doing');
      await until(async () => /\b\d of 3 pictures\b/.test(await text('[data-row="job"]')), 'the row counts the pictures');
      assert(true, 'and counts what it has to fetch: three, not all of them');
      await h.send({cmd: 'release'});
      await until(async () => !(await state()).arasaac.job.running, 'it is over', 30000);
      const s = await stats();
      eq(s.lists, 1, 'the list was asked for once');
      eq(s.pictures, 3, 'and only the pictures a record named: the two that moved and the new one');
      eq(s.conditional, 2, 'the two that were here were asked for with If-Modified-Since');
      eq(s.files, 30, 'one new, one gone');
      eq((await state()).arasaac.pictograms, 30, 'and the records say so');
      eq((await state()).arasaac.job.error, '', 'with no error');
      // (if it is not, both sides are described -- what the folder says it is, and what the row says: a timeout alone does not
      // tell a page that did not look again from a folder that is not whole)
      await until(async () => (await text('[data-row="whole"]')).includes('Installed'), 'and it is installed')
        .catch(async e => {
          const st = (await state()).arasaac;
          throw Error(e.message + ' -- the folder: ' + JSON.stringify({state: st.state, pending: st.pending, missing: st.missing, files: st.files,
                      pictograms: st.pictograms, job: st.job}) + '; the row: ' + (await text('[data-row="whole"]')));
        });
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('i) a folder of another shape', async () => {
      await world(10);
      await h.send({cmd: 'other_format'});
      await door();
      has(await main(), 'Made by another Parseh', 'it says so');
      has(await main(), 'press Get it to make it again, or remove it', 'and the two ways out');
      eq(await page.locator('#ar [data-get]').count(), 1, 'Get it');
      eq(await page.locator('#ar [data-remove-all]').count(), 1, 'and Remove…');
    });

    await section('j) 1280 and 390, three themes', async () => {
      await world(12);
      await h.send({cmd: 'build', locales: ['en'], resolution: 300});
      for (const [w, hgt] of [[1280, 900], [390, 844]]) {
        await page.setViewportSize({width: w, height: hgt});
        for (const theme of THEMES) {
          await page.addInitScript(t => { try { localStorage.setItem('parseh.theme', t); } catch (e) {} }, theme);
          await door();
          await page.evaluate(t => { document.documentElement.setAttribute('data-theme', t); }, theme);
          const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
          assert(wide <= 1, `${w}px ${theme}: no sideways scroll (${wide})`);
          const over = await page.evaluate(() => Array.from(document.querySelectorAll('#ar *')).filter(e => {
            const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
          }).map(e => e.tagName + '.' + e.className).slice(0, 5));
          eq(over.length, 0, `${w}px ${theme}: nothing wider than the screen ${over.join()}`);
          if (w === 390) {
            // a box or a dot is pressed through its label, which is the whole line: the target is the larger of the two
            const small = await page.evaluate(() => Array.from(document.querySelectorAll('#ar button, #ar input[type=checkbox], #ar input[type=radio]'))
              .filter(e => {
                const own = e.getBoundingClientRect();
                const lab = e.labels && e.labels[0] ? e.labels[0].getBoundingClientRect() : own;
                const h = Math.max(own.height, lab.height), wd = Math.max(own.width, lab.width);
                return own.width > 0 && (h < (e.tagName === 'BUTTON' ? 40 : 36) || wd < 24);
              }).map(e => e.outerHTML.slice(0, 70)));
            eq(small.join(' | '), '', `${w}px ${theme}: every button is at least 40 pixels tall and every box or dot has a line at least 36`);
          }
          await shot(`j-${w}-${theme}`);
          if (SHOTS && w === 390) {
            // A WHOLE PAGE OF A PHONE IS FOUR THOUSAND PIXELS TALL AND UNREADABLE WHEN SHOWN SMALL: what a person
            // sees on the screen, in the two places that matter -- the licence first, the cost beside its button last
            for (const [name, sel, block] of [['about', '#ar .about', 'start'], ['plan', '#ar .go-row', 'end']]) {
              await page.evaluate(([s, b]) => document.querySelector(s).scrollIntoView({block: b}), [sel, block]);
              await page.screenshot({path: `${SHOTS}/arasaac-${tag}-j-390-${theme}-${name}.png`});
            }
            await page.evaluate(() => scrollTo(0, 0));
          }
        }
      }
      await page.setViewportSize({width: 1280, height: 900});
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('k) the hub and the licences page', async () => {
      await world(10);
      await page.goto(origin + '/settings/');
      const card = (await page.locator('a.door[href="/settings/arasaac/"]').innerText()).replace(/\s+/g, ' ');
      has(card, 'Pictograms (ARASAAC)', 'the hub has a card for it');
      has(card, 'any device let in', 'with the pill that says who may');
      has(card, 'not installed', 'and a tag that says nothing is');
      await h.send({cmd: 'build', locales: ['en', 'fr'], resolution: 300});
      await page.goto(origin + '/settings/');
      const card2 = (await page.locator('a.door[href="/settings/arasaac/"]').innerText()).replace(/\s+/g, ' ');
      has(card2, '10 pictograms', 'once it is here the tag says how many');
      has(card2, 'en', 'and in which languages');
      await page.goto(origin + '/licences/');
      const txt = (await page.locator('main.notices').innerText()).replace(/\s+/g, ' ');
      has(txt, 'ARASAAC pictograms', 'the licences page lists them');
      has(txt, 'The pictographic symbols used are the property of the Government of Aragón', 'with the credit');
      has(txt, 'CC BY-NC-SA 4.0', 'and the licence');
      eq(await page.locator('main.notices a[href="https://creativecommons.org/licenses/by-nc-sa/4.0/"]').count() > 0, true, 'which is linked');
      eq(await page.locator('main.notices a[href="/settings/arasaac/"]').count() > 0, true, 'and the door');
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('l) one failed poll does not end the polling', async () => {
      await world(50, {delay: 0.05});
      await door();
      await page.click('#ar [data-get]');
      await until(async () => /\b[1-9]\d* of 50 pictures/.test(await text('[data-row="job"]')), 'it is running');
      let failed = 0;
      await page.route('**/settings/api/arasaac/state', route => { if (failed++ < 1) route.fulfill({status: 502, body: 'bad gateway'}); else route.continue(); });
      await until(async () => failed >= 2, 'the page asked again after a failed answer');
      await page.unroute('**/settings/api/arasaac/state');
      await installed();
      assert(true, 'and it finished');
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('m) the keyboard stays where it was', async () => {
      await world(50, {delay: 0.05});
      await door();
      await page.focus('#lang-es');
      await page.keyboard.press('Space');
      eq(await page.evaluate(() => document.activeElement && document.activeElement.id), 'lang-es', 'ticking keeps the focus on the box');
      await page.focus('#ar [data-get]');
      await page.keyboard.press('Enter');
      await until(async () => (await text('#ar')).includes('Stop'), 'it runs');
      assert(await page.evaluate(() => !!document.activeElement && document.activeElement !== document.body), 'the keyboard did not fall to the page');
      await page.click('[data-row="job"] [data-stop]');
      await until(async () => (await main()).includes('You stopped it'), 'stopped');
      await h.send({cmd: 'slow', seconds: 0});
      await h.send({cmd: 'clear'}).catch(() => {});
    });

    await section('n) a press whose request never arrives', async () => {
      await world(10);
      await door();
      await page.route('**/settings/api/arasaac/get', route => route.abort());
      await page.click('#ar [data-get]');
      await until(async () => (await main()).includes('The server did not answer.'), 'it says so');
      await until(async () => await page.locator('#ar [data-get]').count() === 1, 'and the button comes back');
      await page.unroute('**/settings/api/arasaac/get');
    });

    eq(errors.length, 0, 'no script error, no failed request: ' + errors.join(' | '));
  } finally {
    await browser.close();
    await h.stop();
  }
}

for (const w of who) await suite(w === 'phone');
console.log(`\n${passed} ok, ${failures.length} FAIL`);
for (const f of failures) console.log('FAIL ' + f);
Deno.exit(failures.length ? 1 : 0);
