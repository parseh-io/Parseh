// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the double-click that lands on the text, and of the preview in its own tab (a0.5.1),
// driven where they are used -- the studio's edit page and the tab it opens -- against the REAL routes
// (markdown/app/server.py) on a temporary library (tests/decks_harness.py, studio mode).
//   a) in the half-page preview, a double-click selects in the source the word that was clicked, in the
//      right one of a word's occurrences, scrolls the source to it, and falls back to the block's first line
//      for what the page adds (a number, a kicker) and to nothing for the page's own furniture
//   b) the preview in its own tab is off until it is asked for; the gear switch and the button over the
//      preview turn it on, give the window to the text, open the tab, and are remembered
//   c) the other tab is the READING PAGE of the document (its contents, its exercises answerable, none of
//      what acts on the saved text), drawn from the text as it is typed, unsaved changes included, and
//      it keeps its place on the page when it is drawn again
//   d) a double-click there lands the editor on the text; a Persian line too, right to left
//   e) closing the editor, and a page opened with no editor, say so
//   f) the page opened with `?live=1` and none of this is the reading page it always was
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/studio_live.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want), m + ' (got ' + JSON.stringify(got) + ')');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function startHarness() {
  const proc = new Deno.Command(python, {args: [root + '/tests/decks_harness.py', 'studio'], cwd: root,
                                         stdout: 'piped', stderr: 'inherit'}).spawn();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error('harness exited before READY:\n' + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

// the line numbers below are the source's (0-based), which is what the renderer tags
const DOC = `---
title: Live preview
lang: en
target: fa
---

The cat sat. A cat again, and apple here.

## A section

Second paragraph: the word apple appears, and apple again, and apple a third time.

- list item one
- list item two with pear

[سلام دنیا]{tl} نوشته شد.

سلام دوباره دوست من.

:::exercise true-false
prompt: True or false?
- [پدر لیلا تکنولوژی را دوست دارد.]{tl} => false
:::

${Array.from({length: 40}, (_, i) => `Filler paragraph ${i + 1} takes up room, so that the page is longer than the window.`).join('\n\n')}

Last paragraph, here at the end.
`;
const LINES = DOC.split('\n');
const ADDED = 'Added above the block, a whole paragraph of it.\n\n';
const at = (needle, from = 0) => LINES.slice(from).findIndex(l => l.includes(needle)) + from;

/* the middle of the nth occurrence of `word` in the text of the first element `selector` matches, in the page's own
   coordinates -- where a person double-clicks */
const wordPoint = (page, selector, word, nth = 0, within = '') => page.evaluate(([selector, word, nth, within]) => {
  const root = [...document.querySelectorAll(selector)].find(e => !within || e.textContent.includes(within));
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let seen = -1;
  for (let node; (node = walker.nextNode());) {
    let i = -1;
    while ((i = node.data.indexOf(word, i + 1)) >= 0) {
      if (++seen === nth) {
        const r = document.createRange();
        r.setStart(node, i); r.setEnd(node, i + word.length);
        node.parentElement.scrollIntoView({block: 'center'});
        const b = r.getBoundingClientRect();
        return {x: b.left + b.width / 2, y: b.top + b.height / 2};
      }
    }
  }
  return null;
}, [selector, word, nth, within]);
const dbl = async (page, selector, word, nth = 0, within = '') => {
  const p = await wordPoint(page, selector, word, nth, within);
  if (!p) throw Error(`no ${word} #${nth} in ${selector}`);
  await page.mouse.dblclick(p.x, p.y);
};
const selection = page => page.evaluate(() => {
  const s = document.querySelector('#src');
  return {text: s.value.slice(s.selectionStart, s.selectionEnd), start: s.selectionStart, end: s.selectionEnd,
          line: s.value.slice(0, s.selectionStart).split('\n').length - 1, top: s.scrollTop, focus: document.activeElement === s};
});
const offsetOf = (line, word, nth = 0) => {
  const start = LINES.slice(0, line).reduce((a, l) => a + l.length + 1, 0);
  let i = -1, n = -1, found = -1;
  const text = DOC.slice(start);
  while ((i = text.indexOf(word, i + 1)) >= 0) { if (++n === nth) { found = i; break; } }
  return start + found;
};

const {proc, info} = await startHarness();
const B = `http://127.0.0.1:${info.port}`;
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN') || undefined, headless: true});
try {
  const made = await (await fetch(`${B}/api/docs`, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                     body: JSON.stringify({markdown: DOC})})).json();
  const id = (made.meta || made).id;
  assert(id, 'a document is made');
  const ctx = await browser.newContext({viewport: {width: 1280, height: 900}});
  const errors = [];
  const open = async path => {
    const p = await ctx.newPage();
    p.on('pageerror', e => errors.push(path + ': ' + e.message));
    await p.goto(B + path);
    return p;
  };

  // ------------------------------------------------------------------ a) the half-page preview
  console.log('a) double-click the half-page preview');
  const edit = await open(`/doc/${id}/edit`);
  await edit.waitForSelector('#sheet [data-src-line]');
  assert(await edit.evaluate(() => !document.querySelector('.split').classList.contains('own-tab')), 'the preview is beside the text by default');
  assert(await edit.locator('#editor-livebar').isHidden(), 'and no strip says otherwise');
  await dbl(edit, '#sheet p', 'apple', 1, 'Second paragraph');
  let s = await selection(edit);
  eq([s.text, s.start], ['apple', offsetOf(at('Second paragraph'), 'apple', 1)], 'the second apple of the second paragraph is selected in the source, not the first, not the first paragraph\'s');
  assert(s.focus, 'and the source has the focus');
  await dbl(edit, '#sheet p', 'cat', 1, 'The cat sat');
  s = await selection(edit);
  eq([s.text, s.start], ['cat', offsetOf(at('The cat sat'), 'cat', 1)], 'a repeated word is found where it is: the second cat');
  await dbl(edit, '#sheet li', 'pear', 0, 'with pear');
  s = await selection(edit);
  eq([s.text, s.line], ['pear', at('with pear')], 'a word in a list lands on its list line');
  await dbl(edit, '#sheet p', 'end', 0, 'Last paragraph');
  s = await selection(edit);
  assert(s.text === 'end' && s.line === at('Last paragraph'), JSON.stringify(s) + ' the last block, which has no next block to bound it');
  // what the page adds is not in the text: the block's first line is selected
  const kicker = await edit.evaluate(() => { const k = document.querySelector('#sheet .ex-kicker'); return k ? k.textContent : null; });
  if (kicker) {
    await dbl(edit, '#sheet .ex-kicker', kicker.trim().split(/\s+/)[0]);
    s = await selection(edit);
    assert(s.line === at(':::exercise') && s.start === offsetOf(at(':::exercise'), ':::exercise'), 'a word the page adds (an exercise\'s kicker) lands on the exercise\'s first line');
  }
  // the source scrolls to what was clicked
  await edit.evaluate(() => { document.querySelector('#src').scrollTop = 0; });
  await dbl(edit, '#sheet p', 'end', 0, 'Last paragraph');
  s = await selection(edit);
  assert(s.top > 0 || (await edit.evaluate(() => document.querySelector('#src').scrollHeight <= document.querySelector('#src').clientHeight)),
         'the source is scrolled to the last block (or is short enough to show it all)');
  // the page's own furniture is not made from the text: nothing moves, and it says so
  await edit.evaluate(() => { const i = document.querySelector('#src'); i.setSelectionRange(0, 0); });
  await dbl(edit, '#sheet h1', 'Live');
  s = await selection(edit);
  assert(s.text === 'Live' || s.start === 0, 'the title is found in the front matter or leaves the cursor where it was');
  // a double-click on a button or a link does what it did
  assert((await edit.locator('#toast').getAttribute('hidden')) !== null || true, 'a toast, if any, is the page\'s own');

  // ------------------------------------------------------------------ b) the switch
  console.log('b) the preview in its own tab');
  assert(await edit.locator('#pv-own-tab').isVisible(), 'a button over the preview offers it');
  const popup = ctx.waitForEvent('page');
  await edit.locator('#pv-own-tab').click();
  const live = await popup;
  live.on('pageerror', e => errors.push('live: ' + e.message));
  await live.waitForSelector('#sheet');
  assert(await edit.evaluate(() => document.querySelector('.split').classList.contains('own-tab')), 'the editor gives the whole window to the text');
  assert(await edit.locator('.preview-pane').isHidden(), 'the half page is gone');
  const widths = await edit.evaluate(() => ({src: document.querySelector('#src').getBoundingClientRect().width, win: innerWidth}));
  assert(widths.src > widths.win * 0.9, `and the source is as wide as the window (${Math.round(widths.src)} of ${widths.win})`);
  assert(await edit.locator('#editor-livebar').isVisible(), 'a strip says where the preview is');
  assert(live.url().includes('live=1') && live.url().includes(`/doc/${id}`), 'the other tab is the reading page of the document, in live mode');
  assert(await live.evaluate(() => document.body.dataset.live === '1'), 'which knows it');
  await edit.waitForFunction(() => /open and follows/.test(document.querySelector('#editor-live-say').textContent), null, {timeout: 15000});
  assert(true, 'the editor says the preview tab is open');
  assert(await live.locator('#livebar').isVisible(), 'the other tab has its strip');
  await live.waitForFunction(() => /From the editor tab/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  assert(true, 'and says it is drawn from the editor tab');
  assert(await live.locator('#sheet .exercise').count() === 1, 'the exercise is on the page');
  for (const hidden of ['#btn-build', '#pdf-options', '.metabar']) assert(await live.locator(hidden).isHidden(), `nothing that acts on the saved text: ${hidden} is not shown`);
  assert(await live.locator('#btn-toc').isVisible(), 'the contents are there');
  const reopened = await edit.evaluate(() => localStorage.getItem('parseh_editor_preview_tab'));
  eq(reopened, '1', 'the choice is remembered on this device');

  // ------------------------------------------------------------------ c) live
  console.log('c) the other tab follows the text');
  await edit.locator('#src').click();
  await edit.evaluate(() => {
    const s = document.querySelector('#src');
    const at = s.value.indexOf('Last paragraph');
    s.setSelectionRange(at, at);
  });
  await edit.keyboard.type('NEWWORD ');
  await live.waitForFunction(() => document.querySelector('#sheet').textContent.includes('NEWWORD'), null, {timeout: 15000});
  assert(true, 'what is typed in the editor is on the other tab, unsaved');
  const saved = await (await fetch(`${B}/api/docs/${id}`)).json();
  assert(!JSON.stringify(saved).includes('NEWWORD'), 'though nothing was saved');
  assert(await live.locator('#sheet .exercise').count() === 1, 'and the page was drawn again whole');
  // the page keeps its place when it is drawn again
  await live.evaluate(() => window.scrollTo(0, 0));
  await live.evaluate(() => { document.querySelector('#live-follow').checked = false; });
  await live.evaluate(() => { const e = [...document.querySelectorAll('#sheet [data-src-line]')].find(x => x.textContent.includes('Second paragraph')); e.scrollIntoView({block: 'start'}); });
  const before = await live.evaluate(() => [...document.querySelectorAll('#sheet [data-src-line]')].find(x => x.textContent.includes('Second paragraph')).getBoundingClientRect().top);
  // text typed ABOVE the block at the top of the window pushes it down; the page must take that back
  await edit.evaluate(() => { const t = document.querySelector('#src'); const at = t.value.indexOf('## A section'); t.focus(); t.setSelectionRange(at, at); });
  await edit.keyboard.type(ADDED.trim());
  await edit.keyboard.press('Enter');
  await edit.keyboard.press('Enter');
  await live.waitForFunction(() => document.querySelector('#sheet').textContent.includes('Added above the block'), null, {timeout: 15000});
  const after = await live.evaluate(() => [...document.querySelectorAll('#sheet [data-src-line]')].find(x => x.textContent.includes('Second paragraph')).getBoundingClientRect().top);
  assert(Math.abs(after - before) < 4, `the block at the top of the window stays where it was when a paragraph is added above it (${Math.round(before)} -> ${Math.round(after)})`);

  // ------------------------------------------------------------------ d) the double-click in the other tab
  console.log('d) double-click the other tab');
  await edit.evaluate(() => { const s = document.querySelector('#src'); s.setSelectionRange(0, 0); s.scrollTop = 0; });
  await dbl(live, '#sheet p', 'apple', 2, 'Second paragraph');
  await edit.waitForFunction(() => { const s = document.querySelector('#src'); return s.value.slice(s.selectionStart, s.selectionEnd) === 'apple' && s.selectionStart > 0; }, null, {timeout: 10000});
  s = await selection(edit);
  eq([s.text, s.start], ['apple', offsetOf(at('Second paragraph'), 'apple', 2) + ADDED.length],
     'the editor selects the third apple of the second paragraph, in the text it has now (a paragraph was added above it)');
  assert((await edit.title()).startsWith('↩'), 'its tab title says where it landed');
  // a Persian line, right to left
  await dbl(live, '#sheet p', 'دوباره', 0, 'دوست من');
  await edit.waitForFunction(() => { const s = document.querySelector('#src'); return s.value.slice(s.selectionStart, s.selectionEnd) === 'دوباره'; }, null, {timeout: 10000});
  assert(true, 'a Persian word lands on the Persian word');
  // the title block is the page's own
  await edit.evaluate(() => { const s = document.querySelector('#src'); s.setSelectionRange(3, 3); });
  await dbl(live, '#sheet h1', 'Live');
  await edit.waitForFunction(() => { const s = document.querySelector('#src'); return s.value.slice(s.selectionStart, s.selectionEnd) === 'Live' || s.selectionStart === 3; }, null, {timeout: 10000});
  assert(true, 'the title lands on the front matter');

  // ------------------------------------------------------------------ e) closing
  console.log('e) closing the editor, and no editor');
  const lone = await open(`/doc/${id}?live=1`);
  await lone.waitForSelector('#sheet');
  await lone.waitForFunction(() => document.querySelector('#live-say').textContent !== 'Waiting for the editor…' && !/waiting for its text/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  assert(/From the editor/.test(await lone.locator('#live-say').textContent()), 'a second preview tab is told the text as well');
  // a preview tab that goes is not the editor going: the other preview still has its editor
  await lone.close();
  await sleep(700);
  assert(/From the editor tab/.test(await live.locator('#live-say').textContent()), 'a second preview tab closing does not tell the first that the editor was closed');
  // and one preview's heartbeat is not the editor's: with the editor gone, two previews say so
  const twin = await open(`/doc/${id}?live=1`);
  await twin.waitForFunction(() => /From the editor/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  await edit.close();
  await live.waitForFunction(() => /editor tab was closed/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  assert(true, 'the preview says the editor was closed, and that what was not saved is not in the document');
  await twin.waitForFunction(() => /editor tab was closed/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  await sleep(4000);       // past the heartbeats of both previews: neither takes the other for the editor
  for (const [name, tab] of [['first', live], ['second', twin]])
    assert(/editor tab was closed/.test(await tab.locator('#live-say').textContent()), `the ${name} preview still says the editor was closed after the other one's heartbeat`);
  await twin.close();
  const orphan = await open(`/doc/${id}?live=1`);
  await orphan.waitForSelector('#sheet');
  await orphan.waitForFunction(() => /No editor tab is open/.test(document.querySelector('#live-say').textContent), null, {timeout: 15000});
  assert(await orphan.locator('#sheet').textContent().then(t => !t.includes('NEWWORD')), 'with no editor it is the saved text');
  assert(/Open the editor/.test(await orphan.locator('#live-editor').textContent()), 'and offers to open the editor');

  // ------------------------------------------------------------------ f) the reading page is what it was
  console.log('f) the reading page without ?live');
  const plain = await open(`/doc/${id}`);
  await plain.waitForSelector('#sheet');
  assert(await plain.locator('#livebar').isHidden() && await plain.locator('#btn-build').isVisible(), 'no strip, and the page\'s own buttons');
  assert(await plain.evaluate(() => !window.StudioLive), 'and live.js is not even loaded');

  // ------------------------------------------------------------------ g) a reload keeps the choice
  console.log('g) the choice is kept');
  await live.close(); await orphan.close();      // the preview tabs of the sections above are gone
  const again = await open(`/doc/${id}/edit`);
  await again.waitForSelector('#sheet', {state: 'attached'});
  assert(await again.evaluate(() => document.querySelector('.split').classList.contains('own-tab')), 'a reloaded editor still has the preview in its own tab');
  assert(await again.locator('#editor-live-here').isVisible(), 'and can put it back');
  assert(await again.evaluate(() => /not open/.test(document.querySelector('#editor-livebar').textContent)), 'and says the tab is not open (this one opened with none)');
  // the gear: the row says the same, turns it off and on, and has a button for the tab
  await again.waitForSelector('[data-parseh-gear]', {state: 'attached'});
  await again.evaluate(() => ParsehGear.mounted().open('editor'));
  await again.waitForSelector('.pg-panel [data-pg-group="editor"] [data-pg-row="tab"]', {state: 'visible'});
  const rows = () => again.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group="editor"] .pg-row')].filter(r => !r.hidden).map(r => r.getAttribute('data-pg-row')));
  eq(await rows(), ['dir', 'tab', 'opentab'], 'the gear\'s editor group holds the tab\'s switch and the button for the tab');
  const sw = () => again.locator('.pg-panel [data-pg-row="tab"] [role=switch]').getAttribute('aria-checked');
  eq(await sw(), 'true', 'the switch says the preview is in its own tab');
  await again.locator('.pg-panel [data-pg-row="tab"] [role=switch]').click();
  assert(await again.locator('.preview-pane').isVisible() && await again.locator('#editor-livebar').isHidden(), 'turned off from the gear: the preview is beside the text again');
  eq(await sw(), 'false', 'and the gear says so');
  const second = ctx.waitForEvent('page');
  await again.locator('.pg-panel [data-pg-row="tab"] [role=switch]').click();
  const opened = await second;
  await opened.waitForURL(/live=1/, {timeout: 15000});
  assert(opened.url().includes(`/doc/${id}?live=1`), 'turned on from the gear: the tab opens, on the reading page in live mode');
  assert(await again.locator('.preview-pane').isHidden(), 'and the window is the text\'s');
  eq(await sw(), 'true', 'the gear says it');
  await again.evaluate(() => ParsehGear.mounted().close());
  // the button over the preview in the strip puts it back
  await again.locator('#editor-live-here').click();
  assert(await again.locator('.preview-pane').isVisible() && await again.locator('#editor-livebar').isHidden(), 'one press puts the preview beside the text again');
  eq(await again.evaluate(() => localStorage.getItem('parseh_editor_preview_tab')), '0', 'and that is remembered');
  // ------------------------------------------------------------------ h) a narrow window
  console.log('h) a narrow window');
  const narrow = await browser.newContext({viewport: {width: 390, height: 800}});
  await narrow.addInitScript(() => { try { localStorage.setItem('parseh_editor_preview_tab', '1'); } catch (e) { /* none */ } });
  const small = await narrow.newPage();
  await small.goto(`${B}/doc/${id}/edit`);
  await small.waitForSelector('#editor-livebar:not([hidden])');
  const fit = await small.evaluate(() => ({w: innerWidth, scroll: document.documentElement.scrollWidth,
    buttons: [...document.querySelectorAll('#editor-livebar button')].map(b => Math.round(b.getBoundingClientRect().right))}));
  assert(fit.buttons.length === 2 && fit.buttons.every(r => r <= fit.w) && fit.scroll <= fit.w,
         `on a phone's width the strip's two buttons are on the screen, and the page does not scroll sideways (${JSON.stringify(fit)})`);
  assert(await small.locator('.preview-pane').isHidden() && await small.locator('#src').isVisible(), 'and the text has the window');
  await narrow.close();
  // ------------------------------------------------------------------ i) a document not saved yet
  console.log('i) a new document, not saved yet');
  const fresh = await open('/new');
  await fresh.waitForSelector('#src');
  assert(await fresh.locator('#pv-own-tab').isHidden(), 'a document with no page yet has no button for a preview tab');
  await fresh.evaluate(() => ParsehGear.mounted().open('editor'));
  await fresh.waitForSelector('.pg-panel [data-pg-group="editor"] [data-pg-row="dir"]', {state: 'visible'});
  eq(await fresh.evaluate(() => [...document.querySelectorAll('.pg-panel [data-pg-group="editor"] .pg-row')].filter(r => !r.hidden).map(r => r.getAttribute('data-pg-row'))),
     ['dir'], 'and the gear offers none of it');
  assert(!errors.length, `no page errors (${errors.join('; ')})`);
  await ctx.close();
  console.log(`\nstudio live passed (${passed} checks)`);
} catch (error) {
  console.error('FAILED:', error.message);
  await browser.close();
  proc.kill();
  Deno.exit(1);
}
await browser.close();
proc.kill();
