// SPDX-License-Identifier: GPL-3.0-or-later
// The analyzers through the pages a person uses, on the REAL hub over a temporary tree (a0.6.0):
//   a) /books/add/, with phrases and "listen to the analyzer" chosen: the draft is an exact cut of the text, the
//      analyzer was asked, and with the choice off the same text is cut with nobody asked
//   b) a word edited in the reader is not cut again by opening it
//   c) a reader's region sheet with the gloss prompts' choice on: "copy the prompt" and the skill's request both
//      carry `analysis` and the rule, at a computer's width and a phone's; with it off, neither does
//   d) an answer echoing `analysis`, pasted and filled: nothing of it in the .tex
//   e) Settings -> Skills for your chatbot: the skill to download has the reference
// With REAL=<folder holding runtime/ and models/>, the real analyzers; else a stand-in that logs each question.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/analysis_drive.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const REAL = Deno.env.get('REAL') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-analysis-drive-'});
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => { const x = JSON.stringify(a), y = JSON.stringify(b); assert(x === y, `${m} (got ${x}, want ${y})`); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const td = new TextDecoder();
async function py(code, ...args) {
  const r = await new Deno.Command(PY, {args: ['-c', code, ...args], cwd: root, stdout: 'piped', stderr: 'piped'}).output();
  if (!r.success) throw Error(td.decode(r.stderr));
  return td.decode(r.stdout);
}
const BUILD = String.raw`
import json, os, shutil, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['tests', 'lib']
import mobile_harness
tmp = Path(sys.argv[1])
root = tmp / 'root'
for d in (root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises', tmp / 'anki', tmp / 'tray', tmp / 'config', tmp / 'dict'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
d = root / 'books' / 'italian' / 'mini-it'
shutil.copytree(str(REPO / 'tests/fixtures/books/italian/mini-it'), str(d), ignore=shutil.ignore_patterns('reader', '.reader-key'))
mobile_harness.built_reader(d)
# a small real dictionary, for the stand-in: each word of the first chunks as a noun, and a verb that has it as a form
import lookup, re, texwrite
words = {w for r in texwrite.read_chunks(str(d / 'ch1.tex'))[:6] for w in re.findall(r'[^\W\d_]+', r['fa'])}
c = lookup.create(str(tmp / 'dict' / 'it.db'))
for w in sorted(words):
    for head, pos in ((w, 'noun'), (w + 'are', 'verb')):
        cur = c.execute('INSERT INTO entry (headword, translit, ipa, pos, sense, sense_tags) VALUES (?,?,?,?,?,?)', (head, '', '', pos, 'x', ''))
        c.execute('INSERT INTO form (form, entry_id, note) VALUES (?,?,?)', (w, cur.lastrowid, ''))
c.commit()
c.close()
print(d)
`;
const SERVE = String.raw`
import os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', '.']
tmp, port, real = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
import prefs, network, offline, prompts, latexthemes, latexdraw, texpackages, analysisconfig, analyzer, getanalysis, lookup
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
latexthemes.STORE = str(tmp / 'config' / 'latex.json')
prompts.STORE = str(tmp / 'config' / 'prompts.json')
latexdraw.DRAWN = str(tmp / 'latex-drawn')
texpackages.TREE = str(tmp / 'texmf')
offline.DIGESTS = str(tmp / 'config' / 'digests.json')
offline.WHERES = str(tmp / 'config' / 'wheres.json')
analysisconfig.STORE = str(tmp / 'config' / 'analysis.json')
lookup.DICT_DIR = sys.argv[4] or str(tmp / 'dict')
if real:
    getanalysis.FOLDER = real
else:
    class Stand:
        name = 'udpipe'
        def languages(self): return ('it', 'en', 'de')
        def status(self, code): return {'package': True, 'resource': True, 'usable': True, 'loaded': True, 'version': '1', 'resource_id': 'x', 'why': ''}
        def analyze(self, code, text, syntax=False, context=''):
            with open(tmp / 'asked.log', 'a', encoding='utf-8') as f: f.write(text + '\n')
            spans = analyzer.source_tokens(text); toks = []
            for i, (s, e) in enumerate(spans):
                w = analyzer.Word(id='s0.w%d' % (i + 1), token='t%d' % i, source='udpipe', status=analyzer.CONTEXTUAL, lemma=text[s:e].lower() + 'are', upos='VERB',
                                  feats={'Number': 'Sing'}, head='s0.w%d' % (i + 2) if i + 1 < len(spans) else None, relation='flat' if i + 1 < len(spans) else 'root', start=s, end=e, surface=text[s:e])
                toks.append(analyzer.Token(id='t%d' % i, start=s, end=e, surface=text[s:e], sentence='s0', words=(w,)))
            return analyzer.Result(language=code, text=text, outcome=analyzer.OK, backend='udpipe', sentences=(('s0', 0, len(text)),), tokens=tuple(toks))
    analyzer.reset([Stand()])
import clips, decks, store
clips.set_dir(tmp / 'tray')
import serve, ytpages
for st in {store, serve.studio.store}:
    st.LIB = tmp / 'library'
    st.set_clips_dir(tmp / 'tray')
decks.set_dir(tmp / 'exercises')
decks.set_clips_dir(tmp / 'tray')
import books, draft
shelf = str(tmp / 'root' / 'books')
books.BOOKS_DIR = serve.booklib.BOOKS_DIR = draft.BOOKS_DIR = shelf
books.all_books.__defaults__ = (shelf, None)
books.book_dirs.__defaults__ = (shelf,)
serve.ROOT = str(tmp / 'root')
serve._AtRoot.directory = str(tmp / 'root')
ytpages.VIDEOS = str(tmp / 'root' / 'youtube' / 'videos')
serve.ANKI = ytpages.ANKI = str(tmp / 'anki')
ytpages.INBOX = str(tmp / 'anki' / 'inbox')
sys.argv = ['serve.py', '--http', '--local', port]
serve.main()
`;
const CHUNKS = String.raw`
import json, sys
sys.path[:0] = ['lib', 'youtube/lib']
import texwrite as X
print(json.dumps([r['fa'] for r in X.read_chunks(sys.argv[1])], ensure_ascii=False))
`;
const STRIP = String.raw`
import sys
sys.path[:0] = ['lib', 'youtube/lib']
import texwrite as X
p = sys.argv[1]
for r in X.read_chunks(p):
    X.edit_chunk(p, r['index'], {f: '' for f in ('tr', 'voc', 'en') if f in r['fields']})
`;
const RELINK = String.raw`
import sys
from pathlib import Path
sys.path[:0] = ['tests', 'lib']
import mobile_harness
mobile_harness.built_reader(Path(sys.argv[1]))
`;
const log = [];
let hub = null, browser = null;
try {
  const mini = (await py(BUILD, TMP)).trim().split('\n').pop();
  const listener = Deno.listen({port: 0}); const port = listener.addr.port; listener.close();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port), REAL, Deno.env.get('DICT') || ''], cwd: root, stdout: 'null', stderr: 'piped'}).spawn();
  (async () => { const r = hub.stderr.pipeThrough(new TextDecoderStream()).getReader();
                 for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); } })();
  const B = `http://127.0.0.1:${port}`;
  const end = Date.now() + 60000;
  for (;;) {
    try { const r = await fetch(B + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) { /* not yet */ }
    if (Date.now() > end) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
  const choose = c => fetch(B + '/settings/api/analysis/use', {method: 'POST', headers: {'Content-Type': 'application/json', Origin: B},
    body: JSON.stringify({choices: c})}).then(r => r.json()).then(r => { if (!r.ok) throw Error(JSON.stringify(r)); });
  const asked = async () => (await Deno.readTextFile(TMP + '/asked.log').catch(() => '')).split('\n').filter(Boolean);
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true, args: ['--no-sandbox']});
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: B});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));

  const TEXT = 'Il vecchio cane del mio vicino mangia la carne in cucina ogni giorno.';
  async function draft(slug) {
    await page.goto(B + '/books/add/');
    await page.waitForSelector('#paths .path[data-path="new"]');
    await page.click('#paths .path[data-path="new"]');
    await page.waitForFunction(() => !document.querySelector('#lane-new').hidden);
    await page.selectOption('#lang', 'it');
    await page.selectOption('#gloss', 'en');
    await page.fill('#title', slug);
    await page.fill('#title_latin', slug);
    await page.fill('#title_en', slug);
    await page.fill('#slug', slug);
    await page.fill('#chtext', TEXT);
    await page.selectOption('#how', 'phrase');
    await Promise.all([page.waitForURL(`${B}/books/italian/${slug}/reader/`, {timeout: 60000}), page.click('#mkempty')]);
    return JSON.parse(await py(CHUNKS, `${TMP}/root/books/italian/${slug}/ch1.tex`));
  }
  console.log('a) new text');
  const before = await draft('senza');
  if (!REAL) eq(await asked(), [], 'off: the analyzer is asked nothing');
  await choose({chunking: 'assist'});
  const n0 = (await asked()).length;
  const after = await draft('con');
  console.log('     without:', before.join(' | '), '\n     with:   ', after.join(' | '));
  if (!REAL) assert((await asked()).length > n0, 'on: the analyzer is asked');
  eq(after.join(' ').replace(/\s+/g, ' '), TEXT, 'the cut is the text, whole');
  if (!REAL) assert(after.join('|') !== before.join('|'), 'and what it says shows in the cut');

  errors.length = 0;     // a reader the hub has just built links lib/ by a climb this temporary root cannot follow: relinked below
  console.log('b) nothing is cut again');
  const n1 = (await asked()).length;
  await py(RELINK, `${TMP}/root/books/italian/con`);
  await page.goto(`${B}/books/italian/con/reader/`);
  await page.waitForSelector('.pass.p2 .row');
  await sleep(500);
  eq(JSON.parse(await py(CHUNKS, `${TMP}/root/books/italian/con/ch1.tex`)), after, 'opening the book leaves its chunks');
  if (!REAL) eq((await asked()).length, n1, 'and asks the analyzer nothing about cutting');
  await choose({chunking: 'off'});

  console.log('c) the prompts');
  await py(STRIP, `${mini}/ch1.tex`);
  await py(RELINK, mini);
  const openRegion = async width => {
    await page.setViewportSize({width, height: 900});
    await page.goto(`${B}/books/italian/mini-it/reader/`);
    await page.waitForSelector('.pass.p2 .row');
    await page.click('#rgn');
    await page.waitForFunction(() => rgShown);
    await page.locator('#rgbox .oltree > li.ol-ch').first().waitFor();
  };
  const pickFirst = async () => {
    const ch = page.locator('#rgbox .oltree > li.ol-ch').first();
    if ((await ch.getAttribute('aria-expanded')) === 'false') await ch.locator(':scope > .olr > .oltw').click();
    for (let i = 0; i < 40; i++) {
      const shut = ch.locator('li[aria-expanded="false"]');
      if (!(await shut.count())) break;
      await shut.first().locator(':scope > .olr > .oltw').click();
    }
    await ch.locator('li.ol-s').first().locator(':scope > .olr').click();
  };
  const copy = async sel => {
    await page.evaluate(() => navigator.clipboard.writeText('SENTINEL'));
    await page.click(sel);
    await page.waitForFunction(() => { const t = document.querySelector('#rgsum').textContent; return t && !/^writing the prompt/.test(t); }, null, {timeout: 120000});
    await sleep(300);
    return page.evaluate(() => navigator.clipboard.readText());
  };
  await openRegion(1280);
  await pickFirst();
  const off = await copy('#rgcopy');
  assert(!off.includes('"analysis"') && !off.includes('What `analysis` is'), 'off: the prompt carries none of it');
  await choose({evidence: 'on'});
  for (const width of [1280, 390]) {
    await openRegion(width);
    await pickFirst();
    const on = await copy('#rgcopy');
    assert(on.includes('"analysis"'), `${width}: the prompt on the clipboard carries the analysis`);
    assert(on.includes('What `analysis` is'), `${width}: and the rule`);
    const skillBtn = page.locator('#rgbox button', {hasText: /request/i}).first();
    if (await skillBtn.count()) {
      await page.evaluate(() => navigator.clipboard.writeText('SENTINEL'));
      await skillBtn.click();
      await sleep(400);
      const req = await page.evaluate(() => navigator.clipboard.readText());
      assert(req.startsWith('Parseh request') && req.includes('"analysis"'), `${width}: the skill's request carries it too`);
      assert(req.length < on.length && !req.includes('What `analysis` is'), `${width}: with the rule left to the skill's reference`);
    } else throw Error('FAIL: no button for the skill\'s request');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${width}: no sideways scroll`);
  }

  console.log('d) an answer that echoes it');
  await openRegion(1280);
  await pickFirst();
  const prompt = await copy('#rgcopy');
  const at = prompt.lastIndexOf('```json\n');
  const doc = JSON.parse(prompt.slice(at + 8, prompt.indexOf('\n```', at + 8)));
  for (const s of doc.sentences) for (const c of s.chunks) if (c.todo) {
    Object.assign(c, {tr: '', voc: '', en: 'GLOSSED'}); delete c.todo;
    if (c.analysis) c.analysis = [{w: 'evil', lemma: 'evil'}];
  }
  await page.evaluate(t => navigator.clipboard.writeText(t), '```json\n' + JSON.stringify(doc) + '\n```');
  await page.click('#rgans');
  await page.keyboard.press('Control+V');
  await page.click('#rgfill');
  await page.waitForFunction(() => /\d/.test(document.querySelector('#rgsay, #rgsum')?.textContent || ''), null, {timeout: 30000});
  await sleep(800);
  const tex = await Deno.readTextFile(`${mini}/ch1.tex`);
  assert(tex.includes('GLOSSED'), 'the gloss went in');
  assert(!tex.includes('evil') && !tex.includes('analysis'), 'and nothing of the analysis did');

  console.log('f) the part of speech, in the book\'s panel, through the real route');
  const panel = async () => {
    await page.goto(`${B}/books/italian/mini-it/reader/`);
    await page.waitForSelector('.pass.p2 .row');
    await page.waitForFunction(() => DICT.ready);
    await page.evaluate(() => { DICT.cache.clear(); if (!DICT.on) dictSwitch(DICT, dictBtn, 'dict', true); });
    await page.evaluate(() => { const w = document.querySelector('.p1 .w[data-c="2"]') || document.querySelector('.p1 .w[data-c]');
                                w.scrollIntoView({block: 'center'}); openCloud(w); });
    await page.waitForSelector('#cloud .dict .dw', {timeout: 60000});
  };
  await py(RELINK, mini);
  await panel();
  assert(!(await page.$('#cloud .dposhere')), 'off: the panel says nothing of any analyzer');
  await choose({lookup: 'show'});
  await panel();
  await page.waitForSelector('#cloud .dict .dposhere', {timeout: 60000});
  const seen = () => page.evaluate(() => [...document.querySelectorAll('#cloud .dict .dw')].map(w => ({
    word: w.querySelector('.dwd')?.textContent, chip: w.querySelector('.dposhere')?.textContent,
    hits: [...w.querySelectorAll('.dhit')].map(h => ({head: h.querySelector('.dhead2')?.textContent, pos: h.querySelector('.dpos')?.textContent?.trim(), fits: !!h.querySelector('.dfits')})),
    line: w.querySelector('.dmachine')?.textContent})));
  const show = await seen();
  console.log(JSON.stringify(show).slice(0, 700));
  assert(show.some(w => w.chip), 'Show: each word says its part of speech, as a chip');
  assert(show.some(w => w.hits.some(h => h.fits)), 'and an entry says it fits this sentence');
  if (!REAL) assert(show.every(w => !w.hits.length || !w.hits[0].fits), 'and the order is the dictionary\'s');
  const SHOTS = Deno.env.get('SHOTS');
  if (SHOTS) await page.locator('#cloud').screenshot({path: SHOTS + '/panel-show.png'});
  await choose({lookup: 'assist'});
  await panel();
  await page.waitForSelector('#cloud .dict .dfits', {timeout: 60000});
  const first = await seen();
  assert(first.filter(w => w.hits.some(h => h.fits)).every(w => w.hits[0].fits), 'Also put what fits first: what fits stands first');
  if (SHOTS) await page.locator('#cloud').screenshot({path: SHOTS + '/panel-assist.png'});
  // and where a gloss is written from: the chunk's sources
  await page.evaluate(() => { const r = document.querySelector('.pass.p2 .row[data-c="2"]'); r.scrollIntoView({block: 'center'}); });
  await sleep(300);
  await page.mouse.move(1, 1);
  await page.hover('.pass.p2 .row[data-c="2"]');
  await page.waitForFunction(() => !document.querySelector('#chpen').hidden);
  await page.click('#chpen');
  await page.waitForFunction(() => chOpen);
  await page.evaluate(() => { if (!sideOn) sideShow(true); });
  await page.waitForSelector('#chside .dposhere', {timeout: 60000});
  assert(true, 'the editor\'s sources say the part of speech');
  await page.waitForSelector('#chside .sfits .dfits', {timeout: 30000});
  assert(true, 'and which entry fits, where a gloss is written from');
  if (SHOTS) await page.locator('#chside').screenshot({path: SHOTS + '/editor.png'});
  await page.click('#chcancel');
  await choose({lookup: 'off'});

  console.log('e) the skill');
  await page.setViewportSize({width: 1280, height: 900});
  await page.goto(B + '/settings/skills/');
  await page.waitForFunction(() => /parseh-gloss/.test(document.body.innerText));
  assert(true, 'the skills page offers parseh-gloss');
  assert(await py(`import sys; sys.path[:0] = ['lib', 'youtube/lib']; import skills; print('references/analysis-evidence.md' in skills.build('parseh-gloss').files)`).then(t => t.includes('True')),
         'and what it would download has the reference');
  eq(errors.join(' | '), '', 'no script error');
  console.log(`analysis_drive: ${passed} checks passed`);
} catch (e) {
  console.error(e, log.slice(-5).join('').slice(-1500));
  Deno.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); } catch (_) { /* gone */ } await hub.status; }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true});
}
