// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the HTML export (TO-DO §8.38 and §9.7; markdown/app/
// webexport.py): a document's Download ▾ → "HTML page, for a website
// (.html)" and a deck's "Export selected to HTML", each clicked on its real
// page (tests/decks_harness.py: the studio's own server, then Parseh's), and
// the two files they give opened FROM DISK, as a student without Parseh
// opens them, with every request the browser makes recorded.  Each press is
// a fetch under a bar and never a navigation (TO-DO §2.28): the bar shows
// where the press was, a computer held 20 s is waited out, the file is the
// computer's own bytes under its own name, and a refused or failed export is
// said plainly with Try again.  The files:
//   * nothing is asked of any server: the one request that leaves a file is
//     the YouTube player the document embeds (answered here by a stand-in),
//     which -- served from a website -- is told the site and no more, as
//     YouTube demands; a link followed says nothing of where it was
//   * the exercises answer and mark; the pictures and the maths are drawn;
//     the recordings play, and a clip is cut to its stretch (ffmpeg here)
//   * both pages open on Sepia (TO-DO §2.26) -- though the studio was
//     showing Dark when they were made, on a dark system, in a browser
//     profile made that moment, and before their script has run -- and the
//     Aa menu still sizes the text and changes the theme, and a reload
//     forgets both: nothing is written -- local and session storage,
//     cookies, IndexedDB and the cache stay empty, whatever the page is
//     asked to do
//   * nothing of the studio's editing, nor of the Markdown, is on the page
//   * the deck's page crams the picked exercises (and only those) to the end:
//     a wrong one comes back, the tally and the lists, "Cram these again";
//     and the deck itself is as it was, nothing scheduled
//   * the foot says the page was exported from Parseh and links Parseh's
//     GitHub page and its guide, each opening in a tab of its own while the
//     page keeps its answers
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/html_export.mjs
//   EXPORT_MODES=studio (or parseh) runs only that one; SHOTS=<dir> also
//   saves screenshots of the two files
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('EXPORT_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
// where the foot of every exported page points: the project's repository and the guide's permanent address
// (lib/project.py; pinned here as literals, because a page exported today carries them for ever)
const GITHUB = 'https://github.com/parseh-io/Parseh';
const GUIDE = 'https://parseh.io/guide';
const FOOT = 'This page was exported from Parseh. Parseh on GitHub · Parseh’s guide';
const YOUTUBE = 'https://www.youtube-nocookie.com/';
// the starter's film on YouTube itself, from where its window begins
const WATCH = 'https://www.youtube.com/watch?v=aqz-KE-bpKQ&t=10s';
// the Italian starter: an exercise of every kind, pictures, a recording and
// a clip of it, a formula, a video, footnotes, sections, glosses
const STARTER = await Deno.readTextFile(`${root}/markdown/exlex/starters/it.md`);
const ASSETS = `${root}/markdown/exlex/starters/assets`;
const BLOCKS = STARTER.match(/^:::exercise[^\n]*\n[\s\S]*?^:::[ \t]*$/gm);

async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/decks_harness.py', mode], cwd: root,
                                         stdout: 'piped', stderr: 'inherit'}).spawn();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

/* A file opened from disk -- or, with `site`, off a website that serves it
   -- in a context of its own that records every request and answers the
   only addresses the page may send the browser to (YouTube's player, and
   the two links of its foot) with a stand-in, so that nothing here needs
   the network and anything else fails.  `heard` is what each stand-in was
   asked, with the Referer it was asked with. */
async function openFile(browser, file, options = {}, site = null) {
  const ctx = await browser.newContext(options);
  const requests = [], errors = [], heard = [];
  ctx.on('request', r => { const u = r.url(); if (!/^(data|blob):/.test(u)) requests.push(u); });
  await ctx.route(/^https?:/, async route => {
    const u = route.request().url();
    if (site && u.startsWith(site)) return route.continue();
    if (u.startsWith(YOUTUBE) || [GITHUB, GUIDE, WATCH].includes(u)) {
      heard.push({url: u, referer: (await route.request().allHeaders())['referer'] || null});
      return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>elsewhere</title>'});
    }
    return route.abort();
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  // which recordings played, from the page's first moment
  await page.addInitScript(() => {
    window.__played = [];
    document.addEventListener('play', e => window.__played.push(
      {src: e.target.currentSrc || e.target.src, cut: e.target.dataset.cut === '1'}), true);
  });
  const url = site ? site + file.replace(/^.*\//, '') : 'file://' + file;
  await page.goto(url);
  return {ctx, page, url, requests, errors, heard};
}

/* The folder of `file`, served as a plain static website would serve it. */
function website(file) {
  const dir = file.replace(/\/[^/]*$/, '');
  const server = Deno.serve({hostname: '127.0.0.1', port: 0, onListen() {}}, async req => {
    const name = decodeURIComponent(new URL(req.url).pathname.slice(1));
    try {
      return new Response(await Deno.readFile(`${dir}/${name}`), {headers: {'Content-Type': 'text/html; charset=utf-8'}});
    } catch (_) {
      return new Response('not here', {status: 404});
    }
  });
  return {server, site: `http://127.0.0.1:${server.addr.port}/`};
}

/* Waits until `fn(arg)` is true in the page.  Not page.waitForFunction: the
   file's own Content-Security-Policy refuses the eval that polls with (no
   'unsafe-eval'), as it should -- page.evaluate reaches the page from the
   browser's side, which a page's rules do not govern. */
async function until(page, fn, arg = null, timeout = 8000) {
  const end = Date.now() + timeout;
  while (!(await page.evaluate(fn, arg))) {
    if (Date.now() > end) throw Error('timed out waiting for ' + String(fn).slice(0, 140));
    await page.waitForTimeout(50);
  }
}

/* Which theme a page is on: the name its <body> carries, what Aa says, and
   the colour actually painted -- so that a sepia named and never painted
   would not pass. */
const look = page => page.evaluate(() => [document.body.dataset.theme || 'paper',
  document.querySelector('#xp-theme').value, getComputedStyle(document.body).backgroundColor]);
// the page's script has run: its Aa has painted, and set the column's width
const painted = page => until(page, () => !!document.documentElement.style.getPropertyValue('--xp-width'));

/* A STUDENT'S FIRST VISIT, twice over (TO-DO §2.26).  The file opened from
   the disk in a browser profile made that moment -- nothing stored anywhere,
   by any page -- on a system set to dark; and in a browser that runs no
   script, where what the page is before its script has run is all there is.
   Both must be the `sepia` the page was measured opening on. */
async function firstVisits(browser, t, file, sepia) {
  const {eq} = t;
  const dir = await Deno.makeTempDir({prefix: 'parseh-html-export-profile-'});
  try {
    const fresh = await chromium.launchPersistentContext(dir, {executablePath: Deno.env.get('CHROME_BIN'),
                                                               headless: true, colorScheme: 'dark'});
    try {
      const page = fresh.pages()[0] || await fresh.newPage();
      await page.goto('file://' + file);
      await painted(page);
      eq(await look(page), ['sepia', 'sepia', sepia],
         'in a browser profile made this moment, on a dark system, the page opens on Sepia');
    } finally {
      await fresh.close();
    }
  } finally {
    await Deno.remove(dir, {recursive: true}).catch(() => {});
  }
  const bare = await browser.newContext({javaScriptEnabled: false});
  try {
    const page = await bare.newPage();
    await page.goto('file://' + file);
    eq(await page.evaluate(() => [!!document.documentElement.style.getPropertyValue('--xp-width'),
                                  document.body.dataset.theme, getComputedStyle(document.body).backgroundColor]),
       [false, 'sepia', sepia], 'and before its script has run -- here, never -- it is Sepia already');
  } finally {
    await bare.close();
  }
}

// what the page could have kept, anywhere the browser keeps things
const kept = page => page.evaluate(async () => {
  let dbs = -1, cached = 0;
  try { dbs = (await indexedDB.databases()).length; } catch (_) { dbs = 0; }
  try { cached = self.caches ? (await caches.keys()).length : 0; } catch (_) { cached = 0; }
  return {local: localStorage.length, session: sessionStorage.length, cookie: document.cookie,
          indexedDB: dbs, caches: cached};
});
const NOTHING = {local: 0, session: 0, cookie: '', indexedDB: 0, caches: 0};

/* The options of every choice exercise in `scope` that its answer holds,
   clicked as a student clicks them (the answers are in the page, the
   owner's choice): all of them, or -- `wrong` -- one that is not. */
async function answerChoice(ex, wrong = false) {
  const options = ex.locator(`.ex-option[data-correct="${wrong ? 0 : 1}"]`);
  const n = wrong ? 1 : await options.count();
  for (let i = 0; i < n; i++) await options.nth(i).click();
}

/* FETCHED UNDER A BAR, AND THE DOCUMENT NEVER LEAVES THE SCREEN (TO-DO
   §2.28).  The owner, from another device, pressed HTML page and landed on
   "Parseh cannot be reached".  Here the computer's answer is held for `hold`
   ms, then refused, then refused with a reason: each press shows the bar
   where the menu was and ends in the file -- the computer's own bytes -- or
   in a sentence with Try again, and never in a navigation. */
async function underABar(page, t, {doc, href, hold}) {
  const {assert, eq} = t;
  const link = page.locator('#dl-html');
  eq(new URL(await link.evaluate(a => a.href)).pathname, href,
     'the entry is still a plain link to the page, for a browser that runs no script');
  const at = page.url(), moves = [], served = [];
  const onNav = f => { if (f === page.mainFrame()) moves.push(f.url()); };
  page.on('framenavigated', onNav);
  let how = {hold: 0, fail: ''};
  const route = new RegExp(`/download/${doc.id}/html(\\?|$)`);
  await page.route(route, async r => {
    if (how.fail === 'refused') return r.abort('connectionrefused');
    if (how.fail === 'refusal')
      return r.fulfill({status: 500, contentType: 'application/json',
                        body: JSON.stringify({ok: false, error: 'the page could not be made'})});
    const res = await r.fetch();
    const body = await res.body();
    served.push(body);
    if (how.hold) await new Promise(ok => setTimeout(ok, how.hold));
    await r.fulfill({response: res, body});
  });
  const panel = page.locator('header.topbar .made-work');
  const failed = page.locator('header.topbar .made-work.err');
  const press = async () => {
    await page.click('details.dropdown > summary:text-is("Download ▾")');
    await link.click();
  };
  const theirs = async download => Buffer.from(await Deno.readFile(await download.path())).equals(served[served.length - 1]);
  const offline = async () => /cannot be reached|not reachable/i.test(await page.title());
  try {
    how = {hold, fail: ''};
    const t0 = Date.now();
    const [download] = await Promise.all([page.waitForEvent('download', {timeout: hold + 60000}), (async () => {
      await press();
      await panel.locator('.bar.loose').waitFor({state: 'visible', timeout: 3000});
      eq(await panel.locator('.made-say').textContent(), `Making the HTML page of “${doc.title}”…`,
         'the press shows the bar at once, where the menu was, saying what it makes');
      eq(await page.evaluate(() => [...document.querySelectorAll('header.topbar details.dropdown')].some(d => d.open)), false,
         'and the menu has closed');
      assert(await link.evaluate(a => a.classList.contains('disabled')), 'the entry rests while the page is made');
      await page.waitForTimeout(hold - 2000);
      const when = await panel.locator('.made-when').textContent();
      assert(await panel.locator('.bar.loose').isVisible() && parseInt(when, 10) >= Math.floor((hold - 3000) / 1000),
             `${(hold - 2000) / 1000} s on, the bar is still there, counting: ${when}`);
      eq([page.url(), await offline()], [at, false], 'and the page is still the document');
    })()]);
    const took = Date.now() - t0;
    assert(took >= hold, `the page arrived when the computer answered (${took} ms), as a download`);
    eq(download.suggestedFilename(), doc.id.replace(/-[0-9a-f]{6}$/, '') + '.html', 'under the name the computer gave it');
    assert(await theirs(download), `byte for byte what the computer sent (${served[served.length - 1].length} bytes)`);
    await panel.waitFor({state: 'detached', timeout: 5000});
    await page.waitForFunction(n => document.querySelector('#toast').textContent === n,
                               `HTML page exported: ${download.suggestedFilename()}`, {timeout: 5000});
    assert(!(await link.evaluate(a => a.classList.contains('disabled'))), 'the bar is gone, the toast says where it went, and the entry is back');

    how = {hold: 0, fail: 'refused'};
    await press();
    await failed.waitFor({state: 'visible', timeout: 5000});
    eq(await failed.locator('.made-say').textContent(),
       'The HTML page was not saved: the connection to Parseh failed before it arrived.',
       'a connection refused is said where the bar was');
    eq(await failed.evaluate(b => [!b.querySelector('[data-x="again"]').hidden, b.querySelector('[data-x="stop"]').textContent,
                                   b.querySelector('.bar').hidden]),
       [true, 'Close', true], 'with Try again and Close, and no bar');
    how = {hold: 0, fail: ''};
    const [again] = await Promise.all([page.waitForEvent('download'), failed.locator('[data-x="again"]').click()]);
    assert(await theirs(again), 'Try again, with the computer answering, gives the page');
    await panel.waitFor({state: 'detached', timeout: 5000});

    how = {hold: 0, fail: 'refusal'};
    await press();
    await failed.waitFor({state: 'visible', timeout: 5000});
    eq(await failed.locator('.made-say').textContent(), 'The HTML page was not saved: the page could not be made.',
       'a refusal is said in the computer\'s own words');
    await failed.locator('[data-x="stop"]').click();
    await panel.waitFor({state: 'detached', timeout: 5000});
    eq([moves, page.url(), await offline()], [[], at, false], 'through all of it the page never navigated');
  } finally {
    page.off('framenavigated', onNav);
    await page.unroute(route);
  }
}

async function suite(browser, mode, tmp) {
  const {proc, info} = await startHarness(mode);
  const S = info.studio;                 // "" or "/studio"
  const url = p => `http://127.0.0.1:${info.port}${p}`;
  let passed = 0;
  const assert = (v, m) => { if (!v) throw new Error(`FAIL (${mode}): ` + m); passed++; console.log('  ok', m); };
  const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
    m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
  const studioErrors = [];
  const watch = (page, name) => {
    page.on('pageerror', e => studioErrors.push(`${name}: ${e.message}`));
    page.on('console', m => {
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) studioErrors.push(`${name} console: ${m.text()}`);
    });
  };
  const ctx = await browser.newContext();
  const request = ctx.request;
  try {
    /* ---------------- the document: Download ▾ on its page ---------------- */
    console.log(`the document's page (${mode}: studio at "${S || '/'}")`);
    const made = await request.post(url(`${S}/api/docs`), {data: {markdown: STARTER}});
    eq(made.status(), 201, 'the starter is made a document (its pictures and recording adopted)');
    const doc = (await made.json()).meta;
    const page = await ctx.newPage();
    watch(page, 'doc');
    await page.goto(url(`${S}/doc/${doc.id}`));
    // THE STUDIO SHOWING DARK as it makes the page, by its own ◐ (the bar's
    // one theme button; the sheet has no menu of its own any more): what the
    // studio shows is its reader's, and the file must start on Sepia anyway
    // (below, for both files -- the deck's page follows the studio's theme)
    for (let i = 0; i < 3 && (await page.evaluate(() => document.body.dataset.theme)) !== 'dark'; i++)
      await page.click('.topbar [data-parseh-theme]');
    eq(await page.evaluate(() => document.body.dataset.theme), 'dark', 'the studio is showing Dark as it exports');
    await page.click('details.dropdown > summary:text-is("Download ▾")');
    const entries = await page.locator('details.dropdown[open] .menu a').evaluateAll(as => as.map(a => a.id || a.textContent.trim()));
    eq(entries.slice(entries.indexOf('dl-pdf'), entries.indexOf('dl-pdf') + 2), ['dl-pdf', 'dl-html'],
       'Download ▾ offers the page right under the PDF');
    eq((await page.locator('#dl-html').textContent()).trim(), 'HTML page, for a website (.html)', 'and says what it is');
    // the document as the studio holds it: its Markdown, its pictures, its recordings
    const held = async () => Promise.all(['download/%s/md', 'api/docs/%s/images', 'api/docs/%s/audio']
      .map(async p => (await request.get(url(`${S}/${p.replace('%s', doc.id)}`))).text()));
    const before = await held();
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('#dl-html')]);
    const docName = download.suggestedFilename();
    eq(docName, doc.id.replace(/-[0-9a-f]{6}$/, '') + '.html', 'the file is named after the document');
    const docPath = `${tmp}/${mode}-${docName}`;
    await download.saveAs(docPath);
    eq(await held(), before, 'the document is as it was');
    await underABar(page, {assert, eq}, {doc, href: `${S}/download/${doc.id}/html`,
                                         hold: mode === 'parseh' ? 20000 : 3000});

    /* ---------------- the deck: Export selected to HTML ---------------- */
    console.log(`the deck's page (${mode})`);
    const deck = (await (await request.post(url('/exercises/api/decks'), {data: {name: 'Esercizi di prova', lang: 'it'}})).json()).deck;
    const api = `/exercises/api/decks/${deck.path}`;
    for (const [kind, name, type] of [['images', 'starter-apple.svg', 'image/svg+xml'], ['images', 'starter-house.svg', 'image/svg+xml'],
                                      ['audio', 'starter-chime.mp3', 'audio/mpeg']]) {
      const r = await request.post(url(`${api}/${kind}?name=${name}`),
                                   {data: Buffer.from(await Deno.readFile(`${ASSETS}/${kind}/${name}`)), headers: {'Content-Type': type}});
      assert(r.ok(), `${name} uploaded to the deck`);
    }
    for (const markdown of BLOCKS) {
      const r = await request.post(url(`${api}/items`), {data: {markdown}});
      if (!r.ok()) throw Error(`FAIL (${mode}): an exercise of the starter was refused: ${await r.text()}`);
    }
    const listed = (await (await request.get(url(api))).json()).items;
    eq(listed.length, BLOCKS.length, `the deck holds the starter's ${BLOCKS.length} exercises`);
    const deckPage = await ctx.newPage();
    watch(deckPage, 'deck');
    await deckPage.goto(url(`/exercises/deck/${deck.path}/`));
    await deckPage.waitForSelector('.dk-row');
    const exportButton = deckPage.locator('#btn-export-html');
    assert(await exportButton.isVisible() && await exportButton.isDisabled(), '“Export selected to HTML” is there, and idle while nothing is selected');
    eq(await exportButton.evaluate(b => b.previousElementSibling && b.previousElementSibling.id), 'btn-cram', 'right beside Cram exercises');
    // everything, by a click and a Shift-click, then two left out again
    await deckPage.locator('.dk-row .dk-select').first().check();
    await deckPage.locator('.dk-row .dk-select').last().click({modifiers: ['Shift']});
    const left = [listed[1], listed[4]];
    for (const it of left) await deckPage.locator(`.dk-row[data-id="${it.id}"] .dk-select`).uncheck();
    const picked = listed.length - left.length;
    eq(await deckPage.locator('#browse-selected').textContent(), `${picked} selected`, `${picked} selected`);
    assert(await exportButton.isEnabled(), 'the button wakes with a selection');
    const deckBefore = await (await request.get(url(api))).text();
    // held a moment, so the bar can be seen: under the row of buttons it was asked from
    const exportRoute = /\/export-html(\?|$)/;
    await deckPage.route(exportRoute, async r => {
      const res = await r.fetch();
      await new Promise(ok => setTimeout(ok, 2500));
      await r.fulfill({response: res});
    });
    const [deckDownload] = await Promise.all([deckPage.waitForEvent('download'), (async () => {
      await exportButton.click();
      const bar = deckPage.locator('.dk-bulkbar + .made-work');
      await bar.locator('.bar.loose').waitFor({state: 'visible', timeout: 2000});
      eq(await bar.locator('.made-say').textContent(), `Exporting ${picked} exercises of “Esercizi di prova” to HTML…`,
         'the click shows the bar under the row it was pressed in, saying what it exports');
      eq([(await exportButton.textContent()).trim(), await exportButton.isDisabled()], ['Exporting…', true],
         'and the button rests, saying so');
    })()]);
    await deckPage.unroute(exportRoute);
    await deckPage.locator('.made-work').waitFor({state: 'detached', timeout: 5000});
    const deckName = deckDownload.suggestedFilename();
    eq(deckName, `${deck.slug}.html`, 'the file is named after the deck');
    await deckPage.waitForFunction(t => document.querySelector('#toast').textContent === t,
                                   `${picked} exercises exported: ${deck.slug}.html`, {timeout: 8000})
      .catch(async () => { throw Error(`FAIL (${mode}): the toast says “${await deckPage.locator('#toast').textContent()}”`); });
    assert(true, 'the toast says how many went, and where');
    assert(await exportButton.isEnabled() && (await exportButton.textContent()).trim() === 'Export selected to HTML',
           'and the button is itself again');
    const deckPath = `${tmp}/${mode}-${deckName}`;
    await deckDownload.saveAs(deckPath);
    eq(await (await request.get(url(api))).text(), deckBefore, 'the deck is as it was: nothing touched, nothing scheduled');

    // the phone's layout of the same page has no such button
    const phone = await browser.newContext();
    try {
      await phone.addInitScript(() => { try { localStorage.setItem('parseh_mode', 'mobile'); } catch (_) { /* none */ } });
      const pp = await phone.newPage();
      await pp.goto(url(`/exercises/deck/${deck.path}/`));
      await pp.waitForFunction(() => document.documentElement.dataset.mode === 'mobile');
      assert(!(await pp.locator('#btn-export-html').isVisible()), 'the mobile layout has no export (browser only)');
    } finally {
      await phone.close();
    }
    assert(studioErrors.length === 0, 'no errors on the studio pages' + (studioErrors.length ? ':\n    ' + studioErrors.join('\n    ') : ''));

    /* ---------------- the document's file, from disk ---------------- */
    console.log(`the document's file, from disk (${mode})`);
    await documentFile(browser, docPath, {assert, eq, mode});

    /* ---------------- the deck's file, from disk ---------------- */
    console.log(`the deck's file, from disk (${mode})`);
    await deckFile(browser, deckPath, {assert, eq, mode, picked, left});
  } finally {
    await ctx.close();
    try { proc.kill('SIGTERM'); } catch (_) { /* already gone */ }
    await proc.status;
  }
  console.log(`${mode}: ${passed} checks passed\n`);
  return passed;
}

/* The foot, on either file: what it says, where it points, and that
   following a link leaves the page -- and every answer on it -- alone.
   `state()` is what the page must still show after. */
async function footChecks(t, f, state) {
  const {assert, eq} = t, {ctx, page} = f;
  const foot = page.locator('footer.xp-foot');
  eq(await foot.count(), 1, 'one foot');
  await foot.scrollIntoViewIfNeeded();
  assert(await foot.isVisible(), 'the foot is shown, below the page');
  eq((await foot.innerText()).trim(), FOOT, 'it says the page was exported from Parseh');
  eq(await foot.locator('a').evaluateAll(as => as.map(a => [a.href, a.target, a.rel, a.textContent])),
     [[GITHUB, '_blank', 'noopener noreferrer', 'Parseh on GitHub'], [GUIDE, '_blank', 'noopener noreferrer', 'Parseh’s guide']],
     'and links Parseh’s GitHub page and its guide, each into a tab of its own');
  const before = await state(), at = page.url();
  for (const [i, where] of [[0, GITHUB], [1, GUIDE]]) {
    const [tab] = await Promise.all([ctx.waitForEvent('page'), foot.locator('a').nth(i).click()]);
    await tab.waitForLoadState();
    eq(tab.url(), where, `the link opens ${where} in a new tab`);
    assert(await tab.evaluate(() => window.opener === null), 'which cannot reach back into the page');
    await tab.close();
  }
  eq(page.url(), at, 'the page stays where it was');
  eq(await state(), before, 'and keeps everything answered on it');
}

async function documentFile(browser, file, t) {
  const {assert, eq, mode} = t;
  const f = await openFile(browser, file);
  const {page, requests, errors} = f;
  let opened = null;
  try {
    await until(page, () => document.querySelectorAll('#sheet .exercise').length > 0);
    // SEPIA FROM THE START (TO-DO §2.26): the studio was showing Dark when
    // this was made, and this browser has nothing stored
    await painted(page);
    opened = await look(page);
    eq(opened.slice(0, 2), ['sepia', 'sepia'], 'the page opens on Sepia, not the Dark the studio was showing, and Aa says so');
    // (a follow-up holds its steps, which are exercises of the page too: they are not counted among the starter's blocks)
    eq(await page.locator('#sheet .exercise:not(.ex-step .exercise)').count(), BLOCKS.length, `all ${BLOCKS.length} exercises are on the page`);
    eq(await page.locator('#sheet [contenteditable], #sheet textarea, .ex-edit, .ex-to-deck, .video-edit, .audio-edit').count(), 0,
       'nothing on it edits');
    eq(await page.locator('[data-tl-src], [data-src-line], [data-occ], [data-editor-preview]').count(), 0,
       'and nothing on it leads back to the Markdown');

    // what travels inside it: pictures, recordings, the maths
    const images = await page.evaluate(() => Promise.all([...document.images].map(i =>
      i.decode().then(() => [i.src.slice(0, 5), i.naturalWidth > 0], () => [i.src.slice(0, 5), false]))));
    assert(images.length > 0 && images.every(([src, ok]) => src === 'data:' && ok), `its ${images.length} pictures are inside it, and drawn`);
    await until(page, () => [...document.querySelectorAll('#sheet .math')].every(m => m.querySelector('svg')),
                               null, 30000);
    assert(await page.locator('#sheet .math').count() > 0, 'the formulas are drawn, by the MathJax inside it');
    const audios = await page.evaluate(async () => {
      const all = [...document.querySelectorAll('#sheet figure.audio audio')].filter(a => !a.closest('.exercise'));
      await Promise.all(all.map(a => a.readyState >= 1 ? 0 : new Promise(r => a.addEventListener('loadedmetadata', r, {once: true}))));
      return all.map(a => ({blob: a.src.startsWith('blob:'), cut: a.dataset.cut === '1', frag: a.dataset.frag || '',
                            duration: a.duration, box: !!a.closest('figure').dataset.start}));
    });
    eq(audios.length, 2, 'the recording and its clip');
    assert(audios.every(a => a.blob), 'both played from inside the file');
    assert(Math.abs(audios[0].duration - 1.5) < 0.1 && !audios[0].cut, `the recording whole (${audios[0].duration.toFixed(2)} s)`);
    // (the prose's two: an exercise's recordings are the exercises' own)
    const clip = page.locator('#sheet figure.audio:not(.exercise *) audio').nth(1);
    if (audios[1].cut) {
      assert(Math.abs(audios[1].duration - 0.4) < 0.15 && !audios[1].box,
             `the clip cut to its stretch by ffmpeg (${audios[1].duration.toFixed(2)} s of 1.5)`);
    } else {
      eq(audios[1].frag, '#t=0,0.4', 'no ffmpeg here: the clip plays its window of the whole');
    }
    // played the way a student plays it: the player's own ▶
    const box = await clip.boundingBox();
    await clip.click({position: {x: 18, y: box.height / 2}});
    await until(page, () => window.__played.length > 0, null, 8000);
    await until(page, () => { const a = [...document.querySelectorAll('#sheet figure.audio audio')].filter(x => !x.closest('.exercise'))[1]; return a.paused && a.currentTime > 0; },
                               null, 8000);
    const heard = await clip.evaluate(a => a.currentTime);
    assert(heard > 0.2 && heard < 0.6, `▶ plays the clip, and it stops at its end (${heard.toFixed(2)} s)`);

    // the exercises: every choice exercise answered right but one, then checked
    // (the steps of a follow-up are answered one by one, below)
    const choice = page.locator('#sheet .exercise[data-primitive="choice"]:not(.ex-step .exercise)');
    const nChoice = await choice.count();
    const wrongAt = await page.evaluate(() => [...document.querySelectorAll('#sheet .exercise[data-primitive="choice"]:not(.ex-step .exercise)')]
      .findIndex(e => e.dataset.subtype === 'single-choice'));
    for (let i = 0; i < nChoice; i++) await answerChoice(choice.nth(i), i === wrongAt);
    await page.click('.ex-correct-all');
    const marks = await page.evaluate(() => [...document.querySelectorAll('#sheet .exercise:not(.ex-step .exercise)')].map(e =>
      [e.dataset.primitive, e.dataset.subtype, e.classList.contains('correct') ? 'right' : e.classList.contains('incorrect') ? 'wrong' : '-']));
    const choiceMarks = marks.filter(m => m[0] === 'choice').map(m => m[2]);
    eq(choiceMarks, choiceMarks.map((_, i) => i === wrongAt ? 'wrong' : 'right'),
       `Check exercises marks the ${nChoice - 1} right answers right and the wrong one wrong`);
    eq(marks.filter(m => ['fill-blanks', 'match-translations'].includes(m[1])).map(m => m[2]), ['wrong', 'wrong'],
       'and an exercise nobody answered wrong');
    const score = await page.locator('.ex-score').textContent();
    const scored = await page.locator('#sheet .exercise[data-scored="1"]').count();
    eq(score, `${marks.filter(m => m[2] === 'right').length} / ${scored} correct`, `the score: “${score}”`);
    assert(await page.locator('#sheet .exercise[data-primitive="choice"]').nth(wrongAt).locator('.ex-option.answer-wrong').count() === 1,
           'the wrong option is shown wrong');
    // the transliterations switch works, and writes nowhere
    await page.locator('.ex-translit-switch').first().click();
    assert(await page.evaluate(() => document.body.classList.contains('ex-hide-transliteration')), 'Hide transliterations hides them');
    // a flashcard, turned as a student turns it, and the 🔊 on its back
    const playedBefore = await page.evaluate(() => window.__played.length);
    const card = page.locator('#sheet .ex-flashcard', {has: page.locator('.ex-card-play')}).first();
    await card.locator('.ex-card-hint').click();
    assert(await card.evaluate(c => c.classList.contains('flipped')), 'a flashcard turns');
    await card.locator('.ex-card-play').click();
    await until(page, n => window.__played.length > n, playedBefore, 8000);
    assert(await page.evaluate(() => window.__played.every(p => p.src.startsWith('blob:'))), 'a flashcard’s recording plays from inside the file too');

    // ⤢ Enlarge: the card large, and Esc puts it away
    await page.locator('#sheet .ex-card-zoom').first().click();
    assert(await page.locator('.ex-zoom-overlay').isVisible(), '⤢ Enlarge opens a flashcard large');
    await page.keyboard.press('Escape');
    eq(await page.locator('.ex-zoom-overlay').count(), 0, 'and Esc puts it away');
    // a footnote, its cloud on a hover
    const note = page.locator('#sheet p .fn').first();
    await note.hover();
    assert(await note.locator('.fncloud').isVisible(), 'a footnote shows its cloud on a hover');
    await page.mouse.move(0, 0);

    // the contents and the glosses
    await page.click('.xp-contents > summary');
    await page.locator('.xp-contents a', {hasText: 'Exercises'}).first().click();
    const hash = await page.evaluate(() => location.hash);
    assert(hash && await page.evaluate(h => !!document.getElementById(decodeURIComponent(h.slice(1))), hash),
           `the contents jump within the page (${hash})`);
    await page.click('.xp-glosses > summary');
    const rows = await page.locator('.xp-glosses tbody tr').count();
    await page.fill('.xp-gl-filter', 'mela');
    const shown = await page.locator('.xp-glosses tbody tr:not([hidden])').count();
    assert(rows > 1 && shown >= 1 && shown < rows, `the glosses filter (${shown} of ${rows} for “mela”)`);
    await page.click('.xp-glosses > summary');

    // the Aa menu: the text's size, and the theme
    const sizeOf = () => page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('#sheet p')).fontSize));
    const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const size0 = await sizeOf();
    await page.click('.xp-aa > summary');
    assert(await page.locator('.xp-aa-menu').isVisible(), 'Aa opens its menu');
    await page.locator('#xp-size').focus();
    for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowRight');
    eq(await page.locator('#xp-size-out').textContent(), '129%', 'the slider says the new size');
    const size1 = await sizeOf();
    assert(Math.abs(size1 / size0 - 22 / 17) < 0.02, `and the text is that much bigger (${size0}px → ${size1}px)`);
    await page.selectOption('#xp-theme', 'paper');
    const paper = await bg();
    eq(await page.evaluate(() => document.body.dataset.theme || 'paper'), 'paper', 'Paper: the start is a default, not a lock');
    await page.selectOption('#xp-theme', 'sepia');
    const sepia = await bg();
    eq(await page.evaluate(() => document.body.dataset.theme), 'sepia', 'Sepia');
    eq(sepia, opened[2], 'the very sepia the page opened on');
    await page.selectOption('#xp-theme', 'dark');
    const dark = await bg();
    eq(await page.evaluate(() => document.body.dataset.theme), 'dark', 'Dark');
    assert(new Set([paper, sepia, dark]).size === 3, `three papers (${paper}, ${sepia}, ${dark})`);
    await page.keyboard.press('Escape');
    assert(!(await page.locator('.xp-aa').evaluate(d => d.open)), 'Escape shuts the menu');
    if (SHOTS) await page.screenshot({path: `${SHOTS}/${mode}-document-dark.png`});

    // opened from the disk, YouTube will not play its player (it names no
    // site): a line under the video says so, and opens it on YouTube
    const line = page.locator('#sheet figure.video .xp-video-note');
    eq(await line.count(), 1, 'from the disk, a line under the video');
    eq(await line.innerText(), 'YouTube plays this video only when the page is on a website — watch it on YouTube',
       'says it plays only on a website');
    eq(await line.locator('a').evaluate(a => [a.href, a.target, a.rel]), [WATCH, '_blank', 'noopener noreferrer'],
       'and links the video on YouTube, from where its window begins');
    const [film] = await Promise.all([f.ctx.waitForEvent('page'), line.locator('a').click()]);
    await film.waitForLoadState();
    eq(film.url(), WATCH, 'which opens in a tab of its own');
    await film.close();

    // the foot, with the answers in place
    await footChecks(t, f, () => page.evaluate(() => [
      document.querySelector('.ex-score').textContent,
      [...document.querySelectorAll('#sheet .exercise')].map(e => e.className).join(' | '),
      [...document.querySelectorAll('#sheet .ex-option.selected')].length, document.body.dataset.theme]));

    // on paper: the sheet and its foot, whose links print their addresses
    await page.emulateMedia({media: 'print'});
    eq(await page.evaluate(() => ['.xp-bar', '.xp-contents', '.xp-glosses'].map(s => getComputedStyle(document.querySelector(s)).display)),
       ['none', 'none', 'none'], 'printed, the bar and the panels are left off');
    eq(await page.evaluate(() => [...document.querySelectorAll('.xp-foot a')].map(a => getComputedStyle(a, '::after').content)),
       [`" (${GITHUB})"`, `" (${GUIDE})"`], 'and the links of the foot print with their addresses');
    await page.emulateMedia({media: 'screen'});

    // nothing asked of any server but YouTube's player; nothing kept
    await page.locator('iframe').scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    eq(await page.locator(`iframe[src^="${YOUTUBE}embed/"]`).count(), 1, 'the video is YouTube’s own player, as the owner chose');
    const away = requests.filter(u => u.split('#')[0] !== f.url && !u.startsWith(YOUTUBE) && ![GITHUB, GUIDE, WATCH].includes(u));
    eq(away, [], 'nothing requested but the file itself and the YouTube player');
    eq(await kept(page), NOTHING, 'nothing written anywhere: storage, cookies, IndexedDB, the cache');
    // and a reload is a fresh page: the choices and the answers gone
    await page.reload();
    await until(page, () => document.querySelectorAll('#sheet .exercise').length > 0);
    await painted(page);
    eq(await page.evaluate(() => [document.body.dataset.theme || 'paper', document.querySelector('#xp-size').value,
                                  document.querySelector('#xp-size-out').textContent,
                                  document.querySelectorAll('#sheet .exercise.correct, #sheet .exercise.incorrect').length,
                                  document.body.classList.contains('ex-hide-transliteration')]),
       ['sepia', '17', '100%', 0, false], 'a reload forgets the size, the theme (Sepia again), the answers and the switch');
    assert(errors.length === 0, 'no page errors, no console errors (none refused by its own rules)' +
           (errors.length ? ':\n    ' + errors.join('\n    ') : ''));
  } finally {
    await f.ctx.close();
  }
  // a reader whose system is dark gets Sepia all the same -- and Dark the
  // moment it is picked
  const d = await openFile(browser, file, {colorScheme: 'dark'});
  try {
    await until(d.page, () => document.querySelectorAll('#sheet .exercise').length > 0);
    await painted(d.page);
    eq(await look(d.page), opened, 'on a dark system the page opens on Sepia all the same, and Aa says so');
    await d.page.click('.xp-aa > summary');
    await d.page.selectOption('#xp-theme', 'dark');
    eq((await look(d.page)).slice(0, 2), ['dark', 'dark'], 'and Dark, picked in Aa, is Dark');
  } finally {
    await d.ctx.close();
  }
  await firstVisits(browser, t, file, opened[2]);
  // on a website: YouTube plays nothing for a player that does not say
  // where it is embedded ("Video player configuration error"), so the player
  // alone is told the site -- its address, and nothing of the page's path --
  // while a link followed says nothing of where it was followed from
  const {server, site} = website(file);
  const w = await openFile(browser, file, {}, site);
  try {
    await until(w.page, () => document.querySelectorAll('#sheet .exercise').length > 0);
    await w.page.locator('iframe').scrollIntoViewIfNeeded();
    for (let i = 0; i < 160 && !w.heard.some(h => h.url.startsWith(YOUTUBE)); i++) await w.page.waitForTimeout(50);
    eq(w.heard.filter(h => h.url.startsWith(YOUTUBE)).map(h => h.referer), [site],
       `served from a website, the YouTube player is told the site (${site}) and no more`);
    eq(await w.page.locator('.xp-video-note').count(), 0, 'and there the player plays: no line under it');
    const [tab] = await Promise.all([w.ctx.waitForEvent('page'), w.page.locator('footer.xp-foot a').first().click()]);
    await tab.waitForLoadState();
    eq(w.heard.filter(h => h.url === GITHUB).map(h => h.referer), [null], 'a link of its foot, followed, does not say where from');
    eq(w.requests.filter(u => u !== w.url && !u.startsWith(YOUTUBE) && u !== GITHUB), [], 'and the page asks the site for nothing but itself');
    assert(w.errors.length === 0, 'no errors on the website either' + (w.errors.length ? ':\n    ' + w.errors.join('\n    ') : ''));
  } finally {
    await w.ctx.close();
    await server.shutdown();
  }
}

async function deckFile(browser, file, t) {
  const {assert, eq, mode, picked, left} = t;
  const f = await openFile(browser, file);
  const {page, requests, errors} = f;
  let opened = null;
  try {
    await page.waitForSelector('#cram-stage .exercise');
    // SEPIA FROM THE START, as the document's (TO-DO §2.26) -- the studio
    // was showing Dark -- and Aa changes it, and changes it back
    await painted(page);
    opened = await look(page);
    eq(opened.slice(0, 2), ['sepia', 'sepia'], 'the page opens on Sepia, not the Dark the studio was showing, and Aa says so');
    await page.click('.xp-aa > summary');
    await page.selectOption('#xp-theme', 'dark');
    eq((await look(page)).slice(0, 2), ['dark', 'dark'], 'Dark, picked in Aa, is Dark');
    await page.selectOption('#xp-theme', 'sepia');
    eq(await look(page), opened, 'and Sepia is the sepia it opened on');
    await page.keyboard.press('Escape');
    const cards = await page.evaluate(() => JSON.parse(document.querySelector('#parseh-cards').textContent));
    eq(cards.length, picked, `the ${picked} picked exercises, and only those`);
    const excerpts = new Set(cards.map(c => c.item.excerpt));
    assert(left.every(it => !excerpts.has(it.excerpt)), 'the two left out are not in it');
    eq(await page.locator('#cram-progress').textContent(), `1 of ${picked}`, `“1 of ${picked}”`);
    eq(await page.locator('.dk-cram-note').textContent(),
       'The exercises come in random order. A wrong answer comes back at the end. Nothing you do here is saved or sent anywhere.',
       'the page says what it does');

    // the whole cram: a choice exercise answered right, any other checked as
    // it stands (wrong, as a rule: it comes back) and skipped when it does;
    // the first flashcard graded Wrong, the rest Correct
    const times = new Map(), first = new Map(), wrongOnce = new Set(), skipped = new Set();
    let flashes = 0, solutions = 0, pictures = 0, steps = 0;
    for (; steps < 120; steps++) {
      const st = await page.evaluate(() => {
        const q = s => document.querySelector(s), vis = s => !!q(s) && !q(s).hidden;
        const ex = q('#cram-stage .exercise');
        const txt = s => (((ex && ex.querySelector(s)) || {}).textContent || '').trim();
        return {done: vis('#cram-done'), progress: q('#cram-progress').textContent,
                key: ex ? [ex.dataset.subtype, txt('.ex-kicker'), txt('.ex-prompt'), txt('.ex-card-front')].join('|') : '',
                primitive: ex ? ex.dataset.primitive : '', check: vis('#cram-check'), show: vis('#cram-show'), next: vis('#cram-next')};
      });
      if (st.done) break;
      const drawn = await page.evaluate(() => Promise.all([...document.querySelectorAll('#cram-stage img')].map(i =>
        i.decode().then(() => i.src.startsWith('data:') && i.naturalWidth > 0, () => false))));
      if (drawn.includes(false)) throw Error(`FAIL (${mode}): a picture not drawn in “${st.key}”`);
      pictures += drawn.length;
      const n = (times.get(st.key) || 0) + 1;
      times.set(st.key, n);
      if (st.primitive === 'chain') {
        // a follow-up, step by step: its choice steps right, a placement step left as it stands, so that it is wrong
        // and comes back, as any exercise that was wrong does -- and is skipped when it does
        if (n > 1) { skipped.add(st.key); await page.click('#cram-skip'); continue; }
        const nSteps = await page.locator('#cram-stage .ex-step').count();
        let checked = 0;
        for (let k = 1; k <= nSteps; k++) {
          const stepEx = page.locator(`#cram-stage .ex-step[data-step="${k}"] > .exercise`);
          if (await stepEx.getAttribute('data-primitive') === 'choice') await answerChoice(stepEx);
          const label = await page.evaluate(() => { const b = document.querySelector('#cram-check:not([hidden])') || document.querySelector('#cram-show:not([hidden])'); return b ? b.id + ':' + b.textContent : ''; });
          if (!/^cram-(check:Check step|show:Show answer)$/.test(label)) throw Error(`FAIL (${mode}): step ${k} of “${st.key}” offers “${label}”`);
          await page.click(label.startsWith('cram-check') ? '#cram-check' : '#cram-show');
          checked++;
          if (k < nSteps) await page.click('#cram-step');
        }
        const said = await page.locator('#cram-result').textContent();
        const m = /^(\d+) of (\d+) steps right$/.exec(said);
        if (!m || checked !== nSteps) throw Error(`FAIL (${mode}): “${st.key}” says “${said}”`);
        first.set(st.key, m[1] === m[2]);
        if (m[1] !== m[2]) wrongOnce.add(st.key);
        await page.click('#cram-next');
        continue;
      }
      if (st.check) {
        if (n > 1) { skipped.add(st.key); await page.click('#cram-skip'); continue; }
        if (st.primitive === 'choice') await answerChoice(page.locator('#cram-stage .exercise'));
        await page.click('#cram-check');
        const said = await page.locator('#cram-result').textContent();
        if (st.primitive === 'choice' && said !== 'Correct') throw Error(`FAIL (${mode}): “${st.key}” answered right, marked “${said}”`);
        first.set(st.key, said === 'Correct');
        if (said !== 'Correct') {
          wrongOnce.add(st.key);
          if (['matching', 'placement'].includes(st.primitive) && await page.locator('#cram-solution:not([hidden]) .exercise').count()) solutions++;
        }
        await page.click('#cram-next');
      } else if (st.show) {
        await page.click('#cram-show');
        await page.waitForSelector('#cram-stage .ex-flashcard.flipped');
        const wrong = n === 1 && flashes++ === 0;
        await page.click(wrong ? '#cram-wrong' : '#cram-correct');
        if (n === 1) first.set(st.key, !wrong);
        if (wrong) wrongOnce.add(st.key);
      } else if (st.next) {
        skipped.add(st.key);
        await page.click('#cram-next');
      } else {
        throw Error(`FAIL (${mode}): no way on from “${st.key}”`);
      }
    }
    eq(times.size, picked, `every picked exercise came up (${picked}), in ${steps} steps`);
    assert([...times.keys()].some(k => k.startsWith('follow-up|')) && [...wrongOnce].some(k => k.startsWith('follow-up|')),
           'a follow-up was among them, done a step at a time in the exported page, and it came back whole because a step was wrong');
    assert(wrongOnce.size > 1 && [...wrongOnce].every(k => times.get(k) === 2), 'every wrong one came back, once');
    assert(solutions > 0, 'a wrong matching or placement exercise shows its correct answer');
    assert(pictures > 0, `the pictures are inside it, and drawn (${pictures} seen)`);
    const played = await page.evaluate(() => window.__played);
    assert(played.length > 0 && played.every(p => p.src.startsWith('blob:')), `the flashcards' recordings play, from inside the file (${played.length})`);
    const right = [...first.values()].filter(Boolean).length;
    const parts = [];
    if (right) parts.push(`${right} right the first time`);
    if (wrongOnce.size) parts.push(`${wrongOnce.size} wrong at least once`);
    if (skipped.size) parts.push(`${skipped.size} skipped`);
    eq(await page.locator('#cram-tally').textContent(), `${picked} exercises: ${parts.join(', ')}.`, 'Practice complete, and the tally');
    eq(await page.locator('#cram-wrong-list li').count(), wrongOnce.size, 'the wrong ones listed');
    eq(await page.locator('#cram-skipped-list li').count(), skipped.size, 'the skipped ones listed');
    await page.locator('#cram-wrong-list .dk-cram-item').first().click();
    // the wrong ones come in the order the cram shuffled them, so the first may be the follow-up: ONE exercise, whose steps
    // are exercises inside it -- it opens solved with every step in it, as any other opens solved
    const solvedOpen = await page.evaluate(() => {
      const all = [...document.querySelectorAll('#cram-wrong-list .dk-cram-solved:not([hidden]) .exercise')];
      const top = all.filter(e => !e.parentElement.closest('.exercise'));
      return {top: top.map(e => e.dataset.subtype), inside: all.length - top.length,
              steps: top.length === 1 ? top[0].querySelectorAll('.ex-step').length : 0};
    });
    assert(solvedOpen.top.length === 1 && (solvedOpen.top[0] === 'follow-up' ? solvedOpen.steps >= 2 && solvedOpen.inside === solvedOpen.steps : solvedOpen.inside === 0),
           'one of them opens solved, a follow-up with its steps in it (opened: ' + JSON.stringify(solvedOpen) + ')');
    if (SHOTS) await page.screenshot({path: `${SHOTS}/${mode}-deck-done.png`, fullPage: true});

    // the foot, with the end of the cram in place
    await footChecks(t, f, () => page.evaluate(() => [document.querySelector('#cram-tally').textContent,
                                                      document.querySelectorAll('.dk-cram-solved:not([hidden])').length]));

    // Cram these again: the wrong ones alone, and Shuffle and repeat after
    await page.locator('#cram-wrong-list [data-x="again"]').click();
    eq(await page.locator('#cram-progress').textContent(), `1 of ${wrongOnce.size}`, `“Cram these again” crams the ${wrongOnce.size} wrong ones`);
    for (let i = 0; i < 60 && !(await page.locator('#cram-done').isVisible()); i++)
      await page.click(await page.locator('#cram-skip').isVisible() ? '#cram-skip' : '#cram-next');
    await page.click('#cram-again');
    eq(await page.locator('#cram-progress').textContent(), `1 of ${wrongOnce.size}`, '“Shuffle and repeat” crams them again');

    eq(requests.filter(u => u.split('#')[0] !== f.url && u !== GITHUB && u !== GUIDE), [], 'nothing requested but the file itself');
    eq(await kept(page), NOTHING, 'nothing written anywhere: storage, cookies, IndexedDB, the cache');
    assert(errors.length === 0, 'no page errors, no console errors' + (errors.length ? ':\n    ' + errors.join('\n    ') : ''));
  } finally {
    await f.ctx.close();
  }
  await firstVisits(browser, t, file, opened[2]);
}

const tmp = await Deno.makeTempDir({prefix: 'parseh-html-export-'});
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  let total = 0;
  for (const mode of modes) total += await suite(browser, mode, tmp);
  console.log(`HTML export passed (${modes.join(' + ')}: ${total} checks)`);
} finally {
  await browser.close();
  await Deno.remove(tmp, {recursive: true}).catch(() => {});
}
