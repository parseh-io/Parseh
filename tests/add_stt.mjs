// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/add_stt.mjs
//      ADD_STT_ONLY=a,c   runs only those sections
//      ADD_STT_SHOTS=<dir>  keeps a screenshot of the block in every state, language,
//                           width and theme it is drawn in
//
// THE ADD PAGE'S SPEECH TO TEXT, in real Chrome, against the REAL hub
// (serve.main() over a temporary tree) and the REAL transcription job -- its
// routes, its state machine, its worker CHILD -- with nothing stood in but what
// this machine may not have: lib/getstt.py is tests/addstt_fakes.py (the state
// of the computer is a file the suite edits, so an install "in another tab" is
// one write) and the worker's faster-whisper is tests/fixtures/stt_runtime.
// No model, no runtime, no CUDA, and nothing fetched: this is what normal CI
// runs.  The YouTube half needs a tab that can be recorded and the fake YouTube
// the capture suite has: tests/youtube_capture.mjs, section n.
//
//  a) speech to text NOT installed: the block is a sentence and a link to where
//     it is set up (in a tab of its own), no button and no picker; the page
//     asked the computer one thing and fetched nothing; the manual way -- a
//     pasted transcript, "Start it empty" -- works and lands in a player that
//     has no trace of speech to text
//  b) installed: the two models offered only where installed, the turbo one
//     first; Automatic and CPU, and the NVIDIA GPU only when the computer says
//     the card is ready (and a card that is there but not ready says why); no
//     CTranslate2 word anywhere in the form; what is chosen is remembered in
//     this browser; an install made in another tab appears on the next look at
//     the page, with no reload; a language Whisper does not know offers nothing
//  c) a film on this computer: Transcribe, the computer's own words as it goes,
//     the text in the transcript box and the video NOT added; the video, the
//     language and the model locked while it runs (and said so), Cancel; the
//     box is never overwritten unasked (before, and again when the text
//     arrives); what was prepared for an LLM is out of date; "Edit the
//     transcript…" takes the result; the tie of the box to its video, language
//     and model, and what breaks it (and what does not: the processor)
//  d) the words of a failure: another job running, the card that would not
//     start (explicit and Automatic), a computer that answers nothing; a
//     reload finds a running job again, and nothing is left stuck
//  e) a browser that cannot record a tab (Firefox, Safari, a page that is not
//     https, a phone): the YouTube way says so, in the module's own words, and
//     the rest -- the manual paste, and a film -- works as ever
//  f) every language of the selector, at 1280 and 390 wide, in the three
//     themes, on a page turned right to left: the block fits, its words are
//     readable, and it is never wider than the page
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('ADD_STT_SHOTS') || '';
const ONLY = (Deno.env.get('ADD_STT_ONLY') || '').split(',').filter(Boolean);
const TMP = await Deno.makeTempDir({prefix: 'parseh-add-stt-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want), m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
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
async function exists(p) { try { await Deno.stat(p); return true; } catch (_) { return false; } }
async function names(dir, re = /./) {
  const out = [];
  try { for await (const e of Deno.readDir(dir)) if (re.test(e.name)) out.push(e.name); } catch (_) {}
  return out.sort();
}
const readJson = async p => JSON.parse(await Deno.readTextFile(p));
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}

/* ---------------------------------------------------------------- the tree and the hub */
const TREE = TMP + '/tree', FAKE = TMP + '/fake', ROOT = TREE + '/root', VIDEOS = ROOT + '/youtube/videos';
const STT_TMP = FAKE + '/stt/tmp';
for (const d of [VIDEOS, TREE + '/config', TREE + '/library', TREE + '/tray', TREE + '/exercises', TREE + '/anki',
                 TREE + '/nodict', TREE + '/nocorpus', TREE + '/nomt', FAKE]) await Deno.mkdir(d, {recursive: true});
await Deno.symlink(root + '/lib', ROOT + '/lib');
await Deno.symlink(root + '/youtube/lib', ROOT + '/youtube/lib');

// The computer, as a file.  Every suite writes it BEFORE it opens a page, and
// the page reads it through POST /lookup/api/speech.
const BOTH = ['large-v3-turbo', 'large-v3'];
const NO_CARD = {ready: false, name: '', why: ''};
const state0 = {runtime: true, models: BOTH, cuda: NO_CARD, no_lang: [], busy: false};
async function setState(patch = {}) {
  await Deno.writeTextFile(FAKE + '/state.json', JSON.stringify(Object.assign({}, state0, patch)));
}
// how the worker's faster-whisper behaves (tests/fixtures/stt_runtime)
const PERSIAN = [[0.0, 2.0, ' سلام دنیا'], [2.5, 4.0, ' خداحافظ']];
async function setFake(cfg = {}) {
  await Deno.writeTextFile(FAKE + '/fake.json', JSON.stringify(Object.assign({segments: PERSIAN}, cfg)));
}
await setState();
await setFake();

const BOOT = String.raw`
import os, sys
from pathlib import Path
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'youtube/lib', 'lib', 'tests', '.']
tmp, port = Path(sys.argv[1]), sys.argv[2]
# the computer's speech to text is a file (tests/addstt_fakes.py), not this machine's
import addstt_fakes
sys.modules['getstt'] = addstt_fakes.make(str(tmp.parent / 'fake'))
import prefs, network, offline, llmconfig
import speechconfig
speechconfig.CONFIG = tmp / 'config/speech.json'
sys.modules['getstt'].preferences_file = speechconfig.CONFIG
llmconfig.ROOT = str(tmp)
prefs.STORE = str(tmp / 'config' / 'prefs.json')
network.STORE = str(tmp / 'config' / 'network.json')
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
const port = freePort(), log = [];
const hub = new Deno.Command(PY, {args: ['-c', BOOT, TREE, String(port)], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
for (const s of [hub.stdout, hub.stderr])
  (async () => { for await (const chunk of s.pipeThrough(new TextDecoderStream())) log.push(chunk); })();
const BASE = `http://127.0.0.1:${port}`;
{
  const t = Date.now();
  for (;;) {
    try { const r = await fetch(BASE + '/lookup/api/speech', {method: 'POST', body: '{}'}); if (r.ok) break; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
}
const api = async (path, body) => {
  const r = await fetch(BASE + path, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body || {})});
  return {status: r.status, j: await r.json()};
};

/* ---------------------------------------------------------------- films */
// A film here is a second or two of a tone in a WAV called film.mp4: the worker's
// stand-in decodes exactly that (tests/fixtures/stt_runtime/faster_whisper/audio.py)
let filmNo = 0;
async function film(seconds = 3) {
  const p = `${TMP}/films/film-${++filmNo}.mp4`;
  await Deno.mkdir(TMP + '/films', {recursive: true});
  const r = await run('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `sine=frequency=440:duration=${seconds}`,
                                 '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', '-f', 'wav', p]);
  if (r.code) throw Error('ffmpeg: ' + r.err);
  return p;
}

/* ---------------------------------------------------------------- the browser */
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true,
                                       args: ['--autoplay-policy=no-user-gesture-required', '--disable-audio-output']});
const errors = [];
// Every request the page makes, the answers of the transcription's routes, and
// the dialogs it asks (answered by `dialogs.answer`, and remembered).  Nothing
// leaves the machine.
async function newPage({width = 1280, height = 900, init = null, theme = null} = {}) {
  const context = await browser.newContext({viewport: {width, height}});
  if (theme) await context.addInitScript(t => { try { localStorage.setItem('parseh_theme', t); } catch (e) {} }, theme);
  for (const f of [].concat(init || [])) await context.addInitScript(f);
  await context.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, route => route.abort());
  const page = await context.newPage();
  page.reqs = [];          // [method, path]
  page.said = [];          // [route, body] of every answer of the job's routes
  page.dialogs = [];       // the messages asked
  page.answer = true;      // what the next confirm gets
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
  page.on('dialog', d => { page.dialogs.push(d.message()); return page.answer ? d.accept() : d.dismiss(); });
  page.on('request', r => { const u = new URL(r.url()); page.reqs.push([r.method(), u.pathname + (u.host === `127.0.0.1:${port}` ? '' : ' @' + u.host)]); });
  page.on('response', async r => {
    const u = new URL(r.url());
    if (u.host !== `127.0.0.1:${port}` || !/\/api\/transcribe\//.test(u.pathname)) return;
    try { page.said.push([u.pathname.replace(/^.*\/transcribe\//, ''), r.status(), await r.json()]); } catch (_) {}
  });
  return {context, page};
}
const seen = (page, re) => page.reqs.filter(r => re.test(r[1])).length;
// the add page, opened on a source and a way, once its body is drawn
async function openAdd(page, {src = 'film', by = 'empty', lang = null} = {}) {
  await page.goto(`${BASE}/youtube/add/?src=${src}&by=${by}`);
  await page.waitForSelector('#transcript', {state: 'visible'});
  if (lang) { await page.selectOption('#lang', lang); }
}
// the block, once the computer has been asked and it has drawn itself
const blockReady = page => page.waitForFunction(() => { const s = document.getElementById('stt'); return s && !s.hidden; });
const shown = (page, sel) => page.evaluate(sel => {
  const el = document.querySelector(sel);
  if (!el || el.closest('[hidden]')) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
}, sel);
const text = (page, sel) => page.evaluate(sel => (document.querySelector(sel) || {}).textContent || '', sel);
const value = (page, sel) => page.inputValue(sel);
const phase = page => page.evaluate(() => document.getElementById('stt').getAttribute('data-state'));
const inPhase = (page, ph, what, ms = 20000) => until(async () => (await phase(page)) === ph, what || `the block is ${ph}`, ms);
async function reviewAndUse(page) {
  const before = await value(page, '#transcript');
  await inPhase(page, 'review', 'post-ASR transcript workspace', 60000);
  eq(await value(page, '#transcript'), before, 'ASR completion does not insert text');
  eq(await value(page, '#transcript'), before, 'opening review does not insert text');
  // a start opens "Transcribe & review" and it stays open; a page that was left (Return to Add Video) or reloaded while the
  // job ran has the window closed, and the review waits behind "Resume transcript review"
  if (!(await page.$eval('#stt_workspace', d => d.open))) {
    eq(await text(page, '#stt_open'), 'Resume transcript review', 'the window is closed: the review waits behind its button');
    await page.click('#stt_open');
  }
  await page.click('#stt_use');
  await inPhase(page, 'idle', 'explicit Use finishes the review');
}
// every control of the block that is on screen, enabled and would DO something
const live = page => page.evaluate(() => [...document.querySelectorAll('#stt button, #stt select, #stt a[href]')]
  .filter(e => e.getClientRects().length > 0 && !e.disabled).map(e => e.id || e.tagName));
const options = (page, sel) => page.$$eval(sel + ' option', os => os.map(o => [o.value, o.textContent]));
async function shot(page, name) {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`, fullPage: true});
}

let current = '';
async function section(id, title, fn) {
  if (ONLY.length && !ONLY.includes(id)) return;
  current = id;
  console.log(`${id}) ${title}`);
  await setState();
  await setFake();
  // every section starts on a host that has remembered nothing: since a0.4.3 the model chosen for a language is kept
  // by the host (config/speech.json), so a section that picks large-v3 would otherwise decide the next one's model
  await Deno.remove(TREE + '/config/speech.json').catch(() => {});
  await fn();
}

// the words the form must never carry: they are the runtime's, not the person's
const IMPLEMENTATION = /device_index|float16|int8|compute[ _]capability|CTranslate2|cuDNN|beam|vad/i;

try {
/* ================================================================ a) not installed */
await section('a', 'speech to text is not installed: a link, and nothing dead', async () => {
  await setState({runtime: false, models: []});
  const {context, page} = await newPage();
  await openAdd(page);
  await blockReady(page);
  eq(await phase(page), 'absent', 'the block says it is not set up');
  eq(await live(page), ['stt_setup'], 'the one thing that can be pressed is the way to set it up');
  const link = await page.$eval('#stt_setup', a => [a.getAttribute('href'), a.target, a.rel]);
  eq(link, ['/settings/speech/', '_blank', 'noopener'], 'it goes to Settings → Speech to text, in a tab of its own (the page and its draft stay)');
  const said = await text(page, '#stt_absent');
  assert(/optional/i.test(said) && /on this computer/.test(said) && /pasting one works exactly as it always did/.test(said),
         'and says in a line what it is and that it is optional: ' + said);
  assert(await shown(page, '#transcript') && await shown(page, '#subedit'), 'the transcript box and its editor are as they were');
  // nothing was asked of anyone because the page was opened
  // (a0.4.3: the page lists the reviews saved for later when it opens, so that Videos can offer to continue one: a read,
  // answered from the disk; nothing starts, nothing is sent)
  eq(seen(page, /transcribe(?!\/pending)/), 0, 'no transcription route was touched, but the list of saved reviews');
  eq(page.reqs.filter(r => / @/.test(r[1])).length, 0, 'nothing left the machine (' + JSON.stringify(page.reqs.filter(r => / @/.test(r[1]))) + ')');
  eq(page.reqs.filter(r => /lookup\/api/.test(r[1])).map(r => r[1]), ['/lookup/api/speech'], 'the one thing asked was what the computer has');
  await shot(page, 'a-absent-1280');

  // installed, but no model: the same, and it says what is missing
  await setState({runtime: true, models: []});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => /a model still has to be added/.test(await text(page, '#stt_absent')), 'a program without a model is said');
  eq(await live(page), ['stt_setup'], 'still only the way to set it up');

  // the manual way is untouched: a pasted transcript, started empty
  await page.fill('#path', await film());
  await page.fill('#transcript', '0:01\nسلام دنیا\n0:05\nخداحافظ\n');
  await page.selectOption('#lang', 'fa');
  await page.click('#empty');
  await page.waitForURL(/\/youtube\/v\/[^/]+\/$/, {timeout: 30000});
  const id = page.url().split('/').filter(Boolean).pop();
  assert(await exists(`${VIDEOS}/persian/${id}/annotations.json`), 'a video was added from the pasted transcript: ' + id);
  // and a video already in the library has nothing of speech to text in it
  await page.waitForSelector('.seg .fa .w', {timeout: 30000});
  const html = await page.content();
  const scripts = await page.$$eval('script[src]', s => s.map(x => x.getAttribute('src')));
  const bodies = [html];
  for (const s of scripts) if (!/^https?:/.test(s)) bodies.push(await (await fetch(BASE + s)).text());
  const trace = /whisper|speech[- ]to[- ]text|transcribe|addstt|ParsehAddStt|api\/transcribe|lookup\/api\/speech/i;
  eq(bodies.map(b => (b.match(trace) || [''])[0]).filter(Boolean), [], `the player of ${id} (and the ${scripts.length} scripts it loads) has no trace of speech to text`);
  assert(!(await page.$('#stt')) && !(await page.$('[id^="stt_"]')), 'and no control of it');
  await context.close();
});

/* ================================================================ b) installed: the pickers */
await section('b', 'installed: the models, the processor, and what is remembered', async () => {
  const {context, page} = await newPage();
  await openAdd(page);
  await blockReady(page);
  eq(await phase(page), 'idle', 'the block is drawn, idle');
  eq(await options(page, '#stt_model'),
     [['large-v3-turbo', 'faster-whisper / large-v3-turbo — Recommended · faster and lighter'],
      ['large-v3', 'faster-whisper / large-v3 — Higher accuracy · larger and slower']],
     'both models, the turbo one first, each with its trade-off');
  eq(await value(page, '#stt_model'), 'large-v3-turbo', 'large-v3-turbo is the default');
  eq(await options(page, '#stt_proc'), [['auto', 'Automatic — recommended'], ['cpu', 'CPU']],
     'Automatic and CPU, and no NVIDIA GPU: this computer has no card');
  eq(await text(page, '#stt_now'), 'Processing: Automatic · currently CPU', 'it says which one is meant, in the person\'s words');
  eq(await shown(page, '#stt_gpu'), false, 'and nothing about a card that is not there');
  const form = await text(page, '#stt');
  eq(form.match(IMPLEMENTATION), null, 'not one implementation word in the form: ' + (form.match(IMPLEMENTATION) || ['none'])[0]);
  // (a0.4.3 added a link, "Manage models", to Settings: a way out of the block, not an action of it)
  eq(await live(page).then(l => l.filter(x => x !== 'stt_model' && x !== 'stt_proc' && x !== 'A')), ['stt_go'],
     'the one action is Transcribe (a film needs nothing else)');
  assert(/Reads? the film|film named above/.test(await text(page, '#stt_how')), 'the film way says what it does: ' + await text(page, '#stt_how'));
  await shot(page, 'b-installed-1280');

  // only what is installed is offered
  for (const [have, dflt] of [[['large-v3-turbo'], 'large-v3-turbo'], [['large-v3'], 'large-v3']]) {
    await setState({models: have});
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await until(async () => { const o = await options(page, '#stt_model'); return o.length === 1 && o[0][0] === have[0]; },
                `${have} alone is offered`);
    eq([(await options(page, '#stt_model'))[0][0], await value(page, '#stt_model')], [have[0], dflt], `only ${have[0]} is offered, and it is the choice`);
  }
  await setState();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => (await options(page, '#stt_model')).length === 2, 'both again after the next look');

  // a card that is there and not ready: not an option, and the reason is said
  const why = 'The graphics card is not ready for speech to text: it needs cuBLAS for CUDA 12 (libcublas.so.12 was not found). CPU transcription still works.';
  await setState({cuda: {ready: false, name: 'NVIDIA GeForce GTX 1650', why}});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(() => shown(page, '#stt_gpu'), 'the card that is not ready is said');
  eq((await options(page, '#stt_proc')).map(o => o[0]), ['auto', 'cpu'], 'still no NVIDIA GPU to pick');
  eq(await text(page, '#stt_gpu'), why, 'and why not, in the computer\'s own words');
  eq(await text(page, '#stt_now'), 'Processing: Automatic · currently CPU', 'Automatic is on the CPU');
  await shot(page, 'b-card-not-ready-1280');
  // the card, ready
  await setState({cuda: {ready: true, name: 'NVIDIA GeForce RTX 4070', why: ''}});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => (await options(page, '#stt_proc')).length === 3, 'the NVIDIA GPU is an option once the computer says it is ready');
  eq(await options(page, '#stt_proc'), [['auto', 'Automatic — recommended'], ['cpu', 'CPU'], ['cuda', 'NVIDIA GPU']], 'Automatic, CPU and NVIDIA GPU');
  eq(await text(page, '#stt_now'), 'Processing: Automatic · currently NVIDIA GeForce RTX 4070', 'Automatic now says it is the card');
  eq(await shown(page, '#stt_gpu'), false, 'and the card is no longer a problem');
  await page.selectOption('#stt_proc', 'cuda');
  eq(await text(page, '#stt_now'), 'Processing: NVIDIA GPU · NVIDIA GeForce RTX 4070', 'chosen, it says so');
  await page.selectOption('#stt_proc', 'cpu');
  eq(await text(page, '#stt_now'), 'Processing: CPU', 'and the CPU too');
  eq((await text(page, '#stt')).match(IMPLEMENTATION), null, 'and still no implementation word');

  // what was chosen is this browser's memory (and nothing else's)
  await page.selectOption('#stt_model', 'large-v3');
  await page.selectOption('#stt_proc', 'cuda');
  const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('yt_add_stt')));
  // (a0.4.3 also remembers the model chosen for the video's language)
  eq(kept, {models_by_language: {fa: 'large-v3'}, model: 'large-v3', processing: 'cuda', exact: true},
     'the model (and the one for this language), processor and exact-word-times choice are kept in localStorage');
  await page.reload();
  await page.waitForSelector('#transcript', {state: 'visible'});
  await blockReady(page);
  await until(async () => (await options(page, '#stt_proc')).length === 3, 'drawn again');
  eq([await value(page, '#stt_model'), await value(page, '#stt_proc')], ['large-v3', 'cuda'], 'after a reload the same are chosen');
  // …unless they are no longer possible
  await setState({models: ['large-v3-turbo'], cuda: NO_CARD});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => (await options(page, '#stt_model')).length === 1, 'the model that was chosen is gone');
  eq([await value(page, '#stt_model'), await value(page, '#stt_proc')], ['large-v3-turbo', 'auto'], 'the choices fall back to what exists: a model that is installed, and Automatic');
  await context.close();
});

await section('b2', 'an install made in another tab appears with no reload; a language Whisper does not know', async () => {
  await setState({runtime: false, models: []});
  const {context, page} = await newPage();
  await openAdd(page, {lang: 'fa'});
  await blockReady(page);
  eq(await phase(page), 'absent', 'nothing installed');
  await setState();                                            // "installed in another tab"
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await inPhase(page, 'idle', 'the block appears when the page is looked at again');
  eq(await seen(page, /transcribe(?!\/pending)/), 0, 'and still nothing of a transcription was touched');
  // Whisper does not know Hindi (a person's own language would be so): nothing is offered
  await setState({no_lang: ['hi']});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.selectOption('#lang', 'hi');
  await until(async () => (await phase(page)) === 'nolang', 'a language Whisper lacks');
  eq(await live(page), [], 'nothing can be pressed');
  eq(await text(page, '#stt_why'), 'Speech to text cannot listen for Hindi. Paste the transcript instead, as always.', 'and it says so');
  await page.selectOption('#lang', 'fa');
  await inPhase(page, 'idle', 'back to a language it knows');
  await context.close();
});

/* ================================================================ c) a film on this computer */
async function chooseFilm(page, {lang = 'fa', seconds = 3} = {}) {
  const f = await film(seconds);
  await page.fill('#path', f);
  await page.selectOption('#lang', lang);
  return f;
}
const say = page => text(page, '#stt_say');
async function saysOver(page, until_) {   // every line the block says, in order, until `until_` is true
  const lines = [];
  for (let i = 0; i < 600; i++) {
    const s = await say(page);
    if (s && lines[lines.length - 1] !== s) lines.push(s);
    if (await until_()) break;
    await sleep(40);
  }
  return lines;
}
const inBox = page => value(page, '#transcript');
const PANEL_FA = '0:00\nسلام دنیا\n0:02.5\nخداحافظ\n';

await section('c', 'a film: Transcribe, the text in the box, the video not added', async () => {
  // slow enough for the page's own asking (every 1.2 s) to find it loading and listening
  await setFake({delay: 1.4, load_delay: 1.4});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'llm'});
  await blockReady(page);
  const f = await chooseFilm(page);
  const before = await names(VIDEOS + '/persian');
  await page.click('#stt_go');
  // its own words as it goes, and a bar that moves
  const lines = await saysOver(page, async () => (await phase(page)) === 'review');
  await reviewAndUse(page);
  assert(lines.some(l => /^Transcribing on CPU… \d+%$/.test(l)), 'it says how far it is: ' + JSON.stringify(lines));
  assert(lines.some(l => /^Loading large-v3-turbo…$/.test(l)), 'and that it loads the model first');
  eq(await inBox(page), PANEL_FA, 'the transcript is in the box, in the panel format: a clock line and the caption');
  // the page's own door reads it
  const read = await api('/youtube/api/transcript', {transcript: await inBox(page), lang: 'fa'});
  eq([read.status, read.j.captions.map(c => [c.start, c.text])], [200, [[0, 'سلام دنیا'], [2.5, 'خداحافظ']]], 'the page\'s own parser reads it back caption by caption');
  eq(await names(VIDEOS + '/persian'), before, 'the video was NOT added');
  eq(page.reqs.filter(r => /\/api\/(add|empty|local)$/.test(r[1])).length, 0, 'nothing called an add door');
  assert(/The transcript is in the box: 2 captions/.test(await text(page, '#stt_note')) && /has not been added/.test(await text(page, '#stt_note')), 'it says so: ' + await text(page, '#stt_note'));
  assert(/made by speech to text \(faster-whisper \/ large-v3-turbo\)/.test(await text(page, '#stt_tied')), 'the box is said to be its work: ' + await text(page, '#stt_tied'));
  // the box is immediately editable, and the editor takes it
  await page.click('#transcript');
  await page.keyboard.press('End');
  await page.keyboard.type('x');
  assert((await inBox(page)).endsWith('x'), 'the box can be typed into');
  await page.fill('#transcript', PANEL_FA);
  await page.click('#subedit');
  await page.waitForSelector('.se-row');
  eq(await page.$$eval('.se-row', rs => rs.map(r => [r.querySelector('.se-at').value, r.querySelector('.se-text').value])),
     [['0:00', 'سلام دنیا'], ['0:02.5', 'خداحافظ']], '"Edit the transcript…" opens the result as its captions');
  await page.click('.se-foot .se-use');
  await page.waitForSelector('.se-box', {state: 'detached'});
  eq(await inBox(page), PANEL_FA, 'and hands it back as the same panel');
  // a temporary recording is nothing to keep, and there is none
  eq(await names(STT_TMP), [], 'nothing is left in the temporary folder');
  await shot(page, 'c-film-done-1280');
  await context.close();
  eq(f.length > 0, true, 'a film');
});

await section('c2', 'while a film is transcribed: what is held, and Cancel', async () => {
  // slow: the whole run lasts long enough to be poked at
  await setFake({delay: 4, load_delay: 0.6});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'llm'});
  await blockReady(page);
  const f = await chooseFilm(page, {seconds: 6});
  await page.fill('#transcript', 'my own words');
  await page.click('#stt_go');
  eq(page.dialogs.length, 1, 'a box with words in it: the page asks first');
  assert(/^Replace the transcript in the box with a new one made by speech to text\?/.test(page.dialogs[0]), 'in these words: ' + page.dialogs[0]);
  await inPhase(page, 'working', 'the computer is at work');
  const job = page.said.find(x => x[0] === 'start')[2].job;
  eq([await shown(page, '#stt_go'), await shown(page, '#stt_cancel')], [false, true], 'Transcribe is gone while it runs, Cancel is there (no second start from here)');
  const second = await api('/youtube/api/transcribe/start', {source: 'film', path: f, lang: 'fa', model: 'large-v3-turbo', processing: 'cpu'});
  eq([second.status, second.j.code], [409, 'busy'], 'and the computer refuses a second one');
  // a0.4.3: a start opens "Transcribe & review", a modal window with the video, the progress and Cancel.  The page
  // behind it cannot be reached at all while it is open (a click on a card lands on the window's backdrop)...
  eq(await page.$eval('#stt_workspace', d => [d.open, d.matches(':modal')]), [true, true], 'the transcription opened its window, a modal one');
  eq(await page.evaluate(() => { const card = document.querySelector('.path[data-src="yt"]');
                                 card.scrollIntoView({block: 'center'});     // (the page was scrolled down to the box)
                                 const r = card.getBoundingClientRect();
                                 const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                                 return !!hit && !hit.closest('.path') && !!hit.closest('#stt_workspace'); }), true,
     'and behind it the other source card is out of reach: a press there lands on the window');
  // ...until the person returns to the page.  The job goes on, and "Open transcription" is the way back in
  await page.click('#stt_back');
  await until(async () => !(await page.$eval('#stt_workspace', d => d.open)), 'Return to Add Video closes the window');
  eq([await phase(page), await shown(page, '#stt_open'), await text(page, '#stt_open')], ['working', true, 'Open transcription'],
     'the job goes on, and the way back is a button on the page');
  eq([await shown(page, '#stt_go'), await shown(page, '#stt_cancel')], [false, false],
     'no Transcribe on the page, and Cancel stays in the window (no second start from here either)');
  // held: the video, its language, the model -- each answers, and nothing changes
  const toast = () => page.evaluate(() => { const t = document.getElementById('parseh-toast'); return t && t.classList.contains('show') ? t.textContent : ''; });
  const HELD = 'a transcription is running — cancel it first';
  // (aria-disabled, so a person's tool says "unavailable" -- and the test has to force what it presses)
  await page.click('.path[data-src="yt"]', {force: true});
  eq(await toast(), HELD, 'the other source card answers: ' + HELD);
  eq([await shown(page, '#src-film'), await shown(page, '#src-yt')], [true, false], 'and the source did not change');
  await sleep(1600);
  await page.selectOption('#lang', 'ar', {force: true});
  eq([await value(page, '#lang'), await toast()], ['fa', HELD], 'the language is put back, and says why');
  await sleep(1600);
  await page.selectOption('#stt_model', 'large-v3', {force: true});
  eq([await value(page, '#stt_model'), await toast()], ['large-v3-turbo', HELD], 'so is the model');
  await sleep(1600);
  await page.click('#path', {force: true});
  await page.keyboard.type('zzz');
  eq([await value(page, '#path'), await toast()], [f, HELD], 'and the film\'s path cannot be typed into');
  await page.selectOption('#gloss', 'it');
  eq(await value(page, '#gloss'), 'it', 'the language of the glosses is not part of the transcript, and is free');
  // Cancel (it is in the window: the way back in first): nothing written, nothing left, nothing stuck
  await page.click('#stt_open');
  await until(() => shown(page, '#stt_cancel'), 'the window is open again, with Cancel');
  await page.click('#stt_cancel');
  await inPhase(page, 'idle', 'Cancel ends it');
  eq(await page.$eval('#stt_workspace', d => d.open), false, 'and closes the window');
  eq(await inBox(page), 'my own words', 'the box is exactly as it was');
  assert(/was cancelled\. The transcript in the box was not touched\./.test(await text(page, '#stt_note')), 'and it says so: ' + await text(page, '#stt_note'));
  const st = await api('/youtube/api/transcribe/status', {job});
  eq([st.j.state, st.j.stopped], ['cancelled', true], 'the computer agrees');
  eq(await names(STT_TMP), [], 'no temporary audio');
  await page.selectOption('#lang', 'ar');
  eq(await value(page, '#lang'), 'ar', 'the language is free again');
  await page.selectOption('#lang', 'fa');
  eq(await page.$eval('#path', e => e.readOnly), false, 'and so is the path');
  // and it can be started again
  await page.click('#stt_go');
  await inPhase(page, 'working', 'a second start, after Cancel, works');
  await page.click('#stt_cancel');
  await inPhase(page, 'idle', 'and can be cancelled too');
  eq(await inBox(page), 'my own words', 'still nothing written');
  await shot(page, 'c2-cancelled-1280');
  await context.close();
});

await section('c3', 'never over a person\'s words unasked; the prompt made stale; whose the box is', async () => {
  await setFake({delay: 0.7, load_delay: 0.7});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'llm'});
  await blockReady(page);
  await chooseFilm(page);
  const PANEL_MINE = '0:01\nسلام\n0:05\nخداحافظ\n';
  await page.fill('#transcript', PANEL_MINE);
  // a prompt for an LLM, prepared from the transcript
  await page.click('#prepare');
  await until(async () => /captions/.test(await text(page, '#pinfo')), 'the prompt is prepared', 20000);
  assert(await shown(page, '#pshow') && await shown(page, '#pinfo'), 'it is prepared and shown');
  // asked, and "no": nothing starts, nothing changes
  page.answer = false;
  await page.click('#stt_go');
  eq(page.dialogs.length, 1, 'the box holds the person\'s own panel: asked');
  eq([await phase(page), seen(page, /transcribe\/start/), await inBox(page)], ['idle', 0, PANEL_MINE], '"no": nothing started, the box is as it was');
  assert(await shown(page, '#pshow'), 'and the prompt is still good');
  // "yes"
  page.answer = true;
  await page.click('#stt_go');
  await reviewAndUse(page);
  await inPhase(page, 'idle');
  eq([await shown(page, '#pshow'), await shown(page, '#pinfo')], [false, false], 'the prompt prepared before is out of date: gone');
  eq(page.dialogs.length, 3, 'start and final Use both confirm replacement');
  // whose the box is
  assert(await shown(page, '#stt_tied') && /made by speech to text/.test(await text(page, '#stt_tied')), 'the box says it was made by speech to text');
  // a run over what speech to text itself wrote asks nothing
  await page.click('#stt_go');
  await until(async () => (await phase(page)) !== 'idle', 'a second run starts');
  eq(page.dialogs.length, 3, 'over its own unedited work: not asked to start');
  await reviewAndUse(page);
  // edited: the tie says so, and it asks again
  await page.click('#transcript');
  await page.keyboard.press('End');
  await page.keyboard.type('x');
  assert(await shown(page, '#stt_tied') && /has been edited since/.test(await text(page, '#stt_tied')), 'an edit is said: ' + await text(page, '#stt_tied'));
  page.answer = false;
  await page.click('#stt_go');
  eq([page.dialogs.length, await phase(page)], [4, 'idle'], 'over an edited box it asks, and "no" leaves it');
  // the same text typed back is the same box
  await page.fill('#transcript', PANEL_FA);
  assert(await shown(page, '#stt_tied') && /made by speech to text/.test(await text(page, '#stt_tied')) && !/edited since/.test(await text(page, '#stt_tied')), 'the same words are its work again (the tie is the text, not the keystrokes)');
  // the processor changes nothing about the transcript
  await page.selectOption('#stt_proc', 'cpu');
  assert(await shown(page, '#stt_tied'), 'changing the processor keeps the box tied');
  // an LLM prompt is stale the moment the box, the video or the word list changes by typing
  const prepare = async () => { await page.click('#prepare'); await until(async () => /captions/.test(await text(page, '#pinfo')), 'prepared', 20000); };
  await prepare();
  await page.click('#transcript'); await page.keyboard.press('End'); await page.keyboard.type(' ');
  eq([await shown(page, '#pshow'), await shown(page, '#pinfo')], [false, false], 'typing in the transcript makes a prepared prompt stale');
  await page.fill('#transcript', PANEL_FA);
  assert(await shown(page, '#stt_tied'), 'and the box that is its work again is tied again');
  // the language
  await page.selectOption('#lang', 'ar');
  eq(await shown(page, '#stt_tied'), false, 'another language: the box is no longer tied to it');
  assert(/no longer tied to speech to text: the language changed/.test(await text(page, '#stt_note')), 'and it says so, quietly: ' + await text(page, '#stt_note'));
  eq(await inBox(page), PANEL_FA, 'the words themselves stay');
  await page.selectOption('#lang', 'fa');
  eq(await shown(page, '#stt_tied'), false, 'and going back does not tie it again');
  await prepare();
  await page.click('#path'); await page.keyboard.press('End'); await page.keyboard.type('z');
  eq(await shown(page, '#pshow'), false, 'typing in the film\'s path makes a prepared prompt stale too');
  await page.fill('#path', await film());
  // a fresh transcription (asked: the tie was dropped), then the model
  page.answer = true;
  await page.click('#stt_go');
  await until(async () => (await phase(page)) !== 'idle', 'started');
  await reviewAndUse(page);
  assert(await shown(page, '#stt_tied'), 'tied again');
  await page.selectOption('#stt_model', 'large-v3');
  eq(await shown(page, '#stt_tied'), false, 'another model: not tied');
  assert(/the model changed/.test(await text(page, '#stt_note')), 'and says so');
  // and the video (the path) -- from a tied box again
  await page.click('#stt_go');
  await until(async () => (await phase(page)) !== 'idle', 'started');
  await reviewAndUse(page);
  assert(await shown(page, '#stt_tied'), 'tied to the second model');
  await page.fill('#path', await film());
  eq(await shown(page, '#stt_tied'), false, 'another film: not tied');
  assert(/the video changed/.test(await text(page, '#stt_note')), 'and says so');
  await shot(page, 'c3-untied-1280');
  await context.close();
});

await section('c4', 'editing the transcript while ASR runs discards stale review', async () => {
  await setFake({delay: 1.6, load_delay: 1.6});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'empty'}); await blockReady(page); await chooseFilm(page);
  await page.click('#stt_go'); await inPhase(page, 'working', 'running');
  // (the window of a0.4.3 holds the page behind it: the box is typed into from the page, once it is returned to)
  await page.click('#stt_back');
  await until(async () => !(await page.$eval('#stt_workspace', d => d.open)), 'back on the page');
  await page.fill('#transcript', 'typed while it ran');
  await inPhase(page, 'idle', 'stale result discarded', 40000);
  eq(await inBox(page), 'typed while it ran', 'the edited box stays untouched');
  eq(await shown(page, '#stt_use'), false, 'stale results cannot be applied');
  assert(/stale review was discarded/.test(await text(page, '#stt_note')), 'the reason is visible');
  eq(page.dialogs.length, 0, 'stale results never offer to replace the edited box');
  await context.close();
});

await section('c5', 'the other source card breaks the tie, and leaves the words', async () => {
  await setFake({delay: 0.7, load_delay: 0.7});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'llm'});
  await blockReady(page);
  await chooseFilm(page);
  await page.click('#stt_go');
  await reviewAndUse(page);
  await inPhase(page, 'idle');
  assert(await shown(page, '#stt_tied'), 'the box is tied to the film');
  await page.click('.path[data-src="yt"]');
  eq(await shown(page, '#stt_tied'), false, 'the YouTube card: no longer tied');
  assert(/no longer tied to speech to text: the video changed/.test(await text(page, '#stt_note')), await text(page, '#stt_note'));
  eq(await inBox(page), PANEL_FA, 'and the words stay, as the page has always kept a transcript when the source changed');
  await page.fill('#url', 'aB3dE5fG7hJ');
  eq(await phase(page), 'idle', 'on YouTube the block is drawn for it (and the tie is not back)');
  eq(await shown(page, '#stt_tied'), false, 'not tied to that either');
  await context.close();
});

/* ================================================================ d) the words of a failure */
await section('d', 'failures are sentences, and nothing is left stuck', async () => {
  const {context, page} = await newPage();
  await openAdd(page, {by: 'llm'});
  await blockReady(page);
  await chooseFilm(page);
  await page.fill('#transcript', 'keep me');
  const failure = async (what) => {
    await inPhase(page, 'idle', what, 40000);
    return text(page, '#stt_note');
  };
  const untouched = async (what) => eq([await inBox(page), await shown(page, '#stt_go'), await shown(page, '#stt_cancel')], ['keep me', true, false], what);

  // another job holds the slot
  const yt = await api('/youtube/api/transcribe/start', {source: 'youtube', url: 'https://www.youtube.com/watch?v=zA1bC2dE3fG', lang: 'fa', model: 'large-v3-turbo', processing: 'cpu'});
  assert(yt.j.ok, 'a recording is under way elsewhere');
  await page.click('#stt_go');
  const busy = await failure('the busy answer');
  eq(busy, 'Another transcription is running. Wait for it to finish, or stop it from the page that started it.', 'a second job is refused, in words: ' + busy);
  await untouched('and the box and the buttons are as they were');
  await api('/youtube/api/transcribe/cancel', {job: yt.j.job});
  eq(await names(STT_TMP), [], 'nothing left of the recording that was cancelled');
  // the slice says it is busy
  await setState({busy: true});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(() => shown(page, '#stt_busy'), 'a busy computer is said');
  assert(/busy right now/.test(await text(page, '#stt_busy')), await text(page, '#stt_busy'));
  eq(await shown(page, '#stt_go'), true, 'but the button stays: the computer decides');
  await setState();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => !(await shown(page, '#stt_busy')), 'and it stops saying it');

  // a film that is not there
  await page.fill('#path', '/nowhere/at/all.mp4');
  await page.click('#stt_go');
  const gone = await failure('no such file');
  assert(/no file at \/nowhere\/at\/all\.mp4/.test(gone), 'the add flow\'s own sentence: ' + gone);
  await untouched('nothing changed');
  await page.fill('#path', await film());

  // no speech in it
  await setFake({segments: []});
  await page.click('#stt_go');
  const quiet = await failure('an empty result');
  assert(quiet.length > 10 && !/Traceback|Error:/.test(quiet), 'a film with no words in it is said in a sentence: ' + quiet);
  await untouched('and the box is as it was');

  // the card that will not start, chosen on purpose: no going behind the back
  await setState({cuda: {ready: true, name: 'NVIDIA GeForce RTX 4070', why: ''}});
  await setFake({cuda_load_error: 'boom', delay: 1.6, load_delay: 1.6});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await until(async () => (await options(page, '#stt_proc')).length === 3, 'the card is offered');
  await page.selectOption('#stt_proc', 'cuda');
  await page.click('#stt_go');
  const gpu = await failure('the card that would not start');
  eq(gpu, 'CUDA was requested but could not be initialized. Choose Automatic or CPU to use the processor instead.', 'an explicit NVIDIA GPU that fails says so and does nothing else: ' + gpu);
  await untouched('the box is as it was');
  assert(!/boom|Traceback/.test(await text(page, '#stt')), 'and no traceback, no runtime message, on the page');
  // Automatic: the same card, and the same failure, is no failure
  await page.selectOption('#stt_proc', 'auto');
  await page.click('#stt_go');
  const lines = await saysOver(page, async () => (await phase(page)) === 'review');
  await reviewAndUse(page);
  assert(lines.some(l => l.startsWith('The graphics card could not start this model, so Parseh continued on the CPU.')),
         'Automatic says that it fell back to the CPU: ' + JSON.stringify(lines));
  eq(await inBox(page), PANEL_FA, 'and the transcript arrives');
  await shot(page, 'd-fell-back-1280');

  // a computer that says nothing
  await setState();
  await setFake({delay: 2, load_delay: 2});
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.fill('#transcript', '');
  await page.route('**/transcribe/status', r => r.abort());
  await page.click('#stt_go');
  await until(async () => /has not answered for a moment/.test(await text(page, '#stt_note')), 'silence is said', 30000);
  eq(await phase(page), 'working', 'and is not a verdict: it goes on waiting');
  await page.unroute('**/transcribe/status');
  await reviewAndUse(page);
  eq(await inBox(page), PANEL_FA, 'the transcript arrives');
  eq(await shown(page, '#stt_note') && !/has not answered/.test(await text(page, '#stt_note')), true, 'and the silence is no longer said');

  // …and one that says nothing exactly when the words are asked for: the job is done, so
  // the page asks again (and never starts another, which would be an hour of sound for nothing)
  await setFake({delay: 0.7, load_delay: 0.7});
  await page.fill('#transcript', '');
  let asks = 0;
  const startsBefore = seen(page, /transcribe\/start/), usesBefore = seen(page, /transcribe\/use/);
  await page.route('**/transcribe/result', r => (++asks <= 2 ? r.abort() : r.continue()));
  await page.click('#stt_go');
  await reviewAndUse(page);
  // (the words are asked for until they are given -- twice unanswered, the third answers; they are not asked for again
  // after "Use this transcript", which is a route of its own: a0.4.3 holds them in the page as the pending review)
  eq([await inBox(page), asks, seen(page, /transcribe\/start/) - startsBefore, seen(page, /transcribe\/use/) - usesBefore], [PANEL_FA, 3, 1, 1],
     'result retried until answered (twice silent, the third answers), then used by the explicit Use alone; only one job was ever started for it');
  await page.unroute('**/transcribe/result');

  // installed a moment ago, gone now: the page finds out when it asks
  await setState({runtime: false, models: []});
  await page.fill('#transcript', '');
  await page.click('#stt_go');
  await until(async () => (await phase(page)) === 'absent', 'the block falls back to the link');
  eq(await live(page), ['stt_setup'], 'and the only thing left to press is the way to set it up');
  await context.close();
});

await section('d2', 'a reload finds a running job again; nothing is left stuck', async () => {
  await setFake({delay: 3, load_delay: 1});
  const {context, page} = await newPage();
  await openAdd(page, {by: 'empty'});
  await blockReady(page);
  await chooseFilm(page);
  await page.click('#stt_go');
  await inPhase(page, 'working', 'running');
  await page.reload();
  await page.waitForSelector('#transcript', {state: 'visible'});
  await inPhase(page, 'working', 'after a reload the block is at the job again');
  eq([await value(page, '#lang'), await page.$eval('#path', e => e.readOnly)], ['fa', true], 'with the same video and language, held');
  assert(await shown(page, '#stt_cancel'), 'and Cancel');
  await reviewAndUse(page);
  eq(await inBox(page), PANEL_FA, 'and the text arrives in the box the draft gave back');
  assert(await shown(page, '#stt_tied') && /made by speech to text/.test(await text(page, '#stt_tied')), 'tied');
  const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('yt_add_stt_state')));
  eq(kept.job, null, 'no job is remembered any more');
  // the tie outlives a reload too
  await page.reload();
  await page.waitForSelector('#transcript', {state: 'visible'});
  await blockReady(page);
  assert(await shown(page, '#stt_tied') && /made by speech to text/.test(await text(page, '#stt_tied')), 'after another reload the box is still its work');
  // a job cancelled, then a reload: idle
  await page.fill('#transcript', '');
  await page.click('#stt_go');
  await inPhase(page, 'working', 'running again');
  await page.click('#stt_cancel');
  await inPhase(page, 'idle', 'cancelled');
  await page.reload();
  await page.waitForSelector('#transcript', {state: 'visible'});
  await blockReady(page);
  eq([await phase(page), await page.$eval('#path', e => e.readOnly)], ['idle', false], 'a reload after Cancel finds nothing running, nothing held');
  // a job whose computer forgot it (Parseh was restarted): forgotten, not stuck
  await page.evaluate(() => localStorage.setItem('yt_add_stt_state', JSON.stringify({job: {id: 'AAAAAAAAAAAAAAAA', kind: 'film', key: 'film:/x', lang: 'fa', model: 'large-v3-turbo', hash: ''}})));
  await page.reload();
  await page.waitForSelector('#transcript', {state: 'visible'});
  await blockReady(page);
  await sleep(600);
  eq([await phase(page), await page.$eval('#path', e => e.readOnly)], ['idle', false], 'a job the computer no longer knows is let go');
  await context.close();
});

/* ================================================================ e) a browser that cannot record a tab */
await section('e', 'a browser that cannot record a tab: the YouTube way says so, the rest works', async () => {
  const module_ = {
    firefox: [() => Object.defineProperty(navigator, 'userAgentData', {get: () => undefined}),
              'only Chrome and Edge, on a computer, can record the sound of a tab', 1280],
    http: [() => Object.defineProperty(window, 'isSecureContext', {get: () => false}),
           'recording this tab needs the page opened at the toolbox’s https address, in Chrome or Edge', 1280],
    phone: [() => Object.defineProperty(navigator, 'userAgentData', {get: () => ({brands: [{brand: 'Chromium', version: '1'}], mobile: true})}),
            'only Chrome and Edge, on a computer, can record the sound of a tab', 390],
  };
  for (const [name, [init, why, width]] of Object.entries(module_)) {
    const {context, page} = await newPage({width, init});
    await openAdd(page, {src: 'yt', by: 'empty'});
    await blockReady(page);
    eq(await phase(page), 'notab', `${name}: the YouTube way is unavailable`);
    eq(await text(page, '#stt_why'),
       'Automatic transcription of a YouTube video records this tab’s sound while the video plays, and this browser cannot: ' + why +
       '. Pasting the transcript works as it always did.', `${name}: in the module's own words`);
    eq(await live(page), [], `${name}: nothing to press, no dead button`);
    await shot(page, `e-${name}-${width}`);
    // the manual way, as ever
    await page.fill('#url', 'zB1cD2eF3gH');
    await page.selectOption('#lang', 'fa');
    await page.fill('#transcript', '0:01\nسلام دنیا\n0:05\nخداحافظ\n');
    await page.click('#empty');
    await page.waitForURL(/\/youtube\/v\/zB1cD2eF3gH\/$/, {timeout: 30000});
    assert(await exists(`${VIDEOS}/persian/zB1cD2eF3gH/annotations.json`), `${name}: the pasted transcript still makes a video`);
    await Deno.remove(`${VIDEOS}/persian/zB1cD2eF3gH`, {recursive: true});
    // and a film needs no recording at all
    await openAdd(page, {src: 'film', by: 'empty'});
    await blockReady(page);
    await chooseFilm(page);
    await page.click('#stt_go');
    await reviewAndUse(page);
    await context.close();
  }
});

await section('review', 'pending LLM draft, accessible details and Unicode-safe edits', async () => {
  const {context, page} = await newPage();
  await openAdd(page, {by: 'empty'}); await blockReady(page);
  await page.evaluate(() => {
    const root = document.createElement('section'); root.id = 'review-contract'; document.body.appendChild(root);
    const original = '0:00\n🙂 loro anno detto ciao\n';
    window.reviewApplied = null;
    const word = {segment_id: 's0', word_id: 's0w2', text: 'anno', start: .5, end: .75,
      asr_confidence: .3, asr_alternatives: [{text: 'hanno', score: .37}], alternatives_available: true,
      low_asr_score: true, reviewable: true, span_start: Array.from(original.slice(0, original.indexOf('anno'))).length,
      span_end: Array.from(original.slice(0, original.indexOf('anno') + 4)).length};
    const res = {text: original, review: {evidence: {source_sha256:'source', low_score_threshold:.5,
      segments: [{segment_id:'s0', start:0, text:'🙂 loro anno detto ciao', words:[word]}]},
      correction:{state:'complete',complete:true}, result:{schema_version:1, assessment:'suggestions', suggestions:[{
        segment_id:'s0',word_id:'s0w2',original:'anno',error_likelihood:.8,reason:'ASR alternative and context.',
        candidates:[{text:'hanno',confidence:.7,reason:'Matches the sentence.'}]}]}}};
    window.contractReview = ParsehAsrReview.mount(root, {choose: function(){}, cancel: function(){},
      use: function(decisions,manual){ window.reviewApplied = decisions; window.reviewManual = manual; },
      retry: function(ids){ window.reviewRetried = ids; }});
    contractReview.show(res, 'review', {configured:true,base_url:'http://saved/v1',selected_model:'served'});
  });
  const marked = '#review-contract [data-review-word="s0w2"]';
  await page.hover(marked);
  assert(/Low ASR score/.test(await text(page, '#review-contract .stt-review-details')), 'hover exposes ASR evidence');
  await page.focus(marked);
  assert(/model estimate/.test(await text(page, '#review-contract .stt-review-details')), 'keyboard focus exposes model estimates');
  await page.click(marked);
  await page.getByRole('button', {name:'Accept this alternative',exact:true}).click();
  eq(await page.evaluate(() => window.reviewApplied), null, 'accept changes only the pending draft');
  eq(await text(page, '#review-contract pre'), '0:00\n🙂 loro hanno detto ciao\n', 'Unicode offsets preserve the emoji and change only the selected span');
  await page.getByRole('button', {name:'Reject this edit / keep Whisper word',exact:true}).click();
  eq(await text(page, '#review-contract pre'), '0:00\n🙂 loro anno detto ciao\n', 'reject restores the original span');
  await page.getByRole('button', {name:'Accept this alternative',exact:true}).click();
  await page.locator('#review-contract #stt_use').click();
  eq(await page.evaluate(() => window.reviewApplied), {s0w2:0}, 'only explicit Use hands off decisions');
  await page.getByRole('button', {name:'Reject this edit / keep Whisper word',exact:true}).click();
  await page.locator('#review-contract #stt_manual_word').fill('avevano');
  await page.locator('#review-contract #stt_manual_word').press('Enter');
  eq(await text(page, '#review-contract pre'), '0:00\n🙂 loro avevano detto ciao\n', 'keyboard edits stay in the Unicode-safe pending draft');
  await page.locator('#review-contract #stt_use').click();
  eq(await page.evaluate(() => window.reviewManual), {s0w2:'avevano'}, 'explicit Use hands off manual edits');
  assert(await page.locator('#review-contract #stt_review_retry').isDisabled(), 'manual corrections are excluded from retry');
  await page.getByRole('button', {name:'Restore Whisper word',exact:true}).click();
  await page.locator('#review-contract #stt_review_retry').click();
  eq(await page.evaluate(() => window.reviewRetried), ['s0w2'], 'one retry action selects the remaining suspicious words');
  assert(await page.locator('#review-contract a[download]').count() === 3, 'review offers separate correction, whole-text and workspace skill downloads');
  assert(await page.locator('#review-contract #stt_review_full').count() === 1, 'whole-text review is an explicit choice');
  eq(await inBox(page), '', 'review component never writes to the existing transcript box');
  await context.close();
});

await section('external', 'external review without an endpoint and explicit draft use', async () => {
  const {context, page} = await newPage();
  await openAdd(page, {by: 'empty'}); await blockReady(page);
  await page.evaluate(() => {
    const root = document.createElement('section'); root.id = 'external-contract'; document.body.appendChild(root);
    const original = '0:00\n🙂 loro anno detto ciao\n';
    const word = {segment_id:'s0', word_id:'s0w2', text:'anno', start:.5, end:.75,
      asr_confidence:.3, low_asr_score:true, alternatives_available:false, asr_alternatives:[], reviewable:true,
      span_start:Array.from(original.slice(0, original.indexOf('anno'))).length,
      span_end:Array.from(original.slice(0, original.indexOf('anno') + 4)).length};
    let res = {text:original, review:{choice:null, evidence:{language:'it', source_sha256:'source',
      low_score_threshold:.5, segments:[{segment_id:'s0', start:0, end:2, text:'🙂 loro anno detto ciao', words:[word]}]}}};
    window.externalApplied = null;
    window.externalContract = ParsehAsrReview.mount(root, {job:() => 'fake-job', current:() => true,
      choose:() => {}, cancel:() => {}, use:decisions => { window.externalApplied = decisions; },
      external:(action, values) => {
        if (action === 'start') {
          window.externalStartValues = values;
          // what the server says: a reasoning workspace is one undivided prompt unless it was asked to divide
          res.review = {...res.review, choice:'external', result:{task:values.task, suggestions:[]},
            external:{id:'session-' + values.task, task:values.task, index:0, batches:1, finished:false,
              divided:values.task !== 'workspace' || values.divide === true,
              submitted:[], words_done:0, words_total:1, prompt:'A bounded prompt for ' + values.task}};
        }
        if (action === 'cancel') res.review = {...res.review, choice:null, external:null, result:null};
        if (action === 'answer') {
          if (values.answer !== 'sentence0: 🙂 loro hanno detto ciao') return Promise.reject(new Error('Invalid pasted answer.'));
          res.review = {...res.review, external:{...res.review.external, finished:true, submitted:[0], words_done:1},
            result:{task:res.review.external.task, suggestions:[{...word, original:'anno', error_likelihood:null,
              candidates:[{text:'hanno', confidence:null, reason:''}]}]}};
        }
        return Promise.resolve({res:JSON.parse(JSON.stringify(res)), state:res.review.choice ? 'review' : 'choice', connection:{configured:false}});
      }});
    externalContract.show(res, 'choice', {configured:false});
  });
  const panel = page.locator('#external-contract #stt_external');
  for (const method of ['suspect', 'full', 'workspace']) {
    if (!(await panel.evaluate(node => node.open))) await panel.locator('summary').click();
    await panel.locator('#stt_external_task').selectOption(method);
    // dividing a reasoning workspace into prompts is an option, off, and only that method has it
    eq(await panel.locator('#stt_external_divide').isVisible(), method === 'workspace', `${method}: the option to divide is for the workspace alone`);
    eq(await panel.locator('#stt_external_divide').isChecked(), false, `${method}: and it is off`);
    await panel.locator('#stt_external_start').click();
    await until(async () => (await panel.locator('#stt_external_prompt').inputValue()).includes(method), 'external prompt ready');
    eq(await page.evaluate(() => window.externalStartValues.divide), false, `${method}: the request does not ask to divide`);
    if (method === 'workspace') {
      assert(/The whole transcript · /.test(await panel.textContent()), 'the undivided workspace says it is the whole transcript');
      eq([await panel.getByRole('button', {name:'Previous prompt', exact:true}).count(), await panel.getByRole('button', {name:'Next prompt', exact:true}).count()], [0, 0],
         'and has no previous or next prompt to go to');
      assert(/whole transcript and its evidence/.test(await panel.textContent()), 'and says the ZIP is where the transcript is');
    } else {
      assert(/Prompt 1 of 1/.test(await panel.textContent()), `${method}: the divided methods count their prompts as before`);
      eq(await panel.getByRole('button', {name:'Next prompt', exact:true}).count(), 1, `${method}: and keep their buttons`);
    }
    assert(!(await page.locator('#external-contract #stt_use').isDisabled()), 'Use is not refused while waiting for a paste: the transcript is obtainable at any time');
    assert(await panel.locator('#stt_external_copy').count() === 1, 'one shared copy control');
    assert(await panel.locator('#stt_external_files').count() === (method === 'workspace' ? 1 : 0), 'workspace download for the workspace method');
    if (method === 'workspace') assert(/session=session-workspace/.test(await panel.locator('#stt_external_files').getAttribute('href')), 'download belongs to this session');
    eq(await inBox(page), '', 'preparing prompts leaves the transcript box untouched');
    await panel.getByRole('button', {name:'Cancel external review', exact:true}).click();
    await until(async () => await panel.locator('#stt_external_prompt').count() === 0, 'external review cancelled');
  }
  // asked to divide, the workspace is a review in prompts like the others
  if (!(await panel.evaluate(node => node.open))) await panel.locator('summary').click();
  await panel.locator('#stt_external_task').selectOption('workspace');
  await panel.locator('#stt_external_divide').check();
  await panel.locator('#stt_external_start').click();
  await until(async () => (await panel.locator('#stt_external_prompt').inputValue()).includes('workspace'), 'divided workspace prompt ready');
  eq(await page.evaluate(() => window.externalStartValues.divide), true, 'the box asks the server to divide');
  assert(/Prompt 1 of 1/.test(await panel.textContent()), 'a divided workspace counts its prompts');
  eq(await panel.getByRole('button', {name:'Next prompt', exact:true}).count(), 1, 'and has its previous and next prompt');
  await panel.getByRole('button', {name:'Cancel external review', exact:true}).click();
  await until(async () => await panel.locator('#stt_external_prompt').count() === 0, 'divided review cancelled');
  eq(await panel.locator('#stt_external_divide').isChecked(), true, 'the box keeps what was chosen for the next review');
  await panel.locator('#stt_external_divide').uncheck();
  if (!(await panel.evaluate(node => node.open))) await panel.locator('summary').click();
  await panel.locator('#stt_external_task').selectOption('suspect');
  await panel.locator('#stt_external_start').click();
  await panel.locator('#stt_external_answer').fill('invalid answer');
  await panel.locator('#stt_external_import').click();
  await until(async () => /Invalid pasted answer/.test(await panel.locator('#stt_external_status').textContent()), 'invalid import explained');
  eq(await panel.locator('#stt_external_answer').inputValue(), 'invalid answer', 'failure preserves pasted text');
  await panel.locator('#stt_external_answer').fill('sentence0: 🙂 loro hanno detto ciao');
  await panel.locator('#stt_external_import').click();
  await until(async () => !(await page.locator('#external-contract #stt_use').isDisabled()), 'import ready for review');
  // what the page says now: the five steps, on the fourth; the answer's outcomes; and the walk, open on what came in
  eq(await page.locator('#external-contract #stt_external_steps li.now').textContent(), 'Go through the answers', 'the steps say that the answers are to be gone through');
  eq(await page.locator('#external-contract #stt_external_steps li.done').count(), 3, 'and that the three before it are done');
  assert((await page.locator('#external-contract #stt_external_result').textContent()).includes('1 edits proposed'), 'the answer says what it came to');
  assert(await page.locator('#external-contract .stt-walk-card').isVisible(), 'the walk opens by itself on the answer that came in');
  assert((await page.locator('#external-contract .stt-walk-head').textContent()).includes('The model suggests a correction'), 'with its first proposal');
  await page.locator('#external-contract .stt-walk-card').press('s');
  assert((await page.locator('#external-contract .stt-walk-end').textContent()).includes('Nothing will change'), 'skipping it ends the walk, which says that nothing will change');
  eq(await page.evaluate(() => externalContract.snapshot().walk.skipped), ['s0w2'], 'and the draft remembers the word as skipped');
  await page.locator('#external-contract [data-review-word="s0w2"]').click();
  await page.locator('#external-contract').getByRole('button', {name:'Accept this alternative', exact:true}).click();
  eq(await page.evaluate(() => window.externalApplied), null, 'import and accept change only the draft');
  eq(await inBox(page), '', 'import and accept leave the transcript box untouched');
  await page.locator('#external-contract #stt_use').click();
  eq(await page.evaluate(() => window.externalApplied), {s0w2:0}, 'explicit Use hands off the accepted edit');
  await page.evaluate(() => externalContract.clear());
  await context.close();
});

/* ================================================================ f) every language, width and theme */
await section('f', 'every language, two widths, three themes, left to right and right to left', async () => {
  await setFake({delay: 30, load_delay: 0.3});
  const LANGS = await api('/lookup/api/speech', {}).then(r => Object.keys(r.j.languages));
  assert(LANGS.length >= 11, `the selector has ${LANGS.length} languages: ` + LANGS.join(' '));
  // the block must fit the page, whatever it says, however wide the words
  const fits = page => page.evaluate(() => {
    const s = document.getElementById('stt'), r = s.getBoundingClientRect(), bad = [];
    const vw = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > vw + 1) bad.push('the page scrolls sideways: ' + document.documentElement.scrollWidth + ' > ' + vw);
    if (s.scrollWidth > s.clientWidth + 1) bad.push('the block overflows itself: ' + s.scrollWidth + ' > ' + s.clientWidth);
    // a0.4.3: while it works, the block's window ("Transcribe & review") is a modal one that takes the screen, not the
    // block's place on the page: it is held to the screen, and what is in it to the window, below
    for (const e of s.querySelectorAll('*')) {
      if (!e.getClientRects().length || e.closest('[hidden]') || e.closest('#stt_workspace')) continue;
      const b = e.getBoundingClientRect();
      if (b.width && (b.left < r.left - 1 || b.right > r.right + 1)) bad.push((e.id || e.tagName) + ' sticks out: ' + Math.round(b.left) + '..' + Math.round(b.right) + ' of ' + Math.round(r.left) + '..' + Math.round(r.right));
    }
    const w = document.getElementById('stt_workspace');
    if (w && w.open) {
      const wr = w.getBoundingClientRect(), vh = document.documentElement.clientHeight;
      if (wr.left < -1 || wr.right > vw + 1 || wr.top < -1 || wr.bottom > vh + 1)
        bad.push('the window leaves the screen: ' + [wr.left, wr.top, wr.right, wr.bottom].map(Math.round) + ' of ' + vw + 'x' + vh);
      if (w.scrollWidth > w.clientWidth + 1) bad.push('the window overflows itself sideways: ' + w.scrollWidth + ' > ' + w.clientWidth);
      // its head is part of it, above its columns (the page's bare `header` rule once pinned it to the top of the screen)
      const head = w.querySelector('header'), cols = w.querySelector('.stt-workspace-columns');
      if (head && cols && (getComputedStyle(head).position === 'fixed' || head.getBoundingClientRect().bottom > cols.getBoundingClientRect().top + 1))
        bad.push('the window\'s head is not above its columns: ' + getComputedStyle(head).position + ' ' + Math.round(head.getBoundingClientRect().bottom) + ' > ' + Math.round(cols.getBoundingClientRect().top));
      for (const e of w.querySelectorAll('*')) {
        if (!e.getClientRects().length || e.closest('[hidden]')) continue;
        const b = e.getBoundingClientRect();
        if (b.width && (b.left < wr.left - 1 || b.right > wr.right + 1)) bad.push('in the window, ' + (e.id || e.tagName) + ' sticks out: ' + Math.round(b.left) + '..' + Math.round(b.right) + ' of ' + Math.round(wr.left) + '..' + Math.round(wr.right));
      }
    }
    return bad;
  });
  const contrast = page => page.evaluate(() => {
    const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
    const rgb = s => (s.match(/[\d.]+/g) || [0, 0, 0, 1]).map(Number);
    const bg = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c[3] === undefined || c[3] > 0.5) return c; } return [255, 255, 255]; };
    const out = {};
    for (const sel of ['#stt .stt-title b', '#stt_intro', '#stt_now', '#stt_lang', '#stt_how', '#stt label', '#stt_go']) {
      const el = document.querySelector(sel);
      if (!el || el.closest('[hidden]') || !el.getClientRects().length) continue;
      const a = lum(rgb(getComputedStyle(el).color)), b = lum(bg(el));
      out[sel] = Math.round((Math.max(a, b) + .05) / (Math.min(a, b) + .05) * 100) / 100;
    }
    return out;
  });
  const worst = {};
  const combos = [[1280, 'light', 'ltr'], [390, 'light', 'ltr'], [1280, 'dark', 'rtl'], [390, 'sepia', 'rtl'], [390, 'dark', 'ltr'], [1280, 'sepia', 'ltr']];
  for (const [width, theme, dir] of combos) {
    const {context, page} = await newPage({width, theme});
    await openAdd(page, {by: 'llm'});
    await blockReady(page);
    if (dir === 'rtl') await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    const label = `${width}px ${theme} ${dir}`;
    const trouble = [];
    for (const code of LANGS) {
      await page.selectOption('#lang', code);
      const said = await text(page, '#stt_lang');
      const L = await page.evaluate(c => { const o = document.querySelector('#lang option[value="' + c + '"]'); return o.textContent; }, code);
      const [name, native] = L.split(' — ');
      if (!said.includes(name) || !said.includes(native)) trouble.push(`${code}: "${said}" lacks ${L}`);
      if ((await phase(page)) !== 'idle') trouble.push(`${code}: the block is ${await phase(page)}`);
      trouble.push(...(await fits(page)).map(b => code + ': ' + b));
    }
    eq(trouble, [], `${label}: all ${LANGS.length} languages name themselves and fit`);
    for (const [k, v] of Object.entries(await contrast(page))) worst[k] = Math.min(worst[k] === undefined ? 99 : worst[k], v);
    await shot(page, `f-idle-${width}-${theme}-${dir}`);
    // and at work, with the video held in its frame of words
    await chooseFilm(page, {lang: 'ja', seconds: 4});
    await page.click('#stt_go');
    await until(async () => /Loading|Transcribing/.test(await say(page)), `${label}: at work`, 30000);
    await shot(page, `f-working-${width}-${theme}-${dir}`);
    eq(await fits(page), [], `${label}: the block at work fits`);
    assert(await shown(page, '#stt_bar') && await shown(page, '#stt_cancel'), `${label}: a bar and Cancel`);
    await page.click('#stt_cancel');
    await inPhase(page, 'idle', `${label}: cancelled`);
    await context.close();
  }
  console.log('  contrast, the worst of every state:', JSON.stringify(worst));
  for (const [k, v] of Object.entries(worst)) assert(v >= 4.5 || k === '#stt_go', `${k} reads at ${v}:1 in the worst theme (4.5 wanted)`);
});

/* ==== END OF SECTIONS ==== */
assert(errors.length === 0, 'no page error and no failed request: ' + JSON.stringify(errors));
// the worker's own traceback goes to the hub's log (never to a page), and the only ones
// here are the card that was MADE to fail (section d)
const tracebacks = log.join('').split('Traceback (most recent call last)').slice(1);
assert(tracebacks.every(t => /RuntimeError: boom/.test(t)), `no traceback in the hub's log but the card made to fail (${tracebacks.length})`);
console.log(`\nadd_stt: ${passed} checks passed`);
} catch (e) {
  console.log(e.stack || e);
  console.log('section:', current, ' page errors:', JSON.stringify(errors));
  console.log('hub log tail:\n' + log.join('').slice(-3000));
  Deno.exitCode = 1;
} finally {
  await browser.close();
  try { hub.kill('SIGTERM'); await hub.status; } catch (_) {}
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
