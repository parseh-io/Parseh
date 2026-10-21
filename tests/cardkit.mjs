// SPDX-License-Identifier: GPL-3.0-or-later
import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/cardkit.mjs
//      CARDKIT_SHOTS=<dir> also saves the cut editor at desktop and phone width
//
// The card kit (lib/cardkit.js, lib/cardkit.css) against the REAL hub:
// serve.main() on a temporary toolbox (tests/cardkit_harness.py) holding a
// narrated book and a film whose sound is a pattern of tones, so where a clip
// starts and ends can be measured in the file the tray keeps.  The book's own
// reader page and the video's own player page are opened, and the kit is put
// on them as the pages will link it.
//
//  a) THE CUT EDITOR over the reader: really on screen, the page's narration
//     paused; the guess in the inputs; −.1 moves the start by exactly 0.1 and
//     plays the first 1.5 s, stopping where it should; an edge dragged on
//     the strip; ◉ stamps the playhead; an edge held past the end of the
//     strip stops there and the strip does not run away, and undo brings the
//     strip back with the guess; arrow keys; Tab stays inside; Escape
//     resolves null.  ▶ plays the clip and is ‖ while it does; pressed during
//     a nudge's preview it plays the whole clip; ‖ stops it.  The waveform
//     is drawn where the tones are.  Edges a few pixels apart, whose hit
//     areas overlap: each knob takes its own edge, and on top of one another
//     the way the pointer goes decides.
//  b) SAVE CLIP cuts on the server: a file in the tray whose length is the
//     clip's and whose tones start where they should; the focus stays where
//     it was, every stop of Tab hears keys, the saved clip plays from its
//     button; Enter uses it; a clip cut again replaces the first, and a
//     cancelled one leaves the tray.
//  c) A FILM, from the player page: the film paused, cut, used.
//  d) A MACHINE WITHOUT FFMPEG (a second hub): no waveform, and the clip is
//     recorded in the browser and uploaded as a WAV of the right length; a
//     recording interrupted while it plays is played again, not cut; and on
//     a throttled connection that loads slower than it plays, the clip is
//     still the right one.  A clip recorded here and one cut from a tab's
//     recording both fade 8 ms at each end, as the server's cut does.
//  e) guess(), markdown() read by the real parser and renderer, the decks,
//     preview() (the studio's own script flips the card; without it, the
//     kit's own few lines do, and a click on a footnote does not), copy,
//     uploadFrame, status, canRecord; and the editor at 400 px wide, where a
//     finger on two edges on one another takes the one it moves towards, and
//     an edge's input shows the whole of its value.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('CARDKIT_SHOTS') || '';
const TMP = await Deno.makeTempDir({prefix: 'parseh-cardkit-'});
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const near = (a, b, tol) => Math.abs(a - b) <= tol;
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
async function duration(path) {
  const r = await run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]);
  if (r.code) throw Error('ffprobe: ' + r.err);
  return parseFloat(r.out);
}
// Where the tones of a clip start and stop, in seconds from its first sample:
// decoded by ffmpeg, a sample louder than 0.3 is inside a tone, and a tone
// ends at the last loud sample before 50 ms of quiet.
async function tones(path) {
  const o = await new Deno.Command('ffmpeg', {args: ['-v', 'error', '-i', path, '-ac', '1', '-ar', '8000',
                                                      '-f', 's16le', '-'], stdout: 'piped', stderr: 'piped'}).output();
  if (!o.success) throw Error('ffmpeg: ' + td.decode(o.stderr));
  const pcm = new Int16Array(o.stdout.buffer, o.stdout.byteOffset, o.stdout.byteLength >> 1);
  const loud = 0.3 * 32767, runs = [];
  let start = -1, last = -1;
  for (let i = 0; i < pcm.length; i++) {
    if (Math.abs(pcm[i]) < loud) continue;
    if (start < 0 || i - last > 400) {
      if (start >= 0) runs.push([start / 8000, (last + 1) / 8000]);
      start = i;
    }
    last = i;
  }
  if (start >= 0) runs.push([start / 8000, (last + 1) / 8000]);
  return runs;
}
// the book's clip [1.8, 3.3] as the pattern has it: tones at [0.2, 0.8] and
// [1.2, 1.5], each start and end within `tol`
const bookTones = (t, tol) => t.length === 2 && near(t[0][0], 0.2, tol) && near(t[0][1], 0.8, tol)
  && near(t[1][0], 1.2, tol) && near(t[1][1], 1.5, tol);
const shown = t => JSON.stringify(t.map(r => r.map(x => +x.toFixed(3))));
// How long a WAV clip cut inside a steady tone fades in and out, in ms: a
// linear fade over n samples takes 2n/3 samples' worth of the tone's energy,
// so n is 1.5 times what the first (last) 25 ms lack against the middle.
async function fadeMs(path) {
  const buf = await Deno.readFile(path), dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let off = 12, rate = 0, x = null;
  while (off + 8 <= buf.length) {
    const id = td.decode(buf.subarray(off, off + 4)), size = dv.getUint32(off + 4, true);
    if (id === 'fmt ') rate = dv.getUint32(off + 12, true);
    if (id === 'data') { x = new Int16Array(buf.slice(off + 8, off + 8 + size).buffer); break; }
    off += 8 + size + (size & 1);
  }
  if (!x || !rate) throw Error('FAIL: not a WAV: ' + path);
  const at = ms => Math.round(ms * rate / 1000), energy = (a, b) => { let e = 0; for (let i = a; i < b; i++) e += (x[i] / 32768) ** 2; return e; };
  // THE TONE'S OWN ENERGY comes from the whole of the clip's middle and is its median, not one stretch of it: 25 ms is
  // eleven periods of 440 Hz, so a steady tone has the same energy in every bin of 25 ms, and the median is the tone's
  // even when a bin or two is not.  A computer too busy for a few milliseconds loses a few milliseconds of what it is
  // recording (a clip of the tab came with level 0.75 and fades of 3.8 ms: the stretch the level was read from had lost
  // 6% of its energy, and the ends looked the fuller for it).  The bins are in the answer, to be read when it fails.
  const n = at(25), bins = [];
  for (let a = n; a + n <= x.length - n; a += n) bins.push(energy(a, a + n) / n);
  const mean = [...bins].sort((p, q) => p - q)[bins.length >> 1];
  const fade = e => +(1.5 * (n * mean - e) / mean / rate * 1000).toFixed(2);
  return {head: fade(energy(0, n)), tail: fade(energy(x.length - n, x.length)), level: +Math.sqrt(2 * mean).toFixed(2),
          bins: bins.map(b => +(b / mean).toFixed(2)).join(' ')};
}
async function trayAudio(dir) {
  const out = [];
  try {
    for await (const e of Deno.readDir(dir))
      if (e.isFile && !e.name.startsWith('.') && !e.name.endsWith('.json') && !/\.(png|jpe?g)$/.test(e.name))
        out.push(e.name);
  } catch (_) {}
  return out.sort();
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
async function hub(extra) {
  const port = freePort(), log = [];
  const proc = new Deno.Command(PY, {args: ['tests/cardkit_harness.py', 'serve', TMP, String(port), ...extra],
                                     cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  drain(proc.stdout, log); drain(proc.stderr, log);
  const base = `http://127.0.0.1:${port}`;
  const until = Date.now() + 60000;
  for (;;) {
    try { const r = await fetch(base + '/clips/api/status'); await r.body?.cancel(); if (r.ok) break; } catch (_) {}
    if (Date.now() > until) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(250);
  }
  return {proc, base, log};
}
function watch(page, errors) {
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('response', r => {
    // the kit's own requests must all be answered (409 is how a machine with
    // no ffmpeg answers a cut); the reader asks for a few optional files of
    // its own that a temporary book does not have, and the deck refusals
    // below are asked for on purpose
    const u = new URL(r.url());
    if (r.status() >= 400 && r.status() !== 409
        && /\/(clips\/|__clip\/|youtube\/api\/|lib\/cardkit|studio\/static\/)/.test(u.pathname))
      errors.push(r.status() + ' ' + u.pathname);
  });
}

async function inject(page, base) {
  await page.addStyleTag({url: base + '/lib/cardkit.css'});
  await page.addScriptTag({url: base + '/lib/cardkit.js'});
  assert(await page.evaluate(() => typeof ParsehCards === 'object' && typeof ParsehCards.cut === 'function'),
         'the kit is on the page: window.ParsehCards');
}
async function openCut(page, which, over = {}) {
  await page.evaluate(([which, over]) => {
    let o;
    if (which === 'book') {
      const ctx = [SUBS[0][0], SUBS[0][1]];
      o = {source: {kind: 'book', src: NARR[0].src, cutUrl: '__clip/cut', peaksUrl: '__clip/peaks', narration: NARR[0].id},
           context: ctx, guess: ParsehCards.guess(ctx, 35, 9, 22), lang: 'en', hint: 'wound',
           label: '1.1', text: 'wound the clock'};
    } else {
      const c = window.YTFRANK;
      o = {source: {kind: 'film', src: c.media, cutUrl: '/youtube/api/clip', peaksUrl: '/youtube/api/peaks', video: c.id},
           context: [2, 4.6], guess: [1.9, 2.7], lang: 'en', hint: 'market', label: '0:02',
           text: 'The market opens early.'};
    }
    Object.assign(o.source, over.source || {});
    for (const k of Object.keys(over)) if (k !== 'source') o[k] = over[k];
    window.__done = false; window.__res = undefined; window.__opts = o;
    ParsehCards.cut(o).then(r => { window.__res = r; window.__done = true; });
  }, [which, over]);
  await page.waitForSelector('.pc-root .pc-cut');
}
const vals = page => page.evaluate(() => ({
  s: document.querySelector('.pc-cut .e0').value, e: document.querySelector('.pc-cut .e1').value,
  dur: document.querySelector('.pc-cut .dur').textContent}));
// An edge's input with a video's times in it, a long one's too: an input
// whose text does not fit scrolls, wider than it is (spin buttons and all).
// [value, scrollWidth, clientWidth], the editor's own value put back.
const wholeValues = page => page.evaluate(() => ['17.62', '1234.56'].map(x => {
  const inp = document.querySelector('.pc-cut .e0'), was = inp.value;
  inp.value = x;
  const r = [x, inp.scrollWidth, inp.clientWidth];
  inp.value = was;
  return r;
}));
async function typeTimes(page, s, e) {
  await page.fill('.pc-cut .e0', s); await page.press('.pc-cut .e0', 'Enter');
  await page.fill('.pc-cut .e1', e); await page.press('.pc-cut .e1', 'Enter');
  const v = await vals(page);
  if (v.s !== (+s).toFixed(2) || v.e !== (+e).toFixed(2)) throw Error(`FAIL: typed ${s}–${e}, the editor holds ${v.s}–${v.e}`);
}
// where the two edges' lines are, and their hit areas' top and bottom
const edges = page => page.evaluate(() => {
  const mid = n => { const b = n.getBoundingClientRect(); return b.left + b.width / 2; };
  const a = document.querySelector('.pc-edge0'), b = document.querySelector('.pc-edge1'), r = a.getBoundingClientRect();
  const st = document.querySelector('.pc-strip'), sp = document.querySelectorAll('.pc-scale span');
  return {x0: mid(a), x1: mid(b), top: r.top, bottom: r.bottom, mid: r.top + r.height / 2,
          pps: st.clientWidth / (parseFloat(sp[sp.length - 1].textContent) - parseFloat(sp[0].textContent)),
          onStartKnob: document.elementFromPoint(mid(a), r.top + 7).className};
});
async function drag(page, x, y, dx) {
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx / 2, y, {steps: 4});
  await page.mouse.move(x + dx, y, {steps: 4});
  await page.mouse.up();
  return vals(page);
}
// every text the editor's status line shows, from now on
const sayings = page => page.evaluate(() => {
  const st = document.querySelector('.pc-stat');
  window.__said = [];
  new MutationObserver(() => window.__said.push(st.textContent))
    .observe(st, {childList: true, characterData: true, subtree: true});
});
// every play and pause of the editor's own element, with its clock
const listen = page => page.evaluate(() => {
  const a = document.querySelector('.pc-root .pc-play');
  window.__plays = [];
  a.addEventListener('playing', () => window.__plays.push(['playing', a.currentTime]));
  a.addEventListener('pause', () => window.__plays.push(['pause', a.currentTime]));
});
async function heard(page, what) {
  await page.waitForFunction(() => window.__plays.some(x => x[0] === 'pause') &&
                                   window.__plays.some(x => x[0] === 'playing'), null, {timeout: 30000})
    .catch(() => { throw Error('FAIL: no preview was played and stopped: ' + what); });
  const p = await page.evaluate(() => window.__plays.slice());
  await page.evaluate(() => { window.__plays = []; });
  return {from: p.find(x => x[0] === 'playing')[1], to: p.filter(x => x[0] === 'pause').pop()[1]};
}
// how late each preview stopped: a timeupdate comes a quarter of a second
// apart, and the editor stops on a frame or a timer instead
const late = [];
async function onScreen(page, sel, what) {
  const r = await page.evaluate(sel => {
    const b = document.querySelector(sel), rc = b.getBoundingClientRect();
    const hit = document.elementFromPoint(rc.left + rc.width / 2, rc.top + rc.height / 2);
    return {l: rc.left, t: rc.top, r: rc.right, b: rc.bottom, w: innerWidth, h: innerHeight,
            hit: !!hit && (b === hit || b.contains(hit)), vis: getComputedStyle(b).visibility,
            disp: getComputedStyle(b).display};
  }, sel);
  assert(r.l >= 0 && r.t >= 0 && r.r <= r.w && r.b <= r.h && r.r - r.l > 10 && r.b - r.t > 10
         && r.hit && r.vis === 'visible' && r.disp !== 'none',
         `${what} is on screen and on top (${Math.round(r.l)},${Math.round(r.t)}–${Math.round(r.r)},${Math.round(r.b)} in ${r.w}x${r.h})`);
}
async function stripGeom(page) {
  return page.evaluate(() => {
    const s = document.querySelector('.pc-strip'), rc = s.getBoundingClientRect();
    const spans = document.querySelectorAll('.pc-scale span');
    return {left: rc.left + s.clientLeft, width: s.clientWidth, top: rc.top, height: rc.height,
            v0: parseFloat(spans[0].textContent), v1: parseFloat(spans[spans.length - 1].textContent)};
  });
}
async function waveform(page, loudAt, quietAt, what) {
  await page.waitForFunction(() => document.querySelector('.pc-strip').classList.contains('pc-drawn'),
                             null, {timeout: 10000});
  const px = await page.evaluate(([a, b]) => {
    const c = document.querySelector('.pc-wave'), g = c.getContext('2d');
    const sp = document.querySelectorAll('.pc-scale span');
    const v0 = parseFloat(sp[0].textContent), v1 = parseFloat(sp[sp.length - 1].textContent);
    const y = Math.round(c.height / 2 - 20 * devicePixelRatio);
    const alpha = t => g.getImageData(Math.round((t - v0) / (v1 - v0) * c.width), y, 1, 1).data[3];
    return [alpha(a), alpha(b)];
  }, [loudAt, quietAt]);
  assert(px[0] > 0 && px[1] === 0, `${what}: the waveform is drawn at the tone (${loudAt} s) and not in the silence (${quietAt} s)`);
}

const errors = [];
let hubA = null, hubB = null, browser = null, browserB = null;
try {
  /* ---------------- the toolbox ---------------- */
  const info = JSON.parse(await py(`
import subprocess, sys
r = subprocess.run([sys.executable, 'tests/cardkit_harness.py', 'build', sys.argv[1]], capture_output=True, text=True)
if r.returncode: raise SystemExit(r.stderr or r.stdout)
print(r.stdout.strip().splitlines()[-1])
`, TMP));
  const TRAY = TMP + '/tray', TRAYB = TMP + '/tray-noff';
  hubA = await hub([]);
  const A = hubA.base;
  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});

  /* ---------------- a) the cut editor over the reader ---------------- */
  console.log('a) the cut editor over the book reader');
  const page = await browser.newPage({viewport: {width: 1280, height: 800}});
  watch(page, errors);
  await page.goto(A + info.reader);
  await page.waitForFunction(() => typeof SUBS !== 'undefined' && typeof NARR !== 'undefined');
  await inject(page, A);
  // the reader's own narration is playing when the editor opens
  await page.click('#play');
  await page.waitForFunction(() => !document.getElementById('audio').paused, null, {timeout: 30000});
  await openCut(page, 'book');
  await onScreen(page, '.pc-cut', 'the cut editor');
  assert(await page.evaluate(() => getComputedStyle(document.querySelector('.pc-root')).position === 'fixed'),
         'the editor is fixed over the page');
  assert(await page.evaluate(() => document.getElementById('audio').paused), "the reader's narration is paused while it is open");
  await onScreen(page, '.pc-cut [data-e="s-"]', 'the −.1 button of the start row');
  await onScreen(page, '.pc-cut .e1', 'the end input');
  const g = await page.evaluate(() => window.__opts.guess);
  let v = await vals(page);
  assert(v.s === g[0].toFixed(2) && v.e === g[1].toFixed(2) && v.dur === (+g[1].toFixed(2) - +g[0].toFixed(2)).toFixed(2) + 's',
         `the inputs show the guess: ${v.s} – ${v.e}, ${v.dur}`);
  assert(await page.evaluate(() => ['.pc-take', '.pc-again'].every(s => document.querySelector('.pc-cut ' + s).getClientRects().length === 0)),
         'a recording that is a file has no record step and no "record again"');
  const whole = await wholeValues(page);
  assert(whole.every(([, sw, cw]) => sw <= cw), `an edge's input shows the whole of 17.62 and of 1234.56: ${JSON.stringify(whole)}`);
  await waveform(page, 2.3, 1.8, 'with ffmpeg');
  await page.waitForFunction(() => document.querySelector('.pc-root .pc-play').readyState >= 1);

  await listen(page);
  await page.click('.pc-cut [data-e="s-"]');
  v = await vals(page);
  const s1 = +(+g[0].toFixed(2) - 0.1).toFixed(2), e1 = +g[1].toFixed(2);
  assert(v.s === s1.toFixed(2) && v.e === e1.toFixed(2), `−.1 moves the start by exactly 0.1: ${v.s}`);
  let h = await heard(page, '−.1');
  const stop1 = Math.min(e1, s1 + 1.5);
  assert(near(h.from, s1, 0.12), `…and plays from the start (${h.from.toFixed(3)} for ${s1})`);
  assert(h.to >= stop1 - 0.02 && h.to <= stop1 + 0.06, `…and stops at ${stop1.toFixed(2)}, the end of the first 1.5 s or of the clip (${h.to.toFixed(3)})`);
  late.push(h.to - stop1);

  // the end edge dragged 60 px to the right
  let geo = await stripGeom(page);
  const eb = await page.locator('.pc-edge1').boundingBox();
  const ex = eb.x + eb.width / 2, ey = eb.y + eb.height / 2;
  await page.mouse.move(ex, ey);
  await page.mouse.down();
  await page.mouse.move(ex + 30, ey, {steps: 4});
  await page.mouse.move(ex + 60, ey, {steps: 4});
  await page.mouse.up();
  v = await vals(page);
  const want = e1 + 60 * (geo.v1 - geo.v0) / geo.width;
  assert(near(+v.e, want, 0.02), `dragging the end edge 60 px moves the end to ${v.e} (≈ ${want.toFixed(2)})`);
  h = await heard(page, 'the dragged edge');
  assert(near(h.to, +v.e, 0.06) && near(h.from, Math.max(s1, +v.e - 1.5), 0.12),
         `…and plays its last 1.5 s: ${h.from.toFixed(2)}–${h.to.toFixed(3)}`);
  late.push(h.to - +v.e);

  // a click on the strip moves the playhead; ◉ stamps the start with it
  geo = await stripGeom(page);
  const cx = geo.left + (2.2 - geo.v0) / (geo.v1 - geo.v0) * geo.width;
  await page.mouse.click(cx, geo.top + geo.height / 2);
  const at = await page.evaluate(() => document.querySelector('.pc-root .pc-play').currentTime);
  assert(near(at, 2.2, 0.02), `a click on the strip moves the playhead (${at.toFixed(3)})`);
  await page.click('.pc-cut [data-e="sh"]');
  v = await vals(page);
  assert(v.s === (Math.round(at * 100) / 100).toFixed(2), `◉ sets the start to the playhead: ${v.s}`);
  h = await heard(page, '◉');
  const stop3 = Math.min(+v.e, +v.s + 1.5);
  assert(near(h.from, +v.s, 0.12) && near(h.to, stop3, 0.06), `…and plays from there to ${stop3.toFixed(2)} (${h.from.toFixed(2)}–${h.to.toFixed(3)})`);
  late.push(h.to - stop3);
  assert(Math.max(...late) <= 0.025 && Math.min(...late) >= -0.02,
         `every preview stopped within 25 ms of its end (${late.map(x => (x * 1000).toFixed(0) + ' ms').join(', ')})`);

  // the end edge taken past the end of the strip and held there, trembling:
  // it stops at the strip's end, and the strip holds still under the pointer
  const strip0 = await stripGeom(page);
  let ed = await edges(page);
  await page.mouse.move(ed.x1, ed.mid);
  await page.mouse.down();
  await page.mouse.move(strip0.left + strip0.width + 20, ed.mid, {steps: 30});
  for (let i = 0; i < 10; i++) await page.mouse.move(strip0.left + strip0.width + 20 + (i % 2), ed.mid);
  v = await vals(page);
  let held = await stripGeom(page);
  assert(+v.e === strip0.v1 && held.v0 === strip0.v0 && held.v1 === strip0.v1,
         `an end held past the strip stops at its end and the strip holds still: ${v.e} on ${held.v0}–${held.v1} (was ${strip0.v0}–${strip0.v1})`);
  await page.mouse.up();
  held = await stripGeom(page);
  assert(held.v0 === strip0.v0 && near(held.v1, +v.e + 1, 0.001),
         `let go, the strip reaches a second past the edge: ${held.v0}–${held.v1}`);
  await page.click('.pc-cut [data-e="rv"]');
  v = await vals(page);
  held = await stripGeom(page);
  assert(v.s === g[0].toFixed(2) && v.e === g[1].toFixed(2) && held.v0 === strip0.v0 && held.v1 === strip0.v1,
         `undo goes back to the guess, and the strip to the sentence: ${v.s} – ${v.e} on ${held.v0}–${held.v1}`);

  // keys: the focused edge moves; the reader underneath hears nothing
  await page.focus('.pc-edge1');
  await page.keyboard.press('ArrowRight');
  v = await vals(page);
  assert(v.e === (+g[1].toFixed(2) + 0.1).toFixed(2), `ArrowRight on the end edge: +0.1 → ${v.e}`);
  await page.keyboard.press('Shift+ArrowLeft');
  v = await vals(page);
  assert(v.e === (+g[1].toFixed(2) + 0.1 - 0.5).toFixed(2), `Shift+ArrowLeft: −0.5 → ${v.e}`);
  await page.focus('.pc-cut .e0');
  await page.keyboard.press('ArrowUp');
  v = await vals(page);
  assert(v.s === (+g[0].toFixed(2) + 0.1).toFixed(2), `ArrowUp in the start input: +0.1 → ${v.s}`);
  await page.waitForFunction(() => document.querySelector('.pc-root .pc-play').paused, null, {timeout: 30000});
  await page.focus('.pc-edge1');
  await page.keyboard.press(' ');
  await sleep(300);
  assert(await page.evaluate(() => document.getElementById('audio').paused &&
                                    !document.querySelector('.pc-root .pc-play').paused),
         'Space plays the editor\'s recording from the playhead, not the reader\'s');
  await page.keyboard.press(' ');
  let inside = true;
  for (let i = 0; i < 24; i++) {
    await page.keyboard.press(i % 5 === 4 ? 'Shift+Tab' : 'Tab');
    inside = inside && await page.evaluate(() => !!document.activeElement.closest('.pc-cut'));
  }
  assert(inside, 'Tab and Shift+Tab never leave the editor');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => window.__done, null, {timeout: 5000});
  assert(await page.evaluate(() => window.__res === null && !document.querySelector('.pc-root')),
         'Escape resolves null and takes the editor away');

  // ▶ plays the clip from its start and is ‖ while it does (the readout
  // beside it holding still); pressed while a nudge's preview plays it plays
  // the whole clip, not stops the preview; ‖ stops it
  await openCut(page, 'book');
  await page.waitForFunction(() => document.querySelector('.pc-root .pc-play').readyState >= 1);
  await typeTimes(page, '1.00', '3.40');
  await page.waitForFunction(() => document.querySelector('.pc-root .pc-play').paused, null, {timeout: 30000});
  await sleep(150);
  const playState = () => page.evaluate(() => {
    const a = document.querySelector('.pc-root .pc-play'), b = document.querySelector('.pc-cut [data-e="p"]');
    return {paused: a.paused, t: a.currentTime, label: b.textContent, title: b.title, aria: b.getAttribute('aria-label'),
            w: b.getBoundingClientRect().width, dur: document.querySelector('.pc-cut .dur').getBoundingClientRect().left};
  });
  let ps = await playState();
  assert(ps.label === '▶' && ps.title === 'play the clip' && ps.aria === 'Play the clip', `▶ at rest: ${ps.label} “${ps.title}”`);
  const restW = ps.w, restDur = ps.dur;
  await listen(page);
  await page.click('.pc-cut [data-e="p"]');
  ps = await playState();
  assert(!ps.paused && ps.label === '‖' && ps.title === 'stop the clip' && ps.aria === 'Stop the clip'
         && near(ps.w, restW, 0.5) && near(ps.dur, restDur, 0.5),
         `▶ plays the clip and shows ‖ “${ps.title}”, as wide as ▶ (${ps.w.toFixed(1)} / ${restW.toFixed(1)} px)`);
  h = await heard(page, '▶');
  ps = await playState();
  assert(near(h.from, 1, 0.12) && near(h.to, 3.4, 0.06) && ps.paused && ps.label === '▶',
         `…from 1.00 to 3.40 (${h.from.toFixed(2)}–${h.to.toFixed(3)}), and is ▶ again when it ends (${ps.label})`);
  await page.click('.pc-cut [data-e="e-"]');
  await sleep(150);
  ps = await playState();
  assert(!ps.paused && ps.t >= 1.75 && ps.label === '▶',
         `−.1 on the end plays its last 1.5 s, and ▶ stays ▶ (at ${ps.t.toFixed(2)}, ${ps.label})`);
  await page.evaluate(() => { window.__plays = []; });
  await page.click('.pc-cut [data-e="p"]');
  await sleep(120);
  ps = await playState();
  assert(!ps.paused && ps.t < 1.5 && ps.label === '‖',
         `▶ pressed 150 ms into that preview plays the clip from its start (at ${ps.t.toFixed(2)}, ${ps.paused ? 'paused' : 'playing'}, ${ps.label})`);
  await page.waitForFunction(() => document.querySelector('.pc-root .pc-play').paused, null, {timeout: 30000});
  const pauses = await page.evaluate(() => window.__plays.filter(x => x[0] === 'pause').map(x => x[1]));
  // (a stop BEFORE the end is what this says it does not have: the pause at the end may be reported twice a few
  // milliseconds apart -- 3.304 and 3.309 on a computer with a hundred things to do -- and is still one stop at the end)
  assert(pauses.length >= 1 && pauses.every(t => near(t, 3.3, 0.06)),
         `…through to its end, 3.30, without a stop on the way (stopped at ${pauses.map(x => x.toFixed(3))})`);
  await page.click('.pc-cut [data-e="p"]');
  await sleep(300);
  await page.click('.pc-cut [data-e="p"]');
  ps = await playState();
  assert(ps.paused && ps.t > 1.1 && ps.t < 3.2 && ps.label === '▶' && ps.title === 'play the clip',
         `‖ stops the clip where it is (${ps.t.toFixed(2)}) and is ▶ again`);
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => window.__done, null, {timeout: 5000});

  // Edges a few pixels apart: their hit areas overlap, the end's on top.
  // The start's knob still takes the start, the end's knob the end, a press
  // elsewhere the nearer line; a press beside a line does not make the edge
  // jump to the pointer.
  await openCut(page, 'book');
  await typeTimes(page, '2.00', '2.08');
  ed = await edges(page);
  assert(ed.x1 - ed.x0 < 24 && /pc-edge1/.test(ed.onStartKnob),
         `(the two hit areas overlap: lines ${(ed.x1 - ed.x0).toFixed(1)} px apart, the end's area over the start's knob)`);
  v = await drag(page, ed.x0 + 4, ed.top + 7, -40);
  assert(v.e === '2.08' && near(+v.s, 2 - 40 / ed.pps, 0.015),
         `the start's knob, grabbed 4 px beside the line, drags the start 40 px left: ${v.s} (≈ ${(2 - 40 / ed.pps).toFixed(2)}) – ${v.e}`);
  await typeTimes(page, '2.00', '2.08');
  ed = await edges(page);
  v = await drag(page, ed.x1, ed.bottom - 7, 40);
  assert(v.s === '2.00' && near(+v.e, 2.08 + 40 / ed.pps, 0.015), `the end's knob drags the end: ${v.s} – ${v.e}`);
  await typeTimes(page, '2.00', '2.08');
  ed = await edges(page);
  v = await drag(page, ed.x0 - 1, ed.mid, -30);
  assert(v.e === '2.08' && +v.s < 1.85, `a press on the start's line, below its knob, takes the start: ${v.s} – ${v.e}`);
  // on one another: the way the pointer goes
  await typeTimes(page, '2.00', '2.02');
  ed = await edges(page);
  assert(ed.x1 - ed.x0 < 4, `(the lines ${(ed.x1 - ed.x0).toFixed(1)} px apart)`);
  v = await drag(page, (ed.x0 + ed.x1) / 2, ed.mid, 30);
  assert(v.s === '2.00' && +v.e > 2.2, `on one another, a drag to the right takes the end: ${v.s} – ${v.e}`);
  await typeTimes(page, '2.00', '2.02');
  ed = await edges(page);
  v = await drag(page, (ed.x0 + ed.x1) / 2, ed.mid, -30);
  assert(v.e === '2.02' && +v.s < 1.8, `…and one to the left the start: ${v.s} – ${v.e}`);
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => window.__done, null, {timeout: 5000});
  assert((await trayAudio(TRAY)).length === 0, 'nothing was cut into the tray');

  /* ---------------- b) save, Enter, cut again, cancel ---------------- */
  console.log('b) save clip');
  await openCut(page, 'book');
  await page.fill('.pc-cut .e0', '1.8');
  await page.press('.pc-cut .e0', 'Enter');
  await page.fill('.pc-cut .e1', '3.3');
  await page.press('.pc-cut .e1', 'Enter');
  v = await vals(page);
  assert(v.s === '1.80' && v.e === '3.30' && v.dur === '1.50s', `typed values are the clip: ${v.s} – ${v.e}, ${v.dur}`);
  await page.click('.pc-cut .pc-save');
  await page.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 15000});
  let tray = await trayAudio(TRAY);
  assert(tray.length === 1 && /^wound-[0-9a-f]{6}\.mp3$/.test(tray[0]), `save clip puts one recording in the tray: ${tray}`);
  const d1 = await duration(`${TRAY}/${tray[0]}`);
  assert(near(d1, 1.5, 0.06), `its length is the clip's, 1.50 s (ffprobe ${d1.toFixed(3)})`);
  let t = await tones(`${TRAY}/${tray[0]}`);
  assert(t.length === 2 && near(t[0][0], 0.2, 0.04) && near(t[0][1], 0.8, 0.04) && near(t[1][0], 1.2, 0.04),
         `its tones are where the recording has them: ${JSON.stringify(t.map(r => r.map(x => +x.toFixed(3))))} (want [0.2,0.8],[1.2,1.5])`);
  assert((await page.textContent('.pc-name')).startsWith(tray[0]), 'the editor names the saved clip');
  await page.waitForFunction(() => document.querySelector('.pc-saved-audio').readyState >= 1, null, {timeout: 30000});
  assert(await page.evaluate(n => document.querySelector('.pc-saved-audio').src.endsWith('/clips/media/' + n), tray[0]),
         'the saved clip loads in the editor from the tray');
  // the keyboard keeps its place through the save
  let focus = await page.evaluate(() => document.activeElement.tagName + '.' + document.activeElement.className);
  assert(/pc-save/.test(focus), `after saving, the focus is still on save clip (${focus})`);
  await page.keyboard.press('Tab');
  assert(await page.evaluate(() => document.activeElement.classList.contains('pc-use')), '…and Tab goes on to use this clip');
  // every place Tab stops at in the editor hears a key pressed there, so
  // Escape and Enter work from each (a media element's own controls keep
  // keys to themselves)
  await page.evaluate(() => { window.__keys = 0; window.addEventListener('keydown', () => window.__keys++, true); });
  const deaf = [], stops = new Set();
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press('Tab');
    const where = await page.evaluate(() => { const a = document.activeElement; return a.tagName + '.' + a.className + (a.dataset.e || ''); });
    stops.add(where);
    const k0 = await page.evaluate(() => window.__keys);
    await page.keyboard.press('Shift');
    if (await page.evaluate(() => window.__keys) === k0) deaf.push(where);
  }
  assert(deaf.length === 0 && stops.has('BUTTON.pc-hear') && ![...stops].some(x => /^(AUDIO|VIDEO)/.test(x)),
         `every one of the ${stops.size} stops of Tab hears keys, the saved clip's ▶ among them${deaf.length ? ': not ' + deaf.join(', ') : ''}`);
  // the saved clip plays from its own button
  await page.waitForFunction(() => document.querySelector('.pc-saved-audio').paused, null, {timeout: 30000});
  await page.click('.pc-cut .pc-hear');
  await page.waitForFunction(() => !document.querySelector('.pc-saved-audio').paused && document.querySelector('.pc-saved-audio').currentTime > 0.2,
                             null, {timeout: 30000});
  assert(await page.textContent('.pc-cut .pc-hear') === '‖' &&
         await page.evaluate(() => parseFloat(document.querySelector('.pc-saved .pc-fill').style.width) > 0),
         'its ▶ plays the saved clip, shows ‖ and how far it has played');
  await page.click('.pc-cut .pc-hear');
  assert(await page.evaluate(() => document.querySelector('.pc-saved-audio').paused) && await page.textContent('.pc-cut .pc-hear') === '▶',
         '…and ‖ pauses it');
  await page.focus('.pc-cut');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => window.__done, null, {timeout: 5000});
  let res = await page.evaluate(() => window.__res);
  assert(res && res.name === tray[0] && res.path === 'audio/' + tray[0] && res.url === '/clips/media/' + tray[0]
         && res.source.narration === 'n1' && res.lang === 'en', `Enter uses the clip: resolves with its record (${res && res.path})`);
  assert(!(await page.$('.pc-root')) && (await trayAudio(TRAY)).length === 1, 'the editor closes; the tray keeps the clip');

  // saved, the end moved, used: the clip is cut again and the first one goes
  await openCut(page, 'book');
  await page.fill('.pc-cut .e0', '1.8'); await page.press('.pc-cut .e0', 'Enter');
  await page.fill('.pc-cut .e1', '3.3'); await page.press('.pc-cut .e1', 'Enter');
  await page.click('.pc-cut .pc-save');
  await page.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 15000});
  const firstCut = (await trayAudio(TRAY)).filter(n => n !== res.name);
  assert(firstCut.length === 1, 'a second clip saved');
  await page.click('.pc-cut [data-e="e+"]');
  assert(await page.evaluate(() => document.querySelector('.pc-saved').classList.contains('pc-stale')),
         'moving an edge marks the saved clip as not this one');
  await page.click('.pc-cut .pc-use');
  await page.waitForFunction(() => window.__done, null, {timeout: 15000});
  const res2 = await page.evaluate(() => window.__res);
  await sleep(300);
  tray = await trayAudio(TRAY);
  assert(res2 && res2.name !== firstCut[0] && tray.includes(res2.name) && !tray.includes(firstCut[0]) && tray.length === 2,
         `use this clip cuts the moved clip again and the superseded one leaves the tray: ${tray}`);
  const d2 = await duration(`${TRAY}/${res2.name}`);
  assert(near(d2, 1.6, 0.06), `…and the clip used is 1.60 s long (${d2.toFixed(3)})`);
  // saved, then cancelled: the clip nobody wanted is not kept
  await openCut(page, 'book');
  await page.click('.pc-cut .pc-save');
  await page.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 15000});
  assert((await trayAudio(TRAY)).length === 3, 'saved: three in the tray');
  await page.click('.pc-cut .pc-cancel');
  await page.waitForFunction(() => window.__done, null, {timeout: 5000});
  await sleep(300);
  assert((await page.evaluate(() => window.__res)) === null && (await trayAudio(TRAY)).length === 2,
         'cancel resolves null and takes the clip it saved out of the tray');

  /* ---------------- e) the rest of the kit, on the same page ---------------- */
  console.log('e) guess, markdown, decks, preview and the small ones');
  const gs = await page.evaluate(() => [
    ParsehCards.guess([10, 20], 100, 25, 50),
    ParsehCards.guess([0.1, 1], 10, 0, 1),
    ParsehCards.guess([5, 5.1], 10, 5, 5, 0),
    ParsehCards.guess([5, 6], 10, 9, 10, 1),
    ParsehCards.guess([4, 6], 0, 0, 0),
  ]);
  const same = (a, b) => a.length === b.length && a.every((x, i) => near(x, b[i], 1e-9));
  assert(same(gs[0], [12.38, 15.12]), `guess: its share of the text, padded by 0.12 → ${gs[0]}`);
  assert(same(gs[1], [0, 0.31]), `guess: never before 0 → ${gs[1]}`);
  assert(same(gs[2], [5.05, 5.25]), `guess: at least 0.2 s long → ${gs[2]}`);
  assert(same(gs[3], [4.9, 6.3]), `guess: within 0.3 s of the sentence → ${gs[3]}`);
  assert(same(gs[4], [3.88, 6.12]), `guess: no units, the whole sentence padded → ${gs[4]}`);

  const clipName = res.name;
  const md = await page.evaluate(([clip, base]) => ({
    vocab: ParsehCards.markdown({fa: 'wound', kana: '', tr: 'waʊnd', en: 'turned (a key)',
      context: 'The old man\nwound the clock', notes: 'wind · wound · wound\nnot the noun wound',
      source: {label: 'The Clock and the Wind — 1.1', url: base + '/books/english/mini-en/reader/#p1'},
      dir: 'both', image: null, audio: {side: 'front', path: 'audio/' + clip}, latin: true}, 'vocab'),
    opposites: ParsehCards.markdown({fa: 'old', tr: 'oʊld', opp: 'young', opp_tr: 'jʌŋ', notes: '|',
      source: {label: 'no link here', url: '/books/english/mini-en/reader/'}, dir: 'reverse',
      audio: {side: 'back', path: 'audio/' + clip}, latin: true}, 'opposites'),
    jolly: ParsehCards.markdown({jolly: {
      'front-primary': '[wound]{tl}\n\n![the word](audio/' + clip + ')',
      'front-secondary': 'waʊnd',
      'back-primary': '| form | sound |\n|---|---|\n| wind | waɪnd |\n| wound | waʊnd |',
      'back-secondary': '- the past of *wind*\n- not the noun\n\n> a box on the card'}, latin: true}, 'jolly'),
    forward: ParsehCards.markdown({fa: 'clock', en: 'a thing that tells the time', dir: 'forward'}, 'vocab'),
    random: ParsehCards.markdown({fa: 'clock', en: 'a thing that tells the time', dir: 'both-random'}, 'vocab'),
    repeat: ParsehCards.markdown({fa: 'clock', en: 'a thing that tells the time', dir: 'both-repeat'}, 'vocab'),
    rtl: ParsehCards.markdown({fa: 'حرف بزنم.', en: 'to talk',
      context: 'امروز میخوام حرف بزنم.\nدر باره همه چیزهایی که دارم.'}, 'vocab'),
  }), [clipName, A]);
  assert(md.vocab.startsWith(':::exercise flashcard\ncard-type: vocab\ntarget: [wound]{tl}\n') && md.vocab.endsWith('\n:::\n')
         && md.vocab.includes('\ncontext: |\n  [The old man]{tl}\n  [wound the clock]{tl}\n')
         && md.vocab.includes(`\nsource: [The Clock and the Wind — 1.1](${A}/books/english/mini-en/reader/#p1)\n`)
         && md.vocab.includes(`\nfront-audio: audio/${clipName}\n`) && md.vocab.includes('\ndirection: both-repeat\n')
         && !md.vocab.includes('reading:') && !md.vocab.includes('bidirectional'),
         'markdown(vocab): a Latin target marked {tl}, a block for two lines, the source a link, the recording, both (repeat)');
  assert(md.opposites.includes('\nopposite: [young]{tl}\n') && md.opposites.includes('\nnotes: |\n  |\n')
         && md.opposites.includes('\nsource: no link here\n') && md.opposites.includes(`\nback-audio: audio/${clipName}\n`)
         && md.opposites.includes('\ndirection: reverse\n') && !md.opposites.includes('bidirectional'),
         'markdown(opposites): the opposite marked, a lone | as a block, a source with no web address as its label, reverse');
  assert(md.jolly.includes('\nfront-primary: |\n  [wound]{tl}\n\n  ![the word](audio/') && md.jolly.includes('\nfront-secondary: waʊnd\n')
         && md.jolly.includes('\nback-primary: |\n  | form | sound |\n  |---|---|\n'),
         'markdown(jolly): the four fields verbatim, a block where there are lines');
  assert(!md.forward.includes('direction') && !md.forward.includes('bidirectional'), 'markdown: forward writes no direction');
  assert(md.rtl.includes('target: [حرف بزنم.]{tl}') && md.rtl.includes('context: |\n  [امروز میخوام حرف بزنم.]{tl}\n  [در باره همه چیزهایی که دارم.]{tl}'),
         'markdown: Persian target and each wrapped context line are marked as the target language');
  assert(md.random.includes('\ndirection: both-random\n') && md.repeat.includes('\ndirection: both-repeat\n')
         && !md.random.includes('bidirectional') && !md.repeat.includes('bidirectional'),
         'markdown: both (random) and both (repeat) are written as their own values, and the sheet\'s old "both" is both (repeat)');
  const parsed = JSON.parse(await py(`
import json, sys
sys.path[:0] = ['markdown/exlex', 'markdown/app', 'lib']
import mdparser, htmlgen, decks
out = {}
for name, md in json.loads(sys.argv[1]).items():
    doc = '---\\ntarget: en\\n---\\n\\n' + md
    fm, blocks = mdparser.parse(doc)
    b = blocks[0]
    html = htmlgen.render_document(doc, asset_base='/clips/media/')['html']
    try:
        decks.validate_markdown(md, 'en'); deck = True
    except Exception as e:
        deck = str(e)
    out[name] = {'types': [x['type'] for x in blocks], 'errors': b.get('errors'), 'fields': b.get('fields'),
                 'raw': b.get('raw_fields'), 'deck': deck, 'html': html}
print(json.dumps(out))
`, JSON.stringify(md)));
  for (const k of Object.keys(md)) {
    const p = parsed[k];
    assert(p.types.length === 1 && p.types[0] === 'exercise' && p.errors.length === 0 && p.deck === true
           && !p.html.includes('ex-invalid') && p.html.includes('class="ex-flashcard'),
           `markdown(${k}) is one sound exercise to mdparser, decks.validate_markdown and htmlgen ${p.errors.join('; ')}${p.deck === true ? '' : p.deck}`);
  }
  assert(parsed.vocab.fields.target === '[wound]{tl}' && parsed.vocab.fields.direction === 'both-repeat'
         && parsed.vocab.fields['front-audio'] === 'audio/' + clipName && parsed.vocab.raw.context === '[The old man]{tl}\n[wound the clock]{tl}'
         && parsed.vocab.html.includes(`src="/clips/media/audio/${clipName}"`) && parsed.vocab.html.includes('ex-card-play'),
         'the vocab card reads back field for field and draws its recording from the tray');
  assert(parsed.opposites.fields.direction === 'reverse' && parsed.opposites.fields.opposite === '[young]{tl}',
         'the opposites card reads back');
  assert(parsed.jolly.raw['back-primary'] === '| form | sound |\n|---|---|\n| wind | waɪnd |\n| wound | waʊnd |'
         && /ex-card-blocks[^>]*>\s*<div class="tablewrap"><table/.test(parsed.jolly.html) && /ex-card-blocks[^>]*>\s*<ul>/.test(parsed.jolly.html)
         && parsed.jolly.html.includes('<div class="box"><p>a box on the card</p></div>'),
         'the jolly card keeps its table, list and box as blocks');
  assert(parsed.jolly.html.includes(`/clips/media/audio/${clipName}`), 'the jolly card\'s recording line is drawn from the tray');
  // the hub's preview renders the same
  const pv = await (await fetch(A + '/clips/api/preview', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                           body: JSON.stringify({markdown: md.jolly, lang: 'en'})})).json();
  assert(pv.ok && pv.html.includes('ex-flashcard') && !pv.html.includes('ex-invalid') && pv.html.includes('<table'),
         '/clips/api/preview renders the jolly card');
  const pv2 = await (await fetch(A + '/clips/api/preview', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                            body: JSON.stringify({markdown: md.vocab, lang: 'en'})})).json();
  assert(pv2.ok && !pv2.html.includes('ex-invalid') && pv2.html.includes(`/clips/media/audio/${clipName}`),
         '/clips/api/preview renders the vocab card with its recording');
  // a both (repeat) card says so beside it; a deck's preview of it does not, it is being asked both ways there
  const pvNote = await (await fetch(A + '/clips/api/preview', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                               body: JSON.stringify({markdown: md.repeat, lang: 'en', in_deck: true})})).json();
  const pvNoteDoc = await (await fetch(A + '/clips/api/preview', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                                  body: JSON.stringify({markdown: md.repeat, lang: 'en'})})).json();
  assert(pv2.html.includes('class="ex-card-note"') && pvNoteDoc.html.includes('class="ex-card-note"')
         && pvNote.ok && !pvNote.html.includes('ex-card-note') && pvNote.html.includes('ex-flashcard'),
         '/clips/api/preview: both (repeat) carries its note as a document draws it, and none as a deck\'s preview');

  // decks
  const dk = await page.evaluate(async mds => {
    const md = mds.forward;
    const deck = await ParsehCards.newDeck('Cardkit test', 'en');
    const list = await ParsehCards.decks('en');
    const origin = {book: '/books/english/mini-en', label: '1.1', url: '/books/english/mini-en/reader/#p1', title: 'The Clock and the Wind'};
    const one = await ParsehCards.add(deck.path, md, origin);
    const again = await ParsehCards.add(deck.path, md, origin);
    const forced = await ParsehCards.add(deck.path, md, origin, true);
    const bad = await ParsehCards.add(deck.path, ':::exercise flashcard\ncard-type: jolly\n:::\n', null);
    const pairDeck = await ParsehCards.newDeck('Cardkit pair', 'en');
    const pair = await ParsehCards.add(pairDeck.path, mds.repeat, origin);
    let err = '';
    try { await ParsehCards.newDeck('', 'en'); } catch (e) { err = e.message; }
    return {deck, list: list.map(d => d.path), one, again, forced, bad, pair, err};
  }, {forward: md.forward, repeat: md.repeat});
  assert(dk.deck && dk.deck.path === 'english/cardkit-test' && dk.list.includes(dk.deck.path),
         `newDeck makes a deck and decks lists it (${dk.deck && dk.deck.path})`);
  assert(dk.one.ok === true && dk.one.item && Array.isArray(dk.one.warnings), 'add puts the card in the deck');
  assert(dk.again.ok === false && dk.again.conflict === 'duplicate' && /already/.test(dk.again.error),
         `add again answers the duplicate: ${dk.again.error}`);
  assert(dk.forced.ok === true && dk.forced.item.id !== dk.one.item.id, 'add with force adds it anyway');
  assert(dk.bad.ok === false && !dk.bad.conflict && dk.bad.error, `add of a broken card answers why: ${dk.bad.error}`);
  assert(dk.err !== '', `newDeck refuses a deck with no name: ${dk.err}`);
  assert(dk.one.items.length === 1 && dk.pair.ok === true && dk.pair.items.length === 2
         && dk.pair.items[0].id !== dk.pair.items[1].id,
         'add hands back every card the deck made: one for a card, two for a both (repeat) one, so a sheet can say so');
  const items = [];
  for await (const e of Deno.readDir(`${TMP}/exercises/english/cardkit-test/items`)) items.push(e.name);
  assert(items.length === 2, `the deck on disk holds the two cards (${items.length})`);

  // preview: the studio's own script in the frame
  await page.evaluate(() => {
    const f = document.createElement('iframe');
    f.id = 'pcpv';
    f.style.cssText = 'position:fixed;left:10px;top:150px;width:560px;height:430px;z-index:500;background:#fff;border:1px solid #888';
    document.body.appendChild(f);
  });
  await page.evaluate(md => ParsehCards.preview(md, 'en', document.getElementById('pcpv')), md.jolly);
  const frame = page.frame({url: /about:srcdoc/}) || page.frames().find(f => f.parentFrame() && f !== page.mainFrame());
  await frame.waitForFunction(() => typeof bindExercises === 'function' && document.querySelector('.ex-flashcard'), null, {timeout: 8000});
  assert(await page.evaluate(() => document.getElementById('pcpv').getAttribute('sandbox') === 'allow-same-origin allow-scripts'),
         'the preview frame is sandboxed to scripts of its own origin');
  const card0 = await frame.evaluate(() => {
    const c = document.querySelector('.ex-flashcard');
    return {flipped: c.classList.contains('flipped'), cursor: getComputedStyle(c).cursor,
            radius: getComputedStyle(c).borderTopLeftRadius, table: !!c.querySelector('.ex-card-back table')};
  });
  assert(!card0.flipped && card0.cursor === 'pointer' && card0.radius === '14px' && card0.table,
         'preview fills the frame with the card, styled by the studio\'s app.css, the back\'s table in it');
  await page.frameLocator('#pcpv').locator('.ex-flashcard .ex-card-front').click({position: {x: 5, y: 5}});
  const card1 = await frame.evaluate(() => {
    const c = document.querySelector('.ex-flashcard');
    return {flipped: c.classList.contains('flipped'), back: !c.querySelector('.ex-card-back').hidden};
  });
  assert(card1.flipped && card1.back, 'a click on the previewed card turns it (bindExercises from /studio/static/app.js)');
  await page.evaluate(() => document.getElementById('pcpv').remove());

  // without the studio's script, the kit's own lines turn the card -- but not
  // for a click on a footnote's number or its cloud, as the studio's own
  // CARD_CONTROLS has it
  await page.route('**/studio/static/app.js', r => r.abort());
  await page.evaluate(() => {
    const f = document.createElement('iframe');
    f.id = 'pcpv2';
    f.style.cssText = 'position:fixed;left:10px;top:150px;width:560px;height:330px;z-index:500;background:#fff;border:1px solid #888';
    document.body.appendChild(f);
  });
  await page.evaluate(() => ParsehCards.preview(':::exercise flashcard\ncard-type: jolly\nfront-primary: wound[^1]\nback-primary: a hurt\n:::\n\n[^1]: an injury\n',
                                                'en', document.getElementById('pcpv2')));
  const fb = page.frameLocator('#pcpv2');
  await fb.locator('.ex-flashcard .fnref').waitFor();
  const turned = () => page.evaluate(() => {
    const d = document.getElementById('pcpv2').contentDocument, c = d.querySelector('.ex-flashcard');
    return [typeof d.defaultView.bindExercises, c.classList.contains('flipped')];
  });
  await fb.locator('.ex-flashcard .fnref').click();
  const onNote = await turned();
  assert(onNote[0] === 'undefined' && onNote[1] === false,
         `with no studio script, a click on a footnote's number does not turn the card: ${JSON.stringify(onNote)}`);
  await fb.locator('.ex-flashcard .ex-card-front').click({position: {x: 5, y: 5}});
  const onCard = await turned();
  assert(onCard[1] === true, `…and a click on the card does: ${JSON.stringify(onCard)}`);
  await page.unroute('**/studio/static/app.js');
  await page.evaluate(() => document.getElementById('pcpv2').remove());

  // copy, uploadFrame, status, canRecord
  const small = await page.evaluate(async () => {
    const was = Parseh.copy;
    let got = null;
    Parseh.copy = (t, raw) => { got = [t, raw]; return Promise.resolve(true); };
    const ok = await ParsehCards.copy(':::exercise flashcard\n:::\n');
    Parseh.copy = was;
    const c = document.createElement('canvas');
    c.width = 8; c.height = 6;
    const x = c.getContext('2d'); x.fillStyle = '#be3455'; x.fillRect(0, 0, 8, 6);
    const frame = await ParsehCards.uploadFrame(c.toDataURL('image/png'), 'a frame', 'en');
    const st = await ParsehCards.status();
    return {ok, got, frame, st, can: ParsehCards.canRecord(), same: ParsehCards.canRecord(NARR[0].src),
            other: ParsehCards.canRecord('https://example.com/a.mp3')};
  });
  assert(small.ok === true && small.got[0] === ':::exercise flashcard\n:::\n' && small.got[1] === true,
         'copy hands the text to Parseh.copy whole (raw)');
  assert(small.frame.kind === 'image' && /^images\/a-frame-[0-9a-f]{6}\.png$/.test(small.frame.path),
         `uploadFrame keeps the frame in the tray: ${small.frame.path}`);
  const png = await Deno.readFile(`${TRAY}/${small.frame.name}`);
  assert(png[0] === 0x89 && png[1] === 0x50, 'the frame on disk is the PNG');
  assert(small.st.ffmpeg === true && small.st.format === '.mp3', `status: ffmpeg here, writes ${small.st.format}`);
  assert(small.can && small.same && !small.other, 'canRecord: Web Audio, and a recording of this origin only');

  if (SHOTS) {
    await openCut(page, 'book');
    await waveform(page, 2.3, 1.8, 'desktop shot');
    await page.screenshot({path: `${SHOTS}/cardkit-desktop.png`});
    await page.keyboard.press('Escape');
  }

  /* ---------------- the editor at phone width ---------------- */
  console.log('   the editor at 400 px');
  const phone = await browser.newPage({viewport: {width: 400, height: 800}, hasTouch: true});
  watch(phone, errors);
  await phone.goto(A + info.reader);
  await phone.waitForFunction(() => typeof SUBS !== 'undefined');
  await inject(phone, A);
  await openCut(phone, 'book');
  await waveform(phone, 2.3, 1.8, 'at 400 px');
  await onScreen(phone, '.pc-cut', 'the editor at 400 px');
  for (const sel of ['.pc-cut [data-e="s-1"]', '.pc-cut [data-e="sh"]', '.pc-cut [data-e="e+1"]', '.pc-cut [data-e="rv"]',
                     '.pc-cut .pc-save', '.pc-cut .pc-use', '.pc-strip'])
    await onScreen(phone, sel, `${sel} at 400 px`);
  assert(await phone.evaluate(() => { const b = document.querySelector('.pc-cut'); return b.scrollWidth <= b.clientWidth && document.documentElement.scrollWidth <= innerWidth; }),
         'nothing is wider than the phone');
  // lines a row wraps into: its controls' middles, 10 px apart or more
  const rows = await phone.evaluate(() => [...document.querySelectorAll('.pc-cut .erow')].map(r => {
    const mids = [...r.children].map(c => { const b = c.getBoundingClientRect(); return (b.top + b.bottom) / 2; })
      .sort((x, y) => x - y);
    return mids.filter((m, i) => i === 0 || m - mids[i - 1] > 10).length;
  }));
  assert(rows[0] === 1 && rows[1] === 1 && rows[2] <= 2, `the rows keep to their lines at 400 px (lines per row: ${rows})`);
  const wholePhone = await wholeValues(phone);
  assert(wholePhone.every(([, sw, cw]) => sw <= cw), `at 400 px an edge's input shows the whole of 17.62 and of 1234.56: ${JSON.stringify(wholePhone)}`);
  // a finger drags the start edge
  const sb = await phone.locator('.pc-edge0').boundingBox();
  const before = await vals(phone);
  const cdp = await phone.context().newCDPSession(phone);
  const fx = sb.x + sb.width / 2, fy = sb.y + sb.height / 2;
  await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: fx, y: fy}]});
  for (const dx of [8, 16, 24, 32, 40])
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: fx - dx, y: fy}]});
  await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  const after = await vals(phone);
  assert(+after.s < +before.s - 0.1, `a touch drag moves the start edge: ${before.s} → ${after.s}`);
  // a word of a few hundredths: the two lines on one another under a finger
  const touchDrag = async (x, y, dx) => {
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y}]});
    for (let k = 1; k <= 5; k++)
      await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: x + dx * k / 5, y}]});
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
    return vals(phone);
  };
  await typeTimes(phone, '2.00', '2.03');
  let ep = await edges(phone);
  let tv = await touchDrag((ep.x0 + ep.x1) / 2, ep.mid, 40);
  assert(ep.x1 - ep.x0 < 4 && tv.s === '2.00' && +tv.e > 2.3,
         `at 400 px, lines ${(ep.x1 - ep.x0).toFixed(1)} px apart: a finger moving right takes the end (${tv.s} – ${tv.e})`);
  await typeTimes(phone, '2.00', '2.03');
  ep = await edges(phone);
  tv = await touchDrag((ep.x0 + ep.x1) / 2, ep.mid, -40);
  assert(tv.e === '2.03' && +tv.s < 1.7, `…and moving left the start (${tv.s} – ${tv.e})`);
  if (SHOTS) await phone.screenshot({path: `${SHOTS}/cardkit-phone.png`});
  await phone.keyboard.press('Escape');
  await phone.close();

  /* ---------------- c) a film, from the player page ---------------- */
  console.log('c) a film, from the video player');
  const film = await browser.newPage({viewport: {width: 1280, height: 800}});
  watch(film, errors);
  await film.goto(`${A}/youtube/v/${info.video}/`);
  await film.waitForFunction(() => document.getElementById('film') && document.getElementById('film').readyState >= 1,
                             null, {timeout: 30000});
  await inject(film, A);
  await film.evaluate(() => { const f = document.getElementById('film'); f.muted = true; return f.play(); });
  await film.waitForFunction(() => !document.getElementById('film').paused);
  await openCut(film, 'film');
  await onScreen(film, '.pc-cut', 'the cut editor over the player');
  assert(await film.evaluate(() => document.getElementById('film').paused), "the player's film is paused while it is open");
  await waveform(film, 2.3, 1.8, 'a film');
  v = await vals(film);
  assert(v.s === '1.90' && v.e === '2.70', `the film's guess in the inputs: ${v.s} – ${v.e}`);
  const before2 = await trayAudio(TRAY);
  await film.click('.pc-cut .pc-save');
  await film.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 15000});
  const fresh = (await trayAudio(TRAY)).filter(n => !before2.includes(n));
  assert(fresh.length === 1 && /^market-[0-9a-f]{6}\.mp3$/.test(fresh[0]), `the film's clip is in the tray: ${fresh}`);
  const d3 = await duration(`${TRAY}/${fresh[0]}`);
  t = await tones(`${TRAY}/${fresh[0]}`);
  assert(near(d3, 0.8, 0.06) && t.length === 1 && near(t[0][0], 0.1, 0.05) && near(t[0][1], 0.7, 0.05),
         `…0.80 s long (${d3.toFixed(3)}), its tone at ${JSON.stringify(t.map(r => r.map(x => +x.toFixed(3))))} (want [0.1,0.7])`);
  await film.click('.pc-cut .pc-use');
  await film.waitForFunction(() => window.__done, null, {timeout: 5000});
  res = await film.evaluate(() => window.__res);
  assert(res && res.name === fresh[0] && res.source.kind === 'film' && res.source.video === info.video,
         `use this clip resolves with the film's record (${res && res.source.video})`);
  await film.close();
  await page.close();

  /* ---------------- d) a machine without ffmpeg ---------------- */
  console.log('d) no ffmpeg: recorded in the browser');
  hubB = await hub(['--no-ffmpeg', '--tray', 'tray-noff']);
  const B = hubB.base;
  browserB = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true,
                                    args: ['--autoplay-policy=no-user-gesture-required']});
  const nb = await browserB.newPage({viewport: {width: 1280, height: 800}});
  watch(nb, errors);
  const uploads = [], peaksAnswers = [];
  nb.on('response', r => { if (r.url().includes('__clip/peaks')) peaksAnswers.push(r.status()); });
  nb.on('request', r => { if (r.url().includes('/clips/api/upload')) uploads.push([r.url(), r.headers()['content-type']]); });
  await nb.goto(B + info.reader);
  await nb.waitForFunction(() => typeof SUBS !== 'undefined');
  await inject(nb, B);
  assert((await nb.evaluate(() => ParsehCards.status())).ffmpeg === false, 'status says there is no ffmpeg');
  await openCut(nb, 'book');
  for (let i = 0; i < 40 && !peaksAnswers.length; i++) await sleep(100);
  await sleep(200);
  assert(peaksAnswers[0] === 409 && await nb.evaluate(() => {
    const st = document.querySelector('.pc-strip');
    return st.classList.contains('pc-plain') && !st.classList.contains('pc-drawn');
  }),
         `no waveform: peaks answered ${peaksAnswers}, the strip is plain`);
  await nb.fill('.pc-cut .e0', '1.8'); await nb.press('.pc-cut .e0', 'Enter');
  await nb.fill('.pc-cut .e1', '3.3'); await nb.press('.pc-cut .e1', 'Enter');
  await nb.waitForFunction(() => document.querySelector('.pc-root .pc-play').paused, null, {timeout: 30000});
  await nb.click('.pc-cut .pc-save');
  await nb.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 20000})
    .catch(async () => { throw Error('FAIL: no clip was recorded: ' + await nb.textContent('.pc-stat')); });
  let trayB = await trayAudio(TRAYB);
  assert(trayB.length === 1 && /^wound-[0-9a-f]{6}\.wav$/.test(trayB[0]), `the browser recorded the clip into the tray: ${trayB}`);
  assert(uploads.length === 1 && uploads[0][0].includes('kind=audio') && uploads[0][1] === 'audio/wav',
         'it was sent to /clips/api/upload?kind=audio as a WAV');
  const d4 = await duration(`${TRAYB}/${trayB[0]}`);
  assert(near(d4, 1.5, 0.15), `the recording is the clip's length, 1.50 s (ffprobe ${d4.toFixed(3)})`);
  t = await tones(`${TRAYB}/${trayB[0]}`);
  console.log('     tones in the browser recording:', JSON.stringify(t.map(r => r.map(x => +x.toFixed(3)))));
  assert(bookTones(t, 0.06), `its tones are within 60 ms of [0.2, 0.8] and [1.2, 1.5], where the recording has them: ${shown(t)}`);
  await nb.click('.pc-cut .pc-use');
  await nb.waitForFunction(() => window.__done, null, {timeout: 5000});
  res = await nb.evaluate(() => window.__res);
  assert(res && res.name === trayB[0] && res.path === 'audio/' + trayB[0] && res.source.narration === 'n1',
         `use this clip resolves with the recorded clip (${res && res.path})`);
  // and a film, recorded the same way
  const nf = await browserB.newPage({viewport: {width: 1000, height: 760}});
  watch(nf, errors);
  await nf.goto(`${B}/youtube/v/${info.video}/`);
  await nf.waitForFunction(() => document.getElementById('film') && document.getElementById('film').readyState >= 1, null, {timeout: 30000});
  await inject(nf, B);
  await openCut(nf, 'film');
  await nf.waitForFunction(() => document.querySelector('.pc-root .pc-play').readyState >= 1);
  await nf.click('.pc-cut .pc-use');
  await nf.waitForFunction(() => window.__done, null, {timeout: 20000});
  res = await nf.evaluate(() => window.__res);
  trayB = await trayAudio(TRAYB);
  assert(res && /^market-[0-9a-f]{6}\.wav$/.test(res.name) && trayB.includes(res.name) && res.source.video === info.video,
         `a film's clip is recorded and used in one step: ${res && res.name}`);
  const d5 = await duration(`${TRAYB}/${res.name}`);
  t = await tones(`${TRAYB}/${res.name}`);
  console.log('     tones in the film recording:', JSON.stringify(t.map(r => r.map(x => +x.toFixed(3)))));
  assert(near(d5, 0.8, 0.15) && t.length === 1 && near(t[0][0], 0.1, 0.06), `…0.80 s long (${d5.toFixed(3)}), its tone within 60 ms of 0.1 s`);
  await nf.close();

  // A recording that stops in the middle of the clip -- here it is paused
  // for 0.6 s at about 2.3 s, inside the clip's first tone, as one that runs
  // out of loaded sound stops -- is played again, and the clip cut from a
  // pass played through.
  const ni = await browserB.newPage({viewport: {width: 1280, height: 800}});
  watch(ni, errors);
  await ni.goto(B + info.reader);
  await ni.waitForFunction(() => typeof SUBS !== 'undefined');
  await inject(ni, B);
  await openCut(ni, 'book', {hint: 'interrupted'});
  await typeTimes(ni, '1.8', '3.3');
  await ni.waitForFunction(() => document.querySelector('.pc-root .pc-play').paused, null, {timeout: 30000});
  await sayings(ni);
  await ni.evaluate(() => {
    window.__cuts = 0;
    new MutationObserver((ms, obs) => {
      const rec = document.querySelector('.pc-root .pc-rec');
      if (!rec) return;
      obs.disconnect();
      rec.addEventListener('playing', () => setTimeout(() => {
        window.__cuts++;
        rec.pause();
        setTimeout(() => rec.play(), 600);
      }, 750), {once: true});
    }).observe(document.querySelector('.pc-root'), {childList: true});
  });
  let beforeB = await trayAudio(TRAYB);
  await ni.click('.pc-cut .pc-save');
  await ni.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 30000})
    .catch(async () => { throw Error('FAIL: no clip was recorded: ' + await ni.textContent('.pc-stat')); });
  let freshB = (await trayAudio(TRAYB)).filter(n => !beforeB.includes(n));
  let said = await ni.evaluate(() => window.__said);
  t = freshB.length === 1 ? await tones(`${TRAYB}/${freshB[0]}`) : [];
  console.log('     tones in the interrupted recording:', JSON.stringify(t.map(r => r.map(x => +x.toFixed(3)))));
  assert(freshB.length === 1 && near(await duration(`${TRAYB}/${freshB[0]}`), 1.5, 0.15) && bookTones(t, 0.06),
         `the clip kept is the one played through: 1.50 s, its tones within 60 ms of [0.2, 0.8] and [1.2, 1.5]: ${shown(t)}`);
  assert(await ni.evaluate(() => window.__cuts) === 1 && said.some(x => /again, 2 of 3/.test(x)),
         `the interrupted pass was played again: “${said.find(x => /again/.test(x)) || said.slice(-3).join(' / ')}”`);
  await ni.keyboard.press('Escape');

  // A connection slower than the recording plays (45 s of 1536 kbit/s WAV
  // over 1000 kbit/s): the stretch is loaded before it is played, and the
  // clip is the right one.
  await openCut(ni, 'book', {source: {src: '../audio/slow.wav'}, context: [30.5, 33], guess: [30.8, 32.3], hint: 'slow'});
  await ni.waitForFunction(() => document.querySelector('.pc-root .pc-play').readyState >= 1, null, {timeout: 30000});
  await sayings(ni);
  const net = await ni.context().newCDPSession(ni);
  await net.send('Network.enable');
  await net.send('Network.setCacheDisabled', {cacheDisabled: true});
  await net.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: 125000, uploadThroughput: -1});
  beforeB = await trayAudio(TRAYB);
  await ni.click('.pc-cut .pc-save');
  await ni.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 60000})
    .catch(async () => { throw Error('FAIL: no clip was recorded: ' + await ni.textContent('.pc-stat')); });
  await net.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
  freshB = (await trayAudio(TRAYB)).filter(n => !beforeB.includes(n));
  said = await ni.evaluate(() => window.__said);
  t = freshB.length === 1 ? await tones(`${TRAYB}/${freshB[0]}`) : [];
  console.log('     tones in the throttled recording:', JSON.stringify(t.map(r => r.map(x => +x.toFixed(3)))));
  assert(freshB.length === 1 && near(await duration(`${TRAYB}/${freshB[0]}`), 1.5, 0.15) && bookTones(t, 0.06),
         `the clip recorded over the slow connection is 1.50 s, its tones within 60 ms of [0.2, 0.8] and [1.2, 1.5]: ${shown(t)}`);
  assert(said.some(x => /^loading the recording/.test(x)), `it waited for the stretch to load: “${said.find(x => /^loading/.test(x))}”`);
  await ni.click('.pc-cut .pc-use');
  await ni.waitForFunction(() => window.__done, null, {timeout: 5000});
  res = await ni.evaluate(() => window.__res);
  assert(res && res.name === freshB[0], `…and is the one used (${res && res.name})`);

  // Every clip the browser cuts fades 8 ms in and 8 ms out, as the server's
  // cut does (audiofile.extract): one recorded here, and one cut from a tab's
  // recording -- the tab a stand-in player over an element of the page's own,
  // heard through the kit's AudioWorklet.  Each is [2.1, 2.5], inside the tone
  // at [2, 2.6], so what its ends lack is the fade.
  const fades = {};
  await openCut(ni, 'book', {context: [2.1, 2.5], guess: [2.1, 2.5], hint: 'fade'});
  await ni.waitForFunction(() => document.querySelector('.pc-root .pc-play').readyState >= 1, null, {timeout: 30000});
  beforeB = await trayAudio(TRAYB);
  await ni.click('.pc-cut .pc-save');
  await ni.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 30000})
    .catch(async () => { throw Error('FAIL: no clip was recorded: ' + await ni.textContent('.pc-stat')); });
  freshB = (await trayAudio(TRAYB)).filter(n => !beforeB.includes(n));
  fades.recorded = await fadeMs(`${TRAYB}/${freshB[0]}`);
  await ni.keyboard.press('Escape');
  await ni.waitForFunction(() => window.__done, null, {timeout: 5000});
  await ni.evaluate(async () => {
    const a = new Audio(NARR[0].src);            // not in the document: no page listener hears it play
    a.preload = 'auto';
    await new Promise(r => a.readyState >= 1 ? r() : a.addEventListener('loadedmetadata', r, {once: true}));
    const player = {
      getCurrentTime: () => a.currentTime, getDuration: () => a.duration,
      getPlayerState: () => a.ended ? 0 : a.seeking ? 3 : a.paused ? 2 : 1,
      playVideo: () => { a.play().catch(() => {}); }, pauseVideo: () => a.pause(), seekTo: t => { a.currentTime = t; },
      isMuted: () => a.muted, mute: () => { a.muted = true; }, unMute: () => { a.muted = false; },
      getVolume: () => a.volume * 100, setVolume: v => { a.volume = v / 100; },
      getPlaybackRate: () => a.playbackRate, setPlaybackRate: r => { a.playbackRate = r; },
    };
    let stream = null;
    window.__tp = window.MediaStreamTrackProcessor;
    window.MediaStreamTrackProcessor = undefined;
    window.__done = false; window.__res = undefined;
    ParsehCards.cut({source: {kind: 'tab', player, video: 'fade', stream: () => Promise.resolve(stream || (stream = a.captureStream()))},
                     context: [2.1, 2.5], guess: [2.1, 2.5], lang: 'en', hint: 'tabfade', label: '0:02', text: 'fade'})
      .then(r => { window.__res = r; window.__done = true; });
  });
  await ni.click('.pc-cut .pc-take .pc-record');
  await ni.waitForFunction(() => /^recorded /.test(document.querySelector('.pc-stat').textContent), null, {timeout: 40000})
    .catch(async () => { throw Error('FAIL: the tab was not recorded: ' + await ni.textContent('.pc-stat')); });
  beforeB = await trayAudio(TRAYB);
  await ni.click('.pc-cut .pc-save');
  await ni.waitForSelector('.pc-saved:not([hidden]) .pc-name', {timeout: 30000})
    .catch(async () => { throw Error('FAIL: the tab\'s clip was not saved: ' + await ni.textContent('.pc-stat')); });
  freshB = (await trayAudio(TRAYB)).filter(n => !beforeB.includes(n));
  fades.tab = await fadeMs(`${TRAYB}/${freshB[0]}`);
  await ni.keyboard.press('Escape');
  await ni.waitForFunction(() => window.__done, null, {timeout: 5000});
  await ni.evaluate(() => { window.MediaStreamTrackProcessor = window.__tp; });
  assert(Object.values(fades).every(f => f.level > 0.7 && [f.head, f.tail].every(ms => ms >= 7 && ms <= 9)),
         `a clip recorded in the browser and one cut from a tab's recording each fade 8 ms at both ends, as the server's: ${JSON.stringify(fades)}`);

  assert(errors.length === 0, 'no page error and no failed request of the kit: ' + errors.join(' | '));
  for (const [name, h] of [['hub', hubA], ['hub without ffmpeg', hubB]])
    assert(!/Traceback/.test(h.log.join('')), `the ${name} logged no traceback`);
  console.log(`cardkit: ${passed} checks passed`);
} finally {
  for (const b of [browser, browserB]) if (b) await b.close().catch(() => {});
  for (const h of [hubA, hubB]) if (h) { try { h.proc.kill('SIGTERM'); await h.proc.status; } catch (_) {} }
  await Deno.remove(TMP, {recursive: true}).catch(() => {});
}
