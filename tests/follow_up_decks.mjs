// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of FOLLOW-UP QUESTIONS IN A DECK (a0.5.4): the REAL routes (tests/decks_harness.py, both servers) on a
// temporary exercises store; a follow-up is ONE exercise of the deck, counted once, studied a step at a time.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/follow_up_decks.mjs
//   FOLLOW_UP_MODES=studio (or parseh) runs one server only; PARSEH_TEST_ARTIFACTS=<dir> saves screenshots
//
//  list)    the deck counts the chain as one exercise, and its row says "Follow-up questions · 3 steps"
//  study)   Check step -> Next step -> ... the four ratings come ONLY after the last step, the focus on Again when a
//           scored step was wrong and on Good when none was; the review carries {right, of}; Enter does it all; Skip
//           and Edit work mid-chain; a step shows the explanation it earned, so the page has no "Correct answer" box
//  mobile)  the answer bar keeps its one place: Check step, Next step and the ratings come where Check was
//  cram)    right only if EVERY scored step was right, and a chain that was not comes round again whole
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('FOLLOW_UP_MODES') || 'studio,parseh').split(',');
const ART = Deno.env.get('PARSEH_TEST_ARTIFACTS') || '';
if (ART) await Deno.mkdir(ART, {recursive: true});

async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/decks_harness.py', mode], cwd: root,
                                         stdout: 'piped', stderr: 'inherit'}).spawn();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

// a dialogue answered line by line: a choice, a true/false pair, and a card (which counts for nothing)
const CHAIN = `:::exercise follow-up
prompt: Read the short dialogue, then answer about it, one question at a time.
explanation-correct: You followed all of it.
explanation-incorrect: Read the dialogue once more, slowly.
::::exercise single-choice
prompt: Where are the two speakers?
- [ ] at home
- [x] at the station
explanation-correct: Yes: the board says *binario*.
explanation-incorrect: Look at the sign again.
::::
::::exercise true-false
prompt: Decide.
- The train leaves at nine. => false
- The speakers are late. => true
::::
::::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
::::
:::`;
// two scored steps and no card
const PAIR = `:::exercise follow-up
prompt: Two questions.
::::exercise single-choice
prompt: First
- [x] yes
- [ ] no
::::
::::exercise single-choice
prompt: Second
- [ ] no
- [x] yes
::::
:::`;
// the exercise a chain keeps company with in a deck
const PICK = ':::exercise single-choice\nprompt: Pick the greeting\n- [x] ciao\n- [ ] tavolo\n:::';

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(JSON.stringify(a) === JSON.stringify(b), `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);

async function suite(mode) {
  console.log(`== ${mode} ==`);
  const {proc, info} = await startHarness(mode);
  const url = p => `http://127.0.0.1:${info.port}${p}`;
  const errors = [];
  const ctx = await browser.newContext({viewport: {width: 1100, height: 900}});
  const watch = page => {
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => {
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text())
          && !/bad HTTP response code.*fetching the script/.test(m.text())) errors.push('console: ' + m.text());
    });
  };
  async function makeDeck(name, markdowns) {
    const made = (await (await ctx.request.post(url('/exercises/api/decks'), {data: {name, lang: 'it'}})).json()).deck;
    const ids = [];
    for (const markdown of markdowns) {
      const r = await ctx.request.post(url(`/exercises/api/decks/${made.path}/items`), {data: {markdown}});
      if (r.status() !== 201) throw Error(`could not add to ${name}: ${await r.text()}`);
      ids.push((await r.json()).item.id);
    }
    return {deck: made, ids, page: `/exercises/deck/${made.path}/`, study: `/exercises/deck/${made.path}/study`,
            cram: `/exercises/deck/${made.path}/cram`};
  }
  // an exercise never rated has no file in schedule/
  const schedule = (d, id) => {
    try { return JSON.parse(Deno.readTextFileSync(`${info.tmp}/exercises/${d.deck.path}/schedule/${id}.json`)); }
    catch (_) { return {history: [], state: {state: 'new'}}; }
  };
  const lookAt = (page, stage) => page.evaluate(stage => {
    const vis = e => !!e && !e.hidden && e.getClientRects().length > 0;
    const c = document.querySelector(`${stage} .ex-chain`), by = id => document.querySelector(id);
    return {say: c && c.querySelector('.ex-strip-say').textContent,
            chainBar: !!c && [...c.querySelectorAll('.ex-step-bar')].some(vis),
            check: vis(by('#btn-check')) ? by('#btn-check').textContent : '', show: vis(by('#btn-show')) ? by('#btn-show').textContent : '',
            step: vis(by('#btn-step')) ? by('#btn-step').textContent : '',
            result: vis(by('#study-result')) ? by('#study-result').textContent : '', bar: vis(by('#rating-bar')),
            focus: document.activeElement ? (document.activeElement.dataset.rating || document.activeElement.id || document.activeElement.className) : ''};
  }, stage);
  const reviewed = page => page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/review'));

  try {
    const d = await makeDeck('Dialoghi', [CHAIN, PICK]);
    const page = await ctx.newPage();
    watch(page);

    /* ---------------- list ---------------- */
    console.log('list) one exercise, and it says how long it is');
    const items = (await (await ctx.request.get(url(`/exercises/api/decks/${d.deck.path}`))).json()).items;
    eq([items.length, items[0].subtype, items[0].steps, items[1].steps || 0], [2, 'follow-up', 3, 0],
       'the deck holds two exercises: the chain (3 steps) and the choice');
    const listed = (await (await ctx.request.get(url('/exercises/api/decks?lang=it'))).json()).decks.find(x => x.path === d.deck.path);
    eq([listed.counts.new, listed.study.new], [2, 2], 'a chain is ONE exercise: two new, two to study');
    await page.goto(url(d.page));
    await page.waitForSelector('.dk-row');
    const kickers = await page.locator('.dk-row .ex-kicker').allTextContents();
    eq(kickers, ['Follow-up questions · 3 steps', 'Choose one answer'], 'the row says “Follow-up questions · 3 steps”');
    assert((await page.locator('.dk-row .dk-select').first().getAttribute('aria-label')).includes('Follow-up questions, 3 steps'),
           'and so does the checkbox\'s label');
    await page.locator('.dk-row .dk-excerpt').first().click();
    await page.waitForSelector('.dk-row-preview:not([hidden]) .ex-chain');
    assert(await page.locator('.dk-row-preview .ex-chain .ex-step').count() === 3, 'the row opens on the chain, its three steps');
    assert(await page.locator('.dk-row-preview .ex-step-check:visible, .dk-row-preview .ex-step-show:visible').count() === 0
           && await page.locator('.dk-row-preview .ex-showall:visible').count() === 1,
           'a preview has no Check step to press, and Show every step instead');

    /* ---------------- study ---------------- */
    console.log('study) a step at a time, the ratings after the last');
    await page.goto(url(d.study));
    await page.waitForSelector('#study-stage .ex-chain');
    let l = await lookAt(page, '#study-stage');
    eq([l.say, l.check, l.show, l.step, l.bar, l.chainBar], ['Step 1 of 3', 'Check step', '', '', false, false],
       'it opens on step 1 of 3: Check step in the answer bar, no ratings, none of the chain\'s own buttons');
    assert((await page.locator('.dk-keys').textContent()).startsWith('Enter checks a step'), 'the key line says what Enter does');
    assert(await page.locator('#study-counts .dk-n.dk-new').textContent() === '2', 'two new, as the deck says');
    // step 1 wrongly
    await page.locator('#study-stage .ex-step[data-step="1"] [data-correct="0"]').first().click();
    await page.click('#btn-check');
    l = await lookAt(page, '#study-stage');
    eq([l.result, l.check, l.step, l.bar, l.focus], ['Not quite', '', 'Next step', false, 'btn-step'],
       'Check step: Not quite, then Next step (with the focus) in the same place, still no ratings');
    eq(await page.locator('#study-stage .ex-step[data-step="1"] .ex-explanation:visible').allTextContents(), ['Look at the sign again.'],
       'the explanation the wrong answer earned is between the steps');
    assert(await page.locator('#study-solution').isHidden(), 'and there is no “Correct answer” box: each step says what it has to say');
    await page.click('#btn-step');
    l = await lookAt(page, '#study-stage');
    eq([l.say, l.check, l.result], ['Step 2 of 3', 'Check step', ''], 'Next step brings step 2: Check step again, the result cleared');
    // step 2 rightly, by the keyboard alone: Enter checks, Enter goes on
    await page.evaluate(() => document.querySelectorAll('#study-stage .ex-step[data-step="2"] .ex-choice-group').forEach(g => g.querySelector('[data-correct="1"]').click()));
    await page.keyboard.press('Enter');
    l = await lookAt(page, '#study-stage');
    eq([l.result, l.step], ['Correct', 'Next step'], 'Enter checks the step');
    await page.keyboard.press('Enter');
    l = await lookAt(page, '#study-stage');
    eq([l.say, l.show, l.check], ['Step 3 of 3', 'Show answer', ''], 'and goes on: a card\'s step has Show answer');
    await page.click('#btn-show');
    await page.waitForSelector('#rating-bar:not([hidden])');
    l = await lookAt(page, '#study-stage');
    eq([l.result, l.show, l.step, l.bar, l.focus], ['1 of 2 steps right', '', '', true, 'again'],
       'after the LAST step: the result in words, the four ratings, the focus on Again (a scored step was wrong)');
    assert((await page.locator('#rating-bar .dk-ivl').allTextContents()).length === 4, 'with their four intervals');
    eq(await page.locator('#study-stage .ex-chain > .ex-explanation:visible').allTextContents(), ['Read the dialogue once more, slowly.'],
       'the chain says its own explanation for a wrong result');
    if (ART) await page.screenshot({path: `${ART}/follow-up-study-${mode}.png`});
    const pending = reviewed(page);
    await page.keyboard.press('1');
    const sent = (await pending).request().postDataJSON();
    eq([sent.item, sent.rating, sent.result, sent.steps], [d.ids[0], 'again', false, {right: 1, of: 2}],
       'the review carries the rating, the result (false) and the steps {right: 1, of: 2}');
    const hist = schedule(d, d.ids[0]).history;
    eq([hist.length, hist[0].rating, hist[0].result, hist[0].steps], [1, 'again', false, {right: 1, of: 2}], 'the history row keeps the steps');
    await page.waitForSelector('#study-stage .exercise[data-subtype="single-choice"]');
    assert(await page.locator('#study-stage .ex-chain').count() === 0, 'then the next exercise: the choice');

    // a chain answered all right -> the focus is on Good
    const e = await makeDeck('Due passi', [PAIR]);
    await page.goto(url(e.study));
    await page.waitForSelector('#study-stage .ex-chain');
    for (const n of [1, 2]) {
      await page.locator(`#study-stage .ex-step[data-step="${n}"] [data-correct="1"]`).first().click();
      await page.click('#btn-check');
      if (n === 1) await page.click('#btn-step');
    }
    await page.waitForSelector('#rating-bar:not([hidden])');
    l = await lookAt(page, '#study-stage');
    eq([l.result, l.focus, l.step], ['2 of 2 steps right', 'good', ''], 'every step right: “2 of 2 steps right”, the focus on Good');
    const ok = reviewed(page);
    await page.click('#rating-bar [data-rating="good"]');
    const got = (await ok).request().postDataJSON();
    eq([got.result, got.steps], [true, {right: 2, of: 2}], 'and the review says true, {right: 2, of: 2}');
    const row = schedule(e, e.ids[0]).history;
    eq([row.length, row[0].rating, row[0].result, row[0].steps], [1, 'good', true, {right: 2, of: 2}], 'the history row: good, true, {right: 2, of: 2}');
    await page.waitForFunction(() => document.querySelector('#rating-bar').hidden);
    l = await lookAt(page, '#study-stage');
    eq([l.say || 'done', l.bar], ['Step 1 of 2', false], 'a chain in its learning step comes round again whole, from step 1 (as any exercise does)');

    // Skip and Edit, half-way
    const f = await makeDeck('Passi', [CHAIN, PICK]);
    await page.goto(url(f.study));
    await page.waitForSelector('#study-stage .ex-chain');
    await page.locator('#study-stage .ex-step[data-step="1"] [data-correct="1"]').first().click();
    await page.click('#btn-check');
    await page.click('#btn-edit-card');
    await page.waitForSelector('#modal-root .ex-form-modal .ex-step-row');
    assert(await page.locator('#modal-root .ex-step-row').count() === 3
           && !await page.locator('#modal-root textarea').evaluateAll(xs => xs.some(x => x.value.includes('::::exercise'))),
           'Edit opens the follow-up\'s form: its three steps in a list, not the fenced source');
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#modal-root .modal-overlay'));
    await page.click('#btn-skip');
    await page.waitForSelector('#study-stage .exercise[data-subtype="single-choice"]');
    assert(await page.locator('#study-stage .ex-chain').count() === 0 && await page.locator('#rating-bar').isHidden(),
           'Skip, half-way, leaves the chain unrated and goes to the next exercise');
    assert(schedule(f, f.ids[0]).history.length === 0, 'and nothing was scheduled for it');

    /* ---------------- mobile ---------------- */
    console.log('mobile) the answer bar keeps its one place');
    const phoneCtx = await browser.newContext({viewport: {width: 390, height: 780}});
    await phoneCtx.addInitScript(() => localStorage.setItem('parseh_mode', 'mobile'));
    const mob = await phoneCtx.newPage();
    watch(mob);
    await mob.goto(url(f.study));
    await mob.waitForSelector('#study-stage .ex-chain');
    await mob.waitForFunction(() => document.documentElement.dataset.mode === 'mobile');
    const box = (page, id) => page.locator(id).boundingBox();
    const same = (a, b) => !!a && !!b && ['x', 'y', 'width', 'height'].every(k => Math.abs(a[k] - b[k]) < 2);
    const first = await box(mob, '#btn-check');
    assert(!!first && first.width > 100 && first.y > 400, `Check step is in the answer bar at the foot of a phone (y ${Math.round(first.y)})`);
    await mob.locator('#study-stage .ex-step[data-step="1"] [data-correct="1"]').first().click();
    await mob.click('#btn-check');
    const second = await box(mob, '#btn-step');
    assert(same(first, second), `Next step is where Check step was (${JSON.stringify(first)} / ${JSON.stringify(second)})`);
    // to the card step: Show answer is in the same place too
    await mob.click('#btn-step');
    await mob.evaluate(() => document.querySelectorAll('#study-stage .ex-step[data-step="2"] .ex-choice-group').forEach(x => x.querySelector('[data-correct="1"]').click()));
    await mob.click('#btn-check');
    await mob.click('#btn-step');
    assert(same(first, await box(mob, '#btn-show')), 'and so is Show answer, on a card\'s step');
    await mob.click('#btn-show');
    await mob.waitForSelector('#rating-bar:not([hidden])');
    const ratings = await mob.locator('#rating-bar [data-rating]').evaluateAll(bs => bs.map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.y), Math.round(r.height)]; }));
    assert(ratings.every(r => r[1] >= 48 && r[0] > 400), `then the four ratings, each 48 px or more, at the foot (${JSON.stringify(ratings)})`);
    assert(await mob.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no sideways scroll');
    if (ART) await mob.screenshot({path: `${ART}/follow-up-study-phone-${mode}.png`});
    await phoneCtx.close();

    /* ---------------- cram ---------------- */
    console.log('cram) right only if every step was');
    const g = await makeDeck('Ripasso', [CHAIN]);
    const cram = await ctx.newPage();
    watch(cram);
    // as a person does it: tick the exercise in Browse, then Cram
    await cram.goto(url(g.page));
    await cram.waitForSelector('.dk-row');
    await cram.locator(`.dk-row[data-id="${g.ids[0]}"] .dk-select`).check();
    await Promise.all([cram.waitForURL(url(g.cram)), cram.click('#btn-cram')]);
    await cram.waitForSelector('#cram-stage .ex-chain', {timeout: 8000})
      .catch(async () => { throw Error('FAIL: cram shows no chain: ' + (await cram.locator('main').innerText()).slice(0, 500) + ' | errors ' + errors.join(' ; ')); });
    const crammed = async () => cram.evaluate(() => {
      const vis = e => !!e && !e.hidden && e.getClientRects().length > 0, by = i => document.querySelector(i);
      return {say: by('#cram-stage .ex-strip-say')?.textContent || '', check: vis(by('#cram-check')) ? by('#cram-check').textContent : '',
              show: vis(by('#cram-show')) ? by('#cram-show').textContent : '', step: vis(by('#cram-step')) ? by('#cram-step').textContent : '',
              next: vis(by('#cram-next')) ? by('#cram-next').textContent : '', result: vis(by('#cram-result')) ? by('#cram-result').textContent : '',
              progress: by('#cram-progress').textContent, skip: vis(by('#cram-skip'))};
    });
    let c = await crammed();
    eq([c.say, c.check, c.show, c.step, c.next, c.progress], ['Step 1 of 3', 'Check step', '', '', '', '1 of 1'], 'cram opens on step 1: Check step');
    // wrongly
    await cram.locator('#cram-stage .ex-step[data-step="1"] [data-correct="0"]').first().click();
    await cram.click('#cram-check');
    c = await crammed();
    eq([c.result, c.step, c.check], ['Not quite', 'Next step', ''], 'Check step, then Next step');
    await cram.click('#cram-step');
    await cram.evaluate(() => document.querySelectorAll('#cram-stage .ex-step[data-step="2"] .ex-choice-group').forEach(x => x.querySelector('[data-correct="1"]').click()));
    await cram.click('#cram-check');
    await cram.click('#cram-step');
    c = await crammed();
    eq([c.say, c.show], ['Step 3 of 3', 'Show answer'], 'the card\'s step: Show answer');
    await cram.click('#cram-show');
    await cram.waitForFunction(() => !document.querySelector('#cram-next').hidden);
    c = await crammed();
    eq([c.result, c.next, c.progress, c.skip, c.show, c.step], ['1 of 2 steps right', 'Next exercise', '1 of 2', false, '', ''],
       'a wrong step makes the chain wrong: it is put back (1 of 2), and only Next exercise is left');
    await cram.click('#cram-next');
    await cram.waitForSelector('#cram-stage .ex-chain .ex-step[data-step="1"]');
    c = await crammed();
    eq([c.say, c.progress, c.check], ['Step 1 of 3', '2 of 2', 'Check step'], 'it comes round again whole, from step 1');
    for (const n of [1, 2]) {
      await cram.evaluate(n => document.querySelectorAll(`#cram-stage .ex-step[data-step="${n}"] .ex-choice-group`).forEach(x => x.querySelector('[data-correct="1"]').click()), n);
      await cram.click('#cram-check');
      await cram.click('#cram-step');
    }
    await cram.click('#cram-show');
    await cram.waitForFunction(() => document.querySelector('#cram-next') && !document.querySelector('#cram-next').hidden);
    c = await crammed();
    eq([c.result, c.next], ['2 of 2 steps right', 'Finish'], 'the second time every step is right: Finish');
    await cram.click('#cram-next');
    await cram.waitForSelector('#cram-done:not([hidden])');
    eq(await cram.locator('#cram-tally').textContent(), '1 exercise: 1 wrong at least once.', 'the tally counts the chain as one exercise, wrong once');
    eq(await cram.locator('#cram-wrong-list .ex-kicker').allTextContents(), ['Follow-up questions · 3 steps'], 'the list of the wrong ones names it, with its steps');
    await cram.click('#cram-wrong-list .dk-cram-item >> nth=0');
    await cram.waitForSelector('#cram-wrong-list .dk-cram-solved:not([hidden]) .ex-chain');
    assert(await cram.locator('#cram-wrong-list .dk-cram-solved .ex-step').count() === 3, 'opened, it shows the chain with its three steps');
    assert(await cram.locator('#cram-wrong-list .dk-cram-solved .ex-step-check:visible, #cram-wrong-list .dk-cram-solved .ex-step-show:visible').count() === 0,
           'with nothing left to check');
    // cram never schedules
    eq(schedule(g, g.ids[0]).history.length, 0, 'cramming wrote nothing to the schedule');


    /* ---------------- form ---------------- */
    console.log('form) the deck\'s own list: edit, make a chain of the ticked ones, from the deck, put back');
    const QA = ':::exercise single-choice\nprompt: Qual è la stazione?\n- [x] la stazione\n- [ ] la scuola\n:::';
    const QB = ':::exercise true-false\nprompt: Vero o falso?\n- Il treno parte alle nove. => false\n:::';
    const QC = ':::exercise yes-no\nprompt: Sì o no?\n- Il binario è il secondo? => yes\n:::';
    const h = await makeDeck('Formulario', [CHAIN, QA, QB, QC]);
    const fp = await ctx.newPage();
    watch(fp);
    const rowsWords = () => fp.locator('#modal-root .ex-step-row .ex-step-words').allTextContents();
    await fp.goto(url(h.page));
    await fp.waitForSelector('.dk-row');
    assert(await fp.locator('#btn-bulk-chain').isDisabled(), 'Make a follow-up chain of these… is off while nothing is ticked');
    // edit the chain in the list
    await fp.locator('.dk-row').first().locator('[data-x="edit"]').click();
    await fp.waitForSelector('#modal-root .ex-form-modal .ex-step-row');
    eq(await fp.locator('#modal-root .ex-form-head h3').textContent(), 'Edit Follow-up questions', 'Edit on the chain opens its form');
    eq((await rowsWords()).length, 3, 'with its three steps');
    // + From this deck…
    await fp.click('[data-x="from-page"]');
    await fp.waitForSelector('.ex-from-page .ex-from-item');
    assert(await fp.locator('.ex-from-page h3').textContent() === 'Steps from this deck', 'the frame says it is the deck\'s');
    eq(await fp.locator('.ex-from-item .ex-from-words').allTextContents(), ['Qual è la stazione?', 'Vero o falso?', 'Sì o no?'], 'the deck\'s other exercises are listed (not the chain being edited)');
    assert(/Remove them from the deck once they are in the chain \(their study history goes with them\)/.test(await fp.locator('.ex-from-remove').textContent()), 'the box says their history goes with them');
    await fp.locator('.ex-from-item').nth(0).locator('input').check();
    await fp.locator('.ex-from-page [data-x="add"]').click();
    await fp.waitForFunction(() => !document.querySelector('.ex-from-page'));
    eq((await rowsWords()).length, 4, 'one more step');
    // put the card back as an exercise of the deck
    await fp.locator('#modal-root .ex-step-row').nth(2).locator('.ex-step-putback').click();
    await fp.locator('#modal-root [data-x="save"]').click();
    await fp.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    await fp.waitForFunction(() => document.querySelectorAll('.dk-row').length === 4);
    let now = (await (await ctx.request.get(url(`/exercises/api/decks/${h.deck.path}`))).json()).items;
    const chain = now.find(i => i.subtype === 'follow-up');
    assert(chain.steps === 3 && chain.markdown.includes('Qual è la stazione?') && !chain.markdown.includes('flashcard'), 'the chain has its first steps and the deck\'s exercise, and not the card');
    const cardBack = now.find(i => i.subtype === 'flashcard');
    assert(!!cardBack && cardBack.markdown.includes('target: [binario]{tl}') && cardBack.steps === 0, 'the card is an exercise of the deck now');
    eq(now.map(i => i.subtype).sort(), ['flashcard', 'follow-up', 'true-false', 'yes-no'], 'the box was ticked: the exercise that became a step is out of the deck, the others stay');
    // the bulk action: tick two, make a chain of them, taking them out of the deck
    await fp.reload();
    await fp.waitForSelector('.dk-row');
    const tick = async text => fp.locator('.dk-row', {hasText: text}).locator('.dk-select').check();
    await tick('Vero o falso?');
    await tick('Sì o no?');
    assert(await fp.locator('#btn-bulk-chain').isEnabled(), 'Make a follow-up chain of these… is on with two ticked');
    await fp.click('#btn-bulk-chain');
    await fp.waitForSelector('#modal-root .ex-form-modal .ex-step-row');
    eq(await fp.locator('#modal-root .ex-form-head h3').textContent(), 'Add Follow-up questions', 'it opens a new follow-up…');
    eq(await rowsWords(), ['Vero o falso?', 'Sì o no?'], '…with the ticked exercises already its steps, in the list\'s order');
    assert(await fp.locator('.ex-steps-originals').isVisible() && !await fp.locator('.ex-steps-originals input').isChecked(), 'and the box to take the originals out of the deck, not ticked');
    await fp.locator('.ex-steps-originals input').check();
    await fp.locator('#modal-root [data-x="save"]').click();
    await fp.waitForFunction(() => !document.querySelector('#modal-root .ex-form-modal'));
    await fp.waitForFunction(() => [...document.querySelectorAll('.dk-row .ex-kicker')].filter(k => /Follow-up/.test(k.textContent)).length === 2);
    now = (await (await ctx.request.get(url(`/exercises/api/decks/${h.deck.path}`))).json()).items;
    assert(now.length === 3 && !now.some(i => i.subtype === 'true-false' || i.subtype === 'yes-no'), 'the two exercises it was made of are out of the deck');
    eq(now.filter(i => i.subtype === 'follow-up').map(i => i.steps).sort(), [2, 3], 'and a second follow-up, of two steps, is in');
    // the bulk action refuses what cannot be a step
    await fp.reload();
    await fp.waitForSelector('.dk-row');
    await tick('Read the short dialogue');
    await tick('binario');
    await fp.click('#btn-bulk-chain');
    assert(/is a follow-up already/.test(await fp.locator('#toast').textContent()), 'a follow-up cannot be a step: said, and nothing opens');
    assert(await fp.locator('#modal-root .ex-form-modal').count() === 0, 'no form');
    // the study page's Edit opens the same form
    await fp.goto(url(h.study));
    await fp.waitForSelector('#study-stage .exercise');
    await fp.evaluate(() => { const c = document.querySelector('#study-stage .ex-chain'); if (!c) document.querySelector('#btn-skip').click(); });
    await fp.waitForSelector('#study-stage .ex-chain');
    await fp.click('#btn-edit-card');
    await fp.waitForSelector('#modal-root .ex-form-modal .ex-step-row');
    assert(await fp.locator('#modal-root .ex-step-row').count() >= 2, 'Edit on the study page opens the chain form with its steps');
    await fp.locator('#modal-root [data-x="cancel"]').last().click();


    /* ---------------- the reading view ---------------- */
    console.log('page) the exercises of a page, made one follow-up of a deck');
    const S = info.studio;
    const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), c => c.charCodeAt(0));
    const doc = await (await ctx.request.post(url(S + '/api/docs'), {data: {markdown:
      `---\ntitle: A dialogue to follow up\ntarget: it\n---\n\n:::exercise single-choice\nprompt: Dove sono?\nimage: images/cat.png\n- [x] alla stazione\n- [ ] a casa\n:::\n\n`
      + `:::exercise true-false\nprompt: Vero o falso?\n- Il treno parte alle nove. => false\n:::\n\n:::exercise yes-no\nprompt: Sì o no?\n- Il binario è il secondo? => yes\n:::\n`}})).json();
    const docId = doc.id || (doc.doc && doc.doc.id) || (doc.meta && doc.meta.id);
    await ctx.request.post(url(`${S}/api/docs/${docId}/images?name=cat.png`), {data: Buffer.from(png), headers: {'Content-Type': 'image/png'}});
    const target = await makeDeck('Da una pagina', []);
    const dp = await ctx.newPage();
    watch(dp);
    await dp.goto(url(`${S}/doc/${docId}`));
    await dp.waitForSelector('#btn-add-all:not([hidden])');
    await dp.click('#btn-add-all');
    await dp.waitForSelector(`.ex-all-modal select option[value="${target.deck.path}"]`, {state: 'attached'});
    await dp.selectOption('.ex-all-modal select[data-x="deck"]', target.deck.path);
    assert(await dp.locator('.ex-all-modal [data-x="chain"]').isEnabled() && /Make a follow-up chain of these/.test(await dp.locator('.ex-all-modal [data-x="chain"]').textContent()),
           'with three exercises ticked the dialog offers Make a follow-up chain of these…');
    await dp.locator('.ex-all-item input').nth(2).uncheck();
    await dp.locator('.ex-all-item input').nth(1).uncheck();
    assert(await dp.locator('.ex-all-modal [data-x="chain"]').isDisabled(), 'with one ticked it is off: a follow-up has two steps at least');
    await dp.locator('.ex-all-item input').nth(1).check();
    await dp.locator('.ex-all-item input').nth(2).check();
    await dp.locator('.ex-all-modal [data-x="chain"]').click();
    await dp.waitForFunction(() => !document.querySelector('.ex-all-modal'));
    assert(/Added one follow-up of 3 steps to “Da una pagina”/.test(await dp.locator('#toast').textContent()), 'it says: one follow-up of 3 steps');
    const made = (await (await ctx.request.get(url(`/exercises/api/decks/${target.deck.path}`))).json()).items;
    eq(made.map(i => [i.subtype, i.steps]), [['follow-up', 3]], 'the deck has ONE exercise, a follow-up of three steps');
    assert(made[0].markdown.includes('::::exercise single-choice') && made[0].markdown.indexOf('Dove sono?') < made[0].markdown.indexOf('Vero o falso?'),
           'in the page\'s order');
    const pic = await ctx.request.get(url(`/exercises/media/${target.deck.path}/images/cat.png`));
    assert(pic.status() === 200, 'and the picture of a step went with it');
    eq(made[0].origin.label, 'Follow-up of 3 exercises', 'its origin says where it came from');
    // again: the same follow-up is refused, unless asked for twice
    await dp.click('#btn-add-all');
    await dp.waitForSelector(`.ex-all-modal select option[value="${target.deck.path}"]`, {state: 'attached'});
    await dp.selectOption('.ex-all-modal select[data-x="deck"]', target.deck.path);
    await dp.locator('.ex-all-modal [data-x="chain"]').click();
    await dp.waitForFunction(() => /already in/.test(document.querySelector('#toast').textContent));
    assert(await dp.locator('.ex-all-modal').count() === 1, 'the same chain again: refused, and the dialog stays for another choice');
    await dp.locator('.ex-all-modal [data-x="cancel"]').click();

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
