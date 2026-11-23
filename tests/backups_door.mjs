// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of Settings -> Backups (TO-DO §13.19), against Parseh's REAL handler, page and routes on a temporary
// tree (tests/backups_harness.py: every store of config/ and every shelf points at the tree, never the checkout's):
//   a) the hub has the door; the page says "never backed up" before anything is taken
//   b) Backup your settings and Backup everything download zips; the day becomes "today" on this page and on the
//      decks' and the studio's own pages (lib/backupday.js)
//   c) after a change, Load from backup of the settings: the plan says what differs and by which rule (a newer
//      reading place stays, a flag removed since stays removed), offers the prompt with no rule of its own, and
//      takes the backup's only where it is picked
//   d) a settings backup with one file damaged is refused in words, and nothing changes
//   e) a new computer (every shelf and store emptied): Load everything puts back the books, the videos, the studio,
//      the decks, the Anki card store, the clip tray and the settings -- a language of the person's with its file
//   f) a damaged backup of everything is refused whole: nothing is written
//   g) a device let in sees the page and the days, a lock where loading is, and the server refuses it a load
//   h) 390 px wide: no sideways scroll
//   CHROME_BIN=... PARSEH_PYTHON=python3 deno run --allow-all tests/backups_door.mjs
import {chromium} from 'npm:playwright-core@1.52.0';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
let passed = 0;
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(`FAIL: ${m} (got ${JSON.stringify(a)}, want ${JSON.stringify(b)})`); assert(true, m); };
const has = (t, p, m) => { if (!String(t).includes(p)) throw Error(`FAIL: ${m} (wanted ${JSON.stringify(p)} in ${JSON.stringify(String(t).slice(0, 600))})`); assert(true, m); };
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

async function startHarness(args) {
  const proc = new Deno.Command(python, {args: [root + '/tests/backups_harness.py', ...args], cwd: root,
    stdin: 'piped', stdout: 'piped', stderr: 'piped'}).spawn();
  const log = [];
  (async () => {
    const r = proc.stderr.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) { const {value, done} = await r.read(); if (done) break; log.push(value); }
  })();
  const lines = [], waiting = [];
  let buf = '';
  const reader = proc.stdout.pipeThrough(new TextDecoderStream()).getReader();
  (async () => {
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += value;
      let at;
      while ((at = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, at); buf = buf.slice(at + 1);
        if (waiting.length) waiting.shift()(line); else lines.push(line);
      }
    }
  })();
  const next = () => new Promise(res => { if (lines.length) res(lines.shift()); else waiting.push(res); });
  const ready = await Promise.race([next(), sleep(90000).then(() => 'TIMEOUT')]);
  if (!ready.startsWith('READY ')) throw Error('harness did not start: ' + ready + '\n' + log.join(''));
  const writer = proc.stdin.getWriter();
  const enc = new TextEncoder();
  const send = async cmd => {
    await writer.write(enc.encode(JSON.stringify(cmd) + '\n'));
    const got = await next();
    if (!got.startsWith('OK')) throw Error('harness: ' + got + '\n' + log.join(''));
    return got.length > 3 ? JSON.parse(got.slice(3)) : null;
  };
  return {proc, info: JSON.parse(ready.slice(6)), send, log,
          stop: async () => { try { proc.kill('SIGTERM'); } catch (_) {} await proc.status; }};
}

const work = await Deno.makeTempDir({prefix: 'parseh-backups-door-'});
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), args: ['--no-sandbox']});
let h = null, phone = null;
try {
  h = await startHarness([]);
  const base = `http://127.0.0.1:${h.info.port}`;
  const ctx = await browser.newContext({acceptDownloads: true, viewport: {width: 1280, height: 900}});
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await h.send({what: 'seed'});
  const before = await h.send({what: 'look'});

  console.log('a) the door, and no backup yet');
  await page.goto(base + '/settings/');
  assert(await page.locator('a.door[href="/settings/backups/"]').count() === 1, 'the Settings hub has a Backups door');
  await page.goto(base + '/settings/backups/');
  has(await page.locator('[data-backup-day="settings"]').first().textContent(), 'never backed up',
      'the settings were never backed up');

  console.log('b) the two backups download, and the day is said');
  async function download(selector, name) {
    const [d] = await Promise.all([page.waitForEvent('download'), page.click(selector)]);
    const path = `${work}/${name}`;
    await d.saveAs(path);
    return {path, suggested: d.suggestedFilename()};
  }
  const settingsZip = await download('a[data-get="settings"]', 'settings.zip');
  assert(/^parseh-settings-backup-\d{8}-\d{4}\.zip$/.test(settingsZip.suggested), 'the settings backup is named by its day');
  const everythingZip = await download('a[data-get="everything"]', 'everything.zip');
  assert(/^parseh-everything-\d{8}-\d{4}\.zip$/.test(everythingZip.suggested), 'the backup of everything is named by its day');
  // what is in it, read raw
  const names = new TextDecoder().decode(await new Deno.Command('unzip', {args: ['-Z1', everythingZip.path], stdout: 'piped'}).output().then(o => o.stdout));
  for (const n of ['parseh-everything.json', 'settings.zip', 'books.zip', 'videos.zip', 'studio.zip', 'decks.zip',
                   'cards/english/market/deck.json', 'cards/notetypes.json', 'clips/hello-abc123.png'])
    has(names, n, 'the backup of everything holds ' + n);
  assert(!names.includes('cards/build/'), "the card store's build/ is left out");
  const inner = new TextDecoder().decode(await new Deno.Command('unzip', {args: ['-Z1', settingsZip.path], stdout: 'piped'}).output().then(o => o.stdout));
  for (const n of ['config/prefs.json', 'config/prompts.json', 'config/languages.json', 'lang/eu.tex', 'docs/eu.md'])
    has(inner, n, 'the settings backup holds ' + n);
  assert(!inner.includes('network.json'), 'the settings backup leaves out network.json');
  const dayOf = async (k, want) => until(async () => {
    await page.evaluate(() => window.ParsehBackupDay && window.ParsehBackupDay.fill());
    await sleep(250);
    return (await page.locator(`[data-backup-day="${k}"]`).first().textContent()).includes(want);
  }, 'the day of ' + k + ' says ' + want);
  await page.reload();
  for (const k of ['settings', 'everything', 'book', 'video', 'studio', 'decks']) await dayOf(k, 'today');
  assert(true, 'every shelf says its last backup was today (the backup of everything holds them all)');
  await page.goto(base + '/exercises/');
  await dayOf('decks', 'last backup: today');
  assert(true, "the decks' own page says the day of the last backup");
  await page.goto(base + '/studio/');
  await dayOf('studio', 'last backup: today');
  assert(true, "the studio's Backup menu says the day of the last backup");

  console.log('c) loading the settings merges them');
  await h.send({what: 'change'});
  await page.goto(base + '/settings/backups/');
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('button[data-load="settings"]')]);
  await chooser.setFiles(settingsZip.path);
  await until(() => page.locator('[data-plan] tr[data-row]').count(), 'the plan is shown');
  const plan = await page.locator('[data-plan]').innerText();
  has(plan, 'the later change wins', 'the reading place is decided by the later change');
  has(plan, 'stays removed', 'a flag removed after the backup stays removed');
  assert(await page.locator('[data-plan] tr[data-row^="prompts.json:"] input[value="backup"]').count() === 1,
         'the prompt that differs is offered, with no rule of its own');
  assert(await page.locator('[data-plan] tr[data-row^="prompts.json:"] input[value="mine"]').isChecked(),
         'yours is kept unless the backup’s is picked');
  has(await page.locator('[data-said="settings"]').textContent(), 'Nothing is loaded until', 'nothing is loaded yet');
  eq((await h.send({what: 'look'})).prompts.brief, 'Answer at length.', 'reading the backup wrote nothing');
  await page.check('[data-plan] tr[data-row^="prompts.json:"] input[value="backup"]');
  await page.click('[data-plan] button[data-apply]');
  await until(async () => (await page.locator('[data-said="settings"]').textContent()).startsWith('Loaded'), 'loaded');
  const after = await h.send({what: 'look'});
  eq(after.prompts.brief, 'Answer in one line.', 'the prompt picked is the backup’s');
  eq(after.places['/books/english/mini-en/reader/'].i, 9, 'the newer reading place stays');
  eq(after.flags.length, 1, 'the flag removed since stays removed, the other is there');
  eq(after.analysis.lookup, 'assist', 'a choice not picked stays yours');

  console.log('d) a damaged settings backup is refused');
  await h.send({what: 'damage', from: settingsZip.path, to: `${work}/settings-bad.zip`, member: 'config/prompts.json'});
  const [c2] = await Promise.all([page.waitForEvent('filechooser'), page.click('button[data-load="settings"]')]);
  await c2.setFiles(`${work}/settings-bad.zip`);
  await until(async () => (await page.locator('[data-said="settings"]').textContent()).includes('damaged'),
              'the damaged backup is refused');
  has(await page.locator('[data-said="settings"]').textContent(), 'config/prompts.json', 'the refusal names the file');
  eq(await h.send({what: 'look'}), after, 'nothing changed');

  console.log('e) a new computer: load everything');
  await h.send({what: 'wipe'});
  const bare = await h.send({what: 'look'});
  eq([bare.books, bare.videos, bare.docs, bare.decks, bare.anki, bare.clips, bare.languages],
     [[], [], [], [], [], [], []], 'the new computer is empty');
  await page.goto(base + '/settings/backups/');
  const [c3] = await Promise.all([page.waitForEvent('filechooser'), page.click('button[data-load="everything"]')]);
  await c3.setFiles(everythingZip.path);
  await until(async () => (await page.locator('[data-said="everything"]').textContent()).includes('Loaded from a backup'),
              'everything is loaded', 90000);
  const said = await page.locator('[data-said="everything"]').innerText();
  for (const part of ['settings', 'books', 'videos', 'studio', 'decks', 'cards', 'clips'])
    has(said, part + ':', 'the answer says what became of ' + part);
  assert(!said.includes('not loaded'), 'no part was refused (' + said.replace(/\n/g, ' | ') + ')');
  const moved = await h.send({what: 'look'});
  eq(moved.books, before.books, 'the books came back');
  eq(moved.videos, before.videos, 'the videos came back');
  eq(moved.docs, before.docs, 'the studio documents came back');
  eq(moved.decks, before.decks, 'the exercise decks came back');
  eq(moved.anki, before.anki.filter(n => !n.startsWith('build/')), 'the Anki card store came back, without its build/');
  eq(moved.clips, before.clips, 'the clip tray came back');
  eq(moved.prompts, {brief: 'Answer in one line.'}, 'the prompts came back');
  eq(moved.places, before.places, 'the reading places came back');
  eq(moved.flags, before.flags, 'the flags to review later came back');
  eq(moved.settings, before.settings, 'the settings that follow you and the names of the levels came back');
  eq([moved.languages, moved.eu_tex, moved.eu_known], [['eu'], true, true],
     'the language of the person’s came back with its LaTeX file, and is known at once');
  assert(!moved.config.includes('network.json'), 'no network.json came with it');

  console.log('f) a damaged backup of everything is refused whole');
  await h.send({what: 'wipe'});
  await h.send({what: 'damage', from: everythingZip.path, to: `${work}/everything-bad.zip`, member: 'clips/hello-abc123.png'});
  const [c4] = await Promise.all([page.waitForEvent('filechooser'), page.click('button[data-load="everything"]')]);
  await c4.setFiles(`${work}/everything-bad.zip`);
  await until(async () => (await page.locator('[data-said="everything"]').textContent()).includes('damaged'),
              'the damaged backup is refused', 60000);
  has(await page.locator('[data-said="everything"]').textContent(), 'nothing was loaded', 'it says nothing was loaded');
  const still = await h.send({what: 'look'});
  eq([still.books, still.docs, still.languages, still.config.filter(n => n !== 'backups.json')], [[], [], [], []],
     'nothing at all was written');

  console.log('h) 390 px: no sideways scroll');
  for (const scheme of ['light', 'dark']) {
    const m = await browser.newContext({viewport: {width: 390, height: 800}, colorScheme: scheme});
    const mp = await m.newPage();
    await mp.goto(base + '/settings/backups/');
    eq(await mp.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'no sideways scroll, ' + scheme);
    await m.close();
  }
  eq(errors, [], 'no script error on the pages');

  console.log('g) a device let in');
  phone = await startHarness(['--as-phone']);
  const pbase = `http://127.0.0.1:${phone.info.port}`;
  const pp = await ctx.newPage();
  await pp.goto(pbase + '/settings/backups/');
  assert(await pp.locator('button[data-load="settings"]').isDisabled(), 'the settings load button is shut');
  assert(await pp.locator('button[data-load="everything"]').isDisabled(), 'the everything load button is shut');
  has(await pp.locator('.lockline').first().textContent(), 'computer only', 'a lock says why');
  assert(await pp.locator('a[data-get="settings"]').count() === 1, 'taking a backup is still offered');
  const refused = await pp.evaluate(async () => {
    const r = await fetch('/settings/api/backups/settings/read', {method: 'POST', body: 'x'});
    return [r.status, (await r.json()).error];
  });
  eq(refused[0], 403, 'the server refuses a load from a device let in');
  has(refused[1], 'computer', 'in the setting’s own words');
} finally {
  await browser.close();
  if (h) await h.stop();
  if (phone) await phone.stop();
  await Deno.remove(work, {recursive: true}).catch(() => {});
}
console.log(`backups_door: ${passed} checks passed`);
