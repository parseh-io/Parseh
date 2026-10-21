// SPDX-License-Identifier: GPL-3.0-or-later
/* IS THE COMPUTER THERE?  The page's one question, driven (TO-DO §2.24).

   The owner, 2026-09-24, working from a remote computer over Tailscale:
   Parseh kept deciding the computer was away when it was not.  On this
   computer nothing of it shows, because nothing is ever slow here -- which
   is how it shipped: every offline test there was stopped the server, and
   none made it SLOW.  The owner's words decide what is right:

     "Offline will mean drastic things usually, it's not a status that
      should change fast ... We should not talk of offline for simply
      having a slow connection."

   So the three ways a computer can fail to answer are made here with the
   real server, and they must behave DIFFERENTLY:

     refused  the server stopped: the socket is refused at once.  Offline,
              promptly -- three refusals in a row, two seconds apart.
     silent   the server suspended (SIGSTOP): the port is open and nothing
              ever answers, which is what a phone meets when the computer on
              the far side of Tailscale is off or asleep.  "checking…", NOT
              offline -- and offline only once three asks across 45 s have
              gone unanswered.
     slow     the server held still for eight seconds at a time and let go
              between: every answer late, and every one real.  NEVER
              offline, not for a moment, however many answers are late.

   And beside them what the owner decided the same day: "no network" and an
   ask that fails is offline at once; an away the page before only ASSUMED
   refuses no write; a REFRESH never inherits what the page before found
   ("upon refreshing, do not assume still offline") -- whether the refresh
   is the browser's own, a finger pulling the page down, or ↻ beside the
   chip -- and a page that has confirmed the computer away stays the offline
   version while it is open (§19).

   AND WHAT THE WORKER DOES WITH A PAGE NOBODY KEPT (the owner, 2026-09-28, TO-DO
   §2.28): a link followed to it, from a page that is open, is given the
   worker's short deadline, and at the deadline the worker asks the page
   whether the computer is answering, rather than deciding by itself.  A
   computer that is alive and merely slow is waited for, up to the long
   deadline; one that is silent, one the page has judged away, one that
   refuses, and a page that cannot answer (nobody open, or hidden) end on the
   offline page where they always did -- the same link from the same page,
   and only what is at the other end of the wire differs (the `nav` part).

   Run: CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/reach.mjs
     REACH_PARTS=refused,silent,slow,nonet,writes,refresh,drag,nav runs some of it */
import { chromium } from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const PY = Deno.env.get('PARSEH_PYTHON') || 'python3';
const CHROME = Deno.env.get('CHROME_BIN');
const PARTS = (Deno.env.get('REACH_PARTS') || 'refused,silent,slow,nonet,writes,refresh,drag,nav').split(',');
const td = new TextDecoder();
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
  m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
// polled from out here: an async predicate handed to waitForFunction "passes"
// at once (tests/mobile_pages.mjs, `until`)
async function until(page, fn, arg, timeout = 30000, every = 100) {
  for (const t = Date.now();;) {
    const v = await page.evaluate(fn, arg).catch(() => null);
    if (v) return v;
    if (Date.now() - t > timeout)
      throw Error('FAIL: waited ' + timeout + 'ms in vain for ' + String(fn).replace(/\s+/g, ' ').slice(0, 160));
    await sleep(every);
  }
}
function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const p = l.addr.port;
  l.close();
  return p;
}

// ---- the toolbox, and its server: tests/mobile_harness.py, as tests/mobile_pages.mjs boots it
const WORK = await Deno.makeTempDir({prefix: 'parseh-reach-'});
const built = await new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'build', WORK], cwd: root,
                                          stdout: 'piped', stderr: 'piped'}).output();
if (!built.success) throw Error(td.decode(built.stderr) || td.decode(built.stdout));
const MADE = JSON.parse(td.decode(built.stdout).trim().split('\n').pop());
const port = freePort();
const B = `http://127.0.0.1:${port}`;
const log = [];
let hub = null, hubUp = false, frozen = false;
async function hubStart() {
  hub = new Deno.Command(PY, {args: ['tests/mobile_harness.py', 'serve', WORK, String(port)], cwd: root,
                              stdout: 'piped', stderr: 'piped'}).spawn();
  hubUp = true;
  for (const s of [hub.stdout, hub.stderr])
    (async () => { for await (const c of s.pipeThrough(new TextDecoderStream())) log.push(c); })();
  for (const t = Date.now();;) {
    try { const r = await fetch(B + '/'); await r.body?.cancel(); if (r.ok) return; } catch (_) {}
    if (Date.now() - t > 60000) throw Error('the hub did not start:\n' + log.join(''));
    await sleep(200);
  }
}
// SWITCHED OFF: the process gone, and the port refusing before anything goes on
async function hubStop() {
  if (!hubUp) return;
  if (frozen) thaw();
  hub.kill('SIGTERM');
  await hub.status;
  hubUp = false;
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(B + '/', {signal: AbortSignal.timeout(500)}); await r.body?.cancel(); await sleep(100); }
    catch (_) { return; }
  }
}
// UNREACHABLE: the port open, the socket accepted, nothing ever answered
const freeze = () => { Deno.kill(hub.pid, 'SIGSTOP'); frozen = true; };
const thaw = () => { Deno.kill(hub.pid, 'SIGCONT'); frozen = false; };
await hubStart();

const browser = await chromium.launch({executablePath: CHROME, headless: true});
const errors = [];
const PHONE = {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true};

/* WHAT THE PAGE SAID, AND WHEN, from its very first moment.  Kept in the page
   itself -- a change is written down as it happens, every 25 ms -- so that
   a state it held for a tenth of a second between two looks from out here is
   still seen: the mark on <html>, the offline chip, ↻, "checking…", and
   whether lib/keep.js had started yet -- which it does in DOMContentLoaded,
   in the same task as the listener below, so no look can fall between the
   two. */
const SAMPLER = () => {
  window.__seen = [];
  let last = '';
  document.addEventListener('DOMContentLoaded', () => { window.__dcl = true; });
  const drawn = sel => !!document.body &&
    [...document.querySelectorAll(sel)].some(e => e.getClientRects().length > 0);
  (function look() {
    const h = document.documentElement;
    // a mark with no value is a mark: an older page set it bare
    const mark = h && h.hasAttribute('data-parseh-away') ? (h.getAttribute('data-parseh-away') || '(set)') : null;
    const now = [mark, drawn('.kp-off'), drawn('.kp-again'),
                 drawn('.kp-wait'), !!window.ParsehKeep && !!window.__dcl];
    const key = JSON.stringify(now);
    if (key !== last) { last = key; window.__seen.push([Math.round(performance.now())].concat(now)); }
    setTimeout(look, 25);
  })();
};
const AWAY = 1, OFF = 2, AGAIN = 3, WAIT = 4, KEPT_UP = 5;     // the columns of a sample

/* HOW MANY ASKS OF THE ONE QUESTION THE PAGE HAS OUT AT ONCE, counted by the page: its own fetch of /__activity, from the
   call to the answer or the abort, kept (the most there ever were) in the tab's sessionStorage, which outlives the
   documents the tab walks through.  The page cuts an ask that has had no answer in fifteen seconds and asks again at
   once; counted from out here, in the browser's own events, the cut ask's `requestfailed` can reach the test after
   the next ask's `request` -- two "out at once" that were never both out -- and on a computer with a hundred other
   things to do it did, in four runs out of four. */
const COUNTER = () => {
  try {
    const real = window.fetch;
    let open = 0;
    window.fetch = function (input) {
      let url = '';
      try { url = typeof input === 'string' ? input : (input && input.url) || String(input); } catch (e) { /* none */ }
      if (!/\/__activity(\?|$)/.test(url)) return real.apply(this, arguments);
      open++;
      try { sessionStorage.setItem('parseh_test_most', String(Math.max(+sessionStorage.getItem('parseh_test_most') || 0, open))); } catch (e) { /* none */ }
      const done = () => { open = Math.max(0, open - 1); };
      const p = real.apply(this, arguments);
      p.then(done, done);
      return p;
    };
  } catch (e) { /* none */ }
};
const mostAtOnce = page => page.evaluate(() => +sessionStorage.getItem('parseh_test_most') || 0);

// every ask of the one question this page makes, and how many were out at once
function countAsks(page) {
  const a = {all: 0, open: 0, most: 0, failed: 0, answered: 0};
  const mine = r => { try { return new URL(r.url()).pathname === '/__activity'; } catch (e) { return false; } };
  page.on('request', r => { if (!mine(r)) return; a.all++; a.open++; a.most = Math.max(a.most, a.open); });
  page.on('requestfinished', r => { if (mine(r)) { a.open = Math.max(0, a.open - 1); a.answered++; } });
  page.on('requestfailed', r => { if (mine(r)) { a.open = Math.max(0, a.open - 1); a.failed++; } });
  return a;
}
async function phone(b = browser, opts = PHONE) {
  const ctx = await b.newContext(opts);
  await ctx.addInitScript(SAMPLER);
  await ctx.addInitScript(COUNTER);
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push(e.message); console.log('PAGE ERROR', e.message); });
  if (opts.hasTouch) {
    page.touch = await ctx.newCDPSession(page);
    await page.touch.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 1});
  }
  page.asks = countAsks(page);
  return page;
}
const state = page => page.evaluate(() => {
  const h = document.documentElement;
  const drawn = sel => [...document.querySelectorAll(sel)].some(e => e.getClientRects().length > 0);
  const A = window.ParsehActivity;
  let memory = null;
  try { memory = JSON.parse(localStorage.getItem('parseh_away') || 'null'); } catch (e) { /* none */ }
  return {away: h.hasAttribute('data-parseh-away') ? (h.getAttribute('data-parseh-away') || '(set)') : null,
          reach: A && A.reach ? A.reach() : null,
          off: drawn('.kp-off'), again: drawn('.kp-again'), wait: drawn('.kp-wait'), memory,
          nav: (performance.getEntriesByType('navigation')[0] || {}).type || null};
});
const confirmed = () => document.documentElement.getAttribute('data-parseh-away') === 'confirmed' &&
  window.ParsehActivity ? window.ParsehActivity.reach() : null;
// online, by the page's one question -- or, on a page from before there was
// one (which is how this file is proved to fail on the fault it is for), by
// lib/keep.js having started and put no mark up
const there = () => {
  const A = window.ParsehActivity;
  if (A && A.reach) return A.reach().state === 'there' ? A.reach() : null;
  return window.ParsehKeep && !document.documentElement.hasAttribute('data-parseh-away') ? {state: 'there'} : null;
};

/* THE APP, as a phone opens it: its own start address in the mobile mode,
   with the worker in charge and the way in kept (lib/sw.js, `warm`), so
   that the pages below open from the phone when the computer is gone --
   and the one question answered once. */
async function app(page, at = '/?mode=mobile') {
  await page.goto(B + at);
  await page.evaluate(() => navigator.serviceWorker.ready);
  if (!(await page.evaluate(() => !!navigator.serviceWorker.controller))) await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, {timeout: 20000});
  const ready = await page.evaluate(() => new Promise((ok, no) => {
    const sw = navigator.serviceWorker;
    const heard = e => {
      const d = e.data || {};
      if (!d.warmed || d.warmed.what !== 'way-in') return;
      sw.removeEventListener('message', heard);
      ok(d.warmed);
    };
    sw.addEventListener('message', heard);
    sw.controller.postMessage({warm: 'way-in'});
    setTimeout(() => no(new Error('the way in was never warmed')), 120000);
  }));
  if (!(ready.of > 10)) throw Error('the way in was not kept: ' + JSON.stringify(ready));
  await until(page, there, null, 20000);
}

// ======== refused: the computer switched off ========
async function partRefused() {
  console.log('\n== SWITCHED OFF: the server stopped, the socket refused');
  const page = await phone();
  await app(page);
  let st = await state(page);
  eq([st.away, st.off, st.wait], [null, false, false], 'with the computer there the page says nothing about it');
  const t0 = Date.now(), failedBefore = page.asks.failed;
  await hubStop();
  const said = await until(page, confirmed, null, 30000);
  const took = Date.now() - t0;
  st = await state(page);
  assert(took < 15000, `a computer that refuses is offline promptly: ${took} ms after it stopped`);
  eq(said.why, 'refused', 'and it was the refusals that said so');
  assert(page.asks.failed - failedBefore >= 3,
         `after three refusals in a row, not one: ${page.asks.failed - failedBefore} asks failed`);
  eq([st.off, st.again], [true, true], 'the page says so: the offline chip, and ↻ beside it');
  eq([st.memory && st.memory.away, st.memory && st.memory.why], [true, 'refused'],
     'and writes it down for the page that comes next');
  // A WRITE ON A PAGE THAT KNOWS fails at once, and says why
  const w = await page.evaluate(async () => {
    const t = performance.now();
    try { await Parseh.ask('/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}); return {ok: true}; }
    catch (e) { return {away: !!e.away, ms: Math.round(performance.now() - t)}; }
  });
  assert(w.away && w.ms < 200, 'a write asked of a page that confirmed the computer away fails at once: ' + JSON.stringify(w));
  // AND IT STAYS THE OFFLINE VERSION WHILE IT IS OPEN (§19), whatever the computer does
  await hubStart();
  // an away page still asks, every fifteen seconds, for the page after it
  await until(page, () => { try { return JSON.parse(localStorage.getItem('parseh_away')).away === false; } catch (e) { return false; } },
              null, 30000);
  st = await state(page);
  eq([st.away, st.off], ['confirmed', true],
     'with the computer back the page stays the offline version it became: it does not flip mid-use');
  eq(st.memory.away, false, 'while what it writes down for the next page is what the question found: there');
  await page.context().close();
}

// ======== silent: the computer that answers nothing ========
async function partSilent() {
  console.log('\n== UNREACHABLE: the server suspended, the socket open, nothing answered');
  const page = await phone();
  await app(page);
  const t0 = Date.now(), asked = page.asks.all;
  const p0 = await page.evaluate(() => performance.now());
  freeze();
  try {
    await until(page, () => [...document.querySelectorAll('.kp-wait')].some(e => e.getClientRects().length),
                null, 15000);
    const tWait = Date.now() - t0;
    let st = await state(page);
    assert(st.away === null && !st.off && st.reach.state === 'slow',
           `silence is not offline: ${tWait} ms in, the page says "checking…" and is online`);
    await sleep(Math.max(0, 30000 - (Date.now() - t0)));
    st = await state(page);
    eq([st.away, st.off, st.wait], [null, false, true], 'half a minute of silence is still not offline');
    const said = await until(page, confirmed, null, 45000);
    const took = Date.now() - t0;
    assert(took >= 44000 && took < 65000, `offline only after the long window: ${took} ms of silence`);
    eq(said.why, 'silent', 'and it was the silence that said so');
    assert(page.asks.all - asked >= 3, `having asked more than once: ${page.asks.all - asked} asks into the silence`);
    const most = await mostAtOnce(page);
    assert(most <= 1, `one ask at a time, never a pile of them: at most ${most} out at once`);
    st = await state(page);
    eq([st.off, st.again, st.wait], [true, true, false], 'then the offline chip and ↻, and "checking…" gone');
    const seen = await page.evaluate(() => window.__seen);
    const early = seen.filter(s => (s[AWAY] || s[OFF]) && s[0] < p0 + 44000);
    eq(early.length, 0, 'and not one moment of it earlier: ' + JSON.stringify(early.slice(0, 3)));
  } finally { thaw(); }
  await page.context().close();
}

// ======== slow: every answer late, and real ========
async function partSlow() {
  console.log('\n== MERELY SLOW: the server held still for eight seconds at a time, every answer late and real');
  const page = await phone();
  await app(page);
  /* A person using it while it is slow: the shelf, the kept page, back to the
     hub, a write -- for two minutes, with the computer answering everything
     between one and eight and a half seconds late.  The old probe gave three
     seconds and read the silence as away; not one moment of offline is
     allowed here. */
  let run = true;
  const cycle = (async () => {
    while (run) { freeze(); await sleep(8000); if (!run) break; thaw(); await sleep(400); }
  })();
  const t0 = Date.now();
  const seenAll = [];
  let writes = 0, walked = 0, sawWait = false;
  try {
    const walk = ['/m/books/', '/?mode=mobile', '/m/kept/', '/m/videos/'];
    for (let i = 0; Date.now() - t0 < 120000; i++) {
      let went = null;                           // how the walk to this page ended, if it did not end well
      const began = Date.now();
      await page.goto(B + walk[i % walk.length], {waitUntil: 'domcontentloaded', timeout: 60000})
        .catch(e => { went = e.message.split('\n')[0] + ' after ' + (Date.now() - began) + ' ms'; });
      walked++;
      // a write while it is slow: waited for, never refused
      const w = await page.evaluate(async () => {
        try {
          const r = await Parseh.ask('/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
          return {status: r.status};
        } catch (e) { return {failed: e.message, away: !!e.away}; }
      }).catch(e => ({failed: e.message}));
      if (w.status) writes++;
      else if (w.away) {
        // said with what else is known: a write that fails because its page was being left (the walk to it ended in an
        // error, or the page was still loading) is not the page calling a slow computer away
        const where = await page.evaluate(() => ({url: location.href, ready: document.readyState, online: navigator.onLine,
          nav: (performance.getEntriesByType('navigation')[0] || {}).type, up: Math.round(performance.now())})).catch(e => String(e));
        throw Error('FAIL: a write on a slow computer was refused as away: ' + JSON.stringify(w) + '; the walk to the page: ' +
                    (went || 'arrived') + '; the page: ' + JSON.stringify(where) + '; frozen now: ' + frozen);
      }
      await sleep(12000);
      const seen = await page.evaluate(() => window.__seen).catch(() => []);
      seenAll.push(...seen);
      if (seen.some(s => s[WAIT])) sawWait = true;
      const offline = seen.filter(s => s[AWAY] || s[OFF]);
      if (offline.length)
        throw Error('FAIL: a slow computer was called offline on ' + walk[i % walk.length] + ': ' +
                    JSON.stringify(offline.slice(0, 4)));
    }
  } finally { run = false; await cycle; thaw(); }
  const st = await state(page);
  assert(seenAll.length > 0 && !seenAll.some(s => s[AWAY] || s[OFF]),
         `two minutes of late answers, ${walked} pages walked: never offline, not for a moment ` +
         `(${seenAll.length} changes of state watched)`);
  assert(writes > 0, `and the writes made meanwhile were waited for and answered: ${writes} of ${walked}`);
  assert(sawWait, 'while "checking…" said, quietly, that the answers were slow');
  eq(st.memory && st.memory.away, false, 'nothing written down for the next page but "there"');
  const most = await mostAtOnce(page);
  assert(most <= 1, `one ask of the question at a time throughout: at most ${most} out at once`);
  await page.context().close();
}

// ======== no network ========
async function partNoNetwork() {
  console.log('\n== NO NETWORK: the browser says so, and an ask fails');
  const page = await phone();
  await app(page);
  const t0 = Date.now();
  await page.context().setOffline(true);
  const said = await until(page, confirmed, null, 10000, 50);
  const took = Date.now() - t0;
  assert(took < 3000, `no network and a failed ask is offline at once: ${took} ms`);
  eq(said.why, 'no network', 'and it was the browser\'s "no network" with the ask that failed');
  await page.context().setOffline(false);
  await sleep(1500);
  eq((await state(page)).away, 'confirmed', 'the network back, the page is still the offline version it became');
  await page.context().close();
}

// ======== writes: an assumed away refuses none ========
async function partWrites() {
  console.log('\n== WRITES: an away the page before found is not one this page knows');
  const ctx = await browser.newContext(PHONE);
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('parseh_mode', 'mobile');
      // the page before found the computer away a moment ago -- and it is back
      localStorage.setItem('parseh_away', JSON.stringify({at: Date.now() / 1000, away: true, trusted: 180,
                                                          why: 'refused'}));
    } catch (e) { /* no storage: said below */ }
    // the question held back until the test lets it go, so that the page is
    // caught in its first breath however long it takes to load
    const real = window.fetch;
    window.fetch = function (input, init) {
      const u = String((input && input.url) || input || '');
      if (!/\/__activity/.test(u)) return real.call(this, input, init);
      return new Promise(ok => {
        const go = () => window.__letGo ? ok(real.call(window, input, init)) : setTimeout(go, 50);
        go();
      });
    };
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => { errors.push(e.message); console.log('PAGE ERROR', e.message); });
  await page.goto(B + '/m/books/');
  eq(await page.evaluate(() => document.documentElement.getAttribute('data-parseh-away')), 'assumed',
     'the page opens on what the page before found, and says it only assumes it');
  const w = await page.evaluate(async () => {
    try {
      const r = await Parseh.ask('/__prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      return {status: r.status, still: document.documentElement.getAttribute('data-parseh-away')};
    } catch (e) { return {refused: e.message, away: !!e.away}; }
  });
  assert(w.status && w.still === 'assumed',
         'a write pressed in that first breath goes to the computer, which answers it: ' + JSON.stringify(w));
  await page.evaluate(() => { window.__letGo = true; });
  await until(page, () => !document.documentElement.hasAttribute('data-parseh-away'), null, 20000);
  assert(true, 'and the question corrects the page once it is answered');
  // the studio's own pages, the same
  await page.goto(B + `/exercises/deck/${MADE.decks.en.folder}/${MADE.decks.en.slug}/`);
  const d = await page.evaluate(async () => {
    const was = document.documentElement.getAttribute('data-parseh-away');
    try { await api('/api/decks/__nothing__/__nothing__/items', {method: 'POST', json: {}}); return {was, done: true}; }
    catch (e) { return {was, status: e.status || 0, away: !!e.away, message: e.message}; }
  });
  assert(d.was === 'assumed' && !d.away && d.status > 0,
         'a deck page\'s write in its first breath reaches the computer too: ' + JSON.stringify(d));
  await page.evaluate(() => { window.__letGo = true; });
  await ctx.close();
}

// ======== refresh: the fall-back ========
/* The owner, 2026-09-24: "A very good fall-back would be that if we refresh
   the page, then it is forced to check again if the computer is online -- so
   upon refreshing, do not assume still offline."  Driven with the computer
   really gone, then really back; on the hub and on a page the worker
   answers from its own cache; and the opposite -- refreshed while the
   computer is still gone -- which must come up offline again without a
   moment of looking online in between. */
async function partRefresh() {
  console.log('\n== REFRESH: a page opened afresh never inherits what the page before found');
  const page = await phone();
  await app(page);
  const pageLooksOnline = s => !s[AWAY] && !s[OFF] && !s[WAIT];

  for (const at of ['/?mode=mobile', '/m/kept/']) {
    await page.goto(B + at);
    await until(page, there, null, 20000);
    // ---- a) offline, for real
    await hubStop();
    await until(page, confirmed, null, 30000);
    // ---- b) the computer back; REFRESH
    await hubStart();
    const t0 = Date.now();
    await page.reload();
    const back = await until(page, there, null, 15000);
    const took = Date.now() - t0;
    let st = await state(page);
    const seen = await page.evaluate(() => window.__seen);
    eq(st.nav, 'reload', `${at}: the browser says this page was refreshed`);
    if (at === '/m/kept/')
      eq(await page.evaluate(() => performance.getEntriesByType('navigation')[0].deliveryType), 'cache-storage',
         `${at}: and the worker answered it from its own cache`);
    assert(back && took < 10000 && !seen.some(s => s[AWAY] || s[OFF]),
           `${at}: refreshed with the computer back, it comes up online in ${took} ms, having taken up ` +
           'nothing of the offline state it had: ' + JSON.stringify(seen.slice(0, 6)));
    eq([st.away, st.off, st.memory.away], [null, false, false], `${at}: online, and written down so`);
    // ---- c) the opposite: offline again, and REFRESHED while the computer is still gone
    await hubStop();
    await until(page, confirmed, null, 30000);
    const t1 = Date.now();
    await page.reload();
    const again = await until(page, confirmed, null, 20000);
    const took2 = Date.now() - t1;
    const seen2 = await page.evaluate(() => window.__seen);
    st = await state(page);
    eq([st.nav, again.why], ['reload', 'refused'], `${at}: refreshed with the computer still gone`);
    assert(took2 < 15000, `${at}: it is offline again promptly: ${took2} ms`);
    const flicker = seen2.filter(s => s[KEPT_UP] && pageLooksOnline(s));
    assert(!flicker.length && !seen2.some(s => s[AWAY] === 'assumed'),
           `${at}: without a moment of looking online in between -- "checking…" until it knew -- and ` +
           'without taking up the memory: ' + JSON.stringify(seen2.slice(0, 8)));
    await hubStart();
  }

  // ---- d) ↻ BESIDE THE CHIP: the same refresh, for a phone with no other way
  await page.goto(B + '/?mode=mobile');
  await until(page, there, null, 20000);
  await hubStop();
  await until(page, confirmed, null, 30000);
  await hubStart();
  await Promise.all([page.waitForEvent('load'), page.locator('.kp-again').first().tap()]);
  await until(page, there, null, 15000);
  const st = await state(page);
  eq([st.nav, st.away, st.off], ['reload', null, false], '↻ opens the page afresh, and it comes up online');

  // ---- e) and the silent kind: offline after the window, refreshed while still silent
  freeze();
  try {
    await until(page, confirmed, null, 75000, 250);
    const t2 = Date.now();
    await page.reload({waitUntil: 'domcontentloaded', timeout: 60000});
    await until(page, () => [...document.querySelectorAll('.kp-wait')].some(e => e.getClientRects().length),
                null, 10000);
    const early = Date.now() - t2;
    const said = await until(page, confirmed, null, 75000, 250);
    const took3 = Date.now() - t2;
    const seen3 = await page.evaluate(() => window.__seen);
    assert(early < 5000 && took3 >= 44000 && said.why === 'silent',
           `refreshed while the computer is SILENT: "checking…" at once (${early} ms), offline again only ` +
           `after the window (${took3} ms) -- silence can only be told from slowness by time`);
    assert(!seen3.some(s => s[KEPT_UP] && pageLooksOnline(s)),
           'and never a moment of looking online in between: ' + JSON.stringify(seen3.slice(0, 8)));
  } finally { thaw(); }
  await page.context().close();
}

// ======== drag: a finger pulling the page down ========
/* In the installed app there is no browser around the page -- the manifest
   asks for the whole screen -- so on Android the pull-down is the only way a
   person refreshes anything.  Chromium's own pull-to-refresh is switched on
   here and fed raw touch points through the real touch path; a pull at the
   top of the page is a reload, and the page it opens reads "reload" from
   its first line.  This is the desktop build's gesture, not Android's: what
   it proves is the page's side -- that nothing on it swallows the pull, and
   that the refresh is recognised -- and his own phone is the proof of the
   rest.  Then every kind of page is pulled, to say where a person cannot. */
async function drag(page, from = 200, to = 780) {
  const t = page.touch;
  const high = (page.viewportSize() || {height: 844}).height;
  to = Math.min(to, high - 10);
  from = Math.min(from, Math.round(high / 4));
  await t.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: 195, y: from}]});
  for (let y = from + 15; y <= to; y += 15) {
    await t.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: 195, y}]});
    await sleep(16);
  }
  await t.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
}
async function pulled(page, from) {
  await page.evaluate(() => { window.__before = 1; scrollTo(0, 0); });
  await sleep(300);
  await drag(page, from);
  for (let i = 0; i < 40; i++) {
    await sleep(100);
    const gone = await page.evaluate(() => window.__before === undefined && document.readyState !== 'loading')
      .catch(() => false);
    if (gone) return (await state(page)).nav;
  }
  return null;
}
async function partDrag() {
  console.log('\n== THE DRAG: a finger pulling the page down, in the touch path');
  const pull = await chromium.launch({executablePath: CHROME, headless: true, args: ['--pull-to-refresh=1']});
  try {
    const page = await phone(pull, {viewport: {width: 390, height: 844}, hasTouch: true});
    await app(page);
    // ---- a) offline for real, the computer back: PULL, and it is online
    await hubStop();
    await until(page, confirmed, null, 30000);
    await hubStart();
    eq(await pulled(page), 'reload', 'a pull at the top of the page refreshes it');
    await until(page, there, null, 15000);
    let st = await state(page);
    const seen = await page.evaluate(() => window.__seen);
    assert(!seen.some(s => s[AWAY] || s[OFF]) && st.away === null,
           'and, the computer back, it comes up online, having taken up nothing: ' + JSON.stringify(seen.slice(0, 6)));
    // ---- b) offline, the computer still gone: PULL, and "checking…" then offline
    await hubStop();
    await until(page, confirmed, null, 30000);
    eq(await pulled(page), 'reload', 'pulled again, with the computer still gone');
    await until(page, confirmed, null, 20000);
    const seen2 = await page.evaluate(() => window.__seen);
    assert(!seen2.some(s => s[KEPT_UP] && !s[AWAY] && !s[OFF] && !s[WAIT]) && !seen2.some(s => s[AWAY] === 'assumed'),
           'offline again, with "checking…" until it knew and never a moment online: ' + JSON.stringify(seen2.slice(0, 8)));
    await hubStart();

    /* ---- c) EVERY KIND OF PAGE, PULLED.  The owner asked to be told where a
       person simply cannot refresh, since on such a page the fall-back does
       not exist.  What must refresh is asserted; what cannot is said. */
    const en = MADE.decks.en;
    // [name, address, what to press first, and the proof that it was pressed]
    // a book's reader has the gear, whose sheet is not in the header (a0.5.0)
    const READER_GEAR_UP = () => { const p = document.querySelector('.pg-panel'); return !!p && !p.hidden; };
    const OPEN = () => !!document.querySelector('header.m-more');
    // a video has no ⋯ any more (a0.5.0): its gear opens a sheet from the foot, which html wears while it is up
    const GEAR_UP = () => document.documentElement.classList.contains('pg-sheet');
    const FULL = () => document.documentElement.classList.contains('m-vfullon');
    const SIDE = {width: 844, height: 390}, UP = {width: 390, height: 844};
    const pages = [
      ['the hub', '/?mode=mobile'],
      ['the book shelf', '/m/books/'],
      ['the videos shelf', '/m/videos/'],
      ['kept on this phone', '/m/kept/'],
      ['the exercises', '/exercises/'],
      ['a deck', `/exercises/deck/${en.folder}/${en.slug}/`],
      ['a deck, crammed', `/exercises/deck/${en.folder}/${en.slug}/cram`],
      ['a book\'s reader', MADE.readers.en],
      ['a book\'s reader, the gear open', MADE.readers.en, '[data-parseh-gear]', READER_GEAR_UP],
      ['a book\'s reader, the gear open, sideways', MADE.readers.en, '[data-parseh-gear]', READER_GEAR_UP, SIDE],
      ['a video', `/youtube/v/${MADE.video}/`],
      ['a video, the gear open', `/youtube/v/${MADE.video}/`, 'header > button.pg-gear', GEAR_UP],
      // ⛶ is there only sideways: upright a video on the whole screen leaves nothing to read
      ['a video on the whole screen, sideways', `/youtube/v/${MADE.video}/`, '.m-vfull', FULL, SIDE],
    ];
    const must = new Set(['the hub', 'the book shelf', 'the videos shelf', 'kept on this phone',
                          'the exercises', 'a deck', 'a book\'s reader', 'a video']);
    const cannot = [];
    for (const [name, at, open, proof, size] of pages) {
      await page.setViewportSize(size || UP);
      await page.goto(B + at);
      await until(page, there, null, 20000);
      await page.evaluate(() => new Promise(r => setTimeout(r, 300)));
      // the reading place is asked about on a device that has not read here
      if (await page.$('.pf-bar')) await page.locator('.pf-stay').first().tap().catch(() => {});
      if (open) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.locator(open).first().tap().catch(() => {});
        await sleep(600);
        // the survey says nothing about a state it never reached
        assert(await page.evaluate(proof), `${name}: pressed, and it is so`);
      }
      // where the finger lands, and whether what it lands on scrolls by itself:
      // an open ⋯ panel taller than the screen keeps a pull to itself
      const under = await page.evaluate(y => {
        const e = document.elementFromPoint(195, y);
        const panel = e && e.closest && e.closest('header.m-more, .pg-panel');
        return panel ? 'on the open panel, which ' + (panel.scrollHeight > panel.clientHeight + 1
                                                    ? 'scrolls' : 'does not scroll')
                     : 'on ' + (e ? e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') : 'nothing');
      }, Math.min(200, Math.round(((page.viewportSize() || {height: 844}).height) / 4)));
      const how = await pulled(page);
      console.log(`     ${how === 'reload' ? 'refreshes ' : 'CANNOT    '} ${name} (the finger ${under})`);
      if (how !== 'reload') cannot.push(name);
      if (must.has(name)) eq(how, 'reload', `${name}: a pull at the top refreshes it`);
    }
    await page.setViewportSize(UP);
    console.log('  pages where a pull refreshes nothing: ' + (cannot.length ? cannot.join('; ') : 'none'));
    await page.context().close();
  } finally { await pull.close(); }
}

// ======== nav: a page nobody kept, followed while the computer is slow, silent, away or gone ========
/* Every case is the same link from the same page -- the hub, with a live
   verdict, the worker in control -- to a document nobody has kept, and only
   what is at the other end of the wire changes.  What is measured is when
   the new page COMMITS and which page it is: the document, or the one that
   says Parseh cannot be reached.  `fromServiceWorker` says that the worker
   was the one that answered, so a page the browser fetched by itself is never
   mistaken for one the worker let through.

   The worker's constants are read from lib/sw.js, so that a test of its
   deadlines follows them. */
async function partNav() {
  console.log('\n== A PAGE NOBODY KEPT, followed from a page that is open: at its deadline the worker asks the page');
  const sw = await Deno.readTextFile('lib/sw.js');
  const k = name => +new RegExp('const ' + name + ' = (\\d+);').exec(sw)[1];
  const DEADLINE = k('DEADLINE'), PATIENT = k('PATIENT'), ASKED = k('ASKED');
  const stamp = String(Date.now() % 100000);
  const doc = async title => {
    const m = await (await fetch(B + '/studio/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: `---\ntitle: ${title} ${stamp}\nlang: en\ntarget: it\n---\n\nA page nobody kept.\n`})})).json();
    if (!(m.meta && m.meta.id)) throw Error('FAIL: no document made: ' + JSON.stringify(m));
    return m.meta.id;
  };
  // how often the computer was asked for that document's page (the harness writes each ask down)
  const asked = async id => (await Deno.readTextFile(WORK + '/page-asked').catch(() => ''))
    .split('\n').filter(l => l.startsWith(id + ' ')).length;
  const page = await phone();
  /* HOW MANY ASKS OF THE QUESTION WERE OUT AT ONCE, counted in each page itself:
     the page's poll must stay the one asker, one ask at a time, whoever is
     waiting for its answer.  (Counted from out here, an ask that a page
     abandons by being navigated away would stay "open" for ever.) */
  const most = {n: 0};
  await page.exposeFunction('__concurrent', n => { most.n = Math.max(most.n, n); });
  await page.context().addInitScript(() => {
    let out = 0;
    const real = window.fetch;
    window.fetch = function (input) {
      if (!/\/__activity/.test(String((input && input.url) || input || ''))) return real.apply(this, arguments);
      out++;
      try { window.__concurrent(out); } catch (e) { /* not bound yet */ }
      const done = () => { out--; };
      const asking = real.apply(this, arguments);
      asking.then(done, done);
      return asking;
    };
  });
  await app(page);
  const worker = page.context().serviceWorkers()[0];
  const home = async () => { await page.goto(B + '/?mode=mobile'); await until(page, there, null, 20000); };
  // the worker's own question, asked directly: what the pages say, and how soon
  const probe = () => worker.evaluate(async () => {
    const t = performance.now();
    const answering = await computerAnswers();
    return {answering, ms: Math.round(performance.now() - t)};
  });
  /* THE LINK, FOLLOWED FROM THE PAGE (`link`) -- the page itself moves, as a
     link does -- or typed where no page of Parseh's is open (`typed`).  A page
     whose navigation is pending cannot be asked anything from outside, so
     nothing is asked of it until the new page has committed. */
  const follow = async (path, how = 'link') => {
    const moves = [];
    let workerAnswered = null;
    const moved = f => { if (f === page.mainFrame()) moves.push(f.url().slice(B.length)); };
    const responded = r => {
      if (workerAnswered === null && r.request().isNavigationRequest() && r.frame() === page.mainFrame())
        workerAnswered = r.fromServiceWorker();
    };
    page.on('framenavigated', moved);
    page.on('response', responded);
    const arrived = page.waitForEvent('framenavigated', {timeout: 90000});
    const t0 = Date.now();
    if (how === 'link') await page.evaluate(p => { location.href = p; }, path);
    else page.goto(B + path, {waitUntil: 'commit', timeout: 90000}).catch(() => {});
    await arrived;
    const ms = Date.now() - t0;
    await page.waitForLoadState('domcontentloaded');
    const here = await page.evaluate(() => ({title: document.title, h1: (document.querySelector('h1') || {}).textContent || ''}));
    page.off('framenavigated', moved);
    page.off('response', responded);
    return {ms, offline: here.h1 === 'Parseh cannot be reached', title: here.title, moves, workerAnswered};
  };
  // a socket that accepts and never answers, on the port the computer had: silence, from a
  // computer the page has already judged gone
  const silentSocket = () => {
    const held = [];
    const listener = Deno.listen({hostname: '127.0.0.1', port});
    (async () => { try { for await (const c of listener) held.push(c); } catch (_) { /* closed */ } })();
    return () => { listener.close(); held.forEach(c => { try { c.close(); } catch (_) { /* gone */ } }); };
  };
  const said = r => JSON.stringify(r);

  // ---- a) ALIVE, AND SIX SECONDS SLOW: the page opens -- once, and with no offline page on the way
  const slow = await doc('Slow to make');
  await home();
  const live = await probe();
  assert(live.answering && live.ms < ASKED,
         `the worker asks the open page whether the computer answers, and it says so: ${live.ms} ms`);
  await Deno.writeTextFile(WORK + '/page-delay', '6');
  let r = await follow('/studio/doc/' + slow);
  assert(!r.offline && r.title.startsWith('Slow to make') && r.workerAnswered === true && r.ms >= 5900 && r.ms < 8500,
         `a computer alive and six seconds slow: the page opens, after ${r.ms} ms, answered by the worker -- ${said(r)}`);
  assert(r.moves.length === 1 && !r.offline && r.moves[0].startsWith('/studio/doc/slow-to-make'),
         'the page moved once, straight to the document, and never through the offline page: ' + said(r.moves));
  eq(await asked(slow), 1, 'and the computer was asked for the page once: the worker waited for its own ask');
  await Deno.remove(WORK + '/page-delay');

  // ---- b) THE PAGE HAS JUDGED THE COMPUTER AWAY, and what answers is silence: the deadline, no more
  const away = await doc('Away');
  await home();
  await hubStop();
  const judged = await until(page, confirmed, null, 30000);
  eq(judged.why, 'refused', 'the computer switched off: the page has judged it away');
  const stopSilent = silentSocket();
  try {
    const told = await probe();
    assert(!told.answering && told.ms < 500, `asked, the page says away at once: ${told.ms} ms`);
    r = await follow('/studio/doc/' + away);
    assert(r.offline && r.workerAnswered === true && r.ms >= DEADLINE - 50 && r.ms < DEADLINE + 900,
           `the page away, the socket silent: the offline page at the deadline (${r.ms} ms)`);
  } finally { stopSilent(); }
  await hubStart();

  // ---- c) SILENT: suspended, the port open and nothing answered, the page still thinking it is there
  const silent = await doc('Silent');
  await home();
  freeze();
  try {
    const told = await probe();
    assert(!told.answering && told.ms >= ASKED - 100 && told.ms < ASKED + 700,
           `asked, the page hears nothing from a computer suspended a moment ago, and says no after ${told.ms} ms`);
    r = await follow('/studio/doc/' + silent);
    assert(r.offline && r.workerAnswered === true && r.ms >= DEADLINE + ASKED - 100 && r.ms < DEADLINE + ASKED + 900,
           `the computer suspended: the offline page after the deadline and one question (${r.ms} ms), ` +
           `far below the long deadline of ${PATIENT} ms`);
  } finally { thaw(); }

  // ---- d) REFUSED: at once, as ever
  const refused = await doc('Refused');
  await home();
  await hubStop();
  r = await follow('/studio/doc/' + refused);
  assert(r.offline && r.workerAnswered === true && r.ms < 1000,
         `the computer switched off: the offline page at once (${r.ms} ms), the page still saying it is there`);
  await hubStart();

  // ---- e) NO PAGE OF PARSEH'S IS OPEN: nobody to ask, the offline page at the deadline, as it was
  const fresh = await doc('Fresh tab');
  await Deno.writeTextFile(WORK + '/page-delay', '6');
  await page.goto('about:blank');
  r = await follow('/studio/doc/' + fresh, 'typed');
  assert(r.offline && r.workerAnswered === true && r.ms >= DEADLINE - 50 && r.ms < DEADLINE + 900,
         `a link typed where no page of Parseh's is open, a computer six seconds slow: the offline page at the ` +
         `deadline (${r.ms} ms)`);
  // ... but another tab of Parseh that is in sight answers for it
  const other = await doc('Another tab');
  await home();
  const tab = await page.context().newPage();
  const t1 = Date.now();
  await tab.goto(B + '/studio/doc/' + other, {waitUntil: 'commit', timeout: 90000});
  await tab.waitForLoadState('domcontentloaded');
  const second = await tab.evaluate(() => ({title: document.title, h1: (document.querySelector('h1') || {}).textContent || ''}));
  assert(second.title.startsWith('Another tab') && Date.now() - t1 >= 5900,
         `and with another tab of Parseh open, in sight, the same link opens (${Date.now() - t1} ms): ${second.title}`);
  await tab.close();
  await Deno.remove(WORK + '/page-delay');

  // ---- f) A STALE VERDICT IS NOT ONE: the page says there, and cannot say it now
  const stale = await doc('Stale');
  await home();
  await Deno.writeTextFile(WORK + '/page-delay', '6');
  // headless Chromium keeps every tab in sight, so what a tab behind another gives its page is given
  // to it: the page's own code then stops asking, and what it last found stays what it says it found
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
    document.dispatchEvent(new Event('visibilitychange'));
  });
  eq(await page.evaluate(() => window.ParsehActivity.reach().state), 'there', 'the page holds the verdict it had: there');
  const hidden = await probe();
  assert(!hidden.answering && hidden.ms >= ASKED - 100,
         `a page that has stopped asking cannot say that the computer answers now: no, after ${hidden.ms} ms`);
  r = await follow('/studio/doc/' + stale);
  assert(r.offline && r.workerAnswered === true && r.ms >= DEADLINE + ASKED - 100 && r.ms < DEADLINE + ASKED + 900,
         `a computer alive and slow, a page whose verdict is only old: the offline page after the deadline and ` +
         `one question (${r.ms} ms)`);
  await Deno.remove(WORK + '/page-delay');

  // ---- h) A DOWNLOAD MADE ON DEMAND is still not the worker's: the browser waits for it, the page stays
  const made = await doc('Made on demand');
  await home();
  await Deno.writeTextFile(WORK + '/export-delay', '4');
  let served = null;
  const onDownload = res => { if (/\/download\//.test(res.url())) served = res.fromServiceWorker(); };
  page.on('response', onDownload);
  const t2 = Date.now();
  const [file] = await Promise.all([page.waitForEvent('download', {timeout: 60000}),
                                    page.evaluate(p => { location.href = p; }, '/studio/download/' + made + '/html')]);
  const took = Date.now() - t2;
  page.off('response', onDownload);
  await Deno.remove(WORK + '/export-delay');
  assert(took >= 3900 && served === false && /\.html$/.test(file.suggestedFilename()),
         `a document's HTML page, followed as a link, is made and given after ${took} ms by the browser, ` +
         `not the worker (${file.suggestedFilename()})`);
  eq(await page.evaluate(() => location.pathname), '/', 'and the page the person was on never left');

  // ---- g) A COMPUTER THAT ANSWERS AFTER THE LONG DEADLINE is given up on at it
  const late = await doc('Too late');
  await home();
  await Deno.writeTextFile(WORK + '/page-delay', String(PATIENT / 1000 + 4));
  r = await follow('/studio/doc/' + late);
  assert(r.offline && r.workerAnswered === true && r.ms >= PATIENT - 100 && r.ms < PATIENT + 1500,
         `a computer alive and ${PATIENT / 1000 + 4} seconds slow: the offline page at the long deadline (${r.ms} ms)`);
  eq(await asked(late), 1, 'and the computer was asked for the page once, in all those seconds');
  await Deno.remove(WORK + '/page-delay');
  assert(most.n === 1, `the page's poll stayed the one asker, one ask at a time, whoever was waiting for its answer: ` +
                       `at most ${most.n} out at once in any page`);
  await page.context().close();
}

const RUN = {refused: partRefused, silent: partSilent, slow: partSlow, nonet: partNoNetwork,
             writes: partWrites, refresh: partRefresh, drag: partDrag, nav: partNav};
let failed = null;
try {
  for (const p of PARTS) {
    if (!RUN[p]) throw Error('no such part: ' + p);
    if (!hubUp) await hubStart();
    if (frozen) thaw();
    await RUN[p]();
  }
  if (errors.length) throw Error('FAIL: errors on the pages: ' + errors.slice(0, 5).join(' | '));
} catch (e) {
  failed = e;
} finally {
  await browser.close();
  if (hubUp) { if (frozen) thaw(); hub.kill('SIGTERM'); await hub.status; }
  await Deno.remove(WORK, {recursive: true}).catch(() => {});
}
if (failed) {
  console.log('\n' + failed.message + '\n' + (failed.stack || '').split('\n').slice(1, 4).join('\n'));
  console.log(`\n${passed} passed, then a failure`);
  Deno.exit(1);
}
console.log(`\nall ${passed} passed`);
