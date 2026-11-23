// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/tex_specials.mjs
//      PARSEH_KEEP=1 keeps the temporary tree
//
// "50%" AND "R&D" IN A BOOK, FROM THE PAGES (TO-DO §6.5, §6.6).  Until a0.6.3
// the add refused a text holding any of \ { } $ % & # _ ^ ~ ("Take it out of
// the text (or spell it in words)"), and the chunk sheet would not save one.
// Now the chapter holds their LaTeX escapes and everything that reads it
// gives them back as typed (lib/texesc.py).  On the REAL hub -- serve.main()
// over a temporary tree, the harness of tests/draft_end_to_end.mjs -- for
// English and for Persian (right to left):
//   - /books/add/ "Write it here, by hand", "Make the draft" takes the text
//     and opens the reader; ch1.tex holds 50\% and R\&D;
//   - the reader's row and the chunk sheet's text box hold the text as typed;
//   - a meaning typed with every special in it is saved, read back as typed
//     by texwrite and by the reader, and written escaped into the .tex;
//   - the reader opened again agrees; verify_book reproduces the source;
//   - the owner's config/, books/ and the fixtures are untouched.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-tex-specials-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));

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
import json, os, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['lib']
tmp = Path(sys.argv[1])
root = tmp / 'root'
for d in (root / 'books', root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises',
          tmp / 'anki', tmp / 'tray', tmp / 'config', tmp / 'nodict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
import words
print(json.dumps({'root': str(root), 'words': {c: words.available(c) for c in ('ja', 'zh')}}))
`;
const SERVE = String.raw`
import os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
REPO = os.getcwd()
import prefs, network, offline
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
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
import lookup, corpus, getmt
lookup.DICT_DIR = str(tmp / 'nodict')
corpus.CORPUS_DIR = str(tmp / 'nocorpus')
getmt.MT_DIR = str(tmp / 'nomt')
getmt.ENGINE_DIR = str(tmp / 'nomt' / 'engine')
# and speech to text (optional, the add page's): none installed, whatever this machine has
import getstt
getstt.STT_DIR = str(tmp / 'nostt')
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
// every chunk of a chapter file as texwrite reads it
const CHUNKS = String.raw`
import json, sys
sys.path.insert(0, 'lib')
import texwrite
print(json.dumps(texwrite.read_chunks(sys.argv[1]), ensure_ascii=False))
`;
const chunksOf = async path => JSON.parse(await py(CHUNKS, path));
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

// The books: a spaced language left to right and one right to left.  Each
// text holds the specials once refused at the add.
const BOOKS = [
  {code: 'en', folder: 'english', slug: 'fifty-per-cent', title: 'Fifty per cent', title_latin: 'Fifty per cent',
   text: 'It costs 50% of the R&D budget.\n\nItem #1 costs $5 and a_b is {here}.',
   rowFa: 'It costs 50% of the R&D budget.'},
  {code: 'fa', folder: 'persian', slug: 'panjah-dar-sad', title: 'پنجاه درصد', title_latin: 'Panjah dar sad',
   text: 'پنجاه درصد یعنی 50% و R&D هم هست.\n\nاین {متن} و $5 و #1 است.',
   rowFa: 'پنجاه درصد یعنی 50% و R&D هم هست.'},
];
const MEANING = 'half & half, 100% {sure} ~ ^ _ # $ \\ done';

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B0 = JSON.parse((await py(BUILD, TMP)).trim().split('\n').pop());
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  drain(hub.stdout, log); drain(hub.stderr, log);
  const B = `http://127.0.0.1:${port}`;
  for (const t = Date.now();;) {
    try { const r = await fetch(B + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  await context.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => route.abort());
  const optional = (status, path) => status === 404 &&
    (/\/timings\.json$/.test(path) || /^\/mt\//.test(path) || path === '/favicon.ico');
  async function open(url, name) {
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host === `127.0.0.1:${port}` && r.status() >= 400 && !optional(r.status(), u.pathname))
        errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
    await page.goto(B + url);
    return page;
  }
  const readerReady = page => page.waitForFunction(
    () => typeof SRC !== 'undefined' && window.Parseh && document.querySelector('.sub'), null, {timeout: 30000});
  const row = n => '.pass.p2 .row[data-c="' + n + '"]';
  const rowsOf = page => page.evaluate(() => [...document.querySelectorAll('.pass.p2 .row[data-c]')].map(r => {
    const line = s => { const e = r.querySelector('.gl ' + s); return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
    return {c: +r.dataset.c, fa: r.querySelector('.fa').textContent.replace(/\s+/g, ' ').trim(), en: line('.en')};
  }));
  async function openChunk(page, n) {
    await page.mouse.move(1, 1);
    await page.evaluate(async sel => {
      document.querySelector(sel).scrollIntoView({block: 'center'});
      await new Promise(r => setTimeout(r, 250));
    }, row(n));
    await page.hover(row(n));
    await page.waitForFunction(n => !document.querySelector('#chpen').hidden && penFor && +penFor.dataset.c === n, n);
    await page.click('#chpen');
    await page.waitForFunction(n => chOpen && chN === n, n);
  }

  for (const bk of BOOKS) {
    console.log(`\n${bk.code}: "${bk.text.split('\n')[0]}"`);
    const bookDir = `${B0.root}/books/${bk.folder}/${bk.slug}`;
    const readerUrl = `/books/${bk.folder}/${bk.slug}/reader/`;

    /* the add: "Write it here, by hand", "Make the draft" -- refused before §6.6 */
    const page = await open('/books/add/', bk.code + '-add');
    await page.waitForSelector('#paths .path[data-path="new"]');
    await page.click('#paths .path[data-path="new"]');
    await page.waitForFunction(() => !document.querySelector('#lane-new').hidden);
    await page.selectOption('#lang', bk.code);
    await page.selectOption('#gloss', bk.code === 'en' ? 'it' : 'en');
    await page.fill('#slug', '');
    await page.fill('#title', bk.title);
    await page.fill('#title_latin', bk.title_latin);
    await page.fill('#chtext', bk.text);
    await page.click('#mkempty');
    const opened = await page.waitForURL(B + readerUrl, {timeout: 30000}).then(() => true, () => false);
    if (!opened) {
      const said = await page.evaluate(() => document.body.innerText.match(/[^\n]*(LaTeX|instruction|spell it)[^\n]*/g));
      throw Error(`FAIL: ${bk.code}: "Make the draft" did not open the reader -- the page says ${JSON.stringify(said)}`);
    }
    await readerReady(page);
    assert(true, `${bk.code}: "Make the draft" took the text with % & $ # _ { } in it and opened the reader`);
    const tex = await Deno.readTextFile(bookDir + '/ch1.tex');
    assert(tex.includes('50\\%') && tex.includes('R\\&D'), `${bk.code}: the chapter holds 50\\% and R\\&D`);
    let recs = await chunksOf(bookDir + '/ch1.tex');
    const n = recs.findIndex(r => r.fa === bk.rowFa);
    assert(n >= 0, `${bk.code}: the chunk sheet's reader gives the chunk as typed: ${JSON.stringify(recs.map(r => r.fa))}`);

    /* the reader shows the text as typed */
    let rows = await rowsOf(page);
    eq(rows[n].fa, bk.rowFa, `${bk.code}: the reader's row reads ${JSON.stringify(bk.rowFa)}`);
    assert(!rows.some(r => /\\[%&$#_{}]/.test(r.fa)), `${bk.code}: and no row shows a TeX escape`);

    /* the chunk sheet: opened on the chunk, a meaning with every special typed, saved */
    await openChunk(page, n);
    eq(await page.evaluate(() => document.getElementById('chfa').value), bk.rowFa,
       `${bk.code}: the chunk sheet's text box holds the text as typed`);
    await page.fill('#chen', MEANING);
    await page.click('#chsave');
    await page.waitForFunction(() => /^saved/.test(document.querySelector('#chstat').textContent), null, {timeout: 20000});
    const stat = await page.evaluate(() => document.querySelector('#chstat').textContent);
    assert(/^saved en/.test(stat), `${bk.code}: the sheet says ${JSON.stringify(stat)}`);
    recs = await chunksOf(bookDir + '/ch1.tex');
    eq([recs[n].fa, recs[n].en], [bk.rowFa, MEANING], `${bk.code}: saved, and read back exactly as typed`);
    const tex2 = await Deno.readTextFile(bookDir + '/ch1.tex');
    assert(tex2.includes('half \\& half, 100\\% \\{sure\\} \\textasciitilde{} \\textasciicircum{} \\_ \\# \\$ \\textbackslash{} done'),
           `${bk.code}: the .tex holds the meaning escaped`);
    rows = await rowsOf(page);
    eq(rows[n].en, MEANING, `${bk.code}: the row shows the meaning as typed`);

    /* the page opened again from the server: the rebuilt reader agrees */
    const again = await open(readerUrl, bk.code + '-again');
    await readerReady(again);
    rows = await rowsOf(again);
    eq([rows[n].fa, rows[n].en], [bk.rowFa, MEANING], `${bk.code}: the reader opened again shows both as typed`);
    await again.close();

    const v = await run(PY, ['lib/verify_book.py', '--book', bookDir]);
    assert(v.code === 0 && / 0 mismatched/.test(v.out), `${bk.code}: verify_book: ${JSON.stringify(v.out.trim().split('\n').pop())}`);
    await page.close();
  }

  assert(!errors.length, 'no page threw or had a request refused: ' + errors.join('; '));
  assert(!/Traceback/.test(log.join('')), 'no traceback in the hub\'s log');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq(ownAfter.digests, ownBefore.digests, 'the owner\'s config/, books/ and the fixtures are untouched');
  console.log(`\ntex_specials: ${passed} checks passed`);
} finally {
  if (errors.length) console.log('what the pages said:\n  ' + errors.join('\n  '));
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); await hub.status; } catch (_) {} }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept ' + TMP);
}
