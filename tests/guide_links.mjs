// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
import { gearOpen } from './gear_driver.mjs';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/guide_links.mjs
// A LINK TO THE GUIDE FROM EVERY DOOR (TO-DO §15.10, lib/guidelink.js).  The
// REAL hub (serve.main, booted by tests/mobile_harness.py over a temporary
// tree with books, a video and exercise decks) is opened door by door, on a
// computer's screen in the browser interface and on a phone in the mobile one,
// and each door must show a guide link a person can see and press -- on the
// page's own page of the guide, a page this Parseh's /guide/ really serves.
// A phone's bar has no room for it: on the mobile layout it is a line at the
// foot of the page, scrolled to.  Where a phone's door keeps its one line of
// header for a thumb (the reader, the player, studying and cramming a deck),
// the link is in the gear's sheet, and the sheet is opened to find it.  Screenshots go to $SHOTS when it is set.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const WORK = await Deno.makeTempDir({prefix: 'parseh-guide-links-'});
const built = await new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'build', WORK], cwd: root,
                                          stdout: 'piped', stderr: 'piped'}).output();
if (!built.success) throw Error(td.decode(built.stderr) || td.decode(built.stdout));
const MADE = JSON.parse(td.decode(built.stdout).trim().split('\n').pop());
const l = Deno.listen({hostname: '127.0.0.1', port: 0});
const port = l.addr.port;
l.close();
const log = [];
const hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                                  stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}

const deck = MADE.decks.en;
const D = `/exercises/deck/${deck.folder}/${deck.slug}`;
// every door, and the page of the guide it must point at (null: the one it already had)
const DOORS = [
  ['the book library', '/books/', 'books/library.html'],
  ['a reader (English)', MADE.readers.en, 'books/reader.html', 'gear'],
  ['a reader (Persian, right to left)', MADE.readers.fa, 'books/reader.html', 'gear'],
  ['a reader (Japanese)', MADE.readers.ja, 'books/reader.html', 'gear'],
  ['adding a book', '/books/add/', 'books/adding.html'],
  ['the video index', '/youtube/', 'videos/finding-a-video.html'],
  ['the player', `/youtube/v/${MADE.video}/`, 'videos/the-player.html', 'gear'],
  ['adding a video', '/youtube/add/', 'videos/adding-a-video.html'],
  ['the phone shelf of books', '/m/books/', 'getting-started/mobile-mode.html'],
  ['the phone shelf of videos', '/m/videos/', 'getting-started/mobile-mode.html'],
  ['the studio library', '/studio/', 'studio/library.html'],
  ['the studio prompt', '/studio/prompt', 'studio/llm-prompt.html'],
  ['the studio editor', '/studio/new', 'studio/editor.html'],
  ['the exercise decks', '/exercises/', 'exercises/decks-page.html'],
  ['a deck', D + '/', 'exercises/deck-page.html'],
  ['studying a deck', D + '/study', 'exercises/studying.html', 'gear'],
  ['cramming a deck', D + '/cram', 'exercises/cram.html', 'gear'],
  ['the Anki page', '/anki/sync/', 'cards-and-anki/card-store.html'],
  // the doors that had one: kept, and now on the phone's bar as well
  ['Settings', '/settings/', null],
  ['Review later', '/later/', null],
];

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN')});
const errors = [];
const SITES = new Map();
async function served(href) {
  const path = href.split('#')[0];
  if (!SITES.has(path)) {
    const r = await fetch(B + path);
    const body = await r.text();
    SITES.set(path, r.ok && /<html/i.test(body));
  }
  return SITES.get(path);
}
// the guide links a person can see on the page as it is drawn
const seen = page => page.evaluate(() => [...document.querySelectorAll('a[href^="/guide"]')]
  .filter(a => { const r = a.getBoundingClientRect();
                 return r.width > 0 && r.height > 0 && getComputedStyle(a).visibility !== 'hidden' &&
                        r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; })
  .map(a => { const bar = a.closest('.parseh-bar, header');
               // the control it was put before (◐, or Stop): one of the bar's own
               const th = a.nextElementSibling || (bar && bar.querySelector('[data-parseh-theme], .m-theme'));
               return {href: a.getAttribute('href'), text: a.textContent.trim(), w: a.getBoundingClientRect().width,
                       h: a.getBoundingClientRect().height, th: th ? th.getBoundingClientRect().height : 0}; }));

for (const [tag, opts, mode] of [
  ['computer', {viewport: {width: 1280, height: 800}}, 'browser'],
  ['phone', {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}, 'mobile']]) {
  console.log(`-- ${tag}, the ${mode} interface`);
  const ctx = await browser.newContext(opts);
  await ctx.addInitScript(m => {
    try { localStorage.setItem('parseh_mode', m); } catch (_) {}
    document.cookie = 'parseh_mode=' + m + '; Path=/; SameSite=Lax';
  }, mode);
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(tag + ' ' + page.url() + ': ' + e.message));
  for (const [name, url, want, phoneWhere] of DOORS) {
    const r = await page.goto(B + url, {waitUntil: 'load'});
    assert(r && r.ok(), `${tag}: ${name} (${url}) opens`);
    // the link comes with the page's scripts (lib/guidelink.js, loaded by lib/parseh.js or by its own tag)
    let links = [];
    for (const t = Date.now(); Date.now() - t < 8000; await sleep(100)) {
      // a reader asks where to go when it opens on a device that has not read the book (§4.9)
      const stay = await page.$('.pf-bar .pf-stay');
      if (stay) await stay.click().catch(() => {});
      links = await seen(page);
      if (links.length || await page.evaluate(ph => !!(window.ParsehGuide && ((ph && document.querySelector('[data-parseh-gear]')) ||
                                                    document.querySelector('.px-guide-end a'))), tag === 'phone'))
        break;
    }
    // THE PHONE'S BAR HAS NO ROOM: its line at the foot of the page, scrolled to as a thumb does
    // (the /m/ pages wear the phone's bar alone, on a computer too)
    let foot = false;
    if (!links.length && phoneWhere !== 'gear' && await page.$('.px-guide-end a')) {
      await sleep(600);              // what the page draws after it loads must not take the line away
      await page.locator('.px-guide-end a').scrollIntoViewIfNeeded();
      await sleep(200);
      links = (await seen(page)).filter(a => a.text === 'The guide to this page');
      foot = true;
    }
    if (tag === 'phone' && phoneWhere === 'gear' && !links.length) {
      await gearOpen(page);
      await sleep(300);
      // at the foot of the sheet's list, under Parseh's settings: scrolled to, as a thumb does
      await page.locator('.pg-panel .px-guide-foot').scrollIntoViewIfNeeded().catch(() => {});
      await sleep(200);
      links = (await seen(page)).filter(a => a.text === 'The guide to this page');
      assert(links.length === 1, `${tag}: ${name}: the gear's sheet has "The guide to this page"`);
    }
    if (SHOTS) {
      await Deno.mkdir(SHOTS, {recursive: true});
      await page.screenshot({path: `${SHOTS}/${tag}-${name.replace(/\W+/g, '-')}.png`});
    }
    assert(links.length >= 1, `${tag}: ${name}: a guide link is drawn (${JSON.stringify(links.map(a => a.href))})`);
    const a = links[0];
    if (want) assert(links.some(x => x.href === '/guide/site/' + want),
                     `${tag}: ${name}: it opens the guide's page for it, ${want}`);
    assert(await served(a.href), `${tag}: ${name}: ${a.href} is a page this Parseh serves`);
    // as tall as the bar's own button beside it: a phone's bar is made for a finger, and the link is too
    if (foot) assert(a.h >= 44, `${tag}: ${name}: a finger finds the line at the foot (${Math.round(a.w)}×${Math.round(a.h)} px)`);
    else if (phoneWhere !== 'gear' || tag === 'computer')
      assert(a.h >= a.th - 1, `${tag}: ${name}: as easy to press as the bar's own button beside it (${Math.round(a.w)}×${Math.round(a.h)} px, beside ${Math.round(a.th)})`);
    // and no bar wears two
    const twice = await page.evaluate(() => [...document.querySelectorAll('.parseh-bar, header.topbar, header.m-topbar, body > header')]
      .filter(b => b.querySelectorAll('a[href^="/guide"]').length > 1).length);
    assert(twice === 0, `${tag}: ${name}: no bar has two guide links`);
  }
  // the hub is left as it was: the link it had, and nothing added beside it
  await page.goto(B + '/', {waitUntil: 'load'});
  await sleep(800);
  const added = await page.evaluate(() => document.querySelectorAll('.px-guide, .px-guide-end').length);
  assert(added === 0, `${tag}: the hub keeps its own guide links and gains none`);
  await ctx.close();
}
await browser.close();
hub.kill();
await hub.status;
await Deno.remove(WORK, {recursive: true}).catch(() => {});
if (errors.length) throw Error('page errors:\n' + errors.join('\n'));
console.log(`guide_links: ${passed} checks passed`);
