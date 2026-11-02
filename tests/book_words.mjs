// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/book_words.mjs
// The word layer in the book reader (lib/tex2html.py).  Copies of the
// Japanese and Chinese fixtures are given words in some chunks through
// lib/texwrite.py and built.  Every chunk without words is held byte for byte
// against the reader the base commit's tex2html.py builds from the same files
// (PARSEH_BASE, default d231de8), and so is every fixture edition as it
// stands.  Then the page is driven in a browser: every request it makes is
// answered here, __edit/chunk and __divide/chunk by the real writer.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const BASE = Deno.env.get('PARSEH_BASE') || 'd231de8';
const TMP = await Deno.makeTempDir({prefix: 'parseh-book-words-'});
const td = new TextDecoder();

async function run(cmd, args) {
  const o = await new Deno.Command(cmd, {args, stdout: 'piped', stderr: 'piped'}).output();
  return {ok: o.success, out: td.decode(o.stdout), err: td.decode(o.stderr)};
}
async function py(code, ...args) {
  const r = await run(PY, ['-c', code, ...args]);
  if (!r.ok) throw Error(r.err || r.out);
  return r.out;
}
const pyJSON = async (code, ...args) => JSON.parse(await py(code, ...args));
const assert = (v, m) => { if (!v) throw Error(m); };
const eq = (got, want, m) => {
  if (JSON.stringify(got) !== JSON.stringify(want))
    throw Error(m + ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
};

const LINES = {
  'mini-ja': {6: '山(やま) へ 柴刈り(しばかり) に 、', 8: '川(かわ) へ 洗濯(せんたく) に',
              11: '川(かわ) で 洗濯(せんたく) を', 12: 'して いる と 、', 24: '二人(ふたり) は'},
  'mini-zh': {0: '从前(cóngqián) ，', 1: '山(shān) 下(xià)',
              2: '有(yǒu) 一个(yí ge) 小(xiǎo) 村子(cūnzi) 。'},
};
// chunk 17 of mini-ja carries a line written by hand that does not give its
// text back (家に is not 家 を): the build draws it as it always drew it
const BAD = {n: 17, line: '家(いえ) を'};

const SETUP = String.raw`
import glob, json, os, shutil, sys
sys.path.insert(0, 'lib')
import texwrite
tmp, lines = sys.argv[1], json.loads(sys.argv[2])
keep = shutil.ignore_patterns('reader', '.reader-key')
for rel, name in (('japanese/mini-ja', 'mini-ja'), ('chinese/mini-zh', 'mini-zh')):
    d = os.path.join(tmp, 'words', name)
    shutil.copytree(os.path.join('tests/fixtures/books', rel), d, ignore=keep)
    ch = os.path.join(d, 'ch1.tex')
    for i, line in lines[name].items():
        r = texwrite.edit_chunk(ch, int(i), {'words': line})
        assert r['macro'] in ('chw', 'chrw') and not r['warnings'], r
    if name == 'mini-ja':
        t = open(ch, encoding='utf-8').read()
        old = r'\chr{}{家に}{いえに}{ie ni}{\dw{家}{ie} house, home}{home}'
        assert old in t
        open(ch, 'w', encoding='utf-8').write(t.replace(old, r'\chrw' + old[4:] + '{家(いえ) を}'))
    shutil.copytree(d, os.path.join(tmp, 'wbase', name))
for d in sorted(glob.glob('tests/fixtures/books/*/*')):
    for side in ('plain', 'pbase'):
        shutil.copytree(d, os.path.join(tmp, side, os.path.basename(d)), ignore=keep)
print(json.dumps(sorted(os.listdir(os.path.join(tmp, 'plain')))))
`;
// the base commit's tex2html.py, run as if it were the file in lib/
const BASE_BUILD = String.raw`
import os, subprocess, sys
base, book = sys.argv[1], sys.argv[2]
src = subprocess.run(['git', 'show', base + ':lib/tex2html.py'], capture_output=True, check=True).stdout
path = os.path.abspath('lib/tex2html.py')
sys.argv = [path, '--book', book]
exec(compile(src, path, 'exec'), {'__name__': '__main__', '__file__': path})
`;
const WORDED = String.raw`
import json, sys
sys.path.insert(0, 'lib')
import tex2html
tex2html.set_lang('ja')
cases = [('山へ柴刈りに、', '山(やま) へ 柴刈り(しばかり) に 、'), ('私は 本を', '私(わたし) は 本(ほん) を'),
         ('(注)', '((注))'), ('𠮷野家', '𠮷(よし) 野家(のや)'), ('A&B<山>"', 'A&B<山>"(やま)'),
         ('山　へ', '山(やま) へ'), ('山へ', '山(やま)'), ('山(', '山((')]
out = [{'fa': fa, 'line': line, 'html': tex2html.worded(fa, line)} for fa, line in cases]
tex2html.set_lang('fa')
out.append({'fa': 'آب', 'line': 'آب', 'html': tex2html.worded('آب', 'آب'), 'nolayer': True})
print(json.dumps(out, ensure_ascii=False))
`;
const EDIT = String.raw`
import json, os, sys
sys.path.insert(0, 'lib')
import texwrite
book, body = sys.argv[1], json.loads(sys.argv[2])
try:
    r = texwrite.edit_chunk(os.path.join(book, 'ch1.tex'), body['index'], body['fields'])
except texwrite.Refused as e:
    print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)); sys.exit()
r.update(ok=True, file='ch1.tex', reader={'ok': True}, pdf_stale=bool(r['changed']))
print(json.dumps(r, ensure_ascii=False))
`;
// a preview is the book's own; a split or a join is tried on a copy of it,
// so the page under test keeps its numbering
const DIVIDE = String.raw`
import json, os, shutil, sys, tempfile
sys.path.insert(0, 'lib')
import texwrite
book, body = sys.argv[1], json.loads(sys.argv[2])
try:
    if body['action'] == 'preview':
        r = texwrite.divide_preview(os.path.join(book, 'ch1.tex'), body['index'])
    else:
        d = os.path.join(tempfile.mkdtemp(), 'b')
        shutil.copytree(book, d, ignore=shutil.ignore_patterns('reader'))
        ch = os.path.join(d, 'ch1.tex')
        if body['action'] == 'split':
            r = texwrite.split_chunk(ch, body['index'], body.get('first') or {}, body.get('second') or {})
        else:
            r = texwrite.merge_chunks(ch, body['index'], body.get('fields'))
        shutil.rmtree(os.path.dirname(d))
except texwrite.Refused as e:
    print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)); sys.exit()
r.update(ok=True, file='ch1.tex', index=body['index'])
print(json.dumps(r, ensure_ascii=False))
`;

const WORDS_ROW = '  <div class="arow" id="chwordsrow" hidden><span class="alab">words</span>\n' +
                  '    <div class="actl" id="chwords"></div></div>\n';
function pieces(html) {
  return {main: html.match(/<main>\n([\s\S]*?)\n<\/main>/)[1],
          src: JSON.parse(html.match(/const SRC=(.*?);<\/script>/s)[1]),
          meta: JSON.parse(html.match(/const META=(.*?);const LANG=/s)[1]),
          chbox: html.match(/<form id="chbox"[\s\S]*?<\/form>/)[0],
          head: html.split('<style>')[0]};
}
// every element a chunk's data-c sits on, as the file spells it, in order
function chunkEls(html, n) {
  const out = [], at = new RegExp('<(span|div) class="[^"]*" data-c="' + n + '"', 'g');
  let m;
  while ((m = at.exec(html))) {
    const tag = new RegExp('<' + m[1] + '[\\s>]|</' + m[1] + '>', 'g');
    tag.lastIndex = m.index + 1;
    let depth = 1, t;
    while (depth && (t = tag.exec(html))) depth += t[0][1] === '/' ? -1 : 1;
    out.push(html.slice(m.index, tag.lastIndex));
  }
  return out;
}
const reader = (side, name) => `${TMP}/${side}/${name}/reader/index.html`;
async function build(dir) {
  const r = await run(PY, ['lib/tex2html.py', '--book', dir]);
  if (!r.ok) throw Error('tex2html on ' + dir + ': ' + r.err);
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
// ---- the built page, against the base commit's --------------------------
const editions = JSON.parse(await py(SETUP, TMP, JSON.stringify(LINES)));
const haveBase = (await run('git', ['cat-file', '-e', BASE + ':lib/tex2html.py'])).ok;
await Promise.all([...editions.map(n => build(`${TMP}/plain/${n}`)),
                   ...Object.keys(LINES).map(n => build(`${TMP}/words/${n}`))]);
if (haveBase)
  await Promise.all([...editions.map(n => py(BASE_BUILD, BASE, `${TMP}/pbase/${n}`)),
                     ...Object.keys(LINES).map(n => py(BASE_BUILD, BASE, `${TMP}/wbase/${n}`))]);
else console.log('no ' + BASE + ' in this repository: the comparisons with its reader are skipped');

for (const n of editions) {
  const now = pieces(await Deno.readTextFile(reader('plain', n)));
  assert(now.src.every(r => r.length === 7 && r[6] === ''), n + ': SRC gains a seventh slot, empty for a chunk without words');
  assert(now.meta.reorders === false, n + ': META says whether the book reorders');
  assert(now.chbox.includes(WORDS_ROW) === ['mini-ja', 'mini-zh'].includes(n),
         n + ': a words row in the chunk sheet exactly for a language divided into words');
  assert(/\/lib\/wordline\.js"><\/script>\n<script src="[^"]*\/lib\/parseh\.js">/.test(now.head),
         n + ': wordline.js is loaded, before parseh.js');
  if (!haveBase) continue;
  const was = pieces(await Deno.readTextFile(reader('pbase', n)));
  assert(now.main === was.main, n + ': the text is byte for byte what the base commit builds');
  eq(now.src.map(r => r.slice(0, 6)), was.src, n + ': SRC keeps its six slots');
  for (const k of ['build', 'built']) { delete now.meta[k]; delete was.meta[k]; }
  delete now.meta.reorders;
  eq(now.meta, was.meta, n + ': META is otherwise as it was');
  assert(now.chbox.replace(WORDS_ROW, '') === was.chbox, n + ': the chunk sheet gains the words row and nothing else');
  // and the card kit, which the card sheet cuts clips and writes exercises
  // with (tests/book_cards.mjs drives it)
  assert(now.head.replace(/<script src="[^"]*\/lib\/wordline\.js"><\/script>\n/, '')
           .replace(/<link rel="stylesheet" href="[^"]*\/lib\/cardkit\.css">\n<script src="[^"]*\/lib\/cardkit\.js"><\/script>\n/, '') === was.head,
         n + ': the head gains wordline.js and the card kit, and nothing else');
}
const SRCS = {};
for (const name of Object.keys(LINES)) {
  const now = pieces(await Deno.readTextFile(reader('words', name)));
  SRCS[name] = now.src;
  const worded = Object.keys(LINES[name]).map(Number);
  eq(now.src.map(r => r[6]), now.src.map((_, n) => LINES[name][n] || (name === 'mini-ja' && n === BAD.n ? BAD.line : '')),
     name + ': the seventh slot is the chunk\'s word line');
  for (const n of worded) {
    const els = chunkEls(now.main, n);
    assert(els.every(e => !/<ruby>[^<]*<span/.test(e)), name + ' chunk ' + n + ': no ruby over a worded chunk anywhere');
    assert(els[0].includes(' data-w="') && els[2].includes(' data-w="'), name + ' chunk ' + n + ': pass 1 and the chunk column a word at a time');
  }
  if (name === 'mini-zh') {
    assert(chunkEls(now.main, 0)[1] === '<span class="w" data-c="0" lang="zh-Latn">cóngqián，</span>',
           'the reading pass says its pinyin is Latin letters: ' + chunkEls(now.main, 0)[1]);
    assert(chunkEls(now.main, 3)[1] === '<span class="w" data-c="3">cūnzi lǐ</span>', 'a chunk without words keeps its span');
  }
  if (!haveBase) continue;
  const was = pieces(await Deno.readTextFile(reader('wbase', name)));
  eq(now.src.map(r => r.slice(0, 6)), was.src, name + ': SRC keeps its six slots');
  for (let n = 0; n < now.src.length; n++) {
    const a = chunkEls(now.main, n), b = chunkEls(was.main, n);
    eq(a.length, b.length, name + ' chunk ' + n + ': as many elements');
    if (!worded.includes(n)) { eq(a, b, name + ' chunk ' + n + ': a chunk without words is byte for byte the base commit\'s'); continue; }
    const [p1, p5, row, ...plain] = a, [, bp5, , ...bplain] = b;
    assert(p1 !== b[0] && row !== b[2], name + ' chunk ' + n + ': drawn otherwise than the base commit drew it');
    eq(plain, bplain, name + ' chunk ' + n + ': passes 3 and 4 stay plain');
    eq(p5, name === 'mini-zh' ? bp5.replace(`data-c="${n}">`, `data-c="${n}" lang="zh-Latn">`) : bp5,
       name + ' chunk ' + n + ': the reading pass as built');
  }
  const nowL = now.main.split('\n'), wasL = was.main.split('\n');
  eq(nowL.length, wasL.length, name + ': as many lines');
  nowL.forEach((l, i) => {
    if (l !== wasL[i]) assert(worded.some(n => l.includes(`data-c="${n}"`)), name + ': line ' + i + ' changed and holds no worded chunk');
  });
}
const CASES = await pyJSON(WORDED);
assert(CASES.find(c => c.nolayer).html === null, 'a language with no word layer draws no words');
console.log('Build: every fixture edition and every chunk without words as the base commit builds them' +
            (haveBase ? '' : ' (base comparison skipped)') + '; worded chunks drawn per word, SRC and META: passed');

// ---- the page -------------------------------------------------------------
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => { errors.push(e.message); console.log('PAGE ERROR', e.message); });
page.on('dialog', d => d.accept());           // propose asks before replacing a written line
const seen = {lookup: [], propose: [], edit: [], divide: [], tried: []};
const ROWS = {'二人(ふたり) は': [
  {word: 'は', i: 1, hits: [], tried: ['は']},
  {word: '二人', i: 0, hits: [{headword: '二人', translit: 'futari', pos: 'noun', senses: ['two people']}], tried: ['二人']}]};
const PROPOSAL = {'山へ柴刈りに、': '山(さん) へ 柴刈り(しばかり) に 、'};
function lookup(body) {
  seen.lookup.push(body);
  if (body.about) return {ok: true, help: true, available: true, corpus_available: true,
                          source: {source: 'a test dictionary'}, corpus: {source: 'Tatoeba'}};
  if (body.corpus_only) return {ok: true, pairs: [], pairs_more: false, pairs_offset: body.corpus_offset || 0};
  return {ok: true, words: (body.words && ROWS[body.words]) || [{word: body.text, hits: [], tried: [body.text]}],
          pairs: [{src: '二人は友達です。', dst: 'The two are friends.', matched: ['二人']}],
          pairs_more: true, pairs_offset: 0, corpus: {source: 'Tatoeba'}};
}
const MIME = {html: 'text/html', js: 'text/javascript', css: 'text/css', json: 'application/json'};
await page.route('**/*', async route => {
  const req = route.request(), url = new URL(req.url());
  if (url.hostname !== 'parseh.test') return route.abort();
  const path = decodeURIComponent(url.pathname), book = path.slice(0, path.indexOf('/reader/'));
  if (path === '/anki/decks') return route.fulfill({json: []});
  if (path.endsWith('/reader/__lookup')) return route.fulfill({json: lookup(req.postDataJSON())});
  if (path.endsWith('/reader/__words/propose')) {
    const b = req.postDataJSON(); seen.propose.push(b);
    return route.fulfill({json: {ok: true, words: PROPOSAL[b.text] || '', available: true, python: 'test'}});
  }
  if (path.endsWith('/reader/__edit/chunk')) {
    const b = req.postDataJSON(); seen.edit.push(b);
    const r = await pyJSON(EDIT, book, JSON.stringify(b));
    if (r.ok) await build(book);
    return route.fulfill({json: r});
  }
  if (path.endsWith('/reader/__divide/chunk')) {
    const b = req.postDataJSON(); seen.divide.push(b);
    const r = await pyJSON(DIVIDE, book, JSON.stringify(b));
    if (b.action !== 'preview') seen.tried.push(r);
    return route.fulfill({json: r});
  }
  try {
    return route.fulfill({body: await Deno.readTextFile(path), contentType: MIME[path.split('.').pop()] || 'application/octet-stream'});
  } catch (_) { return route.fulfill({body: '{}', contentType: 'application/json'}); }
});
async function hoverChunk(n) {
  await page.mouse.move(1, 1);
  await page.locator('.p1 [data-c="' + n + '"]').hover();
  await page.waitForFunction(n => cloudC === n && !document.querySelector('#cloud').hidden, n);
}
// the helpers every page.evaluate below starts from
const H = `const assert = (v, m) => { if (!v) throw Error(m); };
  const eq = (g, w, m) => { if (JSON.stringify(g) !== JSON.stringify(w)) throw Error(m + ': got ' + JSON.stringify(g) + ' want ' + JSON.stringify(w)); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const until = async (f, m) => { for (let i = 0; i < 300; i++) { if (f()) return; await sleep(20); } throw Error('timed out: ' + m); };
  const row = n => document.querySelector('.row[data-c="' + n + '"]');`;
const inPage = (body, arg) => page.evaluate(`(async (arg) => { ${H}\n${body} })(${JSON.stringify(arg)})`);

const JA = `http://parseh.test${TMP}/words/mini-ja/reader/index.html`;
await page.goto(JA, {waitUntil: 'load'});
console.log(await inPage(`
  const doc = new DOMParser().parseFromString(await (await fetch('index.html', {cache: 'no-store'})).text(), 'text/html');
  const blank = Parseh.readings({scope: 'test:nothing-known', kind: 'book', selector: '.none'});
  const drawn = (fa, line) => { const el = document.createElement('span'); return blank.renderWords(el, fa, line) ? el.innerHTML : null; };
  for (const c of arg) {
    if (c.nolayer) continue;
    if (c.html === null) { assert(drawn(c.fa, c.line) === null, 'the build falls back where the page does: ' + c.line); continue; }
    const el = document.createElement('span'); el.innerHTML = c.html;
    eq(el.innerHTML, drawn(c.fa, c.line), 'tex2html.worded builds what renderWords builds for ' + c.line);
  }
  for (const n of [6, 8, 11, 12, 24]) {
    const s = SRC[n], at = '[data-c="' + n + '"]', want = drawn(s[1], s[6]);
    assert(want, 'chunk ' + n + ' draws');
    eq(doc.querySelector('.p1 ' + at).innerHTML, want, 'pass 1 of chunk ' + n + ' is the markup renderWords builds');
    eq(doc.querySelector('.row' + at + ' .fa').innerHTML, want, 'and so is its chunk column');
    assert([...doc.querySelectorAll(at + ' ruby')].every(r => r.parentElement.matches('.wd[data-w]')), 'no ruby over chunk ' + n + ' but its words');
    eq(doc.querySelector('.p3 ' + at).innerHTML, '<span class="wd">' + s[1] + '</span>', 'pass 3 stays plain');
    const d = chunkData(n);
    assert(Parseh.baseText(document.querySelector('.p1 ' + at)) === s[1] && d.fa === s[1] && d.drawn && d.words === s[6], 'the chunk read without its readings');
  }
  const six = document.querySelector('.p1 [data-c="6"]');
  assert(six.querySelectorAll('.wd[data-w] > ruby').length === 2 && !six.querySelector('.wd:not([data-w])'), 'the load leaves a worded chunk as built');
  const four = document.querySelector('.p1 [data-c="4"]');
  assert(four.querySelector('.wd:not([data-w]) > ruby rt').textContent === 'す' && !four.querySelector('ruby .wd'),
         'a chunk without words has its kana split over its kanji, as ever');
  const bad = document.querySelector('.p1 [data-c="17"]');
  assert(!document.querySelector('[data-c="17"] [data-w]') && bad.querySelector('.wd > ruby rt').textContent === 'いえ'
         && lineOf(17) === '家(いえ) を' && !chunkData(17).drawn, 'a line that does not give its text back: the chunk as it always was');
  return 'Render: pass 1 and the chunk column are renderWords\\' markup, passes 3/4 plain, the rest split as before: passed';
`, CASES));

await page.evaluate(() => setHover(true));
await hoverChunk(6);
console.log(await inPage(`
  const cloud = document.querySelector('#cloud'), words = [...cloud.querySelectorAll('[data-known-word]')];
  eq(words.map(b => b.dataset.knownWord), ['山(やま)', '柴刈り(しばかり)'], 'I know this, a word at a time');
  assert(!cloud.querySelector('[data-known-kanji]'), 'and not a kanji at a time');
  eq(cloud.querySelector('.kana').textContent, 'やまへしばかりに', 'the chunk\\'s own reading, on hover');
  words[0].click();
  assert(JSON.parse(localStorage.getItem('parseh_known_word:book:ja:mini-ja')).includes('山(やま)'), 'saved for the book');
  for (const sel of ['.p1 [data-c="6"]', '.row[data-c="6"] .fa']) {
    const rt = document.querySelector(sel + ' .wd[data-w="山(やま)"] ruby.reading-known rt');
    assert(rt && getComputedStyle(rt).visibility === 'hidden', 'the known word hides its reading in ' + sel);
    assert(!document.querySelector(sel + ' .wd[data-w="柴刈り(しばかり)"] ruby.reading-known'), 'and nothing else does');
  }
  return 'Cloud: per-word controls, the reading on hover, the click hides the word in pass 1 and the column: passed';
`));
await hoverChunk(8);
await inPage(`
  document.querySelector('#cloud [data-known-word="川(かわ)"]').click();
  assert(document.querySelector('.p1 [data-c="11"] .wd[data-w="川(かわ)"] ruby.reading-known'), 'every appearance of the word hides');
`);
await inPage(`
  // what an analyzer read the word as (lib/lookupassist.py): one line under the word, found or not, and none without it
  const said = {lemma: '二人', upos: 'NOUN', feats: {Number: 'Sing'}, source: 'native', status: 'lexical', readings: 2};
  const none = dictLine({word: '二人', hits: [], tried: ['二人'], machine: said});
  assert(/native knows this as 二人 · NOUN · Number=Sing · one of 2 readings/.test(none.querySelector('.dmachine').textContent), 'the line under a word not found');
  const found = dictLine({word: '二人', hits: [{headword: '二人', senses: ['two people']}], tried: [], via: 'as written',
                          machine: Object.assign({}, said, {status: 'contextual', ranked: true})});
  assert(/reads this here as .* its entry moved first/.test(found.querySelector('.dmachine').textContent), 'the line under a word found');
  assert(!dictLine({word: '二人', hits: [], tried: ['二人']}).querySelector('.dmachine'), 'no line without a reading');
`);
await hoverChunk(4);
await inPage(`assert(document.querySelector('#cloud [data-known-kanji="住"]') && !document.querySelector('#cloud [data-known-word]'), 'a chunk without words: kanji controls, as before');`);
await hoverChunk(17);
await inPage(`assert(document.querySelector('#cloud [data-known-kanji="家"]') && !document.querySelector('#cloud [data-known-word]'), 'a line the build could not draw: kanji controls');`);
await page.reload({waitUntil: 'load'});
console.log(await inPage(`
  for (const sel of ['.p1 [data-c="6"] .wd[data-w="山(やま)"]', '.row[data-c="11"] .wd[data-w="川(かわ)"]']) {
    const rt = document.querySelector(sel + ' ruby.reading-known rt');
    assert(rt && getComputedStyle(rt).visibility === 'hidden', 'known after a reload: ' + sel);
  }
  assert(!document.querySelector('.p1 [data-c="6"] .wd[data-w="柴刈り(しばかり)"] ruby.reading-known'), 'and only those');
  return 'Known words hidden after a click and after a reload: passed';
`));

// the dictionary
await page.waitForFunction(() => DICT.ready);
await page.evaluate(() => dictSwitch(DICT, dictBtn, 'dict', true));
await hoverChunk(24);
await page.waitForSelector('#cloud .dict .dwd');
console.log(await inPage(`
  const heads = [...document.querySelectorAll('#cloud .dict .dwd')];
  eq(heads.map(h => h.textContent), ['は', '二人 ふたり'], 'each row under parse(line)[i], as the line writes the word');
  eq(heads[1].querySelector('.dread').textContent, 'ふたり', 'its reading beside it');
  assert(DICT.cache.has('24\\n二人(ふたり) は') && !DICT.cache.has('24'), 'the answer is kept under the line');
  document.querySelector('#cloud .dict .dmore').click();
  await until(() => !document.querySelector('#cloud .dict .dmore'), 'load more');
  DICT.cache.clear();
  await preOne({n: 24}); await preOne({n: 7});
  assert(DICT.cache.has('24\\n二人(ふたり) は') && DICT.cache.has('7'), 'the look-ahead keys by the line too, and a chunk without one as before');
  openChunk(24, row(24)); sideShow(true);
  await until(() => document.querySelector('#chsrcbody .sword'), 'the sidebar\\'s dictionary');
  const w = document.querySelector('#chsrcbody .sword');
  assert(w.textContent === '二人 ふたり' && w.nextElementSibling.classList.contains('srow'), 'the editor\\'s rows under their word too');
  await until(() => { const b = document.querySelector('#chside .llmrow-copy'); return b && !b.disabled; }, 'the chatbot\\'s corpus pages');
  sideShow(false); closeChunk();
  return 'Lookup: the cloud, the look-ahead, the sidebar, rows placed by i, keys with the line: passed';
`));
const TEXT_LINE = {[SRCS['mini-ja'][BAD.n][1]]: BAD.line};
for (const [n, line] of Object.entries(LINES['mini-ja'])) TEXT_LINE[SRCS['mini-ja'][n][1]] = line;
const asked = seen.lookup.filter(b => !b.about);
assert(asked.some(b => b.text === '二人は' && !b.corpus_only) && asked.filter(b => b.text === '二人は' && b.corpus_only).length >= 2,
       'a lookup and corpus pages (the cloud\'s and the chatbot\'s) for a worded chunk');
for (const b of asked) eq(b.words, TEXT_LINE[b.text], 'the lookup body for ' + b.text + ' carries the chunk\'s line exactly when it has one');
assert(asked.some(b => !b.words), 'and one for a chunk without');
console.log('Lookup bodies: every one for a worded chunk carries its line, and no other does: passed');

// cards
console.log(await inPage(`
  const alt = el => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, altKey: true}));
  const card = () => ['#afa', '#akana', '#atr', '#actx'].map(s => document.querySelector(s).value);
  const shut = () => document.querySelector('#acancel').click();
  const sentOf = n => textOf(document.querySelector('.p1 [data-c="' + n + '"]').closest('.sub').querySelector('.p1')).replace(/\\s+/g, ' ').trim();
  assert(!sentOf(6).includes('やま'), 'the context without the readings');
  alt(document.querySelector('.p1 [data-c="6"] .wd[data-w="柴刈り(しばかり)"] rt'));
  eq(card(), ['柴刈り', 'しばかり', SRC[6][3], sentOf(6)], 'a word of pass 1: its surface, its reading, its subparagraph'); shut();
  alt(document.querySelector('.row[data-c="6"] .wd[data-w="山(やま)"]'));
  eq(card(), ['山', 'やま', SRC[6][3], sentOf(6)], 'a word of the chunk column'); shut();
  // read off the word's own token: a line in SRC the page does not show (a
  // save whose repaint failed) does not move the card onto another word
  const had = SRC[6][6]; SRC[6][6] = '山へ(やまへ) 柴刈りに(しばかりに) 、';
  alt(document.querySelector('.p1 [data-c="6"] .wd[data-w="柴刈り(しばかり)"]'));
  eq(card(), ['柴刈り', 'しばかり', SRC[6][3], sentOf(6)], 'the card is the word the page shows'); shut();
  SRC[6][6] = had;
  alt(document.querySelector('.p1 [data-c="4"] .wd'));
  eq(card(), ['住んでいました', SRC[4][2], SRC[4][3], sentOf(4)], 'a chunk without words is carded as ever'); shut();
  alt(document.querySelector('.p1 [data-c="17"] .wd'));
  eq(card(), ['家に', SRC[17][2], SRC[17][3], sentOf(17)], 'and so is a chunk its line could not draw'); shut();
  return 'Cards: a word of a worded chunk with its own reading, the rest unchanged: passed';
`));

// the chunk sheet and its word strip
console.log(await inPage(`
  openChunk(6, row(6));
  const strip = () => document.querySelector('#chwords .wordstrip');
  assert(!document.querySelector('#chwordsrow').hidden && strip(), 'the words row, with its strip');
  eq(strip().querySelector('.ws-text').value, SRC[6][6], 'holding the line the file holds');
  await until(() => !strip().querySelector('.ws-propose').hidden, 'propose, once the server says it can');
  const cs = s => getComputedStyle(strip().querySelector(s));
  assert(cs('.ws-read').borderTopStyle === 'dashed' && cs('.ws-cut').paddingLeft === '0px' && cs('.ws-join').borderTopStyle === 'none',
         'inside the sheet the strip is styled by parseh.css');
  assert(getComputedStyle(CH.fa).paddingLeft === '9px' && getComputedStyle(document.querySelector('#chsave')).paddingLeft === '10px',
         'and the sheet\\'s own boxes as they were');
  strip().querySelector('.ws-propose').click();
  await until(() => chStrip.value() === '山(さん) へ 柴刈り(しばかり) に 、', 'the proposal');
  eq(chunkEdits(), {words: '山(さん) へ 柴刈り(しばかり) に 、'}, 'a changed line is sent, alone');
  await saveChunk();
  assert(!CH.stat.classList.contains('bad'), 'saved: ' + CH.stat.textContent);
  assert(/chunk's reading/.test((CH.stat.querySelector('.warn') || {}).textContent), 'the answer\\'s warning under it: ' + CH.stat.textContent);
  eq([SRC[6][6], chStrip.value()], ['山(さん) へ 柴刈り(しばかり) に 、', '山(さん) へ 柴刈り(しばかり) に 、'], 'SRC and the strip hold the line written');
  for (const sel of ['.p1 [data-c="6"]', '.row[data-c="6"] .fa'])
    eq(document.querySelector(sel + ' .wd[data-w="山(さん)"] rt').textContent, 'さん', 'repainted with the new reading in ' + sel);
  CH.fa.value = '山へ柴刈りに。'; CH.fa.dispatchEvent(new Event('input'));
  await until(() => strip().querySelector('.ws-note .ws-err'), 'the strip made again over the new text');
  eq(chunkEdits(), {fa: '山へ柴刈りに。', words: SRC[6][6]}, 'a changed text sends the line with it, changed or not');
  document.querySelector('#chrevert').click();
  eq([CH.fa.value, chStrip.value(), !strip().querySelector('.ws-note .ws-err')], [SRC[6][1], SRC[6][6], true], 'revert: the text and the line');
  closeChunk();

  openChunk(24, row(24));
  CH.fa.value = '二人は、'; CH.fa.dispatchEvent(new Event('input'));
  await saveChunk();
  // the line went with the text, so the writer judges the two together
  assert(CH.stat.classList.contains('bad') && /words: the words do not reproduce the text/.test(CH.stat.textContent),
         'the server holds the two together: ' + CH.stat.textContent);
  closeChunk();

  openChunk(8, row(8));
  CH.en.value = 'to the river, to do the washing';
  eq(chunkEdits(), {en: 'to the river, to do the washing'}, 'an untouched line is not sent');
  await saveChunk();
  assert(document.querySelector('.p1 [data-c="8"] .wd[data-w="川(かわ)"] ruby.reading-known'), 'a repainted chunk hides the words already known');
  closeChunk();

  openChunk(4, row(4));
  CH.en.value = 'were living there.';
  eq(chunkEdits(), {en: 'were living there.'}, 'a chunk without words sends no words');
  CH.fa.value = SRC[4][1] + ' ';
  eq(Object.keys(chunkEdits()), ['fa', 'en'], 'not even with its text changed');
  CH.fa.value = SRC[4][1];
  await saveChunk();
  const four = document.querySelector('.p1 [data-c="4"]');
  assert(four.querySelector('.wd:not([data-w]) > ruby rt').textContent === 'す' && !four.querySelector('ruby .wd'),
         'a saved chunk without words is repainted as a fresh page draws it: ' + four.innerHTML);
  closeChunk();

  openChunk(13, row(13));
  const t = document.querySelector('#chwords .ws-text');
  t.value = '大きな(おおきな) 桃(もも) が'; t.dispatchEvent(new Event('input'));
  eq(chunkEdits(), {words: '大きな(おおきな) 桃(もも) が'}, 'a line given to a chunk that had none');
  await saveChunk();
  assert(!CH.stat.classList.contains('bad'), 'saved: ' + CH.stat.textContent);
  assert(document.querySelector('.p1 [data-c="13"] .wd[data-w="桃(もも)"] rt').textContent === 'もも'
         && !document.querySelector('[data-c="13"] ruby .wd'), 'drawn from it at once, without its old ruby');
  eq(SRC[13][6], '大きな(おおきな) 桃(もも) が', 'and SRC has it');
  closeChunk();
  return 'Chunk sheet: the strip, propose, the POST bodies, warnings, revert, repaint: passed';
`));
eq(seen.propose, [{text: ''}, {text: '山へ柴刈りに、', reading: 'やまへしばかりに'}],
   'one probe for the page, then the proposal for the text box, read by the kana box');
eq(seen.edit.map(b => b.fields), [{words: '山(さん) へ 柴刈り(しばかり) に 、'}, {fa: '二人は、', words: '二人(ふたり) は'},
   {en: 'to the river, to do the washing'}, {en: 'were living there.'}, {words: '大きな(おおきな) 桃(もも) が'}],
   'the edit bodies');

// the divide sheet
console.log(await inPage(`
  const col = k => DV.pair.querySelectorAll('.dvcol')[k];
  const boxes = () => [...DV.pair.querySelectorAll('textarea[data-k="words"]')].map(t => t.value);
  const fill = c => c.querySelectorAll('textarea').forEach(t => {
    if (!t.value.trim() && t.dataset.k !== 'voc' && t.dataset.k !== 'words')
      t.value = {kana: 'しばかりに', tr: 'shibakari ni,', en: 'to cut firewood,'}[t.dataset.k];
  });
  const done = () => assert(DV.act.textContent === 'reload the reader', 'written: ' + DV.stat.textContent);
  openChunk(6, row(6)); await dvStart('split');
  const i = dvData.cuts.findIndex(c => c.a === '山へ');
  dvPick(i);
  eq(boxes(), [dvData.cuts[i].first.words, dvData.cuts[i].second.words], 'a words box each side, from the preview\\'s halves');
  eq(boxes(), ['山(さん) へ', '柴刈り(しばかり) に 、'], 'the line cut where the text is');
  fill(col(1)); await dvCommit(); done(); dvShut();
  openChunk(8, row(8)); await dvStart('merge');
  eq(boxes(), [''], 'a join where one side has words: the box, empty, as the proposal dropped the line');
  await dvCommit(); done(); dvShut();
  openChunk(11, row(11)); await dvStart('merge');
  eq(boxes(), [dvData.merge.fields.words], 'a join of two worded chunks: the proposal\\'s line');
  eq(boxes(), ['川(かわ) で 洗濯(せんたく) を して いる と 、'], 'the two lines end to end');
  await dvCommit(); done(); dvShut();
  openChunk(4, row(4)); await dvStart('split'); dvPick(0);
  eq(boxes(), [], 'a chunk without words has no words box');
  fill(col(1)); await dvCommit(); done(); dvShut();
  closeChunk();
  return 'Divide sheet: words boxes on a split and a join, none without words: passed';
`));
const splits = seen.divide.filter(b => b.action === 'split'), joins = seen.divide.filter(b => b.action === 'merge');
eq([splits[0].first.words, splits[0].second.words], ['山(さん) へ', '柴刈り(しばかり) に 、'], 'the split posts both halves\' words');
assert(!('words' in splits[1].first) && !('words' in splits[1].second), 'a chunk without words posts as it always did');
eq(joins.map(b => b.fields.words), ['', '川(かわ) で 洗濯(せんたく) を して いる と 、'], 'the joins post the line');
assert(seen.tried.length === 4 && seen.tried.every(r => r.ok), 'and the writer takes every one: ' + JSON.stringify(seen.tried.filter(r => !r.ok)));
console.log('Divide POST bodies, taken by lib/texwrite.py: passed');

// Chinese: pinyin over the words, and no reading field
await page.goto(`http://parseh.test${TMP}/words/mini-zh/reader/index.html`, {waitUntil: 'load'});
console.log(await inPage(`
  const doc = new DOMParser().parseFromString(await (await fetch('index.html', {cache: 'no-store'})).text(), 'text/html');
  const blank = Parseh.readings({scope: 'test:nothing-known', kind: 'book', selector: '.none'});
  for (const n of [0, 1, 2]) {
    const el = document.createElement('span');
    assert(blank.renderWords(el, SRC[n][1], SRC[n][6]), 'chunk ' + n + ' draws');
    eq(doc.querySelector('.p1 [data-c="' + n + '"]').innerHTML, el.innerHTML, 'pass 1 of chunk ' + n + ' is renderWords\\' markup');
    eq(doc.querySelector('.row[data-c="' + n + '"] .fa').innerHTML, el.innerHTML, 'and its column');
  }
  eq([document.querySelector('.p5 [data-c="0"]').lang, document.querySelector('.p5 [data-c="3"]').hasAttribute('lang')], ['zh-Latn', false],
     'the reading pass marks pinyin as Latin where the words are');
  const rt = getComputedStyle(document.querySelector('.row[data-c="1"] .wd[data-w="山(shān)"] rt'));
  assert(rt.fontFamily.includes('system-ui') && rt.fontStyle === 'normal', 'pinyin in the chunk column is set as Latin letters: ' + rt.fontFamily);
  assert(READINGS, 'a language with words and no reading has READINGS');
  return 'Chinese render: per-word pinyin, the Latin reading pass, the column\\'s pinyin face: passed';
`));
await hoverChunk(1);
console.log(await inPage(`
  const words = [...document.querySelectorAll('#cloud [data-known-word]')];
  eq(words.map(b => b.dataset.knownWord), ['山(shān)', '下(xià)'], 'I know this, per word');
  words[0].click();
  assert(JSON.parse(localStorage.getItem('parseh_known_word:book:zh:mini-zh')).includes('山(shān)')
         && getComputedStyle(document.querySelector('.p1 [data-c="1"] .wd[data-w="山(shān)"] ruby.reading-known rt')).visibility === 'hidden',
         'a known word hides its pinyin');
  return 'Chinese cloud: per-word controls: passed';
`));
await hoverChunk(3);
console.log(await inPage(`
  assert(!document.querySelector('#cloud .reading-controls'), 'a chunk without words offers no controls, as before');
  const alt = el => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, altKey: true}));
  alt(document.querySelector('.p1 [data-c="2"] .wd[data-w="一个(yí ge)"]'));
  const sent = textOf(document.querySelector('.p1 [data-c="2"]').closest('.sub').querySelector('.p1')).replace(/\\s+/g, ' ').trim();
  eq(['#afa', '#akana', '#atr', '#actx'].map(s => document.querySelector(s).value), ['一个', '', 'yí ge', sent], 'a word\\'s card: its pinyin as the transliteration');
  document.querySelector('#acancel').click();
  openChunk(1, row(1));
  const t = document.querySelector('#chwords .ws-text');
  t.value = '山(shān) 下(shàng)'; t.dispatchEvent(new Event('input'));
  await until(() => document.querySelector('#chwords .ws-note .ws-warn'), 'the strip compares the words with the pinyin box');
  CH.tr.value = 'shān shàng'; CH.tr.dispatchEvent(new Event('input'));
  await until(() => !document.querySelector('#chwords .ws-note .ws-warn'), 'and is made again when it changes');
  eq(chStrip.value(), '山(shān) 下(shàng)', 'keeping its line');
  closeChunk();
  // a chunk given words, and then without them again, is repainted as a
  // fresh page draws it: the reading pass calls its pinyin Latin exactly
  // while the words draw the chunk
  const p5 = () => document.querySelector('.p5 [data-c="3"]').getAttribute('lang');
  const give = async line => {
    openChunk(3, row(3));
    const box = document.querySelector('#chwords .ws-text');
    box.value = line; box.dispatchEvent(new Event('input'));
    await saveChunk();
    assert(!CH.stat.classList.contains('bad') && /saved words/.test(CH.stat.textContent), 'saved: ' + CH.stat.textContent);
    closeChunk();
  };
  await give('村子(cūnzi) 里(lǐ)');
  eq([p5(), !!document.querySelector('.p1 [data-c="3"] .wd[data-w="村子(cūnzi)"] rt')], ['zh-Latn', true], 'repainted with words');
  await give('');
  eq([p5(), !!document.querySelector('[data-c="3"] [data-w]')], [null, false], 'and repainted without them');
  DICT.cache.clear(); await preOne({n: 1});
  return 'Chinese card, strip against the pinyin box: passed';
`));
eq(seen.lookup.filter(b => b.text === '山下').map(b => b.words), ['山(shān) 下(xià)'], 'a Chinese lookup body carries its line');
eq(seen.propose.slice(2), [{text: ''}], 'one probe for the Chinese page');
if (errors.length) throw Error(errors.join('\n'));
console.log('Book reader words: passed');
} finally {
  await browser.close();
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true});
}
