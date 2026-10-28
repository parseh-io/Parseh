// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the LaTeX drawings (TO-DO §8.39, a0.4.0), against the REAL
// routes on a temporary library, with the TeX this computer has:
//   a) the editor's preview draws a document's latex blocks, and a block that
//      cannot be drawn is a frame saying why, in words
//   b) the LaTeX drawing sheet: a theme chosen, the drawing made as it is
//      typed, a mistake said in words beside it, Insert putting the block in
//   c) THE PENCIL: hovering a drawing in the preview offers ✎ on the drawing,
//      it goes away again when the pointer leaves, and pressing it reopens
//      the block, whose edit goes back over the very lines it came from.
//      (It never appeared for a whole week of a0.4.0's work -- it reused the
//      RTL pencil's class, which is `display: none`, and only set `hidden` --
//      because no test had ever opened the sheet: found by driving, 2026-09-25.)
//   c2) THE PENCIL ON A DRAWING INSIDE AN EXERCISE, and inside a step of a follow-up: it rewrites that drawing's own
//      lines, indented as they were and fenced as they were (five colons in a step) -- it used to be told a line number
//      counted from the start of the prompt, and rewrote the front matter of the page and the exercise's first lines
//   d) (parseh) Settings -> LaTeX drawings: its themes, the bar of its doors,
//      and a page that never scrolls sideways on a phone
// Two modes, each a tests/studio_harness.py:
//   studio  the studio's own server (studio at /)
//   parseh  Parseh's handler (studio at /studio, Settings at /settings/)
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/latex_drawings.mjs
//   LATEX_DRAWINGS_MODES=studio (or parseh) runs one; SHOTS=<dir> saves the
//   screenshots. LATEX_DRAWINGS_SETTINGS_ONLY=1 runs just the Settings checks,
//   without compiling a drawing, on Parseh's handler. A computer with no
//   xelatex otherwise skips it, saying so: the drawings are TeX's, and a
//   fresh clone must stay green.
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const settingsOnly = Deno.env.get('LATEX_DRAWINGS_SETTINGS_ONLY') === '1';
const modes = settingsOnly ? ['parseh']
  : (Deno.env.get('LATEX_DRAWINGS_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(a === b, `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
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

// no TeX, no drawings: a named skip
if (!settingsOnly) {
  const hasTeX = await new Deno.Command('xelatex', {args: ['--version'], stdout: 'null', stderr: 'null'}).output()
    .then(r => r.success, () => false);
  if (!hasTeX) {
    console.log('SKIP: no xelatex on this computer -- the drawings are made by TeX (tests/latex_drawings.mjs)');
    Deno.exit(0);
  }
}

const DOC = `---
target: it
---
# Disegni

Una formula ordinaria: [E = mc^2]{math}.

::::latex chemistry {width=45 align=center}
\\ce{2H2 + O2 -> 2H2O}
::::

Un blocco rotto:

::::latex
\\undefinedcommandxyz
::::

Un blocco con un tema che non esiste:

::::latex nosuchtheme
x
::::
`;

async function startHarness(mode) {
  const args = [root + '/tests/studio_harness.py', mode];
  if (mode === 'parseh') args.push('--latex-missing');
  if (mode === 'parseh') args.push('--latex-compiler-states');
  const proc = new Deno.Command(python, {args, cwd: root,
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

async function suite(mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info, log} = await startHarness(mode);
  const origin = `http://127.0.0.1:${info.port}`, base = info.studio;
  const url = p => origin + base + p;
  const api = async (method, path, body) => {
    const r = await fetch(url(path), {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                      body: body ? JSON.stringify(body) : undefined});
    const data = await r.json();
    if (!r.ok) throw Error(`${method} ${path}: ${r.status} ${JSON.stringify(data)}`);
    return data;
  };
  const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const shot = async name => { if (SHOTS) await page.screenshot({path: `${SHOTS}/latex-${mode}-${name}.png`}); };
    if (!settingsOnly) {
      const source = () => page.locator('#src').inputValue();
      const made = await api('POST', '/api/docs', {markdown: DOC});
      const id = made.meta.id;

    /* ---------------- a) the preview ---------------- */
    console.log('a) the preview');
    await page.goto(url(`/doc/${id}/edit`));
    await page.waitForSelector('#btn-latex-editor');
    await page.waitForSelector('#sheet figure.latex', {timeout: 30000});
    eq(await page.locator('#sheet figure.latex').count(), 1, 'the block that can be drawn is a drawing');
    const drawn = await page.evaluate(() => {
      const i = document.querySelector('#sheet figure.latex img');
      return i.complete && i.naturalWidth > 20 && /svg/.test(i.currentSrc);
    });
    assert(drawn, 'and its picture (an SVG) really loaded');
    const said = await page.locator('#sheet .latex-fail .latex-said').allTextContents();
    eq(said.length, 2, 'the two blocks that cannot be drawn are frames');
    assert(/undefinedcommandxyz is not a command LaTeX knows here on line 1 of the block/.test(said[0]),
           'one says which command and on which line: ' + said[0].slice(0, 90));
    assert(/asks for the theme .nosuchtheme., which this Parseh does not have/.test(said[1]),
           'the other says the theme is missing: ' + said[1].slice(0, 90));
    await shot('preview');

    /* ---------------- b) the sheet ---------------- */
    console.log('b) the LaTeX drawing sheet');
    // where the block goes is where the caret is, as for every button of the editor: at the end
    await page.locator('#src').click();
    await page.keyboard.press('Control+End');
    await page.click('#btn-latex-editor');
    await page.waitForSelector('.latex-overlay .lx-theme option[value="chemistry"]', {state: 'attached'});
    await page.selectOption('.latex-overlay .lx-theme', 'chemistry');
    await page.fill('.latex-overlay .lx-src', '\\ce{CH4 + 2O2 -> CO2 + 2H2O}');
    await page.waitForSelector('.latex-overlay .lx-stage img', {timeout: 30000});
    assert(await page.evaluate(() => {
      const i = document.querySelector('.latex-overlay .lx-stage img');
      return i.complete && i.naturalWidth > 20;
    }), 'the sheet draws the reaction as it is typed');
    await shot('sheet');
    await page.fill('.latex-overlay .lx-src', '\\undefinedcommandxyz');
    await until(async () => /not a command LaTeX knows/.test(await page.locator('.latex-overlay .lx-status').textContent()),
                'a mistake said in words');
    assert(true, 'a mistake in the sheet is said in words beside the drawing');
    await page.fill('.latex-overlay .lx-src', '\\ce{CH4 + 2O2 -> CO2 + 2H2O}');
    await page.waitForSelector('.latex-overlay .lx-stage img', {timeout: 30000});
    await page.click('.latex-overlay [data-x="ok"]');
    await page.waitForSelector('.latex-overlay', {state: 'detached'});
    assert(/::::latex chemistry[^\n]*\n\\ce\{CH4 \+ 2O2 -> CO2 \+ 2H2O\}\n::::/.test(await source()),
           'Insert puts a ::::latex chemistry block into the text');
    await until(async () => (await page.locator('#sheet figure.latex').count()) === 2, 'the preview draws one more');
    assert(true, 'and the preview draws one more');

    /* ---------------- c) the pencil ---------------- */
    console.log('c) the pencil on a drawing');
    const fig = page.locator('#sheet figure.latex[data-latex-src]').first();
    await fig.scrollIntoViewIfNeeded();
    const pencil = page.locator('button.rtl-edit-btn').filter({hasText: '✎'});
    assert(!(await pencil.count()) || !(await pencil.first().isVisible()), 'no pencil while the pointer is elsewhere');
    await fig.hover();
    await until(async () => (await pencil.count()) && await pencil.first().isVisible(), 'the pencil appears');
    assert(true, 'hovering a drawing offers ✎');
    const boxes = await page.evaluate(() => {
      const f = document.querySelector('#sheet figure.latex[data-latex-src]').getBoundingClientRect();
      const b = [...document.querySelectorAll('button.rtl-edit-btn')].find(x => x.textContent.trim() === '✎').getBoundingClientRect();
      return {f: [f.left, f.top, f.right, f.bottom], b: [b.left, b.top, b.right, b.bottom]};
    });
    // at the drawing's top corner: a short drawing (one line of a reaction is 21 px tall) is
    // shorter than the button, which then hangs below it -- so the corner, not the whole box
    assert(boxes.b[2] - boxes.b[0] > 5 && boxes.b[3] - boxes.b[1] > 5
           && boxes.b[2] <= boxes.f[2] + 2 && boxes.b[2] >= boxes.f[2] - 14
           && Math.abs(boxes.b[1] - boxes.f[1]) <= 8 && boxes.b[0] >= boxes.f[0] - 2,
           `and sits at the drawing's top corner (${boxes.b.map(Math.round)} against ${boxes.f.map(Math.round)})`);
    await page.mouse.move(5, 5);
    await until(async () => !(await pencil.first().isVisible()), 'the pencil goes away', 3000);
    assert(true, 'it goes away again when the pointer leaves');
    await fig.hover();
    await until(async () => await pencil.first().isVisible(), 'the pencil is back');
    await pencil.first().click();
    await page.waitForSelector('.latex-overlay .lx-src');
    eq(await page.inputValue('.latex-overlay .lx-src'), '\\ce{2H2 + O2 -> 2H2O}', 'the pencil reopens the block that was drawn');
    eq(await page.inputValue('.latex-overlay .lx-theme'), 'chemistry', 'with its theme');
    eq(await page.inputValue('.latex-overlay .lx-width'), '45', 'and its width');
    await page.fill('.latex-overlay .lx-src', '\\ce{2H2 + O2 -> 2H2O}\n% edited');
    await page.click('.latex-overlay [data-x="ok"]');
    await page.waitForSelector('.latex-overlay', {state: 'detached'});
    const text = await source();
    assert(/::::latex chemistry \{width=45( align=center)?\}\n\\ce\{2H2 \+ O2 -> 2H2O\}\n% edited\n::::\n/.test(text),  // centred is the default, so the sheet may leave it unsaid
           'saving puts the edit back over the block it came from, its fence and layout kept');
      eq((text.match(/::::latex/g) || []).length, 4, 'and no block was lost or doubled');

      /* ---------------- c2) the pencil inside an exercise ---------------- */
      console.log('c2) the pencil on a drawing inside an exercise, and inside a step');
      const INSIDE = `---
target: it
title: Drawings inside exercises
---

Intro.

:::exercise single-choice
prompt: |
  Which one?
  ::::latex
  \\textbf{PLAIN}
  ::::
- [x] a
- [ ] b
:::

:::exercise follow-up
prompt: Look.
::::exercise single-choice
prompt: |
  And this?
  :::::latex
  \\textbf{STEP}
  :::::
- [x] a
- [ ] b
::::
::::exercise true-false
prompt: Decide.
- yes => true
::::
:::
`;
      const inside = await api('POST', '/api/docs', {markdown: INSIDE});
      await page.goto(url(`/doc/${inside.meta.id}/edit`));
      await page.waitForSelector('#sheet figure.latex img', {timeout: 30000});
      await until(async () => (await page.locator('#sheet figure.latex[data-latex-src]').count()) === 2, 'both drawings are drawn');
      eq(JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('#sheet figure.latex[data-src-line]')].map(f => +f.dataset.srcLine))),
         '[10,22]', 'each drawing is told the line of the document it opens on, not a number counted from its prompt');
      const pencilOn = async (which, to) => {
        const figure = page.locator('#sheet figure.latex[data-latex-src]').nth(which);
        await figure.scrollIntoViewIfNeeded();
        // the pencil sits at the drawing's top right: a short drawing is hovered at its other corner
        await figure.hover({position: {x: 2, y: 2}});
        const pen = page.locator('button.rtl-edit-btn').filter({hasText: '✎'});
        await until(async () => (await pen.count()) && await pen.first().isVisible(), 'the pencil appears on the drawing');
        await pen.first().click();
        await page.waitForSelector('.latex-overlay .lx-src');
        await page.fill('.latex-overlay .lx-src', to);
        await page.click('.latex-overlay [data-x="ok"]');
        await page.waitForSelector('.latex-overlay', {state: 'detached'});
        await page.mouse.move(5, 5);
        await until(async () => !(await pen.first().isVisible()), 'the pencil goes away again', 3000);
      };
      await pencilOn(0, '\\textbf{EDITED-PLAIN}');
      eq(await source(), INSIDE.replace('\\textbf{PLAIN}', '\\textbf{EDITED-PLAIN}'),
         'the pencil on a drawing in a prompt rewrites that drawing alone, still indented under its field');
      await until(() => page.evaluate(() => !!document.querySelector('#sheet .ex-chain') && !document.querySelector('#sheet .ex-invalid')
        && document.querySelectorAll('#sheet figure.latex[data-latex-src]').length === 2), 'the preview draws the page again');
      await pencilOn(1, '\\textbf{EDITED-STEP}');
      eq(await source(), INSIDE.replace('\\textbf{PLAIN}', '\\textbf{EDITED-PLAIN}').replace('\\textbf{STEP}', '\\textbf{EDITED-STEP}'),
         'and on a drawing in a step: its five colons and its indent kept, every other line as it was');
      await until(() => page.evaluate(() => !!document.querySelector('#sheet .ex-chain') && !document.querySelector('#sheet .ex-invalid')),
                  'and the follow-up is still a follow-up');
      assert(true, 'the follow-up is still drawn as one after the edit');
      eq(errors.join(';'), '', 'no page error');
    }

    /* ---------------- d) Settings ---------------- */
    if (mode === 'parseh') {
      console.log('d) Settings -> LaTeX drawings');
      // nothing got by Parseh yet: the list the harness filled is emptied for this part, and written back after it
      const gotList = await Deno.readTextFile(info.texmf_list);
      await Deno.writeTextFile(info.texmf_list, JSON.stringify({format: 1, packages: {}}));
      const planReply = (names, licence = 'lppl1.3c', repository = 'available') => ({
        ok: true, can: true, tex: 'TeX Live test', why: '',
        packages: names.map((name, at) => ({name, size: repository === 'unreachable' ? null : 185000 + at * 1000,
          licence, here: 'missing', repository, can_get: repository === 'available',
          why: repository === 'unreachable' ? 'The TeX Live repository could not be reached.' : ''})),
      });
      const planCalls = [];
      let replyToPlan = async (route, packages) => { await route.fulfill({json: planReply(packages)}); };
      await page.route('**/settings/api/latex/package-plan', async route => {
        const packages = route.request().postDataJSON().packages;
        planCalls.push(packages);
        await replyToPlan(route, packages);
      });
      await page.goto(origin + '/settings/latex/');
      await page.waitForSelector('.lx .theme');
      const names = (await page.locator('.lx .theme h3').allTextContents()).map(s => s.split('(')[0].trim());
      eq(names.join(','), 'default,chemistry,drawing', 'a fresh Parseh has three themes');
      const themeActions = await page.locator('.lx [data-edit], .lx [data-rename], .lx [data-default], .lx [data-delete]')
        .evaluateAll(buttons => buttons.map(button => ({text: button.textContent.trim(), label: button.getAttribute('aria-label')})));
      assert(themeActions.length > 6 && themeActions.every(action => action.label
             && action.label.toLowerCase().includes('theme')),
             'repeated theme-card actions say which theme they affect: ' + JSON.stringify(themeActions));
      const compilerList = page.locator('.lx dl.tex-status');
      const compilerFacts = await compilerList.evaluate(list => ({
        rows: [...list.children].map(row => ({
          compiler: row.getAttribute('data-compiler'),
          term: row.querySelector('dt')?.textContent.trim(),
          state: row.querySelector('.st')?.textContent.trim(),
          version: row.querySelector('.compiler-version')?.textContent.trim() || '',
        })),
        table: !!list.querySelector('table'),
      }));
      assert(compilerFacts.rows.length === 3 && !compilerFacts.table
             && compilerFacts.rows.every(row => row.term === row.compiler && row.state),
             'compiler facts are a semantic status list, not a headerless table: ' + JSON.stringify(compilerFacts));
      const xetex = compilerFacts.rows.find(row => row.compiler === 'xelatex');
      const pdftex = compilerFacts.rows.find(row => row.compiler === 'pdflatex');
      const luatex = compilerFacts.rows.find(row => row.compiler === 'lualatex');
      assert(xetex?.state === '✓ Available' && xetex.version === 'XeTeX test 2026'
             && pdftex?.state === '— Not on this computer' && !pdftex.version
             && luatex?.state === '✓ Available' && /LuaHBTeX/.test(luatex.version),
             'available and unavailable compilers say their status in words, with a version when available');
      const desktopCompilerLayout = await compilerList.evaluate(list => [...list.children].map(row => {
        const term = row.querySelector('dt').getBoundingClientRect();
        const description = row.querySelector('dd').getBoundingClientRect();
        return {termLeft: term.left, descriptionLeft: description.left};
      }));
      assert(desktopCompilerLayout.every(row => row.descriptionLeft > row.termLeft),
             'at desktop width, compiler names and their facts form compact status rows');
      // L14: what a missing package costs is asked for when the page opens
      const panel = page.locator('.lx [data-package-panel]');
      const cardNeeds = await page.locator('.lx [data-install]').evaluateAll(buttons =>
        buttons.map(button => button.getAttribute('data-install').split(' ')));
      const everyNeed = [...new Set(cardNeeds.flat())];
      await until(async () => (await panel.locator('[data-package-get]').count()) >= everyNeed.length,
                  'every missing package is quoted without anyone asking');
      eq(planCalls.length, 1, 'opening the page asks once, in one batch, and asks nothing else');
      eq(JSON.stringify([...planCalls[0]].sort()), JSON.stringify([...everyNeed].sort()),
         'that ask names exactly the packages the saved themes lack');
      const readRows = () => panel.locator('[data-package-row]').evaluateAll(rows => rows.map(row => ({
        name: row.getAttribute('data-package-row'), why: row.children[1].textContent.trim(),
        cells: [...row.children].slice(2).map(cell => cell.textContent.trim().replace(/\s+/g, ' ')),
      })));
      const quoted = await readRows();
      assert(quoted.length === everyNeed.length && quoted.every(row => row.cells[0] === '○ Not installed'
             && /^\d+ kB$/.test(row.cells[1]) && row.cells[2] === 'lppl1.3c' && row.cells[3] === 'Get it'),
             'each row reads Not installed, its size, its licence, Get it: ' + JSON.stringify(quoted[0]));
      assert(quoted.every(row => /^for (the themes? |every theme$)/.test(row.why)), 'and says which theme needs it');
      assert(/^Get all — /.test(await panel.locator('[data-package-get-all]').textContent()),
             'Get all shows the total when more than one is ready');
      assert(/^\d+ packages ready to get\. Nothing has been downloaded\.$/.test(
             await panel.locator('[data-pkg-said]').textContent()), 'and it says that nothing has been downloaded');
      const rowText = async name => {
        const row = panel.locator(`[data-package-row="${name}"]`);
        return (await row.count()) ? (await row.textContent()).replace(/\s+/g, ' ') : '';
      };
      const reviewPackages = async viewport => {
        const review = page.locator('.lx [data-install]').first();
        eq((await review.textContent()).trim(), 'Review packages…',
           'the missing-package action truthfully says it reviews packages');
        assert(/^Review packages needed by /.test(await review.getAttribute('aria-label')),
               'each repeated Review packages action says which theme it belongs to');
        const expected = (await review.getAttribute('data-install')).split(' ').filter(
          (name, at, all) => name && all.indexOf(name) === at);
        assert(await panel.locator('[data-package-row]').count() >= expected.length,
               'missing theme packages are persistent rows');
        const asked = planCalls.length;
        await page.evaluate(() => window.scrollTo(0, 0));
        await review.focus();
        await page.keyboard.press('Enter');
        const get = panel.locator('[data-package-get]').first();
        await get.waitFor();
        assert(/Nothing has been downloaded/.test(await panel.locator('[data-pkg-said]').textContent()),
               'the package rows say clearly that reviewing changed nothing');
        eq(planCalls.length, asked, 'the review asks nothing again: the quotes are kept for the session');
        assert(await get.evaluate(button => button.classList.contains('go')),
               'Get it is the magenta action that starts an acquisition');
        const getName = await get.getAttribute('data-package-get');
        assert(expected.includes(getName) && (await get.getAttribute('aria-label')).startsWith(`Get ${getName}, `),
           'Get it says its package and quoted cost to a screen reader');
        const getNames = await panel.locator('[data-package-get]').evaluateAll(buttons =>
          buttons.map(button => button.getAttribute('data-package-get')));
        assert(expected.every(name => getNames.includes(name)),
           'each quoted package has its own Get it action in the packages table: ' + JSON.stringify(getNames));
        assert(await panel.locator('[data-package-get-all]').count() === 1,
               'Get all is available beside the individual package actions');
        const rowFacts = await panel.locator('[data-package-row]').evaluateAll(rows => rows.map(row => ({
          name: row.getAttribute('data-package-row'), scope: row.querySelector('th')?.getAttribute('scope'),
          state: row.querySelector('.pkg-state')?.textContent.trim(), action: row.querySelector('.pkg-action')?.textContent.trim(),
        })));
        assert(expected.every(name => rowFacts.some(row => row.name === name && row.scope === 'row'
               && /Not installed/.test(row.state) && /Get it/.test(row.action))),
               'each package has semantic table facts, state, and its local action: ' + JSON.stringify(rowFacts));
        await until(() => get.evaluate(button => document.activeElement === button),
                    `the first Get it receives keyboard focus after the ${viewport} review`);
        await until(() => panel.evaluate(el => {
          const r = el.getBoundingClientRect();
          return r.top <= innerHeight / 2 && r.bottom >= innerHeight / 2;
        }), `the ${viewport} package rows are centred in view`);
        for (const theme of ['light', 'sepia', 'dark']) {
          await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
          const color = await get.evaluate(button => {
            const swatch = document.createElement('i');
            swatch.style.color = 'var(--accent)';
            document.body.appendChild(swatch);
            const answer = {accent: getComputedStyle(swatch).color,
                            background: getComputedStyle(button).backgroundColor};
            swatch.remove();
            return answer;
          });
          eq(color.background, color.accent, `Get it uses the ${theme} magenta`);
          await shot(`package-review-${viewport}-${theme}`);
        }
        await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      };
      await reviewPackages('desktop');
      // an answer that comes late changes its own row and no other
      let releaseOlder;
      const older = new Promise(resolve => { releaseOlder = resolve; });
      replyToPlan = async (route, packages) => {
        if (packages[0] === 'older-quote') {
          await older;
          await route.fulfill({json: planReply(packages, 'older-licence')});
        } else await route.fulfill({json: planReply(packages, 'newer-licence')});
      };
      const packageName = page.locator('.lx [data-pkgname]');
      await packageName.fill('older-quote');
      await page.locator('.lx [data-package-plan]').click();
      await until(() => planCalls.some(call => call[0] === 'older-quote'), 'the first typed package reaches the planner');
      await packageName.fill('newer-quote');
      await page.locator('.lx [data-package-plan]').click();
      await until(async () => /newer-licence/.test(await rowText('newer-quote')), 'the later ask is answered first');
      assert(/Asking…/.test(await rowText('older-quote')) && !/older-licence/.test(await panel.textContent()),
             'the older one is still asking, and its row says so');
      eq(await packageName.inputValue(), 'newer-quote', 'what was typed in the box is still there');
      releaseOlder();
      await until(async () => /older-licence/.test(await rowText('older-quote')), 'the delayed answer arrives in its own row');
      assert(/newer-licence/.test(await rowText('newer-quote')) && !/newer-licence/.test(await rowText('older-quote')),
             'and neither answer landed on the other one\'s row');
      // a failed ask is said, in words, with a way to ask again
      replyToPlan = async route => { await route.abort('failed'); };
      await packageName.fill('failed-quote');
      await page.locator('.lx [data-package-plan]').click();
      const failedPlan = page.locator('.lx [data-pkg-said]');
      await until(async () => /Could not ask what failed-quote costs/.test(await failedPlan.textContent()),
                  'a network failure is said beside the package rows');
      assert(await failedPlan.evaluate(out => document.activeElement === out),
               'a failed quote leaves keyboard focus on its explanation');
      assert(/Could not ask/.test(await rowText('failed-quote'))
             && await panel.locator('[data-package-row="failed-quote"] [data-package-review]').count() === 1,
             'its row says so and offers Ask again');
      // the repository itself did not answer: the server's own words, and a manual retry
      replyToPlan = async (route, packages) => { await route.fulfill({json: planReply(packages, 'lppl1.3c', 'unreachable')}); };
      await panel.locator('[data-package-row="failed-quote"] [data-package-review]').click();
      await until(async () => /The TeX Live repository could not be reached/.test(await rowText('failed-quote')),
                  'an unreachable repository is said in plain words on the row');
      assert(await panel.locator('[data-package-row="failed-quote"] [data-package-get]').count() === 0
             && /Ask again/.test(await rowText('failed-quote')), 'with no Get it until it is asked again');
      replyToPlan = async (route, packages) => { await route.fulfill({json: planReply(packages)}); };
      await panel.locator('[data-package-row="failed-quote"] [data-package-review]').click();
      await until(async () => /Not installed/.test(await rowText('failed-quote')) && /Get it/.test(await rowText('failed-quote')),
                  'asked again when the repository answers, it is quoted');
      // the quotes are kept for the session: a page read again asks for nothing it knows
      const askedBefore = planCalls.length;
      await page.reload();
      await page.waitForSelector('.lx [data-package-get]');
      await sleep(400);
      eq(planCalls.length, askedBefore, 'a page read again in the same session asks the repository for nothing it already knows');
      // the keyboard stays with a package's row while it is got, stopped and removed:
      // the rows are kept and changed one by one, never rebuilt (found driving the first version)
      const pk = {jobs: {}, installed: {}, states: {}, available: {}};
      let polls = 0;
      const pkStatus = () => ({ok: true, ...pk});
      await page.route('**/settings/api/latex/package-get', route => {
        for (const n of route.request().postDataJSON().packages) {
          pk.jobs[n] = {name: n, state: 'queued', queued: true, running: false, done: 0, total: 0, say: 'waiting'};
        }
        route.fulfill({json: pkStatus()});
      });
      await page.route('**/settings/api/latex/package-status', route => {
        polls++;
        for (const n of Object.keys(pk.jobs)) {
          if (polls === 1) pk.jobs[n] = {name: n, state: 'running', running: true, done: 1, total: 3, say: 'downloading'};
          else {
            pk.jobs[n] = {name: n, state: 'installed', running: false, say: 'installed'};
            pk.installed[n] = {licence: 'lppl1.3c', size: 30000, at: 'now'};
            pk.available[n] = true;
            pk.states[n] = 'installed';
          }
        }
        route.fulfill({json: pkStatus()});
      });
      await page.route('**/settings/api/latex/state', async route => {
        const v = await (await route.fetch()).json();
        v.packages = pkStatus();
        for (const n of Object.keys(pk.installed)) for (const c of v.catalogue) if ((c.tl || []).includes(n)) v.files[c.file] = true;
        route.fulfill({json: v});
      });
      await page.route('**/settings/api/latex/package-remove', route => {
        const n = route.request().postDataJSON().package;
        for (const key of ['jobs', 'installed', 'available', 'states']) delete pk[key][n];
        route.fulfill({json: pkStatus()});
      });
      const mhchem = panel.locator('[data-package-row="mhchem"]');
      await mhchem.locator('[data-package-get]').click();
      await until(async () => (await mhchem.locator('[data-package-stop]').count()) === 1, 'a package being got shows Stop');
      await mhchem.locator('[data-package-stop]').focus();
      await until(async () => /Got/.test(await rowText('mhchem')), 'and is Got when it is done');
      assert(await page.evaluate(() => document.activeElement && document.activeElement.hasAttribute('data-remove')),
             'the keyboard followed the row from Stop to Remove… through every change of the table');
      await mhchem.locator('[data-remove]').press('Enter');
      assert(await page.evaluate(() => document.activeElement && document.activeElement.hasAttribute('data-remove-no')),
             'asking to remove puts the keyboard on Cancel, the harmless choice');
      await page.keyboard.press('Enter');
      assert(/Got/.test(await rowText('mhchem')) && await mhchem.locator('[data-remove-yes]').count() === 0, 'Cancel leaves it as it was');
      await mhchem.locator('[data-remove]').click();
      await mhchem.locator('[data-remove-yes]').click();
      await until(async () => /Not installed/.test(await rowText('mhchem')), 'Remove takes it out again, and it is offered again');
      for (const name of ['package-get', 'package-status', 'state', 'package-remove']) await page.unroute(`**/settings/api/latex/${name}`);
      await page.locator('.lx [data-edit="default"]').click();
      eq(await page.locator('.lx .grp h4').first().textContent(), 'Base packages',
         'the public package group does not name Formulae');
      assert(/The basics every drawing uses/.test(await page.locator('.lx .grp-why').first().textContent()),
             'Base packages says plainly what it is for');
      assert(await page.locator('.lx [data-save]').evaluate(button => button.classList.contains('go')),
             'Save the theme is its form\'s magenta commit');
      assert(await page.locator('.lx [data-draw-sample]').evaluate(button => button.classList.contains('plain'))
             && await page.locator('.lx [data-cancel]').evaluate(button => button.classList.contains('plain')),
             'drawing a sample and cancelling stay quiet reversible actions');
      const actions = await page.locator('.lx button').evaluateAll(buttons => buttons.map(button => ({
        text: button.textContent.trim(), className: button.className,
      })));
      assert(actions.length > 8 && actions.every(button => /\b(go|plain|parseh-btn)\b/.test(button.className)),
             'every LaTeX action has the shared affirmative, quiet, or existing link-style control: '
             + JSON.stringify(actions));
      const exportButton = page.locator('.lx .theme a.plain').first();
      await page.locator('.lx [data-rename="default"]').focus();
      await page.keyboard.press('Tab');
      assert(await exportButton.evaluate(link => document.activeElement === link
             && link.matches(':focus-visible') && getComputedStyle(link).outlineWidth === '2px'),
             'Export is one of the quiet actions and has the shared visible keyboard focus');
      // L13: not the top bar's chip -- the very look of Rename, in every theme
      for (const theme of ['light', 'sepia', 'dark']) {
        const looks = await page.evaluate(theme => {
          document.documentElement.dataset.theme = theme;
          const look = el => {
            const c = getComputedStyle(el), r = el.getBoundingClientRect();
            return {tag: el.tagName, size: c.fontSize, weight: c.fontWeight, color: c.color, background: c.backgroundColor,
                    border: c.borderTopColor + ' ' + c.borderTopWidth, radius: c.borderTopLeftRadius,
                    padding: c.paddingTop + ' ' + c.paddingRight, height: Math.round(r.height), decoration: c.textDecorationLine};
          };
          const link = document.querySelector('.lx .theme a.plain'), peer = document.querySelector('.lx [data-rename]');
          return {link: look(link), peer: look(peer)};
        }, theme);
        const {tag: t1, ...linkLook} = looks.link, {tag: t2, ...peerLook} = looks.peer;
        eq(JSON.stringify(linkLook), JSON.stringify(peerLook), `Export looks exactly like Rename in ${theme}`);
        eq(looks.link.decoration, 'none', `and is not underlined in ${theme}`);
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      const importButton = page.locator('.lx [data-import-open]');
      eq(await importButton.evaluate(button => button.tagName), 'BUTTON',
         'Import a theme is a keyboard-focusable button, not a file-input label');
      await importButton.focus();
      assert(await page.evaluate(() => document.activeElement.matches('.lx [data-import-open]')),
             'Import a theme receives keyboard focus');
      for (const theme of ['light', 'sepia', 'dark']) {
        const colors = await page.evaluate(theme => {
          document.documentElement.dataset.theme = theme;
          const swatch = document.createElement('i');
          swatch.style.color = 'var(--accent)';
          document.body.appendChild(swatch);
          const want = getComputedStyle(swatch).color;
          const got = [...document.querySelectorAll('.lx [data-pkg], .lx input[name="lx-comp"]')]
            .map(input => getComputedStyle(input).accentColor);
          const save = getComputedStyle(document.querySelector('.lx [data-save]')).backgroundColor;
          swatch.remove();
          return {want, got, save};
        }, theme);
        assert(colors.got.length > 1 && colors.got.every(color => color === colors.want),
               `package checks and compiler choices use the ${theme} accent (${JSON.stringify(colors)})`);
        eq(colors.save, colors.want, `Save the theme uses the ${theme} magenta`);
        await shot(`settings-${theme}`);
        await page.locator('.lx [data-save]').scrollIntoViewIfNeeded();
        await shot(`editor-actions-${theme}`);
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      // L14 in the editor: a box ticked is marked where it is ticked, before any Save
      const line = page.locator('.lx [data-edit-missing]');
      const lineText = async () => (await line.textContent()).replace(/\s+/g, ' ').trim();
      assert(!(await line.isHidden()) && /^Not installed here: .+ — see the table$/.test(await lineText()),
             'a theme being edited says, in one line, what this computer lacks of it: ' + await lineText());
      assert(!/circuitikz/.test(await lineText()), 'a package that is not ticked is not named');
      const gates = {};
      const gate = name => { let open; gates[name] = new Promise(resolve => { open = resolve; }); return open; };
      replyToPlan = async (route, packages) => {
        for (const name of packages) if (gates[name]) await gates[name];
        await route.fulfill({json: planReply(packages, 'gpl,lppl')});
      };
      const openCircuit = gate('circuitikz');
      const preamble = page.locator('.lx [data-preamble]');
      await preamble.fill('% my unsaved words');
      await page.locator('.lx [data-pkg="circuitikz"]').check();
      await until(async () => /circuitikz/.test(await lineText()),
                  'ticking a missing package names it in the line at once, with no save and no reload');
      await until(async () => /Asking…/.test(await rowText('circuitikz')), 'and its row is in the table, asking');
      assert(/for the theme being edited \(unsaved\)/.test(await rowText('circuitikz')), 'saying whom it is for');
      await preamble.focus();
      await page.keyboard.type(' and more');
      openCircuit();
      await until(async () => /Not installed/.test(await rowText('circuitikz')) && /Get it/.test(await rowText('circuitikz')),
                  'the quote arrives in its row');
      eq(await preamble.inputValue(), '% my unsaved words and more', 'a quote arriving leaves what was typed in the editor alone');
      assert(await preamble.evaluate(el => document.activeElement === el), 'and the keyboard where it was');
      await page.locator('.lx [data-pkg="circuitikz"]').scrollIntoViewIfNeeded();
      for (const theme of ['light', 'sepia', 'dark']) {
        await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
        await shot(`editor-missing-desktop-${theme}`);
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      await page.locator('.lx [data-pkg="circuitikz"]').uncheck();
      await until(async () => !/circuitikz/.test(await lineText()) && (await rowText('circuitikz')) === '',
                  'unticking takes it off the line and out of the table');
      const askedTicks = planCalls.length;
      await page.locator('.lx [data-pkg="circuitikz"]').check();
      await until(async () => /Not installed/.test(await rowText('circuitikz')) && /Get it/.test(await rowText('circuitikz')),
                  'ticked again, the kept quote answers at once');
      eq(planCalls.length, askedTicks, 'and is not asked for twice');
      // the keyboard in the table stays where it is while another row changes
      const openForest = gate('forest');
      await page.locator('.lx [data-pkg="forest"]').check();
      await until(async () => /Asking…/.test(await rowText('forest')), 'another box ticked: its row asks');
      const firstGet = panel.locator('[data-package-get]').first();
      const firstName = await firstGet.getAttribute('data-package-get');
      await firstGet.focus();
      openForest();
      await until(async () => /Not installed/.test(await rowText('forest')), 'and is quoted');
      assert(await page.evaluate(name => document.activeElement && document.activeElement.getAttribute('data-package-get') === name, firstName),
             'the keyboard stays on the Get it it was on while another row changed');
      const openTipa = gate('tipa');
      await page.locator('.lx [data-pkg="tipa"]').check();
      await until(async () => /Asking…/.test(await rowText('tipa')), 'a third box ticked: its row asks');
      await panel.locator('[data-package-get-all]').focus();
      openTipa();
      await until(async () => /Not installed/.test(await rowText('tipa')), 'and is quoted');
      assert(await page.evaluate(() => document.activeElement && document.activeElement.hasAttribute('data-package-get-all')),
             'Get all keeps the keyboard while its total changes');
      // a Save that leaves packages missing takes the person to the table
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.locator('.lx [data-save]').click();
      await until(async () => (await page.locator('.lx [data-package-panel].flash').count()) === 1,
                  'after a Save that leaves packages missing the table is flashed');
      eq(await panel.evaluate(el => getComputedStyle(el).animationName), 'lx-plan-flash', 'with its animation');
      await until(() => panel.evaluate(el => {
        const r = el.getBoundingClientRect();
        return r.top <= innerHeight / 2 && r.bottom >= innerHeight / 2;
      }), 'and scrolled to');
      assert(/^Saved the theme default\. Not installed here: /.test(await panel.locator('[data-pkg-said]').textContent()),
             'and it says what was saved and what is still missing');
      assert(await page.locator('.lx section.edit').count() === 0, 'the editor is closed by the Save');
      await page.emulateMedia({reducedMotion: 'reduce'});
      await page.locator('.lx [data-install]').first().click();
      eq(await panel.evaluate(el => getComputedStyle(el).animationName), 'none', 'a person who asked for reduced motion gets no flash');
      await page.emulateMedia({reducedMotion: null});
      assert(await page.locator('.lx [data-save-limit]').evaluate(button => button.classList.contains('go')),
             'Save is the magenta commit for the time-limit form');
      // L15: cleaning the cache shows that it is working
      let openForget, forgetCalls = 0, stateCalls = 0, forgetReply = {ok: true, drawings: 3, bytes: 4096, forgotten: 3, kept: {drawings: 0, bytes: 0}};
      const forgetHeld = new Promise(resolve => { openForget = resolve; });
      page.on('request', request => { if (/\/latex\/state$/.test(request.url())) stateCalls++; });
      await page.route('**/settings/api/latex/forget', async route => {
        forgetCalls++;
        await forgetHeld;
        await route.fulfill({json: forgetReply});
      });
      const forgetButton = page.locator('.lx [data-forget]'), bar = page.locator('.lx [data-forget-bar]');
      const forgetSaid = page.locator('.lx [data-forget-said]');
      await forgetButton.scrollIntoViewIfNeeded();
      assert(await bar.isHidden(), 'no bar while nothing is being done');
      await forgetButton.click();
      await until(() => forgetButton.isDisabled(), 'the button is disabled while the cleanup works');
      assert(await bar.isVisible() && (await bar.getAttribute('role')) === 'progressbar', 'a bar shows that it is working');
      eq(await bar.locator('i').evaluate(el => getComputedStyle(el).animationName), 'lx-slide',
         'the loose bar Updating Parseh uses, moving');
      eq((await forgetSaid.textContent()).trim(), 'Looking through every document, deck and note…', 'and it says what it is doing');
      await forgetButton.click({force: true, timeout: 1000}).catch(() => {});
      await sleep(150);
      eq(forgetCalls, 1, 'pressing it again does not start a second scan');
      const stateBefore = stateCalls;
      for (const theme of ['light', 'sepia', 'dark']) {
        await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
        await forgetButton.scrollIntoViewIfNeeded();
        if (SHOTS) await page.locator('.lx section').last().screenshot({path: `${SHOTS}/latex-${mode}-forgetting-desktop-${theme}.png`});
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      openForget();
      await until(async () => /^3 drawings forgotten, 4 kB freed\.$/.test((await forgetSaid.textContent()).trim()),
                  'when it is done it says how many drawings went, and what that freed');
      assert(await bar.isHidden() && !(await forgetButton.isDisabled()), 'the bar goes and the button is ready again');
      assert(stateCalls > stateBefore, 'and the count of the drawings kept was read again, not left as it was');
      await page.unroute('**/settings/api/latex/forget');
      await page.route('**/settings/api/latex/forget', route => route.fulfill({json: {ok: false, error: 'The library could not be read.'}}));
      await forgetButton.click();
      await until(async () => /^The library could not be read\.$/.test((await forgetSaid.textContent()).trim()),
                  'a refusal is said in the words the server gave');
      assert(await forgetSaid.evaluate(el => el.classList.contains('bad')) && !(await forgetButton.isDisabled()) && await bar.isHidden(),
             'as a failure, with the button ready and no bar');
      await page.unroute('**/settings/api/latex/forget');
      await page.route('**/settings/api/latex/forget', route => route.fulfill({json: {ok: true, drawings: 0, bytes: 0, forgotten: 0, kept: {drawings: 0, bytes: 0}}}));
      await forgetButton.click();
      await until(async () => /^Nothing to forget/.test((await forgetSaid.textContent()).trim()), 'nothing forgotten is said too');
      await page.unroute('**/settings/api/latex/forget');
      // a stopped server answers nothing: the cleanup gives up by itself
      const late = await context.newPage();
      await late.clock.install();
      await late.route('**/settings/api/latex/forget', () => new Promise(() => {}));
      await late.goto(origin + '/settings/latex/');
      await late.waitForSelector('.lx [data-forget]');
      await late.locator('.lx [data-forget]').click();
      await until(async () => await late.locator('.lx [data-forget]').isDisabled(), 'the cleanup of a silent server starts');
      await late.clock.fastForward(61000);
      await until(async () => /did not answer/.test(await late.locator('.lx [data-forget-said]').textContent()),
                  'a server that answers nothing is given up on, in words');
      assert(!(await late.locator('.lx [data-forget]').isDisabled()) && await late.locator('.lx [data-forget-bar]').isHidden(),
             'and the button is ready again');
      await late.close();
      for (const theme of ['light', 'sepia', 'dark']) {
        await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
        await compilerList.scrollIntoViewIfNeeded();
        await shot(`compiler-status-desktop-${theme}`);
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      assert(await page.locator('.parseh-doors a, nav a, .doors a').filter({hasText: 'LaTeX drawings'}).count() > 0
             || (await page.content()).includes('LaTeX drawings'), 'the bar of the doors names this page');
      await shot('settings');
      await page.setViewportSize({width: 390, height: 844});
      await sleep(300);
      await reviewPackages('phone');
      const phonePackageLayout = await page.locator('.lx [data-package-row]').first().evaluate(row => {
        const cells = [...row.querySelectorAll('th,td')].map(cell => getComputedStyle(cell).display);
        const action = row.querySelector('button')?.getBoundingClientRect();
        return {display: getComputedStyle(row).display, cells, actionHeight: action ? Math.round(action.height) : 0};
      });
      assert(phonePackageLayout.display === 'block' && phonePackageLayout.cells.slice(0, 5).every(display => display === 'grid')
             && phonePackageLayout.cells[5] === 'block'
             && phonePackageLayout.actionHeight >= 44,
             'at phone width, each package table row becomes a labelled action card: ' + JSON.stringify(phonePackageLayout));
      for (const theme of ['light', 'sepia', 'dark']) {
        const layout = await page.evaluate(theme => {
          document.documentElement.dataset.theme = theme;
          return {
            over: document.documentElement.scrollWidth - window.innerWidth,
            compilers: (() => {
              const list = document.querySelector('.lx .tex-status');
              return {over: list ? list.scrollWidth - list.clientWidth : Infinity,
                      rows: list ? [...list.children].map(row => {
                        const term = row.querySelector('dt').getBoundingClientRect();
                        const description = row.querySelector('dd').getBoundingClientRect();
                        return {width: row.getBoundingClientRect().width, stacked: description.top > term.bottom};
                      }) : []};
            })(),
            touch: [...document.querySelectorAll('.lx button.go, .lx button.plain, .lx a.plain')]
              .filter(control => !!(control.offsetWidth || control.offsetHeight))
              .map(control => ({text: control.textContent.trim(), height: Math.round(control.getBoundingClientRect().height)})),
          };
        }, theme);
        assert(layout.over <= 1, `at 390 px in ${theme}, the page never scrolls sideways (${layout.over} px over)`);
        assert(layout.touch.length > 0 && layout.touch.every(control => control.height >= 44),
               `at 390 px in ${theme}, each visible action has a 44 px touch target (${JSON.stringify(layout.touch)})`);
        assert(layout.compilers.over <= 1 && layout.compilers.rows.length === 3
               && layout.compilers.rows.every(row => row.stacked),
               `at 390 px in ${theme}, each compiler fact fits its status list (${JSON.stringify(layout.compilers)})`);
        await page.locator('.lx .tex-status').scrollIntoViewIfNeeded();
        await shot(`compiler-status-phone-${theme}`);
        await shot(`settings-phone-${theme}`);
      }
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      await shot('settings-phone');
      await Deno.writeTextFile(info.texmf_list, gotList);
    }

    /* ---------------- e) the drawings kept, after everything that held one is deleted ---------------- */
    if (mode === 'parseh' && !settingsOnly) {
      console.log('e) Settings -> the drawings kept: delete everything that held one, then forget');
      await page.setViewportSize({width: 1280, height: 900});
      await page.unroute('**/settings/api/latex/package-plan');
      const send = async (method, path, body) => {
        const r = await fetch(origin + path, {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                              body: body ? JSON.stringify(body) : undefined});
        return r.json();
      };
      const SAVED = `---\ntarget: it\n---\n# Uno\n\n::::latex chemistry\n\\ce{H2O}\n::::\n\nUna [\\ce{CO2}]{latex chemistry} riga.\n`;
      const EXERCISE = ':::exercise single-choice\nprompt: |\n  Pick.\n  ::::latex chemistry\n  \\ce{NaCl}\n  ::::\n'
        + '- [x] [\\ce{Na}]{latex chemistry}\n- [ ] [\\ce{Cl}]{latex chemistry}\n:::\n';
      const doc2 = (await send('POST', '/studio/api/docs', {markdown: SAVED})).meta.id;
      await (await fetch(url(`/doc/${doc2}`))).text();
      // the page opens without waiting for its drawings; its script has them made, as this does
      for (let left = 1, round = 0; left && round < 10; round++) {
        left = (await send('POST', `/studio/api/docs/${doc2}/drawings`, {batch: 8})).left;
      }
      const deck =(await send('POST', '/exercises/api/decks', {name: 'Geometry', lang: 'it'})).deck;
      const item = (await send('POST', `/exercises/api/decks/${deck.folder}/${deck.slug}/items`, {markdown: EXERCISE})).item;
      await (await fetch(`${origin}/exercises/api/decks/${deck.folder}/${deck.slug}/items/${item.id}`)).text();
      await page.goto(origin + '/settings/latex/');
      await page.waitForSelector('.lx [data-kept]');
      const keptNow = async () => (await page.locator('.lx [data-kept]').textContent()).trim();
      const said = () => page.locator('.lx [data-forget-said]');
      // what the pencil's edit above left unnamed goes first, so that what follows is only this section's
      await page.locator('.lx [data-forget]').click();
      await until(async () => /(forgotten|Nothing to forget)/.test(await said().textContent()), 'the drawings the earlier checks left unnamed are let go');
      const before = +(await keptNow()).match(/^(\d+) saved drawings?/)[1];
      assert(before >= 4, `a document and an exercise made ${before} saved drawings, a block and its marks each`);
      await page.locator('.lx [data-forget]').click();
      await until(async () => /^Nothing to forget/.test((await said().textContent()).trim()),
                  'while a document and a deck still name them, nothing is forgotten');
      eq(+(await keptNow()).match(/^(\d+) saved/)[1], before, 'and every drawing is still kept');
      eq((await send('DELETE', `/studio/api/docs/${doc2}`)).ok, true, 'the document is deleted');
      eq((await send('DELETE', `/exercises/api/decks/${deck.folder}/${deck.slug}`)).ok, true, 'the deck is deleted');
      const trash = info.library.replace(/library$/, 'exercises/.trash');
      assert((await Deno.stat(trash)).isDirectory, 'a deck is only moved to its trash, where its exercises are still read');
      await page.reload();
      await page.waitForSelector('.lx [data-kept]');
      eq(+(await keptNow()).match(/^(\d+) saved/)[1], before, 'the page still counts what is kept');
      await page.locator('.lx [data-forget]').click();
      await until(async () => (await keptNow()) === '0 saved drawings, 0 kB', 'one press, and the page counts none', 30000);
      eq((await page.locator('.lx [data-forget-said]').textContent()).trim().replace(/, .*/, ''), `${before} drawings forgotten`,
         'and says how many went');
      const leftovers = [];
      const walk = async dir => {
        for await (const entry of Deno.readDir(dir)) {
          if (entry.isDirectory) { if (entry.name !== '.preview') await walk(`${dir}/${entry.name}`); }
          else if (entry.name !== 'owners.json') leftovers.push(`${dir}/${entry.name}`);
        }
      };
      await walk(info.latex_drawn);
      eq(leftovers.join(', '), '', 'and not one file of a drawing is left on the disk');
      await shot('forgotten');
    }
    eq(errors.join(' | '), '', 'no script error on any page');
  } finally {
    await browser.close();
    proc.kill('SIGTERM');
    await proc.status.catch(() => {});
  }
  return passed;
}

// f) A COMPUTER WHOSE TeX HAS EVERY PACKAGE, AND A PARSEH THAT HAS GOT NONE
// (the owner, 2026-09-28): a theme's packages beyond the base are Parseh's own,
// so they are missing whatever the computer's TeX holds, and a drawing that
// needs one is refused with the way to get it; the base comes with the
// computer's TeX and is listed with nothing to get or remove.  Real TeX, the
// real kpsewhich; only the repository's quote is answered here.
async function ownPackages() {
  console.log('\n== f) a full TeX, and Parseh\'s own packages not got ==');
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', 'parseh', '--latex-own-missing'],
                                         cwd: root, stdout: 'piped', stderr: 'piped'}).spawn();
  (async () => { const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader(); for (;;) { if ((await r.read()).done) break; } })();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error('harness (own) exited before READY:\n' + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { if ((await reader.read()).done) break; } })();
  const origin = `http://127.0.0.1:${info.port}`;
  const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/settings/api/latex/package-plan', async route => {
      const names = route.request().postDataJSON().packages;
      await route.fulfill({json: {ok: true, can: true, tex: 'TeX Live test', why: '',
        packages: names.map((name, at) => ({name, size: 20000 + at * 1000, licence: 'lppl1.3c', here: 'missing',
                                             repository: 'available', can_get: true, why: ''}))}});
    });
    await page.goto(origin + '/settings/latex/');
    await page.waitForSelector('[data-pkg-rows] [data-package-get]');
    const table = await page.evaluate(() => ({
      own: [...document.querySelectorAll('[data-pkg-rows] tr[data-package-row]')].map(tr => tr.dataset.packageRow),
      ownGet: [...document.querySelectorAll('[data-pkg-rows] tr[data-package-row]')].every(tr => tr.querySelector('[data-package-get]')),
      sysShown: !document.querySelector('[data-pkg-sys-head]').hidden,
      sys: [...document.querySelectorAll('[data-pkg-sys] tr[data-package-row]')].map(tr => tr.dataset.packageRow),
      sysSaid: [...document.querySelectorAll('[data-pkg-sys] .pkg-state')].map(td => td.textContent.trim()),
      sysButtons: document.querySelectorAll('[data-pkg-sys] button').length,
      cards: Object.fromEntries([...document.querySelectorAll('[data-theme-missing]')].map(d => [d.dataset.themeMissing, d.textContent.trim()])),
    }));
    eq(table.own.join(','), 'chemfig,chemgreek,mhchem,pgf,pgfplots',
       'with every package on the computer, a theme\'s own packages are still missing: only Parseh\'s copy counts');
    assert(table.ownGet, 'each of them offers Get it');
    assert(table.sysShown && ['amsmath', 'standalone', 'xcolor'].every(n => table.sys.includes(n))
           && !table.sys.some(n => table.own.includes(n)),
           'the base is listed apart, as the computer\'s: ' + table.sys.join(', '));
    assert(table.sysSaid.every(t => /With this computer's TeX/.test(t)) && table.sysButtons === 0,
           'and says so, with nothing to get or remove');
    eq(table.cards.default, '', 'the default theme lacks nothing');
    assert(/Not installed here: mhchem, chemfig/.test(table.cards.chemistry) && /Not installed here: tikz, pgfplots/.test(table.cards.drawing),
           'the theme cards say what is not got: ' + JSON.stringify(table.cards));
    for (const [w, h] of [[1280, 900], [390, 844]]) {
      await page.setViewportSize({width: w, height: h});
      for (const theme of ['light', 'sepia', 'dark']) {
        await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
        await page.locator('[data-pkg-sys-head]').scrollIntoViewIfNeeded();
        if (SHOTS) await page.screenshot({path: `${SHOTS}/latex-own-table-${w}-${theme}.png`});
      }
      // Edit takes the page to the theme being edited, and says it is there
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.click('[data-edit="chemistry"]');
      await page.waitForFunction(() => { const e = document.querySelector('section.edit');
        if (!e) return false; const r = e.getBoundingClientRect(); return r.top >= -2 && r.top < 40; }, null, {timeout: 5000});
      eq(await page.evaluate(() => document.activeElement.textContent), 'The theme chemistry',
         `Edit brings the theme's editor into view and gives it the keyboard (${w} px)`);
      if (SHOTS) await page.screenshot({path: `${SHOTS}/latex-own-edit-${w}.png`});
      await page.click('[data-cancel]');
    }
    // a drawing that needs one of them is refused, and says how to mend it
    const doc = await (await fetch(origin + '/studio/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: '---\ntitle: Own\nlang: en\ntarget: it\n---\n\n::::latex chemistry\n\\ce{H2O}\n::::\n\n::::latex\n$x^2$\n::::\n'})})).json();
    await page.setViewportSize({width: 1280, height: 900});
    await page.goto(origin + `/studio/doc/${doc.meta.id}`);
    await page.waitForSelector('#sheet .latex-fail', {timeout: 60000});
    await page.waitForSelector('#sheet figure.latex img', {timeout: 60000});
    const refused = await page.evaluate(() => ({said: document.querySelector('#sheet .latex-fail .latex-said').textContent,
      link: [...document.querySelectorAll('#sheet .latex-fail .latex-fix a')].map(a => [a.textContent, a.getAttribute('href')])}));
    assert(/mhchem and chemfig are not among Parseh's own TeX packages yet/.test(refused.said) && /"chemistry"/.test(refused.said),
           'a chemistry drawing is refused, in words: ' + refused.said);
    assert(refused.link.length === 1 && refused.link[0][0] === 'Get mhchem, chemgreek, chemfig…'
           && /\?install=mhchem,chemgreek,chemfig$/.test(refused.link[0][1]),
           'with the way to get it: ' + JSON.stringify(refused.link));
    assert(await page.locator('#sheet figure.latex img').count() === 1, 'while a drawing of the default theme, the base alone, is drawn');
    if (SHOTS) await page.screenshot({path: `${SHOTS}/latex-own-refused.png`});
    // the link opens the table on what it asked for
    await page.goto(origin + refused.link[0][1]);
    await page.waitForFunction(() => /Not installed/.test((document.querySelector('[data-package-row="mhchem"] .pkg-state') || {}).textContent || ''));
    assert(true, 'the link opens Settings on the rows it names');
    eq(errors.join(' | '), '', 'no script error');
  } finally {
    await browser.close();
    proc.kill('SIGTERM');
    await proc.status.catch(() => {});
  }
}

let total = 0;
for (const mode of modes) total += await suite(mode);
await ownPackages();
console.log(`LaTeX drawings passed (${modes.join(' + ')}: ${passed} checks)`);
