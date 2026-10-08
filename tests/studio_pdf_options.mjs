// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of a document's PDF options, driven where they are used --
// the reading page's topbar -- against the REAL routes (markdown/app/server.py)
// on a temporary library (tests/decks_harness.py, studio mode), with a REAL
// build (xelatex), so it needs TeX with extsizes:
//   a) on a desktop, "PDF options ▾" opens a menu that is on the screen, whose
//      print sizes and black-and-white box a click reaches; what is chosen is
//      kept for the document in this browser (exlex-pdf:<id>); Build PDF sends
//      it, and what comes back is built so -- the .tex a download gives is set
//      at that size in black and white, the build record says so, and the
//      badge shows "17 pt · B&W"; changing the options afterwards puts a badge
//      of its own beside it, saying the PDF was built with other options, and
//      a reload keeps both the choice and the badge; a browser that has chosen
//      nothing starts from what the PDF was built with, and so shows no badge
//   b) on a phone (390 and 320 px wide), the menu hangs from the topbar
//      entirely on the screen, every option in it reached by a tap, the page
//      never scrolls sideways, and the build badges are on the screen too
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/studio_pdf_options.mjs
//   SHOTS=<dir> saves the screenshots (the menu open, on a desktop and a phone)
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };

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

const DOC = `---
title: Printed exercises
lang: en
target: fa
---

A [coloured]{teal} word and a [hex]{#8E2B34} one.

:::exercise true-false
prompt: True or false?
- [پدر لیلا تکنولوژی را دوست دارد.]{tl} => false
- [لیلا و دوستانش منتظرِ فناوری جدید هستند.]{tl} => true
:::
`;

/* Where an element is drawn, and whether a tap on its middle reaches it
   (or its label, for a radio or a checkbox). */
const placed = el => el.evaluate(e => {
  const r = e.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const hit = document.elementFromPoint(x, y);
  const lab = e.closest('label');
  return {l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom),
          w: innerWidth, h: innerHeight,
          hit: !!hit && (hit === e || e.contains(hit) || (!!lab && lab.contains(hit)))};
});
const onScreen = p => p.hit && p.l >= 0 && p.r <= p.w && p.t >= 0 && p.b <= p.h;
const noSideways = page => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

const {proc, info} = await startHarness();
const B = `http://127.0.0.1:${info.port}`;
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN') || undefined, headless: true});
try {
  const made = await (await fetch(`${B}/api/docs`, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                     body: JSON.stringify({markdown: DOC})})).json();
  const id = (made.meta || made).id;
  assert(id, 'a document with exercises is made');

  // ------------------------------------------------------------------ a) desktop
  console.log('a) the PDF options on a desktop');
  const ctx = await browser.newContext({viewport: {width: 1280, height: 900}});
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`${B}/doc/${id}`);
  await page.waitForSelector('#sheet');
  // the LaTeX with what it needs to compile elsewhere is greyed out, like the .tex and the PDF, until a PDF has been built
  const texZip = page.locator('#dl-texzip');
  assert(await texZip.textContent() === 'LaTeX + media (.zip)', 'Download ▾ offers "LaTeX + media (.zip)" beside the .tex');
  assert((await texZip.getAttribute('class') || '').includes('disabled'), 'and it is greyed out while no PDF has been built');
  assert((await (await fetch(`${B}/download/${id}/texzip`)).json()).error.includes('build the PDF first'), 'and the route says why it has nothing to give');
  const summary = page.locator('#pdf-options > summary');
  assert(await summary.textContent() === 'PDF options ▾', 'the topbar has "PDF options ▾"');
  assert(onScreen(await placed(summary)), 'it is on the screen and a click reaches it');
  await summary.click();
  const menu = page.locator('#pdf-options .menu');
  assert(await menu.isVisible() && onScreen({...(await placed(menu)), hit: true}),
         'a click opens its menu, on the screen');
  const radio = v => page.locator(`input[name="pdf-size"][value="${v}"]`);
  assert(await radio(11).isChecked() && !(await page.locator('#ck-pdf-mono').isChecked()),
         'a document never built starts at Normal, in colour');
  for (const v of [11, 14, 17, 20])
    assert(onScreen(await placed(radio(v))), `the ${v} pt choice is reached by a click`);
  assert(onScreen(await placed(page.locator('#ck-pdf-mono'))), 'black and white is reached by a click');
  await page.locator('label', {has: radio(17)}).click();
  await page.locator('label', {has: page.locator('#ck-pdf-mono')}).click();
  assert(await menu.isVisible(), 'the menu stays open while its options are changed');
  const kept = await page.evaluate(k => localStorage.getItem(k), `exlex-pdf:${id}`);
  assert(kept === JSON.stringify({size: 17, mono: true}), `the choice is kept for this document (${kept})`);
  if (SHOTS) await page.screenshot({path: `${SHOTS}/pdf-options-desktop.png`});

  await page.locator('#btn-build').click();
  await page.waitForSelector('#buildinfo .badge.ok', {timeout: 300000});
  const badges = await page.locator('#buildinfo').textContent();
  assert(/PDF ✓ .*17 pt · B&W/.test(badges), `the badge says what the PDF was built with (${badges.trim()})`);
  assert(await page.locator('#pdf-options-stale').count() === 0, 'and, built with the options chosen, no other badge');
  const record = (await (await fetch(`${B}/api/docs/${id}`)).json()).meta.build;
  assert(record.status === 'ok' && record.size === 17 && record.mono === true,
         `the build record keeps the options (${JSON.stringify({size: record.size, mono: record.mono})})`);
  const tex = await (await fetch(`${B}/download/${id}/tex`)).text();
  assert(tex.includes('\\documentclass[17pt,a4paper]{extarticle}'), 'the .tex is set at 17 pt');
  assert(tex.includes('\\definecolor{accent}{HTML}{000000}') && !tex.includes('\\textcolor[HTML]{8E2B34}'),
         'and in black and white: the colours black, the hex mark not written');
  assert(tex.includes('\\expaperbool{'), 'its true/false statements are in their own column');
  assert(!((await texZip.getAttribute('class')) || '').includes('disabled'), 'once built, the LaTeX zip is there to press');
  const zip = await fetch(`${B}/download/${id}/texzip`);
  const zipBytes = new Uint8Array(await zip.arrayBuffer());
  const zipText = new TextDecoder('latin1').decode(zipBytes);
  assert(zip.ok && zip.headers.get('content-type') === 'application/zip' && /-latex\.zip"/.test(zip.headers.get('content-disposition')) &&
         zipBytes[0] === 0x50 && zipBytes[1] === 0x4b, 'the real route gives a zip named after the document');
  assert(zipText.includes('main.tex') && zipText.includes('README.txt') && zipText.includes('fonts/'), 'with its main.tex, its README and the fonts it sets its text in');
  const pdf = await fetch(`${B}/pdf/${id}`);
  assert(pdf.ok && (await pdf.arrayBuffer()).byteLength > 1000, 'the PDF is served');

  await page.locator('label', {has: radio(11)}).click();
  const stale = page.locator('#pdf-options-stale');
  assert(await stale.isVisible(), 'changing the options afterwards puts a badge beside the PDF');
  assert((await stale.textContent()).includes('built with other options'), 'which says it was built with other options');
  const why = await stale.getAttribute('title');
  assert(why.includes('built at 17 pt, black and white') && why.includes('now say 11 pt, black and white'),
         `and, on hover, which ones (${why})`);
  await page.reload();
  await page.waitForSelector('#sheet');
  assert(await radio(11).isChecked() && await page.locator('#ck-pdf-mono').isChecked(),
         'a reload keeps the choice');
  assert(await page.locator('#pdf-options-stale').isVisible(), 'and the badge');
  await page.evaluate(k => localStorage.removeItem(k), `exlex-pdf:${id}`);
  await page.reload();
  await page.waitForSelector('#sheet');
  assert(await radio(17).isChecked() && await page.locator('#ck-pdf-mono').isChecked(),
         'a browser with no choice made starts from what the PDF was built with');
  assert(await page.locator('#pdf-options-stale').count() === 0, 'and so shows no badge');
  assert(!errors.length, `no page errors (${errors.join('; ')})`);
  await ctx.close();

  // ------------------------------------------------------------------ b) phone
  console.log('b) the PDF options on a phone');
  for (const [W, H] of [[390, 844], [320, 568]]) {
    const at = `phone ${W}x${H}`;
    const pctx = await browser.newContext({viewport: {width: W, height: H}, deviceScaleFactor: 3,
                                           isMobile: true, hasTouch: true});
    const p = await pctx.newPage();
    const perr = [];
    p.on('pageerror', e => perr.push(e.message));
    await p.goto(`${B}/doc/${id}`);
    await p.waitForSelector('#sheet');
    // the phone's topbar is a row that scrolls sideways: bring the menu to view
    await p.locator('#pdf-options > summary').evaluate(e => e.scrollIntoView({block: 'nearest', inline: 'nearest'}));
    const s = p.locator('#pdf-options > summary');
    assert(onScreen(await placed(s)), `${at}: "PDF options ▾" is reached by a tap once its row is scrolled to it`);
    await s.tap();
    const m = p.locator('#pdf-options .menu');
    const mr = await placed(m);
    assert(await m.isVisible() && mr.l >= 0 && mr.r <= mr.w && mr.t >= 0 && mr.b <= mr.h,
           `${at}: the menu is entirely on the screen (${mr.l}–${mr.r} × ${mr.t}–${mr.b} in ${mr.w}×${mr.h})`);
    for (const v of [11, 14, 17, 20])
      assert(onScreen(await placed(p.locator(`input[name="pdf-size"][value="${v}"]`))),
             `${at}: the ${v} pt choice is reached by a tap`);
    assert(onScreen(await placed(p.locator('#ck-pdf-mono'))), `${at}: black and white is reached by a tap`);
    await p.locator('label', {has: p.locator('input[name="pdf-size"][value="14"]')}).tap();
    assert(await p.locator('input[name="pdf-size"][value="14"]').isChecked(), `${at}: a tap chooses 14 pt`);
    assert(await noSideways(p), `${at}: the page does not scroll sideways with the menu open`);
    if (SHOTS) await p.screenshot({path: `${SHOTS}/pdf-options-${W}.png`});
    await s.tap();                                   // shut it again
    const badges = await p.locator('#buildinfo .badge').evaluateAll(els => els.map(e => {
      const r = e.getBoundingClientRect();
      return {l: r.left, r: r.right, w: innerWidth, text: e.textContent};
    }));
    assert(badges.length >= 2 && badges.every(b => b.l >= 0 && b.r <= b.w),
           `${at}: the build badges, the options one among them, are on the screen (${badges.map(b => b.text).join(' | ')})`);
    assert(badges.some(b => b.text.includes('built with other options')), `${at}: the 14 pt choice is said to differ`);
    assert(!perr.length, `${at}: no page errors (${perr.join('; ')})`);
    await pctx.close();
  }
  console.log(`\n${passed} passed`);
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) { /* gone */ }
  await proc.status;
}
