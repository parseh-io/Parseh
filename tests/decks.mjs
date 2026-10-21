// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of the Exercises door: decks.html, deck.html, study.html
// (static/decks.js and the dk- CSS) and a document page's "+ Deck", against
// the REAL routes (deckroutes, decks.py, the studio) on a temporary library
// and a temporary exercises store.  Three modes:
//   studio  tests/decks_harness.py, the studio's own server (studio at /)
//   parseh  tests/decks_harness.py, Parseh's handler (studio at /studio);
//           both seeded through decks.py, every page of the door in detail
//   e2e     serve.py itself (its main(), through runpy) with store.LIB,
//           decks.DIR and the clip trays pointed at a temporary tree first,
//           filled only the way a learner fills it: a document through the
//           studio's API, then the hub, "+ Deck", browse and edit, study,
//           export and import, the studio library's "Download N shown",
//           recordings uploaded from the exercise form and played on the
//           study card, and a card copied as markdown (the card kit's own
//           markdown, its clip in the tray) pasted into Add exercise
// The recordings are real: ffmpeg (on the PATH) writes the tones and the
// picture once; without it those sections say so and are left out.
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/decks.mjs
//   DECKS_MODES=e2e (or studio,parseh ...) runs only those; SHOTS=<dir> also
//   saves screenshots (the study page with a rich jolly card among them)
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
const modes = (Deno.env.get('DECKS_MODES') || 'studio,parseh,e2e').split(',');

async function startHarness(mode) {
  const proc = new Deno.Command(python, {args: [root + '/tests/decks_harness.py', mode], cwd: root,
                                         stdout: 'piped', stderr: 'inherit'}).spawn();
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '', info = null;
  while (!info) {
    const {value, done} = await reader.read();
    if (done) throw Error(`harness (${mode}) exited before READY:\n` + buf);
    buf += value;
    const m = buf.match(/READY (\{.*\})\n/);
    if (m) info = JSON.parse(m[1]);
  }
  (async () => { for (;;) { const r = await reader.read(); if (r.done) break; } })();
  return {proc, info};
}

// exercises for the decks the study tests make for themselves
const MATCH_EX = ':::exercise match-translations\nprompt: Match them\nexplanation-incorrect: [سلام]{tl} is a greeting\n'
  + '- [سلام]{tl} => hello\n- [کتاب]{tl} => book\n:::';
const FILL_EX = ':::exercise fill-blanks\nprompt: Fill it\ntext: [[slot]] means hello\n- [slot] [سلام]{tl}\n- [ ] [کتاب]{tl}\n:::';
// the same, carrying the two pictures an exercise may have of its own
const MATCH_PIC_EX = MATCH_EX.replace('prompt: Match them\n',
  'prompt: Match them\nimage: images/cat.png\nimage-answer: images/dog.png\n');
const PICK_EX = ':::exercise single-choice\nprompt: Pick the greeting\n- [x] [سلام]{tl}\n- [ ] [کتاب]{tl}\n:::';
const ORDER_EX = ':::exercise order-sentences\nprompt: Put them in order\n- [1] first\n- [2] second\n- [3] third\n:::';
const TF_EX = ':::exercise true-false\nprompt: True or false?\n- [سلام]{tl} is a greeting => true\n:::';
const YN_EX = ':::exercise yes-no\nprompt: Yes or no?\n- Is [کتاب]{tl} a book? => yes\n:::';
const CAT_EX = ':::exercise flashcard\ncard-type: vocab\ntarget: [گربه]{tl}\nmeaning: cat\n:::';
// two different one-pixel PNGs
const PNG_A = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
const PNG_B = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=', 'base64');

/* Real media, written by ffmpeg for this run: three tones of different
   pitch and length (a: 4 s, b: 8 s, c: 3 s) and a picture.  MEDIA.ok is
   false where ffmpeg cannot write them. */
const MEDIA = await (async () => {
  const dir = await Deno.makeTempDir({prefix: 'parseh-decks-media-'});
  const run = async (args, out) => {
    try {
      const r = await new Deno.Command('ffmpeg', {args: ['-y', '-loglevel', 'error', ...args, `${dir}/${out}`],
                                                  stdout: 'null', stderr: 'null'}).output();
      return r.success ? Buffer.from(await Deno.readFile(`${dir}/${out}`)) : null;
    } catch (_) { return null; }
  };
  const tone = (freq, secs, out) => run(['-f', 'lavfi', '-i', `sine=frequency=${freq}:duration=${secs}`,
                                          '-c:a', 'libmp3lame'], out);
  const media = {a: await tone(440, 4, 'a.mp3'), b: await tone(660, 8, 'b.mp3'), c: await tone(880, 3, 'c.mp3'),
                 pic: await run(['-f', 'lavfi', '-i', 'testsrc=size=320x180', '-frames:v', '1'], 'pic.png')};
  await Deno.remove(dir, {recursive: true}).catch(() => {});
  media.ok = !!(media.a && media.b && media.c && media.pic);
  return media;
})();

/* A deck's recordings as a learner meets them, in both kinds of server:
   uploaded from the exercise form (a vocabulary card's recording fields, a
   jolly card's Recording…), served a byte range at a time, played on the
   study card -- the side in view by itself, the back when the card is
   turned -- and stopped when it is rated; a press on a player or on 🔊
   never turns the card, a click on it, Enter and Show answer do; carried
   out in the export and back in by an import, where it plays again, and
   turned in the enlarged card's window, where the window's copy plays.
   `t`: {page, request, url, assert, toast(page, re, what), zip(bytes),
   refusal: whether to try a file that is not a recording (a 400 answer)} */
/* The exercise form's fields and file choosers, on `page`. */
function formKit(page, assert) {
  const fieldOf = label => page.locator(`.ex-form-modal .ex-author-field:has(> span:text-is("${label}"))`);
  const choose = async (button, file) => {
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), button.click()]);
    await chooser.setFiles(file);
  };
  const holds = async (input, want, what) => {
    for (let i = 0; i < 160 && !(await input.inputValue()).includes(want); i++) await page.waitForTimeout(50);
    assert((await input.inputValue()).includes(want), `${what} (“${await input.inputValue()}”)`);
  };
  const mp3 = (name, buffer) => ({name, mimeType: 'audio/mpeg', buffer});
  // two saves answer the same toast: the second must not be read off the first
  const clearToast = () => page.evaluate(() => { const x = document.querySelector('#toast'); if (x) x.textContent = ''; });
  return {fieldOf, choose, holds, mp3, clearToast};
}

async function recordingsFlow(t) {
  const {page, url, assert} = t;
  if (!MEDIA.ok) { console.log('  (recordings left out: ffmpeg could not write the tones here)'); return; }
  const deck = (await (await t.request.post(url('/exercises/api/decks'), {data: {name: 'Recordings', lang: 'fa'}})).json()).deck;
  const api = `/exercises/api/decks/${deck.path}`;
  // what played and what stopped, by file name, from the first moment of every page
  await page.addInitScript(() => {
    window.__played = []; window.__paused = [];
    const name = e => (e.target.currentSrc || e.target.src || '').replace(/^.*\/audio\//, '');
    document.addEventListener('play', e => window.__played.push(name(e)), true);
    document.addEventListener('pause', e => window.__paused.push([name(e), e.target.currentTime, e.target.duration]), true);
  });
  const {fieldOf, choose, holds, mp3, clearToast} = formKit(page, assert);
  const uploads = [];
  page.on('request', r => { if (r.method() === 'POST' && /\/audio\?name=/.test(r.url())) uploads.push(new URL(r.url()).pathname + new URL(r.url()).search); });

  await page.goto(url(`/exercises/deck/${deck.path}/`));
  await page.waitForSelector('#browse-empty:not([hidden])');
  // a vocabulary card, a recording on each side through its field's Upload…
  await page.click('#btn-add-exercise');
  await page.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
  await page.waitForSelector('.ex-form-modal');
  await fieldOf('Word or expression').locator('textarea').fill('[سلام]{tl}');
  await fieldOf('Meaning').locator('textarea').fill('hello');
  await choose(fieldOf('Front recording path').locator('.ex-upload'), mp3('Salam.mp3', MEDIA.a));
  await holds(fieldOf('Front recording path').locator('input[type="text"]'), 'audio/salam.mp3', 'Upload… fills in the front recording');
  assert(uploads[0] === `${api}/audio?name=Salam.mp3`, `the recording goes to the deck, raw, named (${uploads[0]})`);
  await choose(fieldOf('Back recording path').locator('.ex-upload'), mp3('Hello.mp3', MEDIA.b));
  const backField = fieldOf('Back recording path').locator('input[type="text"]');
  await holds(backField, 'audio/hello.mp3', 'and the back one');
  if (t.refusal) {
    await choose(fieldOf('Back recording path').locator('.ex-upload'), mp3('notes.mp3', Buffer.from('only text, however it is named')));
    await t.toast(page, /^Could not upload the recording: only MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM recordings can be added$/,
                  'a file that is not a recording is refused');
    assert(await backField.inputValue() === 'audio/hello.mp3', 'the field keeps its recording');
  }
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await t.toast(page, /^Added to “Recordings”$/, 'the vocabulary card added with its recordings, and no warning');
  await page.waitForSelector('.dk-row');

  // a jolly card: Recording… puts the line in the field, at the cursor
  await page.click('#btn-add-exercise');
  await page.locator('.ex-type', {hasText: 'Embedded Jolly flashcard'}).click();
  await page.waitForSelector('.ex-form-modal');
  const jollyFront = fieldOf('Front — primary text').locator('textarea');
  await jollyFront.fill('[خداحافظ]{tl}');
  await choose(fieldOf('Front — primary text').locator('.ex-insert-audio'), mp3('Goodbye.mp3', MEDIA.c));
  await holds(jollyFront, '![](audio/goodbye.mp3)', 'Recording… puts the recording in the jolly field');
  assert(await jollyFront.inputValue() === '[خداحافظ]{tl}\n![](audio/goodbye.mp3)', 'on a line of its own, where the cursor was');
  await fieldOf('Back — primary text').locator('textarea').fill('goodbye');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await t.toast(page, /^Added to “Recordings”$/, 'the jolly card added with its recording');
  const items = (await (await t.request.get(url(api))).json()).items;
  assert(items.length === 2 && items[0].markdown.includes('\nfront-audio: audio/salam.mp3\n')
         && items[0].markdown.includes('\nback-audio: audio/hello.mp3\n')
         && items[1].markdown.includes('\n  ![](audio/goodbye.mp3)\n'), 'the two exercises name their recordings');
  for (const [name, bytes] of [['salam.mp3', MEDIA.a], ['hello.mp3', MEDIA.b], ['goodbye.mp3', MEDIA.c]]) {
    const got = await t.request.get(url(`/exercises/media/${deck.path}/audio/${name}`));
    assert(got.status() === 200 && got.headers()['content-type'] === 'audio/mpeg' && Buffer.compare(await got.body(), bytes) === 0,
           `the deck serves audio/${name}, as uploaded`);
  }
  const ranged = await t.request.get(url(`/exercises/media/${deck.path}/audio/hello.mp3`), {headers: {Range: 'bytes=100-199'}});
  assert(ranged.status() === 206 && ranged.headers()['content-range'] === `bytes 100-199/${MEDIA.b.length}`
         && Buffer.compare(await ranged.body(), MEDIA.b.subarray(100, 200)) === 0, 'and a byte range of one: 206');

  // study, opened as a learner opens it (a click, which lets the page play sound)
  const media = sel => page.evaluate(s => {
    const a = document.querySelector(s);
    return a ? {ready: a.readyState, time: a.currentTime, paused: a.paused, duration: a.duration} : null;
  }, sel);
  const soundAt = async (sel, what) => {
    const ok = await page.waitForFunction(s => {
      const a = document.querySelector(s);
      return !!a && a.readyState >= 1 && a.currentTime > 0.05;
    }, sel, {timeout: 10000}).then(() => true, () => false);
    const m = await media(sel);
    assert(ok, `${what} (${JSON.stringify(m)})`);
    return m;
  };
  const turned = () => page.locator('#study-stage .ex-flashcard').evaluate(c => c.classList.contains('flipped'));
  const notShown = async () => !(await turned()) && await page.locator('#rating-bar').isHidden() && await page.locator('#btn-show').isVisible();
  await Promise.all([page.waitForURL(url(`/exercises/deck/${deck.path}/study`)), page.click('#btn-study')]);
  await page.waitForSelector('#study-stage .ex-flashcard[data-card-type="vocab"]');
  const FRONT = '#study-stage .ex-card-front .ex-card-audio audio', BACK = '#study-stage .ex-card-back .ex-card-audio audio';
  await soundAt(FRONT, 'the card shown plays its front recording by itself');
  assert(JSON.stringify(await page.evaluate(() => window.__played)) === '["salam.mp3"]', 'that one, once, and nothing else');
  assert(await notShown(), 'playing is not the answer shown: the card is not turned, no rating bar');
  await page.click('#study-stage .ex-card-front .ex-card-play');
  await page.waitForFunction(s => document.querySelector(s).paused, FRONT);
  assert(await notShown(), '🔊 stops it, and turns nothing');
  await page.click('#study-stage .ex-card-front .ex-card-play');
  await page.waitForFunction(s => !document.querySelector(s).paused, FRONT);
  assert(await notShown(), '🔊 plays it again, and turns nothing');
  await page.locator('#study-stage .ex-card-front .ex-card-field').first().click();
  await page.waitForSelector('#rating-bar:not([hidden])');
  assert(await turned(), 'a click on the card itself turns it: the answer shown');
  await soundAt(BACK, 'turned, the card plays its back recording');
  assert((await media(FRONT)).paused, 'and the front one, out of sight, has stopped');
  // rated, it stops at once: not when the next card replaces it, which waits for the answer to be saved
  let release;
  const held = new Promise(r => { release = r; });
  const isReview = u => u.pathname.endsWith('/review');
  await page.route(isReview, async route => { await held; await route.continue(); });
  await page.keyboard.press('3');
  const stopped = await page.waitForFunction(s => document.querySelector(s).paused, BACK, {timeout: 3000})
    .then(() => true, () => false);
  const stops = await page.evaluate(() => window.__paused.filter(p => p[0] === 'hello.mp3'));
  assert(stopped && await page.locator('#study-stage .ex-flashcard[data-card-type="vocab"]').count() === 1
         && stops.length === 1 && stops[0][1] < stops[0][2] - 2,
         `rated, the back recording stops where it was, while the answer is still on its way (${JSON.stringify(stops)})`);
  release();
  await page.unroute(isReview);
  await page.waitForSelector('#study-stage .ex-flashcard[data-card-type="jolly"]');

  // the jolly card: a player of its own, among its lines, which plays by itself as the card is shown
  const PLAYER = '#study-stage .ex-card-front figure.audio audio';
  await soundAt(PLAYER, "the jolly card shown plays its recording line by itself");
  const heard = await page.evaluate(() => window.__played);
  assert(heard.filter(n => n === 'goodbye.mp3').length === 1 && heard[heard.length - 1] === 'goodbye.mp3',
         `that one, once (${JSON.stringify(heard)})`);
  assert(await notShown(), 'playing is not the answer shown');
  const box = await page.locator(PLAYER).boundingBox();
  assert(box && box.width > 100 && box.height > 10, `the jolly card's player is on the card (${JSON.stringify(box)})`);
  // stopped and wound back, so that only its ▶ can play it again
  await page.evaluate(s => { const a = document.querySelector(s); a.pause(); a.currentTime = 0; }, PLAYER);
  await page.mouse.click(box.x + Math.min(24, box.height / 2 + 6), box.y + box.height / 2);   // its ▶
  const pressed = await page.waitForFunction(s => { const a = document.querySelector(s); return !a.paused && a.currentTime > 0.05; },
                                             PLAYER, {timeout: 10000}).then(() => true, () => false);
  assert(pressed, `the player's ▶ plays the recording on the study card (${JSON.stringify(await media(PLAYER))})`);
  assert(await notShown(), 'a press on the player turns nothing');
  await page.mouse.click(box.x + box.width * 0.55, box.y + box.height / 2);                   // its timeline
  await page.waitForTimeout(150);
  assert(await notShown(), 'nor a press on its timeline');
  await page.locator('#study-stage .ex-flashcard').focus();
  await page.keyboard.press('Enter');
  await page.waitForSelector('#rating-bar:not([hidden])');
  assert(await turned() && (await media(PLAYER)).paused, 'Enter on the card turns it, and the player out of sight stops');
  await page.keyboard.press('4');
  // the vocabulary card is back (learn-ahead): Show answer
  await page.waitForSelector('#study-stage .ex-flashcard[data-card-type="vocab"]');
  await soundAt(FRONT, 'the card back again plays its front recording again');
  await page.click('#btn-show');
  await page.waitForSelector('#rating-bar:not([hidden])');
  await soundAt(BACK, 'Show answer turns it, and its back recording plays');
  await page.keyboard.press('4');
  await page.waitForSelector('#study-done:not([hidden])');
  assert(JSON.stringify(await page.evaluate(() => window.__played.filter(n => n !== 'goodbye.mp3')))
         === '["salam.mp3","salam.mp3","hello.mp3","salam.mp3","hello.mp3"]',
         'each recording played when it was meant to: shown, 🔊, turned, shown again, Show answer');

  // export, and back in as a copy that starts new: it plays there
  const zip = await (await t.request.get(url(`${api}/export?scheduling=1`))).body();
  const entries = await t.zip(zip);
  const ids = items.map(i => i.id).sort();
  assert(JSON.stringify(entries.map(e => e[0]).sort()) === JSON.stringify([
           'audio/goodbye.mp3', 'audio/hello.mp3', 'audio/salam.mp3', ...ids.map(i => `items/${i}.json`),
           'parseh-exercise-deck.json', ...ids.map(i => `schedule/${i}.json`)].sort()),
         `the export holds the three recordings (${entries.map(e => e[0]).join(', ')})`);
  assert(entries.filter(e => e[0].startsWith('audio/')).every(e => e[1] === 0), 'stored as they are, not squeezed');
  await page.goto(url('/exercises/'));
  await page.waitForSelector('.dk-card');
  await page.setInputFiles('#file-import', {name: 'recordings.zip', mimeType: 'application/zip', buffer: Buffer.from(zip)});
  await page.waitForSelector('.dk-modal input[type=checkbox]');
  await page.locator('.dk-modal input[type=checkbox]').uncheck();
  await page.locator('.dk-modal button', {hasText: /^Import$/}).click();
  await page.waitForSelector('.dk-modal h3:text("This deck is already here")');
  await clearToast();
  await page.locator('.dk-modal button', {hasText: 'Import as a copy'}).click();
  await t.toast(page, /^Imported “Recordings \(copy\)”: 2 exercises, all new$/, 'imported back as a copy');
  const copy = (await (await t.request.get(url('/exercises/api/decks?lang=fa'))).json()).decks.find(d => d.name === 'Recordings (copy)');
  for (const [name, bytes] of [['salam.mp3', MEDIA.a], ['hello.mp3', MEDIA.b], ['goodbye.mp3', MEDIA.c]]) {
    const got = await t.request.get(url(`/exercises/media/${copy.path}/audio/${name}`));
    assert(got.status() === 200 && Buffer.compare(await got.body(), bytes) === 0, `the copy holds audio/${name}, byte for byte`);
  }
  await page.goto(url(`/exercises/deck/${copy.path}/`));
  await page.waitForSelector('.dk-row');
  await Promise.all([page.waitForURL(url(`/exercises/deck/${copy.path}/study`)), page.click('#btn-study')]);
  await page.waitForSelector('#study-stage .ex-flashcard[data-card-type="vocab"]');
  const src = await page.locator(FRONT).getAttribute('src');
  assert(src === `/exercises/media/${copy.path}/audio/salam.mp3`, `the imported card plays from the copy (${src})`);
  await soundAt(FRONT, 'and the imported recording plays');

  // enlarged, the card in the window is the one in view: turned there, its
  // copy plays the back recording, which its own 🔊 shows and stops, and
  // the card covered by the window keeps still
  await page.click('#study-stage .ex-card-zoom');
  await page.waitForSelector('.ex-zoom-overlay .ex-flashcard');
  assert((await media(FRONT)).paused, 'enlarged, the card underneath stops its front recording');
  await page.locator('.ex-zoom-overlay .ex-card-front .ex-card-field').first().click();
  await page.waitForSelector('#rating-bar:not([hidden])', {state: 'attached'});
  const ZOOM_BACK = '.ex-zoom-overlay .ex-card-back .ex-card-audio audio';
  await soundAt(ZOOM_BACK, 'turned in the window, the enlarged card plays its back recording');
  const still = await page.evaluate(() => [...document.querySelectorAll('#study-stage audio')]
    .map(a => [a.getAttribute('src').replace(/^.*\//, ''), a.paused, a.currentTime > 0.05 && a.closest('.ex-card-back') !== null]));
  assert(still.every(([, paused, backPlayed]) => paused && !backPlayed),
         `and the card under the window plays nothing, its back recording never started (${JSON.stringify(still)})`);
  assert(await page.locator('.ex-zoom-overlay .ex-card-back .ex-card-play').evaluate(b => b.classList.contains('playing')),
         "the window's 🔊 shows the recording playing");
  await page.click('.ex-zoom-overlay .ex-card-back .ex-card-play');
  const quiet = await page.waitForFunction(() => [...document.querySelectorAll('audio')].every(a => a.paused), null, {timeout: 3000})
    .then(() => true, () => false);
  assert(quiet, "the window's 🔊 stops it: nothing plays anywhere");
  await page.keyboard.press('Escape');
  await page.waitForSelector('.ex-zoom-overlay', {state: 'detached'});
  assert(await turned() && await page.locator('#rating-bar').isVisible(), 'the turn in the window was the answer shown');
  await page.locator('#btn-skip').click();
  return deck;
}

/* A jolly card's recording lines, played on the study card as Anki plays a
   card's sounds: shown, the first recording on its front, once (the one
   after it keeps still); turned, the first on its back.  The first on the
   front is laid out with a clip window, and plays that window only, though
   the page starts it before the file has said how long it is; its ▶,
   pressed at the window's end, plays the window again.  Turned in
   the enlarged card's window, the window's copy plays, and the card under
   it keeps still.  The card is written in the exercise form: its recordings
   put in with Recording…, the window typed by hand.
   `t`: as recordingsFlow's */
async function jollyRecordingsFlow(t) {
  const {page, url, assert} = t;
  if (!MEDIA.ok) { console.log('  (recordings left out: ffmpeg could not write the tones here)'); return; }
  const deck = (await (await t.request.post(url('/exercises/api/decks'), {data: {name: 'Jolly recordings', lang: 'fa'}})).json()).deck;
  // what played, what it was at while it played, and where it stopped: by file name, the window's copy as zoom:<name>
  await page.addInitScript(() => {
    window.__heard = [];
    const name = e => (e.target.closest('.ex-zoom-overlay') ? 'zoom:' : '')
      + (e.target.currentSrc || e.target.src || '').replace(/^.*\/audio\//, '').replace(/#.*$/, '');
    document.addEventListener('play', e => window.__heard.push([name(e), 'play', e.target.readyState]), true);
    document.addEventListener('timeupdate', e => { if (!e.target.paused) window.__heard.push([name(e), 'at', e.target.currentTime]); }, true);
    document.addEventListener('pause', e => window.__heard.push([name(e), 'pause', e.target.currentTime]), true);
  });
  const {fieldOf, choose, holds, mp3, clearToast} = formKit(page, assert);

  await page.goto(url(`/exercises/deck/${deck.path}/`));
  await page.waitForSelector('#browse-empty:not([hidden])');
  await page.click('#btn-add-exercise');
  await page.locator('.ex-type', {hasText: 'Embedded Jolly flashcard'}).click();
  await page.waitForSelector('.ex-form-modal');
  const front = fieldOf('Front — primary text').locator('textarea');
  await front.fill('[سلام]{tl}');
  await choose(fieldOf('Front — primary text').locator('.ex-insert-audio'), mp3('Slowly.mp3', MEDIA.a));
  await holds(front, '![](audio/slowly.mp3)', 'Recording… puts the first recording on the front');
  await choose(fieldOf('Front — primary text').locator('.ex-insert-audio'), mp3('Again.mp3', MEDIA.c));
  await holds(front, '![](audio/again.mp3)', 'and a second one under it');
  // the first one's clip window, typed by hand: from 1 s to 2.5 s of a 4 s tone
  await front.fill((await front.inputValue()).replace('![](audio/slowly.mp3)', '![](audio/slowly.mp3){start=1 end=2.5}'));
  const back = fieldOf('Back — primary text').locator('textarea');
  await back.fill('hello');
  await choose(fieldOf('Back — primary text').locator('.ex-insert-audio'), mp3('Hello.mp3', MEDIA.b));
  await holds(back, '![](audio/hello.mp3)', 'Recording… puts a recording on the back');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await t.toast(page, /^Added to “Jolly recordings”$/, 'the jolly card added with its three recordings, and no warning');
  const [item] = (await (await t.request.get(url(`/exercises/api/decks/${deck.path}`))).json()).items;
  assert(item.markdown.includes('\n  [سلام]{tl}\n  ![](audio/slowly.mp3){start=1 end=2.5}\n  ![](audio/again.mp3)\n')
         && item.markdown.includes('\n  hello\n  ![](audio/hello.mp3)\n'), `the card names them in that order (${JSON.stringify(item.markdown)})`);
  await page.waitForSelector('.dk-row');

  const SLOW = '#study-stage .ex-card-front figure.audio audio[src$="/audio/slowly.mp3#t=1,2.5"]';
  const AGAIN = '#study-stage .ex-card-front figure.audio audio[src$="/audio/again.mp3"]';
  const HELLO = '#study-stage .ex-card-back figure.audio audio[src$="/audio/hello.mp3"]';
  const ZOOM_HELLO = '.ex-zoom-overlay .ex-card-back figure.audio audio[src$="/audio/hello.mp3"]';
  const media = sel => page.evaluate(s => {
    const a = document.querySelector(s);
    return a ? {ready: a.readyState, time: a.currentTime, paused: a.paused} : null;
  }, sel);
  const still = async sel => { const m = await media(sel); return !!m && m.paused && m.time === 0; };
  const heard = () => page.evaluate(() => window.__heard);
  const plays = async () => (await heard()).filter(h => h[1] === 'play').map(h => h[0]);
  const turned = () => page.locator('#study-stage .ex-flashcard').evaluate(c => c.classList.contains('flipped'));
  const notShown = async () => !(await turned()) && await page.locator('#rating-bar').isHidden() && await page.locator('#btn-show').isVisible();
  // the window: played (after the event `from`) from its start, and stopped by itself inside it, well past the half
  const inWindow = async (from, what) => {
    const ok = await page.waitForFunction(([s, from]) => {
      const a = document.querySelector(s);
      return !!a && a.readyState >= 1 && a.paused && a.currentTime > 1.5
        && window.__heard.slice(from).some(h => h[0] === 'slowly.mp3' && h[1] === 'play');
    }, [SLOW, from], {timeout: 10000}).then(() => true, () => false);
    const m = await media(SLOW);
    const times = (await heard()).slice(from).filter(h => h[0] === 'slowly.mp3' && h[1] === 'at').map(h => h[2]);
    assert(ok && m.time >= 2.3 && m.time <= 2.7 && times.length > 0 && Math.min(...times) >= 0.95 && Math.max(...times) <= 2.7,
           `${what}, its window only: from 1 s, stopped at ${m.time} s ` +
           `(${JSON.stringify(m)}, while playing ${times.length ? Math.min(...times) + '…' + Math.max(...times) : 'nothing'})`);
  };

  // studied, opened as a learner opens it (a click, which lets the page play sound)
  await Promise.all([page.waitForURL(url(`/exercises/deck/${deck.path}/study`)), page.click('#btn-study')]);
  await page.waitForSelector('#study-stage .ex-flashcard[data-card-type="jolly"]');
  await inWindow(0, 'the first recording on the front plays by itself');
  assert(JSON.stringify(await plays()) === '["slowly.mp3"]',
         `that one, once, and nothing else (${JSON.stringify((await heard()).filter(h => h[1] === 'play'))}: name, play, readyState)`);
  assert(await still(AGAIN) && await still(HELLO), 'the second on the front and the one on the back keep still');
  assert(await notShown(), 'playing is not the answer shown: the card is not turned, no rating bar');
  // played again from its end, where the browser's own #t= stop is spent: the page's window rule alone
  const box = await page.locator(SLOW).boundingBox();
  const replay = (await heard()).length;
  await page.mouse.click(box.x + Math.min(24, box.height / 2 + 6), box.y + box.height / 2);   // its ▶
  await inWindow(replay, "its player's ▶ plays it again");
  assert(await notShown() && JSON.stringify(await plays()) === '["slowly.mp3","slowly.mp3"]', 'and turns nothing');

  // enlarged and turned there: the window's copy plays the back's recording, the card underneath keeps still
  await page.click('#study-stage .ex-card-zoom');
  await page.waitForSelector('.ex-zoom-overlay .ex-flashcard');
  await page.locator('.ex-zoom-overlay .ex-card-front .ex-card-field').first().click({position: {x: 4, y: 4}});
  await page.waitForSelector('#rating-bar:not([hidden])', {state: 'attached'});
  const zoomed = await page.waitForFunction(s => {
    const a = document.querySelector(s);
    return !!a && a.readyState >= 1 && !a.paused && a.currentTime > 0.05;
  }, ZOOM_HELLO, {timeout: 10000}).then(() => true, () => false);
  assert(zoomed, `turned in the window, the enlarged card plays the recording on its back (${JSON.stringify(await media(ZOOM_HELLO))})`);
  assert(await still(HELLO) && await still(AGAIN) && JSON.stringify((await plays()).slice(2)) === '["zoom:hello.mp3"]',
         `and the card under the window plays nothing (${JSON.stringify(await plays())})`);
  await page.keyboard.press('Escape');
  await page.waitForSelector('.ex-zoom-overlay', {state: 'detached'});
  assert(await turned() && await page.locator('#rating-bar').isVisible(), 'the turn in the window was the answer shown');

  // Again: the card is back, and plays its front again; Show answer plays its back on the page
  const from = (await heard()).length;
  await page.keyboard.press('1');
  await page.waitForFunction(() => { const c = document.querySelector('#study-stage .ex-flashcard'); return c && !c.classList.contains('flipped'); });
  await inWindow(from, 'the card back again plays its first front recording by itself again');
  assert(JSON.stringify((await plays()).slice(3)) === '["slowly.mp3"]' && await still(AGAIN) && await still(HELLO),
         `and only that (${JSON.stringify(await plays())})`);
  await page.click('#btn-show');
  await page.waitForSelector('#rating-bar:not([hidden])');
  const backPlays = await page.waitForFunction(s => {
    const a = document.querySelector(s);
    return !!a && a.readyState >= 1 && !a.paused && a.currentTime > 0.05;
  }, HELLO, {timeout: 10000}).then(() => true, () => false);
  assert(backPlays, `Show answer turns it, and the recording on its back plays (${JSON.stringify(await media(HELLO))})`);
  assert((await media(SLOW)).paused && await still(AGAIN) && JSON.stringify((await plays()).slice(3)) === '["slowly.mp3","hello.mp3"]',
         `nothing else on the card plays (${JSON.stringify(await plays())}, ${(await heard()).length - from} events since it came back)`);
  // rated, it stops
  await page.keyboard.press('4');
  await page.waitForSelector('#study-done:not([hidden])');
  assert((await heard()).some(h => h[0] === 'hello.mp3' && h[1] === 'pause'), 'rated, the back recording stops');
}

/* Two things the study page's recordings must not get wrong, on two jolly
   cards made in the exercise form: a clip that starts past the end of its
   recording has nothing to play, and stays silent (played, the page would
   seek back to its start for as long as the card is shown); and a card
   enlarged while its answer is on its way takes its window with it when the
   next card comes, which then plays its own recordings and has the keys.
   `t`: as jollyRecordingsFlow's */
async function studyEdgesFlow(t) {
  const {page, url, assert} = t;
  if (!MEDIA.ok) { console.log('  (recordings left out: ffmpeg could not write the tones here)'); return; }
  const deck = (await (await t.request.post(url('/exercises/api/decks'), {data: {name: 'Jolly edges', lang: 'fa'}})).json()).deck;
  // what played, stopped and seeked, by file name, the window's copy as zoom:<name>
  await page.addInitScript(() => {
    window.__edges = [];
    const name = e => (e.target.closest('.ex-zoom-overlay') ? 'zoom:' : '')
      + (e.target.currentSrc || e.target.src || '').replace(/^.*\/audio\//, '').replace(/#.*$/, '');
    for (const type of ['play', 'pause', 'seeked'])
      document.addEventListener(type, e => window.__edges.push([name(e), type, e.target.currentTime]), true);
  });
  const {fieldOf, choose, holds, mp3, clearToast} = formKit(page, assert);

  await page.goto(url(`/exercises/deck/${deck.path}/`));
  await page.waitForSelector('#browse-empty:not([hidden])');
  const addJolly = async (n, word, front, meaning, back, clip = '') => {
    await page.click('#btn-add-exercise');
    await page.locator('.ex-type', {hasText: 'Embedded Jolly flashcard'}).click();
    await page.waitForSelector('.ex-form-modal');
    const frontText = fieldOf('Front — primary text').locator('textarea');
    await frontText.fill(word);
    await choose(fieldOf('Front — primary text').locator('.ex-insert-audio'), front);
    const line = `![](audio/${front.name.toLowerCase()})`;
    await holds(frontText, line, `Recording… puts ${line} on the front of card ${n}`);
    if (clip) await frontText.fill((await frontText.inputValue()).replace(line, line + clip));   // typed by hand
    const backText = fieldOf('Back — primary text').locator('textarea');
    await backText.fill(meaning);
    await choose(fieldOf('Back — primary text').locator('.ex-insert-audio'), back);
    await holds(backText, `![](audio/${back.name.toLowerCase()})`, 'and one on its back');
    await clearToast();
    await page.click('.ex-form-modal [data-x="save"]');
    await t.toast(page, /^Added to “Jolly edges”$/, `card ${n} added, with no warning`);
    await page.waitForFunction(k => document.querySelectorAll('.dk-row').length === k, n);
  };
  await addJolly(1, '[سلام]{tl}', mp3('One.mp3', MEDIA.a), 'hello', mp3('Two.mp3', MEDIA.c));
  // a 4 s recording, its clip from 10 s: played, this one is sought forever (the 8 s tone just ends)
  await addJolly(2, '[کتاب]{tl}', mp3('Late.mp3', MEDIA.a), 'book', mp3('Book.mp3', MEDIA.b), '{start=10}');
  const items = (await (await t.request.get(url(`/exercises/api/decks/${deck.path}`))).json()).items;
  assert(items.length === 2 && items[1].markdown.includes('\n  [کتاب]{tl}\n  ![](audio/late.mp3){start=10}\n'),
         `the second card keeps its clip past the end (${JSON.stringify(items.map(i => i.markdown))})`);

  const ONE = '#study-stage .ex-card-front figure.audio audio[src$="/audio/one.mp3"]';
  const TWO = '#study-stage .ex-card-back figure.audio audio[src$="/audio/two.mp3"]';
  const LATE = '#study-stage .ex-card-front figure.audio audio[src*="/audio/late.mp3"]';
  const BOOK = '#study-stage .ex-card-back figure.audio audio[src$="/audio/book.mp3"]';
  const media = sel => page.evaluate(s => {
    const a = document.querySelector(s);
    return a ? {ready: a.readyState, time: a.currentTime, paused: a.paused, seeking: a.seeking, duration: a.duration} : null;
  }, sel);
  const sounds = async (sel, what) => {
    const ok = await page.waitForFunction(s => {
      const a = document.querySelector(s);
      return !!a && a.readyState >= 1 && !a.paused && a.currentTime > 0.05;
    }, sel, {timeout: 10000}).then(() => true, () => false);
    assert(ok, `${what} (${JSON.stringify(await media(sel))})`);
  };
  const edges = () => page.evaluate(() => window.__edges);

  // studied, opened with a click (which lets the page play sound): card 1 speaks by itself, and turned
  await Promise.all([page.waitForURL(url(`/exercises/deck/${deck.path}/study`)), page.click('#btn-study')]);
  await page.waitForSelector(ONE);
  await sounds(ONE, 'card 1 shown plays its front recording by itself: this page may make a sound');
  await page.click('#btn-show');
  await sounds(TWO, 'Show answer plays its back');

  // rated while its answer is held on the way, and enlarged meanwhile: its ⤢ still answers
  let reached, release;
  const arrived = new Promise(r => { reached = r; });
  const held = new Promise(r => { release = r; });
  const toReview = u => u.pathname.endsWith(`/${deck.path}/review`);
  const hold = async route => { reached(); await held; await route.continue(); };
  await page.route(toReview, hold);
  await page.keyboard.press('3');
  await arrived;
  await page.click('#study-stage .ex-card-zoom');
  await page.waitForSelector('.ex-zoom-overlay .ex-flashcard');
  const mark = (await edges()).length;
  release();
  await page.waitForSelector(LATE);
  await page.unroute(toReview, hold);
  const closed = await page.waitForSelector('.ex-zoom-overlay', {state: 'detached', timeout: 5000}).then(() => true, () => false);
  assert(closed, 'card 2 drawn, the window of card 1 opened while its answer was saved closes with it');

  // card 2: its length known, and a second more
  const known = await page.waitForFunction(s => {
    const a = document.querySelector(s);
    return !!a && a.readyState >= 1 && Number.isFinite(a.duration);
  }, LATE, {timeout: 10000}).then(() => true, () => false);
  await page.waitForTimeout(1000);
  const late = await media(LATE), since = (await edges()).slice(mark);
  const seeks = since.filter(h => h[0] === 'late.mp3' && h[1] === 'seeked').length;
  assert(known && late.duration < 10 && late.paused && !late.seeking && seeks <= 2
         && !since.some(h => h[0] === 'late.mp3' && h[1] === 'play'),
         `its clip from 10 s of a ${late.duration} s recording is left silent: not played, not seeking back to its start ` +
         `(${JSON.stringify(late)}, ${seeks} seeks in that second)`);
  assert(!since.some(h => h[1] === 'play'),
         `nothing else plays: not card 1's recordings in the window that was over it (${JSON.stringify(since.filter(h => h[1] === 'play'))})`);

  // the keys are the page's again: Enter shows the answer, and 4 rates it
  await page.keyboard.press('Enter');
  const shown = await page.waitForSelector('#rating-bar:not([hidden])', {timeout: 5000}).then(() => true, () => false);
  assert(shown && await page.locator('#study-stage .ex-flashcard.flipped').count() === 1, 'Enter shows card 2’s answer');
  await sounds(BOOK, 'and the recording on its back plays');
  await page.keyboard.press('4');
  const rated = await page.waitForSelector(LATE, {state: 'detached', timeout: 8000}).then(() => true, () => false);
  assert(rated, '4 rates it: card 2 goes');
  assert(!(await edges()).some(h => h[0].startsWith('zoom:') && h[1] === 'play'), 'no copy in a window played at any time');
}

/* A BOTH-REPEAT FLASHCARD IS TWO LINKED CARDS IN A DECK (TO-DO L17, the deck
   half): made by "+ Deck" (and the API's add), told apart in Browse by a
   badge, asked about whenever an edit or a delete would leave the other side
   as it was -- from Browse, from the study page and from a selection -- and
   buried until the next day when the other side is answered (Anki's way);
   cramming ignores the burying.  `t`: {page, browser, request, url, assert,
   toast(page, re, what), studio, tmp, mode}; SHOTS=<dir> saves the dialogs and the
   badge on the three themes, wide and narrow. */
async function linkedCardsFlow(t) {
  const {page, browser, url, assert} = t;
  const S = t.studio;
  const shots = Deno.env.get('SHOTS');
  const {fieldOf, clearToast} = formKit(page, assert);
  const card = (word, extra = '') => `:::exercise flashcard\ncard-type: vocab\ntarget: [${word}]{tl}\n`
    + `meaning: the ${word}\ndirection: both-repeat\n${extra}:::`;
  const post = (path, data) => t.request.post(url(path), {data});
  const mk = async name => (await (await post('/exercises/api/decks', {name, lang: 'fa'})).json()).deck;
  const itemsOf = async d => (await (await t.request.get(url(`/exercises/api/decks/${d.path}`))).json()).items;
  const addPair = async (d, md) => {
    const r = await post(`/exercises/api/decks/${d.path}/items`, {markdown: md});
    assert(r.status() === 201, `a both-repeat card added over the API: 201 (${r.status()})`);
    return r.json();
  };
  // what the edit form is told it may offer (opts.directions), kept from the moment a page is opened
  const spy = () => page.evaluate(() => {
    window.__forms = [];
    const open = window.openExerciseMarkdown;
    window.openExerciseMarkdown = (markdown, opts) => { window.__forms.push(opts.directions || null); return open(markdown, opts); };
  });
  const open = async d => {
    await page.goto(url(`/exercises/deck/${d.path}/`));
    await page.waitForSelector('.dk-row');
    await spy();
  };
  const rowOf = (id) => page.locator(`.dk-row[data-id="${id}"]`);
  const ask = () => page.locator('.dk-ask');
  const askButtons = () => page.locator('.dk-ask .row .btn').allTextContents();
  const nothingOpen = async what => assert(await page.locator('#modal-root > .modal-overlay').count() === 0, what);
  const shoot = async (name, frame, mobile = false) => {
    if (!shots) return;
    for (const [width, height, label] of mobile ? [[390, 800, 'phone']] : [[1280, 800, 'wide'], [390, 800, 'narrow']]) {
      for (const theme of ['light', 'sepia', 'dark']) {
        const ctx = await browser.newContext({viewport: {width, height}});
        try {
          await ctx.addInitScript(([th, m]) => {
            try { localStorage.setItem('parseh_theme', th); if (m) localStorage.setItem('parseh_mode', 'mobile'); } catch (_) {}
          }, [theme, mobile]);
          const p = await ctx.newPage();
          await frame(p);
          await p.screenshot({path: `${shots}/linked-${name}-${label}-${theme}-${t.mode}.png`});
        } finally { await ctx.close(); }
      }
    }
  };
  const deckPage = async (p, d) => {
    await p.goto(url(`/exercises/deck/${d.path}/`));
    await p.waitForSelector('.dk-row');
  };

  /* ---- made by "+ Deck" from a studio page: two cards, front first ---- */
  const deck = await mk('Linked pairs');
  const doc = await (await post(`${S}/api/docs`, {markdown: `---\ntitle: A pair\ntarget: fa\n---\n\n${card('گربه')}\n`})).json();
  await page.goto(url(`${S}/doc/${doc.meta.id}`));
  await page.waitForSelector('#sheet .exercise[data-subtype="flashcard"] .ex-to-deck');
  await page.locator('#sheet .exercise[data-subtype="flashcard"] .ex-to-deck').click();
  await page.waitForSelector(`.ex-to-deck-modal select option[value="${deck.path}"]`, {state: 'attached'});
  await page.locator('.ex-to-deck-modal select').selectOption(deck.path);
  await page.locator('.ex-to-deck-modal [data-x="copy"]').click();
  await t.toast(page, /Copied into “Linked pairs” as two linked cards/, '+ Deck on a both-repeat card says it made two');
  let items = await itemsOf(deck);
  assert(items.length === 2 && items[0].link && items[0].link === items[1].link
         && items[0].direction === 'forward' && items[1].direction === 'reverse'
         && items[0].mates[0] === items[1].id && items[1].mates[0] === items[0].id
         && items[0].created < items[1].created,      // microseconds: a Date cannot tell them apart
         'two items, front first and back first, sharing one link, the back made a moment after the front');
  assert(items[0].markdown.includes('\ndirection: forward\n') && items[1].markdown.includes('\ndirection: reverse\n')
         && !/both-repeat/.test(items[0].markdown + items[1].markdown),
         'each writes its direction out, and neither keeps "both-repeat"');
  assert(items[0].origin.doc_id === doc.meta.id && items[1].origin.ordinal === 1, 'both name the page they came from');
  const again = await post('/exercises/api/decks/' + deck.path + '/copy',
    {doc_id: doc.meta.id, ordinal: 1, subtype: 'flashcard'});
  assert(again.status() === 409 && (await again.json()).conflict === 'duplicate',
         'the same card again is refused as a duplicate: one of its sides is already in the deck');

  /* ---- Browse: the badge tells the two rows apart ---- */
  await open(deck);
  assert(await page.locator('.dk-row').count() === 2, 'Browse lists two rows');
  const badges = await page.locator('.dk-row .dk-linked').allTextContents();
  assert(JSON.stringify(badges) === JSON.stringify(['↔ linked · front first', '↔ linked · back first']),
         `each row wears its side (${JSON.stringify(badges)})`);
  await shoot('badge', async p => { await deckPage(p, deck); });
  await shoot('badge-mobile', async p => {
    await deckPage(p, deck);
    await p.evaluate(() => document.querySelector('.dk-row').scrollIntoView({block: 'start'}));
  }, true);

  /* ---- edit: the server asks, the page shows the question ---- */
  const [front, back] = items;
  await rowOf(front.id).locator('[data-x="edit"]').click();
  await page.waitForSelector('.ex-form-modal');
  const fixed = () => page.evaluate(() => [...document.querySelectorAll('.ex-form-modal select')]
    .filter(s => [...s.options].every(o => /^(forward|reverse|both-random|both-repeat)$/.test(o.value)))
    .map(s => ({disabled: s.disabled, note: s.closest('label').querySelector('.dk-fixed-side')?.textContent || ''})));
  let sides = await fixed();
  assert(sides.length === 1 && sides[0].disabled && sides[0].note === 'This card is one side of a pair: its side is fixed.',
         `a linked card's side select is fixed, and says why (${JSON.stringify(sides)})`);
  assert(JSON.stringify(await page.evaluate(() => window.__forms)) === '[["forward"]]',
         'the form is told the one side this card may show');
  await fieldOf('Meaning').locator('textarea').fill('the kitten');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await ask().waitFor();
  assert(await ask().locator('h3').textContent() === 'This card has another side'
         && JSON.stringify(await askButtons()) === JSON.stringify(['Cancel', 'Change only this one (unlink them)', 'Change both cards']),
         `the edit asks: change both, change only this one, or cancel (${JSON.stringify(await askButtons())})`);
  assert((await ask().locator('p').first().textContent()).includes('Is this change for both cards?')
         && (await ask().locator('li').allTextContents()).join('|').includes('گربه')
         && (await ask().locator('li').textContent()).includes('shows the back first'),
         'and names the other side: its text and which face it shows first');
  assert(await page.locator('.ex-form-modal').count() === 1, 'the form stays open under the question');
  await shoot('edit-ask', async p => {
    await deckPage(p, deck);
    await p.locator(`.dk-row[data-id="${front.id}"] [data-x="edit"]`).click();
    await p.waitForSelector('.ex-form-modal');
    await p.locator('.ex-form-modal .ex-author-field:has(> span:text-is("Meaning")) textarea').fill('the kitten');
    await p.click('.ex-form-modal [data-x="save"]');
    await p.waitForSelector('.dk-ask');
  });
  await ask().locator('[data-x="cancel"]').click();
  await page.waitForFunction(() => !document.querySelector('.dk-ask'));
  await t.toast(page, /^Not saved: the card is left as it was$/, 'Cancel leaves the card as it was, and says so');
  assert(await page.locator('.ex-form-modal').count() === 1, 'the form is still open after Cancel');
  items = await itemsOf(deck);
  assert(items[0].markdown.includes('meaning: the گربه') && items[1].markdown.includes('meaning: the گربه'),
         'nothing was written to either card');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await ask().waitFor();
  await ask().locator('button', {hasText: 'Change both cards'}).click();
  await t.toast(page, /^Exercise saved$/, 'Change both cards saves');
  await page.waitForFunction(() => !document.querySelector('.ex-form-modal') && !document.querySelector('.dk-ask'));
  items = await itemsOf(deck);
  assert(items.every(i => i.markdown.includes('meaning: the kitten')) && items[0].direction === 'forward'
         && items[1].direction === 'reverse' && items[0].link === items[1].link && items[0].mates.length === 1,
         'both cards took the change, each kept its own side, and they are still linked');
  assert(items.every(i => i.schedule.state === 'new' && i.reps === 0), 'and no schedule was touched');

  // a save that changes nothing asks nothing
  await open(deck);
  await rowOf(items[0].id).locator('[data-x="edit"]').click();
  await page.waitForSelector('.ex-form-modal');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await t.toast(page, /^Exercise saved$/, 'saving a linked card with no change asks nothing');
  await nothingOpen('and closes the form');

  // Change only this one: unlinked, the change is this card's alone
  await rowOf(items[1].id).locator('[data-x="edit"]').click();
  await page.waitForSelector('.ex-form-modal');
  assert(JSON.stringify(await page.evaluate(() => window.__forms.slice(-1))) === '[["reverse"]]',
         'the back-first card may show the back first only');
  await fieldOf('Meaning').locator('textarea').fill('the lion');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await ask().waitFor();
  await ask().locator('button', {hasText: 'Change only this one (unlink them)'}).click();
  await t.toast(page, /^Exercise saved$/, 'Change only this one saves');
  await page.waitForFunction(() => !document.querySelector('.ex-form-modal'));
  items = await itemsOf(deck);
  assert(items[0].markdown.includes('the kitten') && items[1].markdown.includes('the lion')
         && !items[0].link && !items[1].link && !items[0].mates.length && !items[1].mates.length,
         'only that card changed, and the two are linked no more');
  await open(deck);
  assert(await page.locator('.dk-linked').count() === 0, 'Browse shows no badge on either');
  await rowOf(items[0].id).locator('[data-x="edit"]').click();
  await page.waitForSelector('.ex-form-modal');
  assert(JSON.stringify(await page.evaluate(() => window.__forms.slice(-1)))
         === JSON.stringify([['forward', 'reverse', 'both-random']])
         && JSON.stringify(await fixed()) === JSON.stringify([{disabled: false, note: ''}]),
         'an unlinked card may show front, back or either at random -- but Both (repeat) is how a card is ADDED');
  await page.click('.ex-form-modal [data-x="cancel"]');

  /* ---- delete, one card ---- */
  const two = await addPair(deck, card('سگ'));
  await open(deck);
  const [dogFront, dogBack] = two.items.map(i => i.id);
  await rowOf(dogFront).locator('[data-x="delete"]').click();
  await ask().waitFor();
  assert(JSON.stringify(await askButtons()) === JSON.stringify(['Cancel', 'Delete only this (the other stays, unlinked)', 'Delete both'])
         && (await ask().locator('p').first().textContent()).includes('Delete the other side too?'),
         `deleting a linked card asks: both, only this one, or cancel (${JSON.stringify(await askButtons())})`);
  await shoot('delete-ask', async p => {
    await deckPage(p, deck);
    await p.locator(`.dk-row[data-id="${dogFront}"] [data-x="delete"]`).click();
    await p.waitForSelector('.dk-ask');
  });
  await ask().locator('[data-x="cancel"]').click();
  await nothingOpen('Cancel closes the question');
  assert((await itemsOf(deck)).length === 4, 'and nothing was deleted');
  await rowOf(dogFront).locator('[data-x="delete"]').click();
  await ask().locator('button', {hasText: 'Delete only this'}).click();
  await t.toast(page, /^Exercise deleted$/, 'Delete only this');
  await page.waitForFunction(id => !document.querySelector(`.dk-row[data-id="${id}"]`), dogFront);
  items = await itemsOf(deck);
  assert(items.length === 3 && items.find(i => i.id === dogBack) && !items.find(i => i.id === dogBack).link
         && !items.find(i => i.id === dogBack).mates.length,
         'the other side stays, and is linked with nothing');
  assert(await page.locator(`.dk-row[data-id="${dogBack}"] .dk-linked`).count() === 0, 'its badge is gone');

  const third = await addPair(deck, card('کتاب'));
  await open(deck);
  await rowOf(third.items[1].id).locator('[data-x="delete"]').click();
  await ask().locator('button', {hasText: 'Delete both'}).click();
  await t.toast(page, /^Both cards deleted$/, 'Delete both');
  await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 3);
  assert((await itemsOf(deck)).length === 3, 'both sides of the third pair are gone');
  const raw = await t.request.delete(url(`/exercises/api/decks/${deck.path}/items/${items[0].id}`));
  assert(raw.status() === 200, 'an unlinked card is deleted as it always was');
  const lone = await addPair(deck, card('مداد'));
  const refused = await t.request.delete(url(`/exercises/api/decks/${deck.path}/items/${lone.item.id}`));
  const answer = await refused.json();
  assert(refused.status() === 409 && answer.conflict === 'linked' && answer.detail.mates.length === 1
         && answer.detail.mates[0].side === 'back' && (await itemsOf(deck)).length === 4,
         'the server refuses a delete that does not say what becomes of the other side: 409 "linked", naming it');

  /* ---- delete, a selection ---- */
  const pairs = [lone, await addPair(deck, card('میز')), await addPair(deck, card('خانه'))];
  await open(deck);
  const picked = () => page.locator('.dk-row .dk-select:checked').count();
  for (const p of pairs) await rowOf(p.item.id).locator('.dk-select').check();
  await page.click('#btn-bulk-delete');
  await ask().waitFor();
  assert(JSON.stringify(await askButtons()) === JSON.stringify(['Cancel', 'Delete only the selected', 'Delete their other sides too']),
         `three front sides picked, none of their backs: ONE question (${JSON.stringify(await askButtons())})`);
  assert((await ask().locator('p').first().textContent()).startsWith('3 picked exercises are one side of a pair')
         && await ask().locator('li').count() === 3, 'it counts them, and lists the other sides');
  await shoot('bulk-ask', async p => {
    await deckPage(p, deck);
    for (const q of pairs) await p.locator(`.dk-row[data-id="${q.item.id}"] .dk-select`).check();
    await p.click('#btn-bulk-delete');
    await p.waitForSelector('.dk-ask');
  });
  await ask().locator('button', {hasText: 'Delete only the selected'}).click();
  await t.toast(page, /^3 exercises deleted$/, 'Delete only the selected');
  await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 5);
  items = await itemsOf(deck);
  assert(items.filter(i => pairs.some(p => p.items[1].id === i.id)).length === 3
         && items.every(i => !i.link && !i.mates.length), 'the three backs stay, each linked with nothing');
  await open(deck);
  // both sides picked: nothing to ask
  const whole = await addPair(deck, card('پنجره'));
  await open(deck);
  for (const i of whole.items) await rowOf(i.id).locator('.dk-select').check();
  await page.click('#btn-bulk-delete');
  await page.waitForSelector('.dk-modal');
  assert(await ask().count() === 0 && (await page.locator('.dk-modal h3').textContent()) === 'Delete 2 exercises?',
         'both sides of a pair picked: the plain question, nothing about links');
  await page.locator('.dk-modal button', {hasText: 'Delete selected'}).click();
  await t.toast(page, /^2 exercises deleted$/, 'both sides deleted');
  const last = await addPair(deck, card('درخت'));
  await open(deck);
  await rowOf(last.items[0].id).locator('.dk-select').check();
  await page.click('#btn-bulk-delete');
  await ask().waitFor();
  await ask().locator('button', {hasText: 'Delete their other sides too'}).click();
  await t.toast(page, /^2 exercises deleted$/, 'the other sides go with them: the count says both');
  items = await itemsOf(deck);
  assert(!items.some(i => last.items.some(x => x.id === i.id)), 'neither side of that pair is left');

  /* ---- studying: the other side is buried until the next day ---- */
  const study = await mk('Pair study');
  const studied = (await addPair(study, card('ماهی'))).items;
  await page.goto(url(`/exercises/deck/${study.path}/study`));
  await page.waitForSelector('#study-stage .ex-flashcard');
  // editing from the study page asks the same question, over the form
  await page.click('#btn-edit-card');
  await page.waitForSelector('.ex-form-modal');
  await fieldOf('Meaning').locator('textarea').fill('the fish');
  await page.click('.ex-form-modal [data-x="save"]');
  await ask().waitFor();
  await shoot('study-edit-ask', async p => {
    await p.goto(url(`/exercises/deck/${study.path}/study`));
    await p.waitForSelector('#study-stage .ex-flashcard');
    await p.click('#btn-edit-card');
    await p.waitForSelector('.ex-form-modal');
    await p.locator('.ex-form-modal .ex-author-field:has(> span:text-is("Meaning")) textarea').fill('the fish');
    await p.click('.ex-form-modal [data-x="save"]');
    await p.waitForSelector('.dk-ask');
  });
  await ask().locator('button', {hasText: 'Change both cards'}).click();
  await t.toast(page, /^Exercise saved: its scheduling is unchanged$/, 'the study page asks the same, and saves');
  await page.waitForFunction(() => document.querySelector('#study-stage')?.textContent.includes('fish'));
  assert((await itemsOf(study)).every(i => i.markdown.includes('meaning: the fish')), 'both sides were changed from the study page');

  const shown = () => page.evaluate(() => document.querySelector('#study-stage .ex-flashcard')?.className || '');
  await page.click('#btn-show');
  await page.waitForSelector('#rating-bar:not([hidden])');
  await page.click('[data-rating="easy"]');
  await page.waitForSelector('#study-done:not([hidden])');
  assert(await page.locator('#study-done .dk-held').textContent()
         === '1 card held back until tomorrow: the other side of a card answered today.',
         'the front answered: the back is not offered in this session, and the page says it is held back');
  let next = await (await t.request.get(url(`/exercises/api/decks/${study.path}/next`))).json();
  assert(next.done === true && next.item === null && next.buried === 1, 'the queue agrees: nothing, one buried');
  const listed = (await (await t.request.get(url('/exercises/api/decks?lang=fa'))).json()).decks.find(d => d.path === study.path);
  assert(listed.study.new === 0 && listed.counts.new === 1, 'the deck counts it as new, and as nothing to study today');
  await shoot('study-held', async p => {
    await p.goto(url(`/exercises/deck/${study.path}/study`));
    await p.waitForSelector('#study-done:not([hidden])');
  });
  const cram = await (await post(`/exercises/api/decks/${study.path}/cram`, {ids: studied.map(i => i.id)})).json();
  assert(cram.cards.length === 2, 'cramming both sides offers both: it never schedules, so it never buries');

  // the day passes: every stored time moves a day back
  const shift = await new Deno.Command(python, {args: ['-c', `
import json, sys
from datetime import datetime, timedelta
for path in sys.argv[2:]:
    doc = json.load(open(path))
    def back(x): return (datetime.fromisoformat(x) - timedelta(days=int(sys.argv[1]))).isoformat() if x else x
    doc['state']['due'] = back(doc['state']['due']); doc['state']['last_review'] = back(doc['state']['last_review'])
    for h in doc['history']: h['at'] = back(h['at']); h['due'] = back(h['due'])
    json.dump(doc, open(path, 'w'))`, '1', `${t.tmp}/exercises/${study.path}/schedule/${studied[0].id}.json`],
    stdout: 'piped', stderr: 'piped'}).output();
  assert(shift.success, 'a day passes over the answered card (its stored times move back a day)');
  next = await (await t.request.get(url(`/exercises/api/decks/${study.path}/next`))).json();
  assert(next.done === false && next.item.id === studied[1].id && next.buried === 0,
         'the next day the back is offered, and it is the card that shows the back first');
  await page.reload();
  await page.waitForSelector('#study-stage .ex-flashcard');
  assert(await page.locator('#study-stage .ex-card-front').textContent().then(x => x.includes('the fish')),
         'the study page shows it, back first');
  await page.click('#btn-show');
  await page.waitForSelector('#rating-bar:not([hidden])');
  await page.click('[data-rating="easy"]');
  await page.waitForSelector('#study-done:not([hidden])');
  assert(await page.locator('#study-done .dk-held').isHidden() || (await page.locator('#study-done .dk-held').textContent()) === '',
         'and answered, nothing is held back: the front is not due for days');

  /* ---- the deck's own Add form: Both (repeat) is chosen where the side is ---- */
  const added = await mk('Added by the form');
  await page.goto(url(`/exercises/deck/${added.path}/`));
  await page.waitForSelector('#browse-empty:not([hidden])');
  await page.click('#btn-add-exercise');
  await page.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
  await page.waitForSelector('.ex-form-modal');
  await fieldOf('Word or expression').locator('textarea').fill('[کتاب]{tl}');
  await fieldOf('Meaning').locator('textarea').fill('book');
  const side = fieldOf('Which side appears first').locator('select');
  const offered = await side.locator('option').evaluateAll(os => os.map(o => o.value));
  // the form's own select, however many values it offers; one that does not yet offer both-repeat is given it
  if (!offered.includes('both-repeat'))
    await side.evaluate(s => { const o = document.createElement('option'); o.value = 'both-repeat'; o.textContent = 'Both (repeat)'; s.appendChild(o); });
  await side.selectOption('both-repeat');
  await clearToast();
  await page.click('.ex-form-modal [data-x="save"]');
  await t.toast(page, /^Added two linked cards to “Added by the form”$/, 'the Add form with Both (repeat) says it added two linked cards');
  await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 2);
  const formed = await itemsOf(added);
  assert(formed.length === 2 && formed[0].direction === 'forward' && formed[1].direction === 'reverse'
         && formed[0].link === formed[1].link && formed[0].markdown.includes('meaning: book'),
         'two cards in the deck, front first and back first, linked, as the form wrote them');
  assert(JSON.stringify(await page.locator('.dk-row .dk-linked').allTextContents())
         === JSON.stringify(['↔ linked · front first', '↔ linked · back first']), 'and Browse marks them');
}

async function suite(browser, mode) {
  const {proc, info} = await startHarness(mode);
  const S = info.studio;                 // "" or "/studio"
  const url = p => `http://127.0.0.1:${info.port}${p}`;
  const errors = [];
  let passed = 0;
  const assert = (v, m) => { if (!v) throw new Error(`FAIL (${mode}): ` + m); passed++; console.log('  ok', m); };
  const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
    m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
  function watch(page, name) {
    page.on('pageerror', e => errors.push(`${name}: ${e.message}`));
    page.on('console', m => {
      // a 404/409 answer is logged by Chrome as "Failed to load resource" for
      // most tags, but as "A bad HTTP response code (…) was received when
      // fetching the script" for a <script> Chrome noticed under mobile mode's
      // extra bookkeeping (studio mode alone never serves /lib/*, on any
      // layout: expected here, on both counts, same as decks_harness.py's docstring says)
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text())
          && !/bad HTTP response code.*fetching the script/.test(m.text())) errors.push(`${name} console: ${m.text()}`);
    });
  }
  const toastText = page => page.locator('#toast').textContent();
  async function waitToast(page, re, what) {
    await page.waitForFunction(r => new RegExp(r).test(document.querySelector('#toast').textContent), re.source, {timeout: 8000})
      .catch(async () => { throw Error(`FAIL (${mode}): toast ${what}: got “${await toastText(page)}”`); });
    passed++; console.log('  ok toast', what);
  }
  const overlays = page => page.locator('#modal-root > .modal-overlay').count();
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    watch(page, 'decks');

    /* ---------------- the decks ---------------- */
    console.log(`decks page (${mode}: studio at "${S || '/'}")`);
    await page.goto(url('/exercises/'));
    await page.waitForSelector('.dk-card');
    assert(await page.evaluate(() => document.body.dataset.studio) === S, `data-studio is the studio's mount (“${S}”)`);
    assert(await page.evaluate(s => [...document.styleSheets].some(x => x.href && new URL(x.href).pathname === s + '/static/app.css'
                                                                     && x.cssRules.length > 100), S),
           "the studio's stylesheet loads from its mount");
    assert(await page.evaluate(() => typeof openExercisePicker === 'function' && typeof bindExercises === 'function'),
           "the studio's app.js loads before decks.js");
    assert(await page.locator('.dk-card').count() === 4, 'one card per deck (4)');
    const faCard = page.locator('.dk-card', {has: page.locator('.dk-card-title', {hasText: 'Persian practice'})});
    assert((await faCard.locator('.badge.lang').textContent()) === 'فارسی', 'language badge in its native name');
    assert((await faCard.locator('.dk-total').textContent()) === '5 exercises', '“5 exercises”');
    assert(await faCard.locator('.dk-n.dk-new').textContent() === '4', 'new count (blue)');
    assert(await faCard.locator('.dk-n.dk-learn').textContent() === '1', 'learning count (red)');
    assert(!(await faCard.locator('[data-x="study"]').getAttribute('class')).includes('dk-off'), 'Study enabled when something is due');
    assert((await faCard.locator('[data-x="browse"]').getAttribute('href')) === '/exercises/deck/persian/persian-practice/', 'Browse links the deck page');
    const newColor = await faCard.locator('.dk-n.dk-new').evaluate(e => getComputedStyle(e).color);
    const revColor = await faCard.locator('.dk-n.dk-rev').evaluate(e => getComputedStyle(e).color);
    assert(newColor !== revColor, `queue colours differ (${newColor} / ${revColor})`);
    const empty = page.locator('.dk-card', {has: page.locator('.dk-card-title', {hasText: 'Empty deck'})});
    const emptyStudy = empty.locator('[data-x="study"]');
    assert((await emptyStudy.getAttribute('class')).includes('dk-off') && (await emptyStudy.getAttribute('aria-disabled')) === 'true',
      'Study disabled on an empty deck');
    assert((await empty.locator('.dk-card-study').textContent()).startsWith('Empty'), 'empty deck says so');
    assert(await page.locator('#decks-empty').isHidden() && await page.locator('#decks-empty-lang').isHidden(), 'no empty states with decks');

    // chips: all 4, persian 3, arabic 1
    assert(await page.locator('.parseh-langs .chip').count() === 3, 'chips: all + the two languages with decks');
    await page.click('.parseh-langs .chip[data-pick="ar"]');
    assert(await page.locator('.dk-card:visible').count() === 1, 'the Arabic chip hides the other cards');
    assert(await page.evaluate(() => localStorage.getItem('parseh_lang')) === 'ar', 'the pick is the shared preference');
    assert(await page.locator('.parseh-langs .chip.on').getAttribute('data-pick') === 'ar', 'the picked chip is lit');
    await page.evaluate(() => localStorage.setItem('parseh_lang', 'ja'));
    await page.reload();
    await page.waitForSelector('.dk-card');
    assert(await page.locator('.dk-card:visible').count() === 4, 'a preference no chip offers reads as all');
    assert(await page.evaluate(() => localStorage.getItem('parseh_lang')) === 'all', '…and is put right');

    // the ⋯ menu
    const arCard = page.locator('.dk-card[data-lang="ar"]');
    await arCard.locator('summary').click();
    const exports = await arCard.locator('.menu a').evaluateAll(as => as.map(a => a.getAttribute('href')));
    assert(exports[0].endsWith('/export?scheduling=1') && exports[1].endsWith('/export?scheduling=0'), 'export links, with and without scheduling');
    await page.click('main', {position: {x: 5, y: 5}});
    assert(!(await arCard.locator('details').evaluate(d => d.open)), 'a click elsewhere closes the menu');

    // delete (Escape first)
    await empty.locator('summary').click();
    await empty.locator('[data-x="delete"]').click();
    await page.waitForSelector('.dk-modal');
    assert((await page.locator('.dk-modal h3').textContent()) === 'Delete “Empty deck”?', 'delete asks first');
    assert((await page.locator('.dk-modal p').textContent()).includes('exercises/.trash/'), 'and says it goes to exercises/.trash');
    await page.keyboard.press('Escape');
    assert(await overlays(page) === 0, 'Escape closes the dialog');
    assert(await page.locator('.dk-card').count() === 4, 'nothing deleted on Escape');
    await empty.locator('summary').click();
    await empty.locator('[data-x="delete"]').click();
    await page.locator('.dk-modal button', {hasText: 'Delete deck'}).click();
    await waitToast(page, /moved to exercises\/\.trash/, 'deck moved to trash');
    await page.waitForFunction(() => document.querySelectorAll('.dk-card').length === 3);
    assert(true, 'the card is gone');

    // import: the Arabic deck's own export is a conflict -> a copy
    const zip = await (await ctx.request.get(url(exports[0]))).body();
    assert(zip.length > 100 && zip[0] === 0x50 && zip[1] === 0x4b, 'the export is a zip');
    await page.setInputFiles('#file-import', {name: 'arabic.zip', mimeType: 'application/zip', buffer: zip});
    await page.waitForSelector('.dk-modal input[type=checkbox]');
    assert(await page.locator('.dk-modal input[type=checkbox]').isChecked(), '“Keep the scheduling” ticked by default');
    const importReq = page.waitForRequest(r => r.url().includes('/api/import'));
    await page.locator('.dk-modal button', {hasText: /^Import$/}).click();
    // what the import is asked for is in its query; the query also carries the
    // file's name and, under the hub, the activity list's token (lib/activity.js)
    const asked = new URL((await importReq).url());
    assert(asked.pathname.endsWith('/api/import') && asked.searchParams.get('scheduling') === '1'
           && asked.searchParams.get('mode') === 'new' && asked.searchParams.get('name') === 'arabic.zip',
           'posted raw with scheduling=1&mode=new');
    await page.waitForSelector('.dk-modal h3:text("This deck is already here")');
    assert((await page.locator('.dk-modal p').textContent()).includes('Arabic basics'), 'the conflict names the deck already here');
    const copyReq = page.waitForRequest(r => r.url().includes('mode=copy'));
    await page.locator('.dk-modal button', {hasText: 'Import as a copy'}).click();
    await copyReq;
    await waitToast(page, /Imported “Arabic basics \(copy\)”: 2 exercises, with its scheduling/, 'import outcome');
    await page.waitForFunction(() => document.querySelectorAll('.dk-card').length === 4);
    assert(true, 'the imported copy has its card');

    // new deck: refused without a name, then made and opened
    await page.click('#btn-new-deck');
    await page.waitForSelector('.dk-modal select');
    await page.locator('.dk-modal button', {hasText: 'Create deck'}).click();
    await waitToast(page, /Give the deck a name/, 'nameless deck refused');
    assert(await overlays(page) === 1, 'the dialog stays open');
    await page.fill('.dk-modal input[type=text]', 'Nuovo mazzo');
    await page.selectOption('.dk-modal select', 'ar');
    await Promise.all([page.waitForURL(url('/exercises/deck/arabic/nuovo-mazzo/')), page.keyboard.press('Enter')]);
    assert(true, 'Enter creates the deck and opens its page');

    /* ---------------- a deck ---------------- */
    console.log('deck page (empty)');
    await page.waitForSelector('#browse-empty:not([hidden])');
    assert(await page.locator('#browse-empty [data-x="empty-deck"]').isVisible(), 'an empty deck explains how to fill it');
    assert((await page.locator('#btn-study').getAttribute('class')).includes('dk-off'), 'Study now disabled on an empty deck');
    await page.click('#btn-delete-deck');
    await Promise.all([page.waitForURL(url('/exercises/')), page.locator('.dk-modal button', {hasText: 'Delete deck'}).click()]);
    assert(true, 'Delete deck goes back to the decks');

    const deck = await ctx.newPage();
    watch(deck, 'deck');
    console.log('deck page (browse + manage)');
    await deck.goto(url('/exercises/deck/persian/persian-practice/'));
    await deck.waitForSelector('.dk-row');
    assert(await deck.locator('.dk-row').count() === 5, '5 rows');
    assert(await deck.locator('#browse-count').textContent() === '5 exercises', 'count without filters');
    assert((await deck.locator('#btn-study').getAttribute('href')) === '/exercises/deck/persian/persian-practice/study', 'Study now links the study page');
    assert((await deck.locator('#deck-counts').textContent()).includes('5 exercises · 4 new · 1 learning · 0 in review'), 'deck counts');
    const badRow = deck.locator('.dk-row', {has: deck.locator('.badge.err')});
    assert(await badRow.count() === 1, 'the broken exercise is marked “needs attention”');
    const docRow = deck.locator('.dk-row', {has: deck.locator('.dk-origin a')});
    assert((await docRow.locator('.dk-origin a').getAttribute('href')) === `${S}/doc/${info.doc_id}`, 'origin links the studio document, under its mount');
    assert((await docRow.locator('.dk-origin').textContent()) === 'from Greetings doc', 'origin names it');
    const learnRow = deck.locator('.dk-row', {has: deck.locator('.dk-state-learning')});
    assert((await learnRow.locator('.dk-when').textContent()) === 'due now', 'a learning exercise past due: “due now”');
    assert((await learnRow.locator('.dk-reps').textContent()) === '1 review · 0 lapses', 'reps · lapses');

    await deck.fill('#browse-filter', 'HELLO');
    await deck.waitForFunction(() => document.querySelector('#browse-count').textContent === '2 of 5');
    assert(true, 'the text filter folds case and reads the markdown too (2 of 5)');
    await deck.fill('#browse-filter', '');
    await deck.waitForFunction(() => document.querySelectorAll('.dk-row').length === 5);
    const types = await deck.locator('#browse-type option').allTextContents();
    assert(types.length === 6 && types.includes('Match translations (1)'), 'type select: the types present, counted');
    await deck.selectOption('#browse-type', 'match-translations');
    assert(await deck.locator('.dk-row').count() === 1, 'type filter');
    await deck.selectOption('#browse-type', '');
    await deck.selectOption('#browse-state', 'due');
    assert(await deck.locator('.dk-row').count() === 1 && await deck.locator('#browse-count').textContent() === '1 of 5', 'due-now filter');
    await deck.selectOption('#browse-state', 'review');
    assert(await deck.locator('#browse-empty [data-x="empty-filter"]').isVisible()
           && await deck.locator('#browse-empty [data-x="empty-deck"]').isHidden(), 'a filter that matches nothing says so');
    await deck.selectOption('#browse-state', '');

    // the solved preview
    const scRow = deck.locator('.dk-row', {has: deck.locator('.ex-kicker', {hasText: /^Choose one answer$/})});
    await scRow.locator('.dk-excerpt').click();
    await scRow.locator('.dk-row-preview .sheet.dk-sheet .exercise').waitFor();
    assert(await scRow.locator('.ex-option.selected').count() === 1, 'the preview is solved');
    assert(await scRow.locator('.ex-edit').count() === 0, 'no ✎ Edit inside the preview');
    assert(await scRow.locator('.dk-row-toggle').getAttribute('aria-expanded') === 'true', 'aria-expanded follows');
    const sheetShadow = await scRow.locator('.sheet.dk-sheet').evaluate(e => getComputedStyle(e).boxShadow);
    assert(sheetShadow === 'none', '.sheet.dk-sheet has no page shadow');
    await scRow.locator('.dk-row-meta').click();
    assert(await scRow.locator('.dk-row-preview').isHidden(), 'clicking the row again closes it');

    // edit in the form
    await scRow.locator('[data-x="edit"]').click();
    await deck.waitForSelector('.ex-form-modal');
    assert((await deck.locator('.ex-form-modal h3').textContent()).startsWith('Edit'), 'Edit opens the form in edit mode');
    await deck.waitForFunction(() => /Correct answer shown/.test(document.querySelector('.ex-form-preview-status').textContent));
    assert(await deck.locator('.ex-form-preview .exercise').count() === 1, 'the form preview is rendered by the deck');
    await deck.locator('.ex-form-body textarea').first().fill('Pick the greeting');
    const putReq = deck.waitForRequest(r => r.method() === 'PUT');
    await deck.click('.ex-form-modal [data-x="save"]');
    assert(JSON.parse((await putReq).postData()).markdown.includes('prompt: Pick the greeting'), 'PUT the edited markdown');
    await waitToast(deck, /Exercise saved/, 'saved');
    await deck.waitForFunction(() => [...document.querySelectorAll('.dk-excerpt')].some(e => e.textContent === 'Pick the greeting'));
    assert(await overlays(deck) === 0, 'the form closed; the row shows the new prompt');

    // edit a shape the form cannot show: the markdown dialog
    await badRow.locator('[data-x="edit"]').click();
    await deck.waitForSelector('.dk-raw-modal textarea');
    assert((await deck.locator('.dk-raw-modal textarea').inputValue()).includes('mystery-type'), 'the raw markdown dialog opens');
    await deck.fill('.dk-raw-modal textarea', ':::exercise yes-no\nprompt: Fixed?\n- Is it fixed => yes\n:::');
    await deck.locator('.dk-raw-modal button', {hasText: 'Save exercise'}).click();
    await waitToast(deck, /Exercise saved/, 'raw save');
    await deck.waitForFunction(() => !document.querySelector('.dk-row .badge.err'));
    assert(true, 'the exercise no longer needs attention');

    // duplicate, delete
    const mtRow = deck.locator('.dk-row', {has: deck.locator('.ex-kicker', {hasText: 'Match translations'})});
    await mtRow.locator('[data-x="duplicate"]').click();
    await waitToast(deck, /Duplicated/, 'duplicate');
    await deck.waitForFunction(() => document.querySelectorAll('.dk-row').length === 6);
    const last = deck.locator('.dk-row').last();
    assert((await last.locator('.dk-origin').textContent()) === 'a duplicate' && (await last.locator('.dk-state').textContent()) === 'new',
      'the copy starts new and says it is a duplicate');
    await last.locator('[data-x="delete"]').click();
    await deck.locator('.dk-modal button', {hasText: 'Delete exercise'}).click();
    await waitToast(deck, /Exercise deleted/, 'delete');
    await deck.waitForFunction(() => document.querySelectorAll('.dk-row').length === 5);

    // add through the picker; then the same again: a duplicate, refused then forced
    const addOnce = async () => {
      await deck.click('#btn-add-exercise');
      await deck.locator('.ex-type', {hasText: 'Yes / No questions'}).click();
      await deck.waitForSelector('.ex-form-modal');
      assert((await deck.locator('.ex-form-modal [data-x="save"]').textContent()) === 'Add to deck', 'save says “Add to deck”');
      await deck.locator('.ex-form-row textarea').first().fill('Is this new?');
    };
    await addOnce();
    await deck.click('.ex-form-modal [data-x="save"]');
    await waitToast(deck, /Added to “Persian practice”/, 'added');
    await deck.waitForFunction(() => document.querySelectorAll('.dk-row').length === 6);
    await addOnce();
    await deck.click('.ex-form-modal [data-x="save"]');
    await deck.waitForSelector('.dk-modal h3:text("Already in this deck")');
    assert(await overlays(deck) === 2, 'the duplicate question opens over the form');
    await deck.keyboard.press('Escape');
    await waitToast(deck, /Not added/, 'declined duplicate');
    assert(await overlays(deck) === 1 && await deck.locator('.ex-form-modal').isVisible(), 'the form stays open');
    await deck.click('.ex-form-modal [data-x="save"]');
    const forced = deck.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/items') && (r.postData() || '').includes('"force":true'));
    await deck.locator('.dk-modal button', {hasText: 'Add again'}).click();
    await forced;
    await deck.waitForFunction(() => document.querySelectorAll('.dk-row').length === 7);
    assert(await overlays(deck) === 0, 'forced: added a second time, form closed');

    // options
    await deck.click('#btn-options');
    await deck.waitForSelector('.dk-options');
    const optInputs = deck.locator('.dk-options input');
    assert(await optInputs.nth(0).inputValue() === '20' && await optInputs.nth(2).inputValue() === '1 10', 'options show the settings (steps as minutes)');
    await optInputs.nth(0).fill('abc');
    await deck.locator('.dk-modal button', {hasText: 'Save options'}).click();
    await waitToast(deck, /a whole number/, 'bad number refused');
    await optInputs.nth(0).fill('7');
    await optInputs.nth(2).fill('2 20');
    await deck.locator('.dk-modal button', {hasText: 'Save options'}).click();
    await waitToast(deck, /Options saved/, 'options saved');
    const got = await (await ctx.request.get(url('/exercises/api/decks/persian/persian-practice'))).json();
    assert(got.deck.settings.new_per_day === 7 && JSON.stringify(got.deck.settings.learning_steps) === '[2,20]', 'PATCHed settings stored');

    // rename (Enter)
    await deck.click('#btn-rename');
    await deck.fill('.dk-modal input', 'Persian drills');
    await deck.keyboard.press('Enter');
    await deck.waitForFunction(() => document.querySelector('#deck-name').textContent === 'Persian drills');
    assert((await deck.title()).startsWith('Persian drills'), 'renamed: heading and title');
    assert((await deck.locator('#btn-export-plain').getAttribute('href')).endsWith('/api/decks/persian/persian-practice/export?scheduling=0'), 'export link');

    // an exercise copied from notes beside a book links the notes, under their mount
    const arDeck = await ctx.newPage();
    watch(arDeck, 'arabic deck');
    await arDeck.goto(url('/exercises/deck/arabic/arabic-basics/'));
    await arDeck.waitForSelector('.dk-row .dk-origin a');
    const notesLink = arDeck.locator('.dk-row .dk-origin a');
    const notesHref = await notesLink.getAttribute('href');
    assert(await notesLink.count() === 1 && notesHref === `${info.notes_source}/doc/${info.notes_doc_id}`,
           `a copy from notes links them under their mount (${notesHref})`);
    assert(await arDeck.locator('.dk-row .dk-origin', {has: arDeck.locator('a')}).textContent() === 'from Arabic grammar notes',
           'and names them');
    await arDeck.close();

    /* ---------------- study ---------------- */
    const study = await ctx.newPage();
    watch(study, 'study');
    const reviews = [], itemGets = [];
    study.on('request', r => { if (r.url().endsWith('/review')) reviews.push(JSON.parse(r.postData())); });
    study.on('request', r => { if (r.method() === 'GET' && /\/items\/[0-9a-f]{12}$/.test(r.url())) itemGets.push(r.url()); });
    console.log('study page');
    await study.goto(url('/exercises/deck/persian/persian-study/study'));
    await study.waitForSelector('#study-stage .exercise');
    assert((await study.title()) === 'Study: Persian study — Parseh exercises', 'page title');
    assert(await study.locator('#study-counts .dk-new').textContent() === '4', 'counts: 4 new');
    assert(await study.locator('#study-counts .dk-current').count() === 1
           && (await study.locator('#study-counts .dk-current').getAttribute('class')).includes('dk-new'), 'the current queue is underlined');
    assert(await study.locator('#btn-check').isVisible() && await study.locator('#btn-show').isHidden(), 'a scored exercise: Check');
    assert(await study.locator('#rating-bar').isHidden(), 'no rating bar before checking');
    assert(await study.locator('#study-stage .exercise-correction').count() === 0, 'the page-wide correction is gone');
    await study.keyboard.press('3');
    assert(reviews.length === 0 && await study.locator('#rating-bar').isHidden(), 'keys do not rate before checking');
    // Enter on an answer reached from the keyboard chooses it, and does not check
    assert(await study.evaluate(() => document.activeElement.id) === 'btn-check', 'Check has the focus');
    const onRight = () => study.evaluate(() => document.activeElement.matches('#study-stage .ex-option[data-correct="1"]'));
    for (let i = 0; i < 6 && !(await onRight()); i++) await study.keyboard.press('Shift+Tab');
    assert(await onRight(), 'Shift+Tab from Check reaches the right answer');
    await study.keyboard.press('Enter');
    assert(await study.locator('.ex-option[data-correct="1"]').evaluate(o => o.classList.contains('selected'))
           && await study.locator('#rating-bar').isHidden() && await study.locator('#study-result').isHidden()
           && !(await study.locator('#study-stage .ex-body').evaluate(b => b.inert)),
           'Tab then Enter chooses the answer: nothing is checked');
    // a click on an answer, then Enter: that checks
    await study.locator('.ex-option[data-correct="0"]').click();
    await study.keyboard.press('Enter');
    await study.waitForSelector('#rating-bar:not([hidden])');
    assert((await study.locator('#study-result').textContent()) === 'Not quite', 'Enter checks: “Not quite”');
    assert(await study.locator('.ex-option[data-correct="0"]').evaluate(o => o.classList.contains('selected')), 'Enter did not toggle the focused answer');
    assert(await study.evaluate(() => document.activeElement.dataset.rating) === 'again', 'Again has the focus when wrong');
    assert(await study.locator('#study-stage .ex-body').evaluate(b => b.inert), 'the exercise is locked');
    assert(await study.locator('#btn-check').isHidden(), 'Check is gone');
    const ivls = await study.locator('#rating-bar .dk-ivl').allTextContents();
    assert(ivls.every(Boolean), `interval labels: ${ivls.join(' ')}`);
    assert((await study.locator('[data-rating="good"]').getAttribute('aria-label')).includes('comes back in ' + ivls[2]), 'aria-label carries the interval');
    await study.keyboard.press('1');
    await study.waitForSelector('#btn-show:not([hidden])');
    assert(reviews[0].rating === 'again' && reviews[0].result === false && Array.isArray(reviews[0].skip), 'review {item, rating, result:false, skip}');
    assert(reviews[0].reps === 0, 'the review names the reps its labels were worked out for (0)');
    assert(itemGets.length === 0 && await study.locator('#study-solution').isHidden(),
           'a wrong choice marks the answer it wanted: no solution is asked for');

    // flashcard
    assert(await study.locator('#rating-bar').isHidden(), 'the next card starts without the bar');
    await study.click('#btn-show');
    await study.waitForSelector('#rating-bar:not([hidden])');
    assert(await study.locator('.ex-flashcard').evaluate(c => c.classList.contains('flipped')), 'Show answer turns the card');
    assert(await study.evaluate(() => document.activeElement.dataset.rating) === 'good', 'Good has the focus');
    await study.keyboard.press('3');
    await study.waitForSelector('#study-stage .ex-invalid');
    assert(reviews[1].rating === 'good' && reviews[1].result === null, 'a flashcard answer has result null');

    // an exercise with errors: Edit and Skip only
    assert(await study.locator('#btn-check').isHidden() && await study.locator('#btn-show').isHidden(), 'invalid: no Check, no Show');
    assert(await study.locator('#btn-edit-card').isVisible() && await study.locator('#btn-skip').isVisible(), 'invalid: Edit and Skip');
    assert(await study.evaluate(() => document.activeElement.id) === 'btn-edit-card', 'invalid: Edit has the focus');
    await study.evaluate(() => document.activeElement.blur());
    await study.keyboard.press('Enter');
    assert(await study.locator('#rating-bar').isHidden() && await overlays(study) === 0, 'Enter (focus on the page) does nothing there');
    const skipReq = study.waitForRequest(r => r.url().includes('/next?skip='));
    await study.click('#btn-skip');
    await skipReq;
    await study.waitForSelector('#study-stage .exercise[data-subtype="true-false"]');
    assert(true, 'Skip asks /next?skip=… and moves on');

    // true-false, right, by the button; Easy by click
    for (const g of await study.locator('.ex-choice-group').all()) await g.locator('.ex-option[data-correct="1"]').click();
    await study.click('#btn-check');
    assert((await study.locator('#study-result').textContent()) === 'Correct', '“Correct”');
    assert(await study.evaluate(() => document.activeElement.dataset.rating) === 'good', 'Good has the focus when right');
    await study.click('[data-rating="easy"]');
    await study.waitForFunction(() => document.querySelector('#rating-bar').hidden);
    assert(reviews[2].rating === 'easy' && reviews[2].result === true && reviews[2].skip.length === 1, 'the skipped id rides along with the review');

    // the first exercise is back (learn-ahead): edit it here, then answer Easy
    await study.waitForSelector('#study-stage .exercise[data-subtype="single-choice"]');
    await study.click('#btn-edit-card');
    await study.waitForSelector('.ex-form-modal');
    await study.keyboard.press('2');
    assert(reviews.length === 3, 'keys are ignored while the form is open');
    await study.locator('.ex-form-body textarea').first().fill('Choose again');
    await study.click('.ex-form-modal [data-x="save"]');
    await waitToast(study, /Exercise saved/, 'edited from study');
    await study.waitForFunction(() => /Choose again/.test(document.querySelector('#study-stage .ex-prompt')?.textContent || ''));
    assert(true, 'the same card, re-rendered as edited');
    await study.locator('.ex-option[data-correct="1"]').click();
    await study.click('#btn-check');
    await study.keyboard.press('4');
    // the flashcard's 10m step is inside the learn-ahead window: it comes back
    await study.waitForSelector('#btn-show:not([hidden])');
    await study.locator('.ex-flashcard').click();
    await study.waitForSelector('#rating-bar:not([hidden])');
    assert(true, 'turning the card by clicking it counts as showing');
    await study.keyboard.press('4');
    await study.waitForSelector('#study-done:not([hidden])');
    assert((await study.locator('#study-done h2').textContent()) === 'Nothing more to study now', 'done');
    const due = await study.locator('#study-next-due').textContent();
    assert(/^next exercise (in \S+|tomorrow)$|^no exercises scheduled$/.test(due), `next due: “${due}”`);
    assert(await study.locator('#study-stage').isHidden() && await study.locator('#study-actions').isHidden(), 'the stage and the actions go');
    assert((await study.locator('#btn-back-deck').getAttribute('href')) === '/exercises/deck/persian/persian-study/', 'back to the deck');
    assert((await study.locator('.dk-skipped').textContent()) === '1 exercise skipped this time.', 'says what was skipped');
    await study.click('.dk-unskip');
    await study.waitForSelector('#study-stage .ex-invalid');
    assert(true, 'the skipped exercise comes back on request');
    await study.click('#btn-edit-card');
    await study.waitForSelector('.dk-raw-modal');
    await study.keyboard.press('Escape');
    assert(await overlays(study) === 0, 'Escape closes the markdown dialog');

    // stop
    await study.route('**/exercises/api/shutdown', r => r.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'}));
    await study.click('#btn-stop');
    await study.locator('.dk-modal button', {hasText: 'Stop server'}).click();
    await study.waitForSelector('#shutdown-overlay:not([hidden])');
    assert(true, 'Stop posts to /exercises/api/shutdown and shows the overlay');

    // dark theme: tokens resolve
    await study.evaluate(() => { localStorage.setItem('parseh_theme', 'dark'); });
    await study.reload();
    await study.waitForSelector('#study-stage .exercise');
    assert(await study.evaluate(() => document.body.dataset.theme) === 'dark', 'the shared dark theme is applied');

    // a deck of its own for each of what follows, made through the API
    async function makeDeck(name, markdowns) {
      const res = await ctx.request.post(url('/exercises/api/decks'), {data: {name, lang: 'fa'}});
      const made = (await res.json()).deck;
      const ids = [];
      for (const markdown of markdowns) {
        const r = await ctx.request.post(url(`/exercises/api/decks/${made.path}/items`), {data: {markdown}});
        if (r.status() !== 201) throw Error(`could not add to ${name}: ${await r.text()}`);
        ids.push((await r.json()).item.id);
      }
      return {deck: made, ids, page: `/exercises/deck/${made.path}/`, study: `/exercises/deck/${made.path}/study`};
    }
    const until = async (fn, what) => {
      for (let t = 0; t < 160; t++) { if (await fn()) return; await new Promise(r => setTimeout(r, 50)); }
      throw Error(`FAIL (${mode}): ${what}`);
    };
    const pathOf = r => new URL(r.url()).pathname;

    /* ---------------- browse: provenance facets ---------------- */
    console.log('deck browse: provenance filters');
    const sourceMade = (await (await ctx.request.post(url('/exercises/api/decks'), {
      data: {name: 'Provenance filter', lang: 'fa'},
    })).json()).deck;
    const sourceBase = `/exercises/api/decks/${sourceMade.path}`;
    const sourceCards = [
      {markdown: PICK_EX.replace('Pick the greeting', 'Common provenance: notebook one alpha'),
       origin: {doc_uid: 'notebook-one-uid', doc_id: 'notebook-one', title: 'Notebook one'}, tags: ['lesson']},
      {markdown: PICK_EX.replace('Pick the greeting', 'Common provenance: notebook one beta'),
       origin: {doc_uid: 'notebook-one-uid', doc_id: 'notebook-one', title: 'Notebook one'}, tags: ['detail']},
      {markdown: PICK_EX.replace('Pick the greeting', 'Common provenance: notebook two'),
       origin: {doc_uid: 'notebook-two-uid', doc_id: 'notebook-two', title: 'Notebook two'}, tags: ['lesson']},
      {markdown: PICK_EX.replace('Pick the greeting', 'A book-source exercise'),
       origin: {book: '/books/persian/grammar', title: 'Persian grammar'}, tags: ['lesson']},
      {markdown: PICK_EX.replace('Pick the greeting', 'A video-source exercise'),
       origin: {video: 'provenance-video', title: 'Lesson video'}, tags: ['video']},
      {markdown: PICK_EX.replace('Pick the greeting', 'A local-source exercise'), tags: ['local']},
    ];
    for (const card of sourceCards) {
      const made = await ctx.request.post(url(`${sourceBase}/items`), {data: card});
      if (made.status() !== 201) throw Error(`could not add provenance exercise: ${await made.text()}`);
    }
    const provenance = await ctx.newPage();
    watch(provenance, 'provenance');
    await provenance.goto(url(`/exercises/deck/${sourceMade.path}/`));
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 6);
    assert(await provenance.locator('#browse-source-filter').isVisible(), 'the source facet is visible for a non-empty deck');
    await provenance.locator('#browse-source-filter > summary').click();
    const sourceTexts = await provenance.locator('.dk-source-option').allTextContents();
    const hasSource = text => sourceTexts.some(x => x.trim() === text);
    assert(hasSource('Document: Notebook one(2)') && hasSource('Document: Notebook two(1)')
           && hasSource('Book: Persian grammar(1)') && hasSource('Video: Lesson video(1)')
           && hasSource('Written here(1)'), 'document, book, video and written-here sources are counted');

    const openSources = async () => {
      const details = provenance.locator('#browse-source-filter');
      if (!(await details.evaluate(x => x.open))) await details.locator('summary').click();
    };
    const sourceOption = text => provenance.locator('.dk-source-option', {hasText: text}).locator('input');
    await sourceOption('Document: Notebook one').check();
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 2
                                      && document.querySelector('#browse-count').textContent === '2 of 6');
    assert((await provenance.locator('#browse-source-label').textContent()) === 'Sources (1)', 'one selected source is named in the control');
    await sourceOption('Document: Notebook two').check();
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 3);
    assert(true, 'two checked sources are alternatives within the source facet');
    await sourceOption('Document: Notebook two').uncheck();

    await provenance.fill('#browse-filter', 'common provenance');
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 2
                                      && document.querySelector('#browse-count').textContent === '2 of 6');
    assert(true, 'a source choice ANDs with a text filter');
    // the text filter narrowed the options above; clear it so the next check
    // is of the tag filter narrowing them on its own, not the two combined
    await provenance.fill('#browse-filter', '');
    await provenance.selectOption('#browse-tag', 'lesson');
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 1
                                      && document.querySelector('#browse-count').textContent === '1 of 6');
    const narrowedSources = await provenance.locator('.dk-source-option').allTextContents();
    assert(narrowedSources.some(x => x.trim() === 'Document: Notebook one(1)')
           && narrowedSources.some(x => x.trim() === 'Document: Notebook two(1)')
           && narrowedSources.some(x => x.trim() === 'Book: Persian grammar(1)')
           && !narrowedSources.some(x => /Video: Lesson video|Written here/.test(x)),
           'source options self-narrow on the other filters and omit zeroes');
    await provenance.locator('#btn-select-shown').click();
    assert((await provenance.locator('#browse-selected').textContent()) === '1 selected', 'Select shown uses the source-filtered rows');
    await provenance.locator('#btn-deselect-shown').click();
    assert((await provenance.locator('#browse-selected').textContent()) === '0 selected', 'Deselect shown uses the same source-filtered rows');

    await provenance.selectOption('#browse-tag', '');
    await provenance.fill('#browse-filter', 'video-source');
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 0
                                      && document.querySelector('#browse-count').textContent === '0 of 6');
    assert((await provenance.locator('.dk-source-option').allTextContents()).some(x => x.trim() === 'Document: Notebook one(0)'),
           'an active source remains removable at zero, so it keeps the AND result');
    await openSources();
    // a plain click, not .uncheck(): once unticked this option's own count is
    // zero and unselected, so the design removes its row on this very
    // render (only a TICKED zero is kept) -- .uncheck() would keep polling a
    // handle that is gone by design, not a bug to route around
    await sourceOption('Document: Notebook one').click();
    await provenance.waitForFunction(() => document.querySelectorAll('.dk-row').length === 1);
    const videoOnlySources = await provenance.locator('.dk-source-option').allTextContents();
    assert(videoOnlySources.length === 1 && videoOnlySources[0].trim() === 'Video: Lesson video(1)',
           'a text-filtered source menu has no zero-count choices');

    await provenance.fill('#browse-filter', '');
    await openSources();

    const phoneCtx = await browser.newContext({viewport: {width: 390, height: 844}});
    try {
      await phoneCtx.addInitScript(() => localStorage.setItem('parseh_mode', 'mobile'));
      const phone = await phoneCtx.newPage();
      watch(phone, 'provenance phone');
      await phone.goto(url(`/exercises/deck/${sourceMade.path}/`));
      await phone.waitForFunction(() => document.documentElement.dataset.mode === 'mobile'
                                     && document.querySelectorAll('.dk-row').length === 6);
      await phone.locator('#browse-source-filter > summary').click();
      const phoneLayout = await phone.evaluate(() => {
        const summary = document.querySelector('#browse-source-filter > summary').getBoundingClientRect();
        const menu = document.querySelector('.dk-source-menu').getBoundingClientRect();
        const option = document.querySelector('.dk-source-option').getBoundingClientRect();
        return {summary: summary.height, option: option.height, left: menu.left, right: menu.right,
                viewport: innerWidth, scroll: document.documentElement.scrollWidth};
      });
      assert(phoneLayout.summary >= 48 && phoneLayout.option >= 44
             && phoneLayout.left >= 0 && phoneLayout.right <= phoneLayout.viewport + 1
             && phoneLayout.scroll <= phoneLayout.viewport + 1,
             'the source dropdown has phone-sized targets without horizontal overflow at 390px');
      if (Deno.env.get('SHOTS')) {
        const dir = Deno.env.get('SHOTS');
        await provenance.screenshot({path: `${dir}/deck-provenance-desktop-${mode}.png`, fullPage: true});
        await phone.screenshot({path: `${dir}/deck-provenance-phone-${mode}.png`, fullPage: true});
      }
    } finally {
      await phoneCtx.close();
    }
    await provenance.close();

    /* ---------------- study: the answer of a wrong match or placement ---------------- */
    console.log('study: the solution under a wrong match or fill-in');
    const sol = await makeDeck('Solutions', [MATCH_PIC_EX, FILL_EX]);
    const solve = await ctx.newPage();
    watch(solve, 'solutions');
    const solGets = [];
    solve.on('request', r => { if (r.method() === 'GET' && /\/items\/[0-9a-f]{12}$/.test(r.url())) solGets.push(pathOf(r)); });
    await solve.goto(url(sol.study));
    await solve.waitForSelector('#study-stage .exercise[data-subtype="match-translations"]');
    assert(await solve.locator('#study-solution').isHidden(), 'no solution before checking');
    const placeMatch = async right => {
      const drops = solve.locator('#study-stage .ex-match-drop');
      const wants = await drops.evaluateAll(ds => ds.map(d => d.dataset.answer));
      for (let i = 0; i < wants.length; i++) {
        await solve.locator(`#study-stage .ex-item[data-item="${wants[right ? i : (i + 1) % wants.length]}"]`).click();
        await drops.nth(i).click();
      }
    };
    const solvedRows = sel => solve.locator(`#study-solution ${sel}`).evaluateAll(ds => ds.map(d => {
      const item = d.querySelector('.ex-item');
      return !!item && item.dataset.item === d.dataset.answer;
    }));
    await placeMatch(false);
    await solve.click('#btn-check');
    await solve.waitForSelector('#study-solution:not([hidden]) .exercise[data-subtype="match-translations"]');
    assert(await solve.locator('#study-result').textContent() === 'Not quite'
           && JSON.stringify(solGets) === JSON.stringify([`/exercises/api/decks/${sol.deck.path}/items/${sol.ids[0]}`]),
           'a wrong match: “Not quite”, and the deck is asked for the exercise solved');
    assert(await solve.locator('#study-solution .dk-solution-head').textContent() === 'Correct answer', 'under the heading “Correct answer”');
    const matchRows = await solvedRows('.ex-match-drop');
    assert(matchRows.length === 2 && matchRows.every(Boolean), 'the solution shows each word in its row');
    assert(await solve.locator('#study-stage .ex-match-drop.answer-wrong').count() === 2
           && await solve.locator('#study-stage .ex-body').evaluate(b => b.inert), 'the answer given stays as checked, locked');
    assert(await solve.locator('#study-solution :is(.ex-explanation, .ex-edit, .ex-to-deck, .exercise-correction)').count() === 0
           && await solve.locator('#study-stage .ex-explanation:not([hidden])').count() === 1, 'the explanation shows once, on the card');
    // the exercise's own pictures: both on the card, neither repeated under it
    assert(await solve.locator('#study-stage .ex-image-prompt').count() === 1
           && await solve.locator('#study-stage .ex-image-answer:not([hidden])').count() === 1,
           'the answer picture is shown on the card once the answer is checked');
    assert(await solve.locator('#study-solution .ex-image').count() === 0,
           'and the correct answer under it does not repeat either picture');
    await solve.keyboard.press('1');
    await solve.waitForSelector('#study-stage .exercise[data-subtype="fill-blanks"]');
    assert(await solve.locator('#study-solution').isHidden() && await solve.locator('#study-solution .exercise').count() === 0,
           'the next exercise takes the solution away');

    // THE ARROWS AND THEIR SWITCH ARE HERE TOO.  The study page draws an
    // exercise with the same renderer and binds it with the same script, so a
    // sequence carries its arrows and the switch that says whether it may
    // also be dragged -- which is the whole of "in the exercises subsoftware".
    console.log('study: a sequence, its arrows, and the switch that says whether it may be dragged');
    const ord = await makeDeck('Ordering', [ORDER_EX]);
    const order = await ctx.newPage();
    watch(order, 'ordering');
    await order.goto(url(ord.study));
    await order.waitForSelector('#study-stage .exercise[data-subtype="order-sentences"]');
    const sw = order.locator('#study-stage .ex-drag-switch');
    assert(await sw.count() === 1 && await sw.isVisible(), 'the study page shows the dragging switch');
    assert(await order.locator('#study-stage .ex-sequence .ex-move').count() === 6,
           'and every block has its two arrows');
    const said = await sw.textContent();
    await sw.click();
    assert(await sw.textContent() !== said, 'the switch flips on the study page: ' + said + ' -> ' + await sw.textContent());
    assert(await order.locator('#study-stage .ex-sequence .ex-item').first()
             .evaluate(i => i.draggable) === (await sw.getAttribute('aria-pressed') === 'true'),
           'and the blocks follow what it says');
    // the exercise is answered with the arrows alone
    const want = (await order.locator('#study-stage .ex-sequence').getAttribute('data-answer')).split(',');
    const now = () => order.locator('#study-stage .ex-sequence .ex-item')
      .evaluateAll(xs => xs.map(x => x.dataset.item));
    for (let want_at = 0; want_at < want.length; want_at++) {
      for (let at = (await now()).indexOf(want[want_at]); at > want_at; at--)
        await order.locator(`#study-stage .ex-item[data-item="${want[want_at]}"] [data-move="earlier"]`).click();
    }
    assert(JSON.stringify(await now()) === JSON.stringify(want), 'the arrows alone put it right: ' + (await now()).join());
    await order.click('#btn-check');
    assert(await order.locator('#study-result').textContent() === 'Correct', 'and it is marked correct');
    await order.close();

    // the keyboard: Enter on an item reached from the keyboard picks it, Enter on the blank places it
    const blankAnswer = await solve.locator('#study-stage .ex-blank').getAttribute('data-answer');
    const wrongId = await solve.locator(`#study-stage .ex-bank .ex-item:not([data-item="${blankAnswer}"])`).getAttribute('data-item');
    const wrongItem = solve.locator(`#study-stage .ex-item[data-item="${wrongId}"]`);
    await wrongItem.focus();
    await solve.keyboard.press('Enter');
    assert(await wrongItem.evaluate(i => i.classList.contains('picked')) && await solve.locator('#rating-bar').isHidden()
           && await solve.locator('#study-result').isHidden(), 'Enter on an item reached from the keyboard picks it: nothing is checked');
    await solve.locator('#study-stage .ex-blank').focus();
    await solve.keyboard.press('Enter');
    assert(await solve.locator(`#study-stage .ex-blank .ex-item[data-item="${wrongId}"]`).count() === 1
           && await solve.locator('#rating-bar').isHidden(), 'Enter on the blank puts it there');
    await solve.click('#btn-check');
    await solve.waitForSelector('#study-solution:not([hidden]) .exercise[data-subtype="fill-blanks"]');
    const blankRows = await solvedRows('.ex-blank');
    assert(await solve.locator('#study-result').textContent() === 'Not quite' && blankRows.length === 1 && blankRows[0],
           'a wrong fill-in: the solution fills the blank rightly');
    await solve.keyboard.press('4');
    // the match is back (learn-ahead): right this time, and no solution is asked for
    await solve.waitForSelector('#study-stage .exercise[data-subtype="match-translations"]');
    await placeMatch(true);
    await solve.click('#btn-check');
    await solve.waitForSelector('#rating-bar:not([hidden])');
    await solve.waitForTimeout(300);
    assert(await solve.locator('#study-result').textContent() === 'Correct' && solGets.length === 2
           && await solve.locator('#study-solution').isHidden(), 'a right answer: “Correct”, no solution');
    await solve.keyboard.press('4');
    await solve.waitForSelector('#study-done:not([hidden])');
    await solve.close();

    /* ---------------- study: a slow answer, a skip, an edit, a failure ---------------- */
    console.log('study: while an answer is on its way');
    const slow = await makeDeck('Slow answers', [PICK_EX, TF_EX, YN_EX]);
    const sp = await ctx.newPage();
    watch(sp, 'slow');
    const sent = [];       // the deck requests, in order: "POST /review", "GET /next?skip=…"
    sp.on('request', r => {
      const u = new URL(r.url());
      if (u.pathname.startsWith(`/exercises/api/decks/${slow.deck.path}/`))
        sent.push(`${r.method()} ${u.pathname.slice(`/exercises/api/decks/${slow.deck.path}`.length)}${u.search}`);
    });
    const isReview = u => u.pathname.endsWith('/review'), isNext = u => u.pathname.endsWith('/next');
    const hold = async (page, match) => {
      let release;
      const held = new Promise(r => { release = r; });
      await page.route(match, async route => { await held; await route.continue(); });
      return async () => { release(); await page.unroute(match); };
    };
    const checkRight = async subtype => {
      await sp.waitForSelector(`#study-stage .exercise[data-subtype="${subtype}"]`);
      for (const g of await sp.locator('#study-stage .ex-choice-group').all()) await g.locator('.ex-option[data-correct="1"]').click();
      await sp.click('#btn-check');
      await sp.waitForSelector('#rating-bar:not([hidden])');
    };
    await sp.goto(url(slow.study));
    await checkRight('single-choice');
    let release = await hold(sp, isReview);
    let n = sent.length;
    await sp.keyboard.press('3');
    await sp.waitForFunction(() => document.querySelector('#rating-bar button').disabled);
    await sp.evaluate(() => { document.querySelector('#btn-skip').click(); document.querySelector('#btn-edit-card').click(); });
    await sp.keyboard.press('4');
    assert(await sp.locator('#btn-skip').isDisabled() && await sp.locator('#btn-edit-card').isDisabled(),
           'Skip and Edit wait while the answer is on its way');
    await release();
    await sp.waitForSelector('#study-stage .exercise[data-subtype="true-false"]');
    assert(JSON.stringify(sent.slice(n)) === '["POST /review"]' && await overlays(sp) === 0,
           `…so the rated exercise is neither skipped nor edited, nor answered twice (${sent.slice(n).join(', ')})`);

    // Skip, while the next exercise is slow to come: a rating key finds nothing to rate
    await checkRight('true-false');
    release = await hold(sp, isNext);
    n = sent.length;
    await sp.click('#btn-skip');
    assert(await sp.locator('#rating-bar').isHidden(), 'Skip takes the rating bar away at once');
    await sp.keyboard.press('3');
    await release();
    await sp.waitForSelector('#study-stage .exercise[data-subtype="yes-no"]');
    assert(JSON.stringify(sent.slice(n)) === JSON.stringify([`GET /next?skip=${slow.ids[1]}`]),
           `a key pressed after Skip rates nothing (${sent.slice(n).join(', ')})`);

    // an edit's reload still on its way when the exercise is rated: the answer's next exercise stays
    await checkRight('yes-no');
    release = await hold(sp, isNext);
    await sp.click('#btn-edit-card');
    await sp.waitForSelector('.ex-form-modal');
    await sp.click('.ex-form-modal [data-x="save"]');
    await waitToast(sp, /^Exercise saved: its scheduling is unchanged$/, 'edited while checked');
    await until(async () => await overlays(sp) === 0, 'the form did not close');
    const reviewed = sp.waitForResponse(r => isReview(new URL(r.url())));
    await sp.keyboard.press('4');
    await reviewed;
    await sp.waitForSelector('#study-stage .exercise[data-subtype="single-choice"]');
    await sp.evaluate(() => { document.querySelector('#study-stage .exercise').dataset.mark = 'shown'; });
    const late = sp.waitForResponse(r => isNext(new URL(r.url())));
    await release();
    await late;
    await sp.waitForTimeout(200);
    assert(await sp.locator('#study-stage .exercise[data-mark="shown"][data-subtype="single-choice"]').count() === 1,
           'the reload that was on its way does not draw over the next exercise');

    // an answer that fails: it may have been saved, so the deck is asked again
    await checkRight('single-choice');
    await sp.route(isReview, r => r.fulfill({status: 500, contentType: 'application/json',
                                             body: '{"ok": false, "error": "the disk is full"}'}));
    const again = sp.waitForRequest(r => isNext(new URL(r.url())));
    again.catch(() => {});    // awaited below; a check failing first must be the error shown
    await sp.keyboard.press('3');
    await waitToast(sp, /^The answer may not have been saved: the disk is full$/, 'a failed answer');
    await again;
    await sp.waitForSelector('#study-stage .exercise[data-subtype="single-choice"] .ex-body:not([inert])');
    assert(await sp.locator('#rating-bar').isHidden() && await sp.locator('#btn-check').isVisible(),
           'the deck says what comes now: the same exercise, to answer afresh');
    await sp.unroute(isReview);
    await sp.close();

    /* ---------------- study: one exercise, answered in two tabs ---------------- */
    console.log('study: the same exercise in two tabs');
    const two = await makeDeck('Two tabs', [PICK_EX, YN_EX]);
    const tabA = await ctx.newPage(), tabB = await ctx.newPage();
    watch(tabA, 'tab A');
    watch(tabB, 'tab B');
    for (const t of [tabA, tabB]) {
      await t.goto(url(two.study));
      await t.waitForSelector('#study-stage .exercise[data-subtype="single-choice"]');
    }
    const answerEasy = async t => {
      await t.locator('#study-stage .ex-option[data-correct="1"]').click();
      await t.click('#btn-check');
      await t.waitForSelector('#rating-bar:not([hidden])');
      const res = t.waitForResponse(r => isReview(new URL(r.url())));
      await t.keyboard.press('4');
      return res;
    };
    assert((await answerEasy(tabA)).status() === 200, 'tab A answers it Easy');
    await tabA.waitForSelector('#study-stage .exercise[data-subtype="yes-no"]');
    const stale = await answerEasy(tabB);
    assert(stale.status() === 409 && (await stale.json()).conflict === 'reviewed', 'tab B, still showing it, is refused: 409 “reviewed”');
    await tabB.waitForSelector('#study-stage .exercise[data-subtype="yes-no"]');
    await waitToast(tabB, /^This exercise was already answered/, 'tab B says so');
    assert(!(await tabB.locator('#toast').evaluate(t => t.classList.contains('err'))), '…and moves on to what comes next, without an error');
    const once = (await (await ctx.request.get(url(`/exercises/api/decks/${two.deck.path}/items/${two.ids[0]}`))).json()).item;
    assert(once.reps === 1 && once.schedule.state === 'review', `the exercise was scheduled once (reps ${once.reps})`);
    await tabA.close();
    await tabB.close();

    /* ---------------- pictures, uploaded from the exercise form ---------------- */
    console.log('pictures uploaded into a deck from the form');
    const pics = await makeDeck('Pictures', [CAT_EX]);
    const ps = await ctx.newPage();
    watch(ps, 'pictures');
    await ps.goto(url(pics.study));
    await ps.waitForSelector('#btn-show:not([hidden])');
    await ps.click('#btn-edit-card');
    await ps.waitForSelector('.ex-form-modal');
    // a vocabulary card has two picture fields and two recording fields: an Upload… beside each
    assert(await ps.locator('.ex-form-modal .ex-upload').count() === 4, 'Edit on the study page: Upload… beside both picture and both recording fields');
    await ps.keyboard.press('Escape');

    await ps.goto(url(pics.page));
    await ps.waitForSelector('.dk-row');
    const fieldOf = label => ps.locator(`.ex-form-modal .ex-author-field:has(> span:text-is("${label}"))`);
    const openCard = async () => {
      await ps.click('#btn-add-exercise');
      await ps.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
      await ps.waitForSelector('.ex-form-modal');
    };
    await openCard();
    assert(await ps.locator('.ex-form-modal .ex-upload').count() === 4, 'Add exercise… on the deck page: Upload… beside both picture and both recording fields');
    await fieldOf('Word or expression').locator('textarea').fill('[سگ]{tl}');
    await fieldOf('Meaning').locator('textarea').fill('dog');
    const front = fieldOf('Front image path').locator('input[type="text"]');
    const back = fieldOf('Back image path').locator('input[type="text"]');
    const uploads = [];
    ps.on('request', r => { if (r.method() === 'POST' && pathOf(r).endsWith('/images')) uploads.push(r.url()); });
    const upload = async (i, file) => {
      const [chooser] = await Promise.all([ps.waitForEvent('filechooser'), ps.locator('.ex-form-modal .ex-upload').nth(i).click()]);
      await chooser.setFiles(file);
    };
    await upload(0, {name: 'dog.png', mimeType: 'image/png', buffer: PNG_A});
    await until(async () => await front.inputValue() === 'images/dog.png', `the front field: “${await front.inputValue()}”`);
    assert(uploads[0] === url(`/exercises/api/decks/${pics.deck.path}/images?name=dog.png`), 'the picture goes to the deck, raw, named');
    await upload(1, {name: 'dog.png', mimeType: 'image/png', buffer: PNG_B});
    await until(async () => await back.inputValue() === 'images/dog-2.png', `the back field: “${await back.inputValue()}”`);
    assert(true, 'another picture of the same name is stored under another: images/dog-2.png');
    await upload(1, {name: 'text.png', mimeType: 'image/png', buffer: Buffer.from('not a picture at all')});
    await waitToast(ps, /^Could not upload the picture: /, 'a file that is not a picture is refused');
    assert(await back.inputValue() === 'images/dog-2.png' && await overlays(ps) === 1, 'the field keeps its picture, the form stays open');
    await ps.click('.ex-form-modal [data-x="save"]');
    await waitToast(ps, /^Added to “Pictures”$/, 'added with its pictures, and no warning');
    const dog = (await (await ctx.request.get(url(`/exercises/api/decks/${pics.deck.path}`))).json()).items.find(i => i.markdown.includes('dog'));
    assert(dog && dog.markdown.includes('front-image: images/dog.png') && dog.markdown.includes('back-image: images/dog-2.png'), 'the exercise names both pictures');
    const served = await ctx.request.get(url(`/exercises/media/${pics.deck.path}/images/dog-2.png`));
    assert(served.status() === 200 && Buffer.compare(await served.body(), PNG_B) === 0, 'and the deck serves them');

    // a picture typed in that the deck does not have: added, with a warning
    await openCard();
    await fieldOf('Word or expression').locator('textarea').fill('[ماهی]{tl}');
    await fieldOf('Front image path').locator('input[type="text"]').fill('images/fish.png');
    await ps.click('.ex-form-modal [data-x="save"]');
    await waitToast(ps, /^Added to “Pictures”, but front-image: images\/fish\.png is not among this deck's pictures/, 'a missing picture is warned of');

    // studied, the card shows the pictures uploaded for it
    await ps.goto(url(pics.study));
    await ps.waitForSelector('#study-stage .exercise[data-primitive="flashcard"]');
    await ps.click('#btn-show');                    // the card without pictures comes first: Easy
    await ps.waitForSelector('#rating-bar:not([hidden])');
    await ps.keyboard.press('4');
    const loaded = side => ps.waitForFunction(s => {
      const img = document.querySelector(`#study-stage .ex-card-${s} img.ex-card-image`);
      return img && !img.closest('[hidden]') && img.complete && img.naturalWidth > 0 ? img.getAttribute('src') : false;
    }, side, {timeout: 8000}).then(h => h.jsonValue()).catch(() => '');
    const frontSrc = await loaded('front');
    assert(frontSrc === `/exercises/media/${pics.deck.path}/images/dog.png`, `the study card shows the front picture (${frontSrc})`);
    await ps.click('#btn-show');
    const backSrc = await loaded('back');
    assert(backSrc === `/exercises/media/${pics.deck.path}/images/dog-2.png`, `and, turned, the back one (${backSrc})`);
    await ps.close();

    /* ---------------- recordings, from the form to the study card and back ---------------- */
    console.log('recordings uploaded from the form, played on the study card, exported and imported');
    {
      const rp = await ctx.newPage();
      watch(rp, 'recordings');
      await recordingsFlow({page: rp, request: ctx.request, url, assert, zip: zipEntries, refusal: true,
                            toast: (pg, re, what) => waitToast(pg, re, what)});
      await rp.close();
    }
    console.log("a jolly card's recording lines, played on the study card as Anki plays them");
    {
      const jp = await ctx.newPage();
      watch(jp, 'jolly recordings');
      await jollyRecordingsFlow({page: jp, request: ctx.request, url, assert, toast: (pg, re, what) => waitToast(pg, re, what)});
      await jp.close();
    }
    console.log('a clip past the end of its recording, and a window left open while an answer was saved');
    {
      const ep = await ctx.newPage();
      watch(ep, 'study edges');
      await studyEdgesFlow({page: ep, request: ctx.request, url, assert, toast: (pg, re, what) => waitToast(pg, re, what)});
      await ep.close();
    }
    console.log('a both-repeat card is two linked cards: badge, the question on edit and delete, buried on study');
    {
      const lp = await ctx.newPage();
      watch(lp, 'linked cards');
      await linkedCardsFlow({page: lp, browser, request: ctx.request, url, assert, studio: S, tmp: info.tmp, mode,
                             toast: (pg, re, what) => waitToast(pg, re, what)});
      await lp.close();
    }

    /* ---------------- where a card made in a book or a video came from ---------------- */
    console.log('the origin of a card made in a book or a video');
    {
      const made = (await (await ctx.request.post(url('/exercises/api/decks'), {data: {name: 'Made elsewhere', lang: 'fa'}})).json()).deck;
      const add = async (markdown, origin) => {
        const r = await ctx.request.post(url(`/exercises/api/decks/${made.path}/items`), {data: {markdown, origin}});
        assert(r.status() === 201, `POST …/items with an origin: 201 (${r.status()})`);
        return (await r.json()).item;
      };
      const fromBook = await add(PICK_EX, {book: '/books/persian/tale', label: '3.2', title: 'A tale',
                                           url: '/books/persian/tale/reader/#p3.2', page: 'dropped'});
      const fromVideo = await add(TF_EX, {video: 'abc_DEF-123', time: 65.9, label: '1:05', title: 'A film'});
      const hostile = await add(YN_EX, {book: '/books/persian/other', url: 'javascript:alert(1)', label: '<b>7</b>'});
      const film = await add(CAT_EX, {video: 'abc_DEF-123', url: '//evil.example/watch', time: -4});
      // a YouTube address beside the second: Parseh's own player all the same; with no second, that address
      const onYoutube = await add(MATCH_EX, {video: 'abc_DEF-123', time: 65, label: '1:05',
                                             url: 'https://www.youtube.com/watch?v=abc_DEF-123&t=65s'});
      const noSecond = await add(FILL_EX, {video: 'abc_DEF-123', url: 'https://www.youtube.com/watch?v=abc_DEF-123'});
      assert(JSON.stringify(fromBook.origin) === JSON.stringify({title: 'A tale', book: '/books/persian/tale', label: '3.2',
                                                                 url: '/books/persian/tale/reader/#p3.2'})
             && JSON.stringify(hostile.origin) === JSON.stringify({book: '/books/persian/other', label: '<b>7</b>'})
             && JSON.stringify(film.origin) === JSON.stringify({video: 'abc_DEF-123'}),
             `the store keeps what can be linked, and drops the rest (${JSON.stringify([fromBook.origin, hostile.origin, film.origin])})`);
      const op = await ctx.newPage();
      watch(op, 'origins');
      // a hand-edited item file the store did not clean: the page links no other host either
      await op.route(url(`/exercises/api/decks/${made.path}`), async route => {
        const res = await route.fetch();
        const data = await res.json();
        data.items.find(i => i.id === film.id).origin.url = '/\\evil.example/x';
        await route.fulfill({response: res, json: data});
      });
      await op.goto(url(`/exercises/deck/${made.path}/`));
      await op.waitForSelector('.dk-row .dk-origin a');
      const link = async id => op.locator(`.dk-row[data-id="${id}"] .dk-origin`).evaluate(o => {
        const a = o.querySelector('a');
        return [o.textContent, a && a.getAttribute('href'), a && a.title];
      });
      let got = await link(fromBook.id);
      assert(JSON.stringify(got) === JSON.stringify(['from A tale · 3.2', '/books/persian/tale/reader/#p3.2', 'The book the card was made from']),
             `a book's card links the moment it was made at (${got})`);
      got = await link(fromVideo.id);
      assert(JSON.stringify(got) === JSON.stringify(['from A film · 1:05', '/youtube/v/abc_DEF-123/#t=65', 'The video the card was made from']),
             `a video's card links the player at its second (${got})`);
      got = await link(hostile.id);
      assert(got[0] === 'from other · <b>7</b>' && got[1] === '/books/persian/other/reader/' && !(await op.locator('.dk-origin b').count()),
             `no link but a path here: the book's reader instead, the label as text (${got})`);
      got = await link(film.id);
      assert(got[0] === 'from abc_DEF-123' && got[1] === '/youtube/v/abc_DEF-123/', `nor one a browser reads as another host: the player (${got})`);
      got = await link(onYoutube.id);
      assert(JSON.stringify(got) === JSON.stringify(['from abc_DEF-123 · 1:05', '/youtube/v/abc_DEF-123/#t=65', 'The video the card was made from']),
             `a video's card with a YouTube address opens Parseh's player at its second, not YouTube (${got})`);
      got = await link(noSecond.id);
      assert(got[1] === 'https://www.youtube.com/watch?v=abc_DEF-123', `with no second kept, its own address (${got})`);
      await op.close();
    }

    /* ---------------- a rich jolly card on the study page, wide and narrow ---------------- */
    if (MEDIA.ok) {
      console.log('a rich jolly card on the study page');
      const rich = (await (await ctx.request.post(url('/exercises/api/decks'), {data: {name: 'Rich card', lang: 'fa'}})).json()).deck;
      const rapi = `/exercises/api/decks/${rich.path}`;
      assert((await ctx.request.post(url(`${rapi}/images?name=pic.png`), {data: MEDIA.pic})).status() === 201
             && (await ctx.request.post(url(`${rapi}/audio?name=salam.mp3`), {data: MEDIA.a})).status() === 201,
             'its picture and its recording uploaded');
      const RICH = [':::exercise flashcard', 'card-type: jolly', 'front-primary: |', '  ### [سلام]{tl}', '',
        '  ![a greeting](images/pic.png){width=60 align=center}', '', '  ![said slowly](audio/salam.mp3)',
        'front-secondary: salām, the everyday greeting[^n1]', 'back-primary: |', '  **hello** — said on arriving', '',
        '  | when | what is said |', '  |---|---|', '  | morning | [صبح بخیر]{tl} |', '  | any hour | [سلام]{tl} |', '',
        '  - to a friend', '  - to a stranger', '', '  > The reply is the same word.',
        'back-secondary: |', '  see the note', '', '  [^n1]: the long a of the Persian word', ':::'].join('\n');
      const r = await ctx.request.post(url(`${rapi}/items`), {data: {markdown: RICH}});
      assert(r.status() === 201 && JSON.stringify((await r.json()).warnings) === '[]', `the rich card is added, with nothing missing (${r.status()})`);
      for (const [w, h, name] of [[1280, 900, 'desktop'], [400, 860, 'narrow']]) {
        const vc = await browser.newContext({viewport: {width: w, height: h}});
        try {
          const sp = await vc.newPage();
          watch(sp, `rich card ${name}`);
          await sp.goto(url(`/exercises/deck/${rich.path}/`));
          await sp.waitForSelector('.dk-row');
          await Promise.all([sp.waitForURL(url(`/exercises/deck/${rich.path}/study`)), sp.click('#btn-study')]);
          await sp.waitForSelector('#study-stage .ex-flashcard[data-card-type="jolly"]');
          const fits = () => sp.evaluate(() => {
            const card = document.querySelector('#study-stage .ex-flashcard').getBoundingClientRect();
            const out = [...document.querySelectorAll('#study-stage .ex-flashcard *')].filter(e => {
              // what is not in view: a hidden side, a note's cloud until it is pointed at
              if (e.closest('[hidden]') || getComputedStyle(e).visibility === 'hidden') return false;
              const r = e.getBoundingClientRect();
              return r.width && (r.left < card.left - 1 || r.right > card.right + 1);
            }).map(e => e.tagName + '.' + e.className);
            return {out, page: document.documentElement.scrollWidth, inner: innerWidth, right: card.right};
          });
          await sp.waitForFunction(() => {
            const img = document.querySelector('#study-stage .ex-card-front img');
            const a = document.querySelector('#study-stage .ex-card-front figure.audio audio');
            return img && img.complete && img.naturalWidth === 320 && a && a.readyState >= 1;
          }, null, {timeout: 10000});
          let f = await fits();
          assert(f.out.length === 0 && f.page <= f.inner && f.right <= f.inner,
                 `${name} (${w}px): the front, its heading, picture and player inside the card and the page (${JSON.stringify(f)})`);
          if (Deno.env.get('SHOTS')) await sp.screenshot({path: `${Deno.env.get('SHOTS')}/rich-card-front-${name}-${mode}.png`, fullPage: true});
          // a press on a note's mark opens the note (on a phone a tap is the only way) and turns nothing,
          // on the card and on its enlarged copy
          const unturned = async () => !(await sp.locator('#study-stage .ex-flashcard').evaluate(c => c.classList.contains('flipped')))
            && await sp.locator('#rating-bar').isHidden() && await sp.locator('#btn-show').isVisible();
          await sp.click('#study-stage .ex-card-front .fnref');
          const noteOpen = await sp.waitForFunction(() => {
            const c = document.querySelector('#study-stage .ex-card-front .fncloud');
            return !!c && getComputedStyle(c).visibility === 'visible' && +getComputedStyle(c).opacity > 0.9;
          }, null, {timeout: 3000}).then(() => true, () => false);
          assert(noteOpen && await unturned(), `${name}: a press on the note's mark opens the note, and turns nothing`);
          if (Deno.env.get('SHOTS')) await sp.screenshot({path: `${Deno.env.get('SHOTS')}/rich-card-note-${name}-${mode}.png`, fullPage: true});
          await sp.click('#study-stage .ex-card-zoom');
          await sp.waitForSelector('.ex-zoom-overlay .ex-flashcard');
          await sp.click('.ex-zoom-overlay .ex-card-front .fnref');
          await sp.waitForTimeout(200);
          assert(await unturned() && !(await sp.locator('.ex-zoom-overlay .ex-flashcard').evaluate(c => c.classList.contains('flipped'))),
                 `${name}: nor on the enlarged card`);
          await sp.keyboard.press('Escape');
          await sp.waitForSelector('.ex-zoom-overlay', {state: 'detached'});
          await sp.click('#btn-show');
          await sp.waitForSelector('#rating-bar:not([hidden])');
          f = await fits();
          assert(f.out.length === 0 && f.page <= f.inner && await sp.locator('#study-stage .ex-card-back table').isVisible()
                 && await sp.locator('#study-stage .ex-card-back li').count() === 2
                 && await sp.locator('#study-stage .ex-card-back .box').isVisible(),
                 `${name}: turned, the back's table, list and box inside the card and the page (${JSON.stringify(f)})`);
          assert((await sp.locator('#study-stage .fncloud, #study-stage .footnotes').first().textContent()).includes('the long a'),
                 `${name}: the note written on the card is the page's`);
          if (Deno.env.get('SHOTS')) await sp.screenshot({path: `${Deno.env.get('SHOTS')}/rich-card-back-${name}-${mode}.png`, fullPage: true});
        } finally {
          await vc.close();
        }
      }
    }

    /* ---------------- a review's day, across a clock change ---------------- */
    console.log('due days across a clock change (Europe/Rome)');
    const rome = await browser.newContext({timezoneId: 'Europe/Rome'});
    try {
      const dp = await rome.newPage();
      watch(dp, 'due days');
      let forcedDue = '';
      await dp.route(url('/exercises/api/decks/arabic/arabic-basics'), async route => {
        const res = await route.fetch();
        const data = await res.json();
        const here = data.items.find(i => !i.origin);
        here.schedule = Object.assign({}, here.schedule, {state: 'review', due: forcedDue, interval: 13, ease: 2.5, reps: 3});
        here.reps = 3;
        // a source that is not a path on this server: the link stays in the studio
        const noted = data.items.find(i => i.origin && i.origin.source);
        noted.origin = Object.assign({}, noted.origin, {source: '//elsewhere.example/notes'});
        await route.fulfill({response: res, json: data});
      });
      const readDue = async (now, due) => {
        forcedDue = due;
        await dp.clock.setFixedTime(new Date(now));
        await dp.goto(url('/exercises/deck/arabic/arabic-basics/'));
        await dp.waitForSelector('.dk-row .dk-state-review');
        const when = await dp.locator('.dk-row', {has: dp.locator('.dk-state-review')}).locator('.dk-when').textContent();
        await dp.selectOption('#browse-state', 'due');
        const dueRows = await dp.locator('.dk-row').count();
        await dp.selectOption('#browse-state', '');
        return `${when} / ${dueRows}`;
      };
      // answered in summer (+02:00) for 2 November, read after the clocks went back (+01:00)
      let got = await readDue('2026-11-01T15:00:00+01:00', '2026-11-02T04:00:00+02:00');
      assert(got === 'due tomorrow / 0', `the afternoon before: “${got}”`);
      assert(await dp.locator('.dk-origin a').getAttribute('href') === `${S}/doc/${info.notes_doc_id}`,
             'a source that is not a path here links the studio instead');
      got = await readDue('2026-11-02T03:30:00+01:00', '2026-11-02T04:00:00+02:00');
      assert(got === 'due in 30m / 0', `half an hour before its day starts: “${got}”`);
      got = await readDue('2026-11-02T04:30:00+01:00', '2026-11-02T04:00:00+02:00');
      assert(got === 'due now / 1', `once its day has started: “${got}”`);
      // answered in winter (+01:00) for 28 March, read after the clocks went forward (+02:00)
      got = await readDue('2027-03-28T04:30:00+02:00', '2027-03-28T04:00:00+01:00');
      assert(got === 'due now / 1', `spring: its day has started: “${got}”`);
      // the day before the clocks go forward, that day is still tomorrow (not "in 17h")
      got = await readDue('2027-03-27T10:00:00+01:00', '2027-03-28T04:00:00+01:00');
      assert(got === 'due tomorrow / 0', `spring, the day before: “${got}”`);
      // a due not at the rollover hour is an instant, as the scheduler reads it
      got = await readDue('2026-11-02T03:30:00+01:00', '2026-11-02T03:00:00Z');
      assert(got === 'due in 30m / 0', `an instant (03:00Z): “${got}”`);
    } finally {
      await rome.close();
    }

    /* ---------------- "+ Deck" on a studio document, against the real deck API ---------------- */
    console.log('+ Deck on a document page');
    const doc = await ctx.newPage();
    watch(doc, 'doc');
    const questions = [];
    doc.on('dialog', d => { questions.push(d.message()); d.accept(); });
    await doc.goto(url(`${S}/doc/${info.doc_id}`));
    await doc.waitForSelector('#sheet .ex-to-deck');
    assert(await doc.evaluate(() => document.body.dataset.decksBase) === '/exercises', 'the document page knows where the decks are');
    const itemsOf = async path => (await (await ctx.request.get(url('/exercises/api/decks/' + path))).json()).items;
    const before = (await itemsOf('persian/persian-practice')).length;
    const tf = doc.locator('#sheet .exercise[data-subtype="true-false"]');
    await tf.locator('.ex-to-deck').click();
    await doc.waitForSelector('.ex-to-deck-modal select option[value="persian/persian-study"]', {state: 'attached'});
    const offered = await doc.locator('.ex-to-deck-modal select option').evaluateAll(os => os.map(o => o.value));
    assert(offered.includes('persian/persian-practice') && !offered.some(v => v.startsWith('arabic/')),
           `the Persian decks are offered, and only they (${offered.filter(Boolean).join(', ')})`);
    await doc.locator('.ex-to-deck-modal select').selectOption('persian/persian-practice');
    await doc.locator('.ex-to-deck-modal [data-x="copy"]').click();
    await waitToast(doc, /Copied into “Persian drills”/, 'copied into the renamed deck');
    assert(questions.length === 1 && questions[0].includes('already in “Persian drills”'),
           'the exercise was already there (copied when the deck was made): asked, and added again');
    const after = await itemsOf('persian/persian-practice');
    const newest = after[after.length - 1];
    assert(after.length === before + 1 && newest.subtype === 'true-false' && newest.origin.doc_id === info.doc_id
           && newest.origin.ordinal === 1 && newest.origin.title === 'Greetings doc',
           'the copy is in the deck, with the document as its origin');
    assert(await tf.locator('.ex-option.selected').count() === 0 && !(await tf.evaluate(e => e.classList.contains('correct'))),
           '+ Deck never answers the exercise it sits on');

    await tf.locator('.ex-to-deck').click();
    await doc.waitForSelector('.ex-to-deck-modal select option[value="persian/persian-practice"]', {state: 'attached'});
    assert(await doc.locator('.ex-to-deck-modal select').inputValue() === 'persian/persian-practice', 'the deck used last is preselected');
    await doc.locator('.ex-to-deck-modal select').selectOption('');
    await doc.fill('.ex-to-deck-modal [data-x="name"]', 'From the page');
    await doc.locator('.ex-to-deck-modal [data-x="copy"]').click();
    await waitToast(doc, /Copied into “From the page”/, 'a new deck, made and filled from the page');
    const persian = (await (await ctx.request.get(url('/exercises/api/decks?lang=fa'))).json()).decks;
    const made = persian.find(d => d.name === 'From the page');
    assert(made && made.lang === 'fa' && made.counts.total === 1, 'the new deck is Persian and holds the exercise');
    assert(questions.length === 1, 'no question for a deck the exercise is not in');

    /* ---------------- "+ Deck" on a note beside a book (Parseh: serve.py's notes route) ---------------- */
    if (mode === 'parseh') {
      console.log('+ Deck on a note beside a book');
      const note = await ctx.newPage();
      watch(note, 'note');
      const copies = [];
      note.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/copy')) copies.push(JSON.parse(r.postData())); });
      const notePage = `${info.notes_source}/doc/${info.notes_doc_id}`;
      await note.goto(url(notePage));
      await note.waitForSelector('#sheet .ex-to-deck');
      assert(await note.evaluate(() => `${document.body.dataset.decksBase} ${document.body.dataset.notesSource}`)
             === `/exercises ${info.notes_source}`, 'the note knows where the decks are, and names its own mount');
      assert(await note.locator('#sheet .ex-to-deck').count() === 2, '+ Deck beside each of its two exercises');
      await note.locator('#sheet .exercise[data-subtype="single-choice"] .ex-to-deck').click();
      await note.waitForSelector('.ex-to-deck-modal select option[value="arabic/arabic-basics"]', {state: 'attached'});
      await note.locator('.ex-to-deck-modal select').selectOption('arabic/arabic-basics');
      await note.locator('.ex-to-deck-modal [data-x="copy"]').click();
      await waitToast(note, /Copied into “Arabic basics”/, 'copied from the note');
      assert(copies.length === 1 && copies[0].source === info.notes_source && copies[0].doc_id === info.notes_doc_id,
             `the copy names the note's mount (${JSON.stringify(copies[0])})`);
      const fromNote = (await itemsOf('arabic/arabic-basics')).find(i => i.subtype === 'single-choice' && i.origin);
      assert(fromNote && fromNote.origin.source === info.notes_source && fromNote.origin.doc_id === info.notes_doc_id
             && fromNote.origin.ordinal === 2 && fromNote.origin.title === 'Arabic grammar notes',
             'the deck holds it, with the note as its origin');
      await note.goto(url('/exercises/deck/arabic/arabic-basics/'));
      const back = note.locator(`.dk-row[data-id="${fromNote.id}"] .dk-origin a`);
      assert(await back.getAttribute('href') === notePage, 'its row links the note');
      await Promise.all([note.waitForURL(url(notePage)), back.click()]);
      await note.waitForSelector('#sheet .exercise[data-subtype="single-choice"]');
      assert(true, 'and the link opens the note');

      /* and back the other way, into the note's own editor: the document is
         read from that shelf, and its pictures land in ITS folder */
      await ctx.request.post(url('/exercises/api/decks/arabic/arabic-basics/images?name=cat.png'),
                             {headers: {'Content-Type': 'image/png'}, data: PNG_A});
      await ctx.request.post(url('/exercises/api/decks/arabic/arabic-basics/items'),
        {data: {markdown: ':::exercise single-choice\nprompt: أي صورة؟\nimage: images/cat.png\n' +
                          '- [x] هذه\n- [ ] تلك\n:::'}});
      await note.goto(url(`${info.notes_source}/doc/${info.notes_doc_id}/edit`));
      await note.waitForSelector('#src');
      assert(await note.evaluate(() => `${document.body.dataset.decksBase} ${document.body.dataset.notesSource}`)
             === `/exercises ${info.notes_source}`, 'the note’s editor knows the decks, and names its own mount');
      await note.evaluate(() => { const t = document.querySelector('#src');
                                  t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
      await note.locator('summary.btn', {hasText: 'Exercises'}).click();
      await note.locator('#btn-exercise-deck').click();
      await note.waitForSelector('.ex-from-deck-modal .dl-item');
      await note.locator('.ex-from-deck-modal [data-x="deck"]').selectOption('arabic/arabic-basics');
      await note.waitForFunction(() => [...document.querySelectorAll('.ex-from-deck-modal .dl-item')]
                                        .some(e => /صورة/.test(e.textContent)));
      await note.locator('.ex-from-deck-modal .dl-item', {hasText: 'صورة'}).click();
      await note.locator('.ex-from-deck-modal [data-x="insert"]').click();
      await waitToast(note, /Exercise inserted/, 'loaded into the note');
      assert(/image: images\/cat\.png/.test(await note.inputValue('#src')),
             'the block went into the note naming its picture');
      const notePics = (await (await ctx.request.get(
        url(`${info.notes_source}/api/docs/${info.notes_doc_id}/images`))).json()).images;
      assert(notePics.some(p => p.name === 'cat.png'),
             'and the picture is in the note’s own folder, on that shelf');
      await note.close();
    }

    /* ---------------- the editor's "Load from a deck…": the other direction ---------------- */
    {
      console.log('Load from a deck (the editor)');
      // an exercise with a picture and a footnote, put into the deck the way
      // a page puts one there -- the only way a deck item HAS footnotes
      const srcDoc = await (await ctx.request.post(url(`${S}/api/docs`), {data: {markdown:
        '---\ntitle: Source page\ntarget: fa\n---\n\n' +
        ':::exercise single-choice\nprompt: Which cat?\nimage: images/cat.png\n' +
        '- [x] this one[^n1]\n- [ ] that one\n:::\n\n[^n1]: the deck’s own note\n'}})).json();
      const srcId = srcDoc.meta.id;
      await ctx.request.post(url(`${S}/api/docs/${srcId}/images?name=cat.png`),
                             {headers: {'Content-Type': 'image/png'}, data: PNG_A});
      // a deck of its own, so what the list shows is this test's alone
      const mine = (await (await ctx.request.post(url('/exercises/api/decks'),
        {data: {name: 'To load from', lang: 'fa'}})).json()).deck;
      const put = await (await ctx.request.post(url(`/exercises/api/decks/${mine.path}/copy`),
        {data: {doc_id: srcId, ordinal: 1, subtype: 'single-choice', updated: srcDoc.meta.updated}})).json();
      assert(put.item && put.item.footnotes === '[^n1]: the deck’s own note',
             'the deck holds the exercise with the note it calls');

      // the document it is going into already has a DIFFERENT cat.png and a
      // DIFFERENT note called n1: neither may be overwritten
      await ctx.request.post(url(`${S}/api/docs/${info.doc_id}/images?name=cat.png`),
                             {headers: {'Content-Type': 'image/png'}, data: PNG_B});
      const had = (await (await ctx.request.get(url(`${S}/api/docs/${info.doc_id}`))).json()).markdown;
      await ctx.request.put(url(`${S}/api/docs/${info.doc_id}`), {data: {markdown:
        had + '\nA line calling a note[^n1].\n\n[^n1]: the document’s own note\n'}});

      const ed = await ctx.newPage();
      watch(ed, 'editor');
      await ed.goto(url(`${S}/doc/${info.doc_id}/edit`));
      await ed.waitForSelector('#src');
      assert(await ed.evaluate(() => document.body.dataset.decksBase) === '/exercises',
             'the editor knows where the decks are');
      await ed.evaluate(() => { const t = document.querySelector('#src');
                                t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
      await ed.locator('summary.btn', {hasText: 'Exercises'}).click();
      await ed.locator('#btn-exercise-deck').click();
      await ed.waitForSelector('.ex-from-deck-modal .dl-item');
      assert(await ed.locator('.ex-from-deck-modal option[value=""]').count() === 0,
             'no "+ New deck…": there is nothing to take out of a deck that does not exist');
      assert((await ed.locator('.ex-from-deck-modal option').allTextContents())
               .every(t => !/Arabic/.test(t)),
             'only the decks of the page’s own language are offered');
      await ed.locator('.ex-from-deck-modal [data-x="deck"]').selectOption(mine.path);
      await ed.waitForFunction(() => [...document.querySelectorAll('.ex-from-deck-modal .dl-item')]
                                      .some(e => /Which cat/.test(e.textContent)));
      assert((await ed.locator('.ex-from-deck-modal .dl-item').allTextContents())
               .join('|') === 'Choose one answerWhich cat?',
             'the deck’s exercises, each headed by what kind it is');
      assert(await ed.locator('.ex-from-deck-modal [data-x="insert"]').isDisabled(),
             'nothing chosen, nothing to insert');
      await ed.locator('.ex-from-deck-modal .dl-item', {hasText: 'Which cat'}).click();
      await ed.locator('.ex-from-deck-modal [data-x="insert"]').click();
      await waitToast(ed, /Exercise inserted/, 'the exercise went in');
      assert(await overlays(ed) === 0, 'and the dialog closed');

      const now = await ed.inputValue('#src');
      assert(/\n:::exercise single-choice\nprompt: Which cat\?\nimage: images\/cat-2\.png\n/.test(now),
             `the block went in naming the picture where it landed:\n${now.slice(now.indexOf(':::exercise single-choice'))}`);
      assert(/- \[x\] this one\[\^n1-2\]/.test(now) && /\[\^n1-2\]: the deck’s own note/.test(now),
             'the note it calls came with it, renamed round the document’s own');
      assert(/\[\^n1\]: the document’s own note/.test(now) && !/n1-3/.test(now),
             'and the document’s own note is untouched');
      const pics = (await (await ctx.request.get(url(`${S}/api/docs/${info.doc_id}/images`))).json()).images;
      assert(pics.length === 2 && pics.some(p => p.name === 'cat-2.png'),
             'the picture is in the document’s own folder, beside the one it did not overwrite');

      // the same exercise twice: the picture is already there, byte for byte
      await ed.locator('summary.btn', {hasText: 'Exercises'}).click();
      await ed.locator('#btn-exercise-deck').click();
      await ed.waitForSelector('.ex-from-deck-modal .dl-item');
      await ed.locator('.ex-from-deck-modal [data-x="deck"]').selectOption(mine.path);
      await ed.waitForFunction(() => [...document.querySelectorAll('.ex-from-deck-modal .dl-item')]
                                      .some(e => /Which cat/.test(e.textContent)));
      await ed.locator('.ex-from-deck-modal .dl-item', {hasText: 'Which cat'}).click();
      await ed.locator('.ex-from-deck-modal [data-x="insert"]').click();
      // THE SECOND BLOCK IS WAITED FOR IN THE TEXT, not in the toast: the toast of the first insertion keeps its words after
      // it has faded (its element is hidden, never emptied), so the same words were "seen" at once, and the checks below
      // looked at a page the copy had not reached -- green on a quiet computer, red on a busy one
      await ed.waitForFunction(() => document.querySelector('#src').value.split('image: images/cat-2.png').length === 3,
                               null, {timeout: 20000}).catch(() => { throw Error(`FAIL (${mode}): the second block was never put in`); });
      assert(true, 'the same exercise a second time went in');
      const twice = (await (await ctx.request.get(url(`${S}/api/docs/${info.doc_id}/images`))).json()).images;
      assert(twice.length === 2, 'the same picture again is the picture already there, not cat-3.png');
      assert((await ed.inputValue('#src')).split('image: images/cat-2.png').length === 3,
             'and the second block names it too');
      await ed.close();
    }

    if (Deno.env.get('SHOTS')) {
      const dir = Deno.env.get('SHOTS');
      await page.goto(url('/exercises/')); await page.waitForSelector('.dk-card');
      await page.screenshot({path: `${dir}/decks-${mode}.png`, fullPage: true});
      await deck.reload(); await deck.waitForSelector('.dk-row');
      await deck.locator('.dk-row').first().locator('.dk-excerpt').click();
      await deck.waitForSelector('.dk-row-preview .exercise');
      await deck.screenshot({path: `${dir}/deck-${mode}.png`, fullPage: true});
      await study.evaluate(() => localStorage.setItem('parseh_theme', 'light'));
      await study.reload(); await study.waitForSelector('#study-stage .exercise');
      await study.screenshot({path: `${dir}/study-${mode}.png`, fullPage: true});
    }
    assert(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
    console.log(`${mode}: ${passed} checks passed\n`);
    return passed;
  } finally {
    await ctx.close();
    try { proc.kill('SIGTERM'); } catch (_) {}
    await proc.status;
  }
}

/* ======================================================================
   e2e: the whole toolbox's server, started the way ./serve.sh starts it
   ====================================================================== */

// serve.py, with the studio's library and the deck store pointed at a
// temporary tree before it serves: serve.py loads the studio, which imports
// the `store` and `decks` this has already imported, and both read their
// root (store.lib() -> store.LIB, decks.DIR) on every call
const BOOT = `
import os, runpy, sys
from pathlib import Path
for p in ("youtube/lib", "lib", "markdown/exlex", "markdown/app"):
    sys.path.insert(0, os.path.join(os.getcwd(), p))
import store, decks, clips, prefs
tmp = Path(sys.argv[1])
store.LIB = tmp / "library"
# the owner's preferences: a deck loads lib/prefs.js since a0.5.0 (the theme follows a person)
prefs.STORE = str(tmp / "config" / "prefs.json")
decks.set_dir(tmp / "exercises")
# every clip tray: an exercise naming a clip looks there, never in clips/
decks.set_clips_dir(tmp / "clips")
store.set_clips_dir(tmp / "clips")
clips.set_dir(tmp / "clips")
sys.argv = ["serve.py", "--http", "--local", sys.argv[2]]
runpy.run_path("serve.py", run_name="__main__")
`;

// three documents: the lesson carries the exercises (a match with a [x]{tl}
// left side, a flashcard, one inside a > box, one with a footnote); the two
// notes are there for the library's language chips
const LESSON = `---
title: Saluti e case
target: it
---

A short lesson[^n1].

:::exercise match-translations
prompt: Match the words.
- [ciao]{tl} => hello
- [x]{tl} => the letter x
:::

:::exercise flashcard
card-type: vocab
target: [casa]{tl}
meaning: house
:::

> Remember this one.
>
> :::exercise true-false
> prompt: Judge the sentences.
> - [Buongiorno]{tl} is said in the morning. => true
> - [Notte]{tl} means day. => false
> :::

:::exercise single-choice
prompt: Pick the greeting[^n2].
- [ ] [tavolo]{tl}
- [x] [salve]{tl}
:::

[^n1]: a note for the page
[^n2]: said to anyone, at any hour
`;
const NOTE_IT = `---
title: Appunti di grammatica
target: it
---

[Essere]{tl} and [avere]{tl}.
`;
const NOTE_FA = `---
title: Persian note
target: fa
---

سلام means hello.
`;

function freePort() {
  const l = Deno.listen({hostname: '127.0.0.1', port: 0});
  const port = l.addr.port;
  l.close();
  return port;
}

/* [[name, compress_type, text], ...] in the zip's own order, read by
   Python's zipfile (the reader Parseh itself uses) */
async function zipEntries(bytes) {
  const code = 'import io, json, sys, zipfile\n'
    + 'z = zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))\n'
    + 'print(json.dumps([[i.filename, i.compress_type, z.read(i).decode("utf-8", "replace")] for i in z.infolist()]))';
  const child = new Deno.Command(python, {args: ['-c', code], stdin: 'piped', stdout: 'piped', stderr: 'piped'}).spawn();
  const w = child.stdin.getWriter();
  await w.write(bytes);
  await w.close();
  const out = await child.output();
  if (!out.success) throw Error('not a readable zip: ' + new TextDecoder().decode(out.stderr));
  return JSON.parse(new TextDecoder().decode(out.stdout));
}

/* names, sizes and mtimes under a directory: the owner's stores must read
   the same after the run as before it */
async function snapshot(dir, depth) {
  const out = [];
  async function walk(d, rel, left) {
    let names;
    try { names = [...Deno.readDirSync(d)].map(e => e.name).sort(); } catch (_) { return; }
    for (const name of names) {
      const st = await Deno.lstat(`${d}/${name}`);
      out.push(`${rel}${name} ${st.isDirectory ? 'dir' : st.size} ${st.mtime ? st.mtime.getTime() : ''}`);
      if (st.isDirectory && left > 1) await walk(`${d}/${name}`, `${rel}${name}/`, left - 1);
    }
  }
  await walk(dir, '', depth);
  return out.join('\n');
}

const exists = p => Deno.lstat(p).then(() => true, () => false);

async function endToEnd(browser) {
  const mode = 'e2e';
  const owner = {exercises: await snapshot(root + '/exercises', 6),
                 library: await snapshot(root + '/markdown/library', 3)};
  const tmp = await Deno.makeTempDir({prefix: 'parseh-decks-e2e-'});
  const port = freePort();
  const proc = new Deno.Command(python, {args: ['-u', '-c', BOOT, tmp, String(port)], cwd: root,
                                         stdout: 'piped', stderr: 'piped'}).spawn();
  let log = '', exited = false;
  const drain = async stream => { for await (const chunk of stream.pipeThrough(new TextDecoderStream())) log += chunk; };
  const drained = Promise.all([drain(proc.stdout), drain(proc.stderr)]);
  proc.status.then(() => { exited = true; });
  const url = p => `http://127.0.0.1:${port}${p}`;
  let passed = 0;
  const assert = (v, m) => { if (!v) throw new Error(`FAIL (${mode}): ` + m); passed++; console.log('  ok', m); };
  const eq = (got, want, m) => assert(JSON.stringify(got) === JSON.stringify(want),
    m + (JSON.stringify(got) === JSON.stringify(want) ? '' : ': got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want)));
  async function http(method, path, body) {
    const r = await fetch(url(path), {method, body: body === undefined ? undefined : JSON.stringify(body),
                                      headers: body === undefined ? {} : {'Content-Type': 'application/json'}});
    const text = await r.text();
    let data = null;
    try { data = JSON.parse(text); } catch (_) { /* not JSON */ }
    return {status: r.status, data, text};
  }

  const ctx = await browser.newContext({viewport: {width: 1280, height: 900}, acceptDownloads: true});
  try {
    const deadline = Date.now() + 60000;
    for (;;) {
      if (exited) throw Error('serve.py exited before answering:\n' + log);
      try {
        const r = await fetch(url('/'));
        await r.arrayBuffer();
        if (r.status === 200) break;
      } catch (_) { /* not listening yet */ }
      if (Date.now() > deadline) throw Error('serve.py did not answer:\n' + log);
      await new Promise(r => setTimeout(r, 250));
    }
    console.log(`end to end: serve.py on port ${port}, stores in ${tmp}`);
    const status = await http('GET', '/studio/api/status');
    assert(status.data.library === `${tmp}/library` && status.data.docs === 0,
           'serve.py serves the temporary studio library (empty)');
    assert(JSON.stringify((await http('GET', '/exercises/api/decks')).data) === '{"ok":true,"decks":[]}',
           '…and the temporary deck store (no decks)');

    // the documents, through the studio's own API
    const made = [];
    for (const markdown of [NOTE_FA, NOTE_IT, LESSON]) {
      const r = await http('POST', '/studio/api/docs', {markdown});
      if (r.status !== 201) throw Error('could not create a document: ' + r.text);
      made.push(r.data.meta);
    }
    const lesson = made[2];
    assert(await exists(`${tmp}/library/italian/${lesson.id}/source.md`) && await exists(`${tmp}/library/persian/${made[0].id}/source.md`),
           'three documents made through POST /studio/api/docs, in the temporary library');

    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
    // a 409 (a duplicate, a deck already here) is an answer the pages expect;
    // Chrome logs it as a failed resource.  So is the hub's /favicon.ico: the
    // hub page (serve.py) links no icon, so Chrome asks for one by itself and
    // nothing in Parseh answers it -- older than the decks, not a page fault.
    // Anything else is.
    page.on('console', m => {
      const at = (m.location() || {}).url || '';
      if (m.type() !== 'error' || /status of 409 \(Conflict\)/.test(m.text())) return;
      if (new URL(at || 'http://x/').pathname === '/favicon.ico') return;
      errors.push(`console on ${page.url()}: ${m.text()} (${at || 'no url'})`);
    });
    page.on('response', r => { if (r.status() >= 400 && r.status() !== 409) errors.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
    const dialogs = [], answers = [];
    page.on('dialog', d => {
      dialogs.push(d.message());
      if (!answers.length) { errors.push(`unexpected dialog: ${d.type()} “${d.message()}”`); d.dismiss(); return; }
      answers.shift() ? d.accept() : d.dismiss();
    });
    const reviews = [];
    page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/review')) reviews.push(JSON.parse(r.postData())); });
    const clearToast = () => page.evaluate(() => { const t = document.querySelector('#toast'); if (t) t.textContent = ''; });
    async function waitToast(re, what) {
      await page.waitForFunction(r => new RegExp(r).test((document.querySelector('#toast') || {}).textContent || ''), re.source, {timeout: 8000})
        .catch(async () => { throw Error(`FAIL (${mode}): toast ${what}: got “${await page.locator('#toast').textContent()}”`); });
      passed++; console.log('  ok toast:', what);
    }
    const deckApi = '/exercises/api/decks/italian/italian-drills';

    /* ---------------- a) the hub ---------------- */
    console.log('a) the hub');
    await page.goto(url('/'));
    const doors = page.locator('.hub .doors > a.door');
    const hrefs = await doors.evaluateAll(ds => ds.map(d => d.getAttribute('href')));
    assert(JSON.stringify(hrefs) === '["/books/","/youtube/","/studio/","/exercises/"]',
           `four doors, Exercises right after Studio (${hrefs.join(' ')})`);
    const boxes = await doors.evaluateAll(ds => ds.map(d => { const r = d.getBoundingClientRect(); return [r.left, r.top, r.right]; }));
    assert(boxes.every(b => Math.abs(b[1] - boxes[0][1]) < 1) && boxes.every((b, i) => !i || b[0] >= boxes[i - 1][2]),
           `the four doors share one row at 1280px (tops ${boxes.map(b => Math.round(b[1])).join(', ')})`);
    const xDoor = doors.nth(3);
    assert(await xDoor.locator('.dname').textContent() === 'Exercises'
           && await xDoor.locator('.dfa').textContent() === 'تمرین‌ها',
           'the door reads تمرین‌ها / Exercises');
    const xTags = await xDoor.locator('.tag').allTextContents();
    assert(xTags[0] === '0 decks' && xTags[1] === '0 due', `its tags on a fresh store: ${xTags.join(', ')}`);
    await Promise.all([page.waitForURL(url('/exercises/')), xDoor.click()]);
    await page.waitForSelector('#decks-empty:not([hidden])');
    assert(await page.locator('.dk-card').count() === 0, 'the door opens /exercises/: no decks yet, the empty state explains');

    /* ---------------- b) "+ Deck" on the document ---------------- */
    console.log('b) "+ Deck" on a studio document');
    await page.goto(url(`/studio/doc/${lesson.id}/edit`));
    await page.waitForFunction(() => document.querySelectorAll('#sheet .exercise').length === 4);
    const editCounts = await page.evaluate(() => ['.exercise', '.ex-edit', '.ex-to-deck']
      .map(s => document.querySelectorAll('#sheet ' + s).length).join());
    assert(editCounts === '4,3,0', `the editor preview: ✎ Edit on the three top-level exercises, no + Deck anywhere (${editCounts})`);

    await page.goto(url(`/studio/doc/${lesson.id}`));
    await page.waitForSelector('#sheet .ex-to-deck');
    const docCounts = await page.evaluate(() => ['.exercise', '.ex-to-deck', '.ex-edit', '.box .exercise .ex-head .ex-to-deck']
      .map(s => document.querySelectorAll('#sheet ' + s).length).join());
    assert(docCounts === '4,4,0,1', `the document page: + Deck on each of the 4 exercises, the boxed one too, no ✎ Edit (${docCounts})`);

    // ↑ Top: a long note is scrolled back to its beginning from the corner,
    // and the button stays out of the way until the page has actually moved
    assert(await page.locator('#btn-top').count() === 1 && await page.locator('#btn-top').isHidden(),
           'the back-to-top button is in the page, and hidden while the page is at the top');
    await page.evaluate(() => { document.querySelector('#sheet').style.minHeight = '3000px'; });
    await page.evaluate(() => window.scrollTo(0, 1500));
    await page.waitForSelector('#btn-top:not([hidden])');
    await page.click('#btn-top');
    await page.waitForFunction(() => window.pageYOffset < 5);
    assert(true, '↑ Top shows itself down a long note and takes the page back to the beginning');
    await page.evaluate(() => { document.querySelector('#sheet').style.minHeight = ''; });
    const exOf = sub => page.locator(`#sheet .exercise[data-subtype="${sub}"]`);
    const modal = '.ex-to-deck-modal';

    // into a NEW deck: there is none yet
    await exOf('match-translations').locator('.ex-to-deck').click();
    await page.waitForSelector(modal);
    const offered0 = await page.locator(`${modal} select option`).evaluateAll(os => os.map(o => o.value));
    assert(offered0.length === 1 && offered0[0] === '' && await page.locator(`${modal} [data-x="new-field"]`).isVisible(),
           'no Italian deck yet: the modal offers “+ New deck…” and asks for a name');
    assert((await page.locator(`${modal} p`).textContent()).includes('your Italian decks'), 'the modal names the page language');
    await page.fill(`${modal} [data-x="name"]`, 'Italian drills');
    await clearToast();
    await page.click(`${modal} [data-x="copy"]`);
    await waitToast(/^Copied into “Italian drills”$/, 'copied into a new deck');
    assert(await page.locator(modal).count() === 0, 'the modal closes');
    const deckFile = JSON.parse(await Deno.readTextFile(`${tmp}/exercises/italian/italian-drills/deck.json`));
    assert(deckFile.name === 'Italian drills' && deckFile.lang === 'it', 'the deck is written to the temporary store, in Italian');
    assert(await exOf('match-translations').locator('.ex-item.picked, .ex-match-drop .ex-item').count() === 0,
           '+ Deck does not touch the exercise it sits on');

    // the boxed one: the deck just made is preselected
    const boxed = page.locator('#sheet .box .exercise');
    const copyBoxed = async () => {
      await boxed.locator('.ex-to-deck').click();
      await page.waitForSelector(`${modal} select option[value="italian/italian-drills"]`, {state: 'attached'});
    };
    await copyBoxed();
    assert(await page.locator(`${modal} select`).inputValue() === 'italian/italian-drills'
           && await page.locator(`${modal} [data-x="new-field"]`).isHidden(), 'the deck used last is preselected, no name asked');
    await clearToast();
    await page.click(`${modal} [data-x="copy"]`);
    await waitToast(/^Copied into “Italian drills”$/, 'the boxed exercise copied');

    // the same one again: asked; declined keeps the modal, accepted copies
    await copyBoxed();
    answers.push(false);
    await page.click(`${modal} [data-x="copy"]`);
    // the question is answered in this process (page.on('dialog')), then the
    // modal's Copy button comes back once the declined attempt has returned
    for (let t = 0; dialogs.length < 1 && t < 160; t++) await page.waitForTimeout(50);
    await page.waitForFunction(() => {
      const b = document.querySelector('.ex-to-deck-modal [data-x="copy"]');
      return b && !b.disabled;
    });
    assert(dialogs.length === 1 && dialogs[0] === 'This exercise is already in “Italian drills” — add it again?',
           `a second copy asks first (“${dialogs[0]}”)`);
    assert(await page.locator(modal).count() === 1
           && (await http('GET', deckApi)).data.items.length === 2, 'declined: nothing copied, the modal stays open');
    answers.push(true);
    await clearToast();
    await page.click(`${modal} [data-x="copy"]`);
    await waitToast(/^Copied into “Italian drills”$/, 'accepted: copied again');
    assert(dialogs.length === 2, 'asked once more, and accepted');

    for (const sub of ['flashcard', 'single-choice']) {
      await exOf(sub).locator('.ex-to-deck').click();
      await page.waitForSelector(`${modal} select option[value="italian/italian-drills"]`, {state: 'attached'});
      await clearToast();
      await page.click(`${modal} [data-x="copy"]`);
      await waitToast(/^Copied into “Italian drills”$/, `the ${sub} copied`);
    }
    let {items} = (await http('GET', deckApi)).data;
    assert(items.map(i => i.subtype).join() === 'match-translations,true-false,true-false,flashcard,single-choice',
           'the deck holds the five copies, in the order copied');
    assert(items.every(i => i.origin.doc_id === lesson.id && i.origin.title === 'Saluti e case' && i.errors.length === 0)
           && items.map(i => i.origin.ordinal).join() === '1,3,3,2,4', 'each remembers its document and ordinal');
    assert(!/^>/m.test(items[1].markdown) && items[1].markdown.startsWith(':::exercise true-false'), 'the boxed exercise is copied without its box');
    assert(items[4].footnotes === '[^n2]: said to anyone, at any hour' && items[0].footnotes === '',
           'the footnoted exercise carries its own note, and only it');
    assert(items[0].markdown.includes('- [x]{tl} => the letter x'), 'the match is copied as written');
    assert((await http('GET', `/studio/api/docs/${lesson.id}`)).data.meta.updated === lesson.updated, 'the document itself is unchanged');
    const [matchId, , , flashId, choiceId] = items.map(i => i.id);

    /* ---------------- c) the decks, browse, manage ---------------- */
    console.log('c) /exercises/: the deck, browse and manage');
    await page.goto(url('/exercises/'));
    await page.waitForSelector('.dk-card');
    const card = page.locator('.dk-card');
    assert(await card.count() === 1 && await card.locator('.dk-card-title').textContent() === 'Italian drills'
           && await card.locator('.badge.lang').textContent() === 'italiano', 'one deck card: its name, its language');
    assert(await card.locator('.dk-total').textContent() === '5 exercises'
           && [await card.locator('.dk-n.dk-new').textContent(), await card.locator('.dk-n.dk-learn').textContent(),
               await card.locator('.dk-n.dk-rev').textContent()].join() === '5,0,0', 'its counts: 5 exercises, 5 new · 0 · 0');
    await Promise.all([page.waitForURL(url('/exercises/deck/italian/italian-drills/')), card.locator('[data-x="browse"]').click()]);
    await page.waitForSelector('.dk-row');
    const rows = page.locator('.dk-row');
    const rowOf = id => page.locator(`.dk-row[data-id="${id}"]`);
    assert(await rows.count() === 5 && await page.locator('#browse-count').textContent() === '5 exercises', 'Browse: a row per exercise');
    const origins = await page.locator('.dk-row .dk-origin a').evaluateAll(as => as.map(a => a.getAttribute('href')));
    assert(origins.length === 5 && origins.every(h => h === `/studio/doc/${lesson.id}`), 'every row links its document under /studio');

    await page.fill('#browse-filter', 'CIAO');
    await page.waitForFunction(() => document.querySelector('#browse-count').textContent === '1 of 5');
    assert(await rows.count() === 1 && await rows.getAttribute('data-id') === matchId, 'the text filter folds case and reads the markdown (1 of 5)');
    await page.fill('#browse-filter', '');
    await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 5);
    await page.selectOption('#browse-type', 'true-false');
    assert(await rows.count() === 2 && await page.locator('#browse-count').textContent() === '2 of 5', 'the type filter (2 of 5)');
    await page.selectOption('#browse-state', 'learning');
    assert(await rows.count() === 0 && await page.locator('#browse-empty [data-x="empty-filter"]').isVisible(),
           'type + state matching nothing say so');
    await page.selectOption('#browse-type', '');
    await page.selectOption('#browse-state', 'new');
    assert(await rows.count() === 5, 'the state filter: all 5 are new');
    await page.selectOption('#browse-state', '');

    await rowOf(matchId).locator('.dk-excerpt').click();
    await rowOf(matchId).locator('.dk-row-preview .sheet.dk-sheet .exercise[data-subtype="match-translations"]').waitFor();
    assert(await rowOf(matchId).locator('.dk-row-preview .ex-match-drop .ex-item').count() === 2
           && await rowOf(matchId).locator('.dk-row-preview .ex-to-deck, .dk-row-preview .ex-edit').count() === 0,
           'the row preview: the exercise solved, without + Deck or ✎ Edit');
    await rowOf(matchId).locator('.dk-row-toggle').click();
    assert(await rowOf(matchId).locator('.dk-row-preview').isHidden(), 'a second click closes it');

    // edit the match through the form: its pairs survive
    await rowOf(matchId).locator('[data-x="edit"]').click();
    await page.waitForSelector('.ex-form-modal');
    await page.waitForFunction(() => /Correct answer shown/.test((document.querySelector('.ex-form-preview-status') || {}).textContent || ''));
    const pairs = await page.locator('.ex-form-modal .ex-field-cols textarea').evaluateAll(xs => xs.map(x => x.value));
    assert(JSON.stringify(pairs) === JSON.stringify(['[ciao]{tl}', 'hello', '[x]{tl}', 'the letter x']),
           `the form opens the match with both pairs, [x]{tl} included (${JSON.stringify(pairs)})`);
    assert(await page.locator('.ex-form-preview .exercise[data-subtype="match-translations"]').count() === 1, 'its preview comes from the deck');
    await page.locator('.ex-form-section', {hasText: 'Instructions'}).locator('textarea').fill('Match them again.');
    const put = page.waitForRequest(r => r.method() === 'PUT' && r.url().endsWith(`/items/${matchId}`));
    await clearToast();
    await page.click('.ex-form-modal [data-x="save"]');
    await put;
    await waitToast(/^Exercise saved$/, 'the edit saved');
    const edited = (await http('GET', `${deckApi}/items/${matchId}`)).data.item;
    assert(edited.markdown.includes('prompt: Match them again.') && edited.markdown.includes('- [ciao]{tl} => hello')
           && edited.markdown.includes('- [x]{tl} => the letter x') && edited.errors.length === 0 && edited.origin.ordinal === 1,
           'stored with the new instructions, both pairs and its origin, still valid');
    await page.waitForFunction(id => (document.querySelector(`.dk-row[data-id="${id}"] .dk-excerpt`) || {}).textContent === 'Match them again.', matchId);
    assert(await page.locator('.ex-form-modal').count() === 0, 'the form closed and the row shows the new instructions');

    // duplicate, then delete the copy
    await clearToast();
    await rowOf(flashId).locator('[data-x="duplicate"]').click();
    await waitToast(/^Duplicated: the copy starts as new$/, 'duplicate');
    await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 6);
    ({items} = (await http('GET', deckApi)).data);
    const dup = items[5];
    assert(dup.subtype === 'flashcard' && dup.markdown === items[3].markdown && dup.id !== flashId
           && dup.origin.duplicate_of === flashId && dup.schedule.state === 'new', 'the duplicate: the same flashcard, a new id, new');
    assert(await rowOf(dup.id).locator('.dk-origin').textContent() === 'from Saluti e case (a duplicate)', 'its row says it is a duplicate');
    await rowOf(dup.id).locator('[data-x="delete"]').click();
    await page.waitForSelector('.dk-modal');
    await clearToast();
    await page.locator('.dk-modal button', {hasText: 'Delete exercise'}).click();
    await waitToast(/^Exercise deleted$/, 'delete');
    await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 5);
    assert(!(await exists(`${tmp}/exercises/italian/italian-drills/items/${dup.id}.json`)), 'the deleted exercise is gone from the store');

    // add through the picker and the form
    await page.click('#btn-add-exercise');
    await page.locator('.ex-type', {hasText: 'Yes / No questions'}).click();
    await page.waitForSelector('.ex-form-modal');
    assert(await page.locator('.ex-form-modal [data-x="save"]').textContent() === 'Add to deck', 'the picker opens the form: “Add to deck”');
    await page.locator('.ex-form-row textarea').first().fill('Is [pane]{tl} bread?');
    await page.waitForFunction(() => /Correct answer shown/.test((document.querySelector('.ex-form-preview-status') || {}).textContent || '')
                                    && /pane/.test((document.querySelector('.ex-form-preview') || {}).textContent || ''));
    const posted = page.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/italian-drills/items'));
    await clearToast();
    await page.click('.ex-form-modal [data-x="save"]');
    await posted;
    await waitToast(/^Added to “Italian drills”$/, 'added');
    await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 6);
    ({items} = (await http('GET', deckApi)).data);
    const yesNo = items[5];
    assert(yesNo.subtype === 'yes-no' && yesNo.markdown.includes('Is [pane]{tl} bread?') && yesNo.origin === null && yesNo.errors.length === 0,
           'a new row: the yes/no exercise, written here');
    assert(await rowOf(yesNo.id).locator('.dk-origin').textContent() === 'written here', 'its row says it was written here');

    /* ---------------- d) study ---------------- */
    console.log('d) study');
    await Promise.all([page.waitForURL(url('/exercises/deck/italian/italian-drills/study')), page.click('#btn-study')]);
    await page.waitForSelector('#study-stage .exercise');
    const subtype = () => page.locator('#study-stage .exercise').getAttribute('data-subtype');
    const barShown = () => page.waitForSelector('#rating-bar:not([hidden])');
    async function rateBy(action) {
      const n = reviews.length;
      const answered = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/review'));
      await action();
      await answered;
      await page.waitForFunction(() => document.querySelector('#rating-bar').hidden);
      return reviews[n];
    }
    assert(await subtype() === 'match-translations' && await page.locator('#study-counts .dk-n.dk-new').textContent() === '6',
           'study opens on the first exercise copied, 6 new');
    assert(await page.locator('#btn-check').isVisible() && await page.locator('#btn-show').isHidden()
           && await page.locator('#rating-bar').isHidden(), 'a scored exercise: Check, no rating bar yet');
    // wrongly: each word into the other's row
    const drops = page.locator('#study-stage .ex-match-drop');
    const wants = await drops.evaluateAll(ds => ds.map(d => d.dataset.answer));
    for (let i = 0; i < wants.length; i++) {
      await page.locator(`#study-stage .ex-item[data-item="${wants[(i + 1) % wants.length]}"]`).click();
      await drops.nth(i).click();
    }
    assert(await page.locator('#study-stage .ex-match-drop .ex-item').count() === 2, 'both words placed, each in the wrong row');
    await page.click('#btn-check');
    await barShown();
    assert(await page.locator('#study-result').textContent() === 'Not quite', 'Check: “Not quite”');
    const ivls = await page.locator('#rating-bar .dk-ivl').allTextContents();
    assert(ivls[0] === '1m' && ivls[1] === '6m' && ivls[2] === '10m' && /^[345]d$/.test(ivls[3]),
           `the rating bar carries the intervals: ${ivls.join(' · ')}`);
    assert(await page.evaluate(() => document.activeElement.dataset.rating) === 'again', 'Again has the focus after a wrong answer');
    // the match is locked as answered, so its right answer is shown beneath
    await page.waitForSelector('#study-solution:not([hidden]) .exercise[data-subtype="match-translations"]');
    const solvedRows = await page.locator('#study-solution .ex-match-drop').evaluateAll(ds => ds.map(d => {
      const item = d.querySelector('.ex-item');
      return !!item && item.dataset.item === d.dataset.answer;
    }));
    assert(await page.locator('#study-solution .dk-solution-head').textContent() === 'Correct answer'
           && solvedRows.length === 2 && solvedRows.every(Boolean)
           && await page.locator('#study-stage .ex-match-drop.answer-wrong').count() === 2,
           'under “Not quite”, the correct answer: each word in its row, the answer given still marked wrong');
    let r = await rateBy(() => page.click('#rating-bar [data-rating="again"]'));
    assert(r.item === matchId && r.rating === 'again' && r.result === false, 'Again saved: {item, rating: again, result: false}');
    assert(await subtype() === 'true-false' && await page.locator('#rating-bar').isHidden() && await page.locator('#btn-check').isVisible()
           && await page.locator('#study-solution').isHidden(), 'the next card, without the bar or the solution');

    // the boxed true-false, right: Enter checks, key 3 rates Good
    for (const g of await page.locator('#study-stage .ex-choice-group').all()) await g.locator('.ex-option[data-correct="1"]').click();
    await page.keyboard.press('Enter');
    await barShown();
    assert(await page.locator('#study-result').textContent() === 'Correct', 'Enter checks: “Correct”');
    r = await rateBy(() => page.keyboard.press('3'));
    assert(r.rating === 'good' && r.result === true, 'key 3: Good');
    // its copy, wrong: key 2 rates Hard
    for (const g of await page.locator('#study-stage .ex-choice-group').all()) await g.locator('.ex-option[data-correct="0"]').click();
    await page.keyboard.press('Enter');
    await barShown();
    r = await rateBy(() => page.keyboard.press('2'));
    assert(r.rating === 'hard' && r.result === false, 'key 2: Hard');

    // the flashcard: Show, then Good
    await page.waitForSelector('#btn-show:not([hidden])');
    assert(await subtype() === 'flashcard' && await page.locator('#btn-check').isHidden(), 'a flashcard: Show answer, no Check');
    await page.click('#btn-show');
    await barShown();
    assert(await page.locator('#study-stage .ex-flashcard').evaluate(c => c.classList.contains('flipped')), 'Show answer turns the card');
    r = await rateBy(() => page.click('#rating-bar [data-rating="good"]'));
    assert(r.item === flashId && r.rating === 'good' && r.result === null, 'Good on a flashcard: result null');

    // the footnoted one: its note is on the card; key 4 rates Easy
    assert(await subtype() === 'single-choice' && await page.locator('#study-stage .fnref').count() === 1
           && (await page.locator('#study-stage .fncloud').textContent()).includes('said to anyone'), 'the copied footnote shows on the card');
    // from the keyboard alone: Shift+Tab from Check to the right answer and
    // Enter chooses it (nothing is checked); Enter on Check then checks
    assert(await page.evaluate(() => document.activeElement.id) === 'btn-check', 'Check has the focus');
    const onRight = () => page.evaluate(() => document.activeElement.matches('#study-stage .ex-option[data-correct="1"]'));
    for (let i = 0; i < 6 && !(await onRight()); i++) await page.keyboard.press('Shift+Tab');
    assert(await onRight(), 'Shift+Tab reaches the right answer');
    await page.keyboard.press('Enter');
    assert(await page.locator('#study-stage .ex-option[data-correct="1"]').evaluate(o => o.classList.contains('selected'))
           && await page.locator('#rating-bar').isHidden() && await page.locator('#study-result').isHidden()
           && !(await page.locator('#study-stage .ex-body').evaluate(b => b.inert)),
           'Tab then Enter chooses the answer, and checks nothing');
    await page.locator('#btn-check').focus();
    await page.keyboard.press('Enter');
    await barShown();
    assert(await page.locator('#study-result').textContent() === 'Correct', 'Enter on Check checks it: “Correct”');
    r = await rateBy(() => page.keyboard.press('4'));
    assert(r.item === choiceId && r.rating === 'easy' && r.result === true, 'key 4: Easy');
    // the one written here, wrong: key 1 rates Again
    assert(await subtype() === 'yes-no', 'the exercise added in the deck comes last among the new');
    await page.locator('#study-stage .ex-option[data-correct="0"]').first().click();
    await page.keyboard.press('Enter');
    await barShown();
    r = await rateBy(() => page.keyboard.press('1'));
    assert(r.item === yesNo.id && r.rating === 'again' && r.result === false, 'key 1: Again');

    // what is still learning comes back (learn-ahead): Easy until done
    let rounds = 0;
    while (await page.locator('#study-done').isHidden()) {
      if (++rounds > 12) throw Error(`FAIL (${mode}): the session does not end`);
      await page.keyboard.press('Enter');         // Check, or Show answer
      await barShown();
      await rateBy(() => page.keyboard.press('4'));
    }
    assert(rounds === 5 && reviews.slice(6).every(x => x.rating === 'easy'), `the 5 exercises still learning came back and graduated (${rounds} rounds)`);
    assert(await page.locator('#study-done h2').textContent() === 'Nothing more to study now'
           && await page.locator('#study-stage').isHidden(), 'done: “Nothing more to study now”');
    const nextDue = await page.locator('#study-next-due').textContent();
    assert(/^next exercise (in [345]d|tomorrow)$/.test(nextDue), `with the next due: “${nextDue}”`);
    assert((await page.locator('#study-counts .dk-n').allTextContents()).join() === '0,0,0', 'counts: 0 · 0 · 0');
    ({items} = (await http('GET', deckApi)).data);
    assert(items.every(i => i.schedule.state === 'review') && items.find(i => i.id === matchId).lapses === 0
           && items.find(i => i.id === matchId).reps === 2, 'the store agrees: every exercise in review, the match answered twice');

    /* ---------------- e) export and import ---------------- */
    console.log('e) export, with and without scheduling, and import');
    await page.goto(url('/exercises/deck/italian/italian-drills/'));
    await page.waitForSelector('.dk-row');
    async function exportVia(id) {
      await page.locator('.dk-deckactions details.dropdown summary').click();
      const [dl] = await Promise.all([page.waitForEvent('download'), page.click(id)]);
      return {name: dl.suggestedFilename(), bytes: await Deno.readFile(await dl.path())};
    }
    const ids = items.map(i => i.id).sort();
    const withSched = await exportVia('#btn-export-sched');
    let entries = await zipEntries(withSched.bytes);
    let byName = Object.fromEntries(entries.map(([n, , t]) => [n, t]));
    assert(withSched.name === 'exercises-italian-drills-with-scheduling.zip', `with scheduling: ${withSched.name}`);
    assert(JSON.stringify(Object.keys(byName).sort()) === JSON.stringify(
             ['parseh-exercise-deck.json', ...ids.map(i => `items/${i}.json`), ...ids.map(i => `schedule/${i}.json`)].sort()),
           'its entries: the manifest, 6 exercises, 6 schedules, nothing else');
    let manifest = JSON.parse(byName['parseh-exercise-deck.json']);
    assert(manifest.format === 'parseh-exercise-deck/2' && manifest.scheduling === true && manifest.deck.name === 'Italian drills'
           && manifest.deck.lang === 'it' && manifest.deck.id === deckFile.id, 'the manifest says so (format, scheduling, the deck)');
    const matchSched = JSON.parse(byName[`schedule/${matchId}.json`]);
    assert(matchSched.state.state === 'review' && matchSched.history.map(h => h.rating).join() === 'again,easy', 'a schedule: state and history');
    assert(JSON.parse(byName[`items/${matchId}.json`]).markdown === edited.markdown, 'an exercise: its markdown as edited');

    const plain = await exportVia('#btn-export-plain');
    entries = await zipEntries(plain.bytes);
    byName = Object.fromEntries(entries.map(([n, , t]) => [n, t]));
    assert(plain.name === 'exercises-italian-drills.zip', `without scheduling: ${plain.name}`);
    assert(JSON.stringify(Object.keys(byName).sort()) === JSON.stringify(['parseh-exercise-deck.json', ...ids.map(i => `items/${i}.json`)].sort()),
           'its entries: the manifest and the 6 exercises, no schedule');
    assert(JSON.parse(byName['parseh-exercise-deck.json']).scheduling === false, 'the manifest says without scheduling');

    await page.goto(url('/exercises/'));
    await page.waitForSelector('.dk-card');
    async function importBack(file, keep, toastRe, what) {
      await page.setInputFiles('#file-import', {name: file.name, mimeType: 'application/zip', buffer: Buffer.from(file.bytes)});
      await page.waitForSelector('.dk-modal input[type=checkbox]');
      assert(await page.locator('.dk-modal input[type=checkbox]').isChecked(), `${what}: “Keep the scheduling saved in the file” starts ticked`);
      if (!keep) await page.locator('.dk-modal input[type=checkbox]').uncheck();
      await page.locator('.dk-modal button', {hasText: /^Import$/}).click();
      await page.waitForSelector('.dk-modal h3:text("This deck is already here")');
      assert((await page.locator('.dk-modal p').textContent()).includes('Italian drills'), `${what}: the conflict names the deck already here`);
      const again = page.waitForRequest(q => q.url().includes('/exercises/api/import') && q.url().includes('mode=copy'));
      await clearToast();
      await page.locator('.dk-modal button', {hasText: 'Import as a copy'}).click();
      const sent = new URL((await again).url());
      assert(sent.pathname.endsWith('/exercises/api/import') && sent.searchParams.get('mode') === 'copy'
             && sent.searchParams.get('scheduling') === String(keep ? 1 : 0), `${what}: sent again as a copy`);
      await waitToast(toastRe, what);
    }
    await importBack(withSched, true, /^Imported “Italian drills \(copy\)”: 6 exercises, with its scheduling$/, 'imported with scheduling');
    await page.waitForFunction(() => document.querySelectorAll('.dk-card').length === 2);
    await importBack(plain, false, /^Imported “Italian drills \(copy\)”: 6 exercises, all new$/, 'imported without');
    await page.waitForFunction(() => document.querySelectorAll('.dk-card').length === 3);
    const decksNow = (await http('GET', '/exercises/api/decks?lang=it')).data.decks;
    const copies = decksNow.filter(d => d.name === 'Italian drills (copy)').sort((a, b) => a.created.localeCompare(b.created));
    assert(copies.length === 2 && copies.every(d => d.id !== deckFile.id && d.counts.total === 6), 'two copies, new ids, 6 exercises each');
    assert(copies[0].counts.review === 6 && copies[0].study.new === 0 && copies[1].counts.new === 6 && copies[1].study.new === 6,
           'the first kept its scheduling, the second starts new');
    const kept = page.locator(`.dk-card[data-path="${copies[0].path}"]`), fresh = page.locator(`.dk-card[data-path="${copies[1].path}"]`);
    assert(await kept.locator('.dk-total').textContent() === '6 exercises' && (await kept.locator('[data-x="study"]').getAttribute('class')).includes('dk-off')
           && /^next exercise (in [345]d|tomorrow)$/.test(await kept.locator('.dk-next').textContent()),
           'its card: 6 exercises, nothing to study now, the next due');
    assert(await fresh.locator('.dk-n.dk-new').textContent() === '6' && !(await fresh.locator('[data-x="study"]').getAttribute('class')).includes('dk-off'),
           'the other card: 6 new to study');

    await page.goto(url('/'));
    const deckTags = () => page.locator('.hub .doors > a.door').nth(3).locator('.tag').allTextContents();
    const tagsNow = await deckTags();
    assert(tagsNow.join(', ') === '3 decks, 6 due', `the hub's door counts them, and counts nothing else: ${tagsNow.join(', ')}`);
    // the count follows the chips: one tag per door saying what the picked
    // language has, in place of a grey tag per language beside it
    const saysDecks = (t) => page.waitForFunction(
      want => document.querySelectorAll('.hub .doors > a.door')[3].querySelector('.tag').textContent === want, t);
    await page.click('.parseh-langs .chip[data-pick="fa"]');
    await saysDecks('0 decks');
    assert((await deckTags()).join(', ') === '0 decks, 0 due', 'pick Persian and it says Persian has no deck');
    await page.click('.parseh-langs .chip[data-pick="it"]');
    await saysDecks('3 decks');
    assert((await deckTags()).join(', ') === '3 decks, 6 due', 'pick Italian and it says the three Italian decks, six due');
    await page.click('.parseh-langs .chip[data-pick="all"]');
    await saysDecks('3 decks');

    /* ---------------- f) the studio library: download the shown ---------------- */
    console.log('f) the studio library: “Download N shown”');
    await page.goto(url('/studio/'));
    await page.waitForFunction(() => document.querySelectorAll('#cards .card').length === 3);
    // a <summary> takes no disabled attribute: with nothing shown the menu is
    // shut and made unclickable instead
    const dlShows = (label, off = false) => page.waitForFunction(([l, d]) => {
      const b = document.querySelector('#btn-download-shown');
      const box = document.querySelector('#download-shown');
      return b && b.textContent === l && !!box && box.classList.contains('disabled') === d;
    }, [label, off]);
    await dlShows('Download 3 shown');
    assert(await page.locator('#btn-download-shown').getAttribute('title') === 'Download the 3 documents shown',
           '“Download 3 shown”, its title naming the count');
    await page.click('.parseh-langs .chip[data-pick="fa"]');
    await dlShows('Download 1 shown');
    assert(await page.locator('#btn-download-shown').getAttribute('title') === 'Download the 1 document shown',
           'the Persian chip: “Download 1 shown”');
    await page.click('.parseh-langs .chip[data-pick="it"]');
    await dlShows('Download 2 shown');
    assert(true, 'the Italian chip: “Download 2 shown”');
    const shownIds = await page.locator('#cards .card:not([hidden])').evaluateAll(cs => cs.map(c => c.dataset.id));
    // the .md shape, from the menu the button now opens
    await page.click('#btn-download-shown');
    const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#dl-shown-md')]);
    assert(/^studio-2-documents-\d{8}-\d{4}\.zip$/.test(dl.suggestedFilename()), `the zip: ${dl.suggestedFilename()}`);
    entries = await zipEntries(await Deno.readFile(await dl.path()));
    const wantNames = shownIds.map(id => id.replace(/-[0-9a-f]{6}$/, '') + '.md');
    assert(shownIds.length === 2 && shownIds.includes(lesson.id) && !shownIds.includes(made[0].id)
           && JSON.stringify(entries.map(e => e[0])) === JSON.stringify(wantNames),
           `exactly the shown .md files, in the order shown (${entries.map(e => e[0]).join(', ')})`);
    for (const [i, id] of shownIds.entries()) {
      const src = (await http('GET', `/studio/api/docs/${id}`)).data.markdown;
      assert(entries[i][2] === src && entries[i][1] === 8, `${entries[i][0]} is the document's source, deflated`);
    }
    // ...and the same two with their pictures and recordings: each document's own zip in one
    await page.click('#btn-download-shown');
    assert(await page.locator('#dl-shown-zip').textContent() === 'Markdown + media (.zip)',
           'the menu names the zip of zips by what it carries: “Markdown + media (.zip)”');
    const [dlz] = await Promise.all([page.waitForEvent('download'), page.click('#dl-shown-zip')]);
    assert(/^studio-2-documents-with-media-\d{8}-\d{4}\.zip$/.test(dlz.suggestedFilename()),
           `the zip of zips: ${dlz.suggestedFilename()}`);
    const outer = await zipEntries(await Deno.readFile(await dlz.path()));
    assert(JSON.stringify(outer.map(e => e[0]))
           === JSON.stringify(shownIds.map(id => id.replace(/-[0-9a-f]{6}$/, '') + '.zip')),
           `each document's own zip inside (${outer.map(e => e[0]).join(', ')})`);
    assert(outer.every(e => e[1] === 0), 'stored, not squeezed a second time');
    await page.click('.parseh-langs .chip[data-pick="all"]');
    await dlShows('Download 3 shown');
    assert(await page.locator('#cards .card').count() === 3, 'the page stayed; “all” shows the three again');

    // one button clears every filter: the search, the tags and the chip
    assert(await page.locator('#btn-clear-filters').isHidden(), 'nothing filtering: no clear button');
    await page.click('.parseh-langs .chip[data-pick="fa"]');
    await page.waitForSelector('#btn-clear-filters:not([hidden])');
    assert(true, 'a language picked: “Clear all filters” appears');
    await page.click('#btn-clear-filters');
    await page.waitForSelector('#btn-clear-filters', {state: 'hidden'});
    await dlShows('Download 3 shown');
    assert(await page.evaluate(() => localStorage.getItem('parseh_lang')) === 'all',
           'it clears the language chip too, and the three are shown again');
    assert(await page.locator('#btn-restore').count() === 1
           && await page.locator('#backup-file').count() === 1,
           'and the library offers “Load from backup” beside Backup');

    // the sort menu is not a filter: it is remembered, and opening the page
    // again must not quietly put the list back in another order
    await page.selectOption('#sort', 'title');
    await page.waitForFunction(() => localStorage.getItem('parseh_studio_sort') === 'title');
    await page.goto(url('/studio/'));
    await page.waitForFunction(() => document.querySelectorAll('#cards .card').length === 3);
    assert(await page.locator('#sort').inputValue() === 'title',
           'the sort menu comes back on what it was left on');
    await page.selectOption('#sort', 'updated');

    // Opening a document and using its Library button keeps this tab's
    // search, text-search switch and both kinds of tag filter.
    assert((await http('PATCH', `/studio/api/docs/${lesson.id}/meta`, {tags: ['review']})).status === 200,
           'the lesson has a tag to filter by');
    assert((await http('PATCH', `/studio/api/docs/${made[1].id}/meta`, {tags: ['reference']})).status === 200,
           'another document has a tag to exclude');
    await page.goto(url('/studio/'));
    await page.waitForSelector('#tagbar .tagchip');
    await page.locator('#tagbar .tagchip', {hasText: 'reference'}).click({modifiers: ['Shift']});
    await page.locator('#tagbar .tagchip', {hasText: 'review'}).click();
    await page.fill('#search', 'Saluti');
    await page.check('#intext');
    await page.click('.parseh-langs .chip[data-pick="it"]');
    await page.selectOption('#sort', 'title');
    await page.waitForFunction(id => {
      const shown = [...document.querySelectorAll('#cards .card:not([hidden])')];
      return shown.length === 1 && shown[0].dataset.id === id;
    }, lesson.id);
    await Promise.all([page.waitForURL(url(`/studio/doc/${lesson.id}`)),
                       page.click('#cards .card:not([hidden])')]);
    await Promise.all([page.waitForURL(url('/studio/')),
                       page.locator('.topbar a.btn.ghost', {hasText: 'Library'}).click()]);
    await page.waitForFunction(id => {
      const shown = [...document.querySelectorAll('#cards .card:not([hidden])')];
      return shown.length === 1 && shown[0].dataset.id === id;
    }, lesson.id);
    assert(await page.locator('#search').inputValue() === 'Saluti'
           && await page.locator('#intext').isChecked()
           && await page.locator('#sort').inputValue() === 'title'
           && await page.locator('.parseh-langs .chip.on').getAttribute('data-pick') === 'it'
           && await page.locator('#tagbar .tagchip.active').count() === 1
           && await page.locator('#tagbar .tagchip.excluded').count() === 1,
           'Library returns to the same search, text mode, sort, language and tag filters');
    await page.click('#btn-clear-filters');
    await page.waitForFunction(() => document.querySelectorAll('#cards .card:not([hidden])').length === 3);
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('#cards .card:not([hidden])').length === 3);
    assert(await page.locator('#search').inputValue() === '' && !(await page.locator('#intext').isChecked())
           && await page.locator('#tagbar .tagchip.active, #tagbar .tagchip.excluded').count() === 0,
           'Clear all filters stays cleared after another library load');
    await page.selectOption('#sort', 'updated');

    /* ---------------- g) a picture uploaded from the flashcard form, on the study card ---------------- */
    console.log('g) a picture uploaded from the form shows on the study card');
    const picDeck = (await http('POST', '/exercises/api/decks', {name: 'Pictures', lang: 'it'})).data.deck;
    await page.goto(url(`/exercises/deck/${picDeck.path}/`));
    await page.waitForSelector('#browse-empty:not([hidden])');
    await page.click('#btn-add-exercise');
    await page.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
    await page.waitForSelector('.ex-form-modal');
    const formField = label => page.locator(`.ex-form-modal .ex-author-field:has(> span:text-is("${label}"))`);
    await formField('Word or expression').locator('textarea').fill('[gatto]{tl}');
    await formField('Meaning').locator('textarea').fill('cat');
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'),
                                         page.locator('.ex-form-modal .ex-upload').first().click()]);
    await chooser.setFiles({name: 'Gatto.png', mimeType: 'image/png', buffer: PNG_A});
    const picSrc = `/exercises/media/${picDeck.path}/images/gatto.png`;
    const shows = where => page.waitForFunction(([w, src]) => {
      const img = document.querySelector(`${w} img.ex-card-image`);
      return !!img && img.getAttribute('src') === src && img.complete && img.naturalWidth > 0;
    }, [where, picSrc], {timeout: 8000}).then(() => true, () => false);
    // the upload is on its way: the field is filled in when it has been stored
    const frontPath = formField('Front image path').locator('input[type="text"]');
    await frontPath.evaluate(i => new Promise(done => {
      const t0 = Date.now();
      (function poll() { if (i.value === 'images/gatto.png' || Date.now() - t0 > 8000) done(); else setTimeout(poll, 50); })();
    }));
    assert(await frontPath.inputValue() === 'images/gatto.png' && await shows('.ex-form-preview'),
           `Upload… fills in images/gatto.png (“${await frontPath.inputValue()}”), and the preview shows the picture`);
    await clearToast();
    await page.click('.ex-form-modal [data-x="save"]');
    await waitToast(/^Added to “Pictures”$/, 'the flashcard added with its picture');
    assert(await exists(`${tmp}/exercises/${picDeck.path}/images/gatto.png`), 'the picture is in the deck, in the temporary store');
    await page.waitForSelector('.dk-row');
    await Promise.all([page.waitForURL(url(`/exercises/deck/${picDeck.path}/study`)), page.click('#btn-study')]);
    await page.waitForSelector('#study-stage .exercise[data-primitive="flashcard"]');
    assert(await shows('#study-stage .ex-card-front'), 'the study card shows the picture');
    // ⤢ Enlarge: the picture card large over the study page -- the same card,
    // only bigger: its picture magnified exactly as much as the card around it
    // -- and turning it there shows the answer
    const onPage = await page.locator('#study-stage .ex-card-front img.ex-card-image').boundingBox();
    const cardOnPage = await page.locator('#study-stage .ex-flashcard').boundingBox();
    await page.click('#study-stage .ex-card-zoom');
    assert(await shows('.ex-zoom-modal .ex-card-front'), 'the enlarged card shows the picture');
    const enlarged = await page.locator('.ex-zoom-modal .ex-card-front img.ex-card-image').boundingBox();
    const cardEnlarged = await page.locator('.ex-zoom-modal .ex-flashcard').boundingBox();
    const times = cardEnlarged.width / cardOnPage.width;
    assert(onPage && enlarged && times >= 1.5
           && Math.abs(enlarged.height / onPage.height - times) < 0.02 * times
           && Math.abs(enlarged.width / onPage.width - times) < 0.02 * times,
           `the picture is enlarged with its card (${Math.round(onPage.width)}x${Math.round(onPage.height)}px ` +
           `on the page, ${enlarged.width.toFixed(1)}x${enlarged.height.toFixed(1)}px enlarged, the card ${times.toFixed(2)} times its size)`);
    assert(await page.locator('#btn-show').isVisible(), 'the answer is not shown yet');
    await page.click('.ex-zoom-modal .ex-flashcard');
    assert(await page.waitForFunction(() => document.querySelector('#btn-show').hidden, null, {timeout: 5000})
             .then(() => true, () => false)
           && await page.locator('#study-stage .ex-flashcard.flipped').count() === 1,
           'turning the enlarged card turns the study card, and counts as the answer shown');
    await page.keyboard.press('Escape');
    assert(await page.waitForFunction(() => !document.querySelector('.ex-zoom-overlay'), null, {timeout: 5000})
             .then(() => true, () => false), 'Escape closes the enlarged card');

    /* ---------------- h) recordings, from the form to the study card and back ---------------- */
    console.log('h) recordings uploaded from the form, played on the study card, exported and imported');
    await recordingsFlow({page, request: ctx.request, url, assert, zip: zipEntries, refusal: false,
                          toast: (_page, re, what) => waitToast(re, what)});
    console.log("i) a jolly card's recording lines, played on the study card as Anki plays them");
    await jollyRecordingsFlow({page, request: ctx.request, url, assert, toast: (_page, re, what) => waitToast(re, what)});
    console.log('j) a clip past the end of its recording, and a window left open while an answer was saved');
    await studyEdgesFlow({page, request: ctx.request, url, assert, toast: (_page, re, what) => waitToast(re, what)});
    console.log('j2) a both-repeat card is two linked cards: badge, the question on edit and delete, buried on study');
    await linkedCardsFlow({page, browser, request: ctx.request, url, assert, studio: '/studio', tmp, mode,
                           toast: (_page, re, what) => waitToast(re, what)});

    /* ---------------- k) a card copied as markdown, pasted into Add exercise ---------------- */
    console.log('k) a card copied as markdown on a card sheet, pasted into the deck’s Add exercise');
    if (!MEDIA.ok) console.log('  (left out: ffmpeg could not write the tones here)');
    else {
      await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: url('')});
      const clip = (await (await fetch(url('/clips/api/upload?kind=audio&hint=wound&lang=en&text=wound'), {method: 'POST', body: MEDIA.c})).json()).clip;
      assert(await exists(`${tmp}/clips/${clip.name}`), `a clip cut on a card sheet waits in the tray (${clip.name})`);
      const clock = (await http('POST', '/exercises/api/decks', {name: 'Clock deck', lang: 'en'})).data.deck;
      await page.goto(url(`/exercises/deck/${clock.path}/`));
      await page.waitForSelector('#browse-empty:not([hidden])');
      // the markdown the sheets copy, made by the card kit they use
      await page.addScriptTag({url: '/lib/cardkit.js'});
      const cards = await page.evaluate(path => ({
        jolly: ParsehCards.markdown({latin: true, jolly: {
          'front-primary': '[wound]{tl}\n![](' + path + ')', 'front-secondary': 'waʊnd',
          'back-primary': '| tense | form |\n|---|---|\n| past | wound |', 'back-secondary': 'wound the clock'}}, 'jolly'),
        vocab: ParsehCards.markdown({latin: true, fa: 'wound', en: 'past of wind', dir: 'both-random',
                                     audio: {side: 'front', path}}, 'vocab')}), clip.path);
      assert(cards.jolly.includes(`  ![](${clip.path})\n`) && cards.vocab.includes(`front-audio: ${clip.path}\n`) && cards.vocab.includes('direction: both-random\n'),
             'the card kit writes a jolly card with the clip in a field, and a vocabulary card that draws its first side, with the clip as its front recording');
      const writeClipboard = text => page.evaluate(t => navigator.clipboard.writeText(t), text);
      const form = () => page.evaluate(() => ({
        title: document.querySelector('.ex-form-modal h3').textContent,
        save: document.querySelector('.ex-form-modal [data-x="save"]').textContent,
        jolly: [...document.querySelectorAll('.ex-form-modal textarea.ex-jolly-text')].map(x => x.value)}));

      // Add exercise… → Paste markdown… → Ctrl+V → Open in the form → Add to deck
      await writeClipboard('Copied from the reader:\n\n' + cards.jolly + '\n(end)\n');
      await page.click('#btn-add-exercise');
      await page.waitForSelector('.ex-picker .ex-type-grid');
      assert(await page.locator('.ex-picker button[data-x="paste"]').textContent() === 'Paste markdown…',
             'the deck’s Add exercise… offers Paste markdown…, beside the exercise types');
      await page.click('.ex-picker [data-x="paste"]');
      assert(await page.evaluate(() => document.activeElement.matches('.ex-picker textarea.ex-paste')), 'Paste markdown… opens a box to paste into, with the focus');
      await page.click('.ex-picker .ex-text-direction');
      assert(await page.locator('.ex-picker textarea.ex-paste').getAttribute('dir') === 'rtl',
             'the paste box can be edited right to left');
      await page.click('.ex-picker .ex-text-direction');
      assert(await page.locator('.ex-picker textarea.ex-paste').getAttribute('dir') === 'ltr',
             'the paste box can switch back to left to right');
      await page.keyboard.press('Control+V');
      await page.click('.ex-picker [data-x="open"]');
      await page.waitForSelector('.ex-form-modal');
      let shown = await form();
      assert(JSON.stringify(shown) === JSON.stringify({title: 'Add Embedded Jolly flashcard', save: 'Add to deck',
               jolly: ['[wound]{tl}\n![](' + clip.path + ')', 'waʊnd', '| tense | form |\n|---|---|\n| past | wound |', 'wound the clock']}),
             'Open in the form: a new jolly card, the words around the block left out, every field as copied ' + JSON.stringify(shown));
      const previewPlays = await page.waitForFunction(() => {
        const a = document.querySelector('.ex-form-preview .ex-card-front figure.audio audio');
        return !!a && a.readyState >= 1 && !!document.querySelector('.ex-form-preview .ex-card-back table');
      }, null, {timeout: 8000}).then(() => true, () => false);
      assert(previewPlays, 'the form’s preview draws the card, its table, and a player that loads the clip still in the tray');
      await clearToast();
      await page.click('.ex-form-modal [data-x="save"]');
      await waitToast(/^Added to “Clock deck”$/, 'the pasted jolly card added, with no warning');
      let items = (await http('GET', `/exercises/api/decks/${clock.path}`)).data.items;
      assert(items.length === 1 && items[0].markdown === cards.jolly.trim(), 'the deck holds the card as it was copied ' + JSON.stringify(items.map(i => i.markdown)));
      const inDeck = `${tmp}/exercises/${clock.path}/audio/${clip.name}`;
      assert(await exists(inDeck) && (await Deno.readFile(inDeck)).length === (await Deno.readFile(`${tmp}/clips/${clip.name}`)).length,
             'the recording came along from the clip tray into the deck, and the tray keeps it');

      // Ctrl+V straight on the types: the form opens at once
      await writeClipboard(cards.vocab);
      await page.click('#btn-add-exercise');
      await page.waitForSelector('.ex-picker .ex-type-grid');
      await page.keyboard.press('Control+V');
      await page.waitForSelector('.ex-form-modal');
      shown = await form();
      const frontAudio = await page.locator('.ex-form-modal .ex-author-field:has(> span:text-is("Front recording path")) input:not([type=file])').inputValue();
      assert(shown.title === 'Add Embedded vocabulary flashcard' && frontAudio === clip.path,
             `Ctrl+V on the exercise types opens the pasted vocabulary card in the form, its recording in its field (${frontAudio})`);
      await clearToast();
      await page.click('.ex-form-modal [data-x="save"]');
      await waitToast(/^Added to “Clock deck”$/, 'the pasted vocabulary card added');
      items = (await http('GET', `/exercises/api/decks/${clock.path}`)).data.items;
      assert(items.length === 2 && items.some(i => i.markdown === cards.vocab.trim()),
             'saved through the form it is the card as copied, its first side drawn (both (random)) and all ' + JSON.stringify(items.map(i => i.markdown)));

      // what is not one exercise is said, and the box keeps the text
      await page.click('#btn-add-exercise');
      await page.click('.ex-picker [data-x="paste"]');
      for (const [text, said] of [['wound the clock', /^There is no :::exercise block to open/],
                                  [cards.jolly + '\n' + cards.vocab, /^That is 2 exercises: paste one at a time$/]]) {
        await clearToast();
        await page.locator('.ex-picker textarea.ex-paste').fill(text);
        await page.click('.ex-picker [data-x="open"]');
        await waitToast(said, `refused: ${said.source}`);
        assert(!await page.locator('.ex-form-modal').count() && await page.locator('.ex-picker textarea.ex-paste').inputValue() === text,
               'the form does not open, and the pasted text stays in the box');
      }
      await page.click('.ex-picker [data-x="back"]');
      assert(await page.locator('.ex-picker .ex-type-grid').isVisible() && await page.locator('.ex-picker textarea.ex-paste').isHidden(), 'Back shows the exercise types again');
      await page.keyboard.press('Escape');
      assert(!await page.locator('.ex-picker').count() && (await http('GET', `/exercises/api/decks/${clock.path}`)).data.items.length === 2,
             'Escape closes it, and nothing more was added');
    }

    /* ---------------- l) browse selection, tags, transfers and cram ---------------- */
    console.log('l) browse selection, tags, transfers and cram');
    {
      const source = (await http('POST', '/exercises/api/decks', {name: 'Bulk source', lang: 'en'})).data.deck;
      const target = (await http('POST', '/exercises/api/decks', {name: 'Bulk target', lang: 'en'})).data.deck;
      const at = `/exercises/api/decks/${source.path}`;
      const flashA = (await http('POST', at + '/items', {markdown: ':::exercise flashcard\nfront: apple\nback: fruit\n:::'})).data.item;
      const flashB = (await http('POST', at + '/items', {markdown: ':::exercise flashcard\nfront: moon\nback: satellite\n:::'})).data.item;
      const scored = (await http('POST', at + '/items', {markdown: ':::exercise true-false\n- sky is blue => true\n:::'})).data.item;
      /* THE CRAM DOOR A PHONE CAN KEEP (the owner's 8, 2026-09-23: "offline
         exercises get stuck to 'loading exercises…' and never load").  This
         page asks for its exercises with a POST carrying the picked ids, and
         the Cache API refuses a request whose method is anything but GET --
         so from the day it started asking that way, a deck kept on a phone
         could never show one exercise away from the computer, however
         faithfully its pages and its scripts had been kept.  Beside the POST
         there is a GET at the same address now, answering the WHOLE deck with
         nothing in the address to vary, which is exactly what makes it
         keepable: lib/offline.py names it in the deck's record, and
         static/decks.js asks for it when the POST goes unanswered. */
      const post = (await http('POST', at + '/cram', {ids: [flashA.id, flashB.id]}));
      const whole = await http('GET', at + '/cram');
      const picked = await http('GET', at + '/cram?ids=' + flashA.id);
      const junk = await http('GET', at + '/cram?ids=nothing-like-an-id');
      eq([post.status, whole.status, picked.status, junk.status], [200, 200, 200, 200],
         'the cram address answers a GET as well as a POST');
      eq((whole.data.cards || []).map(c => c.item.id).sort(),
         ((await http('GET', at)).data.items || []).map(i => i.id).sort(),
         'the GET asked bare is the whole deck — one address, the same every time, which is ' +
         'the only shape a cache can hold');
      const sameCard = id => JSON.stringify((post.data.cards || []).find(c => c.item.id === id)) ===
                             JSON.stringify((whole.data.cards || []).find(c => c.item.id === id));
      assert(sameCard(flashA.id) && sameCard(flashB.id),
             'and a card out of it is the very card the POST answers with, summary and rendered ' +
             'html alike: the page cannot tell which door answered it');
      eq((picked.data.cards || []).map(c => c.item.id), [flashA.id],
         'asked with a selection it answers that selection');
      eq((junk.data.cards || []).length, (whole.data.cards || []).length,
         'and a selection naming nothing falls back to the whole deck rather than refusing — a ' +
         'page asking this way has already lost its first choice');
      eq((await http('GET', '/exercises/api/decks/english/no-such-deck/cram')).status, 404,
         'a deck that is not there is still not there');

      await page.goto(url(`/exercises/deck/${source.path}/`));
      await page.waitForSelector('.dk-row');
      assert((await page.locator('.dk-selection-hint').textContent()).includes('Shift-click'),
             'the browse page explains range selection visibly');
      await page.locator('.dk-row .dk-select').first().check();
      await page.locator('.dk-row .dk-select').last().click({modifiers: ['Shift']});
      assert(await page.locator('.dk-select:checked').count() === 3,
             'Shift-click selects the visible range of exercise checkboxes');
      await page.locator('.dk-row .dk-select').last().uncheck();
      await page.locator('.dk-row .dk-select').first().click({modifiers: ['Shift']});
      assert(await page.locator('.dk-select:checked').count() === 0,
             'Shift-click deselects a range in reverse order');
      await page.locator('.dk-row .dk-select').first().check();
      await page.locator('.dk-row').last().locator('.dk-row-toggle').click({modifiers: ['Shift']});
      assert(await page.locator('.dk-select:checked').count() === 3
             && await page.locator('.dk-row.open').count() === 0,
             'Shift-clicking a row selects the range without opening its preview');
      await page.selectOption('#browse-type', 'flashcard');
      await page.locator('.dk-row .dk-select').first().uncheck();
      await page.locator('.dk-row .dk-select').last().click({modifiers: ['Shift']});
      assert(await page.locator('.dk-select:checked').count() === 0
             && await page.locator('#browse-selected').textContent() === '1 selected',
             'range deselection leaves filtered-out exercises selected');
      await page.selectOption('#browse-type', '');
      await page.click('#btn-select-all');
      assert(await page.locator('.dk-select:checked').count() === 3 && await page.locator('#browse-selected').textContent() === '3 selected',
             'Select all selects every exercise');
      await page.click('#btn-bulk-new');
      await page.click('.dk-modal button:text-is("Set to new")');
      await page.waitForFunction(() => !document.querySelector('.dk-modal'));
      assert(await page.locator('.dk-select:checked').count() === 3,
             'setting selected exercises to new keeps them selected');
      await page.click('#btn-bulk-add-tag');
      await page.fill('.dk-modal input[type=text]', 'Old');
      await page.click('.dk-modal button:text-is("Add tag")');
      await page.waitForFunction(() => [...document.querySelectorAll('.dk-item-tags')].every(e => e.textContent.includes('old')));
      assert(await page.locator('.dk-select:checked').count() === 3, 'adding a tag keeps the three exercises selected');
      await page.click('#btn-bulk-remove-tag');
      await page.click('.dk-modal button:text-is("Remove tag")');
      await page.waitForFunction(() => [...document.querySelectorAll('.dk-item-tags')].every(e => !e.textContent.includes('old')));
      assert(await page.locator('.dk-select:checked').count() === 3, 'removing a tag keeps the same selection');
      await page.click('#btn-bulk-add-tag');
      await page.fill('.dk-modal input[type=text]', 'New');
      await page.click('.dk-modal button:text-is("Add tag")');
      await page.waitForFunction(() => [...document.querySelectorAll('.dk-item-tags')].every(e => e.textContent.includes('new')));
      await page.selectOption('#browse-tag', 'new');
      assert(await page.locator('.dk-row').count() === 3, 'the tag filter finds the tagged exercises');
      await page.selectOption('#browse-tag', '');
      await page.click('#btn-deselect-all');
      assert(await page.locator('.dk-select:checked').count() === 0, 'Deselect all clears selection');
      await page.selectOption('#browse-type', 'flashcard');
      await page.click('#btn-select-shown');
      assert(await page.locator('.dk-select:checked').count() === 2 && await page.locator('#browse-selected').textContent() === '2 selected',
             'Select shown selects only exercises matching the current filter');
      // Deselect shown, its opposite: everything selected, then the shown
      // flashcards let go -- and the rest, which the filter hides, kept
      await page.selectOption('#browse-type', '');
      await page.click('#btn-select-all');
      const every = await page.locator('.dk-row').count();
      await page.selectOption('#browse-type', 'flashcard');
      await page.click('#btn-deselect-shown');
      assert(await page.locator('.dk-select:checked').count() === 0
             && await page.locator('#browse-selected').textContent() === `${every - 2} selected`,
             'Deselect shown lets go of the exercises the filter shows, and only of them');
      await page.selectOption('#browse-type', '');
      assert(await page.locator('.dk-select:checked').count() === every - 2,
             'what the filter hid is still selected once it is cleared');
      await page.selectOption('#browse-type', '');
      await page.click('#btn-deselect-all');
      await page.click('#btn-select-tag');
      await page.click('.dk-modal button:text-is("Select matching")');
      assert(await page.locator('.dk-select:checked').count() === 3, 'Select by tag picks every matching exercise');
      await page.locator(`.dk-row[data-id="${scored.id}"] .dk-select`).uncheck();
      assert(await page.locator('.dk-select:checked').count() === 2, 'one exercise can be deselected separately');
      await page.click('#btn-bulk-copy');
      await page.selectOption('.dk-modal select', target.path);
      await page.click('.dk-modal button:text-is("Copy to deck")');
      await page.waitForFunction(() => document.querySelector('#browse-selected').textContent === '2 selected');
      assert((await http('GET', `/exercises/api/decks/${target.path}`)).data.items.length === 2
             && await page.locator('.dk-select:checked').count() === 2,
             'copying the group adds two fresh cards and keeps them selected here');
      await page.locator(`.dk-row[data-id="${scored.id}"] [data-x="move"]`).click();
      await page.selectOption('.dk-modal select', target.path);
      await page.click('.dk-modal button:text-is("Move to deck")');
      await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 2);
      assert((await http('GET', `/exercises/api/decks/${target.path}`)).data.items.length === 3,
             'the row Move to deck action removes it here and adds it there');
      const boolean = (await http('POST', at + '/items', {markdown: ':::exercise true-false\n- sky is blue => true\n:::'})).data.item;
      const matching = (await http('POST', at + '/items', {markdown: ':::exercise match-translations\n- cat => feline\n- dog => canine\n:::'})).data.item;
      await page.reload();
      await page.waitForFunction(() => document.querySelectorAll('.dk-row').length === 4);
      await page.locator(`.dk-row[data-id="${boolean.id}"] .dk-select`).check();
      await page.locator(`.dk-row[data-id="${matching.id}"] .dk-select`).check();
      assert(await page.locator('#browse-selected').textContent() === '4 selected',
             'cram accepts flashcards and scored exercises in the same selection');
      await Promise.all([page.waitForURL(url(`/exercises/deck/${source.path}/cram`)), page.click('#btn-cram')]);
      await page.waitForSelector('#cram-stage .exercise');
      const seen = [];
      let wrongFlash = '';
      for (let n = 0; n < 7; n++) {
        const ex = page.locator('#cram-stage .exercise');
        const subtype = await ex.getAttribute('data-subtype');
        seen.push(subtype);
        if (subtype === 'flashcard') {
          const front = await page.locator('#cram-stage .ex-card-front').textContent();
          await page.click('#cram-show');
          assert(await page.locator('#cram-stage .ex-flashcard.flipped').count() === 1,
                 'cram reveals a flashcard answer');
          await page.waitForSelector('#cram-wrong:not([hidden])');
          if (!wrongFlash)
            assert(await page.locator('#cram-skip').isVisible(), 'a turned card not graded yet can still be skipped');
          if (!wrongFlash) {
            wrongFlash = front;
            await page.click('#cram-wrong');
          } else {
            if (n >= 4) assert(front === wrongFlash, 'the wrong flashcard returns at the end of cram');
            await page.click('#cram-correct');
          }
        } else if (subtype === 'true-false') {
          await page.click(`#cram-stage .ex-option[data-correct="${n < 4 ? '0' : '1'}"]`);
          assert(await page.locator('#cram-skip').isVisible(), 'an exercise not checked yet has Skip');
          await page.click('#cram-check');
          assert(await page.locator('#cram-result').textContent() === (n < 4 ? 'Not quite' : 'Correct'),
                 'cram checks a scored choice again after a wrong answer');
          assert(!(await page.locator('#cram-skip').isVisible()), 'checked, it is answered: no Skip, only Next');
          await page.click('#cram-next');
        } else if (subtype === 'match-translations') {
          if (n >= 4) {
            const drops = page.locator('#cram-stage .ex-match-drop');
            const wants = await drops.evaluateAll(ds => ds.map(d => d.dataset.answer));
            for (let i = 0; i < wants.length; i++) {
              await page.locator(`#cram-stage .ex-item[data-item="${wants[i]}"]`).click();
              await drops.nth(i).click();
            }
          }
          await page.click('#cram-check');
          if (n < 4) {
            await page.waitForSelector('#cram-solution:not([hidden])');
            assert(await page.locator('#cram-result').textContent() === 'Not quite'
                   && await page.locator('#cram-solution .ex-match-drop .ex-item').count() === 2,
                   'cram shows the correct matching answer after an incomplete response');
          } else {
            assert(await page.locator('#cram-result').textContent() === 'Correct',
                   'the matching exercise can be solved when it returns');
          }
          await page.click('#cram-next');
        }
        if (n === 3) assert(await page.locator('#cram-progress').textContent() === '5 of 7',
                            'wrong exercises return after the original four');
      }
      assert(await page.locator('#cram-done').isVisible()
             && seen.filter(x => x === 'flashcard').length === 3
             && seen.filter(x => x === 'true-false').length === 2
             && seen.filter(x => x === 'match-translations').length === 2,
             'cram ends after every wrong exercise has been answered correctly');
      // ---- the end says how it went, and names what to look at again
      eq(await page.locator('#cram-tally').textContent(), '4 exercises: 1 right the first time, 3 wrong at least once.',
         'the end: how many right the first time, how many wrong at least once');
      const listed = sel => page.evaluate(sel => [...document.querySelectorAll(sel + ' .dk-cram-item')]
        .map(b => [b.querySelector('.ex-kicker').textContent, b.querySelector('.dk-cram-meta')?.textContent || '']), sel);
      const wrongOnes = await listed('#cram-wrong-list');
      eq(wrongOnes.map(w => w[1]), ['wrong once, then right', 'wrong once, then right', 'wrong once, then right'],
         'the three answered wrong, each once and then right');
      eq(wrongOnes.map(w => w[0]).sort(), ['Flashcard', 'Match translations', 'True or false'].sort(),
         'they are the flashcard, the choice and the match');
      assert(await page.locator('#cram-skipped-list').isHidden(), 'nothing skipped, no list of skipped ones');
      await page.click('#cram-wrong-list .dk-cram-item >> nth=0');
      await page.waitForSelector('#cram-wrong-list .dk-cram-solved:not([hidden]) .exercise');
      eq(await page.locator('#cram-wrong-list .dk-cram-item >> nth=0').getAttribute('aria-expanded'), 'true',
         'a click on one shows it solved under it');
      // ---- the wrong ones again, one of them skipped
      await page.click('#cram-wrong-list [data-x="again"]');
      await page.waitForFunction(() => document.querySelector('#cram-progress').textContent === '1 of 3');
      assert(await page.locator('#cram-done').isHidden(), 'Cram these again: a practice of the three');
      const skippedKind = await page.locator('#cram-stage .exercise').getAttribute('data-subtype');
      await page.click('#cram-skip');
      for (let n = 0; n < 2; n++) {
        const ex = page.locator('#cram-stage .exercise');
        const subtype = await ex.getAttribute('data-subtype');
        if (subtype === 'flashcard') {
          await page.click('#cram-show');
          await page.waitForSelector('#cram-correct:not([hidden])');
          await page.click('#cram-correct');
        } else {
          if (subtype === 'true-false') await page.click('#cram-stage .ex-option[data-correct="1"]');
          else {
            const drops = page.locator('#cram-stage .ex-match-drop');
            const wants = await drops.evaluateAll(ds => ds.map(d => d.dataset.answer));
            for (let i = 0; i < wants.length; i++) {
              await page.locator(`#cram-stage .ex-item[data-item="${wants[i]}"]`).click();
              await drops.nth(i).click();
            }
          }
          await page.click('#cram-check');
          await page.click('#cram-next');
        }
      }
      await page.waitForSelector('#cram-done:not([hidden])');
      eq(await page.locator('#cram-tally').textContent(), '3 exercises: 2 right the first time, 1 skipped.',
         'the end: two right, one skipped');
      assert(await page.locator('#cram-wrong-list').isHidden(), 'nothing wrong this time, no list of wrong ones');
      const skippedOnes = await listed('#cram-skipped-list');
      eq(skippedOnes.length, 1, 'the skipped one, named');
      eq(await page.locator('#cram-skipped-list .ex-kicker').first().textContent(),
         {'flashcard': 'Flashcard', 'true-false': 'True or false', 'match-translations': 'Match translations'}[skippedKind],
         'and it is the one skipped');
      assert((await http('GET', at)).data.items.every(i => i.schedule.state === 'new' && i.reps === 0),
             'cram does not change scheduling or review counts');
      await page.click('#cram-done .dk-back');
      await page.waitForSelector('.dk-row');
      assert(await page.locator('.dk-select:checked').count() === 4, 'returning from cram preserves the selection');
      await page.click('#btn-bulk-delete');
      await page.click('.dk-modal button:text-is("Delete selected")');
      await page.waitForSelector('#browse-empty:not([hidden])');
      assert((await http('GET', at)).data.items.length === 0 && await page.locator('#browse-selected').textContent() === '0 selected',
             'bulk delete removes selected exercises and clears the selection');
      assert(flashA.id !== flashB.id, 'the two cram flashcards were distinct items');
      await http('POST', at + '/items', {markdown: ':::exercise flashcard\nfront: sun\nback: star\n:::'});
      await http('POST', at + '/items', {markdown: ':::exercise flashcard\nfront: earth\nback: planet\n:::'});
      await page.reload();
      await page.waitForSelector('.dk-row');
      await page.click('#btn-select-all');
      await page.click('#btn-bulk-move');
      await page.selectOption('.dk-modal select', target.path);
      await Promise.all([page.waitForURL(u => u.pathname === `/exercises/deck/${target.path}/`),
                         page.click('.dk-modal button:text-is("Move to deck")')]);
      await page.waitForSelector('.dk-row');
      assert(await page.locator('.dk-select:checked').count() === 2,
             'bulk Move opens the destination with the moved group still selected');
      await page.click('#btn-bulk-add-tag');
      await page.fill('.dk-modal input[type=text]', 'moved');
      await page.click('.dk-modal button:text-is("Add tag")');
      await page.waitForFunction(() => [...document.querySelectorAll('.dk-row.selected .dk-item-tags')].every(e => e.textContent.includes('moved')));
      assert(await page.locator('.dk-select:checked').count() === 2,
             'the moved selection can be tagged immediately in the destination');
    }

    assert(errors.length === 0, 'no page errors, console errors or failed requests' + (errors.length ? ':\n    ' + errors.join('\n    ') : ''));
    assert(dialogs.length === 2, 'no other dialog was opened');
  } finally {
    await ctx.close();
    try { proc.kill('SIGTERM'); } catch (_) { /* already gone */ }
    await proc.status;
    await drained.catch(() => {});
    await Deno.remove(tmp, {recursive: true}).catch(() => {});
  }
  // after the server is gone: its log, its temp tree, the owner's stores
  if (/Traceback/.test(log)) throw Error(`FAIL (${mode}): a traceback in the server log:\n` + log);
  assert(!(await exists(tmp)), 'the temporary tree is removed');
  assert(await snapshot(root + '/exercises', 6) === owner.exercises && await snapshot(root + '/markdown/library', 3) === owner.library,
         "the real exercises/ and markdown/library/ are untouched");
  console.log(`${mode}: ${passed} checks passed\n`);
  return passed;
}

const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
try {
  let total = 0;
  for (const mode of modes) total += mode === 'e2e' ? await endToEnd(browser) : await suite(browser, mode);
  console.log(`exercise deck pages passed (${modes.join(' + ')}: ${total} checks)`);
} finally {
  await browser.close();
}
