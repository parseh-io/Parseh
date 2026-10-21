// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the mobile interface's books and exercises (docs/mobile.md),
// against the REAL hub (serve.main, booted by tests/mobile_harness.py) over a
// temporary toolbox: the fixture editions of English (narrated), Persian,
// Arabic, Japanese, Hindi and Chinese with their readers built, the Italian one
// never built, and three exercise decks.  Measured where the page is drawn -- computed
// display, bounding rects, elementFromPoint -- on a phone held upright (390x844
// and 360x740, touch, Chromium's device emulation), on one held sideways
// (844x390, touch), and on a desktop with a mouse:
//
// shelf -- the book shelf, /m/books/:
//   a) the mobile hub's Books door, tapped, lands on /m/books/ (the browser
//      hub's lands on the library, /books/); a ctrl-click too, in a new tab;
//      sideways, the hub's doors two to a row
//   b) all there is to tap: home, the switch, the theme, the chips and one card
//      per built book, each 48px high at the least, inside the screen and
//      reached by a tap on it; the book never built says so and is no link; no
//      delete, no build, no bundle, no stop; the page never scrolls sideways;
//      sideways, the books two to a row
//   c) a chip shows its language's books and heading alone (the shelf holds
//      Persian, Arabic, Italian unbuilt, Japanese, English, Hindi, Chinese)
//   d) a book read on this phone says how far ("read on"), and its card opens
//      the reader at the address the place was kept under
//   e) Browser, pressed on the shelf, goes to the library; the shelf opened in
//      the browser mode says what it is and where the library is
// reader -- a book's reader, in the mobile mode (lib/mobilereader.js):
//   a) opened from the shelf; its header: the way out (hub, shelf), the
//      contents, the text size and the gear ⚙ -- and on a narrated book ↺ ▶ ↻, on a
//      line of their own upright and on the one line sideways -- each 48px at
//      the least, on the screen; nothing else of the header drawn, and none of
//      the page's writing doors -- book info, the builds, the narration,
//      folding, timings, stop, download, the dictionary setup, the pencil, a
//      note's plus
//   b) the gear (a0.5.0; it replaced ⋯) opens the rest in a sheet, a group to a
//      heading: the levels and the glosses, the listening (only a narrated
//      book), looking a word up, the text, the colours, the interface; a level
//      still hides its pass; the theme still turns; sideways, the sheet inside
//      the screen
//   c) the contents opens, without its naming; the gloss cloud opens on a tap
//      in hover mode, with copy and without card or edit
//   d) on a desktop in the mobile mode, alt-click on a word opens no card
//      sheet and E no chunk editor -- both of which they open in the browser
//      mode, measured on the same page
//   e) play plays, and the shelf's ▤ goes to the mobile shelf
//   f) Browser, pressed, gives the reader back its browser header, the same
//      controls as it had before Mobile was pressed
//   g) ↻ and ↺ move the recording by the seconds the gear's Skip distance
//      says, and the reading place with it; the choice keeps its number for
//      every book, and refuses nonsense; sideways, the header goes on the
//      way down and comes back on the way up, and the gear's sheet is not modal
// export -- a document's HTML page from a phone the worker controls, switched
//   to Browser, with the computer slow to make it (TO-DO §2.28): Download ▾ →
//   HTML page shows the bar and, 35 s on, gives the computer's own bytes as a
//   download; the bare link, followed, waits 20 s and downloads too; neither
//   ever leaves the document for "Parseh cannot be reached"; and a page nobody
//   kept, from a computer alive and 8 s slow, opens, while one from a computer
//   that answers nothing is the offline page, whose Try again says that it tried
// decks -- the exercise decks, /exercises/ (markdown/app, static/mobile.css):
//   a) the mobile hub's Exercises door lands on the decks' mobile layout, the
//      browser bar display:none; all there is to tap: home, the switch, the
//      theme, the chips, and a deck's name, Study and Open -- no import,
//      backup, restore, new deck, stop, ⋯ -- each 48px at the least
//   b) a chip filters the decks; the theme button turns the page dark
//   c) a deck: its counts, Study now and Cram all, and its exercises to pick
//      from -- the filters, all, shown, by tag, none -- and no rename, add,
//      export, options, delete, nor anything in the list that changes an
//      exercise; an empty deck says where exercises are added
//   d) studying: no bar over the exercise, no Edit, no key hints, no stop; ‹
//      back to the deck; Show answer or Check, then Next in the very same
//      place and the four ratings with their intervals -- a bar at the foot
//      upright, a column down the right sideways; Next and Good schedule the
//      exercise (the deck's own file says so); a choice answered right says
//      Correct
//   e) Cram all crams every exercise of the deck, the scheduling as it was; two
//      picked by hand are crammed, and so are the ones a tag picks
//   f) Browser, pressed, brings back every control of the browser layout
// app -- the mobile interface as an app (lib/mobile.py, lib/sw.js):
//   a) the app's address, /?mode=mobile, sets the mode and is given back
//      without it; the hub, the shelf, a reader and the decks are installable
//      as Chromium judges it (the one thing it has against them is the test's
//      own incognito profile), the worker taking the pages over
//   a2) the app gets itself ready AFTER it is installed, and says so: the page
//      asks for the way in by itself, the hub counts the addresses as they
//      come ("Getting ready — 41 of 46") and says nothing once it is done --
//      and the studio's faces are on no phone that has only installed the app;
//      the line stands at the FOOT, so its coming and going moves no door
//   a3) a note opened is what fetches them, all thirteen
//   b) the install page says this phone trusts Parseh, and says when the
//      waiting it asked for is over; the hub has its door
//   c) the server stopped, a page opened says Parseh cannot be reached
// update -- Parseh updated on the computer (TO-DO §13.16): a book and a video
//   kept, the hub back as another release with two shared scripts changed;
//   the app takes the new worker and says so in a line, reloading nothing;
//   the kept caches survive; renew mends every copy; the keep check says
//   "updated" and never "no longer whole" for them, and still catches a copy
//   really broken; both still open with the computer away
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/mobile_pages.mjs
//   MOBILE_PARTS=shelf,reader,touch,prefs,video,studio,export,decks,offline,checkout,background,app,update runs some of it
//   (MOBILE_KEEP_WAY=worker: keeping the iPad's way only; see WAY below)
import { chromium } from 'npm:playwright-core@1.52.0';
import {gearOpen, gearClose, gearUp, gearSwitch, rowDrawn} from './gear_driver.mjs';

const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
const PARTS = (Deno.env.get('MOBILE_PARTS') || 'shelf,reader,touch,prefs,video,studio,export,drawings,decks,offline,checkout,background,app,update').split(',');
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
  m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const near = (a, b, tol = 2) => Math.abs(a - b) <= tol;
const sleep = ms => new Promise(r => setTimeout(r, ms));
/* WHAT MUST BE AWAITED IN THE PAGE IS POLLED FROM HERE.  page.waitForFunction
   takes whatever its predicate returns for the answer, and an async predicate
   returns a Promise, which is truthy: it "passes" at once, whatever the page
   holds (driven, playwright-core 1.52: resolved after 10 ms on `async () =>
   false`).  So a wait on the caches -- which can only be asked with an await --
   is a loop out here, and it fails when it runs out. */
async function until(page, fn, arg, timeout = 60000, every = 250) {
  for (const t = Date.now();;) {
    const v = await page.evaluate(fn, arg);
    if (v) return v;
    if (Date.now() - t > timeout)
      throw Error('FAIL: waited ' + timeout + 'ms in vain for ' + String(fn).replace(/\s+/g, ' ').slice(0, 140));
    await sleep(every);
  }
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}

// ---- the toolbox, and its server
const WORK = await Deno.makeTempDir({prefix: 'parseh-mobile-pages-'});
const built = await new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'build', WORK], cwd: root,
                                          stdout: 'piped', stderr: 'piped'}).output();
if (!built.success) throw Error(td.decode(built.stderr) || td.decode(built.stdout));
const MADE = JSON.parse(td.decode(built.stdout).trim().split('\n').pop());
const port = freePort();
const log = [];
let hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                                stdout: 'piped', stderr: 'piped'}).spawn();
let hubUp = true;
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}

/* TWO WAYS OF KEEPING, AND BOTH ARE DRIVEN ON EVERY RUN (the owner, 2026-09-23).
   A book is kept by the browser's own download where the page's registration
   has one (lib/keep.js, bgKeep; lib/sw.js, settle) -- which this Chromium
   has, so a run as launched drives that way.  Everywhere else -- the iPad,
   Firefox -- the worker keeps it as it always did, and that is the whole
   feature there, so it is driven too: MOBILE_KEEP_WAY=worker launches this
   same Chromium with the API taken out of the page AND the worker (a Blink
   switch, so a worker the browser stops and starts cannot lose it), and the
   keeps then go the iPad's way through the very same assertions.  The run as
   launched starts that second run by itself at its end (below), one after
   the other and never at once. */
const WAY = Deno.env.get('MOBILE_KEEP_WAY') || 'background';
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true,
  args: WAY === 'worker' ? ['--disable-blink-features=BackgroundFetch'] : []});
console.log(WAY === 'worker' ? '\n(keeping the worker\'s way, as on the iPad: no background download)'
                             : '\n(keeping a book by the browser\'s own download where it can)');
/* WHICH WAY A KEEP WENT, seen from outside the page's own words: the browser's
   record of its background downloads (CDP, BackgroundService), and the notes a
   background keep leaves in `parseh-jobs` and clears when it ends.  A keep that
   quietly fell back to the other way would otherwise pass every assertion. */
async function watchWay(page) {
  const seen = [];
  try {
    const cdp = await page.context().newCDPSession(page);
    cdp.on('BackgroundService.backgroundServiceEventReceived',
           e => seen.push((e.backgroundServiceEvent || {}).eventName || '?'));
    await cdp.send('BackgroundService.startObserving', {service: 'backgroundFetch'});
    await cdp.send('BackgroundService.setRecording', {shouldRecord: true, service: 'backgroundFetch'});
  } catch (e) { seen.push('unobservable: ' + e.message); }
  page.bgSeen = seen;
  return seen;
}
async function keptWay(page, what, want = WAY) {
  const look = () => page.evaluate(async () => {
    const r = await navigator.serviceWorker.getRegistration();
    const jobs = await caches.has('parseh-jobs');
    return {bf: !!(r && 'backgroundFetch' in r), jobs,
            left: jobs ? (await (await caches.open('parseh-jobs')).keys()).length : 0};
  });
  let saw = await look();
  // the notes go once the keep has ended, and once more a moment later
  // (lib/keep.js, jobDrop): a note really left behind is still there after that
  for (const t = Date.now(); want === 'background' && saw.left > 0 && Date.now() - t < 6000; ) {
    await sleep(250);
    saw = await look();
  }
  // only what the browser recorded since the last keep asked about
  const all = (page.bgSeen || []).filter(n => !/^unobservable/.test(n));
  const events = all.slice(page.bgMark || 0);
  page.bgMark = all.length;
  const count = n => events.filter(e => e === n).length;
  if (want === 'background')
    eq([saw.bf, saw.jobs, saw.left, count('Background Fetch registered') > 0,
        count('Background Fetch completed') === count('Background Fetch registered')],
       [true, true, 0, true, true],
       what + ' went by the browser\'s own download, and left no note behind: the browser ' +
       'registered and completed ' + count('Background Fetch registered') + ' download(s)');
  else if (WAY === 'worker')
    eq([saw.bf, saw.jobs, events.length], [false, false, 0],
       what + ' went by the worker, as on the iPad: this browser has no background download');
  else
    eq([saw.bf, events.length], [true, 0],
       what + ' went by the worker although this browser has the background download: it is not a book');
}
const errors = [];
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true};
const NARROW = {viewport: {width: 360, height: 740}, isMobile: true, hasTouch: true};
// a phone held sideways, the way it is held most (docs/mobile.md)
const LAND = {viewport: {width: 844, height: 390}, isMobile: true, hasTouch: true};
const DESK = {viewport: {width: 1280, height: 800}};

async function newPage(opts, tag) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push(tag + ': ' + e.message); console.log('PAGE ERROR', tag, e.message); });
  // Chromium's headless shell drops the touch emulation when a screenshot
  // resizes the page (tests/mobile_mode.mjs, grab): said again over CDP
  if (opts.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  return page;
}
const tap = async (page, sel) => { const l = page.locator(sel).first(); if (page.touch) await l.tap(); else await l.click(); };
/* THE BROWSER | MOBILE SWITCH OF A DOCUMENT OR A DECK is in its gear (a0.5.0), not on the phone's bar: the ⚙ after ◐, the
   Interface group of the sheet, the half that says `mode` (the library's and the decks' list's keep their own on the bar) */
async function gearMode(page, mode) {
  await tap(page, '.m-topbar [data-parseh-gear]');
  await page.waitForSelector('.pg-panel:not([hidden])');
  await page.evaluate(() => ParsehGear.mounted().open('interface'));
  await sleep(150);
  await tap(page, `.pg-panel [data-pg-group=interface] .pg-chip:text-is("${mode === 'browser' ? 'Browser' : 'Mobile'}")`);
}
// The toolbox keeps the reading place for every device (§4.9): a book opened
// on a device that has not read it is ASKED whether to go to the place
// another left.  A person answers before doing anything else, and so does a
// test -- the line sits over the page until it is answered.
async function answerPlace(page, how = '.pf-stay') {
  await sleep(350);
  if (await page.$('.pf-bar')) await tap(page, how);
}
const settle = page => page.evaluate(() => document.fonts.ready.then(() =>
  new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))));
const shot = async (page, name) => {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`});
  if (page.touch) await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
};
const setMode = (page, m) => page.evaluate(m => {
  // the one switch, as the pages keep it (Parseh.mode on the toolbox's own
  // pages, decks.js on the studio's): stored, and mirrored in the cookie
  localStorage.setItem('parseh_mode', m);
  document.cookie = 'parseh_mode=' + m + '; Path=/; SameSite=Lax; Max-Age=31536000';
}, m);
// The header of a mobile page goes on the way down (parseh.js, bars()): a
// test that scrolled -- or a reader that went back to its reading place --
// brings it back as a person does, with a small move up.
async function reveal(page) {
  if (!(await page.evaluate(() => document.body.classList.contains('barhidden')))) return;
  await page.evaluate(() => scrollBy(0, -12));
  await page.waitForFunction(() => !document.body.classList.contains('barhidden'));
  await sleep(250);                                   // the slide back
}
// a tap on what sel matches, brought to the middle of the screen first --
// where no bar is over it, and nothing that floats at the foot
async function tapMiddle(page, sel) {
  await page.locator(sel).first().evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(250);
  await tap(page, sel);
}
// a tap on the mark of one named note, brought to the middle first.  By its
// title and not by its place in the page: the marks of three notes stand in
// three seams, and a test that tapped "the first one" would be proving
// whatever the build happened to put at the top.
async function tapMark(page, title) {
  const mark = page.locator('.gap .mark').filter({hasText: title}).first();
  await mark.evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(250);
  if (page.touch) await mark.tap(); else await mark.click();
}
const rect = (page, sel) => page.evaluate(sel => {
  const e = document.querySelector(sel);
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height};
}, sel);

// ---- what a page shows, measured
const CLICKABLE = 'a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"]), label[for]';
// every element that can be clicked and is drawn, said as tag:what
function clickable(page, scope) {
  return page.evaluate(([sel, scope]) => {
    const drawn = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const what = el => {
      const s = el.getAttribute('href') || el.getAttribute('data-parseh-mode') || el.getAttribute('data-pick') ||
        (el.hasAttribute('data-parseh-theme') ? 'theme' : '') || el.id || (el.getAttribute('data-x') || '') ||
        el.className || el.textContent.trim().slice(0, 20);
      return el.tagName.toLowerCase() + ':' + s;
    };
    const base = scope ? document.querySelector(scope) : document;
    return [...base.querySelectorAll(sel)].filter(drawn).map(what);
  }, [CLICKABLE, scope || null]);
}
// the targets matching sel: size, inside the screen, and whether a tap at
// the middle of each (scrolled into view first) reaches it
function targets(page, sel) {
  return page.evaluate(sel => [...document.querySelectorAll(sel)]
    .filter(el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden')
    .map(el => {
      el.scrollIntoView({block: 'center', inline: 'nearest'});
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return {what: (el.id || el.getAttribute('href') || el.getAttribute('data-parseh-mode') ||
                     el.getAttribute('data-pick') || el.className || el.textContent.trim()).toString().slice(0, 40),
              w: Math.round(r.width), h: Math.round(r.height), l: r.left, r: r.right, top: Math.round(r.top),
              inside: r.left >= -0.5 && r.right <= innerWidth + 0.5,
              hit: !!hit && (hit === el || el.contains(hit))};
    }), sel);
}
function allFit(list, m, min = 48) {
  const bad = list.filter(t => !(t.h >= min && t.w >= min && t.inside && t.hit));
  assert(list.length > 0 && bad.length === 0, m + (bad.length ? ' -- not: ' + JSON.stringify(bad) : ` (${list.length})`));
}
const sideways = page => page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
const isDrawn = (page, sel) => page.evaluate(sel => [...document.querySelectorAll(sel)]
  .some(el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden'), sel);
// the tops of what sel matches, where each stands now (nothing scrolled)
const tops = (page, sel) => page.evaluate(sel => [...document.querySelectorAll(sel)]
  .filter(e => e.getClientRects().length).map(e => Math.round(e.getBoundingClientRect().top)), sel);

// ======== shelf ========
async function partShelf() {
  for (const [opts, tag] of [[PHONE, 'phone'], [NARROW, 'narrow'], [LAND, 'landscape'], [DESK, 'desktop']]) {
    console.log(`\n== shelf, ${tag}`);
    const page = await newPage(opts, 'shelf ' + tag);
    // ---- a) the doors
    await page.goto(B + '/');
    await setMode(page, 'browser');
    await page.reload();
    if (tag === 'phone') {
      await Promise.all([page.waitForURL(B + '/books/'), tap(page, '.hub-browser a.door[href="/books/"]')]);
      assert(true, 'the browser hub: Books opens the library, /books/');
      await page.goto(B + '/');
    }
    // the switch in the browser bar, pressed as a person presses it
    await tap(page, '.parseh-bar:not(.m-bar) [data-parseh-mode=mobile]');
    eq(await page.evaluate(() => document.documentElement.getAttribute('data-mode')), 'mobile', 'Mobile pressed on the hub');
    if (tag === 'landscape') {
      // five doors (the four, and Review later after them), two to a row; the guide and the app's door under them
      await settle(page);
      await shot(page, 'hub-landscape');
      const doors = await page.evaluate(() => [...document.querySelectorAll('.m-doors a.m-door')]
        .map(d => { const r = d.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.left)]; }));
      assert(doors.length === 5 && doors[0][0] === doors[1][0] && doors[2][0] === doors[3][0] &&
             doors[2][0] > doors[0][0] && doors[4][0] > doors[2][0] && doors[1][1] > doors[0][1],
             'sideways: the hub\'s doors two to a row ' + JSON.stringify(doors));
      assert(await sideways(page) <= 0, 'and the hub does not scroll sideways');
    }
    await Promise.all([page.waitForURL(B + '/m/books/'), tap(page, '.hub-mobile a.m-door[href="/books/"]')]);
    assert(true, 'the mobile hub: Books opens the mobile shelf, /m/books/');
    if (tag === 'desktop') {
      await page.goto(B + '/');
      const [tab] = await Promise.all([page.context().waitForEvent('page'),
        page.locator('.hub-mobile a.m-door[href="/books/"]').click({modifiers: ['Control']})]);
      await tab.waitForLoadState();
      eq(new URL(tab.url()).pathname, '/m/books/', 'and a ctrl-click opens it in a new tab');
      await tab.close();
      await page.goto(B + '/m/books/');
    }
    await settle(page);
    await shot(page, `shelf-${tag}`);

    // ---- b) what can be tapped
    const got = await clickable(page, 'body');
    // the chips and the books in the registry's order (fa ar it ja fr de tr
    // en hi es zh), a language only where it has a book
    // on a touch screen the bar wears a ? as well: what a button does, for a
    // finger that cannot rest on it (lib/explain.js, §4.7)
    const want = ['a:/', 'button:browser', 'button:mobile', 'button:theme',
                  ...(tag === 'desktop' ? [] : ['button:px-ask']), 'button:all',
                  'button:fa', 'button:ar', 'button:it', 'button:ja', 'button:en', 'button:hi', 'button:zh',
                  'a:/books/persian/mini-fa/reader/', 'a:/books/arabic/mini-ar/reader/',
                  'a:/books/japanese/mini-ja/reader/', 'a:/books/english/mini-en/reader/',
                  'a:/books/hindi/mini-hi/reader/', 'a:/books/chinese/mini-zh/reader/'];
    // (the chips row scrolls on a phone and wraps for a mouse: either way
    // every chip is drawn)
    eq(got, want, 'all there is to tap: home, the switch, the theme, the chips, one card per built book');
    for (const no of ['[data-del]', '[data-build]', '[data-parseh-stop]', 'input[type=file]', '#take', '#shelf'])
      assert(!(await page.$(no)), 'nothing on the shelf is ' + no);
    const cards = await targets(page, 'a.m-book');
    allFit(cards, 'each card at least 48px (' + cards.map(c => c.h).join(', ') + '), inside the screen, reached by a tap');
    assert(cards.every(c => c.h >= 96), 'and as tall as the hub\'s doors');
    if (tag === 'landscape' || tag === 'desktop') {
      // one book to a language here: two to a row is two cards' width a row
      const col = await page.evaluate(() => {
        const s = document.querySelector('.m-shelf').getBoundingClientRect();
        const c = document.querySelector('a.m-book').getBoundingClientRect();
        return [Math.round(s.width), Math.round(c.width)];
      });
      assert(col[1] < col[0] * 0.55, 'from 600px the books go two to a row ' + JSON.stringify(col));
    }
    await page.evaluate(() => scrollTo(0, 0));
    await sleep(250);
    allFit(await targets(page, '.m-bar a, .m-bar button'), 'the bar\'s controls: 48px, on the screen');
    const barTops = await page.evaluate(() => [...document.querySelectorAll('.m-bar a, .m-bar button')]
      .filter(e => e.getClientRects().length).map(e => Math.round(e.getBoundingClientRect().top)));
    assert(Math.max(...barTops) - Math.min(...barTops) <= 6, 'and one line of them ' + JSON.stringify(barTops));
    assert(await sideways(page) <= 0, 'the page does not scroll sideways');
    const off = await page.evaluate(() => {
      const c = document.querySelector('.m-book.m-off');
      return c && {tag: c.tagName, href: c.getAttribute('href'), said: c.textContent.replace(/\s+/g, ' '),
                   inLink: !!c.closest('a')};
    });
    assert(off && off.tag === 'DIV' && !off.href && !off.inLink && /not built yet/.test(off.said) &&
           /browser interface/.test(off.said), 'the book never built says so, and opens nothing');
    // the titles in their own direction and face
    const fa = await page.evaluate(() => {
      const t = document.querySelector('a.m-book[data-lang=fa] .m-btitle');
      return {dir: getComputedStyle(t).direction, lang: t.getAttribute('lang')};
    });
    eq(fa, {dir: 'rtl', lang: 'fa'}, 'a Persian title reads right to left');

    // ---- c) a chip
    await page.evaluate(() => scrollTo(0, 0));
    await sleep(250);
    await page.locator('.m-langs .chip[data-pick=ja]').scrollIntoViewIfNeeded();
    await tap(page, '.m-langs .chip[data-pick=ja]');
    const shown = await page.evaluate(() => [...document.querySelectorAll('.m-book, .m-lhead')]
      .filter(e => e.getClientRects().length).map(e => e.className.split(' ')[0] + ':' + e.getAttribute('data-lang')));
    eq(shown, ['m-lhead:ja', 'm-book:ja'], 'Japanese picked: its heading and its one book, nothing else');
    await tap(page, '.m-langs .chip[data-pick=all]');

    // ---- d) read on
    if (tag === 'phone') {
      const en = MADE.readers.en;
      await page.evaluate(p => localStorage.setItem('bk_pos:' + p + 'index.html', JSON.stringify({i: 2})), en);
      await page.reload();
      const card = await page.evaluate(p => {
        const a = [...document.querySelectorAll('a.m-book')].find(x => x.getAttribute('data-lang') === 'en');
        const t = a.querySelector('.m-readon');
        return {tag: t && t.textContent, href: a.getAttribute('href'), bar: getComputedStyle(a, '::after').width,
                subs: +a.getAttribute('data-subs')};
      }, en);
      const pct = Math.round(3 * 100 / card.subs);
      eq([card.tag, card.href], [`read on · ${pct}%`, en + 'index.html'],
         'a book read here says how far, and opens where the place was kept');
      assert(parseFloat(card.bar) > 0, 'with a line along its foot: ' + card.bar);
      await page.evaluate(p => localStorage.removeItem('bk_pos:' + p + 'index.html'), en);
      await page.reload();
    }

    // ---- e) Browser
    await reveal(page);
    await Promise.all([page.waitForURL(B + '/books/'), tap(page, '.m-bar [data-parseh-mode=browser]')]);
    assert(true, 'Browser pressed on the shelf: the library, /books/');
    await page.goto(B + '/m/books/');
    assert(await isDrawn(page, '.m-elsewhere'), 'opened in the browser mode, the shelf says it is the mobile one');
    eq(await page.evaluate(() => location.pathname), '/m/books/', 'and stays: nothing redirects at load');
    await setMode(page, 'mobile');
    await page.reload();
    assert(!(await isDrawn(page, '.m-elsewhere')), 'in the mobile mode it does not');
    await page.context().close();
  }
}

// ======== reader ========
const HEADER_SEL = 'header a[href], header button, header select, header input, header label[for]';
// the header's drawn controls, in the order they are SEEN -- line by line,
// then left to right -- which is not the order of the markup: the mobile
// layout places them with `order`
const headerDrawn = page => page.evaluate(sel => [...document.querySelectorAll(sel)]
  .filter(e => e.getClientRects().length > 0)
  .map(e => ({r: e.getBoundingClientRect(), name: e.id || (e.hasAttribute('data-parseh-gear') ? 'gear' : e.classList.contains('home')
    ? (e.classList.contains('glyph') ? 'hub' : 'shelf')
    : e.getAttribute('data-toggle') || e.getAttribute('data-parseh-mode') || e.className)}))
  .sort((a, b) => (Math.abs(a.r.top - b.r.top) > 6 ? a.r.top - b.r.top : a.r.left - b.r.left))
  .map(x => x.name), HEADER_SEL);
const WRITES = ['#bookinfo', '#buildbook', '#buildhtml', '#narr', '#fold', '#editmode', '#editbyear', '#savetimes', '#droptimes',
                '#stopsrv', 'header .dl', '#lookupset', '#build', '#pdfstale', '#chpen', '.gap .plus', '#editmsg'];

// What the header holds: one line, whatever the book and whichever way the
// phone is held -- the hub, the shelf, the contents, the text size and the gear (a0.5.0: it holds
// everything the ⋯ menu did, in a sheet).  The recording is not moved from here any more -- ↺, ⏯ and
// ↻ float at the foot, in the dock (lib/narrctl.js), where a thumb has them
// without reaching up into a header that hides on the way down.
function firstLines(code, tag) {
  // and the ? at its end, since a phone cannot rest on a button to read what
  // it does (lib/explain.js, §4.7)
  return [['hub', 'shelf', 'toc', 'typo', 'gear', 'px-ask']];
}

async function partReader() {
  for (const [opts, tag] of [[PHONE, 'phone'], [NARROW, 'narrow'], [LAND, 'landscape']]) {
    const page = await newPage(opts, 'reader ' + tag);
    await page.goto(B + '/');
    await setMode(page, 'mobile');
    for (const code of ['en', 'fa', 'ar', 'ja', 'hi', 'zh']) {
      console.log(`\n== reader ${code}, ${tag}`);
      const lines = firstLines(code, tag), want = lines.flat();
      // ---- a) from the shelf
      await page.goto(B + '/m/books/');
      await Promise.all([page.waitForURL(B + MADE.readers[code]),
                         tap(page, `a.m-book[data-lang=${code}]`)]);
      await page.waitForFunction(() => document.querySelector('[data-parseh-gear]'));
      await settle(page);
      await answerPlace(page);
      await reveal(page);
      await shot(page, `reader-${code}-${tag}`);
      eq(await headerDrawn(page), want, `${code}: the header: ${lines.map(l => l.join(', ')).join(' / ')}`);
      const line = await targets(page, 'header a[href], header button');
      allFit(line, `${code}: each at least 48px, on the screen, reached by a tap`);
      const rows = [...new Set(line.map(t => t.top))].sort((a, b) => a - b);
      const grouped = rows.reduce((g, t) => (g.length && t - g[g.length - 1] <= 6 ? g : [...g, t]), []);
      eq(grouped.length, lines.length, `${code}: ${lines.length === 1 ? 'all on one line' : 'on two lines'} ` +
         JSON.stringify(line.map(t => t.top)));
      for (const w of WRITES) assert(!(await isDrawn(page, w)), `${code}: no ${w}`);
      assert(await sideways(page) <= 0, `${code}: the page does not scroll sideways`);
      eq(await page.evaluate(() => document.body.hasAttribute('data-mobile-page')), true, `${code}: a mobile page`);
      if (code === 'fa' || code === 'ar')
        eq(await page.evaluate(() => getComputedStyle(document.querySelector('main .p1')).direction), 'rtl',
           `${code}: the text reads right to left, under a header that reads left to right`);
      if (code !== 'en')
        assert(!(await isDrawn(page, '.nc-dock, .m-rskip')), `${code}: no narration, no dock and no ↺ ↻`);
      else
        assert(await isDrawn(page, '.nc-dock .nc-play'), `${code}: the dock floats at the foot`);

      // ---- b) the gear: everything ⋯ held, in a sheet
      await gearOpen(page);
      await settle(page);
      await sleep(350);                                  // the sheet rises in a sixth of a second: measured at rest
      await shot(page, `reader-${code}-${tag}-gear`);
      const groups = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group]')]
        .filter(g => !g.hidden).map(g => g.getAttribute('data-pg-group')).filter(g => g !== 'zoom'));
      eq(groups, code === 'en' ? ['levels', 'listening', 'looking', 'text', 'colours', 'interface']
                               : ['levels', 'looking', 'text', 'colours', 'interface'],
         `${code}: the gear opens the groups this book has`);
      eq(await page.evaluate(() => document.querySelector('[data-parseh-gear]').getAttribute('aria-expanded')), 'true',
         `${code}: and says it is open`);
      // hover ⏸ (a0.4.1, lib/mobilereader.js): the narration waits while a gloss is open.  A row of the one
      // narrated book -- and so nowhere in a book with no recording, in whatever language it is set (the
      // gear's chrome is an LTR island, right to left included), which is also what keeps the Listening
      // group off that book's gear (the groups just above)
      eq(await rowDrawn(page, 'hoverpause'), code === 'en',
         `${code}: hover ⏸ ${code === 'en' ? 'is a row of the gear, "Pause while a gloss is open"' : 'is not offered: no narration to wait'}`);
      if (code === 'en')
        assert(await page.evaluate(() => document.querySelector('.pg-panel [data-pg-row=hoverpause]').getBoundingClientRect().height >= 48),
               `${code}: and a finger high`);
      // the sheet is inside the screen, whichever way the phone is held (half of it, and never less than 240px: a phone
      // held sideways), with the text above it still there
      const sheetBox = await page.evaluate(() => {
        const r = document.querySelector('.pg-panel').getBoundingClientRect();
        return {t: r.top, b: r.bottom, h: r.height, vh: innerHeight};
      });
      assert(sheetBox.t >= 0 && sheetBox.b <= sheetBox.vh + 0.5 && sheetBox.h <= Math.max(240, sheetBox.vh * 0.6) + 1,
             `${code}: the sheet is inside the screen and about half of it: ${JSON.stringify(sheetBox)}`);
      allFit(await targets(page, '.pg-panel button, .pg-panel select, .pg-panel .pg-lvcheck'),
             `${code}: every control in the sheet at least 48px, on the screen, reached by a tap`);
      for (const w of WRITES) assert(!(await isDrawn(page, w)), `${code}: still no ${w}`);
      await gearOpen(page, 'interface');
      eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-row=mode] button')]
        .map(b => b.getAttribute('aria-pressed'))), ['false', 'true'], `${code}: the switch is there, Mobile pressed`);
      await gearOpen(page, 'levels');
      // a level still hides its pass: its tick, in the gear, drives the page's own button
      const pass = await page.evaluate(() => {
        const b = document.querySelector('.pgrp [data-toggle]');
        return b && b.getAttribute('data-toggle');
      });
      const passCls = pass.replace('no', '.p');
      const tick = '.pg-panel [data-pg-row=levels] .pg-lv:first-child .pg-lvcheck';
      assert(await isDrawn(page, 'main ' + passCls), `${code}: level ${passCls} drawn`);
      await tap(page, tick);
      assert(!(await isDrawn(page, 'main ' + passCls)), `${code}: its tick hides it`);
      await tap(page, tick);
      assert(await isDrawn(page, 'main ' + passCls), `${code}: and brings it back`);
      if (code === 'en') {
        const t0 = await page.evaluate(() => Parseh.theme.resolved());
        await gearOpen(page, 'colours');
        await tap(page, `.pg-panel [data-pg-row=theme] .pg-chip:text-is("${t0 === 'dark' ? 'Light' : 'Dark'}")`);
        const t1 = await page.evaluate(() => Parseh.theme.resolved());
        assert(t0 !== t1, `en: the theme turns, from the gear (${t0} -> ${t1})`);
        await page.evaluate(t => Parseh.theme.set(t), t0);
      }
      await gearClose(page);
      eq(await headerDrawn(page), want, `${code}: the gear shut: the first line alone`);

      // ---- g) the recording, back and on
      if (code === 'en') await partSkip(page, tag);

      // ---- c) the contents, and the cloud
      // the page settled first: the header slides on a scroll, and the
      // recording's own scrolling (partSkip, just above) leaves it moving
      await page.evaluate(() => scrollTo(0, 0));
      await sleep(500);
      await reveal(page);
      await tap(page, '#toc');
      await page.waitForFunction(() => !document.querySelector('#tocwrap').hidden);
      assert(await isDrawn(page, '#toclist a[href^="#par-"]'), `${code}: the contents opens, its entries there`);
      assert(!(await isDrawn(page, '.tocedit')) && !(await isDrawn(page, '#tocsecs')),
             `${code}: without the naming of chapters and sections`);
      await tap(page, '#tocx');
      await reveal(page);
      await gearSwitch(page, 'hover', true);
      await tap(page, 'main .p1 .w');
      await page.waitForFunction(() => !document.querySelector('#cloud').hidden);
      assert(await isDrawn(page, '#cloud .mkcopy'), `${code}: a tap opens the gloss cloud, with copy`);
      assert(!(await isDrawn(page, '#cloud .mkcard')) && !(await isDrawn(page, '#cloud .mkedit')),
             `${code}: and no card, no edit`);
      // THE CLOUD LEFT ALONE (a0.3.2, TO-DO §4.18): on a phone the dictionary
      // opens in a sheet of its own, and only when asked -- a chunk tapped
      // opens its gloss beside the word exactly as it did: the row's own
      // reading, transliteration, vocabulary and meaning, line for line, the
      // cloud at the word, and nothing of the dictionary
      const alone = await page.evaluate(() => {
        const cloud = document.getElementById('cloud'), hot = document.querySelector('.hot');
        const row = document.querySelector(`main .p2 .row[data-c="${hot.closest('[data-c]').dataset.c}"] .gl`);
        const lines = els => [...els].filter(e => e.matches('.kana, .tr, .voc, .en'))
          .map(e => [e.className, e.textContent.replace(/\s+/g, ' ').trim()]);
        const c = cloud.getBoundingClientRect(), w = hot.getBoundingClientRect();
        return {cloud: lines(cloud.children), row: lines(row.children),
                beside: (c.bottom <= w.top + 1 && w.top - c.bottom < 24 || c.top >= w.bottom - 1 && c.top - w.bottom < 24) &&
                        c.left < w.right && c.right > w.left,
                sheet: !!document.querySelector('.m-dback, .m-dsheet'), entry: !!cloud.querySelector('.dict'),
                sparse: document.documentElement.classList.contains('m-sparse'), marks: document.querySelectorAll('.m-gl').length};
      });
      assert(alone.cloud.length > 0 && JSON.stringify(alone.cloud) === JSON.stringify(alone.row),
             `${code}: the cloud is the chunk's own gloss, line for line: ${JSON.stringify(alone.cloud)}`);
      eq([alone.beside, alone.sheet, alone.entry, alone.sparse, alone.marks], [true, false, false, false, 0],
         `${code}: at the word, with no sheet and no entry -- and a book glossed as this one is wears no mark`);
      assert(await isDrawn(page, '#cloud .mkdict'), `${code}: the dictionary one press away, beside copy`);
      await page.evaluate(() => { localStorage.setItem('bk_hover', '0'); });

      // ---- e) the shelf's ▤ goes to the mobile shelf
      if (code === 'zh') {
        await page.reload();
        await page.waitForFunction(() => document.querySelector('[data-parseh-gear]'));
        await reveal(page);
        await Promise.all([page.waitForURL(B + '/m/books/'), tap(page, 'header a.home:not(.glyph)')]);
        assert(true, 'zh: ▤ goes to the mobile shelf');
      }
    }
    await page.context().close();
  }

  // ---- d) the writing gestures, on a desktop, in both modes
  console.log('\n== reader, desktop: the gestures that write');
  const page = await newPage(DESK, 'reader desktop');
  await page.goto(B + '/');
  await setMode(page, 'browser');
  const en = B + MADE.readers.en;
  await page.goto(en);
  await page.waitForFunction(() => window.ParsehMobileReader && document.getElementById('hoverpause'));
  const before = await headerDrawn(page);
  assert(before.includes('bookinfo') && before.includes('buildbook') && before.includes('narr'),
         'the browser mode: the header as the reader builds it ' + JSON.stringify(before));
  assert(!(await isDrawn(page, '.nc-dock, .m-rskip')), 'with nothing of the mobile layer drawn');
  // the gear stands at the end of the first row in this mode too, and what it took off the page -- hover ⏸ (a0.4.1),
  // stop at a change, the definitions -- is in the DOM for its rows to press and is not drawn
  // (tests/phone_clouds.mjs, n, asks that hover ⏸ is still the very next control after hover)
  assert(before.includes('gear') && before.includes('hovermode') && !before.includes('hoverpause') &&
         !before.includes('stopbnd') && !before.includes('lookupset'),
         'and the gear, with hover ⏸ and the rest it holds out of sight ' + JSON.stringify(before));
  assert(await isDrawn(page, 'header .nc-skip[data-skip="-1"]') && await isDrawn(page, 'header .nc-chip'),
         'and the recording moved from the header instead: ↺ ↻ beside ▶, the speed as a chip (§4.15)');
  const word = 'main .p1 .wd';
  const card = async () => {
    await page.locator(word).first().click({modifiers: ['Alt']});
    await sleep(300);
    return page.evaluate(() => !document.querySelector('#anki').hidden);
  };
  const edit = async () => {
    await page.locator('main .p2 .row[data-c]').first().hover();
    await sleep(200);
    await page.keyboard.press('e');
    await sleep(300);
    return page.evaluate(() => !document.querySelector('#chbox').hidden);
  };
  assert(await card(), 'browser: alt-click on a word opens the card sheet');
  await page.locator('#acancel').click();
  assert(await edit(), 'browser: E over a chunk opens its editor');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.querySelector('#chbox').hidden);
  // Mobile, pressed in another tab: this one follows
  const other = await page.context().newPage();
  await other.goto(B + '/');
  await other.locator('.parseh-bar:not(.m-bar) [data-parseh-mode=mobile]').click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-mode') === 'mobile');
  await other.close();
  assert(await isDrawn(page, '[data-parseh-gear].pg-mobile'), 'a switch made in another tab: the reader follows, the gear in its phone dress');
  assert(!(await card()), 'mobile: alt-click on the same word opens nothing');
  assert(!(await edit()), 'mobile: E over the same chunk opens nothing');
  // ---- e) play, from the dock that the mobile mode floats at the foot
  await reveal(page);
  await page.locator('.nc-dock .nc-play').click();
  await page.waitForFunction(() => !document.querySelector('#audio').paused, null, {timeout: 5000});
  eq(await page.evaluate(() => [document.querySelector('.nc-play').textContent,
                                document.querySelector('#play').textContent]),
     ['‖', '‖'], 'the dock plays, and both it and the reader\'s own button say so ' +
     '(‖ and ▶: no colour font can claim them, which is why the phone drew an orange emoji)');
  await page.locator('.nc-dock .nc-play').click();
  await page.waitForFunction(() => document.querySelector('#audio').paused);
  // ---- f) back to the browser mode
  await reveal(page);
  await gearOpen(page, 'interface');
  await page.locator('.pg-panel [data-pg-row=mode] button:text-is("Browser")').click();
  await gearClose(page);
  eq(await page.evaluate(() => document.documentElement.getAttribute('data-mode')), 'browser', 'Browser pressed in the gear of the reader');
  eq(await headerDrawn(page), before, 'the header is the browser\'s again, control for control');
  eq(await page.evaluate(() => document.body.hasAttribute('data-bars-held')), false,
     'and nothing holds its bars any more');
  assert(await card(), 'and alt-click makes a card again');
  await page.locator('#acancel').click();
  // hover ⏸ in the browser mode of every language's reader: drawn beside hover in the narrated
  // one, and there but not drawn where there is no recording to wait
  for (const code of ['en', 'fa', 'ar', 'ja', 'hi', 'zh']) {
    await page.goto(B + MADE.readers[code]);
    await page.waitForFunction(() => document.getElementById('hoverpause'));
    await gearOpen(page);
    eq(await rowDrawn(page, 'hoverpause'), code === 'en',
       `browser mode, ${code}: the gear ${code === 'en' ? 'offers hover ⏸' : 'does not offer hover ⏸: no narration'}`);
    await gearClose(page);
  }
  await page.context().close();
}

// ---- g) THE DOCK, on the narrated book (its recording is 8 seconds long):
// ↺ in one corner, ⏯ and ↻ with the speed in the other, holding a skip
// button for the seconds, and all of it fading when nothing is touched
// (lib/narrctl.js; TO-DO §4.17, the owner's choices of 2026-09-22)
async function partSkip(page, tag) {
  const K = 'bk_skip';
  await answerPlace(page);
  const state = () => page.evaluate(() => ({t: Math.round(document.getElementById('audio').currentTime * 100) / 100,
    paused: document.getElementById('audio').paused, cur,
    on: (document.querySelector('.on-air') || {dataset: {}}).dataset.s,
    labels: [...document.querySelectorAll('.nc-dock .nc-skip')].map(b => b.textContent + '|' + b.getAttribute('aria-label'))}));
  // the dock: each button in its own corner, and bigger than the 48px a
  // target must be, since these are pressed again and again without looking
  eq(await page.evaluate(() => {
    const d = document.querySelector('.nc-dock');
    const box = s => { const e = d.querySelector(s); return e && e.getBoundingClientRect(); };
    const l = box('.nc-skip[data-skip="-1"]'), p = box('.nc-play'), r = box('.nc-skip[data-skip="1"]');
    return [l.left < 40, r.right > innerWidth - 40, p.right < r.left + 1,
            Math.min(l.width, l.height, p.width, p.height, r.width, r.height) >= 56,
            d.getBoundingClientRect().bottom <= innerHeight + 1,
            !!d.querySelector('.nc-chip')];
  }), [true, true, true, true, true, true],
     'en: the dock: ↺ in the left corner, ⏯ ↻ in the right, 56px, above the foot, with the speed');
  eq((await state()).labels, ['↺ 10|back 10 seconds', '10 ↻|on 10 seconds'],
     'en: ↺ and ↻ say ten seconds, until told otherwise');
  // THE DOCK IS NOT MIRRORED BY A RIGHT-TO-LEFT BOOK (the owner, on a Persian
  // book, 2026-09-23: "the triangle is on the left, forward is on the left and
  // back on the right").  A page that reads right to left mirrors every row
  // laid out inside it, and the dock was laid out inside one -- but time does
  // not run backwards in Persian: ↺ is behind and ↻ is ahead wherever the
  // words go, as they are on every player the owner has ever held.  So the
  // dock says dir="ltr" for itself, and this drives it: the page is turned
  // round under a dock that is already built, as a Persian book's page is.
  eq(await page.evaluate(() => {
    const h = document.documentElement, was = h.getAttribute('dir');
    h.setAttribute('dir', 'rtl');
    const d = document.querySelector('.nc-dock');
    const box = s => d.querySelector(s).getBoundingClientRect();
    const out = [getComputedStyle(d).direction, d.getAttribute('dir'),
                 box('.nc-skip[data-skip="-1"]').left < box('.nc-play').left,
                 box('.nc-play').left < box('.nc-skip[data-skip="1"]').left];
    if (was === null) h.removeAttribute('dir'); else h.setAttribute('dir', was);
    return out;
  }), ['ltr', 'ltr', true, true],
     'en: and a right-to-left page does not mirror it: ↺ stays behind, ↻ stays ahead');
  // ⏯ is the reader's own ▶, which is no longer in the header
  assert(!(await isDrawn(page, 'header #play')), 'en: ▶ has left the header');
  await page.evaluate(() => { document.getElementById('audio').pause(); });
  await tap(page, '.nc-dock .nc-play');
  await page.waitForFunction(() => !document.getElementById('audio').paused);
  eq(await page.evaluate(() => document.querySelector('.nc-play').textContent), '‖',
     'en: a tap on ⏯ plays, and it says pause');
  await tap(page, '.nc-dock .nc-play');
  await page.waitForFunction(() => document.getElementById('audio').paused);
  eq(await page.evaluate(() => document.querySelector('.nc-play').textContent), '▶', 'en: and a tap pauses');
  // the first tap says, once, what a hold does
  await page.evaluate(() => { localStorage.removeItem('bk_skiphint');
                              document.getElementById('audio').currentTime = 0; });
  await tap(page, '.nc-dock .nc-skip[data-skip="1"]');
  eq(await page.evaluate(() => [(document.getElementById('parseh-toast') || {}).textContent,
                                localStorage.getItem('bk_skiphint')]),
     ['hold ↺ or ↻ to choose the seconds', '1'], 'en: the first tap says the hold, once');
  // held: the row of seconds, and five of them is what a person picks from
  const held = async (sel) => {
    const b = await page.locator(sel).boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    await page.mouse.down();
    // held until the row of seconds is there -- a hold opens it after half a second of the page's own clock, and a
    // fixed 700 ms was a look taken before it on a computer too busy to keep that clock
    await page.waitForFunction(() => document.querySelectorAll('.nc-popb').length > 0, null, {timeout: 15000}).catch(() => {});
    const rows = await page.evaluate(() => [...document.querySelectorAll('.nc-popb')].map(x => x.textContent));
    await page.mouse.up();
    return rows;
  };
  eq(await held('.nc-dock .nc-skip[data-skip="1"]'), ['1s', '2s', '5s', '10s', '15s', '30s', '60s'],
     'en: holding ↻ opens the seconds to choose from');
  // BY NAME AND NOT BY POSITION: the row now begins at one second (the owner
  // asked for 1s and 2s, 2026-09-23), so the first button is no longer 5s and
  // a test that counted would have been testing the wrong number for ever.
  await page.click('.nc-pop button:text-is("5s")');
  eq([await page.evaluate(k => localStorage.getItem(k), K), (await state()).labels],
     ['5', ['↺ 5|back 5 seconds', '5 ↻|on 5 seconds']], 'en: 5s chosen: kept, and said on both');
  // the same choice in the gear's "Skip distance", since a hold cannot be seen (the phone's own row of seconds
  // is the gear's now: still in the header's DOM, not drawn)
  await reveal(page);
  await gearOpen(page, 'listening');
  eq(await page.evaluate(() => {
    const s = document.querySelector('.pg-panel [data-pg-row=skip] select');
    return [s.getClientRects().length > 0, [...s.options].map(o => o.textContent), s.options[s.selectedIndex].textContent];
  }), [true, ['1 s', '2 s', '5 s', '10 s', '15 s', '30 s', '60 s'], '5 s'], 'en: the gear shows the same choice, with 5 s marked');
  await gearClose(page);
  // the move itself: the recording, and the reading place with it
  await page.waitForFunction(() => document.getElementById('audio').readyState >= 1);
  await page.evaluate(() => { const a = document.getElementById('audio'); a.pause(); a.currentTime = 0; });
  await sleep(150);
  await tap(page, '.nc-dock .nc-skip[data-skip="1"]');
  await sleep(400);
  const s1 = await state();
  const said = await page.evaluate(() => subAtTime(5));
  eq([s1.t, s1.paused, s1.cur, s1.on], [5, true, said, String(said)],
     'en: ↻ paused: five seconds on, and the reading place is the subparagraph said there');
  await tap(page, '.nc-dock .nc-skip[data-skip="-1"]');
  await sleep(400);
  eq((await state()).t, 0, 'en: ↺: back to the start');
  await page.keyboard.press('ArrowRight');
  await sleep(400);
  eq((await state()).t, 5, 'en: keyboard → in Mobile mode: on by the same chosen seconds');
  await page.keyboard.press('ArrowLeft');
  await sleep(400);
  eq((await state()).t, 0, 'en: keyboard ← in Mobile mode: back by the same chosen seconds');
  // the speed: the chip says it, a tap opens the row, and the sound obeys
  eq(await page.evaluate(() => document.querySelector('.nc-dock .nc-chip').textContent), '1×',
     'en: the speed chip says 1×');
  await tap(page, '.nc-dock .nc-chip');
  eq(await page.evaluate(() => [...document.querySelectorAll('.nc-popb')].map(x => x.textContent)),
     ['0.25×', '0.5×', '0.6×', '0.75×', '0.9×', '1×', '1.1×', '1.25×', '1.5×', '1.75×', '2×'],
     'en: a tap opens the speeds — one list for everything Parseh itself plays, 0.25 among them');
  await page.click('.nc-pop button:nth-child(9)');
  eq(await page.evaluate(() => [document.querySelector('.nc-dock .nc-chip').textContent,
                                document.getElementById('audio').playbackRate,
                                document.getElementById('audio').defaultPlaybackRate,
                                localStorage.getItem('bk_rate')]),
     ['1.5×', 1.5, 1.5, '1.5'], 'en: 1.5× chosen: the chip, the sound and what is kept agree');
  // AND IT STAYS THERE when the recording is loaded again -- the owner's bug
  await page.evaluate(() => { const a = document.getElementById('audio'); a.load(); });
  await sleep(500);
  eq(await page.evaluate(() => [document.getElementById('audio').playbackRate,
                                document.querySelector('.nc-dock .nc-chip').textContent]),
     [1.5, '1.5×'], 'en: the recording loaded again does NOT put the speed back to 1×');
  await page.click('.nc-dock .nc-chip');
  await page.click('.nc-pop button:nth-child(5)');
  // faint when nothing is touched, whole again at a touch -- and the page
  // scrolling itself, as it does while a narration plays, is not a touch
  const faint = () => page.evaluate(() => document.querySelector('.nc-dock').classList.contains('nc-idle'));
  await page.evaluate(() => document.getElementById('audio').pause());
  await page.touchscreen.tap(30, 200).catch(() => page.mouse.click(30, 200));
  await sleep(200);
  const f0 = await faint();
  await sleep(4600);
  const f1 = await faint();
  await page.touchscreen.tap(30, 200).catch(() => page.mouse.click(30, 200));
  await sleep(200);
  eq([f0, f1, await faint()], [false, true, false],
     'en: the dock fades when nothing is touched, and is whole again at a touch');
  if (tag === 'landscape') {
    // sideways: the header goes on the way down, comes back on the way up,
    // and the gear's sheet is not modal -- and the dock is there throughout
    const hidden = () => page.evaluate(() => document.body.classList.contains('barhidden'));
    await page.evaluate(() => scrollTo(0, 0));
    await sleep(300);
    await page.evaluate(() => scrollBy(0, 240));
    await page.waitForFunction(() => document.body.classList.contains('barhidden'));
    await sleep(300);
    assert((await rect(page, 'header')).b <= 1, 'en, sideways: scrolled down, the header is away');
    assert(await isDrawn(page, '.nc-dock .nc-play'), 'en, sideways: and the dock is still there');
    await page.evaluate(() => scrollBy(0, -20));
    await page.waitForFunction(() => !document.body.classList.contains('barhidden'));
    await sleep(300);
    assert(near((await rect(page, 'header')).t, 0), 'en, sideways: a move up brings it back');
    await reveal(page);
    await gearOpen(page);
    await page.evaluate(() => scrollBy(0, 200));
    await sleep(400);
    assert(await gearUp(page), 'en, sideways: the gear\'s sheet is not modal: the page above it scrolls and the sheet stays');
    await gearClose(page);
    await page.evaluate(() => scrollTo(0, 0));
    await sleep(300);
  }
  // The place, the number and the speed as they were, so the next viewport
  // starts clean -- ON THE TOOLBOX TOO, since it keeps them for every device
  // now (§4.9): a phone that cleared only its own would be handed the last
  // device's ten seconds back at its first load.
  await page.evaluate(k => { localStorage.removeItem(k); localStorage.removeItem('bk_rate');
    localStorage.removeItem('parseh_at');
    Object.keys(localStorage).filter(x => x.startsWith('bk_pos:')).forEach(x => localStorage.removeItem(x)); }, K);
  await fetch(B + '/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({by: 'the test', settings: {bk_skip: {v: '10', at: Date.now() / 1000},
                                                     bk_rate: {v: '1', at: Date.now() / 1000}}})})
    .then(r => r.body?.cancel());
  await page.reload();
  await page.waitForFunction(() => document.querySelector('[data-parseh-gear]'));
  await reveal(page);
}


// ======== a finger: what a modifier-click and a tooltip used to keep ========
// §4.6 a held finger opens the copy and the card a mouse holds a key for;
// §4.7 "?" says what a button does, where no mouse can rest on it.  A TABLET
// IN THE BROWSER MODE is the case that suffered most: touch, and every
// control of the full interface.
const TABLET = {viewport: {width: 820, height: 1180}, hasTouch: true};
async function hold(page, sel, ms = 700) {
  const b = await page.locator(sel).first().boundingBox();
  const x = Math.round(b.x + b.width / 2), y = Math.round(b.y + b.height / 2);
  const pt = [{x, y, radiusX: 4, radiusY: 4, force: 1, id: 1}];
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: pt});
  await sleep(ms);
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  await sleep(150);
}
const wtRows = page => page.evaluate(() => [...document.querySelectorAll('.wt-menu button')].map(b => b.textContent));

async function partTouch() {
  console.log('\n== a finger on a word, and the ? that explains (§4.6, §4.7)');
  // ---- a) a tablet, the browser mode: copy and card, from a held finger
  let page = await newPage(TABLET, 'tablet');
  await page.goto(B + MADE.readers.en);
  await setMode(page, 'browser');
  await page.reload();
  await page.waitForFunction(() => !!window.ParsehWordTouch);
  await hold(page, 'main .p1 .wd');
  const rows = await wtRows(page);
  eq(rows.length, 4, 'a tablet, browser mode: a held finger opens four lines ' + JSON.stringify(rows));
  assert(/^Card for /.test(rows[0]), 'the first makes a card of that word: ' + rows[0]);
  assert(/^Copy /.test(rows[1]) && rows[2] === 'Copy the sentence',
         'then the chunk and the sentence: ' + JSON.stringify(rows.slice(1, 3)));
  // (a0.5.0) and the last, the nearest to the finger, flags the chunk to review later -- in both modes
  assert(/^Review later: “/.test(rows[3]), 'and the chunk to review later: ' + rows[3]);
  await page.click('.wt-menu button:nth-child(1)');
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  assert((await page.inputValue('#afa')).length > 0,
         'the card line opens the page\'s OWN card sheet, with that very word on it');
  await page.click('#acancel');
  // the copies go through the page's own shift-click, toast and all
  await page.evaluate(() => { window.__copied = null;
    const was = Parseh.copy; Parseh.copy = t => { window.__copied = t; return was.call(Parseh, t); }; });
  await hold(page, 'main .p1 .wd');
  await page.click('.wt-menu button:nth-child(2)');
  const chunk = await page.evaluate(() => window.__copied);
  assert(!!chunk, 'Copy “…” copies the chunk: ' + JSON.stringify(chunk));
  await hold(page, 'main .p1 .wd');
  await page.click('.wt-menu button:nth-child(3)');
  const sentence = await page.evaluate(() => window.__copied);
  assert(!!sentence && sentence.length >= chunk.length,
         'Copy the sentence copies the whole of it: ' + JSON.stringify(sentence));
  // a tap is untouched: it still plays, and opens no menu
  await tap(page, 'main .p1 .wd');
  await sleep(300);
  eq(await page.evaluate(() => [cur >= 0, !!document.querySelector('.wt-menu')]), [true, false],
     'a plain tap still plays the subparagraph, and opens no menu');
  await page.context().close();

  // ---- b) the mobile mode: the copies stay, the card does not (§18)
  page = await newPage(PHONE, 'phone touch');
  await page.goto(B + MADE.readers.en);
  await setMode(page, 'mobile');
  await page.reload();
  await page.waitForFunction(() => !!window.ParsehWordTouch);
  await hold(page, 'main .p1 .wd');
  const m = await wtRows(page);
  eq(m.length, 3, 'the mobile mode: three lines ' + JSON.stringify(m));
  assert(m.slice(0, 2).every(x => /^Copy/.test(x)) && /^Review later: “/.test(m[2]),
         'two copies and the flag for review later: nothing there makes a card');

  // ---- c) "?" -- every title one tap away
  eq(await page.evaluate(() => window.matchMedia('(hover: none)').matches), true,
     'the phone says it cannot hover');
  await page.waitForSelector('.px-ask');
  await reveal(page);
  await tap(page, '.px-ask');
  await page.waitForSelector('.px-tip');
  assert(/Tap anything/.test(await page.textContent('.px-tip')), 'pressed, ? says what it is for');
  await tap(page, '#toc');
  await sleep(250);
  eq(await page.evaluate(() => [document.querySelector('.px-tip').textContent.includes('jump to a paragraph'),
                                !document.getElementById('tocwrap').hidden]),
     [true, false], 'a tap on ☰ SAYS what it does, and does not open the contents');
  await tap(page, '.px-ask');
  eq(await page.evaluate(() => [!!document.querySelector('.px-tip'),
                                document.querySelector('.px-ask').getAttribute('aria-pressed')]),
     [false, 'false'], 'pressed again, the bubble goes and the page is itself');
  await tap(page, '#toc');
  await sleep(300);
  eq(await page.evaluate(() => !document.getElementById('tocwrap').hidden), true,
     'and ☰ opens the contents again');
  await page.context().close();

  // ---- d) a mouse keeps its tooltips: no ? at all
  page = await newPage(DESK, 'desk touch');
  await page.goto(B + MADE.readers.en);
  await page.waitForFunction(() => !!window.ParsehExplain);
  await sleep(300);
  eq(await page.evaluate(() => !!document.querySelector('.px-ask')), false,
     'where a mouse can hover, no ? is drawn');
  await page.context().close();

  // ---- e) the studio's pages carry the tag themselves (they load no parseh.js)
  page = await newPage(PHONE, 'decks touch');
  await page.goto(B + '/exercises/');
  await setMode(page, 'mobile');
  await page.reload();
  await page.waitForFunction(() => !!window.ParsehExplain, null, {timeout: 20000});
  await page.waitForSelector('.px-ask', {timeout: 20000});
  assert(await page.locator('.px-ask').isVisible(), 'the decks have a ? of their own');
  await page.context().close();
}


// ======== the place and the settings the toolbox keeps (§4.9) ========
// A phone goes on where the computer stopped: the reading place per book, the
// narration's settings and the theme are the toolbox's (lib/prefs.py,
// lib/prefs.js).  What is SHOWN -- the passes, the text size -- is not.
const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 ' +
                '(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36';
async function partPrefs() {
  console.log('\n== the reading place and the settings, kept by the toolbox');
  const kept = async () => (await (await fetch(B + '/__prefs')).json());
  // the toolbox is told a moment after a change (lib/prefs.js waits 900ms):
  // asked for until it knows, rather than slept at
  const until = async (fn, ms = 8000) => {
    for (const t = Date.now(); Date.now() - t < ms;) {
      const v = await fn();
      if (v !== null && v !== undefined && v !== false) return v;
      await sleep(200);
    }
    return null;
  };
  const READER = B + MADE.readers.en;
  const path = new URL(READER).pathname;
  // the reader's own part read this book before us, and the toolbox keeps
  // that place now: forgotten, so this part starts where a new book does
  await fetch(B + '/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({forget: path})}).then(r => r.body?.cancel());

  // ---- a) the computer reads, and sets a speed and a theme
  let page = await newPage(DESK, 'prefs desk');
  await page.goto(READER);
  await page.waitForFunction(() => !!window.ParsehPrefs);
  eq(await page.evaluate(() => !!document.querySelector('.pf-bar')), false,
     'the first device to open a book is asked nothing');
  // a click on a subparagraph is the reading place, as it always was; the
  // narration is stopped where it is, so the place stays where the click put it
  await page.locator('main .sub').nth(2).click();
  await page.evaluate(() => { cont = false; loop = false; document.getElementById('audio').pause(); });
  await sleep(300);
  const at = await page.evaluate(() => cur);
  assert(at > 0, 'the computer reads on to subparagraph ' + at);
  let rec = await until(async () => {
    const r = (await kept()).places[path];
    return r && r.i === at ? r : null;
  });
  assert(rec, 'the toolbox was told where the book was left');
  eq([rec.i, !!rec.label, !!rec.by, rec.pct > 0], [at, true, true, true],
     'the place it keeps: which subparagraph, said in words, by which device, how far in');
  await page.click('.nc-chip');
  await page.click('.nc-pop button:nth-child(9)');
  await page.evaluate(() => Parseh.theme.set('dark'));
  const set = await until(async () => {
    const j = await kept();
    return (j.settings.bk_rate || {}).v === '1.5' && j.settings.parseh_theme ? j.settings : null;
  });
  assert(set, 'the toolbox was told the speed and the theme');
  eq([set.bk_rate.v, set.parseh_theme.v, !!set.bk_rate.at], ['1.5', 'dark', true],
     'the speed and the theme, each with the moment it was set');
  // what is SHOWN is not the toolbox's: the text size stays on the device
  await page.evaluate(() => { localStorage.setItem('parseh_typo', '{"size":22}'); });
  await sleep(1200);
  eq(Object.keys((await kept()).settings).filter(k => /typo|p1|nogloss/.test(k)), [],
     'the text size and the passes stay with the device that shows them');
  await page.context().close();

  // ---- b) the phone opens the same book: the settings arrive, the place is ASKED
  page = await newPage({...PHONE, userAgent: ANDROID}, 'prefs phone');
  await page.goto(READER);
  await setMode(page, 'mobile');
  await page.reload();
  await page.waitForFunction(() => localStorage.getItem('bk_rate') === '1.5', null, {timeout: 10000});
  eq(await page.evaluate(() => [document.documentElement.getAttribute('data-theme'),
                                document.getElementById('audio').playbackRate]),
     ['dark', 1.5], 'the phone wears the speed and the theme the computer set');
  await page.waitForSelector('.pf-bar', {timeout: 10000});
  const said = await page.textContent('.pf-bar');
  assert(/you were at/.test(said) && /computer|Mac|Windows|Linux/.test(said),
         'and is asked about the place, saying whose it is and when: ' + JSON.stringify(said.slice(0, 80)));
  eq(await page.evaluate(() => cur), -1, 'nothing has moved while the question stands');
  await tap(page, '.pf-go');
  await sleep(400);
  eq(await page.evaluate(() => [cur, !!document.querySelector('.pf-bar')]), [at, false],
     '"Go there" takes it to that very subparagraph, and the question goes');
  // the phone reads on, and says so in its own name
  await page.evaluate(() => scrollTo(0, 0));
  await sleep(250);
  await page.locator('main .sub').nth(3).click();
  await page.evaluate(() => { cont = false; loop = false; document.getElementById('audio').pause(); });
  await sleep(300);
  const on = await page.evaluate(() => cur);
  assert(on !== at, 'the phone reads on to another subparagraph (' + on + ')');
  rec = await until(async () => {
    const r = (await kept()).places[path];
    return r && r.i === on ? r : null;
  });
  assert(rec, 'the phone hands its place back');
  assert(/Android phone/.test(rec.by), 'in a name it works out for itself: ' + JSON.stringify(rec.by));
  await page.context().close();

  // ---- c) the shelf shows it, on a phone that has never opened the book
  page = await newPage({...PHONE, userAgent: ANDROID}, 'prefs shelf');
  await page.goto(B + '/');
  await setMode(page, 'mobile');
  await page.goto(B + '/m/books/');
  await page.waitForSelector('a.m-book[data-lang=en]');
  const tag = await page.evaluate(() => {
    const a = document.querySelector('a.m-book[data-lang=en]');
    const t = a.querySelector('.m-readon');
    return [a.getAttribute('data-place'), t ? t.textContent : null, t ? t.title : null];
  });
  assert(+tag[0] > 0 && /read on · \d+%/.test(tag[1] || ''),
         'the shelf says how far the book has been read, from the toolbox: ' + JSON.stringify(tag.slice(0, 2)));
  assert(/Android phone/.test(tag[2] || ''), 'and whose place it is: ' + JSON.stringify(tag[2]));
  await page.context().close();

  // ---- d) a device with no toolbox to ask is not stuck
  page = await newPage(DESK, 'prefs alone');
  await page.goto(READER);
  await page.waitForFunction(() => !!window.ParsehPrefs);
  await page.evaluate(() => { window.fetch = () => Promise.reject(new Error('no toolbox')); });
  await page.locator('main .sub').nth(1).click();
  await page.evaluate(() => document.getElementById('audio').pause());
  await sleep(1200);
  eq(await page.evaluate(() => { const v = JSON.parse(localStorage.getItem('bk_pos:' + location.pathname));
                                 return !!v && typeof v.i === 'number'; }), true,
     'with the toolbox unreachable the page still keeps its own place, and says nothing about it');
  await page.context().close();
}


// ======== the videos, on a phone (§4.2) ========
// The shelf of channels, a channel's own page with its videos, and the
// player itself with the mobile layer over it: the dock drives the video, the
// phone turned puts the video at the left and the transcript at the right
// with a draggable divider, and ⛶ gives the video the whole screen with the
// line being said over it.
//
// THE SHELF IS THE CHANNELS (the owner, 2026-09-23, decision C): one card per
// channel and the videos a tap inside, exactly as the browser's index does
// it.  It was a flat list before -- every video of every channel under a
// heading apiece -- which on a phone is a page you scroll past rather than
// one you choose from.  What that shelf looks like with the computer away is
// driven under "kept on this phone", where the computer is really stopped.
async function partVideo() {
  console.log('\n== the videos, on a phone');
  const V = MADE.video;
  const ctx = await browser.newContext(PHONE);
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push('video: ' + e.message); console.log('PAGE ERROR video', e.message); });
  page.touch = await ctx.newCDPSession(page);
  await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  await page.goto(B + '/');
  await setMode(page, 'mobile');

  // ---- a) the shelf: CHANNELS, and the videos a tap inside (decision C)
  await page.goto(B + '/m/videos/');
  await page.waitForSelector('a.m-book');
  const shelfIs = await page.evaluate(() => ({
    cards: [...document.querySelectorAll('a.m-book')].map(a => a.getAttribute('href')),
    chans: document.querySelectorAll('a.m-book.m-chancard').length,
    players: [...document.querySelectorAll('a.m-book')]
      .filter(a => /^\/youtube\/v\//.test(a.getAttribute('href'))).length,
    del: !!document.querySelector('.card-del'),
    stands: document.body.getAttribute('data-browser-page'),
    tags: [...document.querySelectorAll('.m-chancard .m-tags .tag')].map(t => t.textContent)}));
  eq([shelfIs.chans, shelfIs.players, shelfIs.del, shelfIs.stands],
     [1, 0, false, '/youtube/'],
     'the videos shelf is the channels — one card per channel and not one that opens a ' +
     'player, nothing that deletes, and the browser page it stands for: ' +
     JSON.stringify(shelfIs.cards));
  assert(shelfIs.tags.some(t => /^1 video$/.test(t)),
         'and a card says how many videos are inside it: ' + JSON.stringify(shelfIs.tags));
  allFit(await targets(page, '.m-shelf a, .m-bar a[href], .m-bar button'),
         'its cards and its bar: 48px, on the screen, reached by a tap');
  assert(await sideways(page) <= 0, 'and it does not scroll sideways');
  // THE VIDEOS ARE ONE TAP INSIDE.  The card is the whole way in, and the
  // channel's own page is where the player is reached from -- so the tap is
  // made here rather than the address being read off the card and jumped to.
  await Promise.all([page.waitForURL(/\/m\/videos\/[^/]+\/$/), tap(page, 'a.m-chancard')]);
  await page.waitForSelector('a.m-book');
  const inside = await page.evaluate(() => {
    const back = document.querySelector('.m-tagline a[href]');
    return {title: document.title,
            videos: [...document.querySelectorAll('a.m-book')].map(a => a.getAttribute('href')),
            back: back ? back.getAttribute('href') : ''};
  });
  assert(inside.videos.length >= 1 && inside.videos.every(h => /^\/youtube\/v\//.test(h)),
         'a channel opens on its videos, each one opening the player: ' +
         JSON.stringify(inside.videos));
  eq(inside.back, '/m/videos/', 'with the way back to all the channels said on the page');
  allFit(await targets(page, '.m-shelf a, .m-bar a[href], .m-bar button'),
         'the channel page: 48px, on the screen, reached by a tap');

  // ---- b) the player, with the mobile layer
  await Promise.all([page.waitForURL(new RegExp(`/youtube/v/${V}/$`)), tap(page, 'a.m-book')]);
  await page.waitForFunction(() => !!window.ParsehMobilePlayer && !!window.ParsehNarr);
  await page.waitForFunction(() => document.querySelectorAll('#segs .seg').length > 0);
  await settle(page);
  await shot(page, 'video-phone');
  eq(await page.evaluate(() => [document.documentElement.classList.contains('m-player'),
                                document.body.hasAttribute('data-mobile-page'),
                                !!document.querySelector('.m-rmore'), !!document.querySelector('header > button.pg-gear'),
                                !!document.querySelector('.nc-dock')]),
     [true, true, false, true, true],
     'the player wears the mobile layer, with the gear where ⋯ was (a0.5.0: and no ⋯) and the dock at the foot');
  for (const no of ['#dl', '#vidinfo', '#captimes', '#lookupset', '#sbs', '#stop', 'main > .hint'])
    assert(!(await isDrawn(page, no)), 'the player: no ' + no);
  // nor the + between two captions, "write a note here" (a0.3.2): it writes
  // into the video, and a mobile page never writes -- the book's reader has
  // hidden its own (.gap .plus) from the first.  Counted first, so the check
  // cannot pass for want of a transcript with seams
  eq(await page.evaluate(() => document.querySelectorAll('#segs .gap .plus').length > 0), true,
     'the transcript has its seams, each with its +');
  assert(!(await isDrawn(page, '#segs .gap .plus')), 'the player: no + between the captions to write a note with');
  allFit(await targets(page, 'header a[href], header button'), 'its header: 48px, on the screen');
  // the gear opens the rest, a group to a line (it took ⋯'s place; tests/gear_player.mjs drives every row)
  await tap(page, 'header > button.pg-gear');
  await settle(page);
  eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel[data-pg-page=video] [data-pg-group]')]
       .filter(e => !e.hidden && e.getClientRects().length).map(e => e.getAttribute('data-pg-group'))),
     ['watching', 'looking', 'playback', 'text'].concat(await page.evaluate(() => window.ParsehZoom ? ['zoom'] : []), ['colours', 'interface']),
     'the gear opens the groups this page has');
  await tap(page, 'header > button.pg-gear');

  // ---- c) the dock drives the video
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready(), null, {timeout: 20000});
  await tap(page, '.nc-dock .nc-play');
  await page.waitForFunction(() => !ParsehPlayer.paused(), null, {timeout: 8000});
  eq(await page.evaluate(() => document.querySelector('.nc-play').textContent), '‖',
     'a tap on ⏯ plays the video, and it says pause');
  await tap(page, '.nc-dock .nc-play');
  await page.waitForFunction(() => ParsehPlayer.paused());
  await page.evaluate(() => ParsehPlayer.seek(0));
  await sleep(200);
  await tap(page, '.nc-dock .nc-skip[data-skip="1"]');
  await sleep(400);
  const at = await page.evaluate(() => ParsehPlayer.time());
  assert(at >= 4.5, `↻ moves the video on by the seconds it says (${at.toFixed(2)}s)`);
  await tap(page, '.nc-dock .nc-chip');
  await page.waitForSelector('.nc-pop');
  const speeds = await page.evaluate(() => [...document.querySelectorAll('.nc-popb')].map(b => b.textContent));
  assert(speeds.includes('1.5×'), 'the chip offers the speeds this player will play at: ' + JSON.stringify(speeds));
  await page.click('.nc-pop button:nth-child(' + (speeds.indexOf('1.5×') + 1) + ')');
  await sleep(300);
  eq(await page.evaluate(() => [ParsehPlayer.rate(), document.querySelector('.nc-chip').textContent]),
     [1.5, '1.5×'], 'and sets the video to it');
  eq(await page.evaluate(() => { const b = document.querySelector('.m-vfull'); return !!b && !b.hidden; }),
     false, 'upright there is no full-screen button: a video on the whole screen leaves nothing to read');

  // ---- d) held sideways: the video at the left, the transcript at the right
  await page.setViewportSize(LAND.viewport);
  await sleep(700);
  await settle(page);
  await shot(page, 'video-landscape');
  eq(await page.evaluate(() => {
    const wrap = document.getElementById('playerwrap').getBoundingClientRect();
    const segs = document.getElementById('segs').getBoundingClientRect();
    const full = document.querySelector('.m-vfull');
    return [document.body.classList.contains('sbs'), wrap.left < 5, segs.left >= wrap.right - 1,
            !!full && !full.hidden];
  }), [true, true, true, true],
     'held sideways: the video at the left, the transcript at the right, and ⛶ appears');
  // the divider between them takes a finger
  const was = await page.evaluate(() => document.getElementById('playerwrap').getBoundingClientRect().width);
  const g = await page.locator('#grip').boundingBox();
  const pt = (x, y) => [{x, y, radiusX: 4, radiusY: 4, force: 1, id: 1}];
  const gx = Math.round(g.x + g.width / 2), gy = Math.round(g.y + g.height / 2);
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: pt(gx, gy)});
  for (let k = 1; k <= 5; k++) {
    await page.touch.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: pt(gx + k * 20, gy)});
    await sleep(20);
  }
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  await sleep(300);
  const now = await page.evaluate(() => document.getElementById('playerwrap').getBoundingClientRect().width);
  assert(now > was + 20, `the divider between them is dragged by a finger (${Math.round(was)} → ${Math.round(now)}px)`);

  // ---- e) THE WHOLE SCREEN (the owner's 5 of 2026-09-23).  ⛶ takes the
  // page, not the video's box: an embedded YouTube frame given the screen
  // takes the top layer with it and nothing of Parseh's can be drawn over it
  // -- which is why the subtitles were never seen and it would not let go.
  // The contract is html.m-vfullon: Parseh's own layout over the page,
  // whether or not the phone grants the browser's full screen.
  // stand on a caption that HAS phrases to gloss: a caption the video merely
  // frames (.plain, the video's own English) is shown as it stands and never
  // glossed, so a subtitle copied from one has nothing to tap
  assert(await page.evaluate(() => {
    const seg = [...document.querySelectorAll('#segs .seg')].find(s => s.querySelector('.fa .w'));
    if (!seg) return false;
    seg.querySelector('.lab').click();     // plays from this caption's start
    return true;
  }), 'the fixture video has a caption with phrases to gloss');
  await sleep(600);
  await page.evaluate(() => ParsehPlayer.pause());
  await tap(page, '.m-vfull');
  await sleep(700);
  eq(await page.evaluate(() => [document.documentElement.classList.contains('m-vfullon'),
                                !!document.querySelector('.m-subs .m-subline'),
                                document.getElementById('cloud').parentNode.tagName,
                                !!document.querySelector('#playerwrap .m-vout')]),
     [true, true, 'BODY', true],
     '⛶: the video is laid over the whole page, the line being said lies on it, the gloss cloud ' +
     'stays where it belongs (nothing outside a full-screen element is drawn, which is why it ' +
     'must not be moved into the video\'s box), and there is a way out drawn on the screen');
  eq(await page.evaluate(() => {
    const clean = e => (e ? e.textContent : '').replace(/\s+/g, ' ').trim();
    const air = clean(document.querySelector('#segs .seg.on-air'));
    return [!!air, air === clean(document.querySelector('.m-subs .m-subline'))];
  }), [true, true], 'and it is the very line the transcript is following, as it stands');
  // the subtitle is a COPY, and a copy carries no listeners: the tap must
  // still open the gloss cloud, which is the one thing the whole screen is for
  await page.waitForSelector('.m-subs .m-subline .w');
  await tap(page, '.m-subs .m-subline .w');
  await sleep(400);
  eq(await page.evaluate(() => {
    const cloud = document.getElementById('cloud'), r = cloud.getBoundingClientRect();
    const w = document.querySelector('.m-subs .m-subline .w.hot');
    return [!!w, !cloud.hidden, r.width > 0 && r.height > 0];
  }), [true, true, true],
     'and a tap on a word of the subtitle opens its gloss, against the subtitle itself — the ' +
     'copy says which caption and which phrase it is, and the player hangs the cloud on the copy');
  // the back gesture is one of the three ways out: the entry pushed on the way in
  await page.goBack();
  await sleep(500);
  eq(await page.evaluate(() => [document.documentElement.classList.contains('m-vfullon'),
                                !!document.querySelector('.m-subs'),
                                document.getElementById('cloud').parentNode.tagName]),
     [false, false, 'BODY'], 'the phone\'s back gesture leaves it, and everything goes home');
  // and the corner ⛶ itself, which is what a finger finds first
  await tap(page, '.m-vfull');
  await sleep(600);
  assert(await page.evaluate(() => document.documentElement.classList.contains('m-vfullon')),
         'in again');
  await tap(page, '#playerwrap .m-vout');
  await sleep(500);
  eq(await page.evaluate(() => document.documentElement.classList.contains('m-vfullon')), false,
     'and the corner ⛶ leaves it too');
  // the third way: the black beside the picture, which is the box itself (the
  // video swallows the taps that land on the video)
  await tap(page, '.m-vfull');
  await sleep(600);
  eq(await page.evaluate(() => {
    document.getElementById('playerwrap').click();
    return document.documentElement.classList.contains('m-vfullon');
  }), false, 'and a tap on the black beside the picture leaves it too — three ways out, so nobody is trapped');

  // ---- e1) THE SIZE OF THE WORDS, off the whole screen and on it (L12; the
  // owner, 2026-09-25 and -28: "resizing of text in mobile version of videos
  // interface working both in standard and full-screen mode" -- ONE SIZE
  // EACH: the transcript keeps its own, the subtitles get one of theirs).
  // Nothing made the words larger or smaller from the whole screen: the
  // header is under the black box there, and Aa was under ⋯.
  const words = () => page.evaluate(() => {
    const px = s => { const e = document.querySelector(s); return e ? parseFloat(getComputedStyle(e).fontSize) : null; };
    const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    return {seg: px('#segs .seg:not(.plain) .fa'), sub: px('.m-subs .m-subline .fa'),
            near: px('.m-subs .m-subnear .fa'), yt: {fa: tok('--yt-fa'), sub: tok('--yt-sub')}};
  });
  const panelFacts = () => page.evaluate(() => {
    const p = document.querySelector('.parseh-typo'), r = p.getBoundingClientRect();
    const hd = p.querySelector('.thead').getBoundingClientRect();
    const at = document.elementFromPoint(hd.left + hd.width / 2, hd.top + hd.height / 2);
    return {up: !p.hidden, l: r.left, t: r.top, r: r.right, b: r.bottom, W: innerWidth, H: innerHeight,
            onTop: !!at && p.contains(at),
            rows: [...p.querySelectorAll('.trow')].filter(t => getComputedStyle(t).display !== 'none')
                    .map(t => t.querySelector('input').id.replace('st-', '')),
            reset: p.querySelector('.treset').getClientRects().length > 0};
  });
  const slide = (id, v) => page.evaluate(([id, v]) => {
    const i = document.getElementById(id);
    i.value = v;
    i.dispatchEvent(new Event('input', {bubbles: true}));
  }, [id, v]);
  // the gear's own slider for a field of Aa's (a0.5.0: the header's Aa opens the gear at Text)
  const gearSlide = (row, v) => page.evaluate(([row, v]) => {
    const i = document.querySelector(`.pg-panel[data-pg-page=video] [data-pg-row="${row}"] input[type=range]`);
    i.value = v;
    i.dispatchEvent(new Event('input', {bubbles: true}));
  }, [row, v]);
  const gearFacts = () => page.evaluate(() => {
    const p = document.querySelector('.pg-panel[data-pg-page=video]'), r = p.getBoundingClientRect();
    const hd = p.querySelector('.pg-head').getBoundingClientRect();
    const at = document.elementFromPoint(hd.left + hd.width / 2, hd.top + hd.height / 2);
    const text = p.querySelector('[data-pg-group=text]'), body = p.querySelector('.pg-body');
    return {up: !p.hidden, l: r.left, t: r.top, r: r.right, b: r.bottom, W: innerWidth, H: innerHeight,
            onTop: !!at && p.contains(at), old: document.querySelector('.parseh-typo').hidden,
            atText: Math.round(text.getBoundingClientRect().top - body.getBoundingClientRect().top),
            rows: [...text.querySelectorAll('[data-pg-row]')].filter(t => !t.hidden && t.getClientRects().length).map(t => t.dataset.pgRow)};
  });
  const yt = () => page.evaluate(() => JSON.parse(localStorage.getItem('yt_typo') || '{}'));
  const enterFull = async () => {
    await page.evaluate(() => {
      const seg = [...document.querySelectorAll('#segs .seg')].find(s => s.querySelector('.fa .w'));
      seg.querySelector('.lab').click();
    });
    await sleep(500);
    await page.evaluate(() => ParsehPlayer.pause());
    await tap(page, '.m-vfull');
    await sleep(600);
  };
  const fullOn = () => page.evaluate(() => document.documentElement.classList.contains('m-vfullon'));
  const panelUp = () => page.evaluate(() => !document.querySelector('.parseh-typo').hidden);
  const ready = async () => {
    await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready() && !!window.ParsehMobilePlayer,
                               null, {timeout: 20000});
    await page.waitForFunction(() => document.querySelectorAll('#segs .seg').length > 0);
    await sleep(400);
  };

  // the ordinary view: Aa on the header's first line, a target a thumb
  // reaches, the header still one line
  allFit(await targets(page, '#typo'), 'the text size, Aa, stands on the header\'s first line: 48px, on the screen, reached by a tap');
  eq(await page.evaluate(() => [document.querySelector('#typo').getBoundingClientRect().top < 60,
                                document.querySelector('header').getBoundingClientRect().height < 70,
                                !document.querySelector('header').classList.contains('m-more')]),
     [true, true, true], 'without opening ⋯, and the header is still one line');
  await tap(page, '#typo');
  await sleep(300);
  let gf = await gearFacts();
  eq([gf.up, gf.onTop, gf.old, gf.rows], [true, true, true, ['fa', 'sub', 'gl', 'width', 'lead', 'reset']],
     'Aa opens the gear (not the old panel) at Text: the transcript\'s size and the subtitles\' and the rest, each its own slider');
  assert(gf.atText >= 0 && gf.atText <= 14, `at its Text group (${gf.atText}px from the top of the sheet)`);
  assert(gf.t >= 0 && gf.b <= gf.H + 0.5 && gf.l >= 0 && gf.r <= gf.W,
         `held sideways it is on the screen (${Math.round(gf.t)}-${Math.round(gf.b)} of ${gf.H})`);
  await shot(page, 'video-size-panel-ordinary');
  const w0 = await words();
  await gearSlide('fa', 30);
  const w1 = await words();
  eq([w0.seg, w1.seg, w1.yt.fa, w1.yt.sub], [20, 30, '30px', w0.yt.sub],
     'the transcript\'s own slider moves the transcript\'s words (20 → 30px) and not the subtitles\' size, --yt-sub as it was');
  await tap(page, '.pg-panel[data-pg-page=video] .pg-x');
  eq(await page.evaluate(() => ParsehGear.mounted().isOpen()), false, '✕ closes it');
  let pf;
  // where a panel opened LOW in the screen goes: the clamp (a panel opened
  // from ⋯ in a phone held sideways ran 69px off the foot).  Aa is on the
  // first line now, so the low anchor is made here, of a button of the test's
  const low = await page.evaluate(() => {
    const b = document.createElement('button');
    b.style.cssText = 'position:fixed;left:24px;top:' + (innerHeight - 56) + 'px;width:48px;height:48px;z-index:1';
    document.body.appendChild(b);
    ParsehPlayer.typo.open(b);
    const r = document.querySelector('.parseh-typo').getBoundingClientRect();
    ParsehPlayer.typo.close();
    b.remove();
    return {t: r.top, b: r.bottom, H: innerHeight};
  });
  assert(low.t >= 8 && low.b <= low.H - 8 + 0.5,
         `opened from a button at the foot of a 390px screen the panel is pulled up to fit (${Math.round(low.t)}-${Math.round(low.b)})`);

  // the whole screen: a button of its own for the subtitles' size, beside the other two
  await enterFull();
  assert(await fullOn(), 'on the whole screen');
  const corner = await page.evaluate(() => {
    const q = s => { const e = document.querySelector(s), r = e && e.getBoundingClientRect(); return r && {l: r.left, r: r.right, t: r.top, w: r.width, h: r.height}; };
    const b = document.querySelector('.m-vtxt');
    return {txt: q('.m-vtxt'), ctx: q('.m-vctx'), out: q('.m-vout'), name: b && b.getAttribute('aria-label'),
            text: b && b.textContent, expanded: b && b.getAttribute('aria-expanded'),
            inBox: !!(b && b.parentNode.id === 'playerwrap')};
  });
  eq([corner.text, corner.inBox, corner.expanded, /subtitles/.test(corner.name || '')], ['Aa', true, 'false', true],
     'Aa, in the corner, says what it is (' + corner.name + ') and is not pressed');
  assert(corner.txt.w >= 48 && corner.txt.h >= 48 && corner.txt.r <= corner.ctx.l && corner.txt.t === corner.ctx.t &&
         corner.ctx.r <= corner.out.l,
         'a 48px button of its own beside the lines-around switch and ⛶, none on top of another: ' + JSON.stringify(corner));
  await tap(page, '.m-vtxt');
  await sleep(300);
  pf = await panelFacts();
  eq([pf.up, pf.onTop, pf.rows, pf.reset], [true, true, ['sub', 'gl'], false],
     'it opens the panel over the picture -- drawn on top of the black box -- with the subtitles\' slider and the glosses\', ' +
     'and no reset that would put back the transcript\'s rows it does not show');
  assert(pf.t >= 0 && pf.b <= pf.H && pf.r <= pf.W, 'on the screen');
  eq(await page.evaluate(() => document.querySelector('.m-vtxt').getAttribute('aria-expanded')), 'true', 'and Aa says it is open');
  await shot(page, 'video-size-panel-full');
  // the subtitles change LIVE, under the finger, while the video plays
  await page.evaluate(() => { ParsehPlayer.setRate(1); ParsehPlayer.seek(2.05); ParsehPlayer.play(); });
  await sleep(300);
  const s0 = await words();
  const sl = await page.evaluate(() => { const i = document.getElementById('st-sub'), r = i.getBoundingClientRect();
    return {x: r.left, y: r.top + r.height / 2, w: r.width, v: +i.value, min: +i.min, max: +i.max}; });
  const sx = Math.round(sl.x + 8 + (sl.v - sl.min) / (sl.max - sl.min) * (sl.w - 16)), sy = Math.round(sl.y);
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: pt(sx, sy)});
  for (let k = 1; k <= 8; k++) {
    await page.touch.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: pt(sx + k * 12, sy)});
    await sleep(25);
  }
  const mid = await words();
  await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  await sleep(200);
  const s1 = await words();
  const playing = await page.evaluate(() => !ParsehPlayer.paused());
  assert(s0.sub === 20 && mid.sub > 20 && s1.sub > 20 && Math.abs(s1.sub - parseFloat(s1.yt.sub)) < 0.01,
         `dragged by a finger, the subtitle grows as it goes (${s0.sub} → ${mid.sub} → ${s1.sub}px) and is the size the slider says`);
  eq([playing, await panelUp(), s1.seg, s1.yt.fa], [true, true, 30, '30px'],
     'the video went on playing, the panel stayed open under the finger, and the transcript\'s words are the size they were (30px)');
  eq((await yt()).sub, parseFloat(s1.yt.sub), 'the size is kept for this device (yt_typo)');
  await page.evaluate(() => ParsehPlayer.pause());
  // the lines around the one being said follow the size, in their own proportion
  await tap(page, '.m-vctx');
  await sleep(300);
  const ctxSizes = await words();
  assert(ctxSizes.near === null || Math.abs(ctxSizes.near - ctxSizes.sub * 0.82) < 0.6,
         `the caption beside keeps its .82 of the line being said (${ctxSizes.near} of ${ctxSizes.sub}px)`);
  assert(await panelUp(), 'the lines-around switch, pressed, leaves the panel open: the change is seen with it there');
  await tap(page, '.m-vctx');
  await sleep(200);
  // Aa again closes it; a second press opens it
  await tap(page, '.m-vtxt');
  eq([await panelUp(), await page.evaluate(() => document.querySelector('.m-vtxt').getAttribute('aria-expanded'))],
     [false, 'false'], 'Aa again closes the panel');
  await tap(page, '.m-vtxt');
  eq(await panelUp(), true, 'and again opens it');
  // a tap on the black beside the picture closes the panel first -- the
  // whole screen stays; the next one leaves
  assert(await page.evaluate(() => document.elementFromPoint(24, 200) === document.getElementById('playerwrap')),
         'the black beside the picture is at the edge of the screen');
  await page.touchscreen.tap(24, 200);
  await sleep(300);
  eq([await panelUp(), await fullOn()], [false, true], 'a tap on the black closes the panel and leaves the video on the whole screen');
  // a tap on a phrase of the subtitle: the panel is out of the cloud's way
  await tap(page, '.m-vtxt');
  await page.waitForSelector('.m-subs .m-subline .w');
  await tap(page, '.m-subs .m-subline .w');
  await sleep(400);
  eq([await panelUp(), await page.evaluate(() => !document.getElementById('cloud').hidden)], [false, true],
     'a tap on a word of the subtitle closes the panel and opens the gloss');
  await tap(page, '.m-subs .m-subline .w');
  // ⛶ with the panel open: the panel goes with the whole screen, and so does the button
  await tap(page, '.m-vtxt');
  await tap(page, '#playerwrap .m-vout');
  await sleep(500);
  eq(await page.evaluate(() => [document.documentElement.classList.contains('m-vfullon'), !!document.querySelector('.m-vtxt'),
                                document.querySelector('.parseh-typo').hidden]),
     [false, false, true], '⛶ with the panel open leaves the whole screen, and the panel and Aa go with it');
  // the back gesture too
  await enterFull();
  await tap(page, '.m-vtxt');
  assert(await panelUp(), 'in again, the panel open');
  await page.goBack();
  await sleep(500);
  eq([await fullOn(), await panelUp()], [false, false], 'the phone\'s back gesture leaves the whole screen and the panel with it');
  // remembered: after a reload the subtitles are the size they were left,
  // the transcript its own
  const kept = await yt();
  await page.reload();
  await ready();
  await enterFull();
  const back = await words();
  eq([back.sub, back.yt.sub, back.seg], [kept.sub, kept.sub + 'px', 30],
     `after a reload the subtitles are the size they were left (${kept.sub}px) and the transcript's its own (30px)`);
  await tap(page, '#playerwrap .m-vout');
  await sleep(400);
  // a store written before the subtitles had a size of their own: the subtitles
  // at their default, the rest as it was kept
  await page.evaluate(() => localStorage.setItem('yt_typo', JSON.stringify({fa: 26, gl: 14})));
  await page.reload();
  await ready();
  const old = await words();
  eq([old.yt.fa, old.yt.sub], ['26px', '20px'],
     'a device that had set only the transcript\'s size gets the subtitles\' at their default (20px) and keeps its 26px');
  await page.evaluate(() => { ParsehPlayer.typo.reset(); ParsehPlayer.setRate(1.5); });
  eq((await words()).yt, {fa: '20px', sub: '20px'}, 'reset puts every size back');
  // and a screen only 320px wide: the first line still holds the hub, the
  // shelf, Aa, ? and the gear (⋯'s place) in one line, the title given up for them
  const tiny = await newPage({viewport: {width: 320, height: 568}, isMobile: true, hasTouch: true}, 'tiny');
  await tiny.goto(B + '/');
  await setMode(tiny, 'mobile');
  await tiny.goto(B + `/youtube/v/${V}/`);
  await tiny.waitForFunction(() => !!window.ParsehMobilePlayer && document.querySelectorAll('#segs .seg').length > 0);
  await settle(tiny);
  eq(await tiny.evaluate(() => [document.querySelector('header').getBoundingClientRect().height < 70,
                                getComputedStyle(document.querySelector('header .ttl')).display]),
     [true, 'none'], 'at 320px the header is one line, with the title left out');
  allFit(await targets(tiny, 'header a[href], header button'), 'its header at 320px: Aa, ? and the gear 48px, on the screen, reached by a tap');
  await shot(tiny, 'video-320');
  await tiny.context().close();
  // YouTube's own ⛶ is not offered on a phone: there is one whole screen,
  // Parseh's, and it carries the subtitles
  eq(await page.evaluate(() => (window.YTFRANK && window.ParsehPlayer &&
                                ParsehPlayer.kind() === 'film') ? 'film' : 'youtube'), 'film',
     'the fixture is a film of this machine, so YouTube\'s own button is not in play here');

  // ---- e2) the speed chip says the speed that was CHOSEN, at once (the
  // owner's 6: on a video it lagged one change behind, because it painted
  // what the player reported before the player had taken the new rate)
  // the book's own speed, as this phone left it: a video must not touch it
  const bookRate = await page.evaluate(() => localStorage.getItem('bk_rate'));
  await tap(page, '.nc-dock .nc-chip');
  await page.waitForSelector('.nc-pop');
  const want = await page.evaluate(() => {
    const b = [...document.querySelectorAll('.nc-popb')].find(x => x.textContent === '1.25×');
    if (!b) return null;
    b.click();
    return document.querySelector('.nc-chip').textContent;   // read with no wait at all
  });
  eq(want, '1.25×', 'the chip says the speed the finger chose, without waiting for the player');
  await sleep(600);
  eq(await page.evaluate(() => [ParsehPlayer.rate(), document.querySelector('.nc-chip').textContent]),
     [1.25, '1.25×'], 'and the player has it a moment later, with the chip unchanged');
  eq(await page.evaluate(() => localStorage.getItem('vd_rate')), '1.25',
     'a video remembers a speed of its own, vd_rate');
  eq(await page.evaluate(() => localStorage.getItem('bk_rate')), bookRate,
     `and leaves the book's alone (${JSON.stringify(bookRate)}): watching and listening are ` +
     'different habits, and the owner asked for them to be kept apart');
  // and it is still that speed when the video is opened again -- the player
  // is put back to it the moment it says it is ready, which is the whole of
  // what "remembers" means
  await page.reload();
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready());
  await sleep(700);
  eq(await page.evaluate(() => [ParsehPlayer.rate(), document.querySelector('.nc-chip').textContent]),
     [1.25, '1.25×'], 'opened again, the video plays at the speed it was left at, and says so');

  // ---- f) the browser mode is untouched
  await page.setViewportSize(DESK.viewport);
  await setMode(page, 'browser');
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll('#segs .seg').length > 0);
  eq(await page.evaluate(() => [!!document.querySelector('.m-rmore'),
                                !!document.querySelector('.nc-dock'),
                                document.getElementById('dl').offsetParent !== null]),
     [false, false, true], 'in the browser mode the player is the page it always was');
  assert(await isDrawn(page, '#segs .gap .plus'), 'the + between the captions there, to write a note with');
  await page.locator('#typo').click();
  await page.waitForFunction(() => window.ParsehGear && ParsehGear.mounted().isOpen());
  eq(await page.evaluate(() => [...document.querySelectorAll('.pg-panel[data-pg-page=video] [data-pg-group=text] [data-pg-row]')]
       .filter(t => !t.hidden && t.getClientRects().length).map(t => t.dataset.pgRow)),
     ['fa', 'gl', 'width', 'lead', 'reset'], 'and the Text group Aa opens has no subtitles slider: a desktop has no subtitles');
  await page.locator('.pg-panel[data-pg-page=video] .pg-x').click();
  await ctx.close();
}


// ======== the studio's library and a document, on a phone (§4.3) ========
// Both pages carry the two layouts, as the deck pages do.  What is drawn is
// READING: the library to find a document in, and the document to read --
// with its exercises, which can be answered, since answering writes nothing.
// Everything that writes, builds, downloads or administers is not there (the
// owner's choice: no View PDF and no Print either).
const LESSON = `---
title: A phone lesson
lang: en
---

# A phone lesson

Some plain text to read on a phone.

:::exercise single-choice
prompt: Which article goes before [apple]{tl}?
- [ ] [a]{tl}
- [x] [an]{tl}
explanation-correct: [an]{tl} comes before a vowel sound.
:::
`;
async function partStudio() {
  console.log('\n== the studio: the library and a document, on a phone');
  const made = await (await fetch(B + '/studio/api/docs', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: LESSON})})).json();
  const id = made.meta && made.meta.id;
  assert(!!id, 'a document to read: ' + JSON.stringify(id));
  const page = await newPage(PHONE, 'studio');
  await page.goto(B + '/studio/');
  await setMode(page, 'mobile');
  await page.reload();
  await page.waitForSelector('.m-topbar');
  eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'),
                                getComputedStyle(document.querySelector('header.topbar')).display,
                                document.querySelector('.m-topbar').offsetParent !== null,
                                !!document.querySelector('.m-topbar [data-parseh-mode]')]),
     ['mobile', 'none', true, true],
     'the library: the mobile bar is drawn, the browser one is display:none, and the switch is in it');
  for (const no of ['.topbar-actions', '#btn-stop', '#download-shown', '#btn-restore', '#btn-paste-answer'])
    assert(!(await isDrawn(page, no)), 'the library: no ' + no);
  await page.waitForFunction(() => document.querySelectorAll('#cards .card').length > 0, null, {timeout: 20000});
  eq(await page.evaluate(() => {
    const c = document.querySelector('#cards .card'), del = c.querySelector('.card-del');
    return [c.getBoundingClientRect().height >= 88, !del || getComputedStyle(del).display === 'none'];
  }), [true, true], 'its cards are a finger\'s size, and nothing on them deletes a document');
  allFit(await targets(page, '.m-topbar a[href], .m-topbar button'), 'its bar: 48px, on the screen');
  assert(await sideways(page) <= 0, 'and it does not scroll sideways');

  // ---- the document
  await page.goto(B + '/studio/doc/' + id);
  await page.waitForSelector('article.sheet');
  await settle(page);
  await shot(page, 'studio-doc-phone');
  eq(await page.evaluate(() => [document.querySelector('.m-topbar').offsetParent !== null,
                                getComputedStyle(document.querySelector('header.topbar')).display]),
     [true, 'none'], 'a document: the mobile bar, and the browser header gone');
  for (const no of ['.topbar-actions', '.metabar', '#btn-build', '#btn-pdf-toggle', '#btn-add-all',
                    '#btn-stop', '.ex-to-deck'])
    assert(!(await isDrawn(page, no)), 'the document: no ' + no);
  assert(/phone lesson/i.test(await page.textContent('article.sheet')), 'its text is there to read');
  assert(await isDrawn(page, '#btn-toc') && await isDrawn(page, '#btn-typo'),
         'and what reads it stays: the contents, and the size of the text');
  // the exercise inside it is answered with a finger
  const ex = await page.evaluate(async () => {
    const opt = [...document.querySelectorAll('article.sheet .ex-option')]
      .find(o => /^\s*an\s*$/.test(o.textContent));
    if (!opt) return 'no option';
    const tall = opt.getBoundingClientRect().height;
    opt.click();
    await new Promise(r => setTimeout(r, 400));
    return [tall >= 48, opt.classList.contains('selected')];
  });
  eq(ex, [true, true], 'its exercise is a finger\'s size and answers a tap (answering writes nothing)');
  await page.context().close();
}

// ======== a document's HTML page, from a device the worker controls (TO-DO §2.28)
// The owner, from another device: Download ▾ → HTML page landed on "Parseh
// cannot be reached", and Try again did the same.  The worker controls the
// whole address once the mobile mode has registered it, the browser mode
// included; a navigation it had no copy of was raced against DEADLINE and
// fell to /m/offline/, while the computer was still making the page.  Driven
// here with the computer really slow (tests/mobile_harness.py: the page made
// <tmp>/export-delay seconds late): pressed, and as a plain link.
// A DOCUMENT WHOSE DRAWINGS ARE NOT MADE YET, opened from a phone the worker
// controls, with the computer two seconds on every drawing (the owner,
// 2026-09-28: such a page took as long to open as its drawings took to make,
// and the phone gave up on it -- "Parseh cannot be reached").  It opens at
// once, each drawing its source until it is made, a bar counting them; they
// come into the page one by one, and a second opening waits for nothing.
async function partDrawings() {
  console.log('\n== a document with LaTeX drawings not made yet, from a phone the worker controls');
  const stamp = String(Date.now() % 100000);
  const blocks = [1, 2, 3, 4].map(n => `::::latex\n$\\displaystyle\\sum_{k=1}^{${n}${stamp}} k$\n::::`).join('\n\n');
  const markdown = `---\ntitle: Drawn late\nlang: en\ntarget: it\n---\n\nTwo in a line: [$a_{${stamp}}$]{latex} and [$b_{${stamp}}$]{latex}.\n\n${blocks}\n`;
  const made = await (await fetch(B + '/studio/api/docs', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({markdown})})).json();
  const id = made.meta && made.meta.id;
  assert(!!id, 'a document with six drawings: ' + JSON.stringify(made.meta ? id : made));
  const page = await newPage(PHONE, 'drawings');
  const DELAY = WORK + '/latex-delay';
  try {
    // the worker takes the page over on another document first, one with no drawing
    const plain = await (await fetch(B + '/studio/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: '---\ntitle: Plain\nlang: en\ntarget: it\n---\n\nNothing drawn.\n'})})).json();
    await page.goto(B + '/studio/doc/' + plain.meta.id);
    await setMode(page, 'mobile');
    await page.reload();
    for (let i = 0; i < 3 && !(await page.evaluate(() => !!navigator.serviceWorker.controller)); i++) {
      await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
      await page.reload();
    }
    eq(await page.evaluate(() => !!navigator.serviceWorker.controller), true, 'the worker controls the page');
    await Deno.writeTextFile(DELAY, '2');
    const t0 = Date.now();
    await page.goto(B + '/studio/doc/' + id);
    await page.waitForSelector('#sheet [data-latex-pending]', {state: 'attached', timeout: 10000});
    const opened = Date.now() - t0;
    const first = await page.evaluate(() => ({title: document.title, pending: document.querySelectorAll('#sheet [data-latex-pending]').length,
      say: (document.querySelector('.latex-waiting-say') || {}).textContent || ''}));
    assert(opened < 2500 && !/cannot be reached/i.test(first.title) && first.pending === 6,
           `the page opens at once (${opened} ms), its six drawings still to make: ${JSON.stringify(first)}`);
    assert(/^Making the LaTeX drawings: \d of 6$/.test(first.say), 'a bar says how many are made: ' + first.say);
    await shot(page, 'drawings-phone-waiting');
    await page.waitForFunction(() => !document.querySelector('#sheet [data-latex-pending]'), null, {timeout: 90000});
    const drawn = await page.evaluate(() => ({
      blocks: [...document.querySelectorAll('#sheet figure.latex img')].filter(i => i.complete && i.naturalWidth > 0).length,
      marks: [...document.querySelectorAll('#sheet img.latex-inline')].length,
      say: document.querySelector('.latex-waiting-say').textContent, url: location.href, title: document.title}));
    eq([drawn.blocks, drawn.marks, drawn.say], [4, 2, 'The 6 LaTeX drawings are made.'],
       'they come into the page as they are made, and the bar says so');
    assert(drawn.url.endsWith('/studio/doc/' + id) && !/cannot be reached/i.test(drawn.title), 'and the page never left the document');
    await shot(page, 'drawings-phone-made');
    const t1 = Date.now();
    await page.reload();
    await page.waitForSelector('#sheet figure.latex img');
    eq([await page.locator('#sheet [data-latex-pending]').count(), await page.locator('.latex-waiting').count()], [0, 0],
       `opened again (${Date.now() - t1} ms), every drawing is there and nothing waits`);
  } finally {
    await Deno.remove(DELAY).catch(() => {});
    await page.close();
  }
}

async function partExport() {
  console.log('\n== a document\'s HTML page, from a phone the worker controls, with the computer slow -- and the way back from a page that does not arrive');
  // a name of its own: the studio's part has made "A phone lesson" already
  const markdown = LESSON.replace(/A phone lesson/g, 'A page for students');
  const made = await (await fetch(B + '/studio/api/docs', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({markdown})})).json();
  const id = made.meta && made.meta.id;
  assert(!!id, 'a document to export: ' + JSON.stringify(made.meta ? id : made));
  const page = await newPage(PHONE, 'export');
  const DELAY = WORK + '/export-delay';
  // the computer suspended (SIGSTOP: a device away from it meets silence, not refusal), and let go again
  const freeze = () => Deno.kill(hub.pid, 'SIGSTOP');
  const thaw = () => { try { Deno.kill(hub.pid, 'SIGCONT'); } catch (_) { /* gone */ } };
  // one more document, under a name of its own
  const makeOne = async title => {
    const m = await (await fetch(B + '/studio/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: LESSON.replace(/A phone lesson/g, title)})})).json();
    assert(!!(m.meta && m.meta.id), 'a document to open: ' + title);
    return m.meta.id;
  };
  try {
    await page.goto(B + '/studio/doc/' + id);
    await setMode(page, 'mobile');
    await page.reload();
    for (let i = 0; i < 3 && !(await page.evaluate(() => !!navigator.serviceWorker.controller)); i++) {
      await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
      await page.reload();
    }
    eq(await page.evaluate(() => !!navigator.serviceWorker.controller), true, 'the worker controls the document');
    await gearMode(page, 'browser');
    await page.waitForFunction(() => document.documentElement.dataset.mode === 'browser');
    await page.waitForSelector('header.topbar #dl-html', {state: 'attached'});
    eq(await page.evaluate(() => !!navigator.serviceWorker.controller), true,
       'Browser, pressed: the browser header with Download ▾, and the worker still controls the page');
    const at = page.url();
    const moves = [];
    page.on('framenavigated', f => { if (f === page.mainFrame()) moves.push(f.url()); });
    // what the computer made for that very ask (no two exports are the same bytes)
    const direct = async () => new Uint8Array(await Deno.readFile(WORK + '/export-made'));
    const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
    const stillHere = async what => {
      const now = await page.evaluate(() => [location.href, document.title,
        !!document.querySelector('article.sheet') && /page for students/i.test(document.querySelector('article.sheet').textContent)]);
      eq([now[0], /cannot be reached|not reachable/i.test(now[1]), now[2]], [at, false, true], what);
    };

    // a) pressed, with the computer 35 s making the page: longer than the
    // worker's patience with anything it has no copy of (lib/sw.js, PATIENT)
    await Deno.writeTextFile(DELAY, '35');
    const t0 = Date.now();
    await tap(page, 'details.dropdown > summary:text-is("Download ▾")');
    const refused = page.waitForSelector('.made-work.err', {timeout: 120000})
      .then(async e => { throw Error('FAIL: the page gave up: ' + await e.textContent()); }, () => {});
    const [dl] = await Promise.all([
      Promise.race([page.waitForEvent('download', {timeout: 120000}), refused]),
      (async () => {
        await tap(page, '#dl-html');
        await page.waitForSelector('header.topbar .made-work .bar.loose', {state: 'visible', timeout: 5000});
        eq(await page.locator('header.topbar .made-work .made-say').textContent(), 'Making the HTML page of “A page for students”…',
           'the press shows the bar at once, under the header, saying what it is making');
        await shot(page, 'export-phone-working');
        await sleep(8000);
        assert(await page.locator('header.topbar .made-work .bar.loose').isVisible(),
               'eight seconds on -- past the worker\'s DEADLINE -- the bar is still there');
        await stillHere('and the page is still the document');
      })()]);
    const took = Date.now() - t0;
    const file = new Uint8Array(await Deno.readFile(await dl.path()));
    await Deno.remove(DELAY);
    assert(took >= 35000, `the page arrived when the computer had made it (${took} ms), as a download`);
    assert(same(file, await direct()), `its bytes are the ones the computer made (${file.length} bytes)`);
    await page.waitForFunction(() => !document.querySelector('.made-work'), null, {timeout: 5000});
    await stillHere('the bar is gone, and the page never left the document');

    // b) the plain link, as a browser that runs no script follows it
    await Deno.writeTextFile(DELAY, '20');
    const t1 = Date.now();
    const href = await page.getAttribute('#dl-html', 'href');
    let over = false;
    const landed = (async () => {
      while (!over) {
        await sleep(250);
        const t = await page.title().catch(() => '');
        if (/cannot be reached|not reachable/i.test(t)) throw Error(`FAIL: the link, followed, landed on “${t}”`);
      }
    })();
    const [dl2] = await Promise.all([Promise.race([page.waitForEvent('download', {timeout: 90000}), landed]),
                                     page.evaluate(h => { location.href = h; }, href)]);
    over = true;
    await sleep(500);
    await Deno.remove(DELAY);
    const took2 = Date.now() - t1;
    assert(took2 >= 20000, `the link, followed, waited for the computer (${took2} ms) and gave a download`);
    assert(same(new Uint8Array(await Deno.readFile(await dl2.path())), await direct()),
           'and it is the page the computer made');
    await stillHere('and never "Parseh cannot be reached": the document is still on the screen');
    eq(moves, [], 'the page never navigated away');

    // c) A PAGE A COMPUTER IS SLOW TO MAKE, and the way back from one that does
    // not arrive (TO-DO §2.28: "the try again button which doesn't do
    // anything").  A document nobody has kept, followed from this page while
    // the computer is ALIVE and answers only after 8 s -- slower than the
    // worker's deadline (lib/sw.js, DEADLINE) -- OPENS: at the deadline the
    // worker asks the page whether the computer answers, it does, and the
    // worker goes on waiting for the ask it made (the owner's decision of
    // 2026-09-28; tests/reach.mjs, partNav, drives every other end of it).
    // It used to end on the offline page.  The offline page, and the way back
    // from it, is reached here by a computer that answers nothing at all
    // (suspended: a device away from it meets silence, not refusal) -- which is what still
    // ends there, after the deadline and one question.
    const slowdoc = await makeOne('Eight seconds slow');
    const other = await makeOne('Never opened before');
    const third = await makeOne('Not opened either');
    const SLOW = WORK + '/page-delay';
    const offlineNow = () => page.evaluate(() => [document.querySelector('h1') && document.querySelector('h1').textContent,
                                                  location.pathname]);
    await Deno.writeTextFile(SLOW, '8');
    const t2 = Date.now();
    await page.goto(B + '/studio/doc/' + slowdoc);
    const slowly = Date.now() - t2;
    assert(slowly >= 7900 && /eight seconds slow/i.test(await page.title()) && (await offlineNow())[0] !== 'Parseh cannot be reached',
           `a page never kept, from a computer alive and 8 s slow, is opened by the worker after ${slowly} ms, not the offline page`);
    await Deno.remove(SLOW);
    freeze();
    const t3 = Date.now();
    await page.goto(B + '/studio/doc/' + other);
    eq((await offlineNow())[0], 'Parseh cannot be reached',
       `a page never kept, from a computer that answers nothing, is the offline page (after ${Date.now() - t3} ms)`);
    // GO BACK is its own button, there because there is a page to go back to
    assert(await page.locator('#back').isVisible(), 'the page came from another one: Go back is on offer');
    eq(await page.locator('#back').textContent(), 'Go back', 'and it says what it is');
    eq(await page.locator('#tried').isVisible(), false, 'nothing is said of a try before one is made');
    // TRY AGAIN SAYS THAT IT TRIED: at once, and then what it found
    await shot(page, 'export-phone-offline');
    // A page whose reload is pending cannot be asked anything from outside
    // (page.evaluate waits for the page that comes back), so this one keeps a
    // DIARY of what it shows, every 100 ms, in the tab's own memory -- which
    // the page that comes back can read
    await page.evaluate(() => {
      sessionStorage.setItem('__trace', '[]');
      setInterval(() => {
        const a = document.getElementById('again'), t = document.getElementById('tried');
        const all = JSON.parse(sessionStorage.getItem('__trace') || '[]');
        all.push([a ? a.textContent : null, a ? a.disabled : null, t && !t.hidden ? t.textContent : '']);
        sessionStorage.setItem('__trace', JSON.stringify(all.slice(-100)));
      }, 100);
    });
    await sleep(450);
    await page.locator('#again').tap({noWaitAfter: true});
    await page.waitForFunction(() => /^Still cannot reach it\. Tried again at /.test((document.getElementById('tried') || {}).textContent || ''),
                               null, {timeout: 15000});
    const trace = await page.evaluate(() => { const t = JSON.parse(sessionStorage.getItem('__trace') || '[]'); sessionStorage.removeItem('__trace'); return t; });
    const trying = trace.filter(x => x[0] === 'Trying…');
    assert(trying.length >= 10 && trying.every(x => x[1] === true && x[2] === 'Asking the computer…'),
           `Try again, pressed, says at once that it is trying, and keeps saying it while it waits (${trying.length} looks of ${trace.length})`);
    eq(trace[0], ['Try again', false, ''], 'and before the press it was an ordinary button with nothing said');
    const said1 = await page.locator('#tried').textContent();
    assert(/^Still cannot reach it\. Tried again at \S.*\.$/.test(said1), 'and when it fails again, says when it tried: ' + said1);
    eq([await page.locator('#again').textContent(), await page.locator('#again').isEnabled(), (await offlineNow())[1]],
       ['Try again', true, '/studio/doc/' + other], 'the button is ready for another try, on the same address');
    await shot(page, 'export-phone-tried');
    // AND IT IS A TRY THAT CAN SUCCEED: the computer is back, the same
    // button is pressed, and the page the person wanted is what comes
    thaw();
    await tap(page, '#again');
    await page.waitForFunction(() => !document.getElementById('again'), null, {timeout: 15000});
    eq(await page.evaluate(() => [location.pathname, /never opened before/i.test(document.title)]),
       ['/studio/doc/' + other, true], 'Try again, with the computer back, opens the page');
    // A TRY THAT WORKED DOES NOT SPEAK FOR A LATER FAILURE: it left its note
    // behind, and a new visit to the same address a moment later is not the
    // answer to any press
    await page.goto(B + '/studio/doc/' + third);
    freeze();
    await page.goto(B + '/studio/doc/' + other);
    eq((await offlineNow())[0], 'Parseh cannot be reached', 'the same page again, the computer silent again: the offline page');
    eq(await page.locator('#tried').isVisible(), false,
       'and it does not say that anybody tried: the page was opened, not tried again');
    // GO BACK: from a page that fails, to the one the person was on
    thaw();
    await tap(page, '#back');
    await page.waitForFunction(p => location.pathname === p && !!document.querySelector('article.sheet'),
                               '/studio/doc/' + third, {timeout: 15000});
    eq(await page.evaluate(() => /not opened either/i.test(document.title)), true,
       'Go back returns to the page the person was on, and it opens');
  } finally {
    thaw();
    await Deno.remove(DELAY).catch(() => {});
    await Deno.remove(WORK + '/page-delay').catch(() => {});
    await page.context().close();
  }
}



// ======== a deck taken out, studied away, and given back (§19.9, §19.10) ====
// The owner chose CHECK-OUT for studying offline: the phone takes the deck,
// the computer may only cram it until it comes back, and every answer made
// away is replayed on the computer through its own scheduler.  Driven with
// the computer really stopped, since a browser's offline switch does not
// reach a worker's own fetches.
//
// AND A SECOND DECK THAT IS ONLY KEPT, never taken out (the owner's 8,
// 2026-09-23), because the two are different promises: a kept deck must CRAM
// away from the computer -- which it could not, the cram page asking for its
// exercises with a POST that no cache may hold -- and must say at once that
// STUDYING it needs the computer, rather than sitting on "Loading exercises…"
// until somebody closes it.
async function partCheckout() {
  console.log('\n== a deck taken out on a phone, studied with the computer away');
  const EN = MADE.decks.en;
  const deckApi = `${B}/exercises/api/decks/${EN.folder}/${EN.slug}`;
  const deckPage = `${B}/exercises/deck/${EN.folder}/${EN.slug}/`;
  const all = (await (await fetch(deckApi)).json()).items.map(it => it.id);
  await fetch(deckApi + '/items/bulk', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'set-new', ids: all})}).then(r => r.body?.cancel());

  // ---- a) what a deck is made of (§19.9)
  const made = await (await fetch(deckApi + '/__offline')).json();
  eq([made.ok, made.kind, made.small.length >= 4], [true, 'deck', true],
     'the computer says what the deck is made of: its pages, its exercises and the studio\'s own files');
  assert(made.small.some(x => /static\/decks\.js$/.test(x.url)),
         'including the scripts its pages load, or the page would open offline with none');

  // ---- b) the phone takes it out
  const page = await newPage({...PHONE, userAgent: ANDROID}, 'checkout');
  await watchWay(page);
  await page.goto(deckPage);
  await setMode(page, 'mobile');
  await page.reload();
  if (!(await page.evaluate(() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)))) {
    await page.waitForFunction(() => navigator.serviceWorker.ready, null, {timeout: 20000}).catch(() => {});
    await page.reload();
    await page.waitForFunction(() => navigator.serviceWorker.controller, null, {timeout: 20000});
  }
  await page.waitForSelector('#btn-takeout:not([hidden])', {timeout: 20000});
  await tap(page, '#btn-takeout');
  // taking it out KEEPS it first (the owner's 8), and the page then re-reads
  // the deck: a door answered from the copy taken a second earlier would show
  // a deck that is not out (lib/sw.js, `isDoor`)
  await page.waitForSelector('#btn-giveback:not([hidden])', {timeout: 90000});
  const rec = await (await fetch(deckApi)).json();
  eq([rec.checkout.out, /Android phone/.test(rec.checkout.device)], [true, true],
     'taken out: the computer knows which device has it (' + rec.checkout.device + ')');
  // KEEPING AND TAKING OUT ARE TWO THINGS (the owner's 8, 2026-09-23), and
  // taking out asks for the copy first: there is no studying away without it
  const isKept = () => page.evaluate(() => {
    try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; }
    catch (e) { return false; }
  });
  eq(await isKept(), true, 'and it kept the deck on this phone as part of the same press');
  await keptWay(page, 'taking a deck out', 'worker');

  // ---- b2) A SECOND DECK, KEPT AND NOT TAKEN OUT (the owner's 8,
  // 2026-09-23: "offline exercises get stuck to 'loading exercises…' and
  // never load the exercise, which should be instant instead since they
  // should have been kept").  Keeping is not taking out, and he never asked
  // for the two to be one thing: a deck he has only KEPT must cram away from
  // the computer -- that is what he said keeping a deck was for -- and must
  // say plainly that STUDYING it needs the computer.  Both are driven below,
  // with the hub really stopped.
  const FA = MADE.decks.fa;
  const faPage = `${B}/exercises/deck/${FA.folder}/${FA.slug}/`;
  const faApi = `/exercises/api/decks/${FA.folder}/${FA.slug}`;
  const faIds = ((await (await fetch(B + faApi)).json()).items || []).map(it => it.id);
  const faRec = await (await fetch(B + faApi + '/__offline')).json();
  assert((faRec.small || []).some(x => x.url === faApi + '/cram'),
         'a deck is made of its exercises too, at an address a worker can keep — a GET, ' +
         'because the standard lets no cache hold a POST: ' + JSON.stringify(
           (faRec.small || []).map(x => x.url).filter(u => /\/cram$/.test(u))));
  eq((faRec.media || []).length, 0,
     'and there is nothing left for him to pick: the exercises, with their pictures and ' +
     'their recordings, travel with the deck under its one tick');
  await page.goto(faPage);
  await page.waitForSelector('.kp-keep', {timeout: 30000});
  eq(await page.textContent('.kp-keep'), 'Keep on this phone', 'the second deck is not kept yet');
  await tap(page, '.kp-keep');
  await page.waitForSelector('.kp-sheet');
  await page.locator('.kp-go').click();
  await page.waitForFunction(() => {
    try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; }
    catch (e) { return false; }
  }, null, {timeout: 120000});
  eq([await page.textContent('.kp-keep'),
      await page.evaluate(() => !document.querySelector('#btn-takeout').hidden)],
     ['Change what is kept', true],
     'it is kept, and Take it out is still there to press: keeping a deck is not taking it out');
  await keptWay(page, 'a deck kept from its sheet', 'worker');

  /* ---- b2) A COMPUTER THAT ANSWERS NOTHING, which is the only kind a phone
     ever meets (the owner's 2 of 2026-09-23).  Every other offline test in
     this file STOPS the server, and a stopped server REFUSES the socket at
     once -- that is what his computer sees, and it is not what his phone
     sees.  A phone whose tunnel has gone is answered with silence: the
     connection is made and nothing ever comes back.  A SUSPENDED server is
     exactly that, and it is the difference that hid this fault for so long:
     cramming asks the computer with a POST first, lib/sw.js answers GETs
     only (`r.method !== 'GET'`), and nothing else in the stack held a
     deadline -- so on the desk the refusal was instant and the page fell to
     its copy, while on his phone and his iPad the same page sat on "Loading
     exercises…" for ever.  Both halves of the mend are driven here: the page
     believes what the page before it found (lib/keep.js writes the memory
     with its own terms in it now, so a plain script that runs before the
     deferred keep.js can still read it), and an ask that has a copy to fall
     back on is not waited out. */
  Deno.kill(hub.pid, 'SIGSTOP');
  try {
    await page.evaluate(([key, ids]) => {
      try { sessionStorage.setItem(key, JSON.stringify(ids)); } catch (e) { /* said below */ }
    }, [`parseh-cram:${FA.folder}/${FA.slug}`, faIds.slice(0, 2)]);
    const began = Date.now();
    await page.goto(faPage + 'cram', {timeout: 60000});
    let drew = true;
    await page.waitForFunction(() => {
      const s = (document.querySelector('#cram-stage') || {}).textContent || '';
      const c = document.querySelector('#cram-cannot');
      return (c && !c.hidden) || (s.trim() && !/Loading exercises/.test(s));
    }, null, {timeout: 30000}).catch(() => { drew = false; });
    const took = Date.now() - began;
    const stage = ((await page.locator('#cram-stage').textContent().catch(() => '')) || '')
      .replace(/\s+/g, ' ').trim();
    assert(drew && !/Loading exercises/.test(stage) && took < 15000,
           'a computer that answers nothing is not waited out: a kept deck crams anyway, in ' +
           `${took}ms — ${JSON.stringify(stage.slice(0, 50))}`);
  } finally {
    Deno.kill(hub.pid, 'SIGCONT');
  }

  await page.goto(deckPage);
  await page.waitForSelector('#btn-giveback:not([hidden])', {timeout: 30000});

  // ---- c) while it is out: cram here, nothing else
  const studyTry = await fetch(deckApi + '/review', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({item: all[0], rating: 'good'})});
  const saidStudy = await studyTry.json();
  eq([studyTry.status, saidStudy.conflict || ''], [409, 'checked-out'],
     'the computer refuses to study it, saying where it is');
  const editTry = await fetch(deckApi + '/items', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: ':::exercise flashcard\\ncard-type: vocab\\ntarget: [x]{tl}\\nmeaning: y\\n:::'})});
  await editTry.body?.cancel();
  eq(editTry.status, 409, 'and refuses to edit it');
  const cram = await fetch(deckApi + '/cram', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ids: all.slice(0, 2)})});
  const crammed = await cram.json();
  eq([cram.status, (crammed.cards || []).length > 0], [200, true],
     'but cramming it here is untouched: cram never schedules');

  // ---- d) the computer is stopped, and the phone studies
  hub.kill('SIGTERM');
  await hub.status;
  hubUp = false;
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(B + '/', {cache: 'no-store'}); await r.body?.cancel(); await sleep(250); }
    catch (_) { break; }
  }
  await page.goto(deckPage + 'study');
  await page.waitForFunction(() => !document.querySelector('#btn-show').hidden ||
                                   !document.querySelector('#btn-check').hidden, null, {timeout: 30000});
  assert((await page.locator('#study-stage').textContent()).trim().length > 0,
         'with the computer stopped, studying opens from the pack the phone was handed');
  for (let i = 0; i < 2; i++) {
    const primary = await page.evaluate(() => !document.querySelector('#btn-show').hidden ? '#btn-show'
                                            : !document.querySelector('#btn-check').hidden ? '#btn-check' : null);
    if (!primary) break;
    await tap(page, primary);
    await page.waitForSelector('#rating-bar:not([hidden])', {timeout: 10000});
    await tap(page, '#rating-bar [data-rating=good]');
    await sleep(500);
  }
  const queued = await page.evaluate(() => {
    const k = Object.keys(localStorage).find(x => x.startsWith('parseh_deck_answers:'));
    return k ? JSON.parse(localStorage.getItem(k)).length : 0;
  });
  assert(queued >= 2, `what was answered away is kept on the phone (${queued}) until the computer is there`);

  // ---- d2) AND THE DECK THAT WAS ONLY KEPT CRAMS (the owner's 8).  Its
  // exercises come from the copy of the GET door that was kept with it.  The
  // page's own first ask is a POST carrying the picked ids, and a service
  // worker may not cache a POST at all -- whatever had been kept, that ask
  // could never be answered here, which is why "Loading exercises…" was all
  // this page ever said on a train.
  //
  // Reached as the deck page reaches it: the picks in sessionStorage and the
  // BARE address, which is the one the record names and the one the phone
  // holds (a cram page is not a different page for a different selection).
  await page.evaluate(([key, ids]) => {
    try { sessionStorage.setItem(key, JSON.stringify(ids)); } catch (e) { /* said below */ }
  }, [`parseh-cram:${FA.folder}/${FA.slug}`, faIds]);
  await page.goto(faPage + 'cram', {timeout: 30000});
  await page.waitForFunction(() => /of 2/.test((document.querySelector('#cram-progress') || {})
                                               .textContent || ''), null, {timeout: 30000});
  eq(await page.locator('#cram-progress').textContent(), '1 of 2',
     'with the computer stopped, a deck that was kept CRAMS: its exercises are on this phone');
  const oneCard = (await page.locator('#cram-stage').textContent()).replace(/\s+/g, ' ').trim();
  assert(oneCard.length > 0 && !/Loading/.test(oneCard),
         'the exercise itself is drawn, not a spinner: ' + JSON.stringify(oneCard.slice(0, 60)));
  assert(!(await isDrawn(page, '#cram-cannot')), 'and nothing says it cannot be shown');
  // answered, and the next one comes: a practice, not one card in a frame
  await page.waitForSelector('#cram-show:not([hidden])', {timeout: 20000});
  await tap(page, '#cram-show');
  await page.waitForSelector('#cram-correct:not([hidden])', {timeout: 20000});
  await tap(page, '#cram-correct');
  await page.waitForFunction(() => /^2 of 2/.test((document.querySelector('#cram-progress') || {})
                                                  .textContent || ''), null, {timeout: 20000});
  const twoCard = (await page.locator('#cram-stage').textContent()).replace(/\s+/g, ' ').trim();
  assert(twoCard.length > 0 && twoCard !== oneCard,
         'answered, and the next one comes: ' + JSON.stringify(twoCard.slice(0, 60)));

  // ---- d3) STUDYING IT SAYS SO AT ONCE, AND THE WAY OUT IT OFFERS WORKS
  // (§19.10, his 8).  Parseh keeps one scheduler and it is on the computer,
  // so a deck that was not taken out cannot be studied away from it -- and
  // nothing kept could ever have made it possible.  What the page used to do
  // was find that out the slow way: an ask to a door nobody was going to
  // answer, the worker's whole patience spent on it, and a fetch's complaint
  // about a server at the end.  It knows before it asks now, because the page
  // before it found out (his 5), so this is on the clock as well as read.
  const began = Date.now();
  await page.goto(faPage + 'study', {timeout: 30000});
  await page.waitForSelector('#study-cannot:not([hidden])', {timeout: 20000});
  const waited = Date.now() - began;
  const saidNo = (await page.locator('#study-cannot').textContent()).replace(/\s+/g, ' ').trim();
  assert(/Studying needs the computer/.test(saidNo) && /not out/.test(saidNo),
         'a kept deck that was never taken out says so when Study is pressed: ' +
         JSON.stringify(saidNo.slice(0, 90)));
  assert(/Cram this deck/.test(saidNo), 'with what can be done instead, as a press');
  assert(waited < 15000, 'and says it at once rather than hanging on it (' + waited + 'ms)');
  // AND THE PRESS IS PRESSED, because an offer that opens "Parseh cannot be
  // reached" is worse than no offer: this one goes to <deck>/cram?all=1, a
  // NAVIGATION WITH A QUERY, and what the phone holds is the bare address.
  // Nothing here knows how that is made to work -- the worker matching a kept
  // navigation without its query, or the record naming this address too -- and
  // nothing here should: what the owner does is press the button he is given.
  const offered = await page.locator('#study-cannot a.btn').first().getAttribute('href');
  await Promise.all([page.waitForURL(/\/cram\b/, {timeout: 30000}),
                     tap(page, '#study-cannot a.btn')]);
  await page.waitForFunction(() => /of \d+/.test((document.querySelector('#cram-progress') || {})
                                                 .textContent || '') ||
                                   /cannot be reached/.test(document.title),
                             null, {timeout: 40000});
  const offerWorks = await page.evaluate(() => ({
    offline: /cannot be reached/.test(document.title),
    progress: (document.querySelector('#cram-progress') || {}).textContent || '',
    stage: ((document.querySelector('#cram-stage') || {}).textContent || '')
      .replace(/\s+/g, ' ').trim().slice(0, 60)}));
  assert(!offerWorks.offline && /of 2/.test(offerWorks.progress),
         'Cram this deck, pressed with the computer stopped, really crams (' + offered + '): ' +
         JSON.stringify(offerWorks));

  // ---- e) the computer comes back: the answers go home by themselves
  hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  hubUp = true;
  for (const st of [hub.stdout, hub.stderr])
    (async () => { for await (const c of st.pipeThrough(new TextDecoderStream())) log.push(c); })();
  for (const t = Date.now();;) {
    try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start again');
    await sleep(250);
  }
  await page.goto(deckPage);
  await page.waitForFunction(() => document.querySelectorAll('.dk-row').length > 0, null, {timeout: 30000});
  await sleep(2500);
  const after = await (await fetch(deckApi)).json();
  const scheduled = after.items.filter(it => ((it.schedule || {}).state || 'new') !== 'new').length;
  assert(scheduled >= 2, `the computer has what was answered away: ${scheduled} exercises have left "new"`);
  eq(await page.evaluate(() => {
    const k = Object.keys(localStorage).find(x => x.startsWith('parseh_deck_answers:'));
    return k ? JSON.parse(localStorage.getItem(k)).length : 0;
  }), 0, 'and the phone holds none of them any more');

  // ---- f) given back
  await tap(page, '#btn-giveback');
  await page.waitForSelector('#btn-takeout:not([hidden])', {timeout: 30000});
  eq((await (await fetch(deckApi)).json()).checkout.out, false, 'given back');
  // and the copy stays: coming home from a journey must not cost the whole
  // deck again the next time (the owner's 9).  Remove from this phone is what
  // takes it off, and it says so.
  eq(await isKept(), true, 'the kept copy is left alone: giving it back is not taking it off');
  const again = await fetch(deckApi + '/review', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({item: all[0], rating: 'good'})});
  await again.body?.cancel();
  eq(again.status, 200, 'and the computer studies it again');

  // ---- g) taken back from a phone that will not come home: refused, and listed
  await fetch(deckApi + '/checkout', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({device: 'A lost phone', id: 'dev-lost'})}).then(r => r.body?.cancel());
  await fetch(deckApi + '/takeback', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({})}).then(r => r.body?.cancel());
  const late = await (await fetch(deckApi + '/answers', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: 'dev-lost', answers: [{item: all[0], rating: 'easy',
                                                     at: new Date().toISOString()}]})})).json();
  eq([late.applied, late.refused.length, late.taken_back === true], [0, 1, true],
     'after Take it back that phone\'s answers are refused — and not in silence:');
  const listed = (await (await fetch(deckApi)).json()).checkout.refused;
  assert(listed.length >= 1 && /taken back/.test(listed[0].why || ''),
         'the deck keeps what could not be applied, with why: ' + JSON.stringify((listed[0] || {}).why));
  await fetch(deckApi + '/refused', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({})}).then(r => r.body?.cancel());
  await page.context().close();
}

// ---- notes written into a book's seams, through the book's own doors.
// POST <mount>/api/marks makes a note in the gap the page names and PUT
// <mount>/api/docs/<id> is the editor's own Save (serve.py `_notes`,
// markdown/app/server.py `api_save`) -- the two doors the + in a seam and the
// editor press, so what is kept below is a note somebody could have written.
// The anchors are read off the seams the reader really drew: a note anchored
// at a line the book has not got hangs adrift at the end, and a mark at the
// end of a book would not prove that a mark stands in a seam.
async function writeNotes(page, mount, target, notes) {
  const seams = await page.evaluate(() => [...document.querySelectorAll('.gap')]
    .map(g => g.dataset.after).filter(Boolean));
  if (!seams.length) throw Error('the reader drew no seam a note could go in');
  const ids = [];
  for (let i = 0; i < notes.length; i++) {
    // round the seams again where there are fewer of them than notes: two
    // notes in one seam are two marks in it, which is a thing a book does
    const made = await (await fetch(mount + '/api/marks', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({side: 'after', kind: 'sub', at: seams[i % seams.length],
                            target})})).json();
    const id = (made.note || {}).id;
    if (!id) throw Error('the seam would not take a note: ' + JSON.stringify(made));
    // its own front matter back, with the title changed and the rest left
    // alone: the anchor the door wrote is the note's place in the book, and
    // a save that replaced the front matter would set it adrift
    const got = await (await fetch(mount + '/api/docs/' + id)).json();
    const head = String(got.markdown || '').split('\n---\n')[0]
      .replace(/^title:.*$/m, 'title: ' + notes[i].title);
    const saved = await fetch(mount + '/api/docs/' + id, {method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: head + '\n---\n\n' + notes[i].body + '\n'})});
    if (!saved.ok) throw Error('the note would not save: ' + saved.status + ' ' + await saved.text());
    await saved.body?.cancel();
    ids.push(id);
  }
  return ids;
}
// What the notes say, chosen so that each one proves a different sentence of
// the owner's: a note read on a train, an exercise answered on one, and a
// formula that must bring MathJax with it or show as its own source.
const NOTE_SAID = 'The idiom in this line is the one from chapter two.';
const NOTES_TO_WRITE = [
  {title: 'On the idiom', body: NOTE_SAID},
  {title: 'Drill on the idiom', body: ':::exercise fill-blanks\nprompt: Complete it.\n' +
    'text: The knight rode home through the [[one]].\n- [one] night\n- [ ] day\n:::'},
  {title: 'The counting of it', body: 'The metre comes to [a^2+b^2]{math} feet.'},
];

// ======== kept on this phone, and the computer away (§19) ========
// Keep a narrated book, stop the computer, and READ it: the page, its text,
// its recording -- with a range asked of it, which is what makes ↺ and ↻ work
// on a train -- the chip that says the computer cannot be reached, what has
// no answer offline saying so at once, and the list of what is kept.
//
// AND ITS NOTES, which are the whole of the owner's second block of
// 2026-09-23: a kept book used to keep its text and its recordings and leave
// every note he had written on the computer, so every seam on a train opened
// on nothing.  Two books are kept here for that -- the English one WITH its
// notes ticked and the Persian one with them UNTICKED -- because a tick that
// cannot be taken off is not a tick, and the honest answer where they were
// not kept is as much a promise as the note where they were.
//
// AND FOUR THINGS FROM HIS THIRD BLOCK, all of them found in airplane mode on
// his own phone and none of them findable by reading the source:
//   a4) every address the built reader asks for is in the record.  One was
//       not -- /lib/mt.js, a parser-blocking script in the reader's head --
//       and the page stopped on it and never reached its text: "all books do
//       not open while offline, loading stops at ~half".
//   b0) what a recording's row says (the chapter and the section first, the
//       paragraph addresses under them) and the shape of it (four fifths of
//       the width, against the left, 48px still, and the drag still selects).
//   b1a) a tick that is a lie: the kept recording is damaged in the cache,
//       byte for byte the same size, and the sheet must untick it and say so.
//   b5) the state is carried from page to page and corrected by the probe.
// It runs LAST but one: it stops the server itself and starts it again for
// the app part after it.
async function partOffline() {
  console.log('\n== kept on this phone, with the computer away');
  const READER = B + MADE.readers.en;
  const NOTES = B + MADE.readers.en.replace(/reader\/$/, 'notes');
  const FA_READER = B + MADE.readers.fa;
  const FA_NOTES = B + MADE.readers.fa.replace(/reader\/$/, 'notes');
  // ---- a) what the computer says the book is made of (§19.3)
  const made = await (await fetch(READER + '__offline')).json();
  eq([made.ok, made.kind, made.small.length > 0, !!made.version, made.shared.length > 5],
     [true, 'book', true, true, true],
     'the computer says what the book is made of: its pages, its version, and the shared files');
  assert(made.media.length >= 1 && made.media[0].bytes > 1000,
         'and its recordings, each with its size: ' + JSON.stringify(made.media.map(m => m.bytes)));
  assert((made.small_bytes || 0) > 0 && (made.bytes || 0) >= made.small_bytes,
         'with what it costs, said in two halves');
  eq([made.notes ? 1 : 0, made.bytes === made.small_bytes + made.media_bytes],
     [0, true],
     'a book nobody has written a note beside is exactly what it was: no group, and the sum still adds up');

  // ---- a2) THE WAY IN, as the computer gives it (lib/offline.py, shell()).
  // Without this the app had nothing to open from: its start address was in
  // no cache at all.
  const shellDoor = await fetch(B + '/__shell');
  const shell = shellDoor.ok ? await shellDoor.json() : null;
  eq([shellDoor.status, !!(shell && shell.ok)], [200, true],
     'the computer says what the way in is made of, at /__shell');
  assert(shell && ['/', '/?mode=mobile', '/m/books/', '/m/videos/', '/exercises/', '/studio/']
           .every(p => shell.pages.includes(p)),
         'the hub at both its addresses, the shelves and the two libraries: ' +
         JSON.stringify((shell || {}).pages));
  assert(shell && shell.files.some(u => /\/lib\/parseh\.css$/.test(u)) &&
         shell.files.some(u => /static\/decks\.js$/.test(u)),
         'with the sheets and the scripts those pages load, the studio\'s among them');
  // AND WHAT IS NOT THE WAY IN (TO-DO §0, the third block of 2026-09-23).
  // The three lists above are how a person GETS somewhere; the studio's
  // thirteen faces are what a studio PAGE needs to look like itself, and they
  // were 1.83 of the 3.26 megabytes this door named in one breath -- fetched,
  // all of them, inside the worker's install event, which is why the app
  // would no longer install at all.  They are named apart now and warmed when
  // a page that needs them asks.
  assert(shell && (shell.later || []).length > 0 &&
         shell.later.every(u => /\/static\/fonts\//.test(u)),
         'the studio\'s faces are named apart, to be warmed later: ' +
         JSON.stringify((shell || {}).later || []));
  assert(shell && !shell.files.some(u => /\/static\/fonts\//.test(u)),
         'and not one of them is in the way in, which is what an install now fetches');

  const ctx = await browser.newContext(PHONE);
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push('offline: ' + e.message); console.log('PAGE ERROR offline', e.message); });
  await watchWay(page);
  page.touch = await ctx.newCDPSession(page);
  await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  await page.goto(READER);
  await setMode(page, 'mobile');
  await page.reload();
  await page.waitForFunction(() => !!window.ParsehKeep, null, {timeout: 20000});
  if (!(await page.evaluate(() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)))) {
    await page.waitForFunction(() => navigator.serviceWorker.ready, null, {timeout: 20000}).catch(() => {});
    await page.reload();
    await page.waitForFunction(() => navigator.serviceWorker.controller, null, {timeout: 20000});
  }
  await answerPlace(page);

  // ---- a3) THREE NOTES WRITTEN BESIDE THIS BOOK, and what the door then
  // says about them (the owner's second block of 2026-09-23).  Written now
  // rather than built into the fixture because the question is what happens
  // to a note when the book it sits in is KEPT, and every other part of this
  // suite reads the same book.
  const noteIds = await writeNotes(page, NOTES, 'en', NOTES_TO_WRITE);
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll('.gap .mark').length >= 3,
                             null, {timeout: 30000});
  await answerPlace(page);
  eq(await page.evaluate(() => [...document.querySelectorAll('.gap .mark')]
       .map(b => b.textContent).sort()),
     NOTES_TO_WRITE.map(n => n.title).sort(),
     'three notes written into the book\'s seams, each with its mark in one');
  const withNotes = await (await fetch(READER + '__offline')).json();
  // THE NOTES ARE THEIR OWN HALF OF THE RECORD (lib/offline.py's header):
  // every entry stands for one address, and the grouping into one tick is the
  // sheet's, where the owner sees it (lib/keep.js).
  const group = withNotes.notes || {};
  group.urls = (group.small || []).map(x => x.url);
  eq([withNotes.notes ? 1 : 0, group.kind, group.title, group.count, group.about],
     [1, 'notes', 'its notes', 3, true],
     'the notes are ONE tick of their own, beside the recordings, and what it costs is "about"');
  assert(group.urls && group.urls.includes(NOTES.slice(B.length) + '/api/marks'),
         'the seams\' list travels with them, or nothing on the phone could find a note: ' +
         JSON.stringify(group.urls));
  const plain = NOTES.slice(B.length) + '/note/' + noteIds[0];
  const drill = NOTES.slice(B.length) + '/doc/' + noteIds[1];
  assert(group.urls.includes(plain), 'a note is kept as its bare page: ' + plain);
  assert(group.urls.includes(drill),
         'and one that holds an exercise as the studio\'s whole page, so it can be answered ' +
         'on a train exactly as at the desk: ' + drill);
  // WHAT THE STUDIO LENDS THE PHONE lives inside the notes' own half, where
  // the sheet fetches it only when the row is ticked: in the record's own
  // `shared` it would be four megabytes fetched on a first keep by somebody
  // who asked for the text of a book and was told it cost a few hundred kB.
  const lent = (group.shared || []).map(x => x.url);
  assert(!(withNotes.shared || []).some(u => /\/studio\/static\/fonts\//.test(u.url)),
         'and not in what every page of the app needs, which any first keep fetches');
  assert(lent.includes('/studio/static/sheet.css') &&
         lent.filter(u => /\/studio\/static\/fonts\//.test(u)).length > 1 &&
         lent.some(u => /\/studio\/static\/mathjax\/tex-svg\.js$/.test(u)),
         'what a note opens on -- the studio\'s sheet, its faces, and MathJax where a note ' +
         'has a formula -- is named at the STUDIO\'s own address, once for the phone');
  assert(!lent.some(u => u.startsWith(MADE.readers.en.replace(/reader\/$/, ''))),
         'and none of it under this one book, or ten books would keep ten copies: ' +
         JSON.stringify(lent.filter(u => !u.startsWith('/lib/'))));
  eq(withNotes.bytes === withNotes.small_bytes + withNotes.groups_bytes + withNotes.media_bytes,
     true, 'what the book costs is said in three parts now, and they add up');
  // THE NOTES CARRY A VERSION OF THEIR OWN, beside the thing's: folded into
  // one, a note written at the desk would tell somebody who kept this book
  // WITHOUT its notes that what he has is out of date, and the press he was
  // offered would fetch him nothing (lib/keep.js, look()).
  assert(group.version && group.version !== withNotes.version,
         'the notes have a version of their own: ' + group.version);

  // ---- a4) EVERY ADDRESS THE BUILT READER ASKS FOR IS IN THE RECORD (the
  // owner's 7, 2026-09-23: "all books do not open while offline, loading
  // stops at ~half").  One address was missing from every list -- /lib/mt.js,
  // which lib/tex2html.py writes into the reader's head as a PARSER-BLOCKING
  // script -- so with the computer away the parser stopped on it and the page
  // never reached its body: half a reader, in all five of his books.
  //
  // It is asked of the HTML THE PARSER SEES, fetched from the computer as the
  // browser fetches it, because that is the only place the fault could be
  // seen: the DOM of a page that loaded perfectly well with the computer
  // there says nothing about which of its addresses a phone holds.  Only what
  // the reader asks of the toolbox and of its own folder is weighed -- the
  // manifest and its icons are the app's badge, asked for at install and
  // never on a page's way to its text, and the writing doors (__download,
  // __narration) are not drawn on a phone at all.
  const askedFor = await (async () => {
    const html = await (await fetch(READER)).text();
    const out = new Map();
    // the tags the parser itself fetches from, and only those: a <link> that
    // is not a stylesheet is a hint, and an <a href> is somewhere to go
    for (const m of html.matchAll(/<(script|link|img|source|audio|video)\b([^>]*)>/gi)) {
      const tag = m[1].toLowerCase(), rest = m[2];
      if (tag === 'link' && !/stylesheet/i.test(rest)) continue;
      const a = /\b(?:src|href)="([^"]+)"/i.exec(rest);
      if (!a) continue;
      let u;
      try { u = new URL(a[1], READER); } catch (_) { continue; }
      if (u.origin !== B) continue;
      if (!/^\/lib\//.test(u.pathname) && !u.pathname.startsWith(MADE.readers.en.replace(/reader\/$/, '')))
        continue;
      if (!out.has(u.pathname)) out.set(u.pathname, tag);
    }
    return [...out];
  })();
  const inRecord = new Set([...withNotes.small, ...withNotes.shared, ...withNotes.media]
    .map(x => x.url));
  const missing = askedFor.filter(([u]) => !inRecord.has(u));
  assert(askedFor.length >= 8, 'the built reader asks the toolbox for ' + askedFor.length +
         ' addresses of its own: ' + JSON.stringify(askedFor.map(([u]) => u)));
  eq(missing, [], 'and the computer names every one of them — nothing the parser stops on is ' +
     'left out of the record');
  assert(inRecord.has('/lib/mt.js'),
         'the translation helper among them, which is the one that was missing');

  // ---- b) Keep on this phone, with the recording picked (§19.1, §19.2)
  await reveal(page);
  await gearOpen(page, 'interface');
  await page.waitForSelector('.kp-keep');
  // TWO BUTTONS SHARE THE LINE NOW (the owner's 4, 2026-09-23), so `.kp-btn`
  // is the WRAPPER and `.kp-keep` is the button it holds: reading the
  // wrapper's text would read both of them at once, and tapping the wrapper
  // would tap neither.
  eq(await page.textContent('.kp-keep'), 'Keep on this phone', 'the button in the gear\'s last group says what it does');
  assert(!(await isDrawn(page, '.kp-drop')),
         'and with nothing kept there is nothing to remove: the first button has the line');
  await tap(page, '.kp-keep');
  await page.waitForSelector('.kp-sheet');
  const sheet = await page.evaluate(() => ({
    what: document.querySelector('.kp-what').textContent,
    rows: [...document.querySelectorAll('.kp-row')].length,
    sum: document.querySelector('.kp-sum').textContent}));
  assert(/take/.test(sheet.what) && sheet.rows >= 1 && /In all/.test(sheet.sum),
         'the sheet says what the text costs and lists the recordings to pick, one by one');
  // THE NOTES ARE A ROW ON THAT SAME LIST (his first decision): one tick for
  // all three, saying how many and ABOUT how much, and ticked to begin with
  // -- a seam that opens on nothing is the fault the row exists to mend.
  const notesRow = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.kp-row')]
      .find(r => /^its notes/.test((r.querySelector('.kp-name') || {}).textContent || ''));
    if (!row) return null;
    return {name: row.querySelector('.kp-name').textContent,
            size: (row.querySelector('.kp-size') || {}).textContent || '',
            on: row.querySelector('input').checked};
  });
  assert(notesRow && /^its notes · 3$/.test(notesRow.name) && /^about /.test(notesRow.size) &&
         notesRow.on === true,
         'the notes are one row of their own, ticked, saying how many and about how much: ' +
         JSON.stringify(notesRow));

  // ---- b0) WHAT A RECORDING'S ROW SAYS, AND THE SHAPE OF IT (the owner's 2,
  // 2026-09-23).  Two things he asked for in one sentence, and both are
  // measured where they are drawn rather than read out of a stylesheet:
  //   "indicate also chapters and section range that each narration covers in
  //    the rectangles instead of only the range of paragraphs" -- a row said
  //    "n2 · 7.1 – 36.1", which is exact and no use at all to somebody
  //    choosing two of fifty recordings for a train;
  //   "reduce the size of the rectangles by 20% and align them left, so that
  //    part of the page is free to move the thumb and scroll without issues"
  //    -- a row takes the drag away from the browser (touch-action:none, so
  //    that a finger drawn down the boxes ticks them), and with rows the
  //    whole width of the sheet there was nowhere left to put a thumb.
  // It is the WIDTH that shrinks: every row keeps its 48px.
  const narr = await page.evaluate(() => {
    const row = document.querySelector('.kp-row'), list = row.parentElement;
    const r = row.getBoundingClientRect(), L = list.getBoundingClientRect();
    const mid = r.top + r.height / 2;
    const beside = document.elementFromPoint(Math.min(innerWidth - 2, r.right + 8), mid);
    return {top: (row.querySelector('.kp-top') || {}).textContent || '',
            sub: (row.querySelector('.kp-sub') || {}).textContent || '',
            share: r.width / L.width, indent: Math.round(r.left - L.left),
            high: Math.round(r.height), strip: Math.round(L.right - r.right),
            onARow: !!(beside && beside.closest && beside.closest('.kp-row')),
            drags: getComputedStyle(row).touchAction};
  });
  assert(/^chapter\b/.test(narr.top) && !/\d+\.\d+/.test(narr.top),
         'the chapter comes first, in the reader\'s own wording, and the paragraph addresses ' +
         'are no longer what the row leads with: ' + JSON.stringify(narr.top));
  assert(/n1/.test(narr.sub) && /1\.1/.test(narr.sub),
         'and they are still there, under it, for whoever knows the book by them: ' +
         JSON.stringify(narr.sub));
  assert(near(narr.share, 0.8, 0.02) && narr.indent === 0 && narr.strip > 20,
         'the row is four fifths of the list, against its left edge, with a clear strip down ' +
         'the right: ' + JSON.stringify({share: +narr.share.toFixed(3), indent: narr.indent,
                                         strip: narr.strip}));
  assert(narr.high >= 48 && narr.drags === 'none',
         'still 48px high, and still the row that takes the drag: ' + narr.high + 'px, ' +
         narr.drags);
  assert(narr.onARow === false,
         'and what a thumb lands on in that strip is not a row, so the sheet scrolls there');
  // AND THE DRAG STILL SELECTS.  Narrower rows must not be harder to stroke:
  // a finger put down on the first box and drawn to the last takes every row
  // it crosses (lib/keep.js, dragging).  Driven with real pointer events at
  // the rows' own coordinates, because what the code reads is
  // elementFromPoint and not the element the event was aimed at.
  const stroked = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.kp-row')];
    const boxes = rows.map(r => r.querySelector('input'));
    boxes.forEach(b => { b.checked = false; });
    const at = r => { const b = r.getBoundingClientRect(); return [b.left + 30, b.top + b.height / 2]; };
    const fire = (el, name, [x, y]) => el.dispatchEvent(new PointerEvent(name,
      {bubbles: true, cancelable: true, pointerId: 7, pointerType: 'touch', clientX: x, clientY: y}));
    fire(boxes[0], 'pointerdown', at(rows[0]));
    for (const r of rows) fire(rows[0], 'pointermove', at(r));
    fire(rows[0], 'pointerup', at(rows[rows.length - 1]));
    const took = boxes.map(b => b.checked);
    // and the sheet is left as the test below expects to find it: the first
    // recording and the notes, which is what the owner would have ticked
    const want = rows.map((r, i) => i === 0 ||
      /^its notes/.test((r.querySelector('.kp-name') || {}).textContent || ''));
    boxes.forEach((b, i) => {
      if (b.checked === want[i]) return;
      b.checked = want[i];
      b.dispatchEvent(new Event('change', {bubbles: true}));
    });
    return {rows: rows.length, took: took};
  });
  assert(stroked.rows >= 2 && stroked.took.every(Boolean),
         'a finger drawn down the boxes takes every row it crosses: ' +
         JSON.stringify(stroked));
  await page.locator('.kp-row input').first().check();
  await page.locator('.kp-go').click();
  await page.waitForFunction(() => {
    try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; }
    catch (e) { return false; }
  }, null, {timeout: 120000});
  await keptWay(page, 'the first book');
  // KEPT, IT IS TWO BUTTONS (the owner's 4, 2026-09-23): one changes what is
  // kept, one takes it off -- neither of them carrying the other's meaning
  eq([await page.textContent('.kp-keep'), await page.textContent('.kp-drop'),
      await isDrawn(page, '.kp-drop')],
     ['Change what is kept', 'Remove from this phone', true],
     'kept: Change what is kept, and Remove from this phone beside it');
  // AND THEY DIVIDE THAT LINE IN TWO, HALF EACH, which is what he asked for:
  // "they should divide the space that currently is allocated to change what
  // is kept in two, one half for change the other for remove".  Remove used
  // to hang on a line of its own underneath -- directly under the thumb that
  // had just reached for Change -- and a button that throws away three
  // hundred megabytes should not be where the other one was a moment ago.
  const pair = await page.evaluate(() => {
    const row = document.querySelector('.kp-pair');
    const a = row.querySelector('.kp-keep').getBoundingClientRect();
    const b = row.querySelector('.kp-drop').getBoundingClientRect();
    return {line: Math.round(row.getBoundingClientRect().width),
            one: Math.round(a.width), two: Math.round(b.width),
            apart: Math.round(b.left - a.right), sameLine: Math.abs(a.top - b.top) <= 1,
            high: Math.round(Math.min(a.height, b.height))};
  });
  assert(pair.sameLine && near(pair.one, pair.two, 2) &&
         near(pair.one + pair.two + pair.apart, pair.line, 2) && pair.high >= 48,
         'on one line, half each, and each still 48px: ' + JSON.stringify(pair));

  // ---- b1) Change what is kept: the recording is ticked, and unticking it
  // asks once and gives the room back.
  //
  // AND THE BOXES ARE TICKED FROM WHAT IS REALLY ON THE PHONE (the owner's 3,
  // 2026-09-23: "the boxes should by default show the things that are
  // actually kept in memory, and there should be a check of this, it should
  // actually look for the file and check that the download was complete and
  // correct").  So the sheet waits here for the worker's answer rather than
  // reading the boxes the moment they are drawn: what they say before the
  // check has spoken is the old guess, and it is the check this proves.
  const looked = () => page.waitForFunction(() => {
    const c = document.querySelector('.kp-check');
    return !!c && !/Looking at/.test(c.textContent);
  }, null, {timeout: 60000});
  await tap(page, '.kp-keep');
  await page.waitForSelector('.kp-sheet');
  await looked();
  // two of them now: the recording that was picked, and the notes that came
  // with the book
  eq(await page.evaluate(() => [document.querySelector('.kp-h').textContent,
                                [...document.querySelectorAll('.kp-row input')].filter(b => b.checked).length,
                                document.querySelector('.kp-check').textContent,
                                document.querySelectorAll('.kp-row.kp-torn').length]),
     ['Change what is kept', 2,
      'Looked at file by file: what is ticked is whole on this phone.', 0],
     'the list opens again with what is on this phone already ticked — and it looked, ' +
     'file by file, before it said so');
  // Clear all, the second of the two controls: nothing would be fetched and
  // the recording that is here would be given back
  await page.evaluate(() => document.querySelectorAll('.kp-pickall button')[1].click());
  assert(/Save fetches .*, frees /.test(await page.textContent('.kp-sum')),
         'and the line says both numbers: ' + (await page.textContent('.kp-sum')));
  await page.locator('.kp-no').click();

  // ---- b1a) A TICK THAT IS A LIE, FOUND AND MENDED (his 3, driven).  A box
  // used to be ticked because the address was a KEY IN A CACHE, which a 503
  // kept by mistake satisfies, and a page sent where a recording was asked
  // for, and a fetch a tunnel cut in half.  So the copy of the recording on
  // this phone is broken here on purpose -- the SAME NUMBER OF BYTES and not
  // the same bytes, with the computer's own headers kept, so that nothing but
  // the digest can tell it from the real one -- and the sheet is opened
  // again.  It must not be ticked, and it must say why.
  const tornUrl = withNotes.media[0].url;
  const broke = await page.evaluate(async (url) => {
    for (const name of await caches.keys()) {
      const c = await caches.open(name);
      const was = await c.match(url, {ignoreVary: true});
      if (!was) continue;
      const body = new Uint8Array(await was.arrayBuffer());
      const at = Math.floor(body.length / 2), before = body[at];
      body[at] = before ^ 0xff;
      await c.put(url, new Response(body, {status: 200, statusText: 'OK',
                                           headers: new Headers(was.headers)}));
      return {cache: name, bytes: body.length, at: at, was: before,
              said: was.headers.get('content-length')};
    }
    return null;
  }, tornUrl);
  assert(broke && broke.bytes > 1000,
         'the recording kept on this phone is damaged, byte for byte the same size: ' +
         JSON.stringify(broke));
  await tap(page, '.kp-keep');
  await page.waitForSelector('.kp-sheet');
  await looked();
  const torn = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.kp-row')];
    const bad = rows.find(r => r.classList.contains('kp-torn'));
    const line = document.querySelector('.kp-check');
    return {which: rows.indexOf(bad), on: bad ? bad.querySelector('input').checked : null,
            why: bad ? ((bad.querySelector('.kp-whytorn') || {}).textContent || '') : '',
            line: line.textContent, warned: line.classList.contains('kp-bad'),
            others: rows.filter(r => !r.classList.contains('kp-torn') &&
                                     r.querySelector('input').checked).length};
  });
  assert(torn.which === 0 && torn.on === false,
         'the box is NOT ticked for a copy that is not whole: ' + JSON.stringify(torn));
  assert(/no longer whole/.test(torn.why) && torn.warned &&
         /One file kept here is no longer whole/.test(torn.line) && /unticked/.test(torn.line),
         'and the sheet says why, in the row and over the list: ' +
         JSON.stringify({why: torn.why, line: torn.line}));
  eq(torn.others, 1,
     'while what IS whole keeps its tick — the notes are not unticked because a recording ' +
     'came back torn');
  // TICKED AGAIN, SAVE FETCHES IT AGAIN.  Everything in that list is either
  // missing or a broken copy under the address it is meant to mend, so the
  // press asks the worker for it WHOLE (lib/keep.js, change(): renew) rather
  // than passing over "what is already there" and reporting success.
  await page.locator('.kp-row input').first().check();
  await page.locator('.kp-go').click();
  await until(page, async (d) => {
    const r = await caches.match(d.url, {ignoreVary: true});
    if (!r) return false;
    const b = new Uint8Array(await r.arrayBuffer());
    return b.length === d.bytes && b[d.at] === d.was;
  }, {url: tornUrl, bytes: broke.bytes, at: broke.at, was: broke.was}, 120000);
  assert(true, 'ticking it again fetches it again: the bytes on this phone are the computer\'s');
  // the button says "keeping…" while it runs and will not open a sheet then
  await page.waitForFunction(() => {
    const b = document.querySelector('.kp-keep');
    return !!b && !b.disabled;
  }, null, {timeout: 60000});
  await keptWay(page, 'Save, bringing a torn recording again');
  await tap(page, '.kp-keep');
  await page.waitForSelector('.kp-sheet');
  await looked();
  eq(await page.evaluate(() => [document.querySelector('.kp-check').textContent,
                                document.querySelectorAll('.kp-row.kp-torn').length,
                                [...document.querySelectorAll('.kp-row input')].filter(b => b.checked).length]),
     ['Looked at file by file: what is ticked is whole on this phone.', 0, 2],
     'and looking again finds it whole');
  await page.locator('.kp-no').click();

  // ---- b1b) A SECOND BOOK KEPT WITH ITS NOTES UNTICKED.  The tick is only a
  // tick if it can be taken off, and what a phone does with a note it was
  // never given is as much a promise as what it does with one it has: the
  // Persian book goes onto the phone without its note, and below, with the
  // computer stopped, it must say so rather than show an empty frame.
  await page.goto(FA_READER);
  await page.waitForFunction(() => !!window.ParsehKeep, null, {timeout: 20000});
  await answerPlace(page);
  const faNote = (await writeNotes(page, FA_NOTES, 'fa',
                                   [{title: 'On this line', body: NOTE_SAID}]))[0];
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll('.gap .mark').length >= 1,
                             null, {timeout: 30000});
  await answerPlace(page);
  await reveal(page);
  await gearOpen(page, 'interface');
  await page.waitForSelector('.kp-btn');
  await tap(page, '.kp-btn');
  await page.waitForSelector('.kp-sheet');
  const unticked = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.kp-row')]
      .find(r => /^its notes/.test((r.querySelector('.kp-name') || {}).textContent || ''));
    if (!row) return null;
    row.querySelector('input').click();
    return {on: row.querySelector('input').checked,
            sum: (document.querySelector('.kp-sum') || {}).textContent || ''};
  });
  assert(unticked && unticked.on === false,
         'the notes row can be unticked, and the sum says what is left: ' + JSON.stringify(unticked));
  await page.locator('.kp-go').click();
  await page.waitForFunction(() => {
    try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; }
    catch (e) { return false; }
  }, null, {timeout: 120000});
  // the slot holds BOTH buttons now, half each (the owner's 4 of the fourth
  // block): what says it is kept is the pair, not one caption
  eq(await page.textContent('.kp-keep'), 'Change what is kept',
     'the second book is kept, without its notes');
  await keptWay(page, 'the second book');
  eq(await page.textContent('.kp-drop'), 'Remove from this phone',
     'and the way to remove it stands beside it');
  await page.goto(READER);
  await answerPlace(page);

  // ---- b2) a video and a document can be kept too (§19.7, §19.8)
  const vid = await (await fetch(`${B}/youtube/v/${MADE.video}/__offline`)).json();
  eq([vid.ok, vid.kind, vid.small.length > 0], [true, 'video', true],
     'a video says what it is made of: its page, its transcript and its glosses');
  assert((vid.media || []).some(m => /\.(mp4|webm|mkv|mov)$/i.test(m.url)),
         'with the film on this machine among the heavy things to pick');
  // AND ITS NOTES, the same row under its own mount: the owner asked for
  // books and videos together, and the two readers' note code is a mirror.
  const vNotes = `${B}/youtube/v/${MADE.video}/notes`;
  const vMade = await (await fetch(vNotes + '/api/marks', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({side: 'before', kind: 'cap', at: '0', target: 'fa'})})).json();
  assert((vMade.note || {}).id, 'a note written into a caption\'s seam: ' + JSON.stringify(vMade));
  const vid2 = await (await fetch(`${B}/youtube/v/${MADE.video}/__offline`)).json();
  const vGroup = vid2.notes || {};
  vGroup.urls = (vGroup.small || []).map(x => x.url);
  eq([vid2.notes ? 1 : 0, vGroup.kind, vGroup.url, vGroup.count],
     [1, 'notes', `/youtube/v/${MADE.video}/notes`, 1],
     'a video\'s notes are the same one tick, under the video\'s own mount');
  assert((vGroup.urls || []).includes(`/youtube/v/${MADE.video}/notes/api/marks`) &&
         (vGroup.urls || []).includes(`/youtube/v/${MADE.video}/notes/note/${vMade.note.id}`),
         'with its marks and its bare page: ' + JSON.stringify(vGroup.urls));
  const doc = await (await fetch(B + '/studio/api/docs', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: '---\ntitle: A kept page\nlang: en\n---\n\n# A kept page\n\nText.\n'})})).json();
  const docId = doc.meta && doc.meta.id;
  const docOff = await (await fetch(B + '/studio/doc/' + docId + '/__offline')).json();
  eq([docOff.ok, docOff.kind, docOff.small.some(x => /static\/app\.js$/.test(x.url))],
     [true, 'document', true],
     'and a document says the page the computer rendered, with the studio\'s own scripts');

  // ---- b3) what is kept goes out of date when the computer changes it
  const readerFile = `${WORK}/root${MADE.readers.en}index.html`;
  const was = await Deno.readTextFile(readerFile);
  await Deno.writeTextFile(readerFile, was + '\n<!-- changed on the computer -->\n');
  const now = await (await fetch(B + MADE.readers.en + '__offline')).json();
  assert(now.version !== withNotes.version,
         'a book changed on the computer has another version (' + withNotes.version +
         ' → ' + now.version + ')');
  await Deno.writeTextFile(readerFile, was);

  // ---- b4) THE APP GETS ITSELF READY BEFORE THE COMPUTER GOES (TO-DO §0,
  // the third block of 2026-09-23).  The way in used to be fetched inside the
  // worker's install event; it is warmed afterwards now, by a page that is
  // open and asks for it.  So everything below -- the hub and the shelf
  // opening with the computer stopped -- waits on the WARMING and not on a
  // stopwatch: the worker's own "that list is done" is what is waited for.
  // The ask here is the page's own ask made once more, and that is exactly
  // what makes it safe to make: the worker passes over every address this
  // phone holds already, so a second ask of a warm phone fetches nothing at
  // all and still says when it has settled the list.
  const ready = await page.evaluate(() => new Promise((ok, no) => {
    const sw = navigator.serviceWorker;
    const heard = e => {
      const d = e.data || {};
      if (!d.warmed || d.warmed.what !== 'way-in') return;
      sw.removeEventListener('message', heard);
      ok(d.warmed);
    };
    sw.addEventListener('message', heard);
    sw.controller.postMessage({warm: 'way-in'});
    setTimeout(() => no(new Error('the way in was never warmed')), 180000);
  }));
  assert(ready.of > 10, 'the way in is warmed while the computer is there, and says when it is done: ' +
         ready.of + ' addresses');
  eq(await page.evaluate(() => Promise.all(['/?mode=mobile', '/', '/m/books/', '/m/kept/']
       .map(u => caches.match(u).then(r => !!r)))),
     [true, true, true, true],
     'so the app\'s start address, the hub at its other address and the shelves are on ' +
     'the phone before the computer goes');

  // ---- b5) A PAGE OPENS IN THE STATE THE LAST ONE WAS IN, AND CORRECTS
  // ITSELF (the owner's 5, 2026-09-23: "when changing pages the app rechecks
  // if it's offline and assumes being online even if the page before showed
  // being offline; good on the check, but assume that the status is the same
  // of the page previous... and yes do the check and if the situation
  // changes, correct, of course").  Walking from an offline hub into the
  // shelf used to give three seconds of a page pretending all was well: cards
  // that could be tapped and went nowhere, no chip, the counts the clock had
  // made wrong still on the screen.
  //
  // BOTH HALVES ARE DRIVEN, and the window between them is made visible by
  // HOLDING THE PROBE'S OWN ASK BACK two seconds -- less than the three it
  // gives up after, so the computer's real answer is what arrives.  What the
  // page shows in the meantime is the memory, and what it shows afterwards is
  // the truth: the memory here says AWAY while the computer is really there,
  // so nothing but the carrying could put the chip up and nothing but the
  // probe could take it down again.  In its own context, so that the held-back
  // fetch belongs to this test and to nothing after it.
  const carrier = await browser.newContext(PHONE);
  await carrier.addInitScript(() => {
    try {
      localStorage.setItem('parseh_mode', 'mobile');
      // what the last page found: away, a moment ago, so it is still trusted
      localStorage.setItem('parseh_away',
                           JSON.stringify({at: Date.now() / 1000, away: true}));
    } catch (e) { /* no storage: the assertions below will say so */ }
    const real = window.fetch;
    window.fetch = function (input, init) {
      const u = String((input && input.url) || input || '');
      if (!/\/__activity/.test(u)) return real.call(this, input, init);
      return new Promise(ok => setTimeout(() => ok(real.call(window, input, init)), 2000));
    };
    window.__away = [];
    (function look() {
      const t = Math.round(performance.now());
      window.__away.push([t, !!(document.documentElement &&
                                document.documentElement.hasAttribute('data-parseh-away'))]);
      if (t < 5000) setTimeout(look, 50);
    })();
  });
  const carried = await carrier.newPage();
  await carried.goto(B + '/m/books/', {timeout: 30000});
  await carried.waitForFunction(() => window.__away && window.__away.length &&
                                window.__away[window.__away.length - 1][0] >= 4000,
                                null, {timeout: 30000});
  const seen = await carried.evaluate(() => window.__away);
  // the first moment the page said "away", and it can only be the memory:
  // the one ask that could have said so is still two seconds out
  const first = seen.find(([, on]) => on) || [];
  const held = seen.filter(([t, ]) => t >= first[0] && t < 1800);
  const after = seen.filter(([t]) => t > 3000);
  assert(first.length && first[0] < 1500 && held.length > 3 && held.every(([, on]) => on),
         'the shelf opens offline because the page before it was, ' + first[0] +
         'ms in and with nothing yet asked of the computer');
  assert(after.length > 3 && after.every(([, on]) => !on),
         'and the probe corrects it the moment the computer answers: ' +
         JSON.stringify(after.slice(-4)));
  eq(await carried.evaluate(() => {
    const r = JSON.parse(localStorage.getItem('parseh_away') || 'null');
    return r ? r.away : null;
  }), false, 'and what is written down for the next page is what the probe found, not the memory');
  await carrier.close();

  // ---- c) THE COMPUTER GOES AWAY.  Stopped, not "offline" in the browser:
  // a browser's offline switch does not reach a worker's own fetches.
  hub.kill('SIGTERM');
  await hub.status;
  hubUp = false;
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(B + '/', {cache: 'no-store'}); await r.body?.cancel(); await sleep(250); }
    catch (_) { break; }
  }
  await page.reload();
  await page.waitForFunction(() => typeof SUBS !== 'undefined', null, {timeout: 30000});
  assert(await page.evaluate(() => document.querySelectorAll('.sub').length > 0),
         'with the computer stopped the kept reader still opens, and its text is there');

  // ---- c1) THE NOTES ARE THERE, which is the whole of what the owner asked
  // for: a mark in the seam, and the note behind it.  The marks come from the
  // seams' list kept with the book (a door: the computer first, this copy
  // behind it), and the note itself from its own bare page.
  await page.waitForFunction(() => document.querySelectorAll('.gap .mark').length >= 3,
                             null, {timeout: 30000});
  const marks = await page.evaluate(() =>
    [...document.querySelectorAll('.gap .mark')].map(b => b.textContent));
  assert(marks.includes('On the idiom'),
         'the marks are drawn in their seams with the computer away: ' + JSON.stringify(marks));
  await tapMark(page, 'On the idiom');
  await page.waitForSelector('#ntbox:not([hidden])', {timeout: 30000});
  const said = await page.evaluate(async () => {
    // asked for again every time round: opening a note puts a FRESH iframe in
    // place of the old one (ntFrame), so one taken hold of early is a
    // detached element that will never fill
    for (let i = 0; i < 80; i++) {
      const d = (document.getElementById('ntframe') || {}).contentDocument;
      const t = d && d.body ? (d.body.textContent || '').trim() : '';
      if (t) return {text: t.slice(0, 300), page: (d.body.dataset || {}).page || ''};
      await new Promise(r => setTimeout(r, 250));
    }
    return {text: '', page: ''};
  });
  assert(/the one from chapter two/.test(said.text) && said.page === 'note',
         'and tapping one opens the note itself — its own words, on the studio\'s bare page, ' +
         'with the computer stopped: ' + JSON.stringify(said));
  await page.keyboard.press('Escape');
  // AND THE ONE THAT HOLDS AN EXERCISE OPENS ANSWERABLE (his third decision):
  // what was kept for it is the studio's whole page, scripts and all, so it
  // is the page it is at the desk and not a box nobody can answer.
  await tapMark(page, 'Drill on the idiom');
  const drilled = await page.evaluate(async () => {
    for (let i = 0; i < 80; i++) {
      const d = (document.getElementById('ntframe') || {}).contentDocument;
      const t = d && d.body ? (d.body.textContent || '').trim() : '';
      if (/Complete it/.test(t))
        // `found` is what was matched; `text` is only the excerpt a failure
        // prints, and asserting on the excerpt failed the test for a page
        // that was entirely right -- the exercise sits below 300 characters
        // of the studio's own chrome.
        return {found: true, text: t.slice(0, 300), page: (d.body.dataset || {}).page || '',
                fields: d.querySelectorAll('input, button, select').length};
      await new Promise(r => setTimeout(r, 250));
    }
    const d = (document.getElementById('ntframe') || {}).contentDocument;
    return {why: 'the exercise never came up', text: d && d.body
              ? (d.body.textContent || '').trim().slice(0, 200) : ''};
  });
  assert(drilled.found && drilled.page === 'doc' && drilled.fields > 0,
         'a note holding an exercise opens its full studio page, answerable, away from the ' +
         'computer exactly as at the desk: ' + JSON.stringify(drilled));
  await page.keyboard.press('Escape');
  const ranged = await page.evaluate(async () => {
    const a = document.getElementById('audio');
    const r = await fetch(a.src, {headers: {Range: 'bytes=100-199'}});
    return [r.status, r.headers.get('content-range'), (await r.arrayBuffer()).byteLength];
  });
  eq([ranged[0], ranged[2]], [206, 100],
     'a range asked of the kept recording is answered 206, cut to size (' + ranged[1] + ') — seeking works');
  eq(await page.evaluate(async () => {
    const r = await fetch('/__prefs');
    return [r.status, (await r.json()).offline === true];
  }), [503, true], 'and what only the computer can answer says so at once, instead of hanging');
  // the page's one question is the one address the worker leaves to the
  // browser (TO-DO §2.24): it hears the network itself, and a refusal is
  // heard at once, never waited out
  eq(await page.evaluate(async () => {
    const t = performance.now();
    try { await fetch('/__activity'); return 'answered'; }
    catch (e) { return performance.now() - t < 1000 ? 'refused at once' : 'refused late'; }
  }), 'refused at once',
     'and "is the computer there?" hears the refusal itself, at once, with no worker in between');
  await page.waitForSelector('.kp-off', {timeout: 30000});
  assert(await page.evaluate(() => document.querySelector('.kp-off').getAttribute('href') === '/m/kept/'),
         'the page wears the offline chip, which opens the list of what is kept');

  // ---- c1b) AND WHERE THE NOTES WERE UNTICKED, THE PHONE SAYS SO.  The
  // second book is kept and opens; its note is not, and nothing pretends
  // otherwise -- no mark in the seam, because the seams' list is the
  // computer's and was not kept with it, and the note's own page answers
  // with "Parseh cannot be reached" rather than an empty frame.
  await page.goto(FA_READER, {timeout: 30000});
  await page.waitForFunction(() => typeof SUBS !== 'undefined', null, {timeout: 30000});
  await answerPlace(page);
  assert(await page.evaluate(() => document.querySelectorAll('.sub').length > 0),
         'the second book opens with the computer stopped too');
  await sleep(1500);            // whatever the marks were going to be, by now
  const empty = await page.evaluate(async () => {
    const marks = document.querySelectorAll('.gap .mark').length;
    const r = await fetch('../notes/api/marks').catch(e => ({status: 0, why: e.message}));
    let said = null;
    try { said = await r.json(); } catch (e) { /* not JSON: the status says it */ }
    return [marks, r.status, !!(said && said.offline)];
  });
  eq(empty, [0, 503, true],
     'its notes were not kept: no mark is drawn, and the seams\' list says at once that it ' +
     'needs the computer instead of hanging');
  const shown = await page.evaluate(async (id) => {
    const f = document.createElement('iframe');
    f.src = '../notes/note/' + id;
    f.style.cssText = 'position:fixed;left:-9999px;width:300px;height:300px';
    document.body.appendChild(f);
    await new Promise(r => { f.onload = r; setTimeout(r, 20000); });
    const d = f.contentDocument;
    return d && d.body ? (d.body.textContent || '').trim().slice(0, 200) : '';
  }, faNote);
  assert(/cannot be reached/i.test(shown),
         'and opening the note that was not kept says the computer is needed, instead of ' +
         'showing a blank frame: ' + JSON.stringify(shown));

  await page.goto(B + '/m/kept/');
  await page.waitForSelector('.m-kept', {timeout: 20000});
  const kept = await page.evaluate(() => [...document.querySelectorAll('.m-kept .m-btitle')].map(e => e.textContent));
  // the two books kept above: the English one with its notes, the Persian one
  // without them
  eq(kept.length, 2, 'the kept page opens with the computer away, and lists them: ' + JSON.stringify(kept));
  assert(await isDrawn(page, '.m-keptoff'), 'with a way to give the room back');

  // ---- c2) THE APP ITSELF OPENS (the owner's 1 and 2, 2026-09-23).  It used
  // to stall on its own splash: /?mode=mobile was in no cache and the fetch
  // had no deadline.  The way in is kept now, and these are NOT the "Parseh
  // cannot be reached" page -- the usual pages open, with the offline chip.
  await page.goto(B + '/?mode=mobile', {timeout: 30000});
  await page.waitForSelector('.hub-mobile .m-doors', {timeout: 30000});
  eq(await page.evaluate(() => /cannot be reached/.test(document.title)), false,
     'the app opens on its own hub with the computer stopped, not on the offline page');
  // what the clock has made wrong is not shown; the doors themselves stay
  await page.waitForFunction(() => document.documentElement.hasAttribute('data-parseh-away'),
                             null, {timeout: 30000});
  eq(await page.evaluate(() => [...document.querySelectorAll('.hub-mobile .m-tags .tag')]
       .filter(t => /^\s*\d+\s+due\s*$/.test(t.textContent) && t.style.display !== 'none').length),
     0, 'and what is due -- the one count the clock moves -- is not shown while it is away');
  assert(await isDrawn(page, '.kp-off'), 'the hub wears the offline chip');

  // the shelf too, with the kept book tappable and the rest drawn and not
  await page.goto(B + '/m/books/', {timeout: 30000});
  await page.waitForSelector('.m-shelf[data-shell-block] .m-book', {timeout: 30000});
  await page.waitForFunction(() => document.querySelectorAll('.m-book.kp-away').length > 0 ||
                                   !document.documentElement.hasAttribute('data-parseh-away'),
                             null, {timeout: 30000});
  const shelf = await page.evaluate(() => {
    const on = [...document.querySelectorAll('a.m-book[href]')].map(a => a.getAttribute('href'));
    const off = [...document.querySelectorAll('.m-book.kp-away')]
      .map(c => (c.querySelector('.kp-note') || {}).textContent || '');
    return [on, off];
  });
  assert(shelf[0].length >= 1 && shelf[0].every(h => /reader\/$/.test(h) || /reader\//.test(h)),
         'the book kept on this phone is still a link: ' + JSON.stringify(shelf[0]));
  assert(shelf[1].length >= 1 && /Not on this phone/.test(shelf[1][0]),
         'and a book that is not on this phone is drawn and cannot be tapped, saying so');

  // ---- c3) THE VIDEOS SHELF, AWAY: CHANNELS, AND THE ONES THIS PHONE
  // CANNOT OPEN LOOK LIKE IT (decision C, 2026-09-23).  The shelf itself is
  // kept with the app and opens whatever happens, so it shows the channels
  // the computer had when it was last reached -- but a CHANNEL's page is on
  // this phone only if the app warmed it, and nothing warms one: tapping such
  // a card would go nowhere, which is worse than a card that says so.
  await page.goto(B + '/m/videos/', {timeout: 30000});
  await page.waitForSelector('.m-shelf[data-shell-block] .m-chancard', {timeout: 30000});
  await page.waitForFunction(() => document.documentElement.hasAttribute('data-parseh-away') &&
    [...document.querySelectorAll('.m-chancard')].every(c => c.hasAttribute('data-m-here')),
                             null, {timeout: 30000});
  const chans = await page.evaluate(() => ({
    title: /cannot be reached/.test(document.title),
    cards: document.querySelectorAll('.m-chancard').length,
    players: document.querySelectorAll('a.m-book[href^="/youtube/v/"]').length,
    off: [...document.querySelectorAll('.m-chancard.m-chanoff')].map(c => ({
      href: c.getAttribute('href'), kept: c.getAttribute('data-m-here'),
      says: (c.querySelector('.m-channote') || {}).textContent || ''}))}));
  eq([chans.title, chans.cards, chans.players], [false, 1, 0],
     'the videos shelf opens with the computer stopped, still the channels and still no ' +
     'card that opens a player');
  assert(chans.off.length === 1 && chans.off[0].href === null && chans.off[0].kept === '0' &&
         /Not on this phone/.test(chans.off[0].says),
         'and a channel whose list is not on this phone is drawn, cannot be tapped, and says ' +
         'so: ' + JSON.stringify(chans.off));
  await page.context().close();

  // ---- d) the computer comes back, for whatever runs after this
  hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  hubUp = true;
  for (const s of [hub.stdout, hub.stderr])
    (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
  for (const t = Date.now();;) {
    try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start again');
    await sleep(250);
  }
  assert(true, 'the computer started again, for what comes after');
}

// ======== decks ========
async function partDecks() {
  const EN = MADE.decks.en, IT = MADE.decks.it;
  for (const [opts, tag] of [[PHONE, 'phone'], [NARROW, 'narrow'], [LAND, 'landscape'], [DESK, 'desktop']]) {
    console.log(`\n== decks, ${tag}`);
    // sideways and on a desktop the answer is a column at the right
    const rail = tag === 'landscape' || tag === 'desktop';
    const page = await newPage(opts, 'decks ' + tag);
    await page.goto(B + '/');
    await setMode(page, 'mobile');
    await page.reload();
    // ---- a) the decks
    await Promise.all([page.waitForURL(B + '/exercises/'), tap(page, '.hub-mobile a.m-door[href="/exercises/"]')]);
    await page.waitForFunction(() => document.querySelectorAll('.dk-card').length === 3);
    await settle(page);
    await shot(page, `decks-${tag}`);
    assert(await isDrawn(page, '.m-topbar') && !(await isDrawn(page, 'header.topbar')),
           'the decks\' mobile layout is the one drawn, the browser bar display:none');
    eq(await page.evaluate(() => getComputedStyle(document.querySelector('header.topbar')).display), 'none',
       'the browser bar is display:none');
    const got = await clickable(page, 'body');
    const deckLinks = ['english/everyday-english', 'italian/nothing-yet', 'persian/persian-words']
      .flatMap(p => [`a:/exercises/deck/${p}/`, `a:/exercises/deck/${p}/study`, `a:/exercises/deck/${p}/`]);
    // on a touch screen the bar wears a ? as well: what a button does, for a
    // finger that cannot rest on it (lib/explain.js, §4.7)
    const ask = tag === 'desktop' ? [] : ['button:px-ask'];
    eq(got.filter(x => !/^a:\/exercises\/deck\//.test(x)),
       ['a:/', 'button:browser', 'button:mobile', 'button:theme', ...ask,
        'button:all', 'button:fa', 'button:it', 'button:en'],
       'the bar and the chips: home, the switch, the theme' + (ask.length ? ', the ?' : '') +
       ', one chip a language');
    eq(got.filter(x => /^a:\/exercises\/deck\//.test(x)).sort(), deckLinks.sort(),
       'and each deck its name, Study and Open');
    eq(await page.evaluate(() => {
      const a = document.querySelector('.dk-card[data-lang=it] [data-x=study]');
      return [a.classList.contains('dk-off'), a.getAttribute('aria-disabled')];
    }), [true, 'true'], 'an empty deck has nothing to study: its Study is off');
    for (const no of ['#btn-import', '#btn-restore', '#btn-new-deck', '#btn-stop', 'a[href$="/api/backup"]',
                      '.dk-card summary', '[data-x=delete]', '.dk-card .dropdown'])
      assert(!(await isDrawn(page, no)), 'no ' + no);
    allFit(await targets(page, '.m-topbar a, .m-topbar button'), 'the bar: 48px, on the screen');
    allFit(await targets(page, '.dk-card h3 a, .dk-card-actions a:not(.dk-off), .parseh-langs .chip'),
           'the names, the Study and Open buttons and the chips: 48px, on the screen, reached by a tap');
    assert(await sideways(page) <= 0, 'the page does not scroll sideways');
    if (rail) {
      const cols = await page.evaluate(() => [...document.querySelectorAll('.dk-card')]
        .map(c => Math.round(c.getBoundingClientRect().top)));
      assert(cols[0] === cols[1], 'from 600px the decks go two to a row ' + JSON.stringify(cols));
    }

    // ---- b) a chip, and the theme
    await page.evaluate(() => scrollTo(0, 0));
    await sleep(250);
    await tap(page, '.parseh-langs .chip[data-pick=fa]');
    eq(await page.evaluate(() => [...document.querySelectorAll('.dk-card')].filter(c => !c.hidden)
      .map(c => c.dataset.lang)), ['fa'], 'Persian picked: the Persian deck alone');
    await tap(page, '.parseh-langs .chip[data-pick=all]');
    if (tag === 'phone') {
      const t0 = await page.evaluate(() => document.body.dataset.theme || 'paper');
      await tap(page, '.m-topbar [data-parseh-theme]');
      const t1 = await page.evaluate(() => [document.body.dataset.theme || 'paper', localStorage.getItem('parseh_theme'),
                                            document.querySelector('.m-topbar [data-parseh-theme]').textContent]);
      assert(t1[0] !== t0 && t1[1] === (t1[0] === 'paper' ? 'light' : t1[0]),
             `the theme button turns the page (${t0} -> ${t1[0]}) and says so for the whole toolbox (${t1[1]}, ${t1[2]})`);
      await shot(page, `decks-${tag}-${t1[0]}`);
      await page.evaluate(() => localStorage.setItem('parseh_theme', 'light'));
    }

    // ---- c) a deck
    await Promise.all([page.waitForURL(B + `/exercises/deck/${IT.folder}/${IT.slug}/`),
                       tap(page, `.dk-card[data-lang=it] [data-x=browse]`)]);
    await page.waitForFunction(() => !document.querySelector('#deck-mobile-note').hidden);
    eq(await page.evaluate(() => document.querySelector('#deck-mobile-note').textContent),
       'This deck has no exercises yet: they are added in the browser interface.', 'an empty deck says where exercises are added');
    assert(!(await isDrawn(page, '.dk-browse')), 'and has no list to pick from');
    await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/`);
    await page.waitForFunction(() => !document.querySelector('#btn-practise').disabled &&
                                     document.querySelectorAll('#browse-list .dk-row').length === 5);
    await settle(page);
    await shot(page, `deck-${tag}`);
    for (const no of ['#btn-rename', '#btn-add-exercise', '.dk-deckactions summary', '#btn-options',
                      '#btn-delete-deck', '#btn-stop', '#btn-bulk-copy', '#btn-bulk-move', '#btn-bulk-add-tag',
                      '#btn-bulk-remove-tag', '#btn-bulk-new', '#btn-bulk-delete', '#btn-cram', '.dk-row-actions',
                      '.dk-selection-hint', '#m-cram'])
      assert(!(await isDrawn(page, no)), 'the deck: no ' + no);
    eq(await page.locator('#btn-practise').textContent(), 'Cram all', 'the deck: Study now, and Cram all');
    allFit(await targets(page, '#btn-study, #btn-practise, #browse-filter, #browse-type, #browse-state, ' +
                               '#browse-tag, .dk-bulkbar .btn, .dk-row .dk-select'),
           'Study now, Cram all, the filters, the five ways to pick, each exercise\'s box: 48px, on the screen');
    assert(/5 exercises/.test(await page.locator('#deck-counts').textContent()), 'its counts');
    assert(await sideways(page) <= 0, 'the deck does not scroll sideways');

    if (tag !== 'narrow') {
      // ---- e) two picked by hand, crammed
      const before = await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json();
      await tapMiddle(page, '.dk-row:nth-child(2) .dk-select');
      await tapMiddle(page, '.dk-row:nth-child(4) .dk-select');
      eq(await page.locator('#browse-selected').textContent(), '2 selected', 'two boxes tapped: two picked');
      const go = await rect(page, '#m-cram');
      eq(await page.locator('#m-cram').textContent(), 'Cram 2 exercises', 'and Cram says so');
      assert(go && go.h >= 48 && go.b <= await page.evaluate(() => innerHeight) && go.l >= 0 &&
             go.r <= await page.evaluate(() => innerWidth), 'at the foot of the screen, over the list ' + JSON.stringify(go));
      await shot(page, `deck-${tag}-picked`);
      await Promise.all([page.waitForURL(/\/cram$/), tap(page, '#m-cram')]);
      await page.waitForFunction(() => /of 2/.test(document.querySelector('#cram-progress').textContent));
      eq(await page.locator('#cram-progress').textContent(), '1 of 2', 'crammed: the two picked');
      await cramAnswerBar(page, tag, rail);
      // ---- and the ones a tag picks
      await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/`);
      await page.waitForFunction(() => document.querySelectorAll('#browse-list .dk-row').length === 5);
      await tap(page, '#btn-deselect-all');
      await tap(page, '#btn-select-tag');
      await page.waitForSelector('.modal.dk-modal select');
      allFit(await targets(page, '.modal.dk-modal select, .modal.dk-modal .row .btn'),
             'Select by tag: its list and its two buttons, 48px');
      await page.locator('.modal.dk-modal select').selectOption('grammar');
      await tap(page, '.modal.dk-modal .row .btn.primary');
      await page.waitForFunction(() => !document.querySelector('.modal-overlay'));
      eq(await page.locator('#browse-selected').textContent(), '2 selected', 'grammar: the two exercises tagged so');
      await Promise.all([page.waitForURL(/\/cram$/), tap(page, '#m-cram')]);
      await page.waitForFunction(() => /of 2/.test(document.querySelector('#cram-progress').textContent));
      const crammed = await page.locator('#cram-stage').textContent();
      assert(/Which article|past of/.test(crammed), 'crammed: one of the grammar ones first: ' +
             crammed.replace(/\s+/g, ' ').trim().slice(0, 50));
      const after = await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json();
      eq(after.items.map(it => JSON.stringify(it.schedule)), before.items.map(it => JSON.stringify(it.schedule)),
         'cramming leaves the scheduling as it was');
    }

    if (tag !== 'narrow') {
      // ---- d) studying, every exercise new again (the deck's own Set to new,
      // asked of its API: this viewport's session starts where the last one did)
      const all = (await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json()).items.map(it => it.id);
      const reset = await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}/items/bulk`, {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'set-new', ids: all})});
      await reset.body?.cancel();
      assert(reset.ok, 'the deck new again, to study');
      await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/`);
      await page.waitForFunction(() => !document.querySelector('#btn-practise').disabled);
      await page.evaluate(() => scrollTo(0, 0));
      await Promise.all([page.waitForURL(/\/study$/), tap(page, '#btn-study')]);
      await page.waitForFunction(() => !document.querySelector('#btn-show').hidden || !document.querySelector('#btn-check').hidden);
      for (const no of ['#btn-edit-card', '.dk-keys', '#btn-stop', '.m-topbar', 'header.topbar'])
        assert(!(await isDrawn(page, no)), 'studying: no ' + no);
      allFit(await targets(page, '.dk-studyhead .m-back'), 'studying: ‹ back to the deck, 48px');
      eq(await page.evaluate(() => new URL(document.querySelector('.dk-studyhead .m-back').href).pathname),
         `/exercises/deck/${EN.folder}/${EN.slug}/`, 'and it goes to the deck');
      if (rail && page.touch) {
        // ---- THE SCROLL STRIP (§4.16).  A finger's device only: a desktop
        // has a wheel, and the column is no use to it.  The empty stretch of the column
        // between the buttons scrolls the exercise, so a long one need not be
        // reached for across the screen.  A screen too short for the exercise
        // is exactly what it is for, so the viewport is made one.
        await page.setViewportSize({width: 844, height: 300});
        await sleep(400);
        await page.evaluate(() => window.ParsehStrip && ParsehStrip.look());
        const strip = await rect(page, '.dk-strip');
        const skipWas = await rect(page, '#btn-skip');
        eq(await page.evaluate(() => [document.querySelector('.dk-strip').classList.contains('dk-can-scroll'),
                                      getComputedStyle(document.querySelector('.dk-strip')).touchAction]),
           [true, 'none'], 'the strip says it can be dragged, and takes the drag itself');
        assert(strip.l >= (await rect(page, '#study-stage')).r - 1,
               'it is in the column, not over the exercise ' + JSON.stringify(strip));
        // a finger dragged up the strip: the page follows it
        const y0 = Math.round(strip.t + strip.h / 2), x = Math.round(strip.l + strip.w / 2);
        const pt = v => [{x, y: v, radiusX: 4, radiusY: 4, force: 1, id: 1}];
        await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: pt(y0 + 60)});
        for (let k = 1; k <= 6; k++) {
          await page.touch.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: pt(y0 + 60 - k * 18)});
          await sleep(16);
        }
        await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
        await sleep(400);
        const moved = await page.evaluate(() => scrollY);
        assert(moved > 40, 'a finger dragged up the strip scrolls the exercise (' + moved + 'px)');
        const skipNow = await rect(page, '#btn-skip');
        assert(near(skipNow.t, skipWas.t) && near(skipNow.l, skipWas.l),
               'and the buttons do not move with it');
        eq(await page.evaluate(() => {
          const b = document.querySelector('#btn-skip'), r = b.getBoundingClientRect();
          const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return b.contains(el);
        }), true, 'a tap on Skip still reaches Skip: nothing of the strip is over it');
        // dragged back down, it goes back; and a short exercise says nothing
        await page.touch.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: pt(y0 - 60)});
        for (let k = 1; k <= 6; k++) {
          await page.touch.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: pt(y0 - 60 + k * 18)});
          await sleep(16);
        }
        await page.touch.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
        await sleep(500);
        assert(await page.evaluate(() => scrollY) < moved, 'dragged the other way, it goes back');
        await page.setViewportSize(LAND.viewport);
        await sleep(400);
      }
      const done = new Set();
      for (let round = 0; round < 5; round++) {
        const card = await page.evaluate(() => ({
          flash: !document.querySelector('#btn-show').hidden, scored: !document.querySelector('#btn-check').hidden,
          text: document.querySelector('#study-stage').textContent.replace(/\s+/g, ' ').trim().slice(0, 60)}));
        const primary = card.flash ? '#btn-show' : card.scored ? '#btn-check' : null;
        if (!primary) break;
        const box = await rect(page, '.dk-answerbar');
        const [W, H] = await page.evaluate(() => [innerWidth, innerHeight]);
        if (rail)
          assert(near(box.r, W) && near(box.t, 0) && near(box.b, H) && box.w <= 220,
                 'sideways: what to do is a column down the right edge ' + JSON.stringify(box));
        else
          assert(near(box.b, H) && near(box.l, 0) && near(box.r, W),
                 'upright: what to do is a bar at the foot of the screen ' + JSON.stringify(box));
        if (rail) {
          const stage = await rect(page, '#study-stage');
          assert(stage.r <= box.l + 0.5, 'and the exercise beside it, not under it');
        }
        allFit(await targets(page, `${primary}, #btn-skip`), `${card.flash ? 'a flashcard: Show answer' : 'Check'} and Skip, 48px`);
        const at = await rect(page, primary);
        if (card.scored && /Which article/.test(card.text)) {
          allFit(await targets(page, '#study-stage .ex-option'), 'its answers: 48px, reached by a tap');
          const right = page.locator('#study-stage .ex-option').filter({hasText: /^\s*an\s*$/});
          if (page.touch) await right.tap(); else await right.click();
        }
        const filled = card.scored && /Complete the sentence/.test(card.text);
        const matched = card.scored && /Match each British word/.test(card.text);
        if (filled) await fillByCloud(page, tag);
        if (matched) await matchByCloud(page, tag);
        await tap(page, primary);
        if (card.scored && /Which article/.test(card.text))
          eq(await page.locator('#study-result').textContent(), 'Correct', 'the choice answered right: Correct');
        if (filled)
          eq(await page.locator('#study-result').textContent(), 'Correct', 'the blanks filled from their clouds: Correct');
        if (matched)
          eq(await page.locator('#study-result').textContent(), 'Correct', 'the matches made from their clouds: Correct');
        await page.waitForFunction(() => !document.querySelector('#rating-bar').hidden &&
                                         !document.querySelector('#btn-next').hidden);
        await sleep(200);
        // Next where the answer's button was, saying what it does
        const nx = await rect(page, '#btn-next');
        assert(near(nx.l, at.l) && near(nx.r, at.r) && near(nx.b, at.b, 4),
               'Next, in the very place of ' + primary + ' ' + JSON.stringify([at, nx]));
        const says = await page.evaluate(() => {
          const n = document.querySelector('#btn-next'), r = n.dataset.rating;
          return [n.querySelector('.dk-word').textContent, n.querySelector('.dk-ivl').textContent, r,
                  document.querySelector('#rating-bar [data-rating=' + r + '] .dk-ivl').textContent];
        });
        eq(says.slice(0, 2), ['Next', `${says[2][0].toUpperCase() + says[2].slice(1)} · ${says[3]}`],
           'Next says the rating it gives, and when the exercise comes back');
        if (card.flash || /Which article/.test(card.text)) eq(says[2], 'good', 'right, or a card turned: Good');
        allFit(await targets(page, '#rating-bar .dk-rate, #btn-next'), 'the four ratings and Next: 48px, on the screen, reached by a tap');
        const rt = await tops(page, '#rating-bar .dk-rate');
        if (rail)
          assert(rt.length === 4 && rt[0] === rt[1] && rt[2] === rt[3] && rt[2] > rt[0],
                 'sideways: the ratings two by two ' + JSON.stringify(rt));
        else
          assert(rt.length === 4 && new Set(rt).size === 1, 'upright: the ratings on one line ' + JSON.stringify(rt));
        assert((await page.evaluate(() => [...document.querySelectorAll('#rating-bar .dk-ivl')].map(i => i.textContent)))
          .every(Boolean), 'each saying when the exercise comes back');
        if (round === 0) await shot(page, `study-${tag}`);
        // Good from the ratings once, Next the rest of the time
        await tap(page, round === 0 ? '#rating-bar [data-rating=good]' : '#btn-next');
        await page.waitForFunction(() => document.querySelector('#rating-bar').hidden);
        done.add(card.text);
      }
      const deck = await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json();
      const studied = deck.items.filter(it => (it.schedule || {}).state && it.schedule.state !== 'new').length;
      assert(studied >= 2, `rated by Good and by Next, the exercises are scheduled in the deck itself: ${studied} of ${deck.items.length}`);

      // ---- e) Cram all
      await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/`);
      await page.waitForFunction(() => !document.querySelector('#btn-practise').disabled);
      await Promise.all([page.waitForURL(/\/cram$/), tap(page, '#btn-practise')]);
      await page.waitForFunction(() => /of 5/.test(document.querySelector('#cram-progress').textContent));
      eq(await page.locator('#cram-progress').textContent(), '1 of 5', 'Cram all: every exercise of the deck, crammed');
      assert(await isDrawn(page, '.dk-cram-note[data-layout=mobile]') &&
             !(await isDrawn(page, '.dk-cram-note[data-layout=browser]')), 'said in the mobile layout\'s words');
      const after = await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json();
      eq(after.items.map(it => JSON.stringify(it.schedule)), deck.items.map(it => JSON.stringify(it.schedule)),
         'and the scheduling as it was');
    }

    // ---- f) Browser
    await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/`);
    // the list arrives after the page: its rows (and their actions, hidden in
    // the mobile layout) must be there before asking whether they are drawn
    await page.waitForFunction(() => document.querySelector('.dk-row-actions'));
    await gearMode(page, 'browser');
    eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'), localStorage.getItem('parseh_mode'),
                                  document.cookie.includes('parseh_mode=browser')]),
       ['browser', 'browser', true], 'Browser pressed on a deck: stored, mirrored, applied');
    for (const yes of ['header.topbar', '#btn-rename', '#btn-add-exercise', '#btn-options', '#btn-delete-deck',
                       '.dk-browse', '#btn-bulk-delete', '#btn-cram', '.dk-row-actions'])
      assert(await isDrawn(page, yes), 'the browser layout is back: ' + yes);
    assert(!(await isDrawn(page, '.m-topbar')) && !(await isDrawn(page, '#btn-practise')) &&
           !(await isDrawn(page, '.m-pickhead')), 'and the mobile one is gone');
    if (tag === 'desktop') {
      // the browser layout fills a blank from its cloud too (a0.3.1), and as
      // it always has: a word, then its blank -- which then opens no cloud
      // (tests/blank_cloud.mjs has every way, the drag among them)
      const fill = (await (await fetch(B + `/exercises/api/decks/${EN.folder}/${EN.slug}`)).json())
        .items.find(it => it.subtype === 'fill-blanks');
      await page.evaluate(([k, id]) => sessionStorage.setItem(k, JSON.stringify([id])),
                          [`parseh-cram:${EN.folder}/${EN.slug}`, fill.id]);
      await page.goto(B + `/exercises/deck/${EN.folder}/${EN.slug}/cram`);
      await page.waitForSelector('#cram-stage .ex-blank');
      await page.locator('#cram-stage .ex-blank').first().click();
      await sleep(250);
      assert(await isDrawn(page, '#cram-stage .ex-cloud'), 'the browser layout: a click on a blank opens its cloud');
      await page.keyboard.press('Escape');
      assert(!(await isDrawn(page, '#cram-stage .ex-cloud')), 'and Escape puts it away');
      await page.locator('#cram-stage .ex-bank .ex-item').filter({hasText: /^\s*went\s*$/}).click();
      await page.locator('#cram-stage .ex-blank').first().click();
      eq(await page.evaluate(() => document.querySelector('#cram-stage .ex-blank').textContent.trim()), 'went',
         'and a word, then its blank, fills it, as it always has');
      assert(!(await isDrawn(page, '#cram-stage .ex-cloud')), 'a picked word goes into the blank clicked: no cloud opens');
    }
    await page.context().close();
  }
}

// Fill in the blanks in the mobile interface: the blank first, then the word
// (app.js, bindExercises) -- a tap on a blank opens a cloud with a copy of
// the words the bank holds, a tap on one puts it there; the bank stays
async function fillByCloud(page, tag) {
  const S = '#study-stage';
  const texts = sel => page.evaluate(sel => [...document.querySelectorAll(sel)].map(x => x.textContent.trim()), sel);
  const bank = async () => (await texts(`${S} .ex-bank .ex-item`)).sort();
  const blanks = () => texts(`${S} .ex-blank`);
  const pick = async word => {
    const l = page.locator(`${S} .ex-cloud button`).filter({hasText: new RegExp('^\\s*' + word + '\\s*$')});
    if (page.touch) await l.tap(); else await l.click();
  };
  const open = async n => {
    await tapMiddle(page, `${S} .ex-blank >> nth=${n}`);
    await page.waitForSelector(`${S} .ex-cloud`);
    await sleep(200);                                  // its fade in, over
  };
  const whole = await bank();
  eq(whole, ['bought', 'goed', 'went'], `${tag}: the fill-in's bank, three words`);
  await tapMiddle(page, `${S} .ex-bank .ex-item`);
  eq(await page.evaluate(S => document.querySelectorAll(S + ' .picked, ' + S + ' .ex-cloud').length, S), 0,
     `${tag}: a word of the bank tapped picks nothing up and opens nothing: the blanks take the words`);
  await open(0);
  eq((await texts(`${S} .ex-cloud .ex-cloud-pick`)).sort(), whole, `${tag}: a blank tapped: a cloud with a copy of every word the bank holds`);
  allFit(await targets(page, `${S} .ex-cloud button`), `${tag}: its words 48px, on the screen, reached by a tap`);
  eq(await page.evaluate(S => {
    const c = document.querySelector(S + ' .ex-cloud').getBoundingClientRect();
    const e = document.querySelector(S + ' .exercise').getBoundingClientRect();
    const f = document.querySelector(S + ' .ex-fill').getBoundingClientRect();
    return [c.left >= e.left, c.right <= e.right, c.top >= f.bottom - 1];
  }, S), [true, true, true], `${tag}: inside the exercise, under the sentence -- which it leaves to be read`);
  eq(await page.evaluate(S => document.querySelector(S + ' .ex-blank').getAttribute('aria-expanded'), S), 'true',
     `${tag}: the blank says its cloud is open`);
  await shot(page, `fill-cloud-${tag}`);
  await pick('went');
  eq([await blanks(), await bank(), await isDrawn(page, `${S} .ex-cloud`)], [['went', ''], ['bought', 'goed'], false],
     `${tag}: went picked: in the first blank, gone from the bank, the cloud away`);
  await open(1);
  eq((await texts(`${S} .ex-cloud .ex-cloud-pick`)).sort(), ['bought', 'goed'], `${tag}: the second blank's cloud: the words left`);
  await pick('bought');
  await open(0);
  eq(await texts(`${S} .ex-cloud button`), [...(await texts(`${S} .ex-cloud .ex-cloud-pick`)), 'Empty this blank'],
     `${tag}: a filled blank's cloud can empty it`);
  await pick('goed');
  eq([await blanks(), await bank()], [['goed', 'bought'], ['went']], `${tag}: another word picked there: the two change places`);
  await open(0);
  await pick('Empty this blank');
  eq([await blanks(), await bank()], [['', 'bought'], ['goed', 'went']], `${tag}: emptied: the word back in the bank`);
  await open(0);
  await tapMiddle(page, `${S} .ex-prompt, ${S} .ex-kicker`);
  assert(!(await isDrawn(page, `${S} .ex-cloud`)), `${tag}: a tap anywhere else puts the cloud away`);
  await open(0);
  await pick('went');
  eq(await blanks(), ['went', 'bought'], `${tag}: filled right`);
}

// A matching exercise in the mobile interface, the same way round: a tap on
// a term's place opens a cloud with a copy of the answers the bank holds
async function matchByCloud(page, tag) {
  const S = '#study-stage';
  const RIGHT = {flat: 'apartment', lift: 'elevator', biscuit: 'cookie'};
  const texts = sel => page.evaluate(sel => [...document.querySelectorAll(sel)].map(x => x.textContent.trim()), sel);
  const bank = async () => (await texts(`${S} .ex-bank .ex-item`)).sort();
  const rows = () => page.evaluate(S => [...document.querySelectorAll(S + ' .ex-pair-row')].map(r =>
    [r.querySelector('.ex-pair-left').textContent.trim(), r.querySelector('.ex-match-drop').textContent.trim()]), S);
  const pick = async word => {
    const l = page.locator(`${S} .ex-cloud button`).filter({hasText: new RegExp('^\\s*' + word + '\\s*$')});
    if (page.touch) await l.tap(); else await l.click();
  };
  const open = async n => {
    await tapMiddle(page, `${S} .ex-match-drop >> nth=${n}`);
    await page.waitForSelector(`${S} .ex-cloud`);
    await sleep(200);
  };
  const whole = await bank();
  eq(whole, ['apartment', 'cookie', 'elevator'], `${tag}: the match's bank, three answers`);
  eq(await page.evaluate(S => getComputedStyle(document.querySelector(S + ' .ex-match-drop'), '::after').content, S),
     '"tap to choose"', `${tag}: an empty place asks for a tap, not a drop`);
  await tapMiddle(page, `${S} .ex-bank .ex-item`);
  eq(await page.evaluate(S => document.querySelectorAll(S + ' .picked, ' + S + ' .ex-cloud').length, S), 0,
     `${tag}: an answer of the bank tapped picks nothing up: the places take the answers`);
  await open(0);
  eq((await texts(`${S} .ex-cloud .ex-cloud-pick`)).sort(), whole, `${tag}: a place tapped: a cloud with a copy of every answer the bank holds`);
  allFit(await targets(page, `${S} .ex-cloud button`), `${tag}: its answers 48px, on the screen, reached by a tap`);
  eq(await page.evaluate(S => {
    const c = document.querySelector(S + ' .ex-cloud').getBoundingClientRect();
    const e = document.querySelector(S + ' .exercise').getBoundingClientRect();
    return [c.left >= e.left, c.right <= e.right];
  }, S), [true, true], `${tag}: the cloud inside the exercise`);
  await shot(page, `match-cloud-${tag}`);
  const terms = (await rows()).map(r => r[0]);
  // the first one wrong, the rest right; then the wrong one changed
  const wrong = RIGHT[terms[1]];
  await pick(wrong);
  for (let i = 1; i < terms.length; i++) {
    await open(i);
    if (i === 1) eq((await texts(`${S} .ex-cloud .ex-cloud-pick`)).sort(), whole.filter(w => w !== wrong),
                    `${tag}: the next place's cloud: the answers left`);
    // the one the first place took is back in the bank when its row needs it
    await pick(i === 1 ? RIGHT[terms[0]] : RIGHT[terms[i]]);
  }
  eq((await rows()).map(r => r[1]), [wrong, RIGHT[terms[0]], RIGHT[terms[2]]], `${tag}: three placed, two of them crossed`);
  await open(0);
  eq(await texts(`${S} .ex-cloud button`), ['Empty this match'], `${tag}: a filled place's cloud, with the bank empty: it can be emptied`);
  await pick('Empty this match');
  eq(await bank(), [wrong], `${tag}: emptied: its answer back in the bank`);
  await open(1);
  await pick(wrong);
  eq([(await rows()).map(r => r[1]), await bank()], [['', wrong, RIGHT[terms[2]]], [RIGHT[terms[0]]]],
     `${tag}: an answer put where another was: that one back in the bank`);
  await open(0);
  await pick(RIGHT[terms[0]]);
  await open(1);
  await tapMiddle(page, `${S} .ex-prompt`);
  assert(!(await isDrawn(page, `${S} .ex-cloud`)), `${tag}: a tap anywhere else puts the cloud away`);
  await open(1);
  await pick('Empty this match');
  await open(1);
  await pick(RIGHT[terms[1]]);
  eq((await rows()).map(r => r[1]), terms.map(t => RIGHT[t]), `${tag}: every term matched right`);
}

// cramming: Skip beside the answer's button, then Next exercise in its
// place; and at the end, what was wrong and what was skipped
async function cramAnswerBar(page, tag, rail) {
  const box = await rect(page, '#cram-actions');
  const [W, H] = await page.evaluate(() => [innerWidth, innerHeight]);
  if (rail) assert(near(box.r, W) && near(box.t, 0) && near(box.b, H), 'cramming sideways: the column at the right');
  else assert(near(box.b, H) && near(box.l, 0), 'cramming upright: the bar at the foot');
  assert(!(await isDrawn(page, '.m-topbar')), 'cramming: no bar over the exercise');
  const primary = await page.evaluate(() => !document.querySelector('#cram-check').hidden ? '#cram-check' : '#cram-show');
  allFit(await targets(page, `${primary}, #cram-skip`), 'cramming: the answer\'s button and Skip, 48px');
  const at = await rect(page, primary), sk = await rect(page, '#cram-skip');
  if (rail) assert(sk.t < at.t && near(sk.l, box.l + 12, 4), 'sideways: Skip at the top of the column, the answer at its foot');
  else assert(near(sk.t, at.t, 4) && sk.r < at.l, 'upright: Skip beside the answer, on its left');
  await tap(page, primary);
  const then = primary === '#cram-check' ? '#cram-next' : '#cram-correct';
  await page.waitForFunction(sel => !document.querySelector(sel).hidden, then);
  const nx = await rect(page, then);
  assert(near(nx.b, at.b, 4) && near(nx.r, at.r), `cramming: ${then} where ${primary} was ` + JSON.stringify([at, nx]));
  await shot(page, `cram-${tag}`);
  // on to the end: this one gone on from, every other one skipped
  if (then === '#cram-next') {
    assert(!(await isDrawn(page, '#cram-skip')), 'checked, it is answered: no Skip');
    await tap(page, '#cram-next');
  } else await tap(page, '#cram-wrong');
  for (let n = 0; n < 6 && !(await isDrawn(page, '#cram-done')); n++) {
    await tap(page, (await isDrawn(page, '#cram-skip')) ? '#cram-skip' : '#cram-next');
    await sleep(150);
  }
  assert(await isDrawn(page, '#cram-done'), 'the practice over, the end is drawn');
  const tally = await page.locator('#cram-tally').textContent();
  assert(/^2 exercises: .*skipped\.$/.test(tally), 'it says how it went: ' + tally);
  await page.evaluate(() => scrollTo(0, 0));
  allFit(await targets(page, '#cram-skipped-list .dk-cram-item, #cram-done .dk-cram-list:not([hidden]) > .btn, ' +
                               '#cram-again, #cram-done .dk-back'),
         'the skipped ones listed, and every button of the end, 48px, reached by a tap');
  if (await isDrawn(page, '#cram-wrong-list'))
    eq(await page.locator('#cram-wrong-list .dk-cram-meta').first().textContent(), 'wrong once, then skipped',
       'the one answered wrong says so, and that it was skipped after');
  await tap(page, '#cram-skipped-list .dk-cram-item');
  await page.waitForSelector('#cram-skipped-list .dk-cram-solved:not([hidden]) .exercise');
  assert(true, 'a tap on one shows it solved');
  await shot(page, `cram-${tag}-end`);
}

// ======== app ========
// ======== a book kept in the background: Android's own download ========
/* The owner's decision of 2026-09-23 (TO-DO §0; lib/keep.js, bgKeep; lib/sw.js,
   settle): what only the background way has, driven -- the computer really
   stopped (SIGSTOP: a phone meets silence, not refusal), the worker really
   stopped (CDP), a Cancel made as the notification makes it (the download's
   own abort, which fires the same event), and every line read off the page in
   the words he chose.  Run only where this Chromium HAS the background
   download; on the worker's way there is none of this to drive.  What no
   headless browser can show -- Android's own notification and its buttons, a
   locked phone, his tunnel -- is his phone's to try (TO-DO §19.11). */
async function partBackground() {
  if (WAY !== 'background') return;
  console.log('\n== a book kept in the background: Android\'s own download');
  const EN = B + MADE.readers.en, FA = B + MADE.readers.fa;
  const HERE = MADE.readers.en;                  // what it is kept under: its reader's address
  const BOOK = MADE.readers.en.replace(/reader\/$/, '');
  const AUDIO = WORK + '/root' + BOOK + 'audio/';
  const LEAVE = ' — you can leave this page';
  const REFUSED = 'Chrome will not download for Parseh in the background — turn on Automatic ' +
                  'downloads for this site in Chrome’s Site settings.';
  /* A RECORDING BIG ENOUGH TO BE CAUGHT HALFWAY.  The fixture's are seconds of
     tone, gone in a blink on this machine, and a keep can only be cancelled,
     stopped or reloaded in its middle if it HAS a middle.  Under the 256 MiB a
     single answer may weigh in an incognito profile's background download. */
  const BIG = 'big.wav', BIG_BYTES = 200 * 1000 * 1000, BIG_URL = BOOK + 'audio/big.wav';
  { const f = await Deno.open(AUDIO + BIG, {write: true, create: true, truncate: true});
    await f.truncate(BIG_BYTES); f.close(); }
  // and what the computer says of the book now, with it among the recordings
  const made = await (await fetch(EN + '__offline')).json();
  const TITLE = made.title, FA_TITLE = (await (await fetch(FA + '__offline')).json()).title;
  // a toast waited for, and when it does not come, the toasts there were: "nothing was changed" in place of a refusal
  // says that the press did not do what it was meant to (a timeout of twenty seconds says only that nothing came)
  const toastedSaying = async (page, line, timeout) => {
    try { return await toasted(page, line, timeout); }
    catch (e) {
      const seen = await page.evaluate(() => ({log: window.__toastLog || [], now: (document.getElementById('parseh-toast') || {}).textContent,
                                               button: (document.querySelector('.kp-keep') || {}).textContent, at: Math.round(performance.now())})).catch(x => String(x));
      throw Error(e.message.split('\n')[0] + ' -- toasts seen: ' + JSON.stringify(seen));
    }
  };
  const stopHub = () => Deno.kill(hub.pid, 'SIGSTOP');
  const goHub = () => Deno.kill(hub.pid, 'SIGCONT');
  async function phone(ctx) {
    ctx = ctx || await browser.newContext(PHONE);
    const page = await ctx.newPage();
    page.on('pageerror', e => { errors.push('background: ' + e.message); console.log('PAGE ERROR background', e.message); });
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
    await watchWay(page);
    await page.addInitScript(() => {                    // every toast the page shows, and when (see toastedSaying)
      window.__toastLog = [];
      const hook = () => {
        const t = document.getElementById('parseh-toast');
        if (!t) { setTimeout(hook, 20); return; }
        new MutationObserver(() => window.__toastLog.push([Math.round(performance.now()), t.textContent]))
          .observe(t, {childList: true, characterData: true, subtree: true});
      };
      hook();
    });
    return page;
  }
  async function open(page, url) {
    await page.goto(url);
    await setMode(page, 'mobile');
    await page.reload();
    // (a minute for each: a browser that has just been started, as step j's is, on a computer with a hundred other things
    // to do, takes longer than twenty seconds to bring a page and its worker up)
    await page.waitForFunction(() => !!window.ParsehKeep, null, {timeout: 60000});
    if (!(await page.evaluate(() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)))) {
      await page.waitForFunction(() => navigator.serviceWorker.ready, null, {timeout: 60000}).catch(() => {});
      await page.reload();
      await page.waitForFunction(() => navigator.serviceWorker.controller, null, {timeout: 60000});
    }
    await answerPlace(page);
  }
  async function sheet(page) {
    await reveal(page);
    await gearOpen(page, 'interface');
    await page.waitForFunction(() => { const b = document.querySelector('.kp-keep'); return !!b && !b.disabled; },
                               null, {timeout: 30000});
    await tap(page, '.kp-keep');
    await page.waitForSelector('.kp-sheet');
    // A BOOK ALREADY KEPT: the sheet looks at what is on the phone file by file ("Looking at what is on this phone, file
    // by file…") and ticks the boxes by what it finds, undoing a tick made before it has answered -- which a person's
    // finger never beats and a test's does (a Save then says "nothing was changed")
    await page.waitForFunction(() => !/^Looking at what is on this phone/.test((document.querySelector('.kp-check') || {}).textContent || ''),
                               null, {timeout: 60000});
  }
  // exactly these recordings ticked, by file name; the notes' row as it is
  const pick = (page, names) => page.evaluate(names => {
    for (const b of document.querySelectorAll('.kp-row input')) {
      if (!b.value) continue;
      if (b.checked !== names.some(n => b.value.endsWith('/' + n))) b.click();
    }
  }, names);
  // Keep it (or Save); and if the room is asked about, what it says
  async function press(page, anyway = true) {
    await page.locator('.kp-go').click();
    await page.waitForFunction(() => !document.querySelector('.kp-sheet') || !!document.querySelector('.kp-room'),
                               null, {timeout: 15000});
    const room = await page.$('.kp-room') ? await page.textContent('.kp-room') : '';
    if (room && anyway) await page.locator('.kp-go').click();
    return room;
  }
  const button = page => page.evaluate(() => (document.querySelector('.kp-keep') || {}).textContent || '');
  const entry = (page, id = HERE) => page.evaluate(id => {
    try { return JSON.parse(localStorage.getItem('parseh_kept') || '{}')[id] || null; } catch (e) { return null; }
  }, id);
  const downloads = page => page.evaluate(async () => {
    const r = await navigator.serviceWorker.getRegistration();
    const out = [];
    for (const id of await r.backgroundFetch.getIds()) {
      const g = await r.backgroundFetch.get(id);
      if (g) out.push({id, part: id.split(':')[2], downloaded: g.downloaded, total: g.downloadTotal});
    }
    return out;
  });
  // what the notification's Cancel does: the download's own abort
  const cancel = (page, part) => page.evaluate(async part => {
    const r = await navigator.serviceWorker.getRegistration();
    for (const id of await r.backgroundFetch.getIds())
      if (id.split(':')[2] === part) { const g = await r.backgroundFetch.get(id); if (g) return g.abort(); }
    return false;
  }, part);
  const inCache = (page, name, url) => page.evaluate(async ([name, url]) => {
    if (!(await caches.has(name))) return -1;
    const r = await (await caches.open(name)).match(url, {ignoreVary: true});
    return r ? (await r.blob()).size : -1;
  }, [name, url]);
  const toasted = (page, line, timeout = 90000) => page.waitForFunction(
    t => ((document.getElementById('parseh-toast') || {}).textContent || '') === t, line, {timeout});
  /* HELD IN ITS MIDDLE.  The computer is stopped, then let go for a few
     milliseconds at a time, until some of `part` has come and not all of it;
     it is left STOPPED -- its socket open and saying nothing, as a phone's
     computer does when it sleeps. */
  async function midway(page, part, open_ = 12, shut = 80) {
    stopHub();
    let last = null, looks = 0, ever = 0;
    const trail = [], began = Date.now();
    for (const t = Date.now(); Date.now() - t < 120000;) {
      last = await downloads(page); looks++;
      const d = last.find(x => x.part === part);
      if (d && d.downloaded > 0 && (!d.total || d.downloaded < d.total)) return d.downloaded;
      if (last.length && !ever) ever = Date.now() - began;
      if (trail.length < 12 && (d || last.length)) trail.push([Date.now() - began, last.map(x => [x.part, x.downloaded, x.total])]);
      goHub(); await sleep(open_); stopHub(); await sleep(shut);
    }
    goHub();
    const kept = await inCache(page, 'parseh-kept-' + HERE, BIG_URL).catch(() => 'err');
    const btn = await button(page).catch(() => 'err');
    throw Error('FAIL: the ' + part + ' download could not be caught halfway: ' + JSON.stringify(last) + ' after ' + looks +
                ' looks; something listed first after ' + ever + ' ms; seen ' + JSON.stringify(trail) +
                '; the big file in the phone\'s cache: ' + kept + '; the button says ' + JSON.stringify(btn));
  }
  async function hubAgain() {
    hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                                stdout: 'piped', stderr: 'piped'}).spawn();
    hubUp = true;
    for (const st of [hub.stdout, hub.stderr])
      (async () => { for await (const c of st.pipeThrough(new TextDecoderStream())) log.push(c); })();
    for (const t = Date.now();;) {
      try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
      if (Date.now() - t > 60000) throw Error('the hub did not start again');
      await sleep(250);
    }
  }

  // MOBILE_BG_ONLY=a,j runs those scenarios alone (they are lettered below)
  const ONLY = (Deno.env.get('MOBILE_BG_ONLY') || '').split(',').filter(Boolean);
  const only = k => !ONLY.length || ONLY.includes(k);
  try {
    // ---- a) THE PAGE CLOSED, THE WORKER STOPPED, AND IT STILL ARRIVES -- the
    // whole point of the background way -- written down by the next page
    // that opens, which says its line once, at its foot
    if (only('a')) {
      const page = await phone();
      const ctx = page.context();
      await open(page, EN);
      await sheet(page);
      await pick(page, ['part1.mp3']);
      // TWO TAPS AT ONCE, as a thumb makes them: the phone is asked about its
      // room between them, and a second keep of the same book used to start
      await page.evaluate(() => { const g = document.querySelector('.kp-go'); g.click(); g.click(); });
      await page.waitForFunction(() => !document.querySelector('.kp-sheet'), null, {timeout: 15000});
      // the browser waits a few seconds before a first download's first ask
      await page.waitForFunction(w => (document.querySelector('.kp-keep') || {}).textContent.endsWith(w),
                                 LEAVE, {timeout: 5000});
      assert(/^Keeping… \d+% — you can leave this page$/.test(await button(page)),
             'the button says the keep is going and that the page may be left: ' +
             JSON.stringify(await button(page)));
      stopHub();
      const two = await downloads(page);
      eq([two.map(d => d.part).sort(), new Set(two.map(d => d.id.split(':')[1])).size], [['rec', 'text'], 1],
         'two downloads, the text and then the recording, both handed to the browser -- and ' +
         'one keep only, for two taps');
      await page.close();
      const blank = await ctx.newPage();
      const cdp = await ctx.newCDPSession(blank);
      await cdp.send('ServiceWorker.enable');
      await cdp.send('ServiceWorker.stopAllWorkers');
      goHub();
      await blank.goto(B + '/manifest.webmanifest');
      await until(blank, async () => {
        if (!(await caches.has('parseh-jobs'))) return false;
        return (await (await caches.open('parseh-jobs')).keys()).some(k => /\/end$/.test(new URL(k.url).pathname));
      }, null, 120000, 500);
      eq(await blank.evaluate(() => localStorage.getItem('parseh_kept')), null,
         'it came with no page open and the worker stopped: put away by a worker woken for it, ' +
         'and not yet written down, since no page has opened');
      const shared = (made.shared || []).map(x => x.url).find(u => /^\/lib\//.test(u));
      eq([await inCache(blank, 'parseh-shared', shared) > 0, await inCache(blank, 'parseh-kept-' + HERE, shared),
          await inCache(blank, 'parseh-kept-' + HERE, HERE) > 0],
         [true, -1, true],
         'and each file went where it belongs: the toolbox\'s own in the shared cache (' + shared +
         '), the book\'s in its own');
      await setMode(blank, 'mobile');
      await blank.goto(B + '/');
      await blank.waitForSelector('.kp-news .kp-newsline', {timeout: 20000});
      eq(await blank.textContent('.kp-news .kp-newsline'), TITLE + ' is on this phone now',
         'the next page opened says it, at its foot');
      const e = await entry(blank);
      eq([!!e, e && e.version === made.version, e && e.media.includes(BOOK + 'audio/part1.mp3'),
          await blank.evaluate(async () => (await (await caches.open('parseh-jobs')).keys()).length)],
         [true, true, true, 0],
         'and writes it down as the press would have: its version, its recording; no note left behind');
      await blank.reload();
      await sleep(2500);
      eq(await blank.$('.kp-news'), null, 'once: the page opened after it says nothing');
      await open(blank, EN);
      assert((await button(blank)).startsWith('Change what is kept'), 'the book\'s own page: it is kept');
      await ctx.close();
    }

    // ---- b) CANCEL BEFORE ANYTHING HAD COME: the whole keep stops -- both
    // downloads -- and nothing is written down (the owner's two answers)
    if (only('b')) {
      const page = await phone();
      await open(page, EN);
      await sheet(page);
      await pick(page, ['part1.mp3']);
      await press(page);
      stopHub();
      for (const t = Date.now(); ; await sleep(100)) {
        const d = await downloads(page);
        if (d.map(x => x.part).sort().join() === 'rec,text') break;
        if (Date.now() - t > 20000) { goHub(); throw Error('FAIL: the two downloads were never handed over: ' + JSON.stringify(d)); }
      }
      assert(await cancel(page, 'text'), 'the text\'s download was there to cancel, as on its notification');
      goHub();
      await toasted(page, TITLE + ': stopped from the notification — nothing of it had come yet');
      assert(true, 'Cancel on the text\'s notification before a byte had come: "' + TITLE +
             ': stopped from the notification — nothing of it had come yet"');
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      eq([(await button(page)).startsWith('Keep on this phone'), await entry(page), (await downloads(page)).length,
          await page.evaluate(id => caches.has('parseh-kept-' + id), HERE)],
         [true, null, 0, false],
         'both downloads stopped, nothing written down, no empty cache left, and the button offers to keep it');
      await page.context().close();
    }

    // ---- c) CANCEL AFTER THE TEXT HAD COME: what arrived is kept
    if (only('c')) {
      const page = await phone();
      await open(page, EN);
      await sheet(page);
      await pick(page, [BIG]);
      await press(page);
      const had = await midway(page, 'rec');
      await cancel(page, 'rec');
      goHub();
      await toasted(page, TITLE + ': stopped from the notification — what had come is on this phone');
      assert(true, 'Cancel on the recordings\' notification with ' + had + ' bytes of it come: "' + TITLE +
             ': stopped from the notification — what had come is on this phone"');
      const e = await entry(page);
      eq([!!e, await inCache(page, 'parseh-kept-' + HERE, HERE) > 0, await inCache(page, 'parseh-kept-' + HERE, BIG_URL)],
         [true, true, -1],
         'the text is kept and written down; the recording that had not finished is not on the phone');
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      await sheet(page);
      eq(await page.evaluate(u => { const b = [...document.querySelectorAll('.kp-row input')].find(x => x.value === u);
                                    return b ? b.checked : null; }, BIG_URL),
         false, 'and Change what is kept shows that recording unticked, to fetch when he likes');
      await page.locator('.kp-no').click();
      await page.context().close();
    }

    // ---- d) A FILE THE COMPUTER NO LONGER HAS, said as that
    if (only('d')) {
      const page = await phone();
      await open(page, EN);
      await sheet(page);
      await pick(page, ['slow.wav']);
      await Deno.rename(AUDIO + 'slow.wav', AUDIO + 'slow.wav.away');
      try {
        await press(page);
        await toasted(page, TITLE + ': 1 of its files is no longer on the computer');
      } finally {
        await Deno.rename(AUDIO + 'slow.wav.away', AUDIO + 'slow.wav');
      }
      assert(true, 'a recording taken off the computer after the list was made: "' + TITLE +
             ': 1 of its files is no longer on the computer"');
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      eq([!!(await entry(page)), (await button(page)).startsWith('Change what is kept')], [true, true],
         'and the rest is kept, as he chose: what arrived stays');
      await page.context().close();
    }

    // ---- e) NO ROOM ON THE PHONE, said in its own words: the room made
    // really short (CDP's quota for the site, which the browser enforces on
    // the download and on the cache alike), and a recording twice too big
    if (only('e')) {
      const page = await phone();
      await open(page, EN);
      const usage = await page.evaluate(async () => (await navigator.storage.estimate()).usage || 0);
      await page.touch.send('Storage.overrideQuotaForOrigin', {origin: B, quotaSize: usage + 100 * 1000 * 1000});
      await sheet(page);
      await pick(page, [BIG]);
      await press(page);
      await toasted(page, TITLE + ': no room on this phone for 1 of its files');
      assert(true, 'a recording the phone has no room for: "' + TITLE + ': no room on this phone for 1 of its files"');
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      eq([!!(await entry(page)), await inCache(page, 'parseh-kept-' + HERE, HERE) > 0,
          await inCache(page, 'parseh-kept-' + HERE, BIG_URL)], [true, true, -1],
         'the text is kept; the recording that had no room is not');
      await page.touch.send('Storage.overrideQuotaForOrigin', {origin: B});
      await page.context().close();
    }
    /* ---- e2) AND THE SHEET ASKS BEFORE IT STARTS.  The warning reads the
       browser's own report of the room (navigator.storage.estimate), and no
       switch this suite has makes that report small -- CDP's quota is enforced
       but not reported.  So here, and only here, the REPORT is made small, in
       this one context, before its pages load; everything after it is the
       page's own path, and the keep then really runs to the end. */
    if (only('e2')) {
      const ctx = await browser.newContext(PHONE);
      await ctx.addInitScript(() => {
        if (navigator.storage)
          navigator.storage.estimate = () => Promise.resolve({usage: 0, quota: 300 * 1000 * 1000});
      });
      const page = await phone(ctx);
      await open(page, EN);
      await sheet(page);
      await pick(page, [BIG]);
      const room = await press(page, false);
      assert(/^Needs about [\d.]+ MB free while it arrives; this phone has 300 MB$/.test(room),
             'with the browser reporting 300 MB, the sheet says so before anything is fetched: "' + room + '"');
      eq(await page.textContent('.kp-go'), 'Keep it anyway', 'and the press then reads Keep it anyway');
      await page.locator('.kp-go').click();
      await toasted(page, TITLE + ' is on this phone now', 180000);
      assert(true, 'pressed anyway, it goes ahead and arrives');
      await ctx.close();
    }

    // ---- f) A SECOND BOOK WHILE THE FIRST IS COMING: it waits and says so;
    // and the first, with the computer gone quiet, says it is waiting for it
    if (only('f')) {
      const ctx = await browser.newContext(PHONE);
      const a = await phone(ctx), b = await phone(ctx);
      await open(a, EN);
      await open(b, FA);
      await sheet(a);
      await pick(a, [BIG]);
      await sheet(b);
      await press(a);
      await midway(a, 'rec');
      await press(b);
      await b.waitForFunction(w => (document.querySelector('.kp-keep') || {}).textContent === w,
                              'Waiting for ' + TITLE + LEAVE, {timeout: 20000});
      assert(true, 'the second book waits behind the first and says so: "Waiting for ' + TITLE + LEAVE + '"');
      // silence is offline only once three asks across 45 s have gone
      // unanswered (TO-DO §2.24, the owner's window): the line follows that
      await a.waitForFunction(() => /^Keeping… \d+% — waiting for the computer$/
                                .test((document.querySelector('.kp-keep') || {}).textContent),
                              null, {timeout: 75000});
      assert(true, 'and the first, with the computer silent, says what it is waiting for: ' +
             JSON.stringify(await button(a)));
      goHub();
      await a.waitForFunction(u => { try { return (JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname] || {}).media.includes(u); } catch (e) { return false; } },
                              BIG_URL, {timeout: 120000});
      await b.waitForFunction(() => { try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; } catch (e) { return false; } },
                              null, {timeout: 120000});
      eq(await inCache(a, 'parseh-kept-' + HERE, BIG_URL), BIG_BYTES,
         'the computer answering again, the first carries on where it was and arrives whole');
      assert(!!(await entry(b, MADE.readers.fa)), 'and the second, which waited, is kept after it (' + FA_TITLE + ')');
      await ctx.close();
    }

    // ---- g) A PAGE RELOADED WHILE ITS BOOK IS COMING takes the keep up where
    // it is -- here a Save on a kept book, reloaded with the computer silent
    if (only('g')) {
      const page = await phone();
      await open(page, EN);
      await sheet(page);
      await pick(page, []);
      await press(page);
      await page.waitForFunction(() => { try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; } catch (e) { return false; } },
                                 null, {timeout: 120000});
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      await sheet(page);
      await pick(page, [BIG]);
      await press(page);
      await midway(page, 'rec');
      await page.reload();
      // a refresh asks afresh, and silence takes the owner's 45 s to be
      // believed (TO-DO §2.24)
      await page.waitForFunction(() => /^Keeping… \d+% — waiting for the computer$/
                                   .test((document.querySelector('.kp-keep') || {}).textContent),
                                 null, {timeout: 75000});
      assert(true, 'reloaded from the phone\'s copy with the computer silent, the page takes the keep up: ' +
             JSON.stringify(await button(page)));
      goHub();
      await page.waitForSelector('.kp-news .kp-newsline', {timeout: 120000});
      eq(await page.textContent('.kp-news .kp-newsline'), TITLE + ' is on this phone now',
         'and when it arrives, that page writes it down and says so');
      eq([(await entry(page)).media.includes(BIG_URL), await inCache(page, 'parseh-kept-' + HERE, BIG_URL)],
         [true, BIG_BYTES], 'the recording is written down, and on the phone whole');
      await page.context().close();
    }

    // ---- h) KEPT ON THIS PHONE, WHILE IT IS COMING: "coming — N%", and Stop
    if (only('h')) {
      const ctx = await browser.newContext(PHONE);
      const page = await phone(ctx);
      await open(page, EN);
      await sheet(page);
      await pick(page, [BIG]);
      await press(page);
      await midway(page, 'rec');
      await page.close();
      const list = await phone(ctx);
      await list.goto(B + '/m/kept/');
      await list.waitForFunction(() => /^coming — \d+%$/.test((document.querySelector('.m-coming') || {}).textContent || ''),
                                 null, {timeout: 30000});
      const row = await list.evaluate(() => {
        const c = document.querySelector('.m-coming').closest('.m-kept');
        return {coming: document.querySelector('.m-coming').textContent,
                stop: !!c.querySelector('.m-keptstop'),
                remove: [...c.querySelectorAll('.m-keptoff')].filter(b => !b.classList.contains('m-keptstop')).length};
      });
      assert(/^coming — \d+%$/.test(row.coming) && row.stop && row.remove === 0,
             'Kept on this phone lists the book still coming, with Stop in place of Remove: ' + JSON.stringify(row));
      await tap(list, '.m-keptstop');
      goHub();
      await list.waitForSelector('.m-keptnews', {timeout: 60000});
      eq(await list.textContent('.m-keptnews'), TITLE + ': stopped on this phone — what had come is on this phone',
         'Stop does what Cancel does, and says it was stopped here');
      eq([await list.$('.m-coming'), !!(await list.$('.m-keptoff:not(.m-keptstop)')),
          await inCache(list, 'parseh-kept-' + HERE, BIG_URL)],
         [null, true, -1],
         'and the list is drawn again: the book kept, with Remove; the recording not on the phone');
      await ctx.close();
    }

    // ---- i) CHROME REFUSES: said plainly, and nothing is fetched
    if (only('i')) {
      const page = await phone();
      const info = await page.touch.send('Target.getTargetInfo');
      const bcdp = await browser.newBrowserCDPSession();
      await bcdp.send('Browser.setPermission', {permission: {name: 'background-fetch'}, setting: 'denied',
                                                origin: B, browserContextId: info.targetInfo.browserContextId});
      await open(page, EN);
      await sheet(page);
      await pick(page, ['part1.mp3']);
      await press(page);
      await toastedSaying(page, REFUSED, 20000);
      assert(true, 'the browser refuses the background download: "' + REFUSED + '"');
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      eq([await entry(page), (await downloads(page)).length, (await button(page)).startsWith('Keep on this phone')],
         [null, 0, true], 'and nothing is fetched or written down');
      await page.context().close();
    }

    // ---- i2) A SAVE THE BROWSER REFUSES FREES NOTHING: whether it will go is
    // asked before what he unticked is given back
    if (only('i2')) {
      const page = await phone();
      await open(page, EN);
      await sheet(page);
      await pick(page, ['part1.mp3']);
      await press(page);
      await page.waitForFunction(() => { try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; } catch (e) { return false; } },
                                 null, {timeout: 120000});
      await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
      const P1 = BOOK + 'audio/part1.mp3';
      const had = await inCache(page, 'parseh-kept-' + HERE, P1);
      const info = await page.touch.send('Target.getTargetInfo');
      const bcdp = await browser.newBrowserCDPSession();
      await bcdp.send('Browser.setPermission', {permission: {name: 'background-fetch'}, setting: 'denied',
                                                origin: B, browserContextId: info.targetInfo.browserContextId});
      await sheet(page);
      await pick(page, ['slow.wav']);                  // part1 unticked, slow.wav ticked
      page.once('dialog', d => d.accept());            // "Give back … ?" -- yes
      await press(page);
      await toastedSaying(page, REFUSED, 20000);
      eq([had > 0, await inCache(page, 'parseh-kept-' + HERE, P1) === had,
          (await entry(page)).media.includes(P1)], [true, true, true],
         'refused, the Save gave nothing back: the unticked recording is still on the phone and written down');
      await page.context().close();
    }

    // ---- k) TWO TABS, ONE BOOK: a sheet opened before the other tab pressed
    // takes that keep up, and says it was already coming (the owner, 2026-09-24)
    if (only('k')) {
      const ctx = await browser.newContext(PHONE);
      const a = await phone(ctx), b = await phone(ctx);
      await open(a, EN);
      await open(b, EN);
      await sheet(b);                                   // opened first, left open
      await pick(b, ['slow.wav']);
      await sheet(a);
      await pick(a, ['part1.mp3']);
      await press(a);
      stopHub();
      try {
        for (const t = Date.now(); ; await sleep(100)) {
          if ((await downloads(a)).length) break;
          if (Date.now() - t > 20000) throw Error('FAIL: the first tab\'s keep never started');
        }
        await press(b);
      } finally { goHub(); }
      await toasted(b, TITLE + ' was already coming onto this phone — change what is kept once it is in', 120000);
      assert(true, 'the second tab took up the keep already coming and said so: "' + TITLE +
             ' was already coming onto this phone — change what is kept once it is in"');
      const e = await entry(b);
      eq([e && e.media.includes(BOOK + 'audio/part1.mp3'), e && e.media.includes(BOOK + 'audio/slow.wav'),
          await inCache(b, 'parseh-kept-' + HERE, BOOK + 'audio/slow.wav')], [true, false, -1],
         'and what is written down is what that keep brought, not the second tab\'s own pick');
      await ctx.close();
    }

    // ---- j) THE PHONE'S OWN PROFILE: the computer killed and started again in
    // the middle, and the download carries on and arrives whole.  An
    // incognito profile -- every other test here -- never resumes a download;
    // a phone's does, and this is the one place the suite can show it.
    if (only('j')) {
      const dir = await Deno.makeTempDir({prefix: 'parseh-bg-profile-'});
      // THE PROFILE KEEPS THE 200 MB RECORDING, and a copy of it while it comes.  A temporary folder without that room
      // fails further down as "got -1 want 200000000", which reads as a fault of Parseh; on a tmpfs /tmp that is filling
      // up it is the folder (docs/releasing.md, "Before you start": TMPDIR on the main disk)
      const df = await new Deno.Command('df', {args: ['-Pk', dir], stdout: 'piped', stderr: 'null'}).output().catch(() => null);
      const room = df ? Math.floor(+td.decode(df.stdout).trim().split('\n').pop().split(/\s+/)[3] / 1024) : NaN;
      if (room < 800) {
        await Deno.remove(dir, {recursive: true}).catch(() => {});
        throw Error('FAIL: step j keeps a 200 MB recording in a browser profile under ' + dir + ' and needs about 800 MB free there; ' +
                    'it has ' + room + ' MB. Set TMPDIR to a folder on a disk with room (docs/releasing.md, "Before you start").');
      }
      const ctx = await chromium.launchPersistentContext(dir, {executablePath: Deno.env.get('CHROME_BIN'),
                                                               headless: true, ...PHONE});
      try {
        const page = await phone(ctx);
        await open(page, EN);
        // the text first, as a person keeps it.  A computer's Chrome, freshly
        // started, holds its first background download until its first page
        // goes idle or a minute has passed (Chromium's startup hold, desktop
        // only; driven: ~60 s), so this first keep may take that long, and the
        // page waits it out -- a download not started yet is never called a
        // refusal (the owner, 2026-09-23)
        await sheet(page);
        await pick(page, []);
        await press(page);
        await page.waitForFunction(() => { try { return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname]; } catch (e) { return false; } },
                                   null, {timeout: 180000});
        await page.waitForFunction(() => !(document.querySelector('.kp-keep') || {}).disabled);
        await sheet(page);
        await pick(page, [BIG]);
        await press(page);
        // a phone's own profile says how far it has got twice a second, so the
        // computer is let go for moments short enough to be seen halfway
        const had = await midway(page, 'rec', 2, 300);
        goHub();
        hub.kill('SIGKILL');
        await hub.status;
        hubUp = false;
        await sleep(10000);
        await hubAgain();
        await page.waitForFunction(u => { try { return (JSON.parse(localStorage.getItem('parseh_kept') || '{}')[location.pathname] || {}).media.includes(u); } catch (e) { return false; } },
                                   BIG_URL, {timeout: 300000, polling: 1000});
        eq(await inCache(page, 'parseh-kept-' + HERE, BIG_URL), BIG_BYTES,
           'the computer killed with ' + had + ' bytes come, and started again ten seconds later: ' +
           'the phone\'s own profile carries on and the recording arrives whole');
      } finally {
        await ctx.close();
        await Deno.remove(dir, {recursive: true}).catch(() => {});
      }
    }
  } finally {
    try { goHub(); } catch (_) { /* not stopped */ }
    await Deno.remove(AUDIO + BIG).catch(() => {});
  }
}

async function partApp() {
  console.log('\n== the mobile interface as an app');
  const page = await newPage(PHONE, 'app');
  const cdp = await page.context().newCDPSession(page);
  // WHAT THE PAGE SAYS WHILE THE APP GETS READY, written down from the first
  // paint onwards.  The line is meant to be SEEN, and a test that went to
  // look for it whenever it got round to looking would be timing the network
  // rather than reading the page: every word the slot ever shows is kept, so
  // a warming that is over in half a second is still read.  The worker's own
  // "that list is done" is kept beside it, which is what everything below
  // waits on instead of a sleep.
  await page.addInitScript(() => {
    window.__warmLines = [];
    window.__warmDone = {};
    const look = () => {
      const s = document.querySelector('[data-parseh-warm]');
      if (!s) return;
      const said = s.hidden ? '' : (s.textContent || '');
      const lines = window.__warmLines;
      if (said !== lines[lines.length - 1]) lines.push(said);
    };
    const watch = () => {
      if (!document.documentElement) { setTimeout(watch, 0); return; }
      new MutationObserver(look).observe(document.documentElement,
        {subtree: true, childList: true, characterData: true, attributes: true});
      look();
    };
    watch();
    addEventListener('DOMContentLoaded', look);
    if (navigator.serviceWorker)
      navigator.serviceWorker.addEventListener('message', e => {
        const d = e.data || {};
        if (d.warmed && d.warmed.what) window.__warmDone[d.warmed.what] = d.warmed;
      });
  });
  // ---- a) the app's own address
  await page.goto(B + '/?mode=mobile#top');
  eq(await page.evaluate(() => [document.documentElement.dataset.mode, localStorage.getItem('parseh_mode'),
                                location.pathname + location.search + location.hash]),
     ['mobile', 'mobile', '/#top'], '/?mode=mobile: the mobile mode, and the address given back without it');
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  eq(await page.evaluate(() => !!navigator.serviceWorker.controller), true, 'the worker takes the pages over');
  const man = await cdp.send('Page.getAppManifest');
  eq([new URL(man.url).pathname, man.errors], ['/manifest.webmanifest', []], 'the manifest, read without an error');

  // ---- a2) THE APP GETS ITSELF READY AFTERWARDS, AND SAYS SO (TO-DO §0,
  // the third block of 2026-09-23, and the owner's own words: "I want the
  // warming not to be silent").  The worker's install event no longer fetches
  // the way in -- fifty-nine addresses and three and a quarter megabytes,
  // which left it installing for minutes over a tunnel and which is a state
  // Chrome will not install a site from.  The page asks for it once it is up,
  // and the hub -- the one place a person is certain to be standing while it
  // happens -- counts them.  NOTHING HERE ASKS THE WORKER FOR ANYTHING: this
  // is the app's own doing, watched.
  const shell = await (await fetch(B + '/__shell')).json();
  const wayIn = shell.pages.length + shell.apis.length + shell.files.length;
  await page.waitForFunction(() => window.__warmDone['way-in'], null, {timeout: 180000});
  const warmed = await page.evaluate(() => ({done: window.__warmDone['way-in'],
                                             lines: window.__warmLines.slice()}));
  eq(warmed.done.of, wayIn,
     `the app asks for the way in by itself and settles all ${wayIn} of its addresses`);
  const counting = warmed.lines.filter(t => /^Getting ready — \d+ of \d+$/.test(t));
  assert(counting.length > 0 && counting.every(t => t.endsWith(' of ' + wayIn)),
         'and it is not silent about it: the page counts them as they come — ' +
         JSON.stringify([counting[0], counting[counting.length - 1]]));
  // and then says nothing at all: the hub is opened a dozen times a day on a
  // phone that has been ready for a week
  await page.waitForFunction(() => {
    const s = document.querySelector('[data-parseh-warm]');
    return s && s.hidden;
  }, null, {timeout: 30000});
  const lines = await page.evaluate(() => window.__warmLines.slice());
  eq(lines[lines.length - 1], '', 'and says nothing once the app is ready: the hub\'s line goes');

  // AND WHERE IT SAYS IT (the owner's 1, 2026-09-23: "the getting ready text
  // appears above and hence even when things are already downloaded for a
  // moment moves all the buttons and then vanishes; move the getting ready
  // text at the end of the page so that this doesn't happen anymore").  It is
  // at the FOOT now, under the last door, so it can come and go without
  // moving anything a thumb is already reaching for.  Shown by hand here --
  // the same two lines warmPaint writes -- because the warming above is long
  // over, and a phone that has everything already is exactly the case he was
  // complaining about.
  const moved = await page.evaluate(() => {
    const doors = [...document.querySelectorAll('.hub-mobile .m-door')];
    const was = doors.map(d => Math.round(d.getBoundingClientRect().top));
    const s = document.querySelector('[data-parseh-warm]');
    s.textContent = 'Getting ready — 3 of 46';
    s.hidden = false;
    const now = doors.map(d => Math.round(d.getBoundingClientRect().top));
    const below = Math.round(s.getBoundingClientRect().top -
                             doors[doors.length - 1].getBoundingClientRect().bottom);
    const drawn = s.getClientRects().length > 0;
    s.hidden = true;
    s.textContent = '';
    return {doors: doors.length, was: was, now: now, below: below, drawn: drawn};
  });
  assert(moved.doors > 2 && moved.drawn &&
         JSON.stringify(moved.was) === JSON.stringify(moved.now),
         'the line appearing moves not one door: ' +
         JSON.stringify({was: moved.was.slice(0, 3), now: moved.now.slice(0, 3)}));
  assert(moved.below >= 0,
         'because it stands at the foot, under the last door (' + moved.below + 'px below it)');

  // AND NOT ONE FACE OF THE STUDIO'S (his decision 3).  A phone that has only
  // installed the app has the way in and nothing else: the thirteen faces are
  // 1.83 MB that only a studio page needs, and they wait to be asked for.
  const cold = await page.evaluate(us => Promise.all(us.map(u => caches.match(u).then(r => !!r))),
                                   shell.later);
  eq(cold.filter(Boolean).length, 0,
     `and the studio's ${shell.later.length} faces are on no phone that has only installed the app`);

  for (const [where, url] of [['the hub', '/'], ['the shelf', '/m/books/'], ['a reader', MADE.readers.fa],
                              ['the decks', '/exercises/']]) {
    await page.goto(B + url);
    await page.waitForLoadState('load');
    await sleep(300);
    const why = (await cdp.send('Page.getInstallabilityErrors')).installabilityErrors.map(e => e.errorId);
    // a test's browser is incognito, which Chromium never installs from:
    // nothing else may stand in the way
    eq(why, ['in-incognito'], `${where}: installable, as far as a page can make it so`);
  }
  eq(await page.evaluate(() => [...document.querySelectorAll('link[rel=manifest]')].length), 1,
     'the decks name the manifest once');

  // ---- a3) AND THE FACES COME WHEN A NOTE IS OPENED, which is the other
  // half of the promise: they are not fetched by an app that has only been
  // installed, and they ARE fetched the moment something wants them.  Opened
  // as a person opens one -- a tap on the mark in the seam, which is what
  // lib/keep.js listens for -- and not by asking the worker here.
  const NOTES = B + MADE.readers.en.replace(/reader\/$/, 'notes');
  await page.goto(B + MADE.readers.en);
  await answerPlace(page);
  if (!(await page.evaluate(() => document.querySelectorAll('.gap .mark').length))) {
    // the offline part writes three notes into this book before this one
    // runs; asked for alone (MOBILE_PARTS=app), this writes its own, so that
    // neither part waits on the other
    await writeNotes(page, NOTES, 'en', [NOTES_TO_WRITE[0]]);
    await page.reload();
    await answerPlace(page);
  }
  await page.waitForFunction(() => document.querySelectorAll('.gap .mark').length >= 1,
                             null, {timeout: 30000});
  const asked = page.waitForFunction(() => window.__warmDone.studio, null, {timeout: 180000});
  await page.locator('.gap .mark').first().evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(250);
  await tap(page, '.gap .mark');
  await asked;
  const faces = await page.evaluate(() => window.__warmDone.studio);
  eq(faces.of, shell.later.length,
     `a note opened asks for the studio's faces, all ${shell.later.length} of them`);
  const held = await page.evaluate(us => Promise.all(us.map(u => caches.match(u).then(r => !!r))),
                                   shell.later);
  eq(held.filter(Boolean).length, shell.later.length,
     'and the phone has every one of them — fetched after the app was installed, not during it');
  await page.keyboard.press('Escape');

  // ---- b) the install page, and the hub's door to it
  await page.goto(B + '/');
  assert(await isDrawn(page, '.hub-mobile a.m-appdoor[href="/m/install/"]'), 'the hub has the door to installing it');
  await Promise.all([page.waitForURL(B + '/m/install/'), tap(page, '.hub-mobile a.m-appdoor')]);
  await page.waitForFunction(() => /trusts/.test(document.querySelector('#m-appnow').textContent));
  assert(/This phone trusts Parseh/.test(await page.locator('#m-appnow').textContent()),
         'the install page: this phone trusts Parseh (here, the computer itself)');
  assert(!(await isDrawn(page, 'a[href$="parseh-ca.crt"]')), 'and no certificate to hand over over plain http');
  // AND THE PAGE THAT ASKS HIM TO STAY SAYS WHEN THE WAITING IS OVER.  Its
  // slot says `stay`, so the line does not go out at the very moment it is
  // ready -- everywhere else it does, but here it would be answering the
  // waiting with nothing.
  await page.waitForFunction(() => {
    const s = document.querySelector('[data-parseh-warm]');
    return s && !s.hidden && /^Ready:/.test(s.textContent || '');
  }, null, {timeout: 180000});
  assert(true, 'the install page, which asks him to stay until the app is ready, says when it is');
  await shot(page, 'install');
  // ---- c) the server away
  hub.kill('SIGTERM');
  await hub.status;
  hubUp = false;
  await page.goto(B + '/m/books/').catch(() => {});
  await sleep(600);
  // THE USUAL PAGE, NOT AN APOLOGY (the owner's 2, 2026-09-23).  The shelf is
  // part of the way in and is installed with the app, so with the computer
  // stopped it opens from the phone's own copy -- where, before, the app put
  // up "Parseh cannot be reached" and a reader with a book kept on the phone
  // could not get at it.  What the browser would have shown here without a
  // worker is its own error page, which is why this is asked at all.
  const said = await page.evaluate(() => [location.pathname, document.querySelector('h1') &&
    document.querySelector('h1').textContent]).catch(() => [page.url(), 'the browser\'s own error page']);
  eq(said, ['/m/books/', 'Books'],
     'the server stopped: the shelf opens from the phone, at its own address');
  // and a page that is neither kept nor part of the way in is what /m/offline/
  // is left for
  await page.goto(B + '/books/persian/mini-fa/reader/').catch(() => {});
  await sleep(600);
  eq(await page.evaluate(() => document.querySelector('h1') &&
                               document.querySelector('h1').textContent)
       .catch(() => 'the browser\'s own error page'),
     'Parseh cannot be reached',
     'while a book that was never kept says so, in Parseh\'s own words');
  await shot(page, 'offline');
  await page.context().close();
}

// ======== Parseh updated on the computer: the app's half (TO-DO §13.16) ========
/* THE PHONE MEETS TWO PARSEHS.  Everything else in this file meets one; the
   owner's promise about an update is about the moment the phone meets the
   next.  A book and a video are kept from the first release, the hub is
   stopped, and it comes back as ANOTHER RELEASE: another version in its
   Server header and in the worker it serves (PARSEH_TEST_VERSION,
   tests/mobile_harness.py), and two of lib/'s shared scripts changed as a
   release changes them -- parseh.js, which the reader loads, and
   mobileplayer.js, which a reader never does, so one copy is renewed by the
   visit and the other is not.  What he asked for, each driven here:

     - the app takes the new worker by itself, and SAYS in one line that
       Parseh was updated -- never a silent swap, and nothing reloaded;
     - activate keeps `parseh-kept-*` and `parseh-shared`;
     - `renew` mends the shared copy on the next online visit -- every copy
       of it, the way in's too;
     - the keep check calls what Parseh changed "updated", writes down the
       digest the copy really has, fetches nothing for it, and never calls it
       "no longer whole" -- while a copy that really is broken is still caught
       and mended;
     - the kept book and video still open with the computer away. */
async function partUpdate() {
  console.log('\n== Parseh updated on the computer: the app is told, and keeps what it kept');
  const BOOK = MADE.readers.hi, VID = `/youtube/v/${MADE.video}/`;
  const LIBDIR = `${WORK}/root/lib`;
  const CHANGED = ['parseh.js', 'mobileplayer.js'];
  const PJS = '/lib/parseh.js', MPJ = '/lib/mobileplayer.js';
  async function hubAs(version) {
    if (hubUp) { hub.kill('SIGTERM'); await hub.status; hubUp = false; }
    hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                                env: version ? {PARSEH_TEST_VERSION: version} : {},
                                stdout: 'piped', stderr: 'piped'}).spawn();
    hubUp = true;
    for (const st of [hub.stdout, hub.stderr])
      (async () => { for await (const c of st.pipeThrough(new TextDecoderStream())) log.push(c); })();
    for (const t = Date.now();;) {
      try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
      if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join('').slice(-2000));
      await sleep(250);
    }
  }
  async function hubDown() {
    if (!hubUp) return;
    hub.kill('SIGTERM');
    await hub.status;
    hubUp = false;
    for (let i = 0; i < 40; i++) {
      try { const r = await fetch(B + '/', {cache: 'no-store'}); await r.body?.cancel(); await sleep(250); }
      catch (_) { break; }
    }
  }
  // what the hub says it is, twice: in its Server header, and in its worker
  const says = async () => {
    const r = await fetch(B + '/sw.js');
    const js = await r.text();
    return {server: (r.headers.get('server') || '').split(' ')[0], js,
            release: (/const RELEASE = "([^"]*)";/.exec(js) || [])[1] || null,
            build: (/const BUILD = "([^"]*)";/.exec(js) || [])[1]};
  };
  const digestOf = (rec, url) => ([].concat(rec.small || [], rec.shared || [], rec.media || [])
    .find(x => x.url === url) || {}).digest || '';
  async function open(page, url) {
    await page.goto(B + url);
    await setMode(page, 'mobile');
    await page.reload();
    // (a minute for each: a browser that has just been started, as step j's is, on a computer with a hundred other things
    // to do, takes longer than twenty seconds to bring a page and its worker up)
    await page.waitForFunction(() => !!window.ParsehKeep, null, {timeout: 60000});
    if (!(await page.evaluate(() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)))) {
      await page.waitForFunction(() => navigator.serviceWorker.ready, null, {timeout: 60000}).catch(() => {});
      await page.reload();
      await page.waitForFunction(() => navigator.serviceWorker.controller, null, {timeout: 60000});
    }
    await answerPlace(page);
  }
  async function sheet(page) {
    await page.waitForFunction(() => !document.documentElement.hasAttribute('data-parseh-away'),
                               null, {timeout: 30000});
    await reveal(page);
    // the Keep buttons live in the last group of the gear's sheet wherever the page has a gear (a book's reader and
    // a video's page, a0.5.0): brought into the sheet while it is up; under ⋯ where the page has none
    if (await page.evaluate(() => document.documentElement.classList.contains('pg-reader'))) await gearOpen(page, 'interface');
    else if (await page.$('button.pg-gear')) {
      if (!(await page.evaluate(() => ParsehGear.mounted().isOpen()))) await tap(page, 'button.pg-gear');
    } else if ((await page.getAttribute('.m-rmore', 'aria-expanded')) !== 'true') await tap(page, '.m-rmore');
    await page.waitForFunction(() => { const b = document.querySelector('.kp-keep'); return !!b && !b.disabled; },
                               null, {timeout: 60000});
    await tap(page, '.kp-keep');
    await page.waitForSelector('.kp-sheet');
    // A BOOK ALREADY KEPT: the sheet looks at what is on the phone file by file ("Looking at what is on this phone, file
    // by file…") and ticks the boxes by what it finds, undoing a tick made before it has answered -- which a person's
    // finger never beats and a test's does (a Save then says "nothing was changed")
    await page.waitForFunction(() => !/^Looking at what is on this phone/.test((document.querySelector('.kp-check') || {}).textContent || ''),
                               null, {timeout: 60000});
  }
  // Keep it, or Save; and where the phone's room is asked about, anyway
  async function press(page) {
    await page.locator('.kp-go').click();
    await page.waitForFunction(() => !document.querySelector('.kp-sheet') || !!document.querySelector('.kp-room'),
                               null, {timeout: 15000});
    if (await page.$('.kp-room')) await page.locator('.kp-go').click();
  }
  const kept = (page, id) => until(page, id => {
    try {
      const b = document.querySelector('.kp-keep');
      return !!JSON.parse(localStorage.getItem('parseh_kept') || '{}')[id] && !!b && !b.disabled;
    } catch (e) { return false; }
  }, id, 180000);
  // the sheet's own verdict, once the worker has looked file by file
  async function looked(page) {
    await page.waitForFunction(() => {
      const c = document.querySelector('.kp-check');
      return !!c && !/Looking at/.test(c.textContent);
    }, null, {timeout: 60000});
    return page.evaluate(() => ({line: document.querySelector('.kp-check').textContent,
                                 sum: (document.querySelector('.kp-sum') || {}).textContent || '',
                                 torn: document.querySelectorAll('.kp-row.kp-torn').length}));
  }
  // one copy on the phone: its bytes' digest, the digest written on it, and
  // how it ends (the changed release's scripts end with a line saying so)
  const copy = (page, url, name = 'parseh-shared') => page.evaluate(async ([url, name]) => {
    if (!(await caches.has(name))) return null;
    const r = await (await caches.open(name)).match(url, {ignoreVary: true});
    if (!r) return null;
    const body = await r.arrayBuffer();
    const sum = [...new Uint8Array(await crypto.subtle.digest('SHA-256', body))]
      .map(b => b.toString(16).padStart(2, '0')).join('');
    return {sum, kept: r.headers.get('x-parseh-kept-digest') || '', bytes: body.byteLength,
            tail: new TextDecoder().decode(body.slice(-80))};
  }, [url, name]);
  const cachesNow = page => page.evaluate(async () => {
    const out = {};
    for (const k of await caches.keys()) out[k] = (await (await caches.open(k)).keys()).length;
    return out;
  });
  // what the tab has said, and which pages it loaded and how, across pages
  const tab = page => page.evaluate(() => {
    const read = k => { try { return JSON.parse(sessionStorage.getItem(k) || '[]'); } catch (e) { return []; } };
    return {said: read('__said').filter(s => /^Parseh (was updated|went back)/.test(s)), docs: read('__docs')};
  });
  // the worker in charge, asked what it is
  const inCharge = page => page.evaluate(() => new Promise(ok => {
    const sw = navigator.serviceWorker;
    const hear = e => { if (e.data && e.data.release) { sw.removeEventListener('message', hear); ok(e.data.release); } };
    sw.addEventListener('message', hear);
    sw.controller.postMessage({release: 1});
    setTimeout(() => ok(null), 10000);
  }));

  // ---- a) THE FIRST RELEASE, as the checkout is
  await hubAs(null);
  const was = await says();
  const source = await Deno.readTextFile('lib/sw.js');
  assert(was.release && was.server === 'Parseh/' + was.release,
         'the hub serves its worker stamped with its own release, the one its Server header names: ' +
         JSON.stringify([was.server, was.release]));
  eq(was.js, source.replace("'__PARSEH_RELEASE__'", JSON.stringify(was.release))
                   .replace("'__PARSEH_BUILD__'", JSON.stringify(was.build)),
     'and the worker is lib/sw.js with those two strings written in, and not a byte else');
  const NEXT = was.release.replace(/\d+$/, n => String(+n + 1));
  const MARK = `// ${NEXT}: changed by this release`;

  const ctx = await browser.newContext(PHONE);
  // EVERY LINE THE PAGE SAYS, written down as it appears: a toast is gone in
  // seconds, and a test that looked for it whenever it got round to looking
  // would be timing the worker rather than reading the page.  AND EVERY PAGE
  // THAT LOADS, with how it was loaded.  Both are kept in the tab's
  // sessionStorage as well, so that they outlive the page they happened on:
  // the new worker may take over whichever page is open when it comes, and
  // a reload nobody asked for is exactly what must be seen if it happens.
  await ctx.addInitScript(() => {
    const read = k => { try { return JSON.parse(sessionStorage.getItem(k) || '[]'); } catch (e) { return []; } };
    const keep = (k, v) => { try { const a = read(k); a.push(v); sessionStorage.setItem(k, JSON.stringify(a)); } catch (e) {} };
    try {
      const n = performance.getEntriesByType('navigation')[0];
      if (location.protocol === 'http:' && window.top === window)
        keep('__docs', [location.pathname, n ? n.type : '?']);
    } catch (e) { /* a page with no storage: nothing to write down */ }
    window.__said = [];
    const look = () => {
      const t = document.getElementById('parseh-toast');
      const now = [t && t.classList.contains('show') ? t.textContent : '']
        .concat([...document.querySelectorAll('.kp-updated')].map(e => e.textContent));
      for (const s of now)
        if (s && window.__said[window.__said.length - 1] !== s) { window.__said.push(s); keep('__said', s); }
    };
    const watch = () => {
      if (!document.documentElement) { setTimeout(watch, 0); return; }
      new MutationObserver(look).observe(document.documentElement,
        {subtree: true, childList: true, characterData: true, attributes: true});
    };
    watch();
  });
  // a window of the app: its pages share the phone's worker, caches and
  // localStorage, and each window has its own sessionStorage
  const windowOf = async () => {
    const p = await ctx.newPage();
    p.on('pageerror', e => { errors.push('update: ' + e.message); console.log('PAGE ERROR update', e.message); });
    p.touch = await ctx.newCDPSession(p);
    await p.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
    return p;
  };
  let page = await windowOf();
  try {
    await open(page, BOOK);
    // A FIRST INSTALL IS NOT AN UPDATE: the phone writes down which release
    // it met, and says nothing
    const first = await until(page, () => localStorage.getItem('parseh_release'), null, 30000);
    eq([first, (await tab(page)).said],
       [was.release + (was.build ? '+' + was.build : ''), []],
       'installing the app, the phone notes the release it met and announces nothing');

    // ---- b) a book and a video kept, with the way in warmed behind them
    await sheet(page);
    await press(page);
    await kept(page, BOOK);
    await open(page, VID);
    await sheet(page);
    await press(page);
    await kept(page, VID);
    const warmed = await page.evaluate(() => new Promise((ok, no) => {
      const sw = navigator.serviceWorker;
      const heard = e => {
        const d = e.data || {};
        if (!d.warmed || d.warmed.what !== 'way-in') return;
        sw.removeEventListener('message', heard);
        ok(d.warmed);
      };
      sw.addEventListener('message', heard);
      sw.controller.postMessage({warm: 'way-in'});
      setTimeout(() => no(new Error('the way in was never warmed')), 180000);
    }));
    assert(warmed.of > 10, 'a book and a video kept on the phone, and the way in warmed: ' + warmed.of);
    const before = await cachesNow(page);
    assert(before['parseh-kept-' + BOOK] > 0 && before['parseh-kept-' + VID] > 0 && before['parseh-shared'] > 0,
           'each in a cache of its own, the shared files in one for both: ' + JSON.stringify(before));
    const rec1 = await (await fetch(B + BOOK + '__offline')).json();
    const old = {pjs: digestOf(rec1, PJS), mpj: digestOf(rec1, MPJ)};
    const kp = {pjs: await copy(page, PJS), mpj: await copy(page, MPJ)};
    // THE DIGEST EACH FILE WAS KEPT WITH IS WRITTEN ON THE COPY (lib/sw.js,
    // `stamped`): what the computer said the file was, and the copy is it
    eq([kp.pjs.kept, kp.pjs.sum, kp.mpj.kept, kp.mpj.sum], [old.pjs, old.pjs, old.mpj, old.mpj],
       'each kept copy carries the digest the computer gave it, and its bytes are that file');
    await open(page, BOOK);
    await sheet(page);
    const calm = await looked(page);
    eq([calm.line, calm.torn], ['Looked at file by file: what is ticked is whole on this phone.', 0],
       'before any update the keep check finds the book whole and says nothing more');
    await page.locator('.kp-no').click();

    // ---- c) THE NEXT RELEASE: another version, and two shared scripts
    // changed.  The tree's lib/ becomes a folder of its own -- every entry a
    // link to the checkout's, but the two, which are copies with a line more.
    // The app is CLOSED first, as a phone's is overnight, and opened again
    // in a new window once the computer has been updated: a page left open on
    // the old release would be the one the new worker takes over, and the
    // line would be said there -- right, and not what this part reads -- and
    // the first page of each opening of the app is where it asks for a new
    // worker (lib/keep.js, releaseCheck)
    await page.close();
    page = await windowOf();
    const loadsBefore = 0;
    await hubDown();
    const real = await Deno.realPath(LIBDIR);
    await Deno.remove(LIBDIR);                   // the link, and nothing it points at
    await Deno.mkdir(LIBDIR);
    for await (const e of Deno.readDir(real)) {
      if (CHANGED.includes(e.name))
        await Deno.writeTextFile(`${LIBDIR}/${e.name}`,
                                 (await Deno.readTextFile(`${real}/${e.name}`)) + '\n' + MARK + '\n');
      else await Deno.symlink(`${real}/${e.name}`, `${LIBDIR}/${e.name}`);
    }
    try {
      await hubAs(NEXT);
      const now = await says();
      eq([now.server, now.release], ['Parseh/' + NEXT, NEXT],
         'the computer is another release now, and says so in its Server header and in its worker');
      const rec2 = await (await fetch(B + BOOK + '__offline')).json();
      const neu = {pjs: digestOf(rec2, PJS), mpj: digestOf(rec2, MPJ)};
      assert(neu.pjs && neu.mpj && neu.pjs !== old.pjs && neu.mpj !== old.mpj,
             'and its digests for the two changed scripts have moved');

      // ---- d) THE APP REACHES THE COMPUTER: a new worker, and one line
      await page.goto(B + BOOK);
      // WITHIN A MINUTE OR SO: the page asks for the new worker as soon as it
      // finds the computer (lib/keep.js, releaseCheck), and Chromium holds an
      // update back until a minute after the last one it made (driven: the
      // same ask on a registration a minute old installed in 0.3 s)
      const told = await until(page, () => {
        try {
          return JSON.parse(sessionStorage.getItem('__said') || '[]')
            .find(s => /^Parseh (was updated|went back)/.test(s)) || null;
        } catch (e) { return null; }
      }, null, 150000).catch(async e => {
        // what the phone was doing instead, so that a failure says why
        console.log('the phone, when no line came:', JSON.stringify(await page.evaluate(async () => {
          const r = await navigator.serviceWorker.getRegistration();
          const url = w => (w ? w.state : null);
          return {active: url(r && r.active), waiting: url(r && r.waiting), installing: url(r && r.installing),
                  controlled: !!navigator.serviceWorker.controller, seen: localStorage.getItem('parseh_release'),
                  said: window.__said, mode: document.documentElement.dataset.mode};
        })), JSON.stringify(await inCharge(page)));
        throw e;
      });
      eq(told, 'Parseh was updated to ' + NEXT,
         'the app took the new worker by itself, and says so in one line');
      await shot(page, 'update-line');
      const since = (await tab(page)).docs.slice(loadsBefore);
      eq([since, (await tab(page)).said.length], [[[BOOK, 'navigate']], 1],
         'and nothing was reloaded under the thumb: the one page opened is the one that says it, once');
      const boss = await inCharge(page);
      eq([boss && boss.version, boss && boss.replaced, boss && boss.previous], [NEXT, true, was.release],
         'the worker in charge is the new release\'s, and knows which one it replaced');
      const after = await cachesNow(page);
      const keptKeys = o => Object.keys(o).filter(k => k.startsWith('parseh-kept-')).sort();
      eq(keptKeys(after), keptKeys(before), 'every parseh-kept-* cache survived the new worker');
      eq(keptKeys(after).map(k => after[k]), keptKeys(before).map(k => before[k]),
         'with every file it held');
      assert(after['parseh-shared'] >= before['parseh-shared'],
             'and parseh-shared with them (' + before['parseh-shared'] + ' → ' + after['parseh-shared'] + ')');

      // ---- e) RENEW MENDS THE SHARED COPY ON THIS VERY VISIT -- every copy
      // of it, the way in's as well as the one kept for the book
      const mended = await until(page, async ([url, mark]) => {
        const r = await (await caches.open('parseh-shared')).match(url, {ignoreVary: true});
        return r && (await r.clone().text()).includes(mark) ? true : null;
      }, [PJS, MARK], 60000);
      const pjsNow = await copy(page, PJS);
      eq([mended, pjsNow.sum, pjsNow.kept], [true, neu.pjs, neu.pjs],
         'the reader\'s visit brought the new parseh.js into parseh-shared, its digest written on it');
      const shellPjs = await until(page, async ([url, mark]) => {
        const r = await (await caches.open('parseh-shell-1')).match(url, {ignoreVary: true});
        return r && (await r.clone().text()).includes(mark) ? true : null;
      }, [PJS, MARK], 30000);
      eq(shellPjs, true, 'and into the way in\'s copy too: every cache that held it, not the first found');
      const mpjNow = await copy(page, MPJ);
      eq([mpjNow.tail.includes(MARK), mpjNow.sum, mpjNow.kept], [false, old.mpj, old.mpj],
         'while mobileplayer.js, which no reader loads, is still the copy it was kept as');

      // ---- f) THE KEEP CHECK AFTER THE UPDATE.  parseh.js's copy is given
      // back the digest it was KEPT with -- as a copy renewed by a worker
      // that did not write digests down would be -- so that the check's own
      // refreshing is what is seen, and not renew's
      await page.evaluate(async ([url, was]) => {
        const c = await caches.open('parseh-shared');
        const r = await c.match(url, {ignoreVary: true});
        const head = new Headers(r.headers);
        head.set('X-Parseh-Kept-Digest', was);
        await c.put(url, new Response(await r.arrayBuffer(), {status: r.status, statusText: r.statusText,
                                                              headers: head}));
      }, [PJS, old.pjs]);
      await sheet(page);
      const check = await looked(page);
      await shot(page, 'update-keep-check');
      assert(/^Looked at file by file: what is ticked is whole on this phone\. 2 of its files were updated on the computer since they were kept/.test(check.line) &&
             check.torn === 0 && !/no longer whole/.test(check.line),
             'the keep check calls the two scripts Parseh changed "updated", and not one file ' +
             '"no longer whole": ' + JSON.stringify(check.line));
      eq(check.sum, 'Nothing to change: what is ticked is whole on this phone.',
         'and Save would fetch nothing for them');
      await page.locator('.kp-no').click();
      const pjsRec = await copy(page, PJS), mpjRec = await copy(page, MPJ);
      eq([pjsRec.kept, pjsRec.sum], [neu.pjs, neu.pjs],
         'the copy that already was the new file has its RECORDED digest refreshed to it');
      eq([mpjRec.kept, mpjRec.sum, mpjRec.tail.includes(MARK)], [old.mpj, old.mpj, false],
         'and the one that was not is left as it is — nothing was downloaded again for it');

      // ---- g) AND A COPY THAT REALLY IS BROKEN IS STILL CAUGHT.  One byte of
      // the kept mobileplayer.js turned over, its size and its headers kept,
      // so it matches neither the digest it was kept with nor the computer's
      const torn = await page.evaluate(async (url) => {
        const c = await caches.open('parseh-shared');
        const r = await c.match(url, {ignoreVary: true});
        const body = new Uint8Array(await r.arrayBuffer());
        const at = Math.floor(body.length / 2);
        body[at] ^= 0xff;
        await c.put(url, new Response(body, {status: r.status, statusText: r.statusText,
                                             headers: new Headers(r.headers)}));
        return body.length;
      }, MPJ);
      assert(torn > 1000, 'a kept script damaged on the phone, byte for byte the same size');
      await sheet(page);
      const bad = await looked(page);
      assert(/^One file kept here is no longer whole\./.test(bad.line) && !/updated/.test(bad.line),
             'the keep check catches it, among the files an update changed: ' + JSON.stringify(bad.line));
      await press(page);
      const fixed = await until(page, async ([url, mark]) => {
        const r = await (await caches.open('parseh-shared')).match(url, {ignoreVary: true});
        return r && (await r.clone().text()).includes(mark) ? true : null;
      }, [MPJ, MARK], 120000);
      const mpjFixed = await copy(page, MPJ);
      eq([fixed, mpjFixed.sum, mpjFixed.kept], [true, neu.mpj, neu.mpj],
         'and Save fetches it again, the new release\'s, with its digest written on it');
      await kept(page, BOOK);

      // ---- h) SAID ONCE: the next page opened knows it was said
      await page.goto(B + VID);
      await page.waitForFunction(() => document.querySelectorAll('#segs .seg').length > 0, null, {timeout: 30000});
      await sleep(3000);
      eq([await page.evaluate(() => window.__said.filter(s => /Parseh (was updated|went back)/.test(s))),
          (await tab(page)).said.length, await page.evaluate(() => localStorage.getItem('parseh_release'))],
         [[], 1, NEXT], 'the next page opened says nothing: the phone has written down that it was said');
      await sheet(page);
      const vid = await looked(page);
      assert(vid.torn === 0 && !/no longer whole/.test(vid.line),
             'and the video\'s keep check finds nothing broken either: ' + JSON.stringify(vid.line));
      await page.locator('.kp-no').click();

      // ---- i) THE KEPT THINGS STILL OPEN WITH THE COMPUTER AWAY
      await hubDown();
      await page.goto(B + BOOK, {timeout: 30000});
      await page.waitForFunction(() => typeof SUBS !== 'undefined', null, {timeout: 30000});
      assert(await page.evaluate(() => document.querySelectorAll('.sub').length > 0),
             'with the computer stopped after the update, the kept book opens, its text there');
      await page.goto(B + VID, {timeout: 30000});
      await page.waitForFunction(() => document.querySelectorAll('#segs .seg').length > 0, null, {timeout: 30000});
      assert(true, 'and so does the kept video, its captions drawn');
      await shot(page, 'after-update-offline');
    } finally {
      // the tree's lib/ goes back to being the link it was
      await Deno.remove(LIBDIR, {recursive: true}).catch(() => {});
      await Deno.symlink(real, LIBDIR).catch(() => {});
    }
  } finally {
    await ctx.close();
  }
}

try {
  if (PARTS.includes('shelf')) await partShelf();
  if (PARTS.includes('reader')) await partReader();
  if (PARTS.includes('touch')) await partTouch();
  if (PARTS.includes('prefs')) await partPrefs();
  if (PARTS.includes('video')) await partVideo();
  if (PARTS.includes('studio')) await partStudio();
  if (PARTS.includes('export')) await partExport();
  if (PARTS.includes('drawings')) await partDrawings();
  if (PARTS.includes('decks')) await partDecks();
  // last: it stops the server
  if (PARTS.includes('offline')) await partOffline();
  if (PARTS.includes('checkout')) await partCheckout();
  if (PARTS.includes('background')) await partBackground();
  if (PARTS.includes('app')) await partApp();
  // after everything: it restarts the hub as another release
  if (PARTS.includes('update')) await partUpdate();
} finally {
  await browser.close();
  if (hubUp) { hub.kill('SIGTERM'); await hub.status; }
  await Deno.remove(WORK, {recursive: true}).catch(() => {});
}
if (errors.length) { console.log('\npage errors:\n  ' + errors.join('\n  ')); Deno.exit(1); }
console.log(`\n${passed} passed`);

// AND THE OTHER WAY, AS ON THE IPAD: the keeping parts again, in a browser with
// no background download at all.  Its own run -- a fresh toolbox and a fresh
// hub, because these parts read first-time server state -- started only after
// this one has closed its browser and stopped its hub, so the two never run at
// once.  Asked for by hand (MOBILE_KEEP_WAY set), a run is one way only.
const AGAIN = PARTS.filter(p => p === 'offline' || p === 'checkout');
if (!Deno.env.get('MOBILE_KEEP_WAY') && AGAIN.length) {
  console.log('\n== the same keeping, the iPad\'s way: ' + AGAIN.join(','));
  const env = {MOBILE_KEEP_WAY: 'worker', MOBILE_PARTS: AGAIN.join(',')};
  const child = await new Deno.Command(Deno.execPath(), {
    args: ['run', '--allow-all', import.meta.url], cwd: root, env,
    stdout: 'inherit', stderr: 'inherit'}).output();
  if (!child.success) Deno.exit(1);
}
