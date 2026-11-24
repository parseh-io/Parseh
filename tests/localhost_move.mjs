// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/localhost_move.mjs
//
// THIS COMPUTER ON PLAIN http://localhost, AND THE MOVE FROM https (a0.7.0,
// lib/localhttp.py), driven in real Chromium against the real serve.main()
// speaking TLS (no --http), with its certificate made in a temporary .tls/ and
// every STORE in a temporary tree:
//
//   a) http://localhost:<port>/ is served on the same port, and the page is a
//      secure context;
//   b) the OLD origin (https://localhost:<port>) -- whose localStorage is
//      seeded as a person's browser would have it -- is handed over on its
//      first navigation: every key it kept arrives on the new origin, a key
//      the new origin already had keeps its own value, the browser ends on
//      the address that was asked for, on http://localhost, and nothing is
//      said because nothing has to be done;
//   c) from then on the old address is a redirect (the Secure cookie);
//   d) an installed app (the old origin's window in standalone display) is
//      told, once, to install again, and its "Go on" goes on;
//   e) a script left on the old origin (not a navigation) is still answered.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-localhost-move-'});
const td = new TextDecoder();
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

const SERVE = String.raw`
import os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
(tmp / 'config').mkdir(parents=True, exist_ok=True)
import prefs, network, offline, latexthemes, prompts
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
prompts.STORE = str(tmp / 'config' / 'prompts.json')
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
import serve
serve.TLS_DIR = str(tmp / 'tls')
sys.argv = ['serve.py', '--local', port]
serve.main()
`;

let hub = null, browser = null;
const log = [];
try {
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-u', '-c', SERVE, TMP, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  for (const s of [hub.stdout, hub.stderr])
    (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
  const NEW = `http://localhost:${port}`, OLD = `https://localhost:${port}`;
  for (const t = Date.now();;) {
    try { const r = await fetch(`http://127.0.0.1:${port}/settings/api/ping`); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the server did not start:\n' + log.join(''));
    await sleep(250);
  }
  check(/http:\/\/localhost:\d+\/\s+\(this machine\)/.test(log.join('')),
        'the server prints this computer\'s address as http://localhost');
  check(!/each browser warns once/.test(log.join('')), 'and no longer says every browser warns');
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});

  // ---- a) and b)
  console.log('\na) b) the first visit to the old address');
  const ctx = await browser.newContext({ignoreHTTPSErrors: true, storageState: {cookies: [], origins: [
    {origin: OLD, localStorage: [
      {name: 'bk_rate', value: '1.25'},
      {name: 'bk_edits:/books/fa/a-book/', value: '{"p1s2":{"t0":1.5,"t1":3.25}}'},
      {name: 'bk_pos:/books/fa/a-book/', value: '{"i":42}'},
      {name: 'parseh_theme', value: 'dark'}]},
    {origin: NEW, localStorage: [{name: 'parseh_theme', value: 'light'}]}]}});
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(OLD + '/settings/?from=bookmark');
  await page.waitForURL(u => u.href.startsWith(NEW + '/settings/'), {timeout: 20000}).catch(() => {});
  check(page.url() === NEW + '/settings/?from=bookmark', 'it ends on the same page at http://localhost (' + page.url() + ')');
  check(await page.evaluate(() => window.isSecureContext), 'http://localhost is a secure context');
  const got = await page.evaluate(() => ({rate: localStorage.getItem('bk_rate'),
    edits: localStorage.getItem('bk_edits:/books/fa/a-book/'), pos: localStorage.getItem('bk_pos:/books/fa/a-book/'),
    theme: localStorage.getItem('parseh_theme'), moved: localStorage.getItem('parseh_moved_from')}));
  check(got.rate === '1.25', 'a setting arrives');
  check(got.edits === '{"p1s2":{"t0":1.5,"t1":3.25}}', 'unsaved timing edits arrive');
  check(got.pos === '{"i":42}', 'a reading place arrives');
  check(got.theme === 'light', 'a key the new origin already had keeps its own value');
  check(!!got.moved, 'the new origin notes the move');
  const cookies = await ctx.cookies(OLD);
  const moved = cookies.find(c => c.name === 'parseh_moved_' + port);
  check(!!moved && moved.secure, 'the old origin carries a Secure "moved" cookie');

  // ---- c)
  console.log('\nc) later visits to the old address');
  const seen = [];
  page.on('response', r => seen.push([r.status(), r.url()]));
  await page.goto(OLD + '/youtube/?a=b');
  check(page.url() === NEW + '/youtube/?a=b', 'the old address goes straight on (' + page.url() + ')');
  check(seen.some(([s, u]) => s === 302 && u.startsWith(OLD + '/youtube/')), 'by a 302 from the old origin');
  check(!seen.some(([s, u]) => u.includes('/__move')), 'with no hand-over page this time');

  // ---- e)
  console.log('\ne) a script left on the old origin');
  const api = await ctx.request.get(OLD + '/settings/api/ping');
  check(api.status() === 200 && (await api.text()).includes('ok'), 'is still answered over TLS');
  const plain = await ctx.request.get(`http://127.0.0.1:${port}/settings/api/ping`);
  check(plain.status() === 200, 'and plain http at 127.0.0.1 is served too');
  await ctx.close();

  // ---- d)
  console.log('\nd) an app installed from the old address');
  const ctx2 = await browser.newContext({ignoreHTTPSErrors: true, storageState: {cookies: [], origins: [
    {origin: OLD, localStorage: [{name: 'bk_gap', value: '0.8'}]}]}});
  await ctx2.addInitScript(() => {
    const real = window.matchMedia.bind(window);
    window.matchMedia = q => /display-mode:\s*standalone/.test(q)
      ? {matches: true, media: q, onchange: null, addEventListener() {}, removeEventListener() {},
         addListener() {}, removeListener() {}, dispatchEvent() { return false; }} : real(q);
  });
  const app = await ctx2.newPage();
  await app.goto(OLD + '/?mode=mobile');
  await app.waitForURL(u => u.href.startsWith(NEW + '/__move'), {timeout: 20000}).catch(() => {});
  await app.waitForFunction(() => { const e = document.getElementById('app'); return e && !e.hidden; },
                            null, {timeout: 10000}).catch(() => {});
  const said = await app.evaluate(() => ({app: !document.getElementById('app').hidden,
    text: document.getElementById('app').textContent, n: document.getElementById('carried').textContent,
    gap: localStorage.getItem('bk_gap')}));
  check(said.app && /install Parseh again from/i.test(said.text) && said.text.includes(NEW + '/'),
        'it is told, in plain words, to install the app again from ' + NEW + '/');
  check(said.n === '1' && said.gap === '0.8', 'and what it kept was carried all the same');
  await app.click('#go');
  await app.waitForURL(u => !u.href.includes('/__move'), {timeout: 10000}).catch(() => {});
  // the hub takes ?mode=mobile off the address once it has set the mode (lib/parseh.js)
  const mode = await app.evaluate(() => localStorage.getItem('parseh_mode'));
  check(app.url() === NEW + '/' && mode === 'mobile',
        '"Go on" goes on to the page asked for, /?mode=mobile (' + app.url() + ', mode ' + mode + ')');
  await ctx2.close();
  check(errors.length === 0, 'no page error' + (errors.length ? ': ' + errors.join(' | ') : ''));
} catch (e) {
  failed.push(String(e && e.stack || e));
  console.log('ERROR', e);
} finally {
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); } catch (_) {} try { await hub.status; } catch (_) {} }
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
console.log(`\n${passed} passed, ${failed.length} failed`);
if (failed.length) { console.log(failed.map(f => '  - ' + f).join('\n')); Deno.exit(1); }
