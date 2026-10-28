// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the FOLLOW-UP QUESTIONS FORM (a0.5.4, exform.js): the studio's editor, against the REAL routes
// (tests/studio_harness.py: markdown/app/server.py, store.py, htmlgen) on a temporary library.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/exform_chain.mjs
//   EXFORM_CHAIN_MODES=studio (or parseh) runs one server; PARSEH_TEST_ARTIFACTS=<dir> saves screenshots
//
//  grid)     the tile after the flashcards, with its line; the form's sections; Insert refused under two steps
//  steps)    + New step… opens the grid (no Follow-up tile) and the step's own form ON TOP of the chain's: titled
//            "Step 2 — …", Add to the chain / Save step; the list says "Step 3 of 3", renumbers live
//  order)    reorder by the number box, by the arrows, by the handle's keys and by dragging with the mouse;
//            Duplicate; Delete with an Undo; ticks with Select all / none, Move up / down and Delete together
//  preview)  the chain's preview draws every step unfolded and follows each change
//  insert)   Insert writes the fences one colon deeper; the editor's preview draws the chain; one undo takes it back
//  edit)     ✎ Edit on the chain in the preview reopens it with its steps; a step is edited from the list
//  draw)     a drawing in a step -- written as a page writes it (four colons) or one colon deeper (five) -- is a drawing
//            on the page, the form lists such a step with its words and not its LaTeX, and saving writes it one colon deeper
//  page)     + From this page… lists the page's exercises, greys what cannot be a step, adds them in page order or
//            the order ticked; the originals leave the page in the same undoable step as the chain is written;
//            ⤴ Put back makes a step an exercise of the page again
//  paste)    a chain pasted in the grid opens in the form with its steps; a step with a mistake is named
//  phone)    rows 48 px, the arrows, ✎ and ⋯ fingers' targets, the rest under ⋯
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('EXFORM_CHAIN_MODES') || 'studio,parseh').split(',');
const ART = Deno.env.get('PARSEH_TEST_ARTIFACTS') || '';
if (ART) await Deno.mkdir(ART, {recursive: true});
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
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', mode], cwd: root,
                                         stdout: 'piped', stderr: 'piped'}).spawn();
  const log = [];
  (async () => {
    const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); }
  })();
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
  return {proc, info, log};
}

const DOC = `---
title: Chain form
target: it
---

Intro.

:::exercise single-choice
prompt: Where are the speakers?
- [ ] at home
- [x] at the station
:::

:::exercise true-false
- The train leaves at nine. => false
:::

:::exercise yes-no
- Is the platform the second? => yes
:::

:::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
:::
`;
const CHAIN2 = `:::exercise follow-up
prompt: Read the dialogue.
explanation-incorrect: Read it again.
::::exercise single-choice
prompt: Where?
- [x] at the station
- [ ] at home
::::
::::exercise true-false
prompt: Decide.
- The train is late. => true
::::
::::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
::::
:::
`;
const DOC2 = DOC + '\n' + CHAIN2;
const PASTED = `:::exercise follow-up
prompt: Pasted.
::::exercise single-choice
prompt: One
- [x] a
- [ ] b
::::
::::exercise true-false
- Two => true
::::
:::`;

// a drawing is TeX's: with no xelatex on this computer the draw) section says so and is left out, a fresh clone stays green
const hasTeX = await new Deno.Command('xelatex', {args: ['--version'], stdout: 'null', stderr: 'null'}).output()
  .then(r => r.success, () => false);
// the first step's drawing is written as a drawing is on a page of its own, the second's one colon deeper
const DRAWN = `---
title: Chain with drawings
target: it
---

:::exercise follow-up
prompt: Look at the two drawings, then answer about them.
::::exercise single-choice
prompt: |
  Which one is it?
  ::::latex
  \\textbf{ciao} $E=mc^2$
  ::::
- [x] ciao
- [ ] addio
::::
::::exercise true-false
prompt: |
  Decide.
  :::::latex
  \\textit{arrivederci}
  :::::
- It is a greeting. => true
::::
:::
`;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});

async function suite(mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info} = await startHarness(mode);
  const S = info.studio;
  const url = p => `http://127.0.0.1:${info.port}${p}`;
  const ctx = await browser.newContext({viewport: {width: 1200, height: 1000}});
  const errors = [];
  const watch = page => {
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
  };
  try {
    const made = await (await ctx.request.post(url(S + '/api/docs'), {data: {markdown: DOC}})).json();
    const id = made.id || (made.doc && made.doc.id) || (made.meta && made.meta.id);
    const page = await ctx.newPage();
    watch(page);
    const source = () => page.locator('#src').inputValue();
    const open = async () => {
      await page.goto(url(`${S}/doc/${id}/edit`));
      await until(async () => /rendered/.test(await page.locator('#pv-status').textContent()), 'the preview renders');
    };
    const menu = async sel => {
      const d = page.locator('details.dropdown').filter({has: page.locator('#btn-exercise')});
      if (!await d.evaluate(e => e.open)) await d.locator('summary').click();
      await page.locator(sel).click();
    };
    const frames = () => page.locator('#modal-root .ex-form-modal');
    const top = () => page.locator('#modal-root .ex-form-modal').last();
    const rows = () => page.locator('#modal-root .ex-steps-row, #modal-root .ex-step-row');
    const rowTexts = () => page.locator('.ex-step-row').evaluateAll(rs => rs.map(r => [
      r.querySelector('.ex-step-of').firstChild.textContent, r.querySelector('.ex-step-kind').textContent, r.querySelector('.ex-step-words').textContent]));
    const words = () => page.locator('.ex-step-row .ex-step-words').allTextContents();
    const chainForm = () => page.locator('#modal-root .ex-form-modal').first();
    // the preview of a chain with fewer than two steps is drawn too (as an exercise that needs attention), so it is the
    // preview of the chain with its `n` steps that is waited for, not the first one with a status
    const previewDone = n => until(() => page.evaluate(n => {
      const form = '#modal-root .ex-form-modal:not(.x) ';
      return /Correct answer shown/.test(document.querySelector(form + '.ex-form-preview-status')?.textContent || '')
        && document.querySelectorAll(form + '.ex-form-preview .ex-chain .ex-step').length === n;
    }, n), `the form's preview is drawn with its ${n} steps`);
    const addStep = async (type, fill) => {
      await page.click('.ex-steps-tools ~ .ex-add-row [data-x="new-step"], .ex-add-row [data-x="new-step"]');
      await page.locator('.ex-picker .ex-type', {hasText: type}).click();
      await page.waitForSelector('.ex-step-frame .ex-form-modal');
      if (fill) await fill(page.locator('.ex-step-frame .ex-form-modal'));
      await page.locator('.ex-step-frame [data-x="save"]').click();
      await page.waitForFunction(() => !document.querySelector('.ex-step-frame'));
    };

    /* ---------------- grid ---------------- */
    console.log('grid) the tile and the form');
    await open();
    await menu('#btn-exercise');
    const tiles = await page.locator('.ex-picker .ex-type').allTextContents();
    assert(tiles.length === 16 && tiles[tiles.length - 1].startsWith('Follow-up questions'), 'sixteen tiles: Follow-up questions is the last, after the flashcards');
    assert(tiles[tiles.length - 1].includes('A chain of exercises answered one after the other; a step may build on the one before.'), 'with its one line');
    assert(tiles[tiles.length - 2].startsWith('Embedded Jolly flashcard'), 'the Jolly flashcard is the one before');
    await page.locator('.ex-picker .ex-type', {hasText: 'Follow-up questions'}).click();
    await page.waitForSelector('#modal-root .ex-form-modal');
    eq(await page.locator('#modal-root .ex-form-head h3').textContent(), 'Add Follow-up questions', 'the form is titled Add Follow-up questions');
    eq(await page.locator('#modal-root .ex-form-section h4').allTextContents(),
       ['Instructions', 'Steps', 'Pictures (optional)', 'Recordings (optional)', 'Explanation after checking (optional)', 'Preview'], 'its sections');
    eq(await chainForm().locator('textarea').first().inputValue(), 'Answer these questions one after the other.', 'the prompt starts as the type\'s default');
    assert((await page.locator('.ex-steps-hint').textContent()).startsWith('A follow-up needs at least two steps'), 'the list says it needs two steps');
    assert(await page.locator('.ex-step-row').count() === 0, 'no step yet');
    assert(await page.locator('[data-x="from-page"]').textContent() === '+ From this page…', 'beside + New step…, + From this page…');
    await page.locator('#modal-root [data-x="save"]').click();
    assert(/needs at least two steps/.test(await page.locator('#toast').textContent()), 'Insert is refused under two steps');
    assert((await source()) === DOC, 'and writes nothing');

    /* ---------------- steps ---------------- */
    console.log('steps) a new step, in a frame on top');
    await page.click('[data-x="new-step"]');
    await page.waitForSelector('.ex-picker');
    const stepTiles = await page.locator('.ex-picker .ex-type').allTextContents();
    assert(stepTiles.length === 15 && !stepTiles.some(t => t.startsWith('Follow-up questions')), 'the step grid has every tile but Follow-up questions');
    assert(await frames().count() === 1 && await page.locator('.ex-picker h3').first().textContent() === 'Add a step', 'it opens over the chain\'s form, titled Add a step');
    await page.locator('.ex-picker .ex-type', {hasText: 'Choose one answer'}).click();
    await page.waitForSelector('.ex-step-frame .ex-form-modal');
    eq(await page.locator('.ex-step-frame h3').textContent(), 'Step 1 — Choose one answer', 'the step\'s form is titled Step 1 — Choose one answer');
    eq(await page.locator('.ex-step-frame [data-x="save"]').textContent(), 'Add to the chain', 'its button says Add to the chain');
    assert(await frames().count() === 2, 'the chain\'s form is still there behind it');
    // the step's own fields
    const choice = page.locator('.ex-step-frame .ex-form-row textarea');
    await page.locator('.ex-step-frame .ex-form-section').first().locator('textarea').first().fill('Where are the two speakers?');
    await choice.nth(0).fill('at the station');
    await choice.nth(1).fill('at home');
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('.ex-step-frame'));
    assert(await frames().count() === 1 && await page.locator('.ex-step-row').count() === 0, 'Escape closes the step\'s frame only, and adds nothing');
    await page.click('[data-x="new-step"]');
    await page.locator('.ex-picker .ex-type', {hasText: 'Choose one answer'}).click();
    await page.waitForSelector('.ex-step-frame .ex-form-modal');
    await page.locator('.ex-step-frame .ex-form-section').first().locator('textarea').first().fill('Where are the two speakers?');
    const ch2 = page.locator('.ex-step-frame .ex-form-row textarea');
    await ch2.nth(0).fill('at the station');
    await ch2.nth(1).fill('at home');
    await page.locator('.ex-step-frame [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('.ex-step-frame'));
    eq(await rowTexts(), [['Step 1 of 1', 'Choose one answer', 'Where are the two speakers?']], 'the list has the step: its place, its type, its opening words');
    await addStep('True / False questions', async f => {
      await f.locator('.ex-form-row textarea').first().fill('The train leaves at nine.');
      await f.locator('.ex-form-row select').first().selectOption('false');
    });
    eq((await rowTexts())[1][0], 'Step 2 of 2', 'the second step says Step 2 of 2 -- and the first now says of 2');
    eq((await rowTexts())[0][0], 'Step 1 of 2', 'the first renumbers: Step 1 of 2');
    // the step frame for the third says its place
    await page.click('[data-x="new-step"]');
    await page.locator('.ex-picker .ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
    await page.waitForSelector('.ex-step-frame .ex-form-modal');
    eq(await page.locator('.ex-step-frame h3').textContent(), 'Step 3 — Embedded vocabulary flashcard', 'the third is titled Step 3 — …');
    const dirs = await page.locator('.ex-step-frame select option').evaluateAll(os => os.map(o => o.value));
    assert(dirs.includes('forward') && !dirs.includes('both-repeat'), 'a card as a step is not offered "both (repeat)"');
    const cardField = label => page.locator('.ex-step-frame label.ex-author-field', {has: page.locator(`span:text-is("${label}")`)}).locator('textarea, input').first();
    await cardField('Word or expression').fill('[binario]{tl}');
    await cardField('Meaning').fill('platform');
    await page.locator('.ex-step-frame [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('.ex-step-frame'));
    eq(await rowTexts(), [['Step 1 of 3', 'Choose one answer', 'Where are the two speakers?'], ['Step 2 of 3', 'True / False questions', 'Decide whether each statement is True or False.'],
                          ['Step 3 of 3', 'Embedded vocabulary flashcard', 'binario']], 'three steps, each with its place, its type and its opening words (a card\'s front)');
    await previewDone(3);
    eq(await page.locator('#modal-root .ex-form-preview .ex-chain .ex-step').count(), 3, 'the preview draws the three steps');
    eq(await page.evaluate(() => [...document.querySelectorAll('#modal-root .ex-form-preview .ex-step')].map(s => getComputedStyle(s).display !== 'none' && !s.hidden)), [true, true, true], 'every step unfolded');
    if (ART) await page.screenshot({path: `${ART}/exform-chain-${mode}.png`});


    /* ---------------- order ---------------- */
    console.log('order) the number box, the arrows, the handle, dragging, copies, deleting and ticks');
    const C = 'Where are the two speakers?', T = 'Decide whether each statement is True or False.', K = 'binario';
    const row = i => page.locator('.ex-step-row').nth(i);
    eq(await words(), [C, T, K], 'to start with: the choice, the true/false, the card');
    assert(await row(0).locator('.ex-step-toggle').isHidden() && await row(0).locator('.ex-step-duplicate').isVisible() && await row(0).locator('.ex-step-delete').isVisible(),
           'on a wide screen Duplicate, Put back and Delete are on the row, and the ⋯ is not');
    // the number box: type 3 in step 1's box
    await row(0).locator('.ex-step-no').fill('3');
    await row(0).locator('.ex-step-no').press('Enter');
    eq(await words(), [T, K, C], 'typing 3 in the box of step 1 moves it to place 3');
    eq((await rowTexts()).map(r => r[0]), ['Step 1 of 3', 'Step 2 of 3', 'Step 3 of 3'], 'and every row renumbers');
    eq(await page.evaluate(() => [document.activeElement.className, document.activeElement.closest('.ex-step-row').dataset.i]), ['ex-step-no', '2'], 'the focus follows it, to its box');
    await row(2).locator('.ex-step-up').click();
    eq(await words(), [T, C, K], '↑ moves a step earlier');
    await row(0).locator('.ex-step-down').click();
    eq(await words(), [C, T, K], '↓ moves a step later');
    assert(await row(0).locator('.ex-step-up').isDisabled() && await row(2).locator('.ex-step-down').isDisabled(), '↑ is off at the top and ↓ at the foot');
    // the handle, by the keyboard
    await row(0).locator('.ex-step-grip').focus();
    await page.keyboard.press('ArrowDown');
    eq(await words(), [T, C, K], 'ArrowDown on the handle moves the step later');
    eq(await page.evaluate(() => document.activeElement.className), 'ex-step-grip', 'and the focus stays on its handle');
    await page.keyboard.press('ArrowUp');
    eq(await words(), [C, T, K], 'ArrowUp moves it back');
    // dragging, with the mouse: the first step below the last
    const grip = async i => { const b = await row(i).locator('.ex-step-grip').boundingBox(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; };
    let from = await grip(0), to = await grip(2);
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(from.x, from.y + 30, {steps: 4});
    await page.mouse.move(to.x, to.y + 20, {steps: 8});
    assert(await page.locator('.ex-step-row.dragging').count() === 1 && await page.locator('.ex-step-row.drop-after').count() === 1, 'while dragging: the row is marked, and a line shows where it goes');
    await page.mouse.up();
    eq(await words(), [T, K, C], 'dragging step 1 below step 3 puts it last');
    from = await grip(2); to = await grip(0);
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(to.x, to.y - 12, {steps: 10});
    await page.mouse.up();
    eq(await words(), [C, T, K], 'and dragging the last above the first puts it first');
    // a copy, and taking it away with an Undo
    await row(1).locator('.ex-step-duplicate').click();
    eq(await words(), [C, T, T, K], 'Duplicate puts a copy of a step just after it');
    await row(2).locator('.ex-step-delete').click();
    eq(await words(), [C, T, K], 'Delete takes a step out');
    const undo = page.locator('.ex-steps-undo');
    assert(await undo.isVisible() && /Step 3 removed/.test(await undo.textContent()), 'and says so, with an Undo');
    await undo.locator('[data-x="undo"]').click();
    eq(await words(), [C, T, T, K], 'Undo puts it back where it was');
    await row(2).locator('.ex-step-delete').click();
    await sleep(6400);
    assert(await undo.isHidden(), 'the Undo stays six seconds, and then is gone');
    eq(await words(), [C, T, K], 'the chain is as it was');
    // ticks
    await row(1).locator('.ex-step-pick').check();
    await row(2).locator('.ex-step-pick').check();
    eq(await page.locator('.ex-steps-picked').textContent(), '2 ticked', 'two ticked');
    await page.locator('[data-x="up-picked"]').click();
    eq(await words(), [T, K, C], 'Move up moves the ticked steps one place earlier together');
    await page.locator('[data-x="down-picked"]').click();
    eq(await words(), [C, T, K], 'Move down moves them back');
    await page.locator('[data-x="all"]').click();
    eq(await page.locator('.ex-step-pick:checked').count(), 3, 'Select all ticks every step');
    await page.locator('[data-x="up-picked"]').click();
    eq(await words(), [C, T, K], 'moving all of them up moves nothing');
    await page.locator('[data-x="none"]').click();
    assert(await page.locator('.ex-step-pick:checked').count() === 0 && await page.locator('[data-x="delete-picked"]').isDisabled(), 'Select none unticks them, and the bulk buttons are off');
    await row(0).locator('.ex-step-pick').check();
    await row(2).locator('.ex-step-pick').check();
    await page.locator('[data-x="delete-picked"]').click();
    eq(await words(), [T], 'Delete takes the ticked steps out together');
    assert(/2 steps removed/.test(await undo.textContent()), 'with one Undo for both');
    await undo.locator('[data-x="undo"]').click();
    eq(await words(), [C, T, K], 'which puts both back where they were');
    await previewDone(3);
    eq(await page.locator('#modal-root .ex-form-preview .ex-chain .ex-step').count(), 3, 'the form\'s preview follows every change');

    /* ---------------- insert ---------------- */
    console.log('insert) the fences, the preview, one undo');
    await page.locator('#modal-root [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    let written = await source();
    const chainAt = written.indexOf(':::exercise follow-up');
    assert(chainAt > 0, 'the chain is in the source');
    const block = written.slice(chainAt, written.indexOf('\n:::\n', chainAt) + 4);
    eq(block.split('\n').filter(l => /^:{3,}/.test(l)), [':::exercise follow-up', '::::exercise single-choice', '::::', '::::exercise true-false', '::::', '::::exercise flashcard', '::::', ':::'],
       'its fences: the chain at three colons, each step one colon more');
    assert(block.includes('prompt: Answer these questions one after the other.') && block.includes('- [x] at the station') && block.includes('target: [binario]{tl}'),
           'with the fields of each step in it');
    await until(() => page.evaluate(() => !!document.querySelector('#sheet .ex-chain') && !document.querySelector('#sheet .ex-invalid')), 'the editor\'s preview draws the chain');
    eq(await page.locator('#sheet .ex-chain .ex-step').count(), 3, 'the page shows it with its three steps');
    await page.locator('#btn-undo').click();
    eq(await source(), DOC, 'one Undo takes the chain out');

    /* ---------------- edit ---------------- */
    console.log('edit) the chain reopened, a step edited from the list, a step put back');
    const D2 = DOC2.replace('title: Chain form', 'title: Chain form, edited');
    const made2 = await (await ctx.request.post(url(S + '/api/docs'), {data: {markdown: D2}})).json();
    const id2 = made2.id || (made2.doc && made2.doc.id) || (made2.meta && made2.meta.id);
    const openDoc = async docId => {
      await page.goto(url(`${S}/doc/${docId}/edit`));
      await until(async () => /rendered/.test(await page.locator('#pv-status').textContent()), 'the preview renders')
        .catch(async e => { throw Error(e.message + ' -- status: ' + await page.locator('#pv-status').textContent() + ' url ' + page.url() + ' errors ' + errors.join(';')); });
    };
    await openDoc(id2);
    assert(await page.locator('#sheet .ex-chain > .ex-head .ex-edit').count() === 1 && await page.locator('#sheet .ex-chain .ex-step .ex-edit').count() === 0,
           'the preview has ✎ Edit on the chain, and none on its steps');
    await page.locator('#sheet .ex-chain > .ex-head .ex-edit').click();
    await page.waitForSelector('#modal-root .ex-form-modal');
    eq(await page.locator('#modal-root .ex-form-head h3').textContent(), 'Edit Follow-up questions', 'the form opens as Edit Follow-up questions');
    eq(await words(), ['Where?', 'Decide.', 'binario'], 'with its three steps in the list');
    eq(await chainForm().locator('textarea').first().inputValue(), 'Read the dialogue.', 'and its prompt');
    eq(await page.locator('#modal-root [data-x="save"]').textContent(), 'Save exercise', 'Save exercise');
    await row(1).locator('.ex-step-edit').click();
    await page.waitForSelector('.ex-step-frame .ex-form-modal');
    eq([await page.locator('.ex-step-frame h3').textContent(), await page.locator('.ex-step-frame [data-x="save"]').textContent()],
       ['Step 2 — True / False questions', 'Save step'], 'a step is edited from the list: Step 2 — True / False questions, with Save step');
    await page.locator('.ex-step-frame .ex-form-section').first().locator('textarea').first().fill('Decide now.');
    await page.locator('.ex-step-frame [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('.ex-step-frame'));
    eq(await words(), ['Where?', 'Decide now.', 'binario'], 'the list shows the step as edited');
    await page.locator('#modal-root [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    eq(await source(), D2.replace('prompt: Decide.', 'prompt: Decide now.'), 'saved: the chain is rewritten in place, every other line as it was');
    // put a step back
    await page.locator('#sheet .ex-chain > .ex-head .ex-edit').click();
    await page.waitForSelector('#modal-root .ex-form-modal');
    await row(2).locator('.ex-step-putback').click();
    eq(await words(), ['Where?', 'Decide now.'], '⤴ Put back takes the step out of the list');
    assert(/goes back on the page as an exercise of its own, after the chain, when you save/.test(await page.locator('.ex-steps-undo').textContent()), 'and says where it goes');
    await page.locator('#modal-root [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    written = await source();
    const afterChain = written.slice(written.indexOf(':::exercise follow-up'));
    eq(afterChain, `:::exercise follow-up
prompt: Read the dialogue.
explanation-incorrect: Read it again.
::::exercise single-choice
prompt: Where?
- [x] at the station
- [ ] at home
::::
::::exercise true-false
prompt: Decide now.
- The train is late. => true
::::
:::

:::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
:::
`, 'saved: the chain has two steps, and the card is an exercise of the page after it');
    await page.locator('#btn-undo').click();
    eq(await source(), D2.replace('prompt: Decide.', 'prompt: Decide now.'), 'one Undo puts it all back');

    /* ---------------- draw ---------------- */
    console.log('draw) a drawing in a step');
    if (!hasTeX) console.log('  SKIP: no xelatex on this computer -- a drawing is made by TeX');
    else {
      const made4 = await (await ctx.request.post(url(S + '/api/docs'), {data: {markdown: DRAWN}})).json();
      const id4 = made4.id || (made4.doc && made4.doc.id) || (made4.meta && made4.meta.id);
      await openDoc(id4);
      await until(() => page.evaluate(() => !!document.querySelector('#sheet .ex-chain')), 'the chain is drawn');
      assert(await page.locator('#sheet .ex-invalid').count() === 0,
             'a drawing written with four colons in a step does not end the step: the follow-up needs no attention');
      eq(await page.locator('#sheet .ex-chain .ex-step').count(), 2, 'it has its two steps');
      await page.locator('#sheet .ex-chain .ex-showall').click();
      await until(() => page.evaluate(() => [...document.querySelectorAll('#sheet .ex-chain .ex-step figure.latex img')]
        .filter(i => i.complete && i.naturalWidth > 20).length === 2), 'both drawings are drawn, one in each step');
      assert(true, 'one drawing in each step, the four-colon one and the five-colon one, both really drawn');
      await page.locator('#sheet .ex-chain > .ex-head .ex-edit').click();
      await page.waitForSelector('#modal-root .ex-form-modal');
      eq(await page.locator('.ex-step-row .ex-step-kind').allTextContents(), ['Choose one answer', 'True / False questions'].map(s => s),
         'the form lists both steps by their types');
      const said = await words();
      assert(said.length === 2 && said.every(w => !/latex|textbf|textit/i.test(w)) && said[0].startsWith('Which one is it?'),
             'and by their words, not their LaTeX: ' + JSON.stringify(said));
      await page.locator('#modal-root [data-x="save"]').click();
      await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
      const rewritten = await source();
      // a drawing's fences are the indented ones: it sits under its field's `prompt: |`
      eq(rewritten.split('\n').filter(l => /^\s+:{4,}(latex\b.*)?$/.test(l)).map(l => l.trim().replace(/latex.*/, 'latex')),
         [':::::latex', ':::::', ':::::latex', ':::::'], 'saved: every drawing is one colon deeper, as the page says it is written in a step');
      await until(() => page.evaluate(() => !!document.querySelector('#sheet .ex-chain') && !document.querySelector('#sheet .ex-invalid')), 'the preview draws the chain again');
      await page.locator('#sheet .ex-chain .ex-showall').click();
      await until(() => page.evaluate(() => [...document.querySelectorAll('#sheet .ex-chain .ex-step figure.latex img')]
        .filter(i => i.complete && i.naturalWidth > 20).length === 2), 'both drawings are still drawn');
      assert(true, 'and the rewritten chain still shows both drawings');
    }

    /* ---------------- page ---------------- */
    console.log('page) a chain made of exercises the page already has');
    const D3 = DOC2.replace('title: Chain form', 'title: Chain form, from the page');
    const made3 = await (await ctx.request.post(url(S + '/api/docs'), {data: {markdown: D3}})).json();
    const id3 = made3.id || (made3.doc && made3.doc.id) || (made3.meta && made3.meta.id);
    await openDoc(id3);
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await menu('#btn-exercise');
    await page.locator('.ex-picker .ex-type', {hasText: 'Follow-up questions'}).click();
    await page.waitForSelector('#modal-root .ex-form-modal');
    await page.click('[data-x="from-page"]');
    await page.waitForSelector('.ex-from-page .ex-from-item');
    const offered = await page.locator('.ex-from-item').evaluateAll(is => is.map(i => [i.querySelector('.ex-from-kind').textContent, i.querySelector('.ex-from-words').textContent,
      i.querySelector('input').disabled, (i.querySelector('.ex-from-note') || {}).textContent || '']));
    eq(offered.map(o => o.slice(0, 2)), [['Choose one answer', 'Where are the speakers?'], ['True / False questions', 'The train leaves at nine.'],
      ['Yes / No questions', 'Is the platform the second?'], ['Embedded vocabulary flashcard', 'binario'], ['Follow-up questions', 'Read the dialogue.']],
       'the frame lists the page\'s exercises, in page order, each with its type and its opening words');
    eq(offered.map(o => o[2]), [false, false, false, false, true], 'the follow-up already there is greyed');
    eq(offered[4][3], 'a follow-up cannot be a step of another', 'and says why');
    assert(await page.locator('.ex-from-remove').isVisible() && await page.locator('.ex-from-remove input').isChecked(), 'the box that takes the originals off the page is there, ticked');
    assert(/Remove them from the page once they are in the chain/.test(await page.locator('.ex-from-remove').textContent()), 'in those words');
    await page.locator('.ex-from-filter').fill('platform');
    eq(await page.locator('.ex-from-item:visible').count(), 1, 'the filter narrows the list');
    await page.locator('.ex-from-filter').fill('');
    await page.locator('.ex-from-item').nth(2).locator('input').check();        // yes/no first…
    await page.locator('.ex-from-item').nth(0).locator('input').check();        // …then the choice
    eq(await page.locator('.ex-from-count').textContent(), '2 ticked', 'two ticked');
    await page.locator('.ex-from-order input[value="ticked"]').check();
    await page.locator('.ex-from-page [data-x="add"]').click();
    await page.waitForFunction(() => !document.querySelector('.ex-from-page'));
    eq(await words(), ['Is the platform the second?', 'Where are the speakers?'], 'Add the ticked ones: in the order they were ticked');
    assert(/Taken from the page: the original goes when you save/.test(await row(0).locator('.ex-step-from').textContent()), 'each row says the original goes');
    assert(await page.locator('.ex-steps-originals').isVisible() && await page.locator('.ex-steps-originals input').isChecked(), 'and the chain\'s form has the box, ticked');
    await previewDone(2);
    await page.locator('#modal-root [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    written = await source();
    assert(!written.includes('- [x] at the station\n:::\n\n:::exercise true-false') && !written.includes('\n:::exercise yes-no'), 'the two originals are off the page');
    assert(written.includes(':::exercise true-false\n- The train leaves at nine. => false\n:::\n\n:::exercise flashcard'), 'the others stand, with one blank line between');
    const chained = written.slice(written.lastIndexOf(':::exercise follow-up'));
    assert(chained.indexOf('::::exercise yes-no') < chained.indexOf('::::exercise single-choice') && chained.includes('- [ ] at home'), 'the new chain is at the cursor, with the yes/no step first');
    await page.locator('#btn-undo').click();
    eq(await source(), D3, 'ONE Undo brings the originals back and takes the chain out');
    // and the other way: copied, the originals stay
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await menu('#btn-exercise');
    await page.locator('.ex-picker .ex-type', {hasText: 'Follow-up questions'}).click();
    await page.click('[data-x="from-page"]');
    await page.waitForSelector('.ex-from-page .ex-from-item');
    await page.locator('.ex-from-item').nth(1).locator('input').check();
    await page.locator('.ex-from-item').nth(0).locator('input').check();
    await page.locator('.ex-from-remove input').uncheck();
    await page.locator('.ex-from-page [data-x="add"]').click();
    await page.waitForFunction(() => !document.querySelector('.ex-from-page'));
    eq(await words(), ['Where are the speakers?', 'The train leaves at nine.'], 'in page order by default');
    assert(/Copied from the page: the original stays/.test(await row(0).locator('.ex-step-from').textContent()), 'with the box unticked the rows say the original stays');
    await page.locator('#modal-root [data-x="save"]').click();
    await page.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    written = await source();
    assert(written.startsWith(D3.trimEnd()) && written.includes(':::exercise yes-no') && (written.match(/Where are the speakers\?/g) || []).length === 2, 'the originals are where they were, and the chain has copies');
    await page.locator('#btn-undo').click();
    eq(await source(), D3, 'one Undo');

    /* ---------------- paste ---------------- */
    console.log('paste) a chain pasted in the grid');
    const paste = text => page.evaluate(text => {
      const dt = new DataTransfer();
      dt.setData('text/plain', text);
      document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    }, text);
    await menu('#btn-exercise');
    await paste(PASTED);
    await page.waitForSelector('#modal-root .ex-form-modal');
    eq(await page.locator('#modal-root .ex-form-head h3').textContent(), 'Add Follow-up questions', 'Ctrl+V on the grid opens the chain in the form');
    eq(await words(), ['One', 'Two'], 'with its steps');
    eq(await chainForm().locator('textarea').first().inputValue(), 'Pasted.', 'and its prompt');
    await page.locator('#modal-root [data-x="cancel"]').last().click();
    // a step with a mistake is named
    await menu('#btn-exercise');
    await page.locator('.ex-picker [data-x="paste"]').click();
    await page.locator('.ex-paste').fill(PASTED.replace('- [x] a', '- [ ] a'));
    await page.locator('.ex-picker [data-x="open"]').click();
    await page.waitForSelector('#modal-root .ex-form-modal');
    assert(/Mark exactly one correct answer/.test(await page.locator('.ex-step-row').first().locator('.ex-step-err').textContent()), 'a step with a mistake says so on its row');
    assert(await page.locator('.ex-step-row.bad').count() === 1, 'and the row is marked');
    await page.locator('#modal-root [data-x="save"]').click();
    assert(/Step 1: Mark exactly one correct answer/.test(await page.locator('#toast').textContent()), 'Insert is refused, naming the step');
    await page.locator('#modal-root [data-x="cancel"]').last().click();
    // a follow-up is not a step
    await menu('#btn-exercise');
    await page.locator('.ex-picker .ex-type', {hasText: 'Follow-up questions'}).click();
    await page.click('[data-x="new-step"]');
    await paste(PASTED);
    await sleep(300);
    assert(/A follow-up cannot hold a follow-up/.test(await page.locator('#toast').textContent()), 'a chain pasted into the grid of a step is refused');
    assert(await page.locator('.ex-step-frame').count() === 0, 'and no form opens for it');
    await page.keyboard.press('Escape');
    await page.locator('#modal-root [data-x="cancel"]').last().click();

    /* ---------------- phone ---------------- */
    console.log('phone) the steps list under a finger');
    const phoneCtx = await browser.newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true});
    await phoneCtx.addInitScript(() => localStorage.setItem('parseh_mode', 'mobile'));
    const ph = await phoneCtx.newPage();
    watch(ph);
    await ph.goto(url(`${S}/doc/${id2}/edit`));
    await ph.waitForFunction(() => typeof openExerciseMarkdown === 'function', null, {timeout: 8000})
      .catch(async e => { throw Error(e.message + ' -- mode ' + await ph.evaluate(() => document.documentElement.dataset.mode) + ' url ' + ph.url()); });
    await ph.evaluate(text => { openExerciseMarkdown(text, {mode: 'add', onSave() {}, fromPage: {noun: 'page', list: () => [], removeLabel: '', putBackWhere: 'on the page'}}); }, CHAIN2.trimEnd());
    await ph.waitForSelector('#modal-root .ex-form-modal .ex-step-row');
    const size = await ph.locator('.ex-step-row').first().evaluate(r => {
      const box = e => { const b = e.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; };
      const q = c => r.querySelector(c);
      return {row: box(r), up: box(q('.ex-step-up')), edit: box(q('.ex-step-edit')), toggle: box(q('.ex-step-toggle')), pick: box(q('.ex-step-pick')),
              more: getComputedStyle(q('.ex-step-more')).display};
    });
    assert(size.row[1] >= 48 && size.up[1] >= 44 && size.up[0] >= 44 && size.edit[1] >= 44 && size.toggle[0] >= 44 && size.toggle[1] >= 44,
           `rows 48 px and ↑ ✎ ⋯ fingers' targets: row ${size.row}, ↑ ${size.up}, ✎ ${size.edit}, ⋯ ${size.toggle}`);
    eq(size.more, 'none', 'Duplicate, Put back and Delete are under the ⋯');
    await ph.locator('.ex-step-row').first().locator('.ex-step-toggle').tap();
    const shown = await ph.locator('.ex-step-row').first().locator('.ex-step-more .btn').evaluateAll(bs => bs.map(b => [b.textContent, b.getBoundingClientRect().height >= 44]));
    eq(shown, [['Duplicate', true], ['⤴ Put back', true], ['Delete', true]], '⋯ opens them, each a finger\'s target');
    assert(await ph.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1
      && [...document.querySelectorAll('#modal-root .ex-form-modal, #modal-root .ex-form-body')].every(e => e.scrollWidth <= e.clientWidth + 1)), 'nothing runs off the side of the screen');
    await ph.locator('.ex-step-row').first().locator('.ex-step-down').tap();
    eq(await ph.locator('.ex-step-row .ex-step-words').allTextContents(), ['Decide.', 'Where?', 'binario'], '↓ moves a step on a touch screen');
    if (ART) await ph.screenshot({path: `${ART}/exform-chain-phone-${mode}.png`});
    await phoneCtx.close();

    eq(errors, [], 'no page error, no console error');
  } finally {
    ctx.close().catch(() => {});
    try { proc.kill('SIGTERM'); } catch (_) { /* gone */ }
    await proc.status.catch(() => {});
  }
}

try {
  for (const mode of modes) await suite(mode);
  console.log(`\n${passed} checks passed`);
} finally {
  await browser.close();
}
