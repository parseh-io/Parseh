// SPDX-License-Identifier: GPL-3.0-or-later
// Run: CHROME_BIN=/path/to/chrome PARSEH_PYTHON=/path/to/python3 deno run --allow-all tests/studio_prompt.mjs
//      STUDIO_PROMPT_SHOTS=<dir>   saves the page and the dialog at 1280 and 390 px in the three themes
//      STUDIO_PROMPT_MODES=studio  (or parseh) runs one mount; the other is only a smoke of the page and the dialog
//      STUDIO_PROMPT_KEEPGOING=1   goes on past a section that fails and lists them (to see what an old page fails)
//      STUDIO_PROMPT_ONLY=a1,b1    runs only those sections (a development aid)
//
// THE STUDIO'S PROMPT PAGE AND ITS EXERCISE DIALOG: the boxes, the presets, the level and the length, the
// scheme of the transliteration, and the sizes (static/promptpick.js, app.js initPrompt, editor.js exercisePrompt),
// driven against the REAL routes of tests/studio_harness.py in a real Chromium.  What the page draws is compared with
// what the route answers, read at the time: what a box is called, says, weighs and belongs to, which boxes a language
// has, what a preset holds, how many types there are -- none of it is written in this file.  The ids it names are
// stimuli (boxes it ticks to see the prompt move: math, latex, vocab ...) and `colourparts`, the box of the a0.4.3
// dialect, whose place in its group and absence from every preset but `all` are asserted against the route's data.
// A stub in front of the route (page.route) is used only for what no real route sends yet: a box a person's own
// prompt turns off (`disabled`), a box the page has never heard of, a slow answer, and a deck list.
//
//  a1) the page draws the route's boxes, groups, lines and sizes; the one line about what is not ticked; the
//      lesson ticked; the prompt in the box is the route's; the total is the row's own count
//  a2) a box ticked and unticked: the prompt and the total move, the preset stops showing and comes back
//  a3) every preset: ticks exactly its boxes; shows only while the ticked set is its; the a0.4.3 box is in no
//      preset but `all`; `none` leaves the always-in part
//  a4) a language the route says cannot use a box does not draw it; the ticked set is one for every language
//  a5) level and length: the route's lists; each copied as its line; remembered across a reload
//  a6) the scheme of the transliteration: the language's own word, `translit=ipa` sent, per language, none for Chinese
//  a7) remembered across a reload; localStorage refused; a remembered id the server no longer has
//  a8) a box with `disabled` is greyed with its sentence; a box the page never heard of is drawn; a slow answer
//      that comes late is dropped; the copy is off while the prompt is being made again
//  a9) Edit prompt greys the boxes and the choices; Cancel gives them back
//  a10) the copy is exactly what the box shows, with the question after it
//  b1) the dialog: the route's boxes (those it shows) and the twelve types, ticked from the page, with their sizes
//  b2) a type or a box changed: the copy is the route's prompt for it; no type ticked asks nothing and says why
//  b3) level, length and the scheme of the transliteration go into the request; decks of the page's language only
//  b4) the box of the a0.4.3 dialect is pre-ticked for a page that uses it; the page's own remembered boxes do not
//      come into the dialog, and the dialog never writes them
//  c)  at 1280 and 390 px in the light, sepia and dark themes: nothing outside the window, every control reachable
//  d)  no page error, no console error, no native dialog
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('STUDIO_PROMPT_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('STUDIO_PROMPT_SHOTS') || '';
const KEEP = !!Deno.env.get('STUDIO_PROMPT_KEEPGOING');
const ONLY = (Deno.env.get('STUDIO_PROMPT_ONLY') || '').split(',').filter(Boolean);
if (SHOTS) await Deno.mkdir(SHOTS, {recursive: true});
let passed = 0;
const failed = [];
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const eq = (got, want, m) => assert(same(got, want),
  m + (same(got, want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 10000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(40);
  }
}
async function section(name, what, fn) {
  if (ONLY.length && !ONLY.includes(name)) return;
  console.log(`\n-- ${name}) ${what}`);
  try { await fn(); } catch (e) {
    if (!KEEP) throw e;
    failed.push(name);
    console.log('  FAILED', name, String(e.message).split('\n')[0]);
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

// "12,500", the way the page says an exact count (an oracle of its own: four lines)
const fmt = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const norm = s => s.replace(/\n*$/, '\n');

async function suite(mode) {
  const full = mode === 'studio';
  console.log(`\n==== ${mode} ====`);
  const {proc, info, log} = await startHarness(mode);
  const origin = `http://127.0.0.1:${info.port}`, base = info.studio;
  const url = p => origin + base + p;
  const get = async p => { const r = await fetch(url(p)); return {status: r.status, data: await r.json()}; };
  const post = async (p, body) => {
    const r = await fetch(url(p), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    return {status: r.status, data: await r.json()};
  };
  // what the server makes for a choice: the oracle every comparison of the page's box is made against
  const promptRoute = async (target, o = {}) => {
    const q = ['target=' + target];
    if (o.boxes) q.push('boxes=' + o.boxes.join(','));
    if (o.level) q.push('level=' + o.level);
    if (o.length) q.push('length=' + o.length);
    if (o.translit) q.push('translit=' + o.translit);
    const r = await get('/api/prompt?' + q.join('&'));
    if (r.status !== 200) throw Error('the route refused ' + q.join('&') + ': ' + JSON.stringify(r.data));
    return r.data;
  };
  const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  const problems = [];
  const forgive = re => { for (let i = problems.length - 1; i >= 0; i--) if (re.test(problems[i])) problems.splice(i, 1); };
  async function context(init) {
    const ctx = await browser.newContext({viewport: {width: 1280, height: 900}, serviceWorkers: 'block'});
    await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], {origin});
    if (init) await ctx.addInitScript(init);
    return ctx;
  }
  const watch = (page, name) => {
    page.on('pageerror', e => problems.push(`${name}: page error ${e.message}`));
    // a refused request is named by its address: the console only says "404"
    page.on('response', r => { if (r.status() >= 400) problems.push(`${name}: ${r.status()} ${new URL(r.url()).pathname}`); });
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) problems.push(`${name}: console ${m.text()}`); });
    page.on('dialog', d => { problems.push(`${name}: native dialog ${d.message()}`); d.dismiss(); });
    return page;
  };
  const prompt = async (ctx, name, target, before) => {
    const page = watch(await ctx.newPage(), name);
    if (before) before(page);
    await page.goto(url('/prompt'));
    if (target) await page.selectOption('#prompt-target', target);
    await page.waitForSelector('#prompt-boxes .pp-box');
    await settle(page);
    return page;
  };
  // the prompt is MADE: the copy button is off from the moment a choice changes until the answer is drawn
  const settle = page => page.waitForFunction(() => {
    const b = document.querySelector('#llm-row .llmrow-copy');
    return b && !b.disabled && document.querySelector('#prompt-text').value;
  }, null, {timeout: 15000});
  const clip = page => page.evaluate(() => navigator.clipboard.readText());
  const read = page => page.evaluate(() => {
    const sizeOf = l => l.querySelector('.pp-size');
    return {
      boxes: [...document.querySelectorAll('#prompt-boxes .pp-box[data-box]')].map(l => ({
        id: l.dataset.box, group: l.closest('fieldset').dataset.group, name: l.querySelector('.pp-name').textContent,
        line: l.querySelector('.pp-says').textContent, chars: sizeOf(l).dataset.chars, said: sizeOf(l).textContent,
        on: l.querySelector('input').checked, off: l.querySelector('input').disabled,
        why: l.querySelector('.pp-offwhy').textContent, greyed: l.classList.contains('pp-off')})),
      presets: [...document.querySelectorAll('#prompt-boxes .pp-preset')].map(b => ({
        id: b.dataset.preset, name: b.textContent, on: b.getAttribute('aria-pressed') === 'true', off: b.disabled})),
      groups: [...document.querySelectorAll('#prompt-boxes .pp-group legend')].map(l => l.textContent),
      text: document.querySelector('#prompt-text').value,
      total: (document.querySelector('#prompt-boxes .pp-total') || {}).textContent || '',
      totalChars: ((document.querySelector('#prompt-boxes .pp-total') || {}).dataset || {}).chars,
      rowChars: (document.querySelector('#llm-row .llmrow-size') || {dataset: {}}).dataset.chars,
      copyOff: !!(document.querySelector('#llm-row .llmrow-copy') || {}).disabled,
      level: (document.querySelector('#prompt-level') || {}).value, length: (document.querySelector('#prompt-length') || {}).value,
    };
  });
  const ticked = async page => (await read(page)).boxes.filter(b => b.on).map(b => b.id);
  const click = async (page, id) => { await page.click(`#prompt-boxes [data-box="${id}"] .pp-name`); await settle(page); };
  const setBoxes = async (page, ids) => {          // through the page's own controls: untick what is not wanted, tick what is
    for (const b of (await read(page)).boxes) {
      if (b.on !== ids.includes(b.id)) await page.click(`#prompt-boxes [data-box="${b.id}"] .pp-name`);
    }
    await settle(page);
  };
  const shownIds = c => c.boxes.filter(b => b.shown).map(b => b.id);
  const defaultPreset = c => c.presets.find(p => p.default);
  const sizeOf = (page, text) => page.evaluate(t => ParsehLLMRow.promptSize(t), text);

  try {
    /* the route's data, the oracle of everything below */
    const fa = await promptRoute('fa');
    const colourparts = fa.boxes.find(b => b.id === 'colourparts');
    const lesson = defaultPreset(fa);

    await section('a1', 'the page draws what the route answers', async () => {
      const ctx = await context();
      const asked = [];
      const page = await prompt(ctx, 'a1', null, p => p.on('request', r => { if (/\/api\/prompt\?/.test(r.url())) asked.push(r.url()); }));
      eq(asked.length, 1, 'opened with nothing remembered, the page asks the server for its prompt once');
      const s = await read(page);
      eq(s.boxes.map(b => b.id), shownIds(fa), `the boxes drawn are the ${shownIds(fa).length} the route says Persian can use, in its order`);
      eq(s.boxes.map(b => [b.name, b.line, b.group]), fa.boxes.filter(b => b.shown).map(b => [b.name, b.line, b.group]),
         'each with the name, the one line and the group the route gives');
      eq(s.boxes.map(b => b.chars), fa.boxes.filter(b => b.shown).map(b => String(b.chars)), 'each with the size the route measured');
      eq(s.boxes.map(b => b.said), fa.boxes.filter(b => b.shown).map(b => fmt(b.chars) + ' characters'), 'said in words, with its thousands');
      eq(s.groups, [...new Set(fa.boxes.filter(b => b.shown).map(b => b.group))], 'the group headings are the route\'s, once each, in its order');
      assert(!!colourparts && colourparts.shown, 'the route has the box of the a0.4.3 dialect (colour inside a word), shown for Persian');
      const cp = s.boxes.find(b => b.id === 'colourparts');
      assert(cp && cp.group === colourparts.group && cp.line === colourparts.line && cp.chars === String(colourparts.chars) && !cp.on,
             `that box is drawn in its group "${colourparts.group}", with its line and its size (${colourparts.chars}), unticked`);
      eq(s.boxes.map(b => b.id).indexOf('colourparts'), s.boxes.map(b => b.id).indexOf('colours') + 1, 'right after the colour marks');
      const why = await page.evaluate(() => {
        const w = document.querySelector('#prompt-boxes .pp-why'), g = document.querySelector('#prompt-boxes .pp-group');
        return {text: w.textContent, before: !!(w.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING)};
      });
      assert(/not tick/.test(why.text) && /reserved/.test(why.text) && /by accident/.test(why.text) && why.before,
             'one line above the boxes says that what is not ticked is still named as reserved, so the model does not write it by accident');
      eq(s.boxes.filter(b => b.on).map(b => b.id).sort(), shownIds({boxes: fa.boxes}).filter(id => lesson.boxes.includes(id)).sort(),
         'on opening, the lesson (the route\'s default preset) is ticked');
      eq(s.presets.filter(p => p.on).map(p => p.id), [lesson.id], 'and only it shows as chosen');
      eq(s.presets.map(p => [p.id, p.name]), fa.presets.map(p => [p.id, p.name]), 'the presets are the route\'s, with its names, in its order');
      assert(norm(fa.prompt) === s.text, 'the box shows the prompt the route made');
      const size = await sizeOf(page, fa.prompt);
      eq(String(s.totalChars), String(size.chars), 'the total under the boxes is the row\'s own count of that prompt');
      assert(s.total.includes(size.line) && s.total.includes(fmt(fa.always_chars) + ' characters'),
             `and says it (${size.line}) with what is there whatever is ticked (${fa.always_chars} characters)`);
      eq(s.rowChars, String(size.chars), 'the row\'s size line is the same count');
      const note = await page.evaluate(() => document.querySelector('#question').placeholder);
      assert(/hot and cold/.test(note) && !/Persian|Italian|Farsi|italiano/i.test(note), `the question's example is English and names no language (${note})`);
      await ctx.close();
    });

    await section('a2', 'a box ticked and unticked moves the prompt and the total', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a2');
      const before = await read(page);
      const extra = fa.boxes.find(b => b.shown && !lesson.boxes.includes(b.id));
      await click(page, extra.id);
      let s = await read(page);
      assert(s.boxes.find(b => b.id === extra.id).on, `${extra.name} is ticked`);
      const want = await promptRoute('fa', {boxes: [...lesson.boxes, extra.id]});
      assert(s.text === norm(want.prompt), 'the box shows the route\'s prompt for the lesson and that box');
      const grew = Number(s.totalChars) - Number(before.totalChars);
      assert(grew > extra.chars * 0.75 && grew < extra.chars * 1.3, `the total grew by ${grew} (the box says ${extra.chars})`);
      eq(s.rowChars, s.totalChars, 'the row\'s size follows it');
      eq(s.presets.filter(p => p.on).map(p => p.id), [], 'no preset shows: the ticked set is nobody\'s');
      await click(page, extra.id);
      s = await read(page);
      assert(s.text === before.text && s.totalChars === before.totalChars, 'unticked, the prompt and the total are what they were');
      eq(s.presets.filter(p => p.on).map(p => p.id), [lesson.id], 'and the lesson shows again');
      await ctx.close();
    });

    await section('a3', 'every preset ticks its boxes, and shows only while the set is its own', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a3');
      const shown = new Set(shownIds(fa));
      for (const p of fa.presets) {
        await page.click(`#prompt-boxes [data-preset="${p.id}"]`);
        await settle(page);
        const s = await read(page);
        eq(s.boxes.filter(b => b.on).map(b => b.id).sort(), p.boxes.filter(id => shown.has(id)).sort(), `"${p.name}" ticks its boxes`);
        eq(s.presets.filter(x => x.on).map(x => x.id), [p.id], `and shows alone`);
        const want = await promptRoute('fa', {boxes: p.boxes});
        assert(s.text === norm(want.prompt), `the box shows the route's prompt for "${p.name}"`);
        assert(s.boxes.find(b => b.id === 'colourparts').on === p.boxes.includes('colourparts'), `colour inside a word is ticked by "${p.name}" only if the route's preset has it`);
        if (!p.boxes.length) eq(s.totalChars, String(fa.always_chars), `"${p.name}" leaves exactly the always-in part (${fa.always_chars} characters, the route's own figure)`);
      }
      eq(fa.presets.filter(p => p.boxes.includes('colourparts')).map(p => p.id), ['all'], 'the route puts the a0.4.3 box in no preset but all');
      await ctx.close();
    });

    await section('a4', 'a language that cannot use a box does not draw it; the set is one for every language', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a4');
      const per = {};
      for (const code of ['fa', 'it', 'ja', 'zh', 'ar']) {
        const c = await promptRoute(code, {boxes: await ticked(page)});
        await page.selectOption('#prompt-target', code);
        await settle(page);
        await page.waitForFunction(c => document.querySelector('#prompt-text').value.includes('target: ' + c), code);
        const s = await read(page);
        per[code] = s.boxes.map(b => b.id);
        eq(per[code], shownIds(c), `${code}: the boxes drawn are the ones the route says it can use`);
        assert(s.text === norm((await promptRoute(code, {boxes: await ticked(page)})).prompt), `${code}: and the box shows its prompt`);
      }
      const rtl = id => ['fa', 'ar'].some(c => per[c].includes(id)) && ['it', 'ja'].every(c => !per[c].includes(id));
      assert(rtl('rtl'), 'right-to-left sequences are drawn for Persian and Arabic and not for Italian or Japanese');
      assert(per.ja.includes('reading') && !per.fa.includes('reading') && !per.it.includes('reading'), 'reading marks for Japanese alone');
      // one set: ticked in Japanese, hidden in Persian, still ticked when Japanese comes back
      await page.selectOption('#prompt-target', 'ja'); await settle(page);
      await setBoxes(page, ['reading', 'math']);
      await page.selectOption('#prompt-target', 'fa'); await settle(page);
      eq(await ticked(page), ['math'], 'in Persian the reading marks are not drawn');
      await page.selectOption('#prompt-target', 'ja'); await settle(page);
      eq(await ticked(page), ['reading', 'math'], 'and in Japanese they are ticked still: one set for every language');
      await ctx.close();
    });

    await section('a5', 'level and length', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a5');
      const lists = await page.evaluate(() => ['#prompt-level', '#prompt-length'].map(s =>
        [...document.querySelector(s).options].map(o => [o.value, o.textContent])));
      eq(lists[0], fa.levels.map(x => [x.id, x.name]), 'for a learner at: the route\'s levels');
      eq(lists[1], fa.lengths.map(x => [x.id, x.name]), 'length: the route\'s lengths');
      const s0 = await read(page);
      eq([s0.level, s0.length], ['', ''], 'both on "not said" at first');
      const level = fa.levels[2], length = fa.lengths[2];
      await page.selectOption('#prompt-level', level.id); await settle(page);
      await page.selectOption('#prompt-length', length.id); await settle(page);
      const s = await read(page);
      const want = await promptRoute('fa', {boxes: lesson.boxes, level: level.id, length: length.id});
      assert(s.text === norm(want.prompt) && s.text.length > s0.text.length, `the prompt is the route's for ${level.name} and ${length.name}: a line each at its end`);
      eq(s.rowChars, String((await sizeOf(page, norm(want.prompt))).chars), 'and its size is said');
      await page.reload();
      await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      const r = await read(page);
      eq([r.level, r.length, r.text === s.text], [level.id, length.id, true], 'after a reload both are as they were, and so is the prompt');
      await ctx.close();
    });

    await section('a6', 'the scheme of the transliteration', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a6', 'ja');
      const jaRoute = await promptRoute('ja');
      const opt = jaRoute.options.find(o => o.name === 'translit');
      const label = await page.textContent('.pp-under .llmrow-opt[data-option="translit"]');
      assert(label.startsWith(opt.label + ':'), `Japanese: the choice is labelled with the language's own word (${opt.label})`);
      eq(await page.$$eval('.pp-under .llmrow-opt select option', o => o.map(x => [x.value, x.textContent])),
         opt.choices.map(c => [c.id, c.label]), 'with the route\'s choices');
      const requests = [];
      page.on('request', r => { if (/\/api\/prompt\?/.test(r.url())) requests.push(r.url()); });
      await page.selectOption('.pp-under .llmrow-opt select', 'ipa');
      await settle(page);
      assert(requests.some(u => /translit=ipa/.test(u)), 'choosing IPA sends translit=ipa');
      const want = await promptRoute('ja', {boxes: lesson.boxes, translit: 'ipa'});
      assert((await read(page)).text === norm(want.prompt) && /· IPA/.test(want.prompt.split('\n')[0]), 'and the box shows the prompt whose first line says IPA');
      await page.selectOption('#prompt-target', 'fa'); await settle(page);
      const faOpt = fa.options.find(o => o.name === 'translit');
      assert((await page.textContent('.pp-under .llmrow-opt[data-option="translit"]')).startsWith(faOpt.label + ':'), 'Persian: its own word (' + faOpt.label + ')');
      eq(await page.inputValue('.pp-under .llmrow-opt select'), 'classic', 'and its own choice: IPA was Japanese\'s');
      await page.selectOption('#prompt-target', 'ja'); await settle(page);
      eq(await page.inputValue('.pp-under .llmrow-opt select'), 'ipa', 'back in Japanese the choice is remembered');
      const zh = await promptRoute('zh');
      await page.selectOption('#prompt-target', 'zh'); await settle(page);
      eq(await page.$$eval('.pp-under .llmrow-opt', o => o.length), zh.options.length, `Chinese: as many choices as the route says (${zh.options.length})`);
      await ctx.close();
    });

    await section('a7', 'remembered on this device; storage refused; an id the server no longer has', async () => {
      let ctx = await context();
      let page = await prompt(ctx, 'a7');
      const mine = ['vocab', 'math', 'forms'];
      await setBoxes(page, mine);
      const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('parseh_prompt_boxes')));
      eq(saved.sort(), [...mine].sort(), 'the ticked set is kept under parseh_prompt_boxes, as ids');
      const again = [];
      page.on('request', r => { if (/\/api\/prompt\?/.test(r.url())) again.push(decodeURIComponent(r.url())); });
      await page.reload(); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      eq(again.length, 1, 'a reload asks once, with what was kept');
      assert(/boxes=/.test(again[0]) && mine.every(id => again[0].includes(id)), 'and names those boxes');
      eq(await ticked(page), shownIds(fa).filter(id => mine.includes(id)), 'after a reload the same boxes are ticked');
      assert((await read(page)).text === norm((await promptRoute('fa', {boxes: mine})).prompt), 'and the prompt is the one for them');
      eq((await read(page)).presets.filter(p => p.on).map(p => p.id), [], 'with no preset showing');
      // none ticked is a choice too, and is kept as one (an empty set is not "nothing remembered")
      await page.click('#prompt-boxes [data-preset="none"]'); await settle(page);
      await page.reload(); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      const none = await read(page);
      eq([none.boxes.filter(b => b.on).length, none.presets.filter(p => p.on).map(p => p.id)], [0, ['none']], 'none ticked, kept: after a reload still none, and "none" shows');
      assert(none.text === norm((await promptRoute('fa', {boxes: []})).prompt), 'and the prompt is the always-in part alone');
      await ctx.close();

      // storage refused: every access throws
      ctx = await context(() => { Object.defineProperty(window, 'localStorage', {get() { throw new Error('storage is refused'); }}); });
      page = await prompt(ctx, 'a7-refused');
      eq((await read(page)).presets.filter(p => p.on).map(p => p.id), [lesson.id], 'storage refused: the page opens with the lesson ticked');
      await click(page, 'math');
      assert((await ticked(page)).includes('math'), 'and ticking works');
      await page.reload(); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      eq((await read(page)).presets.filter(p => p.on).map(p => p.id), [lesson.id], 'a reload forgets it, and nothing broke');
      await ctx.close();

      // a newer Parseh without a box the old one remembered: the ids it knows are put back, nothing is said
      ctx = await context(() => {
        if (!sessionStorage.getItem('seeded')) {
          sessionStorage.setItem('seeded', '1');
          localStorage.setItem('parseh_prompt_boxes', JSON.stringify(['vocab', 'a-box-this-version-never-had', 'tables']));
          localStorage.setItem('parseh_prompt_level', JSON.stringify('a-level-of-the-past'));
        }
      });
      page = watch(await ctx.newPage(), 'a7-stale');
      const asked = [];
      page.on('request', r => { if (/\/api\/prompt\?/.test(r.url())) asked.push(decodeURIComponent(r.url()).replace(/^.*\/api\/prompt\?/, '')); });
      await page.goto(url('/prompt'));
      await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      await until(async () => (await ticked(page)).length === 2, 'the known ids are put back');
      eq((await ticked(page)).sort(), ['tables', 'vocab'], 'the ids the server knows are ticked, the other is dropped');
      const s = await read(page);
      assert(s.text === norm((await promptRoute('fa', {boxes: ['vocab', 'tables']})).prompt), 'the box shows the prompt for them');
      eq(s.level, '', 'a level the server does not offer is "not said"');
      assert(asked.length >= 3 && /a-box-this-version-never-had/.test(asked[0]) && !/boxes=/.test(asked[1]) && /boxes=vocab,tables/.test(asked[asked.length - 1]),
             `the asks were: with what was kept, plain, then with what the server knows (${JSON.stringify(asked.map(a => a.slice(0, 60)))})`);
      assert(!(await page.evaluate(() => { const t = document.querySelector('#toast'); return t && !t.hidden && t.classList.contains('err'); })),
             'and no error was said');
      forgive(/a7-stale: 400 /);                // the server's refusal of what was kept is the point of this part
      await ctx.close();
    });

    if (full) await section('a8', 'a box that is off, a box nobody here has heard of, a late answer', async () => {
      // 1) a box a person's own prompt turns off: greyed, with the sentence beside it
      let ctx = await context();
      let page = watch(await ctx.newPage(), 'a8-disabled');
      const SAY = 'your own prompt has no {{?id}} marker for this box, so ticking it changes nothing';
      await page.route(u => u.pathname.endsWith('/api/prompt') && u.search.length > 0, async route => {
        const res = await route.fetch();
        const j = await res.json();
        j.boxes.forEach(b => { if (b.shown) b.disabled = SAY; });
        await route.fulfill({response: res, json: j});
      });
      await page.goto(url('/prompt')); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      let s = await read(page);
      assert(s.boxes.length && s.boxes.every(b => b.off && b.greyed && b.said === ''),
             'every box with a `disabled` sentence is greyed, unticking-proof, with no size');
      eq([s.boxes.filter(b => b.why !== '').length, await page.textContent('#prompt-boxes .pp-busy')], [0, SAY],
         'a sentence that is the same for every box is said once above them, and not under each of twenty');
      assert(s.presets.every(p => p.off), 'and the presets, which can change nothing, are off');
      await page.click(`#prompt-boxes [data-box="${s.boxes[0].id}"] .pp-name`, {force: true});
      eq((await read(page)).boxes.map(b => b.on), s.boxes.map(b => b.on), 'a click on one changes nothing');
      // two reasons: each box says its own, beside it, and nothing is said above
      const OTHER = 'this one is off for another reason';
      page = watch(await ctx.newPage(), 'a8-two-reasons');
      await page.route(u => u.pathname.endsWith('/api/prompt') && u.search.length > 0, async route => {
        const res = await route.fetch();
        const j = await res.json();
        j.boxes.forEach((b, i) => { if (b.shown) b.disabled = i % 2 ? SAY : OTHER; });
        await route.fulfill({response: res, json: j});
      });
      await page.goto(url('/prompt')); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      s = await read(page);
      assert(s.boxes.every(b => b.greyed && [SAY, OTHER].includes(b.why)) && new Set(s.boxes.map(b => b.why)).size === 2,
             'two different reasons: each box says its own beside it');
      eq(await page.textContent('#prompt-boxes .pp-busy'), '', 'and nothing is said above them');
      await ctx.close();

      // 2) a box the page has never heard of, in a group nobody has heard of, and a slow answer
      ctx = await context();
      page = watch(await ctx.newPage(), 'a8-unknown');
      const NEW = {id: 'a-box-from-tomorrow', name: 'a box from tomorrow', group: 'a group of tomorrow', line: 'something this page was never told about', chars: 4321, shown: true, on: false};
      let slow = 0, held = [];
      await page.route(u => u.pathname.endsWith('/api/prompt') && u.search.length > 0, async route => {
        const u = new URL(route.request().url());
        const ids = (u.searchParams.get('boxes') || '').split(',').filter(Boolean);
        u.searchParams.set('boxes', ids.filter(id => id !== NEW.id).join(','));
        if (!ids.length) u.searchParams.delete('boxes');
        if (slow > 0 && ids.includes('math') && !ids.includes('latex')) { slow--; held.push('slow'); await sleep(900); }
        const res = await route.fetch({url: u.toString()});
        const j = await res.json();
        j.boxes.push({...NEW, on: ids.includes(NEW.id)});
        await route.fulfill({response: res, json: j});
      });
      await page.goto(url('/prompt')); await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
      s = await read(page);
      const last = s.boxes[s.boxes.length - 1];
      assert(last.id === NEW.id && last.name === NEW.name && last.line === NEW.line && last.group === NEW.group && last.said === '4,321 characters' && !last.on,
             'a box the page never heard of is drawn, with its line and size, in a group of its own');
      eq(s.groups[s.groups.length - 1], NEW.group, 'under the heading the server gave it');
      await click(page, NEW.id);
      assert((await ticked(page)).includes(NEW.id), 'it can be ticked');
      // the slow answer: tick math (slow), then latex at once (fast): the last choice is what is shown
      slow = 1;
      await page.click('#prompt-boxes [data-box="math"] .pp-name');
      const off = await read(page);
      assert(off.copyOff, 'the copy button is off while the prompt is being made for the choice');
      assert(await page.evaluate(() => /being made again/.test(document.querySelector('#llm-row .llmrow-copy').title)), 'and its tooltip says why');
      await until(() => held.length === 1, 'the first ask is out, and held by the stub');
      await page.click('#prompt-boxes [data-box="latex"] .pp-name');
      await settle(page);
      // what the box holds, sampled every few milliseconds while the slow answer comes in: it is the old choice's
      // prompt, and it must never be drawn -- not even for the moment it takes the page to ask again and put it right
      const lenOld = norm((await promptRoute('fa', {boxes: [...lesson.boxes, 'math']})).prompt).length;
      await page.evaluate(() => { window.__lens = []; window.__t = setInterval(() => window.__lens.push(document.querySelector('#prompt-text').value.length), 4); });
      await sleep(1300);
      const lens = await page.evaluate(() => { clearInterval(window.__t); return window.__lens; });
      assert(lens.length > 100 && !lens.includes(lenOld), `the slow answer, made for the choice before, was never drawn (${lens.length} samples of the box)`);
      s = await read(page);
      const both = (await ticked(page)).filter(id => id !== NEW.id);
      assert(both.includes('math') && both.includes('latex'), 'both boxes are ticked');
      const wantBoth = await promptRoute('fa', {boxes: both});
      assert(s.text === norm(wantBoth.prompt), 'the box shows the prompt for both');
      assert(!s.copyOff, 'and the copy button is on again');
      await ctx.close();
    });

    await section('a9', 'the page has no Edit prompt of its own: the row\'s menu is the way to a prompt of yours, and the boxes stay on while its editor is open', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a9');
      eq(await page.evaluate(() => ['btn-edit-prompt', 'btn-save-prompt', 'btn-cancel-edit', 'btn-reset-prompt'].map(i => !!document.getElementById(i))),
         [false, false, false, false], 'the four buttons of the old way are gone: one way to a prompt of your own, not two');
      await page.waitForSelector('#llm-row .llmrow-pm select');
      const was = await read(page);
      await page.click('#llm-row .llmrow-pbtn:has-text("new")');
      await page.waitForSelector('#llm-row .llmrow-editor');
      const s = await read(page);
      assert(s.boxes.every(b => !b.off) && s.presets.every(p => !p.off), 'the editor open: the boxes and the presets still work (it writes a prompt of yours, not the page\'s own)');
      assert(await page.evaluate(() => document.querySelector('#prompt-text').readOnly), 'and the box that shows the prompt is never the person\'s to write in');
      await page.click('#llm-row .llmrow-editor button:has-text("close")');
      await page.waitForSelector('#llm-row .llmrow-editor', {state: 'detached'});
      eq((await read(page)).text, was.text, 'closed again: the prompt is as it was');
      await ctx.close();
    });

    await section('a10', 'the copy is what the box shows, with the question after it', async () => {
      const ctx = await context();
      const page = await prompt(ctx, 'a10');
      await setBoxes(page, ['gloss', 'notes']);
      await page.selectOption('#prompt-level', fa.levels[1].id); await settle(page);
      const q = 'The words for hot and cold: uses, registers, opposites.';
      await page.fill('#question', q);
      await page.click('#llm-row .llmrow-copy');
      await page.waitForFunction(() => /^copied/.test(document.querySelector('#llm-row .llmrow-say').textContent));
      const want = await promptRoute('fa', {boxes: ['gloss', 'notes'], level: fa.levels[1].id});
      eq(await clip(page), norm(want.prompt) + '\n' + q + '\n', 'the clipboard holds the route\'s prompt for these boxes and that level, a blank line, and the question');
      const s = await read(page);
      eq(s.rowChars, String((await sizeOf(page, norm(want.prompt) + '\n' + q + '\n')).chars), 'and the row\'s size is of that text');
      await ctx.close();
    });

    /* ---------------- the dialog ---------------- */
    const PAGE_MD = '---\ntitle: A page\ntarget: fa\n---\n\n## کتاب | ketâb | عربی | = *book*\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n'
      + ':::exercise fill-blanks\nprompt: Fill the blank\ntext: این [[کتاب]] است\n:::\n';
    let made_n = 0;
    async function dialog(ctx, name, init) {
      // a title of its own each time: the library keeps one page to a title
      const made = await post('/api/docs', {markdown: PAGE_MD.replace('A page', `A page ${++made_n}`)});
      const id = made.data.id || (made.data.doc && made.data.doc.id) || (made.data.meta && made.data.meta.id);
      assert(id, `${name}: a page that uses a table and a fill-in exercise`);
      const page = watch(await ctx.newPage(), name);
      if (init) await init(page);
      await page.goto(url(`/doc/${id}/edit`));
      await page.waitForSelector('#btn-exercise-prompt', {state: 'attached'});
      await page.click('summary:has-text("Exercises")');
      page.md = await page.inputValue('#src');          // the page as the editor holds it: what the dialog sends
      await page.click('#btn-exercise-prompt');
      await page.waitForSelector('.ex-prompt-modal .pp-box');
      await dsettle(page);
      return page;
    }
    const dsettle = page => page.waitForFunction(() => {
      const t = document.querySelector('.ex-prompt-modal .llmrow-size');
      return t && t.dataset.chars;
    }, null, {timeout: 15000});
    const dread = page => page.evaluate(() => {
      const m = document.querySelector('.ex-prompt-modal');
      const items = sel => [...m.querySelectorAll(sel)].map(l => ({
        id: l.dataset.box || l.dataset.type, group: l.closest('fieldset').dataset.group, name: l.querySelector('.pp-name').textContent,
        line: l.querySelector('.pp-says').textContent, chars: l.querySelector('.pp-size').dataset.chars, said: l.querySelector('.pp-size').textContent,
        on: l.querySelector('input').checked}));
      return {boxes: items('.pp-box[data-box]'), types: items('.pp-box[data-type]'), groups: [...m.querySelectorAll('.pp-group legend')].map(l => l.textContent),
        size: m.querySelector('.llmrow-size').dataset.chars, status: m.querySelector('.ex-copy-status').textContent,
        levels: [...m.querySelectorAll('select[data-key="level"] option')].map(o => [o.value, o.textContent]),
        lengths: [...m.querySelectorAll('select[data-key="length"] option')].map(o => [o.value, o.textContent]),
        decks: [...m.querySelectorAll('.ex-deck')].map(d => d.textContent)};
    });
    const dtick = async (page, kind, id) => { await page.click(`.ex-prompt-modal [data-${kind}="${id}"] .pp-name`); await sleep(60); await dsettle(page); };
    async function exRoute(body) { const r = await post('/api/exercise-prompt', body); if (r.status !== 200) throw Error(JSON.stringify(r.data)); return r.data; }

    await section('b1', 'the dialog draws the route\'s boxes and types, ticked from the page', async () => {
      const ctx = await context();
      const page = await dialog(ctx, 'b1');
      const R = await exRoute({markdown: page.md, decks: []});
      const d = await dread(page);
      eq(d.boxes.map(b => b.id), shownIds(R), 'the dialect\'s boxes drawn are those the route shows (the exercises and the right-to-left rule are not offered here)');
      eq(d.types.map(t => [t.id, t.name, t.line, t.chars]), R.types.map(t => [t.id, t.name, t.line, String(t.chars)]), `the ${R.types.length} types, with the route's names, lines and sizes`);
      eq(d.boxes.filter(b => b.on).map(b => b.id), R.preticked.boxes, 'the boxes ticked are the ones the page uses (read with the parser)');
      eq(d.types.filter(t => t.on).map(t => t.id), R.preticked.types, 'the types ticked are the ones the page holds');
      assert(R.preticked.boxes.length > 0 && R.preticked.types.length > 0 && R.preticked.types.length < R.types.length, 'and that is some of them, not all: the page uses a table and one exercise type');
      eq(d.boxes.map(b => b.said), R.boxes.filter(b => b.shown).map(b => fmt(b.chars) + ' characters'), 'each box says its size');
      assert(d.groups.includes('the exercises to ask for'), 'the types have a heading of their own');
      eq(d.size, String((await sizeOf(page, R.prompt)).chars), 'the row says the size of that prompt before any copy');
      await page.click('.ex-prompt-modal .llmrow-copy');
      await page.waitForFunction(() => /^copied/.test(document.querySelector('.ex-prompt-modal .llmrow-say').textContent));
      eq(await clip(page), R.prompt, 'and the copy is the route\'s prompt exactly');
      await page.click('.ex-prompt-modal [data-x="cancel"]');
      eq(await page.evaluate(() => document.querySelectorAll('.ex-prompt-modal, .pp, .llmrow').length), 0, 'Close takes the dialog away');
      await ctx.close();
    });

    if (full) await section('b2', 'a type or a box changed; no type ticked', async () => {
      const ctx = await context();
      const page = await dialog(ctx, 'b2');
      const R = await exRoute({markdown: page.md, decks: []});
      const bodies = [];
      page.on('request', r => { if (/exercise-prompt/.test(r.url())) bodies.push(JSON.parse(r.postData())); });
      // the page holds one type, so unticking it leaves none: nothing to ask for
      await page.click(`.ex-prompt-modal [data-type="${R.preticked.types[0]}"] .pp-name`);
      await until(async () => /tick at least one exercise type/.test((await dread(page)).status), 'the dialog says to tick at least one');
      let d = await dread(page);
      assert(d.types.every(t => !t.on), 'every type unticked: the dialog says to tick at least one');
      assert(!bodies.some(b => Array.isArray(b.types) && b.types.length === 0), 'and asks the server nothing for it');
      eq(d.size, undefined, 'no size is said for a prompt that is not made');
      const flash = R.types.find(t => t.id === 'flashcard');
      await dtick(page, 'type', flash.id);
      const want = await exRoute({markdown: page.md, decks: [], boxes: R.preticked.boxes, types: [flash.id]});
      await page.click('.ex-prompt-modal .llmrow-copy');
      await page.waitForFunction(() => /^copied/.test(document.querySelector('.ex-prompt-modal .llmrow-say').textContent));
      eq(await clip(page), want.prompt, 'with the flashcard alone the copy is the route\'s prompt for it');
      d = await dread(page);
      assert(!d.status.includes('tick at least'), 'and the warning is gone');
      const box = R.boxes.find(b => b.shown && !R.preticked.boxes.includes(b.id));
      await dtick(page, 'box', box.id);
      const want2 = await exRoute({markdown: page.md, decks: [], boxes: [...R.preticked.boxes, box.id], types: [flash.id]});
      await page.click('.ex-prompt-modal .llmrow-copy');
      await page.waitForFunction(() => /^copied/.test(document.querySelector('.ex-prompt-modal .llmrow-say').textContent));
      eq(await clip(page), want2.prompt, `ticking ${box.name} too: the copy is the route's prompt for it`);
      eq([...bodies[bodies.length - 1].boxes].sort(), [...R.preticked.boxes, box.id].sort(), 'the request names the boxes ticked, the page\'s and that one');
      eq(bodies[bodies.length - 1].types, [flash.id], 'and the one type');
      await ctx.close();
    });

    if (full) await section('b3', 'level, length and the scheme go into the request; the decks are the page\'s language', async () => {
      const ctx = await context();
      const decksAsked = [];
      const DECKS = {decks: [{path: 'x/fa-one.apkg', name: 'Persian basics', language: 'fa', cards: 12}, {path: 'x/fa-two.apkg', name: 'Persian verbs', language: 'fa', cards: 1}]};
      const page = await dialog(ctx, 'b3', async p => {
        await p.route(u => u.pathname.endsWith('/api/exercise-decks'), async route => {
          decksAsked.push(new URL(route.request().url()).searchParams.get('target'));
          await route.fulfill({json: DECKS});
        });
      });
      eq(decksAsked, ['fa'], 'the dialog asks for the decks of the page\'s language (target=fa)');
      let d = await dread(page);
      eq(d.decks, ['Persian basics · fa · 12 cards', 'Persian verbs · fa · 1 card'], 'and lists what it was given');
      const R = await exRoute({markdown: page.md, decks: []});
      eq(d.levels, fa.levels.map(x => [x.id, x.name]), 'for a learner at: the server\'s levels');
      eq(d.lengths, fa.lengths.map(x => [x.id, x.name]), 'length: the server\'s lengths');
      const bodies = [];
      page.on('request', r => { if (/exercise-prompt/.test(r.url())) bodies.push(JSON.parse(r.postData())); });
      await page.selectOption('.ex-prompt-modal select[data-key="level"]', 'advanced'); await sleep(60); await dsettle(page);
      await page.selectOption('.ex-prompt-modal select[data-key="length"]', 'short'); await sleep(60); await dsettle(page);
      const optSel = '.ex-prompt-modal .llmrow-opt select';
      await page.selectOption(optSel, 'ipa'); await sleep(60); await dsettle(page);
      await page.check('.ex-prompt-modal .ex-deck input'); await sleep(60); await dsettle(page);
      await page.click('.ex-prompt-modal .llmrow-copy');
      await page.waitForFunction(() => /^copied/.test(document.querySelector('.ex-prompt-modal .llmrow-say').textContent));
      const lastBody = bodies[bodies.length - 1];
      eq([lastBody.level, lastBody.length, lastBody.translit, lastBody.decks], ['advanced', 'short', 'ipa', ['x/fa-one.apkg']], 'the request carries the level, the length, the scheme and the deck ticked');
      assert(/· IPA/.test((await clip(page)).split('\n')[0]) && /advanced/.test(await clip(page)), 'and the copy has them: IPA in its first line, the level in its text');
      await ctx.close();
    });

    await section('b4', 'the a0.4.3 box pre-ticked; the page\'s own choices do not come in, and are not written', async () => {
      const ctx = await context(() => {
        if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
          localStorage.setItem('parseh_prompt_boxes', JSON.stringify(['math', 'latex'])); }
      });
      const page = await dialog(ctx, 'b4', async p => {
        // a page that uses a word coloured in parts: the route says the box is ticked from it, and the page draws it so
        await p.route(u => u.pathname.endsWith('/api/exercise-prompt'), async route => {
          const res = await route.fetch();
          const j = await res.json();
          if (!j.preticked.boxes.includes('colourparts')) j.preticked.boxes.push('colourparts');
          j.boxes.forEach(b => { if (b.id === 'colourparts') b.on = true; });
          await route.fulfill({response: res, json: j});
        });
      });
      const d = await dread(page);
      const cp = d.boxes.find(b => b.id === 'colourparts');
      assert(cp && cp.on && cp.group === colourparts.group && cp.said === fmt(colourparts.chars) + ' characters', `colour inside a word is drawn in "${colourparts.group}" with its size and ticked`);
      assert(!d.boxes.find(b => b.id === 'math').on && !d.boxes.find(b => b.id === 'latex').on, 'the boxes the prompt page remembers (math, latex) are not the dialog\'s');
      await dtick(page, 'box', 'math');
      const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('parseh_prompt_boxes')));
      eq(kept, ['math', 'latex'], 'and what the dialog does is not written into the page\'s memory');
      await ctx.close();
    });

    /* ---------------- how it looks ---------------- */
    // THE THEME IS THE DEVICE'S WORD WITH THE MOMENT IT WAS SAID (a0.5.0): the edit page loads lib/prefs.js, which brings the computer's
    // value when that is the newer -- and an earlier context of this run has told this server a theme.  So each preset carries its moment.
    await section('c', 'at 1280 and 390 px in the three themes: inside the window, reachable', async () => {
      for (const [vw, vh] of [[1280, 800], [390, 844]]) {
        for (const theme of ['light', 'sepia', 'dark']) {
          const ctx = await context(t => { try { localStorage.setItem('parseh_theme', t); } catch (e) {} });
          const page = watch(await ctx.newPage(), `c-${vw}-${theme}`);
          await page.addInitScript(t => { try { localStorage.setItem('parseh_theme', t); localStorage.setItem('parseh_at', JSON.stringify({parseh_theme: Date.now() / 1000})); } catch (e) {} }, theme);
          await page.setViewportSize({width: vw, height: vh});
          await page.goto(url('/prompt'));
          await page.waitForSelector('#prompt-boxes .pp-box'); await settle(page);
          const probe = () => page.evaluate(() => {
            const vwid = document.documentElement.clientWidth;
            const out = {wide: document.documentElement.scrollWidth > vwid + 1, theme: document.body.dataset.theme || 'paper', bad: []};
            for (const el of document.querySelectorAll('#prompt-boxes .pp-box, #prompt-boxes .pp-preset, #prompt-under select, #llm-row button')) {
              const r = el.getBoundingClientRect();
              if (r.width && (r.left < -0.5 || r.right > vwid + 0.5)) out.bad.push((el.dataset.box || el.className) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
            }
            return out;
          });
          let p = await probe();
          eq([p.wide, p.bad], [false, []], `${theme} ${vw}px: nothing is wider than the window`);
          const wantTheme = theme === 'light' ? 'paper' : theme;
          eq(p.theme, wantTheme, `${theme} ${vw}px: the page is in that theme`);
          // every box and every preset can be pressed: what is at the middle of its box is the box
          await page.evaluate(() => document.querySelector('#prompt-boxes .pp-group').scrollIntoView());
          const hit = await page.evaluate(() => {
            const bad = [];
            for (const el of document.querySelectorAll('#prompt-boxes .pp-box, #prompt-boxes .pp-preset')) {
              el.scrollIntoView({block: 'center'});
              const r = el.getBoundingClientRect();
              const top = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(r.height / 2, 12));
              if (!top || !(el === top || el.contains(top))) bad.push((el.dataset.box || el.dataset.preset) + ' under ' + (top && (top.className || top.tagName)));
            }
            return bad;
          });
          eq(hit, [], `${theme} ${vw}px: every box and every preset is what the middle of it points at (nothing lies over it)`);
          // the total stays in view at the foot of the window while the boxes are ticked
          const sticky = await page.evaluate(() => {
            document.querySelector('#prompt-boxes .pp-group:nth-of-type(2)').scrollIntoView({block: 'center'});
            const t = document.querySelector('#prompt-boxes .pp-total').getBoundingClientRect();
            return t.bottom <= innerHeight + 0.5 && t.top >= 0;
          });
          assert(sticky, `${theme} ${vw}px: the total is in view while the boxes are being ticked`);
          if (SHOTS) {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({path: `${SHOTS}/${mode}-page-${theme}-${vw}-top.png`});
            await page.evaluate(() => document.querySelector('#question').scrollIntoView({block: 'center'}));
            await page.screenshot({path: `${SHOTS}/${mode}-page-${theme}-${vw}-question.png`});
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({path: `${SHOTS}/${mode}-page-${theme}-${vw}-full.png`, fullPage: true});
          }
          await ctx.close();
        }
      }
      // the dialog
      for (const [vw, vh] of [[1280, 800], [390, 700]]) {
        for (const theme of ['light', 'sepia', 'dark']) {
          const ctx = await context();
          const page = await dialog(ctx, `c-dialog-${vw}-${theme}`, async p => {
            await p.addInitScript(t => { try { localStorage.setItem('parseh_theme', t); localStorage.setItem('parseh_at', JSON.stringify({parseh_theme: Date.now() / 1000})); } catch (e) {} }, theme);
            await p.setViewportSize({width: vw, height: vh});
          });
          const g = await page.evaluate(() => {
            const m = document.querySelector('.ex-prompt-modal').getBoundingClientRect();
            const body = document.querySelector('.ex-prompt-body');
            const copy = document.querySelector('.ex-prompt-modal .llmrow-copy').getBoundingClientRect();
            const close = document.querySelector('.ex-prompt-modal [data-x="cancel"]').getBoundingClientRect();
            const at = r => document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return {inside: m.left >= 0 && m.right <= innerWidth && m.top >= 0 && m.bottom <= innerHeight + 0.5,
                    scrolls: body.scrollHeight > body.clientHeight, wide: document.documentElement.scrollWidth > innerWidth + 1,
                    copyHit: at(copy).closest('.llmrow-copy') !== null, closeHit: at(close).closest('[data-x="cancel"]') !== null,
                    theme: document.body.dataset.theme || 'paper'};
          });
          eq([g.inside, g.wide, g.copyHit, g.closeHit], [true, false, true, true], `dialog ${theme} ${vw}px: whole inside the window, the copy button and Close reachable`);
          assert(g.scrolls, `dialog ${theme} ${vw}px: its boxes scroll inside it, the copy row stays in view`);
          eq(g.theme, theme === 'light' ? 'paper' : theme, `dialog ${theme} ${vw}px: in that theme`);
          if (SHOTS) {
            await page.screenshot({path: `${SHOTS}/${mode}-dialog-${theme}-${vw}.png`});
            await page.evaluate(() => { const b = document.querySelector('.ex-prompt-body'); b.scrollTop = b.scrollHeight; });
            await page.screenshot({path: `${SHOTS}/${mode}-dialog-${theme}-${vw}-types.png`});
          }
          await ctx.close();
        }
      }
    });

    await section('d', 'no page error, no console error, no native dialog, no refused request', async () => {
      // THE STUDIO RUN ON ITS OWN has no /lib/ of the toolbox (the pages say so in a comment: lib/activity.js is serve.py's;
      // so is lib/prefs.js, which the edit page loads since a0.5.0 so that the theme follows a person -- the gear's own two
      // files, which it answers for itself, are not asked for in vain)
      // and lib/guidelink.js, the guide link of every bar (15.10), is the toolbox's too, as is lib/syncpage.js (sync, a0.7.0)
      if (!base) { forgive(/: 404 \/lib\/activity\.js$/); forgive(/: 404 \/lib\/prefs\.js$/); forgive(/: 404 \/lib\/guidelink\.js$/); forgive(/: 404 \/lib\/syncpage\.js$/); }
      eq(problems, [], 'every page of this run stayed quiet');
    });
  } finally {
    await browser.close();
    proc.kill('SIGTERM');
    try { await proc.status; } catch (_) { /* gone */ }
  }
}

for (const mode of modes) await suite(mode);
console.log(`\n${passed} ok, ${failed.length} sections failed${failed.length ? ': ' + failed.join(', ') : ''}`);
if (failed.length) Deno.exit(1);
