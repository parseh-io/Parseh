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
//   e) THE PHRASES SIDE BY SIDE (a0.6.2).  «Phrases laid out», under «Glosses below the line»: In rows is a)
//      to the pixel; Side by side sets the phrases of a line one after another under it, from the side the
//      language reads from, each a column with its reading, transliteration and meaning under it, every
//      line against the edge the text starts from, and the vocabulary and the notes under the columns.
//      Driven on a Persian, an Italian and a Japanese video; what a phrase's row could do, its column does.
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
// ---- the videos of part e (the phrases side by side), which no other part writes to.  A chunk here is
// [text, meaning, transliteration, vocabulary, note, kana].  A Persian one: a line long enough to wrap, a
// phrase with a vocabulary line, one with a vocabulary line and a note, a phrase nobody glossed, a run in
// another script (drawn bare, no column), a meaning far longer than its phrase, and a line written with
// its vowel marks.  An Italian one, read
// from the left, with no transliteration on most phrases.  A Japanese one, whose phrases have a reading.
const FLOW_FA = {id: 'fa-flow-c4d5e6', folder: 'persian', lang: 'fa', lines: [
  [0, 'Welcome.', null],
  [4, 'امروز می‌خوام با دوستام برم شمال چون هوا خیلی خوبه.',
   [['امروز', 'today', 'emruz'],
    ['می‌خوام', 'I want', 'mi-xām', 'خواستن xāstan to want · می‌خوام mixām I want (spoken)'],
    ['با دوستام', 'with my friends', 'bā dustām'],
    ['برم شمال', '(that) I go north', 'beram šomāl', 'شمال šomāl north; here: the Caspian coast', 'spoken for بروم'],
    ['چون هوا', 'because the weather', 'čun havā'],
    ['خیلی خوبه.', 'is very good', 'xeyli xube']]],
  [12, 'جاده چالوس چطوره؟ okay', [['جاده چالوس', 'the Chalus road', 'jādde-ye čālus'], ['چطوره؟'], ['okay']]],
  [18, 'هر چه بادا باد.',
   [['هر چه بادا باد.', 'come what may: word for word “whatever wind there be, let it be wind”, said when one stops ' +
     'worrying about how a thing will turn out and simply goes ahead with it', 'har če bādā bād']]],
  // a line written WITH its vowel marks, and a note on a phrase of it: what «Diacritics» has to redraw
  [26, 'کِتابِ مَن اینجاست.',
   [['کِتابِ مَن', 'my book', 'ketāb-e man', '', 'written here with its vowels'], ['اینجاست.', 'is here', 'injāst']]],
]};
const FLOW_IT = {id: 'it-flow-f7a8b9', folder: 'italian', lang: 'it', lines: [
  [0, 'Oggi voglio andare al mare con i miei amici.',
   [['Oggi', 'today'], ['voglio andare', 'I want to go', 'vòglio andàre', 'volere: to want', 'a modal and an infinitive'],
    ['al mare', 'to the seaside'], ['con i miei amici.', 'with my friends']]],
  [8, 'Poi mangiamo qualcosa.', [['Poi', 'then'], ['mangiamo qualcosa.', 'we eat something']]],
]};
const FLOW_JA = {id: 'ja-flow-a1c3e5', folder: 'japanese', lang: 'ja', lines: [
  [0, '今日は 天気が いいですね',
   [['今日は', 'today', 'kyō wa', '今日 きょう kyō today', '', 'きょうは'],
    ['天気が', 'the weather', 'tenki ga', '天気 てんき tenki weather', 'が marks the subject', 'てんきが'],
    ['いいですね', 'is nice, isn\'t it', 'ii desu ne', '', '', 'いいですね']]],
]};
const MORE = [FLOW_FA, FLOW_IT, FLOW_JA];

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
# the videos of part e: the same files, of three languages, with the fields part e reads
for m in json.loads(sys.argv[4]):
    dst = root / 'youtube' / 'videos' / m['folder'] / m['id']
    dst.mkdir(parents=True)
    (dst / 'video.json').write_text(json.dumps(
        {'id': m['id'], 'url': 'https://www.youtube.com/watch?v=' + m['id'], 'title': 'Side by side',
         'title_native': 'Side by side', 'channel': '', 'language': m['lang'], 'gloss': 'en', 'duration': '0:30'}),
        encoding='utf-8')
    segs, rows = [], []
    for start, text, chunks in m['lines']:
        rows += [CA.stamp_of(start), text]
        if chunks is None:
            segs.append({'start': start, 'text': text, 'plain': True})
            continue
        out = []
        for c in chunks:
            ch = {'fa': c[0]}
            for k, f in ((1, 'en'), (2, 'tr'), (3, 'voc'), (4, 'note'), (5, 'kana')):
                if len(c) > k and c[k]: ch[f] = c[k]
            out.append(ch)
        segs.append({'start': start, 'text': text, 'chunks': out})
    (dst / 'annotations.json').write_text(json.dumps(
        {'video': m['id'], 'language': m['lang'], 'segments': segs}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
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
const hub = new Deno.Command(PY, {args: ['-c', SERVE, WORK, String(port), JSON.stringify(VIDEO), JSON.stringify(MORE)],
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
async function openPage(storage = {}, width = 1280, video = VIDEO) {
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
  await page.goto(B + `/youtube/v/${video.id}/`);
  await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n, video.lines.length);
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

  /* ====================================================== e) the phrases side by side */
  console.log('e) the phrases side by side under the line');
  // a chip of the gear's «Phrases laid out», pressed as a hand presses it, and the panel shut again
  const layOut = async (page, label) => {
    await page.click('.pg-gear, [data-parseh-gear]');
    await page.waitForSelector('.pg-panel');
    const chip = page.locator('.pg-panel [data-pg-row="flow"] .pg-chip', {hasText: label});
    await chip.scrollIntoViewIfNeeded();
    await chip.click();
    await sleep(150);
    await page.evaluate(() => ParsehGear.mounted().close());
    await sleep(100);
  };
  const flowRow = page => page.evaluate(() => {
    const r = document.querySelector('.pg-panel [data-pg-row="flow"]'), why = r && r.querySelector('.pg-why');
    return r ? {name: r.querySelector('.pg-nametext').textContent, off: r.classList.contains('pg-off'),
                chips: [...r.querySelectorAll('.pg-chip')].map(c => [c.textContent, c.getAttribute('aria-checked'), c.disabled]),
                why: why && !why.hidden ? why.textContent : ''} : null;
  });
  // where every row of the page stands, to the tenth of a pixel, and what it says: what "as it was" is held to
  const rowsGeo = page => page.evaluate(() => JSON.stringify([...document.querySelectorAll('#segs .row')].map(r =>
    [r, r.querySelector('.rfa'), r.querySelector('.rgl')].map(e => { const b = e.getBoundingClientRect();
      return [Math.round(b.left * 10), Math.round(b.width * 10), Math.round(b.height * 10)]; }).concat([r.querySelector('.rgl').innerHTML]))));
  // one line's columns: each column's box, the edges of the TEXT of each of its lines (what the eye sees,
  // not the boxes), and the block under them
  const flowGeo = (page, i) => page.evaluate(i => {
    const seg = document.querySelector('.seg[data-i="' + i + '"]'), rows = seg.querySelector('.rows');
    const ink = e => { const r = document.createRange(); r.selectNodeContents(e);
      return [...r.getClientRects()].filter(b => b.width > 0).map(b => ({l: b.left, r: b.right, t: b.top, b: b.bottom})); };
    const box = e => { const b = e.getBoundingClientRect(); return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };
    const under = rows.querySelector('.fvoc');
    return {box: box(rows), cls: rows.className, dir: rows.getAttribute('dir'),
            cols: [...rows.querySelectorAll('.row')].map(r => ({j: r.dataset.j, box: box(r), rfa: box(r.querySelector('.rfa')),
              rgl: box(r.querySelector('.rgl')), w: ink(r.querySelector('.rfa .w')),
              lines: [...r.querySelectorAll('.rgl > *')].map(e => ({c: e.className, text: e.textContent, ink: ink(e),
                        style: getComputedStyle(e).fontStyle, col: getComputedStyle(e).color, size: getComputedStyle(e).fontSize})),
              ink: getComputedStyle(r.querySelector('.rfa')).color})),
            under: under ? {box: box(under), shown: !!under.getClientRects().length,
              items: [...under.children].map(e => ({c: e.className, f: e.dataset.for, j: e.dataset.j === undefined ? null : e.dataset.j,
                                                    text: e.textContent, lead: e.querySelector('.fph') ? e.querySelector('.fph').textContent : null}))} : null,
            font: parseFloat(getComputedStyle(rows).fontSize)};
  }, i);
  const near = (a, b, by = 2) => Math.abs(a - b) <= by;
  const stood = c => c.rgl.t >= c.rfa.b - 1 && c.lines.every(l => l.ink.every(b => near(b.r, c.w[0].r)));

  page = await openPage({}, 1280, FLOW_FA);
  assert(await page.evaluate(() => localStorage.getItem('yt_flow') === null && !document.body.classList.contains('glossflow') &&
                             !document.querySelector('.rows') && !document.getElementById('flow').getClientRects().length &&
                             document.getElementById('flow').textContent === 'side by side'),
         'off by default: no key, no rows, the body says nothing, and the page\'s own button is the gear\'s (not drawn on the bar)');
  await page.click('.pg-gear, [data-parseh-gear]');
  await page.waitForSelector('.pg-panel [data-pg-row="flow"]');
  let fr = await flowRow(page);
  eq([fr.name, fr.off, fr.chips, fr.why],
     ['Phrases laid out', true, [['In rows', 'true', true], ['Side by side', 'false', true]], 'Turn on Glosses below the line first.'],
     'while the glosses are not below the line the choice rests on In rows, and says why');
  eq(await page.evaluate(() => { const rs = [...document.querySelectorAll('.pg-panel [data-pg-group="watching"] [data-pg-row]')].map(r => r.dataset.pgRow);
       return rs[rs.indexOf('below') + 1]; }), 'flow', 'it hangs right under «Glosses below the line»');
  await page.evaluate(() => ParsehGear.mounted().close());
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForSelector('.rows');
  assert(await page.evaluate(() => !document.querySelector('.rows.flow, .fvoc') && !document.body.classList.contains('glossflow')),
         'the glosses below the line are in rows, as before');
  const rowsBefore = await rowsGeo(page);
  eq(await page.evaluate(() => { const r = document.querySelector('.seg[data-i="1"] .row[data-j="3"] .rgl');
       return [...r.children].map(e => e.className); }), ['tr', 'voc', 'en', 'note'], 'a row holds its vocabulary and its note beside the phrase');
  await shot(page, 'flow-fa-rows-before');

  await layOut(page, 'Side by side');
  await page.waitForSelector('.rows.flow');
  eq(await page.evaluate(() => [localStorage.getItem('yt_flow'), document.body.classList.contains('glossflow'),
                                document.getElementById('flow').classList.contains('on'),
                                [...document.querySelectorAll('#segs .seg')].map(s => s.querySelectorAll('.row').length)]),
     ['1', true, true, [0, 6, 2, 1, 2]], 'Side by side: the key is kept, the body and the page\'s own button say so, and every glossed phrase has its column');
  let g = await flowGeo(page, 1);
  eq([g.cls, g.dir], ['rows flow', 'rtl'], 'the flow says its own direction, the text\'s');
  assert(g.cols.every(c => near(c.box.t, g.cols[0].box.t, 1)), 'the columns of a line that fits stand on one row, their tops together');
  assert(g.cols.every((c, k) => !k || c.box.r < g.cols[k - 1].box.l + 1) && near(g.cols[0].box.r, g.box.r, 1),
         'in Persian the first phrase is the rightmost, at the right edge, and the others follow to its left');
  const gapX = g.cols[0].box.l - g.cols[1].box.r;
  assert(near(gapX, 0.82 * g.font, 1.5), 'the gap between two columns is .82 of the text\'s size: ' + gapX + ' at ' + g.font);
  for (const c of g.cols) {
    assert(c.rgl.t >= c.rfa.b - 1, 'phrase ' + c.j + ': its gloss is under it');
    eq(c.lines.map(l => l.c), ['tr', 'en'], 'phrase ' + c.j + ': the transliteration, then the meaning, and nothing else in the column');
    const right = c.w[0].r;
    assert(c.lines.every(l => l.ink.every(b => near(b.r, right))),
           'phrase ' + c.j + ': every line starts at the phrase\'s own right edge: ' + JSON.stringify([right, c.lines.map(l => l.ink.map(b => b.r))]));
    assert(near(c.box.w, Math.max(Math.max(...c.w.map(b => b.r)) - Math.min(...c.w.map(b => b.l)), ...c.lines.flatMap(l => l.ink.map(b => b.r - b.l))), 2),
           'phrase ' + c.j + ': the column is as wide as its widest line');
    eq([c.lines[0].style, c.lines[1].style, c.lines[0].size === c.lines[1].size, c.lines[1].col === c.ink, c.lines[0].col !== c.ink],
       ['normal', 'normal', true, true, true],
       'phrase ' + c.j + ': the transliteration upright and quieter, the meaning the same size in the text\'s own ink');
  }
  eq(await page.evaluate(() => document.querySelectorAll('.rows.flow .row :is(.voc, .note, .fv, .fn, .unwritten)').length), 0,
     'no vocabulary, no note and no «nothing glossed yet» inside a column');
  eq(g.under.items.map(x => [x.c, x.f, x.j]), [['fv', '1', null], ['fv', '3', null], ['fn', '3', null]],
     'under the columns: the vocabulary of each phrase that has one, and the note, in the phrases\' order, each saying whose it is and none a phrase');
  eq([g.under.items[0].text, g.under.items[2].lead, g.under.items[2].text],
     ['خواستن xāstan to want · می‌خوام mixām I want (spoken)', 'برم شمال', 'برم شمال spoken for بروم'],
     'the vocabulary line as it is written, and the note led by the phrase it is about');
  assert(g.under.box.t >= Math.max(...g.cols.map(c => c.box.b)) - 1 && near(g.under.box.w, g.box.w, 1),
         'that block is under the columns and as wide as the line');
  eq(await page.evaluate(() => document.querySelectorAll('.fvoc .row, .fvoc [data-j], .fvoc .w, .fvoc .wd').length), 0,
     'nothing in it is a row, a phrase or a word');
  // a phrase nobody glossed is its text alone; a run in another script has no column
  g = await flowGeo(page, 2);
  eq([g.cols.map(c => c.j), g.cols[1].lines.length, g.cols[1].rgl.h, g.under.shown], [['0', '1'], 0, 0, false],
     'a phrase nobody glossed is its text alone in its column, a run left as text has none, and a line with no vocabulary has no block');
  // a meaning far longer than its phrase wraps inside its column, each of its lines against the right edge
  g = await flowGeo(page, 3);
  const long = g.cols[0], en = long.lines[1];
  assert(en.ink.length >= 2 && long.box.w <= 22 * g.font + 1 && en.ink.every(b => near(b.r, long.w[0].r)),
         'a long meaning wraps inside a column no wider than 22em (' + long.box.w + '), every line of it against the phrase\'s right edge');
  await shot(page, 'flow-fa');

  console.log('   a narrow window wraps the columns, each new row from the right');
  await page.setViewportSize({width: 520, height: 900});
  await sleep(200);
  g = await flowGeo(page, 1);
  const firstTop = g.cols[0].box.t, wrapped = g.cols.filter(c => c.box.t > firstTop + 5);
  assert(wrapped.length > 0 && near(wrapped[0].box.r, g.box.r, 1), 'the columns wrap, and a new row starts at the right again');
  assert(near(wrapped[0].box.t - Math.max(...g.cols.filter(c => near(c.box.t, firstTop, 1)).map(c => c.box.b)), 0.55 * g.font, 1.5),
         'the rows of columns are .55 of the text\'s size apart');
  assert(g.cols.every(stood), 'and in every column the gloss is still under its phrase, against its right edge');
  eq(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'nothing runs sideways');
  await shot(page, 'flow-fa-narrow');
  await page.setViewportSize({width: 1280, height: 900});
  await sleep(200);

  console.log('   the Aa sizes are the layout\'s sizes');
  const sized = await page.evaluate(() => {
    const h = document.documentElement, was = [h.style.getPropertyValue('--yt-fa'), h.style.getPropertyValue('--yt-gl')];
    h.style.setProperty('--yt-fa', '30px'); h.style.setProperty('--yt-gl', '18px');
    const r = document.querySelector('.seg[data-i="1"] .row[data-j="0"]');
    const out = [getComputedStyle(r.querySelector('.rfa')).fontSize, getComputedStyle(r.querySelector('.tr')).fontSize,
                 getComputedStyle(r.querySelector('.en')).fontSize, getComputedStyle(document.querySelector('.seg[data-i="1"] .fvoc')).fontSize,
                 getComputedStyle(r.parentNode).columnGap];
    ['--yt-fa', '--yt-gl'].forEach((p, k) => { if (was[k]) h.style.setProperty(p, was[k]); else h.style.removeProperty(p); });
    return out;
  });
  eq(sized, ['30px', '18px', '18px', '18px', '24.6px'], 'the phrase is the text size, its lines and the block the gloss size, the gap follows the text');

  console.log('   pointing at a phrase of the line lights its column and opens no cloud');
  await page.hover('.seg[data-i="1"] .fa .w[data-j="2"]');
  await sleep(250);
  eq(await page.evaluate(() => [document.getElementById('cloud').hidden, [...document.querySelectorAll('.row.lit')].map(r => r.dataset.j),
       getComputedStyle(document.querySelector('.row.lit')).backgroundColor !== 'rgba(0, 0, 0, 0)']), [true, ['2'], true],
     'no cloud, and the column of that phrase is lit');
  await shot(page, 'flow-fa-lit');
  await page.mouse.move(5, 5);
  await sleep(200);
  eq(await page.evaluate(() => document.querySelectorAll('.row.lit').length), 0, 'put out when the pointer goes');

  console.log('   pointing at the phrase in its column opens its tools, and what is written there changes the column, the block and the file');
  await page.hover('.seg[data-i="1"] .row[data-j="2"] .rfa .w');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  const ftools = await page.evaluate(() => { const c = document.getElementById('cloud');
    return [!!c.querySelector('.tr, .en, .voc, .note, .unwritten'), !!c.querySelector('.mkedit'), !!c.querySelector('.mkcard'),
            !!c.querySelector('.mkcopy'), !!c.querySelector('.mklater'), c.querySelectorAll('.sw').length]; });
  eq(ftools, [false, true, true, true, true, 5], 'the tools — ✎ edit, + card, copy, review later, the colours — and no gloss said twice');
  await shot(page, 'flow-fa-tools');
  await page.click('#cloud .mkedit');
  await page.waitForSelector('#cloud .ef[data-f="en"]');
  await page.fill('#cloud .ef[data-f="en"]', 'with my dear friends');
  await page.fill('#cloud .ef[data-f="voc"]', 'دوست dust friend');
  await page.click('#cloud .esave');
  await page.waitForFunction(() => /saved/.test(document.querySelector('#cloud .cstat').textContent));
  g = await flowGeo(page, 1);
  eq([g.cols[2].lines.map(l => [l.c, l.text]), g.under.items.map(x => [x.c, x.f]), g.under.items[1].text],
     [[['tr', 'bā dustām'], ['en', 'with my dear friends']], [['fv', '1'], ['fv', '2'], ['fv', '3'], ['fn', '3']], 'دوست dust friend'],
     'the column says the new meaning, and the new vocabulary line stands in the block, in its phrase\'s place');
  const flowDisk = async (i, j) => JSON.parse(await Deno.readTextFile(`${WORK}/root/youtube/videos/persian/${FLOW_FA.id}/annotations.json`)).segments[i].chunks[j];
  const fdisk = await flowDisk(1, 2);
  eq([fdisk.en, fdisk.voc], ['with my dear friends', 'دوست dust friend'], 'and the file has both');
  await page.click('#cloud .ecancel');
  await page.mouse.move(5, 5);
  await sleep(300);
  // a phrase nobody glossed, written from its column: the column gains its lines
  await page.hover('.seg[data-i="2"] .row[data-j="1"] .rfa .w');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.click('#cloud .mkedit');
  await page.waitForSelector('#cloud .ef[data-f="en"]');
  await page.fill('#cloud .ef[data-f="tr"]', 'četowre');
  await page.fill('#cloud .ef[data-f="en"]', 'how is it?');
  await page.fill('#cloud .ef[data-f="note"]', 'spoken for چطور است');
  await page.click('#cloud .esave');
  await page.waitForFunction(() => /saved/.test(document.querySelector('#cloud .cstat').textContent));
  g = await flowGeo(page, 2);
  eq([g.cols[1].lines.map(l => l.text), g.under.shown, g.under.items.map(x => [x.c, x.f, x.lead])],
     [['četowre', 'how is it?'], true, [['fn', '1', 'چطوره؟']]], 'a phrase glossed from its column gains its lines, and its note opens the block under the line');
  await page.click('#cloud .ecancel');
  await page.mouse.move(5, 5);
  await sleep(300);
  await page.hover('.seg[data-i="1"] .row[data-j="0"] .rfa .w');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.click('#cloud .sw.hl-red');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="1"] .fa .w.hl-red').length === 1 &&
                                   document.querySelectorAll('.seg[data-i="1"] .row .rfa .w.hl-red').length === 1);
  assert(true, 'a colour marks the phrase in its column and in its line');
  await shot(page, 'flow-fa-colour');
  await page.click('#cloud .sw.no');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="1"] .w.hl-red').length === 0);
  await page.mouse.move(5, 5);
  await sleep(300);

  console.log('   the choice is kept, rests while the glosses are in the cloud, and In rows is the rows as they were');
  await page.reload();
  await page.waitForSelector('.rows.flow');
  assert(await page.evaluate(() => document.body.classList.contains('glossflow') && document.querySelectorAll('.fvoc').length === 4),
         'a reload keeps the layout');
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForFunction(() => !document.querySelector('.rows'));
  eq(await page.evaluate(() => [document.querySelectorAll('#segs .row, #segs .fvoc').length, document.body.classList.contains('glossflow'),
                                localStorage.getItem('yt_flow')]), [0, false, '1'],
     'the glosses back in the cloud: no row and no column at all, the body says no layout, and the choice is still kept');
  await page.hover('.seg[data-i="1"] .fa .w[data-j="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  assert(await page.evaluate(() => !!document.querySelector('#cloud .en')), 'and the cloud is the whole gloss again');
  await page.mouse.move(5, 5);
  await sleep(300);
  await page.click('.pg-gear, [data-parseh-gear]');
  await page.waitForSelector('.pg-panel [data-pg-row="flow"]');
  fr = await flowRow(page);
  eq([fr.off, fr.chips.map(c => c[1]), fr.chips.map(c => c[2]), fr.why], [true, ['false', 'true'], [true, true], 'Turn on Glosses below the line first.'],
     'the choice rests, still saying Side by side, with its reason');
  await page.evaluate(() => ParsehGear.mounted().close());
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForSelector('.rows.flow');
  await layOut(page, 'In rows');
  await page.waitForFunction(() => document.querySelector('.rows') && !document.querySelector('.rows.flow'));
  eq(await page.evaluate(() => [localStorage.getItem('yt_flow'), document.body.classList.contains('glossflow'), document.querySelectorAll('.fvoc').length]),
     ['0', false, 0], 'In rows: the key, the body and the page agree');
  await page.context().close();
  // what was written above is put back -- from the columns -- so that the rows can be held to what they were
  page = await openPage({yt_below: '1', yt_flow: '1'}, 1280, FLOW_FA);
  for (const [i, j, f] of [[1, 2, {en: 'with my friends', voc: ''}], [2, 1, {tr: '', en: '', note: ''}]]) {
    await page.hover(`.seg[data-i="${i}"] .row[data-j="${j}"] .rfa .w`);
    await page.waitForFunction(() => !document.getElementById('cloud').hidden);
    await page.click('#cloud .mkedit');
    await page.waitForSelector('#cloud .ef[data-f="en"]');
    for (const k in f) await page.fill(`#cloud .ef[data-f="${k}"]`, f[k]);
    await page.click('#cloud .esave');
    await page.waitForFunction(() => /saved/.test(document.querySelector('#cloud .cstat').textContent));
    await page.click('#cloud .ecancel');
    await page.mouse.move(5, 5);
    await sleep(300);
  }
  g = await flowGeo(page, 2);
  eq([g.cols[1].lines.length, g.under.shown], [0, false], 'a gloss emptied from its column leaves the phrase alone again, and the block goes with its last line');
  await layOut(page, 'In rows');
  await page.waitForFunction(() => document.querySelector('.rows') && !document.querySelector('.rows.flow'));
  eq(await rowsGeo(page), rowsBefore, 'In rows: every row stands exactly where it stood before the layout was ever chosen, with the same gloss');
  await page.context().close();

  console.log('   the line being played: a column lit there is not the line\'s own colour');
  page = await openPage({yt_below: '1', yt_flow: '1'}, 1280, FLOW_FA);
  await page.waitForSelector('.rows.flow');
  const litAt = async i => {
    await page.hover(`.seg[data-i="${i}"] .fa .w[data-j="0"]`);
    await page.waitForFunction(i => !!document.querySelector('.seg[data-i="' + i + '"] .row.lit'), i);
    const out = await page.evaluate(i => { const seg = document.querySelector('.seg[data-i="' + i + '"]'), r = seg.querySelector('.row.lit');
      return {j: r.dataset.j, row: getComputedStyle(r).backgroundColor, ring: getComputedStyle(r).boxShadow, seg: getComputedStyle(seg).backgroundColor,
              air: seg.classList.contains('on-air'), cloud: document.getElementById('cloud').hidden}; }, i);
    return out;
  };
  await page.evaluate(() => document.querySelector('.seg[data-i="1"] .lab').click());
  await page.waitForFunction(() => { const s = document.querySelector('#segs .seg.on-air'); return s && +s.dataset.i === 1; });
  await page.mouse.move(5, 5);
  await sleep(200);
  let lit = await litAt(1);
  assert(lit.air && lit.cloud && lit.j === '0' && lit.row !== 'rgba(0, 0, 0, 0)' && lit.row !== lit.seg && lit.ring.indexOf(lit.seg) !== 0,
         'on the playing line the column pointed at from the line is lit in a colour that is not the line\'s: ' + JSON.stringify(lit));
  await shot(page, 'flow-fa-lit-onair');
  for (const theme of ['dark', 'sepia']) {
    await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
    await page.mouse.move(5, 5);
    await sleep(200);
    const l = await litAt(1);
    assert(l.air && l.row !== 'rgba(0, 0, 0, 0)' && l.row !== l.seg, theme + ': the same, the column\'s colour is not the playing line\'s: ' + JSON.stringify([l.row, l.seg]));
    await shot(page, 'flow-fa-lit-onair-' + theme);
  }
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  const litOther = await litAt(4);
  assert(!litOther.air && litOther.row !== 'rgba(0, 0, 0, 0)' && litOther.row !== lit.row,
         'and on a line that is not playing it is lit in the highlight, as a row is: ' + JSON.stringify(litOther));
  await page.mouse.move(5, 5);
  await sleep(200);

  console.log('   Diacritics: the phrase in its column, and the phrase a note is led by, follow the line');
  const marked = /[ً-ْ]/;
  const seen4 = () => page.evaluate(() => { const s = document.querySelector('.seg[data-i="4"]');
    return [s.querySelector('.fa .w[data-j="0"]').textContent, s.querySelector('.row[data-j="0"] .rfa .w').textContent,
            s.querySelector('.fvoc .fn .fph').textContent, s.querySelector('.fvoc .fn').textContent, s.querySelectorAll('.row').length, s.querySelectorAll('.fvoc > *').length]; });
  eq(await seen4(), ['کِتابِ مَن', 'کِتابِ مَن', 'کِتابِ مَن', 'کِتابِ مَن written here with its vowels', 2, 1], 'with its marks: the line, the column and the note\'s lead say the phrase as written');
  await gearSwitch(page, 'Diacritics');
  await page.waitForFunction(() => document.querySelector('.seg[data-i="4"] .fa .w[data-j="0"]').textContent === 'کتاب من');
  let s4 = await seen4();
  eq(s4, ['کتاب من', 'کتاب من', 'کتاب من', 'کتاب من written here with its vowels', 2, 1], 'Diacritics off: the column and the note\'s lead are drawn without the marks, with the line');
  assert(!s4.slice(0, 4).some(t => marked.test(t)), 'no mark is left in any of the three');
  await gearSwitch(page, 'Diacritics');
  await page.waitForFunction(() => document.querySelector('.seg[data-i="4"] .fa .w[data-j="0"]').textContent === 'کِتابِ مَن');
  eq((await seen4()).slice(0, 3), ['کِتابِ مَن', 'کِتابِ مَن', 'کِتابِ مَن'], 'and on again all three have them back');

  console.log('   a layout chosen while a phrase is being edited is drawn when the editor closes');
  const openEditAt = async (i, j) => {
    await page.mouse.move(5, 5);
    await sleep(300);
    await page.hover(`.seg[data-i="${i}"] .row[data-j="${j}"] .rfa .w`);
    await page.waitForFunction(() => !document.getElementById('cloud').hidden && !!document.querySelector('#cloud .mkedit'));
    await page.click('#cloud .mkedit');
    await page.waitForSelector('#cloud .ef[data-f="en"]');
  };
  const drawn = () => page.evaluate(() => [localStorage.getItem('yt_below'), localStorage.getItem('yt_flow'), document.body.classList.contains('glossbelow'),
    document.body.classList.contains('glossflow'), document.querySelectorAll('#segs .rows.flow').length, document.querySelectorAll('#segs .rows:not(.flow)').length,
    !document.getElementById('cloud').hidden && document.getElementById('cloud').classList.contains('editing')]);
  await openEditAt(1, 2);
  await layOut(page, 'In rows');
  eq(await drawn(), ['1', '0', true, false, 4, 0, true], 'In rows chosen with the editor open: kept and said, and the page is not drawn again under the editor');
  await page.click('#cloud .ecancel');
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  eq(await drawn(), ['1', '0', true, false, 0, 4, false], 'the editor closed: every line is in rows, as the gear says');
  await openEditAt(1, 2);
  await layOut(page, 'Side by side');
  eq((await drawn()).slice(4), [0, 4, true], 'and the other way: still rows while the editor is open');
  await page.click('#cloud .ecancel');
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  eq(await drawn(), ['1', '1', true, true, 4, 0, false], 'closed: side by side');
  await openEditAt(1, 2);
  await gearSwitch(page, 'Glosses below the line');
  eq((await drawn()).slice(2), [false, false, 4, 0, true], 'the glosses sent back to the cloud with the editor open: the rows wait for it');
  await page.click('#cloud .ecancel');
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  eq(await drawn(), ['0', '1', false, false, 0, 0, false], 'closed: no row is left on the page');
  await gearSwitch(page, 'Glosses below the line');
  await page.waitForSelector('.rows.flow');
  eq(await drawn(), ['1', '1', true, true, 4, 0, false], '(and below the line again, side by side, for what follows)');

  // what a line's columns and block must say, read from the file: a column's lines are the fields its phrase
  // has, the block the vocabulary and the note of each phrase in order
  const segOnDisk = async i => JSON.parse(await Deno.readTextFile(`${WORK}/root/youtube/videos/persian/${FLOW_FA.id}/annotations.json`)).segments[i];
  const drawnSeg = i => page.evaluate(i => { const s = document.querySelector('.seg[data-i="' + i + '"]');
    return {cols: [...s.querySelectorAll('.rows.flow .row')].map(r => [+r.dataset.j, r.querySelector('.rfa .w').textContent, [...r.querySelectorAll('.rgl > *')].map(e => [e.className, e.textContent])]),
            under: [...s.querySelectorAll('.fvoc > *')].map(e => [e.className, +e.dataset.for, e.querySelector('.fph') ? e.querySelector('.fph').textContent : e.textContent])}; }, i);
  const agrees = async (i, n, m) => {
    const sg = await segOnDisk(i), d = await drawnSeg(i);
    eq(d.cols.length, n, m + ': line ' + i + ' has ' + n + ' columns');
    eq(d.cols, d.cols.map(c => { const ch = sg.chunks[c[0]]; return [c[0], ch.fa, ['tr', 'en'].filter(f => ch[f]).map(f => [f, ch[f]])]; }),
       m + ': each column of line ' + i + ' says its phrase, its transliteration and its meaning as the file has them');
    eq(d.under, sg.chunks.flatMap((ch, j) => (ch.voc ? [['fv', j, ch.voc]] : []).concat(ch.note ? [['fn', j, ch.fa]] : [])),
       m + ': and the block under line ' + i + ' is the vocabulary and the notes the file has, each under its phrase\'s number');
    return d;
  };

  console.log('   a phrase cut in two and joined again: the columns and the block are drawn from what was written');
  await agrees(1, 6, 'before');
  const sheet = async (i, j, which, n) => {
    await openEditAt(i, j);
    await page.click(`#cloud .edv[data-dv="${which}"]`);
    await page.waitForFunction(n => !document.querySelector('#dvbox').hidden && document.querySelectorAll('#dvpair .dvcol').length === n, n);
    await page.click('#dvdo');
    await page.waitForFunction(() => /done/.test(document.querySelector('#dvstat').textContent), null, {timeout: 20000});
    await page.click('#dvdo');                  // the sheet's close
    await page.waitForFunction(() => document.querySelector('#dvbox').hidden);
    await page.waitForSelector('.seg[data-i="' + i + '"] .rows.flow');
  };
  await sheet(1, 3, 'split', 2);
  let cutDrawn = await agrees(1, 7, 'cut in two');
  eq([cutDrawn.cols[3][1], cutDrawn.cols[4][1], cutDrawn.under.filter(x => x[0] === 'fn').map(x => [x[1], x[2]])], ['برم', 'شمال', [[3, 'برم']]],
     'the two halves each have a column, and the note is led by the half that kept it');
  await shot(page, 'flow-fa-cut');
  await sheet(1, 3, 'next', 1);
  cutDrawn = await agrees(1, 6, 'joined again');
  eq([cutDrawn.cols[3][1], cutDrawn.under.map(x => [x[0], x[1]])], ['برم شمال', [['fv', 1], ['fv', 3], ['fn', 3]]], 'one column again, its vocabulary and its note under the line');

  console.log('   move text between lines: the columns go with their words, and the vocabulary and the note with them');
  const beforeMove = [await drawnSeg(1), await drawnSeg(2)];
  await page.mouse.move(5, 5);
  await sleep(300);
  await gearSwitch(page, 'Move text between lines');
  await page.waitForFunction(() => document.body.classList.contains('reflowing'));
  await wordOf(1, 3).click();                        // «دوستام»: the line ends here, «برم شمال» and what follows go down
  await page.waitForSelector('#rfpop:not([hidden])');
  await page.click('#rfpop .rfgo[data-edge="end"]');
  await page.waitForFunction(() => /^Moved/.test(document.getElementById('rfsay').textContent));
  await agrees(1, 3, 'moved');
  const down = await agrees(2, 5, 'moved');
  eq([down.cols.map(c => c[1]), down.under], [['برم شمال', 'چون هوا', 'خیلی خوبه.', 'جاده چالوس', 'چطوره؟'], [['fv', 0, 'شمال šomāl north; here: the Caspian coast'], ['fn', 0, 'برم شمال']]],
     'the phrases that went down are columns of the next line, from its start, and the vocabulary and the note went with their phrase, numbered as it now is');
  eq(await page.evaluate(() => [document.querySelectorAll('#segs .rows.flow').length, document.querySelectorAll('#segs .rows:not(.flow)').length,
       [...document.querySelectorAll('.seg[data-i="2"] .rows.flow .row')].every((r, k, a) => !k || r.getBoundingClientRect().right < a[k - 1].getBoundingClientRect().left + 1 ||
                                                                                               r.getBoundingClientRect().top > a[k - 1].getBoundingClientRect().top + 5)]),
     [4, 0, true], 'both lines are still side by side, each column after the one before it');
  await shot(page, 'flow-fa-moved');
  await page.click('#rfundo');
  await page.waitForFunction(() => /^Taken back/.test(document.getElementById('rfsay').textContent));
  eq([await drawnSeg(1), await drawnSeg(2)], beforeMove, 'Undo: the two lines\' columns and blocks are what they were');
  await agrees(1, 6, 'taken back');
  await page.click('#rfdone');
  await page.waitForFunction(() => !document.body.classList.contains('reflowing'));
  await page.context().close();

  console.log('   a language read from the left: the first phrase at the left, every line against the left edge');
  page = await openPage({yt_below: '1', yt_flow: '1'}, 1280, FLOW_IT);
  await page.waitForSelector('.rows.flow');
  g = await flowGeo(page, 0);
  eq([g.dir, g.cols.length], ['ltr', 4], 'an Italian line: the flow reads from the left');
  assert(near(g.cols[0].box.l, g.box.l, 1) && g.cols.every((c, k) => !k || c.box.l > g.cols[k - 1].box.r - 1) &&
         g.cols.every(c => near(c.box.t, g.cols[0].box.t, 1)), 'the first phrase is the leftmost, the others follow to its right, tops together');
  assert(g.cols.every(c => c.lines.every(l => l.ink.every(b => near(b.l, c.w[0].l)))), 'every line of a column starts at the phrase\'s left edge');
  eq(g.cols.map(c => c.lines.map(l => l.c)), [['en'], ['tr', 'en'], ['en'], ['en']],
     'a phrase without a transliteration has its meaning right under it: an empty line takes no room');
  assert(near(g.cols[0].rgl.t, g.cols[0].rfa.b, 1) && near(g.cols[0].lines[0].ink[0].t, g.cols[1].lines[0].ink[0].t, 3),
         'the meaning of a phrase without one stands where its neighbour\'s transliteration does');
  eq(g.under.items.map(x => [x.c, x.f, x.lead, x.text]),
     [['fv', '1', null, 'volere: to want'], ['fn', '1', 'voglio andare', 'voglio andare a modal and an infinitive']], 'its vocabulary and its note are under the columns');
  await shot(page, 'flow-it');
  await page.context().close();

  console.log('   a language with a reading: the reading first in the column');
  page = await openPage({yt_below: '1', yt_flow: '1'}, 1280, FLOW_JA);
  await page.waitForSelector('.rows.flow');
  g = await flowGeo(page, 0);
  eq(g.cols.map(c => c.lines.map(l => l.c)), [['kana', 'tr', 'en'], ['kana', 'tr', 'en'], ['kana', 'tr', 'en']],
     'a Japanese column: the reading, the transliteration, the meaning');
  eq(g.under.items.map(x => [x.c, x.f, x.lead]), [['fv', '0', null], ['fv', '1', null], ['fn', '1', '天気が']],
     'and the note is led by the phrase as it is written, without the reading hung over it');
  await shot(page, 'flow-ja');
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
