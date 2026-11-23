// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of "no page tells anyone to type a command" (TO-DO §5, a0.6.3 lane J1), on the real pages:
//   a) the reader (built here from the English fixture, served by a small server of the test's own):
//      the narration panel that cannot reach the server says to open the page from Parseh, not
//      "served by serve.py" (5.2); without rapidfuzz it links to Settings > Updating Parseh, with no
//      pip command (5.3); the build button's title names no ./build.sh
//   b) Settings > Updating Parseh lists the missing packages, and Add what is missing adds them (5.3, 5.13)
//   c) the library page's "write the list again" writes books/index.html again (5.5)
//   d) Settings > Reading help: Chinese's Word models row, Get it, the job, Installed (5.10)
//   e) the video index and a channel's page: no youtube/PROMPT.md, the Add card on both (5.14)
//   b-e run against Parseh's REAL handler (tests/no_terminal_harness.py: temporary stores; the
//   package install and the model download are faked, see there).
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/no_terminal.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const has = (t, p, m) => assert(t.includes(p), `${m} (wanted ${JSON.stringify(p)})`);
const hasnt = (t, p, m) => assert(!t.includes(p), `${m} (did not want ${JSON.stringify(p)})`);
const COMMAND = /python3? [\w/.-]+\.py|\.\/(?:serve|build)\.sh|pip install|conda run|PROMPT\.md/;
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(80);
  }
}
async function py(code, ...args) {
  const o = await new Deno.Command(PY, {args: ['-c', code, ...args], stdout: 'piped', stderr: 'piped'}).output();
  if (!o.success) throw Error(td.decode(o.stderr) || td.decode(o.stdout));
  return td.decode(o.stdout);
}

/* ---------------- a) the reader ---------------- */
const TMP = await Deno.makeTempDir({prefix: 'parseh-no-terminal-'});
const BOOK = `${TMP}/books/english/mini-en`;
await py(`
import os, shutil, subprocess, sys
d = sys.argv[1]
os.makedirs(os.path.dirname(d), exist_ok=True)
shutil.copytree('tests/fixtures/books/english/mini-en', d, ignore=shutil.ignore_patterns('reader'))
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', d], capture_output=True, text=True)
if r.returncode: raise SystemExit(r.stderr or r.stdout)
`, BOOK);
const MIME = {html: 'text/html', js: 'text/javascript', css: 'text/css', json: 'application/json'};
let STATUS = null;
const files = Deno.serve({port: 0, onListen: () => {}}, async req => {
  const path = decodeURIComponent(new URL(req.url).pathname);
  if (path.endsWith('/__narration/status'))
    return STATUS ? Response.json(STATUS) : new Response('', {status: 599});
  if (path.endsWith('/__lookup')) return Response.json({ok: true, have: false});
  const at = path.startsWith('/lib/') ? root + path : path;
  try {
    return new Response(await Deno.readFile(at), {headers: {'Content-Type': MIME[at.split('.').pop()] || 'application/octet-stream'}});
  } catch (_) { return new Response('no such file', {status: 404}); }
});
const READER = `http://127.0.0.1:${files.addr.port}${BOOK}/reader/index.html`;

/* ---------------- the harness ---------------- */
const proc = new Deno.Command(PY, {args: [root + '/tests/no_terminal_harness.py'], cwd: root,
  stdin: 'piped', stdout: 'piped', stderr: 'piped'}).spawn();
const errLog = [];
(async () => {
  const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) { const {value, done} = await r.read(); if (done) break; errLog.push(value); }
})();
const out = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
let first = '';
while (!first.includes('\n')) {
  const {value, done} = await out.read();
  if (done) throw Error('harness ended: ' + errLog.join(''));
  first += value;
}
if (!first.startsWith('READY ')) throw Error('harness did not start: ' + first + errLog.join(''));
const {port} = JSON.parse(first.slice(6).split('\n')[0]);
const BASE = `http://127.0.0.1:${port}`;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN')});
const errors = [];
try {
  const page = await browser.newPage();
  page.on('pageerror', e => { errors.push(e.message); console.log('PAGE ERROR', e.message); });

  console.log('a) the reader');
  await page.goto(READER, {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('.sub');
  const buildTitle = await page.getAttribute('#buildbook', 'title');
  hasnt(buildTitle, 'build.sh', 'the build button\'s title names no ./build.sh');
  // the server does not answer the panel at all: what does it say?
  await page.route('**/__narration/status', r => r.abort('connectionrefused'));
  await page.click('#narr');
  const nwarn = await until(async () => {
    const t = await page.textContent('#nwarn');
    return t && t.trim() ? t : false;
  }, 'the panel says it cannot reach the server');
  has(nwarn, 'this panel needs the page opened from Parseh while it runs', 'it says to open the page from Parseh (5.2)');
  hasnt(nwarn, 'serve.py', 'and names no serve.py');
  await page.unroute('**/__narration/status');
  STATUS = {
    ok: true, slug: 'mini-en', title_latin: 'mini-en',
    audio: {declared: null, path: null, exists: false, bytes: 0},
    transcript: {declared: null, path: null, exists: false, bytes: 0},
    narrations: [], labels: [], timings: {subs: 0, manual: 0, audio: null},
    candidates: [], built: true, subs: 0, timed: 0, audio_dir: 'books/english/mini-en/audio/',
    tools: {rapidfuzz: false, ffmpeg: true, python: 'python3'},
  };
  await page.reload({waitUntil: 'domcontentloaded'});
  await page.waitForSelector('.sub');
  await page.click('#narr');
  await until(async () => (await page.textContent('#nnote') || '').includes('rapidfuzz'), 'the note on rapidfuzz');
  const note = await page.textContent('#nnote');
  has(note, 'rapidfuzz is not installed: align still runs', 'without rapidfuzz the panel says so (5.3)');
  assert(!COMMAND.test(note), `and names no command: “${note.trim()}”`);
  const door = await page.getAttribute('#nnote a', 'href');
  assert(door === '/settings/update/#packages', `it links to Settings > Updating Parseh (${door})`);

  console.log('b) Settings > Updating Parseh adds the missing packages');
  await page.goto(BASE + '/settings/update/', {waitUntil: 'domcontentloaded'});
  const list = await page.textContent('[data-pk-list]');
  has(list, 'rapidfuzz', 'rapidfuzz is listed as missing');
  has(list, 'zstandard', 'zstandard is listed as missing (5.13)');
  await page.click('[data-pk-add]');
  await until(async () => await page.isDisabled('[data-pk-add]'), 'the button waits while it runs', 5000);
  await until(async () => (await page.textContent('[data-pk-said]') || '').includes('Everything is here now'),
              'the packages are added');
  has(await page.textContent('[data-pk-log]'), 'Successfully installed rapidfuzz zstandard', 'what it did is shown');
  await page.reload({waitUntil: 'domcontentloaded'});
  assert(await page.locator('[data-pk]').count() === 0, 'with nothing missing, the section is gone');

  console.log('c) the library page writes its list again');
  // books/index.html is a built file, never committed: the one here may be any older Parseh's,
  // so it goes, and the server writes it on the first request, as it does on a fresh copy
  try { await Deno.remove(root + '/books/index.html'); } catch (_) { /* never written */ }
  await page.goto(BASE + '/books/', {waitUntil: 'domcontentloaded'});
  const foot = await page.textContent('footer.idx');
  assert(!COMMAND.test(foot), `the foot names no command: “${foot.replace(/\s+/g, ' ').trim()}”`);
  // a page older than the shelf: what the button must replace
  const index = root + '/books/index.html';
  const fresh = await Deno.readTextFile(index);
  await Deno.writeTextFile(index, fresh.replace('<h1 class="idx">Books</h1>', '<h1 class="idx">STALE</h1>'));
  await page.reload({waitUntil: 'domcontentloaded'});
  has(await page.textContent('h1'), 'STALE', 'the stale page is what is served');
  await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}), page.click('footer [data-relist]')]);
  has(await page.textContent('h1'), 'Books', 'write the list again wrote it afresh, and the page reloaded (5.5)');

  console.log('d) Settings > Reading help fetches Chinese\'s word models');
  await page.goto(BASE + '/settings/reading-help/', {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('#rh [data-open], #rh [data-row]');
  const opener = page.locator('[data-open="zh"]');
  if (await opener.count()) await opener.first().click();
  const row = page.locator('[data-row="words:zh"]');
  await row.waitFor();
  has(await row.textContent(), 'Not yet', 'the Word models row says they are not here');
  await row.locator('[data-get="words:zh"]').click();
  await until(async () => (await row.textContent()).includes('Installed'), 'the models are fetched', 20000);
  const rowText = await row.textContent();
  has(rowText, 'the word model and the part-of-speech model', 'the row says what is here (5.10)');
  assert(!COMMAND.test(await page.textContent('#rh')), 'the page names no command');
  for (const name of ['spacy_ontonotes', 'postag']) {
    const there = await py(`import os,sys; print(os.path.isdir(sys.argv[1]))`, first.includes('"tmp"')
      ? JSON.parse(first.slice(6).split('\n')[0]).tmp + '/pkuseg/' + name : '');
    assert(there.trim() === 'True', `${name} is on disk where pkuseg looks`);
  }

  console.log('e) the video index and a channel\'s page');
  await page.goto(BASE + '/youtube/', {waitUntil: 'domcontentloaded'});
  let html = await page.content();
  hasnt(html, 'PROMPT.md', 'the index names no youtube/PROMPT.md');
  has(await page.textContent('footer.idx'), 'press Add a video above', 'its foot points at the Add card');
  const chan = await page.getAttribute('a.book[href*="/youtube/c/"]', 'href');
  await page.goto(BASE + chan, {waitUntil: 'domcontentloaded'});
  html = await page.content();
  hasnt(html, 'PROMPT.md', 'a channel\'s page names no youtube/PROMPT.md');
  assert(await page.locator('a.book.add[href="/youtube/add/"]').count() === 1, 'a channel\'s page has the Add card (5.14)');
  await page.click('a.book.add[href="/youtube/add/"]');
  await page.waitForURL(/\/youtube\/add\/$/);
  assert(true, 'and it opens the add page');

  assert(errors.length === 0, 'no page error: ' + errors.join(' | '));
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) {}
  await files.shutdown();
  await Deno.remove(TMP, {recursive: true});
}
console.log(`\n${passed} passed`);
Deno.exit(0);
