// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/sync_jobs_latex_page.mjs
//
// A STUDIO DOCUMENT'S PDF AND ITS LATEX DRAWINGS, LENT FROM THE PAGE (a0.7.0 lane J; lib/jobs.js,
// markdown/app/static/latexlend.js, lib/syncjobs.py "doc-build" and "latex-draw"), driven in Chromium.
// Two real installs paired over TLS (tests/sync_harness.py).  B has NO TeX: no engine on its PATH and
// latexdraw finds no compiler (SYNC_BUILDS_FAKE "no_tex").  A has its real TeX, which draws the
// block; A's XeLaTeX is a script writing a real one-page PDF where xelatex would (as in
// tests/test_sync_builds_end_to_end.py) -- the studio's build_pdf itself is the real one.
// On B's document page, "send" on:
//   1. the frame that says the drawing cannot be made here gets "Have a paired computer draw it";
//      pressed, lib/jobs.js offers "Send to <partner>", follows the job, and the page shows A's drawing;
//   2. Build PDF: the panel says why B cannot, "Send to <partner>", the job to "done", the page's own
//      toast "PDF built", and the PDF A built is on B's disk.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-jobs-latex-page-', dir: Deno.env.get('TMPDIR') || undefined});
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
function which(name) {
  for (const d of (Deno.env.get('PATH') || '').split(':')) {
    try { if (Deno.statSync(`${d}/${name}`).isFile) return `${d}/${name}`; } catch (e) { /* not here */ }
  }
  return null;
}
const ENGINES = ['xelatex', 'lualatex', 'pdflatex', 'xetex', 'luatex', 'pdftex'];
// this PATH with every TeX engine left out: a folder that holds one becomes, at its own place, a
// folder of links to everything else it holds (tests/test_sync_jobs_end_to_end.py path_without_tex)
function pathWithoutTex() {
  return (Deno.env.get('PATH') || '').split(':').map((d, i) => {
    if (!d || !ENGINES.some(t => { try { Deno.statSync(`${d}/${t}`); return true; } catch (e) { return false; } })) return d;
    const shadow = `${TMP}/notex-${i}`;
    Deno.mkdirSync(shadow);
    for (const e of Deno.readDirSync(d)) if (!ENGINES.includes(e.name)) Deno.symlinkSync(`${d}/${e.name}`, `${shadow}/${e.name}`);
    return shadow;
  }).join(':');
}
const FAKE = JSON.stringify({deadline: 60, caps_ttl: 1, timeout: 8});
function start(name, env) {
  const tree = `${TMP}/${name}`, port = freePort();
  Deno.mkdirSync(tree);
  const log = Deno.openSync(`${TMP}/${name}.log`, {write: true, create: true});
  const proc = new Deno.Command(PY, {args: ['tests/sync_harness.py', 'serve', tree, String(port)],
    env: {SYNC_JOBS_FAKE: FAKE, ...env}, stdout: 'piped', stderr: 'piped'}).spawn();
  proc.stdout.pipeTo(log.writable);
  proc.stderr.pipeTo(Deno.openSync(`${TMP}/${name}.err`, {write: true, create: true}).writable);
  return {name, tree, port, proc};
}
async function post(inst, route, body) {
  const r = await fetch(`http://localhost:${inst.port}${route}`, {method: 'POST',
    headers: {'Content-Type': 'application/json', Origin: `http://localhost:${inst.port}`},
    body: JSON.stringify(body || {})});
  return {status: r.status, j: await r.json().catch(() => ({}))};
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
function findDir(top, name) {
  for (const e of Deno.readDirSync(top)) {
    if (!e.isDirectory) continue;
    if (e.name === name) return `${top}/${name}`;
    const got = findDir(`${top}/${e.name}`, name);
    if (got) return got;
  }
  return null;
}

const fakebin = `${TMP}/fakebin`;
Deno.mkdirSync(fakebin);
const realXe = which('xelatex');
Deno.writeTextFileSync(`${fakebin}/xelatex`, `#!${PY}
import os
import sys
if "main.tex" not in sys.argv:
    os.execv("${realXe}", ["${realXe}"] + sys.argv[1:])
import pymupdf
d = pymupdf.open()
d.new_page().insert_text((72, 72), "built by A for the page test")
d.save("main.pdf")
open("main.log", "w").write("a stand-in for xelatex\\n")
`);
Deno.chmodSync(`${fakebin}/xelatex`, 0o755);
const A = start('A', {SYNC_BUILDS_FAKE: '{}', PATH: `${fakebin}:${Deno.env.get('PATH')}`});
const B = start('B', {SYNC_BUILDS_FAKE: JSON.stringify({no_tex: true}), PATH: pathWithoutTex()});
let browser;
try {
  await up(A); await up(B);
  const offer = (await post(A, '/settings/api/devices/pair-start')).j;
  const paired = await post(B, '/settings/api/devices/pair-enter',
    {code: offer.said, address: `127.0.0.1:${A.port}`, fingerprint: offer.fingerprint});
  check(paired.status === 200, 'B paired with A');
  write(`${B.tree}/config/sync/jobs-switches.json`, JSON.stringify({send: true}));
  write(`${A.tree}/config/sync/jobs-switches.json`, JSON.stringify({accept: true}));
  const md = '---\ntitle: Lent page\nlanguage: english\n---\n\n# Lent page\n\nSome words.\n\n' +
    '::::latex\n\\(a^2 + b^2 = c^2 + 11\\)\n::::\n';
  const made = await post(B, '/studio/api/docs', {markdown: md});
  const id = made.j.id || (made.j.meta || {}).id;
  check(made.status < 300 && id, 'a document with a LaTeX block made on B: ' + id);
  // the server's own lib/, as the toolbox serves it from its root (tests/sync_jobs_page.mjs does the same)
  try { Deno.symlinkSync(`${root}/lib`, `${B.tree}/root/lib`); } catch (e) { /* there */ }

  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN')});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('response', r => {
    if (r.status() >= 400 && !(r.status() === 409 && /\/(build|lend)(\?|$)/.test(r.url()))) errors.push(r.status() + ' ' + r.url());
  });
  const res = await page.goto(`http://localhost:${B.port}/studio/doc/${id}`);
  check(res && res.status() === 200, 'B\'s document page is served: ' + (res && res.status()));

  // 1. the drawing nobody made
  const frame = page.locator('.latex-fail[data-latex-kind="compiler"]');
  await frame.first().waitFor({timeout: 60000});
  check(/does not have/.test(await frame.first().innerText()), 'the frame says this computer cannot make it');
  const lend = page.locator('[data-latex-lend]');
  await lend.first().waitFor({timeout: 20000});
  check(/Have a paired computer draw it/.test(await lend.first().innerText()),
        'the frame offers: ' + await lend.first().innerText());
  await lend.first().click();
  const panel = page.locator('.pj-panel');
  await panel.waitFor({timeout: 20000});
  check(/cannot be made here/.test(await panel.innerText()), 'the panel says why: ' + (await panel.innerText()).replace(/\s+/g, ' '));
  const go = panel.locator('button.pj-go');
  check((await go.count()) === 1 && /Send to /.test(await go.innerText()), 'one "Send to <partner>" button');
  const seen = new Set();
  const nav = page.waitForEvent('framenavigated', {timeout: 120000});
  await go.click();
  const t0 = Date.now();
  let reloaded = false;
  nav.then(() => { reloaded = true; }, () => {});
  while (!reloaded && Date.now() - t0 < 120000) {
    const t = await panel.isVisible().catch(() => false) ? await panel.locator('.pj-say').innerText().catch(() => '') : '';
    if (t) seen.add(t.replace(/:.*$/, ''));
    await sleep(200);
  }
  console.log('  the panel said:', [...seen].join(' | '));
  check(reloaded, 'the page opened again once the job was done');
  check([...seen].some(s => /^(waiting for a computer|on )/.test(s)), 'the panel followed the job');
  await page.waitForLoadState('load');
  const img = page.locator('#sheet img[src*="/latex/"]');
  await img.first().waitFor({timeout: 30000}).catch(() => {});
  check((await img.count()) === 1 && (await page.locator('.latex-fail').count()) === 0,
        'the page shows the drawing A made, and no frame');
  const src = await img.first().getAttribute('src').catch(() => '');
  const svg = await (await fetch(`http://127.0.0.1:${B.port}${src}`)).text().catch(() => '');
  check(/<svg/.test(svg), 'its SVG is served by B: ' + src);
  check((await lend.count()) === 0, 'nothing left to offer');

  // 2. Build PDF
  await page.click('#btn-build');
  await panel.waitFor({timeout: 20000});
  check(/XeLaTeX/.test(await panel.innerText()), 'the panel says why B cannot build: ' + (await panel.innerText()).replace(/\s+/g, ' '));
  await panel.locator('button.pj-go').click();
  const toast = page.locator('.toast', {hasText: 'PDF built'});
  await toast.first().waitFor({timeout: 120000}).catch(() => {});
  check((await toast.count()) > 0, 'the page\'s own toast: PDF built');
  const folder = findDir(`${B.tree}/library`, id);
  let pdf = '';
  try { pdf = new TextDecoder('latin1').decode(Deno.readFileSync(`${folder}/build/main.pdf`)); } catch (e) { /* none */ }
  check(pdf.startsWith('%PDF'), "the PDF A built is on B's disk");
  const badge = await page.locator('#buildinfo').first().innerText().catch(() => '');
  check(/PDF ✓/.test(badge), 'the page shows the build: ' + badge.replace(/\s+/g, ' ').slice(0, 80));
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
