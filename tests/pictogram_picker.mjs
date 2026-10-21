// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the PICTOGRAM PICKER (lib/pictograms.js, a0.5.3): the frame in which a person looks for an ARASAAC
// pictogram by a word, sees the thumbnails, looks at one properly and -- where the page can use it -- adds it.  Against the
// REAL routes (serve.py's and the studio's own) on a temporary tree that holds an INSTALLED set of pictograms
// (tests/pictogram_world.py: real words in English, Spanish and Persian, real PNG pictures, the flags ARASAAC gives).
//   a) Settings -> Pictograms (ARASAAC): Look through the pictograms… opens the frame; the thumbnails load, a word finds
//      its pictures best first, one is looked at (picture, word, meaning, the words in every language), nothing is
//      offered to add; Escape closes it and the focus goes back to the button
//   b) what is looked for: every language here at once or one, the words under the pictures in the language chosen, a
//      Persian word with either yeh, the pictograms about violence or sex left out and said to be, one tick lets them in
//   c) the keys: arrows walk the thumbnails, Tab stays inside the frame, Enter looks, Escape closes
//   d) the editor's Pictograms…: a figure at the cursor, a copy in the document's own images/, ARASAAC's credit once as
//      the last paragraph, the same pictogram twice stored once, "keep looking" adds several, undo takes it out in one step
//   e) the exercise form: a card's picture sides, an exercise's picture (with the width and side a pictogram wants), a
//      small picture inside the text of the field the hand was last in, a figure in a jolly card; the credit follows
//   f) an exercise deck's form puts the pictures into the deck
//   g) not installed, or part of it: what the frame says, and where it sends
//   h) a phone: the frame fills the screen and the preview comes with a choice; the three themes
// Two modes, each a tests/studio_harness.py:
//   parseh  Parseh's handler (the door, the studio at /studio, the decks at /exercises)
//   studio  the studio's own server (at /, serving the picker's two files itself)
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/pictogram_picker.mjs
//   PICKER_MODES=parseh (or studio) runs one; PICKER_SECTIONS=abc runs only those; SHOTS=<dir> saves the screenshots
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('PICKER_MODES') || 'parseh,studio').split(',');
const sections = Deno.env.get('PICKER_SECTIONS') || 'abcdefgh';
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const equal = (got, want, m) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw Error(`FAIL: ${m}\n   got  ${JSON.stringify(got)}\n   want ${JSON.stringify(want)}`);
  passed++; console.log('  ok', m);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {      // (how long a wait is given is how long a slow computer is)
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}
const exists = async p => { try { await Deno.stat(p); return true; } catch (_) { return false; } };

async function startHarness(mode, flags = ['--pictograms']) {
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', mode, ...flags], cwd: root,
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

const shot = async (page, name) => {
  if (!SHOTS) return;
  await Deno.mkdir(SHOTS, {recursive: true});
  await page.screenshot({path: `${SHOTS}/${name}.png`});
};

async function suite(mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info, log} = await startHarness(mode);
  const origin = `http://127.0.0.1:${info.port}`, base = info.studio;
  const url = p => origin + base + p;
  const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1400, height: 900}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());

    /* ---- what the frame shows, read from the page ---- */
    const frame = page.locator('.pg-overlay');
    const cells = () => page.locator('.pg-cell');
    const ids = () => page.$$eval('.pg-cell', els => els.map(e => +e.dataset.id));
    const captions = () => page.$$eval('.pg-cell .pg-cap', els => els.map(e => e.textContent));
    const count = () => page.locator('.pg-count').textContent();
    const settled = what => until(async () => (await page.locator('.pg-results').getAttribute('aria-busy')) === 'false', what);
    const search = async text => {
      await page.locator('.pg-q').fill(text);
      await page.locator('.pg-q').press('Enter');
      await settled(`the answer for “${text}”`);
    };
    const loaded = async n => until(async () => page.$$eval('.pg-cell img', (els, n) =>
      els.slice(0, n).every(i => i.complete && i.naturalWidth > 0), n), `the first ${n} thumbnails have loaded`);
    const api = async (method, path, body) => {
      const r = await fetch(url(path), {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                        body: body ? JSON.stringify(body) : undefined});
      const data = await r.json();
      if (!r.ok) throw Error(`${method} ${path}: ${r.status} ${JSON.stringify(data)}`);
      return data;
    };
    const docDir = async id => {
      for await (const d of Deno.readDir(info.library)) if (await exists(`${info.library}/${d.name}/${id}`)) return `${info.library}/${d.name}/${id}`;
      throw Error('no such document: ' + id);
    };
    const newDoc = async (title, target = 'es', body = 'Una casa.') =>
      (await api('POST', '/api/docs', {markdown: `---\ntitle: ${title}\ntarget: ${target}\n---\n\n${body}\n`})).meta.id;
    const source = () => page.locator('#src').inputValue();
    const pictogramFile = id => Deno.readFile(`${info.arasaac}/pictograms/${id}.png`);
    const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
    const toastSays = (re, what) => until(async () => re.test(await page.locator('#toast').textContent()), what);
    const CREDIT = 'Pictograms author: Sergio Palao. Origin: ARASAAC (http://www.arasaac.org). License: CC (BY-NC-SA). Owner: Government of Aragon (Spain)';
    const occurrences = (text, what) => text.split(what).length - 1;
    const openEditor = async id => {
      await page.goto(url(`/doc/${id}/edit`));
      await page.locator('#btn-pictograms').waitFor();
    };
    /* the exercise form, wherever it is opened (the editor's Exercises ▾, a deck's Add exercise…) */
    const form = page.locator('.ex-form-modal');
    const fieldOf = label => form.locator('label.ex-author-field').filter({has: page.locator(`span:text-is("${label}")`)});
    const boxOf = label => fieldOf(label).locator('input:not([type=file]), textarea').first();
    const openForm = async type => {
      await page.locator('summary', {hasText: 'Exercises'}).click();
      await page.locator('#btn-exercise').click();
      await page.locator('.ex-type', {hasText: type}).click();
      await form.waitFor();
    };
    const pickIn = async (word, buttonName) => {          // the frame is open: look for `word`, choose it, press the button
      await frame.waitFor();
      await search(word);
      await cells().first().click();
      await page.locator('.pg-actions .pg-btn', {hasText: buttonName}).click();
    };
    const closed = what => until(async () => (await frame.count()) === 0, what);

    if (mode === 'parseh' && sections.includes('a')) {
      console.log(' a) the door');
      await page.goto(origin + '/settings/arasaac/');
      const look = page.locator('[data-look]');
      await look.waitFor({timeout: 20000});
      assert(await look.isVisible(), 'Look through the pictograms… is on the door once they are installed');
      await look.scrollIntoViewIfNeeded();
      await shot(page, `${mode}-a-door-row`);
      await look.click();
      await frame.waitFor();
      assert((await frame.locator('[role=dialog]').getAttribute('aria-modal')) === 'true', 'the frame is a modal dialog');
      equal(await frame.locator('h3').textContent(), 'Pictograms (ARASAAC)', 'it is named');
      await settled('the first page of the list');
      equal((await ids()).length, 48, 'with no word typed, the first page of every pictogram is drawn (48 of 90)');
      assert(/90 pictograms/.test(await count()), `and counted, the two about violence and sex left out: ${await count()}`);
      assert(/2 pictograms are left out/.test(await page.locator('.pg-hidden-note').textContent()), 'and that is said, with a way to let them in');
      assert(await page.locator('.pg-more').isVisible(), 'Show more is there');
      await loaded(12);
      assert(true, 'the thumbnails load (the first twelve are real pictures)');
      equal(await page.evaluate(() => document.activeElement.className), 'pg-q', 'the search box has the keys');
      equal(await page.evaluate(() => getComputedStyle(document.documentElement).overflow), 'hidden', 'while the frame is over it the page behind does not scroll');
      await shot(page, `${mode}-a-door`);

      await search('casa');
      equal(await ids(), [2317, 2319, 2318], '“casa”, Spanish, finds the three houses: the keyword itself, the schematic one, then the longer keyword');
      equal(await captions(), ['house', 'house', 'detached house'], 'under their English words (English is the default)');
      assert(/3 pictograms for “casa”/.test(await count()), `counted: ${await count()}`);
      await cells().first().click();
      await until(async () => (await page.locator('.pg-word').textContent()) === 'house', 'the preview names it');
      await until(() => page.locator('.pg-big img').evaluate(i => i.complete && i.naturalWidth > 0), 'the preview picture has loaded');
      equal(await page.locator('.pg-big img').evaluate(i => ({w: i.naturalWidth, alt: i.alt})), {w: 160, alt: 'house'},
            'the preview shows the picture itself (160 pixels wide), with its word as the alt text');
      equal(await page.locator('.pg-meaning').textContent(), 'a building where people live', 'and what it means');
      equal(await page.locator('.pg-words dd').allTextContents(), ['house, home', 'casa, hogar', 'خانه'],
            'and the words it has in every language here');
      equal(await page.locator('.pg-words dt').allTextContents(), ['English', 'Spanish', 'Persian'], 'each named');
      equal(await page.locator('.pg-number').textContent(), 'ARASAAC pictogram 2317', 'and its number');
      equal(await page.locator('.pg-actions .pg-btn').count(), 0, 'nothing is offered to add: this is only to look');
      assert(/To use a pictogram/.test(await page.locator('.pg-view-only').textContent()), 'and it says where one is used');
      await shot(page, `${mode}-a-looked-at`);
      await page.keyboard.press('Escape');
      await until(async () => (await frame.count()) === 0, 'Escape closes the frame');
      assert(await page.evaluate(() => getComputedStyle(document.documentElement).overflow) !== 'hidden', 'the page scrolls again');
      equal(await page.evaluate(() => document.activeElement.hasAttribute('data-look')), true, 'and the keys are back on the button that opened it');
    }

    if (mode === 'parseh' && sections.includes('b')) {
      console.log(' b) what is looked for');
      await page.goto(origin + '/settings/arasaac/');
      await page.locator('[data-look]').click();
      await settled('the first page');
      await search('casa');
      await page.locator('.pg-lang').selectOption('es');
      await settled('Spanish only');
      equal(await captions(), ['casa', 'casa', 'casa unifamiliar'], 'one language chosen: the words under the pictures are that language\'s');
      assert(/in Spanish/.test(await count()), `and the count says which: ${await count()}`);
      await page.locator('.pg-lang').selectOption('');
      await search('خانه');
      equal(await ids(), [2317, 2319, 2318], 'a Persian word finds the same three');
      equal(await page.locator('.pg-cap').first().getAttribute('dir'), 'auto', 'its caption takes its own direction');
      await search('كتاب');
      equal(await ids(), [2405], 'a word written with the Arabic kaf finds the one a Persian keyboard writes');
      await search('سيب');
      equal(await ids(), [2416], 'and with the Arabic yeh');
      await search('ARBOL');
      equal(await ids(), [2400], 'case and accents do not matter (árbol)');
      await search('cream ice');
      equal(await ids(), [2412], 'every word typed is looked for, in any order');
      await search('eat');
      equal(await ids(), [2407], 'a keyword other than the first finds it ("to eat" is also "eat")');
      await search('zzzz');
      equal(await ids(), [], 'a word nothing has finds nothing');
      equal(await count(), 'No pictogram for “zzzz”.', 'and says so');
      await search('kiss');
      equal(await ids(), [], 'a pictogram ARASAAC marks as about sex is left out…');
      assert(/1 more pictogram matches but is left out/.test(await page.locator('.pg-hidden-note').textContent()), '…and the frame says that one was');
      await page.locator('.pg-hidden-note .pg-link').click();
      await settled('with them let in');
      equal(await ids(), [2500], 'one tick lets it in');
      equal(await page.locator('.pg-sens input').isChecked(), true, 'the box shows it');
      await cells().first().click();
      equal(await page.locator('.pg-tags .pg-flag').allTextContents(), ['about sex'], 'and the preview says what ARASAAC says of it');
      await page.locator('.pg-sens input').uncheck();
      await settled('with them left out again');
      equal(await ids(), [], 'unticked, it goes again');
      await search('war');
      equal(await ids(), [], 'violence is left out too');
      await page.keyboard.press('Escape');
    }

    if (mode === 'parseh' && sections.includes('c')) {
      console.log(' c) the keys');
      await page.goto(origin + '/settings/arasaac/');
      await page.locator('[data-look]').click();
      await settled('the first page');
      await search('house');
      equal(await ids(), [2317, 2319, 2318], '“house” finds the three');
      await page.locator('.pg-cell').first().focus();
      await page.keyboard.press('Enter');
      equal(await page.locator('.pg-word').textContent(), 'house', 'Enter looks at the one the keys are on');
      await page.keyboard.press('ArrowRight');
      equal(await page.evaluate(() => document.activeElement.dataset.id), '2319', 'ArrowRight goes to the next');
      equal(await page.locator('.pg-cell[aria-selected=true]').getAttribute('data-id'), '2319', 'and it is the one looked at');
      await page.keyboard.press('End');
      equal(await page.evaluate(() => document.activeElement.dataset.id), '2318', 'End goes to the last');
      await page.keyboard.press('Home');
      equal(await page.evaluate(() => document.activeElement.dataset.id), '2317', 'Home to the first');
      await page.keyboard.press('ArrowLeft');
      equal(await page.evaluate(() => document.activeElement.dataset.id), '2317', 'and ArrowLeft stops there');
      const inside = async () => page.evaluate(() => !!document.activeElement.closest('.pg-modal'));
      let stayed = true;
      for (let i = 0; i < 25; i++) { await page.keyboard.press('Tab'); stayed = stayed && await inside(); }
      assert(stayed, 'Tab goes round inside the frame and never out into the page');
      for (let i = 0; i < 25; i++) { await page.keyboard.press('Shift+Tab'); stayed = stayed && await inside(); }
      assert(stayed, 'and so does Shift+Tab');
      await page.mouse.click(5, 5);
      await until(async () => (await frame.count()) === 0, 'a click outside the frame closes it');
    }

    if (sections.includes('d')) {
      console.log(' d) the editor');
      const id = await newDoc('Houses');
      const dir = await docDir(id);
      await openEditor(id);
      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await settled('the first page');
      equal(await frame.locator('h3').textContent(), 'Add a pictogram to this page', 'the editor\'s Pictograms… opens the frame, named for what it does');
      assert(/images\/ folder/.test(await page.locator('.pg-note').textContent()), 'and it says a copy goes into the document\'s own folder');
      const add = page.locator('.pg-actions .pg-primary'), keep = page.locator('.pg-actions .pg-btn:not(.pg-primary)');
      equal(await add.textContent(), 'Add to the page', 'the button says what it does');
      equal(await keep.textContent(), 'Add, keep looking', 'and another what it does');
      equal([await add.isDisabled(), await keep.isDisabled()], [true, true], 'neither works until a pictogram is chosen');
      await search('árbol');
      equal(await captions(), ['árbol'], 'the words under the pictures are the document\'s own language (Spanish)');
      await cells().first().click();
      equal([await add.isDisabled(), await keep.isDisabled()], [false, false], 'a choice makes them work');
      await shot(page, `${mode}-d-editor-frame`);
      await add.click();
      await until(async () => (await frame.count()) === 0, 'the frame closes once it is added');
      let text = await source();
      assert(text.includes('![árbol](images/arasaac-2400.png){width=18 align=center}'), 'the figure is at the cursor, its caption the word, its size the one a pictogram wants');
      assert(text.startsWith('---\ntitle: Houses\ntarget: es\n---\n'), 'and below the front matter, which is still the first thing in the page (the cursor had not been moved)');
      assert(text.trimEnd().endsWith(CREDIT), 'and ARASAAC\'s credit is the last paragraph');
      equal(occurrences(text, 'Pictograms author'), 1, 'once');
      assert(same(await Deno.readFile(`${dir}/images/arasaac-2400.png`), await pictogramFile(2400)), 'the document holds its own copy of the picture, byte for byte');
      equal(await page.evaluate(() => { const t = document.getElementById('src'); return [document.activeElement === t, t.value.slice(t.selectionStart, t.selectionEnd)]; }),
            [true, 'árbol'], 'the keys are in the text with the caption selected, to be written over');
      await until(() => page.locator('#sheet figure img[src*="arasaac-2400"]').evaluate(i => i.complete && i.naturalWidth > 0), 'the preview draws the figure');
      equal(await page.locator('#sheet figure figcaption').first().textContent(), 'árbol', 'with its caption');
      await toastSays(/credit/, 'a toast says the credit was added');

      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await search('árbol');
      await cells().first().click();
      await add.click();
      await until(async () => (await frame.count()) === 0, 'closed again');
      text = await source();
      equal(occurrences(text, '![árbol](images/arasaac-2400.png)'), 2, 'the same pictogram twice is two figures');
      const stored = [];
      for await (const f of Deno.readDir(`${dir}/images`)) if (f.name.startsWith('arasaac')) stored.push(f.name);
      equal(stored, ['arasaac-2400.png'], '…of one file: the same bytes are stored once');
      equal(occurrences(text, 'Pictograms author'), 1, 'and the credit is not written twice');

      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await search('perro');
      await cells().first().click();
      await keep.click();
      await until(async () => /Added “perro”/.test(await page.locator('.pg-say').textContent()), 'Add, keep looking says what it added');
      equal(await frame.count(), 1, 'the frame stays');
      equal(await page.evaluate(() => !!document.activeElement.closest('.pg-modal')), true, 'with the keys in it (the editor did not take them)');
      await search('gato');
      await cells().first().click();
      await keep.click();
      await until(async () => /Added “gato”/.test(await page.locator('.pg-say').textContent()), 'and another');
      await page.keyboard.press('Escape');
      await until(async () => (await frame.count()) === 0, 'Escape closes it');
      text = await source();
      assert(text.includes('![perro](images/arasaac-2401.png)') && text.includes('![gato](images/arasaac-2402.png)'), 'both are in the page');
      assert(text.indexOf('![perro]') < text.indexOf('![gato]'), 'in the order added, one after the other');
      equal(occurrences(text, 'Pictograms author'), 1, 'still one credit');
      await shot(page, `${mode}-d-editor-after`);

      // one undo takes the picture and the credit it brought
      const id2 = await newDoc('One house');
      await openEditor(id2);
      const before = await source();
      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await search('sol');
      await cells().first().click();
      await add.click();
      await until(async () => (await frame.count()) === 0, 'closed');
      assert((await source()).includes('Pictograms author'), 'a second page gets its credit');
      await page.locator('#src').press('Control+z');
      equal(await source(), before, 'one undo takes the picture away with the credit it brought');

      // what is said besides, in the frame's own line (a toast is under its dim): the credit, the first time and no other
      const id3 = await newDoc('Said');
      await openEditor(id3);
      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await search('sol');
      await cells().first().click();
      await keep.click();
      await until(async () => /Added “sol”/.test(await page.locator('.pg-say').textContent()), 'the first one is added');
      assert(/credit is now the page's last paragraph/.test(await page.locator('.pg-say').textContent()), 'the frame says the credit was written, in its own line');
      await search('luna');
      await cells().first().click();
      await keep.click();
      await until(async () => /Added “luna”/.test(await page.locator('.pg-say').textContent()), 'the second is added');
      assert(!/credit/.test(await page.locator('.pg-say').textContent()), 'and does not say it again');
      await page.keyboard.press('Escape');
      await closed('closed');

      // what the person had selected is theirs: a figure goes in after it, not over it
      const id4 = await newDoc('Selected', 'es', 'Una casa grande.');
      await openEditor(id4);
      await page.evaluate(() => { const t = document.getElementById('src'); const a = t.value.indexOf('casa'); t.focus(); t.setSelectionRange(a, a + 4); });
      await page.locator('#btn-pictograms').click();
      await frame.waitFor();
      await search('sol');
      await cells().first().click();
      await add.click();
      await closed('closed');
      text = await source();
      assert(text.includes('Una casa') && text.includes('grande.'), `the words that were selected are still there: ${JSON.stringify(text.slice(text.indexOf('Una') - 4))}`);
      assert(text.includes('![sol](images/arasaac-2413.png){width=18 align=center}'), 'and the figure is in');

      // a document not saved yet has no folder to keep a copy in
      await page.goto(url('/new?target=es'));
      await page.locator('#btn-pictograms').click();
      await toastSays(/Save the document first/, 'a new document says it must be saved first');
      equal(await frame.count(), 0, 'and no frame is opened for nothing');
    }

    if (sections.includes('e')) {
      console.log(' e) the exercise form, in the editor');
      const id = await newDoc('Cards');
      const dir = await docDir(id);
      await openEditor(id);

      // a vocabulary card: its picture sides, and a small picture inside a line of its text
      await openForm('Embedded vocabulary flashcard');
      assert(await page.locator('[data-x="pictogram"]').isVisible(), 'the form has a Pictogram… beside LaTeX and Maths, for the field the hand was last in');
      equal(await fieldOf('Front image path').locator('.ex-upload-row button').allTextContents(), ['Upload…', 'Pictogram…'],
            'a card\'s picture side has its Pictogram… beside its Upload…');
      equal(await fieldOf('Front recording path').locator('button.ex-pictogram').count(), 0, 'a recording\'s has none');
      await boxOf('Word or expression').fill('casa');
      await boxOf('Meaning').fill('house');
      await fieldOf('Front image path').locator('button.ex-pictogram').click();
      await frame.waitFor();
      equal(await frame.locator('h3').textContent(), 'A pictogram for this picture', 'the frame says what it is for');
      equal(await page.locator('.pg-actions .pg-btn').allTextContents(), ['Use this pictogram'], 'and offers one thing to do with a choice');
      await pickIn('casa', 'Use this pictogram');
      await closed('the frame closes');
      equal(await boxOf('Front image path').inputValue(), 'images/arasaac-2317.png', 'the path of the document\'s own copy is in the field');
      assert(same(await Deno.readFile(`${dir}/images/arasaac-2317.png`), await pictogramFile(2317)), 'and the copy is in the document\'s images/, byte for byte');
      await until(() => form.locator('.ex-form-preview img[src*="arasaac-2317"]').first().evaluate(i => i.complete && i.naturalWidth > 0), 'the form\'s own preview draws the card with the picture');
      await shot(page, `${mode}-e-card`);

      // a small picture inside the text of the field the hand was last in
      await boxOf('Meaning').click();
      await boxOf('Meaning').press('End');
      await page.locator('[data-x="pictogram"]').click();
      equal(await frame.locator('h3').textContent(), 'A pictogram for this field', 'the action bar\'s button asks for a picture for the field the hand was in');
      equal(await page.locator('.pg-actions .pg-btn').allTextContents(), ['Put it in the text', 'Put it in, keep looking'], 'offering to put it in the text');
      await pickIn('perro', 'Put it in, keep looking');
      await until(async () => /Added “perro”/.test(await page.locator('.pg-say').textContent()), 'added');
      equal(await boxOf('Meaning').inputValue(), 'house ![perro](images/arasaac-2401.png)', 'a small picture, a space from the word before it');
      await search('gato');
      await cells().first().click();
      await page.locator('.pg-actions .pg-btn', {hasText: 'Put it in the text'}).click();
      await closed('closed');
      equal(await boxOf('Meaning').inputValue(), 'house ![perro](images/arasaac-2401.png) ![gato](images/arasaac-2402.png)', 'the next one goes after it');
      equal(await page.evaluate(() => document.activeElement.closest('label')?.querySelector('span')?.textContent), 'Meaning', 'the keys are in the field again');

      // the field the hand was in is a path: the same button fills it
      await boxOf('Back image path').click();
      await page.locator('[data-x="pictogram"]').click();
      equal(await page.locator('.pg-actions .pg-btn').allTextContents(), ['Use this pictogram'], 'in a picture field the action bar\'s button offers it as the picture');
      await pickIn('sol', 'Use this pictogram');
      await closed('closed');
      equal(await boxOf('Back image path').inputValue(), 'images/arasaac-2413.png', 'and the path goes in');

      // a recording field takes no picture
      await boxOf('Front recording path').click();
      await page.locator('[data-x="pictogram"]').click();
      await toastSays(/takes a recording/, 'the action bar says a recording field takes no picture');
      equal(await frame.count(), 0, 'and opens nothing');

      await form.locator('[data-x="save"]').click();
      await form.waitFor({state: 'detached'});
      let text = await source();
      assert(text.includes('front-image: images/arasaac-2317.png') && text.includes('back-image: images/arasaac-2413.png'), 'the card is in the page with its two pictures');
      assert(text.includes('![perro](images/arasaac-2401.png) ![gato](images/arasaac-2402.png)'), 'and its small pictures');
      assert(text.trimEnd().endsWith(CREDIT), 'and ARASAAC\'s credit is the last paragraph, as the pictograms came in through the form');
      equal(occurrences(text, 'Pictograms author'), 1, 'once');

      // an exercise: its picture takes the width and the side a pictogram wants
      await openForm('Choose one answer');
      equal(await fieldOf('Picture with the question').locator('button.ex-pictogram').count(), 1, 'an exercise\'s picture has its Pictogram… too');
      await boxOf('Prompt shown to the learner').fill('Which is the house?');
      await boxOf('Choice 1').fill('la casa');
      await boxOf('Choice 2').fill('el perro');
      await fieldOf('Picture with the question').locator('button.ex-pictogram').click();
      await pickIn('casa', 'Use this pictogram');
      await closed('closed');
      equal(await boxOf('Picture with the question').inputValue(), 'images/arasaac-2317.png', 'the path is in the field');
      await form.locator('summary', {hasText: 'Size and position'}).first().click();
      equal([await fieldOf('Picture with the question').locator('details input[type=number]').inputValue(),
             await fieldOf('Picture with the question').locator('details select').inputValue()], ['20', 'center'],
            'and the width is 20 % and the side the middle, which a pictogram wants (60 % at the left would be soft and huge)');
      await boxOf('Choice 2').click();
      await page.locator('[data-x="pictogram"]').click();
      await pickIn('perro', 'Put it in the text');
      await closed('closed');
      await form.locator('[data-x="save"]').click();
      await form.waitFor({state: 'detached'});
      text = await source();
      assert(text.includes('image: images/arasaac-2317.png {width=20 align=center}'), 'the exercise is in the page with its picture sized and centred: image: images/arasaac-2317.png {width=20 align=center}');
      assert(/el perro !\[perro\]\(images\/arasaac-2401\.png\)|el perro!\[perro\]/.test(text) || text.includes('![perro](images/arasaac-2401.png)'), 'and a small picture in a choice');
      equal(occurrences(text, 'Pictograms author'), 1, 'the credit is still one');
      await until(async () => (await page.locator('#sheet img[src*="arasaac-2317"]').count()) >= 2, 'the preview draws the card\'s picture and the exercise\'s');
      await until(() => page.$$eval('#sheet img[src*="arasaac-"]', els => els.every(i => i.complete && i.naturalWidth > 0)), 'and the pictures have loaded');
      await shot(page, `${mode}-e-exercise`);

      // a jolly card: a figure on a line of its own, in its blocks
      await openForm('Embedded Jolly flashcard');
      equal(await fieldOf('Front — primary text').locator('.ex-insert-row button').allTextContents(), ['Image…', 'Recording…', 'Pictogram…'],
            'a jolly card\'s field has Image…, Recording… and Pictogram… under it');
      await boxOf('Front — primary text').fill('Una casa');
      await boxOf('Back — primary text').fill('A house');
      await boxOf('Front — primary text').click();
      await boxOf('Front — primary text').press('Control+End');
      await fieldOf('Front — primary text').locator('.ex-insert-row button.ex-insert-pictogram').click();
      await pickIn('gato', 'Use this pictogram');
      await closed('closed');
      equal(await boxOf('Front — primary text').inputValue(), 'Una casa\n![gato](images/arasaac-2402.png){width=18 align=center}',
            'a figure on a line of its own, sized for a pictogram, where the cursor was');
      await boxOf('Back — primary text').click();
      await boxOf('Back — primary text').press('Control+End');
      await page.locator('[data-x="pictogram"]').click();
      await pickIn('perro', 'Put it in the text');
      await closed('closed');
      equal(await boxOf('Back — primary text').inputValue(), 'A house\n![perro](images/arasaac-2401.png){width=18 align=center}',
            'the action bar\'s button puts a figure there too, in a field of blocks');
      await form.locator('[data-x="save"]').click();
      await form.waitFor({state: 'detached'});
      text = await source();
      assert(text.includes('![gato](images/arasaac-2402.png){width=18 align=center}') && text.includes('![perro](images/arasaac-2401.png){width=18 align=center}'), 'the jolly card is saved with its figures');
      equal(occurrences(text, 'Pictograms author'), 1, 'and the credit is still one');
      await shot(page, `${mode}-e-jolly`);
    }

    if (mode === 'parseh' && sections.includes('f')) {
      console.log(' f) an exercise deck');
      const r = await fetch(origin + '/exercises/api/decks', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                              body: JSON.stringify({name: 'Casa', lang: 'es'})});
      const deck = (await r.json()).deck;
      const deckApi = `${origin}/exercises/api/decks/${deck.folder}/${deck.slug}`;
      await page.goto(`${origin}/exercises/deck/${deck.folder}/${deck.slug}/`);
      await page.locator('#btn-add-exercise').click();
      await page.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
      await form.waitFor();
      await boxOf('Word or expression').fill('casa');
      await boxOf('Meaning').fill('house');
      equal(await fieldOf('Front image path').locator('.ex-upload-row button').allTextContents(), ['Upload…', 'Pictogram…'], 'a deck\'s form has the same Pictogram… beside Upload…');
      await fieldOf('Front image path').locator('button.ex-pictogram').click();
      await frame.waitFor();
      assert(/this deck's pictures/.test(await page.locator('.pg-note').textContent()), 'the frame says the copy goes into this deck');
      await settled('the first page');
      await pickIn('casa', 'Use this pictogram');
      await closed('closed');
      equal(await boxOf('Front image path').inputValue(), 'images/arasaac-2317.png', 'the deck\'s own copy is named in the field');
      await form.locator('[data-x="save"]').click();
      await form.waitFor({state: 'detached'});
      const got = await (await fetch(deckApi)).json();
      equal(got.items.length, 1, 'the card is in the deck');
      assert(got.items[0].markdown.includes('front-image: images/arasaac-2317.png'), 'with its picture named');
      const bytes = new Uint8Array(await (await fetch(`${origin}/exercises/media/${deck.folder}/${deck.slug}/images/arasaac-2317.png`)).arrayBuffer());
      assert(same(bytes, await pictogramFile(2317)), 'and the deck holds the picture, byte for byte');
      await shot(page, `${mode}-f-deck`);
    }

    if (sections.includes('h')) {
      console.log(' h) the themes and a phone');
      const luminance = rgb => {
        // (a colour made by color-mix() is read back as color(srgb 0.3 0.2 0.1), each between 0 and 1)
        const unit = rgb.startsWith('color(') ? 1 : 255;
        const [r, g, b] = rgb.match(/[\d.]+/g).slice(0, 3).map(Number).map(v => { v /= unit; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      const contrast = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
      const id = await newDoc('Themes');
      await openEditor(id);                                   // (a page to keep the setting on)
      const panels = {};
      for (const theme of ['light', 'dark', 'sepia']) {
        await page.evaluate(t => localStorage.setItem('parseh_theme', t), theme);
        await openEditor(id);
        await page.locator('#btn-pictograms').click();
        await frame.waitFor();
        await search('casa');
        await cells().first().click();
        const c = await page.evaluate(() => {
          const look = sel => { const cs = getComputedStyle(document.querySelector(sel)); return [cs.color, cs.backgroundColor]; };
          return {modal: look('.pg-modal'), input: look('.pg-q'), preview: look('.pg-preview'), tile: look('.pg-tile'), count: look('.pg-count'),
                  foot: look('.pg-credit'), primary: look('.pg-primary')};
        });
        panels[theme] = c.modal[1];
        assert(contrast(c.modal[0], c.modal[1]) >= 4.5, `${theme}: the text reads on the frame (contrast ${contrast(c.modal[0], c.modal[1]).toFixed(1)})`);
        assert(contrast(c.input[0], c.input[1]) >= 4.5, `${theme}: the text reads in the search box`);
        assert(contrast(c.foot[0], c.preview[1]) >= 4.5 || contrast(c.foot[0], c.modal[1]) >= 4.5, `${theme}: the credit reads`);
        assert(contrast(c.primary[0], c.primary[1]) >= 4.5, `${theme}: the button reads`);
        equal(c.tile[1], 'rgb(255, 255, 255)', `${theme}: a picture sits on white, whatever the page is (it is black lines on nothing)`);
        await shot(page, `${mode}-h-${theme}`);
        await page.keyboard.press('Escape');
        await closed('closed');
      }
      assert(new Set(Object.values(panels)).size === 3, `the three themes paint the frame three ways: ${JSON.stringify(panels)}`);
      await page.evaluate(() => localStorage.setItem('parseh_theme', 'light'));

      // a phone
      await context.close();
      const phone = await browser.newContext({viewport: {width: 390, height: 780}, isMobile: true, hasTouch: true, deviceScaleFactor: 2});
      const m = await phone.newPage();
      await m.goto(url(`/doc/${id}/edit`));
      await m.locator('#btn-pictograms').waitFor();
      await m.locator('#btn-pictograms').scrollIntoViewIfNeeded();
      await m.locator('#btn-pictograms').tap();
      await m.locator('.pg-overlay').waitFor();
      await until(async () => (await m.locator('.pg-results').getAttribute('aria-busy')) === 'false', 'the first page, on a phone');
      const box = await m.evaluate(() => {
        const r = document.querySelector('.pg-modal').getBoundingClientRect();
        return {x: r.x, y: r.y, w: r.width, h: r.height, vw: innerWidth, vh: innerHeight, scroll: document.documentElement.scrollWidth,
                preview: getComputedStyle(document.querySelector('.pg-preview')).display};
      });
      equal([box.x, box.y, box.w], [0, 0, box.vw], 'on a phone the frame fills the screen');
      assert(box.h >= box.vh - 1 && box.scroll <= box.vw, `without a sideways scroll (${box.scroll} of ${box.vw})`);
      equal(box.preview, 'none', 'and the preview waits for a choice, so the thumbnails have the room');
      await m.locator('.pg-search .pg-q').fill('casa');
      await m.locator('.pg-search .pg-q').press('Enter');
      await until(async () => (await m.locator('.pg-results').getAttribute('aria-busy')) === 'false', 'the answer');
      await m.locator('.pg-cell').first().tap();
      await until(() => m.locator('.pg-big img').evaluate(i => i.complete && i.naturalWidth > 0), 'the preview picture loads');
      const sheet = await m.evaluate(() => {
        const rect = el => { const r = el.getBoundingClientRect(); return {t: r.top, b: r.bottom, l: r.left, r: r.right, w: r.width, h: r.height}; };
        const top = (el) => { const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!hit && (hit === el || el.contains(hit)); };
        const add = document.querySelector('.pg-actions .pg-primary'), back = document.querySelector('.pg-back'), big = document.querySelector('.pg-big');
        return {preview: getComputedStyle(document.querySelector('.pg-preview')).position, add: rect(add), addOnTop: top(add), back: rect(back), backOnTop: top(back),
                big: rect(big), vh: innerHeight, vw: innerWidth, scroll: document.documentElement.scrollWidth,
                focus: document.activeElement.className, grid: getComputedStyle(document.querySelector('.pg-grid')).display};
      });
      equal(sheet.preview, 'absolute', 'a tap on a thumbnail opens the preview as a sheet over the list');
      assert(sheet.addOnTop && sheet.add.b <= sheet.vh && sheet.add.l >= 0 && sheet.add.r <= sheet.vw, `the Add button is on the screen and nothing covers it (${JSON.stringify(sheet.add)})`);
      assert(sheet.backOnTop, 'so is Back');
      assert(sheet.big.w >= 200 && sheet.big.h >= 200, `the picture is as large as the screen allows (${Math.round(sheet.big.w)} px)`);
      assert(/pg-back/.test(sheet.focus), 'the keys are on Back, in the sheet');
      assert(sheet.scroll <= sheet.vw, 'with no sideways scroll');
      await shot(m, `${mode}-h-phone`);
      await m.locator('.pg-back').tap();
      equal(await m.evaluate(() => getComputedStyle(document.querySelector('.pg-preview')).display), 'none', 'Back shuts the sheet');
      assert(await m.locator('.pg-cell').first().isVisible(), 'and the thumbnails are there');
      await m.locator('.pg-cell').first().tap();
      await m.locator('.pg-actions .pg-btn', {hasText: 'keep looking'}).tap();
      await until(async () => /Added/.test(await m.locator('.pg-say').textContent()), 'Add, keep looking adds');
      equal(await m.evaluate(() => getComputedStyle(document.querySelector('.pg-preview')).display), 'none', 'and goes back to the list, to choose another');
      await m.locator('.pg-cell').nth(1).tap();
      await m.locator('.pg-actions .pg-primary').tap();
      await until(async () => (await m.locator('.pg-overlay').count()) === 0, 'Add, on a phone, closes the frame');
      const phoneText = await m.locator('#src').inputValue();
      assert(phoneText.includes('![casa](images/arasaac-2317.png)') && phoneText.includes('![casa](images/arasaac-2319.png)'), 'and both figures are in the page');
      await phone.close();
    }
  } finally {
    await browser.close();
    proc.kill();
    await proc.status;
  }
}

async function states(mode) {
  console.log(`\n== ${mode}: what is here ==`);
  const run = async (flags, fn) => {
    const {proc, info} = await startHarness(mode, flags);
    const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
    try {
      const context = await browser.newContext({viewport: {width: 1400, height: 900}});
      const page = await context.newPage();
      const origin = `http://127.0.0.1:${info.port}`, base = info.studio;
      await fn({page, info, origin, url: p => origin + base + p, api: async (method, path, body) => {
        const r = await fetch(origin + base + path, {method, headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
        return r.json();
      }});
    } finally {
      await browser.close();
      proc.kill();
      await proc.status;
    }
  };
  const open = async (page, url, api) => {
    const made = await api('POST', '/api/docs', {markdown: '---\ntitle: Empty\ntarget: es\n---\n\nUna casa.\n'});
    await page.goto(url(`/doc/${made.meta.id}/edit`));
    await page.locator('#btn-pictograms').click();
    await page.locator('.pg-overlay').waitFor();
    await until(async () => (await page.locator('.pg-results').getAttribute('aria-busy')) === 'false', 'the answer');
  };

  if (sections.includes('g')) {
    console.log(' g) not installed');
    await run([], async ({page, info, origin, url, api}) => {
      if (mode === 'parseh') {
        await page.goto(origin + '/settings/arasaac/');
        await page.locator('#ar .it, #ar .go-row').first().waitFor();
        equal(await page.locator('[data-look]').count(), 0, 'the door offers nothing to look through while nothing is here');
      }
      await open(page, url, api);
      assert(/not on this computer yet/.test(await page.locator('.pg-empty').textContent()), 'the frame says the pictograms are not on this computer');
      equal([await page.locator('.pg-grid').isVisible(), await page.locator('.pg-preview').isVisible()], [false, false], 'and draws no grid and no preview');
      assert((await page.locator('.pg-credit').textContent()).startsWith('Pictograms author'), 'the credit is still there, from the server');
      if (mode === 'parseh') {
        equal(await page.locator('.pg-empty a.pg-primary').getAttribute('href'), '/settings/arasaac/', 'in Parseh it sends to the door that gets them');
      } else {
        equal(await page.locator('.pg-empty a').count(), 0, 'the studio on its own has no such page, so it does not link to one');
        assert(/Open Parseh's Settings/.test(await page.locator('.pg-empty').textContent()), 'it says where they are got instead');
      }
      await page.screenshot({path: SHOTS ? `${SHOTS}/${mode}-g-absent.png` : '/dev/null'}).catch(() => {});
      // they arrive while the frame is open: Look again
      const put = new Deno.Command(python, {args: [root + '/tests/pictogram_world.py', info.arasaac], cwd: root, stdout: 'null', stderr: 'piped'});
      const done = await put.output();
      assert(done.success, 'the pictograms are put on the computer');
      if (mode === 'studio') {
        await page.locator('.pg-empty button', {hasText: 'Look again'}).click();
      } else {
        await page.keyboard.press('Escape');
        await page.locator('#btn-pictograms').click();
      }
      await until(async () => (await page.locator('.pg-cell').count()) > 0, 'the thumbnails appear');
      assert(true, 'and then the frame has them, with no reload of the page');
    });

    console.log(' g2) part of it');
    await run(['--pictograms=partial'], async ({page, url, api}) => {
      await open(page, url, api);
      const text = await page.locator('.pg-count').textContent();
      assert(/only 12 of 92 pictures are here/.test(text), `only the pictures that are here are listed, and it says how far it got: ${text}`);
      equal(await page.locator('.pg-cell').count(), 12, 'twelve thumbnails');
      await page.locator('.pg-q').fill('sun');
      await page.locator('.pg-q').press('Enter');
      await until(async () => /No pictogram for “sun”/.test(await page.locator('.pg-count').textContent()), 'a word whose picture is still to come finds nothing');
      await page.locator('.pg-q').fill('house');
      await page.locator('.pg-q').press('Enter');
      await until(async () => (await page.locator('.pg-cell').count()) === 3, 'and one whose picture is here finds it');
    });
  }
}

try {
  for (const mode of modes) { await suite(mode); await states(mode); }
  console.log(`\npictogram_picker: ${passed} checks passed`);
} catch (e) {
  console.log(String(e.stack || e));
  Deno.exit(1);
}
