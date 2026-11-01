// SPDX-License-Identifier: GPL-3.0-or-later
// THE VIDEO PLAYER'S TWO WAYS WITH A LINE (a0.5.8), driven on the real player page.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/player_lines.mjs
//   SHOTS=<dir> also saves a screenshot of each look
//
//   a) THE GLOSSES BELOW THE LINE.  "gloss below" draws, under each line, a row for each phrase that has
//      a gloss to show -- the phrase on one side, its reading, transliteration, vocabulary and meaning
//      beside it -- in place of the cloud that opens on a hover.  Off, a line is byte for byte what it
//      was; on, pointing at a phrase of the line lights its row and opens nothing, and pointing at the
//      phrase in its row opens the cloud with the phrase's tools and none of the gloss it would say twice.
//      A phrase written from the row changes the row and the line together; the choice is kept; the gear
//      has the same switch.
//   b) MOVING TEXT BETWEEN LINES.  "move text" turns the words of a line into things to click: a card
//      opens by the word with the two choices, each saying how many words it moves and lighting them while
//      it is pointed at; the server moves them (youtube/lib/reflow.py is held to the checker by
//      tests/test_video_reflow.py -- here it is the page that is held to the server); the two lines are
//      drawn where they stand; Undo (and Ctrl+Z) puts them back byte for byte; a page that is out of date
//      is refused and says to reload; a click that cannot be made says why and cannot be pressed.
//
// The hub is REAL (serve.main on a temporary tree).  YouTube's player is the one fake there is.
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const td = new TextDecoder();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const SHOTS = Deno.env.get('SHOTS') || '';
const shot = async (page, name) => { if (SHOTS) await page.screenshot({path: `${SHOTS}/${name}.png`}); };

let passed = 0;
const errors = [];
const assert = (v, m) => { if (!v) throw new Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
  m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));

// ---- the video: lines that stop in the middle of a sentence, the way a transcript cut by the clock does
const ID = 'fa-lines-a1b2c3';
const LINES = [
  [0, 'Welcome to the lesson.', null],
  [6, 'سلام و درود به همه. چقدر دلم برای این لحظه',
   [['سلام و درود', 'hello and greetings', 'salām o dorud'], ['به همه.', 'to everyone', 'be hame'],
    ['چقدر دلم', 'how much my heart', 'čeqadr del-am'], ['برای این لحظه', 'for this moment', 'barāye in lahze']]],
  [16, 'برای صحبت کردن با شما. امیدوارم حال دلتون',
   [['برای صحبت کردن', 'for talking', 'barāye sohbat kardan'], ['با شما.', 'with you', 'bā šomā'],
    ['امیدوارم', 'I hope', 'omidvār-am'], ['حال دلتون', 'state of your heart', 'hāl-e del-etun']]],
  [26, 'خوب باشه و روزگار بر وفق مرادتون بگرده.',
   [['خوب باشه', 'be well', 'xub bāše'], ['و روزگار', 'and the times', 'o ruzegār'],
    ['بر وفق مرادتون بگرده.', 'turn as you wish', 'bar vafq-e morād-etun bargarde']]],
  [36, 'بعد از آن می‌گویم.', [['بعد از آن', 'after that', 'ba\'d az ān'], ['می‌گویم.', 'I say', 'mi-guyam']]],
];
const VIDEO = {id: ID, lines: LINES};

const WORK = await Deno.makeTempDir({prefix: 'parseh-player-lines-'});
const SERVE = String.raw`
import json, os, sys
from pathlib import Path
tmp, port = Path(sys.argv[1]), int(sys.argv[2])
repo = Path.cwd()
sys.path[:0] = [str(repo / p) for p in ('markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.')]
import check_annotations as CA
v = json.loads(sys.argv[3])
root = tmp / 'root'
(root / 'youtube').mkdir(parents=True)
os.symlink(str(repo / 'lib'), str(root / 'lib'))
os.symlink(str(repo / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
for d in ('library', 'exercises', 'anki'):
    (tmp / d).mkdir()
dst = root / 'youtube' / 'videos' / 'persian' / v['id']
dst.mkdir(parents=True)
(dst / 'video.json').write_text(json.dumps(
    {'id': v['id'], 'url': 'https://www.youtube.com/watch?v=' + v['id'], 'title': 'Lines',
     'title_native': 'خطوط', 'channel': '', 'language': 'fa', 'gloss': 'en', 'duration': '0:45'}), encoding='utf-8')
segs, rows = [], []
for start, text, chunks in v['lines']:
    rows += [CA.stamp_of(start), text]
    if chunks is None:
        segs.append({'start': start, 'text': text, 'plain': True})
        continue
    segs.append({'start': start, 'text': text, 'chunks': [{'fa': c[0], 'tr': c[2], 'en': c[1]} for c in chunks]})
(dst / 'annotations.json').write_text(json.dumps(
    {'video': v['id'], 'language': 'fa', 'segments': segs}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
(dst / 'transcript.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
import cardkit_harness
cardkit_harness.serve_it(tmp, port, False, 'tray')
`;
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
const port = freePort();
const log = [];
const hub = new Deno.Command(PY, {args: ['-c', SERVE, WORK, String(port), JSON.stringify(VIDEO)],
                                  cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 90000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}
const DIR = `${WORK}/root/youtube/videos/persian/${ID}`;
const onDisk = async name => await Deno.readTextFile(`${DIR}/${name}`);
const segsOnDisk = async () => JSON.parse(await onDisk('annotations.json')).segments;

const FAKE_YT = `window.__yt = {t: 0, state: 2, calls: []};
window.YT = {Player: function (el, o) {
  var self = this, Y = window.__yt;
  this.getCurrentTime = function () { return Y.t; };
  this.getDuration = function () { return 45; };
  this.seekTo = function (s) { Y.calls.push(['seek', +s]); Y.t = +s || 0; };
  this.playVideo = function () { Y.calls.push(['play']); Y.state = 1; };
  this.pauseVideo = function () { Y.calls.push(['pause']); Y.state = 2; };
  this.getPlayerState = function () { return Y.state; };
  this.getPlaybackRate = function () { return 1; };
  this.setPlaybackRate = function () {};
  this.getAvailablePlaybackRates = function () { return [1]; };
  this.mute = function () {}; this.unMute = function () {}; this.isMuted = function () { return false; };
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};
if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();`;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
async function openPage(storage = {}, width = 1280) {
  const ctx = await browser.newContext({viewport: {width, height: 900}, serviceWorkers: 'block'});
  await ctx.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname === '127.0.0.1') return route.fallback();
    if (u.href.startsWith('https://www.youtube.com/iframe_api'))
      return route.fulfill({body: FAKE_YT, contentType: 'text/javascript'});
    return route.abort();
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await ctx.addInitScript(s => {
    try {
      if (!sessionStorage.getItem('__seeded')) {
        sessionStorage.setItem('__seeded', '1');
        for (const k in s) localStorage.setItem(k, s[k]);
      }
    } catch (e) { /* the blank document a page starts on */ }
  }, storage);
  await page.goto(B + `/youtube/v/${ID}/`);
  await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n, LINES.length);
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready(), null, {timeout: 20000});
  await sleep(200);
  return page;
}
// a switch of the gear's panel, pressed as a hand presses it, and the panel shut again
async function gearSwitch(page, name) {
  await page.click('.pg-gear, [data-parseh-gear]');
  await page.waitForSelector('.pg-panel');
  const row = page.locator('.pg-panel .pg-row', {hasText: name}).first();
  await row.scrollIntoViewIfNeeded();
  await row.locator('.pg-switch').click();
  await sleep(150);
  await page.evaluate(() => ParsehGear.mounted().close());
  await sleep(100);
}
// what the page says each line is, and which words it has
const shownLines = page => page.evaluate(() =>
  [...document.querySelectorAll('#segs .seg')].map(s => s.querySelector('.fa, .en-line').textContent.replace(/\s+/g, ' ').trim()));
const textsOnDisk = async () => (await segsOnDisk()).map(s => s.text);
const calls = page => page.evaluate(() => window.__yt.calls.slice());

try {
  /* ====================================================== a) the glosses below the line */
  console.log('a) the glosses below the line');
  let page = await openPage();
  const plainBefore = await page.evaluate(() => document.querySelector('#segs').innerHTML);
  assert(await page.evaluate(() => !document.querySelector('.rows') && !document.body.classList.contains('glossbelow')),
         'off, there is no row on the page and the body does not say so');
  assert(await page.evaluate(() => !!document.getElementById('below') && document.getElementById('below').textContent === 'gloss below'),
         'the bar has the button, named for what it does');

  assert(!await page.evaluate(() => { const b = document.getElementById('below'); return !!b.getClientRects().length; }),
         'the bar does not draw it (the header holds no more at 1280): it is the gear\'s row, whose button the gear presses');
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForSelector('.rows');
  eq(await page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(s => s.querySelectorAll('.row').length)),
     [0, 4, 4, 3, 2], 'a row for each phrase of each glossed line, and none under the video\'s own framing');
  const row0 = await page.evaluate(() => {
    const r = document.querySelector('.seg[data-i="1"] .row[data-j="2"]');
    return {fa: r.querySelector('.rfa .w').textContent, tr: r.querySelector('.rgl .tr').textContent,
            en: r.querySelector('.rgl .en').textContent, dir: r.querySelector('.rfa').getAttribute('dir'),
            first: getComputedStyle(r).flexDirection};
  });
  eq([row0.fa, row0.tr, row0.en], ['چقدر دلم', 'čeqadr del-am', 'how much my heart'],
     'a row holds the phrase and, beside it, its transliteration and its meaning');
  eq([row0.dir, row0.first], ['rtl', 'row-reverse'], 'a Persian row stands its phrase at the right');
  assert(await page.evaluate(() => document.body.classList.contains('glossbelow') &&
                             document.getElementById('below').classList.contains('on')),
         'the button is lit and the body says what is drawn');
  await shot(page, 'below');

  console.log('   pointing at a phrase of the line lights its row and opens no cloud');
  await page.hover('.seg[data-i="1"] .fa .w[data-j="1"]');
  await sleep(250);
  assert(await page.evaluate(() => document.getElementById('cloud').hidden), 'no cloud opened');
  eq(await page.evaluate(() => [...document.querySelectorAll('.row.lit')].map(r => r.dataset.j)), ['1'],
     'and the row of that phrase is lit');
  await page.mouse.move(5, 5);
  await sleep(200);
  eq(await page.evaluate(() => document.querySelectorAll('.row.lit').length), 0, 'put out when the pointer goes');

  console.log('   pointing at the phrase in its row opens the cloud with the phrase\'s tools only');
  await page.hover('.seg[data-i="1"] .row[data-j="2"] .rfa .w');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  const tools = await page.evaluate(() => {
    const c = document.getElementById('cloud');
    return {tr: !!c.querySelector('.tr'), en: !!c.querySelector('.en'), unwritten: !!c.querySelector('.unwritten'),
            edit: !!c.querySelector('.mkedit'), card: !!c.querySelector('.mkcard'), colours: c.querySelectorAll('.sw').length};
  });
  assert(!tools.tr && !tools.en && !tools.unwritten, 'it does not say the gloss again');
  assert(tools.edit && tools.card && tools.colours === 5, '✎ edit, + card and the colours are there');

  console.log('   a phrase written from its row changes the row and the line together');
  await page.click('#cloud .mkedit');
  await page.waitForSelector('#cloud .ef[data-f="en"]');
  await page.fill('#cloud .ef[data-f="en"]', 'how much my poor heart');
  await page.click('#cloud .esave');
  await page.waitForFunction(() => /saved/.test(document.querySelector('#cloud .cstat').textContent));
  eq(await page.evaluate(() => document.querySelector('.seg[data-i="1"] .row[data-j="2"] .rgl .en').textContent),
     'how much my poor heart', 'the row says the new meaning');
  eq((await segsOnDisk())[1].chunks[2].en, 'how much my poor heart', 'and the file has it');
  await page.click('#cloud .ecancel');
  await page.mouse.move(5, 5);
  await sleep(300);
  await page.hover('.seg[data-i="1"] .row[data-j="0"] .rfa .w');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.click('#cloud .sw.hl-red');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="1"] .w.hl-red').length === 2);
  assert(true, 'a colour marks the phrase in its row and in its line');
  await page.mouse.move(5, 5);

  console.log('   the gear has the same switch, and the choice is kept');
  await page.reload();
  await page.waitForSelector('.rows');
  assert(await page.evaluate(() => document.body.classList.contains('glossbelow')), 'a reload keeps it');
  await page.click('.pg-gear, [data-parseh-gear]');
  await page.waitForSelector('.pg-panel');
  const gearRow = await page.evaluate(() => {
    const t = [...document.querySelectorAll('.pg-panel .pg-row')].find(r => /Glosses below the line/.test(r.textContent));
    return t ? {text: t.textContent.slice(0, 60), on: !!t.querySelector('[aria-checked="true"], input:checked, .on')} : null;
  });
  assert(gearRow, 'the panel names it: Glosses below the line');
  await page.keyboard.press('Escape');
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForFunction(() => !document.querySelector('.rows'));
  assert(await page.evaluate(() => !document.body.classList.contains('glossbelow')), 'pressed again, the rows go');
  // the colour mark and the saved meaning are in the line, so the line differs from the first draw only
  // by what was written in it; the line markup itself is the same shape it had
  const shapeAfter = await page.evaluate(() => document.querySelectorAll('#segs .seg').length + ':' +
    document.querySelectorAll('#segs .seg .fa .w').length + ':' + document.querySelectorAll('#segs .rows, #segs .row').length);
  eq(shapeAfter, LINES.length + ':13:0', 'and the transcript is the page it was');
  assert(plainBefore.length > 0, 'a baseline was taken');
  await page.context().close();

  /* ====================================================== b) moving text between lines */
  console.log('b) moving text between lines');
  page = await openPage();
  const original = [await onDisk('annotations.json'), await onDisk('transcript.txt')];
  const originalTexts = await textsOnDisk();
  assert(await page.evaluate(() => !document.getElementById('rfdock') || document.getElementById('rfdock').hidden),
         'the dock is not there until the mode is on');
  assert(!await page.evaluate(() => !!document.getElementById('reflow').getClientRects().length),
         'at 1280px the bar has no room for the button, and does not draw it');
  await gearSwitch(page, 'Move text between lines');
  await page.waitForFunction(() => document.body.classList.contains('reflowing'));
  assert(await page.evaluate(() => !document.getElementById('rfdock').hidden), 'the mode shows its dock');
  eq(await page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(s => s.classList.contains('rf-open'))),
     [false, true, true, false, false], 'the lines that stop in the middle of a sentence are marked');
  await shot(page, 'reflow');

  console.log('   a click on a word does not replay the line, it asks where a line ends or begins');
  // the video is pinned over the top of the page and the dock lies over its foot: a line is brought to just
// under the video (its scroll-margin says where that is) before a word of it is clicked, as a hand would,
// rather than left where scrolling "if needed" put it
const wordOf = (i, k) => {
  const loc = page.locator(`.seg[data-i="${i}"] .fa .wd`).nth(k);
  return {click: async () => {
    await loc.evaluate(e => e.closest('.seg').scrollIntoView({block: 'start'}));
    await sleep(60);
    await loc.click();
  }};
};
  await wordOf(1, 4).click();                       // «همه.»
  await page.waitForSelector('#rfpop:not([hidden])');
  eq((await calls(page)).filter(c => c[0] === 'seek').length, 0, 'the video was not sent anywhere');
  const card = await page.evaluate(() => ({
    q: document.getElementById('rfq').textContent,
    end: [...document.querySelectorAll('#rfpop .rfgo')].find(b => b.dataset.edge === 'end'),
    texts: [...document.querySelectorAll('#rfpop .rfgo')].map(b => ({edge: b.dataset.edge, off: b.disabled,
      small: b.querySelector('small').textContent}))}));
  eq(card.q, 'At “همه.”', 'the card names the word');
  const by = Object.fromEntries(card.texts.map(t => [t.edge, t]));
  assert(!by.end.off && /moves the 5 words after it down to the start of the next line/.test(by.end.small),
         'End the line here says how many words it moves and where: ' + by.end.small);
  assert(by.start.off && /line before it is not glossed/.test(by.start.small),
         'Start a line here cannot be pressed on the first glossed line, and says why: ' + by.start.small);

  console.log('   pointing at a choice lights the words it would move');
  await page.hover('#rfpop .rfgo[data-edge="end"]');
  eq(await page.evaluate(() => [...document.querySelectorAll('.rf-moving')].map(e => e.textContent)),
     ['چقدر', 'دلم', 'برای', 'این', 'لحظه'], 'the five words after the click are lit');
  await shot(page, 'reflow-card');

  console.log('   the move: the page, the two files and the dock');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  const moved = await shownLines(page);
  eq(moved.slice(1, 3), ['سلام و درود به همه.', 'چقدر دلم برای این لحظه برای صحبت کردن با شما. امیدوارم حال دلتون'],
     'the two lines are drawn as they now are');
  const disk = await segsOnDisk();
  eq(disk.slice(1, 3).map(s => s.text), moved.slice(1, 3), 'annotations.json says the same');
  const tr = (await onDisk('transcript.txt')).split('\n');
  assert(tr.includes('چقدر دلم برای این لحظه برای صحبت کردن با شما. امیدوارم حال دلتون') &&
         tr.includes('سلام و درود به همه.'), 'and so does transcript.txt');
  assert(disk[2].start > 6 && disk[2].start < 16, 'the second line starts inside the line the words left: ' + disk[2].start);
  const said = await page.evaluate(() => document.getElementById('rfsay').textContent);
  assert(/That line now begins at 0:10\.8 \u2014 worked out from the words, not heard/.test(said),
         'the dock says the new start, to a tenth, and that it is an estimate: ' + said);
  assert(await page.evaluate(() => !document.getElementById('rfundo').disabled &&
                             !document.getElementById('rfplay').disabled && !document.getElementById('rftune').disabled),
         'Undo, hear the join and fine-tune are live');
  assert(await page.evaluate(() => document.querySelectorAll('.rf-flash').length > 0), 'the words that moved are lit where they are now');
  eq(await page.evaluate(() => document.querySelector('.seg[data-i="2"] .lab').textContent.length > 0), true, 'the line keeps its time label');
  // the line's own seam follows the start, so a note anchored to it would still find it
  eq(await page.evaluate(() => document.querySelectorAll('#segs .seg')[2].previousElementSibling.dataset.at),
     String(disk[2].start), 'the seam before the line is named by its new start');

  console.log('   Undo puts both back byte for byte, and Ctrl+Z does the same');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  eq([await onDisk('annotations.json'), await onDisk('transcript.txt')], original, 'the two files are exactly what they were');
  eq(await shownLines(page), originalTexts, 'and so is the page');
  await wordOf(1, 4).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  await page.keyboard.press('Control+z');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  eq(await onDisk('transcript.txt'), original[1], 'Ctrl+Z took it back too');

  console.log('   a line may begin at a word inside a phrase: the phrase is cut');
  await wordOf(2, 2).click();                        // «کردن» of «برای صحبت کردن»
  await page.waitForSelector('#rfpop:not([hidden])');
  const startBtn = await page.evaluate(() => {
    const b = document.querySelector('#rfpop .rfgo[data-edge="start"]');
    return {off: b.disabled, small: b.querySelector('small').textContent};
  });
  assert(!startBtn.off && /moves the 2 words before it up to the end of the line above/.test(startBtn.small),
         'two words go up: ' + startBtn.small);
  await page.click('#rfpop .rfgo[data-edge="start"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  const cut = await segsOnDisk();
  eq(cut[1].text, 'سلام و درود به همه. چقدر دلم برای این لحظه برای صحبت', 'the line above took the first words of the phrase');
  eq(cut[2].chunks.map(c => c.fa).slice(0, 2), ['کردن', 'با شما.'], 'and the phrase was cut at the word');
  assert(!('en' in cut[2].chunks[0]), 'the second half has its meaning still to write');
  assert(/phrase was cut in two/.test(await page.evaluate(() => document.getElementById('rfsay').textContent)),
         'the dock says a phrase was cut');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  eq([await onDisk('annotations.json'), await onDisk('transcript.txt')], original, 'and Undo gives the phrase back whole');

  console.log('   what cannot be done is greyed, with the reason');
  await wordOf(4, 3).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  const last = await page.evaluate(() => [...document.querySelectorAll('#rfpop .rfgo')].map(b =>
    ({edge: b.dataset.edge, off: b.disabled, small: b.querySelector('small').textContent})));
  assert(last.find(x => x.edge === 'end').off && /last line/.test(last.find(x => x.edge === 'end').small),
         'the last line cannot end earlier: ' + JSON.stringify(last));
  await wordOf(2, 0).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  const firstWord = await page.evaluate(() => {
    const b = document.querySelector('#rfpop .rfgo[data-edge="start"]');
    return {off: b.disabled, small: b.querySelector('small').textContent};
  });
  assert(firstWord.off && /already begins here/.test(firstWord.small), 'a line already begins at its first word: ' + firstWord.small);
  await page.keyboard.press('Escape');
  assert(await page.evaluate(() => document.getElementById('rfpop').hidden && document.body.classList.contains('reflowing')),
         'Esc puts the card away and keeps the mode');

  console.log('   fine-tune opens the timings sheet at the line that moved, and the join can be heard (the choice made on its key)');
  await wordOf(1, 4).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.keyboard.press('e');                     // E: end the line here
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  const start2 = (await segsOnDisk())[2].start;
  await page.click('#rfplay');
  await sleep(100);
  const heard = (await calls(page)).filter(c => c[0] === 'seek').pop();
  assert(heard && Math.abs(heard[1] - (start2 - 1.5)) < 0.01, 'the join is played from a second and a half before: ' + JSON.stringify(heard));
  await page.click('#rftune');
  await page.waitForSelector('.tl-root');
  const sheetAt = await page.evaluate(() => (document.querySelector('.tl-now .tl-say') || {}).textContent || '');
  assert(sheetAt.split(' ')[0] === String(start2) || /^\d+:\d+/.test(sheetAt), 'the sheet opens on that line: ' + sheetAt.slice(0, 40));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.tl-root'));
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));

  console.log('   a page that is out of date is refused by name');
  const stale = JSON.parse(original[0]);
  stale.segments[2].text = stale.segments[2].text + ' ';      // not what the page holds, once the spaces are kept
  stale.segments[1].text = stale.segments[1].text.replace('دلم', 'قلبم');
  stale.segments[1].chunks[2].fa = 'چقدر قلبم';
  await Deno.writeTextFile(`${DIR}/annotations.json`, JSON.stringify(stale, null, 1) + '\n');
  await Deno.writeTextFile(`${DIR}/transcript.txt`, original[1].replace('چقدر دلم', 'چقدر قلبم'));
  const staleBefore = [await onDisk('annotations.json'), await onDisk('transcript.txt')];
  await wordOf(1, 4).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => document.getElementById('rfsay').classList.contains('bad'));
  assert(/reload the player before moving words/.test(await page.evaluate(() => document.getElementById('rfsay').textContent)),
         'it says to reload');
  eq([await onDisk('annotations.json'), await onDisk('transcript.txt')], staleBefore, 'and nothing was written');
  await Deno.writeTextFile(`${DIR}/annotations.json`, original[0]);
  await Deno.writeTextFile(`${DIR}/transcript.txt`, original[1]);

  console.log('   a phrase flagged for review later is still flagged, once, where it now is');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.body.classList.contains('reflowing'));
  await page.locator('.seg[data-i="1"] .fa .w[data-j="2"]').evaluate(e => e.closest('.seg').scrollIntoView({block: 'start'}));
  await sleep(100);
  await page.hover('.seg[data-i="1"] .fa .w[data-j="2"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.click('#cloud .mklater');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="1"] .w.later-mark').length === 1);
  await page.mouse.move(5, 5);
  await page.keyboard.press('m');
  await wordOf(1, 4).click();                                    // «همه.»: the flagged «چقدر دلم» goes down
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="2"] .w.later-mark').length === 1, null, {timeout: 6000});
  eq(await page.evaluate(() => ({n: ParsehLater.count({ref: ParsehLater.refOf(location.pathname)}),
                                 on: [...document.querySelectorAll('.w.later-mark')].map(e => e.textContent)})),
     {n: 1, on: ['چقدر دلم']}, 'one flag, on the phrase, in the line it went to');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="1"] .w.later-mark').length === 1, null, {timeout: 6000});
  eq(await page.evaluate(() => ParsehLater.count({ref: ParsehLater.refOf(location.pathname)})), 1, 'and Undo takes it back with the words');
  await page.evaluate(() => { const r = ParsehLater.list({ref: ParsehLater.refOf(location.pathname)}); return Promise.all(r.map(x => ParsehLater.remove(x.id, {toast: false}))); });

  console.log('   leaving the mode gives the lines their clicks back');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.body.classList.contains('reflowing'));
  assert(await page.evaluate(() => document.getElementById('rfdock').hidden &&
                             !document.querySelector('.rf-open') && !document.querySelector('.rf-pick')),
         'the dock, the marks and the pick are gone');
  await page.locator('.seg[data-i="3"] .fa .wd').first().click();
  await sleep(150);
  assert((await calls(page)).filter(c => c[0] === 'seek').pop()[1] === 26, 'a click replays the line again');

  console.log('   with the glosses below the line, a move draws the rows again');
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForSelector('.rows');
  await page.keyboard.press('m');
  await wordOf(1, 4).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  eq(await page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(s => s.querySelectorAll('.row').length)),
     [0, 2, 6, 3, 2], 'two phrases left the first line and six rows stand under the second');
  eq(await page.evaluate(() => document.querySelector('.seg[data-i="2"] .row .rfa .w').textContent), 'چقدر دلم',
     'the moved phrase has its row under its new line');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  await page.context().close();

  /* ====================================================== c) the start, settled into a pause */
  console.log('c) where the sound can be read, the new start is settled into the nearest pause');
  // a picture of the sound, as a YouTube video's recorded one is kept beside it: loud, but for a pause from
  // 9.9 to 10.5 seconds -- and the estimate from the words (b) is 10.8
  const peaks = Array.from({length: 900}, (_, k) => (k >= 198 && k < 210) ? 0 : 0.8);
  await Deno.writeTextFile(`${DIR}/waveform.json`, JSON.stringify({rate: 20, peaks}));
  page = await openPage();
  const before = [await onDisk('annotations.json'), await onDisk('transcript.txt')];
  await page.keyboard.press('m');
  await wordOf(1, 4).click();
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent) &&
                             !document.getElementById('rfdock').classList.contains('busy'), null, {timeout: 8000});
  const settled = (await segsOnDisk())[2].start;
  eq(settled, 10.2, 'the line starts in the middle of the pause, not where the words put it');
  assert(/settled in the nearest pause of the sound/.test(await page.evaluate(() => document.getElementById('rfsay').textContent)),
         'and the dock says so: ' + await page.evaluate(() => document.getElementById('rfsay').textContent));
  eq((await onDisk('transcript.txt')).includes('0:10.2\nچقدر دلم برای این لحظه برای صحبت کردن'), true, 'transcript.txt has the same start');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent), null, {timeout: 8000});
  eq([await onDisk('annotations.json'), await onDisk('transcript.txt')], before, 'Undo takes the words and the settling back, byte for byte');
  await page.context().close();

  /* ====================================================== d) a window with room has the button too */
  console.log('d) in a window with room the bar has the button too');
  page = await openPage({}, 1600);
  assert(await page.evaluate(() => !!document.getElementById('reflow').getClientRects().length), 'at 1600px the bar draws «move text»');
  await page.click('#reflow');
  await page.waitForFunction(() => document.body.classList.contains('reflowing'));
  assert(await page.evaluate(() => document.querySelector('header').getBoundingClientRect().height < 60), 'and the header is one row');
  eq(await page.evaluate(() => document.querySelector('[data-pg-row="reflow"]') === null ||
                         document.getElementById('reflow').classList.contains('on')), true, 'the button is lit');
  await page.click('#rfdone');
  await page.waitForFunction(() => !document.body.classList.contains('reflowing'));
  await page.evaluate(() => { const i = document.createElement('input'); i.id = 'typed'; document.body.appendChild(i); i.focus(); });
  await page.keyboard.press('m');
  assert(await page.evaluate(() => !document.body.classList.contains('reflowing')), 'an M typed into a box is the box\'s, and turns nothing on');
  await page.context().close();

  assert(errors.length === 0, 'no page threw anything: ' + JSON.stringify(errors));
  console.log(`\nplayer_lines: ${passed} checks passed`);
} finally {
  await browser.close();
  try { hub.kill(); } catch (_) { /* gone */ }
  await hub.status;
  await Deno.remove(WORK, {recursive: true});
}
Deno.exit(0);
