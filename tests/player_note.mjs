// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/player_note.mjs
//      PARSEH_KEEP=1 keeps the temporary tree, to read what was written
//      NOTE_SHOTS=<dir> saves the form, the cloud and the transcript with ✱ notes on, in the three themes
//
// THE NOTE OF A VIDEO'S PHRASE, in the video player (youtube/lib/player.js, player.html, style.css) on the
// REAL hub: serve.main() over a temporary tree of temporary copies of the fixture videos -- Japanese (which
// carries a note of its own), Persian glossed in Arabic (a right-to-left line AND a right-to-left gloss, with
// the note of a slip in the transcript) and Italian (three notes, one of them on a chunk drawn bare, and one
// blank).  Nothing is stubbed but YouTube's iframe API.  Every action is the page's own: a phrase hovered, the
// ✎ in its cloud, the keys, the buttons of the bar.
//
//  a) THE OWNER'S CASE: a note an LLM left about a slip in the transcript; the phrase mended through the
//     `free` tick; the note emptied in the ✎ form -- and the file's diff is the one line the note was on, the
//     transcript is never touched, a reload shows the phrase with no note.  The form's note row: in the gloss
//     language's face and direction, under the meaning, with the line that says how a note is taken off.
//  b) the form: the box holds the note; a changed note is saved, drawn in the cloud and there after a reload;
//     a phrase with no note takes one; a card made of the phrase carries it; nothing changed is said so and
//     asks the server nothing.
//  c) the ✱ notes button: in the browser mode and not in the mobile one; off on every visit, with ‹ › out of
//     sight and not a class on the page (on and off again, the transcript is byte for byte what it was); on,
//     its count is the file's (a blank note is not one), every such phrase is dashed under in the accent and
//     followed by a ✱ the stylesheet draws -- no text added to a line, a colour mark showing beside it -- and
//     ‹ › visit them in order, wrapping, each scrolled into view below the bar and the video (in a window as
//     narrow as a phone's, where the bar slides away as the page moves, it stays while the walk is on; and
//     with the video beside the transcript); a note written or taken off in the form updates it at once;
//     hovering still opens the cloud and a click still replays; it asks the server for nothing and writes
//     nothing; a reload finds it off; the mode switched under it takes the highlight away.
//  d) the screenshots (NOTE_SHOTS): a right-to-left line with a right-to-left gloss, and a left-to-right one,
//     at 1280 and 390 px, in the light, dark and sepia themes.
//  e) last: no page threw, logged an error or had a request refused; the hub printed no traceback; the
//     owner's config/, books/, youtube/videos/ and the fixtures are as they were.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-player-note-'});
const SHOTS = Deno.env.get('NOTE_SHOTS') || '';
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

/* ---------------- the toolbox ---------------- */
// Persian glossed in ARABIC: a line that reads right to left over a gloss that does too
const ARABIC = {'سلام،': 'مرحبا،', 'ببخشید': 'عفوا،', 'سیب چند است': 'بكم التفاح',
  'کیلویی سی هزار تومان،': 'ثلاثون ألف تومان للكيلو،', 'تازه آمده': 'وصل للتو',
  'دو کیلو می‌خواهم': 'أريد كيلوين', 'لطفا': 'من فضلك', 'چشم،': 'حاضر،', 'چیز دیگری': 'شيئا آخر',
  'نمی‌خواهید': 'لا تريدون', 'نه ممنون،': 'لا، شكرا،', 'خدا حافظ': 'مع السلامة'};
const BUILD = String.raw`
import json, os, shutil, sys
from pathlib import Path
REPO = Path(os.getcwd())
sys.path[:0] = ['youtube/lib', 'lib']
import annwrite, check_annotations as CA
tmp = Path(sys.argv[1])
ARABIC = json.loads(sys.argv[2])
root = tmp / 'root'
for d in (root / 'youtube' / 'videos', tmp / 'library', tmp / 'exercises', tmp / 'anki',
          tmp / 'tray', tmp / 'config', tmp / 'nodict', tmp / 'nocorpus', tmp / 'nomt'):
    d.mkdir(parents=True, exist_ok=True)
os.symlink(str(REPO / 'lib'), str(root / 'lib'))
os.symlink(str(REPO / 'youtube' / 'lib'), str(root / 'youtube' / 'lib'))
def copy(folder, vid):
    d = root / 'youtube' / 'videos' / folder / vid
    shutil.copytree(str(REPO / 'tests/fixtures/videos' / folder / vid), str(d))
    return d
out = {}
# JAPANESE as the fixture is: its one note is on a phrase that is not the last thing a chunk says
d = copy('japanese', 'aB3dE5fG7hI')
ann = annwrite.read(str(d))
at = next((i, j) for i, sg in enumerate(ann['segments']) for j, c in enumerate(sg.get('chunks') or []) if c.get('note'))
out['ja'] = {'id': 'aB3dE5fG7hI', 'dir': str(d), 'at': list(at), 'note': ann['segments'][at[0]]['chunks'][at[1]]['note'],
             'bare': [0, 0], 'plain': [0, 0], 'blank_at': [1, 0]}
# PERSIAN, glossed in Arabic, with the note an LLM leaves about a slip in what YouTube heard: it wrote
# سیر (garlic) in the transcript for سیب (apple); the gloss followed the speaker, and the note says so
d = copy('persian', 'fA6bK2mQ8sT')
meta = json.loads((d / 'video.json').read_text(encoding='utf-8'))
meta['gloss'] = 'ar'
(d / 'video.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
t = d / 'transcript.txt'
t.write_text(t.read_text(encoding='utf-8').replace('ببخشید سیب', 'ببخشید سیر'), encoding='utf-8')
ann = annwrite.read(str(d))
for sg in ann['segments']:
    for c in sg.get('chunks') or []:
        c['en'] = ARABIC[c['fa']]
sg = ann['segments'][1]
sg['text'] = 'سلام، ببخشید سیر چند است'
sg['chunks'][2]['fa'] = 'سیر چند است'
NOTE = 'سمع النص «سیر» (الثوم)، والمتحدث يقول «سیب» (التفاح)'
sg['chunks'][2]['note'] = NOTE
annwrite.write(str(d), ann)
errs, _w, _n = CA.check(str(d))
out['fa'] = {'id': 'fA6bK2mQ8sT', 'dir': str(d), 'at': [1, 2], 'note': NOTE, 'errors': errs, 'fixed': 'سیب چند است'}
# ITALIAN: three notes -- one on the chunk drawn bare (the English opening aside, marked plain), one on a
# phrase that wears the blue mark, one on 'signora' -- and a note of nothing but spaces, which is no note
d = copy('italian', 'kL9mN1oP3qR')
ann = annwrite.read(str(d))
S = ann['segments']
S[0]['chunks'][0]['note'] = 'an English aside, not glossed'
S[1]['chunks'][2]['note'] = 'pomodori: the plural of pomodoro'
S[1]['chunks'][2]['col'] = 'blue'
S[2]['chunks'][1]['note'] = '   '
S[3]['chunks'][2]['note'] = 'formal: said to a woman one does not know'
annwrite.write(str(d), ann)
errs, _w, _n = CA.check(str(d))
out['it'] = {'id': 'kL9mN1oP3qR', 'dir': str(d), 'errors': errs,
             'noted': [[0, 0], [1, 2], [3, 2]], 'blank': [2, 1], 'coloured': [1, 2], 'bare': [0, 0], 'free': [1, 0],
             'notes': {'0,0': 'an English aside, not glossed', '1,2': 'pomodori: the plural of pomodoro',
                       '3,2': 'formal: said to a woman one does not know'}}
print(json.dumps(out, ensure_ascii=False))
`;
// serve.main() over the temporary tree, every store in there (see tests/vocline_video.mjs, whose harness this is)
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
lookup.DICT_DIR = str(tmp / 'nodict')
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
for top in ('config', 'books', 'youtube/videos', 'tests/fixtures/videos'):
    for d, _, files in os.walk(top):
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
  this.getDuration = function () { return 40; };
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

const errors = [];
let hub = null, browser = null;
const log = [];
try {
  const B = JSON.parse((await py(BUILD, TMP, JSON.stringify(ARABIC))).trim().split('\n').pop());
  eq([B.fa.errors, B.it.errors], [[], []], 'the copies as set up are ones the checker has nothing against');
  const port = freePort();
  hub = new Deno.Command(PY, {args: ['-c', SERVE, TMP, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  drain(hub.stdout, log); drain(hub.stderr, log);
  const HOST = `http://127.0.0.1:${port}`;
  {
    const t = Date.now();
    for (;;) {
      try { const r = await fetch(HOST + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
      if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
      await sleep(250);
    }
  }
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const newContext = async (opts = {}, mode = '') => {
    const ctx = await browser.newContext(Object.assign({viewport: {width: 1280, height: 800}, serviceWorkers: 'block'}, opts));
    await ctx.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, route => {
      if (route.request().url() === 'https://www.youtube.com/iframe_api')
        return route.fulfill({contentType: 'text/javascript', body: FAKE_YT});
      return route.abort();
    });
    if (mode) await ctx.addCookies([{name: 'parseh_mode', value: mode, url: HOST}]);
    return ctx;
  };
  const context = await newContext();
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: HOST});

  /* ---------------- helpers over a page ---------------- */
  const optional = (status, method, path) => status === 404 && method === 'GET' &&
    (/^\/mt\/[^/]+\/meta\.json$/.test(path) || /^\/youtube\/videos\/[^/]+\/[^/]+\/waveform\.json$/.test(path) ||
     path === '/favicon.ico');
  const requests = [];                // every request the pages made to this hub: [method, path]
  async function player(id, name, ctx = context, theme = '') {
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(name + ' pageerror: ' + e.message));
    page.on('request', r => {
      const u = new URL(r.url());
      if (u.host === `127.0.0.1:${port}`) requests.push([r.method(), u.pathname]);
    });
    page.on('response', r => {
      const u = new URL(r.url());
      if (u.host !== `127.0.0.1:${port}` || r.status() < 400) return;
      if (!optional(r.status(), r.request().method(), u.pathname))
        errors.push(name + ' ' + r.status() + ' ' + r.request().method() + ' ' + u.pathname);
    });
    page.on('console', m => {
      if (m.type() !== 'error') return;
      const at = (m.location() || {}).url || '';
      if (/^Failed to load resource/.test(m.text()) && (at.startsWith(HOST) || !at.startsWith('http://127.0.0.1'))) return;
      errors.push(name + ' console: ' + m.text() + (at ? ' (' + at + ')' : ''));
    });
    page.on('requestfailed', r => {
      const u = new URL(r.url());
      if (u.host === `127.0.0.1:${port}`)
        errors.push(name + ' request failed: ' + r.method() + ' ' + u.pathname + ' (' + (r.failure() || {}).errorText + ')');
    });
    await page.goto(`${HOST}/youtube/v/${id}/`);
    await page.waitForSelector('#segs .seg .fa .w');
    await page.waitForFunction(() => window.__yt && document.querySelector('#novid').hidden);
    // the theme as a person sets it (the ◐ button's own call): it is a preference the toolbox keeps for the
    // person, so one written into storage before the page loads is overruled by what the hub was last told
    if (theme) {
      await page.evaluate(t => Parseh.theme.set(t), theme);
      await sleep(400);
      eq(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), theme, `${name}: the ${theme} theme`);
    }
    return page;
  }
  const text = (page, sel) => page.evaluate(sel => { const e = document.querySelector(sel); return e ? e.textContent : null; }, sel);
  const W = (i, j) => `#segs .seg[data-i="${i}"] .fa .w[data-j="${j}"]`;
  const away = async page => {
    await page.mouse.move(1, 1);
    await page.waitForFunction(() => document.querySelector('#cloud').hidden ||
                                     document.querySelector('#cloud').classList.contains('editing'));
  };
  // a point a hand can reach on a phrase: the element the browser finds there is asked, not assumed
  async function point(page, i, j) {
    await page.evaluate(i => {
      const seg = document.querySelector(`#segs .seg[data-i="${i}"]`), r = seg.getBoundingClientRect();
      const top = document.querySelector('#playerwrap').getBoundingClientRect().bottom;
      scrollBy({top: r.top + r.height / 2 - (top + innerHeight) / 2, behavior: 'instant'});
    }, i);
    await sleep(120);
    const p = await page.evaluate(([i, j]) => {
      const seg = document.querySelector(`#segs .seg[data-i="${i}"]`), el = seg.querySelector(`.fa .w[data-j="${j}"]`);
      for (const r of el.getClientRects()) {
        const xs = [];
        for (let d = 0; d < r.width / 2; d += 3) xs.push(r.left + r.width / 2 + d, r.left + r.width / 2 - d);
        for (const y of [r.top + r.height / 2, r.top + 4, r.bottom - 4]) for (const x of xs) {
          if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
          const hit = document.elementFromPoint(x, y);
          if (hit && hit.closest('.w') === el) return {x, y};
        }
      }
      return null;
    }, [i, j]);
    if (!p) throw Error(`FAIL: no reachable point on caption ${i} phrase ${j}`);
    return p;
  }
  async function hover(page, i, j) {
    for (let tries = 0; ; tries++) {
      await away(page);
      const p = await point(page, i, j);
      await page.mouse.move(p.x, p.y);
      try {
        await page.waitForFunction(sel => {
          const c = document.querySelector('#cloud'), w = document.querySelector(sel);
          return !c.hidden && w && w.classList.contains('hot');
        }, W(i, j), {timeout: 3000});
        return;
      } catch (e) { if (tries >= 2) throw e; }
    }
  }
  async function openEdit(page, i, j) {
    await hover(page, i, j);
    await page.click('#cloud .mkedit');
    await page.waitForFunction(w => {
      const c = document.querySelector('#cloud');
      return c.classList.contains('editing') && (c.querySelector('.ewhere') || {}).textContent === w;
    }, `segment ${i} chunk ${j}`);
  }
  async function closeEdit(page) {
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#cloud').classList.contains('editing'));
  }
  async function type(page, f, value) {
    await page.click(`#cloud .ef[data-f="${f}"]`);
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Delete');
    if (value) await page.keyboard.insertText(value);
  }
  const saved = page => page.waitForFunction(() => /^(saved|nothing changed)/.test((document.querySelector('#cloud .cstat') || {}).textContent || ''));
  const save = async page => {
    await page.evaluate(() => { document.querySelector('#cloud .cstat').textContent = ''; });
    await page.click('#cloud .esave');
    await saved(page);
    return text(page, '#cloud .cstat');
  };
  const annOf = async key => JSON.parse(await Deno.readTextFile(B[key].dir + '/annotations.json'));
  const bytesOf = key => Deno.readTextFile(B[key].dir + '/annotations.json');
  const chunkOf = async (key, [i, j]) => (await annOf(key)).segments[i].chunks[j];
  const shot = async (page, name, sel) => {
    if (!SHOTS) return;
    if (sel) await page.locator(sel).first().screenshot({path: `${SHOTS}/${name}.png`});
    else await page.screenshot({path: `${SHOTS}/${name}.png`});
  };
  const within = (box, w, h) => box && box.x >= -0.5 && box.y >= -0.5 && box.x + box.width <= w + 0.5 && box.y + box.height <= h + 0.5;
  // a line of the file's text each: what a diff is made of
  const linesOf = s => s.replace(/\n$/, '').split('\n');
  // what the transcript's lines say, as the page draws them (no generated content in it)
  const transcriptText = page => page.evaluate(() => document.querySelector('#segs').textContent);
  // a phrase, as the page numbers it: [caption, chunk]
  const cloudNote = page => page.evaluate(() => {
    const n = document.querySelector('#cloud .note');
    return n ? {text: n.textContent, lang: n.getAttribute('lang'), dir: n.getAttribute('dir')} : null;
  });
  const urls = () => requests.filter(([m, p]) => m !== 'GET' || /^\/youtube\/api\//.test(p));

  // ✱ notes' walk: the phrase last walked to, and whether the page has stopped moving (the scroll is smooth)
  const here = page => page.evaluate(() => {
    const e = document.querySelector('#segs .note-here');
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {at: [+e.closest('.seg').dataset.i, e.dataset.j !== undefined ? +e.dataset.j : [...e.parentNode.children].indexOf(e)],
            top: r.top, bottom: r.bottom, head: document.querySelector('header').getBoundingClientRect().bottom,
            video: document.querySelector('#playerwrap').getBoundingClientRect().bottom, vh: innerHeight,
            side: document.body.classList.contains('sbs'), many: document.querySelectorAll('#segs .note-here').length};
  });
  async function settle(page) {
    await sleep(80);
    let last = -1;
    for (let n = 0; n < 60; n++) { const y = await page.evaluate(() => scrollY); if (y === last) return; last = y; await sleep(120); }
  }
  const walk = async (page, dir) => { await page.click(dir > 0 ? '#notesnext' : '#notesprev'); await settle(page); return here(page); };
  // the phrase walked to is the one lit, below the bar -- and below the video where it is pinned over the text --
  // and inside the window
  const walks = async (page, what) => {
    const h = await here(page);
    const floor = h && (h.side ? h.head : Math.max(h.head, h.video));
    assert(h && h.many === 1 && h.top >= floor - 1 && h.bottom <= h.vh + 1,
           `${what}: ${JSON.stringify(h && h.at)} is the one phrase lit as walked to, below the ${h && h.side ? 'bar' : 'bar and the video'}, inside the window (${h && Math.round(h.top)}..${h && Math.round(h.bottom)} of ${h && h.vh}; below ${h && Math.round(floor)})`);
    return h.at;
  };

  /* ---------------- a) ---------------- */
  console.log('\na) the owner\'s case: a note about a slip in the transcript, the phrase mended, the note emptied');
  {
    const k = 'fa', at = B.fa.at;
    const page = await player(B.fa.id, k);
    eq(await page.evaluate(() => [window.YTFRANK.lang.dir, window.YTFRANK.gloss.code, window.YTFRANK.gloss.dir]),
       ['rtl', 'ar', 'rtl'], `${k}: a right-to-left line over a right-to-left gloss`);
    await hover(page, ...at);
    eq(await cloudNote(page), {text: B.fa.note, lang: 'ar', dir: 'rtl'}, `${k}: hovering the phrase shows the note under the meaning, in the gloss language and its direction`);
    await openEdit(page, ...at);
    eq(await page.locator('#cloud .ef[data-f="note"]').count(), 1, `${k}: the ✎ form has a box for the note`);
    const box = await page.evaluate(() => {
      const f = n => document.querySelector(`#cloud .ef[data-f="${n}"]`);
      const b = f('note'), e = f('en'), r = b.getBoundingClientRect(), er = e.getBoundingClientRect();
      const lab = b.closest('.erow').querySelector('.elab'), hint = b.closest('.erow').querySelector('.efnote');
      return {value: b.value, lang: b.getAttribute('lang'), dir: b.getAttribute('dir'), cls: b.className, rows: b.rows,
              underMeaning: r.top >= er.bottom - 1, tag: b.tagName, label: lab.textContent, labelFor: lab.getAttribute('for') === b.id,
              hint: hint && hint.textContent, align: getComputedStyle(b).textAlign,
              order: [...document.querySelectorAll('#cloud .ef')].map(x => x.dataset.f)};
    });
    eq([box.value, box.lang, box.dir, box.tag], [B.fa.note, 'ar', 'rtl', 'TEXTAREA'], `${k}: the ✎ form's note box holds the note, in the gloss language's face and direction`);
    assert(/\bgl\b/.test(box.cls) && box.rows === 1, `${k}: it is a gloss box of one row (${box.cls}, rows ${box.rows})`);
    assert(box.underMeaning, `${k}: under the meaning`);
    eq(box.order, ['fa', 'tr', 'voc', 'en', 'note'], `${k}: the form's boxes, the note the last`);
    eq([box.label, box.labelFor], ['note', true], `${k}: called what it is, and the label is the box's own`);
    assert(/Empty it to take the note off/.test(box.hint), `${k}: and a line under it says how a note is taken off: ${box.hint}`);
    await shot(page, 'form-fa-ar-note-1280', '#cloud');
    // the transcript is mended through the `free` tick; the note is stale and still there
    const fileBefore = await bytesOf(k);
    await type(page, 'fa', B.fa.fixed);
    await page.check('#cloud .efree');
    eq(await save(page), 'saved ✓', `${k}: the mended phrase, saved with the transcript tick`);
    const mended = await chunkOf(k, at);
    eq([mended.fa, mended.free, mended.note], [B.fa.fixed, true, B.fa.note], `${k}: the file has the mended text, the mark, and the note still`);
    eq(await page.inputValue('#cloud .ef[data-f="note"]'), B.fa.note, `${k}: the form still holds the stale note`);
    // ...and the note emptied in the same form
    const before = await bytesOf(k);
    await type(page, 'note', '');
    eq(await save(page), 'saved ✓', `${k}: the note emptied and saved`);
    const after = await bytesOf(k);
    const a = linesOf(before), b = linesOf(after);
    const i = a.findIndex((l, n) => l !== b[n]);
    assert(a.length - b.length === 1 && a[i].includes('"note"') && same(a.slice(0, i).concat(a.slice(i + 1)), b),
           `${k}: the file's diff is ONE line, the one the note was on: ${a[i]}`);
    eq((await chunkOf(k, at)).note, undefined, `${k}: no note key left on the phrase`);
    const t = await Deno.readTextFile(B.fa.dir + '/transcript.txt');
    assert(t.includes('ببخشید سیر چند است') && !t.includes('سیب چند'), `${k}: the transcript, what YouTube heard, is exactly as it was`);
    eq(await page.inputValue('#cloud .ef[data-f="note"]'), '', `${k}: the form shows what is now on disk: an empty box`);
    await closeEdit(page);
    await hover(page, ...at);
    eq(await cloudNote(page), null, `${k}: the cloud has no note line any more`);
    await away(page);
    assert(a.length > 1 && fileBefore !== before, `${k}: (the file did change on the way: the mend)`);
    await page.reload();
    await page.waitForSelector('#segs .seg .fa .w');
    await hover(page, ...at);
    eq(await cloudNote(page), null, `${k}: and a reload agrees`);
    await page.close();
  }

  /* ---------------- b) ---------------- */
  console.log('\nb) the form: a note changed, a note written, a card, nothing changed');
  {
    const k = 'ja', at = B.ja.at, blank = B.ja.blank_at;
    const page = await player(B.ja.id, k);
    await hover(page, ...at);
    eq((await cloudNote(page)).text, B.ja.note, `${k}: hovering shows the file's note`);
    await openEdit(page, ...at);
    eq(await page.inputValue('#cloud .ef[data-f="note"]'), B.ja.note, `${k}: the box holds it`);
    eq(await page.evaluate(() => { const b = document.querySelector('#cloud .ef[data-f="note"]'); return [b.getAttribute('lang'), b.getAttribute('dir')]; }),
       ['en', null], `${k}: in a left-to-right gloss, with no direction of its own to say`);
    // nothing changed is said so, and the server is not asked
    const posts = urls().length;
    eq(await save(page), 'nothing changed', `${k}: a save of what was there says nothing changed`);
    eq(urls().length, posts, `${k}: and asks the server nothing`);
    // a longer note: the box grows as it is typed into, and what is typed is what is saved, trimmed
    const longer = '十分 is read じゅっぷん juppun when it means ten minutes — and じゅうぶん jūbun, enough, when it does not; here it is the time, so the first. ';
    const h0 = await page.evaluate(() => document.querySelector('#cloud .ef[data-f="note"]').getBoundingClientRect().height);
    await type(page, 'note', longer);
    const h1 = await page.evaluate(() => document.querySelector('#cloud .ef[data-f="note"]').getBoundingClientRect().height);
    assert(h1 > h0, `${k}: the note's row grows with what is typed into it (${h0} -> ${h1}px)`);
    eq(await save(page), 'saved ✓', `${k}: a changed note is saved`);
    eq((await chunkOf(k, at)).note, longer.trim(), `${k}: trimmed, in the file`);
    eq(await page.inputValue('#cloud .ef[data-f="note"]'), longer.trim(), `${k}: and the box shows what is on disk`);
    await closeEdit(page);
    await hover(page, ...at);
    eq((await cloudNote(page)).text, longer.trim(), `${k}: the cloud shows the new note at once`);
    await away(page);
    await page.reload();
    await page.waitForSelector('#segs .seg .fa .w');
    await hover(page, ...at);
    eq((await cloudNote(page)).text, longer.trim(), `${k}: and after a reload`);
    // a card made of the phrase carries the note it has now
    await page.click('#cloud .mkcard');
    await page.waitForFunction(() => !document.querySelector('#anki').hidden);
    assert((await page.inputValue('#anotes')).includes(longer.trim()), `${k}: a card made of the phrase carries the new note in its notes`);
    await page.click('#acancel');
    await away(page);
    // a phrase with no note takes one
    eq((await chunkOf(k, blank)).note, undefined, `${k}: the phrase beside has no note`);
    await openEdit(page, ...blank);
    eq(await page.inputValue('#cloud .ef[data-f="note"]'), '', `${k}: its note box is there, and empty`);
    await type(page, 'note', '  heard as a greeting, not a farewell  ');
    eq(await save(page), 'saved ✓', `${k}: a note written on a phrase that had none`);
    eq((await chunkOf(k, blank)).note, 'heard as a greeting, not a farewell', `${k}: is in the file, trimmed`);
    eq(Object.keys(await chunkOf(k, blank)).filter(x => ['en', 'note'].includes(x)), ['en', 'note'], `${k}: after the meaning, where the field order puts it`);
    // nothing but spaces over a note takes it off (it is blank once trimmed); over an empty box, nothing changed
    await type(page, 'note', '   ');
    eq(await save(page), 'saved ✓', `${k}: nothing but spaces over a note takes it off`);
    eq((await chunkOf(k, blank)).note, undefined, `${k}: the key is gone from the file`);
    await type(page, 'note', '   ');
    eq(await save(page), 'nothing changed', `${k}: and spaces over an empty box are nothing changed`);
    await closeEdit(page);
    // the note is no gloss: a phrase whose gloss is deleted keeps its note, and its cloud says nothing is glossed
    const only = [3, 0];
    await openEdit(page, ...only);
    await page.click('#cloud .edel');
    await page.waitForFunction(() => /gloss deleted/.test(document.querySelector('#cloud .cstat').textContent));
    await type(page, 'note', 'the topic marker, said softly');
    eq(await save(page), 'saved ✓', `${k}: a note written on a phrase whose gloss has been deleted`);
    eq(await page.evaluate(() => document.querySelector('#cloud .edel').disabled), true, `${k}: delete gloss is greyed: a note is no gloss to delete`);
    await closeEdit(page);
    await hover(page, ...only);
    eq(await page.evaluate(() => [!!document.querySelector('#cloud .unwritten'), (document.querySelector('#cloud .note') || {}).textContent]),
       [true, 'the topic marker, said softly'], `${k}: its cloud still says nothing is glossed yet, and shows the note under it`);
    await away(page);
    // A CUT AND A JOIN, from the page: the sheet draws no box for the note and posts none, and the note comes through
    // all the same -- on the first half of a cut, whole through a join -- with ✱ notes counting the page as it is redrawn
    await page.click('#notesbtn');
    const count = () => page.evaluate(() => document.querySelector('#notesbtn').textContent.trim());
    eq(await count(), '✱ notes 2', `${k}: two phrases carry a note`);
    await openEdit(page, ...at);
    await page.click('#cloud .edv[data-dv="split"]');
    await page.waitForFunction(() => !document.querySelector('#dvbox').hidden && document.querySelectorAll('#dvpair .dvcol').length === 2);
    eq(await page.evaluate(() => document.querySelectorAll('#dvbox [data-k="note"]').length), 0, `${k}: the sheet that cuts has no note box`);
    await page.click('#dvdo');
    await page.waitForFunction(() => /done/.test(document.querySelector('#dvstat').textContent));
    let cs = (await annOf(k)).segments[at[0]].chunks;
    eq([cs[at[1]].fa, cs[at[1]].note, cs[at[1] + 1].fa, cs[at[1] + 1].note], ['十', longer.trim(), '分', undefined],
       `${k}: cut in two, the note stays on the first half, which the sheet never named`);
    await page.click('#dvdo');                  // the sheet's close
    await page.waitForFunction(() => document.querySelector('#dvbox').hidden);
    eq(await count(), '✱ notes 2', `${k}: the page was drawn again from the file, and the count is as it was`);
    eq(await page.evaluate(() => [...document.querySelectorAll('#segs .has-note')].map(e => [+e.closest('.seg').dataset.i, +e.dataset.j])), [[3, 0], [4, 2]],
       `${k}: with the first half lit and the second not`);
    await openEdit(page, at[0], at[1]);
    await page.click('#cloud .edv[data-dv="next"]');
    await page.waitForFunction(() => !document.querySelector('#dvbox').hidden && document.querySelectorAll('#dvpair .dvcol').length === 1);
    await page.click('#dvdo');
    await page.waitForFunction(() => /done/.test(document.querySelector('#dvstat').textContent));
    cs = (await annOf(k)).segments[at[0]].chunks;
    eq([cs[at[1]].fa, cs[at[1]].note], ['十分', longer.trim()], `${k}: joined again, the one phrase has its note`);
    await page.click('#dvdo');
    await page.waitForFunction(() => document.querySelector('#dvbox').hidden);
    eq(await count(), '✱ notes 2', `${k}: and the count is still 2`);
    await page.click('#notesbtn');
    await away(page);
    await page.close();
  }
  console.log(`\nplayer_note: ${passed} checks passed (so far)`);

  /* ---------------- c) ---------------- */
  console.log('\nc) the ✱ notes button: lights, counts and walks, and writes nothing');
  {
    const k = 'it', I = B.it;
    const page = await player(I.id, k);
    const probe = (page, prop) => page.evaluate(prop => {
      const p = document.createElement('i'); p.style.color = `var(${prop})`; document.body.appendChild(p);
      const c = getComputedStyle(p).color; p.remove(); return c;
    }, prop);
    const state = () => page.evaluate(() => {
      const b = document.querySelector('#notesbtn'), p = document.querySelector('#notesprev'), n = document.querySelector('#notesnext');
      const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility === 'visible' && s.display !== 'none' && !e.hidden; };
      return {text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed'), on: b.classList.contains('on'),
              btn: vis(b), prev: vis(p), next: vis(n), disabled: [p.disabled, n.disabled],
              lit: document.querySelectorAll('#segs .has-note').length};
    });
    // every phrase that wears the class, as [caption, chunk]: a .w knows its number, a bare run is the n-th element of its line
    const lit = () => page.evaluate(() => [...document.querySelectorAll('#segs .has-note')].map(e => [
      +e.closest('.seg').dataset.i, e.dataset.j !== undefined ? +e.dataset.j : [...e.parentNode.children].indexOf(e)]));
    const styleOf = (page, sel) => page.evaluate(sel => {
      const e = document.querySelector(sel), s = getComputedStyle(e), a = getComputedStyle(e, '::after');
      return {line: s.textDecorationLine, style: s.textDecorationStyle, color: s.textDecorationColor, ink: s.color,
              after: a.content, afterColor: a.color, classes: e.className};
    }, sel);
    const spanOf = ([i, j]) => `#segs .seg[data-i="${i}"] .fa > :nth-child(${j + 1})`;

    // OFF on a visit: the switch is there, its arrows are not, nothing is lit
    eq(await state(), {text: '✱ notes', pressed: 'false', on: false, btn: true, prev: false, next: false,
                       disabled: [true, true], lit: 0}, `${k}: the button is in the bar, off, with no count and no arrows`);
    eq(await lit(), [], `${k}: with it off not one phrase wears a class of it`);
    // on and off again, the transcript is byte for byte what it was: not a class, not an attribute is left behind.
    // THE PLAYER'S OWN HIGHLIGHT IS NOT THE BUTTON'S: the first tick after the video is ready (every 250 ms, once its metadata is
    // in) puts `on-air` on the segment being played and `near` on its neighbours, and the page is called synced.  Taken before that
    // the picture of the transcript had neither, and taken after the toggle it had both -- a difference the button never made; so
    // the picture is taken once the player has synced (the body says so), and the comparison stays byte for byte
    await page.waitForFunction(() => document.body.classList.contains('synced'), null, {timeout: 20000})
      .catch(() => { throw Error(`FAIL: ${k}: the player never synced with the video, so the transcript has no settled state to compare`); });
    const htmlOff = await page.evaluate(() => document.querySelector('#segs').innerHTML);
    await page.click('#notesbtn');
    eq(await lit(), I.noted, `${k}: on, the phrases that carry a note wear the class, and the blank note is none (${JSON.stringify(I.blank)} is not among them)`);
    await page.click('#notesbtn');
    eq(await page.evaluate(() => document.querySelector('#segs').innerHTML), htmlOff, `${k}: and off again the transcript is exactly what it was before the button was touched`);
    const dotted = await styleOf(page, spanOf(I.noted[1]));
    eq([dotted.style, dotted.after], ['dotted', 'none'], `${k}: while it is off a noted phrase looks as every phrase does (dotted, nothing after it)`);
    eq(await page.evaluate(() => Object.keys(localStorage).filter(x => /note/i.test(x))), [], `${k}: and nothing about it is remembered`);
    // the control costs the bar no row at a desktop's width: every line of the transcript pays for a row
    const bar = await page.evaluate(() => {
      const h = document.querySelector('header'), g = document.querySelector('#notesgrp'), was = h.offsetHeight;
      g.style.display = 'none'; const without = h.offsetHeight; g.style.display = '';
      return [was, without];
    });
    eq(bar[0], bar[1], `${k}: at 1280 px the bar is as tall with the control as without it (${bar[0]}px)`);

    // ON
    const textOff = await transcriptText(page), fileOff = await bytesOf(k), seen = requests.length;
    await page.evaluate(() => scrollTo(0, 0));
    await page.click('#notesbtn');
    eq(await state(), {text: '✱ notes 3', pressed: 'true', on: true, btn: true, prev: true, next: true,
                       disabled: [false, false], lit: 3}, `${k}: on, it says 3 -- the file's count -- with its arrows`);
    const accent = await probe(page, '--accent'), blue = await probe(page, '--hl-blue');
    for (const at of I.noted) {
      const s = await styleOf(page, spanOf(at));
      eq([s.line.includes('underline'), s.style, s.color, s.after, s.afterColor], [true, 'dashed', accent, '"✱"', accent],
         `${k}: ${JSON.stringify(at)} is underlined with a dashed line in the accent, and a ✱ follows it`);
    }
    const plainOne = await styleOf(page, spanOf(I.free));
    eq([plainOne.style, plainOne.after], ['dotted', 'none'], `${k}: a phrase with no note is as it was`);
    const blankOne = await styleOf(page, spanOf(I.blank));
    eq([blankOne.style, blankOne.after], ['dotted', 'none'], `${k}: and one whose note is nothing but spaces too`);
    assert(/\bbare\b/.test((await styleOf(page, spanOf(I.bare))).classes), `${k}: the chunk drawn bare (a plain aside) is one of the three, and is lit as the others are`);
    const col = await styleOf(page, spanOf(I.coloured));
    assert(/\bhl-blue\b/.test(col.classes) && /\bhas-note\b/.test(col.classes), `${k}: the phrase with a colour mark and a note wears both classes`);
    eq([col.ink, col.color], [blue, accent], `${k}: its text keeps the person's blue and the note's line is the accent: the two show together`);
    eq(await transcriptText(page), textOff, `${k}: not a character was added to the transcript: selecting and copying read what they always read`);

    // WALKING: ‹ › visit them in document order, and wrap; the first press goes to the first one below the bar and the video
    const first = await page.evaluate(([noted]) => {
      const edge = document.querySelector('header').offsetHeight + document.querySelector('#playerwrap').offsetHeight;
      const tops = noted.map(([i, j]) => document.querySelector(`#segs .seg[data-i="${i}"] .fa > :nth-child(${j + 1})`).getBoundingClientRect().top);
      const n = tops.findIndex(t => t > edge);
      return n < 0 ? 0 : n;
    }, [I.noted]);
    const order = I.noted.concat(I.noted).slice(first, first + 4);
    const got = [];
    for (let n = 0; n < 4; n++) { await walk(page, 1); got.push(await walks(page, `${k}: › ${n + 1}`)); }
    eq(got, order, `${k}: › four times visits the phrases in order and wraps to the first again`);
    const back = [];
    for (let n = 0; n < 3; n++) { await walk(page, -1); back.push(await walks(page, `${k}: ‹ ${n + 1}`)); }
    eq(back, [got[2], got[1], got[0]], `${k}: ‹ walks back along the same way, and wraps from the first to the last`);
    // it asked the server nothing and wrote nothing
    eq(requests.slice(seen), [], `${k}: toggling and walking made not one request`);
    eq(await bytesOf(k), fileOff, `${k}: the file is exactly as it was`);
    await shot(page, 'notes-it-walk-1280');
    // hovering still opens the cloud, and a click on the line still replays it: nothing means something else
    await hover(page, 3, 2);
    eq((await cloudNote(page)).text, I.notes['3,2'], `${k}: with it on, hovering a noted phrase opens its cloud, note and all`);
    const seeks = await page.evaluate(() => window.__yt.seeks.length);
    const p = await point(page, 3, 2);
    await page.mouse.click(p.x, p.y);
    await page.waitForFunction(n => window.__yt.seeks.length > n, seeks);
    eq(await page.evaluate(() => window.__yt.seeks.slice(-1)[0]), 15, `${k}: and a click on it plays the caption from its beginning`);
    await away(page);

    // LIVE: a note written, changed or taken off in the form updates it at once
    await openEdit(page, ...I.free);
    await type(page, 'note', 'to check: is this the right plural?');
    eq(await save(page), 'saved ✓', `${k}: a note written on ${JSON.stringify(I.free)}`);
    eq(await state().then(s => s.text), '✱ notes 4', `${k}: the count says 4 at once, with no reload`);
    eq(await lit(), [[0, 0], [1, 0], [1, 2], [3, 2]], `${k}: and the phrase is lit`);
    await type(page, 'note', '');
    eq(await save(page), 'saved ✓', `${k}: taken off again`);
    eq([(await state()).text, await lit()], ['✱ notes 3', I.noted], `${k}: the count says 3 again and the phrase is dim`);
    await type(page, 'note', '   ');
    eq(await save(page), 'nothing changed', `${k}: spaces are no note`);
    eq((await state()).text, '✱ notes 3', `${k}: and are not counted`);
    await closeEdit(page);
    // ...on the phrase that wears a colour: the note comes off, the colour stays, the count follows
    await openEdit(page, ...I.coloured);
    await type(page, 'note', '');
    await save(page);
    const dim = await styleOf(page, spanOf(I.coloured));
    eq([(await state()).text, /\bhl-blue\b/.test(dim.classes), /\bhas-note\b/.test(dim.classes), dim.style], ['✱ notes 2', true, false, 'dotted'],
       `${k}: a note taken off the blue phrase: 2, still blue, no longer lit`);
    eq((await chunkOf(k, I.coloured)).col, 'blue', `${k}: and the file still has its colour`);
    await type(page, 'note', I.notes['1,2']);
    await save(page);
    eq((await state()).text, '✱ notes 3', `${k}: written back, 3`);
    await closeEdit(page);
    await away(page);

    // off again, and OFF on every visit
    await page.click('#notesbtn');
    eq(await state(), {text: '✱ notes', pressed: 'false', on: false, btn: true, prev: false, next: false,
                       disabled: [true, true], lit: 0}, `${k}: the button turns it off, and takes its count and arrows with it`);
    eq((await styleOf(page, spanOf(I.noted[2]))).after, 'none', `${k}: and the ✱ is gone from the page`);
    eq(await page.evaluate(() => document.querySelectorAll('#segs .note-here').length), 0, `${k}: with the walk's mark`);
    await page.click('#notesbtn');
    await page.reload();
    await page.waitForSelector('#segs .seg .fa .w');
    eq((await state()).pressed, 'false', `${k}: left on, a reload finds it off`);
    await page.close();

    // the mode switched under a page that has it on takes the highlight away, and it stays off
    const m = await player(I.id, k + ' (the mode switched)');
    await m.click('#notesbtn');
    eq(await m.evaluate(() => document.querySelectorAll('#segs .has-note').length), 3, `${k}: on`);
    await m.evaluate(() => Parseh.mode.set('mobile'));
    await m.waitForFunction(() => document.querySelectorAll('#segs .has-note').length === 0);
    eq(await m.evaluate(() => document.querySelector('#notesbtn').textContent.trim()), '✱ notes', `${k}: switched to the mobile mode, the highlight is gone, and the count with it`);
    await m.evaluate(() => Parseh.mode.set('browser'));
    await sleep(150);
    eq(await m.evaluate(() => [document.querySelectorAll('#segs .has-note').length, document.querySelector('#notesbtn').getAttribute('aria-pressed')]), [0, 'false'],
       `${k}: and switched back it is off, as a visit starts`);
    await m.close();
  }
  // the MOBILE MODE has no such button: the span is gone from the bar, and nothing turns the highlight on
  {
    const k = 'it';
    const ctx = await newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}, 'mobile');
    const page = await player(B.it.id, k + ' (mobile)', ctx);
    await page.waitForFunction(() => document.documentElement.classList.contains('m-player'));
    eq(await page.evaluate(() => document.documentElement.getAttribute('data-mode')), 'mobile', `${k}: the mobile mode`);
    const gone = await page.evaluate(() => {
      const g = document.querySelector('#notesgrp'), r = g.getBoundingClientRect();
      return {display: getComputedStyle(g).display, w: r.width, h: r.height,
              inBar: [...document.querySelectorAll('header button')].filter(b => b.getBoundingClientRect().width > 0 && /notes|‹|›/.test(b.textContent)).length};
    });
    eq(gone, {display: 'none', w: 0, h: 0, inBar: 0}, `${k}: the ✱ notes control is not in the bar: display none, no box, no button of it drawn`);
    await page.evaluate(() => { document.querySelector('#notesbtn').click(); });
    eq(await page.evaluate(() => [document.querySelectorAll('#segs .has-note').length, document.querySelector('#notesbtn').getAttribute('aria-pressed')]),
       [0, 'false'], `${k}: pressed by a script, nothing lights: the highlight is the browser mode's alone`);
    // the mobile mode edits nothing and goes on drawing the note: a tap on a phrase opens its cloud, note and all
    await page.tap(W(3, 2));
    await page.waitForFunction(() => !document.querySelector('#cloud').hidden);
    eq((await cloudNote(page)).text, B.it.notes['3,2'], `${k}: a tap on a phrase of the mobile mode shows its note in the cloud`);
    eq(await page.evaluate(() => !!document.querySelector('#cloud .mkedit') && getComputedStyle(document.querySelector('#cloud .mkedit')).display !== 'none'
                                 && document.querySelector('#cloud .mkedit').getBoundingClientRect().width > 0), false, `${k}: and the cloud has no ✎ there`);
    await page.close();
    await ctx.close();
  }
  // the walk lands where it can be read in the other layouts too: a window as narrow as a phone's (the bar wraps
  // to rows and the video is pinned under it), and the video beside the transcript (a column of its own)
  for (const [label, win, before] of [['a 390 px window', {width: 390, height: 844}, null],
                                      ['the video beside the transcript', {width: 1280, height: 800}, () => localStorage.setItem('yt_sbs', '1')]]) {
    const k = 'it';
    const ctx = await newContext({viewport: win});
    if (before) await ctx.addInitScript(before);
    const page = await player(B.it.id, k + ' (' + label + ')', ctx);
    if (before) eq(await page.evaluate(() => document.body.classList.contains('sbs')), true, `${k}: ${label}`);
    await page.click('#notesbtn');
    const seen = [];
    for (let n = 0; n < 4; n++) { await walk(page, 1); seen.push(await walks(page, `${k}, ${label}: › ${n + 1}`)); }
    eq(seen.slice(0, 3).map(String).sort(), B.it.noted.map(String).sort(), `${k}, ${label}: the three phrases with a note, each walked to`);
    eq(seen[3], seen[0], `${k}, ${label}: and round to the first again`);
    // a narrow screen puts the bar away as the page moves down, and the arrows are in it: while the walk is on it stays
    eq(await page.evaluate(() => [document.body.classList.contains('barhidden'), document.body.hasAttribute('data-bars-held')]), [false, true],
       `${k}, ${label}: the bar was never put away while walking, so every press found its arrow`);
    await page.click('#notesbtn');
    eq(await page.evaluate(() => document.body.hasAttribute('data-bars-held')), false, `${k}, ${label}: and let go of when the walk is off`);
    await page.close();
    await ctx.close();
  }
  console.log(`\nplayer_note: ${passed} checks passed (so far)`);

  /* ---------------- d) ---------------- */
  console.log('\nd) the screenshots');
  if (!SHOTS) console.log('  (NOTE_SHOTS is not set: none taken)');
  else {
    // the Persian video's note was emptied in a): put it back, as an LLM leaves it, for the eye
    await py(`import sys; sys.path[:0] = ['youtube/lib', 'lib']; import annwrite
annwrite.edit_chunk(sys.argv[1], 1, 2, {'note': sys.argv[2]})`, B.fa.dir, B.fa.note);
    const marks = await (async () => {
      const out = [];
      for (const theme of ['light', 'dark', 'sepia']) for (const [w, h] of [[1280, 800], [390, 844]]) {
        const ctx = await newContext({viewport: {width: w, height: h}});
        const tag = `${theme}-${w}`;
        {   // Persian, glossed in Arabic: right to left over right to left
          const page = await player(B.fa.id, 'fa ' + tag, ctx, theme);
          await page.click('#notesbtn');
          await shot(page, `bar-fa-ar-${tag}`);
          await page.click('#notesnext');
          await sleep(900);
          await shot(page, `notes-fa-ar-${tag}`);
          await hover(page, ...B.fa.at);
          await sleep(200);
          await shot(page, `cloud-fa-ar-${tag}`);
          await page.click('#cloud .mkedit');
          await page.waitForFunction(() => document.querySelector('#cloud').classList.contains('editing'));
          await sleep(300);
          await shot(page, `form-fa-ar-${tag}`);
          // the form's column scrolls on a short window: the same form, at its foot
          await page.evaluate(() => { const m = document.querySelector('#cloud .emain'); m.scrollTop = m.scrollHeight; });
          await sleep(200);
          await shot(page, `form-fa-ar-${tag}-foot`);
          out.push(tag);
          await page.close();
        }
        {   // Japanese: the kana drawn over the kanji (ruby) under the ✱ and the line
          const page = await player(B.ja.id, 'ja ' + tag, ctx, theme);
          await page.click('#notesbtn');
          await page.click('#notesnext');
          await sleep(900);
          await shot(page, `notes-ja-${tag}`);
          await page.close();
        }
        {   // Italian, glossed in English: left to right, with a colour mark and a bare run beside the notes
          const page = await player(B.it.id, 'it ' + tag, ctx, theme);
          await page.click('#notesbtn');
          await page.click('#notesnext');
          await sleep(900);
          await shot(page, `notes-it-${tag}`);
          await page.close();
        }
        await ctx.close();
      }
      return out;
    })();
    console.log('  ok screenshots:', marks.join(', '));
  }

  /* ---------------- e) ---------------- */
  console.log('\ne) last: nothing broke, and nothing of the owner\'s was touched');
  eq([...errors], [], 'no page threw, logged an error or had a request refused');
  assert(!/Traceback/.test(log.join('')), 'the hub printed no traceback');
  const ownAfter = JSON.parse(await py(OWN, TMP));
  eq([ownAfter.digests, ownAfter.leaks], [ownBefore.digests, []], 'the owner\'s config/, books/, youtube/videos/ and the fixtures are as they were');
  console.log(`\nplayer_note: ${passed} checks passed`);
} finally {
  if (browser) await browser.close();
  if (hub) { try { hub.kill('SIGTERM'); } catch (_) {} await hub.status; }
  if (!Deno.env.get('PARSEH_KEEP')) await Deno.remove(TMP, {recursive: true});
}
