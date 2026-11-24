// SPDX-License-Identifier: GPL-3.0-or-later
import {chromium} from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/making.mjs
//      SHOTS=<dir> saves a screenshot of every view it looks at (1280 and 390 px, the three themes)
//      PARSEH_KEEP=1 keeps the temporary tree, to read what was written
//
// A BOOK MADE BY AN AGENT, IN PLACE (a0.4.2, TO-DO §8.40), driven end to end in a real browser
// against a scratch install -- a copy of this checkout that is a whole Parseh of its own
// (tests/making_agent.py scratch), so that nothing the owner has is ever in reach.  The agent is
// a scripted stand-in (tests/making_agent.py) that calls Parseh's real tools with Parseh's real
// Python, batch by batch, while the page is watched.  Every action is a person's: the add page's
// card, its fields and its buttons, the library, the reader's header, sheets and pencil.
//
//  a) THE PAGE, way 3 of /books/add/: no terminal left in it (no script to copy, no setup, no
//     return); the original is a file picker; Learn from is "none"; the box about the person's own
//     books is off; the folder's button says why it cannot be pressed; the instructions shown are
//     what the copy button copies, to the letter, and are what the folder gets; making the folder
//     writes the whole folder, on this computer, from an uploaded file -- and the page says where,
//     copies the path, opens the folder (the file manager stood in for) and says what to tell the
//     agent; a second press names the slug that is taken
//  b) THE LIBRARY: the book is there at once, marked being made, and its card moves as the agent
//     works, without a reload
//  c) THE READER, while the agent works: a button in the header and a panel that moves by itself
//     (source recovered, chapter table, batch N of M, the tools' words); the page is said to be
//     older than the newest batch, and look at it now brings it (the panel comes back open); what
//     is still to come is said under the last batch; the PDF of these chapters is made beside the
//     book and never as main.pdf
//  d) NO EDITING WHILE IT IS MADE: the pencil says why, the chunk sheet shows the chunk and shuts
//     what writes it, offers ask about this chunk -- written to ASKS.md with the chunk's address
//     and text -- and the server refuses the doors whatever the page does
//  e) STEERING: what to change from now on, written to ASKS.md; the agent reads it before its next
//     batch and says in NOTES.md what it did; Parseh updated during the making is said
//  f) ANOTHER DEVICE: on a phone (390 px, the mobile interface) the panel is read and an ask
//     written; every device let in does all of it but open the folder, which is the computer's own
//     act: refused in a sentence that says why, with the path to copy, and no file manager started
//  g) NO SH (Windows): the PDF of these chapters is said not to be available and the reader is;
//     look at it now still builds it
//  h) FINISH: a paragraph that no longer reproduces its source stops it, in words, and the making
//     goes on; then, both clean, the making ends: the book is an ordinary book (its pencil edits
//     the .tex, its card says nothing), its bundle carries the original and annot/ and none of the
//     agent's files, and the format number is 3
//  i) A RIGHT-TO-LEFT BOOK: Persian, made from the page (its title box reads right to left, the folder
//     is on the Persian shelf, book.json keeps the letters), read on a phone before it has a chapter
//     at all, worked by the stand-in, watched in the panel, its chunk shut with the ask offered, and
//     an ask in Persian reaches ASKS.md as written
//  k) THE TEXT IN PARTS, from another origin (a phone let in, on a computer with no TeX): it makes the
//     folder from a file and is shown the path and why there is nothing to open; gives the agent part
//     2 between two batches (a file, a label, where it goes); the scripted stand-in takes it BEFORE its
//     next batch with lib/sourcetext.py, numbered on, and writes `sources`; Finish says what it waits
//     for and a second press passes it; "this is all the text" makes the agent end and not wait; a
//     phone finishes the book; the add page reopens it and gives it a third part; and a PDF with its
//     pages is sent onto a book nobody is making, as blank chunks
//  j) and last: no page threw, and the owner's books/ and config/ are as they were
// and every view it looks at (1280 and 390 px, light and dark) is measured too: the page does not
// scroll sideways and the making panel lies inside the window
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-making-'});
const INSTALL = TMP + '/install';
const td = new TextDecoder();
const sleep = ms => new Promise(r => setTimeout(r, ms));
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));

async function run(cmd, args, opt = {}) {
  const o = await new Deno.Command(cmd, {args, cwd: root, stdout: 'piped', stderr: 'piped', ...opt}).output();
  return {code: o.code, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
async function py(args) {
  const r = await run(PY, args);
  if (r.code) throw Error(args.join(' ') + ' -> ' + (r.err || r.out));
  return r.out.trim();
}
const agent = (...args) => py(['tests/making_agent.py', ...args]);
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
// a wait for some text that a page in the middle of a reload (no <main> yet, no panel yet) does not break
const waitText = (pg, sel, re, timeout = 30000) => pg.waitForFunction(
  ([s, src, fl]) => { const e = document.querySelector(s); return !!e && new RegExp(src, fl).test(e.textContent); },
  [sel, re.source, re.flags], {timeout});
const waitNoText = (pg, sel, re, timeout = 30000) => pg.waitForFunction(
  ([s, src, fl]) => { const e = document.querySelector(s); return !!e && !new RegExp(src, fl).test(e.textContent); },
  [sel, re.source, re.flags], {timeout});
// the panel comes back open after a reload when it was open: give that its moment, and open it by the
// button only if it is not
async function openPanel(pg, layout = 'browser') {
  await pg.waitForSelector(`.mk-btn[data-layout=${layout}]`);
  await pg.evaluate(() => window.ParsehMaking.refresh());
  await sleep(300);
  if (!(await pg.$('#mkbox:not([hidden])'))) await pg.click(`.mk-btn[data-layout=${layout}]`);
  await pg.waitForSelector('#mkbox:not([hidden])');
}
// a view in the widths and themes the work is looked at in: 1280 and 390 px, light and dark.
// In each of them nothing this work draws may lie past the window's edge -- the making button,
// the panel, the words under the last batch, the locked chunk sheet with its note and its ask --
// and the library and the add page, which are wholly this work's, must not scroll sideways
// either: a phone's screen is the one nobody can resize.  A reader's own layout is not what this
// suite is about, so there only what the making adds is measured.  The screenshots are taken
// only when SHOTS says where to put them.
async function views(pg, name, {full = false} = {}) {
  // a tab that is not in front is not drawn, and a screenshot of it waits for a frame that never comes
  await pg.bringToFront();
  const was = pg.viewportSize();
  const release = await quietOthers(pg);
  for (const [w, h] of [[1280, 900], [390, 844]])
    for (const theme of ['light', 'dark']) {
      await pg.setViewportSize({width: w, height: h});
      await pg.evaluate(t => Parseh.theme.set(t), theme);
      await sleep(350);
      const fit = await pg.evaluate(() => {
        const de = document.documentElement, cw = de.clientWidth, past = [];
        const whole = !/\/reader\//.test(location.pathname);
        for (const sel of ['.mk-btn', '#mkbox', '#mktocome', '#chbox', '#chbox .mk-chnote', '#chbox .mk-ask'])
          for (const e of document.querySelectorAll(sel)) {
            const r = e.getBoundingClientRect(), st = getComputedStyle(e);
            if (!r.width || st.visibility === 'hidden' || st.display === 'none') continue;
            if (r.right > cw + 1 || r.left < -1) past.push(sel + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
          }
        if (whole && de.scrollWidth > cw + 1) {
          past.push('the page is ' + de.scrollWidth + ' wide');
          for (const e of document.querySelectorAll('body *')) {
            const r = e.getBoundingClientRect(), st = getComputedStyle(e);
            if (r.width && r.right > cw + 1 && st.position !== 'fixed' && st.visibility !== 'hidden' && st.display !== 'none')
              past.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' to ' + Math.round(r.right));
            if (past.length > 5) break;
          }
        }
        return {cw, past};
      });
      assert(!fit.past.length, `${name} at ${w} px, ${theme}: nothing lies past the window's edge (${fit.cw} wide` +
             `${fit.past.length ? '; past it: ' + fit.past.join(', ') : ''})`);
      if (!SHOTS) continue;
      try {
        await pg.screenshot({path: `${SHOTS}/${name}-${w}-${theme}.png`, fullPage: full, timeout: 20000});
      } catch (e) {
        console.log('  screenshot', name, w, theme, 'failed:', e.message.split('\n')[0],
                    JSON.stringify(await pg.evaluate(() => [document.readyState, Math.round(performance.now()), document.hidden]).catch(x => String(x))));
        throw e;
      }
    }
  await pg.evaluate(() => Parseh.theme.set('light'));
  await pg.setViewportSize(was);
  await sleep(250);
  await release();
}
// THE OTHER PAGES OF THIS BROWSER STAY QUIET while the theme is changed on one: each follows it and writes it back
// to the server, and two writes at once are more than lib/prefs.py's one temporary file takes (a 400 from
// /__prefs, logged as an error) -- nothing this suite is about.  -> the function that lets them speak again
async function quietOthers(pg) {
  const quiet = r => r.request().method() === 'POST'
    ? r.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'}) : r.continue();
  const others = pg.context().pages().filter(p => p !== pg);
  for (const p of others) await p.route('**/__prefs', quiet);
  return async () => { for (const p of others) await p.unroute('**/__prefs', quiet); };
}
const shot = async (page, name) => { if (SHOTS) { await page.bringToFront(); await page.screenshot({path: `${SHOTS}/${name}.png`}); } };
async function exists(p) { try { await Deno.stat(p); return true; } catch { return false; } }
async function tree(dir) {
  const out = [];
  for await (const e of Deno.readDir(dir)) {
    if (e.isDirectory) for (const f of await tree(dir + '/' + e.name)) out.push(e.name + '/' + f);
    else out.push(e.name);
  }
  return out.sort();
}

// what is the owner's, which nothing here may touch: their digests now, compared at the end
const OWN = String.raw`
import hashlib, json, os, sys
out = {}
for top in ('config', 'books'):
    for d, _, files in os.walk(top):
        for f in files:
            p = os.path.join(d, f)
            out[p] = hashlib.md5(open(p, 'rb').read()).hexdigest()
print(json.dumps(out, sort_keys=True))
`;
const ownBefore = await py(['-c', OWN]);
// the PDF of a few chapters and the full build are LaTeX's: where there is none the suite says so and
// checks what such a machine does instead (Finish builds the reader and leaves the PDF)
const HAS_TEX = (await run('which', ['lualatex'])).code === 0;
if (!HAS_TEX) console.log('  note: no lualatex on this machine -- the draft PDF and the full build are not driven');

/* ---------------- the scratch install, the original, the servers ---------------- */
await agent('scratch', INSTALL);
const MODEL = root + '/tests/fixtures/books/english/mini-en';
await agent('original', MODEL, TMP + '/the-clock.txt');
const ORIGINAL_TEXT = await Deno.readTextFile(TMP + '/the-clock.txt');
assert(ORIGINAL_TEXT.trim().split(/\n\s*\n/).length === 2, 'the original is two paragraphs');
const BOOK = INSTALL + '/books/english/the-clock';

const logs = [];
const servers = [];
async function serve(extra = [], env = {}) {
  const port = freePort();
  const p = new Deno.Command(PY, {
    args: ['tests/making_agent.py', 'serve', INSTALL, String(port), ...extra], cwd: root,
    env: {PARSEH_PYTHON: PY, HOME: Deno.env.get('HOME') || '', TMPDIR: Deno.env.get('TMPDIR') || '/tmp',
          PATH: Deno.env.get('PATH') || '', ...env},
    clearEnv: true, stdout: 'piped', stderr: 'piped'}).spawn();
  drain(p.stdout, logs); drain(p.stderr, logs);
  servers.push(p);
  for (let i = 0; i < 150; i++) {
    try { const r = await fetch(`http://127.0.0.1:${port}/__activity`); await r.body?.cancel(); if (r.ok) return `http://127.0.0.1:${port}`; }
    catch { /* not yet */ }
    await sleep(200);
  }
  throw Error('the server did not come up: ' + logs.join('').slice(-800));
}
const B = await serve();                                   // this computer
const PHONE = await serve(['--phone']);                    // a phone let in over the Wi-Fi
const NOSH = await serve([], {PATH: '/nonexistent'});      // a machine with no sh: Windows

/* ---------------- the browser ---------------- */
const errors = [];
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
async function context(base, opt = {}) {
  const c = await browser.newContext({viewport: {width: 1280, height: 900}, ...opt});
  await c.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: base});
  return c;
}
function watch(page, label) {
  page.on('pageerror', e => errors.push({label, text: 'pageerror: ' + e.message, url: ''}));
  page.on('console', m => {
    const u = m.location().url || '';
    // the reader asks for a few optional files a temporary book has none of
    if (m.type() === 'error' && !/favicon|\/timings\.json|\/mt\//.test(u))
      errors.push({label, text: m.text(), url: u});
  });
}
// the refusals this suite asks for on purpose, each of which the browser logs as an error: the lock on
// editing, the doors of a phone that are the computer's, the draft on a machine with no shell.  Each
// must have happened -- a refusal that never came is a lock that was never tried
const DELIBERATE = [['computer', 409, /\/reader\/__edit\/chunk$/],
  ['phone', 403, /\/__making\/open$/], ['phone', 409, /\/__making\/finish$/],
  ['no sh', 409, /\/reader\/__build$/]];
const clip = page => page.evaluate(() => navigator.clipboard.readText());
const inView = async (page, sel) => page.$eval(sel, e => {
  const r = e.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && r.left >= -1 && r.top >= -1 &&
         r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
});
// what is drawn at the middle of a control is the control (or something in it): nothing lies over it
const onTop = (page, sel) => page.$eval(sel, e => {
  const r = e.getBoundingClientRect();
  const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return !!at && (at === e || e.contains(at));
});
let failure = null;
try {
const ctx = await context(B);
const page = await ctx.newPage();
watch(page, 'computer');

/* ================= a) the page ================= */
console.log('a) the add page, way 3');
await page.goto(B + '/books/add/');
await page.click('.path[data-path="llm"]');
await page.waitForSelector('#lane-llm:not([hidden])');
const said = await page.evaluate(() => document.body.innerText);
for (const gone of [/terminal/i, /conda/i, /setup script/i, /return script/i, /PROMPT\.md/, /copy the setup/i,
                    /bring it back/i, /working folder/i])
  assert(!gone.test(said), 'no ' + gone + ' on the page');
assert(/Let an agent make it/.test(said), 'the card is the agent\'s');
eq(await page.$eval('#original', e => [e.type, e.accept]), ['file', '.pdf,.epub,.txt,application/pdf,application/epub+zip,text/plain'],
   'the original is a file picker, not a path typed on the server');
eq(await page.$eval('#ref', e => [e.value, e.options.length, e.options[0].textContent]), ['', 1, 'none'],
   'Learn from is "none", and there is no finished book to pick');
eq(await page.$eval('#examples', e => e.checked), false, 'the box about my own books is off');
assert(await page.$eval('#mkfolder', b => b.disabled), 'the folder\'s button cannot be pressed at first');
eq(await page.$eval('#mkfolder', b => b.title), 'the title comes first', '... and says why');
await page.selectOption('#lang', 'en');
await page.fill('#title', 'The Clock');
await page.fill('#title_latin', 'The Clock');
await page.fill('#author', 'a fable');
await page.fill('#author_latin', 'a fable');
eq(await page.$eval('#mkfolder', b => b.title), 'choose the original first', '... and then what is next');
await page.setInputFiles('#original', TMP + '/the-clock.txt');
await page.waitForFunction(() => !document.querySelector('#mkfolder').disabled);
assert(/the-clock\.txt, 1 kB/.test(await page.$eval('#originalnote', e => e.textContent)), 'the chosen file is named, with its size');
await page.fill('#pages', 'nine');
assert(/ignored/.test(await page.$eval('#pagesnote', e => e.textContent)), 'a page range that is no range is said to be ignored');
await page.fill('#pages', '');
// the instructions: what the row shows is what it copies is what the folder gets
await page.click('#ishow summary');
await page.waitForFunction(() => document.querySelector('#itext').textContent.length > 500);
const shown = await page.$eval('#itext', e => e.textContent);
await page.click('#icopy');
await sleep(400);
eq(await clip(page), shown, 'the instructions copied are exactly the ones shown');
assert(shown.includes(INSTALL + '/books/english/the-clock') && shown.includes(INSTALL + '/lib') &&
       /Write only inside this folder/.test(shown) && /ASKS\.md/.test(shown) && /making\.json/.test(shown),
       'they name this folder, this Parseh\'s tools, ASKS.md and making.json by their full paths');
await page.waitForFunction(() => /^about \d[\d,]* characters \(about \d[\d,]* tokens\)/.test(document.querySelector('#ilen').textContent),
                           null, {timeout: 20000});
assert(true, 'and say how long they are, before the copy: the row\'s one size line');
assert(await page.$eval('#instrmount .llmrow', e => !!e) && await inView(page, '#icopy'),
       'the controls are the LLM row\'s, in the window');
await views(page, 'C-add', {full: true});
// make the folder
await page.click('#mkfolder');
await page.waitForSelector('#mkcopy', {timeout: 60000});
const made = await page.$eval('.bigpath', e => e.textContent);
eq(made, BOOK, 'the page says where the folder is');
assert(/read AGENTS\.md and begin/.test(await page.$eval('#mkresult', e => e.textContent)), '... and what to tell the agent');
assert(!/start(s|ed) (an|the) agent/i.test((await page.$eval('#mkresult', e => e.textContent)).replace(/does not start an agent/, '')),
       'Parseh starts no agent and names none');
await page.click('#mkcopy');
await sleep(300);
eq(await clip(page), BOOK, 'copy the path copies the path');
await page.click('#mkopen');
for (let i = 0; i < 30 && !(await exists(INSTALL + '/opened.txt')); i++) await sleep(100);
eq((await Deno.readTextFile(INSTALL + '/opened.txt')).trim(), BOOK, 'open the folder asks the system\'s file manager for it');
// (the project skill, in .claude/skills/ and .agents/skills/, is written beside them where lane G's builder is: not listed here;
// .built-from.json is the reader build's source hash, which lets a synced computer tell a build out of date: lib/syncbuilds.py, a0.7.0)
eq((await tree(BOOK)).filter(n => !/^\.(claude|agents)\//.test(n)), ['.built-from.json', 'AGENTS.md', 'ASKS.md', 'CLAUDE.md', 'NOTES.md', 'annot/', 'book.json', 'main.tex',
                      'making.json', 'original/parts.json', 'original/the-clock.txt', 'reader/index.html', 'source/paras/'].filter(n => !n.endsWith('/')),
   'the folder holds what the brief says, Parseh\'s list of the parts, and the reader');
eq(await Deno.readTextFile(BOOK + '/original/the-clock.txt'), ORIGINAL_TEXT, 'the original is the uploaded file, byte for byte');
eq((await Deno.stat(BOOK + '/ASKS.md')).size, 0, 'ASKS.md is empty');
const making0 = JSON.parse(await Deno.readTextFile(BOOK + '/making.json'));
eq([making0.state, making0.stage], ['making', 'folder'], 'making.json says it is being made');
eq([making0.parts.map(p => [p.n, p.file, p.chapter]), making0.more_coming], [[[1, 'original/the-clock.txt', 'new']], true],
   'the original is part 1, and more text may come later: that is what a folder starts with');
assert(/this is all the text/.test(await page.$eval('#lane-llm', e => e.textContent)) && await page.$eval('#alltext', c => !c.checked),
       'the page offers "this is all the text", unticked');
assert(!await exists(INSTALL + '/others'), 'nothing was put in others/');
eq(await Deno.readTextFile(BOOK + '/AGENTS.md'), shown, 'the folder\'s AGENTS.md is the text the page showed');
assert(await page.$eval('#mkfolder', b => b.disabled) &&
       /a book is already at books\/english\/the-clock\//.test(await page.$eval('#mkfwhy', e => e.textContent)),
       'a second press is shut and names the slug that is taken');
await views(page, 'C-add-made', {full: true});

/* ================= b) the library ================= */
console.log('b) the library');
const lib = await ctx.newPage();
watch(lib, 'library');
await lib.goto(B + '/books/');
await lib.waitForSelector('a.book[data-making]');
eq(await lib.$eval('[data-making-tag]', e => e.textContent.replace(/ · (just now|\d+ minutes? ago)$/, '')),
   'being made · not started yet', 'the book is on the library at once, marked being made');
await views(lib, 'C-library');
console.log('c) the reader, while the agent works');
const url = B + '/books/english/the-clock/reader/';
await page.goto(url);
await page.waitForSelector('.mk-btn[data-layout=browser]');
assert(await inView(page, '.mk-btn[data-layout=browser]') && await onTop(page, '.mk-btn[data-layout=browser]'),
       'the making button is in the header, in the window, and nothing lies over it');
eq(await page.$eval('.mk-btn[data-layout=browser] .mk-txt', e => e.textContent), 'being made · not started yet',
   'it says where the making stands');
assert(/Nothing to read yet/.test(await page.$eval('#mktocome', e => e.textContent)), 'a book with no chapter says so, and does not fail');
assert(await page.$eval('#bookinfo', b => b.disabled) && await page.$eval('#rgn', b => b.disabled),
       'book info and gloss with an LLM are off, each with its reason');
assert(/being made by an agent/.test(await page.$eval('#rgn', b => b.title)), '... in its title');
await page.click('.mk-btn[data-layout=browser]');
await page.waitForSelector('#mkbox:not([hidden])');
assert(await inView(page, '#mkbox') && await onTop(page, '#mkbox h2'), 'the panel is in the window and on top');
await views(page, 'C-panel-not-started');
// the library moves by itself while the agent works
assert(/source recovered/.test(await agent('step', BOOK, MODEL)), 'the stand-in recovers the source');
await waitText(lib, '[data-making-tag]', /source recovered/, 20000);
assert(true, 'the library card moved without a reload');
await waitText(page, '#mkbox .mk-where', /source recovered/, 20000);
assert(true, 'the panel moved without a reload');
assert(/chapter table/.test(await agent('step', BOOK, MODEL)), 'the chapter table is written');
await waitText(page, '#mkbox', /Still to come: 1, 2/, 20000);
assert(/The chapter table: 1 \(1 paragraph\), 2 \(1 paragraph\)/.test(await page.$eval('#mkbox', e => e.textContent)),
       'the chapters the agent decided on are said, and which are still to come');
assert(/batch 1 of 2: chapter 1 assembled/.test(await agent('step', BOOK, MODEL)), 'batch 1 is assembled');
await waitText(page, '#mkbox .mk-where', /batch 2 of 2/, 20000);
const checks = await page.$$eval('#mkbox ul li', els => els.map(e => e.textContent));
assert(checks.includes('check_batch: 0 errors') && checks.includes('assemble: ALL PARAGRAPHS CLEAN'), 'the tools\' own words are shown');
assert(/has written more since this page was built/.test(await page.$eval('#mkbox', e => e.textContent)) &&
       /More is written than this page shows/.test(await page.$eval('#mktocome', e => e.textContent)),
       'the page is said to be older than the newest batch, in the panel and under the text');
assert(!await page.$('.row[data-c]'), '... and it is: no chunk is drawn yet');
await views(page, 'C-panel-batch');
// look at it now: the reader is rebuilt, the page reloads, the panel comes back open
await page.click('#mkbox button:has-text("look at it now")');
await page.waitForFunction(() => document.querySelector('.row[data-c]'), null, {timeout: 90000});
await page.waitForFunction(() => document.querySelector('#mkbox') && !document.querySelector('#mkbox').hidden, null, {timeout: 20000});
assert(/The old man wound the clock/.test(await page.$eval('main', e => e.textContent)), 'look at it now shows the new batch');
await waitText(page, '#mktocome', /Still to come:\s*chapter 2/);
assert(true, 'and says which chapter is still to come');
assert(!/has written more since/.test(await page.$eval('#mkbox', e => e.textContent)), 'the page is current again');
await views(page, 'C-reader-batch-1');

/* ================= the draft PDF ================= */
console.log('   the PDF of these chapters');
assert(await page.$eval('#mkbox button:has-text("the PDF of these chapters")', b => !b.hidden), 'the draft is offered where there is a shell');
if (HAS_TEX) {
  await page.click('#mkbox button:has-text("the PDF of these chapters")');
  await waitText(page, '#mkbox', /open the PDF/, 240000);
  assert(await exists(BOOK + '/frankdraft.pdf'), 'the draft is frankdraft.pdf beside the book');
  assert(!await exists(BOOK + '/main.pdf'), '... never main.pdf: the two cannot collide');
  const pdf = await page.$eval('#mkbox a.mk-a', a => a.href);
  const got = await fetch(pdf);
  eq([got.status, got.headers.get('content-type'), td.decode((await got.arrayBuffer()).slice(0, 5))], [200, 'application/pdf', '%PDF-'],
     'the PDF is served and is one');
  await views(page, 'C-panel-draft');
}

/* ================= d) no editing ================= */
console.log('d) no editing while it is made');
await page.click('#mkbox button.mk-x');
await page.hover('.row[data-c="0"]');
await page.waitForSelector('#chpen:not([hidden])');
assert(/editing is off while an agent makes this book/.test(await page.$eval('#chpen', b => b.title)), 'the pencil says why');
const texBefore = await Deno.readTextFile(BOOK + '/ch1.tex');
await page.click('#chpen');
await page.waitForSelector('#chbox:not([hidden])');
await page.waitForSelector('#chbox .mk-ask');
eq(await page.$eval('#chsave', b => getComputedStyle(b).display), 'none', 'save chunk is not offered');
eq(await page.$$eval('#chdel, #chundo, #chsplit, #chjoin, #chjoinp, #chfree, #chrgn, #chins',
                     els => els.map(e => getComputedStyle(e.closest('.arow') || e).display !== 'none' && getComputedStyle(e).display !== 'none')),
   [false, false, false, false, false, false, false, false], 'nor deleting, dividing, freeing, the LLM row or the macro buttons');
eq(await page.$$eval('#chfa, #chtr, #chvoc, #chen', els => els.map(e => e.readOnly)), [true, true, true, true],
   'the boxes show the chunk and cannot be typed in');
assert(/erased by its next batch/.test(await page.$eval('#chbox .mk-chnote', e => e.textContent)), 'the sheet says why, in words');
assert(await inView(page, '#mkchask') && await onTop(page, '#mkchask'), 'ask about this chunk is in the window and nothing lies over it');
assert(await onTop(page, '#chsrc'), 'the dictionary work (sources) is still there');
await views(page, 'C-chunk-sheet');
await page.fill('#chbox .mk-ask textarea', 'This meaning is too free: make it literal.');
await page.click('#mkchask');
await waitText(page, '#chbox .mk-said', /written to ASKS\.md/);
const asks1 = await Deno.readTextFile(BOOK + '/ASKS.md');
assert(/^## \d{4}-\d\d-\d\d \d\d:\d\d — about a chunk\n\nchapter 1, paragraph 1, subparagraph 1\.1, chunk 0:\n> The old man\n\nThis meaning is too free: make it literal\.\n$/.test(asks1),
       'the ask carries the chunk\'s address and text and the line: ' + JSON.stringify(asks1));
// the server refuses whatever the page does
const refused = await page.evaluate(async () => {
  const r = await fetch('__edit/chunk', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                          body: JSON.stringify({index: 0, fields: {en: 'changed by hand'}})});
  return [r.status, (await r.json())];
});
eq([refused[0], refused[1].making], [409, true], 'the door refuses an edit');
assert(/erased by its next batch/.test(refused[1].error), '... in words');
eq(await Deno.readTextFile(BOOK + '/ch1.tex'), texBefore, 'and the .tex is exactly as the agent left it');
await page.keyboard.press('Escape');
await page.waitForFunction(() => document.querySelector('#chbox').hidden);

/* ================= e) steering ================= */
console.log('e) steering the agent');
await page.click('.mk-btn[data-layout=browser]');
await page.waitForSelector('#mkbox:not([hidden])');
await page.fill('#mkbox textarea[aria-label="what to change from now on"]', 'Please write the meanings in capitals from now on.');
await page.click('#mkbox button:has-text("ask")');
await waitText(page, '#mkbox', /written to ASKS\.md at/);
const asks2 = await Deno.readTextFile(BOOK + '/ASKS.md');
assert(/— what to change from now on\n\nPlease write the meanings in capitals from now on\.\n$/.test(asks2), 'the ask is a dated entry in ASKS.md');
await waitText(page, '#mkbox', /2 asks written so far/, 20000);
assert(true, 'the panel counts the asks');
assert(/batch 2 of 2: chapter 2 assembled/.test(await agent('step', BOOK, MODEL)), 'the stand-in does its next batch');
const notes = await Deno.readTextFile(BOOK + '/NOTES.md');
assert(/ASKS\.md, [^\n]*about a chunk[^\n]*noted, and left/.test(notes) && /Please write the meanings in capitals[^\n]*done from batch 2 on/.test(notes),
       'it read ASKS.md before the batch, and NOTES.md says what it did about each entry');
assert(/\\ch\{\}\{A child came in\}\{[^}]*\}\{[^\n]*\}\{A CHILD CAME IN\}/.test(await Deno.readTextFile(BOOK + '/ch2.tex')),
       'the next batch is in capitals, as asked');
assert(!/THE OLD MAN/.test(await Deno.readTextFile(BOOK + '/ch1.tex')), 'and the batch already checked is not touched');
await page.click('#mkbox button:has-text("look at it now")');
await waitText(page, 'main', /A CHILD CAME IN/, 90000);
await waitText(page, '#mktocome', /Still being made/);
assert(true, 'with every chapter of the table in, it says it is still being made');
// Parseh updated during the making
const mk = JSON.parse(await Deno.readTextFile(BOOK + '/making.json'));
await Deno.writeTextFile(BOOK + '/making.json', JSON.stringify({...mk, parseh: 'a0.1.0'}, null, 2));
await waitText(page, '#mkbox', /Parseh was updated during the making/, 20000);
assert(/began under a0\.1\.0 and this is a0\./.test(await page.$eval('#mkbox .mk-note', e => e.textContent)), 'Parseh updated during the making is said, with both versions');
await Deno.writeTextFile(BOOK + '/making.json', JSON.stringify(mk, null, 2));
// a file half written by the agent is said, and the book is still being made
await Deno.writeTextFile(BOOK + '/making.json', '{"state": "maki');
await waitText(page, '#mkbox', /cannot be read just now/, 20000);
assert(await page.$eval('#bookinfo', b => b.disabled), 'a half-written making.json does not lift the lock');
await Deno.writeTextFile(BOOK + '/making.json', JSON.stringify(mk, null, 2));
await waitNoText(page, '#mkbox', /cannot be read just now/, 20000);
// THE INSTRUCTIONS WRITTEN AGAIN, from the panel: what the agent reads is made again, nothing the agent made is
// touched, and the person is told that the agent must be told (its chat has read the old file)
const agentsMade = await Deno.readTextFile(BOOK + '/AGENTS.md');
const kept = [await Deno.readTextFile(BOOK + '/NOTES.md'), await Deno.readTextFile(BOOK + '/ASKS.md'),
              await Deno.readTextFile(BOOK + '/making.json'), await Deno.readTextFile(BOOK + '/ch1.tex')];
await Deno.writeTextFile(BOOK + '/AGENTS.md', 'an old one, from before an update of Parseh');
await page.click('#mkbox button:has-text("write the instructions again")');
await waitText(page, '#mkbox', /tell it to read AGENTS\.md again/, 20000);
eq(await Deno.readTextFile(BOOK + '/AGENTS.md'), agentsMade, 'the instructions are written again, as they were made');
eq([await Deno.readTextFile(BOOK + '/NOTES.md'), await Deno.readTextFile(BOOK + '/ASKS.md'),
    await Deno.readTextFile(BOOK + '/making.json'), await Deno.readTextFile(BOOK + '/ch1.tex')], kept,
   'and the journal, the asks, the record and the chapters are exactly as they were');
assert(/were written (just now|\d+ minutes? ago)/.test(await page.$eval('#mkbox', e => e.textContent)), 'the panel says when they were written');
await shot(page, 'H-panel-instructions-again-1280');
await page.evaluate(() => { document.querySelector('#mkbox').scrollTop = 0; });      // the click scrolled the panel to its button

/* ================= the themes and the widths ================= */
console.log('   themes and widths');
const hush = await quietOthers(page);
for (const theme of ['dark', 'sepia']) {
  await page.evaluate(t => Parseh.theme.set(t), theme);
  await sleep(300);
  assert(await inView(page, '#mkbox') && await onTop(page, '#mkbox h2'), 'the panel in the ' + theme + ' theme is in the window');
  await shot(page, 'C-panel-batch-2-1280-' + theme);
}
await page.evaluate(() => Parseh.theme.set('light'));
await sleep(300);
await hush();
await page.setViewportSize({width: 390, height: 844});
await sleep(400);
assert(await inView(page, '#mkbox'), 'the panel fits a 390 px window (the browser interface)');
await shot(page, 'C-panel-390-browser-light');
await page.locator('#mkbox button:has-text("write the instructions again")').scrollIntoViewIfNeeded();
await shot(page, 'H-panel-instructions-again-390-light');
await page.setViewportSize({width: 1280, height: 900});

/* ================= f) another device ================= */
console.log('f) a phone, and a device that is not the computer');
const pctx = await context(PHONE, {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
await pctx.addInitScript(() => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (e) { /* refused */ } });
const phone = await pctx.newPage();
watch(phone, 'phone');
await phone.goto(PHONE + '/books/english/the-clock/reader/');
await phone.waitForSelector('.mk-btn[data-layout=mobile]');
assert(await phone.$eval('.mk-btn[data-layout=mobile]', b => getComputedStyle(b).display !== 'none') &&
       await phone.$eval('.mk-btn[data-layout=browser]', b => getComputedStyle(b).display === 'none'),
       'in the mobile interface the panel\'s button is the mobile one');
await phone.click('.mk-btn[data-layout=mobile]');
await phone.waitForSelector('#mkbox:not([hidden])');
assert(await inView(phone, '#mkbox') && await onTop(phone, '#mkbox h2'), 'the panel fits the phone and is on top');
const ptext = await phone.$eval('#mkbox', e => e.textContent);
assert(/all batches in|batch 2 of 2/.test(ptext) && /check_batch: 0 errors/.test(ptext), 'the phone reads where the making stands');
// ANOTHER DEVICE DOES EVERYTHING BUT OPEN THE FOLDER (the owner, 2026-09-29): the path is shown to it to copy, with
// the reason it is not offered a button that would open a window on the computer's screen
assert(await phone.$eval('#mkbox code.mk-path', e => e.textContent) === BOOK && !await phone.$('#mkbox button:has-text("open the folder")'),
       'the folder\'s path is shown to a phone to copy, and it is offered no folder to open');
assert(/shows it on the screen of the computer Parseh runs on/.test(await phone.$eval('#mkbox', e => e.textContent)) &&
       (await phone.$$('#mkbox .mk-lock')).length === 0, 'the reason is a plain sentence, and nothing else is shut');
assert(await phone.$('#mkbox button:has-text("finish")'), 'a Finish button is drawn for a phone');
await shot(phone, 'C-panel-phone-390-light');
await phone.fill('#mkbox textarea[aria-label="what to change from now on"]', 'From the phone: keep the vocabulary short.');
await phone.click('#mkbox button:has-text("ask")');
await waitText(phone, '#mkbox', /written to ASKS\.md at/);
assert(/From the phone: keep the vocabulary short\./.test(await Deno.readTextFile(BOOK + '/ASKS.md')), 'a phone may write an ask');
const phoneDoors = await phone.evaluate(async () => {
  const out = {};
  for (const [name, url, opt] of [
      ['open', '/books/english/the-clock/__making/open', {method: 'POST', body: '{}'}],
      ['instructions', '/books/__making/instructions', {method: 'POST', body: '{"book": {"lang": "en", "gloss": "en"}}'}]]) {
    const r = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...opt});
    out[name] = [r.status, (await r.json())];
  }
  return out;
});
assert(phoneDoors.open[0] === 403 && /screen of the computer Parseh runs on/.test(phoneDoors.open[1].error) && phoneDoors.open[1].path === BOOK,
       'open the folder is refused a phone in a sentence that says why, and gives the path');
assert(!await exists(INSTALL + '/opened.txt') || (await Deno.readTextFile(INSTALL + '/opened.txt')).trim().split('\n').length === 1,
       'no file manager was started for the phone');
assert(phoneDoors.instructions[0] === 200 && phoneDoors.instructions[1].ok, 'the instructions are shown to a phone');
assert(await exists(BOOK + '/making.json') && JSON.parse(await Deno.readTextFile(BOOK + '/making.json')).state === 'making',
       'and nothing changed');
const phoneAdd = await ctx.newPage();
await phoneAdd.goto(PHONE + '/books/add/?path=llm');
await phoneAdd.waitForSelector('#lane-llm:not([hidden])');
assert(await phoneAdd.$('#mklock') === null && !/computer only|computer's alone/i.test(await phoneAdd.$eval('#lane-llm', e => e.textContent)),
       'the add page on a phone says nothing about the computer\'s alone');
await phoneAdd.close();
await pctx.close();

/* ================= g) a machine with no sh ================= */
console.log('g) no sh: the PDF of these chapters is not available, the reader is');
const nctx = await context(NOSH);
const nosh = await nctx.newPage();
watch(nosh, 'no sh');
await nosh.goto(NOSH + '/books/english/the-clock/reader/');
await nosh.waitForSelector('.mk-btn[data-layout=browser]');
await nosh.click('.mk-btn[data-layout=browser]');
await nosh.waitForSelector('#mkbox:not([hidden])');
assert(await nosh.$eval('#mkbox button:has-text("the PDF of these chapters")', b => b.hidden), 'the draft button is not drawn');
assert(/not available on this computer, which has no shell to make it\. The reader is available/.test(await nosh.$eval('#mkbox', e => e.textContent)),
       'it is said plainly not to be available, and that the reader is');
await shot(nosh, 'C-panel-no-sh-1280-light');
const rs = await nosh.evaluate(async () => {
  const r = await fetch('__build', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({what: 'draft'})});
  return [r.status, (await r.json()).error];
});
eq(rs[0], 409, 'the door refuses the draft too');
assert(/not available on this computer/.test(rs[1]), '... in the same words');
// the reader is what such a machine can build: made stale by the agent, then brought by look at it now
await Deno.writeTextFile(BOOK + '/ch2.tex', (await Deno.readTextFile(BOOK + '/ch2.tex')) + '% the agent touched this batch\n');
await waitText(nosh, '#mkbox', /has written more since this page was built/, 20000);
const back = nosh.waitForNavigation({timeout: 180000});
await nosh.click('#mkbox button:has-text("look at it now")');
await back;
await nosh.waitForFunction(() => document.querySelector('#mkbox') && !document.querySelector('#mkbox').hidden, null, {timeout: 20000});
assert(!/has written more since/.test(await nosh.$eval('#mkbox', e => e.textContent)), 'look at it now builds the reader without sh, all the same');
await nctx.close();

/* ================= h) finish ================= */
console.log('h) finish');
assert(/final/.test(await agent('step', BOOK, MODEL)), 'the stand-in checks everything and says every batch is in');
await page.reload();
await openPanel(page);
await waitText(page, '#mkbox .mk-where', /waiting for the next part/, 20000);   // every part is in, and the person has not said this is all the text
// a paragraph that no longer reproduces its source stops it
const paraFile = BOOK + '/source/paras/ch1_p00.txt';
const paraWas = await Deno.readTextFile(paraFile);
await Deno.writeTextFile(paraFile, paraWas.trim().replace('old man', 'old men') + '\n');
await page.click('#mkbox button:has-text("finish…")');
await waitText(page, '#mkbox', /Has the agent stopped\?/);
await shot(page, 'C-finish-question-1280-light');
await page.click('#mkbox button:has-text("not yet")');
assert(!/Has the agent stopped\?/.test(await page.$eval('#mkbox', e => e.textContent)), '"not yet" takes the question away');
await page.click('#mkbox button:has-text("finish…")');
await page.click('#mkbox button:has-text("yes, finish now")');
await waitText(page, '#mkbox', /not finished/, 120000);
const fin = await page.$eval('#mkbox', e => e.textContent);
assert(/1 paragraph does not reproduce its source/.test(fin) && /chapter 1 paragraph 1 does not reproduce its source \(it differs at character \d+\)/.test(fin),
       'a paragraph that does not reproduce its source stops Finish, and says which: ' + fin.slice(-400));
assert(/put what is said above right, then finish again/.test(fin), '... and what to do');
eq(JSON.parse(await Deno.readTextFile(BOOK + '/making.json')).state, 'making', 'the making goes on');
assert(await page.$eval('#bookinfo', b => b.disabled), 'and the reader still does not edit');
await views(page, 'C-finish-refused');
await Deno.writeTextFile(paraFile, paraWas);
await page.click('#mkbox button:has-text("finish…")');
await page.click('#mkbox button:has-text("yes, finish now")');
// both clean: the making ends and the page is an ordinary book again
await page.waitForFunction(() => !document.querySelector('.mk-btn'), null, {timeout: 400000});
eq(JSON.parse(await Deno.readTextFile(BOOK + '/making.json')).state, 'finished', 'making.json says finished');
assert(/— finished\n\nThe person finished this book from Parseh\. Stop:/.test(await Deno.readTextFile(BOOK + '/ASKS.md')),
       'a running agent is told to stop, in the file it reads before every batch');
assert(/stop: the book is finished|finished: the person ended the making/.test(await agent('step', BOOK, MODEL)), 'the stand-in reads it and stops');
assert(HAS_TEX ? await exists(BOOK + '/main.pdf') : !await exists(BOOK + '/main.pdf'),
       HAS_TEX ? 'the full build ran: main.pdf is there' : 'no TeX: the reader was built and the PDF left');
assert(await exists(BOOK + '/annot/ch1_p00.json') && await exists(BOOK + '/original/the-clock.txt'), 'annot/ stays as the record, and the original with it');
await page.waitForSelector('.row[data-c]');
eq(await page.$$eval('.mk-btn, #mkbox, #mktocome', e => e.length), 0, 'no making button, no panel, no still-to-come');
assert(!await page.$eval('#bookinfo', b => b.disabled) && !await page.$eval('#rgn', b => b.disabled), 'book info and gloss with an LLM work again');
await lib.reload();
assert(!await lib.$('[data-making-tag]'), 'the library card says nothing of being made');
// the reader's doors edit the .tex now
await page.hover('.row[data-c="0"]');
await page.waitForSelector('#chpen:not([hidden])');
await page.click('#chpen');
await page.waitForSelector('#chbox:not([hidden])');
assert(await page.$eval('#chsave', b => getComputedStyle(b).display !== 'none') && !await page.$eval('#chfa', e => e.readOnly),
       'the chunk sheet writes again');
assert(!await page.$('#chbox .mk-ask'), 'and offers no ask about this chunk');
await page.fill('#chen', 'the old fellow');
await page.click('#chsave');
await waitText(page, '#chstat', /saved en into ch1\.tex/, 60000);
assert(/\{the old fellow\}/.test(await Deno.readTextFile(BOOK + '/ch1.tex')), 'an edit is written into the .tex');
// its download carries the original and annot/, never the agent's files
const dl = await fetch(B + '/books/english/the-clock/__download');
const zipPath = TMP + '/the-clock-book.zip';
await Deno.writeFile(zipPath, new Uint8Array(await dl.arrayBuffer()));
const names = JSON.parse(await py(['-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps([sorted(z.namelist()), json.loads(z.read("parseh-bundle.json"))["format"]]))', zipPath]));
for (const want of ['original/the-clock.txt', 'annot/ch1_p00.json', 'annot/ch2_p00.json', 'NOTES.md', 'book.json', 'main.tex', 'ch1.tex', 'ch2.tex'])
  assert(names[0].includes('the-clock/' + want), 'the download carries ' + want);
for (const never of ['AGENTS.md', 'CLAUDE.md', 'ASKS.md', 'making.json', 'frankdraft.pdf', 'main.pdf'])
  assert(!names[0].some(n => n.endsWith('/' + never)), 'the download never carries ' + never);
eq(names[1], 'parseh-bundle/3', 'the bundle\'s format number is 3');
await views(page, 'C-finished-reader');

/* ================= i) a right-to-left book ================= */
console.log('i) Persian: a book that is read the other way, made from the page');
const MODEL_FA = root + '/tests/fixtures/books/persian/mini-fa';
await agent('original', MODEL_FA, TMP + '/farsi.txt');
const FA = INSTALL + '/books/persian/farsi-shekar-ast';
await page.goto(B + '/books/add/');
await page.click('.path[data-path="llm"]');
await page.waitForSelector('#lane-llm:not([hidden])');
await page.selectOption('#lang', 'fa');
await page.fill('#title', 'فارسی شکر است');
await page.fill('#title_latin', 'Farsi shekar ast');
await page.fill('#author', 'محمدعلی جمال‌زاده');
await page.fill('#author_latin', 'Mohammad-Ali Jamalzadeh');
eq(await page.$eval('#title', e => getComputedStyle(e).direction), 'rtl', 'the title box reads right to left');
await page.setInputFiles('#original', TMP + '/farsi.txt');
await page.waitForFunction(() => !document.querySelector('#mkfolder').disabled);
// THE ROW'S CHOICES, for a language that has them: a book made in place writes the short vowels unless it is
// told not to, and its transliteration is in the usual scheme unless it is told IPA; both are the book's own facts
const MARKS = '#instrmount .llmrow-opt[data-option="marks"] select', TRANSLIT = '#instrmount .llmrow-opt[data-option="translit"] select';
await page.waitForSelector(MARKS);
eq(await page.$eval(MARKS, s => s.value), 'marks', 'a book made in place writes the short vowels unless it is told otherwise');
await page.click('#ishow summary');
await page.waitForFunction(() => /The short vowels are written/.test(document.querySelector('#itext').textContent));
await page.selectOption(MARKS, 'nomarks');
await page.selectOption(TRANSLIT, 'ipa');
await page.waitForFunction(() => /The short vowels are left alone/.test(document.querySelector('#itext').textContent) &&
                                 /is written in IPA/.test(document.querySelector('#itext').textContent));
const farsiShown = await page.$eval('#itext', e => e.textContent);
assert(farsiShown.split('\n')[0].endsWith('· IPA · no marks'), 'the instructions\' first line says which choices they were written with');
await page.click('#mkfolder');
await page.waitForSelector('#mkcopy', {timeout: 60000});
eq(await page.$eval('.bigpath', e => e.textContent), FA, 'the folder is on the Persian shelf, named from the transliterated title');
const faJson = JSON.parse(await Deno.readTextFile(FA + '/book.json'));
eq([faJson.language, faJson.title, faJson.author], ['fa', 'فارسی شکر است', 'محمدعلی جمال‌زاده'], 'book.json keeps the Persian, letter for letter');
eq(faJson.translit, 'ipa', 'the scheme the row said is a fact of the book');
assert(/Persian/.test(await Deno.readTextFile(FA + '/AGENTS.md')), 'the instructions say it is a Persian book');
eq(await Deno.readTextFile(FA + '/AGENTS.md'), farsiShown, 'and they are the text the page showed, with the choices made');
eq(JSON.parse(await Deno.readTextFile(FA + '/making.json')).instructions.marks, 'nomarks', 'making.json keeps how they were written, so that they can be written again');
await views(page, 'C-fa-add-made', {full: true});
await lib.goto(B + '/books/');
await lib.waitForSelector('a.book[data-making*="persian"]');
eq(await lib.$eval('a.book[data-making*="persian"] [data-making-tag]', e => e.textContent.replace(/ · (just now|\d+ minutes? ago)$/, '')),
   'being made · not started yet', 'the Persian book is on the library at once, marked being made');
await views(lib, 'C-fa-library');
// a book with no chapter at all, on a phone in the mobile interface: nothing throws (the errors of this page
// are counted at the end), the panel reads, and the page says there is nothing to read yet
const zctx = await context(PHONE, {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
await zctx.addInitScript(() => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (e) { /* refused */ } });
const zero = await zctx.newPage();
watch(zero, 'phone');
await zero.goto(PHONE + '/books/persian/farsi-shekar-ast/reader/');
await zero.waitForSelector('.mk-btn[data-layout=mobile]');
await zero.click('.mk-btn[data-layout=mobile]');
await zero.waitForSelector('#mkbox:not([hidden])');
assert(/not started yet/.test(await zero.$eval('#mkbox', e => e.textContent)) && await inView(zero, '#mkbox'),
       'a book with no chapter yet reads on a phone: the panel says the agent has not started');
assert(/Nothing to read yet/.test(await zero.$eval('#mktocome', e => e.textContent)), '... and the page says there is nothing to read yet');
await shot(zero, 'C-fa-phone-390-not-started-light');
await zctx.close();
assert(/source recovered/.test(await agent('step', FA, MODEL_FA)), 'the stand-in recovers the Persian source');
assert(/chapter table/.test(await agent('step', FA, MODEL_FA)), '... writes its chapter table');
assert(/batch 1 of 2: chapter 1 assembled/.test(await agent('step', FA, MODEL_FA)), '... and assembles a batch');
await page.goto(B + '/books/persian/farsi-shekar-ast/reader/');
await page.waitForSelector('.mk-btn[data-layout=browser]');
await page.click('.mk-btn[data-layout=browser]');
await page.waitForSelector('#mkbox:not([hidden])');
await page.click('#mkbox button:has-text("look at it now")');
await page.waitForFunction(() => document.querySelector('.row[data-c]'), null, {timeout: 90000});
await page.waitForFunction(() => document.querySelector('#mkbox') && !document.querySelector('#mkbox').hidden, null, {timeout: 20000});
assert(await inView(page, '.mk-btn[data-layout=browser]') && await onTop(page, '.mk-btn[data-layout=browser]') && await inView(page, '#mkbox'),
       'the making button and the panel of a right-to-left book lie inside the window, and nothing over them');
eq(await page.$eval('.mk-btn[data-layout=browser] .mk-txt', e => e.textContent), 'being made · batch 2 of 2', 'the button says where it is');
assert(/The instructions in this folder were written (just now|\d+ minutes? ago), with the short vowels left as the source has them and the transliteration in IPA\./.test(await page.$eval('#mkbox', e => e.textContent)),
       'the panel says how the instructions were written: the two choices that are the book\'s own facts');
await views(page, 'C-fa-panel');
await page.keyboard.press('Escape');
await page.waitForFunction(() => document.querySelector('#mkbox').hidden);
assert(true, 'Escape closes the panel');
await page.hover('.row[data-c="0"]');
await page.waitForSelector('#chpen:not([hidden])');
await page.click('#chpen');
await page.waitForSelector('#chbox .mk-ask');
eq(await page.$$eval('#chfa, #chtr, #chvoc, #chen', els => els.map(e => e.readOnly)), [true, true, true, true],
   'the Persian chunk is shown and cannot be typed in');
assert(await inView(page, '#mkchask') && await onTop(page, '#mkchask'), 'ask about this chunk is in the window in a right-to-left book too');
await page.fill('#chbox .mk-ask textarea', 'معنی را تحت‌اللفظی بنویس');
await page.click('#mkchask');
await waitText(page, '#chbox .mk-said', /written to ASKS\.md/);
assert((await Deno.readTextFile(FA + '/ASKS.md')).includes('معنی را تحت‌اللفظی بنویس'), 'an ask in Persian reaches ASKS.md letter for letter');
await views(page, 'C-fa-chunk-sheet');

/* ================= k) the text in parts, from another device ================= */
console.log('k) the text in parts: made from a phone, a part given while the agent works, all the text, Finish, reopen');
// The computer's own pages are closed first: the four servers of this suite share ONE scratch config/, and the
// preferences file is written through a temporary name every process shares (lib/prefs.py), so a page of
// another server following a theme this section changes could make two of them write at once -- a harness
// matter, which nothing here is about -- and one at a time, for a page that is closed writes its place back
for (const pg of [lib, page]) { await pg.close(); await sleep(700); }
await ctx.close();
// a phone let in over the Wi-Fi, on a computer with no TeX: Finish builds the reader alone, which is quick
const PN = await serve(['--phone'], {PATH: '/nonexistent'});
await agent('original', MODEL, TMP + '/part1.txt', '--first', '0', '--count', '1');
await agent('original', MODEL, TMP + '/part2.txt', '--first', '1', '--count', '1');
const PARTS = INSTALL + '/books/english/two-parts';
const kctx = await context(PN, {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
await kctx.addInitScript(() => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (e) { /* refused */ } });
const kp = await kctx.newPage();
watch(kp, 'phone');
await kp.goto(PN + '/books/add/?path=llm');
await kp.waitForSelector('#lane-llm:not([hidden])');
await kp.selectOption('#lang', 'en');
await kp.fill('#title', 'Two Parts');
await kp.fill('#title_latin', 'Two Parts');
await kp.setInputFiles('#original', TMP + '/part1.txt');
await kp.waitForFunction(() => !document.querySelector('#mkfolder').disabled);
await kp.click('#mkfolder');
await kp.waitForSelector('#mkcopy', {timeout: 60000});
assert(await exists(PARTS + '/making.json'), 'a phone made the folder');
assert(!await kp.$('#mkopen') && /screen of the computer Parseh runs on/.test(await kp.$eval('#mkopensaid', e => e.textContent)),
       'it is offered no button to open the folder, and is told why: the computer\'s own act, not a permission');
eq(await kp.$eval('.bigpath', e => e.textContent), PARTS, '... and is shown the path to copy');
await views(kp, 'K-add-made-phone', {full: true});
const k0 = JSON.parse(await Deno.readTextFile(PARTS + '/making.json'));
eq([k0.parts.length, k0.more_coming], [1, true], 'the folder starts with the original as part 1, and more text expected');
assert(/source recovered: 1 paragraphs/.test(await agent('step', PARTS, MODEL)), 'the stand-in recovers part 1 with lib/sourcetext.py');
assert(/chapter table: 1 chapters/.test(await agent('step', PARTS, MODEL)), '... and writes its chapter table');
assert(/Recovered from `original\/part1\.txt` with sourcetext\.py/.test(await Deno.readTextFile(PARTS + '/NOTES.md')), '... and says so in NOTES.md');
// THE PHONE GIVES THE AGENT PART 2, between two batches
await kp.goto(PN + '/books/english/two-parts/reader/');
await kp.waitForSelector('.mk-btn[data-layout=mobile]');
await kp.click('.mk-btn[data-layout=mobile]');
await kp.waitForSelector('#mkbox:not([hidden])');
await waitText(kp, '#mkparts', /part 1.*taken by the agent/s);
assert(/More text may still come/.test(await kp.$eval('#mkmore', e => e.textContent)), 'the panel says more text may come, and offers "this is all the text"');
await kp.click('#mkadd summary');
await kp.setInputFiles('#mkpartfile', TMP + '/part2.txt');
assert(/part2\.txt, 1 kB\./.test(await kp.$eval('#mkadd', e => e.textContent)), 'the chosen file is named, with its size');
await kp.selectOption('#mkpartwhere', 'new|');
await kp.fill('#mkpartlabel', 'second half');
await kp.click('#mkpartadd');
await waitText(kp, '#mkpartsaid', /part 2 added: the agent takes it before its next batch/);
const k1 = JSON.parse(await Deno.readTextFile(PARTS + '/making.json'));
eq(k1.parts.map(p => [p.n, p.file, p.chapter, p.join, p.label]),
   [[1, 'original/part1.txt', 'new', '', ''], [2, 'original/part-002-part2.txt', 'new', '', 'second half']], 'the list is Parseh\'s, and complete');
eq(await Deno.readTextFile(PARTS + '/original/part-002-part2.txt'), await Deno.readTextFile(TMP + '/part2.txt'), 'the file arrived byte for byte, from another origin');
assert(/a part was added[\s\S]*part-002-part2\.txt/.test(await Deno.readTextFile(PARTS + '/ASKS.md')), 'the file the agent reads before every batch says a part came');
await waitText(kp, '#mkparts', /part 2.*second half.*a new chapter.*not taken by the agent yet/s);
await shot(kp, 'K-panel-phone-390-part-added-light');
// Finish would wait, in words: part 2 is not taken and the agent is not idle; a second press passes it
await kp.click('#mkbox button:has-text("finish…")');
const waits = await kp.$eval('#mkbox', e => e.textContent);
assert(/Before you finish:/.test(waits) && /part 2 \(second half\) has not been taken by the agent yet/.test(waits) &&
       /the agent has not said it is done/.test(waits) && /Finish anyway\?/.test(waits), 'Finish says what it waits for, and asks again: ' + waits.slice(-500));
await views(kp, 'K-finish-waits');
await kp.click('#mkbox button:has-text("not yet")');
const early = await kp.evaluate(async () => {
  const r = await fetch('/books/english/two-parts/__making/finish', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  return [r.status, await r.json()];
});
assert(early[0] === 409 && early[1].confirm === true && early[1].blockers.length === 2, 'the door answers the first press with the sentences, not with a Finish');
eq(JSON.parse(await Deno.readTextFile(PARTS + '/making.json')).state, 'making', 'nothing finished');
// THE AGENT TAKES IT BEFORE ITS NEXT BATCH, numbered on from the book's
assert(/part 2 taken: 1 paragraphs from chapter 2/.test(await agent('step', PARTS, MODEL)), 'the stand-in takes part 2 BEFORE batch 1');
const k2 = JSON.parse(await Deno.readTextFile(PARTS + '/making.json'));
eq([k2.sources.done, k2.sources.of, k2.batches, k2.chapters.map(c => [c.chapter, c.part])], [[1, 2], 2, {done: 0, of: 2}, [[1, 1], [2, 2]]],
   'it wrote its record: parts taken, the batches grown, the chapter table with where each came from');
eq(k2.parts, k1.parts, 'and left the list, which is Parseh\'s, as it was');
assert(await exists(PARTS + '/source/paras/ch2_p00.txt') && /## Part 2[\s\S]*Decided: a new chapter/.test(await Deno.readTextFile(PARTS + '/NOTES.md')),
       'part 2 is chapter 2 in source/paras, and what was decided is in NOTES.md');
await kp.evaluate(() => window.ParsehMaking.refresh());
await waitText(kp, '#mkparts', /part 2.*taken by the agent/s);
assert(/the agent decided: a new chapter/.test(await kp.$eval('#mkparts', e => e.textContent)), 'the panel shows what the agent decided');
assert(/batch 1 of 2/.test(await agent('step', PARTS, MODEL)) && /batch 2 of 2/.test(await agent('step', PARTS, MODEL)), 'the batches of both parts are made');
assert(/final/.test(await agent('step', PARTS, MODEL)), 'verify_book is clean');
eq(JSON.parse(await Deno.readTextFile(PARTS + '/making.json')).stage, 'waiting', 'every part is in and the person has not said it is all: the agent WAITS');
assert(/waiting for the next part/.test(await agent('step', PARTS, MODEL)), '... and says so when asked again');
await kp.evaluate(() => window.ParsehMaking.refresh());
await waitText(kp, '.mk-where', /waiting for the next part/);
// "this is all the text", from the phone
await kp.click('#mkmore button:has-text("this is all the text")');
await waitText(kp, '#mkmore', /You said this is all the text/);
eq(JSON.parse(await Deno.readTextFile(PARTS + '/making.json')).more_coming, false, 'more_coming is false');
assert(/all the text/.test(await Deno.readTextFile(PARTS + '/ASKS.md')), 'and the agent is told in the file it reads');
assert(/final/.test(await agent('step', PARTS, MODEL)), 'the agent reads it, and now ends');
eq(JSON.parse(await Deno.readTextFile(PARTS + '/making.json')).stage, 'done', '"the text is complete": stage done');
await kp.evaluate(() => window.ParsehMaking.refresh());
await waitText(kp, '.mk-where', /all batches in/);
await views(kp, 'K-panel-parts');
// the third theme: the panel with its parts list and its box, in sepia, on a phone and on a computer's window
for (const [w, h] of [[390, 844], [1280, 900]]) {
  await kp.setViewportSize({width: w, height: h});
  await kp.evaluate(() => Parseh.theme.set('sepia'));
  await kp.evaluate(() => { document.querySelector('#mkbox').scrollTop = 0; });          // the panel was scrolled to its end
  await sleep(300);
  const sepia = [await inView(kp, '#mkbox'), await onTop(kp, '#mkbox h2'),
    await kp.evaluate(() => { const b = document.querySelector('#mkbox').getBoundingClientRect(), p = document.querySelector('#mkparts').getBoundingClientRect();
                              return p.width > 0 && p.left >= b.left - 1 && p.right <= b.right + 1; })];
  assert(sepia.every(Boolean), `the panel with its parts list is in the window at ${w} px in the sepia theme, and the list lies inside the panel ` +
         `(in the window, nothing over its title, list inside: ${sepia.join(', ')})`);
  await shot(kp, `K-panel-parts-${w}-sepia`);
}
await kp.evaluate(() => Parseh.theme.set('light'));
await kp.setViewportSize({width: 390, height: 844});
// FINISH, from the phone: nothing is waited for, and a Finish ends the making
await kp.click('#mkbox button:has-text("finish…")');
assert(!/Before you finish:/.test(await kp.$eval('#mkbox', e => e.textContent)), 'with every part taken and the agent idle, Finish waits for nothing');
await kp.click('#mkbox button:has-text("yes, finish now")');
await kp.waitForFunction(() => !document.querySelector('.mk-btn'), null, {timeout: 400000});
eq(JSON.parse(await Deno.readTextFile(PARTS + '/making.json')).state, 'finished', 'a phone finished the book');
// ONE PAGE OF THE PHONE'S BROWSER AT A TIME from here on: pages of one browser share their preferences, and each
// one that follows a theme another changes writes it back -- two writes at once are what lib/prefs.py's one
// temporary file cannot take (a 400 from /__prefs), which is nothing this section is about
await kp.close();
// REOPEN, from the add page: the agent makes the next part
const kadd = await kctx.newPage();
watch(kadd, 'phone');
await kadd.goto(PN + '/books/add/?path=extend');
await kadd.waitForSelector('#lane-extend:not([hidden])');
await kadd.selectOption('#addinto', '/books/english/two-parts');
assert(await kadd.$eval('#addwho', e => !e.hidden) && await kadd.$eval('#addwho_me', r => r.checked && !r.disabled) &&
       /reopens the making/.test(await kadd.$eval('#addwho_agent_note', e => e.textContent)),
       'a book the agent made is offered "the agent makes it" (which reopens the making) and "I gloss it myself", which is the default once it is finished');
await kadd.click('#addwho_agent');
assert(await kadd.$eval('#addwhere_auto', r => r.checked) && await kadd.$eval('#addauto_row', e => !e.hidden), '"the agent decides" is what a part starts as');
await kadd.fill('#aptext', 'Chapter three begins here. The clock had stopped.');
await views(kadd, 'K-add-extend-agent', {full: true});
await kadd.click('#addto');
await waitText(kadd, '#addresult', /Added as part 3\./);
assert(/the making was reopened/.test(await kadd.$eval('#addresult', e => e.textContent)), 'the page says the making was reopened');
const k3 = JSON.parse(await Deno.readTextFile(PARTS + '/making.json'));
eq([k3.state, k3.finished, k3.parts.map(p => [p.n, p.chapter]), k3.sources.done, 'finished' in k3], ['making', undefined, [[1, 'new'], [2, 'new'], [3, 'auto']], [1, 2], false],
   'reopened: making again, the part listed with "auto", what the agent recorded kept');
assert(await exists(PARTS + '/annot/ch1_p00.json') && await exists(PARTS + '/annot/ch2_p00.json'), 'annot/ is as it was');
assert(/— reopened[\s\S]*is taken back/.test(await Deno.readTextFile(PARTS + '/ASKS.md')), 'the agent is told in ASKS.md, after the entry that said to stop');
eq(await Deno.readTextFile(PARTS + '/original/part-003-pasted.txt'), 'Chapter three begins here. The clock had stopped.', 'the pasted text is the third part');
await kadd.close();
const kr = await kctx.newPage();
watch(kr, 'phone');
await kr.goto(PN + '/books/english/two-parts/reader/');
await kr.waitForSelector('.mk-btn[data-layout=mobile]');
await kr.click('.mk-btn[data-layout=mobile]');
await waitText(kr, '#mkparts', /part 3.*pasted\.txt.*the agent decides.*not taken by the agent yet/s);
assert(/Before you finish:[\s\S]*part 3 has not been taken by the agent yet/.test(await kr.$eval('#mkbox', e => e.textContent)),
       'a reopened book says, before Finish is pressed, that it waits for its new part');
assert(!/the agent has not said it is done/.test(await kr.$eval('#mkbox', e => e.textContent)), '... and not that the agent is busy: it said it was done, and was reopened after');
await kr.click('#mkbox button:has-text("finish…")');
assert(/Finish anyway\?/.test(await kr.$eval('#mkbox', e => e.textContent)), 'and the press asks again, since a second one goes through');
await views(kr, 'K-reopened-panel');
await kr.close();
// an agent that was stopped by "finished" goes on at "reopened": the stand-in reads both entries and takes the new part
assert(/part 3 taken: 1 paragraphs from chapter 3/.test(await agent('step', PARTS, MODEL)),
       'the stand-in, which stopped at "finished", goes on at "reopened" and takes part 3 (its batch it cannot make: the model has two paragraphs)');
// THE CHATBOT ROAD beside it: text sent as a PDF with its pages onto a book nobody is making, as blank chunks
await py(['-c', `import pymupdf
d = pymupdf.open()
for lines in ([(92, "Il gatto dorme sul divano tutto il giorno e non si muove"), (72, "mai, nemmeno quando il cane abbaia forte alla porta e poi"), (72, "Si sveglia lentamente.")],
              [(92, "Il cane corre nel giardino con la palla rossa e salta sopra"), (72, "sopra la siepe bassa fino alla strada del paese vicino e poi si"), (72, "Tutti sono felici oggi.")]):
    p = d.new_page()
    for i, (x, t) in enumerate(lines):
        p.insert_text((x, 80 + 16 * i), t, fontsize=11)
d.save(${JSON.stringify(TMP + '/two-pages.pdf')})`]);
const kc = await kctx.newPage();
watch(kc, 'phone');
await kc.goto(PN + '/books/add/?path=extend');
await kc.waitForSelector('#lane-extend:not([hidden])');
await kc.selectOption('#addinto', '/books/english/the-clock');
assert(await kc.$eval('#addwho', e => !e.hidden) && await kc.$eval('#addwho_me', r => r.checked), 'a finished book of the agent\'s offers the hand way, chosen');
await kc.setInputFiles('#apfile', TMP + '/two-pages.pdf');
await kc.fill('#appages', '1-1');
assert(/two-pages\.pdf, \d+ kB\./.test(await kc.$eval('#apfilenote', e => e.textContent)) && !/ignored/.test(await kc.$eval('#appagesnote', e => e.textContent)),
       'the file and its page range are named before anything is sent');
await kc.click('#addto');
await waitText(kc, '#addresult', /Added\./, 60000);
const ch3 = await Deno.readTextFile(BOOK + '/source/paras/ch3_p00.txt');
eq(ch3.trim(), 'Il cane corre nel giardino con la palla rossa e salta sopra sopra la siepe bassa fino alla strada del paese vicino e poi si Tutti sono felici oggi.',
   'the PDF\'s page 1 (counted from 0) was read by lib/sourcetext.py and added as blank chunks: page 0 is not in it');
assert(await exists(BOOK + '/ch3.tex'), 'a new chapter was written');
await views(kc, 'K-add-extend-file', {full: true});
await kc.close();
await kctx.close();

/* ================= l) a prompt of the person's own for the instructions ================= */
console.log('l) a prompt of the person\'s own for the instructions, chosen in the row\'s menu');
{
  const lctx = await context(B);
  const own = await lctx.newPage();
  watch(own, 'computer');
  await own.goto(B + '/books/add/');
  await own.click('.path[data-path="llm"]');
  await own.waitForSelector('#lane-llm:not([hidden])');
  await own.waitForSelector('#instrmount .llmrow');
  const MENU = '#instrmount .llmrow-pm select';
  // THE MENU IS THE ROW'S (lane F's): where this tree has none there is nothing to drive, and the server's own side
  // of it -- a prompt written into AGENTS.md when the folder is made -- is held by tests/test_making.py
  let hasMenu = true;
  try { await own.waitForSelector(MENU, {timeout: 6000}); } catch (e) { hasMenu = false; }
  if (!hasMenu) {
    console.log('   (this row has no prompt menu in this tree: nothing to drive here)');
  } else {
    await own.evaluate(async () => (await fetch('/settings/api/prompts/save', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({surface: 'book-new', kind: 'added', name: 'my book rules', text: 'Never gloss the names of people.'})})).json());
    await own.reload();
    await own.click('.path[data-path="llm"]');
    await own.waitForSelector('#lane-llm:not([hidden])');
    await own.waitForFunction(sel => [...document.querySelectorAll(sel + ' option')].some(o => o.textContent === 'my book rules'), MENU);
    assert(true, 'a prompt of mine for the instructions is in the menu beside copy the instructions');
    await own.selectOption('#lang', 'en');
    await own.fill('#title', 'The Bell');
    await own.fill('#title_latin', 'The Bell');
    await own.fill('#slug', '');
    await own.fill('#author', 'a fable');
    await own.fill('#author_latin', 'a fable');
    await own.setInputFiles('#original', TMP + '/the-clock.txt');
    await own.waitForFunction(() => !document.querySelector('#mkfolder').disabled);
    await own.selectOption(MENU, {label: 'my book rules'});
    if (!await own.$eval('#ishow', d => d.open)) await own.click('#ishow summary');
    await own.waitForFunction(() => /· custom: my book rules/.test(document.querySelector('#itext').textContent.split('\n')[0]) &&
                                     /Never gloss the names of people\.\s*$/.test(document.querySelector('#itext').textContent), null, {timeout: 20000});
    const bellShown = await own.$eval('#itext', e => e.textContent);
    assert(/Write only inside this folder/.test(bellShown), 'the person\'s words come after Parseh\'s, which are all there');
    await own.click('#mkfolder');
    await own.waitForSelector('#mkcopy', {timeout: 60000});
    const BELL = INSTALL + '/books/english/the-bell';
    eq(await own.$eval('.bigpath', e => e.textContent), BELL, 'the folder is made');
    eq(await Deno.readTextFile(BELL + '/AGENTS.md'), bellShown, 'its AGENTS.md is the text the page showed, with the person\'s prompt in it');
    assert(JSON.parse(await Deno.readTextFile(BELL + '/making.json')).instructions.prompt.length > 3,
           'making.json keeps which prompt it was, so that the instructions can be written again with it');
  }
  await own.close();
  await lctx.close();
}

/* ================= j) last ================= */
console.log('j) nothing broke, nothing of the owner\'s was touched');
const rest = [...errors];
for (const [label, status, url] of DELIBERATE) {
  const at = rest.findIndex(e => e.label === label && e.text.includes('status of ' + status) && url.test(e.url));
  assert(at >= 0, label + ' was refused ' + status + ' at ' + url + ', on purpose');
  rest.splice(at, 1);
}
// (This used to let through the one error the harness could not avoid: lib/prefs.py wrote the preferences file
// through ONE temporary name, so two writes at once -- pages that navigate together, on servers that share this
// scratch config/ -- made one of them fail with a 400 from /__prefs, which the browser logged: 379 of 3000 writes,
// reproduced without a browser.  It writes through a name of its own, under one lock, now (a0.5.0), and nothing
// passes here that is not on the DELIBERATE list.)
eq(rest, [], 'nothing else threw or logged an error');
assert(!/Traceback/.test(logs.join('')), 'no server printed a traceback: ' + (logs.join('').match(/Traceback[\s\S]{0,600}/) || [''])[0]);
eq(await py(['-c', OWN]), ownBefore, 'the checkout\'s books/ and config/ are exactly as they were');
console.log('\n%d checks passed', passed);
} catch (e) {
  failure = e;
} finally {
  try { await browser.close(); } catch { /* gone */ }
  for (const sv of servers) { try { sv.kill(); } catch { /* gone */ } }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true});
}
if (failure) { console.error(failure); Deno.exit(1); }
Deno.exit(0);
