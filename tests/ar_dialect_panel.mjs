// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/ar_dialect_panel.mjs
//      PARSEH_KEEP=1 keeps the temporary tree
//
// AN ARABIC TEXT IN A DIALECT (a0.6.1), driven in the book reader and in the video player on the REAL hub: serve.main()
// over a temporary tree with two small Arabic dictionaries built here (the standard one, and Egyptian's: dict/ar.egy.db),
// a copy of the Arabic fixture book and video, two chunks and two captions of which are the sentence `هيكتب دلوقتي`.
// Every action is the page's own: the dictionary switched on, a chunk hovered, the variety chosen in the cloud.
//
//  a) in the reader: the dictionary block has a "written in" row, on the standard language at first; read as standard,
//     دلوقتي is not found and هيكتب finds no verb; Egyptian chosen in the row is written into book.json; the next chunk
//     finds دلوقتي in Egyptian's dictionary, its card saying so, and هيكتب as كتب through the future's ha-
//  b) the same in the player, written into video.json
//  c) a language without varieties shows no row, and asks nothing about them
//  d) no page threw or had a request refused; the hub printed no traceback; the owner's files are untouched
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-ar-dialect-'});
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

const SENTENCE = 'هيكتب دلوقتي';
const BUILD = String.raw`
import json, os, shutil, subprocess, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['youtube/lib', 'lib', 'tests']
import annwrite, check_annotations as CA, lookup, texwrite
tmp, text = Path(sys.argv[1]), sys.argv[2]
root = tmp / 'root'
for d in (root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises', tmp / 'anki', tmp / 'tray', tmp / 'config',
          tmp / 'dict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
def dictionary(path, rows):
    c = lookup.create(path)
    for head, pos, sense, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, pos, sense, sense_tags) VALUES (?,?,?,?)", (head, pos, sense, ""))
        for f in [head] + forms:
            c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (f, cur.lastrowid, ""))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)", [("lang", "ar"), ("source", "a fixture"), ("licence", "none")])
    c.commit(); c.close()
dictionary(str(tmp / 'dict' / 'ar.db'), [("كتب", "verb", "to write", ["يكتب"]), ("وقت", "noun", "time", [])])
dictionary(str(tmp / 'dict' / 'ar.egy.db'), [("دلوقتي", "adv", "now", [])])
out = {}
vid = 'aR5nJ3xW7yZ'
d = root / 'youtube' / 'videos' / 'arabic' / vid
shutil.copytree(str(REPO / 'tests/fixtures/videos/arabic' / vid), str(d))
ann = annwrite.read(str(d))
first = len(ann['segments'])
last = max(sg['start'] for sg in ann['segments'])
for k in range(2):
    ann['segments'].append({'start': last + 2 * (k + 1), 'text': text, 'chunks': [{'fa': text}]})
annwrite.write(str(d), ann)
caps = [{'start': sg['start'], 'text': sg['text'], 'chapter': sg.get('chapter')} for sg in ann['segments']]
(d / 'transcript.txt').write_text(CA.transcript_text(caps), encoding='utf-8')
meta = json.loads((d / 'video.json').read_text(encoding='utf-8'))
meta['duration'] = '9:00'
(d / 'video.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
out['video'] = {'id': vid, 'segs': [first, first + 1], 'json': str(d / 'video.json')}
rel = 'arabic/mini-ar'
b = root / 'books' / rel
shutil.copytree(str(REPO / 'tests/fixtures/books' / rel), str(b), ignore=shutil.ignore_patterns('reader', '.reader-key', 'source'))
for k in (0, 1):
    texwrite.edit_chunk(str(b / 'ch1.tex'), k, {'fa': text, 'tr': '', 'voc': '', 'en': ''})
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', str(b)], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr or r.stdout)
rdr = b / 'reader'
climb = os.path.relpath(str(REPO), str(rdr)).replace(os.sep, '/') + '/'
for name in os.listdir(str(rdr)):
    if name.endswith('.html'):
        pth = rdr / name
        pth.write_text(pth.read_text(encoding='utf-8').replace(climb, '/'), encoding='utf-8')
out['book'] = {'rel': rel, 'json': str(b / 'book.json')}
# c) a book of a language without varieties
rel2 = 'italian/mini-it'
b2 = root / 'books' / rel2
shutil.copytree(str(REPO / 'tests/fixtures/books' / rel2), str(b2), ignore=shutil.ignore_patterns('reader', '.reader-key', 'source'))
texwrite.edit_chunk(str(b2 / 'ch1.tex'), 0, {'fa': 'la casa', 'tr': '', 'voc': '', 'en': ''})
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', str(b2)], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr or r.stdout)
for name in os.listdir(str(b2 / 'reader')):
    if name.endswith('.html'):
        pth = b2 / 'reader' / name
        climb2 = os.path.relpath(str(REPO), str(b2 / 'reader')).replace(os.sep, '/') + '/'
        pth.write_text(pth.read_text(encoding='utf-8').replace(climb2, '/'), encoding='utf-8')
dictionary(str(tmp / 'dict' / 'it.db'), [("casa", "noun", "house", [])])
out['other'] = {'rel': rel2}
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


// the cards of one word in the open cloud, as drawn
const CARDS = ([word]) => {
  const dw = [...document.querySelectorAll('#cloud .ddict .dw')].find(d => d.querySelector('.dwd').textContent.trim() === word);
  if (!dw) return null;
  return [...dw.querySelectorAll(':scope > .dhit')].map(h => ({
    head: (h.querySelector('.dhead2') || {textContent: ''}).textContent.trim().split(' ')[0],
    note: (h.querySelector('.dnote') || {textContent: ''}).textContent}));
};
const ROW = () => {
  const r = document.querySelector('#cloud .ddict .dvariety select');
  return r ? {value: r.value, options: [...r.options].map(o => o.textContent)} : null;
};

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B0 = JSON.parse((await py(BUILD, TMP, SENTENCE)).trim().split('\n').pop());
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
  const context = await browser.newContext({viewport: {width: 1280, height: 900}, serviceWorkers: 'block'});
  await context.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => {
    if (route.request().url() === 'https://www.youtube.com/iframe_api')
      return route.fulfill({contentType: 'text/javascript', body: FAKE_YT});
    return route.abort();
  });
  const varietyAsks = [];
  const watch = (page, name) => {
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host !== `127.0.0.1:${port}` || r.status() < 400) return;
      if (r.status() === 404 && r.request().method() === 'GET' &&
          (/\/mt\//.test(u.pathname) || /waveform\.json$|timings\.json$|favicon/.test(u.pathname))) return;
      errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
    page.on('request', r => { if (/(__variety|\/youtube\/api\/variety)$/.test(new URL(r.url()).pathname)) varietyAsks.push(name); });
  };
  const waitLooked = page => page.waitForFunction(() => {
    const c = document.querySelector('#cloud');
    return c && !c.hidden && c.querySelector('.ddict .dw') && !c.querySelector('.dwait');
  }, null, {timeout: 15000});
  const readJson = async p => JSON.parse(await Deno.readTextFile(p));

  /* ---------------- a) the reader ---------------- */
  console.log('\na) the book reader');
  const reader = await context.newPage();
  watch(reader, 'reader');
  await reader.goto(`${B}/books/${B0.book.rel}/reader/`);
  await reader.waitForFunction(() => typeof DICT !== "undefined" && DICT.ready && DICT.words);
  await reader.evaluate(() => { setHover(true); dictSwitch(DICT, dictBtn, 'dict', true); });
  const hoverChunk = async n => {
    await reader.mouse.move(1, 1);
    await reader.evaluate(() => { const c = document.querySelector('#cloud'); if (c) c.hidden = true; });
    await reader.locator(`.p1 [data-c="${n}"]`).first().hover();
    await reader.waitForFunction(k => cloudC === k && !document.querySelector('#cloud').hidden, n);
    await waitLooked(reader);
  };
  await hoverChunk(0);
  const row = await until(() => reader.evaluate(ROW), 'the variety row in the reader\'s dictionary block');
  eq(row.value, '', 'the row says the standard language at first');
  eq(row.options, ['Modern Standard Arabic', 'Egyptian Arabic', 'Levantine Arabic', 'Gulf Arabic', 'Moroccan Arabic'],
     'and offers the four dialects');
  eq(await reader.evaluate(CARDS, ['دلوقتي']), [], 'read as standard Arabic, دلوقتي is not found');
  eq(await reader.evaluate(CARDS, ['هيكتب']), [], 'and هيكتب finds no verb');
  await reader.selectOption('#cloud .ddict .dvariety select', 'egy');
  await until(() => reader.evaluate(() => /saved/.test(document.querySelector('#cloud .dvariety').textContent)), 'saved');
  eq((await readJson(B0.book.json)).variety, 'egy', 'the choice is written into book.json');
  await hoverChunk(1);
  const now = await reader.evaluate(CARDS, ['دلوقتي']);
  assert(now && now[0].head === 'دلوقتي' && /^ — Egyptian Arabic/.test(now[0].note),
         'the next chunk finds دلوقتي in Egyptian\'s dictionary, and its card says so: ' + JSON.stringify(now));
  const verb = await reader.evaluate(CARDS, ['هيكتب']);
  assert(verb && verb[0].head === 'كتب', 'and هيكتب as كتب, the future\'s ha- taken off: ' + JSON.stringify(verb));
  eq(await reader.evaluate(ROW).then(r => r.value), 'egy', 'the row says Egyptian now');

  /* ---------------- b) the player ---------------- */
  console.log('\nb) the video player');
  const player = await context.newPage();
  watch(player, 'player');
  await player.goto(`${B}/youtube/v/${B0.video.id}/`);
  await player.waitForSelector('#segs .seg .fa .w');
  await player.waitForFunction(() => window.__yt && document.querySelector('#novid').hidden);
  await player.waitForFunction(() => !document.querySelector('#dictmode').hidden);
  if (!(await player.evaluate(() => document.querySelector('#dictmode').classList.contains('on')))) await player.click('#dictmode');
  const hoverSeg = async i => {
    await player.mouse.move(1, 1);
    await player.waitForFunction(() => document.querySelector('#cloud').hidden || document.querySelector('#cloud').classList.contains('editing'));
    const sel = `#segs .seg[data-i="${i}"] .fa .w[data-j="0"]`;
    await player.evaluate(k => {
      const seg = document.querySelector(`#segs .seg[data-i="${k}"]`), r = seg.getBoundingClientRect();
      const top = document.querySelector('#playerwrap').getBoundingClientRect().bottom;
      scrollBy({top: r.top + r.height / 2 - (top + innerHeight) / 2, behavior: 'instant'});
    }, i);
    await sleep(120);
    await player.locator(sel).hover();
    await player.waitForFunction(s => { const cl = document.querySelector('#cloud'), w = document.querySelector(s);
      return !cl.hidden && w && w.classList.contains('hot'); }, sel);
    await waitLooked(player);
  };
  await hoverSeg(B0.video.segs[0]);
  const prow = await until(() => player.evaluate(ROW), 'the variety row in the player\'s dictionary block');
  eq(prow.value, '', 'the player\'s row says the standard language at first');
  eq(await player.evaluate(CARDS, ['دلوقتي']), [], 'and دلوقتي is not found');
  await player.selectOption('#cloud .ddict .dvariety select', 'egy');
  await until(() => player.evaluate(() => /saved/.test(document.querySelector('#cloud .dvariety').textContent)), 'saved');
  eq((await readJson(B0.video.json)).variety, 'egy', 'the choice is written into video.json');
  await hoverSeg(B0.video.segs[1]);
  const pnow = await player.evaluate(CARDS, ['دلوقتي']);
  assert(pnow && pnow[0].head === 'دلوقتي' && /Egyptian Arabic/.test(pnow[0].note),
         'the next caption finds دلوقتي in Egyptian\'s dictionary: ' + JSON.stringify(pnow));
  await player.selectOption('#cloud .ddict .dvariety select', '');
  await until(() => player.evaluate(() => /saved/.test(document.querySelector('#cloud .dvariety').textContent)), 'saved again');
  assert(!('variety' in (await readJson(B0.video.json))), 'the standard language again takes `variety` out of video.json');

  /* ---------------- c) a language without varieties ---------------- */
  console.log('\nc) a language without varieties');
  const before = varietyAsks.length;
  const other = await context.newPage();
  watch(other, 'italian reader');
  await other.goto(`${B}/books/${B0.other.rel}/reader/`);
  await other.waitForFunction(() => typeof DICT !== "undefined" && DICT.ready && DICT.words);
  await other.evaluate(() => { setHover(true); dictSwitch(DICT, dictBtn, 'dict', true); });
  await other.locator('.p1 [data-c="0"]').first().hover();
  await other.waitForFunction(() => !document.querySelector('#cloud').hidden && document.querySelector('#cloud .ddict'));
  await sleep(400);
  eq(await other.evaluate(ROW), null, 'an Italian reader shows no variety row');
  eq(varietyAsks.length, before, 'and asks nothing about varieties');

  /* ---------------- d) ---------------- */
  console.log('\nd) what the pages and the hub said');
  assert(!errors.length, 'no page threw or had a request refused: ' + errors.join('; '));
  assert(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq(ownAfter.digests, ownBefore.digests, 'the owner\'s config/, books/, youtube/videos/ and the fixtures are untouched');
  console.log(`\nar_dialect_panel: ${passed} checks passed`);
} finally {
  if (errors.length) console.log('what the pages said:\n  ' + errors.join('\n  '));
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept ' + TMP);
}
