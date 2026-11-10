// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of links between documents by NAME, against the REAL routes
// (serve.py's handler: the studio at /studio, a book's notes under its own
// prefix) on a temporary library -- tests/doclinks_harness.py:
//   a) the editor's Save with a title another document has (and, in c, the
//      first save of a document made with + New): the name-conflict
//      dialog, a name given that is taken too (said under its field, the
//      dialog stays), then two free names -- both documents renamed, and a
//      document linking to the saved one follows it; Cancel writes nothing;
//      at 390 px the dialog fits the screen
//   b) the Doc link picker writes a name escaped as texgen does
//   c) the library's Paste (cancelling the names brings the paste back),
//      Upload .md, Load from backup (a document of another id with a name
//      taken), and a document's Duplicate
//   d) the same dialog on a book's notes, its "open it" inside the notes, and
//      a note's "Linked from"
//   e) "Linked from" on a document's page (desktop and 390 px): the button
//      with the count, the drawer with every document linking here by name or
//      by an old uid, the words around each link, Esc, the empty state
//   f) Load from backup, then Replace them: the names the first pass gave are
//      sent again, and one the replaced documents take back is asked about in
//      a dialog of its own, with a field for each of the two documents
//   g) a title holding "|" (it would split the table cell a link to it is
//      in): the dialog asks for another name, in a field of its own
//   h) an editor left open while a document it links to is renamed in
//      another tab: its save keeps the link that followed the rename
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/doclinks.mjs
//   SHOTS=<dir> saves screenshots of the dialog (desktop and phone)
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}

async function startHarness() {
  const proc = new Deno.Command(python, {args: [root + '/tests/doclinks_harness.py'], cwd: root,
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
  return {proc, info, log};
}

const {proc, info, log} = await startHarness();
const origin = `http://127.0.0.1:${info.port}`, S = info.studio, N = info.notes;
const D = info.docs;
const api = async (method, path, body) => {
  const r = await fetch(origin + path, {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                        body: body ? JSON.stringify(body) : undefined});
  const data = await r.json().catch(() => ({}));
  return {status: r.status, data};
};
const get = async id => (await api('GET', `${S}/api/docs/${id}`)).data;
const titleOf = async (id, base = S) => (await api('GET', `${base}/api/docs/${id}`)).data.meta.title;

/* What a person sees of the dialog: each element's box on screen, the
   field a problem belongs to, the colour it is said in. */
async function dialogState(page) {
  return page.evaluate(() => {
    const m = document.querySelector('.names-modal');
    if (!m) return null;
    const box = e => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, r: r.right, b: r.bottom}; };
    return {
      modal: box(m), vw: innerWidth, vh: innerHeight,
      fields: [...m.querySelectorAll('.names-field input')].map(i => {
        const p = i.parentNode.querySelector('.names-problem');
        return {key: i.dataset.key, value: i.value, label: i.parentNode.querySelector('.names-label').textContent,
                box: box(i), dir: i.dir, invalid: i.getAttribute('aria-invalid'),
                problem: p && !p.hidden ? p.textContent : '',
                problemBox: p && !p.hidden ? box(p) : null,
                problemColor: p ? getComputedStyle(p).color : '',
                onTop: (() => { const r = i.getBoundingClientRect();
                                return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === i; })()};
      }),
      open: [...m.querySelectorAll('.names-open')].map(a => a.getAttribute('href')),
      error: m.querySelector('.names-error').hidden ? '' : m.querySelector('.names-error').textContent,
    };
  });
}
const setField = (page, key, value) => page.evaluate(([k, v]) => {
  const i = document.querySelector(`.names-field input[data-key="${k}"]`);
  i.value = v; i.dispatchEvent(new Event('input', {bubbles: true}));
}, [key, value]);
async function retitle(page, title) {
  await page.evaluate(t => {
    const src = document.querySelector('#src');
    src.value = src.value.replace(/^title: .*$/m, 'title: ' + t);
    src.dispatchEvent(new Event('input', {bubbles: true}));
  }, title);
}

/* The drawer as a person meets it: the button on screen and on top, the
   drawer off screen until it is opened, then whole on screen with every
   document that links here, the Persian one right to left; Esc puts it
   away and gives the focus back; a link in it goes there. */
async function drawerState(page) {
  return page.evaluate(() => {
    const btn = document.querySelector('#btn-backlinks'), pane = document.querySelector('#linkspane');
    const r = btn.getBoundingClientRect(), p = pane.getBoundingClientRect();
    return {label: btn.textContent.trim(), expanded: btn.getAttribute('aria-expanded'),
            btn: {x: r.left, r: r.right, y: r.top, b: r.bottom},
            btnOnTop: document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2) === btn,
            pane: {x: p.left, r: p.right, y: p.top, b: p.bottom},
            visible: getComputedStyle(pane).visibility === 'visible',
            vw: innerWidth, vh: innerHeight, scrollW: document.documentElement.scrollWidth,
            docs: [...pane.querySelectorAll('.link-doc')].map(a => [a.textContent, a.getAttribute('href')]),
            snippets: [...pane.querySelectorAll('.link-snippet')].map(p => ({
              text: p.textContent, mark: p.querySelector('mark').textContent, rtl: p.matches(':dir(rtl)'),
              markColor: getComputedStyle(p.querySelector('mark')).color})),
            empty: (pane.querySelector('.links-empty') || {}).textContent || '',
            focus: document.activeElement && (document.activeElement.id || document.activeElement.className)};
  });
}
async function backlinks(page, width) {
  await page.goto(`${origin}${S}/doc/${D.verbs}`);
  await page.waitForSelector('#btn-backlinks');
  let st = await drawerState(page);
  if (SHOTS) await page.screenshot({path: `${SHOTS}/linked-from-button-${width}.png`});
  assert(st.label === '↩ Linked from (3)' && st.btnOnTop
         && st.btn.x >= 0 && st.btn.r <= st.vw && st.btn.y >= 0,
         `${width} px: the button says how many, on screen and on top: ${st.label} ${JSON.stringify(st.btn)}`);
  assert(st.scrollW <= st.vw, `${width} px: and the page does not scroll sideways (${st.scrollW})`);
  if (width > 560) {
    // a wide screen keeps the bar at the top of the window as tall as it
    // was with two buttons: "Linked from" beside Contents, not under Glosses
    const rows = await page.evaluate(() => {
      const r = s => document.querySelector(s).getBoundingClientRect();
      return {nav: r('.navstack').height, toc: r('#btn-toc'), glosses: r('#btn-glosses'), links: r('#btn-backlinks')};
    });
    assert(Math.abs(rows.links.top - rows.toc.top) < 1 && rows.links.left >= rows.toc.right
           && rows.nav <= rows.toc.height + rows.glosses.height + 8,
           `${width} px: the three buttons take two rows, Linked from beside Contents: ${JSON.stringify(rows)}`);
  }
  assert(!st.visible && (st.pane.x >= st.vw - 1), `${width} px: the drawer is away until opened`);
  await page.click('#btn-backlinks');
  await until(async () => (await drawerState(page)).visible
              && (await drawerState(page)).pane.r <= (await drawerState(page)).vw + 0.5, 'the drawer slides in');
  await sleep(250);                                   // its transition, to the end
  st = await drawerState(page);
  assert(st.expanded === 'true' && st.pane.x >= 0 && st.pane.r <= st.vw + 0.5 && st.pane.b <= st.vh + 0.5,
         `${width} px: opened, it is whole on screen: ${JSON.stringify(st.pane)}`);
  assert(JSON.stringify(st.docs.map(d => d[0])) === JSON.stringify(['Grammar', 'Old links', 'شکل کلمه']),
         `${width} px: every document that links here, by name or by an old uid: ${st.docs.map(d => d[0])}`);
  assert(st.docs.every(([, h]) => h.startsWith(`${S}/doc/`)), `${width} px: each a link to it`);
  const persianSnip = st.snippets.find(x => x.mark === 'فعل‌های حرکتی');
  assert(persianSnip && persianSnip.rtl && persianSnip.text === 'کلمه‌ها در فعل‌های حرکتی هم دیده می‌شوند.',
         `${width} px: the Persian context reads right to left, its link marked`);
  const grammarSnip = st.snippets.find(x => x.mark === 'Taken');
  assert(grammarSnip && !grammarSnip.rtl && /again, with its title\.$/.test(grammarSnip.text),
         `${width} px: an empty label shows the title it has now: ${grammarSnip && grammarSnip.text}`);
  assert(st.focus === 'link-doc', `${width} px: the focus goes to the first document in it`);
  if (SHOTS) await page.screenshot({path: `${SHOTS}/linked-from-${width}.png`});
  await page.keyboard.press('Escape');
  await until(async () => !(await drawerState(page)).visible, 'Esc closes it');
  st = await drawerState(page);
  assert(st.expanded === 'false' && st.focus === 'btn-backlinks', `${width} px: Esc closes it, the focus back on the button`);
  await page.click('#btn-backlinks');
  await until(async () => (await drawerState(page)).visible, 'open again');
  await Promise.all([page.waitForURL(`**/doc/${D.persian}`), page.click(`#linkspane a[href$="${D.persian}"]`)]);
  assert(true, `${width} px: a document in it opens`);
  await page.goto(`${origin}${S}/doc/${D.lonely}`);
  st = await drawerState(page);
  assert(st.label === '↩ Linked from (0)' && st.empty === 'No document links here yet.',
         `${width} px: a document nothing links to says so`);
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  const ctx = await browser.newContext({viewport: {width: 1280, height: 860}});
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  // ------------------------------------------------------------------ a)
  console.log('a) Save with a title another document has');
  await page.goto(`${origin}${S}/doc/${D.verbs}/edit`);
  await page.waitForSelector('#src');
  await retitle(page, 'taken');
  await page.click('#btn-save');
  await page.waitForSelector('.names-modal');
  let st = await dialogState(page);
  assert(st.modal.x >= 0 && st.modal.r <= st.vw && st.modal.y >= 0 && st.modal.b <= st.vh,
         'the dialog is on screen whole: ' + JSON.stringify(st.modal));
  assert(st.fields.length === 2 && st.fields[0].key === 'existing:' + D.taken
         && st.fields[1].key === 'incoming:' + D.verbs,
         'two fields: the document already in the library, the one being saved');
  assert(st.fields[0].value === 'Taken' && st.fields[1].value === 'taken',
         'each prefilled with its own name: ' + st.fields.map(f => f.value));
  assert(/already in the library/.test(st.fields[0].label) && /being saved/.test(st.fields[1].label),
         'and each says which document it renames');
  assert(st.fields.every(f => f.onTop && f.dir === 'auto'),
         'both fields are on top, and take a right-to-left name the right way');
  assert(st.open[0] === `${S}/doc/${D.taken}`, 'the one already there can be opened first: ' + st.open[0]);
  assert(await page.evaluate(() => document.querySelector('#btn-save').disabled),
         'Save stays disabled while the dialog is open');
  assert((await titleOf(D.verbs)) === 'Verbs of motion', 'nothing was written');
  if (SHOTS) await page.screenshot({path: `${SHOTS}/names-dialog-desktop.png`});

  // a name given that is taken as well: said under its field, the dialog stays
  await setField(page, 'incoming:' + D.verbs, 'Grammar');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => (await dialogState(page)).fields[1].problem, 'the problem under the field');
  st = await dialogState(page);
  assert(st.fields[1].problem === '“Grammar” is already the name of another document — choose another name',
         'a name taken is said under its own field: ' + st.fields[1].problem);
  assert(st.fields[1].problemBox.y >= st.fields[1].box.b - 1 && st.fields[1].invalid === 'true',
         'right under it, and the field is marked');
  assert(st.fields[1].problemColor === await page.evaluate(() =>
           getComputedStyle(document.documentElement).getPropertyValue('--danger').trim()
             .replace(/^#(..)(..)(..)$/, (_, r, g, b) => `rgb(${parseInt(r, 16)}, ${parseInt(g, 16)}, ${parseInt(b, 16)})`)),
         'in the danger colour: ' + st.fields[1].problemColor);
  assert(!st.fields[0].problem, 'the other field has nothing to say');
  if (SHOTS) await page.screenshot({path: `${SHOTS}/names-dialog-problem.png`});
  assert((await titleOf(D.verbs)) === 'Verbs of motion' && (await titleOf(D.taken)) === 'Taken',
         'still nothing written');

  // an empty name is refused before anything is sent
  await setField(page, 'incoming:' + D.verbs, '   ');
  await page.click('.names-modal [data-x="ok"]');
  st = await dialogState(page);
  assert(/needs a name/.test(st.fields[1].problem), 'an empty name is asked for again: ' + st.fields[1].problem);

  // two free names: both renamed, and the links follow
  await setField(page, 'existing:' + D.taken, 'Taken before');
  await setField(page, 'incoming:' + D.verbs, 'Taken');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => !(await page.$('.names-modal')), 'the dialog closes');
  await until(async () => (await page.textContent('#toast')) === 'Saved', 'Saved');
  assert((await titleOf(D.verbs)) === 'Taken' && (await titleOf(D.taken)) === 'Taken before',
         'both documents have the names given');
  assert((await page.textContent('.doc-title')) === 'Taken', 'the editor says its new name');
  const src = await page.$eval('#src', e => e.value);
  assert(/^title: Taken$/m.test(src) && src.includes('See also [myself](doc:Taken).'),
         'the editor holds the text as written, its link to itself following it');
  assert(!(await page.evaluate(() => document.querySelector('#btn-save').disabled)), 'Save is back');
  const grammar = (await get(D.grammar)).markdown;
  assert(grammar.includes('[the verbs](doc:Taken), and then [](doc:Taken) again'),
         'a document that linked to it follows it, labels kept: ' + grammar.split('\n').slice(-2).join(' '));
  await page.goto(`${origin}${S}/doc/${D.grammar}`);
  const links = await page.$$eval('#sheet a.doclink', as => as.map(a => [a.getAttribute('href'), a.textContent]));
  assert(links.length === 2 && links.every(([h]) => h === `${S}/doc/${D.verbs}`)
         && links[1][1] === 'Taken', 'and its page links to it, the empty label showing its new title: '
         + JSON.stringify(links));

  // Cancel: nothing written, the text kept
  await page.goto(`${origin}${S}/doc/${D.lonely}/edit`);
  await page.waitForSelector('#src');
  await retitle(page, 'Grammar');
  const before = await page.$eval('#src', e => e.value);
  await page.keyboard.press('Control+s');
  await page.waitForSelector('.names-modal');
  await page.keyboard.press('Escape');
  await until(async () => !(await page.$('.names-modal')), 'Escape closes the dialog');
  assert((await page.$eval('#src', e => e.value)) === before, 'the text in the editor is as it was');
  assert((await titleOf(D.lonely)) === 'Lonely', 'and nothing was saved');
  assert(/Not saved/.test(await page.textContent('#toast')), 'which the page says');

  // at 390 px
  const phone = await browser.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 3,
                                          isMobile: true, hasTouch: true});
  const pp = await phone.newPage();
  await pp.goto(`${origin}${S}/doc/${D.lonely}/edit`);
  await pp.waitForSelector('#src');
  await retitle(pp, 'Grammar');
  await pp.evaluate(() => document.querySelector('#btn-save').click());
  await pp.waitForSelector('.names-modal');
  st = await dialogState(pp);
  assert(st.modal.x >= 0 && st.modal.r <= 390 && st.modal.b <= 844,
         'at 390 px the dialog fits the screen: ' + JSON.stringify(st.modal));
  assert(st.fields.every(f => f.box.x >= st.modal.x && f.box.r <= st.modal.r && f.onTop),
         'and its fields fit it, on top');
  if (SHOTS) await pp.screenshot({path: `${SHOTS}/names-dialog-phone.png`});
  await phone.close();

  // ------------------------------------------------------------------ e)
  console.log('e) "Linked from" on a document\'s page, desktop and 390 px');
  await backlinks(page, 1280);
  const phoneCtx = await browser.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 3,
                                             isMobile: true, hasTouch: true});
  const phonePage = await phoneCtx.newPage();
  phonePage.on('pageerror', e => errors.push(e.message));
  await backlinks(phonePage, 390);
  await phoneCtx.close();

  // ------------------------------------------------------------------ b)
  console.log('b) the Doc link picker writes a name as texgen does');
  await page.goto(`${origin}${S}/doc/${D.lonely}/edit`);
  await page.waitForSelector('#src');
  const escaped = await page.evaluate(names => Object.fromEntries(names.map(n => [n, escapeDocName(n)])),
                                      Object.keys(info.escapes));
  assert(JSON.stringify(escaped) === JSON.stringify(info.escapes),
         'escapeDocName agrees with texgen.escape_doc_name on every awkward name');
  await page.evaluate(() => { const s = document.querySelector('#src'); s.focus(); s.setSelectionRange(s.value.length, s.value.length); });
  await page.click('#btn-doclink');
  await page.waitForSelector('.dl-modal .dl-item');
  await page.fill('.dl-filter', 'شکل');
  await page.click('.dl-modal .dl-item');
  await page.click('.dl-modal [data-x="ok"]');
  assert((await page.$eval('#src', e => e.value)).endsWith('[](doc:شکل کلمه)'),
         'the picker inserts the document by its name');
  await until(async () => (await page.$$eval('#sheet a.doclink', as => as.map(a => a.getAttribute('href'))))
                .includes(`${S}/doc/${D.persian}`), 'the preview links it');
  assert(true, 'and the preview links to it');

  // ------------------------------------------------------------------ c)
  console.log('c) the library: paste, upload, backup, duplicate');
  page.on('dialog', d => d.accept());
  await page.goto(`${origin}${S}/`);
  // "Paste LLM answer" is an entry of the bar's "With an LLM ▾" menu (a0.6.2): the menu is opened first
  await page.waitForSelector('#btn-paste-answer', {state: 'attached'});
  await page.click('#menu-llm > summary');
  const pasted = '---\ntitle: Grammar\nsubtitle:\nnote:\nlang: en\ntarget: en\n---\n\nPasted text.\n';
  await page.click('#btn-paste-answer');
  await page.fill('.modal textarea', pasted);
  await page.click('.modal [data-x="ok"]');
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(st.fields[1].key === 'incoming:new' && /being added/.test(st.fields[1].label),
         'Paste: the pasted document is the one being added');
  await page.click('.names-modal [data-x="cancel"]');
  await until(async () => (await page.$eval('.modal textarea', e => e.value).catch(() => '')) === pasted,
              'cancelling brings the paste back, text and all');
  assert(true, 'cancelling brings the paste back, text and all');
  await page.click('.modal [data-x="ok"]');
  await page.waitForSelector('.names-modal');
  await setField(page, 'incoming:new', 'Grammar, pasted');
  await Promise.all([page.waitForURL(/\/doc\/grammar-pasted-/), page.click('.names-modal [data-x="ok"]')]);
  assert((await page.textContent('.doc-title')) === 'Grammar, pasted', 'and made under the name given');

  await page.goto(`${origin}${S}/`);
  await page.waitForSelector('#file-upload', {state: 'attached'});
  await page.setInputFiles('#file-upload', {name: 'grammar.md', mimeType: 'text/markdown',
                                            buffer: Buffer.from(pasted.replace('Pasted', 'Uploaded'))});
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(/grammar\.md/.test(st.fields[1].label), 'Upload .md: the file is named in its field: ' + st.fields[1].label);
  await setField(page, 'existing:' + D.grammar, 'Grammar, first');
  await Promise.all([page.waitForURL(/\/doc\/grammar-/), page.click('.names-modal [data-x="ok"]')]);
  assert((await page.textContent('.doc-title')) === 'Grammar'
         && (await titleOf(D.grammar)) === 'Grammar, first',
         'the upload keeps its name, the one already there took the new one');

  // a new document's first save, from + New
  await page.goto(`${origin}${S}/new?target=en`);
  await page.waitForSelector('#src');
  await retitle(page, 'grammar');
  await page.click('#btn-save');
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(st.fields[1].key === 'incoming:new' && /being saved/.test(st.fields[1].label),
         '+ New: the first save of a new document is asked about too');
  await setField(page, 'incoming:new', 'Grammar, new');
  await Promise.all([page.waitForURL(/\/doc\/grammar-new-[0-9a-f]{6}\/edit$/), page.click('.names-modal [data-x="ok"]')]);
  assert(/^title: Grammar, new$/m.test(await page.$eval('#src', e => e.value)),
         'and made under the name given, which its text says');

  // a backup holding a document whose name another document has taken since
  const backup = Buffer.from(await (await fetch(`${origin}${S}/api/export`)).arrayBuffer());
  assert((await api('DELETE', `${S}/api/docs/${D.lonely}`)).status === 200, 'a document deleted through the API is answered OK');
  const impostor = (await api('POST', `${S}/api/docs`, {markdown: '---\ntitle: Lonely\ntarget: en\n---\n\nAnother one.\n'})).data.meta;
  assert(impostor && impostor.title === 'Lonely', 'a new document takes the deleted one\'s name');
  await page.goto(`${origin}${S}/`);
  await page.waitForSelector('#backup-file', {state: 'attached'});
  await page.setInputFiles('#backup-file', {name: 'backup.zip', mimeType: 'application/zip', buffer: backup});
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(st.fields.length === 2 && st.fields[0].key === 'existing:' + impostor.id
         && st.fields[1].key === 'incoming:' + D.lonely,
         'Load from backup: the backed-up document against the one that has its name now');
  await setField(page, 'existing:' + impostor.id, 'Lonely, too');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => /already here/.test(await page.textContent('#modal-root')), 'then the kept ones are counted');
  await page.click('[data-x="keep"]');
  await until(async () => /1 document restored/.test(await page.textContent('#toast')), 'restored: ' + await page.textContent('#toast'));
  assert((await titleOf(D.lonely)) === 'Lonely' && (await titleOf(impostor.id)) === 'Lonely, too',
         'the backup\'s document is back under its name, the other renamed');

  await page.goto(`${origin}${S}/doc/${D.grammar}`);
  await page.click('.topbar .dropdown:last-of-type summary');
  await Promise.all([page.waitForURL(u => !u.toString().endsWith(D.grammar)), page.click('#btn-duplicate')]);
  assert((await page.textContent('.doc-title')) === 'Grammar, first (copy)', 'Duplicate names its copy');
  const copyId = page.url().split('/doc/')[1];
  assert(/^title: Grammar, first \(copy\)$/m.test((await get(copyId)).markdown), 'in its front matter too');

  // ------------------------------------------------------------------ d)
  console.log('d) a book\'s notes');
  const second = info.notes_docs.second, first = info.notes_docs.first;
  await page.goto(`${origin}${N}/doc/${second}/edit`);
  await page.waitForSelector('#src');
  await retitle(page, 'A note');
  await page.click('#btn-save');
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(st.open[0] === `${N}/doc/${first}`, 'the note already there opens inside the notes: ' + st.open[0]);
  await setField(page, 'existing:' + first, 'The first note');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => (await page.textContent('#toast')) === 'Saved', 'Saved');
  assert((await titleOf(first, N)) === 'The first note' && (await titleOf(second, N)) === 'A note',
         'both notes renamed');
  assert((await page.$eval('#src', e => e.value)).includes('[the first note](doc:The first note)'),
         'the link the saved note had to the other follows the other');
  assert((await titleOf(D.grammar)) === 'Grammar, first', 'the studio\'s library is untouched');
  await page.goto(`${origin}${N}/doc/${first}`);
  await page.click('#btn-backlinks');
  await until(async () => (await drawerState(page)).visible, 'the notes drawer opens');
  st = await drawerState(page);
  assert(st.label === '↩ Linked from (1)' && JSON.stringify(st.docs) === JSON.stringify([['A note', `${N}/doc/${second}`]]),
         'a note\'s drawer lists the note that links to it, inside the notes: ' + JSON.stringify(st.docs));

  // ------------------------------------------------------------------ f)
  console.log('f) Load from backup, Replace: a name its first pass gave, taken back');
  const mk = async (title, body) => (await api('POST', `${S}/api/docs`,
    {markdown: `---\ntitle: ${title}\ntarget: en\n---\n\n${body}\n`})).data.meta;
  const alpha = await mk('RB Alpha', '[the delta](doc:RB Delta)');
  const delta = await mk('RB Delta', 'Backed up.');
  const rbBackup = Buffer.from(await (await fetch(`${origin}${S}/api/export`)).arrayBuffer());
  await api('PUT', `${S}/api/docs/${alpha.id}`,
            {markdown: (await get(alpha.id)).markdown.replace('title: RB Alpha', 'title: RB Gamma')});
  assert((await api('DELETE', `${S}/api/docs/${delta.id}`)).status === 200, 'so is another');
  const newer = await mk('RB Delta', 'A newer one.');
  await page.goto(`${origin}${S}/`);
  await page.waitForSelector('#backup-file', {state: 'attached'});
  await page.setInputFiles('#backup-file', {name: 'backup.zip', mimeType: 'application/zip', buffer: rbBackup});
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  assert(st.fields.length === 2 && st.fields[0].key === 'existing:' + newer.id
         && st.fields[1].key === 'incoming:' + delta.id,
         'the backup\'s Delta against the newer one');
  // the name the kept Alpha had in the backup: free, Alpha is Gamma now
  await setField(page, 'incoming:' + delta.id, 'RB Alpha');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => /already here/.test(await page.textContent('#modal-root')), 'then the kept ones are counted');
  await page.click('[data-x="replace"]');
  await page.waitForSelector('.names-modal');
  await sleep(100);
  st = await dialogState(page);
  if (SHOTS) await page.screenshot({path: `${SHOTS}/names-dialog-replace.png`});
  assert(await page.textContent('#names-title') === 'This name is already in use',
         'Replace them: the backup\'s Alpha takes its name back, and it is asked about');
  assert(st.fields.length === 2 && st.fields.every(f => f.onTop),
         'with a field for each of the two documents that want it: '
         + JSON.stringify(st.fields.map(f => [f.key, f.value])));
  const wants = st.fields.find(f => f.key === 'incoming:' + delta.id);
  assert(wants && wants.value === 'RB Alpha'
         && wants.problem === '“RB Alpha” is already the name of another document — choose another name',
         'the name the first pass gave, refused under its own field: ' + JSON.stringify(wants));
  assert(st.fields.some(f => f.key === 'incoming:' + alpha.id && f.value === 'RB Alpha' && !f.problem),
         'beside the backup\'s Alpha, which holds it');
  await setField(page, 'incoming:' + delta.id, 'RB Delta, backed up');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => /restored/.test(await page.textContent('#toast')), 'restored');
  assert((await titleOf(alpha.id)) === 'RB Alpha' && (await titleOf(delta.id)) === 'RB Delta, backed up'
         && (await titleOf(newer.id)) === 'RB Delta',
         'every document under the name it was given, the kept one replaced');
  assert((await get(alpha.id)).markdown.includes('[the delta](doc:RB Delta, backed up)'),
         'and the backup\'s link follows the backup\'s document');

  // ------------------------------------------------------------------ g)
  console.log('g) a name holding "|" is asked about');
  const bar = await mk('Bar test', 'A document to rename.');
  await page.goto(`${origin}${S}/doc/${bar.id}/edit`);
  await page.waitForSelector('#src');
  await retitle(page, 'Bar | test');
  await page.click('#btn-save');
  await page.waitForSelector('.names-modal');
  st = await dialogState(page);
  if (SHOTS) await page.screenshot({path: `${SHOTS}/names-dialog-bar.png`});
  assert(await page.textContent('#names-title') === 'This name cannot be used',
         'the dialog says the name cannot be used (no other document has it)');
  assert(st.fields.length === 1 && st.fields[0].key === 'incoming:' + bar.id
         && st.fields[0].value === 'Bar | test' && st.fields[0].onTop,
         'with one field, for the document being saved: ' + JSON.stringify(st.fields.map(f => [f.key, f.value])));
  assert(/cannot hold “\|”/.test(st.fields[0].problem), 'and why, under it: ' + st.fields[0].problem);
  assert((await titleOf(bar.id)) === 'Bar test', 'nothing written');
  await setField(page, 'incoming:' + bar.id, 'Bar, test');
  await page.click('.names-modal [data-x="ok"]');
  await until(async () => (await page.textContent('#toast')) === 'Saved', 'Saved');
  assert((await titleOf(bar.id)) === 'Bar, test'
         && /^title: Bar, test$/m.test(await page.$eval('#src', e => e.value)),
         'saved under the name given, which the editor\'s text says');

  // ------------------------------------------------------------------ h)
  console.log('h) an editor left open, a rename in another tab');
  const renamed = await mk('Open target', 'Renamed in another tab.');
  const linking = await mk('Open linker', 'See [the target](doc:Open target).');
  const tab1 = await ctx.newPage(), tab2 = await ctx.newPage();
  for (const t of [tab1, tab2]) t.on('pageerror', e => errors.push(e.message));
  await tab1.goto(`${origin}${S}/doc/${linking.id}/edit`);
  await tab1.waitForSelector('#src');
  const rename = async title => {
    await tab2.goto(`${origin}${S}/doc/${renamed.id}/edit`);
    await tab2.waitForSelector('#src');
    await retitle(tab2, title);
    await tab2.click('#btn-save');
    await until(async () => (await tab2.textContent('#toast')) === 'Saved', 'tab 2 saved');
  };
  const typeAndSave = async line => {
    await tab1.evaluate(() => { const s = document.querySelector('#src'); s.focus();
                                s.setSelectionRange(s.value.length, s.value.length); });
    await tab1.keyboard.type(line);
    await tab1.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await tab1.click('#btn-save');
    await until(async () => (await tab1.textContent('#toast')) === 'Saved', 'tab 1 saved');
  };
  await rename('Open target, renamed');
  assert((await get(linking.id)).markdown.includes('[the target](doc:Open target, renamed)'),
         'the rename in tab 2 rewrote the link on disk');
  await typeAndSave('\nA line typed in the open editor.');
  let written = (await get(linking.id)).markdown;
  assert(written.includes('See [the target](doc:Open target, renamed).')
         && written.includes('A line typed in the open editor.'),
         'tab 1, open all along, saves its line and keeps the link that followed: '
         + written.split('\n').slice(-3).join(' | '));
  assert((await tab1.$eval('#src', e => e.value)) === written, 'and tab 1 holds the text as written');
  await rename('Open target, again');
  await typeAndSave('\nAnother line.');
  written = (await get(linking.id)).markdown;
  assert(written.includes('See [the target](doc:Open target, again).') && written.includes('Another line.'),
         'a second rename, a second save: followed from where the editor stood');
  await tab1.goto(`${origin}${S}/doc/${renamed.id}`);
  assert((await drawerState(tab1)).label === '↩ Linked from (1)', 'and the document is still linked from there');
  await tab1.close(); await tab2.close();

  assert(!errors.length, 'no script error on any page: ' + errors.join(' | '));
  console.log(`\n${passed} passed`);
} catch (e) {
  console.error(e.message);
  console.error(log.join('').slice(-3000));
  Deno.exitCode = 1;
} finally {
  await browser.close();
  try { proc.kill('SIGTERM'); } catch (_) { /* gone */ }
  await proc.status;
}
