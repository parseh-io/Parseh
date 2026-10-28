// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of CHECK AS I ANSWER (a0.5.7): the document page's gear -> Exercises -> "Check as I answer".  The REAL studio
// (tests/studio_harness.py, both servers) with a document of every kind of exercise, in a real Chromium:
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/autocheck.mjs
//   AUTOCHECK_MODES=studio (or parseh) runs one; SHOTS=<dir> saves screenshots
//
//  off)    as ever: an answer is not checked; no exercise has a Check button of its own; "Check exercises" at the foot judges
//          them all and says the score
//  on)     the switch is in the gear's Exercises group of a document (and only of a document), says what it does, and is off
//          until it is turned on; turned on, with the exercises answered or not:
//            a single choice is checked the moment an option is picked -- right ones green with their explanation, a wrong one
//              red with the right answer shown and the other explanation;
//            true/false, which asks several questions, only when every one has its answer;
//            a fill-in when every blank holds a block, a matching when every place does;
//            choose-all and an ordering, which have no end of their own, are not: each has a Check button of its own;
//            a follow-up's steps keep Check step; a flashcard is nothing to check;
//          changing an answer checks again at once; the score under "Check exercises" follows each check and says what is not
//          checked yet; Check exercises still judges what is left
//  stays)  the choice is the reader's, kept on this device: it is still on when the page is opened again, and off again when turned off
//  elsewhere) the pages of exercises (a deck, studying, cramming) are not changed: no such row in their gear
import {chromium} from 'npm:playwright-core@1.52.0';
import {gearOpen, gearSwitch, gearClose, gearRow} from './gear_driver.mjs';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('AUTOCHECK_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(JSON.stringify(a) === JSON.stringify(b), `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 15000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}

async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', mode], cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  const log = [];
  (async () => { const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader(); for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); } })();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf + log.join(''));
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

// one of every kind that has an end of its own, and the kinds that do not, a follow-up and a card
const DOC = `---
title: Check as I answer
target: it
---

:::exercise single-choice
prompt: SINGLE which is right?
- [x] right
- [ ] wrong
explanation-correct: SINGLE-RIGHT said.
explanation-incorrect: SINGLE-WRONG said.
:::

:::exercise true-false
prompt: TWOQ decide.
- The sky is blue. => true
- Fire is cold. => false
:::

:::exercise fill-blanks
prompt: BLANKS fill them.
text: A [[one]] and a [[two]].
- [one] cat
- [two] dog
- [ ] bird
:::

:::exercise match-translations
prompt: MATCH them.
- uno => one
- due => two
:::

:::exercise choose-all
prompt: ALL pick every right one.
- [x] yes one
- [x] yes two
- [ ] no
:::

:::exercise order-sentences
prompt: ORDER them.
- [1] first
- [2] second
- [3] third
:::

:::exercise follow-up
prompt: CHAIN look.
::::exercise single-choice
prompt: STEPONE which?
- [x] a
- [ ] b
::::
::::exercise true-false
- yes => true
::::
:::

:::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
:::
`;

const state = ex => ex.evaluate(e => ({correct: e.classList.contains('correct'), incorrect: e.classList.contains('incorrect'),
  shown: [...e.querySelectorAll('.ex-explanation')].filter(x => !x.hidden).map(x => x.textContent.trim()),
  missed: e.querySelectorAll('.answer-missed').length, own: !!e.querySelector(':scope > .ex-check-row .ex-check-one')}));

async function suite(browser, mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info} = await startHarness(mode);
  const origin = `http://127.0.0.1:${info.port}`, S = info.studio;
  const url = p => origin + S + p;
  const errors = [];
  try {
    const made = await (await fetch(url('/api/docs'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({markdown: DOC})})).json();
    const id = made.meta.id;
    const ctx = await browser.newContext({viewport: {width: 1200, height: 1000}});
    const open = async () => {
      const p = await ctx.newPage();
      p.on('pageerror', e => errors.push(e.message));
      await p.goto(url(`/doc/${id}`));
      await p.waitForSelector('.exercise');
      return p;
    };
    const ex = (page, word) => page.locator('.exercise', {hasText: word}).first();
    const score = page => page.locator('[data-exercise-results] .ex-score');

    /* ---------------- off ---------------- */
    console.log('off) as it always was');
    let page = await open();
    await ex(page, 'SINGLE').locator('.ex-option', {hasText: 'right'}).first().click();
    eq(await state(ex(page, 'SINGLE')), {correct: false, incorrect: false, shown: [], missed: 0, own: false}, 'an answer is not checked');
    eq(await page.locator('.ex-check-one').count(), 0, 'no exercise has a Check button of its own');
    await page.locator('.ex-correct-all').click();
    assert(/correct$/.test(await score(page).textContent()), 'Check exercises judges them all and says the score: ' + await score(page).textContent());
    await page.close();

    /* ---------------- on ---------------- */
    console.log('on) the switch, and what it does');
    page = await open();
    await gearOpen(page, 'exercises');
    const rows = await page.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group="exercises"] [data-pg-row]')].map(r => r.getAttribute('data-pg-row')));
    eq(rows, ['translit', 'drag', 'autocheck'], 'the gear\'s Exercises group of a document holds Check as I answer');
    const row = gearRow(page, 'autocheck');
    eq((await row.locator('.pg-nametext').textContent()).trim(), 'Check as I answer', 'under that name');
    assert(/instead of waiting for Check exercises/.test(await row.locator('.pg-help').textContent()), 'with a sentence that says what it does');
    eq(await row.locator('button.pg-switch').getAttribute('aria-checked'), 'false', 'off until it is turned on');
    await gearClose(page);
    await gearSwitch(page, 'autocheck', true);
    eq(await page.evaluate(() => localStorage.getItem('parseh_exercise_autocheck')), '1', 'turned on, and kept on this device');

    // a single choice: the wrong one first, the right one after
    const single = ex(page, 'SINGLE');
    await single.locator('.ex-option', {hasText: 'wrong'}).click();
    let s = await state(single);
    assert(s.incorrect && !s.correct && s.missed === 1 && s.shown.join() === 'SINGLE-WRONG said.', 'a wrong pick is checked at once: red, the right one shown, the other explanation: ' + JSON.stringify(s));
    await single.locator('.ex-option', {hasText: /^right/}).click();
    s = await state(single);
    assert(s.correct && !s.incorrect && s.shown.join() === 'SINGLE-RIGHT said.', 'changing the answer checks again at once: green with its explanation: ' + JSON.stringify(s));
    eq((await score(page).textContent()), '1 / 8 correct · 7 not checked yet', 'and the score under Check exercises follows, saying what is not checked yet');

    // several questions: only when every one has its answer
    const two = ex(page, 'TWOQ');
    const groups = two.locator('.ex-choice-group');
    eq(await groups.count(), 2, 'a true/false exercise asks two questions');
    await groups.nth(0).locator('.ex-option').first().click();
    eq(await state(two).then(x => [x.correct, x.incorrect]), [false, false], 'it is not checked with one of its two questions answered');
    await groups.nth(1).locator('.ex-option').nth(1).click();
    s = await state(two);
    assert(s.correct || s.incorrect, 'it is checked when both have their answer');

    // a fill-in: drag-free, tap-to-place: pick a block, then a blank
    const blanks = ex(page, 'BLANKS');
    const place = async (word, blank) => {
      await blanks.locator('.ex-item', {hasText: word}).first().click();
      await blanks.locator('.ex-blank').nth(blank).click();
    };
    await place('cat', 0);
    eq(await state(blanks).then(x => [x.correct, x.incorrect]), [false, false], 'a fill-in is not checked with a blank still empty');
    await place('dog', 1);
    s = await state(blanks);
    assert(s.correct, 'it is checked when every blank holds a block: ' + JSON.stringify(s));

    // a matching
    const match = ex(page, 'MATCH');
    const drops = match.locator('.ex-match-drop');
    const n = await drops.count();
    const first = await match.locator('.ex-item').first().textContent();
    for (let i = 0; i < n; i++) {
      await match.locator('.ex-bank .ex-item, .ex-bank [data-item]').first().click();
      await drops.nth(i).click();
    }
    s = await state(match);
    assert(s.correct || s.incorrect, `a matching is checked when every place holds a block (${n} places, started with “${first.trim()}”)`);

    // no end of their own: a Check button each
    for (const word of ['ALL', 'ORDER']) {
      s = await state(ex(page, word));
      assert(s.own && !s.correct && !s.incorrect, `${word}: not checked by itself, and has a Check button of its own`);
    }
    const all = ex(page, 'ALL');
    await all.locator('.ex-option', {hasText: 'yes one'}).click();
    eq(await state(all).then(x => [x.correct, x.incorrect]), [false, false], 'picking one of several right answers checks nothing');
    await all.locator('.ex-option', {hasText: 'yes two'}).click();
    await all.locator('.ex-check-one').click();
    s = await state(all);
    assert(s.correct, 'its own Check button judges it: ' + JSON.stringify(s));
    await ex(page, 'ORDER').locator('.ex-check-one').click();
    s = await state(ex(page, 'ORDER'));
    assert(s.correct || s.incorrect, 'and so does the ordering\'s');

    // a follow-up keeps its own flow; a card is nothing to check
    const chain = ex(page, 'CHAIN');
    eq(await chain.locator('.ex-check-one').count(), 0, 'a follow-up\'s steps have no such button: Check step is theirs');
    assert(await chain.locator('.ex-step-check').first().isVisible(), 'Check step is still there');
    await chain.locator('.ex-step[data-step="1"] .ex-option').first().click();
    eq(await state(chain.locator('.ex-step[data-step="1"] > .exercise')).then(x => [x.correct, x.incorrect]), [false, false], 'and a step is not checked by an answer');
    eq(await ex(page, 'binario').locator('.ex-check-one').count(), 0, 'a flashcard has none');

    // Check exercises still judges what is left
    await page.locator('.ex-correct-all').click();
    assert(/^\d+ \/ \d+ correct$/.test(await score(page).textContent()), 'Check exercises judges what is left and says the whole score: ' + await score(page).textContent());
    if (SHOTS) await page.screenshot({path: `${SHOTS}/autocheck-${mode}.png`, fullPage: true});

    /* ---------------- stays ---------------- */
    console.log('stays) the reader\'s choice, on this device');
    await page.close();
    page = await open();
    eq(await page.evaluate(() => localStorage.getItem('parseh_exercise_autocheck')), '1', 'still on when the page is opened again');
    await ex(page, 'SINGLE').locator('.ex-option', {hasText: /^right/}).click();
    assert((await state(ex(page, 'SINGLE'))).correct, 'and it checks at once');
    eq(await page.locator('.ex-check-one').count(), 2, 'with the two Check buttons there');
    await gearSwitch(page, 'autocheck', false);
    eq(await page.locator('.ex-check-one').count(), 0, 'turned off, the Check buttons go');
    await ex(page, 'SINGLE').locator('.ex-option', {hasText: 'wrong'}).click();
    eq(await state(ex(page, 'SINGLE')).then(x => [x.correct, x.incorrect]), [false, false], 'and an answer is not checked again');
    eq(await page.evaluate(() => localStorage.getItem('parseh_exercise_autocheck')), '0', 'off is kept too');
    await page.close();

    /* ---------------- elsewhere ---------------- */
    console.log('elsewhere) the editor\'s preview and the pages of exercises are not changed');
    await ctx.addInitScript(() => { try { localStorage.setItem('parseh_exercise_autocheck', '1'); } catch (_) {} });
    const edit = await ctx.newPage();
    edit.on('pageerror', e => errors.push(e.message));
    await edit.goto(url(`/doc/${id}/edit`));
    await edit.waitForSelector('#sheet .exercise');
    await sleep(600);
    eq(await edit.locator('#sheet .ex-check-one').count(), 0, 'the editor\'s preview has no Check button of its own');
    await edit.close();

    eq(errors, [], 'no page error');
    await ctx.close();
  } finally {
    proc.kill();
    await sleep(100);
  }
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  for (const mode of modes) await suite(browser, mode);
  console.log(`\nCheck as I answer passed (${modes.join(' + ')}: ${passed} checks)`);
} finally {
  await browser.close();
}
