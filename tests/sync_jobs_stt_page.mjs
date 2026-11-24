import { chromium } from 'npm:playwright-core@1.52.0';
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/sync_jobs_stt_page.mjs
//
// A TRANSCRIPTION LENT BY ITS SOUND, from the add page (a0.7.0, lane D2; lib/jobs.js,
// lib/syncjobs.py "transcribe", lib/sttjobs.py), driven in Chromium.
// Two real installs paired over TLS (tests/sync_harness.py).  B has no speech to text and
// "send" on; A has it (SYNC_JOBS_FAKE "stt": tests/addstt_fakes.py, the real job and worker with
// the faster-whisper stand-in) and "accept" on.  On B's add page, with a YouTube link:
//   the block offers A's model (B has none), Transcribe -> the panel says why B cannot and
//   offers "Send to A" -> pressed, the video is put in its frame and "Start recording" records
//   it -> the pieces go to B as always -> the page says "Waiting for a computer…" / "On A…" ->
//   the transcript A made is in B's USUAL review -> "Use" puts it in the box.
// FAKED: Whisper (above), and THE TAB CAPTURE: youtube/lib/tabcapture.js is answered by a
// stand-in whose embed() gives a player that does nothing and whose record() hands the page
// four seconds of a tone in two pieces, a mark and the peaks, then "ended" -- the page's own
// sending of the pieces, marks, wave and seal are the real ones.  YouTube is never reached.
const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const TMP = await Deno.makeTempDir({prefix: 'parseh-jobs-stt-page-'});
let passed = 0;
const failed = [];
const check = (v, m) => { if (v) { passed++; console.log('  ok', m); } else { failed.push(m); console.log('  FAIL', m); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 60000) {
  const t = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t > ms) throw new Error('timed out: ' + what);
    await sleep(150);
  }
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}
const TURBO = 'large-v3-turbo';
const FAKE = {deadline: 20, caps_ttl: 1, timeout: 4};
function start(name, stt) {
  const tree = `${TMP}/${name}`, port = freePort();
  Deno.mkdirSync(tree);
  const log = Deno.openSync(`${TMP}/${name}.log`, {write: true, create: true});
  const proc = new Deno.Command(PY, {args: ['tests/sync_harness.py', 'serve', tree, String(port)],
    env: {SYNC_JOBS_FAKE: JSON.stringify({...FAKE, stt})}, stdout: 'piped', stderr: 'piped'}).spawn();
  proc.stdout.pipeTo(log.writable);
  proc.stderr.pipeTo(Deno.openSync(`${TMP}/${name}.err`, {write: true, create: true}).writable);
  return {name, tree, port, proc};
}
async function post(inst, route, body) {
  const r = await fetch(`http://127.0.0.1:${inst.port}${route}`, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
  return {status: r.status, j: await r.json()};
}
async function up(inst) {
  for (let i = 0; i < 300; i++) {
    try { const r = await post(inst, '/settings/api/devices/state'); if (r.status === 200 && r.j.this.key) return; }
    catch (e) { /* not yet */ }
    await sleep(300);
  }
  throw new Error(inst.name + ' never came up: ' + TMP);
}
const write = (p, t) => { Deno.mkdirSync(p.replace(/\/[^/]*$/, ''), {recursive: true}); Deno.writeTextFileSync(p, t); };

// the tab capture's stand-in (see the head of this file)
const FAKE_CAPTURE = `
(function () {
  function player() {
    var t = 0, state = 5;
    return {getCurrentTime: function () { return t; }, getDuration: function () { return 4; },
      getPlayerState: function () { return state; }, seekTo: function (s) { t = s; },
      playVideo: function () { state = 1; }, pauseVideo: function () { state = 2; },
      mute: function () {}, unMute: function () {}, isMuted: function () { return false; },
      setVolume: function () {}, getVolume: function () { return 100; }, destroy: function () {},
      getIframe: function () { return document.createElement('iframe'); }};
  }
  function tone(n, from) {
    var a = new Int16Array(n);
    for (var i = 0; i < n; i++) a[i] = Math.round(12000 * Math.sin(2 * Math.PI * 440 * (from + i) / 16000));
    return a;
  }
  window.__captured = 0;
  window.ParsehTabCapture = {
    capability: function () { return {ok: true, why: ''}; }, problem: function () { return ''; },
    busy: function () { return false; }, release: function () {}, share: function () { return Promise.resolve(); },
    embed: function (box) { box.appendChild(document.createElement('div')); return Promise.resolve(player()); },
    record: function (o) {
      var ctl = {state: 'recording', stop: function () {}};
      ctl.promise = Promise.resolve().then(function () {
        if (o.onStart) o.onStart();
        var half = 32000, a = tone(half, 0), b = tone(half, half);
        return o.onChunk(a, 0, null).then(function () {
          if (o.onProgress) o.onProgress(2, 4);
          return o.onChunk(b, half, null);
        }).then(function () {
          window.__captured = 2 * half;
          if (o.onMark) { o.onMark(0, 0); o.onMark(64000, 4); }
          if (o.onPeaks) o.onPeaks([0.1, 0.5, 0.9, 0.5, 0.1, 0.5, 0.9, 0.5], 2);
          ctl.state = 'ended';
          return {reason: 'ended'};
        });
      });
      return ctl;
    }
  };
})();`;

const A = start('A', {runtime: true, models: [TURBO], segments: [[0.0, 1.5, ' uno due tre'], [2.0, 3.5, ' quattro cinque']]});
const B = start('B', {runtime: false, models: []});
let browser;
try {
  await up(A); await up(B);
  const offer = (await post(A, '/settings/api/devices/pair-start')).j;
  const paired = await post(B, '/settings/api/devices/pair-enter',
    {code: offer.said, address: `127.0.0.1:${A.port}`, fingerprint: offer.fingerprint});
  check(paired.status === 200, 'B paired with A');
  write(`${B.tree}/config/sync/jobs-switches.json`, JSON.stringify({send: true}));
  write(`${A.tree}/config/sync/jobs-switches.json`, JSON.stringify({accept: true}));
  // the server's own lib/ and youtube/lib/, as the toolbox serves them from its root (tests/add_stt.mjs does the same)
  Deno.symlinkSync(`${root}/lib`, `${B.tree}/root/lib`);
  Deno.symlinkSync(`${root}/youtube/lib`, `${B.tree}/root/youtube/lib`);

  browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN')});
  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  await context.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, r => r.abort());
  await context.route(/\/youtube\/lib\/tabcapture\.js(\?.*)?$/, r => r.fulfill({status: 200,
    contentType: 'text/javascript', body: FAKE_CAPTURE}));
  const page = await context.newPage();
  const errors = [], calls = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('dialog', d => d.accept());
  page.on('request', q => { const u = new URL(q.url()); if (/transcribe\//.test(u.pathname)) calls.push(u.pathname.replace(/^.*transcribe\//, '')); });
  page.on('response', r => { if (r.status() >= 400 && !(r.status() === 409 && /transcribe\/start$/.test(r.url()))) errors.push(r.status() + ' ' + r.url()); });
  await page.goto(`http://localhost:${B.port}/youtube/add/?src=yt&by=empty`);
  await page.waitForSelector('#transcript', {state: 'visible'});
  await page.fill('#url', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  await page.selectOption('#lang', 'it');
  await page.waitForFunction(() => { const s = document.getElementById('stt'); return s && !s.hidden; }, null, {timeout: 20000});
  const ph = () => page.evaluate(() => document.getElementById('stt').getAttribute('data-state'));
  await until(async () => (await ph()) === 'idle', 'the block offers transcription', 20000);
  const models = await page.$$eval('#stt_model option', os => os.map(o => o.value));
  check(models.includes(TURBO), "the block offers A's model though B has none: " + models.join(','));
  check(/paired computer/.test(await page.textContent('#stt')), 'it says the work is done on the paired computer');
  await page.click('#stt_go');
  const panel = page.locator('.pj-panel');
  await panel.waitFor({timeout: 20000});
  const said = (await panel.innerText()).replace(/\s+/g, ' ');
  check(/Speech to text is not installed/.test(said), 'the panel says why B cannot: ' + said);
  const send = panel.locator('button.pj-go');
  check((await send.count()) === 1 && /^Send to A/.test(await send.innerText()), 'one "Send to A" button');
  await send.click();
  await until(async () => (await ph()) === 'ready', 'the video in its frame, waiting for "Start recording"', 20000);
  check(!(await panel.isVisible().catch(() => false)), 'the panel went: the page follows its own job');
  await page.click('#stt_rec');
  const seen = new Set();
  await until(async () => {
    const s = (await page.textContent('#stt_say').catch(() => '')) || (await page.evaluate(() => {
      const e = document.querySelector('#stt [role=status]'); return e ? e.textContent : ''; }));
    if (s) seen.add(s.replace(/:.*$/, '').trim());
    return (await ph()) === 'review';
  }, 'the transcript in the review', 120000);
  console.log('  the page said:', [...seen].join(' | '));
  check([...seen].some(s => /^(Waiting for a computer|On A|Receiving the recording)/.test(s)),
        'the page said where the work was ("waiting for a computer" / "on A")');
  check(calls.filter(c => /^audio/.test(c)).length >= 2, 'the recording went to B in pieces: ' + calls.join(','));
  const review = await page.textContent('#stt_workspace');
  check(/uno/.test(review) && /quattro/.test(review), "A's transcript is in B's review");
  check(/Transcribed on A/.test(review), 'the review says where it was transcribed');
  await page.click('#stt_use');
  await until(async () => (await ph()) === 'idle', 'Use finishes the review', 20000);
  const box = await page.inputValue('#transcript');
  check(/uno due tre/.test(box) && /quattro cinque/.test(box), 'Use puts it in the box: ' + box.replace(/\s+/g, ' ').slice(0, 80));
  check(errors.length === 0, 'no error in the page: ' + errors.join(' / '));
} catch (e) {
  failed.push(String(e && e.stack || e));
  console.log('  FAIL', e);
} finally {
  if (browser) await browser.close();
  for (const i of [A, B]) { try { i.proc.kill('SIGTERM'); await i.proc.status; } catch (e) { /* gone */ } }
  if (!Deno.env.get('KEEP_JOBS_PAGE')) await Deno.remove(TMP, {recursive: true}).catch(() => {});
  else console.log('kept', TMP);
}
console.log(`\n${passed} passed, ${failed.length} failed`);
Deno.exit(failed.length ? 1 : 0);
