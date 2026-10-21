// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the pictures and the recording the starters show
// (markdown/exlex/starters/assets/), against the REAL routes on a temporary
// library (tests/studio_harness.py):
//   a) in every language, the editor of a document not saved yet (/new) shows
//      a starter's picture and plays its recording wherever the dialect puts
//      one -- a line of its own, a card, an exercise -- loaded from where the
//      starters keep them; a picture of the document's own is a placeholder;
//      Images… and Recordings… say "Save the document first" and list nothing
//   b) the first Save gives the document its own copy of each file it names
//      (the bytes the starters ship), the editor and the document page then
//      show the document's copies, and Images… / Recordings… list them in use
//   c) a document saved before naming one shows it at once in the preview,
//      and the next Save copies it in
//   d) a copy deleted with ✕ in Images… or Recordings… stays deleted: the
//      editor shows it missing at once, as the document page does, and the
//      next Save does not bring it back
//   e) one deleted and another picture uploaded under its name: the editor
//      draws the new picture at once, not the one it drew there before; the
//      Save keeps the owner's, and the document page shows it
// Two modes, as tests/studio_audio.mjs: the studio's own server and Parseh's.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/studio_starter_media.mjs
//   STARTER_MEDIA_MODES=studio (or parseh) runs one; SHOTS=<dir> saves screenshots
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('STARTER_MEDIA_MODES') || 'studio,parseh').split(',');
const SHOTS = Deno.env.get('SHOTS') || '';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {      // (a wait for something to be so: how long it is given is how long a slow computer is)
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}
const ASSETS = root + '/markdown/exlex/starters/assets';
const SHIPPED = {'images/starter-apple.svg': await Deno.readFile(`${ASSETS}/images/starter-apple.svg`),
                 'images/starter-house.svg': await Deno.readFile(`${ASSETS}/images/starter-house.svg`),
                 'audio/starter-chime.mp3': await Deno.readFile(`${ASSETS}/audio/starter-chime.mp3`)};
const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const readOr = async p => { try { return await Deno.readFile(p); } catch (_) { return null; } };

// what a starter adds: every place the dialect puts a picture or a recording,
// and one picture of the document's own that it does not hold
const ADDED = `

![an apple](images/starter-apple.svg){width=40 align=center offset=0}

![a chime](audio/starter-chime.mp3)

![a cat of its own](images/cat.png)

:::exercise flashcard
card-type: vocab
target: house
meaning: a building to live in
front-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

:::exercise single-choice
image: images/starter-apple.svg {width=30 align=center}
audio: audio/starter-chime.mp3
prompt: What is it?
- [x] an apple
- [ ] a house
:::
`;

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

/* Every picture and player in the sheet, as the browser has it: where it
   loads from, whether it loaded, and whether it is on the screen, seen. */
async function media(page) {
  // the images decode and the players read their header before we look
  await until(() => page.evaluate(() => [...document.querySelectorAll('#sheet img')].every(i => i.complete)
                                        && [...document.querySelectorAll('#sheet audio')].every(a => a.readyState >= 1 || a.error)),
              'the pictures and the recordings load');
  return page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('#sheet img, #sheet audio')) {
      const r = (el.closest('.ex-card-audio') || el).getBoundingClientRect();
      out.push({tag: el.tagName.toLowerCase(), src: new URL(el.src).pathname,
                where: (w => !w ? '' : w.tagName === 'FIGURE' ? 'figure' : w.className.split(' ')[0])(
                  el.closest('.ex-card-image, .ex-card-audio, .ex-image, .ex-audio, figure')),
                loaded: el.tagName === 'IMG' ? el.naturalWidth > 0 : !el.error && el.readyState >= 1,
                duration: el.tagName === 'AUDIO' ? el.duration : null,
                box: el.tagName === 'IMG' || el.controls ? r.width > 20 && r.height > 20 : true});
    }
    return out;
  });
}

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
    const dialogs = [];
    page.on('dialog', d => { dialogs.push(d.message()); d.accept(); });
    const toastSays = (re, what) => until(async () => re.test(await page.locator('#toast').textContent()), what);
    const rendered = () => until(async () => /rendered/.test(await page.locator('#pv-status').textContent()), 'the preview renders');
    // the starter page now shows the starters' files itself: a document
    // made of the header alone, so what the test adds is all there is
    async function reset(code) {
      await page.evaluate(() => { document.querySelector('#pv-status').textContent = ''; });
      await page.locator('#src').evaluate((t, md) => {
        t.focus();
        t.value = md;
        t.dispatchEvent(new Event('input', {bubbles: true}));
      }, `---\ntitle: Starter media ${code}\nlang: en\ntarget: ${code}\n---\n`);
      await rendered();
    }
    async function append(text) {
      await page.evaluate(() => { document.querySelector('#pv-status').textContent = ''; });
      await page.locator('#src').evaluate((t, add) => {
        t.focus();
        t.value += add;
        t.dispatchEvent(new Event('input', {bubbles: true}));
      }, text);
      await rendered();
    }

    await page.goto(url('/new?target=fa'));
    const langs = await page.evaluate(() => JSON.parse(document.getElementById('langs-json').textContent).map(l => l.code));
    assert(langs.length >= 11 && langs.includes('fa') && langs.includes('ja') && langs.includes('hi'),
           'every language of the registry: ' + langs.join(' '));
    for (const code of langs) {
      await page.goto(url('/new?target=' + code));
      await page.waitForSelector('#src');
      await rendered();
      // the starter itself: its pictures and its recording, from the starters
      const shown = await media(page);
      assert(shown.length >= 3 && shown.every(m => m.src.startsWith(`${base}/starter-media/`) && m.loaded),
             `${code}: the starter page's own pictures and recording come from the starters and load `
             + JSON.stringify(shown.map(m => [m.src, m.loaded])));
      await reset(code);
      await append(ADDED);
      const got = await media(page);
      const want = [['img', 'figure', 'images/starter-apple.svg'], ['audio', 'figure', 'audio/starter-chime.mp3'],
                    ['img', 'ex-card-image', 'images/starter-house.svg'], ['audio', 'ex-card-audio', 'audio/starter-chime.mp3'],
                    ['img', 'ex-image', 'images/starter-apple.svg'], ['audio', 'ex-audio', 'audio/starter-chime.mp3']];
      assert(JSON.stringify(got.map(m => [m.tag, m.where, m.src])) ===
             JSON.stringify(want.map(([t, w, p]) => [t, w, `${base}/starter-media/${p}`])),
             `${code}: every picture and recording of a document not saved yet comes from the starters ` + JSON.stringify(got.map(m => m.src)));
      assert(got.every(m => m.loaded), `${code}: each one loads ` + JSON.stringify(got.filter(m => !m.loaded)));
      assert(got.filter(m => m.tag === 'audio').every(m => Math.abs(m.duration - 1.5) < 0.2),
             `${code}: the recording is the chime, about a second and a half ` + JSON.stringify(got.map(m => m.duration)));
      assert(got.every(m => m.box), `${code}: each is drawn at a size`);
      assert(await page.locator('#sheet .img-placeholder').filter({hasText: 'images/cat.png'}).count() === 1,
             `${code}: a picture of the document's own is a placeholder until it has one`);
    }

    // what is seen, not just what is there: the figure's picture on the screen
    await page.goto(url('/new?target=fa'));
    await page.waitForSelector('#src');
    await rendered();
    await reset('fa');
    await append(ADDED);
    await media(page);
    const fig = page.locator('#sheet figure.img:not(.audio) img').first();
    await fig.scrollIntoViewIfNeeded();
    const seen = await fig.evaluate(img => {
      const r = img.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      return {hit: document.elementFromPoint(x, y) === img, inside: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
              width: r.width};
    });
    assert(seen.hit && seen.inside && seen.width > 100, 'the apple is on the screen, uncovered ' + JSON.stringify(seen));
    const play = await page.locator('#sheet figure.audio audio').evaluate(async a => {
      a.muted = true;
      await a.play();
      // a loaded machine may take a while to get it going: up to 3 s, and
      // the chime is only a second and a half long
      for (let i = 0; i < 60 && a.currentTime <= 0.1 && !a.ended; i++)
        await new Promise(r => setTimeout(r, 50));
      return {t: a.currentTime, paused: a.paused};
    });
    assert(play.t > 0.1, 'the chime plays from the preview ' + JSON.stringify(play));
    if (SHOTS) await page.screenshot({path: `${SHOTS}/starter-media-${mode}-new.png`});

    // nothing of the document's own to list before it is saved
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.click('#btn-images');
    await toastSays(/^Save the document first — images are stored in its folder$/, 'Images… asks for a save first');
    assert(!await page.locator('.modal .imggrid').count(), 'and lists no picture');
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.click('#btn-audios');
    await toastSays(/^Save the document first — recordings are stored in its folder$/, 'Recordings… asks for a save first');
    assert(!await page.locator('.modal.audio-modal').count(), 'and lists no recording');

    // b) the first Save
    await Promise.all([page.waitForURL(/\/doc\/[a-z0-9-]+\/edit$/), page.click('#btn-save')]);
    const id = page.url().match(/\/doc\/([a-z0-9-]+)\/edit$/)[1];
    const dir = `${info.library}/persian/${id}`;
    for (const [path, bytes] of Object.entries(SHIPPED))
      assert(same(await readOr(`${dir}/${path}`) || new Uint8Array(), bytes), `the save copied ${path} into the document, byte for byte`);
    assert(await readOr(`${dir}/images/cat.png`) === null, 'and nothing it does not have');
    await rendered();
    // a saved document's own picture has an address now, and nothing behind
    // it: the starters' files are its own
    const own = got => got.filter(m => !m.src.endsWith('/images/cat.png'));
    const cat = got => got.filter(m => m.src.endsWith('/images/cat.png')).map(m => [m.src, m.loaded]);
    let got = await media(page);
    assert(own(got).length === 6 && own(got).every(m => m.src.startsWith(`${base}/media/${id}/`) && m.loaded),
           'the saved document shows its own copies ' + JSON.stringify(got.map(m => [m.src, m.loaded])));
    assert(JSON.stringify(cat(got)) === JSON.stringify([[`${base}/media/${id}/images/cat.png`, false]]),
           'and a picture it does not hold stays missing ' + JSON.stringify(cat(got)));
    await page.click('#btn-images');
    await page.waitForSelector('.modal .imgcell');
    const cells = await page.locator('.modal .imgcell').evaluateAll(cs => cs.map(c => c.querySelector('.nm').textContent.split(' ')[0] + (c.querySelector('.ref') ? ' in use' : '')));
    assert(JSON.stringify(cells) === JSON.stringify(['starter-apple.svg in use', 'starter-house.svg in use']),
           'Images… lists them as the document\'s own, in use ' + JSON.stringify(cells));
    await page.click('.modal [data-x="close"]');
    await page.click('#btn-audios');
    await page.waitForSelector('.modal.audio-modal [data-x="mine"] .audrow');
    const rows = await page.locator('.modal.audio-modal [data-x="mine"] .audrow').evaluateAll(rs => rs.map(r =>
      r.querySelector('.audname').textContent + (r.querySelector('.ref') ? ' in use' : '')));
    assert(JSON.stringify(rows) === JSON.stringify(['starter-chime.mp3 in use']), 'Recordings… lists the chime, in use ' + JSON.stringify(rows));
    await page.keyboard.press('Escape');

    await page.goto(url(`/doc/${id}`));
    await page.waitForSelector('#sheet');
    got = await media(page);
    assert(own(got).length === 6 && own(got).every(m => m.src.startsWith(`${base}/media/${id}/`) && m.loaded && m.box),
           'the document page shows them from the document ' + JSON.stringify(got.map(m => [m.src, m.loaded])));
    if (SHOTS) await page.screenshot({path: `${SHOTS}/starter-media-${mode}-doc.png`, fullPage: true});

    // c) a document saved before, naming one later
    const made = await (await fetch(url('/api/docs'), {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: '---\ntitle: Later\nlang: en\ntarget: ja\n---\n\nNothing yet.\n'})})).json();
    const later = made.meta.id, laterDir = `${info.library}/japanese/${later}`;
    await page.goto(url(`/doc/${later}/edit`));
    await page.waitForSelector('#src');
    await rendered();
    await append('\n![a house](images/starter-house.svg)\n');
    got = await media(page);
    assert(got.length === 1 && got[0].src === `${base}/starter-media/images/starter-house.svg` && got[0].loaded,
           'the preview shows it from the starters before the save ' + JSON.stringify(got));
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.click('#btn-save');
    await toastSays(/^Saved$/, 'the document is saved');
    assert(same(await readOr(`${laterDir}/images/starter-house.svg`) || new Uint8Array(), SHIPPED['images/starter-house.svg']),
           'and the save copied it in');
    await append('\n');
    got = await media(page);
    assert(got.length === 1 && got[0].src === `${base}/media/${later}/images/starter-house.svg` && got[0].loaded,
           'after which the preview shows the document\'s copy ' + JSON.stringify(got));

    // d) the owner deletes the apple and the chime of the first document
    await page.goto(url(`/doc/${id}/edit`));
    await page.waitForSelector('#src');
    await rendered();
    await media(page);
    await page.click('#btn-images');
    await page.waitForSelector('.modal .imgcell');
    dialogs.length = 0;
    await page.locator('.modal .imgcell').filter({hasText: 'starter-apple.svg'}).locator('.del').click();
    await until(async () => await page.locator('.modal .imgcell').count() === 1, 'the apple leaves Images…');
    assert(JSON.stringify(dialogs) === JSON.stringify(['“starter-apple.svg” is used by the document — the embed will break. Delete anyway?']),
           'Images… warned that the embed would break ' + JSON.stringify(dialogs));
    await page.click('.modal [data-x="close"]');
    await page.click('#btn-audios');
    await page.waitForSelector('.modal.audio-modal [data-x="mine"] .audrow');
    await page.locator('.modal.audio-modal [data-x="mine"] .audrow').filter({hasText: 'starter-chime.mp3'}).locator('.del').click();
    await page.waitForSelector('.modal.audio-modal [data-x="mine"] .hint');
    await page.keyboard.press('Escape');
    assert(await readOr(`${dir}/images/starter-apple.svg`) === null && await readOr(`${dir}/audio/starter-chime.mp3`) === null,
           'the apple and the chime are deleted');
    // and the page says so everywhere, as it does of a file of its own
    const missing = got => got.filter(m => /starter-(apple|chime)/.test(m.src)).map(m => [m.src, m.loaded]);
    const gone = [[`${base}/media/${id}/images/starter-apple.svg`, false], [`${base}/media/${id}/audio/starter-chime.mp3`, false],
                  [`${base}/media/${id}/audio/starter-chime.mp3`, false], [`${base}/media/${id}/images/starter-apple.svg`, false],
                  [`${base}/media/${id}/audio/starter-chime.mp3`, false]];
    // -- the editor at once, with no reload and nothing typed
    got = await until(async () => { const g = missing(await media(page)); return JSON.stringify(g) === JSON.stringify(gone) && g; },
                      'the editor shows them missing at once');
    assert(got, 'the editor shows them missing at once, as the warning said ' + JSON.stringify(got));
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.click('#btn-save');
    await toastSays(/^Saved$/, 'the document is saved again');
    assert(await readOr(`${dir}/images/starter-apple.svg`) === null && await readOr(`${dir}/audio/starter-chime.mp3`) === null,
           'the Save did not bring them back');
    assert(same(await readOr(`${dir}/images/starter-house.svg`) || new Uint8Array(), SHIPPED['images/starter-house.svg']),
           'and left the house alone');
    await append('\n');
    got = await media(page);
    assert(JSON.stringify(missing(got)) === JSON.stringify(gone), 'saved, the editor shows them missing ' + JSON.stringify(missing(got)));
    await page.reload();
    await page.waitForSelector('#src');
    await rendered();
    got = await media(page);
    assert(JSON.stringify(missing(got)) === JSON.stringify(gone), 'reopened, the editor shows them missing ' + JSON.stringify(missing(got)));
    await page.goto(url(`/doc/${id}`));
    await page.waitForSelector('#sheet');
    got = await media(page);
    assert(JSON.stringify(missing(got)) === JSON.stringify(gone), 'and so does the document page ' + JSON.stringify(missing(got)));

    // e) the owner's own picture in the house's place: deleted, and another
    // uploaded under its name with Image
    await page.goto(url(`/doc/${id}/edit`));
    await page.waitForSelector('#src');
    await rendered();
    await media(page);
    // the card's picture as drawn, its middle pixel: which picture it is
    const colour = () => page.locator('#sheet img.ex-card-image').first().evaluate(i => {
      const c = document.createElement('canvas');
      c.width = c.height = 20;
      const g = c.getContext('2d');
      g.drawImage(i, 0, 0, 20, 20);
      return [...g.getImageData(10, 10, 1, 1).data].slice(0, 4);
    });
    const house = await until(async () => { const c = await colour(); return c[3] > 0 && c; }, 'the editor draws the house');
    assert(!(house[0] === 46 && house[1] === 139 && house[2] === 87), 'the editor draws the house on its card ' + JSON.stringify(house));
    await page.click('#btn-images');
    await page.waitForSelector('.modal .imgcell');
    await page.locator('.modal .imgcell').filter({hasText: 'starter-house.svg'}).locator('.del').click();
    await page.waitForSelector('.modal .imggrid .hint');
    await page.click('.modal [data-x="close"]');
    const blank = await until(async () => {
      const h = (await media(page)).filter(m => m.src.endsWith('/images/starter-house.svg'));
      return h.length === 1 && !h[0].loaded && h;
    }, 'the house leaves the editor');
    assert(blank, 'the editor shows the house missing at once ' + JSON.stringify(blank.map(m => [m.src, m.loaded])));
    const pear = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#2e8b57"/></svg>';
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.setInputFiles('#img-upload', {name: 'starter-house.svg', mimeType: 'image/svg+xml', buffer: Buffer.from(pear)});
    await toastSays(/^Uploaded starter-house\.svg$/, 'the upload keeps the name');
    // the page drew the house from that address before: it draws the new
    // picture now, not what it remembers
    // (if it does not, the page is described: which pictures it holds, whether they loaded, which names it marked, what
    // the preview last said -- a timeout of eight seconds on its own says nothing of which of those it was)
    const drawn = await until(async () => { const c = await colour(); return c[0] === 46 && c[1] === 139 && c[2] === 87 && c; },
                              'the editor draws the new picture')
      .catch(async e => {
        const seen = await page.evaluate(() => ({
          imgs: [...document.querySelectorAll('#sheet img')].map(i => [i.getAttribute('src'), i.complete, i.naturalWidth]),
          marked: typeof MEDIA_CHANGED === 'undefined' ? null : [...MEDIA_CHANGED],
          status: (document.querySelector('#pv-status') || {}).textContent, toast: (document.querySelector('#toast') || {}).textContent,
        })).catch(x => String(x));
        throw Error(e.message + ' -- the page: ' + JSON.stringify(seen));
      });
    assert(drawn, 'the editor draws the new picture at once, not the house it drew before ' + JSON.stringify(drawn));
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.click('#btn-save');
    await toastSays(/^Saved$/, 'and the document is saved');
    assert(new TextDecoder().decode(await readOr(`${dir}/images/starter-house.svg`) || new Uint8Array()) === pear,
           'the document holds the owner\'s picture under that name, and the Save left it');
    await page.goto(url(`/doc/${id}`));
    await page.waitForSelector('#sheet');
    got = await media(page);
    const houses = got.filter(m => m.src.endsWith('/images/starter-house.svg'));
    assert(houses.length === 2 && houses.every(m => m.src === `${base}/media/${id}/images/starter-house.svg` && m.loaded),
           'the document page shows it ' + JSON.stringify(houses.map(m => [m.src, m.loaded])));
    assert(JSON.stringify(missing(got)) === JSON.stringify(gone), 'and the apple and the chime still missing ' + JSON.stringify(missing(got)));

    assert(!errors.length, 'no page error: ' + errors.join(' | '));
    // a player the page leaves mid-answer (it had what it needed, or the page
    // moved on) closes its connection under the server, which may say so with
    // a traceback: that is the browser's doing, and anything else is not
    const raised = [...log.join('').matchAll(/Traceback[\s\S]*?\n(\w[\w.]*(?:Error|Exception)\b[^\n]*)/g)].map(m => m[1]);
    const bad = raised.filter(e => !/^(BrokenPipeError|ConnectionResetError|ConnectionAbortedError)\b/.test(e));
    const told = (log.join('').match(/Traceback/g) || []).length;
    assert(!bad.length && raised.length === told,
           'no traceback in the server log but a listener leaving ' + JSON.stringify(raised) + ' ' + log.join('').slice(-3000));
  } finally {
    await browser.close();
    try { proc.kill('SIGTERM'); } catch (_) {}
    await proc.status;
  }
}

for (const mode of modes) await suite(mode);
console.log(`\nstudio_starter_media: ${passed} checks passed`);
