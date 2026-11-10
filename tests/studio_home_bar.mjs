// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the BAR of the studio's library page (a0.6.2), driven as a person uses it, against the REAL routes
// on a temporary library (tests/studio_harness.py), in both mounts: the studio on its own, and Parseh's /studio.
//   a) the bar holds, in this order and on one row at 1280 and at 700 px: Parseh, Studio, + New, With an LLM ▾,
//      Open / import ▾, Backup ▾ and, apart at the far end, Stop server -- and nothing else; nothing passes the side
//      of the window at 700 or at 480, and a bar that wraps (480) covers nothing of the page; it wraps into two
//      rows, and no more, down to a window 360 px wide
//   b) each menu opens on a click and from the keyboard (Enter on its button), holds exactly its entries, each
//      with a line that says what it does, stays inside the window, and shuts on Escape (the keyboard goes back to
//      its button), on a click beside it, when another menu opens, when an entry is chosen, and when Tab or
//      Shift+Tab walks out of it; a window opened from an entry gives the keyboard back to the menu's button
//   c) + New goes to /new, and carries the language chip's language as it did
//   d) With an LLM ▾: LLM prompt goes to the prompt page; Paste LLM answer opens its window
//   e) Open / import ▾: Upload .md / .zip opens the file chooser, and the file chosen becomes a document;
//      Open a file… opens the file browser
//   f) Backup ▾: Backup the whole library downloads /api/export; Load from backup opens the file chooser, and
//      that backup puts a deleted document back
//   g) the row of the documents shown is under the filters and above the cards: its sentence and its two buttons
//      follow the search box, Download N shown's menu opens, shuts as the others do and sends the documents shown,
//      Make drawings of N shown is there -- and none of it is in the bar
//   h) the mobile mode shows nothing that writes: no bar of the browser's, no menu, no row
//   i) the dark and the sepia themes: the menus are drawn in the theme's own panel colour
//   j) a touch screen in the browser interface, where lib/explain.js adds its "?" to the bar: nothing passes the
//      side of the window at any width (700 among them), the "?" is the last thing of the first row, and the bar
//      is one row from 760 px and two below
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/studio_home_bar.mjs
//   STUDIO_HOME_BAR_MODES=studio (or parseh) runs one; SHOTS=<dir> saves the pictures (and, with LaTeX on the
//   computer, one of a drawings job running, which makes the run a few seconds longer)
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('STUDIO_HOME_BAR_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want), m + ' (got ' + JSON.stringify(got) + ')');
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(40);
  }
}

async function startHarness(mode, extra = []) {
  const proc = new Deno.Command(python, {args: [root + '/tests/studio_harness.py', mode, ...extra], cwd: root,
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

// the documents of the temporary library: a right-to-left language, two left-to-right ones and Japanese
const DOCS = [
  ['سلام و احوال‌پرسی', 'fa', ['greetings', 'beginner'], 'سلام! حال شما چطور است؟'],
  ['فعل‌های حرکتی', 'fa', ['verbs'], 'رفتن، آمدن، رسیدن.'],
  ['Greetings', 'en', ['greetings'], 'Hello, how are you?'],
  ['Il passato prossimo', 'it', ['verbs', 'grammar'], 'Ho mangiato una mela.'],
  ['あいさつ', 'ja', ['greetings', 'beginner'], 'こんにちは。お元気ですか。'],
];
const front = (title, lang, body) => `---\ntitle: ${title}\ntarget: ${lang}\n---\n\n${body}\n`;

const MENUS = {
  '#menu-llm': {label: 'With an LLM ▾', entries: [['btn-llm-prompt', 'LLM prompt'], ['btn-paste-answer', 'Paste LLM answer']]},
  '#menu-open': {label: 'Open / import ▾', entries: [['btn-upload', 'Upload .md / .zip'], ['btn-open-file', 'Open a file…']]},
  '#menu-backup': {label: 'Backup ▾', entries: [['btn-backup', 'Backup the whole library'], ['btn-restore', 'Load from backup']]},
};
const BAR = ['Parseh', 'Studio', '+ New', 'With an LLM ▾', 'Open / import ▾', 'Backup ▾', 'Stop server'];

async function suite(browser, mode) {
  console.log(`\n== ${mode} ==`);
  const {proc, info, log} = await startHarness(mode, SHOTS ? ['--latex-slow=1.5'] : []);
  const origin = `http://127.0.0.1:${info.port}`, S = info.studio;
  const url = p => origin + S + p;
  const api = async (method, path, body) => {
    const r = await fetch(url(path), {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                      body: body ? JSON.stringify(body) : undefined});
    return {status: r.status, data: await r.json()};
  };
  const errors = [], natives = [];
  try {
    const ids = {};
    for (const [title, lang, tags, body] of DOCS)
      ids[title] = (await api('POST', '/api/docs', {markdown: front(title, lang, body), tags})).data.meta.id;
    const context = await browser.newContext({viewport: {width: 1280, height: 800}, serviceWorkers: 'block',
                                              acceptDownloads: true});
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => { natives.push(d.type() + ': ' + d.message()); d.dismiss(); });
    const shot = async name => { if (SHOTS) await page.screenshot({path: `${SHOTS}/${mode}-${name}.png`}); };
    const home = async () => {
      await page.goto(url('/'));
      await page.waitForSelector('#cards .card:not([hidden])');
      await page.waitForSelector('#btn-open-file:not([hidden])', {state: 'attached'});
      await page.evaluate(() => document.fonts.ready);
    };
    const cardsShown = () => page.evaluate(() => document.querySelectorAll('#cards .card:not([hidden])').length);
    const isOpen = sel => page.locator(sel).evaluate(d => d.open);
    const openOnes = () => page.evaluate(() => [...document.querySelectorAll('details.dropdown[open]')].map(d => '#' + d.id));
    // what the bar draws, read off the page: every thing of it that takes room, with where it is
    const barDrawn = () => page.evaluate(() => {
      const bar = document.querySelector('header.topbar[data-layout="browser"]');
      const act = bar.querySelector('.topbar-actions');
      const kids = [...bar.children].filter(k => k !== act).concat([...act.children]);
      const out = [];
      for (const k of kids) {
        const r = (k.tagName === 'DETAILS' ? k.querySelector('summary') : k).getBoundingClientRect();
        if (!r.width || !r.height) continue;
        const label = (k.tagName === 'DETAILS' ? k.querySelector('summary') : k).textContent.replace(/[پف]/g, '').trim();
        out.push({label, x: Math.round(r.left), r: Math.round(r.right), y: Math.round(r.top + r.height / 2)});
      }
      out.sort((a, b) => a.y - b.y || a.x - b.x);
      const b = bar.getBoundingClientRect();
      return {things: out, bar: {h: Math.round(b.height), bottom: Math.round(b.bottom), right: Math.round(b.right)},
              vw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth,
              pageTop: Math.round(document.querySelector('.searchrow').getBoundingClientRect().top)};
    });
    const menuBox = sel => page.evaluate(sel => {
      const d = document.querySelector(sel), m = d.querySelector('.menu'), r = m.getBoundingClientRect();
      const s = d.querySelector('summary').getBoundingClientRect();
      return {x: r.left, r: r.right, y: r.top, b: r.bottom, vw: document.documentElement.clientWidth,
              vh: innerHeight, under: r.top >= s.bottom - 1,
              entries: [...m.children].filter(e => e.getBoundingClientRect().height > 0).map(e => {
                const small = e.querySelector('small');
                return {id: e.id, tag: e.tagName, name: (e.firstChild.textContent || '').trim(),
                        says: small ? small.textContent.trim() : '', title: e.title || '',
                        w: e.getBoundingClientRect().width};
              })};
    }, sel);

    /* ---------------- a) the bar ---------------- */
    console.log('a) the bar: what it holds, in which order, on one row');
    await home();
    for (const w of [1280, 1000, 700]) {
      await page.setViewportSize({width: w, height: 800});
      await sleep(120);
      const d = await barDrawn();
      eq(d.things.map(t => t.label), BAR, `${w}px: the bar holds Parseh, Studio, + New, the three menus and Stop server, in that order`);
      const ys = d.things.map(t => t.y);
      assert(Math.max(...ys) - Math.min(...ys) <= 4 && d.bar.h < 64, `${w}px: on one row (${d.bar.h}px high)`);
      assert(d.things.every((t, i) => !i || t.x >= d.things[i - 1].r), `${w}px: nothing over anything else`);
      const stop = d.things[d.things.length - 1], backup = d.things[d.things.length - 2];
      assert(d.bar.right - stop.r < 20 && (w < 1000 || stop.x - backup.r > 60), `${w}px: Stop server is last, at the far end${w < 1000 ? '' : ', apart from the rest'}`);
      assert(d.sw <= d.vw, `${w}px: nothing passes the side of the window (${d.sw} in ${d.vw})`);
      await shot(`bar-${w}`);
    }
    await page.setViewportSize({width: 480, height: 800});
    await sleep(120);
    let d = await barDrawn();
    eq(d.things.map(t => t.label).sort(), [...BAR].sort(), '480px: the bar wraps and still holds all seven');
    assert(d.sw <= d.vw && d.things.every(t => t.x >= 0 && t.r <= d.vw), `480px: nothing passes the side of the window (${d.sw} in ${d.vw})`);
    assert(new Set(d.things.map(t => t.y)).size <= 2 + 1 && d.bar.h < 110, `480px: in two rows (${d.bar.h}px high)`);
    assert(d.pageTop >= d.bar.bottom, '480px: the taller bar covers nothing: the search row begins under it');
    eq(await page.evaluate(() => ['#btn-new', '#menu-llm', '#menu-open', '#menu-backup', '#btn-stop'].map(s => {
      const e = document.querySelector(s); return !!e && e.closest('header.topbar') !== null;
    })), [true, true, true, true, true], 'the five controls are the bar\'s own');
    eq(await page.evaluate(() => ['#download-shown', '#btn-make-drawings', '#make-drawings-state'].map(s =>
      document.querySelector(s).closest('header') === null)), [true, true, true],
       'and the two that act on the documents shown are not in it');
    await shot('bar-480');
    // a phone held upright: still two rows, the four that make and bring in together on the second
    for (const w of [430, 390, 360]) {
      await page.setViewportSize({width: w, height: 800});
      await sleep(120);
      d = await barDrawn();
      const rows = [...new Set(d.things.map(t => t.y))].sort((a, b) => a - b);
      eq(d.things.map(t => t.label).sort(), [...BAR].sort(), `${w}px: the bar still holds all seven`);
      assert(rows.length === 2 && d.bar.h < 110, `${w}px: in two rows and no more (${rows.length} rows, ${d.bar.h}px high)`);
      eq(d.things.filter(t => t.y === rows[1]).map(t => t.label), BAR.slice(2, 6), `${w}px: + New and the three menus are one row, in their order`);
      assert(d.sw <= d.vw && d.things.every(t => t.x >= 0 && t.r <= d.vw), `${w}px: nothing passes the side of the window (${d.sw} in ${d.vw})`);
      assert(d.pageTop >= d.bar.bottom, `${w}px: the bar covers nothing`);
      await shot(`bar-${w}`);
    }

    /* ---------------- b) the menus ---------------- */
    console.log('b) the menus: opened, read, shut');
    for (const w of [1280, 700, 480]) {
      await page.setViewportSize({width: w, height: 800});
      await sleep(120);
      for (const [sel, want] of Object.entries(MENUS)) {
        const summary = page.locator(sel + ' > summary');
        eq((await summary.textContent()).trim(), want.label, `${w}px ${want.label}: named in words`);
        assert(!(await isOpen(sel)), `${w}px ${want.label}: shut until asked for`);
        await summary.click();
        assert(await isOpen(sel), `${w}px ${want.label}: a click opens it`);
        const box = await menuBox(sel);
        eq(box.entries.map(e => [e.id, e.name]), want.entries, `${w}px ${want.label}: holds exactly its entries`);
        assert(box.entries.every(e => e.says.length > 10 && e.title.length > 10),
               `${w}px ${want.label}: every entry says what it does, in a line of its own and in its explanation`);
        assert(box.x >= 0 && box.r <= box.vw && box.b <= box.vh && box.under,
               `${w}px ${want.label}: the menu hangs under its button, whole inside the window (${Math.round(box.x)}–${Math.round(box.r)} of ${box.vw})`);
        if (w === 1280 || (w === 480 && sel === '#menu-backup')) await shot(`menu-${sel.slice(6)}-${w}`);
        // Escape
        await page.keyboard.press('Escape');
        assert(!(await isOpen(sel)), `${w}px ${want.label}: Escape shuts it`);
        eq(await page.evaluate(() => document.activeElement && document.activeElement.textContent.trim()), want.label,
           `${w}px ${want.label}: and the keyboard is back on its button`);
        // the keyboard
        await page.keyboard.press('Enter');
        assert(await isOpen(sel), `${w}px ${want.label}: Enter on its button opens it`);
        await page.keyboard.press('Tab');
        eq(await page.evaluate(() => document.activeElement.id), want.entries[0][0], `${w}px ${want.label}: Tab goes to its first entry`);
        // a click beside it
        await page.mouse.click(3, 600);           // the page's own margin: nothing is there
        assert(!(await isOpen(sel)), `${w}px ${want.label}: a click beside it shuts it`);
      }
      // one at a time
      const order = Object.keys(MENUS);
      await page.locator(order[0] + ' > summary').click();
      for (const next of order.slice(1).concat(['#download-shown'])) {
        await page.locator(next + ' > summary').click();
        eq(await openOnes(), [next], `${w}px: opening ${next} shuts the menu that was open`);
      }
      await page.locator(order[0] + ' > summary').click();
      eq(await openOnes(), [order[0]], `${w}px: and a bar menu shuts Download N shown’s`);
      await page.keyboard.press('Escape');
      eq(await openOnes(), [], `${w}px: all shut`);
    }
    await page.setViewportSize({width: 1280, height: 800});
    await sleep(120);
    // the keyboard that walks out of a menu shuts it behind itself
    await page.locator('#menu-llm > summary').focus();
    await page.keyboard.press('Enter');
    assert(await isOpen('#menu-llm'), 'With an LLM ▾ opened from the keyboard');
    for (const want of ['btn-llm-prompt', 'btn-paste-answer']) {
      await page.keyboard.press('Tab');
      eq([await page.evaluate(() => document.activeElement.id), await isOpen('#menu-llm')], [want, true],
         `Tab walks its entries (${want}), and it stays open`);
    }
    await page.keyboard.press('Tab');
    eq([await page.evaluate(() => document.activeElement.textContent.trim()), await openOnes()], ['Open / import ▾', []],
       'Tab past its last entry goes to the next button of the bar, and the menu is shut behind it');
    await page.keyboard.press('Enter');
    eq(await openOnes(), ['#menu-open'], 'Enter there opens that one');
    await page.keyboard.press('Shift+Tab');
    eq([await page.evaluate(() => document.activeElement.textContent.trim()), await openOnes()], ['With an LLM ▾', []],
       'Shift+Tab back out of it shuts it too');
    // …but a focus that merely leaves (a press on an entry, before the click is whole) does not
    await page.locator('#menu-llm > summary').click();
    const at = await page.locator('#btn-paste-answer').boundingBox();
    await page.mouse.move(at.x + 20, at.y + 10);
    await page.mouse.down();
    assert(await isOpen('#menu-llm'), 'a press on an entry leaves the menu open until the click is whole');
    await page.mouse.move(3, 600);
    await page.mouse.up();
    await page.keyboard.press('Escape');
    eq(await openOnes(), [], 'all shut');

    /* ---------------- c) + New ---------------- */
    console.log('c) + New');
    await home();
    const first = await page.evaluate(() => document.querySelector('.topbar-actions > :not([hidden])').id);
    eq(first, 'btn-new', '+ New is the first of the actions');
    assert(await page.locator('#btn-new').evaluate(e => e.classList.contains('primary')), 'and the one drawn as the main one');
    eq(new URL(await page.locator('#btn-new').evaluate(e => e.href)).pathname + new URL(await page.locator('#btn-new').evaluate(e => e.href)).search,
       S + '/new', 'with every language shown it goes to /new');
    for (const lang of ['fa', 'ja']) {
      await page.locator(`.parseh-langs .chip[data-pick="${lang}"]`).click();
      await until(async () => (await page.locator('#btn-new').getAttribute('href')).endsWith('/new?target=' + lang),
                  `the ${lang} chip is carried by + New`);
      assert(true, `the ${lang} chip picked: + New goes to /new?target=${lang}`);
    }
    await Promise.all([page.waitForURL(u => u.pathname === S + '/new' && u.search === '?target=ja'), page.locator('#btn-new').click()]);
    assert(true, 'a click on + New opens the new document, in the chip\'s language');
    await page.goto(url('/'));
    await page.waitForSelector('#cards .card:not([hidden])');
    await page.locator('.parseh-langs .chip[data-pick="all"]').click();

    /* ---------------- d) With an LLM ---------------- */
    console.log('d) With an LLM ▾');
    await home();
    await page.locator('#menu-llm > summary').click();
    await Promise.all([page.waitForURL(u => u.pathname === S + '/prompt'), page.locator('#btn-llm-prompt').click()]);
    assert(true, 'LLM prompt goes to the prompt page');
    await home();
    await page.locator('#menu-llm > summary').click();
    await page.locator('#btn-paste-answer').click();
    await page.waitForSelector('#modal-root .modal textarea');
    assert(!(await isOpen('#menu-llm')), 'Paste LLM answer opens its window, and the menu is shut behind it');
    await shot('paste-window');
    await page.fill('#modal-root .modal textarea', front('Pasted from a chatbot', 'en', 'What it answered.'));
    await page.click('#modal-root .modal [data-x="ok"]');
    await until(async () => (await api('GET', '/api/docs?q=Pasted')).data.docs.some(x => x.title === 'Pasted from a chatbot'),
                'the pasted answer becomes a document');
    await page.waitForURL(/\/doc\/pasted-from-a-chatbot-[0-9a-f]{6}/);
    assert(true, 'and what is pasted there becomes a document, which the page goes to');

    /* ---------------- e) Open / import ---------------- */
    console.log('e) Open / import ▾');
    await home();
    await page.locator('#menu-open > summary').click();
    let [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.locator('#btn-upload').click()]);
    assert(chooser.isMultiple() && chooser.element() && await chooser.element().evaluate(e => e.id) === 'file-upload',
           'Upload .md / .zip opens the file chooser of the upload, which takes several files');
    assert(!(await isOpen('#menu-open')), 'and the menu is shut');
    await chooser.setFiles({name: 'uploaded.md', mimeType: 'text/markdown',
                            buffer: Buffer.from('---\ntitle: Uploaded through the menu\nsubtitle:\nnote:\nlang: en\ntarget: it\n---\n\nCaricato.\n')});
    await until(async () => (await api('GET', '/api/docs?q=Uploaded')).data.docs.some(x => x.title === 'Uploaded through the menu'),
                'the uploaded file becomes a document');
    await page.waitForURL(/\/doc\/uploaded-through-the-menu-[0-9a-f]{6}/);
    await home();
    assert(await page.locator('#cards .card', {hasText: 'Uploaded through the menu'}).count() === 1,
           'the file chosen is a document of the library');
    await page.locator('#menu-open > summary').click();
    assert(await page.locator('#btn-open-file').isVisible(), 'Open a file… is in the menu');
    await page.locator('#btn-open-file').click();
    await page.waitForSelector('.of-modal .of-path');
    assert(!(await isOpen('#menu-open')), 'and opens the file browser, the menu shut behind it');
    await shot('open-file-window');
    await page.keyboard.press('Escape');
    await page.waitForSelector('.of-modal', {state: 'detached'});
    eq(await page.evaluate(() => [document.activeElement.tagName, document.activeElement.textContent.trim()]), ['SUMMARY', 'Open / import ▾'],
       'the window closed, the keyboard is back on the button of the menu it was opened from');
    assert(!(await isOpen('#menu-open')), 'which is still shut');

    /* ---------------- f) Backup ---------------- */
    console.log('f) Backup ▾');
    await page.locator('#menu-backup > summary').click();
    eq(new URL(await page.locator('#btn-backup').evaluate(e => e.href)).pathname, S + '/api/export',
       'Backup the whole library is the link to /api/export');
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#btn-backup').click()]);
    const kept = await Deno.makeTempFile({suffix: '.zip'});
    await download.saveAs(kept);
    const zip = await Deno.readFile(kept);
    await Deno.remove(kept);
    assert(zip.length > 200 && zip[0] === 0x50 && zip[1] === 0x4b, `and a click downloads the library as a zip (${zip.length} bytes)`);
    assert(!(await isOpen('#menu-backup')), 'the menu is shut');
    const lost = ids['Greetings'];
    eq((await api('DELETE', '/api/docs/' + lost)).status, 200, 'a document is deleted');
    await home();
    assert(await page.locator(`#cards .card[data-id="${lost}"]`).count() === 0, 'and is not in the library any more');
    await page.locator('#menu-backup > summary').click();
    [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.locator('#btn-restore').click()]);
    assert(!chooser.isMultiple() && await chooser.element().evaluate(e => e.id) === 'backup-file',
           'Load from backup opens the file chooser of the backup');
    await chooser.setFiles({name: 'backup.zip', mimeType: 'application/zip', buffer: Buffer.from(zip)});
    // the documents that are still there are asked about, and left as they are
    await page.waitForSelector('#modal-root .modal [data-x="keep"]');
    await page.click('#modal-root .modal [data-x="keep"]');
    await page.waitForSelector(`#cards .card[data-id="${lost}"]`, {timeout: 15000});
    assert(true, 'and the backup chosen puts the deleted document back, on the page, without a reload');

    /* ---------------- g) the documents shown ---------------- */
    console.log('g) the row of the documents shown');
    await home();
    const all = await cardsShown();
    const row = () => page.evaluate(() => ({
      say: document.querySelector('#shown-say').textContent,
      dl: document.querySelector('#btn-download-shown').textContent,
      make: document.querySelector('#btn-make-drawings').textContent,
      dead: document.querySelector('#download-shown').classList.contains('disabled'),
      off: document.querySelector('#btn-make-drawings').disabled,
    }));
    eq(await row(), {say: `The ${all} documents shown:`, dl: `Download ${all} shown`, make: `Make drawings of ${all} shown`, dead: false, off: false},
       'the row says how many documents are shown, and its two buttons with it');
    const where = await page.evaluate(() => {
      const y = s => { const r = document.querySelector(s).getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom)]; };
      const kids = [...document.querySelector('#shown-row').children].filter(k => k.getBoundingClientRect().width > 0);
      return {search: y('.searchrow'), chips: y('.parseh-langs'), tags: y('#tagbar'), row: y('#shown-row'), cards: y('#cards'),
              kids: kids.map(k => k.id), oneLine: new Set(kids.map(k => Math.round((k.getBoundingClientRect().top + k.getBoundingClientRect().bottom) / 2 / 6))).size};
    });
    assert(where.row[0] >= where.search[1] && where.row[0] >= where.chips[1] && where.row[0] >= where.tags[1] && where.row[1] <= where.cards[0],
           'it is under the search, the chips and the tags, and above the cards');
    eq(where.kids, ['shown-say', 'download-shown', 'btn-make-drawings'], 'it holds its sentence, Download N shown and Make drawings of N shown');
    await page.fill('#search', 'greetings');
    await until(async () => (await cardsShown()) < all && (await cardsShown()) > 1, 'the search narrows the set');
    let n = await cardsShown();
    eq(await row(), {say: `The ${n} documents shown:`, dl: `Download ${n} shown`, make: `Make drawings of ${n} shown`, dead: false, off: false},
       'the counts follow the search box');
    await shot('shown-row-search');
    await page.locator('.parseh-langs .chip[data-pick="ja"]').click();
    await until(async () => (await cardsShown()) === 1, 'the chip narrows it further');
    eq(await row(), {say: 'The 1 document shown:', dl: 'Download 1 shown', make: 'Make drawings of 1 shown', dead: false, off: false},
       'and the language chip, in the singular for one');
    await page.locator('.parseh-langs .chip[data-pick="all"]').click();
    await page.fill('#search', 'zzzz no such document');
    await until(async () => (await cardsShown()) === 0, 'the search finds nothing');
    eq(await row(), {say: 'No documents shown:', dl: 'Download 0 shown', make: 'Make drawings of 0 shown', dead: true, off: true},
       'with nothing shown the row says so and both buttons are off');
    await page.fill('#search', 'greetings');
    await until(async () => (await cardsShown()) === n, 'the search again');
    await page.locator('#btn-download-shown').click();
    assert(await isOpen('#download-shown'), 'Download N shown opens its menu');
    let box = await menuBox('#download-shown');
    eq(box.entries.map(e => [e.id, e.name]), [['dl-shown-md', 'Markdown (.md)'], ['dl-shown-zip', 'Markdown + media (.zip)']],
       'which holds the two shapes');
    assert(box.x >= 0 && box.r <= box.vw && box.under, 'whole inside the window, under its button');
    await shot('shown-row-menu');
    await page.keyboard.press('Escape');
    assert(!(await isOpen('#download-shown')), 'Escape shuts it');
    await page.locator('#btn-download-shown').click();
    await page.mouse.click(3, 700);
    assert(!(await isOpen('#download-shown')), 'a click beside it shuts it');
    await page.locator('#btn-download-shown').click();
    const [sent] = await Promise.all([page.waitForRequest(r => r.method() === 'POST' && /\/api\/download/.test(r.url())),
                                      page.locator('#dl-shown-md').click()]);
    const body = new URLSearchParams(sent.postData());
    eq([body.get('ids').split(',').length, body.get('shape')], [n, 'md'], 'choosing a shape sends the documents shown, and no others');
    assert(!(await isOpen('#download-shown')), 'and the menu is shut');
    await page.fill('#search', '');
    await until(async () => (await cardsShown()) === all, 'the whole library again');
    for (const w of [700, 480]) {
      await page.setViewportSize({width: w, height: 800});
      await sleep(150);
      await page.locator('#btn-download-shown').click();
      box = await menuBox('#download-shown');
      const sw = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
      assert(box.x >= 0 && box.r <= box.vw && sw[0] <= sw[1], `${w}px: the row and its menu stay inside the window`);
      await page.keyboard.press('Escape');
      await shot(`page-${w}`);
    }
    await page.setViewportSize({width: 1280, height: 800});

    // a drawings job running, for the picture: its state and its Stop are in the row, beside the button
    if (SHOTS) {
      const tex = k => `::::latex\n\\textbf{bar ${k}} $x^${k}$\n::::`;
      await api('POST', '/api/docs', {markdown: front('Drawings to make', 'it', [1, 2, 3, 4].map(tex).join('\n\n'))});
      await home();
      await page.locator('#btn-make-drawings').click();
      try {
        await until(async () => /^Making drawings…/.test(await page.locator('#btn-make-drawings').textContent()), 'the drawings begin', 20000);
        await page.waitForSelector('#btn-make-stop', {state: 'visible'});
        eq(await page.evaluate(() => document.querySelector('#make-drawings-state').parentElement.id), 'shown-row',
           'a drawings job running says so in the row, with its Stop');
        await shot('drawings-running');
        await page.locator('#btn-make-stop').click();
        await until(async () => /^Make drawings of/.test(await page.locator('#btn-make-drawings').textContent()), 'the job ends', 60000);
      } catch (e) { console.log('  (no picture of a drawings job: ' + e.message + ')'); }
    }

    /* ---------------- i) the themes ---------------- */
    console.log('i) the themes');
    for (const theme of ['dark', 'sepia']) {
      await page.evaluate(t => localStorage.setItem('parseh_theme', t), theme);
      await home();
      await page.locator('#menu-open > summary').click();
      const c = await page.evaluate(() => {
        const cs = e => getComputedStyle(e);
        const m = document.querySelector('#menu-open .menu'), bar = document.querySelector('header.topbar');
        return {theme: document.body.getAttribute('data-theme') || document.documentElement.getAttribute('data-theme'),
                menu: cs(m).backgroundColor, bar: cs(bar).backgroundColor, page: cs(document.body).backgroundColor,
                ink: cs(m.querySelector('button')).color, row: cs(document.querySelector('#shown-row')).backgroundColor};
      });
      assert(c.menu === c.bar && c.row === c.bar && c.menu !== 'rgb(255, 255, 255)' && c.ink !== c.menu,
             `${theme}: the menu and the row are drawn in the theme's own panel colour (${c.menu}, ink ${c.ink})`);
      await shot(theme);
      await page.keyboard.press('Escape');
    }
    await page.evaluate(() => localStorage.setItem('parseh_theme', 'light'));

    /* ---------------- j) a touch screen, browser interface ---------------- */
    console.log('j) a touch screen in the browser interface: the "?" has its room');
    // the "?" is Parseh's (/lib/explain.js): the studio on its own does not serve it, and its bar on a touch screen
    // is then the bar of a) at the touch breakpoint, with nothing after Stop server
    const asks = (await fetch(origin + '/lib/explain.js')).status === 200;
    eq(asks, mode === 'parseh', `the "?" is drawn ${mode === 'parseh' ? 'under Parseh' : 'only under Parseh, not by the studio on its own'}`);
    const Q = asks ? ['?'] : [];
    for (const w of [1024, 760, 759, 700, 480, 390, 360]) {
      const tctx = await browser.newContext({viewport: {width: w, height: 844}, serviceWorkers: 'block', hasTouch: true, isMobile: true});
      const t = await tctx.newPage();
      t.on('pageerror', e => errors.push('touch: ' + e.message));
      await t.goto(url('/'));
      await t.evaluate(() => {
        localStorage.setItem('parseh_mode', 'browser');
        document.cookie = 'parseh_mode=browser; Path=/; SameSite=Lax; Max-Age=31536000';
      });
      await t.reload();
      await t.waitForSelector('#cards .card:not([hidden])');
      if (asks) await t.waitForSelector('header.topbar > .px-ask');
      assert(await t.evaluate(() => matchMedia('(hover: none)').matches), `touch ${w}px: a screen with no hover`);
      await t.evaluate(() => document.fonts.ready);
      const g = await t.evaluate(() => {
        const bar = document.querySelector('header.topbar[data-layout="browser"]');
        const things = [...bar.querySelectorAll('.hublink, .brand, #btn-new, summary.btn, #btn-stop, .px-ask')].map(e => {
          const r = e.getBoundingClientRect();
          return {label: e.textContent.replace(/[پف]/g, '').trim(), x: Math.round(r.left), r: Math.round(r.right), y: Math.round(r.top + r.height / 2)};
        }).sort((a, b) => a.y - b.y || a.x - b.x);
        return {mode: document.documentElement.getAttribute('data-mode'), things, vw: document.documentElement.clientWidth,
                sw: document.documentElement.scrollWidth, bottom: Math.round(bar.getBoundingClientRect().bottom),
                pageTop: Math.round(document.querySelector('.searchrow').getBoundingClientRect().top)};
      });
      assert(g.mode !== 'mobile', `touch ${w}px: the browser interface`);
      assert(g.sw <= g.vw && g.things.every(x => x.x >= 0 && x.r <= g.vw),
             `touch ${w}px: nothing passes the side of the window, the "?" neither (${g.sw} in ${g.vw})`);
      const rows = [...new Set(g.things.map(x => x.y))].sort((a, b) => a - b);
      const firstRow = g.things.filter(x => x.y === rows[0]).map(x => x.label);
      if (w >= 760) eq(firstRow, [...BAR, ...Q], `touch ${w}px: one row${asks ? ', the "?" after Stop server' : ''}`);
      else {
        eq(firstRow, ['Parseh', 'Studio', 'Stop server', ...Q], `touch ${w}px: the first row is the two names and Stop server${asks ? ', then the "?"' : ''}`);
        eq([rows.length, g.things.filter(x => x.y === rows[1]).map(x => x.label)], [2, BAR.slice(2, 6)],
           `touch ${w}px: + New and the three menus are the second row, and there is no third`);
      }
      assert(g.things.every((x, i) => !i || x.y !== g.things[i - 1].y || x.x >= g.things[i - 1].r), `touch ${w}px: nothing over anything else`);
      assert(g.pageTop >= g.bottom, `touch ${w}px: the bar covers nothing`);
      // a menu opened by a tap stays inside the window
      await t.locator('#menu-backup > summary').tap();
      const mb = await t.evaluate(() => { const r = document.querySelector('#menu-backup .menu').getBoundingClientRect(); return [r.left, r.right, document.documentElement.clientWidth, document.querySelector('#menu-backup').open]; });
      assert(mb[3] && mb[0] >= 0 && mb[1] <= mb[2], `touch ${w}px: a tap opens Backup ▾, whole inside the window`);
      if (SHOTS && [700, 390, 360].includes(w)) await t.screenshot({path: `${SHOTS}/${mode}-touch-${w}.png`});
      await tctx.close();
    }

    /* ---------------- h) the mobile mode ---------------- */
    console.log('h) the mobile mode: nothing that writes');
    const phone = await browser.newContext({viewport: {width: 390, height: 844}, serviceWorkers: 'block', hasTouch: true, isMobile: true});
    const m = await phone.newPage();
    m.on('pageerror', e => errors.push('mobile: ' + e.message));
    await m.goto(url('/'));
    await m.evaluate(() => {
      localStorage.setItem('parseh_mode', 'mobile');
      document.cookie = 'parseh_mode=mobile; Path=/; SameSite=Lax; Max-Age=31536000';
    });
    await m.reload();
    await m.waitForSelector('#cards .card:not([hidden])');
    eq(await m.evaluate(() => document.documentElement.getAttribute('data-mode')), 'mobile', 'the page is in the mobile mode');
    const drawn = await m.evaluate(() => ['header.topbar', '.topbar-actions', '#btn-new', '#menu-llm', '#menu-open', '#menu-backup',
      '#btn-llm-prompt', '#btn-paste-answer', '#btn-upload', '#btn-open-file', '#btn-backup', '#btn-restore', '#btn-stop',
      '#shown-row', '#shown-say', '#download-shown', '#btn-download-shown', '#btn-make-drawings', '#make-drawings-state',
      '#btn-make-stop'].filter(s => [...document.querySelectorAll(s)].some(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
      })));
    eq(drawn, [], 'none of the bar, of its menus or of the row of the documents shown is drawn');
    assert(await m.locator('#search').isVisible() && await m.locator('#cards .card').first().isVisible(),
           'the search and the cards are');
    if (SHOTS) await m.screenshot({path: `${SHOTS}/${mode}-mobile.png`});
    await phone.close();

    eq(natives, [], 'no window of the browser\'s own was raised');
    await context.close();
  } catch (e) {
    if (log.length) console.log(log.join(''));
    throw e;
  } finally {
    proc.kill('SIGTERM');
    await proc.status;
  }
  if (errors.length) throw Error('FAIL: page errors: ' + errors.join(' | '));
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN') || undefined, headless: true});
try {
  for (const mode of modes) await suite(browser, mode);
} finally {
  await browser.close();
}
console.log(`\nstudio_home_bar: ${passed} checks passed`);
