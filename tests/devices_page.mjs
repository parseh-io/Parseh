// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Devices (a0.7.0, lane E: lib/devicespage.py, lib/syncpage.js) against Parseh's REAL
// server on a temporary tree (tests/devices_harness.py: every store in the tree, never the checkout's config/), with
// lane C's syncrules and lane D's syncjobs as the FAKES tests/syncrules_fake.py and tests/syncjobs_fake.py:
//   a) the hub has the door; the page lists this computer, the partner, the four questions, the jobs and the switches,
//      what is held, the version kept for a day, the diff file and the build out of date
//   b) pairing: "Show a code" shows the code, the addresses and a QR code; it can be thrown away
//   c) the banner on a document's page (a choice) and on a book's page (a deletion), and the out-of-date mark
//   d) the choice page: both sides, the diff each would throw away shown BEFORE pressing; keeping this computer's
//      offers the diff as a file AFTER, and the file is what was shown
//   e) a grouped deletion: one question with the list; "go through them" answers one; "delete them all" the rest
//   f) a switch, a job cancelled, a version put back, a diff file deleted -- each from the page
//   g) the studio editor holds its document while open and lets go when left; while a sync writes the document the
//      editor says so and opens by itself a moment later; a deck's options hold the deck while open
//   h) "make this computer identical": the summary first (counts, what is lost, jobs cancelled), then one button
//   i) 390 px wide: the door, the choice page's sides stacked, a deletion-edited answered there, no sideways scroll
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/devices_page.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(`FAIL: ${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`); assert(true, m); };
const has = (t, p, m) => { if (!String(t).includes(p)) throw Error(`FAIL: ${m} (wanted ${JSON.stringify(p)} in ${JSON.stringify(String(t).slice(0, 600))})`); assert(true, m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(80);
  }
}

const work = await Deno.makeTempDir({prefix: 'parseh-devices-page-'});
const port = 20000 + Math.floor(Math.random() * 20000);
const base = `http://127.0.0.1:${port}`;
const proc = new Deno.Command(python, {args: [root + '/tests/devices_harness.py', 'serve', work, String(port)], cwd: root,
  stdin: 'null', stdout: 'piped', stderr: 'piped'}).spawn();
const log = [];
for (const s of [proc.stdout, proc.stderr]) (async () => {
  const r = s.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); }
})();
const seeded = await until(() => { const l = log.join('').split('\n').find(x => x.startsWith('SEEDED ')); return l && JSON.parse(l.slice(7)); },
                           'the harness seeded the tree', 60000);
await until(async () => (await fetch(base + '/settings/api/ping')).ok, 'the server answers', 60000);
const api = async (route, body) => (await fetch(base + '/settings/api/devices/' + route, {method: 'POST',
  headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})})).json();

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), args: ['--no-sandbox']});
try {
  const ctx = await browser.newContext({acceptDownloads: true, viewport: {width: 1280, height: 900}});
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));

  // a) the door
  await p.goto(base + '/settings/');
  assert(await p.locator('a.door[href="/settings/devices/"]').count() === 1, 'the hub has a Devices door');
  await p.goto(base + '/settings/devices/');
  await p.waitForSelector('main[data-loaded]');
  eq(await p.locator('[data-name]').inputValue() !== '', true, 'this computer has a name in the box');
  has(await p.locator('[data-partner="p-laptop"]').textContent(), 'laptop', 'the partner is listed');
  assert(/does not answer now|not tried yet/.test(await p.locator('[data-partner="p-laptop"]').textContent()), 'with whether it answers');
  has(await p.locator('[data-partner="p-laptop"]').textContent(), 'last synced never', 'and when it last synced');
  eq(await p.locator('[data-questions] [data-q]').count(), 4, 'four questions wait');
  has(await p.locator('[data-q="q3"]').textContent(), '3 things deleted on laptop', 'the grouped one says how many');
  eq(await p.locator('[data-switch="send"]').isChecked(), false, 'send is off');
  eq(await p.locator('[data-switch="accept"]').isChecked(), false, 'accept is off');
  has(await p.locator('[data-cap]').textContent(), 'Whisper, LaTeX', 'what this computer can run');
  eq(await p.locator('[data-jobs] [data-job]').count(), 2, 'the jobs are listed');
  eq(await p.locator('[data-kept="k1"]').count(), 1, 'a version kept for a day');
  eq(await p.locator('[data-diffs] [data-diff]').count(), 1, 'a diff file');
  assert(await p.locator('[data-ood-section]').isVisible(), 'the out-of-date build is listed');
  eq(await p.locator('[data-hold-lang]').count() > 5, true, 'every language can be left out');
  eq(await p.locator('.sdoor.on').getAttribute('href'), '/settings/devices/', 'the door row marks Devices');
  has(await p.locator('.foot').textContent(), 'sync is not a backup', 'the foot says sync is not a backup');
  eq(await p.locator('.foot a').getAttribute('href'), '/guide/site/getting-started/several-computers.html', 'and links the guide page');

  // b) pairing
  await p.click('[data-pair-start]');
  await p.waitForSelector('[data-offer] [data-code]');
  assert(/^[A-Z0-9]{3}-[A-Z0-9]{3,4}$/.test((await p.locator('[data-offer] [data-code]').textContent()).trim()), 'a code is shown');
  assert(await p.locator('[data-offer] .qr svg path').count() === 1, 'with its QR code');
  assert(await p.locator('[data-offer] li.addr').count() >= 1, 'and the addresses to type with it');
  await p.click('[data-pair-stop]');
  await until(async () => (await api('state')).pairing === 0, 'the code was thrown away');
  assert(true, 'throwing the code away is a button');

  // c) the banner and the mark
  await p.goto(base + `/studio/doc/${seeded.doc}`);
  await p.waitForSelector('[data-sync-banner="choice"]');
  has(await p.locator('[data-sync-banner]').textContent(), 'changed here and on laptop', 'the document says a choice waits');
  eq(await p.locator('[data-sync-answer]').getAttribute('href'), '/settings/devices/question/q1', 'and links its question');
  await p.waitForSelector('[data-sync-ood]');
  has(await p.locator('[data-sync-ood]').textContent(), 'Out of date', 'the PDF is marked out of date');
  eq(await p.locator('[data-sync-ood] button[data-sync-rebuild]').textContent(), 'Build again', 'with the page’s own build behind a button');
  await p.goto(base + '/books/persian/demo/index.html');
  await p.waitForSelector('[data-sync-banner="deletion"]');
  has(await p.locator('[data-sync-banner]').textContent(), 'deleted on laptop', 'a book’s page says a deletion waits');

  // i) phone width: the door, the choice page stacked, and a deletion-edited answered there
  const phone = await browser.newContext({viewport: {width: 390, height: 800}, isMobile: true, hasTouch: true});
  const m = await phone.newPage();
  m.on('pageerror', e => errors.push(e.message));
  await m.goto(base + '/settings/devices/');
  await m.waitForSelector('main[data-loaded]');
  eq(await m.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, 'the door fits 390 px');
  await m.goto(base + '/settings/devices/question/q1');
  await m.waitForSelector('[data-question] .sides');
  const [bm, bt] = [await m.locator('[data-side="mine"]').boundingBox(), await m.locator('[data-side="theirs"]').boundingBox()];
  assert(bm.y + bm.height <= bt.y + 1, 'the two sides stand one above the other');
  eq(await m.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, 'the choice page fits 390 px');
  await m.goto(base + '/settings/devices/question/q4');
  await m.waitForSelector('[data-answer="send-edited"]');
  has(await m.locator('[data-answer="send-edited"]').textContent(), 'Send the edited version everywhere', 'deleted there, edited here: send it everywhere');
  has(await m.locator('[data-answer="delete"]').textContent(), 'Delete it everywhere', 'or delete it everywhere');
  const bb = await m.locator('[data-answer="send-edited"]').boundingBox();
  assert(bb.x >= 0 && bb.x + bb.width <= 390, 'the button is whole on the screen');
  await m.locator('[data-answer="send-edited"]').tap();
  await m.waitForSelector('[data-done="send-edited"]');
  eq((await api('overview')).questions.some(q => q.id === 'q4'), false, 'answered at phone width');
  eq(await m.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, 'still no sideways scroll');
  await phone.close();

  // d) the choice page
  await p.click('[data-sync-answer]');
  await p.waitForSelector('[data-question] [data-answer="delete"]');
  has(await p.locator('[data-answer="delete"]').textContent(), 'Delete it here too', 'its link opens the deletion: delete it here too');
  has(await p.locator('[data-answer="restore"]').textContent(), 'Restore it on laptop', 'or restore it on the partner');
  await p.goto(base + '/settings/devices/question/q1');
  await p.waitForSelector('[data-question] .sides');
  const mine = p.locator('[data-side="mine"]'), theirs = p.locator('[data-side="theirs"]');
  has(await mine.textContent(), 'Keep this computer\u2019s', 'one button keeps this computer\u2019s');
  has(await theirs.textContent(), 'Keep laptop\u2019s', 'the other keeps the partner\u2019s');
  has(await p.locator('[data-side="mine"] pre.diff').textContent(), '+The bell rang once.', 'the diff keeping mine throws away is shown before');
  has(await p.locator('[data-side="theirs"] pre.diff').textContent(), '+The bell rang twice.', 'and the one keeping theirs throws away');
  eq(await p.locator('[data-side="mine"] pre.diff .add').count() > 0, true, 'additions are coloured');
  await p.click('[data-side="mine"] [data-answer="mine"]');
  await p.waitForSelector('[data-done="mine"]');
  const link = await p.locator('[data-diff-download]').getAttribute('href');
  assert(link.startsWith('/settings/devices/diff/') && link.endsWith('?download=1'), 'the diff is offered as a file after');
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('[data-diff-download]')]);
  const text = await Deno.readTextFile(await dl.path());
  has(text, '+The bell rang once.', 'the file is the diff that was shown');
  eq((await api('overview')).questions.some(q => q.id === 'q1'), false, 'the question is gone');
  await p.goto(base + `/studio/doc/${seeded.doc}`);
  await p.waitForSelector('[data-sync-ood]');
  eq(await p.locator('[data-sync-banner]').count(), 0, 'and so is the banner');

  // e) a grouped deletion
  await p.goto(base + '/settings/devices/question/q3');
  await p.waitForSelector('[data-question] ul.units');
  eq(await p.locator('ul.units li').count(), 3, 'one question with the list');
  has(await p.locator('[data-answer="delete"]').first().textContent(), 'Delete them all here too', 'delete them all');
  has(await p.locator('[data-answer="restore"]').first().textContent(), 'Restore them all on laptop', 'restore them all');
  await p.click('[data-through]');
  await p.waitForSelector('[data-unit="clip:c1"]');
  await p.click('[data-unit="clip:c1"] [data-answer="delete"]');
  await until(async () => (await p.locator('[data-unit="clip:c1"]').textContent()).includes('done'), 'one answered');
  eq((await api('overview')).questions.find(q => q.id === 'q3').units.length, 2, 'going through answers one at a time');
  await p.goto(base + '/settings/devices/question/q3');
  await p.waitForSelector('[data-question] ul.units');
  eq(await p.locator('ul.units li').count(), 2, 'the rest stay asked as one');
  await p.click('[data-answer="delete"]');
  await p.waitForSelector('[data-done="delete"]');
  eq((await api('overview')).questions.some(q => q.id === 'q3'), false, 'delete them all answers the rest');

  // f) a switch, a job, a version put back, a diff deleted
  await p.goto(base + '/settings/devices/');
  await p.waitForSelector('main[data-loaded]');
  await p.check('[data-switch="send"]');
  await until(async () => (await api('overview')).switches.send === true, 'send turned on from the page');
  assert(true, 'a job switch is set from the page');
  await p.click('[data-cancel="j1"]');
  await until(async () => (await api('overview')).jobs.find(j => j.id === 'j1').state === 'cancelled', 'job cancelled');
  assert(true, 'a job is cancelled from the page');
  await p.click('[data-put-back="k1"]');
  await until(async () => !(await api('overview')).kept.some(k => k.id === 'k1'), 'put back');
  assert(true, 'a version kept for a day is put back from the page');
  const before = (await api('overview')).diffs.length;
  const first = await p.locator('[data-diffs] [data-diff]').first().getAttribute('data-diff');
  const body = await (await fetch(base + '/settings/devices/diff/' + first)).text();
  assert(body.length > 0, 'a diff file can be read');
  await p.click(`[data-diff-delete="${first}"]`);
  await until(async () => (await api('overview')).diffs.length === before - 1, 'diff deleted');
  assert(true, 'a diff file is deleted from the page');

  // g) leases
  const doc = {unit: seeded.doc_uid};
  eq((await api('unit', doc)).editing, 0, 'nobody edits the document');
  const ed = await ctx.newPage();
  if (Deno.env.get('DEBUG')) ed.on('request', r => { if (r.url().includes('lease')) console.log('   req', r.method(), r.url()); });
  await ed.goto(base + `/studio/doc/${seeded.doc}/edit`);
  await until(async () => (await api('unit', doc)).editing === 1, 'the editor took its lease');
  assert(true, 'the studio editor holds its document while open');
  await ed.goto(base + '/settings/');
  await until(async () => (await api('unit', doc)).editing === 0, 'the editor let go');
  assert(true, 'and lets go when it is left');
  await ed.close();
  await Deno.writeTextFile(work + '/hold-write', '1');
  await sleep(300);
  const ed2 = await ctx.newPage();
  await ed2.goto(base + `/studio/doc/${seeded.doc}/edit`);
  await ed2.waitForSelector('[data-sync-busy]');
  has(await ed2.locator('[data-sync-busy]').textContent(), 'Sync is writing this', 'while a sync writes, the editor says so');
  eq(await ed2.locator('#src').evaluate(e => e.readOnly), true, 'and its text cannot be typed in');
  await Deno.remove(work + '/hold-write');
  await until(async () => await ed2.locator('[data-sync-busy]').count() === 0, 'the note goes', 10000);
  eq(await ed2.locator('#src').evaluate(e => e.readOnly), false, 'it opens by itself a moment later');
  eq((await api('unit', doc)).editing, 1, 'holding the document now');
  await ed2.goto(base + '/settings/');
  await until(async () => (await api('unit', doc)).editing === 0, 'the second editor let go');
  await ed2.close();
  const deckUnit = {unit: 'deck:' + seeded.deck};
  await p.goto(base + `/exercises/deck/${seeded.deck}/`);
  await p.click('#btn-options');
  await until(async () => (await api('unit', deckUnit)).editing === 1, 'the deck options hold the deck');
  assert(true, 'a deck’s options hold the deck while open');
  await p.keyboard.press('Escape');
  await until(async () => (await api('unit', deckUnit)).editing === 0, 'and let go when closed');
  assert(true, 'and let go when closed');

  // h) make identical
  await p.goto(base + '/settings/devices/');
  await p.waitForSelector('main[data-loaded]');
  await p.click('[data-identical-ask="p-laptop"]');
  await p.waitForSelector('[data-summary="p-laptop"]');
  const sum = await p.locator('[data-summary]').textContent();
  has(sum, '4 replaced, 2 added, 1 deleted', 'the summary first: how many replaced, added, deleted');
  has(await p.locator('[data-lost]').textContent(), 'The bell', 'the changes that will be lost');
  has(sum, 'Transcribe the interview', 'the jobs cancelled');
  has(sum, 'is not changed', 'and that the partner is not changed');
  await p.click('[data-identical-go="p-laptop"]');
  await until(async () => (await p.locator('[data-identical]').textContent()).includes('now identical'), 'made identical');
  assert(await p.locator('[data-identical] a[download]').count() === 1, 'the lost changes are offered as a diff');

  eq(errors, [], 'no page threw');
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) {}
  await proc.status;
  await Deno.remove(work, {recursive: true}).catch(() => {});
}
console.log(`devices_page: ${passed} checks passed`);
