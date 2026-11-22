// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/ar_dialect_everywhere.mjs
//      PARSEH_KEEP=1 keeps the temporary tree
//
// THE VARIETY EVERYWHERE (a0.6.3, TO-DO 12.28, 12.34, 12.32), driven on the REAL hub: serve.main() over a temporary tree
// with the Arabic fixture book and video and two small dictionaries (standard Arabic's and Egyptian's, dict/ar.egy.db).
// Every choice is made with the page's own controls; what is asserted is what the pages draw and what is on disk.
//
//  a) a studio document: its info offers the five-way choice; Egyptian chosen is written into its front matter; the
//     library's card says so; the editor's buffer carries it and the exercise prompt made from it names the dialect
//  b) the studio's prompt page: Arabic then Levantine chosen; the prompt names it and asks for `variety: lev`
//  c) an exercise deck: its head offers the choice; Gulf chosen is in deck.json; the decks page's card says so
//  d) Settings -> Languages: Arabic's four varieties as sub-rows, the dictionary fetched for Egyptian only
//  e) the cards: the book's on the library and the phone's shelf, the video's on the index and the phone's channel
//  f) adding a video in Egyptian: the page says which caption track to take (arz), and nothing for the standard
//  g) a book made in place: its instructions, with Moroccan chosen on the add page, name the dialect
//  h) no page threw or had a request refused; the hub printed no traceback; the owner's files are untouched
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-ar-everywhere-'});
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

const BUILD = String.raw`
import json, os, shutil, subprocess, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['youtube/lib', 'lib', 'tests']
import lookup
tmp = Path(sys.argv[1])
root = tmp / 'root'
for d in (root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises', tmp / 'anki', tmp / 'tray', tmp / 'config',
          tmp / 'dict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
def dictionary(path, rows):
    c = lookup.create(path)
    for head, pos, sense in rows:
        cur = c.execute("INSERT INTO entry (headword, pos, sense, sense_tags) VALUES (?,?,?,?)", (head, pos, sense, ""))
        c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (head, cur.lastrowid, ""))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)", [("lang", "ar"), ("source", "a fixture"), ("licence", "none"), ("entries", "1")])
    c.commit(); c.close()
dictionary(str(tmp / 'dict' / 'ar.db'), [("كتب", "verb", "to write")])
dictionary(str(tmp / 'dict' / 'ar.egy.db'), [("دلوقتي", "adv", "now")])
out = {}
vid = 'aR5nJ3xW7yZ'
d = root / 'youtube' / 'videos' / 'arabic' / vid
shutil.copytree(str(REPO / 'tests/fixtures/videos/arabic' / vid), str(d))
out['video'] = {'id': vid, 'json': str(d / 'video.json')}
rel = 'arabic/mini-ar'
b = root / 'books' / rel
shutil.copytree(str(REPO / 'tests/fixtures/books' / rel), str(b), ignore=shutil.ignore_patterns('reader', '.reader-key', 'source'))
r = subprocess.run([sys.executable, 'lib/tex2html.py', '--book', str(b)], capture_output=True, text=True)
if r.returncode:
    raise SystemExit(r.stderr or r.stdout)
out['book'] = {'rel': rel, 'json': str(b / 'book.json')}
print(json.dumps(out, ensure_ascii=False))
`;
// serve.main() over the temporary tree, every store in there (the harness of tests/vocline_video.mjs), with the fixture's dictionary
const SERVE = String.raw`
import sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.']
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
import mobile_harness
def write_library(self):
    try:
        mobile_harness.library_page(tmp / 'root')
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "error": ""}
serve.Handler._write_library = write_library
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
const DOC = '---\ntitle: Fi el-maktab\nlang: en\ntarget: ar\n---\n\n## Words\n\n[دلوقتي]{tl} now.\n\n:::exercise true-false\nprompt: [دلوقتي]{tl} means now.\n- It does. => true\n:::\n';

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B0 = JSON.parse((await py(BUILD, TMP)).trim().split('\n').pop());
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
  await context.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => route.abort());
  const watch = (page, name) => {
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host !== `127.0.0.1:${port}` || r.status() < 400) return;
      if (r.status() === 404 && r.request().method() === 'GET' && /favicon|\/mt\/|waveform\.json$|timings\.json$/.test(u.pathname)) return;
      errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
  };
  const open = async (url, name, ctx = context) => {
    const p = await ctx.newPage();
    watch(p, name);
    await p.goto(B + url);
    return p;
  };
  const post = async (url, body) => (await fetch(B + url, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)})).json();
  const text = (p, sel) => p.evaluate(s => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; }, sel);
  const options = (p, sel) => p.evaluate(s => [...document.querySelectorAll(s + ' option')].map(o => o.textContent), sel);
  const FIVE = ['Modern Standard Arabic', 'Egyptian Arabic', 'Levantine Arabic', 'Gulf Arabic', 'Moroccan Arabic'];

  /* ---------------- a) a studio document ---------------- */
  console.log('\na) a studio document');
  const made = await post('/studio/api/docs', {markdown: DOC});
  const docId = made.meta.id;
  const docDir = `${TMP}/library/arabic/${docId}`;
  const doc = await open(`/studio/doc/${docId}`, 'document');
  await doc.waitForSelector('#variety-edit:not([hidden])');
  eq(await options(doc, '#doc-variety'), FIVE, 'its info offers the standard language and the four dialects');
  eq(await doc.inputValue('#doc-variety'), '', 'on the standard language at first (no `variety` in an old document)');
  await doc.selectOption('#doc-variety', 'egy');
  await until(() => text(doc, '#variety-said').then(t => /saved/.test(t || '')), 'saved');
  const src = await Deno.readTextFile(`${docDir}/source.md`);
  assert(/\ntarget: ar\nvariety: egy\n---/.test(src), 'Egyptian is written into its front matter: ' + JSON.stringify(src.slice(0, 80)));
  eq(JSON.parse(await Deno.readTextFile(`${docDir}/meta.json`)).variety, 'egy', 'and into meta.json');
  await doc.reload();
  await doc.waitForSelector('#variety-edit:not([hidden])');
  eq(await doc.inputValue('#doc-variety'), 'egy', 'a reload shows Egyptian');
  const lib = await open('/studio/', 'studio library');
  await lib.waitForSelector(`.card[data-id="${docId}"]`);
  eq(await text(lib, `.card[data-id="${docId}"] .badge.variety`), 'Egyptian Arabic', 'the library\'s card says Egyptian Arabic');
  const ed = await open(`/studio/doc/${docId}/edit`, 'editor');
  await ed.waitForFunction(() => /variety: egy/.test(document.querySelector('#src').value));
  const ex = await ed.evaluate(async (base) => {
    const r = await fetch(base + '/studio/api/exercise-prompt', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: document.querySelector('#src').value})});
    return r.json();
  }, B);
  assert(/This text is in Egyptian Arabic/.test(ex.prompt || ''), 'the exercise prompt made from the editor\'s buffer names Egyptian Arabic');
  assert(ex.skill && ex.skill.available && /· variety: Egyptian Arabic \(egy\)/.test(ex.skill.text.split('\n')[0]),
         'and so does the skill\'s request: ' + (ex.skill && (ex.skill.text || ex.skill.why || '').split('\n')[0]));
  await ed.close();
  await doc.selectOption('#doc-variety', '');
  await until(async () => !/variety:/.test(await Deno.readTextFile(`${docDir}/source.md`)), 'the line taken out');
  assert(true, 'the standard language again takes the line out');

  /* ---------------- b) the prompt page ---------------- */
  console.log('\nb) the studio\'s prompt page');
  const pp = await open('/studio/prompt', 'prompt page');
  await pp.waitForFunction(() => document.querySelector('#prompt-text').value.length > 100);
  await pp.selectOption('#prompt-target', 'ar');
  await pp.waitForSelector('#prompt-variety-lbl:not([hidden])');
  eq(await options(pp, '#prompt-variety'), FIVE, 'Arabic chosen, "written in" offers the five');
  await pp.selectOption('#prompt-variety', 'lev');
  await pp.waitForFunction(() => /This text is in Levantine Arabic/.test(document.querySelector('#prompt-text').value));
  assert(/`variety: lev`/.test(await pp.inputValue('#prompt-text')), 'Levantine chosen, the prompt asks for `variety: lev` in the front matter');
  await pp.selectOption('#prompt-target', 'it');
  await pp.waitForFunction(() => document.querySelector('#prompt-variety-lbl').hidden &&
    /Italian/.test(document.querySelector('#prompt-text').value) && !/This text is in/.test(document.querySelector('#prompt-text').value));
  assert(true, 'Italian chosen, the row is gone and the prompt names no variety');

  /* ---------------- c) an exercise deck ---------------- */
  console.log('\nc) an exercise deck');
  const dk = (await post('/exercises/api/decks', {name: 'Khaleeji', lang: 'ar'})).deck;
  eq(dk.variety, '', 'a new deck is on the standard language');
  const deckJson = `${TMP}/exercises/${dk.folder}/${dk.slug}/deck.json`;
  const deck = await open(`/exercises/deck/${dk.folder}/${dk.slug}`, 'deck');
  await deck.waitForSelector('#deck-variety-lbl:not([hidden])');
  eq(await options(deck, '#deck-variety'), FIVE, 'its head offers the five');
  await deck.selectOption('#deck-variety', 'gulf');
  await until(async () => JSON.parse(await Deno.readTextFile(deckJson)).variety === 'gulf', 'deck.json says gulf');
  assert(true, 'Gulf chosen is written into deck.json');
  await deck.reload();
  await deck.waitForSelector('#deck-variety-lbl:not([hidden])');
  eq(await deck.inputValue('#deck-variety'), 'gulf', 'a reload shows Gulf');
  const decksPage = await open('/exercises/', 'decks');
  await decksPage.waitForSelector('.dk-card .badge.variety');
  eq(await text(decksPage, '.dk-card .badge.variety'), 'Gulf Arabic', 'the decks page\'s card says Gulf Arabic');

  /* ---------------- d) Settings -> Languages ---------------- */
  console.log('\nd) Settings → Languages');
  const lg = await open('/settings/languages/', 'languages');
  await lg.waitForSelector('details.lang[data-code="ar"]');
  await lg.click('details.lang[data-code="ar"] > summary');
  const vars = await lg.evaluate(() => [...document.querySelectorAll('details.lang[data-code="ar"] details.var')].map(d => ({
    key: d.getAttribute('data-variety'), name: d.querySelector('.nm').textContent,
    rows: Object.fromEntries([...d.querySelectorAll('.feats li')].map(li => [li.getAttribute('data-feature'), li.className]))})));
  eq(vars.map(v => v.name), FIVE.slice(1), 'Arabic has the four varieties as sub-rows');
  eq([vars[0].rows.dictionary, vars[1].rows.dictionary], ['have', 'optional'],
     'Egyptian\'s dictionary is fetched (dict/ar.egy.db), Levantine\'s is not');
  eq(vars.map(v => v.rows['lookup-rules']), ['have', 'have', 'have', 'have'], 'each has its lookup rules');
  eq(await lg.evaluate(() => document.querySelectorAll('details.lang[data-code="it"] details.var').length), 0, 'Italian has none');
  await lg.click('details.lang[data-code="ar"] details.var[data-variety="egy"] > summary');
  assert(await lg.evaluate(() => { const li = document.querySelector('details.var[data-variety="egy"] li[data-feature="captions"]');
    return !!li && li.offsetParent !== null && /arz/.test(li.textContent); }), 'Egyptian\'s rows open, its caption track (arz) said');

  /* ---------------- e) the cards ---------------- */
  console.log('\ne) the cards');
  const rd = await open(`/books/${B0.book.rel}/reader/`, 'reader');
  const said = await rd.evaluate(async () => (await fetch('__variety', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({variety: 'mor'})})).json());
  eq(said.variety, 'mor', 'the reader\'s door writes Moroccan');
  const shelf = await open('/books/', 'library');
  eq(await text(shelf, 'a.book [data-variety="mor"]'), 'Moroccan Arabic', 'the library\'s card says Moroccan Arabic');
  const phone = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, serviceWorkers: 'block'});
  await phone.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => route.abort());
  const mshelf = await open('/m/books/', 'phone shelf', phone);
  eq(await text(mshelf, '[data-variety="mor"]'), 'Moroccan Arabic', 'and so does the phone\'s shelf');
  eq((await post('/youtube/api/variety', {video: B0.video.id, variety: 'lev'})).variety, 'lev', 'the player\'s door writes Levantine');
  const idx = await open('/youtube/', 'video index');
  eq(await text(idx, '[data-variety="lev"]'), 'Levantine Arabic', 'the video\'s card on the index says Levantine Arabic');
  const mv = await open('/m/videos/', 'phone channels', phone);
  const chan = await mv.evaluate(() => { const a = document.querySelector('a[href^="/m/videos/"][href$="/"]:not([href="/m/videos/"])');
    return a && a.getAttribute('href'); });
  const mc = await open(chan, 'phone channel', phone);
  eq(await text(mc, '[data-variety="lev"]'), 'Levantine Arabic', 'and the phone\'s channel page');

  /* ---------------- f) adding a video ---------------- */
  console.log('\nf) adding a video in a dialect');
  const add = await open('/youtube/add/', 'add a video');
  await add.selectOption('#lang', 'ar');
  await add.waitForSelector('#variety_lbl:not([hidden])');
  assert(await add.evaluate(() => document.querySelector('#tracknote').hidden), 'the standard language: no word about tracks');
  await add.selectOption('#variety', 'egy');
  const note = await add.evaluate(() => { const n = document.querySelector('#tracknote'); return n.hidden ? null : n.textContent; });
  assert(note && /Egyptian Arabic track \(arz\)/.test(note) && /Arabic’s otherwise/.test(note),
         'Egyptian chosen, the page says to take the arz track, Arabic\'s otherwise: ' + note);
  await add.selectOption('#lang', 'it');
  assert(await add.evaluate(() => document.querySelector('#tracknote').hidden), 'Italian chosen, the word is gone');

  /* ---------------- g) a book made in place ---------------- */
  console.log('\ng) a book made in place');
  const nb = await open('/books/add/', 'add a book');
  await nb.selectOption('#lang', 'ar');
  await nb.waitForSelector('#variety_lbl:not([hidden])');
  await nb.selectOption('#variety', 'mor');
  const ins = await nb.evaluate(async () => {
    const r = await fetch('/books/__making/instructions', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({book: {lang: document.querySelector('#lang').value, gloss: 'en', title: 'كتاب', title_latin: 'Ktab',
        variety: document.querySelector('#variety').value, original: 'a.txt'}})});
    return r.json();
  });
  assert(ins.ok && /This text is in Moroccan Arabic/.test(ins.text), 'the instructions name Moroccan Arabic');
  assert(ins.skill && ins.skill.available && /· variety: Moroccan Arabic \(mor\)/.test(ins.skill.text.split('\n')[0]),
         'and so does the skill\'s request');

  /* ---------------- h) ---------------- */
  console.log('\nh) what the pages and the hub said');
  assert(!errors.length, 'no page threw or had a request refused: ' + errors.join('; '));
  assert(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq(ownAfter.digests, ownBefore.digests, 'the owner\'s config/, books/, youtube/videos/ and the fixtures are untouched');
  console.log(`\nar_dialect_everywhere: ${passed} checks passed`);
} finally {
  if (errors.length) console.log('what the pages said:\n  ' + errors.join('\n  '));
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept ' + TMP);
}
