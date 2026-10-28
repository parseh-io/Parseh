// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of "MAKE DRAWINGS OF N SHOWN" (a0.5.6, lib/latexbatch.py): the LaTeX drawings of the documents the library
// shows, made in the background without opening one, on the bar every page of the toolbox has and on the hub.  The REAL
// studio (tests/studio_harness.py, with the TeX this computer has; each drawing waits a moment first, --latex-slow, so the
// work lasts long enough to be looked at):
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/latex_batch.mjs
//   LATEX_BATCH_MODES=parseh (or studio) runs one; SHOTS=<dir> saves screenshots
//
//  parseh) the hub's handler, which has the activity list (lib/activity.js, /__activity):
//    a) the button says how many documents are shown, follows the search, and is off when none is
//    b) a click: the pill is on the screen at once, under the words the server's entry will carry, and the bar moves by
//       the share of drawings made -- many distinct values on the way from 0 % to the end, never backwards, with "n of
//       63" in the list, and the same entry on /__activity: kind compile, unit items, done and total in drawings; the
//       hub's own page shows it in its panel; at the end "Done", the button back, and a toast that says what was made
//       and which document a failed drawing was in; the drawings are then really made: a document opens with none
//       pending
//    c) again: nothing to make, said, and nothing started
//    d) Stop: no new drawing, what was made stays made, said in a toast
//    e) the page reloaded while it runs picks the job up where it is, with its Stop
//  studio) a studio run on its own, which has no activity list: the page draws its own bar and number, moved the same way
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('LATEX_BATCH_MODES') || 'parseh,studio').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(JSON.stringify(a) === JSON.stringify(b), `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 60000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}

// no TeX, no drawings: a named skip
const hasTeX = await new Deno.Command('xelatex', {args: ['--version'], stdout: 'null', stderr: 'null'}).output()
  .then(r => r.success, () => false);
if (!hasTeX) {
  console.log('SKIP: no xelatex on this computer -- the drawings are made by TeX (tests/latex_batch.mjs)');
  Deno.exit(0);
}

async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', mode, '--latex-slow=0.12'], cwd: root,
                                         stdout: 'piped', stderr: 'piped'}).spawn();
  const log = [];
  (async () => {
    const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); }
  })();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf + log.join(''));
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

const front = (title, body) => `---\ntitle: ${title}\ntarget: it\n---\n\n${body}\n`;
const block = (what) => `::::latex\n${what}\n::::`;
// ten documents of three blocks and three marks each, all different: sixty drawings
const gamma = d => front(`Gamma ${d}`, [0, 1, 2].map(k => `${block(`\\textbf{gamma ${d} item ${k}} $x^${k}$`)}\n\nA mark [\\textit{i${d}-${k}}]{latex} here.`).join('\n\n'));
const SHARED = block('\\textbf{shared one}') + '\n\n' + block('\\textbf{shared two}');
const BROKEN = front('Broken', block('\\undefinedcommandxyz'));

async function suite(browser, mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info} = await startHarness(mode);
  const origin = `http://127.0.0.1:${info.port}`, S = info.studio;
  const url = p => origin + S + p;
  const api = async (method, path, body) => {
    const r = await fetch(url(path), {method, headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
    return {status: r.status, data: await r.json()};
  };
  const errors = [];
  try {
    const ids = {};
    for (let d = 0; d < 10; d++) ids[`Gamma ${d}`] = (await api('POST', '/api/docs', {markdown: gamma(d)})).data.meta.id;
    for (const [title, md] of [['Plain', front('Plain', 'No drawing here.')], ['Shared A', front('Shared A', SHARED)],
                               ['Shared B', front('Shared B', SHARED)], ['Broken', BROKEN]])
      ids[title] = (await api('POST', '/api/docs', {markdown: md})).data.meta.id;
    // 60 + 2 shared (one each, though two documents show them) + 1 that cannot be made
    const TOTAL = 63;
    const shown = () => page.evaluate(() => [...document.querySelectorAll('.card:not([hidden])')].length);
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    page.on('pageerror', e => errors.push(e.message));
    const button = page.locator('#btn-make-drawings');
    const toast = () => page.locator('#toast').textContent();
    await page.goto(url('/'));
    await page.waitForSelector('.card');
    await until(async () => /of \d+ shown/.test(await button.textContent()) && !/of 0 shown/.test(await button.textContent()), 'the count follows the cards');

    /* ---------------- a) the button ---------------- */
    console.log('a) the button and the set it takes');
    const all = await shown();
    eq(await button.textContent(), `Make drawings of ${all} shown`, 'the button says how many documents are shown');
    assert(await button.isEnabled(), 'and is on');
    await page.fill('#search', 'Gamma 3');
    await until(async () => (await shown()) === 1, 'the search narrows the set');
    eq(await button.textContent(), 'Make drawings of 1 shown', 'it follows the search');
    assert((await button.getAttribute('title')).includes('1 document shown'), 'and its title says it in the singular');
    await page.fill('#search', 'zzzz no such document');
    await until(async () => (await shown()) === 0, 'the search finds nothing');
    assert(await button.isDisabled(), 'with nothing shown it is off');
    await page.fill('#search', '');
    await until(async () => (await shown()) === all, 'the whole library is shown again');

    /* ---------------- b) the bar ---------------- */
    console.log('b) the work, and the bar that follows it');
    const hubPage = mode === 'parseh' ? await browser.newPage({viewport: {width: 1280, height: 900}}) : null;
    if (hubPage) {
      hubPage.on('pageerror', e => errors.push('hub: ' + e.message));
      await hubPage.goto(origin + '/');
    }
    await button.click();
    await until(async () => /^Making drawings…/.test(await button.textContent()), 'the button says the work has begun');
    const seen = {pct: [], done: [], ownBar: [], rows: [], hub: []};
    let sawEntry = null, ended = false;
    for (let i = 0; i < 600 && !ended; i++) {
      const s = await page.evaluate(() => {
        const wrap = document.querySelector('#parseh-activity');
        const live = wrap && !wrap.hidden;
        const pct = live ? document.querySelector('#parseh-activity .pa-pct').textContent : '';
        const say = live ? document.querySelector('#parseh-activity .pa-say').textContent : '';
        const bar = document.querySelector('#make-drawings-bar');
        return {live, pct, say, btn: document.querySelector('#btn-make-drawings').textContent,
                own: bar && !bar.hidden ? {value: bar.value, text: document.querySelector('#make-drawings-say').textContent} : null,
                ended: /^Make drawings of/.test(document.querySelector('#btn-make-drawings').textContent)};
      });
      ended = s.ended;
      const m = s.pct.match(/^(\d+)%$/);
      if (m) seen.pct.push(+m[1]);
      const d = s.btn.match(/(\d+) of (\d+)$/);
      if (d) { seen.done.push(+d[1]); if (+d[2] !== TOTAL && !sawEntry) sawEntry = `button said ${s.btn}`; }
      if (s.own) seen.ownBar.push(s.own.value);
      if (mode === 'parseh' && i % 4 === 1 && !ended) {
        const j = await (await fetch(origin + '/__activity')).json();
        const e = j.running.find(x => x.kind === 'compile');
        if (e) seen.rows.push({kind: e.kind, done: e.done, total: e.total, unit: e.unit, label: e.label, job: e.job});
        seen.hub.push(await hubPage.evaluate(() => {
          const sec = document.querySelector('#parseh-working');
          return sec && !sec.hidden ? sec.querySelector('.pa-when') && sec.querySelector('.pa-when').textContent : null;
        }));
      }
      if (!ended) await sleep(100);
    }
    assert(ended, 'the work ended');
    assert(!sawEntry, 'the total never changed on the way: ' + (sawEntry || `${TOTAL}`));
    const nondecreasing = xs => xs.every((x, k) => k === 0 || x >= xs[k - 1]);
    if (mode === 'parseh') {
      assert(seen.pct.length > 0, 'the pill was on the screen while it ran, saying a percentage');
      assert(new Set(seen.pct).size >= 6, `the bar took many values on its way: ${[...new Set(seen.pct)].join(' ')}`);
      assert(nondecreasing(seen.pct) && seen.pct[0] <= 15, 'never backwards, from the start');
      assert(seen.rows.length > 2 && seen.rows.every(r => r.kind === 'compile' && r.unit === 'items' && r.total === TOTAL),
             `/__activity carried one entry counting drawings, ${TOTAL} of them: ${JSON.stringify(seen.rows[0])}`);
      assert(nondecreasing(seen.rows.map(r => r.done)) && new Set(seen.rows.map(r => r.done)).size >= 4, 'its done grew with the work');
      assert(seen.rows.every(r => r.label === `Making the LaTeX drawings of ${all} documents`), 'under the words ' + seen.rows[0].label);
      assert(seen.rows.every(r => /^[a-z2-9]{12}$/.test(r.job || '')), 'and the token the page put on its request: the entry is the page\'s own, shown once');
      assert(seen.hub.some(t => /\d+ of 63/.test(t || '')), `the hub's own page showed it in its panel: ${JSON.stringify(seen.hub.filter(Boolean).slice(0, 2))}`);
      assert(nondecreasing(seen.done) && new Set(seen.done).size >= 6, 'the button counted as well: ' + [...new Set(seen.done)].slice(0, 8).join(' '));
      eq(seen.ownBar.length, 0, 'and the page drew no bar of its own, the activity list being there to do it');
    } else {
      assert(new Set(seen.ownBar).size >= 6 && nondecreasing(seen.ownBar), `with no hub the page's own bar moved, many values: ${[...new Set(seen.ownBar)].join(' ')}`);
    }
    if (SHOTS) await page.screenshot({path: `${SHOTS}/batch-${mode}-end.png`});
    await until(async () => /Made \d+ of 63 LaTeX drawings/.test(await toast()), 'the toast says what was made');
    const said = await toast();
    assert(said.includes('Made 62 of 63 LaTeX drawings; 1 could not be made') && said.includes('“Broken”'),
           'the toast says what was made and which document a drawing failed in: ' + said);
    assert(await button.isEnabled() && (await button.textContent()) === `Make drawings of ${all} shown`, 'the button is back');
    const after = (await api('GET', '/api/latex/make')).data;
    eq([after.running, after.total, after.done, after.made, after.failed], [false, TOTAL, TOTAL, 62, 1], 'the status of the job as it ended');
    // the drawings are made: a document opens with none to wait for, and its drawings drawn
    const doc = await browser.newPage({viewport: {width: 1100, height: 900}});
    await doc.goto(url(`/doc/${ids['Gamma 4']}`));
    await doc.waitForSelector('#sheet');
    eq(await doc.evaluate(() => [document.querySelectorAll('[data-latex-pending]').length, document.querySelectorAll('#sheet figure.latex img').length,
                                 document.querySelectorAll('#sheet img.latex-inline').length]), [0, 3, 3],
       'a document then opens with its three drawings and its three marks made, and none pending');
    eq(await doc.locator('.latex-waiting').count(), 0, 'with no bar of its own waiting for them');
    await doc.close();

    /* ---------------- c) again ---------------- */
    console.log('c) again, with nothing left');
    await page.evaluate(() => { document.querySelector('#toast').hidden = true; });
    await button.click();
    await until(async () => /made already/.test(await toast()), 'the page says nothing is left to make');
    assert((await toast()).includes('1 cannot be drawn'), 'and that one drawing cannot be made, which no run would change: ' + await toast());
    eq((await api('GET', '/api/latex/make')).data.running, false, 'nothing was started');
    if (mode === 'parseh') await sleep(400);
    eq(await page.evaluate(() => { const w = document.querySelector('#parseh-activity'); return !!w && !w.hidden && /Working/.test(w.textContent); }), false,
       'and the pill did not stay on the screen for it');

    /* ---------------- d) Stop ---------------- */
    console.log('d) Stop');
    const more = [];
    for (let d = 0; d < 6; d++) more.push((await api('POST', '/api/docs', {markdown: front(`Delta ${d}`, [0, 1, 2, 3, 4, 5].map(k => block(`\\textbf{delta ${d} ${k}}`)).join('\n\n'))})).data.meta.id);
    await page.reload();
    await page.waitForSelector('.card');
    await page.fill('#search', 'Delta');
    await until(async () => (await shown()) === 6, 'the six Delta documents are shown');
    await button.click();
    await until(async () => /Making drawings… [1-9]\d* of 36/.test(await button.textContent()), 'some of the 36 are made');
    assert(await page.locator('#btn-make-stop').isVisible(), 'Stop is on the screen while it runs');
    await page.locator('#btn-make-stop').click();
    await until(async () => /^Stopped:/.test(await toast()), 'the toast says it was stopped', 30000);
    const stopped = (await api('GET', '/api/latex/make')).data;
    assert(stopped.running === false && stopped.stopped === true && stopped.done > 0 && stopped.done < 36 && stopped.made === stopped.done,
           `no new drawing was begun, and what was made stays made: ${stopped.made} of 36`);
    assert(await button.isEnabled() && !(await page.locator('#btn-make-stop').isVisible()), 'the button is back and Stop is gone');
    await page.fill('#search', '');
    await until(async () => (await shown()) === all + 6, 'the whole library is shown again');

    /* ---------------- e) a reload ---------------- */
    console.log('e) the page left and opened again while it runs');
    await page.fill('#search', 'Delta');
    await until(async () => (await shown()) === 6, 'the Delta documents again');
    await button.click();
    await until(async () => /Making drawings… [1-9]\d* of \d+/.test(await button.textContent()), 'it is under way');
    await page.reload();
    await page.waitForSelector('.card');
    await until(async () => /Making drawings… \d+ of \d+/.test(await button.textContent()), 'a page opened meanwhile picks the job up');
    assert(await button.isDisabled() && await page.locator('#btn-make-stop').isVisible(), 'with the button off and Stop there');
    await until(async () => /^Make drawings of/.test(await button.textContent()), 'and sees it through', 90000);
    await until(async () => /Made \d+ LaTeX drawings|Stopped/.test(await toast()), 'and says how it ended');
    assert(true, 'a job belongs to the server: the page that began it may be gone');

    eq(errors, [], 'no page error');
    await page.close();
    if (hubPage) await hubPage.close();
  } finally {
    proc.kill();
    await sleep(100);
  }
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  for (const mode of modes) await suite(browser, mode);
  console.log(`\nMake drawings of N shown passed (${modes.join(' + ')}: ${passed} checks)`);
} finally {
  await browser.close();
}
