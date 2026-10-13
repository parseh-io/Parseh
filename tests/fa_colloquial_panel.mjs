// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/fa_colloquial_panel.mjs
//      PARSEH_KEEP=1 keeps the temporary tree, to read what was written
//      FA_PANEL_SHOTS=<dir> saves the cloud of every case, in the reader and in the player
//      FA_PANEL_GUIDE=1     retakes the guide's picture of a spoken word's card (lookup-and-languages/shots/spoken-panel.png)
//
// WHAT THE DICTIONARY PANEL SHOWS FOR A SPOKEN PERSIAN WORD (note section 13), driven in the book reader and in the video
// player on the REAL hub: serve.main() over a temporary tree that holds the small Persian dictionary of the colloquial fixture
// (tests/fa_colloquial_dict.py: formal words only, built here, not downloaded), a copy of the Persian fixture book whose
// chunks, and a copy of the Persian fixture video whose captions, are the sentences of the rows tests/fixtures/fa_colloquial/
// panel.json names.  Nothing is stubbed but YouTube's iframe API.  Every action is the page's own: the dictionary switched on,
// a chunk hovered, the cloud read as drawn -- the DOM the reader sees, not the answer's JSON.
//
//  a) in the reader, every case of panel.json holds: a plain word is drawn exactly as before; a spoken one has its pill, its
//     tint and dotted edge, the word as written, the word it was read as, the reason in words, its pieces, its sound (the spoken
//     one where a rule gives it, the formal one labelled where none does); two readings are numbered under a header; a second
//     line on one card is a line and not a card; a piece with no formal word is named
//  b) the same cases in the player, which draws them with the same function (lib/parseh.js)
//  c) what the page sends: the player says its captions are speech (`register`), the book says nothing of its narration
//  d) the editor's sources column, in the book's chunk sheet and in the player's edit cloud, says it under the row of the word
//  e) the phone's sheet, over either, draws the same block inside the screen
//  f) no page threw, logged an error or had a request refused; the hub printed no traceback; the owner's config/, books/ and
//     youtube/videos/ and the fixtures are as they were.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-fa-panel-'});
const SHOTS = Deno.env.get('FA_PANEL_SHOTS') || '';
const GUIDE = !!Deno.env.get('FA_PANEL_GUIDE');
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = s => String(s || '').replace(/[‌‍]/g, '').replace(/\s+/g, ' ').trim();
async function until(fn, what, ms = 15000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}
async function run(cmd, args) {
  const o = await new Deno.Command(cmd, {args, cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  return {code: o.code, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
async function py(code, ...args) {
  const r = await run(PY, ['-c', code, ...args]);
  if (r.code) throw Error(r.err || r.out);
  return r.out;
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
function drain(stream, sink) {
  (async () => {
    const r = stream.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; sink.push(value); }
  })();
}

/* ---------------- the cases: panel.json, each with the sentence of its row ---------------- */
const PANEL = JSON.parse(await Deno.readTextFile('tests/fixtures/fa_colloquial/panel.json'));
const LEXICON = JSON.parse(await Deno.readTextFile('tests/fixtures/fa_colloquial/lexicon.json')).entries;
const sensesOf = head => (LEXICON.find(e => norm(e[0]) === norm(head)) || [null, null, null, ''])[3].split(';').map(s => s.trim()).filter(Boolean);
const CASES = JSON.parse(await py(String.raw`
import glob, json, sys
sys.path.insert(0, 'tests'); sys.path.insert(0, 'lib')
import test_fa_colloquial as t
panel = json.load(open('tests/fixtures/fa_colloquial/panel.json', encoding='utf-8'))
rows = {}
for rid, fid, layer, row in t.load_rows():
    rows.setdefault((fid, row[1]), []).append((rid, row))
out = []
for c in panel['cases']:
    rid, row = rows[tuple(c['row'])][c.get('at', 0)]
    out.append({'id': c['id'], 'row': rid, 'text': row[0], 'word': row[1], 'shows': c['shows']})
print(json.dumps(out, ensure_ascii=False))
`));

const BUILD = String.raw`
import json, os, shutil, subprocess, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['youtube/lib', 'lib', 'tests']
import annwrite, check_annotations as CA, languages, tex2html, texparse, texwrite
import books as booklib
import fa_colloquial_dict as fd
tmp = Path(sys.argv[1])
CASES = json.loads(sys.argv[2])
root = tmp / 'root'
for d in (root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises', tmp / 'anki', tmp / 'tray', tmp / 'config',
          tmp / 'dict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
# the dictionary of the fixture: formal Persian, in Wiktionary's shape
fd.build(str(tmp / 'dict' / 'fa.db'))
out = {'cases': CASES}
# the video: each case is a caption of its own, after the ones the fixture has
vid = 'fA6bK2mQ8sT'
d = root / 'youtube' / 'videos' / 'persian' / vid
shutil.copytree(str(REPO / 'tests/fixtures/videos/persian' / vid), str(d))
ann = annwrite.read(str(d))
first = len(ann['segments'])
last = max(sg['start'] for sg in ann['segments'])
for k, c in enumerate(CASES):
    ann['segments'].append({'start': last + 2 * (k + 1), 'text': c['text'], 'chunks': [{'fa': c['text']}]})
    c['seg'] = first + k
annwrite.write(str(d), ann)
caps = [{'start': sg['start'], 'text': sg['text'], 'chapter': sg.get('chapter')} for sg in ann['segments']]
(d / 'transcript.txt').write_text(CA.transcript_text(caps), encoding='utf-8')
meta = json.loads((d / 'video.json').read_text(encoding='utf-8'))
meta['duration'] = '9:00'
(d / 'video.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
errs, _w, _n = CA.check(str(d))
out['video'] = {'id': vid, 'errors': errs}
# the book: the fixture's first chapter, with a run of its chunks made the cases' sentences and left unglossed
rel = 'persian/mini-fa'
b = root / 'books' / rel
# (without its source folder: the paragraphs are the sentences of the cases now, and are not the source's any more)
shutil.copytree(str(REPO / 'tests/fixtures/books' / rel), str(b), ignore=shutil.ignore_patterns('reader', '.reader-key', 'source'))
BASE = 120
for k, c in enumerate(CASES):
    texwrite.edit_chunk(str(b / 'ch1.tex'), BASE + k, {'fa': c['text'], 'tr': '', 'voc': '', 'en': ''})
    c['chunk'] = BASE + k
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', str(b)], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr or r.stdout)
rdr = b / 'reader'
climb = os.path.relpath(str(REPO), str(rdr)).replace(os.sep, '/') + '/'
for name in os.listdir(str(rdr)):
    if name.endswith('.html'):
        pth = rdr / name
        pth.write_text(pth.read_text(encoding='utf-8').replace(climb, '/'), encoding='utf-8')
out['book'] = {'rel': rel}
print(json.dumps(out, ensure_ascii=False))
`;
// serve.main() over the temporary tree, every store in there (the harness of tests/vocline_video.mjs), with the fixture's dictionary
const SERVE = String.raw`
import sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
import prefs, network, offline
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
latexdraw.DRAWN = str(tmp / 'latex-drawn')
texpackages.TREE = str(tmp / 'texmf')
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
import lookup, corpus, getmt
lookup.DICT_DIR = str(tmp / 'dict')
corpus.CORPUS_DIR = str(tmp / 'nocorpus')
getmt.MT_DIR = str(tmp / 'nomt')
getmt.ENGINE_DIR = str(tmp / 'nomt' / 'engine')
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
sys.argv = ['serve.py', '--http', '--local', port]
serve.main()
`;
// the owner's own files, which nothing here may touch
const OWN = String.raw`
import hashlib, json, os, sys
tmp = sys.argv[1]
out, leaks = {}, []
for top in ('config', 'books', 'youtube/videos', 'tests/fixtures/videos', 'tests/fixtures/books'):
    for d, _, files in os.walk(top):
        if '/reader' in d.replace(os.sep, '/') + '/' and top == 'tests/fixtures/books':
            continue                    # build output, gitignored
        for f in files:
            p = os.path.join(d, f)
            if p.replace(os.sep, '/') in ('config/digests.json', 'config/wheres.json'):
                try:
                    text = open(p, encoding='utf-8').read()
                except OSError:
                    continue
                if tmp in text:
                    leaks.append(p)
                continue
            out[p] = hashlib.md5(open(p, 'rb').read()).hexdigest()
print(json.dumps({'digests': out, 'leaks': leaks}, sort_keys=True))
`;
const ownBefore = JSON.parse(await py(OWN, TMP));

// THE YOUTUBE PLAYER, as the page loads it from https://www.youtube.com/iframe_api
const FAKE_YT = `window.YT = {Player: function (el, o) {
  var t = 0, going = false, self = this;
  window.__yt = {seeks: [], t: function () { return t; }, going: function () { return going; }};
  this.getCurrentTime = function () { return t; };
  this.getDuration = function () { return 400; };
  this.seekTo = function (s) { t = +s || 0; window.__yt.seeks.push(t); };
  this.playVideo = function () { going = true; };
  this.pauseVideo = function () { going = false; };
  this.getPlayerState = function () { return going ? 1 : 2; };
  this.getPlaybackRate = function () { return 1; };
  this.setPlaybackRate = function () {};
  this.mute = function () {}; this.unMute = function () {};
  this.isMuted = function () { return false; };
  setInterval(function () { if (going) t += 0.05; }, 50);
  setTimeout(function () { if (o.events && o.events.onReady) o.events.onReady({target: self}); }, 20);
}};
if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();`;

/* ---------------- what a word's card is, read off the page as drawn ---------------- */
// the card(s) of the word of this case in the open cloud, as the page draws them
const READ = ([word]) => {
  const n = s => String(s || '').replace(/[‌‍]/g, '').replace(/\s+/g, ' ').trim();
  const txt = (e, sel) => { const x = e.querySelector(sel); return x ? x.textContent : null; };
  const dws = [...document.querySelectorAll('#cloud .ddict .dw')];
  const dw = dws.find(d => n(txt(d, '.dwd')) === n(word));
  if (!dw) return {found: false, words: dws.map(d => n(txt(d, '.dwd')))};
  const cards = [...dw.querySelectorAll(':scope > .dhit')].map(h => {
    const cs = getComputedStyle(h), block = h.querySelector('.dspoken:not(.dsame)'), second = h.querySelector('.dspoken.dsame');
    return {
      head: (txt(h, '.dhead2') || '').trim().split(' ')[0],
      num: txt(h, '.dsnum'),
      row: h.className,
      pill: txt(h, '.dspill'),
      was: block ? txt(block, '.dwas') : null,
      as: block ? txt(block, '.das') : null,
      why: block ? txt(block, '.dwhy') : null,
      parts: block ? txt(block, '.dparts .dptext') : null,
      pieces: block ? [...block.querySelectorAll('.dpiece')].map(p => [txt(p, '.dptext'), txt(p, '.drole'), p.textContent]) : [],
      alts: block ? [...block.querySelectorAll('.dalt .dasr')].map(a => a.textContent) : [],
      sound: block ? txt(block, '.dsound') : null,
      sounded: block ? txt(block, '.dsound .dsnd') : null,
      second: second ? [txt(second, '.dspill'), txt(second, '.das')] : null,
      blockText: block ? block.textContent : '',
      senses: [...h.querySelectorAll(':scope > .dsense')].map(s => s.textContent),
      note: txt(h, '.dnote'),
      edge: cs.borderInlineStartStyle, bg: cs.backgroundColor,
      dir: block ? (block.querySelector('.das') || {getAttribute() {}}).getAttribute('dir') : null,
      lang: block ? (block.querySelector('.das') || {getAttribute() {}}).getAttribute('lang') : null,
    };
  });
  return {found: true, header: txt(dw, '.dsreadings'), cards, none: txt(dw, '.dnone'),
          dnoneAll: [...dw.querySelectorAll('.dnone')].map(x => x.textContent)};
};
// the case's `shows`, held against what was read
function check(surface, c, got) {
  const s = c.shows, at = `${surface}: ${c.id} (${c.word})`;
  if (s.cards === 0) {
    assert(!got.found || got.cards.length === 0, `${at}: no card for a word that is not looked up (${s.note})`);
    return;
  }
  assert(got.found, `${at}: the word has a row in the dictionary block of the cloud` + (got.found ? '' : ': ' + JSON.stringify(got.words)));
  const first = got.cards[0];
  if ('cards' in s) eq(got.cards.length, s.cards, `${at}: ${s.cards} cards`);
  if (s.badge === null) {
    assert(got.cards.every(k => !k.pill && !/dspk/.test(k.row) && !k.blockText && !k.second) && !got.header,
           `${at}: drawn as it always was: no pill, no tint, no reading, no header`);
  }
  if (s.badge === 'spoken') {
    assert(first.pill && /^spoken/.test(first.pill), `${at}: a pill that says spoken: ${first.pill}`);
    assert(/dspk/.test(first.row) && first.edge === 'dotted' && first.bg !== 'rgba(0, 0, 0, 0)',
           `${at}: tinted, with a dotted edge (${first.edge}, ${first.bg})`);
  }
  if (s.label_has) assert(norm(first.pill).includes(norm(s.label_has).replace(/'/g, '’')) || norm(first.pill).includes(norm(s.label_has)),
                          `${at}: the pill says "${s.label_has}": ${first.pill}`);
  if (s.written) eq(norm(first.was), norm(s.written), `${at}: the word as written`);
  if (s.reads_as) eq(norm(first.as), norm(s.reads_as), `${at}: the word it was read as`);
  if (s.reason_has) assert(norm(first.why).includes(norm(s.reason_has)), `${at}: the reason in words says "${s.reason_has}": ${first.why}`);
  if (s.senses) {
    const head = s.reads_as || (/([\u0600-\u06ff\u200c]+)\s*$/.exec(s.senses) || [])[1];
    assert(sensesOf(head).length > 0, `${at}: the fixture dictionary has ${head}`);
    eq(first.senses, sensesOf(head), `${at}: ${s.senses}`);
  }
  if ('sound' in s) eq(first.sounded, s.sound, `${at}: the spoken sound`);
  if ('sound_label' in s) {
    if (s.sound_label === null) assert(first.sound && !/formal/.test(first.sound), `${at}: the sound is not labelled formal: ${first.sound}`);
    else assert(first.sound && first.sound.includes(s.sound_label), `${at}: the sound is labelled ${s.sound_label}: ${first.sound}`);
  }
  if (s.pieces_line) eq(norm(first.parts), norm(s.pieces_line), `${at}: the pieces in the order they were read`);
  if (s.header_has) assert(got.header && got.header.includes(s.header_has), `${at}: the header says "${s.header_has}": ${got.header}`);
  if (s.numbered) eq(got.cards.map(k => k.num), got.cards.map((_k, i) => (i + 1) + '.'), `${at}: the readings are numbered`);
  if (s.first) assert(norm(first.head) === norm(s.first), `${at}: the first card is ${s.first}: ${first.head}`);
  if (s.second) assert(norm((got.cards[1] || {}).head) === norm(s.second), `${at}: the second card is ${s.second}: ${(got.cards[1] || {}).head}`);
  if (s.second_line_has) {
    assert(got.cards.some(k => k.second && norm(k.second[1]).includes(norm(s.second_line_has))),
           `${at}: a second line on the card says ${s.second_line_has}: ${JSON.stringify(got.cards.map(k => k.second))}`);
  }
  if (s.names_piece) assert(first.pieces.some(p => p[1] === s.names_piece), `${at}: a piece named ${s.names_piece}: ${JSON.stringify(first.pieces)}`);
  if (s.line_has) assert(norm(first.blockText).includes(s.line_has), `${at}: the block says "${s.line_has}"`);
  if (s.reads_as === undefined && s.badge === 'spoken' && s.first === undefined && !s.pieces_line) { /* nothing more to say */ }
}

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B0 = JSON.parse((await py(BUILD, TMP, JSON.stringify(CASES))).trim().split('\n').pop());
  eq(B0.video.errors, [], 'the copy of the video, as set up, is one the checker has nothing against');
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port)], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  drain(hub.stdout, log); drain(hub.stderr, log);
  const B = `http://127.0.0.1:${port}`;
  {
    const t = Date.now();
    for (;;) {
      try { const r = await fetch(B + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
      if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
      await sleep(250);
    }
  }
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const newContext = async (opts = {}, mode = '') => {
    const ctx = await browser.newContext(Object.assign({viewport: {width: 1280, height: 900}, serviceWorkers: 'block'}, opts));
    await ctx.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => {
      if (route.request().url() === 'https://www.youtube.com/iframe_api')
        return route.fulfill({contentType: 'text/javascript', body: FAKE_YT});
      return route.abort();
    });
    if (mode) await ctx.addCookies([{name: 'parseh_mode', value: mode, url: B}]);
    return ctx;
  };
  const sent = {reader: [], player: []};
  const optional = (status, method, path) => status === 404 && method === 'GET' &&
    (/^\/mt\/[^/]+\/meta\.json$/.test(path) || /^\/youtube\/videos\/[^/]+\/[^/]+\/waveform\.json$/.test(path) ||
     /^\/books\/[^/]+\/[^/]+\/timings\.json$/.test(path) || path === '/favicon.ico');
  async function watch(page, name, surface) {
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host !== `127.0.0.1:${port}` || r.status() < 400) return;
      if (!optional(r.status(), r.request().method(), u.pathname)) errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
    page.on('console', m => {
      if (m.type() !== 'error') return;
      const at = (m.location() || {}).url || '';
      if (/^Failed to load resource/.test(m.text()) && (at.startsWith(B) || !at.startsWith('http://127.0.0.1'))) return;
      errors.push(name + ' console: ' + m.text() + (at ? ' (' + at + ')' : ''));
    });
    page.on('request', r => {
      if (r.method() === 'POST' && /(__lookup|\/youtube\/api\/lookup)$/.test(new URL(r.url()).pathname)) {
        try { sent[surface].push(JSON.parse(r.postData() || '{}')); } catch (_) {}
      }
    });
    page.on('requestfailed', r => {
      const u = new URL(r.url());
      if (u.host === `127.0.0.1:${port}`) errors.push(name + ' request failed: ' + r.method() + ' ' + u.pathname + ' (' + (r.failure() || {}).errorText + ')');
    });
  }
  const context = await newContext();
  const shot = async (page, name) => {
    if (SHOTS) await page.locator('#cloud').first().screenshot({path: `${SHOTS}/${name}.png`});
  };
  const waitLooked = page => page.waitForFunction(() => {
    const c = document.querySelector('#cloud');
    return c && !c.hidden && c.querySelector('.ddict .dw') && !c.querySelector('.dwait');
  }, null, {timeout: 15000});

  /* ---------------- a) the book reader ---------------- */
  console.log('\na) the book reader: every case of panel.json');
  const reader = await context.newPage();
  await watch(reader, 'reader', 'reader');
  await reader.goto(`${B}/books/${B0.book.rel}/reader/`);
  await reader.waitForFunction(() => typeof DICT !== "undefined" && DICT.ready && DICT.words);
  await reader.evaluate(() => { setHover(true); dictSwitch(DICT, dictBtn, 'dict', true); });
  for (const c of B0.cases) {
    await reader.mouse.move(1, 1);
    await reader.evaluate(() => { const c = document.querySelector('#cloud'); if (c) c.hidden = true; });
    await reader.locator(`.p1 [data-c="${c.chunk}"]`).first().hover();
    await reader.waitForFunction(n => cloudC === n && !document.querySelector('#cloud').hidden, c.chunk);
    await waitLooked(reader);
    const got = await reader.evaluate(READ, [c.word]);
    check('reader', c, got);
    await shot(reader, `reader-${c.id}`);
    if (GUIDE && c.id === 'composed') {
      // the card of the word, whole, as a person sees it when the cloud is scrolled to it
      await reader.setViewportSize({width: 1280, height: 1500});
      await sleep(200);
      const h = await reader.evaluateHandle(w => [...document.querySelectorAll('#cloud .ddict .dw')]
        .find(d => d.querySelector('.dwd').textContent.replace(/[\u200c\u200d]/g, '') === w), c.word.replace(/[\u200c\u200d]/g, ''));
      await h.asElement().screenshot({path: `${root}/html-guide/markdown/lookup-and-languages/shots/spoken-panel.png`});
      await reader.setViewportSize({width: 1280, height: 900});
    }
  }
  // for the eye only: the cloud of a spoken word and of two readings in the dark theme, and the phone's sheet
  if (SHOTS) {
    await reader.evaluate(() => Parseh.theme.set('dark'));
    for (const id of ['spoken-by-rule', 'two-readings-two-words']) {
      const c = B0.cases.find(k => k.id === id);
      await reader.mouse.move(1, 1);
      await reader.evaluate(() => { document.querySelector('#cloud').hidden = true; });
      await reader.locator(`.p1 [data-c="${c.chunk}"]`).first().hover();
      await reader.waitForFunction(n => cloudC === n && !document.querySelector('#cloud').hidden, c.chunk);
      await waitLooked(reader);
      await shot(reader, `reader-dark-${id}`);
    }
    await reader.evaluate(() => Parseh.theme.set('light'));
  }
  // the reader's text is the book's: it says nothing of the register
  const asking = sent.reader.filter(b => !b.about && b.text);
  assert(asking.length >= B0.cases.length && asking.every(b => !('register' in b)), 'c) the book sends no register with its lookups');

  /* ---------------- b) the video player ---------------- */
  console.log('\nb) the video player: the same cases');
  const player = await context.newPage();
  await watch(player, 'player', 'player');
  await player.goto(`${B}/youtube/v/${B0.video.id}/`);
  await player.waitForSelector('#segs .seg .fa .w');
  await player.waitForFunction(() => window.__yt && document.querySelector('#novid').hidden);
  await player.waitForFunction(() => !document.querySelector('#dictmode').hidden);
  if (!(await player.evaluate(() => document.querySelector('#dictmode').classList.contains('on')))) await player.click('#dictmode');
  for (const c of B0.cases) {
    await player.mouse.move(1, 1);
    await player.waitForFunction(() => document.querySelector('#cloud').hidden || document.querySelector('#cloud').classList.contains('editing'));
    const sel = `#segs .seg[data-i="${c.seg}"] .fa .w[data-j="0"]`;
    await player.evaluate(i => {
      const seg = document.querySelector(`#segs .seg[data-i="${i}"]`), r = seg.getBoundingClientRect();
      const top = document.querySelector('#playerwrap').getBoundingClientRect().bottom;
      scrollBy({top: r.top + r.height / 2 - (top + innerHeight) / 2, behavior: 'instant'});
    }, c.seg);
    await sleep(120);
    await player.locator(sel).hover();
    await player.waitForFunction(s => {
      const cl = document.querySelector('#cloud'), w = document.querySelector(s);
      return !cl.hidden && w && w.classList.contains('hot');
    }, sel);
    await waitLooked(player);
    const got = await player.evaluate(READ, [c.word]);
    check('player', c, got);
    await shot(player, `player-${c.id}`);
  }
  const asked = sent.player.filter(b => !b.about && b.text);
  assert(asked.length >= B0.cases.length && asked.every(b => b.register === 'spoken'), 'c) the player says its captions are speech, in every lookup of a caption it asks');

  /* ---------------- the editor's sources ---------------- */
  console.log('\nthe editor\'s sources column says it too');
  {
    const c = B0.cases.find(k => k.id === 'spoken-by-rule');
    // the book's chunk sheet: the dictionary's rows beside the fields, each with its buttons
    await reader.evaluate(n => { openChunk(n, document.querySelector(`.row[data-c="${n}"]`) || rowOf(n)); sideShow(true); }, c.chunk);
    await until(() => reader.evaluate(() => !!document.querySelector('#chsrcbody .srow .dspoken')), 'the sheet\'s sources hold a spoken block');
    eq(await reader.evaluate(() => [...document.querySelectorAll('#chsrcbody .srow .dspoken .das')].map(e => e.textContent.replace(/\u200c/g, ''))
         .filter(t => t === 'خانه').length > 0), true, 'the book\'s sources: a row of the word read as خانه says what it was read as');
    await reader.evaluate(() => closeChunk());
    // the player's edit cloud, with its sources
    await player.mouse.move(1, 1);
    const sel = `#segs .seg[data-i="${c.seg}"] .fa .w[data-j="0"]`;
    await player.evaluate(i => document.querySelector(`#segs .seg[data-i="${i}"]`).scrollIntoView({block: 'center'}), c.seg);
    await sleep(150);
    await player.locator(sel).hover();
    await player.waitForSelector('#cloud .mkedit', {state: 'visible'});
    await player.click('#cloud .mkedit');
    await player.waitForSelector('#cloud .esrc', {state: 'visible'});
    if (await player.evaluate(() => document.querySelector('#cloud .eside').hidden)) await player.click('#cloud .esrc');
    await until(() => player.evaluate(() => !!document.querySelector('#cloud .eside .srow .dspoken')), 'the player\'s sources hold a spoken block');
    assert(await player.evaluate(() => [...document.querySelectorAll('#cloud .eside .srow .dspoken .das')]
             .some(e => e.textContent.replace(/\u200c/g, '') === 'خانه')), 'the player\'s sources: a row of the word read as خانه says what it was read as');
    await player.keyboard.press('Escape');
  }

  /* ---------------- d) the phone ---------------- */
  console.log('\nd) the phone\'s sheet draws the same block');
  {
    const ctx = await newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true}, 'mobile');
    const phone = await ctx.newPage();
    await watch(phone, 'phone', 'player');
    await phone.goto(`${B}/books/${B0.book.rel}/reader/`);
    await phone.waitForFunction(() => typeof DICT !== "undefined" && DICT.ready && DICT.words);
    const c = B0.cases.find(k => k.id === 'spoken-by-rule');
    await phone.evaluate(() => { setHover(true); dictSwitch(DICT, dictBtn, 'dict', true); });
    await phone.evaluate(n => { const el = document.querySelector(`.p1 [data-c="${n}"]`); el.scrollIntoView({block: 'center'}); el.click(); }, c.chunk);
    await until(() => phone.evaluate(() => !!document.querySelector('.m-dsheet .dspoken')), 'the phone\'s sheet holds the spoken block');
    const inside = await phone.evaluate(() => {
      const b = document.querySelector('.m-dsheet .dspoken').getBoundingClientRect();
      return b.left >= 0 && b.right <= innerWidth + 0.5 && b.width > 0;
    });
    assert(inside, 'the spoken block is inside the phone\'s screen');
    if (SHOTS) await phone.screenshot({path: `${SHOTS}/phone-sheet.png`});
    await ctx.close();
  }

  /* ---------------- e) ---------------- */
  console.log('\ne) what the pages and the hub said');
  assert(!errors.length, 'no page threw, logged an error or had a request refused: ' + errors.join('; '));
  assert(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq(ownAfter.leaks, [], 'nothing of this run\'s tree was remembered in the owner\'s config/digests.json or wheres.json');
  eq(ownAfter.digests, ownBefore.digests, 'the owner\'s config/, books/, youtube/videos/ and the fixtures are untouched');
  console.log(`\nfa_colloquial_panel: ${passed} checks passed`);
} finally {
  if (errors.length) console.log('what the pages said:\n  ' + errors.join('\n  '));
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept ' + TMP);
}
