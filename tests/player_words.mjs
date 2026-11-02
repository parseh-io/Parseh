// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome deno run --allow-all tests/player_words.mjs
// The player over a video whose chunks carry a word line ("words") beside
// chunks that carry none: a chunk drawn a word at a time, the cloud's
// "I know this" per word, the reading alone (#aloud), the word strip in the
// editor, the lookup's words, a word's card, the pinyin's stylesheet, and the
// decomposition mode over all of it.  The fixtures are
// tests/fixtures/videos/{japanese,chinese,italian}, copied in memory with
// lines added to some chunks; every request is intercepted and the server's
// answers are written here.
//
// A CHUNK WITHOUT WORDS IS HELD BYTE FOR BYTE TO A PLAYER THAT STAYS PUT:
// tests/fixtures/player_base/, the player as it was committed at 0519a1f
// (`git show 0519a1f:youtube/lib/<file>`, copied there once, by hand, and
// never refreshed by a run).  The base was a git revision, and a revision is
// the wrong thing to hold a player to twice over.  7a02e64, the player before
// words, went in the squash, and a revision git cannot show stopped the suite
// before its first check.  HEAD, which took its place, is the working tree
// itself the moment the work is committed: in any clean checkout both builds
// ran the same page, script and style over the same annotations, and every
// comparison below compared a render with itself -- it guarded only what
// happened to be uncommitted, and a regression committed while the suite was
// red or skipped became the base.  A copy under tests/ changes only when
// somebody changes it, in a commit that says so.  PLAYER_BASE, a git
// revision, still overrides it (PLAYER_BASE=HEAD compares with the last
// commit, to see what uncommitted work has changed).
//
// THE BASE IS THE PAGE AS A WHOLE, not its script alone: player.html,
// player.js and style.css come from the same place together.  Its script
// dropped into today's page met a page that had lost an element it still set
// (the draft badge, #draft), threw in its boot, and drew no transcript at all
// -- the same death as a revision git cannot show.  What the page loads from
// /lib/ is today's, for both.
//
// The base already draws word lines (BASE_KNOWS_WORDS), so a worded chunk is
// held to it byte for byte too; and because a base is only ever as right as
// the day it was taken, every worded chunk is ALSO held directly to its own
// line, whatever the base does: one .wd[data-w] per word of the line, in its
// order, the text given back (drawnFromLines).
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const dec = new TextDecoder();
async function out(cmd, args) {
  const r = await new Deno.Command(cmd, {args, stdout:'piped', stderr:'piped'}).output();
  if (!r.success) throw Error(cmd + ': ' + dec.decode(r.stderr));
  return dec.decode(r.stdout);
}
const REG = JSON.parse(await out(Deno.env.get('PARSEH_PYTHON') || 'python3', ['-c',
  'import json,sys; sys.path.insert(0,"lib"); import languages as L; ' +
  'print(json.dumps({"langs": {c: L.LANGS[c].as_json() for c in ("ja","zh","it")}, ' +
  '"gloss": L.gloss_or_default("en").as_json()}))']));
const BASE_REV = Deno.env.get('PLAYER_BASE') || '';
const BASE_DIR = 'tests/fixtures/player_base/';
const BASE = {};
for (const f of ['player.html', 'player.js', 'style.css'])
  BASE['/youtube/lib/' + f] = BASE_REV ? await out('git', ['show', BASE_REV + ':youtube/lib/' + f])
                                       : await Deno.readTextFile(BASE_DIR + f);
console.log('the base: ' + (BASE_REV ? 'git revision ' + BASE_REV : BASE_DIR));
const PAGE = await Deno.readTextFile('youtube/lib/player.html');
// A base that already draws word lines (the vendored one does: the player
// before words went with its commit) is not a player "before words", so a
// worded chunk cannot be told apart from it -- there it is held to it byte
// for byte instead, like every other chunk (sameAsBefore), and to its own
// line directly (drawnFromLines).
const BASE_KNOWS_WORDS = BASE['/youtube/lib/player.js'].includes('words-bad');

const FIX = {
  ja: {id:'aB3dE5fG7hI', dir:'tests/fixtures/videos/japanese/aB3dE5fG7hI'},
  zh: {id:'zH8cN2hA6nZ', dir:'tests/fixtures/videos/chinese/zH8cN2hA6nZ'},
  it: {id:'kL9mN1oP3qR', dir:'tests/fixtures/videos/italian/kL9mN1oP3qR'},
};
// "segment:chunk" -> the line; コーヒー を を does not give its text back
const LINES = {
  ja: {'2:0':'今日(きょう) は', '2:1':'天気(てんき) が', '3:1':'毎朝(まいあさ)', '3:2':'コーヒー を を',
       '3:3':'飲みます(のみます)', '4:0':'駅(えき) まで', '5:0':'この 本(ほん) は'},
  zh: {'1:1':'我(wǒ) 想(xiǎng) 要(yào) 一(yì) 杯(bēi) 茶(chá)', '2:1':'你(nǐ) 要(yào) 什么(shénme) 茶(chá)',
       '3:0':'绿茶(lǜchá) ，'},
};
const PROPOSALS = {'いいですね':'いい です ね'};
const eq = (got, want, msg) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw Error(msg + ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
};
const ok = (v, msg) => { if (!v) throw Error(msg); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 8000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw Error('timed out: ' + what);
    await sleep(60);
  }
}
const parse = line => line.trim().split(/\s+/).map(t => { const m = /^(.+?)\((.*)\)$/.exec(t); return m ? [m[1], m[2]] : [t, '']; });
const gives = (line, fa) => parse(line).map(p => p[0]).join('') === fa.replace(/\s+/g, '');

async function annotations(lang) {
  const data = JSON.parse(await Deno.readTextFile(FIX[lang].dir + '/annotations.json'));
  for (const [at, line] of Object.entries(LINES[lang] || {})) {
    const [s, c] = at.split(':').map(Number), seg = data.segments[s];
    // "words" directly after "fa", where the format puts it
    seg.chunks[c] = Object.fromEntries(Object.entries(seg.chunks[c])
      .flatMap(([k, v]) => k === 'fa' ? [[k, v], ['words', line]] : [[k, v]]));
  }
  // two phrases nobody wrote a vocabulary for, so the dictionary is asked:
  // one divided into words and one not
  if (lang === 'ja') { delete data.segments[4].chunks[0].voc; delete data.segments[6].chunks[0].voc; }
  // a stray kana copied from a Japanese template onto a Chinese chunk with no
  // words: the player never hung it over the text, and must not start to
  if (lang === 'zh') data.segments[4].chunks[1].kana = 'りゃんふんちょんじゅうはお';
  return data;
}

const browser = await chromium.launch({executablePath:Deno.env.get('CHROME_BIN'), headless:true});
const errors = [];
async function open(lang, storage = {}, {build = 'mine', available = true} = {}) {
  const context = await browser.newContext({viewport:{width:1280, height:900}});
  const page = await context.newPage();
  const ann = await annotations(lang), rec = {lookup:[], words:[], edit:[], divide:[]};
  page.on('pageerror', e => { errors.push(lang + ' ' + build + ': ' + e.message); console.log('PAGE ERROR', lang, build, e.message); });
  const cfg = {id:FIX[lang].id, ann:'/fixture/' + lang + '/annotations.json', lang:REG.langs[lang],
               gloss:REG.gloss, local:true, notes:'', editable:{}};
  const html = (build === 'base' ? BASE['/youtube/lib/player.html'] : PAGE)
    .replace('__YTFRANK__', JSON.stringify(cfg)).replaceAll('__BASE__', '/youtube')
    .replaceAll('__LANG__', lang).replaceAll('__LANG_DIR__', 'ltr');
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname;
    if (url.hostname !== 'parseh.test') return route.abort();
    const json = j => route.fulfill({json:j});
    if (p === '/blank') return route.fulfill({body:'<!doctype html><title>blank</title>', contentType:'text/html'});
    if (p === '/video') return route.fulfill({body:html, contentType:'text/html'});
    if (p === cfg.ann) return json(ann);
    if (p === cfg.ann.replace('annotations.json', 'video.json'))
      return route.fulfill({body:await Deno.readTextFile(FIX[lang].dir + '/video.json'), contentType:'application/json'});
    if (build === 'base' && (p === '/youtube/lib/player.js' || p === '/youtube/lib/style.css'))
      return route.fulfill({body:BASE[p], contentType:p.endsWith('.js') ? 'text/javascript' : 'text/css'});
    if (p === '/lib/wordline.js')
      return route.fulfill({body:(await Deno.readTextFile('lib/wordline.js')), contentType:'text/javascript'});
    if (p === '/anki/decks') return json([]);
    // no translation model: one answered by the catch-all below would be a
    // model that never translates, and the look-ahead would wait on it forever
    if (p.startsWith('/mt/')) return route.fulfill({status:404, body:'no model'});
    if (p === '/lookup/api/decompositions') return json({ok:true, packs:[{have:true, languages:['ja', 'zh']}]});
    if (p === '/youtube/api/lookup') {
      const b = req.postDataJSON();
      if (b.about) return json({ok:true, help:true, available:true, corpus_available:true,
                                source:{source:'a test dictionary'}, corpus:{source:'Tatoeba'}});
      rec.lookup.push(b);
      if (b.corpus_only) return json({ok:true, pairs:[], pairs_more:false, pairs_offset:b.corpus_offset || 0});
      // a line's rows come back last word first, each spelled otherwise than
      // the line and naming its place in it: the page places them by `i`
      // A COMPOUND'S VERB ENTRY, as lib/verbs/fa.py builds one: the light
      // verb's own entry, the \bw it still wants named in `missing`, and the
      // whole compound in `compound` -- one line, the compound said and
      // glossed as a whole, with the verb that conjugates in it after.
      if (b.text === 'コーヒーを')
        return json({ok:true, words:[{word:b.text, tried:[b.text],
          machine:{lemma:'zadan', others:['zad'], pos:'verb', here:true, grammar:'past', who:'UDPipe'}, hits:[{
          fits:true, headword:'zadan', translit:'zadan', pos:'verb', senses:['to beat, hit, strike'],
          vb:{lemma:'zadan', here:'ZADAN (zadan · pres. zan · past zad)',
              tex:'\\vb{zadan}{}{zan}{}{zad}{}{}', plain:'zadan · pres. zan · past zad',
              line:'pres. zan · past zad', complete:false,
              missing:['bw for labxand after it: to smile'],
              compound:{name:'compound verb', whole:'labxand zadan', sound:'',
                        mean:'to smile', word:'labxand',
                        bw:'\\bw{labxand}{}{to smile}',
                        tex:'\\vb{zadan}{}{zan}{}{zad}{}{}\\bw{labxand}{}{to smile}',
                        plain:'labxand zadan to smile (zadan · pres. zan · past zad)',
                        complete:true, missing:[]}}}]}],
          pairs:[], pairs_more:false});
      const words = typeof b.words === 'string'
        ? parse(b.words).map((w, i) => ({word:'?' + w[0], i, tried:[w[0]],
            hits:i ? [] : [{headword:w[0], translit:'x', pos:'noun', senses:['the first word']}]})).reverse()
        : [{word:b.text, tried:[b.text], hits:[{headword:b.text, senses:['the whole phrase']}]}];
      return json({ok:true, words, pairs:[{src:b.text + '。', dst:'An example.', matched:[b.text]}],
                   pairs_more:true, pairs_offset:0, corpus:{source:'Tatoeba'}});
    }
    if (p === '/youtube/api/words') {
      const b = req.postDataJSON(); rec.words.push(b);
      return json({ok:true, words:available && b.text ? (PROPOSALS[b.text] || '') : '', available, python:'test'});
    }
    if (p === '/youtube/api/edit') {
      const b = req.postDataJSON(); rec.edit.push(b);
      const seg = ann.segments[b.segment], now = JSON.parse(JSON.stringify(seg.chunks[b.chunk]));
      for (const [k, v] of Object.entries(b.fields)) {
        // annwrite's own two shapes: a flag is true or the key is gone,
        // everything else is trimmed text and an empty one removes the key
        if (typeof v === 'boolean') { if (v) now[k] = true; else delete now[k]; continue; }
        const t = String(v ?? '').trim(); if (t) now[k] = t; else delete now[k];
      }
      if (now.words && !gives(now.words, now.fa))
        return json({ok:false, error:`segment ${b.segment} (start ${seg.start}) chunk ${b.chunk}: the words do not reproduce the text`});
      seg.chunks[b.chunk] = now;
      return json({ok:true, chunk_now:now});
    }
    if (p === '/youtube/api/divide') {
      const b = req.postDataJSON(); rec.divide.push(b);
      const seg = ann.segments[b.segment];
      if (b.action === 'preview')
        return json({ok:true, chunk:seg.chunks[b.chunk], next:seg.chunks[b.chunk + 1] || null, voc_sep:' · ',
          pieces:[{text:'駅'}, {text:'まで'}],
          cuts:[{first:{fa:'駅', words:'駅(えき)', kana:'えき', tr:'eki', en:'the station'},
                 second:{fa:'まで', words:'まで', kana:'まで', tr:'made', en:'as far as'}, entries:[], notes:[]}]});
      // the server keeps the lines chunkdiv divided, the page having sent none
      seg.chunks.splice(b.chunk, 1, {...b.first, words:'駅(えき)'}, {...b.second, words:'まで'});
      return json({ok:true, chunks:seg.chunks, count:seg.chunks.length});
    }
    try {
      const path = root + decodeURIComponent(p), ext = path.split('.').pop();
      const mime = {html:'text/html', js:'text/javascript', css:'text/css', json:'application/json'}[ext] || 'application/octet-stream';
      return route.fulfill({body:await Deno.readTextFile(path), contentType:mime});
    } catch (_) { return route.fulfill({body:'{}', contentType:'application/json'}); }
  });
  await page.goto('http://parseh.test/blank');
  await page.evaluate(s => { localStorage.clear(); for (const k in s) localStorage.setItem(k, s[k]); }, storage);
  await page.goto('http://parseh.test/video');
  await page.waitForSelector('.seg .fa .w');
  return {page, context, ann, rec};
}

async function hover(page, s, j) {
  await page.mouse.move(1, 1);
  await page.waitForFunction(() => document.querySelector('#cloud').hidden);
  await page.locator(`.seg[data-i="${s}"] .w[data-j="${j}"]`).hover();
  await page.waitForFunction(() => !document.querySelector('#cloud').hidden);
}
const away = async page => { await page.mouse.move(1, 1); await page.waitForFunction(() => document.querySelector('#cloud').hidden); };
const click = (page, sel) => page.evaluate(sel => document.querySelector(sel).click(), sel);
const cloudHTML = page => page.evaluate(() => document.querySelector('#cloud').innerHTML.replace(/<div class="arrow"[^>]*><\/div>/, ''));
const lines = page => page.evaluate(() => [...document.querySelectorAll('#segs .seg .fa')].map(f => f.innerHTML));
const drawn = page => page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(seg => ({
  html:seg.innerHTML,
  els:[...seg.querySelectorAll('.fa > *')].map(el => ({j:el.dataset.j ?? null, cls:el.className, html:el.innerHTML, outer:el.outerHTML}))
})));
// an alt/ctrl-click, and what the card sheet was filled with
const card = (page, sel) => page.evaluate(sel => {
  document.querySelector(sel).dispatchEvent(new MouseEvent('click', {bubbles:true, ctrlKey:true}));
  const v = id => document.querySelector(id).value;
  const got = {fa:v('#afa'), kana:v('#akana'), tr:v('#atr'), ctx:v('#actx')};
  document.querySelector('#acancel').click();
  return got;
}, sel);

// ---- a chunk WITH words is drawn from its own line ----
// Held to the line itself, not to the base: whatever the base draws, a chunk
// carrying a line that gives its text back is drawn one .wd per word of that
// line, each a child of the phrase, named by the word as the line writes it
// (data-w) and numbered in the line's order (data-k), the chunk's own text
// given back between them -- and one whose line does not give it back is
// drawn as a chunk without one, and says so (words-bad), with no word named.
async function drawnFromLines(lang, mine) {
  const got = await mine.page.evaluate(() => [...document.querySelectorAll('#segs .seg')].map(seg =>
    [...seg.querySelectorAll('.fa > .w')].map(w => ({
      j:+w.dataset.j, bad:w.classList.contains('words-bad'), named:w.querySelectorAll('[data-w]').length,
      kids:[...w.children].map(el => [el.className, el.dataset.w ?? null, el.dataset.k ?? null]),
      text:Parseh.baseText(w)}))));
  let worded = 0, bad = 0;
  mine.ann.segments.forEach((sg, s) => (sg.chunks || []).forEach((ch, j) => {
    if (!('words' in ch)) return;
    const w = got[s].find(x => x.j === j), at = `${lang}: caption ${s} phrase ${j}`;
    ok(w, `${at}, with words, is drawn as a phrase`);
    if (!gives(ch.words, ch.fa)) {
      eq([w.bad, w.named, w.text], [true, 0, ch.fa], `${at}, a line that does not give its text back: the text, marked words-bad, no word named`);
      bad++;
      return;
    }
    eq([w.bad, w.kids], [false, ch.words.trim().split(/\s+/).map((t, k) => ['wd', t, String(k)])],
       `${at} is drawn from its line: one .wd[data-w] per word, in the line's order`);
    eq(w.text, ch.fa, `${at}: its words give its text back`);
    worded++;
  }));
  ok(worded >= 3, `${lang}: enough chunks drawn from their lines (${worded})`);
  return {worded, bad};
}

// ---- a chunk without words is the chunk it was ----
async function sameAsBefore(lang, base, mine, clouds) {
  await drawnFromLines(lang, mine);
  const was = await drawn(base.page), now = await drawn(mine.page);
  eq(now.length, was.length, lang + ': every caption drawn');
  let whole = 0, plain = 0;
  was.forEach((seg, s) => {
    const chunks = base.ann.segments[s].chunks || [];
    if (!chunks.some(c => 'words' in c)) { eq(now[s].html, seg.html, `${lang}: caption ${s}, no word line in it, byte for byte`); whole++; }
    eq(now[s].els.length, seg.els.length, `${lang}: caption ${s} has as many phrases`);
    seg.els.forEach((el, k) => {
      const got = now[s].els[k], ch = el.j === null ? null : chunks[+el.j];
      if (!ch || !('words' in ch)) { eq(got.outer, el.outer, `${lang}: caption ${s} phrase ${el.j}, without words, byte for byte`); plain++; }
      else if (BASE_KNOWS_WORDS)
        eq(got.outer, el.outer, `${lang}: caption ${s} phrase ${el.j}, with words, drawn as the committed player draws it`);
      else if (!gives(ch.words, ch.fa))
        eq([got.cls, got.html], [el.cls + ' words-bad', el.html], `${lang}: caption ${s} phrase ${el.j}, a line that does not give its text back, drawn as before`);
      else ok(got.html !== el.html && /<span class="wd" data-w="/.test(got.html), `${lang}: caption ${s} phrase ${el.j} is drawn from its line`);
    });
  });
  ok(whole >= 3 && plain >= 6, `${lang}: enough without words to compare (${whole} captions, ${plain} phrases)`);
  for (const [s, j] of clouds) {
    await hover(base.page, s, j); await hover(mine.page, s, j);
    // two deliberate changes since the base: the cloud's card button reads
    // "+ card", the sheet it opens making an Anki card, an exercise or markdown,
    // and its row ends with the button that flags the phrase for later (a0.5.0)
    const LATER = '<button type="button" class="mklater" aria-pressed="false" title="flag this phrase to come back to it later (L)">review later</button>';
    eq(await cloudHTML(mine.page), (await cloudHTML(base.page)).replace('>+ anki card</button>', '>+ card</button>')
         .replace('</div><div class="colrow">', LATER + '</div><div class="colrow">'),
       `${lang}: the cloud of caption ${s} phrase ${j}, without words, as it was (its card button renamed "+ card", a review later button at the end of its row)`);
  }
  await base.context.close();
}

try {
// ======== Japanese ========
{
  const KNOWN = {yt_pin:'0', ['parseh_known_kanji:video:ja:' + FIX.ja.id]:'["私","分","駅"]'};
  const mine = await open('ja', KNOWN);
  await sameAsBefore('ja', await open('ja', KNOWN, {build:'base'}), mine, [[2, 2], [3, 0]]);
  const {page, ann} = mine;
  await away(page);
  const r = await page.evaluate(() => {
    const w = document.querySelector('.seg[data-i="2"] .w[data-j="0"]');
    const src = [...document.scripts].map(s => s.src && new URL(s.src).pathname);
    return {
      order:[src.indexOf('/lib/wordline.js'), src.indexOf('/youtube/lib/player.js')],
      kids:[...w.childNodes].map(n => n.nodeType === 3 ? ['#text', n.data]
        : [n.className, n.dataset.w, n.dataset.k, n.parentNode === w, (n.querySelector('rt') || {}).textContent || '']),
      text:Parseh.baseText(w),
      one:[...document.querySelectorAll('.seg[data-i="3"] .w[data-j="1"] rt')].map(rt => rt.textContent),
      known:[...document.querySelectorAll('#segs .wd[data-w] ruby.reading-known')].map(x => x.closest('.wd').dataset.w),
      jaRt:getComputedStyle(w.querySelector('rt')).fontFamily
    };
  });
  ok(r.order[0] >= 0 && r.order[0] < r.order[1], 'player.html loads lib/wordline.js before player.js: ' + r.order);
  eq(r.kids, [['wd', '今日(きょう)', '0', true, 'きょう'], ['wd', 'は', '1', true, '']],
     'a worded chunk: one .wd per word, each a child of the phrase, its own reading over it');
  eq([r.text, r.one], ['今日は', ['まいあさ']], 'the text is the chunk\'s, and no ruby over the chunk as a whole');
  eq(r.known, ['駅(えき)'], 'a word whose every kanji is marked known is known');
  ok(!/^-apple-system/.test(r.jaRt), 'the pinyin rule leaves the kana alone: ' + r.jaRt);
  console.log('Japanese: a chunk without words byte for byte, a chunk drawn a word at a time: passed');

  await hover(page, 2, 0);
  const cloud = () => page.evaluate(() => ({
    text:(document.querySelector('#cloud .ctext') || {}).textContent || null,
    kana:(document.querySelector('#cloud .kana') || {}).textContent || null,
    words:[...document.querySelectorAll('#cloud [data-known-word]')].map(b => b.dataset.knownWord),
    kanji:document.querySelectorAll('#cloud [data-known-kanji]').length
  }));
  eq(await cloud(), {text:null, kana:'きょうは', words:['今日(きょう)'], kanji:0},
     'the cloud of a worded chunk keeps its reading line and says "I know this" a word at a time');
  eq(await page.evaluate(id => {
    document.querySelector('#cloud [data-known-word="今日(きょう)"]').click();
    return [getComputedStyle(document.querySelector('.seg[data-i="2"] .wd[data-w="今日(きょう)"] rt')).visibility,
            JSON.parse(localStorage.getItem('parseh_known_word:video:ja:' + id)),
            document.querySelector('#cloud [data-known-word]').textContent];
  }, FIX.ja.id), ['hidden', ['今日(きょう)'], '今日: show reading'], 'the word\'s reading hides in the transcript and is remembered for this video');
  await hover(page, 3, 0);
  eq((await cloud()).words.length === 0 && (await cloud()).kanji > 0, true, 'a chunk without words keeps its kanji controls');
  await hover(page, 3, 2);
  eq((await cloud()).words, [], 'a line that does not give its text back offers no word controls');
  await away(page);

  eq(await card(page, '.seg[data-i="2"] .w[data-j="1"] .wd[data-k="0"] rt'),
     {fa:'天気', kana:'てんき', tr:'tenki ga', ctx:'今日は 天気が いいですね'}, 'alt-click on a word: the word, its reading, the caption');
  eq(await card(page, '.seg[data-i="3"] .w[data-j="0"] .wd'),
     {fa:'私は', kana:'わたしは', tr:'watashi wa', ctx:'私は毎朝コーヒーを飲みます'}, 'alt-click on a chunk without words: the chunk, as before');
  console.log('Japanese: the cloud, per-word "I know this", the word\'s card: passed');

  // the reading alone
  await away(page);
  const before = await lines(page);
  eq(await page.evaluate(() => [document.querySelector('#aloud').hidden, document.querySelector('#aloud').textContent]), [false, 'kana only'],
     'a language divided into words has the button, named after its reading');
  await click(page, '#aloud');
  const aloud = () => page.evaluate(ann => [...document.querySelectorAll('#segs .seg .fa .w')].map(w => {
    const ch = ann.segments[+w.parentNode.parentNode.dataset.i].chunks[+w.dataset.j];
    return w.textContent === ParsehWordline.aloud(ch.kana || '', ch.fa) && !w.querySelector('rt,[data-w]') &&
           getComputedStyle(w).fontSize === getComputedStyle(w.parentNode).fontSize ? '' : w.outerHTML;
  }).filter(Boolean), ann);
  eq(await aloud(), [], 'every phrase shows its reading alone, at the transcript\'s size');
  eq(await page.evaluate(() => [document.body.classList.contains('aloud'), document.querySelector('#aloud').classList.contains('on'),
     localStorage.getItem('yt_aloud')]), [true, true, '1'], 'the switch is on, and remembered');
  await hover(page, 2, 1);
  eq(await page.evaluate(() => ['.ctext', '.kana', '.en'].map(s => document.querySelector('#cloud ' + s).textContent)),
     ['天気が', 'てんきが', 'the weather'], 'hovering still gives the text, its reading and its gloss');
  await page.reload();
  await page.waitForSelector('.seg .fa .w');
  eq([await aloud(), await page.evaluate(() => document.body.classList.contains('aloud'))], [[], true], 'and it is still on after a reload');
  await away(page);
  await click(page, '#aloud');
  eq(await lines(page), before, 'off again, every phrase is drawn exactly as it was');
  await mine.context.close();
  console.log('Japanese: the reading alone, on, hovered, reloaded, off: passed');
}

// ======== Chinese ========
{
  const mine = await open('zh', {yt_pin:'0'});
  await sameAsBefore('zh', await open('zh', {yt_pin:'0'}, {build:'base'}), mine, [[4, 0], [4, 1], [5, 0]]);
  eq(await mine.page.evaluate(() => document.querySelectorAll('#segs rt').length), 6 + 4 + 1,
     'ruby only over words a line drew, never from a stray kana');
  const {page} = mine;
  await away(page);
  eq(await page.evaluate(() => [...document.querySelectorAll('.seg[data-i="1"] .w[data-j="1"] > .wd')].map(w => w.dataset.w + '|' + w.querySelector('rt').textContent)),
     ['我(wǒ)|wǒ', '想(xiǎng)|xiǎng', '要(yào)|yào', '一(yì)|yì', '杯(bēi)|bēi', '茶(chá)|chá'], 'pinyin over each word');
  const css = await page.evaluate(() => {
    document.documentElement.style.setProperty('--cjk-space', '0.3em');
    const w = document.querySelector('.seg[data-i="1"] .w[data-j="1"]'), rts = [...w.querySelectorAll('rt')];
    const box = el => el.getBoundingClientRect(), fs = parseFloat(getComputedStyle(w).fontSize);
    // the baseline under a word, from a marker of no size set on it
    const baseline = rt => {
      const m = document.createElement('span');
      m.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
      rt.parentNode.insertBefore(m, rt); const y = box(m).top; m.remove(); return y;
    };
    // what a syllable measures set on its own, in the rt's face and size
    const natural = rt => {
      const c = getComputedStyle(rt), s = document.createElement('span');
      s.style.cssText = `position:absolute;white-space:nowrap;font:${c.fontStyle} ${c.fontWeight} ${c.fontSize} ${c.fontFamily};letter-spacing:${c.letterSpacing}`;
      s.textContent = rt.textContent; document.body.appendChild(s);
      const wd = box(s).width; s.remove(); return wd;
    };
    const st = getComputedStyle(rts[0]);
    const got = {style:st.fontStyle, latin:/^-apple-system/.test(st.fontFamily), size:parseFloat(st.fontSize),
      base:fs, spacing:st.letterSpacing,
      overlap:rts.slice(1).some((rt, i) => Math.abs(box(rts[i]).top - box(rt).top) < 2 && box(rts[i]).right > box(rt).left + 0.5),
      // each column holds its syllable, and the pinyin stays over the
      // characters' em box (a CJK glyph's top is 0.88em over its baseline)
      fits:rts.every(rt => box(rt).width + 0.5 >= natural(rt)),
      over:rts.every(rt => box(rt).height > 0 && box(rt).bottom <= baseline(rt) - 0.88 * fs + 1)};
    document.documentElement.style.removeProperty('--cjk-space');
    return got;
  });
  ok(css.style === 'normal' && css.latin && css.size >= 10 && css.size < css.base && ['0px', 'normal'].includes(css.spacing) &&
     !css.overlap && css.fits && css.over,
     'pinyin is small, upright, Latin, unspaced, and sits over its word without running into the next: ' + JSON.stringify(css));

  await hover(page, 1, 1);
  eq(await page.evaluate(() => [document.querySelector('#cloud .tr').textContent, !!document.querySelector('#cloud .kana')]),
     ['wǒ xiǎng yào yì bēi chá', false], 'the chunk\'s own pinyin stays in the cloud');
  eq(await page.evaluate(() => {
    document.querySelector('#cloud [data-known-word="茶(chá)"]').click();
    return [...document.querySelectorAll('#segs .wd[data-w] ruby.reading-known')].map(r => r.closest('.w').dataset.j + ':' + r.closest('.wd').dataset.w);
  }), ['1:茶(chá)', '1:茶(chá)'], 'a word known is known wherever it appears, and only that word');
  await away(page);
  eq(await card(page, '.seg[data-i="1"] .w[data-j="1"] .wd[data-k="5"]'),
     {fa:'茶', kana:'', tr:'chá', ctx:'你好，我想要一杯茶'}, 'a Chinese word\'s card takes its pinyin as the transliteration');

  const before = await lines(page);
  eq(await page.evaluate(() => document.querySelector('#aloud').textContent), 'pinyin only', 'the button is named after pinyin: «pinyin only»');
  await click(page, '#aloud');
  eq(await page.evaluate(() => {
    // with character spacing set, which pinyin alone must not take
    document.documentElement.style.setProperty('--cjk-space', '0.3em');
    const w = j => document.querySelector(`.seg[data-i="1"] .w[data-j="${j}"]`);
    const got = [w(0).textContent, w(1).textContent, getComputedStyle(w(0).parentNode).letterSpacing,
            parseFloat(getComputedStyle(w(0)).marginInlineStart), parseFloat(getComputedStyle(w(1)).marginInlineStart) > 0];
    document.documentElement.style.removeProperty('--cjk-space');
    return got;
  }), ['nǐ hǎo，', 'wǒ xiǎng yào yì bēi chá', 'normal', 0, true], 'pinyin alone, its trailing stop kept, unspaced, two phrases parted');
  await click(page, '#aloud');
  eq(await lines(page), before, 'and drawn again exactly as it was');
  await mine.context.close();
  console.log('Chinese: byte for byte, pinyin per word and its stylesheet, known words, card, pinyin alone: passed');
}

// ======== a language with no word layer ========
{
  const it = await open('it', {yt_pin:'0', yt_aloud:'1'});
  eq(await it.page.evaluate(ann => [document.querySelector('#aloud').hidden, document.body.classList.contains('aloud'),
     [...document.querySelectorAll('#segs .seg .fa .w')].filter(w =>
       w.textContent !== ann.segments[+w.parentNode.parentNode.dataset.i].chunks[+w.dataset.j].fa).map(w => w.outerHTML)],
     it.ann), [true, false, []], 'no button without a word layer, and a preference left on changes nothing');
  await it.context.close();
}

// ======== the editor's word strip ========
{
  const {page, rec, context} = await open('ja', {yt_pin:'0'});
  const strip = () => page.evaluate(() => ({
    value:document.querySelector('#cloud .ws-text').value,
    propose:!document.querySelector('#cloud .ws-propose').hidden,
    errors:[...document.querySelectorAll('#cloud .ws-note .ws-err')].map(e => e.textContent).join(' '),
    under:document.querySelector('#cloud .ef[data-f="fa"]').closest('.erow').nextElementSibling.contains(document.querySelector('#cloud .wordstrip'))
  }));
  const stat = () => page.evaluate(() => { const s = document.querySelector('#cloud .cstat'); return [s.textContent, s.classList.contains('bad')]; });
  const saved = async n => { await click(page, '#cloud .esave'); await until(() => rec.edit.length === n, 'edit ' + n); return rec.edit[n - 1]; };
  await hover(page, 2, 2);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .wordstrip');
  const s0 = await strip();
  eq([s0.value, s0.under], ['', true], 'the words row sits under the text, empty for a chunk without words');
  await until(() => rec.words.length === 1, 'the probe');
  eq(rec.words[0], {video:FIX.ja.id, text:''}, 'one probe asks whether anything can propose');
  await page.waitForFunction(() => !document.querySelector('#cloud .ws-propose').hidden);
  await click(page, '#cloud .ws-propose');
  await until(() => rec.words.length === 2, 'the proposal');
  eq(rec.words[1], {video:FIX.ja.id, text:'いいですね', reading:'いいですね'}, 'propose sends the text box\'s text, and the reading box\'s reading');
  await page.waitForFunction(() => document.querySelector('#cloud .ws-text').value === 'いい です ね');
  eq((await saved(1)), {video:FIX.ja.id, segment:2, chunk:2, fields:{words:'いい です ね'}}, 'a changed line is sent, alone');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="2"] .w[data-j="2"] > .wd[data-w]').length === 3);
  eq(await stat(), ['saved ✓', false], 'and drawn from the answer');
  await click(page, '#cloud .ecancel');

  await hover(page, 2, 2);
  eq(await page.evaluate(() => { document.querySelector('#cloud .mkedit').click(); return !document.querySelector('#cloud .ws-propose').hidden; }), true,
     'the next editor offers propose at once');
  eq(rec.words.filter(b => b.text === '').length, 1, 'and the probe was asked once for the page');
  await page.locator('#cloud .ef[data-f="fa"]').fill('いいですねえ');
  const s1 = await strip();
  eq(s1.value, 'いい です ね', 'a changed text makes the strip again, keeping its line');
  ok(/do not reproduce/.test(s1.errors), 'and checks the line against the new text: ' + s1.errors);
  eq((await saved(2)).fields, {fa:'いいですねえ', words:'いい です ね'}, 'a changed text goes with its line');
  await page.waitForFunction(() => document.querySelector('#cloud .cstat').classList.contains('bad'));
  ok(/do not reproduce/.test((await stat())[0]), 'the refusal is shown in the server\'s words');
  await page.locator('#cloud .ef[data-f="fa"]').fill('いいですね');
  await click(page, '#cloud .esave');
  eq([(await stat())[0], rec.edit.length], ['nothing changed', 2], 'nothing changed is nothing sent');
  await page.locator('#cloud .ef[data-f="fa"]').fill('いい ですね');
  eq((await saved(3)).fields, {fa:'いい ですね', words:'いい です ね'}, 'the line goes with a changed text even when it is the same line');
  await page.waitForFunction(() => document.querySelector('.seg[data-i="2"] .w[data-j="2"]').childNodes.length === 4);
  eq(await page.evaluate(() => [...document.querySelector('.seg[data-i="2"] .w[data-j="2"]').childNodes].map(n => n.nodeType === 3 ? '#' + n.data : n.dataset.w)),
     ['いい', '# ', 'です', 'ね'], 'the phrase is drawn from the answer, its space kept between words');
  await click(page, '#cloud .ecancel');

  await hover(page, 3, 0);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .wordstrip');
  await page.locator('#cloud .ef[data-f="fa"]').fill('私わ');
  eq((await saved(4)).fields, {fa:'私わ'}, 'a chunk without words sends no line with its text');
  await click(page, '#cloud .ecancel');
  await context.close();
  console.log('Editor: the word strip, the probe, propose, what a save sends, a refusal: passed');
}

// ======== the box that frees a phrase from the transcript ========
{
  const {page, rec, ann, context} = await open('ja', {yt_pin:'0'});
  const box = () => page.evaluate(() => {
    const b = document.querySelector('#cloud .efree');
    return b && {checked:b.checked, after:b.closest('.erow') === document.querySelector('#cloud .emain').lastElementChild,
                 says:b.closest('.echk').textContent.trim(), note:!!document.querySelector('#cloud .efnote')};
  });
  const saved = async n => { await click(page, '#cloud .esave'); await until(() => rec.edit.length === n, 'edit ' + n); return rec.edit[n - 1]; };
  const stat = () => page.evaluate(() => document.querySelector('#cloud .cstat').textContent);
  await hover(page, 3, 0);            // 私は: no word line, so nothing else rides along
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .efree');
  const b0 = await box();
  eq([b0.checked, b0.after, b0.note], [false, true, true], 'an unmarked phrase opens with the box clear, last under the fields, its note with it');
  eq(b0.says, 'this phrase need not reproduce transcript.txt', 'and the box says what ticking it means');
  // the box alone is a change
  await page.locator('#cloud .efree').check();
  eq((await saved(1)).fields, {free:true}, 'the mark on its own is sent on its own');
  await page.waitForFunction(() => document.querySelector('#cloud .cstat').textContent === 'saved ✓');
  eq(ann.segments[3].chunks[0].free, true, 'and lands on the chunk');
  eq((await box()).checked, true, 'the box says what the answer says');
  await click(page, '#cloud .esave');
  eq([await stat(), rec.edit.length], ['nothing changed', 1], 'and an unmoved box is nothing to send');
  // and it goes with the edit it permits
  await page.locator('#cloud .ef[data-f="fa"]').fill('私わ');
  eq((await saved(2)).fields, {fa:'私わ'}, 'a text edit under a mark already on sends the text alone');
  await page.locator('#cloud .efree').uncheck();
  await page.locator('#cloud .ef[data-f="fa"]').fill('私は');
  eq((await saved(3)).fields, {fa:'私は', free:false}, 'the words put back and the box cleared travel together');
  await page.waitForFunction(() => document.querySelector('#cloud .cstat').textContent === 'saved ✓');
  eq('free' in ann.segments[3].chunks[0], false, 'and the key goes off the chunk');
  await click(page, '#cloud .ecancel');
  // a phrase that carries the mark in the file opens ticked: put it in the
  // file the page is served and load the page again
  ann.segments[4].chunks[0].free = true;
  await page.reload();
  await page.waitForSelector('.seg .fa .w');
  await hover(page, 4, 0);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .efree');
  eq((await box()).checked, true, 'a phrase already marked in the file opens with the box ticked');
  await click(page, '#cloud .ecancel');
  await context.close();
  console.log('Editor: the transcript box -- clear, ticked, sent with the edit it permits, read back from the file: passed');
}

// ======== the lookup's words, and a divide ========
{
  const {page, rec, context} = await open('ja', {yt_pin:'0', yt_dict:'1'}, {available:false});
  const L4 = LINES.ja['4:0'];
  const asked = t => rec.lookup.filter(b => b.text === t && !b.corpus_only);
  await until(() => asked('駅まで').length && asked('少し').length, 'the look-ahead', 15000);
  eq([asked('駅まで')[0].words, 'words' in asked('少し')[0]], [L4, false], 'the look-ahead sends a chunk\'s word line, and none for a chunk without');
  await hover(page, 4, 0);
  await page.waitForSelector('#cloud .ddict');
  eq(await page.evaluate(() => [...document.querySelectorAll('#cloud .ddict .dwd')].map(d => d.textContent)), ['まで', '駅 えき'],
     'each row is placed under the word of the line its i names');
  eq(asked('駅まで').length, 1, 'and the answer kept for that line is the one shown');
  await click(page, '#cloud .dmore');
  await until(() => rec.lookup.some(b => b.corpus_only && b.text === '駅まで'), 'Load more');
  eq(rec.lookup.find(b => b.corpus_only && b.text === '駅まで').words, L4, 'Load more sends the line too');
  await hover(page, 6, 0);
  await page.waitForSelector('#cloud .ddict');
  eq(await page.evaluate(() => [...document.querySelectorAll('#cloud .ddict .dwd')].map(d => d.textContent)), ['少し'],
     'a chunk without words is headed as the dictionary answered');

  await hover(page, 4, 0);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .wordstrip');
  await until(() => rec.words.length === 1, 'the probe');
  await sleep(200);
  eq(await page.evaluate(() => document.querySelector('#cloud .ws-propose').hidden), true, 'nothing to propose with, no propose');
  await click(page, '#cloud .ws-astext');
  await page.locator('#cloud .ws-text').fill('駅まで(えきまで)');
  await click(page, '#cloud .esave');
  await until(() => rec.edit.length === 1, 'the edit');
  await page.waitForFunction(() => document.querySelector('.seg[data-i="4"] .w[data-j="0"] .wd[data-w="駅まで(えきまで)"]'));
  await click(page, '#cloud .ecancel');
  await hover(page, 4, 0);
  await until(() => asked('駅まで').some(b => b.words === '駅まで(えきまで)'), 'a new line is a new answer');

  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .esrc');
  await click(page, '#cloud .esrc');
  await until(() => rec.lookup.some(b => b.corpus_only && b.corpus_limit === 50 && b.text === '駅まで'), 'the sources and the chatbot\'s corpus pages');
  const wrong = rec.lookup.filter(b => (b.text === '駅まで' && !(b.words === L4 || b.words === '駅まで(えきまで)')) || (b.text === '少し' && 'words' in b));
  eq(wrong, [], 'every lookup of a worded chunk carries its line, and none of a chunk without');

  // A VERB THAT IS MORE THAN ONE WORD HAS ITS OWN BUTTON.  The light verb
  // and the word it carries are ONE verb, and the compound goes in as one
  // line of its own; the plain button stays what it was, the light verb
  // alone and dashed.
  await click(page, '#cloud .ecancel');
  await hover(page, 3, 2);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .esrc');
  await click(page, '#cloud .esrc');
  await until(() => page.locator('#cloud .esrcbody .sput button').count().then(n => n > 0),
              'the sources answer for the compound');
  // what the analyzer read, where a gloss is written from (lib/lookupassist.py)
  eq(await page.locator('#cloud .esrcbody .dposhere').textContent(), 'verb', 'the sources say the part of speech in this sentence');
  ok(/from zadan .* past .* can also be zad \(UDPipe\)/.test(await page.locator('#cloud .esrcbody .sreadl').textContent()), 'and the rest of the reading');
  eq(await page.locator('#cloud .esrcbody .sfits .dfits').textContent(), 'fits this sentence', 'and the entry that fits says so');
  const cmpBtn = page.locator('#cloud .esrcbody .sput button', {hasText: 'compound verb'});
  const vocBtn = page.locator('#cloud .esrcbody .sput button', {hasText: 'vocabulary'});
  const labels = await page.evaluate(
    () => [...document.querySelectorAll('#cloud .esrcbody .sput button')].map(b => b.textContent));
  ok(labels.indexOf('\u2192 compound verb') >= 0 &&
     labels.indexOf('\u2192 compound verb') < labels.indexOf('\u2192 vocabulary'),
     'a compound gets a button of its own, before the plain one: ' + labels.join(' | '));
  ok((await cmpBtn.getAttribute('title')).includes(
       'is ONE verb written in two words, not two entries'),
     'which says in so many words what the pair is: ' + await cmpBtn.getAttribute('title'));
  eq(await cmpBtn.evaluate(b => b.className.includes('sgap')), false,
     'and is not drawn unfinished, since nothing is left to type');
  ok(await page.evaluate(() => /to fill in/.test(document.querySelector('#cloud .esrcbody').textContent)),
     'the row still names the \\bw under "to fill in"');
  await page.evaluate(() => { document.querySelector('#cloud .ef[data-f="voc"]').value = ''; });
  await cmpBtn.evaluate(b => b.click());   // the sidebar scrolls; the press is what is tested
  eq(await page.inputValue('#cloud .ef[data-f="voc"]'),
     'labxand zadan to smile (zadan \u00b7 pres. zan \u00b7 past zad)',
     'and one press puts the whole compound in as one entry');
  await page.evaluate(() => { document.querySelector('#cloud .ef[data-f="voc"]').value = ''; });
  await vocBtn.evaluate(b => b.click());
  eq(await page.inputValue('#cloud .ef[data-f="voc"]'),
     'ZADAN (zadan \u00b7 pres. zan \u00b7 past zad)',
     'the plain button is untouched: the light verb alone');
  eq(await vocBtn.evaluate(b => b.className.includes('sgap')), true,
     'and still dashed, half a verb being what it puts');
  await click(page, '#cloud .ecancel');
  await hover(page, 4, 0);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .edv[data-dv="split"]');

  await click(page, '#cloud .edv[data-dv="split"]');
  await page.waitForFunction(() => !document.querySelector('#dvbox').hidden && !document.querySelector('#dvdo').disabled);
  await click(page, '#dvdo');
  await until(() => rec.divide.some(b => b.action === 'split'), 'the divide');
  ok(!JSON.stringify(rec.divide.find(b => b.action === 'split')).includes('"words"'), 'the divide sheet never sends a line');
  await page.waitForFunction(() => document.querySelector('.seg[data-i="4"] .w[data-j="0"] > .wd[data-w="駅(えき)"]') &&
                                   document.querySelector('.seg[data-i="4"] .w[data-j="1"] > .wd[data-w="まで"]'));
  await context.close();
  console.log('Lookup: the line in every body, rows placed by i, the cache keyed by the line; the divide sends none: passed');
}

// ======== decomposition mode over words, a repaint and the reading alone ========
{
  const {page, rec, context} = await open('ja', {yt_pin:'0'});
  const phrase = (s, j) => page.evaluate(([s, j]) => document.querySelector(`.seg[data-i="${s}"] .w[data-j="${j}"]`).outerHTML, [s, j]);
  const was = [await phrase(2, 0), await phrase(3, 0)];
  // the editor first: the mode closes a cloud, never a form being written
  await hover(page, 2, 1);
  await click(page, '#cloud .mkedit');
  await page.waitForSelector('#cloud .wordstrip');
  await click(page, '.cd-toggle');
  await page.waitForFunction(() => document.body.classList.contains('cd-mode') && document.querySelector('#segs .cd-char'));
  await page.evaluate(() => { window.muts = 0; new MutationObserver(() => window.muts++).observe(document.querySelector('#segs'), {subtree:true, childList:true, characterData:true}); });
  async function settles(what) {
    let last = await page.evaluate(() => muts);
    for (let i = 0; ; i++) {
      await sleep(250);
      const n = await page.evaluate(() => muts);
      if (n === last) return;
      if (i > 20) throw Error(what + ': the transcript never settles');
      last = n;
    }
  }
  const words = (s, j) => page.evaluate(([s, j]) => {
    const w = document.querySelector(`.seg[data-i="${s}"] .w[data-j="${j}"]`);
    return {wd:[...w.children].map(c => c.dataset.w || c.className), direct:[...w.querySelectorAll('.wd')].every(d => d.parentNode === w),
            chars:[...w.querySelectorAll('ruby > .cd-char')].map(c => c.textContent).join(''),
            inRt:document.querySelectorAll('#segs rt .cd-char').length};
  }, [s, j]);
  const worded = {wd:['今日(きょう)', 'は'], direct:true, chars:'今日', inRt:0};
  eq(await words(2, 0), worded, 'the mode takes the characters of a word drawn from its line, and leaves the words where they are');
  await click(page, '#aloud');
  await settles('the reading alone, on');
  eq(await page.evaluate(() => [document.querySelector('.seg[data-i="2"] .w[data-j="0"]').textContent,
     document.querySelectorAll('#segs .wd[data-w]').length]), ['きょうは', 0], 'the reading alone, in the mode');
  await click(page, '#aloud');
  await settles('the reading alone, off');
  eq(await words(2, 0), worded, 'off again, the words come back and the mode takes their characters again');
  await click(page, '#cloud .ws-astext');
  await page.locator('#cloud .ws-text').fill('天(てん) 気(き) が');
  await click(page, '#cloud .esave');
  await until(() => rec.edit.length === 1, 'the edit');
  await page.waitForFunction(() => document.querySelectorAll('.seg[data-i="2"] .w[data-j="1"] > .wd[data-w]').length === 3);
  await settles('a phrase drawn again a word at a time');
  eq(await words(2, 1), {wd:['天(てん)', '気(き)', 'が'], direct:true, chars:'天気', inRt:0}, 'a saved line is drawn a word at a time, and the mode takes it');
  await click(page, '.cd-toggle');
  await page.waitForFunction(() => !document.body.classList.contains('cd-mode'));
  eq([await page.evaluate(() => document.querySelectorAll('#segs .cd-char').length), await phrase(2, 0), await phrase(3, 0)], [0, ...was],
     'leaving the mode leaves every phrase as it was drawn');
  await click(page, '#cloud .ecancel');
  await context.close();
  console.log('Decomposition mode: a per-word repaint and the reading alone settle, and leave the words intact: passed');
}
if (errors.length) throw Error(errors.join('\n'));
} finally { await browser.close(); }
