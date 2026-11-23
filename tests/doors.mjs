// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
import { Buffer } from 'node:buffer';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/doors.mjs
// Everything from the page and nothing from a terminal: two doors that used
// to want one.  The panel that takes a bundle back answers a book with a
// button that builds it -- the build job followed to its end, the reader
// offered when it is done -- where it used to hand over a ./build.sh to copy.
// And the book reader writes the way the video player does, with no mode to
// turn on first: the cloud's pencil in hover mode, a pencil over the chunk
// under the pointer everywhere else (over the chunk last tapped, on a touch
// screen), E for either -- and a click on the chunk itself still what it was.
// Every request either page makes is answered here; the reader is a copy of
// the English fixture edition, built.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-doors-'});
const td = new TextDecoder();
async function py(code, ...args) {
  const o = await new Deno.Command(PY, {args: ['-c', code, ...args], stdout: 'piped', stderr: 'piped'}).output();
  if (!o.success) throw Error(td.decode(o.stderr) || td.decode(o.stdout));
  return td.decode(o.stdout);
}
const assert = (v, m) => { if (!v) throw Error(m); };
const eq = (got, want, m) => {
  if (JSON.stringify(got) !== JSON.stringify(want))
    throw Error(m + ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 15000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('timed out: ' + what);
    await sleep(50);
  }
}
const MIME = {html: 'text/html', js: 'text/javascript', css: 'text/css', json: 'application/json'};
async function file(route, path) {
  let body;
  try { body = await Deno.readTextFile(path); }
  catch (_) { return route.fulfill({status: 404, body: 'no such file'}); }
  return route.fulfill({body, contentType: MIME[path.split('.').pop()] || 'application/octet-stream'});
}

// the panel as make_index.py writes it, in the library page's own shell
const PANEL = await py(String.raw`
import sys
sys.path.insert(0, 'lib')
import make_index
sys.stdout.write(make_index.bundle_panel('book', '/books/__upload'))
`);
const LIBRARY = '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
  '<link rel="stylesheet" href="/lib/parseh.css"><script src="/lib/parseh.js"></script>' +
  '</head><body class="index"><main>' + PANEL + '</main></body></html>';
// the answers are written here, so all the panel needs is a file to send
const ZIP = {name: 'momotaro-book.zip', mimeType: 'application/zip',
             buffer: Buffer.from([0x50, 0x4b, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])};

// the English fixture edition, copied and built
await py(String.raw`
import os, shutil, subprocess, sys
d = os.path.join(sys.argv[1], 'mini-en')
shutil.copytree('tests/fixtures/books/english/mini-en', d,
                ignore=shutil.ignore_patterns('reader', '.reader-key'))
subprocess.run([sys.executable, 'lib/tex2html.py', '--book', d], check=True, capture_output=True)
`, TMP);
const READER = `http://parseh.test${TMP}/mini-en/reader/index.html`;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
const errors = [];
try {
// ======== bringing a book back ========
{
  const page = await browser.newPage();
  page.on('pageerror', e => { errors.push('panel: ' + e.message); console.log('PAGE ERROR', e.message); });
  let KIND = 'book', ENDS = 'done', polls = 0;
  const builds = [];
  const answer = () => KIND === 'book'
    ? {ok: true, kind: 'book', language: 'ja', gloss: 'en', audio: 'text', name: 'momotaro', folder: 'japanese',
       dir: 'books/japanese/momotaro', files: ['book.json', 'main.tex', 'ch1.tex'], bytes: 4096, dropped: [],
       replaced: null, kept: [], notes: []}
    : {ok: true, kind: 'video', language: 'ja', gloss: 'en', audio: null, name: 'aB3dE5fG7hI', folder: 'japanese',
       dir: 'youtube/videos/japanese/aB3dE5fG7hI', files: ['video.json'], bytes: 512, dropped: [],
       replaced: null, kept: [], notes: []};
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname;
    if (url.hostname !== 'parseh.test') return route.abort();
    if (p === '/books/') return route.fulfill({body: LIBRARY, contentType: 'text/html'});
    if (p === '/books/__upload') return route.fulfill({json: answer()});
    if (p === '/books/japanese/momotaro/__build') {
      builds.push(req.postDataJSON()); polls = 0;
      return route.fulfill({json: {ok: true, state: 'running', what: 'pdf', log: []}});
    }
    if (p === '/books/japanese/momotaro/__build/status') {
      if (++polls < 2)
        return route.fulfill({json: {ok: true, state: 'running', what: 'pdf', log: ['== momotaro', '   pdf: 19 pages']}});
      return route.fulfill({json: ENDS === 'done'
        ? {ok: true, state: 'done', what: 'pdf', code: 0, log: ['== momotaro', 'books/index.html  1 book']}
        : {ok: true, state: 'failed', what: 'pdf', code: 1, log: ['! Undefined control sequence.', '   PDF FAILED']}});
    }
    return file(route, root + decodeURIComponent(p));
  });
  const bringBack = async () => {
    await page.goto('http://parseh.test/books/');
    await page.setInputFiles('#takefile', ZIP);
    await page.waitForSelector('#takemsg.good');
  };

  await bringBack();
  let r = await page.evaluate(() => ({
    msg: document.querySelector('#takemsg').innerHTML,
    text: document.querySelector('#takemsg').textContent,
    build: !!document.querySelector('#takebuild'),
    reload: !!document.querySelector('#takereload'),
    reader: !!document.querySelector('#takemsg a.btn')}));
  assert(!r.msg.includes('build.sh') && !r.msg.includes('takecopy'), 'no command to copy into a terminal: ' + r.msg);
  // THE PANEL BUILDS NOTHING.  A book installed is on the shelf, grey like
  // any book nobody has built, and the `build` button on its own card is the
  // one way to build it -- the panel used to carry a second one of its own.
  assert(!r.build, 'the panel no longer builds anything itself');
  assert(/on the shelf now/.test(r.text) && /not built yet/.test(r.text) && /build/.test(r.text),
         'it says the book is on the shelf, not built yet, to be built from its card: ' + r.text);
  assert(r.reload, 'and offers the list, which is where that card is');
  assert(!r.reader, 'and no reader to open: a bundle carries none unless it kept one');
  eq(builds, [], 'nothing was built from the panel');

  KIND = 'video';
  await bringBack();
  r = await page.evaluate(() => {
    const a = document.querySelector('#takemsg a.btn');
    return {build: !!document.querySelector('#takebuild'), reload: !!document.querySelector('#takereload'),
            href: a ? a.getAttribute('href') : ''};
  });
  eq(r, {build: false, reload: true, href: '/youtube/v/aB3dE5fG7hI/'},
     'a video is answered the same way: its player, and the list to reload');
  await page.close();
  console.log('Bringing a book back: onto the shelf not built, built from its own card and ' +
              'nowhere else, a video the same: passed');
}

// ======== writing in the book reader ========
async function reader(contextOptions) {
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  page.on('pageerror', e => { errors.push('reader: ' + e.message); console.log('PAGE ERROR', e.message); });
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), p = decodeURIComponent(url.pathname);
    if (url.hostname !== 'parseh.test') return route.abort();
    if (p.endsWith('/reader/__lookup')) return route.fulfill({json: {ok: true, help: false}});
    if (p === '/anki/decks') return route.fulfill({json: []});
    if (p.startsWith('/mt/')) return route.fulfill({status: 404, body: 'no model'});
    return file(route, p);
  });
  await page.goto(READER, {waitUntil: 'load'});
  return {context, page};
}
const row = n => '.pass.p2 .row[data-c="' + n + '"]';
// the pointer out of the way first: two rows scrolled to the middle of the
// window land under the same point, and a pointer that does not move says
// nothing to the page
const into = async (page, sel) => {
  await page.mouse.move(1, 1);
  await page.evaluate(async sel => {
    document.querySelector(sel).scrollIntoView({block: 'center'});
    await new Promise(r => setTimeout(r, 250));    // let the scroll land
  }, sel);
};

{
  const {context, page} = await reader({viewport: {width: 1280, height: 900}});
  eq(await page.evaluate(() => [!!document.querySelector('#edittext'), typeof setGlossing,
                                document.body.classList.contains('glossing'), matchMedia('(hover: hover)').matches]),
     [false, 'undefined', false, true], 'no edit mode, and no switch for one');
  await into(page, row(3));
  await page.hover(row(3));
  await page.waitForFunction(() => !document.querySelector('#chpen').hidden && penFor && +penFor.dataset.c === 3);
  assert(await page.evaluate(sel => {
    const p = document.querySelector('#chpen').getBoundingClientRect(), w = document.querySelector(sel).getBoundingClientRect();
    return p.top >= w.top && p.bottom <= w.bottom && p.left >= w.left && p.right <= w.right;
  }, row(3)), 'the pencil sits inside the corner of the row under the pointer');
  await page.hover('#chpen');
  await sleep(450);                                 // longer than the grace it has
  eq(await page.evaluate(() => !document.querySelector('#chpen').hidden), true, 'and stays while the pointer is on it');
  await page.click('#chpen');
  await page.waitForFunction(() => chOpen && chN === 3);
  eq(await page.evaluate(() => [CH.fa.value === SRC[3][1], document.querySelector('#chpen').hidden]), [true, true],
     'the pencil opens that chunk, and goes');
  await page.evaluate(() => { closeChunk(); document.activeElement.blur(); });

  await page.click(row(3));
  await sleep(300);
  eq(await page.evaluate(() => chOpen), false, 'a click on the chunk itself opens no sheet');

  // the pencil goes with its chunk when the page scrolls under it
  await into(page, row(3));
  await page.hover(row(3));
  await page.waitForFunction(() => penFor && +penFor.dataset.c === 3 && !document.querySelector('#chpen').hidden);
  const moved = await page.evaluate(async sel => {
    const before = document.querySelector('#chpen').getBoundingClientRect().top;
    scrollBy(0, 40);
    await new Promise(r => setTimeout(r, 150));
    const p = document.querySelector('#chpen').getBoundingClientRect(), w = document.querySelector(sel).getBoundingClientRect();
    return {by: Math.round(before - p.top), inside: p.top >= w.top && p.bottom <= w.bottom};
  }, row(3));
  eq(moved, {by: 40, inside: true}, 'the pencil scrolls with the row it is on');

  await into(page, row(4));
  await page.hover(row(4));
  await page.waitForFunction(() => penFor && +penFor.dataset.c === 4);
  await page.keyboard.press('e');
  await page.waitForFunction(() => chOpen && chN === 4);
  await page.evaluate(() => { closeChunk(); document.activeElement.blur(); setHover(true); });

  await page.mouse.move(1, 1);
  await into(page, '.p1 [data-c="5"]');
  await page.hover('.p1 [data-c="5"]');
  await page.waitForFunction(() => cloudC === 5 && !document.querySelector('#cloud').hidden);
  eq(await page.evaluate(() => [!!document.querySelector('#cloud .mkedit'), document.querySelector('#chpen').hidden]),
     [true, true], 'hover mode: the cloud has the pencil, and pass 1 no second one');
  await page.hover('#cloud .mkedit');
  await page.click('#cloud .mkedit');
  await page.waitForFunction(() => chOpen && chN === 5);
  await page.evaluate(() => { closeChunk(); document.activeElement.blur(); });

  await page.mouse.move(1, 1);
  await page.hover('.p1 [data-c="6"]');
  await page.waitForFunction(() => cloudC === 6 && !document.querySelector('#cloud').hidden);
  await page.keyboard.press('E');
  await page.waitForFunction(() => chOpen && chN === 6);
  await context.close();
  console.log('Book reader, with a pointer: no mode; a pencil over the row under the pointer that opens it, a click on ' +
              'the chunk still a click; E; the cloud\'s pencil in hover mode: passed');
}

{
  const {context, page} = await reader({viewport: {width: 900, height: 1000}, hasTouch: true, isMobile: true});
  eq(await page.evaluate(() => matchMedia('(hover: hover)').matches), false, 'a touch screen');
  await into(page, row(2));
  await page.tap(row(2));
  await page.waitForFunction(() => !document.querySelector('#chpen').hidden && penFor && +penFor.dataset.c === 2);
  eq(await page.evaluate(() => chOpen), false, 'the tap is still a tap on the chunk');
  await page.tap('#chpen');
  await page.waitForFunction(() => chOpen && chN === 2);
  await context.close();
  console.log('Book reader, on a touch screen: the pencil comes to the chunk tapped, and opens it: passed');
}

assert(!errors.length, 'page errors: ' + errors.join('; '));
} finally {
  await browser.close();
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
