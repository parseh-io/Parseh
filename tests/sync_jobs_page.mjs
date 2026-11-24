// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/sync_jobs_page.mjs
//
// A JOB LENT FROM A PAGE (a0.7.0, lane D; lib/jobs.js, lib/syncjobs.py), driven in Chromium.
// Two real installs paired over TLS (tests/sync_harness.py; THE BUILD IS FAKED there by
// SYNC_JOBS_FAKE, and the capabilities set: A can build a PDF, B cannot).  On B, with "send"
// on, a book card's build button is pressed through the real lib/parseh.js: the panel says
// why B cannot and offers "Send to A"; pressed, it follows the job to "done", the page's own
// toast says "built", and the PDF A built is on B's disk.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-jobs-page-'});
let passed = 0;
const failed = [];
const check = (v, m) => { if (v) { passed++; console.log('  ok', m); } else { failed.push(m); console.log('  FAIL', m); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
const FAKE = {deadline: 20, caps_ttl: 1, timeout: 4, run_seconds: 3};
function start(name, caps) {
  const tree = `${TMP}/${name}`, port = freePort();
  Deno.mkdirSync(tree);
  const log = Deno.openSync(`${TMP}/${name}.log`, {write: true, create: true});
  const proc = new Deno.Command(PY, {args: ['tests/sync_harness.py', 'serve', tree, String(port)],
    env: {SYNC_JOBS_FAKE: JSON.stringify({...FAKE, caps})}, stdout: log.writable ? 'piped' : 'null',
    stderr: 'piped'}).spawn();
  proc.stdout.pipeTo(log.writable);
  proc.stderr.pipeTo(Deno.openSync(`${TMP}/${name}.err`, {write: true, create: true}).writable);
  return {name, tree, port, proc};
}
async function post(inst, route, body) {
  const r = await fetch(`http://127.0.0.1:${inst.port}${route}`, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
  return {status: r.status, j: await r.json()};
}
async function up(inst) {
  for (let i = 0; i < 300; i++) {
    try { const r = await post(inst, '/settings/api/devices/state'); if (r.status === 200 && r.j.this.key) return; }
    catch (e) { /* not yet */ }
    await sleep(300);
  }
  throw new Error(inst.name + ' never came up: ' + TMP);
}
const write = (p, t) => { Deno.mkdirSync(p.replace(/\/[^/]*$/, ''), {recursive: true}); Deno.writeTextFileSync(p, t); };

const A = start('A', {latex: true, reader: true});
const B = start('B', {latex: false, reader: true});
let browser;
try {
  await up(A); await up(B);
  const offer = (await post(A, '/settings/api/devices/pair-start')).j;
  const paired = await post(B, '/settings/api/devices/pair-enter',
    {code: offer.said, address: `127.0.0.1:${A.port}`, fingerprint: offer.fingerprint});
  check(paired.status === 200, 'B paired with A');
  write(`${B.tree}/config/sync/jobs-switches.json`, JSON.stringify({send: true}));
  write(`${A.tree}/config/sync/jobs-switches.json`, JSON.stringify({accept: true}));
  const book = `${B.tree}/root/books/italian/storia`;
  write(`${book}/book.json`, JSON.stringify({title: 'Storia', language: 'italian'}));
  write(`${book}/ch1.tex`, 'Una storia.\n');
  // the server's own lib/, as the toolbox serves it from its root (tests/activity.mjs does the same)
  Deno.symlinkSync(`${root}/lib`, `${B.tree}/root/lib`);
  // a card as the library page draws it (lib/make_index.py), on a page that loads lib/parseh.js
  write(`${B.tree}/root/books/cards.html`, '<!doctype html><meta charset="utf-8"><title>cards</title>' +
    '<script src="/lib/parseh.js"></script><body><div class="card">Storia ' +
    '<button type="button" class="card-build" data-build="/books/italian/storia/__build" ' +
    'data-what="Storia">Build</button></div></body>');

  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN')});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const T0 = Date.now(), trail = [];
  let reloads = 0;
  page.on('framenavigated', f => { if (f === page.mainFrame()) reloads++; });
  page.on('request', q => { if (/__jobs|__build/.test(q.url())) trail.push('>' + ((Date.now() - T0) / 1000).toFixed(1) + ' ' + q.url().replace(/^.*\//, '')); });
  page.on('response', r => { if (/__jobs|__build/.test(r.url())) r.text().then(t => trail.push('<' + ((Date.now() - T0) / 1000).toFixed(1) + ' ' + t.slice(0, 60)), () => {}); });
  page.on('response', r => { if (r.status() >= 400 && !(r.status() === 409 && /__build$/.test(r.url()))) errors.push(r.status() + ' ' + r.url()); });
  const res = await page.goto(`http://localhost:${B.port}/books/cards.html`);
  check(res && res.status() === 200, 'the page with the card is served: ' + (res && res.status()));
  await page.waitForFunction(() => !!window.ParsehJobs, null, {timeout: 15000})
    .catch(e => { throw new Error(e.message + ' -- ' + errors.join(' / ') + ' -- ' +
      'scripts'); });
  check(true, 'lib/jobs.js loaded beside lib/parseh.js');
  await page.click('button.card-build');
  const panel = page.locator('.pj-panel');
  await panel.waitFor({timeout: 20000});
  const said = await panel.innerText();
  check(/LaTeX/.test(said), 'the panel says why B cannot: ' + said.replace(/\s+/g, ' '));
  const send = panel.locator('button.pj-go');
  check((await send.count()) === 1 && /Send to /.test(await send.innerText()), 'one "Send to <partner>" button');
  await send.click();
  const seen = new Set();
  const t0 = Date.now();
  let pdf = false;
  while (Date.now() - t0 < 90000) {
    const t = await panel.isVisible() ? (await panel.locator('.pj-say').innerText().catch(() => '')) : '';
    if (t) seen.add(t.replace(/:.*$/, ''));
    try { pdf = Deno.statSync(`${book}/storia.pdf`).isFile; } catch (e) { pdf = false; }
    if (pdf && (reloads > 1 || (seen.has('done') && trail.some(t => /^<.* \{"state": "done"/.test(t))))) break;
    await sleep(250);
  }
  if (Deno.env.get('JOBS_TRAIL')) console.log(trail.join('\n'));
  console.log('  the panel said:', [...seen].join(' | '));
  console.log('  __build/status:', JSON.stringify(await (await fetch(`http://127.0.0.1:${B.port}/books/italian/storia/__build/status`)).json()).slice(0, 400));
  check([...seen].some(s => /^on /.test(s)), 'the panel said "on <partner>"');
  // the card's build reloads the library page 0.9 s after its own poll says "done" (parseh.js
  // cardBuild), which may come before the panel's next look: either shows the end
  check(seen.has('done') || reloads > 1, 'the panel said "done", or the page reloaded on "done"');
  check(pdf && Deno.readTextFileSync(`${book}/storia.pdf`).startsWith('%PDF-1.5 built by'), "A's PDF is on B");
  // (the reload is cardBuild's answer to its own poll saying "done", so either proves it)
  check(reloads > 1 || trail.some(t => /^<.* \{"state": "done"/.test(t)),
        "the page's own poll of __build/status heard \"done\"");
  check(errors.length === 0, 'no error in the page: ' + errors.join(' / '));
} catch (e) {
  failed.push(String(e && e.stack || e));
  console.log('  FAIL', e);
} finally {
  if (browser) await browser.close();
  for (const i of [A, B]) { try { i.proc.kill('SIGTERM'); await i.proc.status; } catch (e) { /* gone */ } }
  if (!Deno.env.get('KEEP_JOBS_PAGE')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
console.log(`\n${passed} passed, ${failed.length} failed`);
Deno.exit(failed.length ? 1 : 0);
