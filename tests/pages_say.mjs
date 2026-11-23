// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/pages_say.mjs
//
// WHAT THE PAGES SAY THAT THEY DID NOT (a0.6.3, lane J2), driven on the REAL hub -- serve.main() over a
// temporary tree, no dictionary installed, Japanese's and Chinese's analyzers stood down, and YouTube's oEmbed
// answered by this test (a file in the tree says what it answers) -- every action a person's:
//   6.11  /books/add/, "sense groups", German (no dictionary, no word lists): the page stays and says every
//         sentence stayed one chunk, why, and where to get a dictionary; English (its own word lists) is cut
//         and the reader opens as ever
//   6.19  the library card says "0 of N chunks glossed"; a chunk glossed in the reader, the library page come
//         back to says "1 of N" (it asks the server, the file is not rewritten); the phone's shelf says it too
//   6.12  a Japanese chunk's sheet in the reader, a Chinese phrase's editor in the player: no "propose", and
//         "why no propose?" says which analyzer, which Python, and where it comes from
//   7.6   /youtube/add/ "Start it empty": with YouTube unreachable the page stays and says so, video.json has
//         the id and "Unknown channel"; reachable, the title and the channel are YouTube's and the player opens
//   10.7  the player's card sheet, saved to Anki twice: "already in", "add it again", a second card -- on a
//         computer and on a phone
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-pages-say-'});
const td = new TextDecoder();
let passed = 0;
// PAGES_SAY_SOFT=1 says every check that fails and goes on, to prove each item's checks fail on the old code
const SOFT = !!Deno.env.get('PAGES_SAY_SOFT'), failed = [];
const assert = (v, m) => {
  if (!v) { if (!SOFT) throw Error('FAIL: ' + m); failed.push(m); console.log('  FAIL', m); return; }
  passed++; console.log('  ok', m);
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want), m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 30000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) { if (SOFT) { assert(false, 'timed out: ' + what); return false; } throw Error('FAIL: timed out: ' + what); }
    await sleep(80);
  }
}
async function py(code, ...args) {
  const o = await new Deno.Command(PY, {args: ['-c', code, ...args], cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  if (o.code) throw Error(td.decode(o.stderr));
  return td.decode(o.stdout);
}
function freePort() { const l = Deno.listen({hostname: '127.0.0.1', port: 0}); const p = l.addr.port; l.close(); return p; }
function drain(stream, sink) {
  (async () => {
    const r = stream.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; sink.push(value); }
  })();
}

const BUILD = String.raw`
import os, sys
from pathlib import Path
REPO = Path(os.getcwd())
tmp = Path(sys.argv[1])
root = tmp / 'root'
for d in (root / 'books', root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises',
          tmp / 'anki', tmp / 'tray', tmp / 'config', tmp / 'nodict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
`;
// serve.main() over the tree, every store in it (as tests/draft_end_to_end.mjs points them)
const SERVE = String.raw`
import json, os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
REPO = os.getcwd()
import prefs, network, offline, latexthemes, latexdraw, texpackages, prompts, analysisconfig
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
latexdraw.DRAWN = str(tmp / 'latex-drawn')
texpackages.TREE = str(tmp / 'texmf')
prompts.STORE = str(tmp / 'config' / 'prompts.json')
analysisconfig.STORE = str(tmp / 'config' / 'analysis.json')
import lookup, corpus, getmt, getstt
lookup.DICT_DIR = str(tmp / 'nodict')
corpus.CORPUS_DIR = str(tmp / 'nocorpus')
getmt.MT_DIR = str(tmp / 'nomt')
getmt.ENGINE_DIR = str(tmp / 'nomt' / 'engine')
getstt.STT_DIR = str(tmp / 'nostt')
# Japanese's and Chinese's analyzers stood down, whatever this machine has (6.12)
import segmenter
segmenter.available = lambda code: False
import books
shelf = str(tmp / 'root' / 'books')
books.BOOKS_DIR = shelf
books.all_books.__defaults__ = (shelf, None)
books.book_dirs.__defaults__ = (shelf,)
import newbook
newbook.ROOT = str(tmp / 'root')
import clips, decks, store
clips.set_dir(tmp / 'tray')
import serve, ytpages
for st in {store, serve.studio.store}:
    st.LIB = tmp / 'library'
    st.set_clips_dir(tmp / 'tray')
decks.set_dir(tmp / 'exercises')
decks.set_clips_dir(tmp / 'tray')
serve.ROOT = str(tmp / 'root')
serve._AtRoot.directory = str(tmp / 'root')
ytpages.VIDEOS = str(tmp / 'root' / 'youtube' / 'videos')
serve.ANKI = ytpages.ANKI = str(tmp / 'anki')
ytpages.INBOX = str(tmp / 'anki' / 'inbox')
# YouTube's oEmbed, as this test says it answers: <tmp>/oembed.json
def oembed_why(vid):
    said = json.loads((tmp / 'oembed.json').read_text(encoding='utf-8'))
    return (said['got'], said['why'])
ytpages.oembed_why = oembed_why
import mobile_harness
def write_library(self):
    try:
        mobile_harness.library_page(tmp / 'root')
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "error": ""}
serve.Handler._write_library = write_library
built = serve.Handler._rebuild_reader
def rebuild_reader(self, book):
    r = built(self, book)
    out = os.path.join(book, 'reader')
    climb = os.path.relpath(REPO, out).replace(os.sep, '/') + '/'
    for name in os.listdir(out) if os.path.isdir(out) else ():
        if name.endswith('.html'):
            p = os.path.join(out, name)
            with open(p, encoding='utf-8') as f:
                text = f.read()
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text.replace(climb, '/'))
    return r
serve.Handler._rebuild_reader = rebuild_reader
sys.argv = ['serve.py', '--http', '--local', port]
serve.main()
`;
const FAKE_YT = `window.YT = {Player: function (el, o) {
  var t = 0, going = false, self = this;
  window.__yt = {t: function () { return t; }};
  this.getCurrentTime = function () { return t; };
  this.getDuration = function () { return 40; };
  this.seekTo = function (s) { t = +s || 0; };
  this.playVideo = function () { going = true; };
  this.pauseVideo = function () { going = false; };
  this.getPlayerState = function () { return going ? 1 : 2; };
  this.getPlaybackRate = function () { return 1; };
  this.setPlaybackRate = function () {};
  this.mute = function () {}; this.unMute = function () {};
  this.isMuted = function () { return false; };
  setInterval(function () { if (going) t += 0.05; }, 50);
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};`;
const oembed = (got, why) => Deno.writeTextFile(TMP + '/oembed.json', JSON.stringify({got, why}));

const DE = 'Gestern bin ich mit meinem Freund in die große Bibliothek der Stadt gegangen.\n\nDann habe ich dort einige alte Bücher gekauft.';
const EN = 'Yesterday I went with my friend to the big library of the town.';
const JA = '昨日、友達と一緒に町の大きな図書館へ行きました。';
const ZH = '0:01\n昨天我和朋友一起去了城里的大图书馆。\n0:06\n我们买了几本书。\n';
const FA = '0:01\nمن دیروز با دوستم به کتابخانه رفتم.\n0:05\nچند کتاب خریدم.\n';

let hub, browser;
const log = [];
try {
  await py(BUILD, TMP);
  await oembed({}, 'offline');
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port)], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  drain(hub.stdout, log); drain(hub.stderr, log);
  const B = `http://127.0.0.1:${port}`;
  await until(async () => { const r = await fetch(B + '/clips/api/status'); await r.body?.cancel(); return r.ok; },
              'the hub starts:\n' + log.join(''), 60000);
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const errors = [];
  async function newContext(opts) {
    const context = await browser.newContext(opts || {viewport: {width: 1280, height: 900}});
    await context.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => {
      if (route.request().url() === 'https://www.youtube.com/iframe_api')
        return route.fulfill({contentType: 'text/javascript', body: FAKE_YT});
      return route.abort();
    });
    return context;
  }
  const context = await newContext();
  async function open(ctx, url, name) {
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    if (url) await page.goto(B + url);
    return page;
  }
  const text = (page, sel) => page.evaluate(sel => { const e = document.querySelector(sel); return e ? e.textContent : null; }, sel);
  const shown = (page, sel) => page.evaluate(sel => { const e = document.querySelector(sel); return !!e && e.getClientRects().length > 0; }, sel);

  async function addBook(page, code, title, body, how) {
    await page.goto(B + '/books/add/');
    await page.waitForSelector('#paths .path[data-path="new"]');
    await page.click('#paths .path[data-path="new"]');
    await page.waitForFunction(() => !document.querySelector('#lane-new').hidden);
    await page.selectOption('#lang', code);
    await page.selectOption('#gloss', 'en');
    await page.fill('#slug', '');
    await page.fill('#title', title);
    await page.fill('#title_latin', title);
    await page.fill('#chtext', body);
    await page.selectOption('#how', how);
    await page.click('#mkempty');
  }

  /* ---------------- 6.11 ---------------- */
  console.log('\n6.11 sense groups that fell back');
  const add = await open(context, null, 'add');
  await addBook(add, 'de', 'Zwei Tage', DE, 'phrase');
  await until(async () => /\/reader\/$/.test(add.url()) || await shown(add, '#eresult .note.good'), 'the book is drafted', 60000);
  await until(() => shown(add, '#cutnote'), 'the note of the cut', 5000);
  const cut = await text(add, '#cutnote');
  assert(/every sentence stayed one chunk/.test(cut) && /no German dictionary is installed/.test(cut) &&
         /Settings → Reading help/.test(cut), 'German, "sense groups": the page says every sentence stayed one chunk, why, and where: ' + cut);
  await sleep(1500);
  assert(new URL(add.url()).pathname === '/books/add/', 'and it stays to say so (the reader is a link away)');
  eq(await add.evaluate(() => !!document.querySelector('#eresult a[href*="/reader/"]')), true, 'the reader\'s link is there');
  await Promise.all([add.waitForURL(/\/books\/english\/[^/]+\/reader\/$/, {timeout: 60000}), addBook(add, 'en', 'One Day', EN, 'phrase')]);
  assert(true, 'English, "sense groups": cut by its own word lists, and the reader opens as ever (no note to stay for)');

  /* ---------------- 6.19 ---------------- */
  console.log('\n6.19 a book\'s glossing on its card');
  const lib = await open(context, '/books/', 'library');
  const tagOf = (page, rel) => page.evaluate(rel => { const t = document.querySelector('[data-book="' + rel + '"][data-glossed]'); return t ? t.textContent : null; }, rel);
  const deRel = 'german/zwei-tage';
  const n = +(await until(async () => { const t = await tagOf(lib, deRel); return t && (/^0 of (\d+) chunks glossed$/.exec(t) || [])[1]; }, 'the German card\'s tag'));
  assert(n >= 2, `the German book's card: "0 of ${n} chunks glossed"`);
  const reader = await open(context, `/books/${deRel}/reader/`, 'reader-de');
  await reader.waitForFunction(() => typeof SRC !== 'undefined' && window.Parseh && document.querySelector('.sub'), null, {timeout: 30000});
  const row = '.pass.p2 .row[data-c="0"]';
  await reader.evaluate(sel => document.querySelector(sel).scrollIntoView({block: 'center'}), row);
  await sleep(250);
  await reader.hover(row);
  await reader.waitForFunction(() => !document.querySelector('#chpen').hidden && penFor && +penFor.dataset.c === 0);
  await reader.click('#chpen');
  await reader.waitForFunction(() => chOpen && chN === 0);
  await reader.fill('#chen', 'yesterday I went');
  await reader.click('#chsave');
  await reader.waitForFunction(() => /^saved/.test(document.querySelector('#chstat').textContent), null, {timeout: 20000});
  await lib.bringToFront();
  await lib.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await until(async () => await tagOf(lib, deRel) === `1 of ${n} chunks glossed`, 'the library page come back to counts the chunk glossed in the reader');
  assert(true, `the library page, come back to: "1 of ${n} chunks glossed" (asked of the server; the file was not rewritten)`);
  const libFile = await Deno.readTextFile(TMP + '/root/books/index.html');
  assert(libFile.includes(`0 of ${n} chunks glossed`), 'the page file itself still says what it was written with: the count came from the server');
  const phone = await newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
  const shelf = await open(phone, '/m/books/', 'phone-shelf');
  const ptag = await shelf.evaluate(() => [...document.querySelectorAll('.m-tags .tag')].map(t => t.textContent).filter(t => /chunks glossed/.test(t)));
  assert(ptag.includes(`1 of ${n} chunks glossed`), 'the phone\'s shelf says it too: ' + JSON.stringify(ptag));

  /* ---------------- 6.12 (reader) ---------------- */
  console.log('\n6.12 no propose, and why');
  await Promise.all([add.waitForURL(/\/books\/japanese\/[^/]+\/reader\/$/, {timeout: 60000}), addBook(add, 'ja', 'Kino', JA, 'sentence')]);
  const ja = add;
  await ja.waitForFunction(() => typeof SRC !== 'undefined' && window.Parseh && document.querySelector('.sub'), null, {timeout: 30000});
  await ja.evaluate(sel => document.querySelector(sel).scrollIntoView({block: 'center'}), row);
  await sleep(250);
  await ja.hover(row);
  await ja.waitForFunction(() => !document.querySelector('#chpen').hidden && penFor);
  await ja.click('#chpen');
  await ja.waitForSelector('#chwords .wordstrip');
  await until(() => shown(ja, '#chwords .ws-whynot'), 'the reader\'s strip offers "why no propose?"');
  eq(await shown(ja, '#chwords .ws-propose'), false, 'no "propose" in the reader');
  await ja.evaluate(() => { const b = document.querySelector('#chwords .ws-whynot'); if (b) b.click(); });
  const jwhy = await text(ja, '#chwords .ws-why');
  assert(/SudachiPy/.test(jwhy) && /Packages this Parseh lacks/.test(jwhy) && !/pip /.test(jwhy) && await shown(ja, '#chwords .ws-why'),
         'pressed, it says which analyzer, which Python, and where it comes from (no command): ' + jwhy);

  /* ---------------- 7.6 ---------------- */
  console.log('\n7.6 Start it empty, its title and channel');
  async function startEmpty(page, id, lang, transcript) {
    await page.goto(B + '/youtube/add/');
    await page.waitForSelector('#q1 .path[data-src="yt"]');
    await page.click('#q1 .path[data-src="yt"]');
    await page.click('#q2 .path[data-by="empty"]');
    await page.waitForFunction(() => !document.querySelector('#vbody').hidden && !document.querySelector('#step-empty-3').hidden);
    await page.fill('#url', id);
    await page.selectOption('#lang', lang);
    await page.fill('#transcript', transcript);
    await page.click('#empty');
  }
  const yt = await open(context, null, 'add-video');
  await oembed({}, 'offline');
  await startEmpty(yt, 'aB1cD2eF3gH', 'fa', FA);
  await until(() => shown(yt, '#fetchnote'), 'the note of the fetch', 60000);
  const fnote = await text(yt, '#fetchnote');
  assert(/YouTube could not be reached/.test(fnote) && /video info/.test(fnote), 'YouTube unreachable: the page says so, and where to fill them later: ' + fnote);
  await sleep(1200);
  assert(/\/youtube\/add\/?$/.test(new URL(yt.url()).pathname), 'and it stays to say so');
  const off = JSON.parse(await Deno.readTextFile(TMP + '/root/youtube/videos/persian/aB1cD2eF3gH/video.json'));
  eq([off.title, off.channel], ['aB1cD2eF3gH', 'Unknown channel'], 'the video is made, called by its id, "Unknown channel"');
  await oembed({title: '图书馆', channel: 'Zhongwen Channel'}, '');
  await Promise.all([yt.waitForURL(/\/youtube\/v\/zH1cD2eF3gH\/$/, {timeout: 60000}), startEmpty(yt, 'zH1cD2eF3gH', 'zh', ZH)]);
  const on = JSON.parse(await Deno.readTextFile(TMP + '/root/youtube/videos/chinese/zH1cD2eF3gH/video.json'));
  eq([on.title, on.channel], ['图书馆', 'Zhongwen Channel'], 'YouTube reachable: the title and the channel are its own, and the player opens');

  /* ---------------- 6.12 (player) ---------------- */
  const pl = yt;
  await pl.waitForSelector('#segs .seg .fa .w', {timeout: 30000});
  await pl.mouse.move(1, 1);
  await pl.locator('.seg[data-i="0"] .w[data-j="0"]').hover();
  await pl.waitForFunction(() => !document.querySelector('#cloud').hidden);
  await pl.evaluate(() => document.querySelector('#cloud .mkedit').click());
  await pl.waitForSelector('#cloud .wordstrip');
  await until(() => shown(pl, '#cloud .ws-whynot'), 'the player\'s strip offers "why no propose?"');
  eq(await shown(pl, '#cloud .ws-propose'), false, 'no "propose" in the player');
  await pl.evaluate(() => { const b = document.querySelector('#cloud .ws-whynot'); if (b) b.click(); });
  const zwhy = await text(pl, '#cloud .ws-why');
  assert(/spacy-pkuseg and pypinyin/.test(zwhy) && /Packages this Parseh lacks/.test(zwhy) && /Word models/.test(zwhy), 'the player says it for Chinese: ' + zwhy);
  await pl.keyboard.press('Escape');

  /* ---------------- 10.7 ---------------- */
  console.log('\n10.7 a card the Anki deck already has');
  const cardsIn = async () => { try { return [...Deno.readDirSync(TMP + '/anki/persian/mots/cards')].length; } catch (_) { return 0; } };
  async function saveTwice(page, tapped, where) {
    for (let k = 0; k < 2; k++) {
      await page.mouse.move(1, 1);
      if (tapped) await page.tap('.seg[data-i="0"] .w[data-j="0"]');
      else await page.locator('.seg[data-i="0"] .w[data-j="0"]').hover();
      await page.waitForFunction(() => !document.querySelector('#cloud').hidden);
      await page.evaluate(() => document.querySelector('#cloud .mkcard').click());
      await page.waitForFunction(() => { const b = document.querySelector('#anki'); return b && !b.hidden; });
      await page.waitForFunction(() => document.querySelector('#adeck').options.length > 0);
      await sleep(300);
      if (await page.evaluate(() => document.querySelector('#adeck').value === '')) {
        await until(() => shown(page, '#adecknew'), where + ': the new deck\'s name box');
        await page.fill('#adecknew', 'Mots');
      }
      await page.fill('#aen', 'a meaning');
      const had = await cardsIn();
      await page.click('#asave');
      if (k === 0 && had === 0) {
        await until(async () => await cardsIn() === 1, where + ': the first card is saved');
        await until(() => page.evaluate(() => document.querySelector('#anki').hidden), where + ': the sheet closes', 10000);
        continue;
      }
      await until(async () => await text(page, '#asavelab') === 'add it again', where + ': the duplicate is asked about');
      const said = await text(page, '#astat');
      assert(/already in “Mots”/.test(said) && /add it again/.test(said), `${where}: "${said}"`);
      eq(await cardsIn(), had, `${where}: and nothing was saved`);
      await page.click('#asave');
      await until(async () => await cardsIn() === had + 1, where + ': "add it again" adds a second one');
      assert(true, `${where}: "add it again" saved a second card (${had + 1} in the deck)`);
      await until(() => page.evaluate(() => document.querySelector('#anki').hidden), where + ': the sheet closes', 10000);
      return;
    }
  }
  const fa = await open(context, '/youtube/v/aB1cD2eF3gH/', 'player-fa');
  await fa.waitForSelector('#segs .seg .fa .w', {timeout: 30000});
  await saveTwice(fa, false, 'on a computer');
  const fp = await open(phone, '/youtube/v/aB1cD2eF3gH/', 'player-phone');
  await fp.waitForSelector('#segs .seg .fa .w', {timeout: 30000});
  // A PHONE THAT SAVES A CARD is one in the browser layout: the phone layout writes nothing, the card sheet
  // included (lib/mobile.css), so it has no duplicate to ask about.  Tapped, on a phone's screen.
  eq(await fp.evaluate(() => document.documentElement.getAttribute('data-mode')), 'browser', 'a phone\'s screen, in the browser layout');
  await saveTwice(fp, true, 'on a phone');

  eq(errors, [], 'no page error');
  console.log(`\n${passed} checks passed`);
  if (failed.length) throw Error(failed.length + ' checks FAILED:\n  ' + failed.join('\n  '));
} catch (e) {
  console.error(e.message || e);
  console.error(log.join('').slice(-3000));
  if (hub) try { hub.kill('SIGTERM'); } catch (_) {}
  if (browser) await browser.close().catch(() => {});
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
  Deno.exit(1);
}
if (hub) try { hub.kill('SIGTERM'); } catch (_) {}
if (browser) await browser.close().catch(() => {});
await Deno.remove(TMP, {recursive: true}).catch(() => {});
