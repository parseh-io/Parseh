// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of recordings in a studio document, against the REAL routes
// (markdown/app/server.py, store.py, htmlgen) on a temporary library and a
// temporary clip tray, with real recordings written by ffmpeg:
//   a) the editor's Audio button uploads a recording and puts its line in;
//      the preview's player loads it; two picked at once go in one line
//      after the other
//   b) a recording dropped on the editor goes in the same way, and a
//      recording and a picture dropped together likewise; a file dropped
//      anywhere never takes the page away
//   c) Recordings… lists the document's recordings (in use, ▶, ✕ delete, a
//      click inserts) and, in the hub, the clips waiting in the tray, whose
//      Add puts one in and copies it into the document and whose ✕ deletes
//      it from the tray; it takes the focus, and Escape closes it
//   d) text pasted naming a clip brings the clip into the document, and the
//      preview plays it
//   e) the layout panel of a recording saves a clip window in hundredths (and
//      says so), the player keeps to the window, in the editor and on the
//      page, and a window starting past the recording's end stops at once
//   f) the exercise form uploads a card's recordings (vocabulary field,
//      jolly "Recording…"), plays them, previews the card as the page draws
//      it, and says "Save the document first" in a document not saved yet;
//      Add exercise's "Paste markdown…" opens a card copied as markdown in
//      the form, its clip brought in from the tray first
//   g) a rich jolly card on the document page, on a desktop and at 400 px,
//      and the page's players wide enough for a timeline on a phone
//   h) (hub) the clip tray's own page, from the hub's door: every clip
//      played or shown, ✕ deletes one, "Empty the tray" all of them
// Two modes, each a tests/studio_harness.py:
//   studio  the studio's own server (studio at /, no clip tray to list)
//   parseh  Parseh's handler (studio at /studio, the tray at /clips)
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/studio_audio.mjs
//   STUDIO_AUDIO_MODES=studio (or parseh) runs one; SHOTS=<dir> saves the
//   screenshots (the editor with Recordings… open, the rich card page)
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('STUDIO_AUDIO_MODES') || 'studio,parseh').split(',');
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
const exists = async p => { try { await Deno.stat(p); return true; } catch (_) { return false; } };

/* Real recordings, written once by ffmpeg for this run. */
const MEDIA = await (async () => {
  const dir = await Deno.makeTempDir({prefix: 'parseh-studio-audio-media-'});
  const run = async (args, out) => {
    const r = await new Deno.Command('ffmpeg', {args: ['-y', '-loglevel', 'error', ...args, `${dir}/${out}`],
                                                stdout: 'null', stderr: 'piped'}).output();
    if (!r.success) throw Error('ffmpeg: ' + new TextDecoder().decode(r.stderr));
    return Buffer.from(await Deno.readFile(`${dir}/${out}`));
  };
  const tone = (freq, secs, codec, out) => run(['-f', 'lavfi', '-i', `sine=frequency=${freq}:duration=${secs}`, '-c:a', codec], out);
  const media = {tone: await tone(440, 4, 'libmp3lame', 'tone.mp3'), dropped: await tone(660, 3, 'libvorbis', 'dropped.ogg'),
                 word: await tone(330, 3, 'libmp3lame', 'word.mp3'), card: await tone(550, 3, 'libmp3lame', 'card.mp3'),
                 // several at once: bytes of their own (the store gives equal bytes one name)
                 first: await tone(370, 2, 'libmp3lame', 'first.mp3'), second: await tone(415, 2, 'libmp3lame', 'second.mp3'),
                 third: await tone(494, 2, 'libvorbis', 'third.ogg'),
                 picture: Buffer.from(await Deno.readFile(new URL('./fixtures/studio/audio/images/swatch.png', import.meta.url)))};
  await Deno.remove(dir, {recursive: true});
  return media;
})();

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
    const context = await browser.newContext({viewport: {width: 1400, height: 900},
                                              permissions: ['clipboard-read', 'clipboard-write']});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());
    const made = await api('POST', '/api/docs', {markdown: '---\ntitle: Listening\ntarget: fa\n---\n\nA page with recordings.\n'});
    const id = made.meta.id;
    const docDir = `${info.library}/persian/${id}`;
    assert(await exists(docDir + '/source.md'), `a document made through the API (${id})`);
    const source = () => page.locator('#src').inputValue();
    const toastSays = (re, what) => until(async () => re.test(await page.locator('#toast').textContent()), what);
    const player = sel => page.evaluate(sel => {
      const a = document.querySelector(sel);
      return a && {ready: a.readyState, paused: a.paused, t: a.currentTime, src: a.getAttribute('src'), error: a.error && a.error.code};
    }, sel);
    const previewAudio = name => `#sheet figure.audio audio[src*="/audio/${name}"]`;
    const loads = (sel, what) => until(async () => { const p = await player(sel); return p && p.ready >= 1; }, what);
    /* THE PREVIEW IS DRAWN AGAIN by every change of the source and by every file brought in -- the page asks for it 350 ms
       after a change, and again at once when the clip tray has given it a file -- and each drawing replaces the players
       of the one before.  A player found while one of them is still to come is a player about to be taken away (a
       click on it lands on nothing; Playwright says "Element is not attached to the DOM"), so the drawings are counted
       from out here and waited for: none under way, and none begun for 800 ms. */
    const renders = {open: 0, last: Date.now()};
    const isRender = r => r.method() === 'POST' && r.url().endsWith('/api/preview');
    page.on('request', r => { if (isRender(r)) { renders.open++; renders.last = Date.now(); } });
    for (const gone of ['requestfinished', 'requestfailed'])
      page.on(gone, r => { if (isRender(r)) { renders.open = Math.max(0, renders.open - 1); renders.last = Date.now(); } });
    const previewSettled = (what = 'the preview is drawn') => until(async () => renders.open === 0 && Date.now() - renders.last >= 800, what, 20000);
    /* A real click on a native player's ▶ (its left end), made where the player stands STILL and on what is there,
       and LOOKED FOR in the player's own events: the click that did nothing is made again, the one that did something
       never is (a second would pause what the first started).  A player that has just been drawn lays its controls
       out, and the page aligns its panes after a drawing, so a box measured and clicked 250 ms later was a guess. */
    const clickPlay = async (sel, tab = page, event = 'play') => {
      for (let attempt = 1; attempt <= 5; attempt++) {
        const at = await tab.evaluate(([sel, event]) => new Promise(done => {
          let last = '', same = 0, looks = 0;
          const look = () => {
            const a = document.querySelector(sel);
            if (a) {
              a.scrollIntoView({block: 'nearest'});
              const r = a.getBoundingClientRect(), key = [r.x, r.y, r.width, r.height].map(Math.round).join();
              same = key === last ? same + 1 : 0;
              last = key;
              const x = r.x + 20, y = r.y + r.height / 2;
              if (same >= 6 && document.elementFromPoint(x, y) === a) {
                window.__heard = 0;
                a.addEventListener(event, () => { window.__heard++; }, {once: true});
                return done({x, y});
              }
            } else { same = 0; last = ''; }
            if (++looks > 400) return done(null);
            setTimeout(look, 25);
          };
          look();
        }), [sel, event]);
        if (!at) continue;
        await tab.mouse.click(at.x, at.y);
        for (let i = 0; i < 30; i++) {
          if (await tab.evaluate(() => window.__heard).catch(() => 0)) return;
          await sleep(50);
        }
        // a click heard late is a click that worked: the player is already doing what it was asked
        if (await tab.evaluate(([sel, event]) => { const a = document.querySelector(sel); return !!a && (event === 'play' ? !a.paused : a.paused); },
                               [sel, event]).catch(() => false)) return;
      }
      throw Error('FAIL: a click on the ▶ of ' + sel + " never made the player " + event);
    };

    /* ---------------- a) the Audio button ---------------- */
    console.log('a) the Audio button');
    await page.goto(url(`/doc/${id}/edit`));
    await until(async () => /rendered/.test(await page.locator('#pv-status').textContent()), 'the preview renders');
    assert(await page.locator('#audio-upload').getAttribute('accept') === info.audio_accept,
           `the Audio picker offers audiofile.ACCEPT (${info.audio_accept})`);
    assert((await page.locator('label[for="audio-upload"]').getAttribute('title')).startsWith(`Upload a recording (${info.audio_human}) into`),
           `the Audio button names audiofile.HUMAN (${info.audio_human})`);
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    let chooser = page.waitForEvent('filechooser');
    await page.locator('label[for="audio-upload"]').click();
    await (await chooser).setFiles({name: 'Tone.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.tone});
    await until(async () => (await source()).includes('![didascalia](audio/tone.mp3)'), 'the recording line goes in');
    const lines = (await source()).split('\n');
    const at = lines.indexOf('![didascalia](audio/tone.mp3)');
    assert(at > 0 && lines[at - 1] === '', 'on a line of its own, after a blank line');
    assert(await page.locator('#src').evaluate(t => t.value.slice(t.selectionStart, t.selectionEnd)) === 'didascalia',
           'the caption placeholder is selected, ready to be typed over');
    assert(Buffer.from(await Deno.readFile(docDir + '/audio/tone.mp3')).equals(MEDIA.tone), 'the file is in the document\'s audio/ folder, byte for byte');
    await toastSays(/^Uploaded tone\.mp3$/, 'the upload is told');
    await loads(previewAudio('tone.mp3'), 'the preview\'s player loads the recording');
    const pv = await player(previewAudio('tone.mp3'));
    assert(pv.src === `${base}/media/${id}/audio/tone.mp3` && pv.ready >= 1, `the preview's <audio> loaded ${pv.src} (readyState ${pv.ready})`);
    const fits = await page.locator(previewAudio('tone.mp3')).evaluate(a => {
      const r = a.getBoundingClientRect(), f = a.closest('figure').getBoundingClientRect();
      return r.width > 100 && r.left >= f.left - 1 && r.right <= f.right + 1;
    });
    assert(fits, 'the player is as wide as its figure and inside it');
    // two picked at once, the first one's caption still selected when the
    // second arrives: one line after the other, neither inside the other
    const before = await source();
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    chooser = page.waitForEvent('filechooser');
    await page.locator('label[for="audio-upload"]').click();
    await (await chooser).setFiles([{name: 'first.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.first},
                                    {name: 'second.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.second}]);
    await until(async () => (await source()).includes('audio/second.mp3'), 'the second of two recordings goes in');
    assert((await source()) === before + '\n\n![didascalia](audio/first.mp3)\n\n![didascalia](audio/second.mp3)',
           'two recordings picked at once: two lines, in order, each on its own ' + JSON.stringify((await source()).slice(before.length)));
    assert(await page.locator('#src').evaluate(t => t.selectionStart === t.value.lastIndexOf('didascalia') && t.value.slice(t.selectionStart, t.selectionEnd) === 'didascalia'),
           'the last one\'s caption is the one left selected');
    await loads(previewAudio('first.mp3'), 'the first of the two plays in the preview');
    await loads(previewAudio('second.mp3'), 'the second of the two plays in the preview');
    assert(true, 'both players of the two load in the preview');

    /* ---------------- b) dropping files ---------------- */
    console.log('b) dropping files');
    const drop = (selector, files) => page.evaluate(([selector, files]) => {
      const dt = new DataTransfer();
      for (const f of files) dt.items.add(new File([Uint8Array.from(atob(f.b64), c => c.charCodeAt(0))], f.name, {type: f.type}));
      const el = document.querySelector(selector);
      const over = el.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt}));
      const dropped = el.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
      return {overPrevented: !over, dropPrevented: !dropped};
    }, [selector, files.map(f => ({name: f.name, type: f.type, b64: Buffer.from(f.bytes).toString('base64')}))]);
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    let d = await drop('#src', [{name: 'dropped.ogg', type: 'audio/ogg', bytes: MEDIA.dropped}]);
    assert(d.overPrevented && d.dropPrevented, 'a recording dropped on the editor is taken by the page, not opened by the browser');
    await until(async () => (await source()).includes('![didascalia](audio/dropped.ogg)'), 'the dropped recording goes in');
    assert(await exists(docDir + '/audio/dropped.ogg'), 'and is stored in audio/');
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    d = await drop('#src', [{name: 'notes.txt', type: 'text/plain', bytes: Buffer.from('not media')}]);
    assert(d.dropPrevented, 'a text file dropped on the editor is not opened either');
    await toastSays(/notes\.txt: only pictures .* and recordings/, 'and it is said what goes in');
    assert(await page.locator('#toast').textContent() === `notes.txt: only pictures (PNG, JPEG, SVG, PDF) and recordings (${info.audio_human}) go into a document`,
           'the refusal names the recordings audiofile.HUMAN names: ' + await page.locator('#toast').textContent());
    d = await drop('#sheet', [{name: 'elsewhere.mp3', type: 'audio/mpeg', bytes: MEDIA.word}]);
    await sleep(300);
    assert(d.overPrevented && d.dropPrevented && page.url() === url(`/doc/${id}/edit`) && !await exists(docDir + '/audio/elsewhere.mp3')
           && !(await source()).includes('notes.txt') && !(await source()).includes('elsewhere'),
           'a file dropped on the preview: nothing opened, nothing stored, the editor stays');
    // a recording and a picture dropped together: in the order dropped, one line after the other
    const withDropped = await source();
    d = await drop('#src', [{name: 'third.ogg', type: 'audio/ogg', bytes: MEDIA.third},
                            {name: 'swatch.png', type: 'image/png', bytes: MEDIA.picture}]);
    assert(d.dropPrevented, 'two files dropped at once are taken by the page');
    await until(async () => (await source()).includes('images/swatch.png'), 'the second of two dropped files goes in');
    assert((await source()).replace(withDropped, '') === '\n\n![didascalia](audio/third.ogg)\n\n![didascalia](images/swatch.png)',
           'a recording and a picture dropped at once: two lines, in order ' + JSON.stringify((await source()).replace(withDropped, '')));
    await loads(previewAudio('third.ogg'), 'the recording dropped with a picture plays in the preview');
    await until(() => page.evaluate(() => { const i = document.querySelector('#sheet figure.img img[src*="/images/swatch.png"]'); return i && i.complete && i.naturalWidth > 0; }),
                'the picture dropped with a recording shows in the preview');
    assert(true, 'both dropped files are drawn in the preview');
    // what several at once put in taken out of the text again, as a person
    // would, and their files deleted: the manager lists what follows
    await page.locator('#src').evaluate(t => {
      t.value = t.value.replace(/(?:\n*!\[didascalia\]\((?:audio\/(?:dropped\.ogg|first\.mp3|second\.mp3|third\.ogg)|images\/swatch\.png)\)\n*)+/, '\n');
      t.dispatchEvent(new Event('input', {bubbles: true}));
    });
    for (const name of ['first.mp3', 'second.mp3', 'third.ogg']) await api('DELETE', `/api/docs/${id}/audio/${name}`);
    await api('DELETE', `/api/docs/${id}/images/swatch.png`);

    /* ---------------- c) Recordings… ---------------- */
    console.log('c) Recordings…');
    await page.click('#btn-audios');
    await page.waitForSelector('.audio-modal .audrow[data-name="dropped.ogg"]');
    const focusInDialog = () => page.evaluate(() => !!document.activeElement.closest('.audio-modal'));
    assert(await focusInDialog(), 'the dialog takes the focus when it opens');
    const rows = await page.locator('.audio-modal [data-x="mine"] .audrow').evaluateAll(rs => rs.map(r =>
      [r.dataset.name, !!r.querySelector('.ref'), r.querySelector('.audsize').textContent]));
    assert(JSON.stringify(rows.map(r => r.slice(0, 2))) === JSON.stringify([['dropped.ogg', false], ['tone.mp3', true]]),
           'both recordings listed, the one the text names "in use": ' + JSON.stringify(rows));
    await page.locator('.audrow[data-name="tone.mp3"] .audplay').click();
    await page.waitForSelector('.audrow[data-name="tone.mp3"] .audplay.playing', {timeout: 8000});
    assert(!await page.locator('.audio-modal').count() === false, '▶ plays a recording, and the dialog stays');
    if (mode === 'parseh') {
      await page.waitForSelector('.audio-modal .audclips:not([hidden]) .audrow.clip');
      const clipRows = await page.locator('.audclips .audrow.clip').evaluateAll(rs => rs.map(r => [r.dataset.name, r.querySelector('.audtext').textContent]));
      assert(clipRows.length === 2 && clipRows.some(r => r[0] === info.clips[0].name && r[1] === 'سلام'),
             'the clips cut from books and videos, in the document\'s language: ' + JSON.stringify(clipRows));
    } else {
      await sleep(800);
      assert(await page.locator('.audio-modal .audclips').isHidden(), 'the studio on its own has no clip tray: no clip section');
    }
    if (SHOTS) await page.screenshot({path: `${SHOTS}/studio-audio-${mode}-manager.png`});
    await page.locator('.audrow[data-name="dropped.ogg"] .del').click();
    await until(async () => !await page.locator('.audrow[data-name="dropped.ogg"]').count(), 'the deleted recording leaves the list');
    assert(!await exists(docDir + '/audio/dropped.ogg') && (await api('GET', `/api/docs/${id}/audio`)).audio.map(a => a.name).join() === 'tone.mp3',
           '✕ deletes the file an unused recording is');
    // the keyboard: the focus stays in the dialog when its row goes, Escape
    // closes it from there and gives the focus back to Recordings…
    assert(await focusInDialog(), 'the focus stays in the dialog when the deleted row goes');
    await page.keyboard.press('Escape');
    await until(async () => !await page.locator('.audio-modal').count(), 'Escape closes Recordings…');
    assert(await page.evaluate(() => document.activeElement.id) === 'btn-audios', 'Escape closes Recordings…, the focus back on its button');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.audio-modal .audrow[data-name="tone.mp3"]');
    assert(await focusInDialog(), 'opened from the keyboard, the dialog has the focus');
    await page.keyboard.press('Escape');
    await until(async () => !await page.locator('.audio-modal').count(), 'Escape closes Recordings… opened from the keyboard');
    await page.click('#btn-audios');
    await page.waitForSelector('.audio-modal .audrow[data-name="tone.mp3"]');
    await page.locator('.audrow[data-name="tone.mp3"] .audname').click();
    assert(!await page.locator('.audio-modal').count() && (await source()).split('audio/tone.mp3').length === 3,
           'a click on a recording puts it in at the cursor and closes the dialog');
    await page.click('#btn-undo');
    assert((await source()).split('audio/tone.mp3').length === 2, '↺ takes it out again');
    if (mode === 'parseh') {
      const hello = info.clips[0];
      await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
      await page.click('#btn-audios');
      await page.waitForSelector(`.audclips .audrow[data-name="${hello.name}"]`);
      await page.locator(`.audclips .audrow[data-name="${hello.name}"] [data-x="add"]`).click();
      await until(async () => (await source()).includes(`![سلام](${hello.path})`), 'Add puts the clip\'s line in, its words the caption');
      await until(() => exists(`${docDir}/${hello.path}`), 'Add copies the clip into the document');
      await toastSays(/^Brought 1 file from the clip tray$/, 'the copy is told');
      await loads(previewAudio(hello.name), 'the added clip plays in the preview');
      assert(true, `the added clip ${hello.name} is in audio/ and loads in the preview`);
      // a clip nobody wants any more leaves the tray from here, after a question
      const spare = (await (await fetch(`${origin}/clips/api/upload?kind=audio&hint=spare&lang=fa&text=${encodeURIComponent('یدکی')}`,
                                        {method: 'POST', body: MEDIA.second})).json()).clip;
      assert(await exists(`${info.tray}/${spare.name}`) && await exists(`${info.tray}/${spare.name}.json`), `a third clip in the tray (${spare.name})`);
      await page.click('#btn-audios');
      const spareRow = `.audclips .audrow.clip[data-name="${spare.name}"]`;
      await page.waitForSelector(spareRow);
      const trayButtons = await page.locator('.audclips .audrow.clip').evaluateAll(rs => rs.map(r => [...r.querySelectorAll('button')].map(b => b.textContent)));
      assert(trayButtons.length === 3 && trayButtons.every(b => JSON.stringify(b) === JSON.stringify(['▶', 'Add', '✕'])),
             'each clip of the tray has ▶, Add and ✕ ' + JSON.stringify(trayButtons));
      const asked = [];
      const noteDialog = d => asked.push(d.message());
      page.on('dialog', noteDialog);
      await page.locator(`${spareRow} .del`).click();
      await until(async () => !await page.locator(spareRow).count(), 'the deleted clip leaves the list');
      page.off('dialog', noteDialog);
      assert(asked.length === 1 && asked[0].startsWith(`Delete “${spare.name}” from the clip tray?`), 'it asks first: ' + JSON.stringify(asked));
      assert(!await exists(`${info.tray}/${spare.name}`) && !await exists(`${info.tray}/${spare.name}.json`)
             && await exists(`${info.tray}/${hello.name}`) && await exists(`${docDir}/${hello.path}`),
             '✕ deletes that clip and its JSON from the tray, and nothing else: the other clips stay, the added one stays in the document');
      assert(await focusInDialog() && await page.locator('.audclips .audrow.clip').count() === 2, 'the dialog stays, with the two clips left, and keeps the focus');
      await page.keyboard.press('Escape');
      await until(async () => !await page.locator('.audio-modal').count(), 'Escape closes Recordings…');
    }

    /* ---------------- d) pasting a clip's name ---------------- */
    console.log('d) pasting a clip\'s name');
    const bye = info.clips[1];
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await page.evaluate(text => navigator.clipboard.writeText(text), `\n\n![goodbye](${bye.path})\n`);
    await page.keyboard.press('Control+V');
    await until(async () => (await source()).includes(`![goodbye](${bye.path})`), 'the pasted text is in the editor');
    await until(() => exists(`${docDir}/${bye.path}`), 'the pasted clip is brought into the document');
    assert(Buffer.from(await Deno.readFile(`${docDir}/${bye.path}`)).equals(Buffer.from(await Deno.readFile(`${info.tray}/${bye.name}`))),
           `${bye.path} copied from the tray byte for byte (the tray keeps it)`);
    await toastSays(/^Brought 1 file from the clip tray$/, 'the paste says what it brought');
    await previewSettled('the preview is drawn again with the clip in the document');
    await loads(previewAudio(bye.name), 'the pasted clip loads in the preview');
    await clickPlay(previewAudio(bye.name));
    await until(async () => { const p = await player(previewAudio(bye.name)); return !p.paused && p.t > 0.2; }, 'the pasted clip plays');
    assert(true, 'the pasted clip plays in the preview');
    await clickPlay(previewAudio(bye.name), page, 'pause');

    /* ---------------- e) a clip window ---------------- */
    console.log('e) a clip window');
    const toneFig = '#sheet figure.audio:has(audio[src*="/audio/tone.mp3"])';
    await page.locator(`${toneFig} figcaption`).click();
    await page.waitForSelector('.imgpanel .times-row:not([hidden])');
    assert(await page.locator('.imgpanel .panel-head span').textContent() === 'Recording layout', 'the caption opens the recording\'s layout panel, with its clip');
    // the panel says what it takes: hundredths, which is what it keeps
    const timeTitles = await page.locator('.imgpanel .times input').evaluateAll(xs => xs.map(x => x.title));
    assert(JSON.stringify(timeTitles) === JSON.stringify(['Start time — seconds or m:ss, to the hundredth; empty = from the beginning',
                                                          'End time — seconds or m:ss, to the hundredth; empty = to the end']),
           'the clip fields say they take hundredths ' + JSON.stringify(timeTitles));
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    await page.locator('.imgpanel [data-t="start"]').fill('abc');
    await page.locator('.imgpanel [data-t="start"]').press('Tab');
    await toastSays(/^Time as seconds or m:ss, to the hundredth \(e\.g\. 65\.25 or 1:05\.25\)$/, 'a time that is not one is refused, in hundredths');
    assert(await page.locator('.imgpanel [data-t="start"]').inputValue() === '' && !/tone\.mp3\)\{[^}]*start=/.test(await source()),
           'a refused time is not written');
    await page.locator('.imgpanel [data-t="start"]').fill('1.2');
    await page.locator('.imgpanel [data-t="start"]').press('Tab');
    await page.locator('.imgpanel [data-t="end"]').fill('0:02.05');
    await page.locator('.imgpanel [data-t="end"]').press('Tab');
    await until(async () => /!\[didascalia\]\(audio\/tone\.mp3\)\{[^}]*start=1\.2 end=2\.05\}/.test(await source()),
                'the window is written into the markdown in hundredths');
    assert(await page.locator('.imgpanel [data-t="end"]').inputValue() === '0:02.05', 'and shown as m:ss.hh');
    await toastSays(/^Recording layout saved in the markdown$/, 'the save is told');
    assert((await player(`${toneFig} audio`)).src.endsWith('/audio/tone.mp3#t=1.2,2.05'), 'the player\'s media fragment follows the window');
    await page.keyboard.press('Escape');
    // A player with a clip window, played twice by a real click on its ▶:
    // the first play may be the media fragment's (#t=start,end), the second
    // is the page's own -- it starts again at the start, and stops at the end.
    // Every moment it plays is watched, not only where it stopped.
    const keepsWindow = async (tab, sel, start, end, where) => {
      const state = () => tab.evaluate(s => { const a = document.querySelector(s); return {ready: a.readyState, paused: a.paused, t: a.currentTime}; }, sel);
      if (tab === page) await previewSettled(`${where}: the preview is drawn`);
      await until(async () => (await state()).ready >= 1, `${where}: the windowed player loads`);
      for (const round of [1, 2]) {
        await tab.evaluate(s => {
          const a = document.querySelector(s), seen = window.__seen = {min: Infinity, max: 0};
          const look = () => {
            if (!a.paused) { seen.min = Math.min(seen.min, a.currentTime); seen.max = Math.max(seen.max, a.currentTime); }
            if (window.__seen === seen) requestAnimationFrame(look);
          };
          look();
          // and by the player's own events, which do not wait for a frame: a page too busy to draw for the whole of a
          // window less than a second long has no frame in it to look at (the first position seen was Infinity)
          for (const ev of ['playing', 'timeupdate'])
            a.addEventListener(ev, () => { if (window.__seen === seen && !a.paused) { seen.min = Math.min(seen.min, a.currentTime); seen.max = Math.max(seen.max, a.currentTime); } });
        }, sel);
        await clickPlay(sel, tab);
        await until(async () => !(await state()).paused, `${where}: it plays (round ${round})`, 20000);
        await until(async () => (await state()).paused, `${where}: it stops by itself (round ${round})`, 20000);
        const p = await state(), seen = await tab.evaluate(() => window.__seen);
        assert(p.t >= end - 0.15 && p.t <= end + 0.15 && seen.max <= end + 0.15 && seen.min >= start - 0.1 && seen.min <= start + 0.3,
               `${where}, play ${round}: from ${seen.min.toFixed(2)} to ${p.t.toFixed(2)} s, inside [${start}, ${end}] (+0.15)`);
      }
    };
    await keepsWindow(page, `${toneFig} audio`, 1.2, 2.05, 'in the editor');
    await page.click('#btn-save');
    await toastSays(/^Saved$/, 'the document is saved');

    /* ---------------- the same on the document page ---------------- */
    const doc = await context.newPage();
    doc.on('pageerror', e => errors.push(e.message));
    await doc.goto(url(`/doc/${id}`));
    const docFig = 'figure.audio:has(audio[src*="/audio/tone.mp3"])';
    const attrs = await doc.locator(docFig).evaluate(f => [f.dataset.start, f.dataset.end, f.dataset.idx]);
    assert(JSON.stringify(attrs) === JSON.stringify(['1.2', '2.05', '0']), 'the page draws the window: ' + JSON.stringify(attrs));
    assert(await doc.locator('#dl-zip').textContent() === 'Markdown + media (.zip)',
           'Download ▾ names the zip by what it carries: “Markdown + media (.zip)”');
    await keepsWindow(doc, `${docFig} audio`, 1.2, 2.05, 'on the page');
    // the ⚙ handle: under the player, shown on hover, and the page's own layout save takes decimals
    await doc.hover(docFig);
    await until(async () => (await doc.locator(`${docFig} .audio-edit`).evaluate(b => getComputedStyle(b).opacity)) === '1', 'the ⚙ handle shows on hover');
    const handle = await doc.locator(docFig).evaluate(f => {
      const b = f.querySelector('.audio-edit').getBoundingClientRect(), a = f.querySelector('audio').getBoundingClientRect();
      return b.top >= a.bottom - 3 && b.right <= f.getBoundingClientRect().right + 1;
    });
    assert(handle, 'the ⚙ handle hangs under the player, not over its controls');
    await doc.locator(`${docFig} .audio-edit`).click();
    await doc.waitForSelector('.imgpanel .times-row:not([hidden])');
    await doc.locator('.imgpanel [data-t="end"]').fill('3.5');
    await doc.locator('.imgpanel [data-t="end"]').press('Tab');
    await until(async () => /audio\/tone\.mp3\)\{[^}]*start=1\.2 end=3\.5\}/.test((await api('GET', `/api/docs/${id}`)).markdown),
                'the page saves a changed window into the document');
    assert(true, 'the page\'s layout panel saved end=3.5 into the document');
    await doc.close();

    // a window that starts past the end of its recording (from 10 s of the
    // 4 s tone) has nothing to play: its ▶ stops again at once, rather than
    // seeking to the start the browser keeps putting at the end -- pressed
    // once its length is known, and once before it is
    const lateId = (await api('POST', '/api/docs', {markdown: '---\ntitle: Late clip\ntarget: fa\n---\n\n![late](audio/late.mp3){width=60 align=center offset=0 start=10}\n'})).meta.id;
    const lateUp = await fetch(url(`/api/docs/${lateId}/audio?name=late.mp3`), {method: 'POST', body: MEDIA.tone});
    assert(lateUp.status === 201 && (await lateUp.json()).name === 'late.mp3', 'a document whose clip starts past the end of its recording');
    const late = await context.newPage();
    late.on('pageerror', e => errors.push(e.message));
    await late.goto(url(`/doc/${lateId}`));
    const lateSel = 'figure.audio audio[src*="/audio/late.mp3"]';
    for (const known of [true, false]) {
      const lateState = () => late.evaluate(s => { const a = document.querySelector(s); return {ready: a.readyState, duration: a.duration, paused: a.paused, seeking: a.seeking, t: a.currentTime, events: window.__lateEvents}; }, lateSel);
      if (known) await until(async () => (await lateState()).ready >= 1, 'the late clip\'s length is known');
      else await late.evaluate(s => { const a = document.querySelector(s); a.preload = 'none'; a.load(); }, lateSel);
      const before = await lateState();
      await late.evaluate(() => {
        window.__lateEvents = 0;
        if (!window.__lateCounting) for (const type of ['play', 'playing', 'seeking', 'seeked'])
          document.addEventListener(type, () => window.__lateEvents++, true);
        window.__lateCounting = true;
      });
      if (known) {
        await late.locator(lateSel).scrollIntoViewIfNeeded();
        await sleep(250);
        const box = await late.locator(lateSel).boundingBox();
        await late.mouse.click(box.x + 20, box.y + box.height / 2);   // the native ▶
      } else await late.evaluate(s => { document.querySelector(s).play().catch(() => {}); }, lateSel);
      await sleep(2000);
      const after = await lateState();
      assert(after.duration > 3.9 && after.duration < 4.1 && after.paused && !after.seeking && after.events > 0 && after.events <= 8,
             `a clip from 10 s of a 4 s recording, ▶ pressed ${known ? 'once its length is known' : 'before its length is known'}: ` +
             `stopped, not seeking (${JSON.stringify(before)} -> ${JSON.stringify(after)})`);
    }
    await late.close();

    /* ---------------- f) the exercise form ---------------- */
    console.log('f) the exercise form');
    const openForm = async label => {
      // the menu stays open after a choice (a <details>): opened only when shut
      if (!await page.locator('details.dropdown:has(#btn-exercise)').evaluate(d => d.open))
        await page.locator('details.dropdown:has(#btn-exercise) > summary').click();
      await page.click('#btn-exercise');
      await page.locator('.ex-type').filter({hasText: label}).click();
      await page.waitForSelector('.ex-form-modal');
    };
    const fieldOf = label => page.locator('.ex-form-modal .ex-author-field').filter({has: page.locator(`:scope > span:text-is("${label}")`)});
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await openForm('Embedded vocabulary flashcard');
    await fieldOf('Word or expression').locator('textarea').fill('[کتاب]{tl}');
    await fieldOf('Meaning').locator('textarea').fill('book');
    chooser = page.waitForEvent('filechooser');
    await fieldOf('Front recording path').locator('.ex-upload').click();
    await (await chooser).setFiles({name: 'word.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.word});
    await until(async () => await fieldOf('Front recording path').locator('input:not([type=file])').inputValue() === 'audio/word.mp3', 'the uploaded path fills the field');
    assert(Buffer.from(await Deno.readFile(docDir + '/audio/word.mp3')).equals(MEDIA.word), 'the card\'s recording is stored in the document');
    await loads('.ex-form-preview .ex-card-audio[data-side="front"] audio', 'the form\'s preview card loads the recording');
    await fieldOf('Front recording path').locator('.ex-audio-play').click();
    await page.waitForSelector('.ex-form-modal .ex-audio-play.playing', {timeout: 8000});
    assert(true, 'the field\'s ▶ plays it');
    await fieldOf('Front recording path').locator('.ex-audio-play').click();
    await page.locator('.ex-form-preview .ex-card-front .ex-card-play').click();
    await until(async () => !(await player('.ex-form-preview .ex-card-front audio')).paused, 'the preview card\'s 🔊 plays');
    assert(!await page.locator('.ex-form-preview .ex-flashcard:not(.flipped)').count(), 'and does not turn the preview card');
    await page.locator('.ex-form-modal [data-x="save"]').click();
    await until(async () => (await source()).includes('front-audio: audio/word.mp3'), 'the card goes into the text with its recording');
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await openForm('Embedded Jolly flashcard');
    await fieldOf('Front — primary text').locator('textarea').fill('سلام');
    chooser = page.waitForEvent('filechooser');
    await fieldOf('Front — primary text').locator('.ex-insert-audio').click();
    await (await chooser).setFiles({name: 'card.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.card});
    await until(async () => await fieldOf('Front — primary text').locator('textarea').inputValue() === 'سلام\n![](audio/card.mp3)', 'Recording… puts the line in');
    await fieldOf('Back — primary text').locator('textarea').fill('hello');
    await loads('.ex-form-preview figure.audio audio[src*="/audio/card.mp3"]', 'the jolly preview plays the recording on its front');
    // the preview is the page's card, not the dialog's small grey print: its
    // paragraph at the size and in the colour of the card's own text
    const previewText = await page.evaluate(() => {
      const field = document.querySelector('.ex-form-preview .ex-card-front .ex-card-blocks'), p = field.querySelector(':scope > p');
      const fs = getComputedStyle(field), ps = getComputedStyle(p);
      return {same: ps.fontSize === fs.fontSize && ps.color === fs.color, p: [ps.fontSize, ps.color], field: [fs.fontSize, fs.color]};
    });
    assert(previewText.same, 'the form\'s preview draws a card\'s paragraph as the page does ' + JSON.stringify(previewText));
    await page.locator('.ex-form-modal [data-x="save"]').click();
    await until(async () => (await source()).includes('front-primary: |\n  سلام\n  ![](audio/card.mp3)'), 'the jolly card is written with its block');
    await loads(previewAudio('card.mp3'), 'the editor\'s preview draws the card\'s player');
    assert(await exists(docDir + '/audio/card.mp3'), 'the jolly card\'s recording went in through Recording…');
    // an exercise copied as markdown (a card sheet's "copy markdown", words
    // around it): Paste markdown… opens it in the form as a new exercise; in
    // the hub the clip it names comes in from the tray before the form opens,
    // so the form's preview plays it from the document
    let pastedClip = null;
    if (mode === 'parseh') {
      pastedClip = (await (await fetch(`${origin}/clips/api/upload?kind=audio&hint=wound&lang=fa&text=wound`,
                                       {method: 'POST', body: MEDIA.first})).json()).clip;
      assert(!await exists(`${docDir}/${pastedClip.path}`), `a clip in the tray the document does not have (${pastedClip.name})`);
    }
    const pastedFront = '[زخم]{tl}' + (pastedClip ? `\n![](${pastedClip.path})` : '');
    // written as a card sheet writes it: a field of one line on its line, of more as a block
    const pastedCard = ':::exercise flashcard\ncard-type: jolly\nfront-primary: '
      + (pastedFront.includes('\n') ? '|\n' + pastedFront.split('\n').map(x => '  ' + x).join('\n') : pastedFront)
      + '\nback-primary: |\n  | tense | form |\n  |---|---|\n  | past | wound |\nback-secondary: wound the clock\n:::';
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    await page.evaluate(text => navigator.clipboard.writeText(text), 'copied from a card sheet:\n\n' + pastedCard + '\n\nthe end\n');
    await page.evaluate(() => { document.querySelector('#toast').textContent = ''; });
    if (!await page.locator('details.dropdown:has(#btn-exercise)').evaluate(d => d.open))
      await page.locator('details.dropdown:has(#btn-exercise) > summary').click();
    await page.click('#btn-exercise');
    await page.locator('.ex-picker [data-x="paste"]').click();
    assert(await page.evaluate(() => document.activeElement.classList.contains('ex-paste') && !document.querySelector('.ex-type-grid').getClientRects().length),
           'Paste markdown… trades the types for a box to paste into, which has the focus');
    await page.keyboard.press('Control+V');
    await page.locator('.ex-picker [data-x="open"]').click();
    await page.waitForSelector('.ex-form-modal');
    const pastedForm = await page.evaluate(() => ({
      title: document.querySelector('.ex-form-modal h3').textContent,
      save: document.querySelector('.ex-form-modal [data-x="save"]').textContent,
      fields: [...document.querySelectorAll('.ex-form-modal textarea.ex-jolly-text')].map(x => x.value)}));
    assert(JSON.stringify(pastedForm) === JSON.stringify({title: 'Add Embedded Jolly flashcard', save: 'Insert exercise',
                                                          fields: [pastedFront, '', '| tense | form |\n|---|---|\n| past | wound |', 'wound the clock']}),
           'Open in the form: a new jolly card, its four fields as pasted ' + JSON.stringify(pastedForm));
    if (pastedClip) {
      assert(await exists(`${docDir}/${pastedClip.path}`), 'the clip the pasted card names was brought into the document before the form opened');
      await toastSays(/^Brought 1 file from the clip tray$/, 'and it is told');
      const formAudio = `.ex-form-preview figure.audio audio[src="${base}/media/${id}/${pastedClip.path}"]`;
      await loads(formAudio, 'the form\'s preview plays the pasted card\'s clip from the document');
      assert(true, 'the form\'s preview plays the pasted card\'s clip from the document');
    }
    await page.locator('.ex-form-modal [data-x="save"]').click();
    await until(async () => (await source()).includes('\n\n' + pastedCard), 'Insert exercise puts the pasted card in the text, as it was copied and nothing around it');
    assert(!(await source()).includes('copied from a card sheet') && !(await source()).includes('the end'), 'the words around the pasted block stay out');
    // a document not saved yet has no folder to upload into
    const fresh = await context.newPage();
    fresh.on('pageerror', e => errors.push(e.message));
    await fresh.goto(url('/new'));
    await fresh.waitForSelector('#src');
    chooser = fresh.waitForEvent('filechooser');
    await fresh.locator('label[for="audio-upload"]').click();
    await (await chooser).setFiles({name: 'tone.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.tone});
    await until(async () => /^Save the document first/.test(await fresh.locator('#toast').textContent()), 'an unsaved document: the Audio button says to save first');
    await fresh.locator('details.dropdown:has(#btn-exercise) > summary').click();
    await fresh.click('#btn-exercise');
    await fresh.locator('.ex-type').filter({hasText: 'Embedded vocabulary flashcard'}).click();
    chooser = fresh.waitForEvent('filechooser');
    await fresh.locator('.ex-form-modal .ex-author-field').filter({has: fresh.locator(':scope > span:text-is("Back recording path")')}).locator('.ex-upload').click();
    await (await chooser).setFiles({name: 'tone.mp3', mimeType: 'audio/mpeg', buffer: MEDIA.tone});
    await until(async () => (await fresh.locator('#toast').textContent()).includes('Save the document first'), 'an unsaved document: the form says to save first');
    assert(true, 'a document not saved yet: "Save the document first", from the toolbar and from the form');
    await fresh.close();
    await page.click('#btn-save');
    await toastSays(/^Saved$/, 'saved with its cards');

    /* ---------------- g) a rich jolly card on the document page ---------------- */
    console.log('g) a rich jolly card on the document page');
    for (const [width, height, name] of [[1280, 900, 'desktop'], [400, 860, '400px']]) {
      const view = await context.newPage();
      view.on('pageerror', e => errors.push(e.message));
      await view.setViewportSize({width, height});
      await view.goto(url(`/doc/${info.rich_doc_id}`));
      await view.waitForSelector('.ex-flashcard[data-card-type="jolly"]');
      await until(async () => view.evaluate(() => [...document.querySelectorAll('#sheet audio')].every(a => a.closest('[hidden]') || a.readyState >= 1)),
                  `${name}: every recording on the page loads`);
      // the jolly card turned, so its table and list show
      await view.locator('.ex-flashcard[data-card-type="jolly"] .ex-card-field.secondary').first().click();
      const out = await view.evaluate(() => {
        const card = document.querySelector('.ex-flashcard[data-card-type="jolly"]'), cr = card.getBoundingClientRect();
        const bad = [];
        card.querySelectorAll('.ex-card-back table, .ex-card-back ul, .ex-card-back figure, .ex-card-back img, .ex-card-back .box').forEach(x => {
          const r = x.getBoundingClientRect();
          if (r.left < cr.left - 1 || r.right > cr.right + 1) bad.push(x.tagName + ' ' + r.left + '-' + r.right);
        });
        return {bad, flipped: card.classList.contains('flipped'), sideways: document.documentElement.scrollWidth > innerWidth + 1,
                img: [...card.querySelectorAll('.ex-card-back img')].every(i => i.complete && i.naturalWidth > 0)};
      });
      assert(out.flipped && !out.bad.length && !out.sideways && out.img,
             `${name}: the turned jolly card holds its table, list, box and picture inside it, the page does not scroll sideways ` + JSON.stringify(out));
      // the recordings on the page: as wide as written on a desktop; on a
      // phone never so narrow that the player loses its timeline (18rem, or
      // the whole column), inside the column, on the side written
      const players = await view.evaluate(() => {
        const floor = 18 * parseFloat(getComputedStyle(document.documentElement).fontSize);
        return [...document.querySelectorAll('#sheet figure.audio')].filter(f => !f.closest('.ex-flashcard')).map(f => {
          const box = f.parentElement, cs = getComputedStyle(box), br = box.getBoundingClientRect();
          const left = br.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth);
          const right = br.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth);
          const fr = f.getBoundingClientRect(), a = f.querySelector('audio').getBoundingClientRect();
          return {width: +f.dataset.width, align: f.dataset.align, player: Math.round(a.width), column: Math.round(right - left),
                  floor: Math.round(Math.min(floor, right - left)), gaps: [Math.round(fr.left - left), Math.round(right - fr.right)],
                  inside: fr.left >= left - 1 && fr.right <= right + 1 && a.left >= fr.left - 1 && a.right <= fr.right + 1};
        });
      });
      const wrong = players.filter(p => !p.inside || (width < 800
        ? p.player < p.floor - 1 || (p.align === 'center' && Math.abs(p.gaps[0] - p.gaps[1]) > 2)
          || (p.align === 'left' && p.gaps[0] > 1) || (p.align === 'right' && p.gaps[1] > 1)
        : Math.abs(p.player - p.column * p.width / 100) > 2));
      assert(players.length === 4 && !wrong.length,
             `${name}: the page's recordings are ${width < 800 ? 'wide enough for a timeline' : 'as wide as written'}, inside their column, on their side ` + JSON.stringify(players));
      if (SHOTS) {
        await view.locator('.ex-flashcard[data-card-type="jolly"]').scrollIntoViewIfNeeded();
        await view.screenshot({path: `${SHOTS}/studio-audio-${mode}-card-${name}.png`, fullPage: width < 800});
        await view.locator('.ex-flashcard[data-card-type="jolly"]').screenshot({path: `${SHOTS}/studio-audio-${mode}-card-only-${name}.png`});
      }
      await view.close();
    }

    /* ---------------- h) the clip tray's own page ---------------- */
    if (mode === 'parseh') {
      console.log('h) the clip tray\'s page');
      const frame = (await (await fetch(`${origin}/clips/api/upload?kind=image&hint=frame&lang=it&text=${encodeURIComponent('a frame')}`,
                                        {method: 'POST', body: MEDIA.picture})).json()).clip;
      const listed = (await (await fetch(`${origin}/clips/api/list`)).json()).clips;
      const trayFiles = async () => [...Deno.readDirSync(info.tray)].map(e => e.name).sort();
      assert(listed.length === 4 && listed[0].name === frame.name, `four clips in the tray, a frame of another language among them (${listed.map(c => c.name).join(', ')})`);
      const tray = await context.newPage();
      tray.on('pageerror', e => errors.push(e.message));
      const asked = [];
      tray.on('dialog', d => { asked.push(d.message()); d.accept(); });
      await tray.goto(origin + '/');
      const door = tray.locator('a.door.wide[href="/clips/"]');
      assert(await door.locator('.tag').textContent() === '4 clips', 'the hub has a door to the clip tray, saying how many clips wait in it');
      await Promise.all([tray.waitForURL(origin + '/clips/'), door.click()]);
      const rows = () => tray.locator('.crow').evaluateAll(rs => rs.map(r => r.dataset.name));
      assert(JSON.stringify(await rows()) === JSON.stringify(listed.map(c => c.name)), 'the tray page lists every clip, newest first, whatever its language');
      assert(await tray.locator('#count').textContent() === '4 clips in the tray', 'and says how many');
      await until(() => tray.evaluate(n => { const i = document.querySelector(`.crow[data-name="${n}"] img`); return i && i.complete && i.naturalWidth > 0; }, frame.name),
                  'the frame shows');
      const sound = `.crow[data-name="${pastedClip.name}"] audio`;
      await tray.locator(sound).evaluate(a => a.play());
      await until(() => tray.evaluate(s => { const a = document.querySelector(s); return a.readyState >= 1 && !a.paused && a.currentTime > 0.1; }, sound), 'a recording plays on the tray page');
      assert(true, 'a recording plays on the tray page, and a frame shows');
      await tray.locator(`.crow[data-name="${pastedClip.name}"] .del`).click();
      await until(async () => !(await rows()).includes(pastedClip.name), '✕ takes the clip off the page');
      assert(asked.length === 1 && asked[0].startsWith(`Delete “${pastedClip.name}” from the clip tray?`), 'it asks first: ' + JSON.stringify(asked));
      assert(!(await trayFiles()).some(n => n.startsWith(pastedClip.name)) && await exists(`${docDir}/${pastedClip.path}`)
             && await tray.locator('#count').textContent() === '3 clips in the tray',
             '✕ deletes the clip and its JSON from the tray; the document it went into keeps its copy');
      await tray.setViewportSize({width: 400, height: 800});
      const narrow = await tray.evaluate(() => ({sideways: document.documentElement.scrollWidth > innerWidth + 1,
        inside: [...document.querySelectorAll('.crow')].every(r => { const b = r.getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth + 1; })}));
      assert(!narrow.sideways && narrow.inside, 'at 400 px the tray page does not scroll sideways ' + JSON.stringify(narrow));
      if (SHOTS) await tray.screenshot({path: `${SHOTS}/studio-audio-${mode}-tray-400px.png`, fullPage: true});
      await tray.setViewportSize({width: 1280, height: 900});
      if (SHOTS) await tray.screenshot({path: `${SHOTS}/studio-audio-${mode}-tray.png`});
      await tray.click('#empty-tray');
      await tray.waitForSelector('#none:not([hidden])');
      assert(asked.length === 2 && asked[1].startsWith('Delete all 3 clips in the tray?'), 'Empty the tray asks first: ' + JSON.stringify(asked[1]));
      assert(!await tray.locator('.crow').count() && await tray.locator('#empty-tray').isDisabled() && (await trayFiles()).length === 0,
             `Empty the tray deletes every clip: the page says the tray is empty, the folder holds nothing (${JSON.stringify(await trayFiles())})`);
      assert(await exists(`${docDir}/${info.clips[0].path}`) && await exists(`${docDir}/${bye.path}`), 'the clips the document took stay in the document');
      await tray.goto(origin + '/');
      assert(await tray.locator('a.door.wide[href="/clips/"] .tag').textContent() === 'the tray is empty', 'the hub\'s door says the tray is empty');
      await tray.close();
    }

    assert(!errors.length, 'no page error: ' + errors.join(' | '));
    assert(!/Traceback/.test(log.join('')), 'no traceback in the server log');
  } finally {
    await browser.close();
    try { proc.kill('SIGTERM'); } catch (_) {}
    await proc.status;
  }
}

for (const mode of modes) await suite(mode);
console.log(`\nstudio_audio: ${passed} checks passed`);
