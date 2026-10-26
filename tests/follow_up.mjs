// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of FOLLOW-UP QUESTIONS (a0.5.4, the fourteenth exercise type): a chain of exercises answered one after the
// other, drawn by htmlgen and bound by app.js (bindExercises -> bindChain) on a page of the studio's own sheet and script.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/follow_up.mjs
//   PARSEH_TEST_ARTIFACTS=<dir> also saves screenshots
//
//  page)     the steps come one by one: the strip says Step 1 of 3 and a dot for each; only step 1 is shown, with Check
//            step under it; the check marks the step as any exercise is marked, says Correct or Not quite, shows the
//            explanation that answer earned BETWEEN the steps (right or wrong), locks the step and offers Next step, which
//            brings the next one scrolled into view, given the focus and announced (Step 2 of 3); a card's step has Show
//            answer; from the third step on the steps before the last two fold into "Earlier steps (n)"; at the last
//            check the chain says its result in words and its own explanation; Enter does what the button in view does
//  count)    Check exercises counts every scored step as an exercise of the page and a step not come to as unanswered
//            (counted, not judged), and a chain left half-way says "2 of 4 steps answered"; the chain is not scored
//  preview)  the editor's preview shows the stored answers, Next step goes on unchecked and Show every step unfolds all
//  paper...  (tests/follow_up_paper.py: the TeX)
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
Deno.chdir(root);
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const ART = Deno.env.get('PARSEH_TEST_ARTIFACTS') || '';
if (ART) await Deno.mkdir(ART, {recursive: true});
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(JSON.stringify(a) === JSON.stringify(b), `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// a dialogue answered line by line: a choice, a true/false pair, a word built up, and a card -- the last a card
const DOC = `---
title: A dialogue
target: it
---

:::exercise follow-up
prompt: Read the short dialogue, then answer about it, one question at a time.
explanation-correct: You followed all of it.
explanation-incorrect: Read the dialogue once more, slowly.
::::exercise single-choice
prompt: Where are the two speakers?
- [ ] at home
- [x] at the station
- [ ] at school
explanation-correct: Yes: the board says *binario*.
explanation-incorrect: Look at the sign again.
::::
::::exercise true-false
prompt: Decide.
- The train leaves at nine. => false
- The speakers are late. => true
explanation-correct: The announcement said eight.
::::
::::exercise single-choice
prompt: Which platform?
- [x] the second
- [ ] the first
::::
::::exercise flashcard
card-type: vocab
target: [binario]{tl}
meaning: platform
::::
:::

:::exercise single-choice
prompt: An exercise of its own, after the chain.
- [x] yes
- [ ] no
:::
`;

async function render(preview = false) {
  const code = `import sys,json;sys.path[:0]=['markdown/exlex','markdown/app','lib'];import htmlgen;print(json.dumps(htmlgen.render_document(sys.argv[1],editor_preview=${preview ? 'True' : 'False'})['html']))`;
  const out = await new Deno.Command(python, {args: ['-c', code, DOC], stdout: 'piped', stderr: 'piped'}).output();
  if (!out.success) throw Error(new TextDecoder().decode(out.stderr));
  return JSON.parse(new TextDecoder().decode(out.stdout));
}
const appScript = (await Deno.readTextFile(root + '/markdown/app/static/app.js')).replace('__FOLD__', '(s => String(s).toLowerCase())');
const appCss = (await Deno.readTextFile(root + '/markdown/app/static/sheet.css')) + '\n' + (await Deno.readTextFile(root + '/markdown/app/static/app.css'));

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
async function open(preview = false) {
  const page = await browser.newPage({viewport: {width: 900, height: 900}});
  page.errors = [];
  page.on('pageerror', e => page.errors.push(e.message));
  await page.setContent(`<body data-page="noop"><article id="sheet" class="sheet" data-lang="it">${await render(preview)}</article><div id="modal-root"></div></body>`);
  await page.addStyleTag({content: appCss});
  await page.addScriptTag({content: appScript});
  await page.evaluate(p => { window.__run = bindExercises(document.querySelector('#sheet'), {preview: p}); }, preview);
  return page;
}
const shot = async (page, name) => { if (ART) await page.screenshot({path: `${ART}/follow-up-${name}.png`}); };
// what a person sees of the chain right now
const look = page => page.evaluate(() => {
  const c = document.querySelector('.ex-chain'), vis = e => !!e && !e.hidden && e.getClientRects().length > 0 && !e.closest('details:not([open])') || (!!e && e.matches('details') && !e.hidden);
  const steps = [...c.querySelectorAll('.ex-step')];
  return {say: c.querySelector('.ex-strip-say').textContent, step: c.dataset.step, steps: c.dataset.steps, answered: c.dataset.answered,
          shown: steps.map(s => vis(s)), dots: [...c.querySelectorAll('.ex-dot')].map(d => d.textContent + (d.classList.contains('on') ? '*' : '') + (d.classList.contains('done') ? '+' : '')),
          earlier: vis(c.querySelector('.ex-earlier')) ? +c.querySelector('.ex-earlier-n').textContent : 0,
          earlierHolds: [...c.querySelectorAll('.ex-earlier-body > .ex-step')].map(s => s.dataset.step),
          result: vis(c.querySelector('.ex-chain-result')) ? c.querySelector('.ex-chain-result').textContent : '',
          focus: document.activeElement && document.activeElement.closest('.ex-step') ? document.activeElement.closest('.ex-step').dataset.step : null,
          active: document.activeElement ? document.activeElement.className : ''};
});
const stepBar = (page, n) => page.evaluate(n => {
  const s = document.querySelector(`.ex-step[data-step="${n}"]`), vis = e => !!e && !e.hidden && e.getClientRects().length > 0;
  const go = s.querySelector('.ex-step-check, .ex-step-show'), next = s.querySelector('.ex-step-next');
  return {go: vis(go) ? go.textContent : '', next: vis(next) ? next.textContent : '', result: s.querySelector('.ex-step-result').textContent,
          explained: [...s.querySelectorAll('.ex-explanation')].filter(vis).map(e => e.textContent), locked: !!s.querySelector('.ex-body') && s.querySelector('.ex-body').inert,
          marked: s.querySelector(':scope > .exercise').classList.contains('correct') ? 'correct' : s.querySelector(':scope > .exercise').classList.contains('incorrect') ? 'incorrect' : ''};
}, n);
const click = (page, sel) => page.evaluate(sel => document.querySelector(sel).click(), sel);

try {
  /* ---------------- the markup, as the studio draws it ---------------- */
  console.log('page) one step after the other');
  let p = await open();
  eq(await p.evaluate(() => [document.querySelectorAll('.ex-chain').length, document.querySelectorAll('.ex-chain .ex-step').length,
      document.querySelector('.ex-chain').dataset.scored, document.querySelector('.ex-chain .ex-kicker').textContent]),
     [1, 4, '0', 'Follow-up questions'], 'one chain of four steps, not scored itself, with its kicker');
  eq(await p.evaluate(() => [...document.querySelectorAll('[data-scored="1"]')].length), 4, 'the three scored steps and the exercise after it are the page\'s exercises (the card is not)');
  eq((await p.evaluate(() => window.__run.exercises.map(e => e.dataset.exercise))).join(), '1,2,3,4,5,6', 'every exercise of the page is numbered in order, the chain first, then its steps, then the one after');
  let l = await look(p);
  eq([l.say, l.step, l.steps, l.shown, l.dots], ['Step 1 of 4', '1', '4', [true, false, false, false], ['1*', '2', '3', '4']], 'the strip says Step 1 of 4 with a dot for each, and only step 1 is shown');
  eq(await p.evaluate(() => document.querySelector('.ex-strip-say').getAttribute('role')), 'status', 'the strip is a live region: a new step is announced');
  let b = await stepBar(p, 1);
  eq([b.go, b.next], ['Check step', ''], 'under it Check step, and no Next step yet');
  await shot(p, 'step1');

  // step 1: checked without an answer -> wrong, and what the wrong answer earned is shown right there
  await click(p, '.ex-step[data-step="1"] .ex-step-check');
  b = await stepBar(p, 1);
  eq([b.result, b.marked, b.locked, b.go, b.next], ['Not quite', 'incorrect', true, '', 'Next step'], 'Check step marks it, says Not quite, locks the answer and offers Next step');
  eq(b.explained, ['Look at the sign again.'], 'the explanation of a wrong answer is shown between this step and the next');
  l = await look(p);
  eq([l.shown, l.answered, l.dots[0], l.active], [[true, false, false, false], '1', '✓*+', 'btn primary ex-step-next'], 'the next step is NOT revealed by the check; Next step has the focus; dot 1 is ticked');
  await click(p, '.ex-step[data-step="1"] .ex-step-next');
  l = await look(p);
  eq([l.say, l.step, l.shown, l.dots, l.focus], ['Step 2 of 4', '2', [true, true, false, false], ['✓+', '2*', '3', '4'], '2'], 'Next step brings step 2 under step 1, announced, with the focus on it');
  assert((await look(p)).earlier === 0, 'two steps shown, nothing folded yet');
  eq((await stepBar(p, 1)).locked, true, 'earlier steps stay on the page, locked, with their explanations');

  // step 2: answered right -> the explanation of a right answer
  await p.evaluate(() => {
    const s = document.querySelector('.ex-step[data-step="2"]');
    s.querySelectorAll('.ex-choice-group').forEach(g => g.querySelector('[data-correct="1"]').click());
  });
  // Enter does what the button in view does: here Check step (the focus is on the step)
  await p.evaluate(() => document.querySelector('.ex-step[data-step="2"]').focus());
  await p.keyboard.press('Enter');
  b = await stepBar(p, 2);
  eq([b.result, b.marked, b.explained], ['Correct', 'correct', ['The announcement said eight.']], 'Enter checks the step; a right answer shows its right-answer explanation');
  await p.keyboard.press('Enter');
  eq([(await look(p)).say, (await look(p)).focus], ['Step 3 of 4', '3'], 'and Enter again moves on');
  l = await look(p);
  eq([l.shown, l.earlier, l.earlierHolds], [[false, true, true, false], 1, ['1']], 'from the third step on the steps before the last two fold into "Earlier steps (1)", which holds step 1');
  assert(await p.evaluate(() => { const d = document.querySelector('.ex-earlier'); return d.querySelector('summary').textContent.replace(/\s+/g, ' ') === 'Earlier steps (1)' && !d.open; }), 'a line that opens on a click');
  await shot(p, 'step3');

  // step 3, then the card
  await p.evaluate(() => document.querySelector('.ex-step[data-step="3"] [data-correct="1"]').click());
  await click(p, '.ex-step[data-step="3"] .ex-step-check');
  await click(p, '.ex-step[data-step="3"] .ex-step-next');
  l = await look(p);
  eq([l.say, l.earlier, l.earlierHolds], ['Step 4 of 4', 2, ['1', '2']], 'the fourth step folds the second too: "Earlier steps (2)"');
  b = await stepBar(p, 4);
  eq([b.go, b.next], ['Show answer', ''], 'a card\'s step has Show answer, and no Next step (it is the last)');
  assert(await p.evaluate(() => { const f = document.querySelector('.ex-step[data-step="4"] .ex-flashcard'); return !!f && !f.classList.contains('flipped'); }), 'the card is not turned yet');
  await click(p, '.ex-step[data-step="4"] .ex-step-show');
  assert(await p.evaluate(() => document.querySelector('.ex-step[data-step="4"] .ex-flashcard').classList.contains('flipped')), 'Show answer turns the card');
  l = await look(p);
  eq([l.result, l.dots, l.say], ['2 of 3 steps right', ['✓+', '✓+', '✓+', '✓+'], 'All 4 steps'], 'at the last step the chain says its result in words: the card counts for nothing, the first step was wrong');
  eq(await p.evaluate(() => [...document.querySelectorAll('.ex-chain > .ex-explanation')].filter(e => !e.hidden).map(e => e.textContent)), ['Read the dialogue once more, slowly.'],
     'and its own explanation, the one a wrong result earned');
  assert(await p.evaluate(() => document.querySelector('.ex-chain').dataset.answered === '4'), 'every step is counted as answered');
  await shot(p, 'done');
  eq(await p.evaluate(() => [...document.querySelectorAll('.ex-explanation:not(.ex-chain > .ex-explanation)')].filter(e => !e.hidden).length >= 2), true, 'every step keeps the explanation it earned');
  eq(p.errors, [], 'no page error');
  await p.close();

  /* ---------------- Check exercises ---------------- */
  console.log('count) Check exercises counts the steps');
  p = await open();
  await p.evaluate(() => document.querySelector('.ex-step[data-step="1"] [data-correct="1"]').click());
  await click(p, '.ex-step[data-step="1"] .ex-step-check');
  await click(p, '.ex-correct-all');
  eq(await p.evaluate(() => document.querySelector('.ex-score').textContent), '1 / 4 correct', 'one step right of the four scored steps and the exercise after, three of them not answered: counted, not judged');
  l = await look(p);
  eq([l.result, l.shown], ['1 of 4 steps answered', [true, false, false, false]], 'a chain left half-way says how far it got, and the steps not come to stay unfolded');
  assert(await p.evaluate(() => !document.querySelector('.ex-step[data-step="3"] .exercise').classList.contains('incorrect') && !document.querySelector('.ex-step[data-step="3"] .exercise').classList.contains('correct')),
         'a step not come to is not marked: its answers are not shown before it is the learner\'s');
  await click(p, '.ex-step[data-step="1"] .ex-step-next');
  eq((await look(p)).say, 'Step 2 of 4', 'and the chain goes on after Check exercises');
  eq(p.errors, [], 'no page error');
  await p.close();

  /* ---------------- the editor's preview ---------------- */
  console.log('preview) the stored answers, and Show every step');
  p = await open(true);
  l = await look(p);
  eq([l.shown, l.dots[0]], [[true, false, false, false], '1*'], 'the preview shows step 1 first, as the page does');
  eq(await p.evaluate(() => [...document.querySelectorAll('.ex-chain .ex-step-check, .ex-chain .ex-step-show')].filter(e => !e.hidden && e.getClientRects().length).length), 0, 'nothing is checked in a preview');
  assert(await p.evaluate(() => document.querySelector('.ex-step[data-step="1"] .ex-option.answer-correct') !== null), 'the stored answer is drawn');
  await click(p, '.ex-step[data-step="1"] .ex-step-next');
  eq((await look(p)).say, 'Step 2 of 4', 'Next step goes on without a check');
  assert(await p.evaluate(() => !!document.querySelector('.ex-chain .ex-showall') && document.querySelector('.ex-chain .ex-head .ex-showall').textContent === 'Show every step'), 'the head has Show every step');
  await click(p, '.ex-showall');
  l = await look(p);
  eq([l.shown, l.earlier], [[true, true, true, true], 0], 'Show every step unfolds the whole chain, nothing folded');
  eq(await p.evaluate(() => document.querySelector('.ex-showall').getAttribute('aria-pressed')), 'true', 'and says it is on');
  await shot(p, 'preview-all');
  await click(p, '.ex-showall');
  eq((await look(p)).shown, [true, true, false, false], 'pressed again it goes back to where the chain was');
  eq(p.errors, [], 'no page error');
  await p.close();

  console.log(`\nfollow-up questions, on the page: ${passed} checks passed`);
} finally {
  await browser.close();
}
