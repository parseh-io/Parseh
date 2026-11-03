// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Speech to text (TO-DO §7.23, a0.4.1), its own door, against
// Parseh's REAL handler, page and routes on a temporary stt/ tree (tests/speech_harness.py:
// the graphics card and the installing stand in for what a test cannot have):
//   a) not installed: the three parts with what each costs, the processor said the way the
//      brief says it (the CPU already works), no lock and no dead button, the pill that says
//      any device let in, and every language in its own script, right-to-left ones included
//   b) installing: Get it -> a bar that moves (aria-valuenow), Stop, then Installed
//   c) Stop keeps the promise: stopped, not failed, and Carry on
//   d) an error is said in a sentence and Try again works
//   e) installed, then Remove… asks first, Keep it keeps, Remove frees it
//   f) the states of a program made by another Parseh or another Python, with ONE button
//   f2) an installed program that cannot run here can still be removed; f3) no build of it: no size said
//   g) the graphics card: none, found but not ready (what is missing, what it needs, the guide,
//      Check again), ready, and a look that failed
//   h) 1280 and 390, light, dark and sepia: never a sideways scroll, targets big enough,
//      words readable against their ground, nothing wider than the screen
//   i) the Settings hub's card and the reading help's one line pointing here
//   j) one failed poll (a dropped connection, a 502) does not end the polling
//   k) the keyboard stays on the control it was on, through every redraw
//   l) a press whose request never arrives says so, and its button comes back
// Run once from the computer and once as a device that has been let in over the Wi-Fi:
// BOTH are fully working (the owner, 2026-09-28: no lock anywhere on this door).
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/speech_door.mjs
//   SPEECH_DOOR_WHO=computer (or phone) runs one; SECTIONS=jkl runs only those; SHOTS=<dir> saves the screenshots.
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
const who = (Deno.env.get('SPEECH_DOOR_WHO') || 'computer,phone').split(',');
const only = (Deno.env.get('SECTIONS') || '').toLowerCase();
let passed = 0;
const failures = [];
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(a === b, `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const has = (text, part, m) => assert(text.includes(part), `${m} (wanted ${JSON.stringify(part)} in ${JSON.stringify(text.slice(0, 300))})`);
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

// sparse files of the models' real sizes need a file system that has them
if (Deno.build.os === 'windows') {
  console.log('SKIP: the harness lays the models out as sparse files (tests/speech_harness.py)');
  Deno.exit(0);
}

async function startHarness(phone) {
  const args = [root + '/tests/speech_harness.py'];
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
  const pump = (async () => {
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
    if (got !== 'OK') throw Error('harness: ' + got);
  };
  return {proc, info, send, log, stop: async () => { try { proc.kill('SIGTERM'); } catch (_) {} await proc.status; }};
}

const NONE = 'absent';
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
    // a resource the page asked for and the server did not have is named (the browser's own line does not say which)
    // (a 502 is the one a test makes itself: section j answers a poll with one, as a proxy would)
    page.on('response', r => { if (r.status() >= 400 && r.status() !== 502 && !/favicon/.test(r.url())) errors.push(`http ${r.status()} ${r.url()}`); });
    const tag = phone ? 'phone' : 'computer';
    // a section that fails is said, and the rest still run (one run per turn at the shared lock)
    // SECTIONS=jkl runs only those (by their letters)
    const section = async (title, fn) => {
      if (only && !only.includes(title[0])) return;
      console.log(title);
      try { await fn(); } catch (e) { failures.push(`${name}: ${title}: ${e.message}`); console.log('  ' + e.message); }
    };
    const shot = async n => { if (SHOTS) await page.screenshot({path: `${SHOTS}/speech-${tag}-${n}.png`, fullPage: true}); };
    // (a new world is a computer that can have the program: a section that says otherwise says so after)
    const world = async (runtime, models) => {
      await h.send({cmd: 'clear'});
      await h.send({cmd: 'unavailable', why: ''});
      await h.send({cmd: 'wheel', has: true});
      await h.send({cmd: 'state', runtime, models: models || {}});
    };
    const door = async () => {
      await page.goto(origin + '/settings/speech/');
      await page.waitForSelector('#sp .it');
    };
    const row = id => page.locator(`[data-row="${id}"]`);
    const text = async id => (await row(id).innerText()).replace(/\s+/g, ' ');
    const state = () => page.evaluate(() => JSON.parse(document.getElementById('sp-state').textContent));
    const api = async (what, body) => (await (await fetch(origin + '/lookup/api/' + what, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})})).json());

    await section('a) not installed', async () => {
      await h.send({cmd: 'probe', answer: 'none'});
      await world(NONE);
      await door();
      eq(await page.locator('h1.idx').textContent(), 'speech to text', 'the page says what it is');
      const st = await state();
      eq(st.where, phone ? 'lan' : 'self', 'and knows where it is asked from');
      eq(JSON.stringify(st.may), JSON.stringify({'speech.get': true, 'speech.remove': true, 'speech.stop': true, 'speech.preferences': true}),
         'every button is allowed, from here too');
      has(await page.locator('.whomay').innerText(), 'any device let in', "the door's pill says who may");
      // (a0.4.3 shortened the sentence: what can be fetched is fixed, and the page says downloads are checked)
      has(await page.locator('.whomay').innerText(), 'Downloads are checked before use',
          'and why that is safe: what is fetched is checked');
      // THE PROGRAM COMES FIRST (the owner, 2026-10-05): every model runs on it and is fetched with it; the second pass
      // is a choice about those models, so it follows the program, and the models come after both
      const order = await page.evaluate(() => Array.from(document.querySelectorAll('#sp h2.part, #sp-second')).map(
        e => e.id === 'sp-second' ? 'second pass' : e.textContent.trim().split(/\s+/).slice(0, 2).join(' ').toLowerCase()));
      eq(order.slice(0, 3).join(' | '), 'whisper program | second pass | whisper models',
         'the Whisper program is above the rest, then the second pass, then the models: ' + order.join(' | '));
      eq(await page.locator('#sp #sp-second').isVisible(), true, 'and the second pass box is shown, in its place under the program');
      // the page draws itself again after a press and every second while something is fetched: the box is moved
      // back into its place each time, and a keyboard that was on its checkbox stays there
      await page.focus('#sp_second_pass');
      await page.evaluate(() => { const s = document.getElementById('sp_language'); s.value = s.options[1].value;
                                  s.dispatchEvent(new Event('change', {bubbles: true})); });
      eq(await page.evaluate(() => document.activeElement && document.activeElement.id), 'sp_second_pass',
         'a new drawing leaves the keyboard on the second pass checkbox');
      eq(await page.locator('#sp #sp-second').count(), 1, 'and the box is still there once, under the program');
      await page.evaluate(() => { const s = document.getElementById('sp_language'); s.value = '';
                                  s.dispatchEvent(new Event('change', {bubbles: true})); });
      eq(await page.locator('[data-lock]').count(), 0, 'no lock line');
      eq(await page.locator('.gate:not(.open)').evaluateAll(els => els.filter(e => e.closest('.whomay')).length), 0,
         "and none of this page's own pills says the computer only");
      eq(await page.locator('#sp button:disabled').count(), 0, 'no dead button');
      // the parts, each with what it costs
      const rt = await text('runtime');
      has(rt, 'The speech program', 'the program is a part');
      has(rt, 'Not yet', 'not installed');
      has(rt, '128 MB', 'its download is said before anything starts');
      has(rt, 'if you stop it, it starts again from the beginning', 'and where it cannot resume, the page says so');
      const turbo = await text('large-v3-turbo');
      has(turbo, 'faster-whisper / large-v3-turbo', 'the label of the recommended model');
      has(turbo, 'Recommended · faster and lighter', 'and its trade-off');
      has(turbo, '1.7 GB', 'its download counts the program that comes first');
      has(turbo, 'includes the speech program', 'and says so');
      const big = await text('large-v3');
      has(big, 'faster-whisper / large-v3', 'the higher-accuracy model');
      has(big, 'Higher accuracy · larger and slower', 'and its trade-off');
      has(big, '3.2 GB', 'its download');
      // the program, the two standard models, a0.4.3's thirteen language-specific ones, and the optional
      // exact-word-times network of each language that has one pinned (lib/alignerpins.py)
      const ALIGNERS = (Deno.readTextFileSync(root + '/lib/alignerpins.py').match(/^ "[a-z]{2,3}": \("[0-9a-f]{40}"/gm) || []).length;
      const GETS = 1 + 2 + 13 + ALIGNERS;
      eq(await page.locator('[data-row] [data-get]').count(), GETS,
         'a Get it for the program, every model and every language\'s optional exact-word-times network');
      // LABEL IN NAME (WCAG 2.5.3): a person who says "click Get it" reaches every row, and each
      // still says which part it is for
      eq(await page.getByRole('button', {name: 'Get it'}).count(), GETS, 'each "Get it" is named by the words it shows');
      eq((await page.locator('[data-row="runtime"] [data-get]').getAttribute('aria-label')), 'Get it: the speech program',
         'and names its part after them');
      eq((await page.locator('[data-row="large-v3"] [data-get]').getAttribute('aria-label')), 'Get it: faster-whisper / large-v3',
         'each one');
      // the processor, said the way the brief says it: the CPU already works
      const cpu = await text('cpu');
      has(cpu, 'CPU · ready', 'the CPU is ready');
      has(cpu, 'Speech to text will work on this computer. A compatible NVIDIA graphics card can make it considerably faster, but one is not required.',
          'and the first sentence says the CPU already works');
      lacks(cpu, 'CUDA', 'never that anything must be installed for it');
      has(cpu, 'Speech to text will work here. Long videos may take some time.', 'and how many cores');
      await until(async () => (await text('gpu')).includes('No NVIDIA graphics card'), 'the card is looked at once, on opening');
      has(await text('gpu'), 'No NVIDIA graphics card was found on this computer.', 'and none is said, in words');
      eq(await page.locator('details.tech[open]').count(), 0, 'technical details are folded');
      // every language, in its own script
      const chips = await page.locator('.lang-chip').evaluateAll(els => els.map(e => {
        const n = e.querySelector('.nat');
        return {lang: n.getAttribute('lang'), dir: n.getAttribute('dir'), no: e.classList.contains('no'), text: n.textContent};
      }));
      eq(chips.length, st.languages.length, 'a chip for every language Parseh has');
      for (const code of JSON.parse(Deno.readTextFileSync(root + '/lib/languages.json'))._shipped)
        assert(chips.some(c => c.lang === code && !c.no), `${code} is offered`);
      eq(chips.filter(c => c.dir === 'rtl').map(c => c.lang).sort().join(), 'ar,fa', 'Persian and Arabic are marked right-to-left');
      assert(chips.every(c => c.lang && c.text), 'every chip names its language in that language');
      eq(await page.locator('.band .n').first().innerText(), '0 MB', 'nothing kept yet');
      await shot('a-absent');

    });

    await section('b) installing', async () => {
      await h.send({cmd: 'build', steps: 40, pause: 0.12, fail: null});
      await page.click('[data-row="large-v3-turbo"] [data-get]');
      await page.waitForSelector('[data-row="large-v3-turbo"] [role=progressbar]');
      const bar = () => page.locator('[data-row="large-v3-turbo"] [role=progressbar]').getAttribute('aria-valuenow');
      const first = Number(await bar());
      await until(async () => Number(await bar()) > first + 4, 'the bar moves');
      assert(true, `the bar moved from ${first}% on`);
      has(await text('large-v3-turbo'), 'Downloading', 'the state says what it is doing');
      has(await text('large-v3-turbo'), 'of 1.7 GB', 'in bytes');
      eq(await row('large-v3-turbo').locator('[data-stop]').count(), 1, 'with a Stop');
      eq(await row('large-v3-turbo').locator('[data-get]').count(), 0, 'and no second Get it');
      await shot('b-installing');
      await until(async () => (await text('large-v3-turbo')).includes('Installed'), 'the install ends', 30000);
      has(await text('runtime'), 'Installed', 'the program came with it');
      has(await text('large-v3-turbo'), '1.6 GB', 'and the model says how big it is');
      has(await text('large-v3-turbo'), 'dropbox-dash/faster-whisper-large-v3-turbo', 'and where it is from');
      eq(await row('large-v3-turbo').locator('[data-remove]').count(), 1, 'with a Remove');
      assert((await page.locator('.band .n').first().innerText()).includes('GB'), 'the band says what is kept');
      has(await row('large-v3-turbo').locator('.it-lic').innerText(), 'MIT', 'the licence is on the row');
      has(await row('runtime').locator('.it-lic').innerText(), 'BSD-3-Clause', "and the program's, with PyAV's beside it");
      await shot('b-installed');

    });

    await section('c) stop', async () => {
      await world(NONE);
      await h.send({cmd: 'build', steps: 300, pause: 0.1, fail: null});
      await door();
      await page.click('[data-row="large-v3"] [data-get]');
      await page.waitForSelector('[data-row="large-v3"] [data-stop]');
      await sleep(700);
      await page.click('[data-row="large-v3"] [data-stop]');
      await until(async () => (await text('large-v3')).includes('You stopped it'), 'stopped, and said so', 15000);
      has(await text('large-v3'), 'Stopped', 'the state is Stopped');
      lacks(await text('large-v3'), 'The last try stopped', 'not a failure');
      eq(await row('large-v3').locator('[data-get]').innerText(), 'Carry on', 'and the button says what it will do');

    });

    await section('d) an error', async () => {
      await world(NONE);
      const said = 'Parseh could not reach the package server (pypi.org). Check the connection and press it again; nothing was installed.';
      await h.send({cmd: 'build', steps: 6, pause: 0.05, fail: said});
      await door();
      await page.click('[data-row="runtime"] [data-get]');
      await page.waitForSelector('[data-row="runtime"] .note.bad');
      has(await text('runtime'), said, 'the sentence, not a class name');
      eq(await row('runtime').locator('[data-get]').innerText(), 'Try again', 'with Try again');
      lacks(await text('runtime'), 'getstt:', "and not the program's prefix");
      await shot('d-error');
      await h.send({cmd: 'build', steps: 6, pause: 0.05, fail: null});
      await row('runtime').locator('[data-get]').click();
      await until(async () => (await text('runtime')).includes('Installed'), 'and Try again works', 20000);

    });

    await section('e) remove', async () => {
      await world('ready', {'large-v3-turbo': 'ready'});
      await door();
      const inst = await text('large-v3-turbo');
      has(inst, 'Installed', 'installed');
      has(inst, '1.6 GB', 'and how big');
      has(inst, 'built 28 September 2026', 'and when');
      has(await text('runtime'), 'faster-whisper 1.2.1', 'the program names its version');
      has(await text('runtime'), 'CTranslate2 4.8.2', 'and its engine');
      await row('large-v3-turbo').locator('[data-remove]').click();
      await page.waitForSelector('[data-row="large-v3-turbo"] .ask');
      has(await text('large-v3-turbo'), 'Remove the large-v3-turbo model? It frees 1.6 GB; getting it back is a 1.6 GB download.', 'it asks first, with what it frees');
      await row('large-v3-turbo').locator('[data-cancel]').click();
      eq(await row('large-v3-turbo').locator('.ask').count(), 0, 'Keep it keeps');
      eq((await api('speech')).models[0].have, true, 'and the model is still there');
      await row('large-v3-turbo').locator('[data-remove]').click();
      await row('large-v3-turbo').locator('[data-yes]').click();
      await until(async () => (await text('large-v3-turbo')).includes('Not yet'), 'Remove takes it away', 15000);
      eq((await api('speech')).models[0].have, false, 'really');
      eq((await api('speech')).runtime.state, 'ready', 'and the program, which is not the model, stays');
      // taking the program away: the models stay, and are said to wait for it
      await world('ready', {'large-v3': 'ready'});
      await door();
      await row('runtime').locator('[data-remove]').click();
      has(await text('runtime'), 'The models stay, but cannot be used until the program is back.', 'removing the program says what stays');
      await row('runtime').locator('[data-yes]').click();
      await until(async () => (await text('runtime')).includes('Not yet'), 'the program is removed', 15000);
      has(await text('large-v3'), 'Installed', 'the model is untouched');

    });

    await section('f) older, newer, another Python, incomplete', async () => {
      for (const [runtime, word, why] of [['older', 'Built by an older Parseh', 'installed by an older Parseh'],
                                          ['newer', 'Built by a newer Parseh', 'installed by a newer Parseh'],
                                          ['other_python', 'Built for another Python', 'installed for Python 3.11'],
                                          ['broken', 'Incomplete', 'incomplete']]) {
        await world(runtime, {'large-v3-turbo': 'ready'});
        await door();
        const t = await text('runtime');
        has(t, word, `${runtime}: the state is said in words`);
        has(t.toLowerCase(), why.toLowerCase(), `${runtime}: and why`);
        eq(await row('runtime').locator('[data-get]').count(), 1, `${runtime}: ONE button to make it again`);
        has(await row('runtime').locator('[data-get]').innerText(), 'Install it again', `${runtime}: and it says what it is`);
        has(await text('large-v3-turbo'), 'Installed', `${runtime}: the model is still a model here`);
      }
      await world('older', {'large-v3-turbo': 'ready'});
      await h.send({cmd: 'build', steps: 8, pause: 0.05, fail: null});
      await door();
      await shot('f-older');
      await row('runtime').locator('[data-get]').click();
      await until(async () => (await text('runtime')).includes('Installed') && !(await text('runtime')).includes('older Parseh'),
                  'the older program is made again', 20000);
      await world('older', {});
      await h.send({cmd: 'unavailable', why: 'This Parseh runs on Python 3.11, and the speech program is built for Python 3.12 only.'});
      await door();
      has(await text('runtime'), 'Not available', 'a computer that cannot have it says so');
      has(await text('runtime'), 'built for Python 3.12 only', 'and why');
      eq(await page.locator('#sp [data-get]').count(), 0, 'and offers no button that cannot work');
      // THE PROCESSOR PROMISES NOTHING where the program cannot run: it said "CPU · ready" and that
      // speech to text "will work on this computer" beside a program row that said Not available
      const cpuNa = await text('cpu');
      lacks(cpuNa, 'CPU · ready', 'the processor is not called ready where the program cannot run');
      lacks(cpuNa, 'will work', 'and is not promised to work');
      has(cpuNa, 'CPU · not usable here', 'it says so');
      has(cpuNa, 'built for Python 3.12 only', 'and why, in the program row\'s own words');
      has((await page.locator('.modes').innerText()).replace(/\s+/g, ' '), 'Not usable on this computer', 'the modes say it too');
      lacks((await page.locator('.modes').innerText()).replace(/\s+/g, ' '), 'Works on every computer', 'and not that it works everywhere');
      await h.send({cmd: 'unavailable', why: ''});

    });

    await section('f2) a program that is installed and cannot run here', async () => {
      // A PROGRAM THAT IS HERE AND CANNOT RUN is still the person's to take away: no button to get it,
      // one to remove it, and the question says how much room it gives back
      await world('ready', {});
      await h.send({cmd: 'unavailable', why: 'This Parseh runs on Python 3.11, and the speech program is built for Python 3.12 only.'});
      await door();
      has(await text('runtime'), 'Not available', 'an installed program that cannot run says so');
      eq(await row('runtime').locator('[data-get]').count(), 0, 'and offers nothing to get');
      eq(await row('runtime').locator('[data-remove]').count(), 1, 'but can be removed');
      await row('runtime').locator('[data-remove]').click();
      assert(/It frees \d+ MB/.test(await text('runtime')), 'and says how much room that gives back: ' + (await text('runtime')).slice(0, 200));
      await row('runtime').locator('[data-yes]').click();
      await until(async () => !(await api('speech')).runtime.have, 'the program is taken away', 15000);
      await h.send({cmd: 'unavailable', why: ''});

    });

    await section('f3) a computer that has no build of the program', async () => {
      // the size of a download nobody can make is not said
      await world(NONE);
      await h.send({cmd: 'wheel', has: false});
      await h.send({cmd: 'unavailable', why: 'There is no speech program for this kind of computer (freebsd14, amd64).'});
      await door();
      // a0.4.3's page gives every model its own row (the old paragraph "The models are large: 1.6 GB and 3.1 GB." is
      // gone): what a computer with no build of the program says is on the rows, and none of them promises a size
      const rt = await text('runtime');
      has(rt, 'Not available', 'the program says it is not available here');
      has(rt, 'There is no speech program for this kind of computer', 'and why');
      lacks(rt, 'to download', 'and no size of a program that has no build');
      for (const id of ['large-v3-turbo', 'large-v3']) {
        const m = await text(id);
        has(m, 'Not available', id + ' says so too');
        lacks(m, 'GB to download', 'and promises no download that nobody can make');
      }
      await h.send({cmd: 'wheel', has: true});
      await h.send({cmd: 'unavailable', why: ''});

    });

    await section('g) the graphics card', async () => {
      await world('ready', {'large-v3-turbo': 'ready'});
      await h.send({cmd: 'probe', answer: 'found-not-ready'});
      await door();
      await until(async () => (await text('gpu')).includes('Found, not ready'), 'the card is found, and not ready');
      const g = await text('gpu');
      has(g, 'NVIDIA GeForce GTX 1650', 'named');
      has(g, 'NVIDIA GPU found, but speech-to-text acceleration is not ready.', 'the words of the brief');
      has(g, 'CPU transcription will still work.', 'and the CPU is said to work');
      has(g, 'Missing: cuBLAS for CUDA 12 (libcublas.so.12 was not found)', 'the piece that is missing, by name');
      has(g, 'For GPU acceleration this installation needs:', 'what it needs');
      has(g, 'an NVIDIA graphics driver that runs CUDA 12 programs', 'the driver, from the pinned table');
      has(g, 'cuBLAS for CUDA 12', 'cuBLAS for CUDA 12, from the pinned table');
      lacks(g.replace('cuDNN is not needed with this version of the speech program.', ''), 'cuDNN',
            'and no cuDNN: this version does not need it');
      has(g, 'cuDNN is not needed with this version of the speech program.', 'which the page says once');
      const help = await row('gpu').locator('a', {hasText: 'How to enable GPU acceleration'}).getAttribute('href');
      has(help, '/lookup-and-languages/speech-to-text.html#how-to-enable-gpu-acceleration', 'a link to the guide, at its section');
      eq(await row('gpu').locator('[data-check]').innerText(), 'Check again', 'and its own button to look again');
      await row('gpu').locator('details.tech summary').click();
      const techText = (await row('gpu').locator('details.tech').innerText()).replace(/\s+/g, ' ');
      has(techText, 'Driver 595.91.07', 'the technical details are one click away');
      has(techText, 'CPU int8', 'the CPU computes in int8');
      await shot('g-not-ready');
      // Automatic says the CPU while the card is not ready, and the card option says why not
      has(await text('cpu'), 'CPU · ready', 'the CPU is ready all the same');
      await h.send({cmd: 'probe', answer: 'ready'});
      await row('gpu').locator('[data-check]').click();
      await until(async () => (await text('gpu')).includes('GPU acceleration ready'), 'Check again looks again', 15000);
      const ok = await text('gpu');
      has(ok, 'NVIDIA GeForce RTX 4070', 'the new card, by name');
      has(ok, 'Automatic mode will use the graphics card for faster transcription. You can still choose CPU if you prefer.', 'the words of the brief');
      lacks(ok, 'Missing', 'and nothing is missing');
      has((await page.locator('.modes').innerText()).replace(/\s+/g, ' '), 'Right now: NVIDIA GeForce RTX 4070', 'Automatic says which it is using now');
      await shot('g-ready');
      await h.send({cmd: 'probe', answer: 'error'});
      await row('gpu').locator('[data-check]').click();
      await until(async () => (await text('gpu')).includes('took more than 30 seconds'), 'a look that failed is said, not hidden', 15000);
      has(await text('gpu'), 'No NVIDIA graphics card', 'and is not taken for a card that is ready');
      await h.send({cmd: 'probe', answer: 'none'});

    });

    await section('h) widths and themes', async () => {
      await world('ready', {'large-v3-turbo': 'ready'});
      await h.send({cmd: 'probe', answer: 'found-not-ready'});
      const ratio = () => page.evaluate(() => {
        const lum = c => { const v = c.match(/[\d.]+/g).slice(0, 3).map(Number).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
        const ground = el => { for (let e = el; e; e = e.parentElement) { const b = getComputedStyle(e).backgroundColor; const m = b.match(/[\d.]+/g); if (m && (m.length < 4 || Number(m[3]) > .9)) return b; } return 'rgb(255,255,255)'; };
        const worst = [];
        // the technical details are folded, and a folded label has no box to measure: they are opened
        // first, so that what a person reads when the card is "found, not ready" is held to the same 4.5:1
        document.querySelectorAll('#sp details.tech').forEach(d => { d.open = true; });
        for (const sel of ['.it-name', '.it-for', '.it-facts', '.whomay span', '.lang-chip span:not(.nat)',
                           'details.tech dt', 'details.tech dd']) {
          for (const el of document.querySelectorAll('#sp ' + sel + ', main ' + sel)) {
            if (!el.offsetParent || !el.textContent.trim()) continue;
            const a = lum(getComputedStyle(el).color), b = lum(ground(el));
            const r = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
            worst.push([r, sel]);
          }
        }
        worst.sort((x, y) => x[0] - y[0]);
        // the state pills apart: a sign, a word and a border say the state, and their palette is the whole
        // toolbox's (the reading help draws the same amber at the same 3.99:1 on white), so they are held
        // to the 3:1 a component needs and not the 4.5:1 a paragraph does
        const pills = [...document.querySelectorAll('#sp .st')].filter(e => e.offsetParent).map(el => {
          const a = lum(getComputedStyle(el).color), b = lum(ground(el));
          return [(Math.max(a, b) + .05) / (Math.min(a, b) + .05), el.textContent.trim()];
        }).sort((x, y) => x[0] - y[0]);
        return {text: worst[0], pill: pills[0]};
      });
      // one width and theme's checks all run, and every one that fails is said
      const soft = (v, m) => { if (v) { passed++; console.log('  ok', m); } else { failures.push(`${name}: ${m}`); console.log('  FAIL:', m); } };
      for (const w of [1280, 390]) {
        await page.setViewportSize({width: w, height: w === 390 ? 844 : 900});
        for (const theme of ['light', 'dark', 'sepia']) {
          await door();
          await page.evaluate(t => { if (window.Parseh && Parseh.theme) Parseh.theme.set(t); else document.documentElement.setAttribute('data-theme', t); }, theme);
          await until(async () => (await text('gpu')).includes('Found, not ready'), 'the card looked at');
          const label = `${w}px ${theme}`;
          const over = await page.evaluate(() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth}));
          soft(over.sw <= over.cw + 1, `${label}: no sideways scroll (${over.sw} in ${over.cw})`);
          const out = await page.evaluate(() => {
            const vw = document.documentElement.clientWidth;
            return [...document.querySelectorAll('#sp .it, #sp .lang-chip, #sp button, #sp a.plain, .band')]
              .filter(e => e.getBoundingClientRect().right > vw + 1).map(e => e.className || e.tagName);
          });
          soft(out.length === 0, `${label}: nothing wider than the screen (${out.join()})`);
          const small = await page.evaluate(min => [...document.querySelectorAll('#sp button, #sp a.plain, #sp a.go')]
            .filter(e => e.offsetParent && e.getBoundingClientRect().height < min).map(e => e.textContent.trim()), w === 390 ? 40 : 30);
          soft(small.length === 0, `${label}: every button is big enough to press (${small.join()})`);
          const r = await ratio();
          soft(r.text[0] >= 4.5, `${label}: the words are readable against their ground (worst ${r.text[0].toFixed(2)}:1 on ${r.text[1]})`);
          soft(r.pill[0] >= 3, `${label}: the state pills hold 3:1 (worst ${r.pill[0].toFixed(2)}:1, "${r.pill[1]}")`);
          const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
          soft(bg, `${label}: the ground is ${bg}`);
          // the header of every right-to-left language is drawn right-to-left, and inside the screen
          const rtl = await page.locator('.lang-chip .nat[dir=rtl]').evaluateAll(els => els.map(e => {
            const b = e.getBoundingClientRect(); return [getComputedStyle(e).direction, b.left >= 0 && b.right <= innerWidth];
          }));
          soft(rtl.length >= 2 && rtl.every(x => x[0] === 'rtl' && x[1]), `${label}: Persian and Arabic read right-to-left, inside the screen`);
          await shot(`h-${w}-${theme}`);
        }
      }
      await page.setViewportSize({width: 1280, height: 900});
      await page.evaluate(() => { if (window.Parseh && Parseh.theme) Parseh.theme.set('auto'); });
      await h.send({cmd: 'probe', answer: 'none'});

    });

    await section("i) Settings' hub and the reading help", async () => {
      await page.goto(origin + '/settings/');
      const card = page.locator('a.door[href="/settings/speech/"]');
      eq(await card.count(), 1, "the hub has a card for it");
      has(await card.innerText(), 'Speech to text', 'named');
      has(await card.innerText(), 'any device let in', 'with the pill that says who may');
      await card.click();
      await page.waitForSelector('#sp .it');
      eq(new URL(page.url()).pathname, '/settings/speech/', 'and it opens the door');
      await page.goto(origin + '/settings/reading-help/');
      await page.waitForSelector('#rh .it, #rh section');
      const pointer = page.locator('.foot.pointer a[href="/settings/speech/"]');
      eq(await pointer.count(), 1, 'the reading help points here in one line');
      has(await page.locator('.foot.pointer').innerText(), 'speech to text has a page of its own', 'saying so');
      lacks((await page.locator('#rh').innerText()), 'faster-whisper', 'and carries nothing of speech to text itself');
      const doors = await page.locator('.sdoor').evaluateAll(els => els.map(e => e.getAttribute('href')));
      assert(doors.includes('/settings/speech/'), "and Settings' row of doors has it");

    });

    await section('j) a poll that fails does not end the polling', async () => {
      // a phone that loses the Wi-Fi for a moment, a 502 with a page for a body: one failed answer is
      // never a verdict, and the bar goes on (it stopped for good, and said "Downloading" for ever)
      await world(NONE);
      await h.send({cmd: 'build', steps: 300, pause: 0.15, fail: null});
      await door();
      await page.click('[data-row="large-v3-turbo"] [data-get]');
      await page.waitForSelector('[data-row="large-v3-turbo"] [role=progressbar]');
      const bar = async () => Number(await page.locator('[data-row="large-v3-turbo"] [role=progressbar]').getAttribute('aria-valuenow'));
      await until(async () => (await bar()) >= 3, 'the bar has begun');
      let failed = 0;
      await page.route('**/lookup/api/speech', route => {
        failed++;
        if (failed === 1) return route.abort('connectionreset');
        if (failed === 2) return route.fulfill({status: 502, contentType: 'text/html', body: '<html><body>Bad gateway</body></html>'});
        return route.continue();
      });
      await until(async () => failed >= 2, 'two polls were made to fail', 15000);
      const at = await bar();
      await until(async () => (await bar()) >= at + 2, `the bar goes on after two polls that failed (was ${at}%)`, 30000);
      assert(failed >= 3, 'the polling went on');
      await page.unroute('**/lookup/api/speech');
      await page.click('[data-row="large-v3-turbo"] [data-stop]');
      await until(async () => (await text('large-v3-turbo')).includes('You stopped it'), 'and Stop still works', 15000);
    });

    await section('k) the keyboard stays where it is', async () => {
      // the page is drawn again every second while something is fetched, and after every press: the
      // control that had the keyboard is put back (a keyboard user could not reach Stop in time)
      const active = () => page.evaluate(() => {
        const a = document.activeElement;
        return a && a.attributes ? [...a.attributes].map(x => x.name + '=' + x.value).filter(x => x.startsWith('data-')).join(' ') : '';
      });
      await world(NONE);
      await h.send({cmd: 'build', steps: 300, pause: 0.1, fail: null});
      await door();
      await row('large-v3-turbo').locator('[data-get]').focus();
      await page.keyboard.press('Enter');
      await page.waitForSelector('[data-row="large-v3-turbo"] [data-stop]');
      await until(async () => (await active()) === 'data-stop=large-v3-turbo', 'the keyboard is on Stop, which is where the pressed button went', 6000);
      // ...and stays there through redraws (there is one a second)
      await sleep(3500);
      eq(await active(), 'data-stop=large-v3-turbo', 'three redraws later the keyboard is still on Stop');
      await page.keyboard.press('Enter');
      await until(async () => (await text('large-v3-turbo')).includes('You stopped it'), 'Enter on it stops the job', 15000);
      // a question that is asked is asked with the safe answer under the keyboard
      await world('ready', {'large-v3-turbo': 'ready'});
      await door();
      await row('large-v3-turbo').locator('[data-remove]').focus();
      await page.keyboard.press('Enter');
      await page.waitForSelector('[data-row="large-v3-turbo"] .ask');
      await until(async () => (await active()) === 'data-cancel=large-v3-turbo', 'Remove… asks, and the keyboard is on "Keep it"', 4000);
      await page.keyboard.press('Enter');
      await until(async () => (await active()) === 'data-remove=large-v3-turbo', 'Keep it puts it back on Remove…', 4000);
      // Check again is drawn as "Looking…" and back, and keeps the keyboard
      await until(async () => (await text('gpu')).includes('No NVIDIA graphics card'), 'the card is looked at, on opening');
      await row('gpu').locator('[data-check]').focus();
      await page.keyboard.press('Enter');
      await sleep(600);
      eq(await active(), 'data-check=', 'Check again keeps the keyboard, though its button is gone while the card is looked at');
    });

    await section('l) a request that does not arrive is said, and the button comes back', async () => {
      const lost = 'The server did not answer.';
      // Get it
      await world(NONE);
      await door();
      await page.route('**/lookup/api/getspeech', route => route.abort('connectionreset'));
      await page.click('[data-row="large-v3"] [data-get]');
      await until(async () => (await text('large-v3')).includes(lost), 'a Get it that did not arrive says so');
      eq(await row('large-v3').locator('[data-cancel]').innerText(), 'All right', 'with a way to go on');
      await row('large-v3').locator('[data-cancel]').click();
      eq(await row('large-v3').locator('[data-get]:not([disabled])').count(), 1, 'and Get it is there to press again');
      await page.unroute('**/lookup/api/getspeech');
      // Remove
      await world('ready', {'large-v3-turbo': 'ready'});
      await door();
      await page.route('**/lookup/api/dropspeech', route => route.abort('connectionreset'));
      await row('large-v3-turbo').locator('[data-remove]').click();
      await row('large-v3-turbo').locator('[data-yes]').click();
      await until(async () => (await text('large-v3-turbo')).includes(lost), 'a Remove that did not arrive says so');
      await row('large-v3-turbo').locator('[data-cancel]').click();
      eq(await row('large-v3-turbo').locator('[data-remove]:not([disabled])').count(), 1, 'and Remove… is there again');
      eq((await api('speech')).models[0].have, true, 'and the model is still here');
      await page.unroute('**/lookup/api/dropspeech');
      // Stop
      await world(NONE);
      await h.send({cmd: 'build', steps: 300, pause: 0.1, fail: null});
      await door();
      await page.click('[data-row="large-v3"] [data-get]');
      await page.waitForSelector('[data-row="large-v3"] [data-stop]');
      await page.route('**/lookup/api/stopspeech', route => route.abort('connectionreset'));
      await page.click('[data-row="large-v3"] [data-stop]');
      await until(async () => (await text('large-v3')).includes(lost), 'a Stop that did not arrive says so');
      await page.unroute('**/lookup/api/stopspeech');
      await row('large-v3').locator('[data-cancel]').click();
      await until(async () => (await row('large-v3').locator('[data-stop]:not([disabled])').count()) === 1, 'and Stop is there to press again');
      await row('large-v3').locator('[data-stop]').click();
      await until(async () => (await text('large-v3')).includes('You stopped it'), 'and it works', 15000);
    });

    if (errors.length) failures.push(`${name}: page errors: ` + errors.join(' | '));
    else assert(true, 'no page error');
  } finally {
    await browser.close();
    await h.stop();
  }
}

for (const w of who) await suite(w === 'phone');
console.log(`\n${passed} checks passed`);
if (failures.length) { console.log('\nFAILED:\n  ' + failures.join('\n  ')); Deno.exit(1); }
