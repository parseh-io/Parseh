// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/activity.mjs
//      ACTIVITY_SHOTS=<dir> also saves what each page looks like while the work runs
//
// "IT'S WORKING", on the page that started the work and on the hub, until it
// is over (lib/activity.js, lib/activity.py, serve.py's /__activity).  The
// REAL hub, serve.main(), on a temporary toolbox holding the English fixture
// book, its reader built and its library page written -- with two of the
// server's doors made slow on purpose, so the work lasts long enough to be
// looked at: taking a bundle apart (bundle.inspect) and packing one
// (bundle.pack_book) each wait SLOW seconds first.  Everything else is the
// real code, and every action is the page's own: a file chosen in "Bring a
// book back", a click on the reader's "download" link, the hub's stop button.
//
// At 1280x800 and at 390x844, in one browser with three tabs:
//  a) the books page: a bundle chosen -> the pill is on the screen AT ONCE,
//     before any poll, naming the file; the hub, open in the second tab,
//     shows the task in its panel under the brand within a moment, with the
//     page it came from; the pill there steps aside while the panel is in
//     sight and comes back when the page is scrolled; the studio's library,
//     a page that does not load parseh.js, shows it too, in the accent; and
//     all three are clear again once the server has answered.
//  b) the reader: its "download" link -> "Preparing the download…" at once,
//     then the server's own words for it ("Packing ... to download") on the
//     reader and on the hub; the browser's download manager still gets the
//     zip; then "Done", then nothing.  On a phone the pill stays on the
//     screen when the reader's bar goes away on scrolling.
//  c) the hub's stop button while something runs: the question names it,
//     and saying no leaves the server running; the exercises' stop button,
//     an in-page dialog of the studio's own, names it too.
//  d) a note opened over the reader, a recording uploaded from inside it on
//     a slow line: the note is a studio page in a frame, its upload is on
//     the READER's list as the reader's own work, and the pill is drawn
//     over the note's dimmed backdrop, not under it; then it is gone.
//  e) the reader's "rebuild the reader" and "build PDF" buttons (the build
//     itself stubbed, a few seconds that touch nothing): the pill names the
//     book from the click on, and says nothing else until "Done".
// And on the hub, while its panel is in sight, the pill it has shrunk to a
// pixel is no stop on Tab.
// "On the screen" is looked at as drawn: a box of some size inside the
// viewport, not display:none, not hidden, and the element at its middle is
// the pill itself -- nothing is drawn over it, and it is clear of the bars.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('ACTIVITY_SHOTS') || '';
const SLOW = 6;
const TMP = await Deno.makeTempDir({prefix: 'parseh-activity-'});
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

// the toolbox: the fixture book with its reader, the library page, a
// bundle of the book to bring back, and the stores the hub writes into
const BUILD = String.raw`
import os, shutil, subprocess, sys
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', '.']
tmp = sys.argv[1]
REPO = os.getcwd()
root = os.path.join(tmp, 'root')
book = os.path.join(root, 'books', 'english', 'mini-en')
shutil.copytree(os.path.join(REPO, 'tests/fixtures/books/english/mini-en'), book,
                ignore=shutil.ignore_patterns('reader'))
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', book], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr or r.stdout)
# the reader links lib/ relatively, from the repository; served from the
# temporary root that climbs out of the site, so it is the hub's own /lib/
out = os.path.join(book, 'reader')
climb = os.path.relpath(REPO, out).replace(os.sep, '/') + '/'
for n in os.listdir(out):
    if n.endswith('.html'):
        p = os.path.join(out, n)
        t = open(p, encoding='utf-8').read().replace(climb, '/')
        open(p, 'w', encoding='utf-8').write(t)
os.symlink(os.path.join(REPO, 'lib'), os.path.join(root, 'lib'))
os.makedirs(os.path.join(root, 'youtube', 'videos'))
os.symlink(os.path.join(REPO, 'youtube', 'lib'), os.path.join(root, 'youtube', 'lib'))
import books, make_index, bundle
shelf = os.path.join(root, 'books')
books.BOOKS_DIR = make_index.BOOKS_DIR = shelf
make_index.LIB = os.path.join(root, 'lib')
make_index.all_books = lambda: books.all_books(root=shelf)
make_index.main()
data, name = bundle.pack_book(book)
open(os.path.join(tmp, 'mini-en-book.zip'), 'wb').write(data)
# a recording big enough to be worth an entry (app.js's BIG_UPLOAD, 4 MB)
import wave
with wave.open(os.path.join(tmp, 'big.wav'), 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
    w.writeframes(os.urandom(5_000_000))
for d in ('library', 'exercises', 'anki', 'tray'):
    os.makedirs(os.path.join(tmp, d))
`;
// serve.main() over the temporary tree, with the two doors made slow; the
// bundle brought back is the temporary tree's own book, so it is refused as
// already there (409) and nothing is written anywhere
const SERVE = String.raw`
import sys, time
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', '.']
tmp, port, slow = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
import clips, decks, store
clips.set_dir(tmp / 'tray')
import serve, ytpages, bundle
for st in {store, serve.studio.store}:
    st.LIB = tmp / 'library'
    st.set_clips_dir(tmp / 'tray')
decks.set_dir(tmp / 'exercises')
decks.set_clips_dir(tmp / 'tray')
# WHAT THIS MACHINE KEEPS, into the temporary tree (lib/prefs.py, and
# lib/network.py since the network settings): a suite must never read the
# owner's own reading places, theme or network doors -- nor write them, which
# is what happened here: a suite turned the theme to dark in the real
# config/prefs.json and every page of the next suite opened dark.
import prefs
import network
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
# and the LaTeX drawings' themes, their drawings and their packages
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = str(tmp / 'config' / 'prompts.json')
latexdraw.DRAWN = str(tmp / 'latex-drawn')
texpackages.TREE = str(tmp / 'texmf')
import offline  # the phone-keeping memories (lib/offline.py) too
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
serve.ROOT = str(tmp / 'root')
serve._AtRoot.directory = str(tmp / 'root')
ytpages.VIDEOS = str(tmp / 'root' / 'youtube' / 'videos')
serve.ANKI = ytpages.ANKI = str(tmp / 'anki')
ytpages.INBOX = str(tmp / 'anki' / 'inbox')
def slowly(fn):
    def run(*a, **kw):
        time.sleep(slow)
        return fn(*a, **kw)
    return run
# a bundle brought back is checked and installed against the TEMPORARY
# toolbox: bundle.py's own default is the repository it lives in
here = str(tmp / 'root')
_inspect, _install = bundle.inspect, bundle.install
bundle.inspect = slowly(lambda data, root=None: _inspect(data, root=here))
bundle.install = lambda data, replace=False, root=None: _install(data, replace=replace, root=here)
bundle.pack_book = slowly(bundle.pack_book)
# a book build that takes a few seconds and touches nothing: the reader's
# build buttons are pressed in e), and a real ./build.sh would rewrite the
# reader this tree has pointed at the hub's /lib/
import bookbuild
bookbuild.command = lambda book_dir, what: [sys.executable, '-c',
    'import time; print("building", flush=True); time.sleep(3)']
sys.argv = ['serve.py', '--http', '--local', port]
serve.main()
`;

// ---- what "on the screen" means, looked at as drawn
function shownIn(sel) {
    const el = document.querySelector(sel);
    if (!el) return {ok: false, why: 'no ' + sel};
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    let hidden = false;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (n.hidden || s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) hidden = true;
    }
    const inside = r.width > 20 && r.height > 10 && r.left >= 0 && r.top >= 0 &&
      r.right <= innerWidth && r.bottom <= innerHeight;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const onTop = !!hit && (hit === el || el.contains(hit));
    return {ok: !hidden && inside && onTop, hidden, inside, onTop, text: el.textContent.replace(/\s+/g, ' ').trim(),
            rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
            bg: cs.backgroundColor, hit: hit ? hit.tagName + '.' + hit.className : null};
}
const shown = (page, sel) => page.evaluate(shownIn, sel);
const PILL = '#parseh-activity .pa-pill';
const PANEL = '#parseh-working';
async function until(page, fn, arg, ms, what) {
  try { await page.waitForFunction(fn, arg, {timeout: ms, polling: 100}); return true; }
  catch (_) { console.log('  (timed out waiting: ' + what + ')'); return false; }
}
const gone = sel => { const e = document.querySelector(sel);
  return !e || !!e.closest('[hidden]') || getComputedStyle(e).display === 'none'; };
const says = ([sel, re]) => { const e = document.querySelector(sel);
  return !!e && !e.closest('[hidden]') && new RegExp(re).test(e.textContent); };
function clear(a, b) {         // two rects [x, y, w, h] that do not overlap
  return a[0] + a[2] <= b[0] || b[0] + b[2] <= a[0] || a[1] + a[3] <= b[1] || b[1] + b[3] <= a[1];
}
async function rectOf(page, sel) {
  return page.evaluate(sel => { const e = document.querySelector(sel); if (!e) return null;
    const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }, sel);
}

let hub = null, browser = null;
const log = [];
try {
  const b = await new Deno.Command(PY, {args: ['-c', BUILD, TMP], cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  if (b.code) throw Error('the toolbox could not be built:\n' + td.decode(b.stderr) + td.decode(b.stdout));
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port), String(SLOW)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  for (const s of [hub.stdout, hub.stderr])
    (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
  const B = `http://127.0.0.1:${port}`;
  for (const t = Date.now();;) {
    try { const r = await fetch(B + '/__activity'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  // a note on the book, to open over its reader in d)
  const made = await fetch(B + '/books/english/mini-en/notes/api/docs', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: '---\ntitle: On the clock\nlang: en\ntarget: en\n---\n\nThe clock.\n'})});
  const NOTE = (await made.json()).meta.id;

  for (const [w, h] of [[1280, 800], [390, 844]]) {
    console.log(`\n${w}x${h}`);
    const ctx = await browser.newContext({viewport: {width: w, height: h}, acceptDownloads: true});
    const errors = [];
    const open = async path => {
      const p = await ctx.newPage();
      p.on('pageerror', e => errors.push(path + ': ' + e.message));
      await p.goto(B + path);
      await p.waitForFunction(() => !!window.ParsehActivity, null, {timeout: 10000});
      return p;
    };
    const lib = await open('/books/'), hubp = await open('/'), studio = await open('/studio/');
    const decks = await open('/exercises/');

    // a) a bundle brought back, from the books page
    await lib.bringToFront();
    const t0 = Date.now();
    await lib.setInputFiles('#takefile', TMP + '/mini-en-book.zip');
    let s = await shown(lib, PILL);
    check(s.ok && /Working: Uploading mini-en-book\.zip/.test(s.text) && Date.now() - t0 < 1500,
          'the books page shows the upload at once, on the screen: ' + JSON.stringify(s));
    check(await until(lib, says, [PILL, 'mini-en-book\\.zip.*\\(\\d'], 4000, 'the server\'s label'),
          'and then the server\'s words for it, with the size');
    check(await until(hubp, says, [PANEL, 'Uploading .*mini-en-book\\.zip'], 3000, 'the hub panel'),
          'the hub, in another tab, lists it in its panel within a moment');
    s = await shown(hubp, PANEL);
    check(s.ok, 'the hub\'s panel is on the screen, under the brand: ' + JSON.stringify(s.rect));
    check(/open the page/.test(s.text) && await hubp.evaluate(() =>
            document.querySelector('#parseh-working a.pa-open').getAttribute('href') === '/books/'),
          'and links back to the page that started it');
    // THE HUB IS A TAB BEHIND ANOTHER, and a tab behind another is drawn when the browser gets to it: the page learns that
    // its panel is in sight from an IntersectionObserver, which runs when the tab is drawn -- 300 to 600 ms after the
    // panel was there in two runs of ten, and not in four seconds on a loaded computer.  So the tab is the one in front
    // (it is what somebody who is looking at the panel has), and the pill is waited for
    await hubp.bringToFront();
    const quiet = await until(hubp, () => document.getElementById('parseh-activity').classList.contains('pa-quiet'),
                              null, 10000, 'the hub\'s pill steps aside');
    check(quiet, 'the hub\'s pill steps aside while the panel is in sight');
    // ... and out of the keyboard's way: Tab from the page's last control
    // does not land on a button shrunk to a pixel
    await hubp.bringToFront();
    await hubp.evaluate(() => {
      const wrap = document.getElementById('parseh-activity');
      const all = [...document.querySelectorAll('a[href], button')].filter(e => e.offsetParent && !wrap.contains(e));
      all[all.length - 1].focus({preventScroll: true});
    });
    await hubp.keyboard.press('Tab');
    const tabbed = await hubp.evaluate(() => { const w = document.getElementById('parseh-activity');
      return {inPill: w.contains(document.activeElement), quiet: w.classList.contains('pa-quiet')}; });
    check(!(tabbed.inPill && tabbed.quiet), 'and is no stop on Tab while it is shrunk: ' + JSON.stringify(tabbed));
    await lib.bringToFront();
    await hubp.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    check(await until(hubp, () => !document.getElementById('parseh-activity').classList.contains('pa-quiet'),
                      null, 2000, 'the pill back'), 'and comes back once the panel is scrolled away');
    s = await shown(hubp, PILL);
    check(s.ok && /Uploading/.test(s.text), 'the hub\'s pill is on the screen then: ' + JSON.stringify(s.rect));
    if (SHOTS) await hubp.screenshot({path: `${SHOTS}/hub-${w}.png`});
    await hubp.evaluate(() => window.scrollTo(0, 0));
    check(await until(studio, says, [PILL, 'Uploading'], 7000, 'the studio pill'),
          'the studio\'s library, which does not load parseh.js, shows it too');
    s = await shown(studio, PILL);
    const accent = await studio.evaluate(() => getComputedStyle(document.body).getPropertyValue('--accent').trim());
    check(s.ok && s.bg === 'rgb(190, 52, 85)' && accent === '#be3455',
          'on the screen there, in the studio\'s accent: ' + s.bg);
    const bar = await rectOf(studio, '.topbar');
    check(bar && clear(s.rect, bar), 'clear of the studio\'s bar');
    // the reader is a page built once and kept on disk: it gets the list
    // through the parseh.js it links, with no rebuild
    const reader = await open('/books/english/mini-en/reader/');
    check(await until(reader, says, [PILL, 'Uploading'], 4000, 'the reader pill'),
          'the book reader, opened meanwhile, shows it too');
    s = await shown(reader, PILL);
    const head = await rectOf(reader, 'header');
    check(s.ok && head && clear(s.rect, head), 'on the screen there, clear of the reader\'s bar: ' +
          JSON.stringify([s.rect, head]));
    if (SHOTS) await reader.screenshot({path: `${SHOTS}/reader-${w}.png`});
    if (SHOTS) { await lib.screenshot({path: `${SHOTS}/books-${w}.png`}); await studio.screenshot({path: `${SHOTS}/studio-${w}.png`}); }
    if (w < 600) {
      // the bar goes away as a phone scrolls down (parseh.js bars()); the pill
      // is not part of it and stays
      await lib.bringToFront();
      for (let i = 0; i < 3; i++) { await lib.mouse.move(200, 400); await lib.mouse.wheel(0, 300); await sleep(200); }
      const barGone = await lib.evaluate(() => document.body.classList.contains('barhidden'));
      s = await shown(lib, PILL);
      check(barGone && s.ok, 'on a phone the bar goes away on scrolling and the pill stays: ' + barGone + ' ' + JSON.stringify(s.rect));
    }
    check(await until(lib, () => /already|replace|is in/.test(document.getElementById('takemsg').textContent),
                      null, (SLOW + 6) * 1000, 'the answer'), 'the upload is answered');
    for (const [p, name] of [[lib, 'books page'], [hubp, 'hub'], [studio, 'studio'], [reader, 'reader']]) {
      check(await until(p, gone, PILL, 6000, name + ' pill gone') &&
            await until(p, gone, PANEL, 1000, name + ' panel gone'),
            'and the ' + name + ' is clear again once it is over');
    }

    // b) the reader's download link, followed by its token.  WHILE THE
    // DOWNLOAD IS BEING PACKED the reader is, to the browser, in the middle of
    // a navigation, and nothing from outside can ask it anything until the
    // answer arrives (page.evaluate and the DevTools protocol both wait) --
    // though its own script runs on.  So the page keeps a diary of its pill,
    // as drawn, every 100 ms, and the diary is read once the download has
    // started.
    await reader.bringToFront();
    await reader.evaluate(src => {
      const look = new Function('return ' + src)();
      window.__diary = [];
      window.__diaryTimer = setInterval(() => window.__diary.push(look('#parseh-activity .pa-pill')), 100);
    }, shownIn.toString());
    const dl = reader.waitForEvent('download', {timeout: (SLOW + 10) * 1000});
    // the click and a look at the pill in ONE turn of the page's script: what
    // it says then was drawn before any answer from the server could arrive
    const at = await reader.evaluate(src => {
      const a = document.querySelector('header a.dl');
      const was = a.getAttribute('href');
      a.click();
      return {pill: new Function('return ' + src)()('#parseh-activity .pa-pill'),
              was, during: a.getAttribute('href')};
    }, shownIn.toString());
    check(at.pill.ok && /^Working: Preparing the download/.test(at.pill.text),
          'the reader shows "Preparing the download…" on the screen in the same moment as the click: ' +
          JSON.stringify(at.pill));
    check(clear(at.pill.rect, head), 'clear of the reader\'s bar');
    check(/[?&]job=[a-z0-9]{12}$/.test(at.during), 'the click carried a token: ' + at.during);

    // c) the stop button while it runs: the question names the work
    check(await until(hubp, says, [PANEL, 'Packing .*The Clock and the Wind'], 3000, 'hub label'),
          'the hub lists the download while it is packed');
    await hubp.bringToFront();
    const asked = new Promise(r => hubp.once('dialog', d => { r(d.message()); d.dismiss(); }));
    await hubp.click('[data-parseh-stop]');
    const q = await asked;
    check(/1 task is still running/.test(q) && /Packing/.test(q), 'the stop button names what runs: ' + JSON.stringify(q));
    await sleep(300);
    const alive = await fetch(B + '/__activity').then(r => r.ok).catch(() => false);
    check(alive, 'and "no" leaves the server running');
    await decks.bringToFront();
    await decks.click('#btn-stop');
    const ask = await decks.waitForSelector('.dk-modal', {timeout: 3000}).then(m => m.innerText()).catch(() => '');
    check(/1 task is still running/.test(ask) && /Packing .*The Clock and the Wind/.test(ask),
          'the exercises\' stop button names it too: ' + JSON.stringify(ask));
    await decks.click('.dk-modal [data-x="cancel"]');
    check(await fetch(B + '/__activity').then(r => r.ok).catch(() => false), 'and Cancel leaves it running');

    const file = await dl;
    const path = await file.path();
    const size = path ? (await Deno.stat(path)).size : 0;
    check(size > 1000 && /mini-en.*\.zip$/.test(file.suggestedFilename()),
          'the browser\'s own download manager got the zip: ' + file.suggestedFilename() + ', ' + size + ' bytes');
    await reader.bringToFront();
    // "Done" stays on the pill for three seconds after the zip is made, and by the time the browser has handed the file
    // over and this has looked at it a slow computer has let those seconds go: the page's own diary, kept every 100 ms
    // from before the click, has it whenever it is read
    check(await reader.waitForFunction(() => window.__diary.some(d => d.ok && /^Done: Packing .*The Clock and the Wind/.test(d.text)),
                                       null, {timeout: 15000, polling: 100}).then(() => true, () => false),
          'the reader says "Done" when it is over, in the server\'s words');
    const diary = await reader.evaluate(() => { clearInterval(window.__diaryTimer); return window.__diary; });
    const packing = diary.filter(d => d.ok && /^Working: Packing .*The Clock and the Wind.* to download/.test(d.text));
    check(packing.length >= (SLOW - 2) * 10 && packing.every(d => clear(d.rect, head)),
          'while it was packed the reader said so in the server\'s words, on the screen, clear of the bar: ' +
          packing.length + ' of ' + diary.length + ' looks');
    check(await reader.evaluate(was => document.querySelector('header a.dl').getAttribute('href') === was, at.was),
          'and the link itself is as it was');
    check(await until(reader, gone, PILL, 6000, 'reader pill gone'), 'and then nothing');
    check(await until(hubp, gone, PANEL, 6000, 'hub panel gone'), 'and the hub is clear');

    // d) a note over the reader, and a recording uploaded from inside it
    await reader.bringToFront();
    // the EDITOR, which is what this part uploads a recording from: ntShow's
    // third argument is a mode now ('' the bare page, 'edit' the editor,
    // 'full' the studio's whole page), where it used to be "open it in the
    // editor" as a boolean (lib/tex2html.py, the fast notes of 2026-09-23)
    await reader.evaluate(id => ntShow(id, 'On the clock', 'edit'), NOTE);
    const frame = await (await reader.waitForSelector('#ntframe')).contentFrame();
    await frame.waitForSelector('#audio-upload', {state: 'attached', timeout: 10000});
    await frame.waitForFunction(() => !!window.ParsehActivity, null, {timeout: 10000});
    const cdp = await ctx.newCDPSession(reader);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', {offline: false, latency: 20,
      downloadThroughput: -1, uploadThroughput: 1e6});
    await frame.setInputFiles('#audio-upload', TMP + '/big.wav');
    check(await until(reader, says, [PILL, 'Uploading'], 3000, 'the note upload'),
          'an upload from inside a note is on the reader\'s pill');
    s = await shown(reader, PILL);
    const back = await reader.evaluate(() => !document.getElementById('ntback').hidden);
    check(back && s.ok && /big\.wav/.test(s.text),
          'drawn over the note\'s backdrop, not under it: ' + JSON.stringify(s));
    if (SHOTS) await reader.screenshot({path: `${SHOTS}/note-${w}.png`});
    await cdp.send('Network.emulateNetworkConditions', {offline: false, latency: 0,
      downloadThroughput: -1, uploadThroughput: -1});
    check(await until(reader, gone, PILL, 15000, 'note upload over'), 'and gone once it is in');
    await reader.evaluate(() => ntShut());

    // e) the reader's two build buttons: the pill names the book from the
    // click on -- the page calls its own work "the PDF" and "the reader",
    // and the pill once said "Building the PDF of the PDF" until the
    // server's words arrived -- and never anything else while it builds
    for (const [btn, want] of [['#buildhtml', 'Rebuilding the reader'], ['#buildbook', 'Building the PDF']]) {
      await reader.bringToFront();
      const named = `Working: ${want} of \u201c\u2068The Clock and the Wind\u2069\u201d`;
      const first = await reader.evaluate(([sel, src]) => {
        const look = new Function('return ' + src)();
        window.__diary = [];
        window.__diaryTimer = setInterval(() => window.__diary.push(look('#parseh-activity .pa-pill').text), 100);
        document.querySelector(sel).click();
        return look('#parseh-activity .pa-pill');
      }, [btn, shownIn.toString()]);
      check(first.ok && first.text === named, `the reader's ${btn} names the book at the click: ` + JSON.stringify(first.text));
      check(await until(reader, says, [PILL, '^Done: ' + want], 12000, btn + ' done'), 'and says "Done" when it is built');
      const diary = [first.text, ...await reader.evaluate(() => { clearInterval(window.__diaryTimer); return window.__diary; })];
      const working = diary.filter(t => /^Working:/.test(t));
      check(working.length >= 10 && working.every(t => t === named) && !diary.some(t => /of the (PDF|reader)\b/.test(t)),
            'and says nothing else while it builds, never "of the PDF" or "of the reader": ' +
            JSON.stringify([...new Set(diary)]));
      check(await until(reader, gone, PILL, 6000, btn + ' pill gone'), 'and then nothing');
    }

    check(!errors.length, 'no script errors: ' + errors.join(' | '));
    await ctx.close();
  }
  check(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
  if (failed.length) throw Error('FAIL: ' + failed.length + ' check(s):\n  ' + failed.join('\n  '));
  console.log(`\nactivity: ${passed} checks passed`);
} catch (e) {
  console.log(e.stack || e);
  console.log('hub log tail:\n' + log.join('').slice(-3000));
  Deno.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
