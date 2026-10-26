// SPDX-License-Identifier: GPL-3.0-or-later
// THE .tex THAT WAS COMPILED AND THE WHOLE LOG, on request (a0.5.4, the owner, 2026-10-25): "it should be possible to
// see by clicking some button what the actual .tex document that it's tried when one tries to compile a latex
// drawing, this especially should be true for 'draw the sample' in /settings/latex" -- and the log in detail when
// there is an error.  Driven where a person meets them, on Parseh's own handler (the studio at /studio, Settings at
// /settings/) with the TeX this computer has:
//   a) Settings -> LaTeX drawings, the sample of a theme: on a SUCCESS the .tex (the preamble and the block, as the
//      server kept it) and the log, each a <details> with a Copy of its own, under the picture and over the whole
//      preamble, which stays; on a FAILURE the same, the log with the lines the words were made from marked, scrolled
//      to the first, and the Copy giving the log exactly as the server kept it
//   b) the studio: a block that cannot be drawn is a frame with the two buttons, each opening a frame on top with the
//      text (the very document, the whole log, its marked lines in view), a Copy, and Esc to close; a block that
//      never reached TeX (a theme this Parseh has not got) has neither
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/latex_views.mjs     SHOTS=<dir> keeps screenshots
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => assert(a === b, `${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 30000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(80);
  }
}
const hasTeX = await new Deno.Command('xelatex', {args: ['--version'], stdout: 'null', stderr: 'null'}).output()
  .then(r => r.success, () => false);
if (!hasTeX) {
  console.log('SKIP: no xelatex on this computer -- the drawings are made by TeX (tests/latex_views.mjs)');
  Deno.exit(0);
}
if (SHOTS) await Deno.mkdir(SHOTS, {recursive: true});

const DOC = `---
target: it
---
# Disegni

Un blocco rotto:

::::latex
\\undefinedcommandxyz
::::

Un blocco con un tema che non esiste:

::::latex nosuchtheme
x
::::
`;

const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', 'parseh'], cwd: root,
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
  if (done) throw Error('harness exited before READY:\n' + buf + log.join(''));
  buf += value;
  const m = buf.match(/READY (\{.*\})\n/);
  if (m) info = JSON.parse(m[1]);
}
(async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
const origin = `http://127.0.0.1:${info.port}`, studio = origin + info.studio;

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
let failure = null;
try {
  const context = await browser.newContext({viewport: {width: 1280, height: 900}, permissions: ['clipboard-read', 'clipboard-write']});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const shot = async name => { if (SHOTS) await page.screenshot({path: `${SHOTS}/latex-views-${name}.png`}); };
  const clip = () => page.evaluate(() => navigator.clipboard.readText());

  /* ---------------- a) the door's sample ---------------- */
  console.log('a) Settings -> LaTeX drawings: Draw the sample');
  // what the server answers to a sample, to compare the Copy against
  const answers = [];
  page.on('response', async r => {
    if (/\/api\/latex\/sample$/.test(r.url())) { try { answers.push(await r.json()); } catch (_) {} }
  });
  await page.goto(origin + '/settings/latex/');
  await page.waitForSelector('.lx [data-edit="default"]');
  await page.locator('.lx [data-edit="default"]').click();
  await page.waitForSelector('.lx [data-draw-sample]');
  // the default sample is a chemical formula, which the default theme (the base packages) does not know: draw one it does
  await page.locator('.lx [data-sample]').fill('\\textbf{ciao} $E = mc^2$');
  await page.locator('.lx [data-draw-sample]').click();
  await page.waitForSelector('.lx [data-sample-out] img.sample', {timeout: 60000});
  eq(await page.locator('.lx [data-edit-said]').textContent(), 'Drawn.', 'the sample is drawn');
  // the views are under the picture, the preamble under them: one under the other
  const order = await page.evaluate(() => [...document.querySelectorAll('[data-sample-out] > *')].map(e =>
    e.tagName === 'IMG' ? 'picture' : (e.querySelector('summary') ? e.querySelector('summary').textContent : e.tagName)));
  eq(JSON.stringify(order), JSON.stringify(['picture', 'The .tex that was compiled', 'The whole log', 'The whole preamble']),
     'under the picture: the .tex that was compiled, the whole log, and the whole preamble that was always there');
  const a1 = answers[answers.length - 1];
  assert(a1 && typeof a1.tex === 'string' && typeof a1.log === 'string', 'the server answered the sample with the document and the log it kept');
  assert(a1.tex.startsWith(a1.preamble) && a1.tex.endsWith('\\end{document}\n') && a1.tex.includes('\\begin{document}\n'),
         'the .tex is the preamble, \\begin{document}, the sample, \\end{document}: the very file TeX was given');
  await page.locator('details[data-tex-view] > summary').click();
  const texShown = await page.locator('pre[data-tex-pre]').textContent();
  eq(texShown, a1.tex, 'opened, it shows that document byte for byte');
  await page.locator('[data-copy="tex"]').click();
  eq(await clip(), a1.tex, 'its Copy puts exactly that on the clipboard');
  eq(await page.locator('[data-copy="tex"]').textContent(), 'Copied', 'and says so');
  await page.locator('details[data-log-view] > summary').click();
  assert((await page.locator('pre[data-log-pre] .ln').count()) > 20 && /XeTeX|pdfTeX|LuaTeX|LuaHBTeX/.test(await page.locator('pre[data-log-pre]').textContent()),
         'the log of a drawing that was made is there as well, whole');
  eq(await page.locator('pre[data-log-pre] .ln.mark').count(), 0, 'and has no marked line: nothing was wrong');
  await page.locator('[data-copy="log"]').click();
  eq(await clip(), a1.log, 'its Copy puts the log exactly as the server kept it on the clipboard');
  await shot('door-success');

  // a mistake: the words, and under them what they were made from
  await page.locator('.lx [data-sample]').fill('\\undefinedcommandxyz');
  await page.locator('.lx [data-draw-sample]').click();
  await until(async () => /not a command LaTeX knows/.test(await page.locator('.lx [data-edit-said]').textContent()), 'the mistake is said in words');
  const a2 = answers[answers.length - 1];
  assert(a2.marks.length >= 2 && a2.log.split('\n').slice(a2.marks[0] - 1)[0].includes('Undefined control sequence'),
         'the answer says which lines of the log the words were read from');
  assert(a2.tex.includes('\\undefinedcommandxyz\n\\end{document}'), 'the .tex that was compiled holds the mistake, on a failure too');
  await page.locator('details[data-tex-view] > summary').click();
  eq(await page.locator('pre[data-tex-pre]').textContent(), a2.tex, 'and shows it');
  await page.locator('details[data-log-view] > summary').click();
  const marked = await page.locator('pre[data-log-pre] .ln.mark').allTextContents();
  assert(marked.length === a2.marks.length && /Undefined control sequence/.test(marked[0]), 'the lines the words were read from are marked in the log: ' + JSON.stringify(marked.map(x => x.slice(0, 40))));
  const scrolled = await page.evaluate(() => {
    const pre = document.querySelector('pre[data-log-pre]'), first = pre.querySelector('.mark');
    const p = pre.getBoundingClientRect(), f = first.getBoundingClientRect();
    return {top: Math.round(pre.scrollTop), inside: f.top >= p.top - 1 && f.bottom <= p.bottom + 1, scrolls: pre.scrollHeight > pre.clientHeight};
  });
  assert(scrolled.inside, 'the log opens scrolled to the first marked line: ' + JSON.stringify(scrolled));
  await shot('door-failure');
  await page.locator('[data-copy="log"]').click();
  eq(await clip(), a2.log, 'the Copy of a failure\'s log is the log as kept');
  await page.locator('[data-copy="tex"]').click();
  eq(await clip(), a2.tex, 'and the Copy of its .tex the document as kept');
  eq(await page.locator('.lx [data-sample-out] details summary').count(), 3, 'both views and the preamble stay, one under the other');

  /* ---------------- b) the studio's frame ---------------- */
  console.log('b) the studio: a block that cannot be drawn');
  const made = await (await fetch(studio + '/api/docs', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                          body: JSON.stringify({markdown: DOC})})).json();
  await page.goto(`${studio}/doc/${made.meta.id}/edit`);
  await page.waitForSelector('#sheet .latex-fail .latex-said', {timeout: 60000});
  const frames = await page.locator('#sheet .latex-fail').count();
  eq(frames, 2, 'two blocks are not drawn');
  const buttons = await page.evaluate(() => [...document.querySelectorAll('#sheet .latex-fail')].map(f =>
    [...f.querySelectorAll('.latex-views button')].map(b => b.textContent)));
  eq(JSON.stringify(buttons[0]), JSON.stringify(['The .tex that was compiled', 'The whole log']), 'the block that went to TeX has the two buttons');
  eq(JSON.stringify(buttons[1]), JSON.stringify([]), 'a block whose theme this Parseh does not have went nowhere: nothing to show');
  const first = page.locator('#sheet .latex-fail').first();
  await first.locator('[data-latex-view="tex"]').click();
  await page.waitForSelector('.latex-view-modal .latex-view-ln');
  const doc = await page.locator('.latex-view-pre').evaluate(p => [...p.querySelectorAll('.latex-view-ln')].map(l => l.textContent).join('\n'));
  assert(doc.startsWith('\\documentclass[border=2pt]{standalone}') && doc.includes('\\begin{document}\n\\undefinedcommandxyz\n\\end{document}'),
         'the frame on top shows the document TeX was given');
  await shot('studio-tex');
  await page.locator('.latex-view-modal [data-x="copy"]').click();
  eq((await clip()).trimEnd(), doc.trimEnd(), 'its Copy puts it on the clipboard');
  await page.keyboard.press('Escape');
  await page.waitForSelector('.latex-view-modal', {state: 'detached'});
  assert(true, 'Esc closes the frame');
  await first.locator('[data-latex-view="log"]').click();
  await page.waitForSelector('.latex-view-modal .latex-view-ln.mark');
  const lg = await page.evaluate(() => {
    const pre = document.querySelector('.latex-view-pre'), marks = [...pre.querySelectorAll('.mark')], p = pre.getBoundingClientRect();
    const f = marks[0].getBoundingClientRect();
    return {n: marks.length, first: marks[0].textContent, inside: f.top >= p.top - 1 && f.bottom <= p.bottom + 1, lines: pre.querySelectorAll('.latex-view-ln').length};
  });
  assert(lg.n >= 2 && /Undefined control sequence/.test(lg.first) && lg.inside && lg.lines > 20,
         'the whole log, with the lines the words were made from marked and in view: ' + JSON.stringify(lg));
  await shot('studio-log');
  await page.locator('.latex-view-modal [data-x="close"]').click();
  await page.waitForSelector('.latex-view-modal', {state: 'detached'});
  assert(true, 'Close closes it too');
  // the exported page has none of it
  const exported = await (await fetch(`${studio}/download/${made.meta.id}/html`)).text();
  const flags = {html: exported.includes('<html'), text: exported.includes('Un blocco rotto'),
                 buttons: /<button[^>]*data-latex-view|class="latex-views"/.test(exported),
                 source: /<pre class="latex-code"|data-latex-src/.test(exported)};
  assert(flags.html && flags.text && !flags.buttons && !flags.source,
         'an exported page carries neither these buttons nor the block\'s LaTeX source: ' + JSON.stringify(flags));
  assert(errors.length === 0, 'no page error: ' + errors.join(' | '));
} catch (e) {
  failure = e;
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) {}
  await proc.status.catch(() => {});
}
if (failure) { console.log(failure.stack || failure.message || String(failure)); console.log(log.join('').slice(-1500)); Deno.exit(1); }
console.log(passed + ' checks passed');
