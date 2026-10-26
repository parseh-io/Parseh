// SPDX-License-Identifier: GPL-3.0-or-later
// THE VIDEO PLAYER'S GEAR, ⚙ page (a0.5.0), driven on the real player page.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/gear_player.mjs
//   SHOTS=<dir> also saves a screenshot of each look   PARTS=a,b runs only those parts
//
// WHAT IS DRIVEN, and how: the real hub (serve.main on a temporary tree, the dictionaries, the
// settings store and the clip tray all inside it) serves the real player page for videos made
// here -- a Persian one and an Arabic one written WITH their vowel marks, a Persian one without,
// an English one a dictionary is installed for, a Japanese one and a Chinese one -- and Chromium
// opens it as a computer (1280x800, a mouse), as a phone (390x844, a finger, the mobile pages)
// and as a phone held sideways (844x390).  YouTube's player is the one fake there is: a page
// that stands in for www.youtube.com/iframe_api, so a video can be said to be at 12 seconds.
// Everything else is the page's own script, the toolkit's own panel and the hub's own answers.
//
// EVERY ROW OF THE PANEL is pressed (a mouse clicks it, a finger taps it) and what is read is
// the REAL control it stands for -- the page's own button and the key it keeps -- and the real
// page it changes (the transcript, the layout, the video's size), and then the row is pressed
// back.  Nothing here asks whether a property is set where the page could say otherwise.
//   a) the page's own bar: the names the owner chose, what lives only in the gear, the gear
//   b) the panel's groups, in the order the plan gives, each saying where it is kept
//   c) Watching & reading: every row, both ways, and the page behind it
//   d) Looking a word up, Playback, Text, Colours, Interface: every row, both ways
//   e) the bar under the video and the «Video size» slider keep each other in step
//   f) Diacritics: a Persian and an Arabic video, and one with nothing to put away
//   g) Aa opens the gear at Text, and again to put it away
//   h) the keys survive a reload; the person's own (the skip, the colours) cross two browsers
//   i) the phone: no ⋯, the first line, the sheet at half height on its INDEX of themes (a0.5.4) with what each is set to,
//      a theme's rows, Aa on Text (a second press shuts it), the Keep buttons only while their theme is on stage
//   j) the phone held sideways and its whole screen: no gear, its own small Aa, the lines around
//   k) nothing overflows, from 320 to 1280, with the panel up and shut; the three themes
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const td = new TextDecoder();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const SHOTS = Deno.env.get('SHOTS') || '';
const PARTS = (Deno.env.get('PARTS') || '').split(',').filter(Boolean);
const wanted = p => !PARTS.length || PARTS.includes(p);
const shot = async (page, name) => { if (SHOTS) await page.screenshot({path: `${SHOTS}/${name}.png`}); };

let passed = 0;
const errors = [];
const assert = (v, m) => { if (!v) throw new Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
  m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));

// ---- the videos
// A chunk is [text, meaning, vocabulary, transliteration, kana]; '' for a line nobody wrote.
// plain: a chunk that is left as text (an import's)
// a long one (a page that can be scrolled), with a run left as text, a run in another script, a
// chunk with a dagger alif (U+0670) -- which Persian's marks do not include -- and the English framing
const FA = {folder: 'persian', id: 'fa-marks-a1b2c3', lang: 'fa', title: 'Persian with its marks', caps: [
  {start: 0, text: 'Welcome to the lesson.', plain: true},
  {start: 2, text: 'هیچ جایِ دُنیا تَروُ خُشک را', chunks: [
    ['هیچ جایِ دُنیا', 'nowhere in the world', 'جا jā place', 'hič jā-ye donyā'], ['تَروُ خُشک را', 'the wet and the dry']]},
  {start: 4, text: 'مِثلِ ایران okay', chunks: [['مِثلِ ایران', 'like Iran'], ['okay']]},
  {start: 6, text: 'سالِ نو', chunks: [{fa: 'سالِ نو', plain: true}]},
  {start: 8, text: 'نِمی سوزانَند.', chunks: [['نِمی', 'not'], ['سوزانَند.', 'they burn']]},
  {start: 9, text: 'ر\u064E\u062D\u0645\u0670\u0646', chunks: [['ر\u064E\u062D\u0645\u0670\u0646', 'merciful']]},
]};
for (let k = 0; k < 25; k++)
  FA.caps.push({start: 10 + 2 * k, text: 'جایِ دُنیا تَروُ خُشک', chunks: [['جایِ دُنیا', 'the place of the world'], ['تَروُ خُشک', 'the wet and the dry']]});
// the same written in the Arabic script of the Quran, with a dagger alif (U+0670), which Arabic's
// marks include and Persian's do not
const AR = {folder: 'arabic', id: 'ar-marks-d4e5f6', lang: 'ar', title: 'Arabic with its marks', caps: [
  {start: 2, text: 'ٱلْحَمْدُ لِلَّهِ', chunks: [['ٱلْحَمْدُ', 'praise'], ['لِلَّهِ', 'to God']]},
  {start: 4, text: 'ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ', chunks: [['ٱلرَّحْمَـٰنِ', 'the Most Gracious'], ['ٱلرَّحِيمِ', 'the Most Merciful']]},
]};
const FAPLAIN = {folder: 'persian', id: 'fa-plain-b2c3d4', lang: 'fa', title: 'Persian with none', caps: [
  {start: 2, text: 'هیچ جای دنیا تر و خشک را', chunks: [['هیچ جای دنیا', 'nowhere in the world'], ['تر و خشک را', 'the wet and the dry']]},
  {start: 4, text: 'مثل ایران', chunks: [['مثل ایران', 'like Iran']]},
]};
const EN = {folder: 'english', id: 'en-lines-c3d4e5', lang: 'en', title: 'Four lines', caps: [
  {start: 0, text: 'Good morning, friends.', plain: true},
  {start: 2, text: 'The old market opens early.', chunks: [['The old market', 'the place of the stalls', 'market: where things are sold'], ['opens early.']]},
  {start: 4, text: 'Bring a bag today.', chunks: [['Bring a bag', 'come with something to carry', 'bag: a soft carrier'], ['today.']]},
  {start: 6, text: 'We buy fresh bread.', chunks: [['We buy', 'we pay for'], ['fresh bread.']]},
]};
const JA = {folder: 'japanese', id: 'ja-lines-d1e2f3', lang: 'ja', title: 'Japanese lines', caps: [
  {start: 2, text: 'こんにちは、 みなさん', chunks: [
    ['こんにちは、', 'hello,', 'こんにちは konnichiwa hello, good afternoon', 'konnichiwa,', 'こんにちは、'],
    ['みなさん', 'everyone', '皆さん みなさん minasan everyone (polite)', 'minasan', 'みなさん']]},
  {start: 4, text: '今日は 天気が いいですね', chunks: [
    ['今日は', 'today', '今日 きょう kyō today', 'kyō wa', 'きょうは'],
    ['天気が', 'the weather', '天気 てんき tenki weather', 'tenki ga', 'てんきが'],
    ['いいですね', 'is nice, isn\'t it', 'いい ii good', 'ii desu ne', 'いいですね']]},
]};
const ZH = {folder: 'chinese', id: 'zh-lines-e4f5a6', lang: 'zh', title: 'Chinese lines', caps: [
  {start: 2, text: '你好， 我想要一杯茶', chunks: [
    ['你好，', 'hello,', '你 nǐ you; 好 hǎo good', 'nǐ hǎo'], ['我想要一杯茶', 'I would like a cup of tea', '茶 chá tea', 'wǒ xiǎng yào yì bēi chá']]},
  {start: 4, text: '绿茶， 谢谢', chunks: [['绿茶，', 'green tea,', '绿茶 lǜchá green tea', 'lǜchá'], ['谢谢', 'thank you', '谢谢 xièxie thanks', 'xièxie']]},
]};
const VIDEOS = [FA, AR, FAPLAIN, EN, JA, ZH];
// what the dictionaries hold: English's senses are English definitions (the switches under the
// dictionary are offered only for it), Persian's are translations
const DICTS = {
  en: [['old', '', 'adj', 'of great age, said the test dictionary'], ['market', '', 'noun', 'a place of buying and selling'],
       ['bag', '', 'noun', 'a soft carrier']],
  fa: [['هیچ', 'hič', 'det', 'no, none'], ['جا', 'jā', 'noun', 'place']],
};

// ---- the hub: the real one, on a temporary tree with nothing of this machine's in it
const WORK = await Deno.makeTempDir({prefix: 'parseh-gear-player-'});
const SERVE = String.raw`
import json, os, sys
from pathlib import Path
tmp, port = Path(sys.argv[1]), int(sys.argv[2])
repo = Path.cwd()
sys.path[:0] = [str(repo / p) for p in ('markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.')]
import lookup, corpus, getmt
lookup.DICT_DIR = str(tmp / 'dict')
corpus.CORPUS_DIR = str(tmp / 'nocorpus')
getmt.MT_DIR = str(tmp / 'nomt')
getmt.ENGINE_DIR = str(tmp / 'nomt' / 'engine')
os.makedirs(lookup.DICT_DIR, exist_ok=True)
for code, rows in json.loads(sys.argv[3]).items():
    c = lookup.create(lookup.path_for(code))
    for head, translit, pos, sense, *forms in rows:
        cur = c.execute("INSERT INTO entry (headword, translit, pos, sense) VALUES (?,?,?,?)", (head, translit, pos, sense))
        for form in [head] + forms:
            c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (form, cur.lastrowid, ''))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [('lang', code), ('source', 'a test dictionary'), ('licence', 'none')])
    c.commit()
    c.close()
root = tmp / 'root'
(root / 'youtube').mkdir(parents=True)
os.symlink(str(repo / 'lib'), str(root / 'lib'))
os.symlink(str(repo / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
for d in ('library', 'exercises', 'anki'):
    (tmp / d).mkdir()
for v in json.loads(sys.argv[4]):
    dst = root / 'youtube' / 'videos' / v['folder'] / v['id']
    dst.mkdir(parents=True)
    # a video YouTube plays: no film of its own
    (dst / 'video.json').write_text(json.dumps(
        {'id': v['id'], 'url': 'https://www.youtube.com/watch?v=' + v['id'], 'title': v['title'],
         'title_native': v['title'], 'channel': '', 'language': v['lang'], 'gloss': 'en', 'duration': '0:10'}),
        encoding='utf-8')
    segs = []
    for s in v['caps']:
        if s.get('plain'):
            segs.append({'start': s['start'], 'text': s['text'], 'plain': True})
            continue
        chunks = []
        for c in s['chunks']:
            if isinstance(c, dict):
                chunks.append(c)
                continue
            ch = {'fa': c[0]}
            for k, f in ((1, 'en'), (2, 'voc'), (3, 'tr'), (4, 'kana')):
                if len(c) > k and c[k]: ch[f] = c[k]
            chunks.append(ch)
        segs.append({'start': s['start'], 'text': s['text'], 'chunks': chunks})
    (dst / 'annotations.json').write_text(json.dumps(
        {'video': v['id'], 'language': v['lang'], 'segments': segs}, ensure_ascii=False), encoding='utf-8')
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
const hub = new Deno.Command(PY, {args: ['-c', SERVE, WORK, String(port), JSON.stringify(DICTS), JSON.stringify(VIDEOS)],
                                  cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 90000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}

// ---- YouTube's player, which is the one thing here that is not the real one.  The time stays
// where it was put (a video "at 12 seconds" is at 12 seconds for as long as the test looks),
// the speeds are the eight YouTube offers, and every call is written down
const FAKE_YT = `window.__yt = {t: 0, state: 2, rate: 1, calls: [], rates: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]};
window.YT = {Player: function (el, o) {
  var self = this, Y = window.__yt;
  this.getCurrentTime = function () { return Y.t; };
  this.getDuration = function () { return 600; };
  this.seekTo = function (s) { Y.calls.push(['seek', +s]); Y.t = +s || 0; };
  this.playVideo = function () { Y.calls.push(['play']); Y.state = 1; };
  this.pauseVideo = function () { Y.calls.push(['pause']); Y.state = 2; };
  this.getPlayerState = function () { return Y.state; };
  this.getPlaybackRate = function () { return Y.rate; };
  this.setPlaybackRate = function (r) { Y.calls.push(['rate', +r]); Y.rate = +r; };
  this.getAvailablePlaybackRates = function () { return Y.rates.slice(); };
  this.mute = function () {}; this.unMute = function () {}; this.isMuted = function () { return false; };
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};
if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();`;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
const DESK = {viewport: {width: 1280, height: 800}};
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true};
const LAND = {viewport: {width: 844, height: 390}, isMobile: true, hasTouch: true};
const contexts = [];
// A computer, a phone or a phone turned: its own browser (so its own storage), the mode it is in,
// the settings it starts with, and the clipboard written down
async function pageFor(kind, mode = 'browser', storage = {}, {mt = false} = {}) {
  const ctx = await browser.newContext(Object.assign({serviceWorkers: 'block'}, kind));
  contexts.push(ctx);
  await ctx.addCookies([{name: 'parseh_mode', value: mode, url: B}]);
  await ctx.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname === '127.0.0.1') return route.fallback();
    if (u.href.startsWith('https://www.youtube.com/iframe_api'))
      return route.fulfill({body: FAKE_YT, contentType: 'text/javascript'});
    return route.abort();
  });
  // a translation model on this computer, which is only a pair of meta.json files to the page: the
  // switch for translated definitions is offered where one is there
  if (mt) await ctx.route('**/mt/**/meta.json', route => route.fulfill({json: {name: 'a test model'}}));
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(mode + ': ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && /ParsehGear|\[gear\]/.test(m.text())) errors.push('console: ' + m.text()); });
  if (kind.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  // the storage of a browser that has been here before, put in before the page's own script runs
  await ctx.addInitScript(s => {
    try {
      if (!sessionStorage.getItem('__seeded')) {
        sessionStorage.setItem('__seeded', '1');
        for (const k in s) localStorage.setItem(k, s[k]);
      }
    } catch (e) { /* a document with no storage of its own: the blank one a page starts on */ }
    window.__copied = [];
    try { navigator.clipboard.writeText = t => { window.__copied.push(t); return Promise.resolve(); }; } catch (e) {}
  }, storage);
  return page;
}
const tap = async (page, sel) => { const l = page.locator(sel).first(); if (page.touch) await l.tap(); else await l.click(); };
async function open(page, v, wait = true) {
  await page.goto(B + `/youtube/v/${v.id}/`);
  if (wait) {
    await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n, v.caps.length);
    await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready(), null, {timeout: 20000});
    await page.waitForFunction(() => window.ParsehGear && ParsehGear.mounted(), null, {timeout: 10000});
    await sleep(150);
  }
}
const drawn = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  if (!el) return false;
  const r = el.getBoundingClientRect(), st = getComputedStyle(el);
  return !!(r.width && r.height && st.visibility === 'visible' && st.display !== 'none');
}, sel);

// ---- the panel, as the toolkit draws it
const PANEL = '.pg-panel[data-pg-page="video"]';
const GROUP = g => `${PANEL} [data-pg-group="${g}"]`;
const ROW = (g, r) => `${GROUP(g)} [data-pg-row="${r}"]`;
const gearUp = page => page.evaluate(() => ParsehGear.mounted().isOpen());
// the gear open and, where a group is named, THAT GROUP in view: on a phone's sheet its theme entered by a tap on its row of
// the index (‹ first where another theme is up), on a popover nothing to do (it draws every group)
async function openGear(page, group) {
  if (!(await gearUp(page))) await tap(page, 'button.pg-gear');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(120);
  if (group) await enterTheme(page, group);
}
async function enterTheme(page, g) {
  const st = await page.evaluate(() => ParsehGear.mounted().stage());
  if (st === null || st === g) return;
  if (st !== 'index') {
    await tap(page, PANEL + ' .pg-back');
    await page.waitForFunction(() => ParsehGear.mounted().stage() === 'index');
    await sleep(240);
  }
  await tap(page, PANEL + ` .pg-irow[data-pg-index="${g}"]`);
  await page.waitForFunction(x => ParsehGear.mounted().stage() === x, g);
  await sleep(240);
}
async function shutGear(page) {
  if (await gearUp(page)) await page.evaluate(() => ParsehGear.mounted().close());
  await sleep(80);
}
// the groups drawn, and the rows drawn in each: what the page's spec offers, not what is in the DOM.  On a phone's sheet one
// theme is on stage and the others are not DRAWN (they are not hidden: the index lists them), so there it is `hidden`
// that says whether a group or a row is offered
const drawnGroups = page => page.evaluate(sel => {
  const sheet = document.querySelector(sel).classList.contains('pg-sheet'), seen = e => !e.hidden && (sheet || e.getClientRects().length);
  return [...document.querySelectorAll(sel + ' [data-pg-group]')].filter(seen)
    .map(g => [g.dataset.pgGroup, g.querySelector('.pg-gtitle').textContent,
               [...g.querySelectorAll('[data-pg-row]')].filter(seen).map(r => r.dataset.pgRow)]);
}, PANEL);
const switchOn = (page, g, r) => page.evaluate(s => document.querySelector(s + ' .pg-switch').getAttribute('aria-checked') === 'true', ROW(g, r));
async function flip(page, g, r) {
  const sel = ROW(g, r) + ' .pg-switch';
  await openGear(page, g);
  await page.locator(sel).scrollIntoViewIfNeeded();
  await tap(page, sel);
  await sleep(120);
}
const store = (page, k) => page.evaluate(k => localStorage.getItem(k), k);

// ================================================================== a) the page's own bar
async function partA() {
  console.log('a) the page\'s own bar');
  const page = await pageFor(DESK);
  await open(page, EN);
  await shot(page, 'a-header-en');
  const bar = await page.evaluate(() => {
    const t = s => { const e = document.querySelector(s); return e ? e.textContent.replace(/ /g, ' ').trim() : null; };
    const vis = s => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none' && !e.hidden && e.getClientRects().length > 0; };
    return {
      follow: t('#follow'), pin: t('#pin'), sbs: t('#sbs'), typo: t('#typo'),
      gear: [...document.querySelectorAll('header > .pg-gear')].length,
      gearLast: document.querySelector('header').lastElementChild === document.querySelector('button.pg-gear'),
      gone: ['#hoverpause', '#defmode', '#defmt', '#lookupset'].map(s => [s, !!document.querySelector(s), vis(s)]),
      kept: ['#follow', '#pin', '#sbs', '#theme', '#typo', '#notesbtn'].map(s => [s, vis(s)]),
    };
  });
  eq([bar.follow, bar.pin, bar.sbs, bar.typo], ['keep in view', 'keep video', 'beside the text', 'Aa'],
     'the page\'s buttons carry the names the owner chose');
  eq([bar.gear, bar.gearLast], [1, true], 'one gear, the last thing on the bar');
  eq(bar.gone, [['#hoverpause', true, false], ['#defmode', true, false], ['#defmt', true, false], ['#lookupset', true, false]],
     'hover ⏸, definitions, translated and the reading-help link are in the page and not on the bar');
  eq(bar.kept.filter(k => !k[1]).map(k => k[0]), [], 'follow, pin, side, ◐, Aa and ✱ notes are still on the bar');
  await page.context().close();
}

// ================================================================== b) the panel, group by group
// the words are the owner's (plan §6, Video), and the groups come in the order of plan §2
const NAMES = {
  watching: {follow: 'Keep the playing caption in view', hoverpause: 'Pause while a gloss is open',
             aloud: 'Show only the reading', marks: 'Diacritics', sbs: 'Video beside the text',
             pin: 'Keep the video in view', size: 'Video size', lines: 'Show the lines around'},
  looking: {dict: 'Look words up in a dictionary', defs: 'Show the dictionary’s definitions',
            defsmt: 'Translate the definitions into English'},
  playback: {skip: 'Skip distance', speed: 'Playback speed'},
  text: {fa: 'English text size', sub: 'Subtitle size', gl: 'Gloss size', width: 'Text width', lead: 'Line spacing',
         cjkSpace: 'Space between characters', kanaContrast: 'Furigana contrast', kanaSize: 'Furigana size'},
  colours: {theme: 'Colour scheme'}, interface: {mode: 'Browser or mobile pages'},
};
const rowWords = (page, g, r) => page.evaluate(sel => {
  const e = document.querySelector(sel);
  const n = e && e.querySelector('.pg-nametext'), h = e && e.querySelector('.pg-help');
  return {name: n ? n.textContent : null, help: h && !h.hidden ? h.textContent : null};
}, ROW(g, r));

async function partB() {
  console.log('b) the panel, group by group');
  const page = await pageFor(DESK, 'browser', {}, {mt: true});
  await open(page, EN);
  // the dictionary has answered, and the translation model has been found
  await page.waitForFunction(() => !document.querySelector('#dictmode').hidden && !document.querySelector('#defmt').hidden);
  await openGear(page);
  await shot(page, 'b-gear-en');
  const zoom = await page.evaluate(() => !!window.ParsehZoom);
  const got = await drawnGroups(page);
  eq(got.map(g => g[1]),
     ['Watching & reading', 'Looking a word up', 'Playback', 'Text'].concat(zoom ? ['Zoom'] : [], ['Colours', 'Interface']),
     'the groups, in the plan\'s order: watching, looking a word up, playback, text, (zoom,) colours, interface');
  const rows = Object.fromEntries(got.map(g => [g[0], g[2]]));
  eq(rows.watching, ['follow', 'hoverpause', 'sbs', 'pin', 'size'],
     'Watching & reading on a computer: keep in view, pause, beside the text, keep the video, its size -- no reading, no marks, no lines');
  eq(rows.looking, ['dict', 'defs', 'defsmt', 'help'], 'Looking a word up: the dictionary, its definitions, their translation, the link');
  eq(rows.playback, ['skip'], 'Playback on a computer: the skip distance alone (the page has no speed control of its own)');
  eq(rows.text, ['fa', 'gl', 'width', 'lead', 'reset'], 'Text: the language, the glosses, the width, the spacing, the way back (no subtitles: that is the phone\'s)');
  eq(rows.colours, ['theme'], 'Colours');
  eq(rows.interface, ['mode'], 'Interface: the Browser | Mobile choice, and no Keep (that is the phone\'s)');
  // the first line, the foot, and where each group says its settings are kept
  const frame = await page.evaluate(sel => ({
    title: document.querySelector(sel + ' .pg-title').textContent, first: document.querySelector(sel + ' .pg-first').textContent,
    foot: document.querySelector(sel + ' .pg-footlink').textContent, href: document.querySelector(sel + ' .pg-footlink').getAttribute('href'),
    captions: Object.fromEntries([...document.querySelectorAll(sel + ' [data-pg-group]')].filter(g => !g.hidden)
      .map(g => [g.dataset.pgGroup, g.querySelector('.pg-caption').textContent]))}), PANEL);
  eq([frame.title, frame.first, frame.href], ['This page', 'Only for this page.', '/settings/'], 'the panel says it is only about this page, and where Parseh\'s own settings are');
  eq(frame.captions.watching, 'Saved on this device.', 'Watching & reading says where it is kept');
  eq(frame.captions.looking, 'Saved on this device.', 'Looking a word up says where it is kept');
  eq(frame.captions.playback, 'Saved on this device, except the skip distance, which follows you.', 'Playback says its skip follows the person');
  eq(frame.captions.text, 'Saved on this device.', 'Text says where it is kept');
  eq(frame.captions.colours, 'Follows you to your other devices.', 'Colours follow the person');
  eq(frame.captions.interface, 'Saved on this device.', 'Interface says where it is kept');
  // every row says what it is AND what it does, as text on the page
  const all = await page.evaluate(sel => [...document.querySelectorAll(sel + ' [data-pg-row]')]
    .filter(r => !r.hidden && r.getClientRects().length)
    .map(r => [r.dataset.pgRow, r.dataset.pgKind, (r.querySelector('.pg-nametext') || {}).textContent || '', (r.querySelector('.pg-help') || {}).textContent || '']), PANEL);
  for (const [id, kind, name, help] of all) {
    assert(help.length > 20, `the row ${id} has its sentence: ${JSON.stringify(help)}`);
    if (kind !== 'link' && kind !== 'action') assert(name.length > 3, `the row ${id} has its name: ${JSON.stringify(name)}`);
  }
  for (const g of Object.keys(NAMES))
    for (const [r, want] of Object.entries(NAMES[g])) {
      if (!rows[g] || !rows[g].includes(r)) continue;
      eq((await rowWords(page, g, r)).name, want, `the row ${r} is named «${want}»`);
    }
  const w = {};
  for (const r of ['follow', 'hoverpause', 'sbs', 'pin', 'size']) w[r] = (await rowWords(page, 'watching', r)).help;
  eq(w.follow, 'Scrolls the transcript so the caption being said stays on screen; it waits a moment after you scroll yourself.', 'the sentence of «keep in view»');
  eq(w.pin, 'The video stays at the top while the transcript scrolls under it. Not needed when the video is beside the text.', 'the sentence of «keep the video in view»');
  eq(w.sbs, 'Puts the video in a column beside the transcript instead of above it. Only on wide screens (860 px and up); on a phone, turning it sideways does it.', 'the sentence of «video beside the text»');
  eq(w.size, 'How big the video is. You can also drag the bar under it; double-click it to reset.', 'the sentence of «video size»');
  eq(w.hoverpause.startsWith('While a gloss is open the video waits'), true, 'the sentence of «pause while a gloss is open» speaks of the video');
  await shutGear(page);

  // THE OTHER LANGUAGES' ROWS: a language's own name on the text row, and the rows only some have
  const fa = await pageFor(DESK);
  await open(fa, FA);
  await openGear(fa);
  const faRows = await drawnGroups(fa);
  assert(faRows[0][2].includes('marks') && !faRows[0][2].includes('aloud'), 'a Persian video: «Diacritics», and no reading-only row');
  eq((await rowWords(fa, 'text', 'fa')).name, 'Persian text size', 'the text row is named after the video\'s language');
  eq((await rowWords(fa, 'watching', 'marks')).help.startsWith('Shows the small marks that write the vowels, the doubling and the silent stop (fatha, damma, kasra, tanwin, shadda, sukun)'), true,
     'the sentence of «Diacritics» names the marks');
  await fa.context().close();
  const ja = await pageFor(DESK);
  await open(ja, JA);
  await openGear(ja);
  const jaRows = await drawnGroups(ja);
  eq(jaRows.find(g => g[0] === 'watching')[2], ['follow', 'hoverpause', 'aloud', 'sbs', 'pin', 'size'], 'a Japanese video: the reading-only row is there');
  eq(jaRows.find(g => g[0] === 'text')[2], ['fa', 'gl', 'width', 'lead', 'cjkSpace', 'kanaContrast', 'kanaSize', 'reset'],
     'a Japanese video: space between characters, furigana contrast and furigana size');
  eq(await ja.evaluate(() => document.querySelector('#aloud').textContent), 'kana only', 'and its button is «kana only»');
  eq((await rowWords(ja, 'text', 'kanaContrast')).help, 'How strongly the small kana over the kanji are drawn: lower fades them so the kanji stand out, higher makes them darker.', 'the sentence of «furigana contrast»');
  await ja.context().close();
  const zh = await pageFor(DESK);
  await open(zh, ZH);
  await openGear(zh);
  const zhRows = await drawnGroups(zh);
  eq(zhRows.find(g => g[0] === 'text')[2], ['fa', 'gl', 'width', 'lead', 'cjkSpace', 'reset'], 'a Chinese video: space between characters, and no furigana');
  eq(await zh.evaluate(() => document.querySelector('#aloud').textContent), 'pinyin only', 'and its button is «pinyin only»');
  // nothing installed for Chinese: the switches are not drawn; the way to get one is
  eq(zhRows.find(g => g[0] === 'looking')[2], ['help'], 'nothing installed: no dictionary switches, and the link to get one is still there');
  eq(await zh.evaluate(() => [document.querySelector('#dictmode').hidden, document.querySelector('#lookupset').getAttribute('href')]),
     [true, '/settings/reading-help/'], 'the page\'s own dictionary button is hidden for good, the reading-help link is in the page');
  await zh.context().close();
  await page.context().close();
}

// ================================================================== c) Watching & reading: every row, both ways
// A row is pressed, and what is read is the page's OWN control and the key it keeps, and then what
// the page does with it; and then the row is pressed back
async function partC() {
  console.log('c) Watching & reading: every row, both ways');
  // a long Persian video, so that the page can be scrolled and a caption can be far from where it is looked at
  const page = await pageFor(DESK);
  await open(page, FA);
  await openGear(page);
  const state = () => page.evaluate(() => ({
    follow: [document.querySelector('#follow').classList.contains('on'), localStorage.getItem('yt_follow')],
    hover: [document.querySelector('#hoverpause').classList.contains('on'), localStorage.getItem('yt_hoverpause')],
    pin: [document.querySelector('#pin').classList.contains('on'), localStorage.getItem('yt_pin'), document.body.classList.contains('nopin'),
          getComputedStyle(document.querySelector('#playerwrap')).position],
    sbs: [document.querySelector('#sbs').classList.contains('on'), localStorage.getItem('yt_sbs'), document.body.classList.contains('sbs'),
          getComputedStyle(document.querySelector('#playerwrap')).position, document.querySelector('#pin').disabled],
  }));
  // -- keep in view
  eq((await state()).follow, [true, null], 'keep in view starts on, nothing kept yet');
  assert(await switchOn(page, 'watching', 'follow'), 'and the panel says so');
  await flip(page, 'watching', 'follow');
  eq((await state()).follow, [false, '0'], 'the switch put it off: the page\'s own button, and the key it keeps');
  assert(!(await switchOn(page, 'watching', 'follow')), 'and the panel shows it off');
  // what the page does: the video goes to a caption far down, and the transcript stays where it is
  const inView = n => page.evaluate(n => { const r = document.querySelector('#segs .seg[data-i="' + n + '"]').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }, n);
  await page.evaluate(() => document.querySelector('#segs .seg[data-i="20"] .lab').click());
  await page.waitForFunction(() => { const s = document.querySelector('#segs .seg.on-air'); return s && +s.dataset.i === 20; });
  await sleep(1300);
  eq([await page.evaluate(() => scrollY), await inView(20)], [0, false], 'with keep in view off the transcript did not move for the caption on air');
  await flip(page, 'watching', 'follow');
  eq((await state()).follow, [true, '1'], 'and back on');
  await page.waitForFunction(n => { const r = document.querySelector('#segs .seg[data-i="' + n + '"]').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }, 20, {timeout: 4000});
  assert(await page.evaluate(() => scrollY) > 0, 'turned on, the transcript was scrolled to the caption on air');
  await page.evaluate(() => scrollTo(0, 0));
  // -- pause while a gloss is open: the video waits while a phrase's cloud is open and goes on after it
  await flip(page, 'watching', 'hoverpause');
  eq((await state()).hover, [true, '1'], 'pause while a gloss is open: the page\'s own button is on and the key is kept');
  // (a switch no longer shuts the popover as it is pressed, and it covers the transcript: shut it to reach a phrase)
  await shutGear(page);
  await page.evaluate(() => { __yt.calls.length = 0; document.querySelector('#segs .seg[data-i="1"] .lab').click(); });
  await sleep(300);
  await page.hover('#segs .seg[data-i="1"] .w[data-j="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await sleep(200);
  eq(await page.evaluate(() => __yt.calls.map(c => c[0]).slice(-1)), ['pause'], 'a gloss opened: the video paused');
  await page.mouse.move(30, 450);
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  await sleep(700);
  eq(await page.evaluate(() => __yt.calls.map(c => c[0]).slice(-1)), ['play'], 'the gloss closed: the video went on a moment after');
  await flip(page, 'watching', 'hoverpause');
  eq((await state()).hover, [false, '0'], 'and the row put it back off');
  await page.evaluate(() => { __yt.calls.length = 0; });
  // (a switch no longer shuts the popover as it is pressed, so the page under it is reached by shutting it)
  await shutGear(page);
  await page.hover('#segs .seg[data-i="2"] .w[data-j="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await sleep(200);
  eq(await page.evaluate(() => __yt.calls.filter(c => c[0] === 'pause').length), 0, 'off, a gloss opening does not pause the video');
  await page.mouse.move(30, 450);
  // -- keep the video in view
  eq((await state()).pin.slice(0, 3), [true, null, false], 'keep video starts on');
  eq((await state()).pin[3], 'sticky', 'and the video is pinned under the bar');
  await flip(page, 'watching', 'pin');
  eq(await state().then(s => s.pin), [false, '0', true, 'static'], 'the row let the video scroll away with the page, and the page\'s button says so');
  await flip(page, 'watching', 'pin');
  eq(await state().then(s => s.pin), [true, '1', false, 'sticky'], 'and pinned again');
  // -- the video beside the text (a window of 1280 has the room)
  await flip(page, 'watching', 'sbs');
  eq(await state().then(s => s.sbs), [true, '1', true, 'fixed', true], 'beside the text: the page is in two columns, and «keep the video» has nothing left to decide');
  assert(await page.evaluate(sel => document.querySelector(sel + ' .pg-switch').disabled, ROW('watching', 'pin')), 'the gear\'s row for it rests too');
  const why = await page.evaluate(sel => { const w = document.querySelector(sel + ' .pg-why'); return w && !w.hidden ? w.textContent : ''; }, ROW('watching', 'pin'));
  eq(why, 'The video is beside the text, so it is always in view.', 'and says why, under the row');
  await shot(page, 'c-beside');
  await flip(page, 'watching', 'sbs');
  eq(await state().then(s => s.sbs), [false, '0', false, 'sticky', false], 'and back above the text');
  await page.context().close();

  // -- the reading alone (a language divided into words) and what the page does with it
  const ja = await pageFor(DESK);
  await open(ja, JA);
  await openGear(ja);
  const reading = () => ja.evaluate(() => ({
    on: document.querySelector('#aloud').classList.contains('on'), kept: localStorage.getItem('yt_aloud'), body: document.body.classList.contains('aloud'),
    first: document.querySelector('#segs .seg[data-i="0"] .w[data-j="0"]').textContent}));
  eq(await reading(), {on: false, kept: null, body: false, first: 'こんにちは、'}, 'a Japanese video starts with its text');
  await flip(ja, 'watching', 'aloud');
  eq(await reading(), {on: true, kept: '1', body: true, first: 'こんにちは、'}, 'show only the reading: the button, the key, the page');
  await ja.evaluate(() => { document.querySelector('#segs .seg[data-i="1"] .w[data-j="0"]'); });
  eq(await ja.evaluate(() => document.querySelector('#segs .seg[data-i="1"] .w[data-j="0"]').textContent), 'きょうは', 'a phrase is drawn as its kana alone');
  await flip(ja, 'watching', 'aloud');
  // the text with its reading over it: the base text is what is read without the ruby
  eq(await ja.evaluate(() => { const w = document.querySelector('#segs .seg[data-i="1"] .w[data-j="0"]').cloneNode(true);
                               w.querySelectorAll('rt, rp').forEach(e => e.remove());
                               return [w.textContent, localStorage.getItem('yt_aloud'), document.body.classList.contains('aloud')]; }),
     ['今日は', '0', false], 'and back to the text, with its reading over the kanji');
  await ja.context().close();
}

// ================================================================== d) the rest of the panel, both ways
async function partD() {
  console.log('d) looking a word up, playback, text, colours, interface');
  const page = await pageFor(DESK, 'browser', {}, {mt: true});
  await open(page, EN);
  await page.waitForFunction(() => !document.querySelector('#dictmode').hidden && !document.querySelector('#defmt').hidden);
  await openGear(page);
  const st = () => page.evaluate(() => ({
    dict: [document.querySelector('#dictmode').classList.contains('on'), localStorage.getItem('yt_dict')],
    defs: [document.querySelector('#defmode').classList.contains('on'), localStorage.getItem('yt_defs'), document.querySelector('#defmode').disabled],
    mt: [document.querySelector('#defmt').classList.contains('on'), localStorage.getItem('yt_defs_mt'), document.querySelector('#defmt').disabled]}));
  const why = (g, r) => page.evaluate(sel => { const w = document.querySelector(sel + ' .pg-why'); return w && !w.hidden ? w.textContent : ''; }, ROW(g, r));
  // -- the dictionary, its definitions, their translation: each hangs from the one above it
  eq(await st(), {dict: [false, null], defs: [false, null, true], mt: [false, null, true]}, 'the dictionary starts off, and what hangs from it rests');
  eq(await why('looking', 'defs'), 'Turn on the dictionary above first.', 'the definitions say why they rest');
  eq(await why('looking', 'defsmt'), 'Turn on the dictionary first.', 'the translation says why it rests');
  assert(await page.evaluate(sel => document.querySelector(sel + ' .pg-switch').disabled, ROW('looking', 'defs')), 'and cannot be pressed');
  await flip(page, 'looking', 'dict');
  eq((await st()).dict, [true, '1'], 'the dictionary switch: the page\'s own button is on and the key is kept');
  eq(await st().then(s => [s.defs[2], s.mt[2]]), [false, true], 'the definitions are free; the translation waits for them');
  eq(await why('looking', 'defsmt'), 'Turn on the definitions above first.', 'and says what it waits for now');
  await flip(page, 'looking', 'defs');
  eq(await st().then(s => [s.defs[0], s.defs[1], s.mt[2]]), [true, '1', false], 'the definitions switch: the button, the key, and the translation is free');
  await flip(page, 'looking', 'defsmt');
  eq(await st().then(s => s.mt.slice(0, 2)), [true, '1'], 'the translation switch: the button and the key');
  // what the page does with the dictionary: a phrase nobody glossed gets a dictionary panel in its cloud
  await shutGear(page);
  await page.hover('#segs .seg[data-i="3"] .w[data-j="1"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await sleep(300);
  assert(await page.evaluate(() => !!document.querySelector('#cloud .dict')), 'with the dictionary on, a phrase nobody glossed opens a cloud with the dictionary in it');
  await page.mouse.move(30, 450);
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  await openGear(page);
  await flip(page, 'looking', 'defsmt');
  await flip(page, 'looking', 'defs');
  await flip(page, 'looking', 'dict');
  eq(await st(), {dict: [false, '0'], defs: [false, '0', true], mt: [false, '0', true]}, 'all three put back off');
  eq(await page.evaluate(sel => { const a = document.querySelector(sel + ' a.pg-link'); return [a.textContent, a.getAttribute('href')]; }, ROW('looking', 'help')),
     ['Get a dictionary for this language →', '/settings/reading-help/'], 'the link to the reading help');

  // -- Playback: the skip is the person's (bk_skip) and Shift+→ obeys it
  const skip = ROW('playback', 'skip');
  eq(await page.evaluate(s => document.querySelector(s + ' select').value, skip), '3', 'the skip starts at ten seconds');
  await page.selectOption(skip + ' select', {label: '30 s'});
  await sleep(150);
  eq(await store(page, 'bk_skip'), '30', 'the skip row kept 30 where ↺ ↻ and Shift+← → keep it');
  await page.evaluate(() => { document.querySelector('#segs .seg[data-i="1"] .lab').click(); __yt.calls.length = 0; });
  await shutGear(page);
  await page.keyboard.press('Shift+ArrowRight');
  await sleep(200);
  eq(await page.evaluate(() => __yt.calls.filter(c => c[0] === 'seek').map(c => c[1])), [32], 'Shift+→ moved the video thirty seconds on (from 2 to 32)');
  await page.keyboard.press('Shift+ArrowLeft');
  await sleep(200);
  eq(await page.evaluate(() => __yt.calls.filter(c => c[0] === 'seek').map(c => c[1])), [32, 2], 'and Shift+← thirty back');
  await openGear(page);
  await page.selectOption(skip + ' select', {label: '5 s'});
  await sleep(150);
  eq(await store(page, 'bk_skip'), '5', 'the skip row again, to five seconds');

  // -- Text: the Aa panel's own fields, as sliders, and the way back
  const slide = async (g, r, v) => {
    await page.evaluate(([sel, v]) => { const i = document.querySelector(sel + ' input[type=range]'); i.value = String(v); i.dispatchEvent(new Event('input', {bubbles: true})); }, [ROW(g, r), v]);
    await sleep(100);
  };
  const css = p => page.evaluate(p => getComputedStyle(document.documentElement).getPropertyValue(p).trim(), p);
  const typo = () => page.evaluate(() => JSON.parse(localStorage.getItem('yt_typo') || '{}'));
  eq(await css('--yt-fa'), '20px', 'the transcript starts at the usual size');
  await slide('text', 'fa', 30);
  eq([await css('--yt-fa'), (await typo()).fa], ['30px', 30], 'the language\'s size slider moved the page\'s size and kept it where Aa kept it (yt_typo)');
  eq(await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('#segs .seg .fa')).fontSize)), 30, 'and the transcript is drawn at it');
  eq(await page.evaluate(sel => document.querySelector(sel + ' .pg-out').textContent, ROW('text', 'fa')), '30 px', 'the slider says what it is');
  await slide('text', 'gl', 18);
  await slide('text', 'width', 900);
  await slide('text', 'lead', 1.5);
  eq([await css('--yt-gl'), await css('--yt-width'), await css('--yt-lead')], ['18px', '900px', '1.5'], 'the glosses\', the width and the line spacing sliders');
  eq(await page.evaluate(sel => document.querySelector(sel + ' .pg-out').textContent, ROW('text', 'lead')), '1.5×', 'the spacing says «1.5×»');
  await page.locator(ROW('text', 'reset') + ' button.pg-action').click();
  await sleep(150);
  eq([await css('--yt-fa'), await css('--yt-gl'), await css('--yt-width'), await css('--yt-lead')], ['20px', '12.5px', '760px', '1'], 'Put the text back to normal: every field at its usual');
  eq(await page.evaluate(sel => document.querySelector(sel + ' input[type=range]').value, ROW('text', 'fa')), '20', 'and the slider is back at it');

  // -- Colours: the choice, and ◐ which stays on the page; each follows the other
  const theme = () => page.evaluate(() => [document.documentElement.getAttribute('data-theme'), localStorage.getItem('parseh_theme')]);
  const picked = () => page.evaluate(sel => [...document.querySelectorAll(sel + ' [role=radio]')].filter(c => c.getAttribute('aria-checked') === 'true').map(c => c.textContent), ROW('colours', 'theme'));
  eq(await picked(), ['Follow my device'], 'the colours follow the device to begin with');
  await page.locator(ROW('colours', 'theme') + ' [role=radio]', {hasText: 'Dark'}).click();
  await sleep(150);
  eq(await theme(), ['dark', 'dark'], 'Dark: the page is dark and the choice is kept');
  await page.locator(ROW('colours', 'theme') + ' [role=radio]', {hasText: 'Sepia'}).click();
  await sleep(150);
  eq((await theme())[0], 'sepia', 'Sepia');
  await shutGear(page);
  await page.locator('#theme').click();
  await openGear(page);
  const after = await theme();
  assert(after[0] !== 'sepia' && (await picked()).length === 1, '◐ on the page went on to the next colours, and the panel follows it: ' + JSON.stringify(after) + ' ' + JSON.stringify(await picked()));
  await page.locator(ROW('colours', 'theme') + ' [role=radio]', {hasText: 'Follow my device'}).click();
  await sleep(150);
  eq((await theme())[0], null, 'Follow my device: the page wears no colours of its own');

  // -- Interface: the choice that used to be a switch under ⋯ on a phone
  eq(await page.evaluate(sel => [...document.querySelectorAll(sel + ' button')].map(b => [b.textContent, b.getAttribute('aria-pressed')]), ROW('interface', 'mode')),
     [['Browser', 'true'], ['Mobile', 'false']], 'Browser | Mobile, with Browser in force');
  await page.locator(ROW('interface', 'mode') + ' button', {hasText: 'Mobile'}).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-mode') === 'mobile');
  await sleep(300);
  eq(await page.evaluate(() => [document.documentElement.getAttribute('data-mode'), !document.querySelector('.m-rmore')]), ['mobile', true], 'Mobile: the page is in the mobile layout, and has no ⋯');
  assert(await gearUp(page), 'and the panel stayed up while the page changed under it');
  await openGear(page, 'interface');                    // it became the phone's sheet, on its index: the theme again
  await page.locator(ROW('interface', 'mode') + ' button', {hasText: 'Browser'}).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-mode') === 'browser');
  await page.context().close();
}

// ================================================================== e) the bar under the video and the slider
async function partE() {
  console.log('e) the bar under the video and «Video size» keep each other in step');
  const page = await pageFor(DESK);
  await open(page, EN);
  await openGear(page);
  const slider = ROW('watching', 'size') + ' input[type=range]';
  const sliderNow = () => page.evaluate(s => [+document.querySelector(s).value, document.querySelector(s.replace(' input[type=range]', ' .pg-out')).textContent], slider);
  const vid = () => page.evaluate(() => ({w: Math.round(document.querySelector('#vid').getBoundingClientRect().width), kept: localStorage.getItem('yt_vidw'),
                                          sized: document.body.classList.contains('sized')}));
  // the bar itself: three dots to take hold of, and what it does as its tooltip
  const grip = await page.evaluate(() => {
    const g = document.querySelector('#grip'), st = getComputedStyle(g, '::before');
    return {title: g.title, dots: st.backgroundImage.includes('radial-gradient'), w: g.getBoundingClientRect().width, h: g.getBoundingClientRect().height,
            dim: st.backgroundImage};
  });
  assert(grip.dots && grip.w >= 80 && grip.h >= 14, 'the bar under the video has a handle drawn on it: ' + JSON.stringify([grip.w, grip.h]));
  eq(grip.title, 'drag to make the video bigger or smaller — double-click for its usual size', 'and a tooltip that says what it does');
  await shot(page, 'e-grip');
  // -- no size chosen: the video is its usual size, and the slider says what that is
  const v0 = await vid();
  eq([v0.kept, v0.sized], [null, false], 'no size chosen yet');
  const s0 = await sliderNow();
  eq(s0[1], v0.w + ' px', 'the slider says the video\'s width in pixels: ' + s0[1]);
  // -- the slider moves the video and keeps the width where the bar keeps it
  await page.evaluate(s => { const i = document.querySelector(s); i.value = '10'; i.dispatchEvent(new Event('input', {bubbles: true})); }, slider);
  await sleep(200);
  const v1 = await vid();
  assert(v1.kept !== null && +v1.kept === v1.w && v1.sized && v1.w < v0.w, 'the slider made the video smaller and kept its width (yt_vidw): ' + JSON.stringify(v1));
  eq((await sliderNow())[1], v1.w + ' px', 'and says the width it made');
  await page.evaluate(s => { const i = document.querySelector(s); i.value = '90'; i.dispatchEvent(new Event('input', {bubbles: true})); }, slider);
  await sleep(200);
  const v2 = await vid();
  assert(+v2.kept === v2.w && v2.w > v0.w, 'and bigger: ' + JSON.stringify(v2));
  // -- the bar moves the slider, while it is being dragged and when it is let go
  const box = await page.locator('#grip').boundingBox();
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx, cy - 120, {steps: 6});
  await sleep(250);
  const drag = await vid();
  const during = await sliderNow();
  assert(drag.w < v2.w && during[1] === drag.w + ' px', 'dragged up, the video is smaller and the open slider followed it as it went: ' + JSON.stringify([drag.w, during]));
  await page.mouse.up();
  await sleep(200);
  const v3 = await vid();
  assert(+v3.kept === v3.w, 'let go, the bar kept the width where the slider does: ' + JSON.stringify(v3));
  await openGear(page);
  eq((await sliderNow())[1], v3.w + ' px', 'and the slider, opened again, agrees');
  // -- a double-click on the bar forgets the size, and the slider is back at the usual one
  await page.locator('#grip').dblclick();
  await sleep(250);
  await openGear(page);
  const v4 = await vid();
  eq([v4.kept, v4.sized, v4.w], [null, false, v0.w], 'double-clicked, the bar went back to the usual size and forgot the choice');
  eq((await sliderNow())[1], v0.w + ' px', 'and so did the slider');
  await shutGear(page);
  await page.context().close();

  // -- the same beside the text: it is the column that is sized, and kept apart (yt_sidew)
  const side = await pageFor(DESK, 'browser', {yt_sbs: '1'});
  await open(side, EN);
  await openGear(side);
  const col = () => side.evaluate(() => ({w: Math.round(document.querySelector('#playerwrap').getBoundingClientRect().width), kept: localStorage.getItem('yt_sidew'),
                                          stacked: localStorage.getItem('yt_vidw')}));
  const c0 = await col();
  await side.evaluate(s => { const i = document.querySelector(s); i.value = '20'; i.dispatchEvent(new Event('input', {bubbles: true})); }, slider);
  await sleep(200);
  const c1 = await col();
  assert(c1.kept !== null && +c1.kept === c1.w && c1.w < c0.w && c1.stacked === null, 'beside the text the slider sizes the column and keeps it as yt_sidew, the stacked size untouched: ' + JSON.stringify([c0, c1]));
  const dots = await side.evaluate(() => { const st = getComputedStyle(document.querySelector('#grip'), '::before'); return [st.backgroundImage.includes('radial-gradient'), st.width, st.height]; });
  eq(dots, [true, '4px', '30px'], 'the bar between the columns is the same handle, turned upright');
  await shot(side, 'e-grip-beside');
  await side.locator('#grip').dblclick();
  await sleep(250);
  eq((await col()).kept, null, 'double-clicked, the column forgot its width');
  await side.context().close();
}

// ================================================================== f) Diacritics
async function partF() {
  console.log('f) Diacritics');
  const MARKS = {fa: /[ً-ْ]/g, ar: /[ً-ْٰ]/g};
  const lineTexts = page => page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(s => (s.querySelector('.fa, .en-line') || {}).textContent));
  const page = await pageFor(DESK);
  await open(page, FA);
  const written = FA.caps.map(c => c.text);
  eq(await lineTexts(page), written, 'a Persian video is drawn with its marks, as it always was');
  assert(await page.evaluate(() => { const r = [...document.querySelectorAll('#segs .seg')]; return r.length; }) === FA.caps.length, 'every caption is there');
  await openGear(page);
  assert(await switchOn(page, 'watching', 'marks'), '«Diacritics» starts on');
  await shot(page, 'f-marks-on');
  // the hover path first, with the marks: the phrase opens its own gloss
  // -- put the marks away
  const bare = t => t.replace(MARKS.fa, '');
  await flip(page, 'watching', 'marks');
  eq(await store(page, 'yt_marks'), '0', '«Diacritics» off is kept, for this device (yt_marks)');
  const now = await lineTexts(page);
  eq(now, written.map((t, i) => FA.caps[i].plain ? t : bare(t)), 'every line is drawn without the marks, and the English framing is left as it is');
  eq(await page.evaluate(() => document.querySelector('#segs .seg[data-i="1"] .w[data-j="0"]').textContent), 'هیچ جای دنیا', 'a phrase reads «هیچ جای دنیا»: no kasra, no damma');
  eq(await page.evaluate(() => document.querySelector('#segs .seg[data-i="3"] .bare').textContent), 'سال نو', 'a run left as text (a bare one) is drawn without them too');
  eq(await page.evaluate(() => document.querySelector('#segs .seg[data-i="2"] .bare').textContent), 'okay', 'and a run in another script is left alone');
  eq(await page.evaluate(() => document.querySelector('#segs .seg[data-i="5"] .w').textContent), 'ر\u062D\u0645\u0670\u0646', 'a dagger alif (U+0670) is not one of Persian\'s marks: it stays');
  await shot(page, 'f-marks-off');
  // -- it is still a phrase: the cloud opens with ITS gloss, and what is copied and carded is what was written
  await shutGear(page);
  await page.hover('#segs .seg[data-i="1"] .w[data-j="0"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  const cloud = await page.evaluate(() => document.getElementById('cloud').textContent.replace(/\s+/g, ' '));
  assert(cloud.includes('nowhere in the world') && cloud.includes('hič jā-ye donyā'), 'the phrase\'s cloud opens with its own gloss: ' + cloud.slice(0, 80));
  await page.evaluate(() => { __copied.length = 0; });
  await page.locator('#cloud .mkcopy').click();
  await sleep(200);
  eq(await page.evaluate(() => __copied), ['هیچ جایِ دُنیا'], 'the cloud\'s copy button copies the phrase as it was written, marks and all');
  await page.mouse.move(30, 450);
  await page.waitForFunction(() => document.getElementById('cloud').hidden);
  await page.evaluate(() => { __copied.length = 0; });
  await page.locator('#segs .seg[data-i="1"] .w[data-j="1"]').click({modifiers: ['Shift']});
  await sleep(200);
  eq(await page.evaluate(() => __copied), ['تَروُ خُشک را'], 'a shift-click copies the phrase as it was written');
  await page.locator('#segs .seg[data-i="1"] .w[data-j="0"] .wd').nth(1).click({modifiers: ['Alt']});
  await page.waitForFunction(() => !document.getElementById('anki').hidden);
  eq(await page.evaluate(() => document.getElementById('afa').value), 'جایِ', 'an alt-click on a word makes a card of the word as it was written');
  await page.locator('#acancel').click();
  await sleep(200);
  eq(await page.evaluate(() => document.querySelector('#segs .seg[data-i="1"] .w[data-j="0"]').textContent), 'هیچ جای دنیا', 'and the page still draws it without');
  // -- the colour of a marked phrase is still there, and the editor shows the text as written
  await page.hover('#segs .seg[data-i="1"] .w[data-j="1"]');
  await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await page.locator('#cloud .mkedit').click();
  await page.waitForFunction(() => !!document.querySelector('#cloud textarea, #cloud input'));
  const editor = await page.evaluate(() => [...document.querySelectorAll('#cloud textarea, #cloud input')].map(e => e.value));
  assert(editor.includes('تَروُ خُشک را'), 'the editor holds the phrase as it was written: ' + JSON.stringify(editor));
  await page.keyboard.press('Escape');
  await page.mouse.move(30, 450);
  await sleep(300);
  // -- where it was: the page does not move and the caption on air is the same one
  await page.evaluate(() => document.querySelector('#segs .seg[data-i="14"] .lab').click());
  await page.waitForFunction(() => { const s = document.querySelector('#segs .seg.on-air'); return s && +s.dataset.i === 14; });
  await sleep(1300);
  await page.evaluate(() => scrollTo(0, 500));
  await sleep(300);
  const anchor = () => page.evaluate(() => { const a = document.querySelector('#segs .seg[data-i="12"]').getBoundingClientRect().top; return [scrollY, Math.round(a),
                                                +document.querySelector('#segs .seg.on-air').dataset.i]; });
  const before = await anchor();
  await openGear(page);
  await flip(page, 'watching', 'marks');        // back on: the marks come back
  await sleep(300);
  const after = await anchor();
  eq(await lineTexts(page), written, 'the marks came back, line by line');
  eq([after[0], after[2]], [before[0], before[2]], 'the page is where it was, and the caption on air is the same one');
  assert(Math.abs(after[1] - before[1]) <= 1, 'and the caption being read is where it was on the screen: ' + JSON.stringify([before, after]));
  await flip(page, 'watching', 'marks');        // off again, for the reload
  eq(await store(page, 'yt_marks'), '0', 'off again');
  // -- the choice survives a reload
  await page.reload();
  await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n && window.ParsehGear && ParsehGear.mounted(), FA.caps.length);
  eq((await lineTexts(page))[1], 'هیچ جای دنیا ترو خشک را', 'after a reload the lines are still without their marks');
  await openGear(page);
  assert(!(await switchOn(page, 'watching', 'marks')), 'and the row says off');
  await page.context().close();

  // -- ARABIC: its marks include the dagger alif, which Persian's do not
  const ar = await pageFor(DESK, 'browser', {yt_marks: '0'});
  await open(ar, AR);
  const arWritten = AR.caps.map(c => c.text);
  eq(await lineTexts(ar), arWritten.map(t => t.replace(MARKS.ar, '')), 'an Arabic video, its marks put away: every mark of the language\'s record is gone, the dagger alif too');
  eq((await lineTexts(ar))[1], '\u0671\u0644\u0631\u062D\u0645\u0640\u0646 \u0671\u0644\u0631\u062D\u064A\u0645', 'the second line reads ٱلرحمـن ٱلرحيم (the tatweel stays, the dagger alif goes)');
  await shot(ar, 'f-marks-ar-off');
  await openGear(ar);
  assert(!(await switchOn(ar, 'watching', 'marks')), 'the row is there, and off');
  await flip(ar, 'watching', 'marks');
  eq(await lineTexts(ar), arWritten, 'on again, the Arabic lines have everything they were written with');
  await ar.context().close();

  // -- A VIDEO WITH NOTHING TO PUT AWAY has no row; nor has a language that writes no such marks
  const plain = await pageFor(DESK);
  await open(plain, FAPLAIN);
  await openGear(plain);
  assert(!(await drawnGroups(plain))[0][2].includes('marks'), 'a Persian video written without marks has no «Diacritics» row');
  await plain.context().close();
  const en = await pageFor(DESK);
  await open(en, EN);
  await openGear(en);
  assert(!(await drawnGroups(en))[0][2].includes('marks'), 'nor has an English one');
  await en.context().close();
}

// ================================================================== g) Aa opens the gear at Text
async function partG() {
  console.log('g) Aa opens the gear at Text');
  const page = await pageFor(DESK);
  await open(page, EN);
  const atText = () => page.evaluate(sel => {
    const body = document.querySelector(sel + ' .pg-body'), g = document.querySelector(sel + ' [data-pg-group="text"]');
    if (!body || !g) return null;
    return {open: ParsehGear.mounted().isOpen(), top: Math.round(g.getBoundingClientRect().top - body.getBoundingClientRect().top),
            typo: !document.querySelector('.parseh-typo') || document.querySelector('.parseh-typo').hidden,
            on: document.querySelector('#typo').classList.contains('on')};
  }, PANEL);
  await page.locator('#typo').click();
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(200);
  const a = await atText();
  assert(a.open && a.typo && a.on, 'Aa opened the gear, and not the old panel: ' + JSON.stringify(a));
  assert(a.top >= 0 && a.top <= 14, 'at its Text group: the group is at the top of the panel (' + a.top + ' px)');
  await shot(page, 'g-aa-text');
  await page.locator('#typo').click();
  await sleep(200);
  const shut = await atText();
  eq([shut.open, shut.on], [false, false], 'Aa again put it away');
  // the gear opened by its own button, at the top; Aa brings Text up in it, and only the next Aa closes it
  await page.locator('button.pg-gear').click();
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  const top0 = (await atText()).top;
  assert(top0 > 100, 'the gear opens at the top, with Text well below (' + top0 + ' px)');
  await page.locator('#typo').click();
  await sleep(250);
  const b = await atText();
  assert(b.open && b.top >= 0 && b.top <= 14, 'Aa with the gear already open scrolled to Text and left it open: ' + JSON.stringify(b));
  await page.locator('#typo').click();
  await sleep(200);
  eq((await atText()).open, false, 'and the next Aa shut it');
  // scrolled away from Text, Aa goes back to Text instead of shutting
  await page.locator('#typo').click();
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await page.evaluate(sel => { document.querySelector(sel + ' .pg-body').scrollTop = 0; }, PANEL);
  await sleep(100);
  await page.locator('#typo').click();
  await sleep(250);
  const c = await atText();
  assert(c.open && c.top <= 14, 'scrolled away from Text, Aa brought it back: ' + JSON.stringify(c));
  // Esc shuts it and is not heard by the page: a card sheet that is open stays
  await page.keyboard.press('Escape');
  await sleep(200);
  eq((await atText()).open, false, 'Esc shuts the gear');
  await page.context().close();
}

// ================================================================== h) kept across a reload, and across browsers
async function partH() {
  console.log('h) kept across a reload, and across two browsers');
  const page = await pageFor(DESK);
  await open(page, FA);
  await openGear(page);
  // every row of Watching & reading, the dictionary, the skip, the colours and a size: all changed
  await flip(page, 'watching', 'follow');
  await flip(page, 'watching', 'hoverpause');
  await flip(page, 'watching', 'pin');
  await flip(page, 'watching', 'sbs');
  await flip(page, 'watching', 'marks');
  await page.waitForFunction(() => !document.querySelector('#dictmode').hidden);
  await flip(page, 'looking', 'dict');
  await page.evaluate(sel => { const i = document.querySelector(sel + ' input[type=range]'); i.value = '27'; i.dispatchEvent(new Event('input', {bubbles: true})); }, ROW('text', 'fa'));
  await page.selectOption(ROW('playback', 'skip') + ' select', {label: '30 s'});
  await page.locator(ROW('colours', 'theme') + ' [role=radio]', {hasText: 'Dark'}).click();
  await sleep(300);
  const keys = ['yt_follow', 'yt_hoverpause', 'yt_pin', 'yt_sbs', 'yt_marks', 'yt_dict', 'bk_skip', 'parseh_theme'];
  const was = await page.evaluate(k => k.map(x => localStorage.getItem(x)), keys);
  eq(was, ['0', '1', '0', '1', '0', '1', '30', 'dark'], 'every row kept its key');
  const panel = () => page.evaluate(sel => ({
    switches: [...document.querySelectorAll(sel + ' .pg-switch')].filter(s => s.getClientRects().length).map(s => s.getAttribute('aria-checked')),
    skip: document.querySelector(sel + ' [data-pg-row=skip] select').value,
    fa: document.querySelector(sel + ' [data-pg-row=fa] input[type=range]').value,
    theme: [...document.querySelectorAll(sel + ' [data-pg-row=theme] [role=radio]')].filter(c => c.getAttribute('aria-checked') === 'true').map(c => c.textContent)}), PANEL);
  const pageNow = () => page.evaluate(() => ({
    buttons: ['#follow', '#hoverpause', '#pin', '#sbs', '#dictmode'].map(s => document.querySelector(s).classList.contains('on')),
    layout: [document.body.classList.contains('sbs'), document.body.classList.contains('nopin')],
    theme: document.documentElement.getAttribute('data-theme'), fa: getComputedStyle(document.documentElement).getPropertyValue('--yt-fa').trim(),
    marks: document.querySelector('#segs .seg[data-i="1"] .w').textContent}));
  const before = {panel: await panel(), page: await pageNow()};
  await page.reload();
  await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n && window.ParsehGear && ParsehGear.mounted(), FA.caps.length);
  await page.waitForFunction(() => !document.querySelector('#dictmode').hidden);
  await openGear(page);
  eq(await page.evaluate(k => k.map(x => localStorage.getItem(x)), keys), was, 'the keys are still there after a reload');
  const after = {panel: await panel(), page: await pageNow()};
  eq(after, before, 'after a reload the page and the panel are exactly what they were');
  eq(before.page.marks, 'هیچ جای دنیا', '(and the lines are still without their marks)');
  await shot(page, 'h-after-reload');
  await page.waitForTimeout(1500);                    // the toolbox is told of what follows a person, a moment after
  // -- THE PERSON'S OWN: the skip and the colours cross to another browser; the device's own do not
  const other = await pageFor(DESK);
  await open(other, FA);
  await other.waitForFunction(() => localStorage.getItem('bk_skip') === '30' && document.documentElement.getAttribute('data-theme') === 'dark', null, {timeout: 12000});
  eq(await other.evaluate(k => k.map(x => localStorage.getItem(x)), keys), [null, null, null, null, null, null, '30', 'dark'],
     'a second browser, which has never been here, has the skip and the colours of the first -- and none of the device\'s own');
  await openGear(other);
  eq(await other.evaluate(sel => document.querySelector(sel + ' [data-pg-row=skip] select').value, PANEL), '5', 'its panel shows the skip (thirty seconds)');
  await other.context().close();
  await page.context().close();
}

// ================================================================== i) the phone
async function partI() {
  console.log('i) the phone: no ⋯, the first line, the sheet, its rows');
  const page = await pageFor(PHONE, 'mobile', {}, {mt: true});
  await open(page, EN);
  await page.waitForFunction(() => !document.querySelector('#dictmode').hidden && !document.querySelector('#defmt').hidden);
  await page.waitForFunction(() => window.ParsehMobilePlayer && !!ParsehMobilePlayer.lines && document.querySelector('.nc-dock'));
  // lib/keep.js draws the Keep buttons into the bar a moment after the page is up (where the page can be kept)
  await page.waitForFunction(() => !!document.querySelector('.kp-btn'), null, {timeout: 6000}).catch(() => {});
  await shot(page, 'i-phone-line');
  // -- the first line: ش ▤ the title, Aa, ?, ⚙ -- and no ⋯, no group lines, no switch
  const line = await page.evaluate(() => {
    const h = document.querySelector('header');
    const what = e => e.classList.contains('glyph') ? 'hub' : e.matches('a.home') ? 'shelf' : e.classList.contains('ttl') ? 'title'
      : e.id === 'typo' ? 'Aa' : e.classList.contains('px-ask') ? '?' : e.classList.contains('pg-gear') ? 'gear' : (e.className || e.id || e.tagName);
    const kids = [...h.children].filter(e => getComputedStyle(e).display !== 'none' && e.getClientRects().length)
      .map(e => { const r = e.getBoundingClientRect(); return {t: what(e), top: Math.round(r.top), left: Math.round(r.left), right: Math.round(r.right), h: Math.round(r.height), w: Math.round(r.width)}; })
      .sort((a, b) => a.left - b.left);              // as it is drawn, left to right: the stylesheet orders the line
    return {kids, more: !!document.querySelector('.m-rmore'), labs: document.querySelectorAll('.m-rlab').length, sw: !!h.querySelector('.parseh-mode'),
            moreCls: h.classList.contains('m-more'), W: innerWidth, hh: Math.round(h.getBoundingClientRect().height)};
  });
  eq([line.more, line.labs, line.sw], [false, 0, false], '⋯, the lines that named its groups and the Browser | Mobile switch are not built where there is a gear');
  eq(line.kids.map(k => k.t), ['hub', 'shelf', 'title', 'Aa', '?', 'gear'], 'the first line is ش ▤ the title, Aa, ?, ⚙');
  assert(line.kids.every(k => Math.abs(k.top - line.kids[0].top) <= 12), 'and it is one line: ' + JSON.stringify(line.kids.map(k => k.top)));
  const gear = line.kids[line.kids.length - 1];
  assert(gear.w >= 48 && gear.h >= 48 && line.W - gear.right <= 14, 'the gear is last, 48px or more, at the right edge where ⋯ was: ' + JSON.stringify(gear));
  assert(line.kids.filter(k => k.t !== 'title').every(k => k.w >= 44 && k.h >= 44), 'every target of the line is a finger\'s: ' + JSON.stringify(line.kids.map(k => [k.t, k.w, k.h])));
  eq(await page.evaluate(() => ['#follow', '#hoverpause', '#aloud', '#pin', '#dictmode', '#defmode', '#defmt', '#theme', '#sbs', '#lookupset'].filter(s => { const e = document.querySelector(s); return e && getComputedStyle(e).display !== 'none' && !e.hidden; })),
     [], 'none of what ⋯ held is on the bar: it is in the sheet');
  assert(await drawn(page, '.nc-dock'), 'the dock is at the foot');
  // -- the sheet: one, half the screen, the page above it
  await tap(page, 'button.pg-gear');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(300);
  const sheet = await page.evaluate(sel => { const p = document.querySelector(sel), r = p.getBoundingClientRect();
    return {sheet: p.classList.contains('pg-sheet'), top: Math.round(r.top), h: Math.round(r.height), bottom: Math.round(r.bottom), H: innerHeight, html: document.documentElement.classList.contains('pg-sheet')}; }, PANEL);
  assert(sheet.sheet && sheet.html && Math.abs(sheet.h - sheet.H * 0.55) <= 4 && sheet.bottom === sheet.H, 'a sheet from the foot, about half the screen high: ' + JSON.stringify(sheet));
  // -- THE INDEX it opens on: a row for each theme, what each is set to under its name
  eq(await page.evaluate(() => ParsehGear.mounted().stage()), 'index', 'it opens on the index of the themes');
  const idx = await page.evaluate(sel => [...document.querySelectorAll(sel + ' .pg-irow')].filter(r => r.getClientRects().length).map(r =>
    [r.dataset.pgIndex, r.querySelector('.pg-iname').textContent, r.querySelector('.pg-isum').textContent, Math.round(r.getBoundingClientRect().height)]), PANEL);
  console.log('  index:', JSON.stringify(idx));
  assert(idx.length >= 6 && idx.every(r => r[3] >= 48), 'a row for each theme, each a finger high: ' + JSON.stringify(idx.map(r => [r[0], r[3]])));
  const fits = await page.evaluate(sel => { const b = document.querySelector(sel + ' .pg-body').getBoundingClientRect();
    return [...document.querySelectorAll(sel + ' .pg-irow')].filter(r => r.getClientRects().length).every(r => { const q = r.getBoundingClientRect(); return q.top >= b.top - 0.5 && q.bottom <= b.bottom + 0.5; }); }, PANEL);
  eq(fits, true, 'and every one of them is inside the half sheet at once, with no scrolling');
  const said = Object.fromEntries(idx.map(r => [r[0], r[2]]));
  assert(/^follows\b/.test(said.watching) && /video \d+ %$/.test(said.watching), 'Watching & reading says the switches that are on and the size of the video: "' + said.watching + '"');
  assert(/^1×, skip \d+ s$/.test(said.playback), 'Playback says its speed and its skip: "' + said.playback + '"');
  eq(said.looking.length > 0, true, 'Looking a word up says whether a dictionary is used: "' + said.looking + '"');
  assert(/^English text \d+(\.\d+)? px$/.test(said.text), 'Text says its first slider\'s value: "' + said.text + '"');
  eq(said.interface, 'Mobile pages', 'Interface says Mobile pages');
  await shot(page, 'i-sheet-index');
  await enterTheme(page, 'watching');
  await shot(page, 'i-sheet-watching');
  const groups = await drawnGroups(page);
  const zoom = await page.evaluate(() => !!window.ParsehZoom);
  eq(groups.map(g => g[1]), ['Watching & reading', 'Looking a word up', 'Playback', 'Text'].concat(zoom ? ['Zoom'] : [], ['Colours', 'Interface']), 'the same groups, in the same order');
  const kp = await page.evaluate(() => document.querySelectorAll('.kp-btn').length);
  const rows = Object.fromEntries(groups.map(g => [g[0], g[2]]));
  eq(rows.watching, ['follow', 'hoverpause', 'sbs', 'pin', 'size', 'lines'], 'Watching & reading on a phone gains «show the lines around»');
  eq(rows.playback, ['skip', 'speed'], 'Playback gains the speed: the page has a control of its own for it, the dock');
  eq(rows.text, ['fa', 'sub', 'gl', 'width', 'lead', 'reset'], 'Text gains the subtitles\' size');
  assert(rows.interface[0] === 'mode' && (kp ? rows.interface[1] === 'keep' : true), 'Interface holds the Browser | Mobile choice' + (kp ? ' and the Keep buttons' : ' (no Keep buttons on this page)') + ': ' + JSON.stringify(rows.interface));
  // every drawn row is a finger's, and the page above the sheet is the page
  const small = await page.evaluate(sel => [...document.querySelectorAll(sel + ' [data-pg-group=watching] [data-pg-row]')].filter(r => r.getClientRects().length && r.getBoundingClientRect().height < 48).map(r => r.dataset.pgRow), PANEL);
  eq(small, [], 'no row is under 48px high');
  const above = await page.evaluate(sel => { const p = document.querySelector(sel).getBoundingClientRect().top; const v = document.querySelector('#playerwrap').getBoundingClientRect(); return [Math.round(v.bottom), Math.round(p)]; }, PANEL);
  assert(above[0] <= above[1] + 1, 'the video is above the sheet, not under it: ' + JSON.stringify(above));
  // -- every row, both ways, by a finger
  const st = () => page.evaluate(() => ({
    follow: [document.querySelector('#follow').classList.contains('on'), localStorage.getItem('yt_follow')],
    hover: [document.querySelector('#hoverpause').classList.contains('on'), localStorage.getItem('yt_hoverpause')],
    pin: [document.querySelector('#pin').classList.contains('on'), localStorage.getItem('yt_pin'), document.body.classList.contains('nopin')],
    dict: [document.querySelector('#dictmode').classList.contains('on'), localStorage.getItem('yt_dict')],
    defs: [document.querySelector('#defmode').classList.contains('on'), localStorage.getItem('yt_defs')],
    mt: [document.querySelector('#defmt').classList.contains('on'), localStorage.getItem('yt_defs_mt')]}));
  eq(await st().then(s => [s.follow, s.hover, s.pin]), [[true, null], [false, null], [true, null, false]], 'the page, before');
  await flip(page, 'watching', 'follow');
  await flip(page, 'watching', 'hoverpause');
  await flip(page, 'watching', 'pin');
  eq(await st().then(s => [s.follow, s.hover, s.pin]), [[false, '0'], [true, '1'], [false, '0', true]], 'tapped: the page\'s own buttons moved, and the keys');
  await flip(page, 'watching', 'follow');
  await flip(page, 'watching', 'hoverpause');
  await flip(page, 'watching', 'pin');
  eq(await st().then(s => [s.follow, s.hover, s.pin]), [[true, '1'], [false, '0'], [true, '1', false]], 'and tapped back');
  // the video beside the text rests on a phone, and says it is the turning that does it
  const sbs = await page.evaluate(sel => ({off: document.querySelector(sel + ' .pg-switch').disabled, on: document.querySelector(sel + ' .pg-switch').getAttribute('aria-checked'),
                                           why: document.querySelector(sel + ' .pg-why').textContent}), ROW('watching', 'sbs'));
  eq(sbs, {off: true, on: 'false', why: 'On a phone, turning it sideways does it.'}, '«video beside the text» rests on a phone, and says what does it');
  await flip(page, 'looking', 'dict');
  await flip(page, 'looking', 'defs');
  await flip(page, 'looking', 'defsmt');
  eq(await st().then(s => [s.dict, s.defs, s.mt]), [[true, '1'], [true, '1'], [true, '1']], 'the dictionary, its definitions and their translation, tapped');
  await flip(page, 'looking', 'defsmt');
  await flip(page, 'looking', 'defs');
  await flip(page, 'looking', 'dict');
  eq(await st().then(s => [s.dict, s.defs, s.mt]), [[false, '0'], [false, '0'], [false, '0']], 'and back');
  // the skip, the speed (the dock's chip follows it), the sizes
  await openGear(page, 'playback');
  await page.selectOption(ROW('playback', 'skip') + ' select', {label: '15 s'});
  await sleep(150);
  eq(await page.evaluate(() => [localStorage.getItem('bk_skip'), document.querySelector('.nc-skip[data-skip="1"]').textContent]), ['15', '15 ↻'], 'the skip: kept, and the dock\'s ↻ says it');
  const speed = ROW('playback', 'speed');
  eq(await page.evaluate(s => document.querySelector(s + ' .pg-stepval').textContent, speed), '1×', 'the speed starts at 1×');
  await tap(page, speed + ' button[aria-label=Increase]');
  await sleep(300);
  eq(await page.evaluate(s => [document.querySelector(s + ' .pg-stepval').textContent, localStorage.getItem('vd_rate'), __yt.rate, document.querySelector('.nc-chip').textContent], speed),
     ['1.25×', '1.25', 1.25, '1.25×'], 'the speed stepper: the video\'s own key (vd_rate), the player, and the dock\'s chip');
  await tap(page, speed + ' button[aria-label=Decrease]');
  await sleep(300);
  eq(await page.evaluate(() => __yt.rate), 1, 'and back down');
  // a speed chosen on the dock moves the stepper (the dock is under the sheet, out of reach of a finger: the
  // chip's menu calls this very function)
  await page.evaluate(() => ParsehNarr.setRate(1.5));
  await sleep(400);
  eq(await page.evaluate(s => document.querySelector(s + ' .pg-stepval').textContent, speed), '1.5×', 'a speed chosen from the dock moves the open stepper');
  await page.evaluate(() => ParsehNarr.setRate(1));
  await shot(page, 'i-sheet-playback');
  // -- Text on the sheet, and Aa
  await enterTheme(page, 'text');
  await shot(page, 'i-sheet-text');
  await tap(page, 'button.pg-gear');                       // shut
  await page.waitForFunction(() => !ParsehGear.mounted().isOpen());
  await tap(page, '#typo');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(300);
  const aa = await page.evaluate(sel => [ParsehGear.mounted().stage(), document.querySelector(sel + ' .pg-title').textContent, !document.querySelector('.parseh-typo') || document.querySelector('.parseh-typo').hidden], PANEL);
  eq(aa, ['text', 'Text', true], 'Aa on a phone opens the sheet at Text (the index underneath) and not the old panel');
  await shot(page, 'i-aa-text');
  // a second press shuts it while Text is on stage; pressed on another theme it brings Text back
  await tap(page, '#typo');
  await page.waitForFunction(() => !ParsehGear.mounted().isOpen());
  assert(true, 'a second press of Aa shuts the sheet while Text is on stage');
  await tap(page, '#typo');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(300);
  await enterTheme(page, 'colours');
  await tap(page, '#typo');
  await sleep(300);
  eq(await page.evaluate(() => [ParsehGear.mounted().isOpen(), ParsehGear.mounted().stage()]), [true, 'text'], 'pressed while another theme is on stage, Aa brings Text and does not shut the sheet');
  await page.evaluate(sel => { const i = document.querySelector(sel + ' input[type=range]'); i.value = '30'; i.dispatchEvent(new Event('input', {bubbles: true})); }, ROW('text', 'sub'));
  eq(await page.evaluate(() => JSON.parse(localStorage.getItem('yt_typo')).sub), 30, 'the subtitles\' size, kept in yt_typo');
  // -- the Keep buttons: in the sheet's last group while it is up, and where they were when it is not
  if (kp) {
    eq(await page.evaluate(sel => [!!document.querySelector(sel + ' [data-pg-row=keep] .kp-btn'), !!document.querySelector('header .kp-btn')], PANEL), [false, true], 'the Keep buttons stay on the page while another theme is on stage');
    await enterTheme(page, 'interface');
    eq(await page.evaluate(sel => [!!document.querySelector(sel + ' [data-pg-row=keep] .kp-btn'), !!document.querySelector('header .kp-btn')], PANEL), [true, false], 'the Keep buttons stand in the last group while its theme is on stage');
    await shot(page, 'i-sheet-interface');
    await page.evaluate(() => ParsehGear.mounted().close());
    eq(await page.evaluate(() => [!!document.querySelector('.pg-panel .kp-btn'), !!document.querySelector('header .kp-btn')]), [false, true], 'and are back on the page when it is shut');
  }
  // -- the Browser | Mobile choice is in the sheet, and the page has no switch of its own
  await tap(page, 'button.pg-gear');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  eq(await page.evaluate(sel => [...document.querySelectorAll(sel + ' [data-pg-row=mode] button')].map(b => [b.textContent, b.getAttribute('aria-pressed')]), PANEL),
     [['Browser', 'false'], ['Mobile', 'true']], 'the Browser | Mobile choice, Mobile in force');
  eq(await page.evaluate(sel => document.querySelector(sel + ' .pg-irow[data-pg-index=interface] .pg-isum').textContent, PANEL), 'Mobile pages', 'and the index says it');
  await page.context().close();
}

// ================================================================== j) held sideways, and the whole screen
async function partJ() {
  console.log('j) a phone held sideways, and its whole screen');
  const page = await pageFor(LAND, 'mobile', {}, {});
  await open(page, EN);
  await page.waitForFunction(() => window.ParsehMobilePlayer && !!ParsehMobilePlayer.lines && document.querySelector('.m-vfull') && !document.querySelector('.m-vfull').hidden);
  await shot(page, 'j-sideways');
  const first = await page.evaluate(() => [...document.querySelector('header').children].filter(e => getComputedStyle(e).display !== 'none' && e.getClientRects().length)
    .sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left).map(e => e.className || e.id));
  assert(first[first.length - 1].includes('pg-gear') && first.some(c => String(c).includes('m-vfull')) && first.includes('typo'), 'sideways the first line is ... Aa ⛶ ? ⚙: ' + JSON.stringify(first));
  await tap(page, 'button.pg-gear');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  await sleep(300);
  const sheet = await page.evaluate(sel => { const r = document.querySelector(sel).getBoundingClientRect(); return [Math.round(r.height), innerHeight]; }, PANEL);
  assert(sheet[0] >= 239 && sheet[0] <= 242, 'sideways the sheet is half the screen, with a floor of 240px: ' + JSON.stringify(sheet));
  await shot(page, 'j-sheet-sideways');
  const sbs = await page.evaluate(sel => [document.querySelector(sel + ' .pg-switch').getAttribute('aria-checked'), document.querySelector(sel + ' .pg-switch').disabled], ROW('watching', 'sbs'));
  eq(sbs, ['true', true], 'sideways «video beside the text» says that it is on (the phone\'s turning did it) and rests');
  // the lines around: set from the gear, seen on the whole screen
  eq(await switchOn(page, 'watching', 'lines'), false, 'the lines around are off to begin with');
  await flip(page, 'watching', 'lines');
  eq(await store(page, 'vd_subctx'), '1', 'the row kept the choice where the whole screen keeps it (vd_subctx)');
  await page.evaluate(() => document.querySelector('#segs .seg[data-i="2"] .lab').click());
  await page.waitForFunction(() => { const s = document.querySelector('#segs .seg.on-air'); return s && +s.dataset.i === 2; });
  await tap(page, '.m-vfull');
  await page.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(500);
  const full = await page.evaluate(() => ({
    gear: ParsehGear.mounted().isOpen(), sheet: document.documentElement.classList.contains('pg-sheet'),
    ctx: (() => { const b = document.querySelector('.m-vctx'); return b && {pressed: b.getAttribute('aria-pressed'), text: b.textContent, aria: b.getAttribute('aria-label'), w: Math.round(b.getBoundingClientRect().width), h: Math.round(b.getBoundingClientRect().height)}; })(),
    lines: document.querySelectorAll('.m-subs .seg').length, txt: !!document.querySelector('.m-vtxt'),
    corner: ['.m-vout', '.m-vctx', '.m-vtxt'].map(s => { const r = document.querySelector(s).getBoundingClientRect(); return [s, Math.round(r.left), Math.round(r.right)]; })}));
  assert(!full.gear && !full.sheet, 'the whole screen put the sheet away: it carries no gear');
  eq(full.ctx.pressed, 'true', 'the lines-around button over the picture is on, in step with the row');
  assert(full.ctx.text.includes('lines around') && full.ctx.aria.startsWith('lines around'), 'and says what it is, in words: ' + JSON.stringify(full.ctx));
  eq(full.lines, 3, 'and the subtitle is three lines: the one before, the one being said, the one after');
  const [out, ctx, txt] = full.corner;
  assert(txt[2] <= ctx[1] && ctx[2] <= out[1], 'in the corner they stand side by side, none over another: ' + JSON.stringify(full.corner));
  await shot(page, 'j-whole-screen');
  // its own small Aa: the subtitles and the glosses, and nothing else; no gear
  await tap(page, '.m-vtxt');
  await page.waitForFunction(() => document.querySelector('.parseh-typo') && !document.querySelector('.parseh-typo').hidden);
  const aa = await page.evaluate(() => ({rows: [...document.querySelectorAll('.parseh-typo .trow')].filter(r => getComputedStyle(r).display !== 'none').map(r => r.querySelector('input').id),
                                          foot: getComputedStyle(document.querySelector('.parseh-typo .tfoot')).display, gear: document.querySelectorAll('.pg-panel:not([hidden])').length}));
  eq(aa, {rows: ['st-sub', 'st-gl'], foot: 'none', gear: 0}, 'the whole screen\'s own Aa is the small panel it was: the subtitles and the glosses, no foot, no gear');
  await shot(page, 'j-whole-aa');
  await tap(page, '.m-vtxt');
  // the button over the picture, off; and the gear agrees
  await tap(page, '.m-vctx');
  await sleep(300);
  eq([await store(page, 'vd_subctx'), await page.evaluate(() => document.querySelectorAll('.m-subs .seg').length)], ['0', 1], 'the button over the picture put the lines around away');
  await tap(page, '#playerwrap .m-vout');
  await page.waitForFunction(() => !document.documentElement.classList.contains('m-vfullon'));
  await tap(page, 'button.pg-gear');
  await page.waitForFunction(() => ParsehGear.mounted().isOpen());
  eq(await switchOn(page, 'watching', 'lines'), false, 'back on the page the gear says they are off');
  await page.context().close();
}

// ================================================================== k) room, and the three themes
const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
async function partK() {
  console.log('k) nothing overflows, and the three themes');
  const page = await pageFor(DESK, 'browser', {}, {mt: true});
  await open(page, EN);
  // -- from 320 to 1280, in both layouts, the panel up and shut
  for (const mode of ['browser', 'mobile']) {
    await page.evaluate(m => { localStorage.setItem('parseh_mode', m); document.cookie = 'parseh_mode=' + m + '; path=/'; }, mode);
    await page.reload();
    await page.waitForFunction(n => document.querySelectorAll('#segs .seg').length === n && window.ParsehGear && ParsehGear.mounted(), EN.caps.length);
    for (const w of [320, 360, 390, 560, 768, 1024, 1280]) {
      await page.setViewportSize({width: w, height: w < 600 ? 800 : 700});
      await sleep(200);
      for (const up of [false, true]) {
        // a narrow screen's bar slides away as the page moves down and is whole again at the top
        await page.evaluate(() => scrollTo(0, 0));
        await sleep(250);
        if (up) await openGear(page); else await shutGear(page);
        await sleep(150);
        const r = await page.evaluate(() => ({doc: document.documentElement.scrollWidth, body: document.body.scrollWidth, W: innerWidth,
          panel: (() => { const p = document.querySelector('.pg-panel'); if (!p || p.hidden) return null; const b = p.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right)]; })()}));
        assert(r.doc <= r.W && r.body <= r.W, `${mode} layout, ${w}px, panel ${up ? 'up' : 'shut'}: nothing wider than the window (${r.doc}/${r.body} in ${r.W})`);
        if (up) assert(r.panel[0] >= 0 && r.panel[1] <= r.W, `${mode} layout, ${w}px: the panel is inside the window ${JSON.stringify(r.panel)}`);
      }
    }
  }
  await shutGear(page);
  await page.context().close();
  // -- the three themes: the bar, the button, the panel, and the sheet are readable in each
  for (const [name, kind, mode] of [['desk', DESK, 'browser'], ['phone', PHONE, 'mobile']]) {
    for (const theme of ['light', 'dark', 'sepia']) {
      const p = await pageFor(kind, mode);
      await open(p, FA);
      await tap(p, 'button.pg-gear');
      await p.waitForFunction(() => ParsehGear.mounted().isOpen());
      // the colours are chosen where a person chooses them, in the panel: they follow the person, and the toolbox
      // has already been told of the last choice made in this run
      await enterTheme(p, 'colours');
      await tap(p, ROW('colours', 'theme') + ' [role=radio]:has-text("' + theme[0].toUpperCase() + theme.slice(1) + '")');
      await p.waitForFunction(t => document.documentElement.getAttribute('data-theme') === t, theme);
      await sleep(300);
      const c = await p.evaluate(sel => {
        // a colour as the browser answers it: rgb(r, g, b), or -- where the sheet mixes two -- color(srgb r g b) with the
        // three in 0..1
        const rgb = s => { const n = (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number); return /^color\(/.test(s) ? n.map(v => v * 255) : n; };
        const bg = e => { for (let n = e; n; n = n.parentElement) { const v = getComputedStyle(n).backgroundColor; const m = v.match(/[\d.]+/g); if (m && (m.length < 4 || +m[3] > 0.5)) return rgb(v); } return [255, 255, 255]; };
        const pair = s => { const e = document.querySelector(s); return [rgb(getComputedStyle(e).color), bg(e)]; };
        return {theme: document.documentElement.getAttribute('data-theme'), gear: pair('button.pg-gear'), name: pair(sel + ' .pg-nametext'), help: pair(sel + ' .pg-help'),
                caption: pair(sel + ' .pg-caption'), title: pair(sel + ' .pg-gtitle'), follow: pair('#follow'), typo: pair('#typo')};
      }, PANEL);
      eq(c.theme, theme, `${name}: the page wears ${theme}`);
      for (const k of ['gear', 'name', 'help', 'caption', 'title']) {
        const [fg, bgc] = c[k];
        assert(ratio(fg, bgc) >= 4.5, `${name}, ${theme}: the ${k} is readable (${ratio(fg, bgc).toFixed(1)}:1)`);
      }
      await p.evaluate(sel => { document.querySelector(sel + ' .pg-body').scrollTop = 0; }, PANEL);
      await sleep(100);
      await shot(p, `k-${name}-${theme}-gear`);
      await p.evaluate(sel => document.querySelector(sel + ' [data-pg-group=text]').scrollIntoView(), PANEL);
      await shot(p, `k-${name}-${theme}-text`);
      await p.context().close();
    }
  }
}

const RUN = {a: partA, b: partB, c: partC, d: partD, e: partE, f: partF, g: partG, h: partH, i: partI, j: partJ, k: partK};
// every part runs, whatever the one before it did: a part that fails says where and the next goes on,
// so that one run tells everything that is wrong and not only the first thing
const failed = [];
try {
  for (const [k, fn] of Object.entries(RUN)) {
    if (!wanted(k)) continue;
    try { await fn(); }
    catch (e) {
      failed.push(k + ': ' + (e && e.message || e));
      console.log('  FAILED part ' + k + ' -- ' + (e && e.message || e));
      for (const c of contexts.splice(0)) await c.close().catch(() => {});
    }
  }
} finally {
  for (const c of contexts) await c.close().catch(() => {});
  await browser.close();
  try { hub.kill('SIGTERM'); } catch (_) {}
  await Deno.remove(WORK, {recursive: true}).catch(() => {});
}
if (errors.length) failed.push('page errors: ' + [...new Set(errors)].join(' | '));
if (failed.length) {
  console.log(passed + ' checks passed, and ' + failed.length + ' failed:\n  ' + failed.join('\n  '));
  Deno.exit(1);
}
console.log(passed + ' checks passed');
