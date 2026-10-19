// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of a file from the computer, open in the studio (a0.5.2), driven where it is used -- the library
// page's file browser, a file's own pages, the editor -- against the REAL routes on temporary folders
// (tests/openfile_harness.py), in both hosts: the studio on its own, and Parseh's /studio.
//   a) the library page offers "Open a file…"; the browser lists a folder (folders first, only what the studio
//      opens), goes in and up, and takes a typed path; choosing a file opens it on its own pages
//   b) a file's pages say which file it is and that it holds what the page holds; the library's own business
//      (duplicate, delete) is not offered
//   c) the editor's Save writes the working copy AND the file, byte for byte but for the change (a Windows file keeps
//      its mark and its line ends); nothing is written before that
//   d) a change made on the document page (a tag) is "not saved to the file yet"; saving asks what a Markdown file
//      cannot hold and offers the zip beside it or the text alone; the .md is never rewritten into the zip
//   e) a zip is patched: its other entries come back byte for byte; a zip of several documents asks which
//   f) the file changed behind our back is not overwritten without a word; Load it again; Save as…
//   g) closing: nothing unsaved closes at once and deletes the copy, unsaved asks; the files open now are listed
//   h) a path that cannot be opened says why and lets the person choose again
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/openfile.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want), m + ' (got ' + JSON.stringify(got) + ')');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function startHarness(mode, extra = []) {
  const proc = new Deno.Command(python, {args: [root + '/tests/openfile_harness.py', mode, ...extra], cwd: root,
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

/* a zip's entries, and one entry's bytes, read by python (the suite has no zip reader of its own) */
async function zipInfo(path) {
  const code = `import zipfile,sys,json,hashlib
z=zipfile.ZipFile(sys.argv[1])
print(json.dumps({i.filename:[hashlib.sha256(z.read(i)).hexdigest(), list(i.date_time), i.external_attr, i.compress_type] for i in z.infolist()}))`;
  const out = await new Deno.Command(python, {args: ['-c', code, path], stdout: 'piped'}).output();
  return JSON.parse(new TextDecoder().decode(out.stdout));
}
async function zipText(path, name) {
  const code = `import zipfile,sys
sys.stdout.buffer.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))`;
  const out = await new Deno.Command(python, {args: ['-c', code, path, name], stdout: 'piped'}).output();
  return new TextDecoder().decode(out.stdout);
}
const names = async path => Object.keys(await zipInfo(path));
const exists = async path => { try { await Deno.stat(path); return true; } catch { return false; } };
async function openDirCount(dir) {
  let n = 0;
  try { for await (const e of Deno.readDir(dir)) if (e.isDirectory) n++; } catch { /* not made yet */ }
  return n;
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN') || undefined, headless: true});
const errors = [];

// the harness is stopped, and its temporary tree with it, whatever the checks found
async function suite(mode, opts = {}) {
  const {proc, info} = await startHarness(mode, opts.remote ? ['remote'] : []);
  try { await runSuite(mode, info, opts); } finally { proc.kill('SIGTERM'); await proc.status; }
}

async function runSuite(mode, info, opts = {}) {
  console.log(`\n=== ${opts.remote ? 'another device, let in (the studio on its own)' : mode === 'parseh' ? 'Parseh (/studio)' : 'the studio on its own'} ===`);
  const B = `http://127.0.0.1:${info.port}`, S = info.studio, mine = info.mine, sep = info.sep;
  const file = name => mine + sep + name;
  const ctx = await browser.newContext({viewport: {width: 1280, height: 900}});
  const newPage = async path => {
    const p = await ctx.newPage();
    p.on('pageerror', e => errors.push(mode + ' ' + path + ': ' + e.message));
    p.on('dialog', d => d.dismiss());
    await p.goto(B + path);
    return p;
  };
  const toastText = async (p, re, ms = 8000) => {
    await p.waitForFunction(re => { const t = document.querySelector('#toast'); return t && !t.hidden && new RegExp(re).test(t.textContent); },
                            re.source, {timeout: ms});
  };
  const refresh = p => p.evaluate(() => window.dispatchEvent(new Event('focus')));
  const barSays = async (p, re, ms = 8000) => {
    await refresh(p);
    await p.waitForFunction(re => new RegExp(re).test(document.querySelector('#filebar .fb-state').textContent), re.source, {timeout: ms});
  };
  const dialogTitle = p => p.locator('.of-modal h3').textContent();
  const clickButton = (p, label) => p.locator('.of-modal .of-buttons button', {hasText: label}).first().click();
  const sid = p => new URL(p.url()).pathname.match(/\/open\/([0-9a-f]{12})\//)[1];
  // the bar learns the file's state from the server a moment after the page is drawn
  const barName = async p => {
    await p.waitForFunction(() => document.querySelector('#filebar .fb-name') && document.querySelector('#filebar .fb-name').textContent);
    return p.locator('#filebar .fb-name').textContent();
  };
  const barWhere = async p => { await barName(p); return p.locator('#filebar .fb-where').textContent(); };

  // open a file from the library page through the browser's typed path, and arrive at its reading page
  const openTyped = async (lib, path) => {
    await lib.locator('#btn-open-file').click();
    await lib.waitForSelector('.of-modal .of-path');
    await lib.fill('.of-path', path);
    await lib.press('.of-path', 'Enter');
    await lib.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
  };
  const library = async () => {
    const p = await newPage(S + '/');
    await p.waitForSelector('#btn-open-file:not([hidden])');
    return p;
  };

  // ------------------------------------------------------------------ r) another device, let in
  if (opts.remote) {
    console.log('r) another device that is let in uses it too, and is told whose disk it sees');
    assert(info.remote === true, 'the studio takes this browser for another device');
    const far = await library();
    assert(await far.locator('#btn-open-file').isVisible(), 'the library offers "Open a file…" to it as well');
    await far.locator('#btn-open-file').click();
    await far.waitForSelector('.of-modal .of-path');
    await far.waitForFunction(h => document.querySelector('.of-modal h3').textContent.includes(h), info.host);
    assert((await dialogTitle(far)).includes('Open a file on ' + info.host), 'the window says whose disk it shows: ' + await dialogTitle(far));
    await far.fill('.of-path', file('lesson.md'));
    await far.press('.of-path', 'Enter');
    await far.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
    assert((await barWhere(far)).includes(' on ' + info.host), 'the bar says the file is on that computer: ' + await barWhere(far));
    await far.locator('a.btn', {hasText: 'Edit'}).first().click();
    await far.waitForSelector('#src');
    const before = await Deno.readTextFile(file('lesson.md'));
    await far.fill('#src', before + '\nWritten from another device.\n');
    await far.locator('#btn-save').click();
    await toastText(far, /Saved to lesson\.md/);
    eq(await Deno.readTextFile(file('lesson.md')), before + '\nWritten from another device.\n', 'and Save writes the file on the computer Parseh runs on');
    await far.locator('#filebar .fb-saveas').click();
    await far.waitForSelector('.of-modal .of-name');
    assert((await dialogTitle(far)).includes('on ' + info.host), 'Save as… says whose disk too: ' + await dialogTitle(far));
    await far.keyboard.press('Escape');
    await far.locator('#filebar .fb-close').click();
    await far.waitForURL(u => !/\/open\//.test(u.pathname));
    await ctx.close();
    return;
  }

  // ------------------------------------------------------------------ a) the library page and the browser
  console.log('a) the library page and the file browser');
  let lib = await library();
  assert(await lib.locator('#btn-open-file').isVisible(), 'the library offers "Open a file…" to this computer');
  assert(await lib.locator('#open-files').isHidden(), 'and lists no file open: there is none');
  await lib.locator('#btn-open-file').click();
  await lib.waitForSelector('.of-modal .of-row');
  assert((await dialogTitle(lib)).includes('Open a file'), 'a window with a file browser opens');
  assert(await lib.locator('.of-place').count() >= 2, 'with places to start from');
  await lib.fill('.of-path', mine + sep);
  await lib.press('.of-path', 'Enter');
  await lib.waitForFunction(() => [...document.querySelectorAll('.of-list .of-n')].some(n => n.textContent === 'lesson.md'));
  const listed = await lib.$$eval('.of-list .of-n', els => els.map(e => e.textContent));
  eq(listed, ['Up one folder', 'images', 'notes', 'course.zip', 'lesson.md', 'pictures.md', 'two.zip', 'windows.md', 'درس.md'],
     'a folder lists its folders first, then the files the studio opens (the PDF is not among them), in natural order');
  await lib.locator('.of-row', {hasText: 'notes'}).first().click();
  await lib.waitForFunction(() => [...document.querySelectorAll('.of-list .of-n')].some(n => n.textContent === 'deep.md'));
  assert((await lib.inputValue('.of-path')).endsWith('notes' + sep), 'clicking a folder goes in, and the path box follows');
  await lib.locator('.of-up').click();
  await lib.waitForFunction(() => [...document.querySelectorAll('.of-list .of-n')].some(n => n.textContent === 'lesson.md'));
  // a double-click on a folder goes in once (as in every file dialog), and the second click does not land on the new list
  await lib.locator('.of-row', {hasText: 'notes'}).first().dblclick();
  await lib.waitForFunction(() => [...document.querySelectorAll('.of-list .of-n')].some(n => n.textContent === 'deep.md'));
  await sleep(400);
  assert((await lib.inputValue('.of-path')).endsWith('notes' + sep), 'a double-click on a folder goes in once, and stays there');
  await lib.locator('.of-up').click();
  await lib.waitForFunction(() => [...document.querySelectorAll('.of-list .of-n')].some(n => n.textContent === 'lesson.md'));
  await lib.locator('.of-row', {hasText: 'lesson.md'}).first().click();
  eq(await lib.locator('.of-chosen').textContent(), 'lesson.md', 'a click on a file chooses it');
  await clickButton(lib, 'Open');
  await lib.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
  assert(lib.url().includes(`${S}/open/`), 'it opens on its own pages, under ' + (S || '/') + 'open/<id>/');
  assert(await openDirCount(info.open_dir) === 1, 'the studio made a working copy in its temporary folder');

  // ------------------------------------------------------------------ b) the file's pages
  console.log('b) the file\'s own pages');
  let doc = lib;
  await doc.waitForSelector('#filebar .fb-state');
  eq(await barName(doc), 'lesson.md', 'the bar names the file');
  assert((await barWhere(doc)).includes(mine), 'and the folder it is in');
  await barSays(doc, /Saved/);
  assert(await doc.locator('#filebar').getAttribute('data-tone') === 'ok', 'it holds what the page holds');
  eq(await doc.locator('.doc-title').textContent(), 'A lesson', 'the page is the studio\'s own, on the file');
  assert(await doc.locator('#btn-duplicate').isHidden() && await doc.locator('#btn-delete').isHidden(),
         'Duplicate and Delete — the library\'s business — are not offered for a file');
  assert((await doc.locator('a.btn.ghost', {hasText: 'Library'}).first().getAttribute('href')) === (S || '') + '/',
         'and "Library" leads to the studio\'s library, not to this one document');
  assert(await lib.evaluate(() => !!window.ParsehFile && window.ParsehFile.active), 'the editor can ask the page to write the file');
  assert(await Deno.readTextFile(file('lesson.md')) .then(t => t.includes('The cat sat on the mat.')), 'and the file has not been touched');

  // ------------------------------------------------------------------ c) the editor writes the file
  console.log('c) the editor');
  await doc.locator('a.btn', {hasText: 'Edit'}).first().click();
  await doc.waitForSelector('#src');
  assert((await doc.inputValue('#src')).includes('Hello there.'), 'the editor holds the file\'s text');
  await doc.locator('#filebar').waitFor({timeout: 8000});
  assert(await doc.locator('#filebar').isVisible(), 'and the bar is there too');
  const before = await Deno.readTextFile(file('lesson.md'));
  await doc.fill('#src', before + '\nAdded in the editor.\n');
  eq(await Deno.readTextFile(file('lesson.md')), before, 'nothing is written while typing');
  await doc.locator('#btn-save').click();
  await toastText(doc, /Saved to lesson\.md/);
  eq(await Deno.readTextFile(file('lesson.md')), before + '\nAdded in the editor.\n', 'Save wrote the file: the text, and only that');
  await barSays(doc, /Saved/);
  assert(await openDirCount(info.open_dir) === 1, 'the working copy is still the one');
  // saving again with nothing new writes nothing
  const m1 = (await Deno.stat(file('lesson.md'))).mtime.getTime();
  await sleep(50);
  await doc.locator('#btn-save').click();
  await toastText(doc, /Saved to lesson\.md|Nothing new/);
  eq((await Deno.stat(file('lesson.md'))).mtime.getTime(), m1, 'a save of nothing new leaves the file as it is');
  // a Windows file keeps its mark and its line ends
  const win = await library();
  await openTyped(win, file('windows.md'));
  await win.locator('a.btn', {hasText: 'Edit'}).first().click();
  await win.waitForSelector('#src');
  const w0 = await win.inputValue('#src');
  assert(!w0.includes('\r'), 'the editor works on \\n');
  await win.fill('#src', w0 + 'Third line.\n');
  await win.locator('#btn-save').click();
  await toastText(win, /Saved to windows\.md/);
  const wb = await Deno.readFile(file('windows.md'));
  assert(wb[0] === 0xEF && wb[1] === 0xBB && wb[2] === 0xBF, 'the byte order mark is kept');
  const wt = new TextDecoder().decode(wb.slice(3));
  assert(wt.split('\r\n').length > 3 && !/[^\r]\n/.test(wt), 'and every line end is still CRLF, the new line\'s too');
  // a Persian file name
  const fa = await library();
  await openTyped(fa, file('درس.md'));
  eq(await barName(fa), 'درس.md', 'a file with a Persian name opens, under its own name');
  await fa.locator('#filebar .fb-close').click();
  await fa.waitForURL(u => !/\/open\//.test(u.pathname));
  await win.locator('#filebar .fb-close').click();
  await win.waitForURL(u => !/\/open\//.test(u.pathname));

  // ------------------------------------------------------------------ c2) the bar on the editor's page
  console.log('c2) the bar on the editor\'s page');
  const ed = await library();
  await openTyped(ed, file('notes' + sep + 'deep.md'));
  await ed.locator('a.btn', {hasText: 'Edit'}).first().click();
  await ed.waitForSelector('#src');
  await barName(ed);
  const base = await ed.inputValue('#src');
  await ed.fill('#src', base + '\nTyped, and not saved anywhere.\n');
  await ed.locator('#filebar .fb-save').click();
  await toastText(ed, /Saved to deep\.md/);
  assert((await Deno.readTextFile(file('notes' + sep + 'deep.md'))).endsWith('Typed, and not saved anywhere.\n'),
         '"Save to file" on the editor\'s page is the editor\'s own Save: the typed text reaches the file');
  await ed.fill('#src', base + '\nTyped, and not saved anywhere.\nAnd a bit more.\n');
  await ed.locator('#filebar .fb-saveas').click();
  await ed.waitForSelector('.of-modal .of-name');
  await ed.fill('.of-name', 'typed-copy.md');
  await clickButton(ed, 'Save');
  await toastText(ed, /Saved to typed-copy\.md/);
  assert((await Deno.readTextFile(file('notes' + sep + 'typed-copy.md'))).endsWith('And a bit more.\n'), '"Save as…" saves the typing first, then writes the new file');
  eq(await barName(ed), 'typed-copy.md', 'and the page stands for the new file');
  await ed.fill('#src', base + '\nTyped again, and thrown away.\n');
  await ed.locator('#filebar .fb-close').click();
  await ed.waitForSelector('.of-modal');
  assert((await dialogTitle(ed)).startsWith('Close typed-copy.md'), 'closing with typed text asks first, before the server has anything to say');
  await clickButton(ed, 'Keep working');
  assert((await ed.inputValue('#src')).includes('thrown away'), 'and keeps the typing when told to');
  await ed.locator('#filebar .fb-close').click();
  await ed.waitForSelector('.of-modal');
  await clickButton(ed, 'Close without saving');
  await ed.waitForURL(u => !/\/open\//.test(u.pathname));
  assert(!(await Deno.readTextFile(file('notes' + sep + 'typed-copy.md'))).includes('thrown away'), 'throwing it away leaves the file as it was');
  assert(await openDirCount(info.open_dir) === 1, 'and closes only that file\'s copy');

  // ------------------------------------------------------------------ d) what a Markdown file cannot hold
  console.log('d) what a Markdown file cannot hold');
  await doc.goto(B + new URL(doc.url()).pathname.replace(/\/edit$/, ''));
  await doc.waitForSelector('#tag-input');
  await doc.fill('#tag-input', 'verbs');
  await doc.press('#tag-input', 'Enter');
  await doc.waitForSelector('#tag-chips >> text=verbs');
  await barSays(doc, /not saved to the file yet/);
  assert(await doc.locator('#filebar .fb-save').evaluate(b => b.classList.contains('primary')), 'a tag is a change the file does not hold: Save to file is the thing to press');
  const beforeTags = await Deno.readTextFile(file('lesson.md'));
  await doc.locator('#filebar .fb-save').click();
  await doc.waitForSelector('.of-modal');
  assert((await dialogTitle(doc)).includes('cannot hold all of this'), 'saving asks: a Markdown file cannot hold tags');
  assert((await doc.locator('.of-left').textContent()).includes('verbs'), 'and names them');
  assert((await doc.inputValue('.of-zip')).endsWith(sep + 'lesson.zip'), 'offering the zip beside it, with a name to change');
  // the browser opened from the question closes alone on Escape, and the question stays
  await doc.locator('.of-modal button', {hasText: 'Browse'}).click();
  await doc.waitForSelector('.of-modal .of-name');
  await doc.keyboard.press('Escape');
  await doc.waitForFunction(() => document.querySelectorAll('.of-modal').length === 1);
  assert((await dialogTitle(doc)).includes('cannot hold all of this'), 'Escape closes the browser opened from the question, and the question stays');
  await clickButton(doc, 'Save the text only');
  await toastText(doc, /Nothing to write|stay out|Saved/);
  eq(await Deno.readTextFile(file('lesson.md')), beforeTags, 'the text only: the Markdown file is as it was');
  await barSays(doc, /Saved/);
  // a second tag changes what is left out: asked again, this time as a zip
  await doc.fill('#tag-input', 'a1');
  await doc.press('#tag-input', 'Enter');
  await barSays(doc, /not saved to the file yet/);
  await doc.locator('#filebar .fb-save').click();
  await doc.waitForSelector('.of-modal');
  await clickButton(doc, 'Save as zip');
  await toastText(doc, /Saved as lesson\.zip/);
  eq((await names(file('lesson.zip'))).sort(), ['lesson.md', 'lesson.tags.json'], 'the zip holds the Markdown and its tags, in the library\'s own layout');
  eq(await Deno.readTextFile(file('lesson.md')), beforeTags, 'and lesson.md itself is untouched');
  assert(JSON.parse(await zipText(file('lesson.zip'), 'lesson.tags.json')).tags.join() === 'a1,verbs', 'with the tags in it');
  eq(await doc.locator('#filebar .fb-name').textContent(), 'lesson.zip', 'the page now stands for the zip');
  await barSays(doc, /Saved/);
  // from here it is a zip like any other
  await doc.locator('a.btn', {hasText: 'Edit'}).first().click();
  await doc.waitForSelector('#src');
  await doc.fill('#src', (await doc.inputValue('#src')) + '\nIn the zip now.\n');
  await doc.locator('#btn-save').click();
  await toastText(doc, /Saved to lesson\.zip/);
  assert((await zipText(file('lesson.zip'), 'lesson.md')).includes('In the zip now.'), 'a later save writes into the zip');
  // closing a saved file closes at once
  await doc.locator('#filebar .fb-close').click();
  await doc.waitForURL(u => !/\/open\//.test(u.pathname));
  assert(doc.url().replace(B, '').startsWith(S + '/'), 'closing goes to the library');
  await sleep(200);
  eq(await openDirCount(info.open_dir), 0, 'and the working copy is deleted');

  // ------------------------------------------------------------------ e) zips
  console.log('e) zips');
  lib = await library();
  await openTyped(lib, file('course.zip'));
  eq(await barName(lib), 'course.zip', 'a zip opens');
  assert((await barWhere(lib)).includes('course.md in the zip'), 'saying which document in it');
  assert((await lib.locator('#tag-chips').textContent()).includes('verbs'), 'its tags are the document\'s tags');
  const pictureShown = (pg) => pg.waitForFunction(() => [...document.images].some(i => i.src.includes('/media/') && i.naturalWidth > 0), null, {timeout: 8000}).then(() => true, () => false);
  assert(await pictureShown(lib), 'and its picture is shown');
  const zipBefore = await zipInfo(file('course.zip'));
  await lib.locator('a.btn', {hasText: 'Edit'}).first().click();
  await lib.waitForSelector('#src');
  await lib.fill('#src', (await lib.inputValue('#src')) + '\nMore.\n');
  await lib.locator('#btn-save').click();
  await toastText(lib, /Saved to course\.zip/);
  const zipAfter = await zipInfo(file('course.zip'));
  eq(Object.keys(zipAfter), Object.keys(zipBefore), 'a zip keeps its entries and their order');
  for (const n of Object.keys(zipBefore)) {
    if (n === 'course.md') assert(zipAfter[n][0] !== zipBefore[n][0], 'the document changed');
    else eq(zipAfter[n], zipBefore[n], n + ' came back byte for byte, with its date and mode');
  }
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForURL(u => !/\/open\//.test(u.pathname));
  // a zip of several documents asks which
  lib = await library();
  await lib.locator('#btn-open-file').click();
  await lib.waitForSelector('.of-modal .of-path');
  await lib.fill('.of-path', file('two.zip'));
  await lib.press('.of-path', 'Enter');
  await lib.waitForSelector('.of-modal .dl-item');
  assert((await dialogTitle(lib)).includes('Which document in two.zip'), 'a zip of several documents asks which');
  eq(await lib.$$eval('.dl-item .dl-t', els => els.map(e => e.textContent)), ['First one', 'Second one'], 'by their titles');
  await lib.locator('.dl-item', {hasText: 'Second one'}).click();
  await lib.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
  assert((await barWhere(lib)).includes('second.md in the zip'), 'and opens that one');
  const twoBefore = await zipInfo(file('two.zip'));
  await lib.locator('a.btn', {hasText: 'Edit'}).first().click();
  await lib.waitForSelector('#src');
  await lib.fill('#src', (await lib.inputValue('#src')) + '\nSecond, changed.\n');
  await lib.locator('#btn-save').click();
  await toastText(lib, /Saved to two\.zip/);
  const twoAfter = await zipInfo(file('two.zip'));
  eq([twoAfter['first.md'], twoAfter['data.csv']], [twoBefore['first.md'], twoBefore['data.csv']], 'the other document and the data are as they were');
  assert(twoAfter['second.md'][0] !== twoBefore['second.md'][0], 'only the document opened changed');
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForURL(u => !/\/open\//.test(u.pathname));

  // pictures beside a Markdown file are shown, and the file saves without a question
  lib = await library();
  await openTyped(lib, file('pictures.md'));
  assert(await pictureShown(lib), 'the picture beside the Markdown file is shown');
  await lib.locator('a.btn', {hasText: 'Edit'}).first().click();
  await lib.waitForSelector('#src');
  await lib.fill('#src', (await lib.inputValue('#src')) + '\nAnd more.\n');
  await lib.locator('#btn-save').click();
  await toastText(lib, /Saved to pictures\.md/);
  assert((await Deno.readTextFile(file('pictures.md'))).endsWith('And more.\n'), 'it saves with no question: the picture is beside the file already');
  assert(await exists(file('images') + sep + 'cat.png'), 'and the picture was not moved or copied');

  // ------------------------------------------------------------------ f) somebody else changed the file
  console.log('f) the file changed behind our back');
  await lib.fill('#src', (await lib.inputValue('#src')) + 'Mine, unsaved to the file.\n');
  await Deno.writeTextFile(file('pictures.md'), 'Written by another program.\n');
  await lib.locator('#btn-save').click();
  await lib.waitForSelector('.of-modal');
  assert((await dialogTitle(lib)).includes('changed on disk'), 'saving says the file changed on disk');
  await clickButton(lib, 'Cancel');
  await toastText(lib, /not to pictures\.md yet/);
  eq(await Deno.readTextFile(file('pictures.md')), 'Written by another program.\n', 'and does not replace it');
  await barSays(lib, /changed on disk, and you have changes/);
  await lib.locator('#filebar .fb-save').click();
  await lib.waitForSelector('.of-modal');
  await clickButton(lib, 'Replace it with my version');
  await toastText(lib, /Saved to pictures\.md/);
  assert((await Deno.readTextFile(file('pictures.md'))).includes('Mine, unsaved to the file.'), 'the person can choose to replace it');
  // a file changed while the page holds nothing new: it can be loaded again
  await Deno.writeTextFile(file('pictures.md'), '---\ntitle: Rewritten\nlang: en\ntarget: fa\n---\n\nNew from outside.\n');
  await barSays(lib, /changed on disk since you opened it/);
  assert(await lib.locator('#filebar .fb-reload').isVisible(), '"Load it again" is offered');
  await lib.locator('#filebar .fb-reload').click();
  await lib.waitForFunction(() => /Rewritten/.test(document.title) || /New from outside/.test(document.body.textContent || ''), null, {timeout: 15000});
  assert(await openDirCount(info.open_dir) === 1, 'the old copy was replaced, not added to');
  // Save as…
  await lib.goto(B + new URL(lib.url()).pathname.replace(/\/edit$/, ''));
  await barName(lib);
  await lib.locator('#tag-input').fill('x');
  await lib.press('#tag-input', 'Enter');
  await lib.locator('#filebar .fb-saveas').click();
  await lib.waitForSelector('.of-modal .of-name');
  assert((await dialogTitle(lib)).includes('Save as'), 'Save as… is the browser again, with a name to type');
  assert((await lib.inputValue('.of-name')) === 'pictures.md', 'offering the current name');
  await lib.fill('.of-name', 'copy.zip');
  await clickButton(lib, 'Save');
  await toastText(lib, /Saved as copy\.zip/);
  assert(await exists(file('copy.zip')), 'and the copy is there');
  eq(await lib.locator('#filebar .fb-name').textContent(), 'copy.zip', 'the page stands for the copy now');
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForURL(u => !/\/open\//.test(u.pathname));

  // ------------------------------------------------------------------ g) closing, and the files open now
  console.log('g) closing');
  lib = await library();
  await openTyped(lib, file('lesson.md'));
  const keep = await Deno.readTextFile(file('lesson.md'));
  await lib.fill('#tag-input', 'unsaved');
  await lib.press('#tag-input', 'Enter');
  await barSays(lib, /not saved to the file yet/);
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForSelector('.of-modal');
  assert((await dialogTitle(lib)).startsWith('Close lesson.md'), 'closing with something unsaved asks first');
  await clickButton(lib, 'Keep working');
  assert(await lib.locator('#filebar').isVisible() && await openDirCount(info.open_dir) === 1, 'and keeps working when told to');
  // the files open now, on the library page
  const idOfLesson = sid(lib);
  const lib2 = await library();
  await lib2.waitForSelector('#open-files:not([hidden]) .of-open');
  assert((await lib2.locator('#open-files').textContent()).includes('lesson.md'), 'the library lists the file open now');
  assert((await lib2.locator('#open-files .of-open-s').first().textContent()).includes('not saved'), 'saying it has changes the file does not');
  await lib2.locator('#open-files .of-open a.btn', {hasText: 'Read'}).click();
  await lib2.waitForURL(new RegExp('/open/' + idOfLesson + '/doc/'));
  await lib2.close();
  const lib3 = await library();
  await lib3.waitForSelector('#open-files .of-open');
  await lib3.locator('#open-files .of-open button', {hasText: 'Close'}).click();
  await lib3.waitForSelector('.dk-modal');
  await lib3.locator('.dk-modal button', {hasText: 'Close without saving'}).click();
  await lib3.waitForSelector('#open-files', {state: 'hidden'});
  eq(await Deno.readTextFile(file('lesson.md')), keep, 'closing without saving left the file as it was');
  await sleep(200);
  eq(await openDirCount(info.open_dir), 0, 'and deleted the copy');
  await refresh(lib);
  await lib.waitForFunction(() => /closed in another window/.test(document.querySelector('#filebar .fb-state').textContent), null, {timeout: 8000});
  assert(true, 'a page of a file closed elsewhere says so, and does not pretend');
  assert(await lib.locator('#filebar .fb-save').isDisabled(), 'and cannot save into nothing');
  const gone404 = await (await fetch(B + new URL(lib.url()).pathname)).status;
  eq(gone404, 404, 'and its address is not found any more');

  // ------------------------------------------------------------------ h) a path that cannot be opened
  console.log('h) refusals');
  lib = await library();
  await lib.locator('#btn-open-file').click();
  await lib.waitForSelector('.of-modal .of-path');
  await lib.fill('.of-path', mine + sep + 'no' + sep + 'such' + sep + 'file.md');
  await lib.press('.of-path', 'Enter');
  await lib.waitForFunction(() => { const t = document.querySelector('.of-status'); return t && /not there/.test(t.textContent); });
  assert((await lib.inputValue('.of-path')).startsWith(mine), 'a path that is not there goes to the nearest folder that is, and says so');
  await lib.fill('.of-path', file('readme.pdf'));
  await lib.press('.of-path', 'Enter');
  await lib.waitForFunction(() => { const h = document.querySelector('.of-modal h3'); return h && /did not open/.test(h.textContent); });
  assert(/opens Markdown/.test(await lib.locator('.of-bad').textContent()), 'a file of another kind says what the studio opens');
  await clickButton(lib, 'Choose another file');
  await lib.waitForSelector('.of-modal .of-path');
  await lib.keyboard.press('Escape');
  await lib.waitForSelector('.of-modal', {state: 'detached'});
  assert(await openDirCount(info.open_dir) === 0, 'nothing was opened');
  // a path typed and the Open button pressed (not Enter) is the path asked for
  await lib.locator('#btn-open-file').click();
  await lib.waitForSelector('.of-modal .of-path');
  await lib.fill('.of-path', file('pictures.md'));
  await clickButton(lib, 'Open');
  await lib.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
  eq(await barName(lib), 'pictures.md', 'a path typed and the Open button pressed opens that file');
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForURL(u => !/\/open\//.test(u.pathname));
  lib = await library();
  // the files opened lately are offered again, one click each
  await lib.locator('#btn-open-file').click();
  await lib.waitForSelector('.of-modal .of-place');
  assert(await lib.locator('.of-recent').count() >= 3, 'the dialog offers the files opened lately');
  await lib.locator('.of-recent', {hasText: 'lesson.md'}).first().click();
  await lib.waitForURL(/\/open\/[0-9a-f]{12}\/doc\//);
  eq(await barName(lib), 'lesson.md', 'a click on one opens it');
  await lib.locator('#filebar .fb-close').click();
  await lib.waitForURL(u => !/\/open\//.test(u.pathname));

  // the library holds nothing of all this
  const listing = await (await fetch(`${B}${S}/api/docs`)).json();
  eq(listing.docs, [], 'the studio\'s own library was never written to');
  await ctx.close();
}

try {
  await suite('studio');
  await suite('parseh');
  await suite('studio', {remote: true});
  assert(errors.length === 0, 'no page script error: ' + errors.join(' | '));
  console.log(`\n${passed} checks passed`);
} finally {
  await browser.close();
}
