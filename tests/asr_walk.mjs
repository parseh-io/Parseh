// SPDX-License-Identifier: GPL-3.0-or-later
// THE MODEL'S ANSWERS, ONE BY ONE (a0.5.1): what a review method said of each word -- changed, agrees, not sure, no
// answer -- and the walk that asks for each whether to take it.  The real review screen (youtube/lib/asrreview.js with
// asrwalk.js) mounted on a page of its own: no server, no recognizer, no endpoint, no chatbot.
//   a) the four outcomes are counted, listed with the model's reason, and worn by the words of the transcript
//   b) the walk opens by itself with a result, goes in the order of the transcript, and each choice does what it says:
//      Accept, Keep, Skip, Write my own, Back -- by button and by key; a word the model agrees with is not in it unless asked
//   c) "Accept the sure ones" takes those and leaves the rest for the walk; "Accept all" takes every edit and ends
//   d) the end says what will change, and Use this transcript hands over exactly that
//   e) the walk is saved with the draft (which words were kept, which skipped) and comes back with it
//   f) the sentence methods have no rows of their own and still say something of each flagged word
//   g) without the walk's file the review is what it was; a phone's width has no sideways scroll
//   ASR_WALK_SHOTS=<dir> saves pictures of the screen, in the page's own stylesheets, to be looked at
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const {chromium} = await import(process.env.PLAYWRIGHT_CORE || 'npm:playwright-core@1.52.0');
const browser = await chromium.launch({executablePath: process.env.CHROME_BIN || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox']});
let checks = 0;
function ok(value, message) { assert.ok(value, message); checks++; console.log('  ok', message); }
function eq(got, want, message) { assert.deepEqual(got, want, message + ': ' + JSON.stringify(got)); checks++; console.log('  ok', message); }
const WALK = await readFile(resolve('youtube/lib/asrwalk.js'), 'utf8'), REVIEW = await readFile(resolve('youtube/lib/asrreview.js'), 'utf8');
// the page's own sheets, so that a picture is what a person sees
const CSS = (await Promise.all(['lib/parseh.css', 'youtube/lib/style.css', 'youtube/lib/addstt.css'].map(f => readFile(resolve(f), 'utf8')))).join('\n');
const SHOTS = Deno.env.get('ASR_WALK_SHOTS') || '';
const shot = async (page, name) => { if (SHOTS) { await Deno.mkdir(SHOTS, {recursive: true}); await page.screenshot({path: SHOTS + '/' + name + '.png'}); } };

async function open(viewport, withWalk = true) {
  const page = await browser.newPage({viewport});
  page.errors = []; page.on('pageerror', e => page.errors.push(e.message));
  await page.setContent('<style>' + CSS + '</style><body class="index wizard"><main><div class="addvid"><div class="stt"><textarea id="transcript">untouched</textarea><section id="review" class="stt-review"></section></div></div></main></body>');
  if (withWalk) await page.addScriptTag({content: WALK});
  await page.addScriptTag({content: REVIEW});
  return page;
}

// three captions, five flagged words (s0w1 and s0w5 are "anno", s1w1 "mare", s1w3 "blu", s2w0 "Ciao")
const SETUP = ({scenario, draft, phase}) => {
  const captions = ['Loro anno detto ciao e anno poi.', 'Il mare e blu oggi.', 'Ciao a tutti.'];
  const flagged = {s0w1: .2, s0w5: .3, s1w1: .25, s1w3: .4, s2w0: .3};
  let text = '';
  const segments = captions.map((caption, s) => {
    text += s * 5 + ':00\n';
    const base = text.length, words = []; let at = 0;
    caption.split(' ').forEach((surface, i) => {
      const a = caption.indexOf(surface, at); at = a + surface.length;
      words.push({segment_id: 's' + s, word_id: 's' + s + 'w' + i, text: surface, start: s * 5 + i * .3, end: s * 5 + i * .3 + .2,
        asr_confidence: flagged['s' + s + 'w' + i] ?? .95, low_asr_score: 's' + s + 'w' + i in flagged, dictionary_miss: false,
        alternatives_available: false, asr_alternatives: [], reviewable: true, span_start: base + a, span_end: base + at});
    });
    text += caption + '\n';
    return {segment_id: 's' + s, start: s * 5, end: s * 5 + 4, text: caption, words};
  });
  const byId = {}; segments.forEach(seg => seg.words.forEach(w => { byId[w.word_id] = w; }));
  const suggestion = (id, to, rating, reason) => ({...byId[id], original: byId[id].text, word_ids: [id], candidates: [{text: to, confidence: null, reason}], reason, rating, method: 'workspace-code'});
  const everything = Object.keys(flagged);
  const results = {
    // what a chatbot's workspace answer comes to: two edits (one sure, one not), one word it agrees with, one it could not tell, one it left out
    workspace: {task: 'workspace', method: 'external-workspace', suggestions: [suggestion('s0w1', 'hanno', 'sure', 'the sentence needs the verb'), suggestion('s1w1', 'mari', 'unsure', 'maybe a plural')],
      kept: [{word_ids: ['s0w5'], original: 'anno', rating: 'sure', reason: 'a year, as it should be'}, {word_ids: ['s1w3'], original: 'blu', rating: 'unsure', reason: 'cannot tell'}],
      failed_word_ids: ['s2w0'], failed_reasons: {s2w0: 'the answer has no row for this word'}, uncertain_word_ids: ['s0w5', 's1w3', 's2w0'], reviewed_word_ids: everything, latest_word_ids: everything},
    // a sentence method: it returns sentences, so the flagged words it gave back unchanged carry no row and no rating
    sentence: {task: 'suspect', method: 'external-suspect', suggestions: [{...suggestion('s0w1', 'hanno', null, ''), reason: ''}], failed_word_ids: ['s2w0'],
      uncertain_word_ids: ['s0w5', 's1w1', 's1w3', 's2w0'], reviewed_word_ids: everything, latest_word_ids: everything}
  };
  window.applied = null; window.saved = null; window.listened = [];
  const root = document.querySelector('#review');
  if (window.walkReview) window.walkReview.clear();
  window.walkReview = ParsehAsrReview.mount(root, {cancel: () => {}, choose: () => {}, select: (w, seg, play) => { if (play) window.listened.push(w.word_id); },
    use: (decisions, manual) => { window.applied = {decisions, manual}; }, save: d => { window.saved = JSON.parse(JSON.stringify(d)); return Promise.resolve(); }});
  window.walkReview.show({text, model: 'large-v3-turbo', review: {draft, evidence: {source_sha256: 'src', language: 'it', low_score_threshold: .5, segments}, result: results[scenario]}},
    phase || 'review', {configured: false});
};
// (the mouse is put out of the way: a word that appears under a resting pointer shows its evidence for a moment, as a hover does)
const setup = async (page, scenario = 'workspace', draft = undefined, phase = undefined) => { await page.mouse.move(1, 1); await page.evaluate(SETUP, {scenario, draft, phase}); };
const head = page => page.locator('.stt-walk-card .stt-walk-head').textContent();
const mark = page => page.locator('.stt-walk-card mark').allTextContents();
const count = page => page.locator('.stt-walk-card .stt-walk-count').textContent();

try {
  /* ============================================================================================== a) */
  console.log('a) the four outcomes: counted, listed with the reason, worn by the words');
  let page = await open({width: 1100, height: 900});
  await setup(page);
  ok(await page.locator('#stt_walk').isVisible(), 'the answers are drawn under the tools');
  ok((await page.locator('.stt-walk-summary').textContent()).startsWith('5 words checked: '), 'the summary says how many words were checked');
  eq(await page.locator('.stt-walk-chip').allTextContents(), ['✎ 2 edits proposed (1 sure, 1 not sure)', '✔ 1 agree with Whisper', '? 1 not sure either way', '✗ 1 with no answer'],
     'and counts what was proposed, what the model agrees with, what it doubts and what it left out');
  await page.locator('.stt-walk-chip.stt-walk-agree').click();
  eq((await page.locator('.stt-walk-list').textContent()).replace(/\s+/g, ' ').trim(), '✔ anno · sure — a year, as it should be', 'a word the model agrees with is listed, with what it said and why');
  await page.locator('.stt-walk-chip.stt-walk-unsure').click();
  ok((await page.locator('.stt-walk-list').textContent()).includes('cannot tell'), 'and so is the one it could not tell, with its reason');
  await page.locator('.stt-walk-chip.stt-walk-none').click();
  ok((await page.locator('.stt-walk-list').textContent()).includes('✗ Ciao'), 'and the one with no answer');
  eq(await page.evaluate(() => ({agree: document.querySelector('[data-review-word=s0w5]').className.includes('asr-agree'), unsure: document.querySelector('[data-review-word=s1w3]').className.includes('asr-unsure'),
                                  none: document.querySelector('[data-review-word=s2w0]').className.includes('asr-noanswer'), change: document.querySelector('[data-review-word=s0w1]').className.includes('asr-proposal')})),
     {agree: true, unsure: true, none: true, change: true}, 'each word of the transcript wears the mark of what the model said of it');
  await page.locator('[data-review-word=s0w5]').click();
  ok((await page.locator('.stt-review-details .stt-walk-wordnote').textContent()).includes('Whisper’s word is right') && (await page.locator('.stt-review-details .stt-walk-wordnote').textContent()).includes('a year, as it should be'),
     'a word\'s own panel says that the model agrees and why: no more silence about it');
  await page.locator('[data-review-word=s2w0]').click();
  ok((await page.locator('.stt-review-details .stt-walk-wordnote').textContent()).includes('no answer'), 'and that the model gave no answer for another');

  /* ============================================================================================== b) */
  console.log('b) the walk, a card at a time');
  await setup(page);
  ok(await page.locator('.stt-walk-card').isVisible(), 'a result that has just come in opens the walk by itself');
  await shot(page, 'walk-card');
  eq(await head(page), '✎ The model corrects this word, and is sure', 'the first card is the first thing in the transcript, a sure correction');
  eq(await mark(page), ['anno'], 'the caption is shown with the word marked');
  ok((await page.locator('.stt-walk-card').textContent()).includes('the sentence needs the verb') && (await page.locator('.stt-walk-card').textContent()).includes('hanno'), 'the proposal and its reason are on the card');
  eq((await count(page)).split(' · ')[0], 'Answer 1 of 4', 'the walk is four cards: the agreement is not one of them');
  eq(await page.locator('.stt-review-details > bdi').textContent(), 'anno', 'the panel beside the transcript shows the card\'s word, with its evidence');
  await page.keyboard.press('a');
  eq(await page.evaluate(() => window.walkReview.snapshot().decisions), {s0w1: 0}, 'A accepts the proposal into the draft');
  eq(await head(page), '✎ The model suggests a correction, but is not sure', 'and the next card is the next word, a correction it is not sure of');
  eq(await page.locator('.stt-review-details > bdi').textContent(), 'mare', 'and it follows the walk to the next word');
  await page.keyboard.press('s');
  eq(await head(page), '? The model kept Whisper’s word but is not sure of it', 'S skips it; the one the model could not tell comes next');
  await page.keyboard.press('k');
  eq(await page.evaluate(() => window.walkReview.snapshot().walk.kept), ['s1w3'], 'K keeps Whisper\'s word, and the walk remembers it');
  eq(await head(page), '✗ The model gave no answer for this word', 'a word with no answer is a card too');
  ok((await page.locator('.stt-walk-card .stt-walk-reason').textContent()).includes('Why there is no answer: the answer has no row for this word'), 'and the card says why there is no answer');
  await page.keyboard.press('ArrowLeft');
  eq([await head(page), await page.evaluate(() => window.walkReview.snapshot().walk.kept)], ['? The model kept Whisper’s word but is not sure of it', []], 'Back takes the last choice back and shows that card again');
  await page.keyboard.press('k'); await page.keyboard.press('w');
  await page.locator('.stt-walk-own input').fill('Ciaoo');
  await page.locator('.stt-walk-own input').press('Enter');
  eq(await page.evaluate(() => window.walkReview.snapshot().manual_edits), {s2w0: 'Ciaoo'}, 'Write my own puts the word in the draft');
  ok((await page.locator('.stt-walk-card').textContent()).includes('All the answers have been looked at') || await page.locator('.stt-walk-end').isVisible(), 'the walk ends when the cards are done');
  await page.locator('.stt-walk-end >> text=Go back to the 1 skipped').click();
  eq(await head(page), '✎ The model suggests a correction, but is not sure', 'the skipped one comes back when asked for');
  await page.getByRole('button', {name: /Accept “mari”/}).click();
  eq(await page.evaluate(() => window.walkReview.snapshot().decisions), {s0w1: 0, s1w1: 0}, 'and Accept takes it');

  /* ============================================================================================== c, d */
  console.log('c) the two bulk buttons, d) the end');
  await setup(page);
  await page.keyboard.press('Escape');
  ok(await page.locator('#stt_walk_sure').isVisible(), 'the answer carries ratings, so there is a button for the sure ones');
  eq((await page.locator('#stt_walk_sure').textContent()), 'Accept the 1 sure edit, then look at the rest', 'it says how many it takes');
  await page.locator('#stt_walk_sure').click();
  eq(await page.evaluate(() => window.walkReview.snapshot().decisions), {s0w1: 0}, 'it takes the sure edit and no other');
  eq(await head(page), '✎ The model suggests a correction, but is not sure', 'and the walk goes on with what the model was not sure of');
  eq((await count(page)).split(' · ')[0], 'Answer 1 of 3', 'three cards are left: the unsure edit, the unsure keep and the word with no answer');
  await setup(page);
  await page.locator('#stt_walk_all').click();
  eq(await page.evaluate(() => window.walkReview.snapshot().decisions), {s0w1: 0, s1w1: 0}, 'Accept all takes every edit, sure or not');
  ok(await page.locator('.stt-walk-end').isVisible(), 'and ends the walk at once');
  await shot(page, 'walk-end');
  eq((await page.locator('.stt-walk-changes li').allTextContents()).map(t => t.replace(/\s+/g, ' ').trim()), ['0:00 anno → hanno', '0:05 mare → mari'], 'with what will change in the transcript, in order');
  await page.locator('#stt_walk_use').click();
  eq(await page.evaluate(() => window.applied), {decisions: {s0w1: 0, s1w1: 0}, manual: {}}, 'Use this transcript hands over exactly those');
  ok(await page.inputValue('#transcript') === 'untouched', 'the transcript box is not touched by any of it');
  await page.locator('#stt_walk_agree').check();
  await page.locator('.stt-walk-end >> text=Close').click();
  await page.locator('#stt_walk_start').click();
  eq(await head(page), '✔ The model says Whisper’s word is right', 'with the switch on, a word the model agrees with is in the walk, marked as that');
  ok((await page.locator('.stt-walk-card').textContent()).includes('a year, as it should be'), 'with its reason');

  /* ============================================================================================== e */
  console.log('e) the walk is saved with the draft and comes back with it');
  await setup(page);
  await page.keyboard.press('s'); await page.keyboard.press('k');
  const saved = await page.evaluate(() => window.walkReview.snapshot());
  eq(saved.walk, {kept: ['s1w1'], skipped: ['s0w1'], include_agree: false}, 'the walk\'s own state is in the snapshot: one word skipped, one kept');
  await setup(page, 'workspace', saved);
  eq(await page.evaluate(() => window.walkReview.snapshot().walk), saved.walk, 'a draft that comes back brings the walk with it');
  eq(await head(page), '? The model kept Whisper’s word but is not sure of it', 'and the walk goes on where it was: what was skipped waits, what was kept does not come back');

  /* ============================================================================================== f */
  console.log('f) a sentence method has no rows and still says something of every flagged word');
  await setup(page, 'sentence');
  eq(await page.locator('.stt-walk-chip').allTextContents(), ['✎ 1 edit proposed', '✔ 3 agree with Whisper', '? 0 not sure either way', '✗ 1 with no answer'],
     'its edit, the three flagged words it gave back unchanged, and the one it left out');
  ok(!(await page.locator('#stt_walk_sure').count()), 'it rates nothing, so there is no button for "the sure ones"');
  await page.locator('.stt-walk-chip.stt-walk-agree').click();
  ok((await page.locator('.stt-walk-list').textContent()).includes('The model gave this word back unchanged.'), 'the words it let stand say how it let them stand');
  ok(!page.errors.length, 'no page error: ' + page.errors.join(' | '));

  console.log('f2) likelihood: its winner is the answer, and a tie or a half-finished comparison is not a clear one');
  const kinds = await page.evaluate(() => {
    const w = (id, text, at) => ({word_id: id, text, span_start: at, span_end: at + text.length, reviewable: true, low_asr_score: true});
    const words = {a: w('a', 'anno', 0), b: w('b', 'mare', 10), c: w('c', 'blu', 20), d: w('d', 'poi', 30)};
    const cand = (text, rank, applicable = true) => ({text, rank, applicable});
    const like = (state, tied) => ({coverage: {state}, tied_best: tied});
    const sug = (id, candidates, likelihood) => ({word_id: id, word_ids: [id], candidates, likelihood});
    const suggestions = {a: sug('a', [cand('anno', 2), cand('hanno', 1)], like('complete', ['hanno'])),   // the other word wins, clearly
                         b: sug('b', [cand('mare', 1), cand('mari', 2)], like('complete', ['mare'])),     // Whisper's own word wins, clearly
                         c: sug('c', [cand('blu', 1), cand('blue', 1)], like('complete', ['blu', 'blue'])), // a tie
                         d: sug('d', [cand('poi', 2), cand('puoi', 1)], like('partial', ['puoi']))};        // a comparison that could not be finished
    return ParsehAsrWalk.outcomes({words, suggestions, result: {task: 'likelihood', latest_word_ids: ['a', 'b', 'c', 'd']}, review: {}, locked: {}})
      .map(i => [i.anchor, i.kind, i.sure, i.candidates[0].text]);
  });
  eq(kinds, [['a', 'change', true, 'hanno'], ['b', 'agree', true, 'mare'], ['c', 'unsure', false, 'blu'], ['d', 'change', false, 'puoi']].map(r => r), 'clear winner: a sure change; its own word winning: an agreement; a tie: not sure; unfinished: a change that is not sure');

  console.log('h) the transcript is obtainable at any time no tool is running');
  await setup(page, 'workspace', undefined, 'external');
  ok(!(await page.locator('#stt_use').isDisabled()), 'while a chatbot review still waits for answers, Use this transcript is there to press');
  await page.locator('#stt_walk_start').click();     // (it opens by itself only once a review is finished)
  await page.keyboard.press('a');
  eq(await page.evaluate(() => window.walkReview.snapshot().decisions), {s0w1: 0}, 'and the walk takes edits in that state too');
  await page.locator('[data-review-word=s1w3]').click();
  ok(await page.locator('#stt_manual_word').isVisible(), 'as does a word\'s own editor');
  await page.locator('#stt_use').click();
  eq(await page.evaluate(() => window.applied), {decisions: {s0w1: 0}, manual: {}}, 'and it hands over what stands, the rest being Whisper\'s');
  await setup(page, 'workspace', undefined, 'correcting');
  ok(await page.locator('#stt_use').isDisabled() && (await page.locator('#stt_use').getAttribute('title')).includes('running'), 'only while a tool is running it waits, and says why');

  /* ============================================================================================== g */
  console.log('g) a phone, and without the walk');
  const phone = await open({width: 360, height: 780});
  await setup(phone);
  await phone.keyboard.press('s');
  await shot(phone, 'walk-phone');
  ok(await phone.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), 'no sideways scroll at 360 px with the walk open: ' + await phone.evaluate(() => document.documentElement.scrollWidth));
  const overflow = await phone.evaluate(() => [...document.querySelectorAll('#stt_walk *')].filter(e => e.getClientRects().length && e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).map(e => e.className || e.tagName).slice(0, 5));
  eq(overflow, [], 'and nothing of it sticks out');
  await phone.close();
  const plain = await open({width: 1100, height: 800}, false);
  await plain.evaluate(SETUP, {scenario: 'workspace'});
  ok(!(await plain.locator('#stt_walk').count()) && await plain.locator('[data-review-word=s0w1]').isVisible(), 'without asrwalk.js the review draws its transcript as before and no walk');
  ok(!plain.errors.length, 'and throws nothing: ' + plain.errors.join(' | '));
  await plain.close();
  await page.close();
  console.log('\nasr walk passed (' + checks + ' checks)');
} catch (error) {
  console.error('FAILED:', error.message);
  await browser.close();
  Deno.exit(1);
}
await browser.close();
