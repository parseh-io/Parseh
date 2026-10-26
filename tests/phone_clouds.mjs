// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of what the mobile interface's clouds gained in a0.3.1 and
// a0.3.2 (the owner, 2026-09-24; TO-DO §4.18), against the REAL hub over a
// temporary toolbox (tests/mobile_harness.py's tree, served here with
// dictionaries of its own -- English, Persian and Arabic -- a book and a
// video with few glosses, two books of two chapters, a Persian video, a
// Japanese one and a Chinese one, and a video on YouTube whose player is
// faked):
//
// lines -- a video on the whole screen (lib/mobileplayer.js):
//   a) beside the way out, a switch for the lines around the one being said;
//      off, the subtitle is the one line it always was
//   b) on: the caption before above and the caption after below, in ONE cloud
//      with the line being said, each a little smaller and a little greyer
//      than it; the cloud larger for them, and clear of the corner's buttons
//   c) a tap on a phrase of the line before, and of the line after, opens that
//      phrase's own gloss; a mouse at rest on one opens it too, and it goes
//      when the mouse goes
//   d) the lines follow the video -- the first caption has none before it, the
//      last none after -- and the choice is remembered, off and on
// the dictionary's sheet -- on a phone (Parseh.dictSheet, lib/parseh.js):
//   e) a GLOSSED phrase or chunk: its cloud as it always was (its gloss, beside
//      the word, nothing more -- the book's the very cloud the browser mode
//      draws, bar the button); beside "copy" a button, and it opens the
//      dictionary in a SHEET from the foot of the screen, not in the cloud:
//      as tall as the entry, one scroller that keeps its scrolling to itself,
//      the word above it and marked, the gloss over the entry; a tap in the
//      sheet leaves it be; closed -- by a tap beside it, a swipe down, ✕ or
//      the back gesture -- NOTHING is left open, and a video the sheet paused
//      goes on; the cloud's buttons a finger's size, and no colour marks (they
//      write the video).  THE SHEET AS TALL AS THE ENTRY, up to 86% of the
//      screen, WHATEVER THE PAGE PINS (the owner, 2026-09-25): the word
//      scrolled into the room above it where there is one, covered by it,
//      still marked, where there is none -- upright under the pinned video,
//      and held sideways -- and seen again, where it was, once the sheet has
//      gone; a YouTube video buffering as the sheet opens paused with the
//      rest, and going on after
//   f) over the subtitles of a video on the whole screen: it covers them, the
//      video waits paused, and the back gesture closes the sheet and leaves
//      the video on the whole screen -- a second one leaves that; and the
//      browser leaving its own full screen (Android's back gesture in a tab)
//      closes the sheet alone, the next back leaving the video, none left over
//   g) RIGHT TO LEFT: a Persian and an Arabic entry, in a book and in a video,
//      in the language's face and direction and isolated, under an English
//      head; the hit's headword says its language; senses numbered, one to a
//      line; the part of speech a label.  Sideways, a long entry stops at 86%
//      of the screen, over the word, and scrolls inside, the page never
//      moving under it.  A
//      language with nothing to look it up says so, and where to set one up.
//      Its own words say they are English in a Persian book; the reader
//      opening its cloud again under it (a model arriving late) leaves the
//      cloud hidden and the answer landing; a sheet over a sheet keeps one
//      going back; Tab stays inside it; the question of where the other
//      device stopped waits for it, and gives way to it; and a book's
//      narration waits while it is up, as a video does
//   h) the browser interface has no such button, no sheet and no mark
//   i) a chunk with NOTHING written, tapped with the dictionary on: the sheet
//      at once, no cloud -- in a book and in a video; its entry already known,
//      the sheet takes it whole, not cut to the room the cloud had; a mouse at
//      rest on one keeps the cloud.  A GLOSS IS ANY LINE OF ONE (the owner,
//      2026-09-25): a chunk with a meaning alone, or a transliteration alone,
//      opens its cloud with the dictionary's button, and no entry in it
//   j) a book or video with FEW glosses (under half, any line counting): where
//      nothing is underlined (a book's passes) its glossed chunks wear a faint
//      dotted underline in --faint; where every phrase already wears that line
//      (a video's phrases, a book's first pass in hover mode) the others keep
//      it and the glossed ones wear it darker, in --dim -- over the subtitles'
//      black, near white; in every theme, the text and its colour as they
//      were; one half glossed or more, and the browser mode, look exactly as
//      they did.  Counted over the WHOLE book -- one glossed from the front is
//      sparse -- and a chapter fetched later marked as it arrives
//   l) the video's transcript on a phone has no + between its captions (it
//      writes a note into the video); the browser interface keeps it
//   k) the toast still stands over the sheet
//   m) the size of the words (L12; tests/mobile_pages.mjs e1 drives the same
//      panel on the English film): on a Persian video and a Japanese and a
//      Chinese one, in the three themes -- upright, Aa on the header's first
//      line opens the panel with the transcript's size and no subtitles'
//      slider; held sideways on the whole screen, the Aa in the corner opens
//      it over the picture with the subtitles' slider and the glosses', the
//      subtitle the size the slider says and in the language's direction,
//      the lines around it in proportion at 48px and clear of the corner;
//      and in English at 36px the proportions of a plain line
// hover ⏸ in a book (a0.4.1; the owner, 2026-09-25 and 2026-09-28; TO-DO §4.20 and §7.21):
//   n) the video's switch in a book's reader, in BOTH modes, remembered on
//      this device only (bk_hoverpause; never in the prefs the computer keeps):
//      kept in the header out of sight (the gear's row "Pause while a gloss is open"
//      presses it, in both layouts), worded as the video's, beside hover in the
//      markup, and not offered in a book with no narration.  Off, nothing changes; on, a cloud opened over a playing
//      narration (a tap, a mouse at rest) pauses it, once, the cloud still
//      open, and it goes on 350 ms after the cloud shuts; from one word to
//      the next within that, one pause and no play; paused by hand, or played
//      and paused by hand under the cloud, it is never started; the
//      dictionary's sheet on top, and a row's tap with nothing written: one
//      pause and one resume, after the grace; the reader opening its own cloud
//      again is no new open; the loop's wait between repeats is taken and given
//      back; the switch turned off under an open cloud gives back what it took;
//      and in the browser interface each of the reader's own sheets (cards, the
//      chunk's editor, the fold, the LLM gloss, the narration's) is left
//      alone.  What is read is the audio element's own play and pause events
//      with the page's clock, printed raw, not a boolean.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/phone_clouds.mjs
//   SHOTS=<dir> also saves a screenshot of each
import {chromium} from 'npm:playwright-core@1.52.0';
import {GEAR, gearOpen, gearClose, gearRow, gearSwitch, gearSelect, rowDrawn} from './gear_driver.mjs';

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

const VIDEO = 'four-lines-d4e5f6';
// every caption but the first has a glossed phrase first, so every line of
// the three has one to tap; the first is the video's own framing (plain),
// drawn as a line of English, which over the picture must be as legible as
// the rest.  Each caption's second phrase has nothing written: three phrases
// of the six glossed -- one of them with a meaning alone, which counts --
// is exactly half, which is NOT few, so the video looks as it always did.
// A chunk is [text, meaning, vocabulary, transliteration], '' for a line
// nobody wrote
const CAPTIONS = [
  {start: 0, text: 'Good morning, friends.', plain: true, chunks: []},
  {start: 2, text: 'The market opens early.', chunks: [['The market', 'the place of the stalls', 'market: where things are sold'], ['opens early.']]},
  {start: 4, text: 'Bring a bag today.', chunks: [['Bring a bag', 'come with something to carry', 'bag: a soft carrier'], ['today.']]},
  {start: 6, text: 'We buy fresh bread.', chunks: [['We buy', 'we pay for'], ['fresh bread.']]},
];
// A PERSIAN VIDEO, the same film: three phrases of eight with a gloss -- one
// with every line, one with a meaning alone, one with a transliteration
// alone -- so it is a video with FEW glosses, and a right-to-left one
const FA_VIDEO = 'persian-lines-a1b2c3';
const FA_CAPTIONS = [
  {start: 0, text: 'هیچ جایِ دُنیا تَروُ خُشک را', chunks: [
    ['هیچ جایِ دُنیا', 'nowhere in the world', 'جا jā place', 'hič jā-ye donyā'], ['تَروُ خُشک را']]},
  {start: 2, text: 'مِثلِ ایران با هَم نِمی سوزانَند.', chunks: [['مِثلِ ایران با هَم'], ['نِمی سوزانَند.', 'do they burn']]},
  {start: 4, text: 'پَس اَز پَنج سال', chunks: [['پَس اَز', '', '', 'pas az'], ['پَنج سال']]},
  {start: 6, text: 'سالِ نو در ایران', chunks: [['سالِ نو'], ['در ایران']]},
];
// A JAPANESE VIDEO AND A CHINESE ONE, the same film again, for the size of the
// words (m): the language's own face, a reading over the characters, and a
// line as tall as a subtitle can be.  A chunk is [text, meaning, vocabulary,
// transliteration, kana]
const JA_VIDEO = 'japanese-lines-d1e2f3';
const JA_CAPTIONS = [
  {start: 0, text: 'Hello everyone, welcome to today\'s lesson', plain: true, chunks: []},
  {start: 2, text: 'こんにちは、みなさん', chunks: [
    ['こんにちは、', 'hello,', 'こんにちは konnichiwa hello, good afternoon', 'konnichiwa,', 'こんにちは、'],
    ['みなさん', 'everyone', '皆さん みなさん minasan everyone (polite)', 'minasan', 'みなさん']]},
  {start: 4, text: '今日は 天気が いいですね', chunks: [
    ['今日は', 'today', '今日 きょう kyō today', 'kyō wa', 'きょうは'],
    ['天気が', 'the weather', '天気 てんき tenki weather', 'tenki ga', 'てんきが'],
    ['いいですね', 'is nice, isn\'t it', 'いい ii good', 'ii desu ne', 'いいですね']]},
  {start: 6, text: '私は毎朝コーヒーを飲みます', chunks: [
    ['私は', 'I', '私 わたし watashi I', 'watashi wa', 'わたしは'],
    ['毎朝', 'every morning', '毎朝 まいあさ maiasa every morning', 'maiasa', 'まいあさ'],
    ['コーヒーを飲みます', 'I drink coffee', '', '', 'コーヒーをのみます']]},
];
const ZH_VIDEO = 'chinese-lines-e4f5a6';
const ZH_CAPTIONS = [
  {start: 0, text: 'Welcome back to the channel, today we learn Chinese at the tea house', plain: true, chunks: []},
  {start: 2, text: '你好，我想要一杯茶', chunks: [
    ['你好，', 'hello,', '你 nǐ you; 好 hǎo good', 'nǐ hǎo'], ['我想要一杯茶', 'I would like a cup of tea', '茶 chá tea', 'wǒ xiǎng yào yì bēi chá']]},
  {start: 4, text: '好的，你要什么茶', chunks: [
    ['好的，', 'all right,', '好的 hǎo de all right', 'hǎo de'], ['你要什么茶', 'what tea do you want', '什么 shénme what', 'nǐ yào shénme chá']]},
  {start: 6, text: '绿茶，谢谢', chunks: [
    ['绿茶，', 'green tea,', '绿茶 lǜchá green tea', 'lǜchá'], ['谢谢', 'thank you', '谢谢 xièxie thanks', 'xièxie']]},
];
// what the dictionaries hold.  English's senses are English definitions,
// which an entry shows only with the header's "definitions" on; it always
// shows the entry, its part of speech and where it came from.  Persian's and
// Arabic's are translations, shown always, several to a word: the senses a
// sheet numbers
const SENSES = {old: 'of great age, said the test dictionary', market: 'a place of buying and selling, said the test dictionary',
                bag: 'a soft carrier, said the test dictionary'};
const DICTS = {
  en: [['old', '', 'adj', SENSES.old], ['market', '', 'noun', SENSES.market], ['bag', '', 'noun', SENSES.bag]],
  fa: [['هیچ', 'hič', 'det', 'no, none\nnothing'], ['جا', 'jā', 'noun', 'place\nroom, space\nseat'],
       ['دنیا', 'donyā', 'noun', 'world\nthe earth'], ['مثل', 'mesl', 'noun', 'like, as\nexample\nproverb'],
       ['ایران', 'irān', 'name', 'Iran'], ['سال', 'sāl', 'noun', 'year\nage']],
  // (the form with the article, as the source's form table would carry it)
  ar: [['خرج', 'ḵaraja', 'verb', 'to go out\nto leave\nto emerge'], ['ثعلب', 'ṯaʿlab', 'noun', 'fox', 'الثعلب']],
};
const SOURCE = 'a test dictionary';
// A PERSIAN BOOK WITH FEW GLOSSES: seven chunks, three with a gloss -- one
// with every line, one with a meaning alone (3), one with a transliteration
// alone (4) -- and four with nothing: three plain (\chp) and one whose lines
// are all there and all empty (5), which is nothing written all the same
const SPARSE = '/books/persian/sparse-fa/reader/';
const SPARSE_TEX = String.raw`\chapopen{۱}

\parstart{۱.۱}{هیچ جایِ دُنیا}
\parnum{۱.۱}
\begin{frank}
\ch{}{هیچ جایِ دُنیا}{hič jā-ye donyā}{\dw{جا}{jā} place, \nobreak+\,ezafe \textit{-ye}}{nowhere in the world}
\chp{}{تَروُ خُشک را}
\chp{}{مِثلِ ایران با هَم}
\ch{}{نِمی سوزانَند}{}{}{do not burn}
\ch{}{پَس اَز}{pas az}{}{}
\ch{}{پَنج سال}{}{}{}
\chp{}{سالِ نو}
\end{frank}
`;
// AND TWO BOOKS OF TWO CHAPTERS, the second of which the reader fetches
// when it is wanted: one glossed chunk of four in each (sparse throughout),
// and one glossed from the front -- its first chapter all glossed, its second
// not at all, which is a book with few glosses however its first chapter
// looks.  A chunk not glossed is plain (\chp): nothing written
const ROWS = [['هیچ جایِ دُنیا', 'hič jā-ye donyā', String.raw`\dw{جا}{jā} place`, 'nowhere in the world'],
              ['تَروُ خُشک را', 'tar-o xošk rā', String.raw`\dw{تر}{tar} wet`, 'the wet and the dry'],
              ['مِثلِ ایران با هَم', 'mesl-e irān bā ham', String.raw`\dw{مثل}{mesl} like`, 'like in Iran, together'],
              ['پَس اَز پَنج سال', 'pas az panj sāl', String.raw`\dw{سال}{sāl} year`, 'after five years']];
const chapter = (num, glossed, paras = 1) => {
  let k = 0, t = `\\chapopen{${num}}\n\n`;
  for (let p = 1; p <= paras; p++) {
    t += `\\parstart{${num}.${p}}{هیچ جایِ دُنیا}\n\\parnum{${num}.${p}}\n\\begin{frank}\n`;
    for (const [fa, tr, voc, en] of ROWS)
      t += glossed.includes(k++) ? `\\ch{}{${fa}}{${tr}}{${voc}}{${en}}\n` : `\\chp{}{${fa}}\n`;
    t += '\\end{frank}\n\n';
  }
  return t;
};
const CHAPTERS = {'multi-fa': [chapter('۱', [0]), chapter('۲', [0])],
                  'front-fa': [chapter('۱', [0, 1, 2, 3]), chapter('۲', [], 3)]};
// A VIDEO ON YOUTUBE, no film of its own: its player is YouTube's, which the
// page asks for at https://www.youtube.com/iframe_api -- faked here (FAKE_YT),
// and made to say it is buffering
const YT_VIDEO = 'yTbUfFeR1ng';
const FAKE_YT = `window.YT = {Player: function (el, o) {
  var t = 0, self = this;
  window.__yt = {state: 2, calls: []};
  this.getCurrentTime = function () { return t; };
  this.getDuration = function () { return 8; };
  this.seekTo = function (s) { t = +s || 0; };
  this.playVideo = function () { window.__yt.calls.push('play'); window.__yt.state = 1; };
  this.pauseVideo = function () { window.__yt.calls.push('pause'); window.__yt.state = 2; };
  this.getPlayerState = function () { return window.__yt.state; };
  this.getPlaybackRate = function () { return 1; };
  this.setPlaybackRate = function () {};
  this.mute = function () {}; this.unMute = function () {};
  this.isMuted = function () { return false; };
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};
if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();`;
// the dictionary's entry in the cloud (the a0.3.1 panel), which a phone
// never shows any more
const PANEL_IN_CLOUD = () => !!document.querySelector('#cloud .dict.m-dict');
// the sheet, holding `head`'s entry, `pos` and the source
const SHEET = ([head, pos, src]) => {
  const d = document.querySelector('.m-dback .m-dsheet .m-dsbody');
  const t = d ? d.textContent.replace(/\s+/g, ' ') : '';
  return t.includes(head + ' ' + pos) && t.includes(src);
};

// ---- the toolbox: the mobile harness's tree, then served here with the
// dictionaries of this run's own and NOTHING ELSE that looks a word up:
// never this machine's dict/, corpus or models
const WORK = await Deno.makeTempDir({prefix: 'parseh-phone-clouds-'});
const built = await new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'build', WORK], cwd: root,
                                          stdout: 'piped', stderr: 'piped'}).output();
if (!built.success) throw Error(td.decode(built.stderr) || td.decode(built.stdout));
const MADE = JSON.parse(td.decode(built.stdout).trim().split('\n').pop());
const SERVE = String.raw`
import json, os, shutil, sys
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
# the harness's film, again, as a video every caption of which is glossed,
# and as a Persian one with few glosses
videos = tmp / 'root' / 'youtube' / 'videos'
src = videos / 'english' / sys.argv[4]
def video(folder, vid, title, lang, caps, film=True):
    dst = videos / folder / vid
    dst.mkdir(parents=True)
    # a film of this machine, or (no media.mp4) a video YouTube plays
    if film:
        os.symlink(str(src / 'media.mp4'), str(dst / 'media.mp4'))
    (dst / 'video.json').write_text(json.dumps(
        {'id': vid, 'url': '' if film else 'https://www.youtube.com/watch?v=' + vid, 'title': title,
         'title_native': title, 'channel': '', 'language': lang, 'gloss': 'en', 'duration': '0:08'}),
        encoding='utf-8')
    segs = []
    for s in caps:
        if s.get('plain'):
            segs.append({'start': s['start'], 'text': s['text'], 'plain': True})
            continue
        chunks = []
        for c in s['chunks']:
            # [text, meaning, vocabulary, transliteration]: a line nobody
            # wrote is not written at all
            ch = {'fa': c[0]}
            for k, f in ((1, 'en'), (2, 'voc'), (3, 'tr'), (4, 'kana')):
                if len(c) > k and c[k]: ch[f] = c[k]
            chunks.append(ch)
        segs.append({'start': s['start'], 'text': s['text'], 'chunks': chunks})
    (dst / 'annotations.json').write_text(json.dumps(
        {'video': vid, 'language': lang, 'segments': segs}, ensure_ascii=False), encoding='utf-8')
video('english', sys.argv[5], 'Four lines', 'en', json.loads(sys.argv[6]))
video('persian', sys.argv[7], 'Persian lines', 'fa', json.loads(sys.argv[8]))
video('japanese', sys.argv[12], 'Japanese lines', 'ja', json.loads(sys.argv[13]))
video('chinese', sys.argv[14], 'Chinese lines', 'zh', json.loads(sys.argv[15]))
video('english', sys.argv[11], 'On YouTube', 'en', json.loads(sys.argv[6]), film=False)
# Persian books with few glosses, the fixture edition's: one of one short
# chapter, and two of two chapters each -- the fixture's main.tex inputs
# ch1.tex, and is made to input as many as the book has
import mobile_harness
def book(slug, chapters):
    b = tmp / 'root' / 'books' / 'persian' / slug
    shutil.copytree(repo / 'tests/fixtures/books/persian/mini-fa', b,
                    ignore=shutil.ignore_patterns('reader', 'source', 'ch1.tex'))
    meta = json.loads((b / 'book.json').read_text(encoding='utf-8'))
    meta['slug'] = slug
    (b / 'book.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    main = (b / 'main.tex').read_text(encoding='utf-8')
    (b / 'main.tex').write_text(main.replace('\\input{ch1.tex}\n', ''.join(
        '\\input{ch%d.tex}\n' % (k + 1) for k in range(len(chapters)))), encoding='utf-8')
    for k, t in enumerate(chapters):
        (b / ('ch%d.tex' % (k + 1))).write_text(t, encoding='utf-8')
    mobile_harness.built_reader(b)
book('sparse-fa', [sys.argv[9]])
for slug, chapters in json.loads(sys.argv[10]).items():
    book(slug, chapters)
mobile_harness.serve_it(tmp, port)
`;
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
const port = freePort();
const log = [];
const hub = new Deno.Command(PY, {args: ['-c', SERVE, WORK, String(port), JSON.stringify(DICTS),
                                         MADE.video, VIDEO, JSON.stringify(CAPTIONS),
                                         FA_VIDEO, JSON.stringify(FA_CAPTIONS), SPARSE_TEX,
                                         JSON.stringify(CHAPTERS), YT_VIDEO,
                                         JA_VIDEO, JSON.stringify(JA_CAPTIONS), ZH_VIDEO, JSON.stringify(ZH_CAPTIONS)],
                                  cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
const B = `http://127.0.0.1:${port}`;
for (const t = Date.now();;) {
  try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
  if (Date.now() - t > 90000) throw Error('the hub did not start:\n' + log.join(''));
  await sleep(250);
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
const LAND = {viewport: {width: 844, height: 390}, isMobile: true, hasTouch: true};
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true};
const DESK = {viewport: {width: 1280, height: 800}};

async function pageFor(opts, mode, tag) {
  // a worker would answer the pages from its cache
  const ctx = await browser.newContext(Object.assign({serviceWorkers: 'block'}, opts));
  await ctx.addCookies([{name: 'parseh_mode', value: mode, url: B}]);
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(tag + ': ' + e.message));
  if (opts.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  return page;
}
const tap = async (page, sel) => { const l = page.locator(sel).first(); if (page.touch) await l.tap(); else await l.click(); };
async function until(page, fn, arg, what, timeout = 10000) {
  for (const t = Date.now();;) {
    const v = await page.evaluate(fn, arg);
    if (v) return v;
    if (Date.now() - t > timeout) {
      // what the cloud holds instead, which is the first thing to know
      const cloud = await page.evaluate(() => {
        const c = document.getElementById('cloud');
        return c ? (c.hidden ? '(hidden) ' : '') + c.textContent.replace(/\s+/g, ' ').trim().slice(0, 300) : '(no cloud)';
      });
      throw Error('FAIL: waited in vain for ' + what + ' -- the cloud says: ' + cloud);
    }
    await sleep(100);
  }
}
/* Drawn and on top: laid out, visible, and what the pointer finds at its
   middle -- never "not hidden", which a box with no CSS at all also is. */
const drawn = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  if (!el) return false;
  const r = el.getBoundingClientRect(), st = getComputedStyle(el);
  if (!r.width || !r.height || st.visibility !== 'visible' || st.display === 'none') return false;
  const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return !!at && el.contains(at);
}, sel);
const cloudText = page => page.evaluate(() => {
  const c = document.getElementById('cloud');
  return c && !c.hidden ? c.textContent.replace(/\s+/g, ' ').trim() : '';
});

/* The player, with the caption `n` (0-based) the one being said. */
async function videoAt(page, n) {
  await page.evaluate(n => document.querySelectorAll('#segs .seg')[n].querySelector('.lab').click(), n);
  await until(page, n => { const s = document.querySelector('#segs .seg.on-air'); return s && +s.dataset.i === n; },
              n, 'caption ' + n + ' on air');
  await page.evaluate(() => ParsehPlayer.pause());
  await sleep(400);                    // the subtitle follows every 250 ms
}
async function openVideo(page, id = VIDEO, n = 4) {
  await page.goto(B + `/youtube/v/${id}/`);
  await page.waitForFunction(n => !!window.ParsehMobilePlayer && document.querySelectorAll('#segs .seg').length === n, n);
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready(), null, {timeout: 20000});
}
// the lines over the picture, top to bottom: which caption each is, its
// text, its target text's size and colour, and where it stands
const lines = page => page.evaluate(() => [...document.querySelectorAll('.m-subs .seg')].map(s => {
  const fa = s.querySelector('.fa, .en-line'), w = s.querySelector('.w') || fa;
  const r = s.getBoundingClientRect();
  return {i: +s.dataset.i, text: fa.textContent.replace(/\s+/g, ' ').trim(),
          size: parseFloat(getComputedStyle(fa).fontSize), colour: getComputedStyle(w).color,
          near: s.classList.contains('m-subnear'), top: r.top, bottom: r.bottom};
}));

// ---- the sheet, and the rest of it, as the page draws it
const tapPhrase = async (page, i, j, cloud = true) => {
  const w = page.locator(`#segs .seg[data-i="${i}"] .w[data-j="${j}"]`);
  await w.evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(300);
  await w.tap();
  if (cloud) await page.waitForFunction(() => !document.getElementById('cloud').hidden);
  await sleep(250);
};
async function openReader(page, path, hover) {
  await page.goto(B + path);
  await page.waitForFunction(() => document.querySelector('[data-parseh-gear]'));
  await sleep(400);
  if (await page.$('.pf-bar')) await tap(page, '.pf-stay');
  if (await page.evaluate(() => document.body.classList.contains('hovermode')) !== hover)
    await gearSwitch(page, 'hover', hover);
}
async function tapWord(page, sel) {
  await page.locator(sel).first().evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(300);
  await tap(page, sel);
  await until(page, () => !document.getElementById('cloud').hidden || !!document.querySelector('.m-dback'), null,
              'a cloud or a sheet');
  await sleep(250);
}
// the dictionary switch, pressed as a finger presses it: in the gear's sheet on a page that has the gear (a book's
// reader and a video's page, since a0.5.0), under ⋯ on one that has none
async function switchDict(page) {
  if (await page.evaluate(() => document.documentElement.classList.contains('pg-reader'))) {
    await gearOpen(page, 'looking');
    await page.waitForSelector('.pg-panel [data-pg-row=dictmode]:not([hidden])');
    await gearSwitch(page, 'dictmode', true);
    assert(await page.evaluate(() => document.querySelector('#dictmode').classList.contains('on')), 'the dictionary switched on, in the gear');
  } else if (!(await page.$('.m-rmore')) && await page.$('button.pg-gear')) {
    await tap(page, 'button.pg-gear');
    await page.waitForFunction(() => ParsehGear.mounted().isOpen());
    await gearOpen(page, 'looking');                     // the sheet draws one theme at a time: the row's own
    await page.locator('.pg-panel [data-pg-row="dict"] .pg-switch').first().scrollIntoViewIfNeeded();
    await tap(page, '.pg-panel [data-pg-row="dict"] .pg-switch');
    assert(await page.evaluate(() => document.querySelector('#dictmode').classList.contains('on')), 'the dictionary switched on, in the gear');
    await tap(page, 'button.pg-gear');
    await page.waitForFunction(() => !ParsehGear.mounted().isOpen());
  } else {
    await tap(page, '.m-rmore');
    await page.waitForSelector('#dictmode', {state: 'visible'});
    await tap(page, '#dictmode');
    assert(await page.evaluate(() => document.querySelector('#dictmode').classList.contains('on')), 'the dictionary switched on, under ⋯');
    await tap(page, '.m-rmore');
  }
  await sleep(300);
}
// the cloud's gloss lines, [class, text]
const GLOSS_LINES = '.ctext, .kana, .tr, .voc, .en, .note, .unwritten';
const cloudLines = page => page.evaluate(sel => [...document.getElementById('cloud').children]
  .filter(c => c.matches(sel)).map(c => [c.className, c.textContent.replace(/\s+/g, ' ').trim()]), GLOSS_LINES);
// a book's row's own gloss, the same way
const rowLines = (page, n) => page.evaluate(n => [...document.querySelector(`main .p2 .row[data-c="${n}"] .gl`).children]
  .map(c => [c.className, c.textContent.replace(/\s+/g, ' ').trim()]), n);
// the cloud's markup, but for where its arrow was put and the phone's button
const cloudHTML = page => page.evaluate(() => document.getElementById('cloud').innerHTML
  .replace(/<div class="arrow"[^>]*><\/div>/, '').replace(/<button[^>]*class="mkdict"[^>]*>dictionary<\/button>/, ''));
// the cloud at the word it glosses: just above or just below it, across it
const besideWord = page => page.evaluate(() => {
  const c = document.getElementById('cloud').getBoundingClientRect(), w = document.querySelector('.hot').getBoundingClientRect();
  const above = c.bottom <= w.top + 1 && w.top - c.bottom < 24, below = c.top >= w.bottom - 1 && c.top - w.bottom < 24;
  return (above || below) && c.left < w.right && c.right > w.left;
});
const sheetFacts = page => page.evaluate(() => {
  const back = document.querySelector('.m-dback'), s = back && back.querySelector('.m-dsheet');
  if (!s) return null;
  const b = s.querySelector('.m-dsbody'), r = s.getBoundingClientRect(), st = getComputedStyle(b);
  const word = document.querySelector('.m-dword'), wr = word && word.getBoundingClientRect();
  // the top of the room a word can be read in: under whatever is pinned at
  // the top of the screen OVER THE WORD'S COLUMN (a video held sideways is
  // pinned beside the transcript, and hides nothing of it)
  let ceiling = 0;
  for (const sel of ['header', '#playerwrap']) {
    const e = document.querySelector(sel);
    if (!e || !wr) continue;
    const pos = getComputedStyle(e).position, er = e.getBoundingClientRect();
    if ((pos === 'fixed' || pos === 'sticky') && er.left < wr.right && er.right > wr.left && er.top < innerHeight / 2)
      ceiling = Math.max(ceiling, er.bottom);
  }
  // and what the eye finds at the word's middle, through the dimmed page:
  // the word itself, not the sheet nor anything pinned over it
  let seen = false;
  if (wr) {
    back.style.pointerEvents = 'none';
    const at = document.elementFromPoint(wr.left + wr.width / 2, wr.top + wr.height / 2);
    back.style.pointerEvents = '';
    seen = !!at && (at === word || word.contains(at));
  }
  return {top: r.top, bottom: r.bottom, h: r.height, w: r.width, H: innerHeight, W: innerWidth, ceiling, seen,
          bodyScroll: b.scrollHeight > b.clientHeight + 1, overflow: st.overflowY, over: st.overscrollBehaviorY,
          // every box in the sheet that scrolls
          scrollers: [...s.querySelectorAll('*')].filter(e => {
            const o = getComputedStyle(e).overflowY;
            return (o === 'auto' || o === 'scroll') && e.scrollHeight > e.clientHeight + 1;
          }).map(e => e.className),
          cloudHidden: document.getElementById('cloud').hidden, inCloud: !!document.querySelector('#cloud .dict'),
          role: s.getAttribute('role'), modal: s.getAttribute('aria-modal'), chrome: getComputedStyle(s).direction,
          gloss: [...s.querySelectorAll('.m-dsgl > *')].map(e => e.className),
          word: word ? {top: wr.top, bottom: wr.bottom, hot: word.classList.contains('hot'),
                        text: word.textContent.replace(/\s+/g, ' ').trim()} : null,
          // the sheet's own language, and that of its English
          lang: back.getAttribute('lang'), english: [s.querySelector('.dhead, .dnone, .dwait'), s.querySelector('.m-dsx')]
            .filter(Boolean).map(e => e.closest('[lang]').getAttribute('lang')),
          paused: window.ParsehPlayer ? ParsehPlayer.paused() : null};
});
// nothing of the sheet or of the cloud left: no sheet, no cloud, no word lit
// or marked, and no history entry of the sheet's
const CLOSED = {sheet: false, cloud: false, hot: false, mark: false, entry: false};
const nothingOpen = page => page.evaluate(() => ({
  sheet: !!document.querySelector('.m-dback'), cloud: !document.getElementById('cloud').hidden,
  hot: !!document.querySelector('.w.hot, .fa.hot'), mark: !!document.querySelector('.m-dword'),
  entry: !!(history.state && history.state.parsehDictSheet)}));
// THE SHEET AS TALL AS THE ENTRY, WHATEVER THE PAGE PINS (the owner,
// 2026-09-25): its height is what it holds -- its head and its body's whole
// content -- up to its most, 86% of the screen, and no cut of its own
const sheetSize = page => page.evaluate(() => {
  const s = document.querySelector('.m-dsheet');
  const content = s.querySelector('.m-dshead').offsetHeight + s.querySelector('.m-dsbody').scrollHeight;
  const h = s.getBoundingClientRect().height, most = parseFloat(getComputedStyle(s).maxHeight);
  return {h: Math.round(h), content, most: Math.round(most), H: innerHeight, inline: s.style.maxHeight,
          sized: Math.abs(h - Math.min(content, most)) <= 1.5};
});
// WHERE THE WORD IS WITH THE SHEET UP: scrolled into the room between what
// is pinned at the top and the sheet, where there is room for it ('clear');
// where there is none, left where it was, under the sheet ('covered') --
// never under the header or the video, never off the screen.  (`seen` looks
// through the dimmed page and the sheet both, whose pointer-events it turns
// off: it says nothing else is over the word; the sheet is asked by where it
// stands.)
const wordPlace = f => {
  if (!f || !f.word || !f.word.hot) return 'NOT MARKED';
  const h = f.word.bottom - f.word.top, room = f.top - f.ceiling >= h + 12;
  if (!f.seen || f.word.top < f.ceiling - 0.5 || f.word.bottom > f.H) return 'UNDER WHAT IS PINNED, OR OFF THE SCREEN';
  if (room) return f.word.bottom <= f.top + 0.5 ? 'clear' : 'NOT CLEAR, WITH ROOM FOR IT';
  return f.word.bottom > f.top ? 'covered' : 'NEITHER CLEAR NOR COVERED';
};
// the word the sheet is about, remembered before the sheet goes, and asked
// afterwards: on the screen, where the eye finds it, nothing over it
const markWord = page => page.evaluate(() => document.querySelector('.m-dword').setAttribute('data-was', ''));
const seenAgain = page => page.evaluate(() => {
  const w = document.querySelector('[data-was]'), r = w.getBoundingClientRect();
  const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  w.removeAttribute('data-was');
  return r.top >= 0 && r.bottom <= innerHeight && !!at && (at === w || w.contains(at));
});
// what the language's runs in the sheet are set in
const rtlFacts = page => page.evaluate(() => {
  const s = document.querySelector('.m-dsheet'), cs = e => getComputedStyle(e);
  const probe = document.createElement('span');
  probe.style.fontFamily = 'var(--tl-font)';
  document.body.appendChild(probe);
  const tl = cs(probe).fontFamily;
  probe.remove();
  const face = e => cs(e).fontFamily === tl;
  const t = s.querySelector('.m-dstitle');
  const hits = [...s.querySelectorAll('.dhit')].map(h => {
    const w = h.querySelector('.m-dhw'), p = h.querySelector('.dpos'), tr = h.querySelector('.m-dtl');
    return {head: w.textContent, lang: w.getAttribute('lang'), dir: cs(w).direction, bidi: cs(w).unicodeBidi, face: face(w),
            tl: tr ? tr.textContent : '', pos: p ? p.textContent.trim() : '',
            label: !!p && cs(p).display === 'inline-block' && cs(p).borderTopStyle === 'solid',
            senses: [...h.querySelectorAll('.dsense')].map(x => {
              const n = x.querySelector('.m-dsn');
              return (n ? n.textContent : '?') + ' ' + x.textContent.slice(n ? n.textContent.length : 0).trim();
            })};
  });
  // one sense to a line: each starts below the last, and below its hit's head
  const lines = [...s.querySelectorAll('.dhit')].map(h => [h.querySelector('.dhead2').getBoundingClientRect().bottom]
    .concat([...h.querySelectorAll('.dsense')].map(x => x.getBoundingClientRect().top)));
  const oneLine = lines.every(l => l.every((v, k) => !k || v >= l[k - 1] - 0.5 && (k === 1 || v > l[k - 1] + 4)));
  const words = [...s.querySelectorAll('.dwd')].map(w => [w.firstChild.textContent.trim(), w.getAttribute('lang'),
                                                          cs(w).direction, cs(w).unicodeBidi, face(w)]);
  return {title: {text: t.textContent, lang: t.getAttribute('lang'), dir: cs(t).direction, bidi: cs(t).unicodeBidi, face: face(t)},
          words, hits, oneLine, lines};
});
// a finger drawn down (or up, dy < 0) from a point of `sel`, `at` of its height
async function swipe(page, sel, dy, steps = 8, stepMs = 16, at = 0.3) {
  const p = await page.evaluate(([sel, at]) => {
    const r = document.querySelector(sel).getBoundingClientRect();
    return {x: r.left + r.width / 2, y: r.top + Math.max(12, r.height * at)};
  }, [sel, at]);
  const send = (type, touchPoints) => page.touch.send('Input.dispatchTouchEvent', {type, touchPoints});
  await send('touchStart', [{x: p.x, y: p.y}]);
  for (let k = 1; k <= steps; k++) {
    await send('touchMove', [{x: p.x, y: p.y + dy * k / steps}]);
    await sleep(stepMs);
  }
  await send('touchEnd', []);
}
// the underline each of `sels` wears: its line, style, thickness, whether it
// is in the theme's --faint, its --dim (the darker mark) or clear, its
// colour as drawn, and the text's own colour
const markFacts = (page, sels) => page.evaluate(sels => {
  const ink = v => {
    const probe = document.createElement('span');
    probe.style.color = v;
    document.body.appendChild(probe);
    const c = getComputedStyle(probe).color;
    probe.remove();
    return c;
  };
  const faint = ink('var(--faint)'), dim = ink('var(--dim)'), accent = ink('var(--accent)');
  return sels.map(sel => {
    const c = getComputedStyle(document.querySelector(sel));
    return {line: c.textDecorationLine, style: c.textDecorationStyle, thick: c.textDecorationThickness,
            isFaint: c.textDecorationColor === faint, isDim: c.textDecorationColor === dim,
            isAccent: c.textDecorationColor === accent,
            clear: c.textDecorationColor === 'rgba(0, 0, 0, 0)', ink: c.textDecorationColor, colour: c.color};
  });
}, sels);

try {
  // ================================================================ lines
  console.log('a video on the whole screen, held sideways: the lines around the one being said');
  const page = await pageFor(LAND, 'mobile', 'lines');
  await openVideo(page);
  await videoAt(page, 2);
  await tap(page, '.m-vfull');
  await page.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(500);
  // ---- a) the switch, beside the way out; off, one line
  const corner = await page.evaluate(() => {
    const r = s => { const e = document.querySelector(s).getBoundingClientRect(); return {l: e.left, r: e.right, t: e.top, b: e.bottom, w: e.width, h: e.height}; };
    return {ctx: r('#playerwrap .m-vctx'), out: r('#playerwrap .m-vout'),
            pressed: document.querySelector('.m-vctx').getAttribute('aria-pressed'), W: innerWidth};
  });
  assert(await drawn(page, '#playerwrap .m-vctx'), 'beside the way out, a switch for the lines around the one being said');
  assert(corner.ctx.w >= 48 && corner.ctx.h >= 48 && corner.ctx.r <= corner.out.l - 4 && Math.abs(corner.ctx.t - corner.out.t) < 1,
         'a finger\'s size, on the same line as ⛶ and clear of it: ' + JSON.stringify(corner));
  eq(corner.pressed, 'false', 'and it starts off');
  let got = await lines(page);
  eq(got.map(l => [l.i, l.near]), [[2, false]], 'off: the subtitle is the line being said alone, as it always was');
  const single = await page.evaluate(() => document.querySelector('.m-subs .m-subline').getBoundingClientRect().height);

  // ---- b) on: three lines in one cloud
  await tap(page, '.m-vctx');
  await sleep(350);
  eq(await page.evaluate(() => [document.querySelector('.m-vctx').getAttribute('aria-pressed'),
                                localStorage.getItem('vd_subctx')]), ['true', '1'], 'pressed: it says so, and it is remembered');
  got = await lines(page);
  eq(got.map(l => [l.i, l.text, l.near]),
     [[1, CAPTIONS[1].text, true], [2, CAPTIONS[2].text, false], [3, CAPTIONS[3].text, true]],
     'the caption before above the line being said, the caption after below it');
  assert(got[0].bottom <= got[1].top + 0.5 && got[1].bottom <= got[2].top + 0.5, 'one under another, in that order');
  const [prev, now, next] = got;
  assert(prev.size < now.size && next.size < now.size && prev.size > now.size * 0.7,
         `the two around it a little smaller (${prev.size}px and ${next.size}px against ${now.size}px)`);
  const rgb = c => c.match(/[\d.]+/g).map(Number);
  assert(rgb(now.colour).slice(0, 3).every(v => v === 255) &&
         [prev, next].every(l => { const [r, g, b, a = 1] = rgb(l.colour); return r === g && g === b && (r < 255 || a < 1) && (a === 1 ? r > 150 : a > .5); }),
         `and a little greyer (${prev.colour}, ${next.colour} against ${now.colour})`);
  const box = await page.evaluate(() => {
    const b = document.querySelector('.m-subs .m-subctx'), r = b.getBoundingClientRect();
    const kids = [...b.children].every(k => k.classList.contains('seg'));
    const out = document.querySelector('#playerwrap .m-vctx').getBoundingClientRect();
    return {n: b.children.length, kids, h: r.height, t: r.top, b: r.bottom, H: innerHeight,
            bg: getComputedStyle(b).backgroundColor, lineBg: getComputedStyle(b.querySelector('.m-subline')).backgroundColor,
            clear: r.top >= out.bottom || r.right <= out.left};
  });
  eq([box.n, box.kids], [3, true], 'the three in ONE cloud');
  assert(box.bg !== 'rgba(0, 0, 0, 0)' && box.lineBg === 'rgba(0, 0, 0, 0)',
         `drawn as one: the cloud has the dark ground (${box.bg}), the line inside it none of its own`);
  await shot(page, 'lines-around');
  assert(box.h > single * 1.8 && box.b <= box.H && box.clear,
         `the cloud larger for them (${Math.round(box.h)}px against ${Math.round(single)}px), on the screen and clear of the corner's buttons`);

  // ---- c) the lines around answer a tap with their own gloss
  // (each cloud put away before the next tap: open over the subtitles it
  // covers the line above the phrase it belongs to, as it would a finger)
  for (const [which, cap] of [['.m-subprev', CAPTIONS[1]], ['.m-subnext', CAPTIONS[3]]]) {
    await page.evaluate(() => ParsehPlayer.ungloss());
    await tap(page, `.m-subs ${which} .w`);
    await sleep(350);
    const said = await cloudText(page);
    assert(said.includes(cap.chunks[0][1]) &&
           await page.evaluate(w => !!document.querySelector(`.m-subs ${w} .w.hot`), which),
           `a tap on a phrase of the line ${which === '.m-subprev' ? 'before' : 'after'} opens ITS gloss: "${said.slice(0, 60)}"`);
  }
  await page.evaluate(() => ParsehPlayer.ungloss());
  await tap(page, '.m-subs .m-subline .w');
  await sleep(350);
  assert((await cloudText(page)).includes(CAPTIONS[2].chunks[0][1]), 'and the line being said still opens its own');

  // ---- d) the lines follow the video, and the choice is kept
  await page.evaluate(() => ParsehPlayer.ungloss());
  await videoAt(page, 3);
  got = await lines(page);
  eq(got.map(l => [l.i, l.near]), [[2, true], [3, false]], 'on the last caption: the line before it, and none after');
  await videoAt(page, 0);
  got = await lines(page);
  eq(got.map(l => [l.i, l.near]), [[0, false], [1, true]], 'on the first: none before, the line after it');
  eq(got[0].colour, 'rgb(255, 255, 255)',
     'a caption of the video\'s own framing (a plain line of English) is as white over the picture as any');
  await page.reload();
  await page.waitForFunction(() => !!window.ParsehMobilePlayer && document.querySelectorAll('#segs .seg').length === 4);
  await page.waitForFunction(() => window.ParsehPlayer && ParsehPlayer.ready(), null, {timeout: 20000});
  await videoAt(page, 1);
  await tap(page, '.m-vfull');
  await sleep(600);
  got = await lines(page);
  eq([await page.evaluate(() => document.querySelector('.m-vctx').getAttribute('aria-pressed')),
      got.map(l => l.i)], ['true', [0, 1, 2]], 'a page opened again comes back with the lines around, as it was left');
  eq(got[0].colour, 'rgba(255, 255, 255, 0.7)', 'and the plain line above it is as grey as a neighbour should be');
  // ---- f) the cloud over the subtitles has the dictionary too: in a sheet
  // over them, the video paused while it is up, and the back gesture closes
  // the sheet and nothing else
  await page.evaluate(() => ParsehPlayer.play());
  await sleep(300);
  await tap(page, '.m-subs .m-subline .w');
  await sleep(350);
  assert(await drawn(page, '#cloud .mkdict'), 'the gloss cloud over the subtitles has the dictionary beside "copy"');
  await tap(page, '#cloud .mkdict');
  await until(page, SHEET, ['market', 'noun', SOURCE], 'the dictionary\'s "market" in the sheet');
  await sleep(300);
  await shot(page, 'fullscreen-sheet');
  const over = await page.evaluate(() => {
    const sub = document.querySelector('.m-subs .m-subline').getBoundingClientRect();
    const at = document.elementFromPoint(sub.left + sub.width / 2, sub.top + sub.height / 2);
    const s = document.querySelector('.m-dsheet').getBoundingClientRect();
    return {covered: !!at && !!at.closest('.m-dback'), full: document.documentElement.classList.contains('m-vfullon'),
            cloud: !document.getElementById('cloud').hidden, paused: ParsehPlayer.paused(),
            h: s.height, H: innerHeight, inPanel: !!document.querySelector('#cloud .dict')};
  });
  eq(await page.evaluate(() => [...document.querySelectorAll('.nc-dock button')].filter(b => b.getClientRects().length).every(b => {
    const r = b.getBoundingClientRect(), at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !!at && !!at.closest('.m-dback');
  })), true, 'the dock\'s buttons lie under the dimmed page with the rest of it');
  eq([over.covered, over.full, over.cloud, over.paused, over.inPanel], [true, true, false, true, false],
     'pressed: the entry opens in a sheet over the subtitles, not in the cloud; the video waits, paused, on the whole screen');
  assert(over.h <= over.H * 0.86 + 1, `the sheet no taller than 86% of the screen (${Math.round(over.h)} of ${over.H})`);
  await page.goBack();
  await sleep(500);
  eq(await page.evaluate(() => [!!document.querySelector('.m-dback'), !document.getElementById('cloud').hidden,
                                 document.documentElement.classList.contains('m-vfullon'), ParsehPlayer.paused()]),
     [false, false, true, false],
     'the back gesture: the sheet and its cloud gone, the video still on the whole screen, and playing again');
  await page.evaluate(() => ParsehPlayer.pause());
  await page.goBack();
  await sleep(400);
  eq(await page.evaluate(() => document.documentElement.classList.contains('m-vfullon')), false,
     'and a second back gesture is the one that leaves the whole screen');
  // THE BROWSER'S OWN WAY OUT, with the sheet up.  In a tab, ⛶ asks the
  // browser for its full screen, and Android's Chrome spends the back gesture
  // on leaving it -- the page hears no going back, only the full screen
  // ending (here: exitFullscreen, the same event).  One gesture, one thing:
  // the sheet goes, the video stays over the page, and the next back leaves it
  await videoAt(page, 1);
  // the entry the page stands on before ⛶ (not null: a state outlives the
  // reload above), which the going back must come home to
  const home = await page.evaluate(() => JSON.stringify(history.state));
  await tap(page, '.m-vfull');
  await page.waitForFunction(() => document.documentElement.classList.contains('m-vfullon') && !!document.fullscreenElement);
  await sleep(400);
  await page.evaluate(() => ParsehPlayer.play());
  await sleep(200);
  await tap(page, '.m-subs .m-subline .w');
  await sleep(350);
  await tap(page, '#cloud .mkdict');
  await until(page, SHEET, ['market', 'noun', SOURCE], 'the sheet over the browser\'s full screen');
  const whole = () => page.evaluate(() => ({screen: document.fullscreenElement ? document.fullscreenElement.tagName : null,
    over: document.documentElement.classList.contains('m-vfullon'), sheet: !!document.querySelector('.m-dback'),
    cloud: !document.getElementById('cloud').hidden, entry: history.state ? Object.keys(history.state)[0] : null,
    paused: ParsehPlayer.paused()}));
  eq(await whole(), {screen: 'HTML', over: true, sheet: true, cloud: false, entry: 'parsehDictSheet', paused: true},
     'the browser\'s own full screen, the sheet up over it, the video paused');
  await page.evaluate(() => document.exitFullscreen());
  await sleep(900);
  eq(await whole(), {screen: null, over: true, sheet: false, cloud: false, entry: 'parsehVideoFull', paused: false},
     'the browser leaves its full screen: the sheet and its cloud go, and nothing else -- the video still over the page, playing again');
  await page.evaluate(() => ParsehPlayer.pause());
  const at = await page.evaluate(() => location.href);
  await page.goBack();
  await sleep(500);
  eq(await page.evaluate(() => [document.documentElement.classList.contains('m-vfullon'), location.href, JSON.stringify(history.state)]),
     [false, at, home], 'and the next back gesture leaves the whole screen, on the entry the page stood on before: no dead going back left over');
  await videoAt(page, 1);
  await tap(page, '.m-vfull');
  await page.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(400);
  await page.evaluate(() => ParsehPlayer.ungloss());
  await tap(page, '.m-vctx');
  await sleep(350);
  eq([(await lines(page)).map(l => [l.i, l.near]), await page.evaluate(() => localStorage.getItem('vd_subctx'))],
     [[[1, false]], '0'], 'pressed again: the one line again, and that is remembered too');
  await page.context().close();

  // a mouse (a tablet with a trackpad, a desktop in the mobile mode)
  console.log('the same, with a mouse');
  const mouse = await pageFor(DESK, 'mobile', 'lines, mouse');
  await openVideo(mouse);
  await videoAt(mouse, 2);
  await mouse.click('.m-vfull');
  await mouse.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(400);
  await mouse.click('.m-vctx');
  await sleep(350);
  await mouse.hover('.m-subs .m-subnext .w');
  await sleep(300);
  assert((await cloudText(mouse)).includes(CAPTIONS[3].chunks[0][1]), 'a mouse at rest on a phrase of the line after opens its gloss');
  // away first: that cloud stands over the lines above the phrase it is for
  await mouse.mouse.move(640, 40);
  await sleep(500);
  eq(await cloudText(mouse), '', 'the mouse gone from the phrase (and not into its cloud), the gloss goes');
  await mouse.hover('.m-subs .m-subprev .w');
  await sleep(300);
  assert((await cloudText(mouse)).includes(CAPTIONS[1].chunks[0][1]), 'and on one of the line before, that one\'s');
  await mouse.click('.m-subs .m-subprev .w');
  await sleep(250);
  assert((await cloudText(mouse)).includes(CAPTIONS[1].chunks[0][1]), 'a click on the phrase it rests on leaves its gloss open');
  await mouse.mouse.move(640, 40);
  await sleep(500);
  eq(await cloudText(mouse), '', 'and the mouse gone from it, the gloss goes');
  await mouse.context().close();

  // ================================================================ the sheet
  // ---- e) a video's phrase, glossed: the cloud as it was, and the sheet
  console.log('the dictionary\'s sheet, on a phone: a video');
  const vid = await pageFor(PHONE, 'mobile', 'video sheet');
  await openVideo(vid);
  // ---- l) the transcript's seams have no + on a phone: it writes a note into
  // the video, and a mobile page never writes (counted first, so the check
  // cannot pass for want of a seam)
  eq(await vid.evaluate(() => { const p = [...document.querySelectorAll('#segs .gap .plus')];
                                return [p.length > 0, p.some(e => e.getClientRects().length > 0)]; }),
     [true, false], 'the transcript\'s seams on a phone: no + to write a note with');
  await tapPhrase(vid, 1, 0);
  const row = await vid.evaluate(() => {
    const c = document.querySelector('#cloud .mkcopy').getBoundingClientRect();
    const d = document.querySelector('#cloud .mkdict').getBoundingClientRect();
    return {same: Math.abs(c.top - d.top) < 2, after: d.left >= c.right - 1 && d.left - c.right < 24,
            label: document.querySelector('#cloud .mkdict').textContent};
  });
  assert(await drawn(vid, '#cloud .mkdict') && row.same && row.after,
         'a glossed phrase\'s cloud: beside "copy", a button: ' + JSON.stringify(row));
  // a finger's size, both (docs/mobile.md: every target 48px) -- drawn for a
  // mouse they were 25px tall -- and no colour marks, which would write the
  // phrase's colour into the video (the mobile mode writes nothing)
  const btns = await vid.evaluate(() => ['.mkcopy', '.mkdict'].map(b => Math.round(document.querySelector('#cloud ' + b).getBoundingClientRect().height)));
  assert(btns.every(h => h >= 48), 'its "copy" and "dictionary" a finger\'s size: ' + JSON.stringify(btns));
  eq(await vid.evaluate(() => [...document.querySelectorAll('#cloud .colrow, #cloud .cstat')].some(e => e.getClientRects().length > 0)),
     false, 'and no colour marks in it: they write the video, and a phone writes nothing');
  eq(await cloudLines(vid), [['voc', CAPTIONS[1].chunks[0][2]], ['en', CAPTIONS[1].chunks[0][1]]],
     'the cloud is the gloss, as it always was: its vocabulary and its meaning');
  eq([row.label, await vid.evaluate(PANEL_IN_CLOUD), await vid.evaluate(() => !!document.querySelector('.m-dback'))],
     ['dictionary', false, false], 'the button says what it opens, and nothing of the dictionary is open by itself');
  assert(await besideWord(vid), 'the cloud stands at the phrase it glosses');
  await tap(vid, '#segs .w.hot');
  await sleep(250);
  eq(await vid.evaluate(() => document.getElementById('cloud').hidden), true, 'the phrase tapped again closes it, as ever');
  // playing, as a phone plays: the cloud does not stop the video, the sheet does
  await vid.evaluate(() => ParsehPlayer.play());
  await sleep(300);
  await tapPhrase(vid, 1, 0);
  eq(await vid.evaluate(() => ParsehPlayer.paused()), false, 'a cloud opened while the video plays leaves it playing');
  await tap(vid, '#cloud .mkdict');
  await until(vid, SHEET, ['market', 'noun', SOURCE], 'the dictionary\'s "market" in the video\'s sheet');
  await sleep(350);
  await shot(vid, 'video-en-sheet');
  let f = await sheetFacts(vid);
  eq([f.cloudHidden, f.inCloud, f.role, f.modal, f.gloss, f.paused],
     [true, false, 'dialog', 'true', ['voc', 'en'], true],
     'pressed: the entry in a SHEET, the cloud not shown, the gloss over the entry, the video paused');
  assert(f.bottom >= f.H - 1 && f.w >= f.W - 1, `the sheet stands on the foot of the screen, the whole width (${JSON.stringify([f.top, f.bottom, f.w])})`);
  let size = await sheetSize(vid);
  assert(size.sized && size.inline === '' && size.h < size.most - 1 && !f.bodyScroll && JSON.stringify(f.scrollers) === '[]',
         `as tall as the entry, a short one: nothing in it scrolling (${JSON.stringify(size)})`);
  eq([f.overflow, f.over], ['auto', 'contain'], 'its body the one scroller, keeping its scrolling to itself');
  eq(wordPlace(f), 'clear',
     `room enough between the pinned video and a short sheet: the phrase scrolled into it, marked: ${JSON.stringify([f.word, f.top, f.ceiling])}`);
  eq([f.lang, f.english], ['en', ['en', 'en']], 'the sheet says its words are English, as the cloud they came from does');
  // THE CLOUD DRAWN AGAIN UNDER THE SHEET: the page redraws its cloud for
  // what has just arrived or been switched (a translation model found late,
  // a switch of the header's) -- under the sheet it must stay hidden, not
  // stand behind the dimmed page with a second lookup in it
  await vid.evaluate(() => { const d = document.getElementById('dictmode'); d.click(); d.click(); });
  await sleep(200);
  eq(await vid.evaluate(() => [document.getElementById('cloud').hidden, !!document.querySelector('.m-dsheet')]), [true, true],
     'the page drawing its cloud again while the sheet is up: the cloud stays hidden under it');
  await tap(vid, '.m-dstitle');
  await sleep(300);
  f = await sheetFacts(vid);
  assert(f && f.word && f.word.hot && f.paused, 'a tap inside the sheet leaves it, the phrase and the pause as they were');
  await vid.touchscreen.tap(20, 20);
  await sleep(600);
  eq(await nothingOpen(vid), CLOSED, 'a tap beside the sheet: the sheet and its cloud gone, the phrase unmarked, nothing open');
  eq(await vid.evaluate(() => ParsehPlayer.paused()), false, 'and the video the sheet paused goes on');
  await vid.evaluate(() => ParsehPlayer.pause());
  await tapPhrase(vid, 1, 0);
  await tap(vid, '#cloud .mkdict');
  await until(vid, SHEET, ['market', 'noun', SOURCE], 'the sheet again');
  await sleep(300);
  const x = await vid.evaluate(() => { const r = document.querySelector('.m-dsx').getBoundingClientRect(); return [r.width, r.height]; });
  assert(x[0] >= 48 && x[1] >= 48 && await drawn(vid, '.m-dsx'), '✕ is a finger\'s size: ' + JSON.stringify(x));
  // ---- k) the toast still over it
  await vid.evaluate(() => Parseh.toast('a toast over the sheet'));
  await sleep(400);
  assert(await vid.evaluate(() => {
    // the toast lets taps through (pointer-events:none); asked to take them
    // for a moment, what the page finds at its middle is what is on top there
    const t = document.getElementById('parseh-toast'), r = t && t.getBoundingClientRect();
    if (!t) return false;
    t.style.pointerEvents = 'auto';
    const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    t.style.pointerEvents = '';
    return !!at && t.contains(at);
  }), 'a toast raised while the sheet is up is drawn over it');
  await tap(vid, '.m-dsx');
  await sleep(500);
  eq(await nothingOpen(vid), CLOSED, '✕: nothing open');
  eq(await vid.evaluate(() => ParsehPlayer.paused()), true, 'and a video that was not playing stays paused');
  await vid.context().close();

  // ---- e) held sideways, not on the whole screen: the video is pinned down
  // the left of the screen, BESIDE the transcript, and hides nothing of it.
  // The sheet is as tall as the entry all the same; the phrase is scrolled
  // into the room under the header where there is room above the sheet, and
  // otherwise left where it was, under it -- and is there again, where it
  // was, when the sheet goes.  The last caption's second phrase has nothing
  // written: its cloud says so, and has the dictionary's button too
  console.log('the dictionary\'s sheet: a video held sideways');
  const sv = await pageFor(LAND, 'mobile', 'video sideways');
  await openVideo(sv);
  for (const [i, j] of [[1, 0], [3, 1]]) {
    await tapPhrase(sv, i, j);
    await tap(sv, '#cloud .mkdict');
    await until(sv, () => !!document.querySelector('.m-dsheet .ddict .dw'), null, 'the entry, sideways');
    await sleep(450);
    f = await sheetFacts(sv);
    size = await sheetSize(sv);
    const pinned = await sv.evaluate(() => getComputedStyle(document.getElementById('playerwrap')).position);
    const place = wordPlace(f);
    assert(pinned === 'fixed' && size.sized && size.inline === '' && (place === 'clear' || place === 'covered'),
           `sideways, the video pinned beside the transcript: the sheet as tall as the entry (${JSON.stringify(size)}), ` +
           `the phrase ${i}:${j} ${place}: ` + JSON.stringify([f.word, f.top, f.ceiling]));
    if (i === 1) await shot(sv, 'video-sideways-sheet');
    await markWord(sv);
    await sv.goBack();
    await sleep(500);
    eq(await nothingOpen(sv), CLOSED, 'and the back gesture closes it');
    assert(await seenAgain(sv), `and the phrase ${i}:${j} is in sight again, where it was`);
  }
  await sv.context().close();

  // ---- e) a YouTube video BUFFERING as the sheet opens -- as one does on a
  // phone over a slow link -- is on its way to playing: paused with the rest,
  // and on its way again when the sheet goes
  console.log('the dictionary\'s sheet: a YouTube video, buffering');
  const yt = await pageFor(PHONE, 'mobile', 'youtube');
  await yt.context().route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, r =>
    r.request().url() === 'https://www.youtube.com/iframe_api'
      ? r.fulfill({contentType: 'text/javascript', body: FAKE_YT}) : r.abort());
  await openVideo(yt, YT_VIDEO);
  await tapPhrase(yt, 1, 0);
  await yt.evaluate(() => { window.__yt.state = 3; window.__yt.calls = []; });
  await tap(yt, '#cloud .mkdict');
  await yt.waitForSelector('.m-dsheet');
  await sleep(300);
  eq(await yt.evaluate(() => [window.__yt.calls.slice(), window.__yt.state]), [['pause'], 2],
     'buffering (YouTube\'s 3) as the sheet opens: paused, as a playing one is');
  await tap(yt, '.m-dsx');
  await sleep(700);
  eq(await yt.evaluate(() => [window.__yt.calls.slice(), window.__yt.state]), [['pause', 'play'], 1],
     'and the sheet closed, it goes on');
  await yt.context().close();

  // ---- g) right to left: Persian, a book
  console.log('the sheet, right to left: a Persian book');
  const book = await pageFor(PHONE, 'mobile', 'book sheet');
  await openReader(book, '/books/persian/mini-fa/reader/', true);
  eq(await book.evaluate(() => [document.documentElement.classList.contains('m-sparse'), document.querySelectorAll('.m-gl').length]),
     [false, 0], 'a book glossed all but through: not sparse, no mark on anything');
  eq(await book.evaluate(() => getComputedStyle(document.querySelector('main .p2 .row .fa')).textDecorationLine), 'none',
     'its rows\' text as it always was');
  await tapWord(book, 'main .p1 .w');
  const faCloud = await cloudHTML(book);
  eq(await cloudLines(book), await rowLines(book, 0), 'the cloud of a glossed chunk: the row\'s own gloss, line for line');
  eq([await book.evaluate(PANEL_IN_CLOUD), await book.evaluate(() => !!document.querySelector('.m-dback'))], [false, false],
     'and no dictionary, until asked');
  assert(await besideWord(book), 'the cloud stands at the word it glosses');
  const bb = await book.evaluate(() => ['.mkcopy', '.mkdict'].map(b => Math.round(document.querySelector('#cloud ' + b).getBoundingClientRect().height)));
  assert(bb.every(h => h >= 48), 'its "copy" and "dictionary" a finger\'s size: ' + JSON.stringify(bb));
  await tap(book, '#cloud .mkdict');
  await until(book, SHEET, ['جا jā', 'noun', SOURCE], 'the dictionary\'s جا in the book\'s sheet');
  await sleep(350);
  await shot(book, 'book-fa-sheet-light');
  f = await sheetFacts(book);
  eq([f.cloudHidden, f.inCloud, f.gloss, f.chrome], [true, false, ['tr', 'voc', 'en'], 'ltr'],
     'the sheet, the cloud not shown, the chunk\'s gloss over the entry, the sheet itself set left to right');
  eq([f.lang, f.english, await book.evaluate(() => document.documentElement.lang)], ['en', ['en', 'en'], 'fa'],
     'in a Persian book the sheet\'s own words say they are English (read out and broken as English), as the cloud\'s do');
  size = await sheetSize(book);
  assert(size.sized && size.inline === '', `the sheet as tall as the entry, up to 86% of the screen: ${JSON.stringify(size)}`);
  eq(wordPlace(f), 'clear', `room under the header for the word: scrolled there, above the sheet, and marked: ${JSON.stringify([f.word, f.top, f.ceiling])}`);
  let rtl = await rtlFacts(book);
  eq(rtl.title, {text: 'هیچ جایِ دُنیا', lang: 'fa', dir: 'rtl', bidi: 'isolate', face: true},
     'its head: the chunk, in Persian\'s face, right to left, isolated');
  eq(rtl.words, [['هیچ', 'fa', 'rtl', 'isolate', true], ['جایِ', 'fa', 'rtl', 'isolate', true], ['دُنیا', 'fa', 'rtl', 'isolate', true]],
     'each word of it, over its entries, in the same face and direction');
  eq(rtl.hits.map(h => [h.head, h.lang, h.dir, h.bidi, h.face, h.tl]),
     [['هیچ', 'fa', 'rtl', 'isolate', true, ' hič'], ['جا', 'fa', 'rtl', 'isolate', true, ' jā'], ['دنیا', 'fa', 'rtl', 'isolate', true, ' donyā']],
     'each headword says it is Persian and is set as Persian, its transliteration after it in the page\'s own type');
  eq(rtl.hits.map(h => h.senses),
     [['1. no, none', '2. nothing'], ['1. place', '2. room, space', '3. seat'], ['1. world', '2. the earth']],
     'the senses numbered, one to a line');
  eq(rtl.hits.map(h => [h.pos, h.label]), [['det', true], ['noun', true], ['noun', true]],
     'each hit\'s part of speech a label beside its headword');
  assert(rtl.oneLine, 'and each sense on a line of its own: ' + JSON.stringify(rtl.lines));
  await book.evaluate(() => Parseh.theme.set('dark'));
  await sleep(300);
  await shot(book, 'book-fa-sheet-dark');
  await book.evaluate(() => Parseh.theme.set('light'));
  // a short, slow pull springs back
  await swipe(book, '.m-dshead', 40, 10, 30);
  await sleep(300);
  eq(await book.evaluate(() => [!!document.querySelector('.m-dsheet'), document.querySelector('.m-dsheet').style.transform]),
     [true, ''], 'a short pull on its head, let go: it springs back');
  await swipe(book, '.m-dshead', 320);
  await sleep(500);
  eq(await nothingOpen(book), CLOSED, 'a swipe down its head: the sheet and the cloud gone, nothing open');
  // THE ANSWER LANDS AFTER A TAP IN THE SHEET.  The book's own lookup puts
  // its answer in only while its cloud is still open on the chunk, and a tap
  // on the sheet is followed by the mouse events a phone makes up for it --
  // the pointer "leaving" the cloud, which closes it: held back a moment, the
  // answer must still land, and the word stay marked
  await book.route('**/__lookup', async r => { await sleep(1500); await r.continue(); });
  await tapWord(book, 'main .p1 .w[data-c="1"]');
  await tap(book, '#cloud .mkdict');
  await book.waitForSelector('.m-dsheet .dwait');
  await tap(book, '.m-dstitle');
  await sleep(150);
  await tap(book, '.m-dsgl');
  await until(book, () => !!document.querySelector('.m-dsheet .ddict .dw'), null, 'the answer, after the taps in the sheet');
  eq(await book.evaluate(() => [!!document.querySelector('.m-dsheet .dwait'), !!document.querySelector('.w.hot.m-dword')]),
     [false, true], 'looked up, then tapped in twice before the answer came: the answer lands all the same, the word still marked');
  await book.touchscreen.tap(20, 20);
  await sleep(500);
  eq(await nothingOpen(book), CLOSED, 'and a tap beside it: nothing open');
  // THE CLOUD OPENED AGAIN UNDER THE SHEET: the reader draws its cloud again,
  // on the same chunk, when something arrives that it would show -- the
  // translation model, found a moment after the page loaded, is the usual
  // one.  That drawing must leave the cloud hidden, or the next tap in the
  // sheet counts as a tap outside the cloud, closes it, and the answer the
  // sheet waits for is thrown away
  // (a chunk not yet looked up, so its answer is on its way, held back)
  await tapWord(book, 'main .p1 .w[data-c="3"]');
  await tap(book, '#cloud .mkdict');
  await book.waitForSelector('.m-dsheet .dwait');
  await book.evaluate(() => { if (cloudFor) { const sp = cloudFor; cloudFor = null; openCloud(sp); } });
  eq(await book.evaluate(() => [document.getElementById('cloud').hidden, cloudC]), [true, 3],
     'the reader opens its cloud again under the sheet (what it does when the model arrives): it stays hidden, on its chunk');
  await tap(book, '.m-dstitle');
  await until(book, () => !!document.querySelector('.m-dsheet .ddict .dw'), null, 'the answer, after the cloud was opened again');
  eq(await book.evaluate(() => !!document.querySelector('.m-dsheet .dwait')), false, 'and tapped in: the answer lands all the same');
  await book.unroute('**/__lookup');
  // A SHEET OVER A SHEET takes over the first one's going back: one entry,
  // and one back gesture closes it, on the page
  const h0 = await book.evaluate(() => history.length);
  await book.evaluate(() => { const b = document.createElement('div'); b.className = 'dict m-dict';
    Parseh.dictSheet({box: b, lang: {code: 'fa', dir: 'rtl'}, title: 'دوم'}); });
  await sleep(400);
  eq(await book.evaluate(() => [history.length, !!(history.state && history.state.parsehDictSheet), document.querySelectorAll('.m-dsheet').length]),
     [h0, true, 1], 'a second sheet over the first: one sheet, on the first one\'s entry');
  const was = await book.evaluate(() => location.href);
  await book.goBack();
  await sleep(500);
  eq([await nothingOpen(book), await book.evaluate(() => location.href)], [CLOSED, was], 'and one back gesture closes it, on the page');
  // THE KEYBOARD (a desktop in the mobile mode): the sheet is a dialog that
  // holds the page, so Tab and Shift+Tab go round its own buttons and links
  await tapWord(book, 'main .p1 .w');
  await book.focus('#cloud .mkdict');
  await book.keyboard.press('Enter');
  await until(book, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet, from the keyboard');
  const inside = [];
  for (const k of ['Tab', 'Tab', 'Tab', 'Shift+Tab', 'Shift+Tab', 'Shift+Tab']) {
    await book.keyboard.press(k);
    inside.push(await book.evaluate(() => !!document.activeElement.closest('.m-dsheet')));
  }
  eq(inside, [true, true, true, true, true, true], 'Tab and Shift+Tab stay inside the sheet');
  await book.keyboard.press('Escape');
  await sleep(400);
  eq(await nothingOpen(book), CLOSED, 'and Escape: nothing open');
  // the back gesture
  await tapWord(book, 'main .p1 .w');
  await tap(book, '#cloud .mkdict');
  await until(book, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet again');
  await sleep(300);
  const here = await book.evaluate(() => location.href);
  await book.goBack();
  await sleep(500);
  eq([await nothingOpen(book), await book.evaluate(() => location.href)], [CLOSED, here],
     'the back gesture: nothing open, and the reader still where it was');
  // THE HEADER HELD WHERE IT IS while the sheet is up: a word low on the
  // screen is scrolled up into the room under the header, and the header
  // going away with that scroll (as it does when the page is read down)
  // would change the room the word was given
  await book.evaluate(() => scrollTo(0, 0));
  await sleep(400);
  const low = await book.evaluate(() => {
    const low = [...document.querySelectorAll('main .p1 .w')].filter(e => { const r = e.getBoundingClientRect(); return r.top > 420 && r.bottom < 760; });
    low[low.length - 1].setAttribute('data-low', '');
    return !document.body.classList.contains('barhidden');
  });
  await tap(book, 'main .p1 .w[data-low]');
  await until(book, () => !document.getElementById('cloud').hidden, null, 'the cloud of a word low on the screen');
  await tap(book, '#cloud .mkdict');
  await until(book, () => !!document.querySelector('.m-dsheet .ddict .dw'), null, 'its entry');
  await sleep(500);
  f = await sheetFacts(book);
  eq([low, await book.evaluate(() => [scrollY > 56, document.body.classList.contains('barhidden')]), wordPlace(f)],
     [true, [true, false], 'clear'], 'a word low on the screen: the page scrolled down for it, the header held where it was, the word under it and seen');
  await book.goBack();
  await sleep(500);
  await book.evaluate(() => document.querySelector('[data-low]').removeAttribute('data-low'));
  // a swipe down the body, scrolled to its top
  await tapWord(book, 'main .p1 .w');
  await tap(book, '#cloud .mkdict');
  await until(book, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet again');
  await sleep(300);
  await swipe(book, '.m-dsbody', 320);
  await sleep(500);
  eq(await nothingOpen(book), CLOSED, 'a swipe down its body, from its top: nothing open');
  // and closing leaves the cloud as a glossed chunk always had it
  await tapWord(book, 'main .p1 .w');
  eq(await cloudHTML(book), faCloud, 'the same chunk tapped again: the very cloud it had before');
  await book.evaluate(() => document.getElementById('cloud').hidden || closeCloud());

  // ---- g) Arabic
  console.log('the sheet, right to left: an Arabic book');
  await openReader(book, '/books/arabic/mini-ar/reader/', true);
  await tapWord(book, 'main .p1 .w');
  await tap(book, '#cloud .mkdict');
  await until(book, SHEET, ['ثعلب ṯaʿlab', 'noun', SOURCE], 'the dictionary\'s ثعلب in the sheet');
  await sleep(350);
  await shot(book, 'book-ar-sheet');
  rtl = await rtlFacts(book);
  eq([rtl.title.lang, rtl.title.dir, rtl.title.bidi, rtl.title.face], ['ar', 'rtl', 'isolate', true],
     'Arabic: the head in Arabic\'s face, right to left, isolated');
  eq(rtl.hits.map(h => [h.head, h.lang, h.dir, h.face, h.senses]),
     [['خرج', 'ar', 'rtl', true, ['1. to go out', '2. to leave', '3. to emerge']], ['ثعلب', 'ar', 'rtl', true, ['1. fox']]],
     'its headwords Arabic, their senses numbered');
  await book.keyboard.press('Escape');
  await sleep(500);
  eq(await nothingOpen(book), CLOSED, 'Escape: nothing open');

  // ---- g) a language with nothing to look it up with
  await openReader(book, '/books/hindi/mini-hi/reader/', true);
  await tapWord(book, 'main .p1 .w');
  await tap(book, '#cloud .mkdict');
  await book.waitForSelector('.m-dsheet');
  await sleep(250);
  const none = await book.evaluate(() => {
    const d = document.querySelector('.m-dsheet .dict.m-dict');
    const a = d && d.querySelector('a[href]');
    return [d ? d.textContent.replace(/\s+/g, ' ').trim().slice(0, 40) : '', a ? a.getAttribute('href') : ''];
  });
  eq(none, ['Nothing is set up to look Hindi words up', '/settings/reading-help/'],
     'Hindi, with no dictionary here: the sheet says nothing is set up, and where to set one up: Settings, Reading help');
  await book.touchscreen.tap(20, 20);
  await sleep(500);
  eq(await nothingOpen(book), CLOSED, 'and a tap beside it closes it');
  await book.context().close();

  // ---- g) the lines that stand at the foot over everything give way to it:
  // "where the other device stopped" sat on the sheet's lower half and took
  // its taps.  The toolbox here knows of no other device's place, so the
  // page asks nothing by itself; the question is put as prefs.js puts it
  console.log('the sheet, and the question of where the other device stopped');
  const pf = await pageFor(PHONE, 'mobile', 'place question');
  await pf.route('**/__prefs', r => r.request().method() === 'GET'
    ? r.fulfill({contentType: 'application/json', body: '{"settings":{},"places":{}}'}) : r.continue());
  await openReader(pf, '/books/persian/mini-fa/reader/', true);
  const REC = {by: 'Linux computer', label: '۱ · ۱.۲', at: Date.now() / 1000 - 7200, i: 1};
  await tapWord(pf, 'main .p1 .w');
  await tap(pf, '#cloud .mkdict');
  await until(pf, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet');
  await pf.evaluate(r => ParsehPrefs.ask(r), REC);
  await sleep(400);
  eq(await pf.evaluate(() => !!document.querySelector('.pf-bar')), false,
     'where the other device stopped, asked while the sheet is up: the question waits');
  await pf.touchscreen.tap(20, 20);
  await until(pf, () => !!document.querySelector('.pf-bar'), null, 'the question, once the sheet has gone', 4000);
  eq(await nothingOpen(pf), CLOSED, 'the sheet gone, it is asked');
  await tapWord(pf, 'main .p1 .w');
  await tap(pf, '#cloud .mkdict');
  await until(pf, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet, the question showing');
  await sleep(300);
  eq(await pf.evaluate(() => {
    const s = document.querySelector('.m-dsheet').getBoundingClientRect(), bar = document.querySelector('.pf-bar');
    return [!!bar, bar.getClientRects().length > 0,
            [0.6, 0.75, 0.9].map(k => !!document.elementFromPoint(s.left + s.width / 2, s.top + s.height * k).closest('.m-dsheet'))];
  }), [true, false, [true, true, true]],
     'the question showing, the sheet opened: the question gives way, and the sheet\'s lower half is the sheet\'s');
  await pf.touchscreen.tap(20, 20);
  await sleep(500);
  eq(await pf.evaluate(() => document.querySelector('.pf-bar').getClientRects().length > 0), true, 'and it is there again when the sheet goes');
  await pf.context().close();

  // ---- g) a book's narration waits while the sheet is up, as a video does:
  // its dock is under the dimmed page, and a narration going on scrolls the
  // word away from above the sheet
  console.log('the sheet, and a book\'s narration');
  const nb = await pageFor(PHONE, 'mobile', 'narration');
  await openReader(nb, '/books/english/mini-en/reader/', true);
  await tap(nb, '.nc-dock .nc-play');
  await until(nb, () => !document.querySelector('audio').paused, null, 'the narration playing');
  await tapWord(nb, 'main .p1 .w');
  await tap(nb, '#cloud .mkdict');
  await nb.waitForSelector('.m-dsheet');
  await sleep(300);
  const heard = () => nb.evaluate(() => [document.querySelector('audio').paused, document.querySelector('audio').currentTime]);
  const n1 = await heard();
  await sleep(500);
  const n2 = await heard();
  eq([n1[0], n2[0], n2[1] === n1[1]], [true, true, true], 'the narration waits, paused, while the sheet is up');
  await nb.touchscreen.tap(20, 20);
  await until(nb, () => !document.querySelector('audio').paused, null, 'the narration going on');
  eq(await nothingOpen(nb), CLOSED, 'and the sheet closed, it goes on');
  await tap(nb, '.nc-dock .nc-play');
  await sleep(300);
  await tapWord(nb, 'main .p1 .w');
  await tap(nb, '#cloud .mkdict');
  await nb.waitForSelector('.m-dsheet');
  await nb.goBack();
  await sleep(600);
  eq(await nb.evaluate(() => document.querySelector('audio').paused), true, 'a narration that was paused stays paused');
  await nb.context().close();

  // ---- g) sideways, a long entry: 86% of the screen, scrolled inside
  console.log('the sheet, sideways');
  const side = await pageFor(LAND, 'mobile', 'book sheet sideways');
  await openReader(side, '/books/persian/mini-fa/reader/', true);
  await tapWord(side, 'main .p1 .w');
  await tap(side, '#cloud .mkdict');
  await until(side, SHEET, ['جا jā', 'noun', SOURCE], 'the sheet, sideways');
  await sleep(400);
  await shot(side, 'book-fa-sheet-sideways');
  f = await sheetFacts(side);
  size = await sheetSize(side);
  assert(size.sized && size.h >= size.most - 1.5 && size.inline === '' && f.bodyScroll && JSON.stringify(f.scrollers) === '["m-dsbody"]',
         `a long entry: the sheet at its most, 86% of the screen, never cut short for the word (${JSON.stringify(size)}) -- and its body alone scrolls`);
  eq(wordPlace(f), 'covered',
     `no room for the word between the header and the sheet: left where it was, under the sheet, marked: ${JSON.stringify([f.word, f.top, f.ceiling])}`);
  const y0 = await side.evaluate(() => [scrollY, document.querySelector('.m-dsbody').scrollTop]);
  await swipe(side, '.m-dsbody', -160, 8, 60, 0.75);
  await sleep(500);
  const y1 = await side.evaluate(() => [scrollY, document.querySelector('.m-dsbody').scrollTop]);
  assert(y1[1] > y0[1] + 40 && y1[0] === y0[0] && await side.evaluate(() => !!document.querySelector('.m-dsheet')),
         `a finger scrolls the entry and not the page under it (page ${y0[0]} -> ${y1[0]}, entry ${y0[1]} -> ${y1[1]})`);
  // a pull down while the entry is scrolled scrolls it back; it does not close it
  await swipe(side, '.m-dsbody', 60, 8, 40, 0.5);
  await sleep(400);
  assert(await side.evaluate(() => !!document.querySelector('.m-dsheet')), 'a pull down inside a scrolled entry scrolls it, and the sheet stays');
  await markWord(side);
  await side.goBack();
  await sleep(500);
  eq(await nothingOpen(side), CLOSED, 'the back gesture: nothing open');
  assert(await seenAgain(side), 'and the word the sheet covered is in sight again, where it was');
  await side.context().close();

  // ---- g) and a Persian video
  console.log('the sheet, right to left: a Persian video');
  const fav = await pageFor(PHONE, 'mobile', 'persian video');
  await openVideo(fav, FA_VIDEO, 4);
  await tapPhrase(fav, 0, 0);
  eq(await cloudLines(fav), [['tr', FA_CAPTIONS[0].chunks[0][3]], ['voc', FA_CAPTIONS[0].chunks[0][2]], ['en', FA_CAPTIONS[0].chunks[0][1]]],
     'a glossed Persian phrase: its cloud, the gloss as it was');
  await tap(fav, '#cloud .mkdict');
  await until(fav, SHEET, ['جا jā', 'noun', SOURCE], 'the dictionary\'s جا in the video\'s sheet');
  await sleep(350);
  // upright, the video pinned over the transcript under the header, a third
  // of the screen: THE SHEET AS TALL AS THE ENTRY all the same -- this one's
  // most, 86% -- and not cut short to leave the phrase a room (the owner,
  // 2026-09-25); the phrase stays where it was, under it, marked
  size = await sheetSize(fav);
  assert(size.sized && size.h >= size.most - 1.5 && size.inline === '',
         `upright, under the pinned video: the sheet at 86% of the screen, as tall as its long entry allows (${JSON.stringify(size)})`);
  f = await sheetFacts(fav);
  eq(wordPlace(f), 'covered',
     `no room between the pinned video and the sheet: the phrase left where it was, under the sheet, marked: ${JSON.stringify([f.word, f.top, f.ceiling])}`);
  await shot(fav, 'video-fa-sheet-light');
  rtl = await rtlFacts(fav);
  eq([rtl.title.text, rtl.title.lang, rtl.title.dir, rtl.title.bidi, rtl.title.face], ['هیچ جایِ دُنیا', 'fa', 'rtl', 'isolate', true],
     'the video\'s sheet: its head in Persian\'s face, right to left, isolated');
  eq(rtl.hits.map(h => [h.head, h.lang, h.dir, h.face, h.senses.length]),
     [['هیچ', 'fa', 'rtl', true, 2], ['جا', 'fa', 'rtl', true, 3], ['دنیا', 'fa', 'rtl', true, 2]],
     'the same entry, drawn by the video\'s own page, the same way');
  await fav.evaluate(() => Parseh.theme.set('dark'));
  await sleep(300);
  await shot(fav, 'video-fa-sheet-dark');
  await fav.evaluate(() => Parseh.theme.set('light'));
  await markWord(fav);
  await swipe(fav, '.m-dshead', 320);
  await sleep(500);
  eq(await nothingOpen(fav), CLOSED, 'a swipe down: nothing open');
  assert(await seenAgain(fav), 'and the phrase the sheet covered is in sight again, where it was');
  await shot(fav, 'video-fa-sheet-closed');

  // ---- i) a phrase with nothing written, with the dictionary on: the sheet at once
  console.log('a chunk nobody has glossed, the dictionary on');
  await switchDict(fav);
  await tapPhrase(fav, 1, 0, false);
  await until(fav, SHEET, ['مثل mesl', 'noun', SOURCE], 'the dictionary\'s مثل, straight away');
  await sleep(350);
  await shot(fav, 'video-fa-unglossed');
  f = await sheetFacts(fav);
  eq([f.cloudHidden, f.inCloud, f.gloss, f.word && f.word.text], [true, false, ['unwritten'], FA_CAPTIONS[1].chunks[0][0]],
     'a tap on a phrase with nothing written: the sheet, with no cloud, "nothing glossed yet" over the entry');
  await fav.goBack();
  await sleep(500);
  eq(await nothingOpen(fav), CLOSED, 'the back gesture: nothing open');
  await tapPhrase(fav, 0, 0);
  eq([await fav.evaluate(() => !!document.querySelector('.m-dback')), (await cloudLines(fav)).map(l => l[0])], [false, ['tr', 'voc', 'en']],
     'and a glossed phrase, the dictionary on, still opens its cloud and nothing else');
  await tapPhrase(fav, 0, 0, false);
  // A GLOSS IS ANY LINE OF ONE (the owner, 2026-09-25): a phrase with a
  // meaning alone, or a transliteration alone, has no vocabulary line -- the
  // rule the dictionary's panel goes by -- and opens its cloud all the same,
  // the dictionary a press away, no entry poured into it and no sheet
  for (const [i, j, lines] of [[1, 1, [['en', 'do they burn']]], [2, 0, [['tr', 'pas az']]]]) {
    await tapPhrase(fav, i, j);
    await sleep(300);
    eq([await cloudLines(fav), await drawn(fav, '#cloud .mkdict'),
        await fav.evaluate(() => [!!document.querySelector('#cloud .dict'), !!document.querySelector('.m-dback')])],
       [lines, true, [false, false]],
       `a phrase with ${lines[0][0] === 'en' ? 'a meaning' : 'a transliteration'} alone, the dictionary on: its cloud, ` +
       'its one line, the dictionary\'s button, no entry in it and no sheet');
    await tapPhrase(fav, i, j, false);
  }
  await tapPhrase(fav, 2, 0);
  await tap(fav, '#cloud .mkdict');
  await fav.waitForSelector('.m-dsheet .ddict');
  await sleep(300);
  f = await sheetFacts(fav);
  eq([f.cloudHidden, f.gloss], [true, ['tr']], 'pressed: the sheet, the transliteration over the entry');
  await fav.goBack();
  await sleep(500);
  eq(await nothingOpen(fav), CLOSED, 'the back gesture: nothing open');
  await fav.context().close();

  const sp = await pageFor(PHONE, 'mobile', 'sparse book');
  await openReader(sp, SPARSE, false);
  await switchDict(sp);
  await tapWord(sp, 'main .p2 .row[data-c="2"] .fa');
  await until(sp, SHEET, ['مثل mesl', 'noun', SOURCE], 'the dictionary\'s مثل, straight away, in the book');
  await sleep(350);
  await shot(sp, 'book-fa-unglossed');
  f = await sheetFacts(sp);
  eq([f.cloudHidden, f.inCloud, f.gloss], [true, false, []],
     'a book: a tap on a chunk with nothing written opens the sheet, with no cloud, nothing to carry over the entry');
  eq(wordPlace(f), 'clear', 'the chunk above the sheet, marked');
  await sp.touchscreen.tap(20, 20);
  await sleep(500);
  eq(await nothingOpen(sp), CLOSED, 'a tap beside it: nothing open');
  // a chunk whose lines are all written and all empty is nothing written too
  await tapWord(sp, 'main .p2 .row[data-c="5"] .fa');
  await until(sp, SHEET, ['سال sāl', 'noun', SOURCE], 'the dictionary\'s سال, straight away');
  eq(await sp.evaluate(() => document.getElementById('cloud').hidden), true,
     'a chunk with every line there and every one empty: the sheet at once, as for a plain one');
  await sp.goBack();
  await sleep(500);
  // A GLOSS IS ANY LINE OF ONE: a meaning alone (3), a transliteration alone
  // (4) -- the reader pours the dictionary's panel into the cloud of either,
  // having no vocabulary line, and on a phone it comes out again: the cloud
  // is the gloss, with the dictionary a press away
  for (const [n, lines] of [[3, [['en', 'do not burn']]], [4, [['tr', 'pas az']]]]) {
    await tapWord(sp, `main .p2 .row[data-c="${n}"] .fa`);
    await sleep(300);
    eq([await cloudLines(sp), await drawn(sp, '#cloud .mkdict'),
        await sp.evaluate(() => [!!document.querySelector('#cloud .dict'), !!document.querySelector('.m-dback')])],
       [lines, true, [false, false]],
       `a book: a chunk with ${lines[0][0] === 'en' ? 'a meaning' : 'a transliteration'} alone, the dictionary on: its cloud, ` +
       'its one line, the dictionary\'s button, no entry in it and no sheet');
    assert(await besideWord(sp), 'the cloud at the word, placed again without the entry it lost');
    await sp.evaluate(() => closeCloud());
  }
  await tapWord(sp, 'main .p2 .row[data-c="3"] .fa');
  await tap(sp, '#cloud .mkdict');
  await sp.waitForSelector('.m-dsheet .ddict');
  await sleep(300);
  f = await sheetFacts(sp);
  eq([f.cloudHidden, f.gloss], [true, ['en']], 'pressed: the sheet, the meaning over the entry');
  await sp.goBack();
  await sleep(500);
  eq(await nothingOpen(sp), CLOSED, 'the back gesture: nothing open');
  await sp.context().close();

  // THE ENTRY ALREADY TO HAND.  Tapped a second time the chunk's entry is
  // known, and the reader draws it into the cloud at once -- and cuts it to
  // the room beside the word, as a cloud does.  Taken into the sheet, that
  // cut went with it: the sheet a peek of the entry, the rest spilling out of
  // its box.  Sideways, where the cloud fits on neither side of the word
  const side2 = await pageFor(LAND, 'mobile', 'sparse book sideways');
  await openReader(side2, SPARSE, false);
  await switchDict(side2);
  for (const k of [1, 2]) {
    await tapWord(side2, 'main .p2 .row[data-c="2"] .fa');
    await until(side2, () => !!document.querySelector('.m-dsheet .ddict .dw'), null, 'the entry in the sheet');
    await sleep(350);
    const cut = await side2.evaluate(() => {
      const s = document.querySelector('.m-dsheet'), box = s.querySelector('.dict');
      const content = s.querySelector('.m-dshead').offsetHeight + s.querySelector('.m-dsbody').scrollHeight;
      const h = s.getBoundingClientRect().height, most = parseFloat(getComputedStyle(s).maxHeight);
      return {box: box.style.maxHeight, spills: box.scrollHeight > box.clientHeight + 1,
              sized: Math.abs(h - Math.min(content, most)) <= 1.5, h: Math.round(h), content, most};
    });
    eq([cut.box, cut.spills, cut.sized], ['', false, true],
       `${k === 1 ? 'looked up' : 'the entry already known'}: the entry whole in the sheet, the sheet as tall as it up to its most: ${JSON.stringify(cut)}`);
    if (k === 2) await shot(side2, 'book-fa-unglossed-known-sideways');
    await side2.goBack();
    await sleep(500);
  }
  await side2.context().close();

  const mouseBook = await pageFor(DESK, 'mobile', 'sparse book, mouse');
  await openReader(mouseBook, SPARSE, true);
  await switchDict(mouseBook);
  await mouseBook.locator('main .p1 .w[data-c="2"]').hover();
  await until(mouseBook, () => !!document.querySelector('#cloud:not([hidden]) .dict .dw'), null, 'the entry in the cloud');
  eq(await mouseBook.evaluate(() => !!document.querySelector('.m-dback')), false,
     'a mouse at rest on such a chunk keeps the cloud, the entry in it: no sheet springs up at a hover');
  await mouseBook.context().close();

  // ---- j) few glosses: the mark
  console.log('a book and a video with few glosses');
  // (drawn at twice the phone's pixels, so the pictures show a 1px line)
  const mk = await pageFor(Object.assign({deviceScaleFactor: 2}, PHONE), 'mobile', 'sparse marks');
  await openReader(mk, SPARSE, false);
  eq(await mk.evaluate(() => [document.documentElement.classList.contains('m-sparse'),
                              [...document.querySelectorAll('.m-gl')].map(e => e.closest('.pass').classList[1] + ':' + e.dataset.c).sort()]),
     [true, ['p1:0', 'p1:3', 'p1:4', 'p2:0', 'p2:3', 'p2:4', 'p3:0', 'p3:3', 'p3:4', 'p4:0', 'p4:3', 'p4:4']],
     'three chunks of seven with a gloss -- every line, a meaning alone, a transliteration alone: the book is sparse, ' +
     'and the three are marked in every pass they are drawn in');
  // WHERE NOTHING IS UNDERLINED (hover mode off): the glossed chunks gain the
  // faint dotted line, the others have none
  const ROWSEL = n => `main .p2 .row[data-c="${n}"] .fa`, WSEL = n => `main .p1 .w[data-c="${n}"]`;
  for (const theme of ['light', 'dark', 'sepia']) {
    await mk.evaluate(t => Parseh.theme.set(t), theme);
    await sleep(200);
    const m = await markFacts(mk, [ROWSEL(0), ROWSEL(2), WSEL(0), WSEL(2), ROWSEL(3), ROWSEL(4)]);
    eq([m[0].line, m[0].style, m[0].thick, m[0].isFaint, m[1].line, m[2].line, m[2].isFaint, m[3].line,
        m[4].line, m[4].isFaint, m[5].line, m[5].isFaint],
       ['underline', 'dotted', '1px', true, 'none', 'underline', true, 'none', 'underline', true, 'underline', true],
       `${theme}: a glossed chunk's text underlined, dotted, 1px, in the theme's --faint -- a meaning alone or a ` +
       'transliteration alone as much as every line; the others not');
    eq([m[0].colour === m[1].colour, m[2].colour === m[3].colour], [true, true], `${theme}: and its colour as the others'`);
    if (theme !== 'sepia') await shot(mk, `book-sparse-${theme}`);
  }
  // WHERE EVERY WORD ALREADY WEARS THE LINE (hover mode: the first pass): the
  // others keep theirs as it was, and the glossed ones wear it darker, in
  // --dim, the theme's muted ink -- a second mark, not the first taken away
  await mk.evaluate(() => Parseh.theme.set('light'));
  await gearSwitch(mk, 'hover', true);
  await sleep(200);
  for (const theme of ['light', 'dark', 'sepia']) {
    await mk.evaluate(t => Parseh.theme.set(t), theme);
    await sleep(200);
    const hv = await markFacts(mk, [WSEL(0), WSEL(2), WSEL(3), WSEL(4), WSEL(6)]);
    eq(hv.map(m => [m.line, m.style, m.thick, m.isDim, m.isFaint]),
       [['underline', 'dotted', '1px', true, false], ['underline', 'dotted', '1px', false, true],
        ['underline', 'dotted', '1px', true, false], ['underline', 'dotted', '1px', true, false],
        ['underline', 'dotted', '1px', false, true]],
       `${theme}, hover mode, where every word wears the dotted line: the unglossed keep it in --faint, the glossed wear it darker, in --dim`);
    eq(hv.every(m => m.colour === hv[0].colour), true, `${theme}: the words' own colour the same, glossed or not`);
    if (theme !== 'sepia') await shot(mk, `book-sparse-hover-${theme}`);
  }
  await mk.evaluate(() => Parseh.theme.set('light'));
  // a glossed word a finger is on lights its line in the accent, as every
  // word in hover mode does
  await tapWord(mk, WSEL(0));
  eq((await markFacts(mk, [WSEL(0)]))[0].isAccent, true, 'hover mode: the glossed word tapped lights its line in the accent, as any word does');
  await mk.evaluate(() => closeCloud());
  await mk.evaluate(() => { localStorage.setItem('bk_hover', '0'); });

  // A BOOK OF TWO CHAPTERS, its second fetched when it is wanted (held back
  // here, so it surely arrives after the page has counted): counted over the
  // whole book, and the chapter that arrives later marked as it arrives --
  // its rows, and in hover mode its words, which there keep their underline
  for (const hover of [false, true]) {
    const pg = await pageFor(PHONE, 'mobile', 'two chapters');
    await pg.route('**/reader/ch-1.html', async r => { await sleep(2500); await r.continue(); });
    await openReader(pg, '/books/persian/multi-fa/reader/', hover);
    eq(await pg.evaluate(() => [document.documentElement.classList.contains('m-sparse'), !!document.querySelector('section.chapter[data-part]')]),
       [true, true], `two chapters, one chunk of four glossed in each${hover ? ', hover mode' : ''}: sparse, the second chapter not here yet`);
    await pg.evaluate(() => document.querySelector('section.chapter[data-part]').scrollIntoView());
    await until(pg, () => !document.querySelector('section.chapter[data-part]'), null, 'the second chapter');
    await sleep(250);
    eq(await pg.evaluate(() => [...document.querySelectorAll('section.chapter[data-ch="1"] .m-gl')]
        .map(e => e.closest('.pass').classList[1] + ':' + e.dataset.c)), ['p1:4', 'p2:4', 'p3:4', 'p4:4'],
       'the second chapter arrived: its glossed chunk marked in every pass, as it came');
    const m = await markFacts(pg, ['main .p2 .row[data-c="4"] .fa', 'main .p2 .row[data-c="5"] .fa',
                                   'main .p1 .w[data-c="4"]', 'main .p1 .w[data-c="5"]']);
    eq([m[0].line, m[0].isFaint, m[1].line, m[2].line, hover ? m[2].isDim : m[2].isFaint, hover ? m[3].isFaint : m[3].line],
       ['underline', true, 'none', 'underline', true, hover ? true : 'none'],
       'its glossed chunk underlined, faint, in its row, and in its words ' +
       (hover ? 'darker, in --dim, the others keeping their faint line' : 'faint too; the others not'));
    if (hover) {
      await pg.evaluate(() => document.querySelector('section.chapter[data-ch="1"]').scrollIntoView({block: 'start'}));
      await sleep(300);
      await shot(pg, 'book-two-chapters-hover');
    }
    await pg.context().close();
  }
  const front = await pageFor(PHONE, 'mobile', 'glossed from the front');
  await front.route('**/reader/ch-1.html', async r => { await sleep(2500); await r.continue(); });
  await openReader(front, '/books/persian/front-fa/reader/', false);
  eq(await front.evaluate(() => [document.documentElement.classList.contains('m-sparse'), !!document.querySelector('section.chapter[data-part]'),
                                 new Set([...document.querySelectorAll('.m-gl')].map(e => e.dataset.c)).size]),
     [true, true, 4], 'a book glossed from the front -- its first chapter all glossed, its second not at all: sparse from the start, ' +
                      'counted over the whole book, the first chapter\'s four marked');
  await front.evaluate(() => document.querySelector('section.chapter[data-part]').scrollIntoView());
  await until(front, () => !document.querySelector('section.chapter[data-part]'), null, 'the second chapter');
  await sleep(250);
  eq(await front.evaluate(() => [document.querySelectorAll('section.chapter[data-ch="1"] .pass .row[data-c]').length,
                                 document.querySelectorAll('section.chapter[data-ch="1"] .m-gl').length]),
     [12, 0], 'and its second chapter, when it comes: twelve chunks, none glossed, none marked');
  await front.context().close();

  await openVideo(mk, FA_VIDEO, 4);
  const vm = await mk.evaluate(() => [document.documentElement.classList.contains('m-sparse'),
                                      [...document.querySelectorAll('#segs .w.m-gl')].map(w => w.closest('.seg').dataset.i + ':' + w.dataset.j)]);
  eq(vm, [true, ['0:0', '1:1', '2:0']],
     'three phrases of eight with a gloss -- every line, a meaning alone, a transliteration alone: the video is sparse, the three marked');
  // EVERY PHRASE OF A VIDEO ALREADY WEARS THE LINE: the unglossed keep it as
  // it was, and the glossed wear it darker, in --dim
  const PH = (i, j) => `#segs .seg[data-i="${i}"] .w[data-j="${j}"]`;
  for (const theme of ['light', 'dark', 'sepia']) {
    await mk.evaluate(t => Parseh.theme.set(t), theme);
    await sleep(200);
    // each caption's glossed phrase, then the one beside it with nothing
    const t = await markFacts(mk, [PH(0, 0), PH(0, 1), PH(1, 1), PH(1, 0), PH(2, 0), PH(2, 1)]);
    const GL = ['underline', 'dotted', '1px', true, false], NO = ['underline', 'dotted', '1px', false, true];
    eq(t.map(m => [m.line, m.style, m.thick, m.isDim, m.isFaint]), [GL, NO, GL, NO, GL, NO],
       `${theme}, in the transcript: every phrase keeps its faint dotted line, and the glossed ones wear it darker, in --dim`);
    // (a caption's words take the colour of where the video is -- said,
    // near, past -- so a phrase is held to the one beside it)
    eq([0, 2, 4].every(k => t[k].colour === t[k + 1].colour), true,
       `${theme}: each phrase's own colour that of the one beside it, glossed or not`);
    if (theme !== 'sepia') await shot(mk, `video-fa-sparse-${theme}`);
  }
  await mk.evaluate(() => Parseh.theme.set('light'));
  await openVideo(mk);
  eq(await mk.evaluate(() => [document.documentElement.classList.contains('m-sparse'), document.querySelectorAll('.m-gl').length]),
     [false, 0], 'three phrases of six glossed -- half, one of them with a meaning alone -- is not few: no mark');
  let t = await markFacts(mk, ['#segs .seg[data-i="1"] .w[data-j="0"]', '#segs .seg[data-i="1"] .w[data-j="1"]']);
  eq([t[0].isFaint, t[1].isFaint], [true, true], 'every phrase wears its dotted line, as it always did');
  await mk.context().close();

  const fsv = await pageFor(Object.assign({deviceScaleFactor: 2}, LAND), 'mobile', 'sparse subtitles');
  await openVideo(fsv, FA_VIDEO, 4);
  await videoAt(fsv, 0);
  await tap(fsv, '.m-vfull');
  await fsv.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(600);
  // over the black of the picture "darker" is the wrong way round: there the
  // glossed phrase's line is a near white, the others' as it always was
  t = await markFacts(fsv, ['.m-subs .m-subline .w[data-j="0"]', '.m-subs .m-subline .w[data-j="1"]']);
  eq([await fsv.evaluate(() => !!document.querySelector('.m-subs .m-subline .w.m-gl')), t[0].line, t[0].ink, t[1].line, t[1].isFaint],
     [true, 'underline', 'rgba(255, 255, 255, 0.82)', 'underline', true],
     'the subtitles over the whole screen: every phrase keeps its line, the glossed one\'s near white against the black');
  await shot(fsv, 'video-fa-fullscreen-sparse');
  await fsv.context().close();

  // ---- m) THE SIZE OF THE WORDS (L12; the owner, 2026-09-25 and -28): the
  // transcript keeps its size, the subtitles over a video on the whole
  // screen get their own, Aa in the corner opens the same panel there.  Driven
  // on a right-to-left video and on two CJK ones, in the three themes,
  // upright (the transcript's size, from the header) and sideways (the
  // subtitles', from the whole screen)
  console.log('the size of the words: the transcript\'s, and the subtitles\' on the whole screen');
  const setTheme = (p, t) => p.evaluate(t => Parseh.theme.set(t), t);
  const slideTo = (p, id, v) => p.evaluate(([id, v]) => {
    const i = document.getElementById(id);
    i.value = v;
    i.dispatchEvent(new Event('input', {bubbles: true}));
  }, [id, v]);
  const panelNow = p => p.evaluate(() => {
    const el = document.querySelector('.parseh-typo'), r = el.getBoundingClientRect();
    const hd = el.querySelector('.thead').getBoundingClientRect();
    const at = document.elementFromPoint(hd.left + hd.width / 2, hd.top + hd.height / 2);
    const probe = document.createElement('span');
    probe.style.background = 'var(--card)';
    document.body.appendChild(probe);
    const card = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return {up: !el.hidden, onTop: !!at && el.contains(at), t: r.top, b: r.bottom, l: r.left, r: r.right,
            W: innerWidth, H: innerHeight, bg: getComputedStyle(el).backgroundColor, card,
            header: document.querySelector('header').getBoundingClientRect().height,
            rows: [...el.querySelectorAll('.trow')].filter(t => getComputedStyle(t).display !== 'none')
                    .map(t => t.querySelector('input').id.replace('st-', ''))};
  });
  const CJK_ROWS = {fa: [], ja: ['cjkSpace', 'kanaContrast', 'kanaSize'], zh: ['cjkSpace']};
  // the header's Aa opens the GEAR at Text (a0.5.0), whose sliders are the Aa panel's own fields: what is read
  // is the sheet and its Text group, and what is moved is the gear's slider for a field
  const gearSlideTo = (p, row, v) => p.evaluate(([row, v]) => {
    const i = document.querySelector(`.pg-panel[data-pg-page=video] [data-pg-row="${row}"] input[type=range]`);
    i.value = v;
    i.dispatchEvent(new Event('input', {bubbles: true}));
  }, [row, v]);
  const gearNow = p => p.evaluate(() => {
    const el = document.querySelector('.pg-panel[data-pg-page=video]'), r = el.getBoundingClientRect();
    const hd = el.querySelector('.pg-head').getBoundingClientRect();
    const at = document.elementFromPoint(hd.left + hd.width / 2, hd.top + hd.height / 2);
    const text = el.querySelector('[data-pg-group=text]');
    return {up: !el.hidden, onTop: !!at && el.contains(at), t: r.top, b: r.bottom, l: r.left, r: r.right, W: innerWidth, H: innerHeight,
            header: document.querySelector('header').getBoundingClientRect().height,
            rows: [...text.querySelectorAll('[data-pg-row]')].filter(t => !t.hidden && t.getClientRects().length).map(t => t.dataset.pgRow)};
  });
  for (const [lang, vid, dir] of [['fa', FA_VIDEO, 'rtl'], ['ja', JA_VIDEO, 'ltr'], ['zh', ZH_VIDEO, 'ltr']]) {
    // sideways, on the whole screen
    const p = await pageFor(LAND, 'mobile', 'size ' + lang);
    await openVideo(p, vid, 4);
    await videoAt(p, 1);
    await tap(p, '.m-vfull');
    await p.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
    await sleep(500);
    const paper = [];
    for (const theme of ['light', 'dark', 'sepia']) {
      await setTheme(p, theme);
      await sleep(150);
      await tap(p, '.m-vtxt');
      await sleep(250);
      await slideTo(p, 'st-sub', 34);
      await sleep(150);
      const f = await panelNow(p);
      const got = await lines(p);
      const fa = await p.evaluate(() => { const e = document.querySelector('.m-subs .m-subline .fa'), r = e.getBoundingClientRect();
        return {dir: getComputedStyle(e).direction, l: r.left, r: r.right, t: r.top, b: r.bottom, W: innerWidth, H: innerHeight}; });
      paper.push(f.bg);
      eq([f.up, f.onTop, f.rows], [true, true, ['sub', 'gl']],
         `${lang}, ${theme}: Aa opens the panel over the picture, on top, with the subtitles' size and the glosses'`);
      assert(f.bg === f.card && f.t >= 0 && f.b <= f.H && f.r <= f.W, `${lang}, ${theme}: in the theme's own card, on the screen`);
      eq([got.length, got[0].size, fa.dir], [1, 34, dir],
         `${lang}, ${theme}: the subtitle is 34px, in the language's own direction`);
      assert(fa.l >= 0 && fa.r <= fa.W && fa.b <= fa.H, `${lang}, ${theme}: and lies on the screen`);
      await shot(p, `size-${lang}-${theme}-full`);
      await tap(p, '.m-vtxt');
      await sleep(150);
    }
    assert(new Set(paper).size === 3, `${lang}: the three themes draw the panel in three colours (${paper.join(' | ')})`);
    // the lines around it at the largest size: in proportion, on the screen, clear of the corner
    await videoAt(p, 2);
    await tap(p, '.m-vtxt');
    await slideTo(p, 'st-sub', 48);
    await tap(p, '.m-vctx');
    await sleep(350);
    got = await lines(p);
    const [pv, nw, nx] = got;
    assert(got.length === 3 && nw.size === 48 && Math.abs(pv.size - 39.36) < 0.3 && Math.abs(nx.size - 39.36) < 0.3,
           `${lang}: at 48px, the slider's largest, the lines around are .82 of it, as at 20 (${got.map(l => l.size).join(', ')}px)`);
    const room = await p.evaluate(() => {
      const c = document.querySelector('.m-subs .m-subctx').getBoundingClientRect();
      const t = document.querySelector('.m-vtxt').getBoundingClientRect();
      return {t: c.top, b: c.bottom, r: c.right, H: innerHeight, clear: c.top >= t.bottom || c.right <= t.left};
    });
    assert(room.b <= room.H && room.clear, `${lang}: on the screen and clear of the buttons in the corner ${JSON.stringify(room)}`);
    await shot(p, `size-${lang}-ctx-48`);
    await p.context().close();

    // upright: the transcript's own size from the header (Aa opens the gear's sheet at Text; the subtitles'
    // slider is among its rows, said to be for a phone held sideways)
    const u = await pageFor(PHONE, 'mobile', 'size upright ' + lang);
    await openVideo(u, vid, 4);
    for (const theme of ['light', 'dark', 'sepia']) {
      await setTheme(u, theme);
      await sleep(150);
      await tap(u, '#typo');
      await sleep(250);
      const f = await gearNow(u);
      eq([f.up, f.onTop, f.rows, f.header < 70], [true, true, ['fa', 'sub', 'gl', 'width', 'lead', ...CJK_ROWS[lang], 'reset'], true],
         `${lang}, ${theme}, upright: Aa on the header's first line opens the gear at Text, on top`);
      assert(f.t >= 0 && f.b <= f.H + 0.5 && f.l >= 0 && f.r <= f.W, `${lang}, ${theme}, upright: on the screen`);
      const before = await u.evaluate(() => parseFloat(getComputedStyle([...document.querySelectorAll('#segs .seg .fa')]
                                                                        .find(e => e.querySelector('.w'))).fontSize));
      await gearSlideTo(u, 'fa', 32);
      await sleep(150);
      const after = await u.evaluate(() => [parseFloat(getComputedStyle([...document.querySelectorAll('#segs .seg .fa')]
                                                                        .find(e => e.querySelector('.w'))).fontSize),
                                             getComputedStyle(document.documentElement).getPropertyValue('--yt-sub').trim()]);
      // (a phone's width takes 1px off, style.css)
      eq(after, [31, '20px'], `${lang}, ${theme}, upright: the transcript's words ${before} → 32px (31 at a phone's width) and the subtitles' size untouched`);
      if (theme !== 'sepia') await shot(u, `size-${lang}-${theme}-upright`);
      await gearSlideTo(u, 'fa', 20);
      await tap(u, '.pg-panel[data-pg-page=video] .pg-x');
    }
    await u.context().close();
  }
  // and the subtitles over an English video, in proportion at a large size
  const big = await pageFor(LAND, 'mobile', 'size near');
  await big.addInitScript(() => {
    localStorage.setItem('yt_typo', JSON.stringify({sub: 36}));
    localStorage.setItem('vd_subctx', '1');
  });
  await openVideo(big);
  await videoAt(big, 2);
  await tap(big, '.m-vfull');
  await big.waitForFunction(() => document.documentElement.classList.contains('m-vfullon'));
  await sleep(500);
  got = await lines(big);
  assert(got.length === 3 && got[1].size === 36 && got.every(l => l.near || l.size === 36) &&
         Math.abs(got[0].size - 36 * .82) < 0.2 && Math.abs(got[2].size - 36 * .82) < 0.2,
         `English at 36px: the line being said 36, the two beside it .82 of that (${got.map(l => l.size).join(', ')}px)`);
  await videoAt(big, 0);
  got = await lines(big);
  assert(Math.abs(got[0].size - 36 * .775) < 0.2 && Math.abs(got[1].size - 36 * .82) < 0.2,
         `and the video's own English framing (a plain line) follows it in its transcript proportion, .775 (${got.map(l => l.size).join(', ')}px)`);
  await videoAt(big, 1);
  got = await lines(big);
  assert(Math.abs(got[0].size - 36 * .64) < 0.2 && got[1].size === 36 && Math.abs(got[2].size - 36 * .82) < 0.2,
         `and the plain line before the one being said, .64 of it (${got.map(l => l.size).join(', ')}px)`);
  await shot(big, 'size-en-plain-36');
  await big.context().close();

  // ---- n) HOVER ⏸ IN A BOOK (a0.4.1; the owner, 2026-09-25 and 2026-09-28;
  // TO-DO §4.20 and §7.21).  The video's switch, in a book's reader, in both
  // modes and remembered on this device only: while a gloss cloud is open the
  // narration waits, and it goes on 350 ms after the cloud shuts.  What is
  // read is the audio element's OWN play and pause events, with the page's
  // clock, printed raw -- a boolean that says "it paused" is not what this
  // proves; the sequence of events, and how long after the cloud shut the
  // last of them came, is.  The narration is the fixture's real 8-second
  // mp3, its first subparagraph 0.8-3.9 s: every phase starts it again a
  // little after its start, and none is allowed to run to the end.
  const HP_ON_VIDEO = (await Deno.readTextFile(`${root}/youtube/lib/player.html`))
    .match(/<button id="hoverpause"[^>]*>([^<]*)<\/button>/)[1].replace(/&nbsp;/g, '\u00a0');
  // the audio's own events, the cloud's own comings and goings, and every
  // click's time -- all in the page's clock, which is the only one that
  // can say how long after the cloud shut the narration went on
  const hpWatch = page => page.evaluate(() => {
    cont = false; loop = false;
    const a = document.getElementById('audio');
    window.__ev = []; window.__cl = []; window.__clk = [];
    ['play', 'pause'].forEach(n => a.addEventListener(n, () => __ev.push([n, Math.round(performance.now())])));
    new MutationObserver(() => {
      __cl.push([document.getElementById('cloud').hidden ? 'shut' : 'open', Math.round(performance.now())]);
    }).observe(document.getElementById('cloud'), {attributes: true, attributeFilter: ['hidden']});
    addEventListener('click', () => __clk.push(Math.round(performance.now())), true);
  });
  const hpRaw = page => page.evaluate(() => __ev.map(e => e.slice()));
  const hpSeq = async page => (await hpRaw(page)).map(e => e[0]).join(',');
  const hpClear = page => page.evaluate(() => { __ev.length = 0; __cl.length = 0; __clk.length = 0; });
  const hpNote = async (page, what) => {
    const ev = await hpRaw(page);
    console.log(`  raw play/pause events, ${what}: ${JSON.stringify(ev)}`);
    return ev;
  };
  const hpAudio = page => page.evaluate(() => [document.getElementById('audio').paused,
                                               document.getElementById('audio').currentTime]);
  const hpNow = page => page.evaluate(() => Math.round(performance.now()));
  const hpCloud = page => page.evaluate(() => {
    const c = document.getElementById('cloud'), h = document.querySelector('.p1 .w.hot');
    return [!c.hidden, h ? +h.dataset.c : null];
  });
  const hpPlaying = (page, what, ms = 4000) =>
    until(page, () => !document.getElementById('audio').paused, null, what, ms);
  // the narration started again from just inside the first subparagraph, by
  // hand, and its own events forgotten
  async function hpStart(page, press) {
    await page.evaluate(() => { document.getElementById('audio').currentTime = 0.85; });
    await press();
    await hpPlaying(page, 'the narration playing');
    await sleep(150);
    await hpClear(page);
  }
  // paused by hand, the events forgotten
  async function hpStop(page, press) {
    if (!(await hpAudio(page))[0]) await press();
    await until(page, () => document.getElementById('audio').paused, null, 'the narration paused by hand', 4000);
    await sleep(150);
    await hpClear(page);
  }
  // the cloud's opening after `at` (a closure that opens it) has landed
  const hpOpenCloud = async (page, at) => {
    await at();
    await until(page, () => !document.getElementById('cloud').hidden && !!document.querySelector('.p1 .w.hot'), null, 'the cloud open');
  };
  const hpCloudShut = page => until(page, () => document.getElementById('cloud').hidden, null, 'the cloud shut', 4000);
  // the switch's state as the page keeps it and draws it
  const hpSwitch = page => page.evaluate(() => {
    const b = document.getElementById('hoverpause');
    return [localStorage.getItem('bk_hoverpause'), b.classList.contains('on'), b.getAttribute('aria-pressed')];
  });
  // what one phase proves about a cloud that opened over a playing narration
  // and shut: paused once, held open, frozen; then the grace, then playing
  async function hpPhaseOpenShut(page, press, open, shut, label) {
    await hpStart(page, press);
    await hpOpenCloud(page, open);
    eq(await hpSeq(page), 'pause', `${label}: a cloud opened over the playing narration: paused, once`);
    const [p1, t1] = await hpAudio(page);
    await sleep(500);
    const [p2, t2] = await hpAudio(page);
    eq([p1, p2, t1 === t2, await hpCloud(page)], [true, true, true, [true, 0]],
       `${label}: paused and frozen for as long as the cloud is open -- and the cloud still open (the press of ▶ did not bubble into "a click outside shuts it")`);
    const t0 = await hpNow(page);
    await shut();
    await hpCloudShut(page);
    await sleep(120);
    eq((await hpAudio(page))[0], true, `${label}: the cloud shut, the narration still waits (the grace)`);
    await hpPlaying(page, 'the narration going on');
    const ev = await hpNote(page, label);
    eq(ev.map(e => e[0]), ['pause', 'play'], `${label}: one pause, one play`);
    const shutAt = await page.evaluate(() => __cl.filter(c => c[0] === 'shut').pop()[1]);
    assert(ev[1][1] - shutAt >= 300 && ev[1][1] - t0 >= 300 && ev[1][1] - shutAt < 1500,
           `${label}: the play came ${ev[1][1] - shutAt} ms after the cloud shut (300 and more, the video's 350 ms grace)`);
  }

  console.log('hover ⏸: a book\'s narration waits while a gloss is open, on a phone');
  const hp = await pageFor(PHONE, 'mobile', 'hover pause');
  await openReader(hp, '/books/english/mini-en/reader/', true);
  const hpPress = () => tap(hp, '.nc-dock .nc-play');
  const hpWord = i => hp.locator('main .p1 .w').nth(i);
  const hpTapWord = i => hpOpenCloud(hp, () => hpWord(i).tap());
  const hpWordIn = async () => { await hpWord(0).evaluate(e => e.scrollIntoView({block: 'center'})); await sleep(400); };
  // the header goes on the way down a page and comes back on the way up: the
  // gear is pressed from the top, and the words are brought back into the screen
  const hpTop = async () => { await hp.evaluate(() => scrollTo(0, 0)); await sleep(600); };
  // the gear is opened from the top and shut again, with fn done in it (its switch pressed, its menu set)
  const hpMore = async fn => {
    await hpTop();
    await gearOpen(hp);
    await fn();
    await gearClose(hp);
    await sleep(300);
    await hpWordIn();
  };
  const hpGearSwitch = async (id, want) => { await gearOpen(hp); await gearSwitch(hp, id, want); };
  await hpWordIn();
  await hpWatch(hp);

  // ---- the switch is the layer's and the gear's: worded as the video's, kept in the header out of sight,
  // and pressed from the gear's row "Pause while a gloss is open", under the hover cloud's
  await hpTop();
  const sw0 = await hp.evaluate(() => {
    const b = document.getElementById('hoverpause');
    return {text: b.textContent, title: b.title, layout: b.getAttribute('data-layout'), tag: b.tagName + '#' + b.id,
            inRow: b.parentNode === document.querySelector('header .hrow'), drawn: b.getClientRects().length > 0};
  });
  eq(sw0.text, HP_ON_VIDEO, `the switch is worded as the video's (${JSON.stringify(HP_ON_VIDEO)}), the same string and the same glyph`);
  eq([sw0.tag, sw0.inRow, sw0.layout, sw0.title], ['BUTTON#hoverpause', true, null, 'pause the narration while a gloss is open'],
     'a button in the header\'s first row, with no data-layout (both modes draw it), saying what it does');
  eq(sw0.drawn, false, 'and not drawn there, in either mode: it is the gear\'s to press');
  await gearOpen(hp, 'levels');
  await gearRow(hp, 'hoverpause').scrollIntoViewIfNeeded();         // the sheet shows half the group: the row is brought into it
  await sleep(250);
  const row0 = await hp.evaluate(() => {
    const r = document.querySelector('.pg-panel [data-pg-row=hoverpause]'), b = r.querySelector('button.pg-switch').getBoundingClientRect();
    const hover = document.querySelector('.pg-panel [data-pg-row=hover]');
    return {name: r.querySelector('.pg-nametext').textContent, h: Math.round(r.getBoundingClientRect().height),
            under: hover.nextElementSibling === r, indent: r.getAttribute('data-pg-indent'), hidden: r.hidden,
            onScreen: b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth};
  });
  eq([row0.name, row0.under, row0.indent, row0.hidden], ['Pause while a gloss is open', true, '1', false],
     'in the gear: "Pause while a gloss is open", hanging under "Glosses in a cloud"');
  assert(row0.h >= 48 && row0.onScreen, `a finger's height and on the screen (${row0.h}px)`);
  eq(await hpSwitch(hp), [null, false, 'false'], 'off until it is turned on: nothing stored, not pressed');
  await gearClose(hp);
  await sleep(250);
  assert(!(await drawn(hp, '#hoverpause')), 'the gear shut: it is not on the first line');
  await hpWordIn();

  // ---- switch OFF: nothing changes
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await sleep(500);
  eq([await hpSeq(hp), (await hpAudio(hp))[0], (await hpCloud(hp))[0]], ['', false, true],
     'switch off: a tap opens the cloud and the narration plays on');
  await hpWord(0).tap();
  await hpCloudShut(hp);
  await sleep(800);
  eq([await hpSeq(hp), (await hpAudio(hp))[0]], ['', false], 'and it plays on when the cloud shuts: nothing paused it, nothing started it');
  await hpNote(hp, 'switch off');
  await hpStop(hp, hpPress);

  // ---- turned on, in the gear, kept on this device only
  await hpMore(() => hpGearSwitch('hoverpause', true));
  eq(await hpSwitch(hp), ['1', true, 'true'], 'turned on: stored \'1\', pressed, aria-pressed true');
  const kept = await hp.evaluate(async () => {
    const r = await fetch('/__prefs'); const j = await r.json();
    return [JSON.stringify(j).includes('bk_hoverpause'), typeof ParsehPrefs === 'object' ? ParsehPrefs.keys.includes('bk_hoverpause') : null];
  });
  eq(kept, [false, false], 'and nothing of it is on the computer: not in the prefs the server keeps, not in the page\'s KEYS');
  await openReader(hp, '/books/english/mini-en/reader/', true);
  eq(await hpSwitch(hp), ['1', true, 'true'], 'a reload: still on, and drawn on');
  await hpWordIn();
  await hpWatch(hp);

  // ---- ON: playing -> a tap opens a cloud -> paused -> the cloud shuts -> playing after the grace
  await hpPhaseOpenShut(hp, hpPress, () => hpWord(0).tap(), () => hpWord(0).tap(), 'a tap');
  await hpStop(hp, hpPress);

  // ---- the next word straight away: no stutter
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await hp.evaluate(() => { __cl.length = 0; });     // the cloud's own comings and goings from here on
  await hpWord(0).tap();          // the open word again: shuts its cloud ...
  await hpWord(1).tap();          // ... and the next one, at once
  await until(hp, () => !document.getElementById('cloud').hidden && +document.querySelector('.p1 .w.hot').dataset.c === 1, null, 'the cloud on the next word');
  await sleep(900);
  const gapMs = await hp.evaluate(() => {
    const shut = __cl.filter(c => c[0] === 'shut')[0], open = __cl.filter(c => c[0] === 'open').pop();
    return shut && open ? open[1] - shut[1] : null;
  });
  const nx = await hpNote(hp, 'A shut, B opened');
  assert(gapMs !== null && gapMs < 350, `the cloud shut and the next word's opened ${gapMs} ms later, inside the grace`);
  eq([nx.map(e => e[0]), (await hpAudio(hp))[0], await hpCloud(hp)], [['pause'], true, [true, 1]],
     'A then B within 350 ms: exactly one pause, no play, no second pause -- waiting on B\'s cloud');
  await hpWord(1).tap();
  await hpCloudShut(hp);
  await hpPlaying(hp, 'the narration going on after B');
  eq(await hpSeq(hp), 'pause,play', 'B shut: it goes on, once');
  await hpStop(hp, hpPress);
  // ... and a plain tap on another word while one is open: no close between
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await hpWord(1).tap();
  await until(hp, () => +document.querySelector('.p1 .w.hot').dataset.c === 1, null, 'the cloud moved to the next word');
  await sleep(900);
  eq([await hpSeq(hp), (await hpAudio(hp))[0], await hpCloud(hp)], ['pause', true, [true, 1]],
     'a tap on another word while a cloud is open: one pause still, no play');
  await hpWord(1).tap();
  await hpCloudShut(hp);
  await hpPlaying(hp, 'the narration going on');
  eq(await hpSeq(hp), 'pause,play', 'and it goes on once when the last cloud shuts');
  await hpStop(hp, hpPress);

  // ---- a narration the person paused is never started by it
  await hpStart(hp, hpPress);
  await hpPress();
  await until(hp, () => document.getElementById('audio').paused, null, 'paused by hand');
  await hpTapWord(0);
  await hpWord(0).tap();
  await hpCloudShut(hp);
  await sleep(900);
  eq([await hpSeq(hp), (await hpAudio(hp))[0]], ['pause', true],
     'paused by hand, a cloud opened and shut: nothing but the hand\'s own pause, and it stays paused');
  await hpNote(hp, 'paused by hand');
  await hpClear(hp);
  // ... and playing under an open cloud, then paused by hand, is the person's too
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await hp.evaluate(() => document.getElementById('audio').play());
  await hpPlaying(hp, 'the narration playing under the open cloud');
  await sleep(250);
  await hp.evaluate(() => document.getElementById('audio').pause());
  await sleep(100);
  await hpWord(0).tap();
  await hpCloudShut(hp);
  await sleep(900);
  eq([await hpSeq(hp), (await hpAudio(hp))[0]], ['pause,play,pause', true],
     'paused by the cloud, played by hand under it, paused by hand: the cloud shuts and nothing is started');
  await hpNote(hp, 'play then pause by hand under an open cloud');
  await hpClear(hp);

  // ---- the dictionary's sheet on top: one pause, one resume, after the grace
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await tap(hp, '#cloud .mkdict');
  await hp.waitForSelector('.m-dsheet');
  await sleep(700);
  const [sp1, st1] = await hpAudio(hp);
  await sleep(400);
  const [sp2, st2] = await hpAudio(hp);
  eq([await hpSeq(hp), sp1, sp2, st1 === st2], ['pause', true, true, true], 'the sheet over the cloud: still the one pause, and frozen');
  const tSheet = await hpNow(hp);
  await hp.touchscreen.tap(20, 20);
  await hpPlaying(hp, 'the narration going on after the sheet');
  const sh = await hpNote(hp, 'the sheet over the cloud');
  eq(sh.map(e => e[0]), ['pause', 'play'], 'the sheet closed: one resume, and no pause of its own');
  assert(sh[1][1] - tSheet >= 300, `the play ${sh[1][1] - tSheet} ms after the sheet was closed: the grace, not the sheet's immediate go-on`);
  eq(await nothingOpen(hp), CLOSED, 'and the sheet, the cloud and the mark are gone');
  await hpStop(hp, hpPress);
  // paused by hand, the sheet on top: never started by it
  await hpStart(hp, hpPress);
  await hpPress();
  await until(hp, () => document.getElementById('audio').paused, null, 'paused by hand');
  await hpTapWord(0);
  await tap(hp, '#cloud .mkdict');
  await hp.waitForSelector('.m-dsheet');
  await sleep(400);
  await hp.touchscreen.tap(20, 20);
  await sleep(900);
  eq([await hpSeq(hp), (await hpAudio(hp))[0]], ['pause', true], 'paused by hand, the sheet opened and closed: stays paused');
  await hpClear(hp);

  // ---- the reader's own re-open of its cloud (a late model) is not a new open
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await hp.evaluate(() => document.getElementById('audio').play());
  await hpPlaying(hp, 'the narration played by hand under the cloud');
  await hp.evaluate(() => { const sp = cloudFor; cloudFor = null; openCloud(sp); });
  await sleep(500);
  eq([await hpSeq(hp), (await hpAudio(hp))[0], (await hpCloud(hp))[0]], ['pause,play', false, true],
     'the reader opening its own cloud again (cloudFor emptied, openCloud) is not a new open: still playing');
  await hpStop(hp, hpPress);

  // ---- the loop's wait between two repeats: the reader's own timer, taken and given back
  await hpMore(async () => { await hpGearSwitch('loop', true); await gearSelect(hp, 'gap', '3 s'); });
  await hp.evaluate(() => { document.getElementById('audio').currentTime = 3.3; });
  await hpClear(hp);
  await hpPress();
  await until(hp, () => document.getElementById('audio').paused && waiting != null, null, 'the loop\'s wait between two repeats');
  await hpClear(hp);
  await hpTapWord(0);
  await sleep(3700);
  eq([await hpSeq(hp), (await hpAudio(hp))[0], (await hpCloud(hp))[0]], ['', true, true],
     'in the loop\'s 3-second wait a cloud opens: the wait is taken, and the repeat does not start under the cloud');
  const tLoop = await hpNow(hp);
  await hpWord(0).tap();
  await hpCloudShut(hp);
  await hpPlaying(hp, 'the repeat starting');
  const lp = await hpNote(hp, 'the loop\'s wait');
  eq(lp.map(e => e[0]), ['play'], 'the cloud shut: the repeat starts, once');
  assert(lp[0][1] - tLoop >= 300, `the repeat ${lp[0][1] - tLoop} ms after the cloud shut: the grace`);
  assert((await hpAudio(hp))[1] < 2.5, `and it is the subparagraph from its start again (${(await hpAudio(hp))[1].toFixed(2)} s)`);
  await hpStop(hp, hpPress);
  await hpMore(() => hpGearSwitch('loop', false));

  // ---- the switch turned off under an open cloud: what it took it gives back
  await hpStart(hp, hpPress);
  await hpTapWord(0);
  await hp.evaluate(() => document.getElementById('hoverpause').dispatchEvent(new MouseEvent('click', {bubbles: false})));
  eq([await hpSwitch(hp), (await hpCloud(hp))[0], (await hpAudio(hp))[0]], [['0', false, 'false'], true, true],
     'the switch turned off under an open cloud: stored \'0\', the cloud still open, the narration still waiting');
  await hpWord(0).tap();
  await hpCloudShut(hp);
  await hpPlaying(hp, 'the narration going on');
  eq(await hpSeq(hp), 'pause,play', 'the cloud shut: it went on all the same (what was taken is given back)');
  await hpTapWord(0);
  await sleep(600);
  eq([await hpSeq(hp), (await hpAudio(hp))[0]], ['pause,play', false], 'and with the switch off a new cloud leaves the narration playing');
  await hpStop(hp, hpPress);
  // on again, for the last one
  await hpMore(() => hpGearSwitch('hoverpause', true));
  eq((await hpSwitch(hp))[0], '1', 'turned on again');

  // ---- a row's tap on a chunk nobody has glossed: the sheet at once, the
  // cloud's pause first, one pause and one resume.  The fixture's chunks are
  // all glossed, so one is emptied here -- its row and the reader's own
  // record of it -- and the dictionary switched on
  await hpTop();
  await switchDict(hp);
  await hpWordIn();
  await hp.evaluate(() => {
    const n = 2;
    document.querySelectorAll(`.row[data-c="${n}"] .gl > *`).forEach(e => { e.textContent = ''; });
    SRC[n] = [SRC[n][0], SRC[n][1], '', '', '', '', SRC[n][6]];
  });
  await hpStart(hp, hpPress);
  await hpWord(2).tap();
  await hp.waitForSelector('.m-dsheet');
  await sleep(700);
  eq([await hpSeq(hp), (await hpAudio(hp))[0], await hp.evaluate(() => document.getElementById('cloud').hidden)], ['pause', true, true],
     'an unglossed chunk tapped, the dictionary on: the sheet at once, no cloud -- and the narration paused, once');
  const tRow = await hpNow(hp);
  await hp.touchscreen.tap(20, 20);
  await hpPlaying(hp, 'the narration going on after the sheet');
  const rw = await hpNote(hp, 'the row\'s tap and its sheet');
  eq(rw.map(e => e[0]), ['pause', 'play'], 'the sheet closed: one resume');
  assert(rw[1][1] - tRow >= 300, `${rw[1][1] - tRow} ms after the sheet closed: the grace`);
  await hpStop(hp, hpPress);
  await hp.context().close();

  // ================= the browser interface: the same switch, beside hover, with a mouse
  console.log('hover ⏸: the same in the browser interface, with a mouse');
  const bd = await pageFor(DESK, 'browser', 'hover pause, browser');
  await bd.goto(B + '/books/english/mini-en/reader/');
  await bd.waitForFunction(() => document.querySelector('#hoverpause') && document.querySelector('#hovermode'));
  await sleep(400);
  if (await bd.$('.pf-bar')) await bd.click('.pf-stay');
  const bsw = await bd.evaluate(() => {
    const b = document.getElementById('hoverpause'), hm = document.getElementById('hovermode');
    return {beside: hm.nextElementSibling === b, drawn: b.getClientRects().length > 0, text: b.textContent,
            layout: b.getAttribute('data-layout'), mode: document.documentElement.getAttribute('data-mode'),
            more: !!document.querySelector('.m-rmore'),
            state: [localStorage.getItem('bk_hoverpause'), b.classList.contains('on')], title: b.title};
  });
  eq([bsw.beside, bsw.drawn, bsw.text === HP_ON_VIDEO, bsw.layout, bsw.mode, bsw.more, bsw.state],
     [true, false, true, null, 'browser', false, [null, false]],
     'the browser interface: the switch beside hover in the markup, worded as the video\'s, off, not drawn (the gear\'s to press); and no ⋯');
  await bd.click('#hovermode');
  const press = () => bd.click('#play');
  const word = i => bd.locator('main .p1 .w').nth(i);
  const away = () => bd.mouse.move(2, 2);
  const openB = i => hpOpenCloud(bd, () => word(i).hover());
  await hpWatch(bd);
  // off: nothing changes
  await hpStart(bd, press);
  await openB(0);
  await sleep(500);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['', false], 'browser, switch off: a mouse at rest on a word opens its cloud and the narration plays on');
  await away();
  await hpCloudShut(bd);
  await sleep(800);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['', false], 'and plays on when the mouse leaves');
  await hpStop(bd, press);
  // turned on, with the mouse
  await gearSwitch(bd, 'hoverpause', true);
  eq(await hpSwitch(bd), ['1', true, 'true'], 'browser: turned on with a click in the gear: stored, pressed');
  await hpPhaseOpenShut(bd, press, () => word(0).hover(), away, 'browser, a mouse at rest');
  await hpStop(bd, press);
  // the next word: straight across (no close between), and with a gap of a
  // moment between them (the cloud shuts, then the next word's opens: inside the grace)
  await hpStart(bd, press);
  await openB(0);
  await word(1).hover();
  await until(bd, () => +document.querySelector('.p1 .w.hot').dataset.c === 1, null, 'the cloud moved to the next word');
  await sleep(900);
  eq([await hpSeq(bd), (await hpAudio(bd))[0], await hpCloud(bd)], ['pause', true, [true, 1]],
     'browser: from one word straight to the next: one pause, no play');
  await away();
  await hpCloudShut(bd);
  await hpPlaying(bd, 'the narration going on');
  eq(await hpSeq(bd), 'pause,play', 'and one play when the mouse leaves');
  await hpStop(bd, press);
  await hpStart(bd, press);
  await openB(0);
  await away();
  await hpCloudShut(bd);
  await hpOpenCloud(bd, () => word(1).hover());
  await sleep(900);
  const bgap = await bd.evaluate(() => {
    const shut = __cl.filter(c => c[0] === 'shut')[0], open = __cl.filter(c => c[0] === 'open').pop();
    return shut && open ? open[1] - shut[1] : null;
  });
  const bx = await hpNote(bd, 'A shut, B opened');
  assert(bgap !== null && bgap < 350, `browser: the cloud shut and the next word's opened ${bgap} ms later, inside the grace`);
  eq([bx.map(e => e[0]), (await hpAudio(bd))[0], await hpCloud(bd)], [['pause'], true, [true, 1]],
     'browser: A then B within 350 ms: exactly one pause, waiting on B\'s cloud');
  await away();
  await hpCloudShut(bd);
  await hpPlaying(bd, 'the narration going on after B');
  eq(await hpSeq(bd), 'pause,play', 'and one play, when B\'s cloud is gone');
  await hpStop(bd, press);
  // paused by hand
  await hpStart(bd, press);
  await press();
  await until(bd, () => document.getElementById('audio').paused, null, 'paused by hand');
  await openB(0);
  await away();
  await hpCloudShut(bd);
  await sleep(900);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['pause', true], 'browser: paused by hand, a cloud opened and shut: it stays paused');
  await hpClear(bd);
  await hpStart(bd, press);
  await openB(0);
  await bd.evaluate(() => document.getElementById('audio').play());
  await hpPlaying(bd, 'played by hand under the cloud');
  await sleep(250);
  await bd.evaluate(() => document.getElementById('audio').pause());
  await sleep(100);
  await away();
  await hpCloudShut(bd);
  await sleep(900);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['pause,play,pause', true],
     'browser: played by hand under the cloud, then paused by hand: not started when the cloud shuts');
  await hpNote(bd, 'browser, play then pause by hand under an open cloud');
  await hpClear(bd);
  // the reader's own re-open
  await hpStart(bd, press);
  await openB(0);
  await bd.evaluate(() => document.getElementById('audio').play());
  await hpPlaying(bd, 'played by hand under the cloud');
  await bd.evaluate(() => { const sp = cloudFor; cloudFor = null; openCloud(sp); });
  await sleep(500);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['pause,play', false], 'browser: the reader\'s own re-open is not a new open');
  await away();
  await hpCloudShut(bd);
  await hpStop(bd, press);
  // the loop's wait
  await bd.click('#loop');
  await bd.selectOption('#gap', '3');
  await bd.evaluate(() => { document.getElementById('audio').currentTime = 3.3; });
  await hpClear(bd);
  await press();
  await until(bd, () => document.getElementById('audio').paused && waiting != null, null, 'the loop\'s wait');
  await hpClear(bd);
  await openB(0);
  await sleep(3700);
  eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['', true], 'browser: a cloud in the loop\'s wait: the repeat does not start under it');
  const tbl = await hpNow(bd);
  await away();
  await hpCloudShut(bd);
  await hpPlaying(bd, 'the repeat starting');
  const bl = await hpNote(bd, 'browser, the loop\'s wait');
  eq(bl.map(e => e[0]), ['play'], 'browser: the mouse gone, the repeat starts once');
  assert(bl[0][1] - tbl >= 300, `browser: ${bl[0][1] - tbl} ms after the mouse left: the cloud's own 120 ms and the grace`);
  await hpStop(bd, press);
  await bd.click('#loop');
  // the switch turned off under an open cloud
  await hpStart(bd, press);
  await openB(0);
  await bd.evaluate(() => document.getElementById('hoverpause').dispatchEvent(new MouseEvent('click', {bubbles: false})));
  eq([(await hpSwitch(bd))[0], (await hpCloud(bd))[0], (await hpAudio(bd))[0]], ['0', true, true],
     'browser: the switch turned off under an open cloud: the narration still waits');
  await away();
  await hpCloudShut(bd);
  await hpPlaying(bd, 'the narration going on');
  eq(await hpSeq(bd), 'pause,play', 'browser: the cloud gone, it goes on (what was taken is given back)');
  await hpStop(bd, press);
  await gearSwitch(bd, 'hoverpause', true);

  // ---- the reader's OWN sheets (the browser interface's alone): each puts
  // the narration back itself, and hover ⏸ must not fight it.  a) under a
  // cloud the narration is paused by the cloud: the sheet takes over, so the
  // debt is dropped and nothing plays under it, nor after; b) with no cloud
  // the sheet's own pause and go-on are exactly what they are with the
  // switch off (the reader's own behaviour, whatever it is)
  const SHEETS = [
    ['the card dashboard', 'ankiOpen', () => bd.locator('#cloud .mkcard').click(), () => bd.locator('#acancel').click(),
     () => bd.locator('main .p1 .wd').first().click({modifiers: ['Alt']})],
    ['the chunk\'s editor', 'chOpen', () => bd.locator('#cloud .mkedit').click(), () => bd.locator('#chcancel').click(), null],
    ['the fold', 'fdShown', () => bd.locator('#fold').click(), () => bd.locator('#fdcancel').click(), () => bd.locator('#fold').click()],
    ['the LLM gloss', 'rgShown', () => bd.locator('#rgn').click(), () => bd.locator('#rgcancel').click(), () => bd.locator('#rgn').click()],
    ['the narration\'s sheet', 'narrOpen', () => bd.locator('#narr').click(), () => bd.locator('#ncancel').click(), () => bd.locator('#narr').click()],
  ];
  const flagOf = (page, flag) => page.evaluate(f => ({ankiOpen, chOpen, fdShown, rgShown, narrOpen})[f], flag);
  const flagIs = (page, flag, want) => until(page, ([f, w]) => ({ankiOpen, chOpen, fdShown, rgShown, narrOpen})[f] === w, [flag, want],
                                              `${flag} ${want}`, 4000);
  for (const [name, flag, open, shut, plain] of SHEETS) {
    eq((await hpSwitch(bd))[0], '1', `(${name}: the switch is on)`);
    await hpStart(bd, press);
    await openB(0);
    await open();
    await flagIs(bd, flag, true);
    await sleep(1300);
    eq([await hpSeq(bd), (await hpAudio(bd))[0], await flagOf(bd, flag)], ['pause', true, true],
       `browser, ${name} opened from a cloud that paused the narration: it stays paused under the sheet (one pause, no play)`);
    await shut();
    await flagIs(bd, flag, false);
    await sleep(900);
    eq([await hpSeq(bd), (await hpAudio(bd))[0]], ['pause', true], `and paused after it: the person's ▶ is the only way on`);
    await hpNote(bd, `browser, ${name} from a cloud`);
    await hpClear(bd);
    if (!plain) continue;
    // b) no cloud (hover mode off, or the mouse arriving over a word would
    // open one): the same with the switch on and off
    await bd.click('#hovermode');
    const runs = [];
    for (const on of ['1', '0']) {
      await bd.evaluate(v => localStorage.setItem('bk_hoverpause', v), on);
      await away();
      await hpStart(bd, press);
      await plain();
      await flagIs(bd, flag, true);
      await sleep(700);
      await shut();
      await flagIs(bd, flag, false);
      await sleep(900);
      runs.push(await hpSeq(bd));
      await hpNote(bd, `browser, ${name}, no cloud, switch ${on === '1' ? 'on' : 'off'}`);
      await hpStop(bd, press);
    }
    eq(runs[0], runs[1], `browser, ${name} with no cloud: the sheet's own pause and go-on are the same with the switch on and off (${JSON.stringify(runs[0])})`);
    // (the last run had the switch off: on again, for the next sheet)
    await bd.evaluate(() => localStorage.setItem('bk_hoverpause', '1'));
    await bd.click('#hovermode');
  }

  // ---- a book with no narration has no such switch, in either mode
  await bd.goto(B + '/books/persian/mini-fa/reader/');
  await bd.waitForFunction(() => document.querySelector('#hovermode'));
  await sleep(400);
  eq([await bd.evaluate(() => !!document.getElementById('hoverpause')), await drawn(bd, '#hoverpause')], [true, false],
     'a book with no narration (Persian): the switch is there for the layer and not drawn');
  await bd.context().close();

  // ---- a mouse in the MOBILE mode (a desk with the phone's layout): no pointer
  // filter, as the video's has none -- what opens the cloud pauses, mouse or finger
  console.log('hover ⏸: a mouse over the mobile interface');
  const md = await pageFor(DESK, 'mobile', 'hover pause, mouse in the mobile mode');
  await md.addInitScript(() => { localStorage.setItem('bk_hover', '1'); localStorage.setItem('bk_hoverpause', '1'); });
  await md.goto(B + '/books/english/mini-en/reader/');
  await md.waitForFunction(() => document.querySelector('[data-parseh-gear]') && document.getElementById('hoverpause'));
  await sleep(400);
  if (await md.$('.pf-bar')) await md.click('.pf-stay');
  await hpWatch(md);
  await hpPhaseOpenShut(md, () => md.locator('.nc-dock .nc-play').click(), () => md.locator('main .p1 .w').first().hover(),
                        () => md.mouse.move(2, 400), 'mobile mode, a mouse at rest');
  await hpStop(md, () => md.locator('.nc-dock .nc-play').click());
  await md.context().close();

  // ---- h) not in the browser interface
  console.log('the browser interface');
  const desk = await pageFor(DESK, 'browser', 'browser');
  await openVideo(desk);
  await desk.locator('#segs .seg').nth(1).locator('.w').first().hover();
  await desk.waitForFunction(() => !document.getElementById('cloud').hidden);
  eq(await desk.evaluate(() => [!!document.querySelector('#cloud .mkcopy'), !!document.querySelector('#cloud .mkdict')]),
     [true, false], 'the browser interface\'s video cloud: copy, and no dictionary button');
  eq(await desk.evaluate(() => [...document.querySelectorAll('#segs .gap .plus')].some(e => e.getClientRects().length > 0)), true,
     'and its transcript\'s seams keep their + to write a note with');
  await openVideo(desk, FA_VIDEO, 4);
  eq(await desk.evaluate(() => [document.documentElement.classList.contains('m-sparse'), document.querySelectorAll('.m-gl').length]),
     [false, 0], 'the video with few glosses: no mark in the browser interface');
  await desk.goto(B + '/books/persian/mini-fa/reader/');
  await desk.waitForFunction(() => document.querySelector('#hovermode'));
  await sleep(400);
  if (await desk.$('.pf-bar')) await desk.click('.pf-stay');
  if (!(await desk.evaluate(() => document.body.classList.contains('hovermode')))) await desk.click('#hovermode');
  await desk.locator('main .p1 .w').first().hover();
  await desk.waitForFunction(() => !document.getElementById('cloud').hidden);
  await sleep(200);
  eq(await desk.evaluate(() => [!!document.querySelector('#cloud .mkcopy'), !!document.querySelector('#cloud .mkdict')]),
     [true, false], 'nor the book\'s');
  eq(await cloudHTML(desk), faCloud,
     'and the phone\'s cloud of that chunk, bar its button, is the very cloud the browser interface draws');
  await desk.goto(B + SPARSE);
  await desk.waitForFunction(() => document.querySelector('#hovermode'));
  await sleep(400);
  eq(await desk.evaluate(() => [document.documentElement.classList.contains('m-sparse'), document.querySelectorAll('.m-gl').length,
                                 getComputedStyle(document.querySelector('main .p2 .row .fa')).textDecorationLine]),
     [false, 0, 'none'], 'nor the book with few glosses');
  await desk.context().close();

  eq(errors, [], 'no page error');
  console.log(`phone_clouds: ${passed} checks passed`);
} finally {
  await browser.close();
  try { hub.kill('SIGTERM'); } catch (_) { /* gone */ }
  await sleep(300);
  await Deno.remove(WORK, {recursive: true}).catch(() => {});
}
